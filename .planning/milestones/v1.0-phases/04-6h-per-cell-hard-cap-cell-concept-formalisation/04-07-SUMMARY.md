---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: "07"
subsystem: daemon-cap-integration
tags: [daemon, tick-cells, state-machine, cancel, reconcile, integration, cap]

dependency_graph:
  requires:
    - 04-03  # next_status pure state machine
    - 04-04  # reconcile_budget_kill + aggregate_folds
    - 04-05  # list_cells, get_cell, is_refusing_new registry
  provides:
    - _tick_cells inserted into daemon tick() at step 1.5
    - _running_in_cell helper for cell-id-tagged experiment filtering
    - cap-detection block in _handle_completion (D-123, D-124)
    - AUTOMIL_FOLD_COUNT env injection into experiment subprocesses (D-120)
  affects:
    - 04-09  # automil cell CLI — reads cell state written by _tick_cells
    - 04-11  # end-to-end Pitfall-4 cap-firing integration test

tech_stack:
  added:
    - "_NodeHandle frozen dataclass in _orchestrator_daemon.py (minimal handle for cancel dispatch)"
    - "self.backend: object | None attribute on ExperimentOrchestrator (injectable for tests)"
  patterns:
    - "cancel_reason annotation written BEFORE backend.cancel() (Pitfall 4 ordering)"
    - "promote-in-place graph node via dict mutation (not add_executed — avoids double-count)"
    - "self.automil_dir / 'cells' used directly in _tick_cells (avoids _find_automil_dir() CWD walk)"

key_files:
  modified:
    - path: src/automil/backends/_orchestrator_daemon.py
      changes: |
        +_NodeHandle frozen dataclass (minimal handle with .node_id)
        +self.backend = None attribute on __init__
        +_running_in_cell(cell_id) method — filters self.running by spec.metadata.cell_id
        +_tick_cells() method — full cap state machine integration (ACTIVE/REFUSING_NEW/TERMINATING/FINALIZED)
        +_read_fold_count_for_node(node_id) helper — reads from spec.env or config.yaml
        +cap-detection block in _handle_completion — detects cancel_reason='cap', calls reconcile_budget_kill, promotes graph node in-place
        +AUTOMIL_FOLD_COUNT injection in _build_subprocess_env
        +self._tick_cells() call in tick() between _check_running() and pending block
  created:
    - path: tests/test_tick_cells.py
      changes: "8 daemon-level integration tests covering all state transitions + cap-detection"

decisions:
  - "_tick_cells uses self.automil_dir / 'cells' directly rather than _cells_dir() which walks CWD — avoids test-env failures where CWD is not the project root"
  - "Chose promote-in-place dict mutation for cap-killed nodes (not add_executed) per PINNED API: running node already exists in graph, add_executed would double-count"
  - "self.backend = None attribute added for test injection; production path falls back to _kill_experiment()"
  - "_NodeHandle added as minimal frozen dataclass satisfying .node_id access needed by backend.cancel(handle, ...)"

metrics:
  duration: "~20 minutes"
  completed_date: "2026-05-05T06:49:41Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
  files_created: 1
---

# Phase 04 Plan 07: Daemon Cap Integration Summary

**One-liner:** Wired the cap state machine into the orchestrator daemon — `_tick_cells()` drives ACTIVE→REFUSING_NEW→TERMINATING→FINALIZED transitions, annotates `cancel_reason='cap'` before SIGTERM dispatch, and `_handle_completion` routes cap-killed experiments through `reconcile_budget_kill` for partial-fold recovery.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Add _tick_cells + _running_in_cell + cap-detection in _handle_completion | c6d2d80 | src/automil/backends/_orchestrator_daemon.py |
| 2 | Write tests/test_tick_cells.py (8 daemon-level integration tests) | 0a8ac33 | tests/test_tick_cells.py |

## What Was Built

### Task 1 — Daemon modifications

Four additive insertions to `_orchestrator_daemon.py`:

