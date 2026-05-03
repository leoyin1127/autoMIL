"""Shared fixtures and helpers for automil.backends contract tests (BCK-01..04).

Provides:
- ``wait_for_state`` polling helper (used by Plans 02-07 contract scenarios)
- ``make_spec`` factory helper (builds minimal valid ``JobSpec`` from ``tmp_path``)
- ``backend`` fixture — parameterised over LocalBackend + MockSLURMBackend (Plan 02-07)
- ``_isolated_backends`` autouse fixture — clears BACKENDS registry before/after
  each test (per PATTERNS.md §11 registry-singleton-isolation pattern)
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
# Backend fixture — parameterised over both implementations (T-02-07-01)
# ---------------------------------------------------------------------------

@pytest.fixture(params=["local", "mock_slurm"])
def backend(request, tmp_path):
    """Parameterised fixture: yields LocalBackend or MockSLURMBackend.

    ``local`` — builds a minimal project directory tree so LocalBackend can
    construct without a running daemon.  The LocalBackend fixture is suitable
    for structural scenarios (submit writes queue file, poll reads it, cancel
    removes it, list_running scans running/) but not for job-execution scenarios
    that require the daemon to be alive (those are skipped via
    ``pytest.mark.skipif`` in test_contract.py).

    ``mock_slurm`` — uses ``poll_lag_seconds=0.05`` so the full contract suite
    runs in <10s wall-clock (D-63 / RESEARCH.md §3 flakiness prevention rule 2).
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
    else:
        from automil.backends.mock_slurm import MockSLURMBackend  # explicit per D-69

        yield MockSLURMBackend(
            poll_lag_seconds=0.05,
            state_file=tmp_path / "mock_state.json",
        )


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
