"""Wave 0 stubs for D-170/D-171 cross-backend log unification (BCK-05/06)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from automil.backends.base import JobState
from tests.backends.conftest import make_spec, wait_for_state


def _drain_to_archive(backend, handle, archive_root: Path) -> Path:
    """Helper: simulate orchestrator's terminal-state log drain (D-170)."""
    from automil.backends._orchestrator_daemon import _atomic_write_lines
    log_path = archive_root / handle.node_id / "run.log"
    lines = list(backend.log_iter(handle))
    _atomic_write_lines(log_path, lines)
    return log_path


def test_archive_run_log_local(tmp_path):
    """D-170: orchestrator drains LocalBackend.log_iter into archive/<id>/run.log on terminal."""
    pytest.skip("Requires live LocalBackend daemon; covered by integration in Wave 4 plan 06-07.")


def test_archive_run_log_slurm(tmp_path):
    """D-170: orchestrator drains SLURMBackend.log_iter into archive/<id>/run.log on terminal."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    config = {
        "backend": {"name": "slurm", "slurm": {
            "debug_in_process": True, "walltime_seconds": 60,
            "directives": {"partition": "debug", "account": "t", "cpus_per_task": 1, "mem_gb": 1},
        }},
    }
    backend = SLURMBackend(automil_dir=automil_dir, config=config)
    spec = make_spec("node_log_slurm", tmp_path, command=("echo", "hello-slurm"))
    handle = backend.submit(spec)
    wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=10.0)
    log_path = _drain_to_archive(backend, handle, automil_dir / "orchestrator" / "archive")
    assert log_path.exists()
    assert "hello-slurm" in log_path.read_text()


def test_archive_run_log_ray(tmp_path):
    """D-170: orchestrator drains RayBackend.log_iter into archive/<id>/run.log on terminal."""
    pytest.importorskip("ray")
    import ray
    from automil.backends.ray import RayBackend
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, log_to_driver=False)
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    backend = RayBackend(
        automil_dir=automil_dir,
        config={"backend": {"name": "ray", "ray": {"allow_local_fallback": True}}},
    )
    spec = make_spec("node_log_ray", tmp_path, command=("echo", "hello-ray"))
    handle = backend.submit(spec)
    try:
        wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=20.0)
        log_path = _drain_to_archive(backend, handle, automil_dir / "orchestrator" / "archive")
        assert log_path.exists()
        assert "hello-ray" in log_path.read_text()
    finally:
        if backend._we_started_ray:
            ray.shutdown()


def test_log_iter_close_60s_timeout(tmp_path):
    """D-170: orchestrator force-closes log_iter at 60s post-terminal (drain wrapper enforces)."""
    from automil.backends._orchestrator_daemon import _drain_log_iter_with_timeout
    # The helper wraps backend.log_iter() and force-closes after the timeout.
    # A pathological backend that yields forever must be drained in <= timeout + small slack.
    class _ForeverBackend:
        def log_iter(self, _handle):
            while True:
                yield "looping\n"
                time.sleep(0.1)
    start = time.monotonic()
    lines = _drain_log_iter_with_timeout(_ForeverBackend(), handle=None, timeout=2.0)
    elapsed = time.monotonic() - start
    assert elapsed < 3.0, f"drain took {elapsed:.2f}s; expected < 3.0s"
    assert isinstance(lines, list)
