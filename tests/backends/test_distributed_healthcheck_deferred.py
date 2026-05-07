"""D-189: distributed backends raise NotImplementedError on healthcheck.

Three tests, one per backend:
  - SLURMBackend (skipped if `submitit` extra not installed)
  - RayBackend (skipped if `ray` extra not installed)
  - MockSLURMBackend (always runnable; test-fixture parity with SLURMBackend)

Locked message per D-189:
  "healthcheck deferred to Phase 7+ for distributed backends "
  "(use `salloc`/`ray status` directly)"
"""
from __future__ import annotations

import pytest


_LOCKED_MSG = r"healthcheck deferred to Phase 7\+ for distributed backends"


def test_mock_slurm_healthcheck_raises_notimplemented(tmp_path):
    """D-189: MockSLURMBackend mirrors SLURMBackend's deferred contract."""
    from automil.backends.mock_slurm import MockSLURMBackend
    backend = MockSLURMBackend()
    with pytest.raises(NotImplementedError, match=_LOCKED_MSG):
        backend.healthcheck()


def test_slurm_healthcheck_raises_notimplemented(tmp_path):
    """D-189: SLURMBackend defers healthcheck."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "debug_in_process": True,
                "walltime_seconds": 60,
                "directives": {
                    "partition": "debug", "account": "test",
                    "cpus_per_task": 1, "mem_gb": 1,
                },
            },
        },
    }
    backend = SLURMBackend(automil_dir=automil_dir, config=config)
    with pytest.raises(NotImplementedError, match=_LOCKED_MSG):
        backend.healthcheck()


def test_ray_healthcheck_raises_notimplemented(tmp_path):
    """D-189: RayBackend defers healthcheck."""
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
    try:
        with pytest.raises(NotImplementedError, match=_LOCKED_MSG):
            backend.healthcheck()
    finally:
        if getattr(backend, "_we_started_ray", False) and ray.is_initialized():
            ray.shutdown()
