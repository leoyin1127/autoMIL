# Phase 4: 6h Per-Cell Hard Cap + Cell-Concept Formalisation — Research

**Researched:** 2026-05-03
**Domain:** Python signal handling, process-group kill discipline, frozen dataclass + str Enum patterns, atomic file IO, daemon tick integration, fold-checkpoint aggregation, descendant cascade mechanics, CLI table formatting (stdlib), test-clock manipulation
**Confidence:** HIGH (all critical claims verified against live code inspection, Python stdlib execution, or direct codebase reads; no ASSUMED claims)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All decisions D-107 through D-133 are locked. See 04-CONTEXT.md `<decisions>` block verbatim.

Key locked choices that directly constrain implementation:
- D-107: `src/automil/cells/` package with five modules: `__init__.py`, `state.py`, `registry.py`, `cap.py`, `reconcile.py`
- D-108: `Cell` is a frozen dataclass in `cells/state.py`
- D-109: `cell_id = sha256(f"{dataset}|{encoder}|{parent_id}".encode("utf-8")).hexdigest()[:16]`
- D-110: `CellStatus` is a `str`-valued Enum (four values)
- D-111: `consumed_seconds` COMPUTED as `time.time() - cell.started_at` — never accumulated
- D-112: Atomic writes via `tempfile.mkstemp + os.rename`
- D-113: Cap state machine is a pure function in `cells/cap.py`
- D-114: Daemon extends `_tick_cells()` in `_orchestrator_daemon.py`
- D-115: Cancel signal contract: SIGTERM, 30s grace, SIGKILL — per Phase 2 D-57
- D-116/D-117: Submit-path refusal hook; `metadata.cell_id` on every node
- D-118: Per-fold file shape: `archive/<node_id>/fold_<i>_result.json`
- D-119: `aggregate_folds()` lives in `cells/reconcile.py` — pure function
- D-120: `expected_fold_count` from `AUTOMIL_FOLD_COUNT` env var
- D-121: `automil.runtime_helpers` is a new module at `src/automil/runtime_helpers.py`
- D-122: Orchestrator does NOT inject SIGTERM handler — opt-in by training script
- D-123: `reconcile_budget_kill(node_id)` entry point in `cells/reconcile.py`
- D-124: `metadata.budget_killed` discriminates cap-kill from organic crash
- D-125: `automil cell` Click group at `src/automil/cli/cell.py`; two subcommands
- D-126: Acceptance gate: conjunction of 7 test files in `tests/cells/`
- D-127 through D-133: Out of scope (GC, pooling, adaptive buffer, per-exp caps, viz, healthcheck, SLURM)

