"""Shared fixtures and helpers for automil.backends contract tests (BCK-01..06).

Provides:
- ``wait_for_state`` polling helper (used by Plans 02-07 contract scenarios)
- ``make_spec`` factory helper (builds minimal valid ``JobSpec`` from ``tmp_path``)
- ``backend`` fixture — parameterised over LocalBackend, MockSLURMBackend,
  SLURMBackend (submitit DebugExecutor), and RayBackend (local cluster) (Plan 02-09)
- ``_isolated_backends`` autouse fixture — clears BACKENDS registry before/after
  each test (per PATTERNS.md §11 registry-singleton-isolation pattern)

Note on the 4-branch if/elif/elif/else chain (Phase 6 W-9 requirement):
  The dispatch is explicit so "ray" never accidentally falls through to MockSLURMBackend.
  - "local"      → LocalBackend (structural scenarios only; daemon-execution skipped)
  - "mock_slurm" → MockSLURMBackend (poll_lag=0.05s; full execution scenarios run)
  - "slurm"      → SLURMBackend(debug_in_process=True) using submitit cluster="debug"
                   SKIPPED if submitit extra not installed (pytest.importorskip)
  - "ray"        → RayBackend with local ray.init() (NOT local_mode=True — deprecated
                   in Ray 2.55+; see RESEARCH.md Pitfall 5)
                   SKIPPED if ray extra not installed (pytest.importorskip)
                   Teardown: ray.shutdown() only if RayBackend._we_started_ray
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from automil.backends.base import JobSpec, JobState


# ---------------------------------------------------------------------------
# Polling helper
# ---------------------------------------------------------------------------

def wait_for_state(
    backend,
    handle,
    target_states,
    timeout: float = 5.0,
    interval: float = 0.05,
) -> JobState:
    """Poll ``backend.poll(handle)`` until state is in ``target_states`` or timeout.

    Args:
        backend: Any ``Backend`` instance.
        handle: ``JobHandle`` returned from ``backend.submit()``.
        target_states: Iterable of ``JobState`` values to wait for.
        timeout: Maximum seconds to poll before raising ``TimeoutError``.
        interval: Seconds between poll attempts.

    Returns:
        The terminal ``JobState`` observed.

    Raises:
        TimeoutError: If ``timeout`` elapses before the target state is reached.
    """
    deadline = time.monotonic() + timeout
    last_state: JobState | None = None
    while time.monotonic() < deadline:
        last_state = backend.poll(handle)
        if last_state in target_states:
            return last_state
        time.sleep(interval)
    raise TimeoutError(
        f"wait_for_state timed out after {timeout}s: "
        f"handle={handle!r}, last_state={last_state!r}, "
        f"target_states={list(target_states)!r}"
    )


# ---------------------------------------------------------------------------
# Spec factory
# ---------------------------------------------------------------------------

def make_spec(
    node_id: str,
    tmp_path: Path,
    command: tuple[str, ...] = ("echo", "hello"),
    **kwargs,
) -> JobSpec:
    """Build a minimal valid ``JobSpec`` for contract test scenarios.

    Args:
        node_id: The autoMIL node id for this spec.
        tmp_path: pytest's ``tmp_path`` fixture; used as ``overlay_dir``.
        command: argv tuple (default: ``("echo", "hello")``).
        **kwargs: Override any ``JobSpec`` field by name.

    Returns:
        A frozen ``JobSpec`` ready for ``backend.submit()``.
    """
    defaults: dict = {
        "node_id": node_id,
        "base_commit": "abc1234",
        "overlay_files": (),
        "overlay_dir": tmp_path,
        "command": command,
        "env": (),
        "working_subdir": "",
        "gpu_estimate_gb": 0.5,
        "walltime_seconds": 60,
    }
    defaults.update(kwargs)
    return JobSpec(**defaults)


# ---------------------------------------------------------------------------
# Backend fixture — parameterised over all 4 implementations (T-02-09-01)
# ---------------------------------------------------------------------------

@pytest.fixture(params=["local", "mock_slurm", "slurm", "ray"])
def backend(request, tmp_path, _isolated_backends):
    """Parameterised fixture: yields LocalBackend, MockSLURMBackend, SLURMBackend, or RayBackend.

    See module docstring for per-branch semantics and skip conditions.
    """
    if request.param == "local":
        from automil.backends.local import LocalBackend  # explicit per D-69

        # Minimal project directory structure that LocalBackend requires.
        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "queue").mkdir(parents=True)
        (automil_dir / "orchestrator" / "running").mkdir(parents=True)
        (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
        (automil_dir / "config.yaml").write_text("backend:\n  name: local\n")
        # Minimal fake git repo (LocalBackend auto-detects project_root via .git).
        (tmp_path / ".git").mkdir()
        yield LocalBackend(project_root=tmp_path, automil_dir=automil_dir)
    elif request.param == "mock_slurm":
        from automil.backends.mock_slurm import MockSLURMBackend  # explicit per D-69

        yield MockSLURMBackend(
            poll_lag_seconds=0.05,
            state_file=tmp_path / "mock_state.json",
        )
    elif request.param == "slurm":
        pytest.importorskip("submitit")
        from automil.backends.slurm import SLURMBackend  # noqa: PLC0415

        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
        (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
        config = {
            "backend": {
                "name": "slurm",
                "slurm": {
                    "debug_in_process": True,  # uses submitit cluster="debug"
                    "walltime_seconds": 300,
                    "directives": {
                        "partition": "debug",
                        "account": "test",
                        "cpus_per_task": 1,
                        "mem_gb": 4,
                    },
                },
            },
        }
        yield SLURMBackend(automil_dir=automil_dir, config=config)
    else:  # request.param == "ray"
        pytest.importorskip("ray")
        import ray  # noqa: PLC0415
        from automil.backends.ray import RayBackend  # noqa: PLC0415

        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True, log_to_driver=False)  # NOT local_mode=True (deprecated; RESEARCH.md Pitfall 5)
        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
        (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
        backend_instance = RayBackend(
            automil_dir=automil_dir,
            config={"backend": {"name": "ray", "ray": {"allow_local_fallback": True}}},
        )
        yield backend_instance
        if backend_instance._we_started_ray and ray.is_initialized():
            ray.shutdown()


# ---------------------------------------------------------------------------
# Registry isolation fixture (PATTERNS.md §11)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_backends():
    """Save + restore BACKENDS registry around every test.

    ``autouse=True`` so every test in the backends/ package gets isolated
    registry state without explicitly requesting the fixture.  This prevents
    MockSLURMBackend's ``@register("mock_slurm")`` call from polluting the
    BACKENDS dict for tests that import mock_slurm explicitly.
    """
    from automil.backends import BACKENDS
    saved = dict(BACKENDS)
    yield
    BACKENDS.clear()
    BACKENDS.update(saved)
