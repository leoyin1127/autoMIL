---
phase: 05-generalization-gate
plan: "04"
subsystem: gate
tags: [nominate, candidate-status, graph-helpers, promotion-rate, tdd, gte-05, gte-06]
dependency_graph:
  requires: ["05-01", "05-02"]
  provides: ["gate/nominate.py", "ExperimentGraph.nominations_in_window", "ExperimentGraph.promotion_rate"]
  affects: ["05-06 (evaluate.py)", "05-07 (promote.py)", "05-09 (cli/nominate.py)", "05-10 (viz/server.py)"]
tech_stack:
  added: []
  patterns: ["idempotent mutation (cells/registry.py analog)", "TDD RED/GREEN/REFACTOR", "history audit trail", "rolling-window rate helper"]
key_files:
  created:
    - src/automil/gate/nominate.py
    - tests/gate/test_nominate.py
    - tests/test_graph_promotion_helpers.py
  modified:
    - src/automil/gate/__init__.py
    - src/automil/graph.py
decisions:
  - "Idempotent on 'candidate' re-call: no history event appended; log at INFO only (D-142)"
  - "Timezone normalisation in nominations_in_window: naive timestamps coerced to UTC (backward compat)"
  - "Inserted helpers after rank_proposals in ExperimentGraph — natural grouping with other read-helpers"
metrics:
  duration_minutes: 4
  completed_date: "2026-05-06"
  tasks_completed: 2
  files_modified: 5
---

# Phase 5 Plan 4: nominate + graph promotion helpers Summary

Implemented the `nominate` operation (GTE-05) and two `ExperimentGraph` helpers (`nominations_in_window`, `promotion_rate`, GTE-06). Status string `candidate` is purely additive — no schema migration, no cascade change to `_reevaluate_descendants` (D-136 confirmed unchanged).

## What Was Built

**`src/automil/gate/nominate.py`** — `nominate(node_id, graph, agent_initiated=False)`:
- Mutates `node["status"]` from `keep` to `candidate` in-place
- Idempotent: re-call on already-`candidate` node is a no-op (logs INFO, returns early, does NOT append a second history event)
- Raises `ValueError` for: unknown node_id (message includes "not found"), non-keep/non-candidate status (message includes the current status and "keep")
- Appends `{"event": "nominated", "timestamp": <ISO-8601 UTC>, "agent_initiated": bool}` to `node["history"]` (via `setdefault`)
- Does NOT call `graph.save()` — caller controls persistence (same discipline as `cells/registry.py`)

**`src/automil/graph.py`** — additive helpers:
- `nominations_in_window(days=30)`: returns list of node dicts with a "nominated" history event within rolling window; handles missing `history` key (D-147 legacy compat); normalises naive timestamps to UTC before comparison
- `promotion_rate(days=30)`: `promoted / nominated` over window (D-144); returns `0.0` if no nominations (zero-division guard); "promoted" = status currently `"registered"`

**`src/automil/gate/__init__.py`** — `nominate` added to imports and `__all__` (alphabetical order).

## TDD Gate Compliance

RED commits:
- `0e38885 test(05-04): add failing tests for gate/nominate.py — RED phase` (8 tests)
- `bfab301 test(05-04): add failing tests for ExperimentGraph promotion helpers — RED phase` (9 tests)

GREEN commits:
- `d7f2114 feat(05-04): implement gate/nominate.py — keep -> candidate idempotent mutation`
- `c614629 feat(05-04): add nominations_in_window + promotion_rate to ExperimentGraph`

## Commits

| Hash | Type | Message |
|------|------|---------|
| `0e38885` | test | Failing tests for gate/nominate.py (RED) |
| `d7f2114` | feat | gate/nominate.py implementation (GREEN) |
| `bfab301` | test | Failing tests for ExperimentGraph helpers (RED) |
| `c614629` | feat | nominations_in_window + promotion_rate (GREEN) |

## Deviations from Plan

None — plan executed exactly as written. The `datetime.fromisoformat` count in graph.py returns 2 (not "at least 1") because there is one existing usage in the reconciliation path; both are valid usages.

Pre-existing RED-phase test failure `tests/test_rank_held_out_filter.py::test_rank_filters_held_out_by_default` (from parallel plan 05-05) noted — out of scope for this plan, not introduced by these changes.

## Known Stubs

None.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced by this plan. The `candidate` status is an in-memory/graph.json field, not a new trust boundary.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `src/automil/gate/nominate.py` exists | FOUND |
| `tests/gate/test_nominate.py` exists | FOUND |
| `tests/test_graph_promotion_helpers.py` exists | FOUND |
| commit `0e38885` (RED test nominate) | FOUND |
| commit `d7f2114` (GREEN nominate impl) | FOUND |
| commit `bfab301` (RED test helpers) | FOUND |
| commit `c614629` (GREEN helpers impl) | FOUND |
| 17 new tests pass | CONFIRMED |
| 30 existing graph tests pass | CONFIRMED |
| Framework purity (0 autobench refs) | CONFIRMED |
| BCK-04 lint clean | CONFIRMED |
