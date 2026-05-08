# Phase 4: 6h Per-Cell Hard Cap + Cell-Concept Formalisation — Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 17 new/modified files
**Analogs found:** 17 / 17

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/automil/cells/__init__.py` | package public surface | request-response | `src/automil/trajectory/__init__.py` | exact |
| `src/automil/cells/state.py` | dataclass + atomic IO | file-I/O | `src/automil/backends/base.py` (frozen dataclass) + `src/automil/cli/lifecycle/_shared.py` (_atomic_write_text) | exact |
| `src/automil/cells/registry.py` | singleton, disk-persisted | CRUD | `src/automil/trajectory/recorder.py` (module-level state dict + path-keyed IO) | role-match |
| `src/automil/cells/cap.py` | pure state machine | event-driven | `src/automil/trajectory/schema.py` (pure validator function, no I/O) | role-match |
| `src/automil/cells/reconcile.py` | service, reconciliation | batch | `src/automil/graph.py:452-478` (_recover_orphans + add_executed) | role-match |
| `src/automil/runtime_helpers.py` | utility, signal handler | event-driven | `src/automil/runtime.py` (stdlib-only module, env-var read) | role-match |
| `src/automil/cli/cell.py` | CLI group + 2 subcommands | request-response | `src/automil/cli/trajectory.py` (Click group + subcommands) | exact |
| `src/automil/backends/_orchestrator_daemon.py` (modified) | daemon tick extension | event-driven | self (lines 938-961 tick() method) | exact (extend) |
| `src/automil/cli/submit.py` (modified) | CLI command, extended | request-response | self (lines 274-302, D-76 / D-97 metadata pattern) | exact (extend) |
| `src/automil/cli/__init__.py` (modified) | CLI group registration | — | self (lines 20-33, import-registers pattern) | exact (extend) |
| `src/automil/templates/config.yaml.j2` (modified) | config template | — | self + `benchmarks/experiments/ccrcc/automil/config.yaml` | exact (extend) |
| `tests/cells/__init__.py` | test package marker | — | `tests/trajectory/__init__.py` | exact |
| `tests/cells/test_cell_state.py` | unit test, dataclass + IO | file-I/O | `tests/trajectory/test_schema.py` (dataclass/schema unit tests) | role-match |
| `tests/cells/test_cap_state_machine.py` | unit test, pure function | request-response | `tests/trajectory/test_schema.py` (validate_event parametrized) | role-match |
| `tests/cells/test_aggregate_folds.py` | unit test, file-I/O | file-I/O | `tests/trajectory/test_recorder.py` (file-level tests with tmp_path) | role-match |
| `tests/cells/test_reconcile.py` | unit test, reconcile | batch | `tests/test_graph.py` (TestReconciliation class) | role-match |
| `tests/cells/test_cap_fires_with_partial_fold_recovery.py` | integration test (anti-acceptance) | event-driven | `tests/backends/test_contract.py` + conftest wait_for_state helper | partial |
| `tests/cells/test_cell_state_survives_daemon_kill_restart.py` | integration test, restart | event-driven | `tests/test_orchestrator_pid_starttime.py` (daemon state persistence) | role-match |
| `tests/cells/test_cli_cell_status_list.py` | CLI integration test | request-response | `tests/test_cli.py` (CliRunner + tmp_path + monkeypatch.chdir) | exact |

---

## Pattern Assignments

### `src/automil/cells/__init__.py` (package, request-response)

**Analog:** `src/automil/trajectory/__init__.py` (lines 1-43)

**Module header + imports pattern:**
```python
"""Cell budget-cap subpackage (CAP-01..06 / D-107..D-125).

Public surface: get_or_create_cell, get_cell, list_cells,
is_refusing_new, CellStatus, consumed_seconds.
"""
from __future__ import annotations

import logging

from automil.cells.state import Cell, CellStatus, consumed_seconds, write_cell
from automil.cells.registry import get_or_create_cell, get_cell, list_cells
from automil.cells.cap import next_status

logger = logging.getLogger(__name__)

