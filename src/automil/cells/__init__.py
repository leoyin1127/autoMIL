"""automil.cells — per-cell wall-clock budget enforcement (CAP-01..06 / D-107..D-134).

Public surface (populated incrementally across Phase 4 plans):
    Phase 4-01: get_or_create_cell, get_cell, list_cells, is_refusing_new, CellStatus
    Phase 4-05: aggregate_folds (reconcile sub-module)
    Phase 4-06: cap state machine, next_status
    Phase 4-07: reconcile_budget_kill
"""
from __future__ import annotations
