"""Shared fixtures and helpers for automil.backends contract tests (BCK-01..04).

Provides:
- ``wait_for_state`` polling helper (used by Plans 02-07 contract scenarios)
- ``make_spec`` factory helper (builds minimal valid ``JobSpec`` from ``tmp_path``)
- ``backend`` fixture stub (raises ``pytest.skip`` until Plans 02-05/02-06 land)
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from automil.backends.base import JobSpec, JobState


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


@pytest.fixture
def backend():
    """Stub backend fixture — replaced by Plans 02-05 (LocalBackend) and 02-06 (MockSLURMBackend).

    This stub ensures ``test_contract.py`` can be authored in advance and
    collected by pytest without failing.  Plans 02-05/02-06 will parametrize
    over concrete implementations.
    """
    pytest.skip(
        "LocalBackend/MockSLURM not yet implemented — Plans 02-05/02-06"
    )
