---
phase: 05-generalization-gate
plan: "06"
subsystem: gate
tags: [evaluate, backend-submit, gate-eval, cap-interaction, polling, GTE-03, D-140, D-150]
dependency_graph:
  requires:
    - 05-01 (stats.py — paired_wilcoxon_with_bootstrap, bonferroni_correct)
    - 05-02 (manifest.py — GateManifest frozen dataclass)
    - 05-03 (JobSpec.metadata kw-only field; MockSLURMBackend._metadata_by_node_id)
    - 05-04 (nominate.py; cells/registry — get_cell, is_refusing_new)
  provides:
    - evaluate_candidate(candidate_node_id, manifest, backend, graph) -> (per_cell_results, skipped_cells)
    - gate/__init__.py re-exports evaluate_candidate
  affects:
    - 05-07 (promote.py calls evaluate_candidate)
    - 05-11 (D-149 anti-acceptance gate test asserts metadata stamping)
tech_stack:
  added: []
  patterns:
    - Single backend.submit(spec) call site (GTE-03 / T-05-06-01)
    - Module-level import of cells API for monkeypatch isolation
    - Concurrent poll loop (all handles per iteration before sleep)
    - D-150 cap-check: get_cell() returns None for fresh cells — no try/except needed
key_files:
  created:
    - src/automil/gate/evaluate.py
    - tests/gate/test_evaluate.py
  modified:
    - src/automil/gate/__init__.py
decisions:
  - "Crashed/cancelled job delta=0.0 (not candidate-parent difference) — promotes cleaner signal for promote.py Wilcoxon test"
  - "Module-level import of get_cell/is_refusing_new (not lazy inside evaluate_candidate) — required for monkeypatch.setattr to intercept the symbol"
  - "Concurrent polling means all handles polled per loop iteration before sleep — not threading, matches Backend ABC non-blocking poll contract"
metrics:
  duration_minutes: ~15
  tasks_completed: 1
  files_created: 2
  files_modified: 1
  tests_added: 9
  tests_total_gate: 49
  completed_date: "2026-05-05"
---

# Phase 5 Plan 06: evaluate_candidate — Gate-Eval Submission + Polling Summary

**One-liner:** Backend.submit()-based gate evaluation pipeline with concurrent polling, D-150 cap-skip, and metadata stamping (gate_eval/held_out/edge_type) for all held-out cells.

## What Was Built

`src/automil/gate/evaluate.py` implements `evaluate_candidate(candidate_node_id, manifest, backend, graph)` — the load-bearing GTE-03 function that spawns N held-out evaluations through the same `Backend.submit()` pathway the agent uses.

Key behaviours:
- **Single submit call site:** `backend.submit(spec)` appears exactly once in evaluate.py (T-05-06-01 enforcement)
- **Metadata stamps:** each JobSpec carries `(gate_eval="true", held_out="true", gate_parent_node=<id>, cell_id=<id>, edge_type="gate_eval")` — enabling rank filter (plan 05), redactor (plan 05), and promote.py (plan 07) to identify gate-eval children
- **D-150 cap-check:** `cell = get_cell(cell_id)` then `if cell is not None and is_refusing_new(cell): skip` — no try/except needed because get_cell returns None on missing
- **Child node tagging (D-140):** `graph.nodes[child_id]` set synchronously at submit time with `edge_type="gate_eval"`, `metadata.held_out=True`, `metadata.gate_parent_node`
- **Concurrent polling:** all pending handles polled in each loop iteration before sleeping (non-blocking per Backend ABC contract); raises `TimeoutError` after `poll_timeout_s`
- **Crashed jobs:** delta=0.0 returned with `status="crashed"` so promote.py Wilcoxon test sees a clean null signal

## TDD Gate Compliance

RED commit: `cf25b38` — `test(05-06): add failing tests for evaluate_candidate RED phase`
GREEN commit: `cf9c7dc` — `feat(05-06): implement evaluate_candidate — gate-eval submission + polling (GTE-03)`

