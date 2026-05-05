---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: 04
subsystem: cells/reconcile
tags: [reconcile, aggregate-folds, partial-result, tdd, budget-kill, cap]

requires:
  - phase: 04
    plan: 02
    provides: "cells package scaffold + aggregate_folds early stub (Rule-3 deviation)"
  - phase: 04
    plan: 03
    provides: "cap state machine (cells/cap.py + cells/state.py)"

provides:
  - "automil.cells.reconcile.aggregate_folds() — D-119-compliant pure reader (tightened from Plan 04-02 stub)"
  - "automil.cells.reconcile.reconcile_budget_kill() — stub per D-123; writes result.json with metadata.budget_killed=True"
  - "reconcile_budget_kill exported from cells/__init__.py public surface"

affects:
  - 04-08 (daemon _handle_completion — wires reconcile_budget_kill into _tick_cells + adds graph mutations)
  - 04-11 (end-to-end anti-acceptance test — fires reconcile_budget_kill path)

tech-stack:
  added: []
  patterns:
    - "aggregate_folds: except (json.JSONDecodeError, OSError) — narrow catch, not broad Exception"
    - "reconcile_budget_kill stub: writes result.json + tags metadata.budget_killed; graph mutations deferred to Plan 04-08"
    - "Pure-reader aggregate_folds returns no metadata field — reconcile_budget_kill adds metadata.budget_killed on its payload copy"

key-files:
  created:
    - tests/cells/test_aggregate_folds.py
  modified:
    - src/automil/cells/reconcile.py
    - src/automil/cells/__init__.py

key-decisions:
  - "aggregate_folds does NOT include metadata in its return dict — it is a pure reader of fold data; reconcile_budget_kill stamps metadata.budget_killed on the payload it receives (D-124 discriminator)"
  - "reconcile_budget_kill stub: graph param accepted but not used — Plan 04-08 adds graph.add_executed/mark_failed + _reevaluate_descendants when daemon context is in scope"
  - "except (json.JSONDecodeError, OSError) not bare Exception — malformed files are skipped with WARNING per T-04-09 threat mitigation"

metrics:
  duration: "~4 min"
  completed: "2026-05-05"
  tasks: 2
  files_modified: 3
---

# Phase 4 Plan 04: aggregate_folds + reconcile_budget_kill — SUMMARY

**Canonical D-119 aggregate_folds implementation + D-123 reconcile_budget_kill stub with metadata.budget_killed=True tagging**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-05-05
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2 modified, 1 created

## Accomplishments

- 9-test `test_aggregate_folds.py` suite covering all D-119 cases: completed (K/K folds), partial (1..K-1), crashed (0), malformed fold skipped with WARNING, metrics mean per-key, elapsed sum, peak_vram max, extra-fold defence, mixed-key metrics
- `reconcile.py` rewritten per D-119 + D-123 verbatim:
  - `aggregate_folds`: narrow `except (json.JSONDecodeError, OSError)`, no `metadata` in return (pure reader), `_crashed_payload` helper, `if not node_archive.exists()` guard
  - `reconcile_budget_kill(node_id, archive_dir, graph, expected_fold_count) -> dict`: calls `aggregate_folds`, stamps `metadata.budget_killed=True`, writes `archive/<node_id>/result.json`, returns payload (D-124)
