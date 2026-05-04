"""Append-only JSONL trajectory recorder with multi-process safety (TRJ-01 / D-85, D-86).

Critical (D-86): Linux flock releases ALL locks when ANY fd to the file is closed.
The recorder keeps an open fd per node_id in _FD_CACHE — never open-close per event.
"""
from __future__ import annotations

import atexit
import fcntl
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

from automil.trajectory.redactor import redact_event, apply_size_cap
from automil.trajectory.rotation import RotationManager
from automil.trajectory.schema import SCHEMA_VERSION, validate_event, TrajectorySchemaError

logger = logging.getLogger(__name__)

# Process-level fd cache — keyed by str(trajectory_path), value is open fd (int)
_FD_CACHE: dict[str, int] = {}
# Per-node RLock — prevents intra-process re-entry deadlock
_NODE_LOCKS: dict[str, threading.RLock] = {}
_DICT_LOCK = threading.Lock()  # protects _FD_CACHE + _NODE_LOCKS dicts

_DEFAULT_ROTATION = RotationManager()


def _get_node_lock(node_id: str) -> threading.RLock:
    with _DICT_LOCK:
        if node_id not in _NODE_LOCKS:
            _NODE_LOCKS[node_id] = threading.RLock()
        return _NODE_LOCKS[node_id]


def _get_or_open_fd(path: Path) -> int:
    """Return cached fd or open a new O_APPEND fd and cache it."""
    key = str(path)
    with _DICT_LOCK:
        if key not in _FD_CACHE:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            _FD_CACHE[key] = fd
        return _FD_CACHE[key]


def _close_fd_for_path(path: Path) -> None:
    """Close and evict the fd for a given path (called on rotation)."""
    key = str(path)
    with _DICT_LOCK:
        fd = _FD_CACHE.pop(key, None)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _close_all_fds() -> None:
    """atexit handler: close all cached fds on process exit (D-86)."""
    with _DICT_LOCK:
        for fd in list(_FD_CACHE.values()):
            try:
                os.close(fd)
            except OSError:
                pass
        _FD_CACHE.clear()


atexit.register(_close_all_fds)


def _append_line(fd: int, data: dict) -> None:
    """Atomically append one JSON line. fd MUST be opened with O_APPEND."""
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        line = json.dumps(data, ensure_ascii=False) + "\n"
        os.write(fd, line.encode("utf-8"))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _write_metadata_header(
    fd: int,
    runtime: str,
    automil_version: str,
) -> None:
    """Write the first-line metadata header per D-80."""
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "runtime": runtime,
        "runtime_version": os.environ.get("AUTOMIL_RUNTIME_VERSION", "unknown"),
        "tool_schema_version": os.environ.get("AUTOMIL_TOOL_SCHEMA_VERSION", "unknown"),
        "automil_version": automil_version,
        "automil_runtime_env": {
            "AUTOMIL_RUNTIME": os.environ.get("AUTOMIL_RUNTIME", runtime),
            "AUTOMIL_GPU": os.environ.get("AUTOMIL_GPU", ""),
        },
    }
    _append_line(fd, metadata)


def record_event(
    *,
    node_id: str,
    event: dict,
    archive_dir: Path,
    automil_version: Optional[str] = None,
    runtime: Optional[str] = None,
    rotation_manager: Optional[RotationManager] = None,
) -> bool:
    """Append one event to archive/<node_id>/trajectory.jsonl (D-85).

    Auto-creates the file with first-line metadata if absent.
    Returns False (and logs WARNING) on any I/O / redaction error — never raises.
    Thread-safe via per-node-id RLock + LOCK_EX flock.
    """
    try:
        if automil_version is None:
            try:
                from automil import __version__ as automil_version  # type: ignore[assignment]
            except Exception:
                automil_version = "unknown"
        if runtime is None:
            runtime = os.environ.get("AUTOMIL_RUNTIME", "unknown")
        if rotation_manager is None:
            rotation_manager = _DEFAULT_ROTATION

        traj_path = archive_dir / node_id / "trajectory.jsonl"
        traj_path.parent.mkdir(parents=True, exist_ok=True)

        lock = _get_node_lock(node_id)
        with lock:
            # Rotation check before write
            if not rotation_manager.check_and_rotate(traj_path, _FD_CACHE):
                logger.critical(
                    "Trajectory hard limit reached for node %s; event dropped", node_id
                )
                return False

            # If rotation renamed the file, evict stale fd
            if str(traj_path) in _FD_CACHE and not traj_path.exists():
                _close_fd_for_path(traj_path)

            is_new = not traj_path.exists()
            fd = _get_or_open_fd(traj_path)

            # Write metadata header on first creation
            if is_new:
                _write_metadata_header(fd, runtime, automil_version)

            # Validate, redact, cap, then append
            try:
                validate_event(event)
            except TrajectorySchemaError as exc:
                logger.warning("Event schema validation failed: %s; skipping event", exc)
                return False

            redacted = redact_event(event)
            capped = apply_size_cap(redacted)
            _append_line(fd, capped)
            return True

    except Exception as exc:
        logger.warning(
            "record_event failed for node %s: %s; event dropped", node_id, exc
        )
        return False


def read_metadata(path: Path) -> dict:
    """Read the first-line metadata from a trajectory.jsonl file.

    Raises TrajectorySchemaError if schema_version is trajectory-v2 or later (D-80).
    Returns metadata dict for trajectory-v1.* (unknown fields tolerated).
    """
    from automil.trajectory.schema import TrajectorySchemaError  # avoid circular at module level
    line = path.read_text(encoding="utf-8").splitlines()[0]
    meta = json.loads(line)
    version = meta.get("schema_version", "")
    if version.startswith("trajectory-v2") or (
        version and not version.startswith("trajectory-v1")
        and not version.startswith("trajectory-v")
    ):
        raise TrajectorySchemaError(
            f"Unsupported schema_version '{version}'; "
            "this reader supports trajectory-v1.* only (D-80)"
        )
    return meta
