---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: "05"
subsystem: cells
tags: [registry, get-or-create, idempotent, restart-safe, TDD, CAP-01, CAP-05]

dependency_graph:
  requires: [04-04]
  provides: [automil.cells.registry, get_or_create_cell, get_cell, list_cells, is_refusing_new]
  affects: [src/automil/cells/__init__.py, src/automil/cells/registry.py]

tech_stack:
  added: []
  patterns:
    - "Read-before-write idempotency: path.exists() check gates cell creation"
    - "D-134 first-submit-wins: budget override silently ignored with INFO log on existing cell"
    - "Pure function is_refusing_new: no I/O, testable in isolation"
    - "_cells_dir() helper: resolves _find_automil_dir() / 'cells' — single location"

key_files:
  created:
    - src/automil/cells/registry.py
    - tests/cells/test_cell_registry.py
  modified:
    - src/automil/cells/__init__.py

decisions:
  - "D-116: get_or_create_cell is the single ingress for cell creation; started_at=time.time() is in exactly one place (registry.py:get_or_create_cell creation branch)"
  - "D-134: first-submit-wins semantics for budget_seconds/safety_buffer_seconds — override only on cell creation, INFO-logged when ignored"
  - "D-111: no accumulator pattern; consumed_seconds computed as time.time() - started_at, never stored"
  - "_find_automil_dir() monkeypatched in tests — tests are filesystem-isolated under tmp_path"

metrics:
  duration_minutes: 8
  completed_date: "2026-05-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
  tests_added: 14
  tests_green: 14
---

# Phase 04 Plan 05: Cell Registry (CRUD + Idempotency) Summary

**One-liner:** Persistence-backed cell registry with read-before-write idempotency and D-134 first-submit-wins budget semantics, tested via TDD RED/GREEN cycle.

## What Was Built

`src/automil/cells/registry.py` — the single ingress module for cell lifecycle, exposing four public functions:

- `get_or_create_cell(dataset, encoder, parent_id, budget_seconds, safety_buffer_seconds) -> Cell` — lazy + idempotent cell creation. If `automil/cells/<cell_id>.json` exists, returns it unchanged (D-134: budget overrides logged at INFO and discarded). If not, creates a fresh `Cell` with `started_at=time.time()` and `status=ACTIVE`, atomically writes it via `write_cell()`, and returns it.
- `get_cell(cell_id) -> Cell | None` — direct lookup by id; returns None for missing files; logs WARNING on parse failure.
- `list_cells() -> list[Cell]` — sorted iteration over all `*.json` files under `automil/cells/`; skips malformed files with WARNING (T-04-14 DoS defence).
- `is_refusing_new(cell) -> bool` — pure predicate: True iff status in `{REFUSING_NEW, TERMINATING, FINALIZED}`.

`src/automil/cells/__init__.py` extended with additive imports from `registry` — four new names added to the public surface and `__all__`.

## TDD Gate Compliance

| Phase | Commit | Description |
|-------|--------|-------------|
| RED   | c429ec9 | 11 failing tests — `ModuleNotFoundError: No module named 'automil.cells.registry'` |
| GREEN | 1424033 | 14 passing (11 named + 4 parametrized) |

RED gate commit (`test(04-05)`) precedes GREEN gate commit (`feat(04-05)`) — gates satisfied.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| c429ec9 | test | RED: 11 failing tests for cells.registry |
| 1424033 | feat | GREEN: registry.py + __init__.py re-export |

## Deviations from Plan

**Merge prerequisite:** The worktree branch was created before Phase 04 cells/ package existed. A `git merge main --no-edit` was performed to bring in the phase 04 prerequisite commits (04-01 through 04-04) before implementing 04-05. This is expected for parallel executor worktrees spawned from an older branch. No plan-directed task was skipped.

All other deviations: None — plan executed exactly as written.

## Success Criteria Verification

- [x] `get_or_create_cell` is idempotent and ignores budget overrides on existing cells (test 3 + test 2)
- [x] `started_at` is set once at creation and persists across reloads — CAP-05 (test 10)
- [x] `is_refusing_new` covers REFUSING_NEW, TERMINATING, FINALIZED (test 9 parametrized x4)
- [x] Module is framework-only — `grep -E "autobench|AUTOBENCH_|benchmarks/" src/automil/cells/registry.py` returns 0
- [x] BCK-04: `grep -rE "os.getpid|os.kill|Popen|\.pid" src/automil/cells/` returns 0
- [x] `started_at=time.time()` appears exactly once in registry.py (single ingress invariant)
- [x] `cells/__init__.py` additively re-exports get_or_create_cell, get_cell, list_cells, is_refusing_new
- [x] Full cells test suite: 45 passed; full suite (excl. autobench): 603 passed, 9 skipped

## Threat Mitigations Verified

| Threat ID | Test | Status |
|-----------|------|--------|
| T-04-12: Reset of started_at by re-creating cell | test_get_or_create_returns_existing_cell_on_second_call | Mitigated |
| T-04-13: Sandbagging via budget_seconds extension | test_get_or_create_ignores_budget_override_on_existing_cell | Mitigated |
| T-04-14: Malformed cell file blocks list_cells | test_list_cells_skips_malformed_files | Mitigated |

## Known Stubs

None — all functions are fully implemented with real on-disk persistence.

## Self-Check: PASSED

Files verified:
- `src/automil/cells/registry.py` — exists, 120 lines
- `tests/cells/test_cell_registry.py` — exists, 204 lines
- `src/automil/cells/__init__.py` — modified with registry exports

Commits verified:
- c429ec9 — present in git log
- 1424033 — present in git log
