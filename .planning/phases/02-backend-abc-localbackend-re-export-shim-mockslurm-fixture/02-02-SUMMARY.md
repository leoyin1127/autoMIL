---
plan: 02-02
phase: "02"
subsystem: backends
tags: [registry, decorator, backend, BCK-01, D-68, D-69]
dependency_graph:
  requires: ["02-01"]
  provides: ["BACKENDS registry", "register decorator", "_clear_backends"]
  affects: ["02-05", "02-06", "02-08"]
tech_stack:
  added: []
  patterns: ["module-level registry dict", "@register class decorator", "registry isolation fixture"]
key_files:
  modified:
    - src/automil/backends/__init__.py
  created:
    - tests/backends/test_registry.py
decisions:
  - "BACKENDS dict and register() live in backends/__init__.py (not a separate _state.py) — one kind, string keys, no circular import risk"
  - "mock_slurm NOT auto-imported per D-69 — test fixture must not leak into production config"
  - "TODO placeholder comment for Plan-02-05 local import per plan directive"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-02"
  tasks_completed: 2
  files_changed: 2
---

# Phase 02 Plan 02: BACKENDS Registry Singleton + register Decorator Summary

## One-liner

BACKENDS registry dict + `@register(name)` class decorator + `_clear_backends()` isolation helper in `backends/__init__.py`, backed by 4 tests.

## What Was Built

### T-02-02-01: Extend `src/automil/backends/__init__.py`

**Before (16 lines):** Plan 02-01 surface only — imports + 5-name `__all__`.

**After (82 lines):** Added on top of the existing imports:
- `BACKENDS: dict[str, type[Backend]] = {}` module-level singleton
- `register(name: str)` function returning a class decorator that:
  - validates `issubclass(cls, Backend)` → raises `BackendError` if not
  - checks name collision → raises `BackendError("Backend {name!r} is already registered as {BACKENDS[name].__name__}. Duplicate registration rejected.")` on duplicate
  - inserts into BACKENDS, calls `logger.info("Registered backend %r -> %s", name, cls.__name__)`
  - returns the class unchanged (identity preserved)
- `_clear_backends() -> None` test-only helper that calls `BACKENDS.clear()`
- TODO comment placeholder for Plan-02-05 local import
- Updated `__all__` to 8 names: the original 5 plus `BACKENDS`, `register`, `_clear_backends`

### T-02-02-02: Tests (`tests/backends/test_registry.py`)

4 tests added:
- `test_register_backend_happy_path` — registers a concrete Backend subclass, asserts BACKENDS["test_backend"] is the class, verifies decorator returns class unchanged
- `test_register_non_backend_raises` — confirms BackendError raised on non-Backend class, registry stays clean
- `test_register_duplicate_raises` — confirms BackendError raised on duplicate name, original registration preserved
- `test_clear_backends_helper` — registers 2 backends, calls _clear_backends(), asserts BACKENDS is empty

`autouse=True` `_isolated_registry` fixture calls `_clear_backends()` before and after every test (PATTERNS.md §11 isolation pattern).

### T-02-02-03: Verification

- `uv run pytest tests/ -q` → **394 passed** (390 baseline + 4 new)
- `uv run python -c "from automil.backends import BACKENDS, register, BackendError; print('registry surface OK')"` → `registry surface OK`
- Inline registration smoke: `@register('test_backend')` on a concrete Backend subclass → `'test_backend' in BACKENDS` asserts True

## Deviations from Plan

### Incidental Inclusion of Plan 02-04 Work

Plan 02-04 (orchestrator rename) was running in parallel in this same worktree. When I ran `git add src/automil/backends/__init__.py tests/backends/test_registry.py`, the rename of `src/automil/orchestrator.py → src/automil/backends/_orchestrator_daemon.py` was already staged (Plan 02-04's work). This appeared in my commit as `R100 src/automil/orchestrator.py -> src/automil/backends/_orchestrator_daemon.py`.

The rename + compat.py update are Plan 02-04's scope, not 02-02's. However, since the rename was already staged and Plan 02-04's test updates (test_compat.py) were also already applied, the full test suite remained green at 394. No correctness impact — this is a commit attribution issue only, not a behavioural deviation.

The `src/automil/orchestrator.py` shim file appears as untracked after the rename (Plan 02-04 created a new `orchestrator.py` shim that points to `_orchestrator_daemon.py`). This will be committed by Plan 02-04's own summary commit.

## Invariants Verified

- `mock_slurm` is NOT imported anywhere in `backends/__init__.py` — confirmed by inspection
- `BACKENDS` starts empty at module load (no auto-registration until Plan 02-05 adds local import)
- `register()` raises `BackendError` (not `TypeError`) on both error cases — tested
- `_clear_backends()` empties the dict completely — tested
- `from automil.backends import Backend, JobHandle, JobSpec, JobState, BackendError, BACKENDS, register, _clear_backends` all resolve

## Test Count Delta

390 → 394 (+4 new tests in tests/backends/test_registry.py)

## Self-Check

- `src/automil/backends/__init__.py` exists: FOUND
- `tests/backends/test_registry.py` exists: FOUND
- Commit 4f667c9 exists: FOUND
- 394 tests pass: CONFIRMED

## Self-Check: PASSED
