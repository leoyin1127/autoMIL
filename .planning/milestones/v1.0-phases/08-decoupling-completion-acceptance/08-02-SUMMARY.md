---
phase: 08-decoupling-completion-acceptance
plan: "02"
subsystem: graph
tags: [refactor, dict-spread, pareto, decoupling, DEC-04]
dependency_graph:
  requires: []
  provides: [D-200 dict-spread storage, OQ-9 Option B Pareto]
  affects: [src/automil/graph.py, tests/test_graph_dict_spread.py]
tech_stack:
  added: []
  patterns: [dict-spread node storage, composite-only Pareto dominance]
key_files:
  modified:
    - src/automil/graph.py
  created:
    - tests/test_graph_dict_spread.py
decisions:
  - "OQ-9 Option B: composite-only Pareto (c_comp > p_comp) across all 3 dominance sites"
  - "No graph.json schema_version bump: forward-compatible cleanup, pre-D-200 files unaffected"
  - "vram_gb, elapsed_min, gpu stay at top level (init.py reads vram_gb for empirical defaults)"
  - "autobench comment removed from _reevaluate_descendants to preserve framework purity gate"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 8 Plan 02: D-200 dict-spread + OQ-9 Option B Pareto Summary

**One-liner:** Replaced 5 named-field-copy write sites in graph.py with `node["metrics"] = dict(metrics)` and migrated 3 Pareto dominance sites to composite-only (`c_comp > p_comp`), decoupling the framework from autobench's 4-key metric schema.

## What Was Done

### Task 1: graph.py Refactor (5 write sites + 3 Pareto sites)

**Write sites migrated:**

| Site | Function | Before | After |
|------|----------|--------|-------|
| add_executed line ~134 | add_executed | 4 named keys (test_auc, test_bacc, val_auc, val_bacc) | `"metrics": dict(metrics)` |
| promote line ~212 | promote | 4 named assignments | `node["metrics"] = dict(metrics)` |
| reconcile metrics assembly line ~559 | reconcile | 4 named `comp_metrics.get(...)` | `metrics = dict(comp_metrics); metrics["composite"] = ...` |
| reconcile recovery node line ~609 | reconcile | 4 named `metrics["test_auc"]` etc | `"metrics": dict(comp_metrics)` |
| archive-result-recovery line ~683 | reconcile | 4 named `r_metrics.get(...)` | `"metrics": dict(r_metrics)` |

**Pareto sites migrated (OQ-9 Option B):**

| Site | Function | Before | After |
|------|----------|--------|-------|
| _reevaluate_descendants line ~263 | _reevaluate_descendants | `c_auc >= p_auc and c_bacc >= p_bacc and c_comp > p_comp` | `c_comp > p_comp` |
| reconcile Pareto check line ~547 | reconcile | `comp_metrics.get("test_auc") >= p_auc and ... and composite > p_comp` | `composite > p_comp` |
| archive-recovery Pareto line ~666 | reconcile | `r_metrics.get("test_auc") >= p_auc and ... and composite > parent_composite` | `composite > parent_composite` |

**Bootstrap loader preserved:** `import_from_tsv` (lines 779-810) retains `val_auc`/`test_auc` named parsing for backwards-compat with pre-D-200 results.tsv files. The variables flow into `add_executed`'s `metrics` dict input, ending up at `node["metrics"]["val_auc"]` automatically.

**Framework-owned scalars preserved at top level:** `composite`, `parent_delta`, `global_delta`, `vram_gb`, `elapsed_min`, `gpu`, `commit`, `archive_id`, `config_hash`, `potential`, `child_count`, `created_at`.

### Task 2: Regression Tests

Created `tests/test_graph_dict_spread.py` with 6 tests, all passing:

1. `test_add_executed_round_trips_arbitrary_metric_keys` - arbitrary keys (top1, top5, custom_score) survive
2. `test_sklearn_iris_two_key_metrics_stored` - sklearn-iris {accuracy, f1} shape works; no val_auc auto-default
3. `test_autobench_four_key_metrics_stored` - autobench 4-key shape works; keys NOT at top level post-D-200
4. `test_promote_uses_dict_spread` - promote() stores metrics under node["metrics"]
5. `test_pareto_dominance_is_composite_only` - child with higher composite but lower val_auc gets "keep"
6. `test_node_metrics_no_silent_zero_default` - framework does not bake autobench keys on minimal payload

## Acceptance Verification

```
grep -nE '"(test_auc|test_bacc|val_auc|val_bacc)":' src/automil/graph.py
# Returns: only lines 783-784 (bootstrap loader parsed-tuple construction)

grep -rE "autobench|AUTOBENCH_|benchmarks/" src/automil/graph.py
# Returns: zero matches (framework purity preserved)

grep -nP "\x{2014}|\x{2013}" tests/test_graph_dict_spread.py
# Returns: zero matches (no em/en-dashes)

uv run pytest tests/test_graph_dict_spread.py tests/test_graph.py tests/test_integration.py -q
# 44 passed
```

## Deviations from Plan

**1. [Rule 2 - Framework Purity] Removed autobench mention from _reevaluate_descendants comment**

- **Found during:** Task 2 acceptance grep check
- **Issue:** The comment I wrote in `_reevaluate_descendants` said "encodes autobench's 4-key monotonicity guard" which would fail `grep -rE "autobench..." src/automil/graph.py`
- **Fix:** Changed to "encodes a named-key monotonicity guard"
- **Files modified:** src/automil/graph.py
- **Commit:** a9f7819

No other deviations. Plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| fce12e5 | refactor(08-02): D-200 dict-spread + OQ-9 Option B Pareto in graph.py |
| a9f7819 | test(08-02): add D-200 dict-spread regression tests + purity fix |

## Self-Check: PASSED

- src/automil/graph.py exists and modified: CONFIRMED
- tests/test_graph_dict_spread.py exists: CONFIRMED
- Commits fce12e5 and a9f7819 exist: CONFIRMED
- 44 tests pass: CONFIRMED
- Named-field copies only in bootstrap loader: CONFIRMED
- Framework purity (zero autobench refs): CONFIRMED
- Em-dash gate clean: CONFIRMED