- `cells/__init__.py`: `reconcile_budget_kill` added to import + `__all__` (additive; `aggregate_folds` already present)
- 595 passed / 9 skipped — no regressions (was 586 before this plan's 9 new tests)
- BCK-04 lint clean: no `os.getpid/os.kill/Popen/.pid` in `src/automil/cells/`

## Task Commits

1. **Task 1: Write test_aggregate_folds.py (RED)** — `4954a92` (test)
2. **Task 2: Implement reconcile_budget_kill + tighten aggregate_folds (GREEN)** — `271f6de` (feat)

## Files Created/Modified

- `tests/cells/test_aggregate_folds.py` — 9 tests; _write_fold helper; caplog for malformed-fold WARNING assertion
- `src/automil/cells/reconcile.py` — full rewrite: D-119-compliant aggregate_folds + D-123 reconcile_budget_kill stub
- `src/automil/cells/__init__.py` — reconcile_budget_kill added to import + __all__

## Decisions Made

- `aggregate_folds` return dict does NOT include `"metadata"` — it is a pure reader of fold data; `reconcile_budget_kill` stamps `metadata.budget_killed=True` on its own copy of the payload. This preserves the separation between the pure aggregation function and the reconciliation path.
- `reconcile_budget_kill` `graph` parameter is accepted but unused in the stub — Plan 04-08 adds `graph.add_executed` / `graph.mark_failed` + `_reevaluate_descendants` when the daemon context is in scope (D-123 steps 2b/3b).
- Narrow `except (json.JSONDecodeError, OSError)` instead of bare `except Exception` — defends T-04-09 tampering threat; unexpected exceptions (e.g., PermissionError) propagate rather than being silently swallowed.

## Deviations from Plan

### TDD Gate Compliance Note

The TDD RED phase for Task 1 did not produce a `ModuleNotFoundError` as the plan expected. Plan 04-02's Rule-3 deviation landed a full `aggregate_folds` implementation in `reconcile.py` before this plan ran. All 9 tests passed immediately on the RED commit.

The TDD RED commit (`4954a92`) represents the behavioral specification — 9 tests documenting all D-119 contracts. The GREEN commit (`271f6de`) tightened the existing implementation (narrow exception catch, removed spurious `metadata` from pure-reader return) and added `reconcile_budget_kill`.

The fail-fast rule was honored: the unexpected passing was noted, investigated, and documented rather than being treated as a gate failure.

### No Other Deviations

Plan executed as specified. No Rule 1/2/3 auto-fixes beyond what is documented above.

## Known Stubs

- `reconcile_budget_kill`: `graph` parameter is accepted but not used. Plan 04-08 adds the graph mutations (`graph.add_executed` / `graph.mark_failed` + `_reevaluate_descendants`). The stub correctly writes `result.json` and returns the payload — sufficient for Plan 04-11's integration test.

## Threat Flags

No new network endpoints, auth paths, or unexpected trust boundaries. `reconcile_budget_kill` writes `archive/<node_id>/result.json` — same trust boundary as existing `archive/` directory (T-04-11 accepted in plan threat register).

## Self-Check: PASSED

Files verified:
- `tests/cells/test_aggregate_folds.py` — FOUND
- `src/automil/cells/reconcile.py` — FOUND
- `src/automil/cells/__init__.py` — FOUND

Commits verified:
- `4954a92` (test RED) — in git log
- `271f6de` (feat GREEN) — in git log

Test results: 9/9 aggregate_folds tests pass; 4/4 runtime_helpers tests pass; 595/595 full suite passes (9 skipped unchanged).

Acceptance criteria:
- [x] `def aggregate_folds(node_archive: Path, expected_fold_count: int) -> dict` — 1 match
- [x] `def reconcile_budget_kill` — 1 match
- [x] `node_archive.glob` — 1 match
- [x] `fold_*_result.json` — 2 matches
- [x] `json.JSONDecodeError` — 1 match
- [x] `logger.warning` — 3 matches (malformed fold + non-numeric metric)
- [x] `"budget_killed"] = True` — 1 match
- [x] `from automil.cells.reconcile import aggregate_folds, reconcile_budget_kill` in __init__.py — 1 match
- [x] `"aggregate_folds"` in __all__ — 1 match
- [x] `"reconcile_budget_kill"` in __all__ — 1 match
- [x] No autobench/AUTOBENCH_/benchmarks/ refs in reconcile.py — 0 matches
- [x] BCK-04 clean — no os.getpid/os.kill/Popen/pid in cells/

---
*Phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation*
*Completed: 2026-05-05*