__all__ = [
    "Cell",
    "CellStatus",
    "consumed_seconds",
    "write_cell",
    "get_or_create_cell",
    "get_cell",
    "list_cells",
    "next_status",
]
```

**Rules (copied from Phase 3 §1):**
- `__init__.py` imports only from sibling submodules — never the reverse.
- `__all__` explicitly lists every exported name.
- `logger = logging.getLogger(__name__)` is the first non-import line after imports.
- REQ-ID / decision annotations as comments per the existing convention.
- Do NOT auto-import test-only utilities at package level.
- Add `is_refusing_new` convenience helper that returns `cell.status in (CellStatus.REFUSING_NEW, CellStatus.TERMINATING, CellStatus.FINALIZED)`.

---

### `src/automil/cells/state.py` (dataclass + atomic IO, file-I/O)

**Frozen dataclass analog:** `src/automil/backends/base.py` lines 36-55 (JobHandle/JobSpec pattern)

**Atomic write analog:** `src/automil/cli/lifecycle/_shared.py` lines 21-38 (`_atomic_write_text`)

**Frozen dataclass pattern** (`src/automil/backends/base.py:36-55`):
```python
# src/automil/backends/base.py:36-55
from dataclasses import dataclass
from enum import Enum

class JobState(str, Enum):
    """String-valued so json.dumps works without a custom encoder."""
    PENDING  = "pending"
    RUNNING  = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BUDGET_KILLED = "budget_killed"

@dataclass(frozen=True)
class JobHandle:
    """Immutable reference — hashable, JSON-serialisable via dataclasses.asdict."""
    node_id: str
    backend: str
    opaque_id: str
    submitted_at: float
```

**CellStatus pattern** (mirror of JobState above):
```python
# src/automil/cells/state.py
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
    """Four-value cap state machine (D-110). str mixin → JSON-safe, no custom encoder."""
    ACTIVE       = "active"
    REFUSING_NEW = "refusing-new"
    TERMINATING  = "terminating"
    FINALIZED    = "finalized"


@dataclass(frozen=True)
class Cell:
    """Immutable budget-cap record (D-108). Frozen → hashable + no mid-tick mutation.

    Status transitions go through write_cell(), NOT in-place mutation.
    JSON-serialisable via dataclasses.asdict() — CellStatus str mixin serialises
    to its string value without a custom encoder. [VERIFIED: live execution]
    """
    cell_id: str
    dataset: str
    encoder: str
    parent_id: str
    started_at: float        # unix epoch, set once at creation (D-111 restart-safe)
    budget_seconds: int
    safety_buffer_seconds: int
    status: CellStatus
```

**`consumed_seconds` computed (NOT accumulated) pattern** (D-111):
```python
def consumed_seconds(cell: Cell) -> float:
    """Compute elapsed wall-clock from persisted started_at (D-111).

    NEVER accumulated — restart-safe: daemon kill at hour 4 of 6h cell
    still returns ~14400 on next call because started_at is persisted on disk.
    """
    return time.time() - cell.started_at
```

**Atomic write pattern** (`src/automil/cli/lifecycle/_shared.py:21-38`):
```python
# src/automil/cli/lifecycle/_shared.py:21-38 — canonical atomic write
def _atomic_write_text(path: Path, content: str) -> None:
    """Atomic tempfile + rename write (PATTERNS.md §3)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

**`write_cell()` follows the same pattern** — pass `dir=str(cells_dir)` to mkstemp to stay same-filesystem (Pitfall 2 in RESEARCH.md):
```python
# src/automil/cells/state.py
def write_cell(cell: Cell, cells_dir: Path) -> None:
    """Atomic write of cells/<cell_id>.json (D-112).

    Always pass dir=cells_dir to mkstemp — cross-device rename raises OSError
    if /tmp is on a different filesystem (RESEARCH.md Pitfall 2).
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
```

**`cell_id` derivation** (D-109):
```python
def make_cell_id(dataset: str, encoder: str, parent_id: str) -> str:
    return hashlib.sha256(
        f"{dataset}|{encoder}|{parent_id}".encode("utf-8")
    ).hexdigest()[:16]
```

---

### `src/automil/cells/registry.py` (singleton, CRUD)

**Analog:** `src/automil/trajectory/recorder.py` lines 23-30 (module-level state dict with lazy init)

**Module-level singleton dict pattern** (`src/automil/trajectory/recorder.py:23-30`):
```python
# src/automil/trajectory/recorder.py:23-30
_FD_CACHE: dict[str, int] = {}
_NODE_LOCKS: dict[str, threading.RLock] = {}
_DICT_LOCK = threading.Lock()
```

**Registry singleton pattern for cells:**
```python
# src/automil/cells/registry.py
from __future__ import annotations

import json
import logging
from pathlib import Path

