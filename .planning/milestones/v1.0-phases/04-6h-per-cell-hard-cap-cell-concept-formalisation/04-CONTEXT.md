# Phase 4: 6h per-cell hard cap + cell-concept formalisation - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning
**Mode:** Engineering decisions locked per production best practice (Leo's directive 2026-05-02 — "decide engineering questions yourself; ask only user/feature questions"). Every decision below is a technical implementation choice; no open user/feature questions for Phase 4.

<domain>
## Phase Boundary

Land **per-cell wall-clock budgets** (configurable, with 6h as Leo/CCRCC's chosen default — NOT a framework-mandated value) AND **per-fold checkpoint protocol** in the same phase — the cap MUST ship with the per-fold protocol or the first cap-firing event corrupts results.tsv (Pitfall 4 anti-acceptance).

> **Configuration scope (Leo 2026-05-05):** The 6-hour figure is the autoMIL-paper research-campaign default — a value Leo picked for ALL his experiments across this milestone (CCRCC, CLWD, future datasets in this paper) — but it is NOT a framework property. autoMIL is generic (memory: project_automil_is_generic); the paper's experiment campaign is one consumer. Every cap parameter — `budget_seconds`, `safety_buffer_seconds`, and `fold_count` — is consumer-supplied via `automil/config.yaml` AND additionally overridable per-cell via CLI flag (D-134). The framework mandates only the cap *mechanism* (state machine, per-fold protocol, reconciliation) — never the cap *value*. A future user (sklearn-iris demo, an external lab, a different paper) sets their own cap and the framework honours it identically.

After Phase 4:

1. **`(dataset, encoder, parent_id)` is a first-class graph entity** — `cell_id` is a deterministic short hash; `cells/<cell_id>.json` persists `started_at`, `budget_seconds`, `safety_buffer_seconds`, `consumed_seconds_at_last_tick`, `status` (`active | refusing-new | terminating | finalized`). Wall-clock state is COMPUTED from `now() - started_at`, never accumulated — restart-safe by construction.
2. **Two-tier cap state machine** — at `T - safety_buffer` (default 30 min) cell transitions `active → refusing-new` and `cli/submit.py` rejects new experiments for that cell with a structured `CellRefusedError`. At `T` cell transitions `refusing-new → terminating` and the daemon calls `Backend.cancel(handle, signal=SIGTERM)` on every running experiment in the cell with a 30s grace window. After all in-cell experiments reach terminal state, transitions `terminating → finalized`.
3. **Per-fold checkpoint protocol** — training scripts write `archive/<node_id>/fold_<i>_result.json` after each fold completes. Framework's `_aggregate_folds()` computes `result.json` from however-many-folds-are-present: all K → `status: completed`; 1 ≤ folds < K → `status: partial`, `partial_folds: <n>`. Composite is the mean of per-fold composites; CI is widened proportional to `1 - partial_folds/K`.
4. **`automil.runtime_helpers.register_sigterm_flush()`** is the per-train-script hook: training script calls it at startup, framework installs a `signal.SIGTERM` handler that aggregates whatever fold files are present, writes `result.json` with `status: partial`, and exits cleanly with code 0 (NOT 130). Without this call, `SIGTERM` falls through to default behaviour (process death, no flush) — the partial-fold files written so far still let the orchestrator reconstruct a partial result via `_aggregate_folds()` after the fact.
5. **Budget-killed reconciliation** — when a budget-cancelled experiment's archive arrives at the orchestrator (with or without SIGTERM-handler flush), `reconcile.py` walks `archive/<node_id>/fold_*_result.json`. If ≥1 fold completed → reconcile to `executed` with `metadata.budget_killed: true`, `composite` = mean of completed folds, `status: partial`. If zero folds completed → reconcile to `crash` (matches existing behaviour). Descendants are recomputed against the partial composite, NOT zero — Fragile Invariant #6 from CONCERNS.md is defended.
6. **`automil cell status [cell_id]`** + **`automil cell list`** surface budget state for operator inspection. Format: `cell_id_8 | dataset | encoder | parent | started | consumed/budget | status | running_exps`.
7. **Process-group kill on cap-fire** — the existing `start_new_session=True` + `os.killpg` discipline (from BCK-04 / Phase 2 isolation) is reused; cap-driven cancels MUST kill the entire process group to release VRAM. Without this, partial-fold orphans hold GPU memory and the next cell starts contaminated.

**Hard floors:**

- Phase 0+1+2+3 baseline (558 + 9 skipped) stays green.
- Cap-firing integration test (`test_cap_fires_with_partial_fold_recovery`) asserts: SIGTERM handler runs, partial `result.json` written with `status: partial`, graph node reconciles to `executed` (NOT `crash`), composite ≠ 0, descendants NOT spuriously discarded, VRAM released.
- Daemon-restart survival test (`test_cell_state_survives_daemon_kill_restart`) asserts: kill-9 the daemon at hour 4 of a 6h cell, restart, `consumed_seconds` resumes correctly (NOT reset to zero — sandbagging defence).
- `automil cell list` shows correct state for a cell that has fired its cap.
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/cells/` returns zero — cap layer is framework-only.

**Wave-cadence target:** 9–10 plans across 5 waves. Granularity `fine`. Dependency shape: cell state schema + registry → per-fold result.json aggregator + sigterm helper → submit-path refusal hook + daemon tick state machine ‖ reconcile.py → cell CLI → end-to-end cap-firing integration test (anti-acceptance).

</domain>

<decisions>
## Implementation Decisions

> **Numbering:** D-107 onward continues from Phase 3's D-78..D-106. Each decision is a locked engineering choice; downstream agents (researcher, planner, executor) honour these verbatim.

### Cell module layout (CAP-01)

- **D-107:** New package `src/automil/cells/` with five modules:
  ```
  src/automil/cells/
    __init__.py              # public surface: get_or_create_cell, get_cell, list_cells, is_refusing_new, CellStatus
    state.py                 # Cell frozen dataclass + cells/<cell_id>.json schema + atomic IO
    registry.py              # module-level CellRegistry singleton (lazy, persisted to disk)
    cap.py                   # two-tier state machine (active → refusing-new → terminating → finalized)
    reconcile.py             # budget-killed → executed reconciliation w/ partial composite (CAP-04)
  ```
  Stdlib-only (no `pydantic`, no `attrs`). Framework-internal — no autobench imports, no consumer-specific paths.

- **D-108:** **`Cell` is a frozen dataclass** in `cells/state.py`:
  ```python
  @dataclass(frozen=True)
  class Cell:
      cell_id: str                     # 16-char hex (sha256 prefix of dataset|encoder|parent_id)
      dataset: str                     # e.g. "ccrcc" — from automil/config.yaml
      encoder: str                     # e.g. "uni-v2" — from automil/config.yaml
      parent_id: str                   # graph node_id of the cell-root experiment
      started_at: float                # unix epoch seconds (UTC), absolute wall-clock — NOT relative
      budget_seconds: int              # consumer-supplied; paper-campaign default 21600 (6h), NOT framework-mandated
      safety_buffer_seconds: int       # consumer-supplied; paper-campaign default 1800 (30 min)
      status: "CellStatus"             # enum (D-110)
  ```
  Frozen so `Cell` instances cannot be mutated mid-tick; status transitions go through `cells/state.py:write_cell()` → atomic on-disk replacement, NOT in-place mutation. Hashable + JSON-serialisable via `dataclasses.asdict`.

  **Default-resolution chain** for `budget_seconds` and `safety_buffer_seconds` at cell creation (precedence high→low):
  1. CLI flag (`automil submit --budget-seconds N --safety-buffer-seconds M` — D-134)
  2. `automil/config.yaml: cap.budget_seconds` / `cap.safety_buffer_seconds` (consumer-supplied)
  3. Framework fallback (`21600` / `1800`) — used only when neither flag nor config is set; chosen because Leo's autoMIL-paper experiment campaign uses 6h across all its datasets (CCRCC, CLWD, future additions), but the framework treats the fallback as "best guess if nothing was specified," NOT as canonical. Any other consumer (different paper, different lab, sklearn-iris demo) MUST configure their own values.

- **D-109:** **`cell_id` derivation** is deterministic and one-line:
  ```python
  cell_id = hashlib.sha256(f"{dataset}|{encoder}|{parent_id}".encode("utf-8")).hexdigest()[:16]
  ```
  16 hex chars → ~6.4×10¹⁹ collision space. Same `(dataset, encoder, parent_id)` always maps to the same cell — re-submits join the existing cell, do not create a new one. `parent_id` is the cell-root node id (the experiment that opens the cell); not the immediate parent of any descendant.

- **D-110:** **`CellStatus` is a `str`-valued `Enum`** (JSON-safe, comparable):
  ```python
  class CellStatus(str, Enum):
      ACTIVE       = "active"
      REFUSING_NEW = "refusing-new"
      TERMINATING  = "terminating"
      FINALIZED    = "finalized"
  ```
  Four values exhaust the cap state machine. `FINALIZED` means "all experiments in this cell have reached terminal state AND the cap has fired" — the cell is dormant and `cell list` may garbage-collect it (out-of-scope for v1; cells stay forever in Phase 4).

### Wall-clock model (CAP-05)

- **D-111:** **`consumed_seconds` is COMPUTED, never accumulated.**
  ```python
  def consumed_seconds(cell: Cell) -> float:
      return time.time() - cell.started_at
  ```
  This is restart-safe by construction — if the daemon dies and restarts at hour 4 of a 6h cell, the next tick still computes `consumed = 4h` from the persisted `started_at`. There is NO `consumed_seconds_at_last_tick += dt` accumulation anywhere — that pattern is the sandbagging bug. The persisted field is `started_at` (set once at cell creation), full stop.

- **D-112:** **Atomic writes via `tempfile.mkstemp + os.rename`** (Phase 0 PATTERNS §3 / D-25 pattern). Every write to `cells/<cell_id>.json` goes through `_atomic_write_json(path, payload)`. Failures partway through never leave a half-written cell state.

### Two-tier cap state machine (CAP-02)

- **D-113:** **Cap state machine** lives in `cells/cap.py`. The transition function is pure (no I/O):
  ```python
  def next_status(cell: Cell, now_epoch: float, running_count: int) -> CellStatus:
      """Pure function. Caller persists the result via state.write_cell()."""
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
  Side-effect-free → unit-testable without filesystem. `running_count` is the count of in-cell experiments NOT in terminal state; the daemon supplies this from `Backend.list_running()` filtered by cell membership.

- **D-114:** **Daemon tick integration** — extend `_orchestrator_daemon.py`'s main loop with one new step `_tick_cells()`:
  ```python
  def _tick_cells(self) -> None:
      now = time.time()
      for cell in list_cells():
          running = self._running_in_cell(cell.cell_id)
          new_status = next_status(cell, now, len(running))
          if new_status != cell.status:
              # Action on transition: only TERMINATING fires cancels.
              if new_status == CellStatus.TERMINATING:
                  for handle in running:
                      self.backend.cancel(handle, signal=signal.SIGTERM)
              write_cell(cell._replace(status=new_status))
  ```
  Idempotent: re-running the tick on an already-transitioned cell is a no-op. The 30s grace + SIGKILL escalation is the backend's responsibility (D-57 + D-115), not the cap layer's.

- **D-115:** **Cancel signal contract** — cap-driven cancels use `signal=SIGTERM`. `LocalBackend.cancel(handle, signal=SIGTERM)` already (Phase 2) sends SIGTERM to the process group, waits 30 seconds, then SIGKILLs (D-57). MockSLURMBackend fire-and-forget. Phase 4 does NOT widen the backend ABC; it composes against existing Phase 2 contracts.

### Submit-path refusal (CAP-02)

- **D-116:** **Submit pathway extension** — `cli/submit.py` reads cell membership BEFORE writing the queue spec:
  ```python
  cell = get_or_create_cell(dataset, encoder, parent_id)
  if cell.status in (CellStatus.REFUSING_NEW, CellStatus.TERMINATING, CellStatus.FINALIZED):
      raise click.ClickException(
          f"Cell {cell.cell_id[:8]} is {cell.status.value}: budget exhausted "
          f"({consumed_seconds(cell):.0f}/{cell.budget_seconds}s consumed). "
          f"Wait for cell to finalize or use a different (dataset, encoder, parent_id) tuple."
      )
  spec["metadata"]["cell_id"] = cell.cell_id
  ```
  `dataset` and `encoder` come from `automil/config.yaml` (consumer-supplied; existing); `parent_id` is the new node's parent (resolved via existing graph logic). Cell creation is lazy + idempotent — the FIRST submit for a `(dataset, encoder, parent_id)` tuple opens the cell.

- **D-117:** **`metadata.cell_id` on every node** — symmetric to Phase 2 D-76 (`metadata.backend`) and Phase 3 D-97 (`metadata.runtime`). Three-line addition to `cli/submit.py`. Backward compat: legacy nodes without `metadata.cell_id` are treated as belonging to no cell (`None`) and are not subject to cap enforcement — they were submitted before the cap shipped, full stop.

### Per-fold checkpoint protocol (CAP-03)

- **D-118:** **Per-fold result file shape** is exactly:
  ```json
  {
    "fold_index":      2,
    "fold_count":      5,
    "status":          "completed",
    "metrics":         {"val_auc": 0.86, "val_bacc": 0.81, "test_auc": 0.85, "test_bacc": 0.83},
    "composite":       0.84,
    "elapsed_seconds": 821,
    "peak_vram_mb":    4500
  }
  ```
  Path: `archive/<node_id>/fold_<i>_result.json` where `<i>` is the zero-indexed fold (so `fold_0_result.json` ... `fold_4_result.json` for K=5). Training scripts write each fold's file IMMEDIATELY after the fold completes — never batch-write at the end. This is the core invariant — without per-fold writes, a SIGTERM mid-fold-3 leaves zero recoverable result.

- **D-119:** **`_aggregate_folds()` lives at `src/automil/cells/reconcile.py`**. Pure function:
  ```python
  def aggregate_folds(node_archive: Path, expected_fold_count: int) -> dict:
      """Walk archive/<node>/fold_*_result.json, return result.json payload.

      Returns:
          {
              "status":            "completed" if folds==expected else "partial",
              "metrics":           <mean across completed folds, key-by-key>,
              "composite":         <mean of per-fold composite>,
              "partial_folds":     <int — number of completed folds>,
              "expected_folds":    <int — expected_fold_count>,
              "elapsed_seconds":   <sum across completed folds>,
              "peak_vram_mb":      <max across completed folds>,
              "metadata": {"budget_killed": <bool inferred from caller context>}
          }
      """
  ```
  - All K folds present → `status: completed`, `partial_folds == expected_fold_count`.
  - 1 ≤ folds < K → `status: partial`, `partial_folds: <n>`, `metrics` is the mean of the available folds.
  - 0 folds → returns `{"status": "crashed", "composite": 0.0, ...}` — caller (reconcile.py) decides graph status.

- **D-120:** **`expected_fold_count` is read from `automil/config.yaml: training.fold_count`** (default `5`). Training scripts query it via `automil.runtime_helpers.get_fold_count()`. The orchestrator passes it via `JobSpec.env: AUTOMIL_FOLD_COUNT=<n>` so the aggregator can reconstruct partial state without re-reading config from inside the daemon.

### SIGTERM handler in train.py (CAP-03)

- **D-121:** **`automil.runtime_helpers` is a new module** at `src/automil/runtime_helpers.py` (separate from `automil.runtime` which only declares `AUTOMIL_RUNTIME`). Public API:
  ```python
  def register_sigterm_flush(*, fold_count_env: str = "AUTOMIL_FOLD_COUNT") -> None:
      """Install signal.SIGTERM handler that flushes a partial result.json
      from whatever fold_*_result.json files exist in CWD, then exits cleanly.

      Idempotent — calling twice is a no-op.
      """

  def get_fold_count() -> int:
      """Read AUTOMIL_FOLD_COUNT env (set by orchestrator from config.yaml).
      Default 5 if unset (matches CCRCC convention)."""
  ```
  Training scripts call `register_sigterm_flush()` at startup. The handler runs `aggregate_folds(Path.cwd(), get_fold_count())`, writes `result.json` to CWD, then `sys.exit(0)` (NOT 130 — clean exit lets the orchestrator distinguish "graceful flush" from "killed before flush").

- **D-122:** **The orchestrator does NOT inject the SIGTERM handler.** It is opt-in by the training script (`from automil.runtime_helpers import register_sigterm_flush; register_sigterm_flush()`). Reasoning: framework-injected signal handlers in user code = invisible behavioural change = debugging nightmare. The cap layer's reconcile path (D-123) handles the "training script forgot to register the handler" case by aggregating fold files from disk anyway.

### Budget-killed reconciliation (CAP-04)

- **D-123:** **`reconcile.py:reconcile_budget_kill(node_id)`** is the post-cancel reconciliation entry. Called by `_orchestrator_daemon.py` when it observes a node transition from RUNNING to CANCELLED with `metadata.cancel_reason == "cap"`:
  1. `payload = aggregate_folds(archive_dir / node_id, expected_fold_count)`
  2. If `payload["partial_folds"] >= 1`:
     - Write `archive/<node_id>/result.json` = payload
     - Update graph node: `status: executed`, `metadata.budget_killed: true`, `composite: payload["composite"]`
     - Move `running/<node>.json` → `archive/<node>/`
  3. If `payload["partial_folds"] == 0`:
     - Write `archive/<node_id>/result.json` with `status: crashed, composite: 0.0`
     - Update graph node: `status: crashed`, `metadata.budget_killed: true`, `composite: 0.0`
  4. Trigger descendant cascade (`_reevaluate_descendants`) — the existing graph logic handles the partial composite correctly because it operates on `composite` numeric, not `status` string.

- **D-124:** **`metadata.budget_killed` is the discriminator** between "experiment crashed organically" and "cap killed me". Distinct from `metadata.cancel_reason: "cli"` (operator cancel) and `metadata.cancel_reason: "cap"` (cap kill). Three lifecycle states post-cancel:
  - `metadata.cancel_reason == "cli"` AND `partial_folds == 0` → `status: cancelled`
  - `metadata.cancel_reason == "cap"` AND `partial_folds >= 1` → `status: executed`, `metadata.budget_killed: true`
  - `metadata.cancel_reason == "cap"` AND `partial_folds == 0` → `status: crashed`, `metadata.budget_killed: true`

### `automil cell` CLI (CAP-06)

- **D-125:** **`automil cell` Click group** lives at `src/automil/cli/cell.py`. Two subcommands:
  - `automil cell status [CELL_ID]` — prints state for one cell (or all if no arg). Output format (tabular):
    ```
    cell_id    dataset  encoder  parent      started_at           consumed/budget   status         running
    a3f9c1d2   ccrcc    uni-v2   node_0042   2026-05-05 10:00:00  03:42:18 / 06:00:00  active         3
    b7e2…      clwd     uni-v2   node_0019   2026-05-04 14:00:00  06:00:00 / 06:00:00  finalized      0
    ```
  - `automil cell list` — short form (cell_id, status, consumed/budget). Pipe-friendly (no headers if `--no-header`).
  - Lazy import of `cells/` inside command body (Phase 1 PATTERNS §8).

### Acceptance gate (CAP-01..06) — Pitfall-4 anti-acceptance

- **D-126:** **Phase 4 acceptance is the conjunction of:**
  1. `tests/cells/test_cell_state.py` covers Cell dataclass + atomic IO + restart-safe consumed_seconds computation.
  2. `tests/cells/test_cap_state_machine.py` covers `next_status()` for all four transitions + idempotency.
  3. `tests/cells/test_aggregate_folds.py` covers all-folds, partial, zero-folds, malformed fold file (skipped with WARNING).
  4. `tests/cells/test_reconcile.py` covers budget_killed=executed (≥1 fold), budget_killed=crashed (zero folds), descendant cascade with partial composite.
  5. `tests/cells/test_cap_fires_with_partial_fold_recovery.py` — **anti-acceptance gate, Pitfall-4 defence** — full end-to-end test: synthesize a 5-fold experiment that writes 3 fold files, send `Backend.cancel(SIGTERM)`, verify reconcile produces `status: executed`, `composite ≠ 0`, `partial_folds == 3`, descendants updated against partial composite (NOT zero). The training script MUST register `automil.runtime_helpers.register_sigterm_flush()`.
  6. `tests/cells/test_cell_state_survives_daemon_kill_restart.py` — kill-9 the daemon mid-cell, restart, assert `consumed_seconds` resumes correctly (NOT reset).
  7. `tests/cells/test_cli_cell_status_list.py` — `automil cell status` + `automil cell list` integration tests.
  8. Existing 558 + 9 skipped baseline stays green — no regression.
  9. `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/cells/` returns zero.

### Per-cell budget override (Leo 2026-05-05)

- **D-134:** **`automil submit` accepts `--budget-seconds N` and `--safety-buffer-seconds M`** Click options that override `cap.*` config values *for the cell this submit opens*. Override semantics:
  - The override is recorded ONLY when this submit is the FIRST in its `(dataset, encoder, parent_id)` cell (i.e., it creates the cell). On subsequent submits joining the existing cell, the flags are IGNORED with a logged INFO ("cell already open with budget_seconds=X; --budget-seconds=Y is ignored").
  - Reasoning: a cell's wall-clock budget is set ONCE at cell creation, then is shared by all experiments in that cell. Allowing later submits to extend a cell's budget = sandbagging vector. Override-only-on-creation is the principled rule.
  - Validation: `budget_seconds > 0`, `0 < safety_buffer_seconds < budget_seconds`. ClickException on violation.
  - This is the "researcher running a 30-min sklearn-iris experiment" use case — they pass `--budget-seconds 1800` once at the start of the cell; the cap fires at 30 min as expected.
  - The framework still ships D-108's `(21600, 1800)` fallback in case neither flag nor config is set (back-compat for any existing autobench script that doesn't read `cap.*`).

### Out of scope (Phase 4)

- **D-127:** **Cell garbage collection** (`finalized` cells stay forever in Phase 4) — v2.
- **D-128:** **Cross-cell budget pooling** ("if cell A finished early, give 30 min to cell B") — v2 / paper-time.
- **D-129:** **Adaptive safety_buffer based on observed fold duration** — v2. Phase 4 ships a static config-set `safety_buffer_seconds: 1800`.
- **D-130:** **Per-experiment budget caps** (sub-cell-level) — out of scope; Phase 4 budgets at the cell granularity only.
- **D-131:** **Cap UI in viz dashboard** — Phase 7 (alongside hardware autodetect).
- **D-132:** **`Backend.healthcheck()` integration** — Phase 7. Phase 4 uses the daemon's existing tick loop.
- **D-133:** **SLURM `--time` directive integration** — Phase 6 (when SLURMBackend lands). Phase 4's cap layer composes via `Backend.cancel(SIGTERM)`; SLURMBackend translates that to `scancel --signal=TERM` in Phase 6.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § Phase 4 (success criteria 1–5)
- `.planning/REQUIREMENTS.md` CAP-01..06
- `.planning/PROJECT.md` § Key decisions (6h cap is per-cell-total, framework-enforced)

### Existing framework code (Phase 4 extends these)
- `src/automil/backends/_orchestrator_daemon.py` — daemon main loop; Phase 4 adds `_tick_cells()` step
- `src/automil/backends/base.py` — `Backend.cancel(handle, signal=SIGTERM)` is the Phase-4 → backend interface (D-57)
- `src/automil/backends/local.py` lines 245-300 — `LocalBackend.cancel` already implements 30s grace + SIGKILL
- `src/automil/cli/submit.py` — submit-pathway; Phase 4 adds cell-budget refusal hook (D-116, D-117)
- `src/automil/graph.py` — `_reevaluate_descendants` cascade; operates on numeric `composite`, so partial values flow through correctly
- `src/automil/cli/__init__.py` — Click main group; cell.py register here

### Phase 0 patterns (continue them)
- `.planning/phases/00-…/00-PATTERNS.md` § "Atomic write via tempfile + os.rename"
- `.planning/phases/00-…/00-PATTERNS.md` § "Click subcommand file structure"

### Phase 1 patterns (continue them)
- `.planning/phases/01-…/01-PATTERNS.md` § 7 "ClickException error format"
- `.planning/phases/01-…/01-PATTERNS.md` § 8 "Lazy import inside command body"

### Phase 2 patterns (continue them)
- `.planning/phases/02-…/02-PATTERNS.md` § "Frozen dataclass with tuple types" (Cell shape)
- `.planning/phases/02-…/02-CONTEXT.md` D-53 (`JobState.BUDGET_KILLED` was reserved for Phase 4 — Phase 4 actually uses it)
- `.planning/phases/02-…/02-CONTEXT.md` D-57 (cancel-signal contract — Phase 4 honours it verbatim)

### Phase 3 patterns (continue them)
- `.planning/phases/03-…/03-CONTEXT.md` D-94, D-97 (metadata.backend / metadata.runtime — Phase 4's metadata.cell_id is symmetric)
- `.planning/phases/03-…/03-PATTERNS.md` § lazy-import discipline

### Anti-pattern reference
- `.planning/research/PITFALLS.md` § Pitfall 4 — wall-clock guillotine without per-fold protocol (Phase 4's primary defence)
- `.planning/codebase/CONCERNS.md` § "Fragile Invariant #6" — descendant cascade against zero composite

### External specs
- [SLURM `--signal=B:TERM@30`](https://slurm.schedmd.com/sbatch.html) — Phase 6 will reuse this; Phase 4's signal contract is compatible
- [Kubernetes #94435 graceful termination](https://github.com/kubernetes/kubernetes/issues/94435) — why hard caps + grace periods are hard

</canonical_refs>

<specifics>
## Specific Ideas

- **`cells/<cell_id>.json` shape (locked):**
  ```json
  {
    "cell_id":               "a3f9c1d2e7b6849a",
    "dataset":               "ccrcc",
    "encoder":               "uni-v2",
    "parent_id":             "node_0042",
    "started_at":            1714932000.0,
    "budget_seconds":        21600,
    "safety_buffer_seconds": 1800,
    "status":                "active"
  }
  ```
  No `consumed_seconds`, no `consumed_seconds_at_last_tick` — those are computed (D-111). Schema is intentionally flat — no nested objects.

- **`automil/config.yaml` extension** (rendered by `automil init` going forward, with comments emphasising consumer-configurable nature):
  ```yaml
  # Cap configuration — consumer-supplied, NOT framework-mandated.
  # autoMIL is generic; values below are example defaults Leo's autoMIL-paper
  # experiment campaign uses across all its datasets (CCRCC, CLWD, future
  # additions). A different consumer (sklearn-iris demo with K=1, an external
  # lab with different time budgets, a follow-up paper) would pick different
  # numbers. The framework only requires that values are present and validated
  # (see D-134); the *values* are entirely the consumer's choice.
  cap:
    budget_seconds:        21600    # 6h — Leo's autoMIL-paper campaign default
    safety_buffer_seconds: 1800     # 30min — must be < budget_seconds; tune to longest-fold duration
  training:
    fold_count: 5                   # 5-fold CV — Leo's paper convention; sklearn-iris would set 1; PathBench-MIL uses 5×5
  ```
  Phase 4 ships fallback defaults of `(21600, 1800, 5)` if `cap:` and `training:` are entirely absent — back-compat for legacy autobench projects that haven't re-run `automil init --update`. The right path for any new consumer (sklearn-iris demo in Phase 8, external labs, follow-up papers) is to set their own values explicitly. Per-cell CLI override (`automil submit --budget-seconds N`) lands as D-134.

- **`get_or_create_cell()` is the only path to cell creation.** No other code constructs a `Cell` directly except deserialisation from `cells/<id>.json`. This keeps the `started_at = time.time()` invariant in one place.

- **The daemon tick interval** stays at the existing default (1 second per ROADMAP Phase 0 cleanup). Cap-tick is one extra step inside the existing loop — no new threading.

- **`refusing-new` reason** in the ClickException at submit-time MUST tell the operator (a) which cell is refusing, (b) how much budget is left until terminating, (c) what action they can take (different cell tuple). Pitfall-9 mitigation — silent rejection is debug-hostile.

- **Cap-firing test design:** synthesize a `Cell` with `budget_seconds=1`, `safety_buffer_seconds=0.2`, write 3 fold files, send SIGTERM via `LocalBackend.cancel(handle)`, wait for reconcile, assert all invariants. Test runs in ~3 seconds with `time.sleep` at appropriate transition points.

- **Daemon-restart test design:** start daemon with a synthetic cell at `started_at = now() - 14400` (4h ago), `budget_seconds=21600` (6h). Kill -9 the daemon. Re-start. Assert `consumed_seconds(cell)` returns ~14400, NOT 0.

</specifics>

<deferred>
## Deferred Ideas

- **Cell garbage collection** — finalized cells stay forever in Phase 4; v2.
- **Cross-cell budget pooling** — paper-time / v2.
- **Adaptive `safety_buffer_seconds`** based on observed fold duration — v2.
- **Per-experiment budget caps** (sub-cell granularity) — out of scope.
- **Cap UI in viz dashboard** — Phase 7.
- **SLURM/Ray cap integration** — Phase 6 (composes via Backend.cancel(SIGTERM)).
- **Mid-fold checkpointing** (within a single fold's training loop) — out of scope; fold granularity is the unit of work.
- **Cap-fire metrics export** (Prometheus, OTel) — v2.

</deferred>

---

*Phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation*
*Context bootstrapped autonomously 2026-05-05 per Leo's "decide engineering, ask features" directive. No open questions for Leo at planning time.*
*Amended 2026-05-05 per Leo's clarification that 6h is the autoMIL-paper campaign-wide default (used across CCRCC, CLWD, and any future datasets in this milestone's paper), NOT framework-mandatory and NOT CCRCC-specific. D-134 added (per-cell `--budget-seconds` CLI override on cell creation only); D-108 default-resolution chain made explicit; §specifics config.yaml example annotated with sklearn-iris / external-lab / follow-up-paper counter-examples. The phase title's "6h" reflects ROADMAP shorthand for the milestone-current campaign value, not a framework constant.*
