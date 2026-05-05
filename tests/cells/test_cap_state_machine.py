"""Exhaustive unit tests for the cap state machine pure function (CAP-02 / D-113).

All transitions:
  ACTIVE          -> ACTIVE           (remaining > safety_buffer)
  ACTIVE          -> REFUSING_NEW     (remaining <= safety_buffer)
  REFUSING_NEW    -> REFUSING_NEW     (remaining > 0)
  REFUSING_NEW    -> TERMINATING      (remaining <= 0)
  TERMINATING     -> TERMINATING      (running_count > 0)
  TERMINATING     -> FINALIZED        (running_count == 0)
  FINALIZED       -> FINALIZED        (terminal / idempotent)

next_status() is a pure function — no I/O, no time.time(). Clock is injected
via the now_epoch parameter (D-113 explicit clock injection).
"""
from __future__ import annotations

import pytest

from automil.cells.state import Cell, CellStatus
from automil.cells.cap import next_status
from tests.cells.conftest import make_cell

FAKE_NOW = 1_000_000.0
BUDGET = 21600
BUFFER = 1800


# ---------------------------------------------------------------------------
# ACTIVE state transitions
# ---------------------------------------------------------------------------


def test_active_stays_active_when_remaining_above_safety_buffer():
    """consumed=3600 (1h), budget=21600, buffer=1800; remaining=18000 > 1800 → ACTIVE."""
    cell = make_cell(
        status=CellStatus.ACTIVE,
        started_at=FAKE_NOW - 3600,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.ACTIVE


def test_active_transitions_to_refusing_new_at_safety_buffer_boundary():
    """consumed = budget - safety_buffer = 19800; remaining == 1800 (boundary) → REFUSING_NEW."""
    cell = make_cell(
        status=CellStatus.ACTIVE,
        started_at=FAKE_NOW - (BUDGET - BUFFER),  # remaining == buffer exactly
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.REFUSING_NEW


def test_active_transitions_to_refusing_new_when_remaining_below_safety_buffer():
    """consumed=20000; remaining=1600 < 1800 → REFUSING_NEW."""
    cell = make_cell(
        status=CellStatus.ACTIVE,
        started_at=FAKE_NOW - 20000,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.REFUSING_NEW


def test_active_with_running_count_does_not_affect_active_status():
    """running_count is only consulted in TERMINATING; ACTIVE ignores it."""
    cell = make_cell(
        status=CellStatus.ACTIVE,
        started_at=FAKE_NOW - 3600,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=10) == CellStatus.ACTIVE


# ---------------------------------------------------------------------------
# REFUSING_NEW state transitions
# ---------------------------------------------------------------------------


def test_refusing_new_stays_refusing_new_when_remaining_positive():
    """status=REFUSING_NEW, consumed=21000; remaining=600 > 0 → REFUSING_NEW."""
    cell = make_cell(
        status=CellStatus.REFUSING_NEW,
        started_at=FAKE_NOW - 21000,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.REFUSING_NEW


def test_refusing_new_transitions_to_terminating_at_zero_remaining():
    """status=REFUSING_NEW, consumed=21600 (== budget); remaining=0 → TERMINATING."""
    cell = make_cell(
        status=CellStatus.REFUSING_NEW,
        started_at=FAKE_NOW - BUDGET,  # remaining == 0 exactly
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.TERMINATING


def test_refusing_new_transitions_to_terminating_when_remaining_negative():
    """status=REFUSING_NEW, consumed=22000; remaining=-400 → TERMINATING."""
    cell = make_cell(
        status=CellStatus.REFUSING_NEW,
        started_at=FAKE_NOW - 22000,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.TERMINATING


# ---------------------------------------------------------------------------
# TERMINATING state transitions
# ---------------------------------------------------------------------------


def test_terminating_stays_terminating_when_running_count_nonzero():
    """status=TERMINATING, running_count=2 → TERMINATING (not yet drained)."""
    cell = make_cell(
        status=CellStatus.TERMINATING,
        started_at=FAKE_NOW - 22000,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=2) == CellStatus.TERMINATING


def test_terminating_transitions_to_finalized_when_running_count_zero():
    """status=TERMINATING, running_count=0 → FINALIZED (all in-cell exps drained)."""
    cell = make_cell(
        status=CellStatus.TERMINATING,
        started_at=FAKE_NOW - 22000,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=0) == CellStatus.FINALIZED


# ---------------------------------------------------------------------------
# FINALIZED state — terminal / idempotent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("running_count", [0, 1, 5])
@pytest.mark.parametrize("consumed", [0, BUDGET, 50000])
def test_finalized_is_terminal(running_count, consumed):
    """FINALIZED is a terminal state — always returns FINALIZED regardless of clock or count."""
    cell = make_cell(
        status=CellStatus.FINALIZED,
        started_at=FAKE_NOW - consumed,
        budget_seconds=BUDGET,
        safety_buffer_seconds=BUFFER,
    )
    assert next_status(cell, now_epoch=FAKE_NOW, running_count=running_count) == CellStatus.FINALIZED