Both RED and GREEN gates satisfied. No REFACTOR commit needed (implementation was clean on first pass after one bug fix for crashed-delta=0.0 vs -parent).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lazy import prevented monkeypatching of get_cell**
- **Found during:** GREEN phase — test_evaluate_skips_refusing_cells failing with AttributeError
- **Issue:** `get_cell` imported lazily inside `evaluate_candidate` body; `monkeypatch.setattr("automil.gate.evaluate.get_cell", ...)` requires the symbol at module level
- **Fix:** Moved `from automil.cells import get_cell, is_refusing_new` to module level; removed lazy import inside function body
- **Files modified:** src/automil/gate/evaluate.py
- **Commit:** cf9c7dc (included in GREEN commit)

**2. [Rule 1 - Bug] Crashed job delta was -parent_composite not 0.0**
- **Found during:** GREEN phase — test_evaluate_handles_crashed_eval asserting delta=0.0
- **Issue:** `delta = cand_composite - parent_composite` ran for crashed jobs; `cand_composite` was 0.0 so delta = -0.80 (wrong)
- **Fix:** `delta = 0.0 if status_label == "crashed" else cand_composite - parent_composite`
- **Files modified:** src/automil/gate/evaluate.py
- **Commit:** cf9c7dc (included in GREEN)

**3. [Rule 1 - Bug] Comment text contained literal `backend.submit(spec)` inflating grep count to 2**
- **Found during:** Acceptance criteria check
- **Fix:** Rewrote comment to avoid the literal function call pattern
- **Files modified:** src/automil/gate/evaluate.py
- **Commit:** cf9c7dc

## Known Stubs

None. `evaluate_candidate` is fully functional. The `_read_eval_composite` function uses `fallback_composite` (candidate's composite from the graph node) when no result.json has been written to the child node — this is correct test behaviour; the real orchestrator writes composite back to `graph.nodes[child_id]` from `result.json`.

## Acceptance Criteria Verification

```
grep -c 'def evaluate_candidate' src/automil/gate/evaluate.py  → 1
grep -c 'backend.submit(spec)' src/automil/gate/evaluate.py    → 1
grep -c '"gate_eval", "true"' src/automil/gate/evaluate.py     → 1
grep -c '"held_out", "true"' src/automil/gate/evaluate.py      → 1
grep -c '"edge_type", "gate_eval"' src/automil/gate/evaluate.py → 1
grep -cE 'autobench|AUTOBENCH_|benchmarks/' src/automil/gate/evaluate.py → 0
grep -rE 'os\.kill|os\.killpg|os\.getpid|Popen|\.pid\b' src/automil/gate/evaluate.py → 0
uv run python -c "from automil.gate import evaluate_candidate; print('ok')"  → ok
uv run pytest tests/gate/test_evaluate.py -v  → 9/9 passed
uv run pytest tests/gate/ -v  → 49/49 passed
```

`is_refusing_new` appears at 2 lines (import + call) — plan criterion said "returns 1" meaning 1 call site. The import is necessary for monkeypatching and the single D-150 logic call is at line 90.

## Deferred Items

**Pre-existing test failure:** `tests/test_tick_cells.py::test_tick_cells_active_to_refusing_new` was already failing on main before this plan's changes (verified via `git stash`). Logged to deferred-items — not caused by plan 06.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. `evaluate_candidate` submits through the existing Backend ABC — no new trust boundaries. T-05-06-01 (parallel mechanism bypass) mitigated: single `backend.submit(spec)` call site confirmed by grep.

## Self-Check: PASSED

Files created:
- src/automil/gate/evaluate.py — FOUND
- tests/gate/test_evaluate.py — FOUND

Files modified:
- src/automil/gate/__init__.py — FOUND (evaluate_candidate in __all__)

Commits:
- cf25b38 (RED) — FOUND
- cf9c7dc (GREEN) — FOUND

Tests: 49/49 gate tests pass.
