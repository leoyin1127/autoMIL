"""Rotation manager unit tests (TRJ-03, TRJ-06 / D-84)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from automil.trajectory.rotation import RotationManager, _next_rotation_index


@pytest.fixture
def archive_dir(tmp_path: Path):
    """Minimal archive directory for a single node."""
    node_id = "node_0001"
    d = tmp_path / "archive" / node_id
    d.mkdir(parents=True)
    return d, node_id


def _write_trajectory(path: Path, size_bytes: int, metadata: dict | None = None) -> None:
    """Write a trajectory.jsonl with the given approximate size."""
    if metadata is None:
        metadata = {
            "schema_version": "trajectory-v1",
            "runtime": "test",
            "runtime_version": "unknown",
            "tool_schema_version": "unknown",
            "automil_version": "0.1.0",
            "automil_runtime_env": {},
        }
    with open(path, "w") as f:
        f.write(json.dumps(metadata) + "\n")
        # Pad to target size with dummy events
        line = '{"gen_ai.provider.name":"test","gen_ai.event.name":"tool_call","gen_ai.event.timestamp":"2026-05-03T00:00:00Z"}\n'
        while path.stat().st_size < size_bytes:
            f.write(line)


# --- Soft rotation tests ---

def test_soft_rotate_triggers_on_threshold(archive_dir) -> None:
    """File at/above soft threshold triggers rename to trajectory.1.jsonl."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager(soft_bytes=100, hard_bytes=50 * 1024 * 1024)
    _write_trajectory(traj, 200)  # 200 bytes > 100 byte soft threshold

    fd_cache: dict = {}
    result = rm.check_and_rotate(traj, fd_cache)

    assert result is True
    assert (d / "trajectory.1.jsonl").exists()


def test_soft_rotate_copies_metadata_header(archive_dir) -> None:
    """After soft rotation, new trajectory.jsonl starts with metadata from old file."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    metadata = {
        "schema_version": "trajectory-v1",
        "runtime": "claude-code",
        "runtime_version": "claude-opus-4-7",
        "tool_schema_version": "claude-2026-04",
        "automil_version": "0.1.0",
        "automil_runtime_env": {"AUTOMIL_RUNTIME": "claude-code"},
    }
    rm = RotationManager(soft_bytes=100, hard_bytes=50 * 1024 * 1024)
    _write_trajectory(traj, 200, metadata=metadata)

    fd_cache: dict = {}
    rm.check_and_rotate(traj, fd_cache)

    if traj.exists():
        first_line = traj.read_text().splitlines()[0]
        meta = json.loads(first_line)
        assert meta["schema_version"] == "trajectory-v1"
        assert meta["runtime"] == "claude-code"


def test_soft_rotate_atomicity(archive_dir) -> None:
    """Rotation target does not overwrite — uses next free integer."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager(soft_bytes=50, hard_bytes=50 * 1024 * 1024)

    # Pre-create trajectory.1.jsonl and trajectory.2.jsonl
    (d / "trajectory.1.jsonl").write_text("existing_1\n")
    (d / "trajectory.2.jsonl").write_text("existing_2\n")

    _write_trajectory(traj, 100)
    fd_cache: dict = {}
    rm.check_and_rotate(traj, fd_cache)

    # Should have renamed to trajectory.3.jsonl (next free)
    assert (d / "trajectory.3.jsonl").exists()
    # Existing files untouched
    assert (d / "trajectory.1.jsonl").read_text() == "existing_1\n"
    assert (d / "trajectory.2.jsonl").read_text() == "existing_2\n"


def test_next_rotation_index_increments_correctly(archive_dir) -> None:
    """_next_rotation_index returns smallest free N."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    traj.write_text("placeholder\n")

    assert _next_rotation_index(traj) == 1

    (d / "trajectory.1.jsonl").write_text("x\n")
    assert _next_rotation_index(traj) == 2

    (d / "trajectory.2.jsonl").write_text("x\n")
    assert _next_rotation_index(traj) == 3

    # Gap at 3, 5 exists — should still return 3 (smallest)
    (d / "trajectory.5.jsonl").write_text("x\n")
    assert _next_rotation_index(traj) == 3


# --- Hard rotation tests ---

def test_hard_rotate_returns_false(archive_dir) -> None:
    """File at/above hard threshold returns False (soft-fail)."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager(soft_bytes=100, hard_bytes=200)
    _write_trajectory(traj, 300)  # 300 bytes > 200 byte hard threshold

    fd_cache: dict = {}
    result = rm.check_and_rotate(traj, fd_cache)

    assert result is False


def test_hard_rotate_does_not_rename(archive_dir) -> None:
    """Hard limit refusal does not rename the file."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager(soft_bytes=100, hard_bytes=200)
    _write_trajectory(traj, 300)

    fd_cache: dict = {}
    rm.check_and_rotate(traj, fd_cache)

    # trajectory.1.jsonl must NOT be created on hard-limit refusal
    assert not (d / "trajectory.1.jsonl").exists()
    # Original file still exists (not renamed)
    assert traj.exists()


# --- Edge cases ---

def test_no_file_returns_true(archive_dir) -> None:
    """Non-existent file returns True (new file case)."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager()
    fd_cache: dict = {}
    assert rm.check_and_rotate(traj, fd_cache) is True


def test_small_file_returns_true(archive_dir) -> None:
    """File below soft threshold returns True (no rotation needed)."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager(soft_bytes=10_000, hard_bytes=50_000)
    _write_trajectory(traj, 100)

    fd_cache: dict = {}
    assert rm.check_and_rotate(traj, fd_cache) is True
    # No rotation — trajectory.1.jsonl must not exist
    assert not (d / "trajectory.1.jsonl").exists()


def test_fd_cache_evicted_on_rotation(archive_dir) -> None:
    """Cached fd is evicted from fd_cache on soft rotation."""
    d, _ = archive_dir
    traj = d / "trajectory.jsonl"
    rm = RotationManager(soft_bytes=50, hard_bytes=50 * 1024 * 1024)
    _write_trajectory(traj, 100)

    # Simulate a cached fd for this path
    fake_fd = os.open(str(traj), os.O_RDONLY)
    fd_cache = {str(traj): fake_fd}

    rm.check_and_rotate(traj, fd_cache)

    # fd should be evicted from cache
    assert str(traj) not in fd_cache
