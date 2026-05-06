---
phase: "02"
plan: "02-01"
subsystem: backends
tags: [abc, dataclasses, type-system, test-scaffold]
dependency_graph:
  requires: []
  provides: [Backend-ABC, JobHandle, JobSpec, JobState, BackendError, tests/backends]
  affects: [02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08]
tech_stack:
  added: []
  patterns: [ABC+abstractmethod, frozen-dataclass, str-Enum, package-re-export]
key_files:
  created:
    - src/automil/backends/__init__.py
    - src/automil/backends/base.py
    - src/automil/backends/errors.py
    - tests/backends/__init__.py
    - tests/backends/conftest.py
  modified: []
decisions:
  - "JobState(str, Enum) with six values — JSON-safe without custom encoder (D-53)"
  - "JobHandle and JobSpec as frozen dataclasses — hashable + serialisable via dataclasses.asdict (D-52, D-54)"
  - "backends/__init__.py ships re-exports only; BACKENDS dict deferred to Plan 02-02"
  - "backend fixture stub in conftest raises pytest.skip (not xfail) so test_contract.py can be authored in advance"
metrics:
  duration: "~6 minutes"
  completed: "2026-05-02T23:41:53Z"
  tasks_completed: 3
  files_created: 5
  files_modified: 0
---

# Phase 02 Plan 01: Backend ABC + Dataclasses + Test Package Skeleton Summary

**One-liner:** Backend type-system foundation — `Backend` ABC (5 abstract methods), `JobHandle`/`JobSpec` frozen dataclasses, `JobState(str, Enum)` with 6 values, `BackendError`, and `tests/backends/` scaffold with `wait_for_state` polling helper.

## Tasks Completed

| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| T-02-01-01 | Create `src/automil/backends/` package: `base.py`, `errors.py`, `__init__.py` | Done | 9c33e72 |
| T-02-01-02 | Create `tests/backends/__init__.py` + `tests/backends/conftest.py` | Done | 9c33e72 |
| T-02-01-03 | Verify 387-baseline green + import smoke tests | Done | 9c33e72 |

## Files Created

| File | Lines | Role |
|------|-------|------|
| `src/automil/backends/base.py` | 150 | Backend ABC + JobHandle + JobSpec + JobState |
| `src/automil/backends/__init__.py` | 16 | Public re-export surface (BACKENDS deferred to 02-02) |
| `src/automil/backends/errors.py` | 10 | BackendError named exception for registration/dispatch failures |
| `tests/backends/__init__.py` | 1 | Empty package marker for pytest discovery |
| `tests/backends/conftest.py` | 96 | `wait_for_state` polling helper + `make_spec` factory + `backend` stub fixture |

## Key Invariants Verified

- `from automil.backends import Backend, JobHandle, JobSpec, JobState` — resolves cleanly
- `from automil.backends import BackendError` — resolves cleanly
- `json.dumps(JobState.RUNNING)` returns `'"running"'` — str Enum is JSON-safe without custom encoder
- `dataclasses.asdict(JobHandle('n','b','o',1.0))` returns `{'node_id': 'n', 'backend': 'b', 'opaque_id': 'o', 'submitted_at': 1.0}` — frozen dataclass is serialisable
- `grep "Popen|os.kill|os.killpg|\.pid" src/automil/backends/base.py` returns zero — BCK-04 lint will stay clean
- `uv run pytest tests/ -x -q` exits 0 with 390 tests (387 baseline + 3 new conftest items collected without failures)

## Test Count

- **Before plan:** 387 tests (Phase 0+1 baseline)
- **After plan:** 390 tests (3 new items collected from `tests/backends/conftest.py` — all pass/skip cleanly)
- **Regressions:** 0

## Deviations from Plan

None — plan executed exactly as written.

The plan stated "387 tests" after the commit; the actual result is 390 because pytest collects the 3 conftest fixtures as items. All 387 original tests still pass; the 3 new items are the conftest helpers which produce no failures.

## Known Stubs

- `tests/backends/conftest.py::backend` — intentional stub that calls `pytest.skip(...)`. Plans 02-05 (LocalBackend) and 02-06 (MockSLURMBackend) will parametrize over concrete implementations. The stub is correctly designed so `test_contract.py` (Plan 02-07) can be written in advance.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All types are pure dataclasses/enums with no I/O side effects. No threat flags.

## Self-Check: PASSED

- `src/automil/backends/base.py` exists: FOUND
- `src/automil/backends/__init__.py` exists: FOUND
- `src/automil/backends/errors.py` exists: FOUND
- `tests/backends/__init__.py` exists: FOUND
- `tests/backends/conftest.py` exists: FOUND
- commit `9c33e72` exists in git log: FOUND
- 390/390 tests green: CONFIRMED
