"""Shared fixtures for tests/acceptance/.

ccrcc_data_root skips a test cleanly on missing AUTOBENCH_CCRCC_ROOT env
var or non-existent directory; used by sub-gates A and C of D-205.

Iter-2 / F-12 fix: the fixture is liberal (no splits/ subdirectory check).
The "is this a CCRCC layout?" semantics are the responsibility of the
specific sub-gate (sub-gate A's autobench-project path probe), not the
fixture. This avoids spurious skips on Leo's workstation when the dataset
layout differs from the original draft assumption.

cli_runner re-exports the project-wide Click CliRunner for ergonomics.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def ccrcc_data_root() -> Path:
    """Resolve CCRCC dataset root or skip the test (D-205 sub-gates A and C).

    The CI environment does not have CCRCC data; Leo's workstation does. This
    fixture skips with a clear message so tests report SKIPPED (not FAILED)
    on CI and run unconditionally when the env var is set.

    Iter-2 / F-12 fix: dropped the splits/ subdirectory check. Sub-gate A
    owns the "is this a CCRCC autobench project?" check via its own path
    probe (F-08 fix); the fixture only validates env-var presence + existence.
    """
    raw = os.environ.get("AUTOBENCH_CCRCC_ROOT")
    if not raw:
        pytest.skip(
            "AUTOBENCH_CCRCC_ROOT not set; sub-gates A and C require real CCRCC "
            "data. CI runs only sub-gate B."
        )
    root = Path(raw)
    if not root.exists():
        pytest.skip(f"AUTOBENCH_CCRCC_ROOT={raw} does not exist on this host")
    return root


@pytest.fixture
def cli_runner() -> CliRunner:
    """Click CliRunner for invoking automil commands in tests."""
    return CliRunner()