1. **`_NodeHandle` dataclass** — minimal frozen `@dataclass(frozen=True)` with `.node_id`. Satisfies `handle.node_id` access pattern needed by `backend.cancel(handle, signal=SIGTERM)` without depending on the full `backends.base.JobHandle` (which carries fields the daemon doesn't track).

2. **`self.backend = None`** — injectable Backend attribute. Production code falls back to `_kill_experiment()` (direct `os.killpg`). Tests inject a `MagicMock` to count cancel calls and inspect ordering.

3. **`_running_in_cell(cell_id)`** — filters `self.running` dict by `spec["metadata"]["cell_id"]`. Returns `_NodeHandle` list. Legacy nodes without `cell_id` are immune (D-117 backward compat).

4. **`_tick_cells()`** — iterates `self.automil_dir / "cells"` directly (not via `_cells_dir()` which calls `_find_automil_dir()` from CWD). For each cell:
   - Calls `next_status(cell, now, len(running))`
   - Skips if status unchanged
   - On TERMINATING: writes `cancel_reason='cap'` to `running/<node>.json` BEFORE `backend.cancel(handle, SIGTERM)` (Pitfall 4 ordering)
   - Persists new status via `write_cell(replace(cell, status=new_status), cells_dir)`

5. **`self._tick_cells()` in `tick()`** — inserted between `_check_running()` and the pending-scheduling block (step 1.5, D-114).

6. **Cap-detection block in `_handle_completion`** — after exp is popped from `self.running`, reads `cancel_reason` from `running/<node>.json` (or archive fallback). If `'cap'`:
   - Calls `reconcile_budget_kill(node_id, archive_dir, graph, expected_folds)`
   - `partial_folds >= 1`: promotes graph node in-place (`type=executed`, `status=keep`, real composite, `metadata.budget_killed=True`), calls `_reevaluate_descendants`, `graph.save()`
   - `partial_folds == 0`: calls `graph.mark_failed(status='crash')`, tags `metadata.budget_killed=True`, `graph.save()`
   - Returns early — does NOT fall through to standard completion path

7. **`_read_fold_count_for_node(node_id)`** — reads `AUTOMIL_FOLD_COUNT` from spec env, falls back to `config.yaml: training.fold_count`, then hard 5.

8. **`AUTOMIL_FOLD_COUNT` injection** in `_build_subprocess_env` — reads `training.fold_count` from config.yaml at launch time (D-120).

### Task 2 — Test file

8 integration tests in `tests/test_tick_cells.py`:

1. `test_tick_cells_active_to_refusing_new` — ACTIVE cell with <buffer remaining → refusing-new; no cancel
2. `test_tick_cells_terminating_fires_cancel_with_cap_reason` — REFUSING_NEW → TERMINATING; Mock side_effect captures `cancel_reason` at call time, asserts it equals `'cap'` (Pitfall 4 order verification)
3. `test_tick_cells_finalized_when_running_empty` — TERMINATING → FINALIZED
4. `test_tick_cells_idempotent_on_finalized` — FINALIZED stays FINALIZED after two calls
5. `test_running_in_cell_filters_by_metadata_cell_id` — 4 experiments, 2 matching cell_id `'abc'`, 1 different, 1 legacy (no cell_id)
6. `test_handle_completion_with_cap_cancel_reason_calls_reconcile` — 2-of-5 fold files → result.json `status=partial`, graph node `type=executed`, `metadata.budget_killed=True`
7. `test_handle_completion_with_cap_cancel_zero_folds_marks_crash` — no fold files → `status=crashed`, graph node `status=crash`, `budget_killed=True`
8. `test_automil_fold_count_injected_into_subprocess_env` — config `fold_count: 7` → `env["AUTOMIL_FOLD_COUNT"] == "7"`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _tick_cells used _cells_dir() which walks CWD**
- **Found during:** Task 2 test run (Test 1 failed: status stayed 'active')
- **Issue:** `_cells_dir()` calls `_find_automil_dir()` which walks up from `os.getcwd()`. In test environments the CWD is the repo root, not `tmp_path`, so it found no cells.
- **Fix:** Changed `_tick_cells` to use `self.automil_dir / "cells"` directly (the daemon knows its own automil_dir). Also reads cells via `read_cell()` in a local loop rather than `list_cells()` which also calls `_cells_dir()`.
- **Files modified:** src/automil/backends/_orchestrator_daemon.py
- **Commit:** c6d2d80 (amended in same commit before final test run)

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: race-window | src/automil/backends/_orchestrator_daemon.py | cancel_reason annotation is NOT atomic with backend.cancel(); a crash between the two leaves `running/<node>.json` annotated but no cancel sent. The archive fallback path in `_handle_completion` mitigates this: if the experiment exits on its own after annotation but before cancel, reconcile still fires. |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| src/automil/backends/_orchestrator_daemon.py exists | FOUND |
| tests/test_tick_cells.py exists | FOUND |
| .planning/.../04-07-SUMMARY.md exists | FOUND |
| commit c6d2d80 exists | FOUND |
| commit 0a8ac33 exists | FOUND |
| 623 tests pass (8 new, 9 skipped, 0 failures) | PASSED |