from automil.cells.state import Cell, CellStatus, make_cell_id, write_cell
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

    If cell already exists: budget_seconds / safety_buffer_seconds overrides
    are IGNORED (D-134: override only on first submit that opens the cell).
    """
    import time
    cells_dir = _cells_dir()
    cell_id = make_cell_id(dataset, encoder, parent_id)
    path = cells_dir / f"{cell_id}.json"
    if path.exists():
        return _read_cell(path)
    # Create new cell with started_at = now (set once, never updated — D-111)
    cell = Cell(
        cell_id=cell_id,
        dataset=dataset,
        encoder=encoder,
        parent_id=parent_id,
        started_at=time.time(),
        budget_seconds=budget_seconds,
        safety_buffer_seconds=safety_buffer_seconds,
        status=CellStatus.ACTIVE,
    )
    write_cell(cell, cells_dir)
    return cell


def get_cell(cell_id: str) -> Cell | None:
    path = _cells_dir() / f"{cell_id}.json"
    if not path.exists():
        return None
    return _read_cell(path)


def list_cells() -> list[Cell]:
    cells_dir = _cells_dir()
    if not cells_dir.exists():
        return []
    cells = []
    for p in sorted(cells_dir.glob("*.json")):
        try:
            cells.append(_read_cell(p))
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Skipping malformed cell file %s: %s", p, exc)
    return cells


def _read_cell(path: Path) -> Cell:
    data = json.loads(path.read_text())
    data["status"] = CellStatus(data["status"])
    return Cell(**data)
```

---

### `src/automil/cells/cap.py` (pure state machine, event-driven)

**Analog:** `src/automil/trajectory/schema.py` lines 36-44 (`validate_event` — pure function, no I/O)

**Pure function pattern** (`src/automil/trajectory/schema.py:36-44`):
```python
# src/automil/trajectory/schema.py:36-44
def validate_event(d: dict) -> None:
    """Raise TrajectorySchemaError if a required gen_ai.* field is missing.

    Unknown fields pass silently — forward-compat per D-80.
    """
    missing = REQUIRED_FIELDS - set(d.keys())
    if missing:
        raise TrajectorySchemaError(f"Required fields missing: {sorted(missing)}")
```

**`next_status()` follows the same pure-function pattern** (D-113 verbatim):
```python
# src/automil/cells/cap.py
"""Two-tier cap state machine — pure function (CAP-02 / D-113).

No I/O. Caller persists the result via state.write_cell().
Side-effect-free → unit-testable without filesystem.
"""
from __future__ import annotations

from automil.cells.state import Cell, CellStatus


def next_status(cell: Cell, now_epoch: float, running_count: int) -> CellStatus:
    """Return the next CellStatus given current time and running experiment count.

    Pure function — no I/O, no side effects.
    Idempotent: FINALIZED always returns FINALIZED.

    Args:
        cell: Current cell state (immutable).
        now_epoch: Current wall-clock (time.time()); injected for testability.
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
```

**Key design note:** `next_status()` takes `now_epoch` as a parameter (D-113), so no `monkeypatch.setattr(time, "time", ...)` is needed in tests for this function. Clock injection is explicit. Only `consumed_seconds()` in `state.py` needs monkeypatching in tests.

---

### `src/automil/cells/reconcile.py` (service, batch)

**Analog:** `src/automil/backends/_orchestrator_daemon.py:452-478` (`_recover_orphans`) + `src/automil/graph.py:241-270` (`_reevaluate_descendants`)

**`_recover_orphans` pattern** (`src/automil/backends/_orchestrator_daemon.py:452-478`):
```python
# src/automil/backends/_orchestrator_daemon.py:452-478
def _recover_orphans(self):
    """Mark orphaned running experiments as crashed and clean up worktrees."""
    if not self.running_dir.exists():
        return
    for f in self.running_dir.glob("*.json"):
        try:
            spec = json.loads(f.read_text())
            node_id = spec.get("id", f.stem)
            logger.info(f"Orphaned experiment {node_id} found, marking as crashed")
            archive = self.archive_dir / node_id
            archive.mkdir(parents=True, exist_ok=True)
            result = {"status": "crash", "error": "Orchestrator restarted while running"}
            (archive / "result.json").write_text(json.dumps(result, indent=2))
            ...
        except Exception:
            continue
