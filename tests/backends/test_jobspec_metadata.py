"""Tests for JobSpec.metadata field — Phase 5 Plan 03 (GTE-03 / D-140).

Verifies:
  1. JobSpec.metadata defaults to empty tuple
  2. Explicit metadata tuple-of-tuples is preserved
  3. frozen=True prevents mutation
  4. LocalBackend.submit() merges spec.metadata into queue_spec["metadata"]
  5. MockSLURMBackend.submit() stores metadata for test introspection
  6. Existing JobSpec callers remain unbroken (backward-compat)
  7. Backend stamp ("local") wins over caller-provided "backend" key (T-05-03-01)
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from automil.backends.base import JobSpec


# ---------------------------------------------------------------------------
# Fixture: minimal orchestrator directory tree for LocalBackend tests
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_orch_dir(tmp_path) -> Path:
    """Build a minimal project directory tree that LocalBackend can use."""
    automil_dir = tmp_path / "automil"
    orch_dir = automil_dir / "orchestrator"
    (orch_dir / "queue").mkdir(parents=True)
    (orch_dir / "running").mkdir(parents=True)
    (orch_dir / "archive").mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("backend:\n  name: local\n")
    # Minimal fake git repo so auto-detect finds the project root.
    (tmp_path / ".git").mkdir()
    return orch_dir


def _make_spec(node_id: str, overlay_dir: Path, **kwargs) -> JobSpec:
    """Minimal valid JobSpec factory."""
    defaults: dict = {
        "node_id": node_id,
        "base_commit": "abc1234",
        "overlay_files": (),
        "overlay_dir": overlay_dir,
        "command": ("echo", "hello"),
        "env": (),
        "working_subdir": "",
        "gpu_estimate_gb": 0.5,
        "walltime_seconds": 60,
    }
    defaults.update(kwargs)
    return JobSpec(**defaults)


# ---------------------------------------------------------------------------
# Test 1: metadata defaults to ()
# ---------------------------------------------------------------------------

def test_jobspec_metadata_default_empty(tmp_path):
    """T1: JobSpec without metadata keyword → spec.metadata == ()."""
    spec = JobSpec(
        node_id="x",
        base_commit="abc",
        overlay_files=(),
        overlay_dir=tmp_path,
        command=("python",),
        env=(),
        working_subdir=".",
        gpu_estimate_gb=1.0,
        walltime_seconds=60,
    )
    assert spec.metadata == ()


# ---------------------------------------------------------------------------
# Test 2: explicit metadata is preserved
# ---------------------------------------------------------------------------

def test_jobspec_metadata_explicit(tmp_path):
    """T2: metadata=(("k1","v1"),("k2","v2")) → dict(spec.metadata) == expected."""
    spec = _make_spec(
        "node_t2",
        tmp_path,
        metadata=(("k1", "v1"), ("k2", "v2")),
    )
    assert dict(spec.metadata) == {"k1": "v1", "k2": "v2"}


# ---------------------------------------------------------------------------
# Test 3: frozen — mutation raises FrozenInstanceError
# ---------------------------------------------------------------------------

def test_jobspec_frozen_with_metadata(tmp_path):
    """T3: Attempting to reassign spec.metadata raises FrozenInstanceError."""
    spec = _make_spec("node_t3", tmp_path, metadata=(("k", "v"),))
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.metadata = (("k", "v"),)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 4: LocalBackend merges spec.metadata into queue_spec["metadata"]
# ---------------------------------------------------------------------------

def test_localbackend_metadata_round_trip(tmp_path, tmp_orch_dir):
    """T4: LocalBackend.submit() persists spec.metadata into queue/<id>.json.

    Asserts:
    - gate_eval and cell_id keys appear in metadata dict
    - existing backend stamp "local" coexists
    - backend stamp is written LAST so it wins over any caller-provided "backend" key
    """
    from automil.backends.local import LocalBackend  # explicit per D-69

    automil_dir = tmp_orch_dir.parent  # .../automil/
    project_root = automil_dir.parent  # tmp_path

    backend = LocalBackend(project_root=project_root, automil_dir=automil_dir)

    spec = _make_spec(
        "node_t4",
        tmp_path,
        metadata=(("gate_eval", "true"), ("cell_id", "abc123")),
    )
    backend.submit(spec)

    queue_file = tmp_orch_dir / "queue" / "node_t4.json"
    assert queue_file.exists(), "queue/<node_id>.json must be written"

    data = json.loads(queue_file.read_text())
    assert "metadata" in data, "metadata key must exist in queue spec"
    assert data["metadata"]["gate_eval"] == "true"
    assert data["metadata"]["cell_id"] == "abc123"
    assert data["metadata"]["backend"] == "local", "backend stamp must coexist"


# ---------------------------------------------------------------------------
# Test 5: MockSLURMBackend stores metadata for introspection
# ---------------------------------------------------------------------------

def test_mockslurmbackend_metadata_round_trip(tmp_path):
    """T5: MockSLURMBackend.submit() stores metadata in _metadata_by_node_id."""
    from automil.backends.mock_slurm import MockSLURMBackend  # explicit per D-69

    mb = MockSLURMBackend(poll_lag_seconds=0.05)
    spec = _make_spec(
        "node_t5",
        tmp_path,
        metadata=(("gate_eval", "true"),),
    )
    handle = mb.submit(spec)

    # The plan calls for backend._metadata_by_node_id[handle.node_id]
    assert hasattr(mb, "_metadata_by_node_id"), (
        "MockSLURMBackend must expose _metadata_by_node_id dict"
    )
    stored = mb._metadata_by_node_id.get(handle.node_id)
    assert stored is not None, f"No metadata stored for node_id={handle.node_id}"
    assert stored["gate_eval"] == "true"


# ---------------------------------------------------------------------------
# Test 6: Existing callers are unbroken (positional construction)
# ---------------------------------------------------------------------------

def test_existing_jobspec_callers_unbroken(tmp_path):
    """T6: All existing positional-arg JobSpec construction sites still work.

    metadata defaults to () when omitted, so no call sites need updating.
    """
    # Positional construction (mirrors cli/submit.py style)
    spec = JobSpec(
        node_id="legacy_node",
        base_commit="deadbeef",
        overlay_files=("train.py",),
        overlay_dir=tmp_path,
        command=("python", "train.py"),
        env=(("CUDA_VISIBLE_DEVICES", "0"),),
        working_subdir=".",
        gpu_estimate_gb=2.0,
        walltime_seconds=3600,
    )
    # Must work without specifying metadata
    assert spec.metadata == ()
    # And dict conversion still works
    assert dict(spec.env) == {"CUDA_VISIBLE_DEVICES": "0"}


# ---------------------------------------------------------------------------
# Test 7: Backend stamp wins over caller-provided "backend" key (T-05-03-01)
# ---------------------------------------------------------------------------

def test_caller_cannot_override_backend_stamp(tmp_path, tmp_orch_dir):
    """T7: Caller-provided metadata key "backend" is overridden by LocalBackend stamp.

    Security property (T-05-03-01): the framework-owned "backend" key cannot be
    spoofed by a caller passing metadata=(("backend","slurm"),).
    """
    from automil.backends.local import LocalBackend  # explicit per D-69

    automil_dir = tmp_orch_dir.parent
    project_root = automil_dir.parent

    backend = LocalBackend(project_root=project_root, automil_dir=automil_dir)

    spec = _make_spec(
        "node_t7",
        tmp_path,
        metadata=(("backend", "slurm"),),  # caller tries to override
    )
    backend.submit(spec)

    queue_file = tmp_orch_dir / "queue" / "node_t7.json"
    data = json.loads(queue_file.read_text())

    # Framework wins — must be "local", not "slurm"
    assert data["metadata"]["backend"] == "local", (
        "Backend stamp must override caller-provided 'backend' key"
    )
