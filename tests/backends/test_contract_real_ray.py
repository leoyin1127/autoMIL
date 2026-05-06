"""@pytest.mark.requires_ray -- real Ray cluster contract tests (D-175).

Skipped in CI by default. Run nightly via:
    RAY_ADDRESS=ray://head:10001 uv run pytest tests/backends/test_contract_real_ray.py -m requires_ray
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.requires_ray


@pytest.fixture
def real_ray_backend(tmp_path):
    """Real RayBackend against the cluster at RAY_ADDRESS."""
    pytest.importorskip("ray")
    if not os.environ.get("RAY_ADDRESS"):
        pytest.skip("RAY_ADDRESS must be set to a real cluster (e.g. ray://head:10001)")
    import ray
    from automil.backends.ray import RayBackend
    if not ray.is_initialized():
        ray.init(address=os.environ["RAY_ADDRESS"], ignore_reinit_error=True, log_to_driver=False)
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    backend = RayBackend(
        automil_dir=automil_dir,
        config={"backend": {"name": "ray", "ray": {"allow_local_fallback": False}}},
    )
    yield backend
    # NOTE: do NOT ray.shutdown() -- operator owns the real cluster (D-161).


def test_real_ray_submit_completes(real_ray_backend, tmp_path):
    """Smoke: real Ray cluster runs `echo hello` and reaches COMPLETED."""
    from automil.backends.base import JobState
    from tests.backends.conftest import make_spec, wait_for_state
    spec = make_spec("real_ray_smoke", tmp_path, command=("echo", "hello-real-ray"))
    handle = real_ray_backend.submit(spec)
    final = wait_for_state(real_ray_backend, handle, {JobState.COMPLETED}, timeout=300.0)
    assert final == JobState.COMPLETED