```

**`aggregate_folds()` pure function** (D-119):
```python
# src/automil/cells/reconcile.py
"""Budget-kill reconciliation + fold aggregation (CAP-04 / D-119, D-123, D-124)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def aggregate_folds(node_archive: Path, expected_fold_count: int) -> dict:
    """Walk archive/<node>/fold_*_result.json; return result.json payload.

    Pure function — no I/O side effects beyond reading fold files.
    Malformed fold files are skipped with WARNING (not silently used).

    Returns:
        status "completed" if all K folds present; "partial" if 1..K-1;
        "crashed" if 0 folds. composite is mean of per-fold composites.
    """
    fold_files = sorted(node_archive.glob("fold_*_result.json"))
    if not fold_files:
        return {
            "status": "crashed", "composite": 0.0,
            "partial_folds": 0, "expected_folds": expected_fold_count,
            "metrics": {},
        }

    composites: list[float] = []
    metrics_by_key: dict[str, list[float]] = {}
    elapsed_total = 0
    peak_vram = 0

    for ff in fold_files:
        try:
            data = json.loads(ff.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping malformed fold file %s: %s", ff, exc)
            continue
        composites.append(data.get("composite", 0.0))
        for k, v in data.get("metrics", {}).items():
            metrics_by_key.setdefault(k, []).append(float(v))
        elapsed_total += data.get("elapsed_seconds", 0)
        peak_vram = max(peak_vram, data.get("peak_vram_mb", 0))

    n = len(composites)
    if n == 0:
        return {
            "status": "crashed", "composite": 0.0,
            "partial_folds": 0, "expected_folds": expected_fold_count,
            "metrics": {},
        }

    return {
        "status": "completed" if n == expected_fold_count else "partial",
        "composite": sum(composites) / n,
        "metrics": {k: sum(v) / len(v) for k, v in metrics_by_key.items()},
        "partial_folds": n,
        "expected_folds": expected_fold_count,
        "elapsed_seconds": elapsed_total,
        "peak_vram_mb": peak_vram,
    }
```

**`reconcile_budget_kill()` pattern** (D-123; mirrors `_recover_orphans` + calls `_reevaluate_descendants`):
```python
def reconcile_budget_kill(node_id: str, archive_dir: Path,
                          graph: "ExperimentGraph",
                          expected_fold_count: int) -> None:
    """Post-cancel reconciliation for cap-driven kills (CAP-04 / D-123).

    Called by the daemon when it observes cancel_reason == "cap".
    ≥1 fold → status: executed, metadata.budget_killed: true.
    0 folds → status: crashed, metadata.budget_killed: true.
    In both cases _reevaluate_descendants is triggered — cascade runs on
    numeric composite (Fragile Invariant #6 defence: cascade against
    partial composite, NOT zero).
    """
    payload = aggregate_folds(archive_dir / node_id, expected_fold_count)
    payload["metadata"] = {"budget_killed": True}
    result_path = archive_dir / node_id / "result.json"
    result_path.write_text(json.dumps(payload, indent=2))

    if payload["partial_folds"] >= 1:
        graph.add_executed(
            node_id,
            composite=payload["composite"],
            metrics=payload["metrics"],
            status="keep",  # Pareto decides keep/discard via _reevaluate_descendants
            ...
        )
    else:
        graph.mark_failed(node_id, status="crash")
```

**`_reevaluate_descendants` operates on numeric `composite`** (`src/automil/graph.py:254-270`):
```python
# src/automil/graph.py:254-270 — no change needed; already float arithmetic
p_comp = parent.get("composite", 0)   # float, NOT status string
c_comp = child.get("composite", 0)
keep = (c_auc >= p_auc and c_bacc >= p_bacc and c_comp > p_comp)
```

---

### `src/automil/runtime_helpers.py` (utility, event-driven)

**Analog:** `src/automil/runtime.py` lines 1-23 (stdlib-only module, single public function, env-var read)

**Module header pattern** (`src/automil/runtime.py:1-23`):
```python
# src/automil/runtime.py:1-23
"""Runtime declaration — reads AUTOMIL_RUNTIME env var (TRJ-04 / D-87)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def get_runtime() -> str:
    """Return the declared runtime identifier. Returns "unknown" if unset."""
    return os.environ.get("AUTOMIL_RUNTIME", "unknown")
```

**`runtime_helpers.py` SIGTERM handler pattern** (D-121):
```python
# src/automil/runtime_helpers.py
"""SIGTERM flush helper and fold count accessor (CAP-03 / D-121, D-122).

register_sigterm_flush() MUST be called in the training script's main()
before any DataLoader/multiprocessing initialisation. signal.signal() only
works in the main thread of the main interpreter — calling it from a
DataLoader worker raises ValueError (RESEARCH.md Pitfall 1). [VERIFIED]
"""
from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_SIGTERM_REGISTERED = False  # module-level idempotent guard


