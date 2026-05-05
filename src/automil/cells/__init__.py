"""Cell budget-cap subpackage (CAP-01..06 / D-107..D-125).

Public surface: Cell, CellStatus, consumed_seconds, write_cell,
make_cell_id, read_cell. Other modules (registry, cap, reconcile)
are added by Wave 2 plans.
"""
from __future__ import annotations

import logging

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
    "consumed_seconds",
    "make_cell_id",
    "read_cell",
    "write_cell",
]
