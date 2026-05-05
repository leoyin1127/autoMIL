---
phase: "04-6h-per-cell-hard-cap-cell-concept-formalisation"
plan: "03"
subsystem: "cells/cap"
tags: [cap, state-machine, pure-function, tdd, CAP-02]
requirements: [CAP-02]

dependency_graph:
  requires:
    - "04-01: Cell frozen dataclass + CellStatus str-Enum (state.py)"
    - "04-02: reconcile.py stub (aggregate_folds importable)"
  provides:
    - "automil.cells.cap:next_status — pure two-tier cap state machine"
    - "automil.cells.next_status — re-exported via cells/__init__.py"
  affects:
    - "04-08: daemon tick _tick_cells() calls next_status"
    - "04-05: registry (is_refusing_new uses CellStatus comparison)"

tech_stack:
  added: []
  patterns:
    - "Pure function with explicit clock injection (D-113): no time.time() inside, now_epoch param"
    - "TDD RED→GREEN gate: commit test first (ImportError), then implement to pass"
    - "Stdlib-only cells/ module — no pydantic, no attrs, no autobench"

key_files:
  created:
    - "src/automil/cells/cap.py"
    - "tests/cells/test_cap_state_machine.py"
  modified:
    - "src/automil/cells/__init__.py"
  also_brought_in_from_main:
    - "src/automil/cells/__init__.py (04-01 version)"
    - "src/automil/cells/state.py (04-01)"
    - "src/automil/cells/reconcile.py (04-02 stub)"
    - "src/automil/runtime_helpers.py (04-02)"
    - "tests/cells/__init__.py, conftest.py, test_runtime_helpers.py"

decisions:
  - "D-113: next_status is a pure function; now_epoch injected by caller (time.time() at daemon tick site, not inside cap.py)"
  - "Worktree was behind main; cells package files brought in via git checkout main -- <files> before TDD cycle. This is the expected parallel-execution pattern when multiple wave-2 plans land simultaneously."

metrics:
  duration_minutes: 12
  completed_date: "2026-05-05"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 04 Plan 03: Cap State Machine — `next_status()` Pure Function

**One-liner:** Pure two-tier cap state machine (`ACTIVE→REFUSING_NEW→TERMINATING→FINALIZED`) with explicit clock injection via `now_epoch` parameter; 18 exhaustive parametrised tests cover all transitions and idempotency.

## What Was Built

`src/automil/cells/cap.py` implements `next_status(cell, now_epoch, running_count) -> CellStatus` per D-113 verbatim. The function is a pure predicate — no imports of `time`, no I/O, no global state mutation. The clock is injected by the caller (`time.time()` at the daemon tick site in Plan 04-08's `_tick_cells()`), making the function unit-testable without monkeypatching.

Transition logic (four exhaustive branches):
1. `ACTIVE` → if `remaining <= safety_buffer_seconds`: `REFUSING_NEW`; else `ACTIVE`
2. `REFUSING_NEW` → if `remaining <= 0`: `TERMINATING`; else `REFUSING_NEW`
3. `TERMINATING` → if `running_count == 0`: `FINALIZED`; else `TERMINATING`
4. Fallthrough: `return cell.status` — `FINALIZED` is terminal

`cells/__init__.py` extended with `from automil.cells.cap import next_status` and `"next_status"` added to `__all__` alphabetically between `make_cell_id` and `read_cell`.

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED  | 8ec8208 | `ModuleNotFoundError: No module named 'automil.cells.cap'` confirmed |
| GREEN | ef29f6b | 18/18 tests pass; 409 total suite green |
| REFACTOR | — | Not needed; implementation is already minimal |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 (RED) | 8ec8208 | test(04-03): add failing tests for cap state machine |
| 2 (GREEN) | ef29f6b | feat(04-03): implement next_status() + re-export |

## Test Coverage

18 tests in `tests/cells/test_cap_state_machine.py`:

| Test | Transition Exercised |
|------|---------------------|
| `test_active_stays_active_when_remaining_above_safety_buffer` | ACTIVE→ACTIVE |
| `test_active_transitions_to_refusing_new_at_safety_buffer_boundary` | ACTIVE→REFUSING_NEW (boundary `remaining == buffer`) |
| `test_active_transitions_to_refusing_new_when_remaining_below_safety_buffer` | ACTIVE→REFUSING_NEW (below) |
| `test_active_with_running_count_does_not_affect_active_status` | running_count ignored in ACTIVE |
| `test_refusing_new_stays_refusing_new_when_remaining_positive` | REFUSING_NEW→REFUSING_NEW |
| `test_refusing_new_transitions_to_terminating_at_zero_remaining` | REFUSING_NEW→TERMINATING (boundary `remaining == 0`) |
| `test_refusing_new_transitions_to_terminating_when_remaining_negative` | REFUSING_NEW→TERMINATING (negative) |
| `test_terminating_stays_terminating_when_running_count_nonzero` | TERMINATING→TERMINATING |
| `test_terminating_transitions_to_finalized_when_running_count_zero` | TERMINATING→FINALIZED |
| `test_finalized_is_terminal[consumed×running_count]` × 9 | FINALIZED idempotency (parametrised) |

## Deviations from Plan

### Context: Worktree behind main

This worktree was created from a branch point before Phase 04 work landed on main. The cells package (`src/automil/cells/`, `tests/cells/`) existed on `main` but was absent in the worktree working tree.

**Fix applied (Rule 3 — blocking issue):** Used `git checkout main -- <files>` to bring the prerequisite cells files into the worktree before starting the TDD cycle. No architectural changes; files are additive only and identical to what main has. The Phase 04-01 and 04-02 files are dependencies for this plan (per `depends_on: ["04-01"]` in the plan frontmatter).

No other deviations — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes. `cap.py` is a pure function with no I/O surface. No threat flags.

## Self-Check: PASSED

- [x] `src/automil/cells/cap.py` exists and exports `next_status`
- [x] `tests/cells/test_cap_state_machine.py` exists with 18 tests (10 non-parametrised + 9 parametrised)
- [x] `src/automil/cells/__init__.py` exports `next_status` via `__all__`
- [x] `grep -c "import time" src/automil/cells/cap.py` == 0
- [x] `uv run pytest tests/cells/test_cap_state_machine.py -x` → 18 passed
- [x] `uv run pytest tests/ -x` → 409 passed (baseline 391 preserved)
- [x] BCK-04 lint: zero `os.getpid`/`os.kill`/`Popen`/`.pid` in `src/automil/cells/`
- [x] `from automil.cells import next_status` imports successfully
- [x] Commits 8ec8208 (RED) and ef29f6b (GREEN) exist in git log