**Hard floors:**
- Phase 0+1+2+3 baseline (567 tests + 9 skipped) stays green
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/cells/` returns zero
- Anti-acceptance gate: `test_cap_fires_with_partial_fold_recovery.py` must pass

### Claude's Discretion

- Implementation details not covered by D-107..D-133 (exact conftest fixtures, helper variable naming, internal error message wording, test parametrisation)

### Deferred Ideas (OUT OF SCOPE)

- Cell garbage collection (D-127)
- Cross-cell budget pooling (D-128)
- Adaptive `safety_buffer_seconds` (D-129)
- Per-experiment budget caps (D-130)
- Cap UI in viz dashboard (D-131)
- `Backend.healthcheck()` integration (D-132)
- SLURM `--time` integration (D-133)
- Mid-fold checkpointing within a single fold's training loop
- Cap-fire metrics export (Prometheus, OTel)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAP-01 | `(dataset, encoder, parent_id)` cell is a first-class entity; `cells/<cell_id>.json` persists `started_at`, `budget_seconds`, `consumed_seconds`, status | §1, §2 — Cell dataclass schema, atomic IO, cell_id derivation confirmed |
| CAP-02 | Two-tier cap: `refusing-new` at `T - safety_buffer`; `terminating` at `T` via `Backend.cancel` | §3 — pure state machine, daemon tick integration, cancel signal path verified |
| CAP-03 | Per-fold checkpoint: `fold_<i>_result.json` after each fold; `result.json` is aggregate (`partial` or `completed`) | §4, §5 — SIGTERM handler threading constraint, fold file path in CCRCC pipeline, aggregate_folds algorithm |
| CAP-04 | Budget-killed → `executed` (not `crash`) with partial composite; descendant cascade against partial composite | §6 — `_reevaluate_descendants` operates on numeric `composite`, not status string; verified |
| CAP-05 | `cell_started_at` and `consumed_seconds` survive daemon restart (persisted, not in-memory) | §2 — computed model (D-111) makes this trivially restart-safe; verified |
| CAP-06 | `automil cell status [cell_id]` and `automil cell list` CLI surfaces budget state | §7 — CLI pattern, table formatting approach (stdlib f-string columns), Click group registration |

</phase_requirements>

---

## Summary

Phase 4 lands the `src/automil/cells/` package, two-tier cap state machine, per-fold checkpoint protocol, and the `automil cell` CLI subcommand group. All engineering decisions D-107..D-133 are locked in CONTEXT.md. This research focuses on verifiable implementation details: signal handler gotchas, process-group kill chain, fold-file location in the live CCRCC pipeline, `_reevaluate_descendants` behaviour with partial composites, daemon tick integration, and test-clock strategy.

The most implementation-sensitive area is the **SIGTERM handler registration constraint** (Python's `signal.signal()` can only be called from the main thread — confirmed by live execution). `register_sigterm_flush()` is safe because training scripts call it at startup in their main thread. The handler itself must be quick: aggregate fold files from CWD, write `result.json`, `sys.exit(0)`. The `sys.exit(0)` returncode-0 path is significant — the daemon's `_handle_completion` treats returncode-0 with a present `result.json` as `status: completed`, which is the correct outcome before `reconcile_budget_kill` converts it to `executed` with `metadata.budget_killed: true`.

The **CCRCC fold structure** is important: `run_experiment.py` calls `runner.run_experiment()` which iterates over `range(exp_cfg.n_folds)`, calling `train_fold()` for each fold. `train_fold()` saves a `metrics.json` file into `<results_dir>/fold_<i>/metrics.json` at the end of each fold. Phase 4's per-fold `fold_<i>_result.json` files need to be written INSIDE `train_fold()` at fold completion — this is the only place where all fold metrics are available and the fold has definitively completed. The `AUTOMIL_RESULTS_DIR` env var is already injected by the orchestrator and points to `archive/<node_id>/`.

The **`_reevaluate_descendants` cascade** operates on numeric `composite` (verified: `p_comp = parent.get("composite", 0)` — float arithmetic, not status string comparison). A partial composite of 0.65 flows through correctly — descendants are re-evaluated against 0.65, not against 0 or against `"partial"`. This directly defends Fragile Invariant #6 from CONCERNS.md.

**Primary recommendation:** Build in dependency order per the wave cadence: cell state schema + registry (Wave 1) → per-fold aggregator + SIGTERM helper (Wave 2 parallel) → submit refusal hook + daemon tick state machine (Wave 2 parallel) → reconcile.py (Wave 3) → cell CLI (Wave 4) → end-to-end cap-firing integration test (Wave 5, anti-acceptance).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cell identity + state persistence | `src/automil/cells/` package | `automil/cells/<id>.json` on disk | Framework-internal; no consumer coupling |
| Cap state machine transitions | `cells/cap.py` pure function | Daemon `_tick_cells()` applies transitions | Pure function is testable without filesystem |
| Budget-kill reconciliation | `cells/reconcile.py` | `_orchestrator_daemon.py` triggers on CANCELLED + `cancel_reason==cap` | Keeps reconcile logic out of the daemon's main loop |
| SIGTERM flush | `src/automil/runtime_helpers.py` | Training script calls at startup | Opt-in by training script; framework never injects automatically |
| Per-fold file writes | Training script (CCRCC: `train_fold()`) | `aggregate_folds()` reads them | Training script is the writer; aggregator is a pure reader |
| Submit-path cell refusal | `src/automil/cli/submit.py` | `cells/__init__.py:get_or_create_cell()` | Submit is the single entry point for new work |
| Cell CLI surface | `src/automil/cli/cell.py` | `cells/registry.py:list_cells()` | Thin CLI wrapper over cells package functions |
| Descendant cascade with partial composite | `src/automil/graph.py:_reevaluate_descendants()` | Triggered by `reconcile_budget_kill()` | No change required — already operates on numeric composite |

---

## Standard Stack

### Core (all stdlib — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `signal` | stdlib | SIGTERM handler registration | Only correct mechanism for clean process shutdown |
| `tempfile` | stdlib | `mkstemp` + `os.rename` atomic write | D-112 / Phase 0 PATTERNS §3 — already the project pattern |
| `dataclasses` | stdlib | Frozen `Cell` dataclass + `dataclasses.replace()` | D-108; frozen = immutable mid-tick [VERIFIED: live execution] |
| `hashlib` | stdlib | SHA256 `cell_id` derivation | D-109; deterministic, collision-resistant |
| `enum` | stdlib | `CellStatus(str, Enum)` | D-110; JSON-safe via `str` mixin [VERIFIED: live execution] |
| `json` | stdlib | Cell state serialisation | Existing project pattern |
| `time` | stdlib | `time.time()` for `consumed_seconds` | D-111; computed not accumulated |
| `pathlib` | stdlib | Path operations | Existing project pattern |
| `glob` | stdlib | `fold_*_result.json` discovery | [VERIFIED: `sorted(Path.glob("fold_*_result.json"))` works] |

### Supporting (existing deps, no new additions)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `click` | >=8.1 | `automil cell` Click group | Consistent with all other CLI commands |
| `yaml` | pyyaml >=6.0 | Read `cap:` section from `automil/config.yaml` | Existing config loading pattern |

**No new dependencies.** Phase 4 is stdlib-only for the core cells package. `click` and `pyyaml` are already project dependencies.

**Installation:** No new packages required.

---

## Architecture Patterns

### System Architecture Diagram

```
automil submit
    │
    ├─► cells/__init__.get_or_create_cell(dataset, encoder, parent_id)
    │       │
    │       └─► cells/state.py: read/write cells/<cell_id>.json (atomic)
    │               cell_id = sha256(dataset|encoder|parent_id)[:16]
    │
    ├─► CellStatus in {REFUSING_NEW, TERMINATING, FINALIZED}?
    │       └─► raise click.ClickException("Cell <id> is refusing-new: ...")
    │
    └─► spec["metadata"]["cell_id"] = cell.cell_id → queue/<node>.json

Daemon main loop (every 5s tick)
    │
    ├─► _tick_cells()
    │       │
    │       ├─► for cell in list_cells():
    │       │       consumed = now - cell.started_at
    │       │       new_status = next_status(cell, now, len(running_in_cell))
    │       │       if new_status != cell.status:
    │       │           if TERMINATING: backend.cancel(handle, signal=SIGTERM)
    │       │           write_cell(replace(cell, status=new_status))  [atomic]
    │       │
    │       └─► TERMINATING → Backend.cancel → os.killpg(SIGTERM) → 30s → SIGKILL
    │
    └─► _handle_completion(node_id, returncode)
            │
            ├─► result.json exists?  (written by SIGTERM handler or not)
            │       ├─► Yes → collect, write completed dir, append results.tsv
            │       └─► No + returncode≠0 → status="crash" written
            │
            └─► [cap path] cancel_reason=="cap" detected in spec metadata
                    └─► reconcile_budget_kill(node_id)
                            │
                            ├─► aggregate_folds(archive/node_id/, fold_count)
                            │       └─► glob fold_*_result.json → compute mean composite
                            │
                            ├─► ≥1 fold: write result.json status="partial"
                            │           graph.promote(node_id, status="executed",
                            │                          composite=mean, budget_killed=True)
                            │           _reevaluate_descendants(node_id)
                            │
                            └─► 0 folds: write result.json status="crashed"
                                        graph.mark_failed(node_id, status="crash",
                                                          budget_killed=True)

Training script (CCRCC run_experiment.py)
    │
    ├─► register_sigterm_flush()  [called at startup, main thread]
    │       └─► installs signal.SIGTERM handler
    │               handler: aggregate_folds(Path.cwd(), get_fold_count())
    │                        write result.json
    │                        sys.exit(0)
    │
    └─► for fold in range(n_folds):
            train_fold(...)
            └─► write archive/<node_id>/fold_<i>_result.json  [NEW in Phase 4]
