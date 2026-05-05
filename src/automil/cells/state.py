"""Cell state primitives — frozen dataclass, str Enum, atomic IO (CAP-01, CAP-05 / D-107..D-112)."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class CellStatus(str, Enum):
    """Cap state machine lifecycle values (D-110).

    String-valued so ``json.dumps(CellStatus.ACTIVE)`` returns ``'"active"'``
    without a custom encoder.  Four values exhaust the two-tier cap machine.
    """

    ACTIVE = "active"
    REFUSING_NEW = "refusing-new"
    TERMINATING = "terminating"
    FINALIZED = "finalized"


@dataclass(frozen=True)
class Cell:
    """Immutable snapshot of a (dataset, encoder, parent_id) budget cell (D-108).

    Frozen so ``Cell`` instances cannot be mutated mid-tick.  Status transitions
    go through ``dataclasses.replace(cell, status=new_status)`` followed by
    ``write_cell(cell, cells_dir)`` — atomic on-disk replacement, never
    in-place mutation.  Hashable + JSON-serialisable via
    ``dataclasses.asdict(cell)``.
    """

    cell_id: str
    """16-char hex derived from sha256(dataset|encoder|parent_id)[:16]."""

    dataset: str
    """Dataset identifier, e.g. ``"ccrcc"`` — from automil/config.yaml."""

    encoder: str
    """Encoder identifier, e.g. ``"uni-v2"`` — from automil/config.yaml."""

    parent_id: str
    """Graph node_id of the cell-root experiment (the first submit that opens the cell)."""

    started_at: float
    """Unix epoch seconds (UTC) when the cell was created — absolute wall-clock,
    NOT relative.  Written ONCE at cell creation; never updated."""

    budget_seconds: int
    """Consumer-supplied wall-clock budget.  Framework fallback: 21600 (6h),
    Leo's autoMIL-paper campaign default across CCRCC/CLWD/future datasets.
    A different consumer (sklearn-iris, external lab) sets their own value."""

    safety_buffer_seconds: int
    """Consumer-supplied pre-termination warning window.  Framework fallback: 1800 (30 min).
    Must be < budget_seconds.  At T - safety_buffer the cell transitions
    ACTIVE → REFUSING_NEW."""

    status: CellStatus
    """Current cap lifecycle state (D-110)."""


def make_cell_id(dataset: str, encoder: str, parent_id: str) -> str:
    """Return a 16-char deterministic hex id for the (dataset, encoder, parent_id) triple.

    Same input always maps to the same id — re-submits join the existing cell.
    Collision space: ~6.4×10¹⁹ (sha256 prefix, 64-bit).

    >>> make_cell_id("ccrcc", "uni-v2", "node_0042") == make_cell_id("ccrcc", "uni-v2", "node_0042")
    True
    """
    return hashlib.sha256(f"{dataset}|{encoder}|{parent_id}".encode("utf-8")).hexdigest()[:16]


def consumed_seconds(cell: Cell) -> float:
    """Return computed wall-clock elapsed seconds for the cell (D-111).

    Computed wall-clock — NEVER accumulated.  Restart-safe: daemon kill at hour 4
    of a 6h cell still returns ~14400 because started_at is persisted on disk.
    There is NO counter accumulation anywhere — that pattern is the sandbagging bug.
    """
    return time.time() - cell.started_at


def write_cell(cell: Cell, cells_dir: Path) -> None:
    """Atomically write cell state to ``cells_dir/<cell_id>.json`` (D-112).

    Uses ``tempfile.mkstemp(dir=str(cells_dir))`` to keep the temp file on the
    same filesystem as the destination so ``os.replace`` is an atomic POSIX rename
    (Pitfall 2 defence — cross-filesystem renames are NOT atomic).

    On failure the temp file is cleaned up and the exception re-raised.
    """
    cells_dir.mkdir(parents=True, exist_ok=True)
    path = cells_dir / f"{cell.cell_id}.json"
    payload = json.dumps(dataclasses.asdict(cell), indent=2)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(cells_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def read_cell(path: Path) -> Cell:
    """Deserialise a cell from ``cells/<cell_id>.json``.

    Re-hydrates ``CellStatus`` from its string value so the returned ``Cell``
    is fully typed — ``cell.status == CellStatus.ACTIVE``, not ``"active"``.
    """
    data = json.loads(path.read_text())
    data["status"] = CellStatus(data["status"])
    return Cell(**data)
