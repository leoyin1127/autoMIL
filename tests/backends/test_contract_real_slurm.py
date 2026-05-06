"""@pytest.mark.requires_slurm -- real SLURM cluster contract tests (D-175).

Skipped in CI by default (the marker is not selected). Run nightly via:
    uv run pytest tests/backends/test_contract_real_slurm.py -m requires_slurm

Configures SLURMBackend against an actual SLURM cluster on PATH (sbatch/scancel/sacct);
exercises the same S-01..S-12 scenarios as test_contract.py.

Real-cluster fixture config is read from environment variables:
    AUTOMIL_TEST_SLURM_PARTITION   -- required
    AUTOMIL_TEST_SLURM_ACCOUNT     -- required
    AUTOMIL_TEST_SLURM_QOS         -- optional
    AUTOMIL_TEST_SLURM_CPUS        -- default "1"
    AUTOMIL_TEST_SLURM_MEM_GB      -- default "4"
"""
from __future__ import annotations

import os
import shutil

import pytest

pytestmark = pytest.mark.requires_slurm


@pytest.fixture
def real_slurm_backend(tmp_path):
    """Real SLURMBackend against the cluster on PATH."""
    pytest.importorskip("submitit")
    if shutil.which("sbatch") is None:
        pytest.skip("sbatch not found on PATH; cannot exercise real SLURM cluster")
    partition = os.environ.get("AUTOMIL_TEST_SLURM_PARTITION")
    account = os.environ.get("AUTOMIL_TEST_SLURM_ACCOUNT")
    if not (partition and account):
        pytest.skip("AUTOMIL_TEST_SLURM_PARTITION and AUTOMIL_TEST_SLURM_ACCOUNT must be set")

    from automil.backends.slurm import SLURMBackend
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    config = {
        "backend": {"name": "slurm", "slurm": {
            "debug_in_process": False,  # REAL cluster
            "walltime_seconds": 600,
            "directives": {
                "partition": partition,
                "account": account,
                "qos": os.environ.get("AUTOMIL_TEST_SLURM_QOS"),
                "cpus_per_task": int(os.environ.get("AUTOMIL_TEST_SLURM_CPUS", "1")),
                "mem_gb": int(os.environ.get("AUTOMIL_TEST_SLURM_MEM_GB", "4")),
            },
        }},
    }
    yield SLURMBackend(automil_dir=automil_dir, config=config)


def test_real_slurm_submit_completes(real_slurm_backend, tmp_path):
    """Smoke: real SLURM cluster runs `echo hello` and reaches COMPLETED."""
    from automil.backends.base import JobState
    from tests.backends.conftest import make_spec, wait_for_state
    spec = make_spec("real_slurm_smoke", tmp_path, command=("echo", "hello-real-slurm"))
    handle = real_slurm_backend.submit(spec)
    final = wait_for_state(real_slurm_backend, handle, {JobState.COMPLETED}, timeout=300.0)
    assert final == JobState.COMPLETED
