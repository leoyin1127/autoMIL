---
phase: 08-decoupling-completion-acceptance
plan: "03"
subsystem: viz
tags: [DEC-04, D-200, migration, viz, reader, metrics]
dependency_graph:
  requires: []
  provides: [node.metrics-read-in-viz, cap-killed-metrics-dict-write]
  affects: [src/automil/viz/static/app.js, src/automil/backends/_orchestrator_daemon.py]
tech_stack:
  added: []
  patterns: [defensive-fallback, static-source-test]
key_files:
  modified:
    - src/automil/viz/static/app.js
    - src/automil/backends/_orchestrator_daemon.py
  created:
    - tests/viz/__init__.py
    - tests/viz/test_app_js_metrics_reader.py
decisions:
  - "metricFields array in app.js stays autobench-shaped for v1 per CONTEXT D-200 deferred section; generic-metric rendering deferred to post-v1"
  - "Defensive (node.metrics || {}) guard preserves legacy graph.json rendering (no node.metrics) without crashing"
  - "Cap-killed reconcile rewrites full metrics dict rather than per-key loop; matches D-200 schema"
metrics:
  duration_minutes: 10
  completed_date: "2026-05-08T03:14:48Z"
  tasks_completed: 2
  files_changed: 4
---

# Phase 8 Plan 03: Downstream Reader Migration Summary

Migrate downstream readers of named-field metric accessors from pre-D-200 top-level `node[key]` to post-D-200 `node["metrics"][key]` access. One-line JS change plus cap-killed orchestrator branch fix, plus 3 regression tests.

## What Was Done

**Task 1: app.js metric reader (1 line changed)**

Changed line 232 in `src/automil/viz/static/app.js` from:

```javascript
var val = node[pair[0]];
```

to:

```javascript
// D-200 / DEC-04: metrics live under node.metrics post-Phase-8; defensive fallback for legacy graph.json returns {}.
var val = (node.metrics || {})[pair[0]];
```

The `(node.metrics || {})` defensive guard ensures legacy graph.json files (where `node.metrics` is undefined) render '-' via the existing `val !== undefined` branch instead of crashing. The `metricFields` array is unchanged per CONTEXT D-200 deferred decision.

**Task 1b: orchestrator cap-killed reconcile branch (3 lines changed)**

Changed `src/automil/backends/_orchestrator_daemon.py` lines 1055-1057 from a per-key loop writing to `gnode[k]` (top-level) to a single `gnode["metrics"] = dict(payload["metrics"])` write. This was an additional downstream WRITE site identified in the execution rules scope.

**Task 2: Regression tests (63 lines added)**

Created `tests/viz/__init__.py` (empty) and `tests/viz/test_app_js_metrics_reader.py` with 3 static-source assertions:

- `test_app_js_reads_node_metrics_post_d200`: post-D-200 pattern present
- `test_app_js_pre_d200_pattern_absent`: pre-D-200 pattern absent (regression prevention)
- `test_app_js_metric_fields_array_unchanged`: metricFields stays autobench-shaped

All 3 pass. Test count +3.

## File-Disjointness with 08-02

08-02 owns `src/automil/graph.py` (WRITE sites). This plan owns `src/automil/viz/static/app.js` and `src/automil/backends/_orchestrator_daemon.py` (READ/WRITE sites for cap-killed branch). No overlap.

## Acceptance Criteria Verification

| Criterion | Status |
|---|---|
| `var val = (node.metrics \|\| {})[pair[0]]` present in app.js line 233 | PASS |
| Pre-D-200 `var val = node[pair[0]]` absent from app.js | PASS |
| Single comment cites D-200 / DEC-04 | PASS |
| `grep -nE 'gnode\[".*_auc"\]\|gnode\[".*_bacc"\]'` returns zero | PASS |
| 3 tests passing in tests/viz/test_app_js_metrics_reader.py | PASS |
| tests/viz/__init__.py exists | PASS |
| No em-dashes introduced by this plan's changes | PASS (pre-existing lines 395/491/512 in app.js are out of scope) |

## Commits

- `41a1cd4` refactor(08-03): migrate viz app.js metric reader to node.metrics (D-200/DEC-04)
- `8f6729a` refactor(08-03): migrate cap-killed reconcile branch to node["metrics"] dict write (D-200/DEC-04)
- `eee681f` test(08-03): add viz app.js metric reader migration regression tests (DEC-04)

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] Orchestrator cap-killed branch write site**

- Found during: Task 1 verification
- Issue: The plan execution rules explicitly listed `_orchestrator_daemon.py:1055-1057` as a target; the code was writing individual metric keys to `gnode[k]` (top-level), not to `gnode["metrics"]`
- Fix: Replaced per-key loop with `gnode["metrics"] = dict(payload["metrics"])` single dict write
- Files modified: `src/automil/backends/_orchestrator_daemon.py`
- Commit: `8f6729a`

**2. Pre-existing em-dashes in app.js**

Lines 395, 491, 512 of app.js contain pre-existing em-dashes in comments unrelated to this plan's changes. These are out of scope per deviation scope boundary (pre-existing issues in unrelated code). Logged to deferred items.

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, or trust-boundary schema changes introduced.