def register_sigterm_flush(*, fold_count_env: str = "AUTOMIL_FOLD_COUNT") -> None:
    """Install SIGTERM handler that flushes partial fold results and exits 0.

    Idempotent — calling twice is a no-op (module-level _SIGTERM_REGISTERED guard).
    Handler writes result.json with status="partial" to CWD, then sys.exit(0).
    sys.exit(0) (NOT 130): returncode 0 lets the daemon distinguish graceful
    flush from process death before flush. [VERIFIED: subprocess test]

    CALL THIS before creating any DataLoader or threading.Thread. signal.signal()
    raises ValueError if called from a non-main thread.
    """
    global _SIGTERM_REGISTERED
    if _SIGTERM_REGISTERED:
        return

    def _handler(signum: int, frame: object) -> None:
        from automil.cells.reconcile import aggregate_folds  # lazy import
        import json
        n = get_fold_count()
        payload = aggregate_folds(Path.cwd(), n)
        (Path.cwd() / "result.json").write_text(json.dumps(payload, indent=2))
        sys.exit(0)  # NOT sys.exit(130) — clean exit signals graceful flush

    signal.signal(signal.SIGTERM, _handler)
    _SIGTERM_REGISTERED = True


def get_fold_count() -> int:
    """Read AUTOMIL_FOLD_COUNT env var (injected by orchestrator). Default 5."""
    return int(os.environ.get("AUTOMIL_FOLD_COUNT", "5"))
```

---

### `src/automil/cli/cell.py` (CLI group + 2 subcommands, request-response)

**Analog:** `src/automil/cli/trajectory.py` lines 1-13 (Click group + subcommands)

**Click group pattern** (`src/automil/cli/trajectory.py:1-13`):
```python
# src/automil/cli/trajectory.py:1-13
"""trajectory subgroup: record and export trajectory events (TRJ-04, TRJ-05 / D-94)."""
from __future__ import annotations

import click

from automil.cli import main


@main.group("trajectory")
def trajectory_group() -> None:
    """Trajectory capture and export commands."""
    pass


@trajectory_group.command("record")
@click.argument("event_json")
def record(event_json: str) -> None:
    """Record one trajectory event (runtime-agnostic CLI fallback)."""
    import json
    from automil.trajectory import record_event  # lazy import
    ...
```

**`automil cell` group pattern:**
```python
# src/automil/cli/cell.py
"""cell subgroup: cell budget status and list commands (CAP-06 / D-125)."""
from __future__ import annotations

import click

from automil.cli import main


@main.group("cell")
def cell_group() -> None:
    """Cell budget-cap management commands."""
    pass


@cell_group.command("status")
@click.argument("cell_id", required=False)
@click.option("--no-header", is_flag=True, default=False, help="Suppress header row.")
def cell_status(cell_id: str | None, no_header: bool) -> None:
    """Show budget state for one cell (or all cells if CELL_ID omitted)."""
    import time
    from datetime import datetime
    from automil.cells import list_cells, consumed_seconds  # lazy import
    ...


@cell_group.command("list")
@click.option("--no-header", is_flag=True, default=False, help="Pipe-friendly: no header.")
def cell_list(no_header: bool) -> None:
    """Short-form cell listing (cell_id, status, consumed/budget)."""
    from automil.cells import list_cells, consumed_seconds  # lazy import
    ...
```

**Lazy import inside command body** (Phase 1+3 pattern, all CLI commands follow this):
```python
# In every @cell_group.command body:
from automil.cells import list_cells, consumed_seconds  # lazy import
```

**CLI table formatting** (stdlib f-string; no rich/tabulate in deps):
```python
# src/automil/cli/cell.py — table format per RESEARCH.md §Code Examples
HEADER = (
    f"{'cell_id':<8}  {'dataset':<8}  {'encoder':<8}  {'parent':<10}  "
    f"{'started':<19}  {'consumed/budget':<17}  {'status':<14}  {'running':<7}"
)
if not no_header:
    click.echo(HEADER)
    click.echo("-" * len(HEADER))
for cell in cells:
    consumed = time.time() - cell.started_at
    h, rem = divmod(int(consumed), 3600)
    m, s = divmod(rem, 60)
    consumed_str = f"{h:02d}:{m:02d}:{s:02d}"
    bh, brem = divmod(cell.budget_seconds, 3600)
    bm = brem // 60
    budget_str = f"{bh:02d}:{bm:02d}:00"
    started_str = datetime.fromtimestamp(cell.started_at).strftime("%Y-%m-%d %H:%M:%S")
    click.echo(
        f"{cell.cell_id[:8]:<8}  {cell.dataset:<8}  {cell.encoder:<8}  "
        f"{cell.parent_id[:10]:<10}  {started_str:<19}  "
        f"{consumed_str}/{budget_str:<17}  {cell.status.value:<14}  {running_count:<7}"
    )
