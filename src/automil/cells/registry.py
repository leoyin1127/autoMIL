"""Cell CRUD + lazy registry (CAP-01, CAP-05 / D-107, D-116, D-134).

Cells are persisted to automil/cells/<cell_id>.json. The registry is
"singleton-ish" — module-level functions reading/writing the on-disk
state. No in-memory cache (would conflict with daemon-restart safety).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from automil.cells.state import (
    Cell,
    CellStatus,
    make_cell_id,
    read_cell,
    write_cell,
)
from automil.cli._helpers import _find_automil_dir

logger = logging.getLogger(__name__)


def _cells_dir() -> Path:
    """Locate automil/cells/ relative to the automil/ overlay dir."""
    return _find_automil_dir() / "cells"


def get_or_create_cell(
    dataset: str,
    encoder: str,
    parent_id: str,
    budget_seconds: int,
    safety_buffer_seconds: int,
) -> Cell:
    """Return existing cell or create a new one (lazy + idempotent, D-116).

    D-134: budget_seconds and safety_buffer_seconds overrides apply ONLY when
    this call CREATES the cell. If the cell already exists, the persisted
    values are kept and the override is logged at INFO. Allowing later
    submits to extend a cell's budget = sandbagging vector.

    Args:
        dataset: e.g. "ccrcc" — from automil/config.yaml.
        encoder: e.g. "uni-v2" — from automil/config.yaml.
        parent_id: graph node_id of cell-root experiment, or "root" for top-level.
        budget_seconds: cap; honored only on creation.
        safety_buffer_seconds: refusing-new lead time; honored only on creation.
    """
    cells_dir = _cells_dir()
    cell_id = make_cell_id(dataset, encoder, parent_id)
    path = cells_dir / f"{cell_id}.json"
    if path.exists():
        cell = read_cell(path)
        if cell.budget_seconds != budget_seconds or cell.safety_buffer_seconds != safety_buffer_seconds:
            logger.info(
                "Cell %s already open with budget_seconds=%d safety_buffer_seconds=%d; "
                "ignoring override (budget_seconds=%d safety_buffer_seconds=%d) per D-134.",
                cell_id[:8], cell.budget_seconds, cell.safety_buffer_seconds,
                budget_seconds, safety_buffer_seconds,
            )
        return cell

    # First submit for this (dataset, encoder, parent_id) tuple → open the cell.
    cell = Cell(
        cell_id=cell_id,
        dataset=dataset,
        encoder=encoder,
        parent_id=parent_id,
        started_at=time.time(),  # set ONCE at creation; never updated (D-111)
        budget_seconds=budget_seconds,
        safety_buffer_seconds=safety_buffer_seconds,
        status=CellStatus.ACTIVE,
    )
    write_cell(cell, cells_dir)
    logger.info(
        "Opened cell %s: dataset=%s encoder=%s parent=%s budget=%ds buffer=%ds",
        cell_id[:8], dataset, encoder, parent_id, budget_seconds, safety_buffer_seconds,
    )
    return cell


def get_cell(cell_id: str) -> Cell | None:
    """Return Cell with the given cell_id, or None if not found."""
    path = _cells_dir() / f"{cell_id}.json"
    if not path.exists():
        return None
    try:
        return read_cell(path)
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        logger.warning("Could not read cell %s: %s", cell_id[:8], exc)
        return None


def list_cells() -> list[Cell]:
    """Return all cells under automil/cells/, sorted by cell_id.

    Malformed cell files are skipped with logger.warning.
    """
    cells_dir = _cells_dir()
    if not cells_dir.exists():
        return []
    cells: list[Cell] = []
    for p in sorted(cells_dir.glob("*.json")):
        try:
            cells.append(read_cell(p))
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as exc:
            logger.warning("Skipping malformed cell file %s: %s", p, exc)
    return cells


def is_refusing_new(cell: Cell) -> bool:
    """True iff cell's status blocks new submits (D-116)."""
    return cell.status in (
        CellStatus.REFUSING_NEW,
        CellStatus.TERMINATING,
        CellStatus.FINALIZED,
    )
