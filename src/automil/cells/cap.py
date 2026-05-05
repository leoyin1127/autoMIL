"""Two-tier cap state machine — pure function (CAP-02 / D-113).

No I/O. Caller persists the result via state.write_cell().
Side-effect-free → unit-testable without filesystem.
"""
from __future__ import annotations

from automil.cells.state import Cell, CellStatus


def next_status(cell: Cell, now_epoch: float, running_count: int) -> CellStatus:
    """Return the next CellStatus given current time and running experiment count.

    Pure function — no I/O, no global state, no time.time() call.
    Idempotent: FINALIZED always returns FINALIZED.

    Args:
        cell: Current cell state (immutable).
        now_epoch: Current wall-clock (caller passes time.time()); explicit
            injection makes the function testable without monkeypatch.
        running_count: Count of in-cell experiments NOT in terminal state.
    """
    consumed = now_epoch - cell.started_at
    remaining = cell.budget_seconds - consumed

    if cell.status == CellStatus.ACTIVE:
        if remaining <= cell.safety_buffer_seconds:
            return CellStatus.REFUSING_NEW
        return CellStatus.ACTIVE

    if cell.status == CellStatus.REFUSING_NEW:
        if remaining <= 0:
            return CellStatus.TERMINATING
        return CellStatus.REFUSING_NEW

    if cell.status == CellStatus.TERMINATING:
        if running_count == 0:
            return CellStatus.FINALIZED
        return CellStatus.TERMINATING

    return cell.status  # FINALIZED is terminal