```

**ClickException error format** (Phase 1 PATTERNS §7):
```python
# src/automil/cli/submit.py:61-67 — exact error format to copy
raise click.ClickException(
    f"Refusing to submit: {node} is already {ntype}/{nstatus}. "
    f"Submitting would overwrite its archive and destroy prior "
    f"results. Use 'automil propose' to create a new proposal, "
    f"then submit against that new node id."
)
```

---

### `src/automil/backends/_orchestrator_daemon.py` (modified) — `_tick_cells()` extension

**Analog:** `src/automil/backends/_orchestrator_daemon.py:938-961` (`tick()` method — extend, not replace)

**Current `tick()` method** (`src/automil/backends/_orchestrator_daemon.py:938-961`):
```python
# src/automil/backends/_orchestrator_daemon.py:938-961
def tick(self):
    """Single scheduling cycle."""
    # 0. Hot-reload config
    self._reload_orchestrator_config()
    # 1. Check running experiments
    self._check_running()
    # 2. Schedule pending experiments (skip if draining)
    if not self.draining:
        pending = self._get_pending()
        for spec in pending:
            ...
    # 3. Save state
    self._save_state()
```

**Phase 4 extension — add `_tick_cells()` as step 1.5** (D-114):
```python
def tick(self):
    """Single scheduling cycle."""
    self._reload_orchestrator_config()
    self._check_running()
    self._tick_cells()          # NEW Phase 4 step — inserted here
    if not self.draining:
        ...
    self._save_state()

def _tick_cells(self) -> None:
    """Advance cap state machine for all active cells (CAP-02 / D-114).

    Idempotent — re-running the tick on an already-transitioned cell is a no-op.
    TERMINATING fires backend.cancel(SIGTERM) on all running in-cell experiments.
    Process-group kill is the backend's responsibility (D-57 / D-115 / LocalBackend).
    """
    import signal as sig_mod
    from dataclasses import replace
    from automil.cells import list_cells, next_status, write_cell, CellStatus

    now = time.time()
    for cell in list_cells():
        running = self._running_in_cell(cell.cell_id)
        new_status = next_status(cell, now, len(running))
        if new_status != cell.status:
            if new_status == CellStatus.TERMINATING:
                for handle in running:
                    # D-115: reuses existing cancel(SIGTERM) path
                    # LocalBackend: 30s grace + SIGKILL, process-group kill
                    self.backend.cancel(handle, signal=sig_mod.SIGTERM)
            write_cell(replace(cell, status=new_status))
            logger.info(
                "_tick_cells: %s transitioned %s → %s",
                cell.cell_id[:8], cell.status.value, new_status.value,
            )

def _running_in_cell(self, cell_id: str) -> list:
    """Return JobHandles for experiments in this cell that are in self.running."""
    return [
        exp.handle for exp in self.running.values()
        if exp.spec.get("metadata", {}).get("cell_id") == cell_id
    ]
```

**cancel_reason annotation before backend.cancel()** (Pitfall 4 in RESEARCH.md):
```python
# In _tick_cells() when transitioning to TERMINATING:
# Write cancel_reason to running/<node_id>.json BEFORE calling cancel —
# reconcile_budget_kill checks metadata.cancel_reason == "cap" (Pitfall 4).
for handle in running:
    running_spec_path = self.running_dir / f"{handle.node_id}.json"
    if running_spec_path.exists():
        try:
            spec_data = json.loads(running_spec_path.read_text())
            spec_data.setdefault("metadata", {})["cancel_reason"] = "cap"
            running_spec_path.write_text(json.dumps(spec_data, indent=2))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not annotate cancel_reason for %s: %s", handle.node_id, exc)
    self.backend.cancel(handle, signal=sig_mod.SIGTERM)
```

---

### `src/automil/cli/submit.py` (modified) — cell refusal hook

**Analog:** `src/automil/cli/submit.py:274-302` (D-76 backend + D-97 runtime metadata pattern)

**Existing metadata injection pattern** (`src/automil/cli/submit.py:274-302`):
```python
# src/automil/cli/submit.py:274-278 — D-76 backend metadata
_backend_name: str = _automil_cfg.get("backend", {}).get("name", "local")
...
spec.setdefault("metadata", {})["backend"] = _backend_name
# src/automil/cli/submit.py:299-302 — D-97 runtime metadata
spec.setdefault("metadata", {})["runtime"] = os.environ.get("AUTOMIL_RUNTIME", "unknown")
```

**Phase 4 cell refusal hook** (D-116, D-117, D-134) — insert AFTER parent guard, BEFORE file snapshotting:
```python
# In submit(), after parent-node guard (line ~113), before file list determination:

