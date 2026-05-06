"""CAP-05 daemon-restart safety tests (D-111).

Verifies that ``started_at`` persists on disk so that ``consumed_seconds``
is computed correctly even after the daemon is kill-9'd and restarted.

There is NO counter accumulation anywhere — ``consumed_seconds`` is:
    time.time() - cell.started_at

This means a daemon kill at hour 4 of a 6h cell still computes ~14400
consumed seconds from the persisted ``started_at``.  Restart-safe by
construction.

Tests:
    test_started_at_persists_across_in_process_reload
    test_consumed_seconds_computed_from_persisted_started_at
    test_started_at_persists_across_subprocess_restart
    test_status_transitions_persist_across_reload
    test_zero_accumulator_pattern_in_state_module
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from automil.cells.state import Cell, CellStatus, read_cell, write_cell
from tests.cells.conftest import make_cell

# ---------------------------------------------------------------------------
# Test 1 — started_at persists across in-process reload
# ---------------------------------------------------------------------------


def test_started_at_persists_across_in_process_reload(cells_dir: Path):
    """started_at round-trips through write_cell / read_cell unchanged.

    Uses a deterministic fake timestamp to guarantee exact equality —
    no floating-point drift from calling time.time() twice.
    """
    fake_now = 1_000_000_000.0
    four_h_ago = fake_now - 14400  # 4h ago

    cell = make_cell(started_at=four_h_ago)
    write_cell(cell, cells_dir)

    # Simulate fresh process: re-read from disk (no in-memory reference)
    cell_path = cells_dir / f"{cell.cell_id}.json"
    reloaded = read_cell(cell_path)

    assert reloaded.started_at == four_h_ago, (
        f"started_at must round-trip exactly: expected {four_h_ago}, got {reloaded.started_at}"
    )


# ---------------------------------------------------------------------------
# Test 2 — consumed_seconds computed from persisted started_at (not zero)
# ---------------------------------------------------------------------------


def test_consumed_seconds_computed_from_persisted_started_at(cells_dir: Path):
    """consumed_seconds(reloaded_cell) ≈ 14400, NOT 0.

    Writes a cell whose started_at is 4h ago.  Re-reads from disk (simulating
    a fresh daemon process after kill-9).  Asserts consumed_seconds is in the
    expected range and is explicitly NOT zero (sandbagging defence / D-111).
    """
    from automil.cells.state import consumed_seconds

    four_h_seconds = 4 * 3600  # 14400
    started_4h_ago = time.time() - four_h_seconds

    cell = make_cell(started_at=started_4h_ago)
    write_cell(cell, cells_dir)

    cell_path = cells_dir / f"{cell.cell_id}.json"
    reloaded = read_cell(cell_path)

    elapsed = consumed_seconds(reloaded)

    # Allow ±10 seconds for test execution drift
    assert elapsed != 0, "consumed_seconds must NOT return 0 after restart (sandbagging guard)"
    assert abs(elapsed - four_h_seconds) < 10, (
        f"consumed_seconds must be ≈14400; got {elapsed:.1f}s "
        f"(started_at={reloaded.started_at:.2f}, now≈{time.time():.2f})"
    )


# ---------------------------------------------------------------------------
# Test 3 — started_at persists across subprocess restart
# ---------------------------------------------------------------------------


def test_started_at_persists_across_subprocess_restart(tmp_path: Path):
    """Cell state read from a fresh Python subprocess matches on-disk started_at.

    Simulates a daemon kill-9 + restart: the main process writes a cell to disk,
    then a *separate subprocess* (clean module state, no in-memory cache) reads
    the same file and prints started_at.  Asserts the subprocess sees the same
    started_at — proving persistence is process-independent.
    """
    from automil.cells.state import consumed_seconds

    cells_dir = tmp_path / "cells"
    cells_dir.mkdir()

    four_h_seconds = 4 * 3600
    started_4h_ago = time.time() - four_h_seconds

    cell = make_cell(cell_id="aabbccddeeff0011", started_at=started_4h_ago)
    write_cell(cell, cells_dir)

    cell_path = cells_dir / f"{cell.cell_id}.json"

    # Subprocess reads the cell file directly via stdlib json — no automil import
    # necessary, keeping the subprocess scope simple and dependency-free.
    script = (
        "import json, sys; "
        f"data = json.loads(open({str(cell_path)!r}).read()); "
        "print(data['started_at'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"Subprocess failed: {result.stderr}"
    )
    subprocess_started_at = float(result.stdout.strip())

    # Assert subprocess sees the same started_at written by main process
    assert subprocess_started_at == started_4h_ago, (
        f"Subprocess read started_at={subprocess_started_at}, "
        f"expected {started_4h_ago} — persistence is not process-independent"
    )

    # consumed_seconds as computed from the subprocess value must also be > 0
    subprocess_consumed = time.time() - subprocess_started_at
    assert subprocess_consumed > 0, (
        "consumed_seconds derived from subprocess-read started_at must be > 0"
    )
    assert abs(subprocess_consumed - four_h_seconds) < 15, (
        f"Subprocess-derived consumed_seconds ≈ {subprocess_consumed:.1f}s, "
        f"expected ≈{four_h_seconds}s"
    )


# ---------------------------------------------------------------------------
# Test 4 — status transitions persist across reload (started_at unchanged)
# ---------------------------------------------------------------------------


def test_status_transitions_persist_across_reload(cells_dir: Path):
    """Status transition writes persist; started_at is unchanged by the transition.

    Simulates the daemon updating status ACTIVE → REFUSING_NEW after a tick.
    The key invariant: status changes must NOT reset started_at (which would
    make consumed_seconds jump back to 0).
    """
    from automil.cells.state import consumed_seconds

    fake_started_at = 1_000_000_000.0
    cell = make_cell(started_at=fake_started_at, status=CellStatus.ACTIVE)
    write_cell(cell, cells_dir)
    cell_path = cells_dir / f"{cell.cell_id}.json"

    # Simulate daemon tick: reload → transition status → write back
    reloaded = read_cell(cell_path)
    assert reloaded.status == CellStatus.ACTIVE
    assert reloaded.started_at == fake_started_at

    # Status transition via frozen dataclass replace (D-108)
    updated = replace(reloaded, status=CellStatus.REFUSING_NEW)
    write_cell(updated, cells_dir)

    # Reload again — simulating the next daemon tick after kill/restart
    reloaded2 = read_cell(cell_path)
    assert reloaded2.status == CellStatus.REFUSING_NEW, (
        "Status transition must persist after write_cell"
    )
    assert reloaded2.started_at == fake_started_at, (
        "Status transition must NOT reset started_at — "
        "would cause consumed_seconds to return incorrect value after restart"
    )


# ---------------------------------------------------------------------------
# Test 5 — static guard: no += accumulation in state.py consumed_seconds
# ---------------------------------------------------------------------------


def test_zero_accumulator_pattern_in_state_module():
    """consumed_seconds must use computation (time.time() - started_at), NOT accumulation.

    Statically asserts that ``+= `` does not appear in state.py.  Catches any
    future regression where someone re-introduces a counter accumulator pattern
    (the sandbagging anti-pattern that breaks restart-safety / D-111).
    """
    state_py = Path("src/automil/cells/state.py")
    assert state_py.exists(), f"Could not find {state_py} — wrong working directory?"
    text = state_py.read_text()
    assert "+= " not in text, (
        "Found '+= ' in src/automil/cells/state.py — this looks like an accumulator "
        "pattern, which breaks restart-safety (D-111). consumed_seconds must be "
        "time.time() - cell.started_at, never accumulated. Remove any '+=' usage."
    )
