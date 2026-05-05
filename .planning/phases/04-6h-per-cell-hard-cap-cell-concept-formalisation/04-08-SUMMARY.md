---
phase: "04-6h-per-cell-hard-cap-cell-concept-formalisation"
plan: "08"
subsystem: "autobench / benchmarks"
tags: [autobench, ccrcc, fold-writer, sigterm, runner, CAP-03]

dependency_graph:
  requires:
    - "04-02 (runtime_helpers.py — parallel wave, created here as Rule 3 fix)"
    - "benchmarks/src/autobench/pipeline/clam/runner.py (existing fold loop)"
    - "benchmarks/scripts/run_experiment.py (existing entry point)"
  provides:
    - "per-fold result files: AUTOMIL_RESULTS_DIR/fold_<i>_result.json (D-118 shape)"
    - "register_sigterm_flush() wired into run_experiment.py:main() (D-121 / D-122)"
    - "src/automil/runtime_helpers.py (Rule 3 stub, Wave 1 parallel delivery)"
  affects:
    - "04-04 (aggregate_folds reads fold files created here)"
    - "04-07 (daemon reconcile_budget_kill reads fold files)"
    - "04-10 / 04-11 (integration test fires SIGTERM, expects partial result.json)"

tech_stack:
  added:
    - "src/automil/runtime_helpers.py — new module; register_sigterm_flush() + get_fold_count()"
    - "tests/test_per_fold_writer.py — 6-test suite for _write_fold_result_json"
  patterns:
    - "_unwrap() defensive pattern for flat-float vs CI-dict metric shapes (Pitfall 5)"
    - "AUTOMIL_RESULTS_DIR env-gating: no-op outside orchestrator"
    - "lazy import of aggregate_folds inside SIGTERM handler body (defers cells/ dependency to call time)"
    - "signal.signal() registered at top of main() before DataLoader (Pitfall 1 compliance)"

key_files:
  created:
    - "src/automil/runtime_helpers.py"
    - "tests/test_per_fold_writer.py"
  modified:
    - "benchmarks/src/autobench/pipeline/clam/runner.py"
    - "benchmarks/scripts/run_experiment.py"

decisions:
  - "Place _write_fold_result_json() as a module-level helper in runner.py (not inside train_fold) so the call site is after fold_results.append(result) in run_experiment() — the natural write point per D-118 and Research finding #3"
  - "Defensive _unwrap() handles both flat-float (actual per-fold shape from compute_extended_metrics) and CI-dict shape (post-compute_confidence_intervals) — belt-and-suspenders per Pitfall 5"
  - "runtime_helpers.py created here (Rule 3) with correct implementation matching Plan 04-02 spec, since Plan 04-02 runs in the same wave and the import would fail at module load time without it"
  - "SIGTERM handler uses lazy import of aggregate_folds from automil.cells.reconcile — allows runtime_helpers.py to compile independently of the cells/ package (which lands in Wave 2)"

metrics:
  duration: "7m 33s"
  completed: "2026-05-05"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 2
---

# Phase 04 Plan 08: Per-Fold Writer + SIGTERM Flush Wiring Summary

**One-liner:** Per-fold `fold_<i>_result.json` writer integrated into CLAM runner with D-118 shape, plus `register_sigterm_flush()` opt-in wired into `run_experiment.py:main()` before DataLoader construction.

## What Was Built

### Task 1: `_write_fold_result_json()` in `benchmarks/src/autobench/pipeline/clam/runner.py`

Added module-level helper function immediately after `fold_results.append(result)` in the fold loop of `run_experiment()`. The helper:
- Is a no-op when `AUTOMIL_RESULTS_DIR` is unset (running outside orchestrator)
- Reads `fold_count` from `AUTOMIL_FOLD_COUNT` env (default 5)
- Maps `test_metrics["auc_roc"]` / `test_metrics["balanced_accuracy"]` → D-118 flat keys `test_auc`, `test_bacc` (and val equivalents)
- `_unwrap()` inner function handles both flat-float (actual per-fold shape) and CI-dict (`{"mean": ..., "std": ...}`) metric shapes — Pitfall 5 defence
- Writes `fold_{fold_index}_result.json` to `AUTOMIL_RESULTS_DIR/` via `pathlib.Path.write_text()`

**Key insight from code read:** `compute_extended_metrics()` returns plain `float` values (not CI dicts) at the per-fold level. CI dicts only appear after `compute_confidence_intervals()` is applied across all folds in `run_experiment()`. The _unwrap() defensive layer handles both shapes correctly regardless.

### Task 2: `register_sigterm_flush()` in `benchmarks/scripts/run_experiment.py`

Added import `from automil.runtime_helpers import register_sigterm_flush` after the dotenv/torch module-level imports. Added `register_sigterm_flush()` as the very first statement of `main()`, before `parse_args()` and before any DataLoader/multiprocessing construction — satisfying the Pitfall 1 constraint (signal.signal() must be called from main thread before threading).