# D-134: resolve budget_seconds with 3-tier precedence (CLI flag > config > fallback)
_cap_cfg = _automil_cfg.get("cap", {})
_resolved_budget = budget_seconds or _cap_cfg.get("budget_seconds", 21600)
_resolved_buffer = safety_buffer_seconds or _cap_cfg.get("safety_buffer_seconds", 1800)

# D-116: get or create cell; check status before writing queue spec
from automil.cells import get_or_create_cell, CellStatus, consumed_seconds as cell_consumed

_parent_id_for_cell = parent or "root"
cell = get_or_create_cell(
    dataset=config.get("dataset", {}).get("name", "unknown"),
    encoder=config.get("encoder", {}).get("name", "unknown"),
    parent_id=_parent_id_for_cell,
    budget_seconds=_resolved_budget,
    safety_buffer_seconds=_resolved_buffer,
)
if cell.status in (CellStatus.REFUSING_NEW, CellStatus.TERMINATING, CellStatus.FINALIZED):
    raise click.ClickException(
        f"Cell {cell.cell_id[:8]} is {cell.status.value}: budget exhausted "
        f"({cell_consumed(cell):.0f}/{cell.budget_seconds}s consumed). "
        f"Wait for cell to finalize or use a different (dataset, encoder, parent_id) tuple."
    )
# D-117: write cell_id to spec metadata (symmetric to metadata.backend, metadata.runtime)
spec.setdefault("metadata", {})["cell_id"] = cell.cell_id
```

**New `--budget-seconds` / `--safety-buffer-seconds` Click options** (D-134) — add to `@main.command()` decorator:
```python
@click.option("--budget-seconds", default=None, type=int,
              help="Override cap.budget_seconds for this cell (on cell creation only).")
@click.option("--safety-buffer-seconds", default=None, type=int,
              help="Override cap.safety_buffer_seconds for this cell (on cell creation only).")
```

---

### `src/automil/cli/__init__.py` (modified) — cell.py registration

**Analog:** `src/automil/cli/__init__.py:20-33` (alphabetical import-register pattern)

**Current registration block** (`src/automil/cli/__init__.py:20-33`):
```python
# src/automil/cli/__init__.py:20-33
from automil.cli import cancel  # noqa: E402,F401
from automil.cli import check   # noqa: E402,F401
...
from automil.cli import trajectory  # noqa: E402,F401
from automil.cli import viz     # noqa: E402,F401
```

**Phase 4 addition** — insert alphabetically (after `cancel`, before `check`):
```python
from automil.cli import cell        # noqa: E402,F401  (CAP-06 / D-125)
```

---

## Shared Patterns

### Atomic write via tempfile + os.replace

**Source:** `src/automil/cli/lifecycle/_shared.py:21-38`
**Also used in:** `src/automil/backends/local.py:147-166`
**Apply to:** `cells/state.py:write_cell()` and any function that writes to `cells/<id>.json`

```python
# src/automil/cli/lifecycle/_shared.py:21-38
def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

**Critical:** Always pass `dir=str(path.parent)` to `mkstemp` so the temp file is on the same filesystem as the destination. `os.replace()` (not `os.rename()`) for POSIX atomicity.

---

### str Enum for JSON-safe status

**Source:** `src/automil/backends/base.py:20-33`
**Apply to:** `CellStatus` in `cells/state.py`

```python
# src/automil/backends/base.py:20-33
class JobState(str, Enum):
    """String-valued so json.dumps works without a custom encoder."""
    PENDING = "pending"
    RUNNING = "running"
    ...
    BUDGET_KILLED = "budget_killed"
```

**Rule:** `class CellStatus(str, Enum)` follows the same pattern. `dataclasses.asdict(cell)` will serialize the enum to its string value directly.

---

### Frozen dataclass with `dataclasses.replace()` for transitions

**Source:** `src/automil/backends/base.py:36-55` (JobHandle)
**Apply to:** `Cell` in `cells/state.py`, transition calls in `_tick_cells()`

```python
# CORRECT pattern — produce new instance, caller persists atomically
from dataclasses import replace
new_cell = replace(cell, status=CellStatus.REFUSING_NEW)
write_cell(new_cell, cells_dir)

# WRONG — raises FrozenInstanceError (frozen=True)
# cell.status = CellStatus.REFUSING_NEW
```