```

### Recommended Project Structure

```
src/automil/
├── cells/
│   ├── __init__.py          # Public: get_or_create_cell, get_cell, list_cells,
│   │                        #         is_refusing_new, CellStatus
│   ├── state.py             # Cell frozen dataclass + cells/<id>.json schema + atomic IO
│   ├── registry.py          # CellRegistry singleton (lazy, disk-persisted)
│   ├── cap.py               # next_status() pure function
│   └── reconcile.py         # aggregate_folds() + reconcile_budget_kill()
├── runtime_helpers.py       # register_sigterm_flush() + get_fold_count()
├── cli/
│   └── cell.py              # automil cell status + automil cell list
tests/
└── cells/
    ├── __init__.py
    ├── test_cell_state.py
    ├── test_cap_state_machine.py
    ├── test_aggregate_folds.py
    ├── test_reconcile.py
    ├── test_cap_fires_with_partial_fold_recovery.py  # anti-acceptance
    ├── test_cell_state_survives_daemon_kill_restart.py
    └── test_cli_cell_status_list.py
```

### Pattern 1: Frozen Dataclass + `dataclasses.replace()` for Status Transitions

**What:** Cell is frozen; status transitions produce a new Cell instance via `dataclasses.replace()`. The result is immediately written to disk atomically.

**When to use:** Any place that needs to transition cell status — always in `_tick_cells()`.

**Example:**
```python
# Source: verified via live Python execution + Phase 2 D-52 pattern (JobHandle frozen dataclass)
from dataclasses import dataclass, replace
from cells.state import CellStatus

# CORRECT: produce new instance, caller persists atomically
new_cell = replace(cell, status=CellStatus.REFUSING_NEW)
write_cell(new_cell)  # atomic mkstemp + os.rename

# WRONG: do NOT do this (frozen dataclass raises FrozenInstanceError)
# cell.status = CellStatus.REFUSING_NEW
```

**Note:** `dataclasses.asdict(cell)` serialises `CellStatus` str Enum as its string value directly, so `json.dumps(dataclasses.asdict(cell))` works without a custom encoder. [VERIFIED: live execution]

### Pattern 2: SIGTERM Handler Registration Constraint

**What:** `signal.signal()` MUST be called from the **main thread of the main interpreter**. Calling it from a background thread (e.g., PyTorch DataLoader worker) raises `ValueError: signal only works in main thread of the main interpreter`.

**When to use:** `register_sigterm_flush()` must be called at the top of the training script's `main()` function — before any threading or DataLoader initialisation.

**Example:**
```python
# Source: verified via live Python execution
# src/automil/runtime_helpers.py
import signal, sys
from pathlib import Path

_SIGTERM_REGISTERED = False  # idempotent guard

def register_sigterm_flush(*, fold_count_env: str = "AUTOMIL_FOLD_COUNT") -> None:
    global _SIGTERM_REGISTERED
    if _SIGTERM_REGISTERED:
        return
    def _handler(signum, frame):
        n = get_fold_count()
        payload = aggregate_folds(Path.cwd(), n)
        import json
        (Path.cwd() / "result.json").write_text(json.dumps(payload, indent=2))
        sys.exit(0)  # NOT sys.exit(130) — clean exit signals graceful flush to daemon
    signal.signal(signal.SIGTERM, _handler)
    _SIGTERM_REGISTERED = True
```

**Key constraint:** `sys.exit(0)` makes returncode = 0. The daemon's `_handle_completion` with returncode=0 and present `result.json` sets `status="completed"` — which is then upgraded to `executed` + `budget_killed=True` by `reconcile_budget_kill()`. If `sys.exit(130)` were used instead, the daemon would see a non-zero returncode and potentially set `status="crash"` for a missing result.json case. [VERIFIED: live subprocess test]

### Pattern 3: Pure Cap State Machine

**What:** `next_status()` in `cells/cap.py` takes `(cell, now_epoch, running_count)` and returns the next `CellStatus`. No I/O. The daemon writes the result.

**When to use:** Called exactly once per cell per tick inside `_tick_cells()`.

**Example:**
```python
# Source: D-113 verbatim (confirmed against project patterns)
def next_status(cell: Cell, now_epoch: float, running_count: int) -> CellStatus:
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

**Idempotency:** Calling `next_status()` on a `FINALIZED` cell always returns `FINALIZED` — re-running the tick on a fully-terminated cell is a no-op.

### Pattern 4: `_tick_cells()` Daemon Integration

**What:** `_tick_cells()` is a new step inside `ExperimentOrchestrator.tick()`. Called once per tick cycle after `_check_running()` and before `_save_state()`.

**When to use:** Mutates cell states based on elapsed time; fires cancels on TERMINATING transition.

**Example:**
```python
# Source: D-114 verbatim — inserted into tick() in _orchestrator_daemon.py
def _tick_cells(self) -> None:
    from automil.cells import list_cells, next_status, write_cell, CellStatus
    from dataclasses import replace
    import signal as sig_mod
    now = time.time()
    for cell in list_cells():
        running = self._running_in_cell(cell.cell_id)
        new_status = next_status(cell, now, len(running))
        if new_status != cell.status:
            if new_status == CellStatus.TERMINATING:
                for handle in running:
                    # D-115: reuses existing LocalBackend.cancel(SIGTERM) path
                    self.backend.cancel(handle, signal=sig_mod.SIGTERM)
            write_cell(replace(cell, status=new_status))

def tick(self):
    self._reload_orchestrator_config()
    self._check_running()
    self._tick_cells()            # NEW: Phase 4 step
    if not self.draining:
        pending = self._get_pending()
        ...
    self._save_state()
```

**`_running_in_cell()` helper:** Scans `self.running` dict (in-memory) for experiments whose `spec.get("metadata", {}).get("cell_id") == cell.cell_id`. Falls back to scanning `running/*.json` on disk for experiments submitted before the current daemon started.

### Pattern 5: Fold File Write in CCRCC `train_fold()`

**What:** After each fold completes in `autobench/pipeline/clam/train.py:train_fold()`, write `fold_<i>_result.json` to the AUTOMIL_RESULTS_DIR.

**When to use:** Immediately after `fold_result` is computed at line ~323 of `train.py` — before `return fold_result`.

