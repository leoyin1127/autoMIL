"""Trajectory rotation manager — 5 MB soft / 50 MB hard (TRJ-03 / D-84).

Soft rotation: atomic os.rename to trajectory.<n>.jsonl + copy metadata header.
Hard rotation: return False (log CRITICAL) — never raises, never kills experiment.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SOFT_DEFAULT = 5 * 1024 * 1024   # 5 MB
_HARD_DEFAULT = 50 * 1024 * 1024  # 50 MB


def _next_rotation_index(traj_path: Path) -> int:
    """Return the next free integer N for trajectory.<N>.jsonl.

    Scans existing siblings: trajectory.1.jsonl, trajectory.2.jsonl, ...
    Returns the smallest N >= 1 that does not already exist as a file.
    """
    parent = traj_path.parent
    n = 1
    while (parent / f"trajectory.{n}.jsonl").exists():
        n += 1
    return n


def _read_first_line(path: Path) -> Optional[bytes]:
    """Read the first line of path as raw bytes. Returns None on any error."""
    try:
        with open(path, "rb") as f:
            return f.readline()
    except Exception as exc:
        logger.warning("Could not read first line from %s: %s", path, exc)
        return None


@dataclass(frozen=True)
class RotationManager:
    """Manages trajectory file rotation by size threshold (D-84).

    soft_bytes: rotate to trajectory.<n>.jsonl when size >= soft_bytes
    hard_bytes: refuse new events when size >= hard_bytes (log CRITICAL, return False)
    """
    soft_bytes: int = _SOFT_DEFAULT
    hard_bytes: int = _HARD_DEFAULT

    def check_and_rotate(self, path: Path, fd_cache: dict) -> bool:
        """Check size thresholds and rotate if needed.

        Returns True  — file is ready for writing (including after rotation).
        Returns False — hard limit exceeded; caller should drop the event.
        Soft-fail: any I/O error is caught and logged; returns True (safe pass-through).
        """
        try:
            if not path.exists():
                return True  # new file — rotation not needed

            size = path.stat().st_size

            # Hard limit: refuse new events
            if size >= self.hard_bytes:
                logger.critical(
                    "Trajectory hard limit (%d bytes) reached at %s; "
                    "refusing new events. Use `automil trajectory export` to archive.",
                    self.hard_bytes, path,
                )
                return False

            # Soft limit: rotate to trajectory.<n>.jsonl
            if size >= self.soft_bytes:
                return self._do_soft_rotate(path, fd_cache)

            return True

        except Exception as exc:
            logger.warning(
                "RotationManager.check_and_rotate failed for %s: %s; "
                "allowing write (safe pass-through)",
                path, exc,
            )
            return True

    def _do_soft_rotate(self, path: Path, fd_cache: dict) -> bool:
        """Perform atomic soft rotation: rename trajectory.jsonl → trajectory.<n>.jsonl.

        After rename:
        - The old fd (if cached) is closed and evicted.
        - A new trajectory.jsonl is created with the metadata header from the old file.
        - A fresh O_APPEND fd is NOT opened here — recorder.py opens it on next write.

        Returns True on success, True on soft-fail (experiment continues either way).
        """
        try:
            n = _next_rotation_index(path)
            dest = path.parent / f"trajectory.{n}.jsonl"

            # Read the first-line metadata before rename (so we can copy to new file)
            first_line = _read_first_line(path)

            # Close and evict the cached fd BEFORE rename (avoids stale fd after rename)
            fd_key = str(path)
            if fd_key in fd_cache:
                fd = fd_cache.pop(fd_key)
                try:
                    os.close(fd)
                except OSError:
                    pass

            # Atomic rename — POSIX guarantees atomicity on same filesystem
            os.rename(str(path), str(dest))
            logger.info(
                "Soft rotation: %s → %s (%d bytes)",
                path.name, dest.name, dest.stat().st_size,
            )

            # Copy metadata header to new trajectory.jsonl
            if first_line:
                new_fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
                try:
                    os.write(new_fd, first_line if first_line.endswith(b"\n") else first_line + b"\n")
                finally:
                    os.close(new_fd)

            return True

        except Exception as exc:
            logger.warning(
                "Soft rotation failed for %s: %s; continuing without rotation",
                path, exc,
            )
            return True  # soft-fail: experiment continues