---

### ClickException error format

**Source:** `src/automil/cli/submit.py:61-67` (Phase 1 PATTERNS §7)
**Apply to:** cell refusal in `cli/submit.py`, validation errors in `cli/cell.py`

```python
raise click.ClickException(
    f"Refusing to submit: {node} is already {ntype}/{nstatus}. "
    f"Submitting would overwrite its archive and destroy prior "
    f"results. Use 'automil propose' to create a new proposal, "
    f"then submit against that new node id."
)
```

**Rule:** Always include: (a) what triggered the error, (b) what state was observed, (c) what the operator can do next. Pitfall-9 mitigation — silent rejection is debug-hostile.

---

### Lazy import inside command body

**Source:** `src/automil/cli/trajectory.py:30` / `src/automil/cli/reconcile.py:39`
**Apply to:** All `@cell_group.command()` function bodies

```python
# src/automil/cli/reconcile.py:39 — canonical example
def reconcile(recompute_best: bool, dry_run: bool):
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph  # lazy import
    ...
```

**Rule:** Import heavy modules (automil.cells, automil.graph, etc.) inside command bodies, not at module level. This keeps the `automil --help` invocation fast.

---

### Module docstring + `from __future__ import annotations` header

**Source:** `src/automil/backends/base.py:1-3`, `src/automil/trajectory/schema.py:1-7`
**Apply to:** Every new module in `cells/`, `runtime_helpers.py`, `cli/cell.py`

```python
"""One-line purpose with REQ-IDs and decisions (CAP-NN / D-NNN)."""
from __future__ import annotations

import logging
...
logger = logging.getLogger(__name__)
```

---

### Test file structure (unit tests in subpackage)

**Source:** `tests/trajectory/test_schema.py:1-20`
**Apply to:** `tests/cells/test_cell_state.py`, `tests/cells/test_cap_state_machine.py`, etc.

```python
# tests/trajectory/test_schema.py:1-20
"""Schema version forward-compat + validate_event tests (TRJ-01, TRJ-06 / D-80, D-81)."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from automil.trajectory.schema import (
    validate_event,
    TrajectorySchemaError,
    REQUIRED_FIELDS,
)


def test_validate_event_passes_with_all_required_fields() -> None:
    """One-line docstring describing the assertion."""
    ...

@pytest.mark.parametrize("missing_field", sorted(REQUIRED_FIELDS))
def test_validate_event_fails_on_missing_required_field(missing_field: str) -> None:
    ...
```

**Rule:** Tests are grouped in classes (`TestCellState`, `TestCapStateMachine`) or as module-level functions with descriptive names. `pytest.mark.parametrize` for exhaustive state-machine transitions. `tmp_path` fixture for file-system tests.

---

### Test conftest fixtures

**Source:** `tests/backends/conftest.py:1-153`
**Apply to:** `tests/cells/` — needs a `conftest.py` with a `cell_factory` fixture and a `cells_dir` tmp fixture

```python
# tests/backends/conftest.py:64-93 — make_spec factory pattern
def make_spec(node_id: str, tmp_path: Path, command=..., **kwargs) -> JobSpec:
    defaults = { "node_id": node_id, ... }
    defaults.update(kwargs)
    return JobSpec(**defaults)
```

**Cells analog:**
```python
# tests/cells/conftest.py
import pytest, time
from pathlib import Path
from automil.cells.state import Cell, CellStatus

@pytest.fixture
def cells_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cells"
    d.mkdir()
    return d

def make_cell(
    cell_id: str = "abc1234567890123",
    status: CellStatus = CellStatus.ACTIVE,
    started_at: float | None = None,
    budget_seconds: int = 21600,
    safety_buffer_seconds: int = 1800,
    **kwargs,
) -> Cell:
    return Cell(
        cell_id=cell_id,
        dataset="test",
        encoder="enc",
        parent_id="node_0001",
        started_at=started_at or time.time(),
        budget_seconds=budget_seconds,
        safety_buffer_seconds=safety_buffer_seconds,
        status=status,
        **kwargs,
    )
```

---

## No Analog Found

All Phase 4 files have analogs. None require RESEARCH.md patterns as the primary reference.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | — |

---

## Metadata

**Analog search scope:** `src/automil/`, `src/automil/cli/`, `src/automil/backends/`, `src/automil/trajectory/`, `src/automil/registry/`, `tests/`, `tests/trajectory/`, `tests/backends/`
**Files scanned:** 28 source + 15 test files
**Pattern extraction date:** 2026-05-05