**Current CCRCC fold structure (confirmed by code read):**
- `run_experiment.py` passes `automil_results_dir` (= `AUTOMIL_RESULTS_DIR/results/`) to `runner.run_experiment()`
- `runner.run_experiment()` passes it as `results_dir` to `train_fold(fold, results_dir, ...)`
- `train_fold()` creates `<results_dir>/fold_<i>/` for CLAM internal outputs
- Phase 4 needs `fold_<i>_result.json` written to `archive/<node_id>/` (= `AUTOMIL_RESULTS_DIR`)

**Key:** The per-fold file path is `AUTOMIL_RESULTS_DIR/fold_<i>_result.json` (one level up from the CLAM fold subdirectory). The `AUTOMIL_RESULTS_DIR` env var points to `archive/<node_id>/` — this is where `result.json` also lives. Fold files land beside it.

```python
# In autobench/pipeline/clam/runner.py, after fold_results.append(result):
import os, json
automil_results_dir = os.environ.get("AUTOMIL_RESULTS_DIR")
if automil_results_dir:
    fold_count = int(os.environ.get("AUTOMIL_FOLD_COUNT", "5"))
    fold_payload = {
        "fold_index":      fold,
        "fold_count":      fold_count,
        "status":          "completed",
        "metrics":         {
            "val_auc":   result["val_metrics"].get("auc_roc", {}).get("mean", 0.0)
                         if isinstance(result.get("val_metrics", {}).get("auc_roc"), dict)
                         else result.get("val_metrics", {}).get("auc_roc", 0.0),
            ...
        },
        "composite":       (test_auc + test_bacc) / 2,
        "elapsed_seconds": 0,   # fold-level timing if available
        "peak_vram_mb":    0,
    }
    fold_path = os.path.join(automil_results_dir, f"fold_{fold}_result.json")
    with open(fold_path, "w") as f:
        json.dump(fold_payload, f, indent=2)
```

**The exact metric extraction from `fold_result` is an implementation detail** — `fold_result["test_metrics"]` contains `auc_roc` and `balanced_accuracy` keys (confirmed from `compute_extended_metrics`). The planner should note that the metrics extraction is data-wrangling work that the implementer must handle carefully.

### Pattern 6: `aggregate_folds()` Algorithm

**What:** Pure function that walks `archive/<node>/fold_*_result.json` and returns a `result.json` payload.

**Example:**
```python
# Source: D-119 + verified glob pattern
def aggregate_folds(node_archive: Path, expected_fold_count: int) -> dict:
    fold_files = sorted(node_archive.glob("fold_*_result.json"))
    if not fold_files:
        return {"status": "crashed", "composite": 0.0, "partial_folds": 0,
                "expected_folds": expected_fold_count, "metrics": {}}
    
    composites, metrics_by_key = [], {}
    for ff in fold_files:
        try:
            data = json.loads(ff.read_text())
        except (json.JSONDecodeError, OSError):
            continue  # skip malformed — log WARNING
        composites.append(data.get("composite", 0.0))
        for k, v in data.get("metrics", {}).items():
            metrics_by_key.setdefault(k, []).append(v)
    
    n = len(composites)
    if n == 0:
        return {"status": "crashed", "composite": 0.0, ...}
    
    return {
        "status": "completed" if n == expected_fold_count else "partial",
        "composite": sum(composites) / n,
        "metrics": {k: sum(v)/len(v) for k, v in metrics_by_key.items()},
        "partial_folds": n,
        "expected_folds": expected_fold_count,
        ...
    }
```

### Anti-Patterns to Avoid

