"""Cell budget-cap subpackage (CAP-01..06 / D-107..D-134).

Public surface (populated incrementally across Phase 4 plans):
    04-01: Cell, CellStatus, consumed_seconds, write_cell, make_cell_id, read_cell
    04-02: aggregate_folds (early stub, replaced by 04-04)
    04-03: cap state machine — next_status (Wave 2)
    04-04: aggregate_folds final, reconcile_budget_kill (Wave 3)
    04-05: registry — get_or_create_cell, get_cell, list_cells, is_refusing_new (Wave 4)
"""
from __future__ import annotations

import logging

from automil.cells.reconcile import aggregate_folds
from automil.cells.state import (
    Cell,
    CellStatus,
    consumed_seconds,
    make_cell_id,
    read_cell,
    write_cell,
)

logger = logging.getLogger(__name__)

__all__ = [
    "Cell",
    "CellStatus",
    "aggregate_folds",
    "consumed_seconds",
    "make_cell_id",
    "read_cell",
    "write_cell",
]