### Rule 3 Deviation: Created `src/automil/runtime_helpers.py`

Plan 04-02 (same Wave 1) creates this module, but since both plans execute in parallel, the import `from automil.runtime_helpers import register_sigterm_flush` in `run_experiment.py` would fail at module load time if 04-02 hasn't completed yet. Created the full correct implementation matching Plan 04-02's spec: `register_sigterm_flush()` with `_SIGTERM_REGISTERED` idempotency guard, lazy import of `aggregate_folds` from `automil.cells.reconcile`, `sys.exit(0)` (not 130), and `get_fold_count()` env reader.

### Task 3: `tests/test_per_fold_writer.py`

6 pytest tests covering the full `_write_fold_result_json` contract:
1. `test_writes_fold_file_when_results_dir_set` — full D-118 shape assertion
2. `test_noop_when_results_dir_unset` — env-gating
3. `test_metric_keys_mapped_correctly_from_dict_shape` — CI-dict unwrap (Pitfall 5)
4. `test_writes_one_file_per_fold` — 5-fold uniqueness + fold_index correctness
5. `test_uses_automil_fold_count_env` — `AUTOMIL_FOLD_COUNT=7` sourced correctly
6. `test_handles_missing_metrics_gracefully` — empty metrics → 0.0 fallback, no exception

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Missing Dependency] Created runtime_helpers.py (Plan 04-02 parallel wave)**
- **Found during:** Task 2
- **Issue:** `from automil.runtime_helpers import register_sigterm_flush` in `run_experiment.py` fails at import time if `src/automil/runtime_helpers.py` doesn't exist. Plan 04-02 runs in the same Wave 1 but may not complete before this plan. The module must exist for `uv run python -c "import benchmarks.scripts.run_experiment"` to pass.
- **Fix:** Created full correct implementation of `runtime_helpers.py` matching Plan 04-02's spec (D-121). Not a minimal stub — the full module is correct and Plan 04-02 landing will either confirm identical content or supersede. No framework functionality is duplicated or added beyond what D-121 specifies.
- **Files modified:** `src/automil/runtime_helpers.py` (created)
- **Commit:** 8eeb1e5

## Test Results

| Suite | Result | Count |
|-------|--------|-------|
| `tests/test_per_fold_writer.py -x` | PASSED | 6/6 |
| `tests/ -x` (full automil suite) | PASSED | 393/393 |
| `benchmarks/tests/ --ignore=test_run_feature_extraction.py` | PASSED | 247/247 |

Note: `benchmarks/tests/test_run_feature_extraction.py::TestSkipSegCoordsDir::test_coords_dir_format` fails (expects `256px_0px_overlap`, actual `224px_0px_overlap`) — pre-existing regression unrelated to this plan's changes. Logged to deferred items.

## Verification Checklist

| Check | Result |
|-------|--------|
| `grep -c "def _write_fold_result_json" runner.py` | 1 |
| `grep -c "_write_fold_result_json(fold, result)" runner.py` | 1 |
| `grep -c "AUTOMIL_RESULTS_DIR" runner.py` | 2 |
| `grep -c "AUTOMIL_FOLD_COUNT" runner.py` | 1 |
| `grep -c '"fold_index"' runner.py` | 1 |
| `grep -c '"composite"' runner.py` | 1 |
| `grep -c '"val_auc"' runner.py` | 1 |
| `grep -c "def _unwrap" runner.py` | 1 |
| `grep -c "register_sigterm_flush()" run_experiment.py` | 1 |
| `register_sigterm_flush()` before DataLoader | OK (line 106, no DataLoader before it) |
| `grep -rE "from autobench\|AUTOBENCH_" src/automil/cells/` | 0 (framework clean) |
| `uv run python -c "import benchmarks.scripts.run_experiment"` | IMPORT OK |
| `uv run python -m py_compile run_experiment.py` | COMPILE OK |

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The only new disk write path is `AUTOMIL_RESULTS_DIR/fold_<i>_result.json` — same exposure surface as the existing `AUTOMIL_RESULTS_DIR/result.json` contract (T-04-23: accepted per plan's threat model).

T-04-22 mitigation confirmed: `_write_fold_result_json` does NOT swallow exceptions in the `fold_path.write_text()` call — disk-full / permission errors propagate to the training script (loud crash) as designed. Only the `AUTOMIL_RESULTS_DIR`-unset path is silent.

## Known Stubs

None. The per-fold writer is fully functional end-to-end. `runtime_helpers.py`'s SIGTERM handler has a fallback for when `automil.cells.reconcile` is not yet deployed (ImportError path), but this is an intentional graceful-degradation path for Wave 1 deployment, not a stub.

## Self-Check: PASSED