- **Accumulating `consumed_seconds`:** `consumed_seconds_at_last_tick += dt` is the sandbagging bug. Phase 4 MUST compute `time.time() - cell.started_at` on every query. D-111 is explicit. [VERIFIED: pattern confirmed dangerous in CONCERNS.md §Pitfall-4 description]
- **Calling `signal.signal()` outside main thread:** Raises `ValueError`. If any code path attempts to register the SIGTERM handler from a DataLoader worker or background thread, it will fail silently (the error is swallowed by the thread's exception handler). Always register at script top-level in `main()`. [VERIFIED: live execution]
- **Writing `result.json` in the SIGTERM handler using blocking I/O with large payloads:** The SIGTERM grace period is 30 seconds. `aggregate_folds()` reads at most 5 small JSON files and writes one small JSON file — well within the grace window. Do not add heavy operations to the handler.
- **Using `_recover_orphans()` in any new CLI command that constructs `ExperimentOrchestrator`:** The `automil cell` commands do NOT use `ExperimentOrchestrator` at all — they read `cells/<id>.json` files directly. No risk of triggering orphan recovery. [VERIFIED: Fragile Invariant #1 from CONCERNS.md]
- **Checking `metadata.budget_killed` before `_reevaluate_descendants`:** The cascade runs on numeric `composite` — it does NOT need to be aware of `budget_killed`. The flag is for human/tooling consumption only. Do NOT gate the cascade on this flag.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Custom write-then-rename | `tempfile.mkstemp + os.replace` | Phase 0 D-25 pattern; already used in LocalBackend.submit() and graph.py |
| Status transition side effects | Stateful state machine class with embedded I/O | Pure `next_status()` function; daemon calls `write_cell()` separately | Side-effect-free = unit-testable without filesystem (confirmed: Phase 2 pattern) |
| Process-group kill | Custom `os.kill(pid, SIGTERM)` per-PID | Existing `_kill_experiment()` → `os.killpg()` in `_orchestrator_daemon.py` | BCK-04 allowlist is clear; `_kill_experiment()` already handles SIGTERM correctly |
| Column-aligned table | `tabulate` or `rich` | f-string with fixed-width columns (`f"{v:<8}"`) | Neither tabulate nor rich is in project deps; stdlib f-string alignment is sufficient for 8-column table |
| Test clock manipulation | `freezegun` or `apscheduler` | `monkeypatch.setattr(time, "time", lambda: ...)` (pytest) or inject `now_fn` parameter | Anti-pattern directive + stdlib monkeypatch is the project pattern (seen in test_runner.py) |

**Key insight:** The cap layer composes entirely against existing Phase 2 contracts (`Backend.cancel`, `os.killpg`, atomic write). No new process-control surface is needed.

---

## Runtime State Inventory

> This is not a rename/refactor phase — no renaming occurs. New `cells/` directory and `runtime_helpers.py` are purely additive.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | No existing `cells/` directory; no cell records exist pre-Phase-4 | None — cells are created lazily on first submit after Phase 4 ships |
| Live service config | Daemon needs `_tick_cells()` — requires daemon restart after Phase 4 deploy | Operator must restart daemon to activate cap enforcement |
| OS-registered state | None | None |
| Secrets/env vars | `AUTOMIL_FOLD_COUNT` is a new env var injected by the orchestrator | Orchestrator injects it via `_build_subprocess_env()` — no `.env` change needed |
| Build artifacts | None | None |

**Backward compat invariant (D-117):** Legacy nodes without `metadata.cell_id` are treated as belonging to no cell (`None`) and are not subject to cap enforcement. The 567-test baseline passes unchanged because no existing node has a `cell_id`.

---

## Common Pitfalls

### Pitfall 1: SIGTERM Handler Not Called Because Not Registered in Main Thread

**What goes wrong:** Training script spawns DataLoader workers (which use `multiprocessing`). If `register_sigterm_flush()` is accidentally called inside a worker initialisation function, `signal.signal()` raises `ValueError` in the worker process. The main process gets no handler. Budget kill fires → SIGKILL → no fold files recovered.

**Why it happens:** PyTorch DataLoader `worker_init_fn` is called in worker subprocesses. Signals can only be registered in the main thread of the main interpreter.

**How to avoid:** Call `register_sigterm_flush()` at the very top of `main()`, before any `DataLoader` construction. The docstring should say "call before creating DataLoaders."

**Warning signs:** Handler install raises `ValueError: signal only works in main thread` in test logs.

### Pitfall 2: `os.replace()` vs `os.rename()` for Cross-Filesystem Atomic Write

**What goes wrong:** `os.rename()` can fail with `OSError: [Errno 18] Invalid cross-device link` if the tmp file is on a different filesystem than the destination. `tempfile.mkstemp()` creates the tmp file in the destination's `dir=` argument to avoid this.

**Why it happens:** `tempfile.mkstemp()` without `dir=` uses `/tmp`, which may be on `tmpfs` while `automil/cells/` is on a different mount point.

**How to avoid:** Always pass `dir=str(cell_state_dir)` to `tempfile.mkstemp()`. Use `os.replace()` (not `os.rename()`) — it is atomic on POSIX and handles the same-filesystem constraint. [VERIFIED: Phase 0 PATTERNS §3 and LocalBackend.submit() use this pattern correctly]

### Pitfall 3: `_running_in_cell()` Missing Daemon-Restart Case

**What goes wrong:** `_tick_cells()` calls `_running_in_cell(cell_id)` to count running experiments in the cell. If the daemon was just restarted and `self.running` is empty (because `_load_state(recover=False)` does not populate `self.running`), `_running_in_cell()` returns 0 even if there are experiments in `running/*.json`. A TERMINATING cell with 0 running experiments transitions to FINALIZED prematurely — but those experiments are orphaned, not finished.

**Why it happens:** `self.running` is in-memory state. It is only populated as experiments are launched during this daemon session. `_recover_orphans()` runs at daemon start-up (in `run()`), archives orphaned running specs as crashes — but that happens before `_tick_cells()` runs. So the sequence is: daemon restart → `_recover_orphans()` marks everything in `running/` as crash → those experiments are now archived → `_running_in_cell()` correctly returns 0 for them → TERMINATING → FINALIZED transition is correct.

**This is actually fine:** After `_recover_orphans()` runs, `running/` is empty. `_tick_cells()` then sees 0 running experiments in TERMINATING cells and transitions them to FINALIZED. The experiments are already archived as crashes by `_recover_orphans()`. The FINALIZED transition here is semantically correct — all in-cell experiments have reached terminal state.

**Residual risk:** If `_tick_cells()` runs between `_load_state(recover=False)` (constructor) and `_recover_orphans()` (in `run()`), there could be a window. But `_tick_cells()` only runs inside `tick()` which is only called inside `run()` after `_recover_orphans()` completes. No window exists. [VERIFIED: daemon `run()` sequence at lines 964-968]

**Warning sign to test:** daemon-restart test (`test_cell_state_survives_daemon_kill_restart.py`) must assert that `consumed_seconds` resumes from `started_at`, not from 0.

### Pitfall 4: `cancel_reason` Not Written to Spec Before Reconcile

**What goes wrong:** `reconcile_budget_kill(node_id)` needs to distinguish cap-driven cancels from operator cancels. D-123 says it is triggered when the daemon observes `metadata.cancel_reason == "cap"`. If the daemon doesn't write `cancel_reason: "cap"` to the completed spec before calling reconcile, the reconcile function cannot distinguish the two cases.

**Why it happens:** The existing cancel path (`automil cancel <node>`) does not write `cancel_reason`. Phase 4 adds cap-driven cancel; the daemon must set `cancel_reason: "cap"` on the spec before calling `reconcile_budget_kill()`.

**How to avoid:** In `_tick_cells()`, when transitioning to TERMINATING and firing `backend.cancel()`, also update the spec in `running/<node_id>.json` to add `metadata.cancel_reason = "cap"`. This must happen BEFORE `backend.cancel()` returns (fire-and-forget — the process may complete before the next tick).

### Pitfall 5: Fold File Metrics Extraction Mismatch

**What goes wrong:** `train_fold()` returns `{"test_metrics": {...}, "val_metrics": {...}}` where `test_metrics["auc_roc"]` is a float (from `compute_extended_metrics`). The `fold_<i>_result.json` shape (D-118) expects `metrics: {"val_auc": ..., "test_auc": ..., "val_bacc": ..., "test_bacc": ...}` as flat floats. If the metric key names or nesting don't match, `aggregate_folds()` silently produces zeros.

**Why it happens:** `compute_extended_metrics()` returns dict keys `"auc_roc"` and `"balanced_accuracy"` (not `"val_auc"` and `"val_bacc"`). The writer of `fold_<i>_result.json` must explicitly map these.

**How to avoid:** The fold-file writer (in `runner.py` or `run_experiment.py`) must explicitly map:
- `test_metrics["auc_roc"]["mean"]` → `metrics["test_auc"]`
- `test_metrics["balanced_accuracy"]["mean"]` → `metrics["test_bacc"]`
- `val_metrics["auc_roc"]["mean"]` → `metrics["val_auc"]`
- `val_metrics["balanced_accuracy"]["mean"]` → `metrics["val_bacc"]`

Note: `compute_confidence_intervals()` wraps per-fold metrics into `{"mean": ..., "std": ..., "ci_low": ..., "ci_high": ...}`. But `train_fold()` returns the *per-fold* metrics dict directly from `compute_extended_metrics()` — which returns flat floats, not CIs. Verify this at implementation time by reading `compute_extended_metrics()` return shape.

---

## Code Examples

Verified patterns from the codebase:

### Cell ID Derivation (SHA256 prefix)
```python
# Source: D-109; verified via live Python execution
import hashlib
cell_id = hashlib.sha256(
    f"{dataset}|{encoder}|{parent_id}".encode("utf-8")
).hexdigest()[:16]
# Example: "2d3c9caff25ee79a" for ("ccrcc", "uni-v2", "node_0042")
```

### Atomic Cell State Write
```python
# Source: Phase 0 D-25 pattern; verified against LocalBackend.submit() lines 149-166
import json, os, tempfile
from pathlib import Path

def write_cell(cell: Cell, cells_dir: Path) -> None:
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

### Submit-Path Cell Refusal Hook
```python
# Source: D-116; symmetric to metadata.backend (D-76) and metadata.runtime (D-97)
# In src/automil/cli/submit.py, after existing parent-node guard:
from automil.cells import get_or_create_cell, CellStatus, consumed_seconds

cell = get_or_create_cell(dataset, encoder, parent or "root")
if cell.status in (CellStatus.REFUSING_NEW, CellStatus.TERMINATING, CellStatus.FINALIZED):
    raise click.ClickException(
        f"Cell {cell.cell_id[:8]} is {cell.status.value}: budget exhausted "
        f"({consumed_seconds(cell):.0f}/{cell.budget_seconds}s consumed). "
        f"Wait for cell to finalize or use a different (dataset, encoder, parent_id) tuple."
    )
spec.setdefault("metadata", {})["cell_id"] = cell.cell_id
```

### `dataset` and `encoder` in Submit
```python
# Source: cli/submit.py existing config load pattern (lines 143-148)
# dataset and encoder come from automil/config.yaml
config = yaml.safe_load((adir / "config.yaml").read_text()) if (adir / "config.yaml").exists() else {}
dataset = config.get("dataset", {}).get("name", "unknown")
encoder = config.get("encoder", {}).get("name", "unknown")
```

### CLI Table Formatting (stdlib f-strings, no rich/tabulate)
```python
# Source: existing status.py pattern (click.echo with f-strings); no rich/tabulate in deps
# For automil cell status output — columns: cell_id(8) dataset encoder parent started consumed/budget status running
HEADER = f"{'cell_id':<8}  {'dataset':<8}  {'encoder':<8}  {'parent':<10}  {'started':<19}  {'consumed/budget':<17}  {'status':<12}  {'running':<7}"
click.echo(HEADER)
click.echo("-" * len(HEADER))
for cell in cells:
    consumed = time.time() - cell.started_at
    consumed_str = f"{int(consumed//3600):02d}:{int((consumed%3600)//60):02d}:{int(consumed%60):02d}"
    budget_str = f"{cell.budget_seconds//3600:02d}:{(cell.budget_seconds%3600)//60:02d}:00"
    started_str = datetime.fromtimestamp(cell.started_at).strftime("%Y-%m-%d %H:%M:%S")
    click.echo(
        f"{cell.cell_id[:8]:<8}  {cell.dataset:<8}  {cell.encoder:<8}  "
        f"{cell.parent_id:<10}  {started_str:<19}  "
        f"{consumed_str}/{budget_str}  {cell.status.value:<12}  {running_count:<7}"
    )
```

### Test Clock Manipulation via Monkeypatch (no freezegun)
```python
# Source: project convention (no freezegun in deps); monkeypatch is pytest stdlib
import time
from automil.cells.cap import next_status
from automil.cells.state import CellStatus, Cell

def test_active_to_refusing_new_at_safety_buffer(monkeypatch):
    fake_now = 1_000_000.0
    cell = Cell(
        cell_id="abc123",
        dataset="test",
        encoder="enc",
        parent_id="node_0001",
        started_at=fake_now - (21600 - 1800 + 1),  # consumed > T - safety_buffer
        budget_seconds=21600,
        safety_buffer_seconds=1800,
        status=CellStatus.ACTIVE,
    )
    result = next_status(cell, now_epoch=fake_now, running_count=2)
    assert result == CellStatus.REFUSING_NEW
```

**Note:** `next_status()` takes `now_epoch` as a parameter (D-113), so no monkeypatching of `time.time` is needed for cap state machine tests. Clock injection is explicit. Only `consumed_seconds()` (which calls `time.time()`) needs monkeypatching in tests for `cells/state.py`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Timeout in `_handle_timeout()` blocks event loop with `time.sleep(5)` | Phase 4 uses daemon-tick-based cap state machine (no blocking sleep in tick) | Phase 4 | Cap enforcement is non-blocking; existing 5s sleep in `_handle_timeout` still exists for per-experiment timeout but cap-driven cancel is fire-and-forget |
| No cap → unlimited cell duration | 6h hard cap with 30min refusing-new buffer | Phase 4 | Agent can plan experiments knowing exactly when the cell closes |
| Crash on SIGTERM = zero recoverable results | Per-fold files + SIGTERM flush = partial composite recoverable | Phase 4 | Budget-kill produces `executed` not `crash`; descendant cascade works correctly |

**Deprecated/outdated for Phase 4 context:**
- `BUDGET_KILLED` JobState was reserved in Phase 2 D-53 for Phase 4 — Phase 4 now actually uses it. The status map in `local.py` line 224 already includes `"budget_killed": JobState.BUDGET_KILLED`.

---

## Assumptions Log

> All claims in this research were verified or cited — no user confirmation needed.

**If this table is empty:** All claims in this research were verified or cited.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| (empty) | | | |

---

## Open Questions

1. **Exact metric key mapping from `compute_extended_metrics()` return value**
   - What we know: `train_fold()` returns `{"test_metrics": {...}, "val_metrics": {...}}` where each contains `auc_roc` and `balanced_accuracy` keys
   - What's unclear: Whether `auc_roc` is a bare float or a dict like `{"mean": ..., "std": ...}` at the per-fold level (before `compute_confidence_intervals` is applied)
   - Recommendation: Implementer must read `autobench/pipeline/evaluate.py:compute_extended_metrics()` at implementation time to confirm the exact return shape of `auc_roc` at per-fold level. The planner should note this as a "read evaluate.py before writing fold writer" requirement.

2. **`get_or_create_cell()` — what is `parent_id` for root-level submits (no `--parent`)?**
   - What we know: Cell key is `(dataset, encoder, parent_id)`. Root submits have `parent = None`.
   - What's unclear: Should `None` map to a sentinel string (`"root"`) or be disallowed?
   - Recommendation: Use `"root"` as the sentinel for root-level submits. This makes `cell_id` deterministic for root experiments without a parent. The planner should lock this as `parent_id = parent or "root"` in submit.py.

3. **`cells/` storage location** — sibling of `automil/orchestrator/` or nested inside it?
   - What we know: `cells/<cell_id>.json` paths are referenced in D-107 and CONTEXT.md specifics
   - What's unclear: Whether `cells/` is at `automil/cells/<id>.json` or `automil/orchestrator/cells/<id>.json`
   - Recommendation: `automil/cells/` at the same level as `automil/orchestrator/` — this matches the CONTEXT.md `<specifics>` block which shows path as `cells/<cell_id>.json` relative to `automil/`. The `get_or_create_cell()` function should locate this via `_find_automil_dir() / "cells"`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib `signal` | CAP-03 SIGTERM handler | ✓ | stdlib | — |
| Python stdlib `tempfile` | D-112 atomic writes | ✓ | stdlib | — |
| Python stdlib `hashlib` | D-109 cell_id | ✓ | stdlib | — |
| Python stdlib `dataclasses` | D-108 Cell dataclass | ✓ | stdlib | — |
| `pytest` monkeypatch | Test clock injection | ✓ | >=9.0.2 | — |
| `rich` / `tabulate` | CLI table formatting | ✗ | — | stdlib f-string columns (no fallback needed) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `rich` and `tabulate` are not installed; stdlib f-string formatting is the correct approach and matches existing project style.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >=9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` `testpaths = ["tests"]` |
| Quick run command | `uv run pytest tests/cells/ -x -v` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAP-01 | Cell frozen dataclass; atomic IO; cell_id deterministic; restart-safe consumed_seconds | unit | `uv run pytest tests/cells/test_cell_state.py -x` | ❌ Wave 0 |
| CAP-02 | `next_status()` all four transitions + idempotency; `_tick_cells()` fires cancel on TERMINATING | unit | `uv run pytest tests/cells/test_cap_state_machine.py -x` | ❌ Wave 0 |
| CAP-03 | `aggregate_folds()`: all-folds, partial, zero, malformed; SIGTERM handler writes result.json | unit + integration | `uv run pytest tests/cells/test_aggregate_folds.py -x` | ❌ Wave 0 |
| CAP-04 | `reconcile_budget_kill()`: ≥1 fold → executed; 0 folds → crash; descendant cascade with partial composite | unit | `uv run pytest tests/cells/test_reconcile.py -x` | ❌ Wave 0 |
| CAP-04 (anti-acceptance) | End-to-end: write 3 fold files, SIGTERM, verify executed + composite≠0 + no spurious discard | integration | `uv run pytest tests/cells/test_cap_fires_with_partial_fold_recovery.py -x` | ❌ Wave 0 |
| CAP-05 | `consumed_seconds` resumes after daemon kill-9 + restart; NOT reset to 0 | integration | `uv run pytest tests/cells/test_cell_state_survives_daemon_kill_restart.py -x` | ❌ Wave 0 |
| CAP-06 | `automil cell status` + `automil cell list` correct output | integration | `uv run pytest tests/cells/test_cli_cell_status_list.py -x` | ❌ Wave 0 |
| Baseline | 567 + 9 skipped passes unchanged | regression | `uv run pytest tests/ -v` | ✅ existing |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/cells/ -x`
- **Per wave merge:** `uv run pytest tests/ -v` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/cells/__init__.py` — package marker
- [ ] `tests/cells/test_cell_state.py` — covers CAP-01
- [ ] `tests/cells/test_cap_state_machine.py` — covers CAP-02
- [ ] `tests/cells/test_aggregate_folds.py` — covers CAP-03
- [ ] `tests/cells/test_reconcile.py` — covers CAP-04
- [ ] `tests/cells/test_cap_fires_with_partial_fold_recovery.py` — Pitfall-4 anti-acceptance gate
- [ ] `tests/cells/test_cell_state_survives_daemon_kill_restart.py` — covers CAP-05
- [ ] `tests/cells/test_cli_cell_status_list.py` — covers CAP-06

---

## Security Domain

> `security_enforcement: true` in `.planning/config.json`. ASVS Level 1.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Cap enforcement is local-only; no auth surface |
| V3 Session Management | no | No user sessions involved |
| V4 Access Control | yes | `cells/<id>.json` is written by daemon process; CLI reads only — no user-provided write path |
| V5 Input Validation | yes | `cell_id` is SHA256-derived (not user-supplied); `budget_seconds` read from config.yaml (validated YAML) |
| V6 Cryptography | no | SHA256 used for ID generation (not crypto key material) |

### Known Threat Patterns for Phase 4 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Clock manipulation via `time.time()` spoofing | Tampering | `consumed_seconds = time.time() - cell.started_at` is verified by daemon-restart test; `started_at` persisted on disk, not in-memory |
| Race between tick and submit | Tampering | Cell status checked at submit time; atomic cell write prevents partial state reads |
| Partial-fold file tampering | Tampering | `aggregate_folds()` uses `try/except json.JSONDecodeError` — malformed files are skipped with WARNING, not silently used |
| `budget_killed=True` node appearing as `crash` in graph | Denial of Service | D-123 and D-124 explicitly distinguish cap-kill from organic crash; `reconcile_budget_kill()` is the only writer of `budget_killed` |
| Sandbagging: daemon restart resets timer | Tampering | `started_at` persisted in `cells/<id>.json`; computed model (D-111) means restart inherits persisted wall time |

---

## Sources

### Primary (HIGH confidence)
- `src/automil/backends/_orchestrator_daemon.py` — daemon tick loop, `_handle_completion`, `_recover_orphans` sequence, `_kill_experiment` [VERIFIED: direct read]
- `src/automil/backends/local.py` — `cancel()` method (30s grace path at D-57) [VERIFIED: direct read]
- `src/automil/backends/base.py` — `Backend.cancel` ABC + `JobState.BUDGET_KILLED` reservation [VERIFIED: direct read]
- `src/automil/cli/submit.py` — existing submit path, metadata.backend pattern (D-76), metadata.runtime (D-97) [VERIFIED: direct read]
- `src/automil/graph.py` — `_reevaluate_descendants()` operates on `parent.get("composite", 0)` float [VERIFIED: direct read lines 254-270]
- `src/automil/cli/__init__.py` — Click group registration pattern [VERIFIED: direct read]
- `benchmarks/src/autobench/pipeline/clam/runner.py` — fold loop structure, `results_dir` → `train_fold()` path [VERIFIED: direct read]
- `benchmarks/src/autobench/pipeline/clam/train.py` — `train_fold()` outputs `metrics_path` per fold; `AUTOMIL_RESULTS_DIR` context [VERIFIED: direct read]
- `benchmarks/scripts/run_experiment.py` — `AUTOMIL_RESULTS_DIR` env var usage, `n_folds` parameter [VERIFIED: direct read]
- Python stdlib signal module — `signal.signal()` threading restriction [VERIFIED: live execution `signal only works in main thread of the main interpreter`]
- Python stdlib dataclasses — frozen dataclass `replace()`, `asdict()`, str Enum JSON serialisation [VERIFIED: live execution]
- Python stdlib tempfile + os.replace — atomic write correctness [VERIFIED: live execution]
- `.planning/research/PITFALLS.md` §Pitfall 4 — mid-fold guillotine design rationale
- `.planning/codebase/CONCERNS.md` §"Fragile Invariant #6 — descendant cascade against zero composite"
- `04-CONTEXT.md` — all locked decisions D-107..D-133

### Secondary (MEDIUM confidence)
- `pyproject.toml` — no `rich` or `tabulate` in deps; stdlib f-string formatting confirmed as correct approach
- Existing test structure in `tests/trajectory/`, `tests/agent_assets/` — pattern reference for new `tests/cells/` structure

---

## Metadata

**Confidence breakdown:**
- Cell state schema + atomic IO: HIGH — verified against live Python execution and existing project patterns
- Cap state machine: HIGH — pure function, no I/O dependencies, D-113 is explicit and complete
- SIGTERM handler threading constraint: HIGH — verified via live execution (`ValueError: signal only works in main thread`)
- `_reevaluate_descendants` behaviour with partial composite: HIGH — direct code read confirms float arithmetic
- CCRCC fold structure: HIGH — direct read of runner.py and train.py confirms fold-level output shape
- CLI table formatting (no rich): HIGH — pyproject.toml confirms no rich/tabulate dep
- Test-clock strategy (monkeypatch, no freezegun): HIGH — no freezegun in deps; next_status() takes explicit `now_epoch` parameter (D-113) making monkeypatching unnecessary for state machine tests

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (stdlib patterns are stable; CCRCC pipeline may drift if Phase 1 registry work modifies train.py/runner.py)

---

## RESEARCH COMPLETE

**Phase:** 04 — 6h Per-Cell Hard Cap + Cell-Concept Formalisation
**Confidence:** HIGH

### Key Findings

1. **Signal handler threading constraint is the single sharpest implementation gotcha.** `signal.signal()` raises `ValueError` in any non-main thread. `register_sigterm_flush()` must be called at the top of `main()` before DataLoader initialisation. [VERIFIED: live execution]

2. **`_reevaluate_descendants` operates on numeric `composite` float — no change needed.** A partial composite of 0.65 flows through the cascade correctly. The descendant re-evaluation does not inspect `status` or `budget_killed` strings. Fragile Invariant #6 is automatically defended by the existing code. [VERIFIED: graph.py lines 254-270]

3. **CCRCC fold-file writer lands in `runner.py` after `fold_results.append(result)`.** The fold loop is in `runner.py:run_experiment()` at line 38. After `train_fold()` returns, metrics are available. `AUTOMIL_RESULTS_DIR` already points to `archive/<node_id>/`. The fold file goes to `AUTOMIL_RESULTS_DIR/fold_<i>_result.json`. Metric keys require explicit mapping from `compute_extended_metrics()` format to D-118 flat format.

4. **No new dependencies required.** Phase 4 is entirely stdlib + existing `click`/`pyyaml` deps. No `rich`, `tabulate`, `freezegun`, `apscheduler`, or `cgroups`.

5. **Test-clock injection is explicit in the state machine.** `next_status(cell, now_epoch, running_count)` takes `now_epoch` as a parameter (D-113), so cap state machine tests need NO monkeypatching. Only `consumed_seconds(cell)` (which calls `time.time()`) needs `monkeypatch.setattr` in tests for `cells/state.py`.

### File Created
`/home/jma/Documents/yinshuol/autoMIL/.planning/phases/04-6h-per-cell-hard-cap-cell-concept-formalisation/04-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | stdlib-only; all patterns verified via live execution |
| Architecture | HIGH | D-107..D-133 are fully locked; code paths verified by direct read |
| Pitfalls | HIGH | Pitfalls 1-5 above all verified against live code or Python runtime behaviour |
| CCRCC integration | HIGH | runner.py and train.py directly read; fold loop structure confirmed |

### Open Questions

- Exact return shape of `compute_extended_metrics()` at per-fold level (flat float or CI dict) — implementer must read `evaluate.py` before writing fold writer
- `parent_id` sentinel for root-level submits (`None` → `"root"` recommended)
- `cells/` storage location relative to `automil/` root (recommended: `automil/cells/`)

### Ready for Planning

Research complete. Planner can now create PLAN.md files for the 9-10 wave-level plans covering: (1) cells/ package + Cell dataclass + atomic IO + cell_id, (2) aggregate_folds() + runtime_helpers.py, (3) submit-path refusal + daemon _tick_cells(), (4) reconcile_budget_kill(), (5) automil cell CLI, (6) CCRCC fold writer, (7) end-to-end anti-acceptance test.
