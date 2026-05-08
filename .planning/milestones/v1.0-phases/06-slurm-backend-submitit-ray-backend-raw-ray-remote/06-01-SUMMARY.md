---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 01
subsystem: test-infrastructure
tags: [nyquist, wave-0, scaffolding, BCK-05, BCK-06]
dependency_graph:
  requires: []
  provides:
    - tests/backends/conftest.py#backend-fixture-4-params
    - tests/backends/test_slurm_directives.py
    - tests/backends/test_running_namespace.py
    - tests/backends/test_log_unification.py
    - tests/backends/test_node_0176_smoke.py
    - tests/backends/test_contract_real_slurm.py
    - tests/backends/test_contract_real_ray.py
    - pyproject.toml#pytest-markers
  affects:
    - tests/backends/test_contract.py (parametrisation now includes slurm/ray params from conftest)
tech_stack:
  added: []
  patterns:
    - pytest.importorskip for optional extras (submitit, ray)
    - explicit 4-branch if/elif/elif/else dispatch in backend fixture
    - pytestmark = pytest.mark.requires_slurm/requires_ray for real-cluster gating
key_files:
  created:
    - tests/backends/test_slurm_directives.py
    - tests/backends/test_running_namespace.py
    - tests/backends/test_log_unification.py
    - tests/backends/test_node_0176_smoke.py
    - tests/backends/test_contract_real_slurm.py
    - tests/backends/test_contract_real_ray.py
  modified:
    - tests/backends/conftest.py
    - pyproject.toml
decisions:
  - conftest 4-branch chain: if/elif/elif/else (not if/elif/else) ensures ray never falls through to MockSLURMBackend
  - Ray init: ray.init(ignore_reinit_error=True, log_to_driver=False) -- NOT local_mode=True (deprecated Ray 2.55+)
  - Log unification slurm/ray tests: pytest.importorskip at function body (not module level) for clean collection
  - test_archive_run_log_local: pytest.skip with explicit message (requires live daemon; deferred to Wave 4 plan 06-07)
metrics:
  duration: ~6 minutes
  completed: 2026-05-06T18:09:57Z
  tasks_completed: 3
  files_modified: 8
---

# Phase 06 Plan 01: Wave 0 Nyquist Stub Scaffolding Summary

Wave 0 Nyquist scaffolding: 6 new test files + conftest extension + pyproject.toml marker registration. All 41 new tests collect cleanly; 29 fail in RED state (implementations land in plans 06-02..06-09); 12 skip cleanly because submitit/ray extras are absent.

## What Was Built

### Task 1: pytest markers + conftest fixture extension

**pyproject.toml:** Added `markers = [...]` block to `[tool.pytest.ini_options]` registering `requires_slurm` (nightly SLURM cluster) and `requires_ray` (nightly Ray cluster) markers. No `PytestUnknownMarkWarning` emitted.

**tests/backends/conftest.py:** Extended `backend` fixture from `params=["local", "mock_slurm"]` to `params=["local", "mock_slurm", "slurm", "ray"]`. Explicit 4-branch if/elif/elif/else chain:
- `if "local"` → `LocalBackend(project_root, automil_dir)` (unchanged)
- `elif "mock_slurm"` → `MockSLURMBackend(poll_lag=0.05)` (formerly the `else` branch)
- `elif "slurm"` → `pytest.importorskip("submitit")` + `SLURMBackend(debug_in_process=True)`
- `else: # "ray"` → `pytest.importorskip("ray")` + `ray.init(ignore_reinit_error=True, log_to_driver=False)` + `RayBackend` + teardown `ray.shutdown()` if `_we_started_ray`

W-9 constraint verified: `grep -c "elif request.param ==" = 2`, `grep -c 'else:  # request.param == "ray"' = 1`.

### Task 2: 4 backend stub files

**test_slurm_directives.py** (3 tests):
- `test_check_rejects_todo`: asserts `SlurmDirectivesIncompleteError` on `TODO_FILL_IN` partition sentinel
- `test_check_accepts_complete`: validator returns None on complete directives
- `test_walltime_seconds_to_timeout_min`: asserts `_walltime_to_timeout_min` helper (0→1, 30→1, 60→1, 120→2, 21600→360)

**test_running_namespace.py** (3 tests):
- `test_running_dir_per_backend`: daemon resolves `_backend_running_dir(name)` per backend
- `test_daemon_refuses_flat_running`: `SystemExit("BREAKING CHANGE")` on flat `running/*.json`
- `test_namespace_isolation`: `LocalBackend.list_running()` must not see `running/slurm/*.json`

**test_log_unification.py** (4 tests):
- `test_archive_run_log_local`: `pytest.skip` (requires live daemon; deferred to Wave 4)
- `test_archive_run_log_slurm`: `pytest.importorskip("submitit")` guard; exercises drain
- `test_archive_run_log_ray`: `pytest.importorskip("ray")` guard; exercises drain
- `test_log_iter_close_60s_timeout`: imports `_drain_log_iter_with_timeout` from daemon

**test_node_0176_smoke.py** (1 parametrised over 3 backends = 3 test IDs):
- `test_node_0176_equivalent_composite_within_tolerance[local/slurm-debug/ray-local]`
- Imports `tests.backends._smoke_helpers.run_node_0176_smoke` (created in plan 06-09)
- Asserts composite within ±0.005 of `_LOCAL_BASELINE_COMPOSITE = 0.502`

### Task 3: 2 real-cluster contract stubs

**test_contract_real_slurm.py**: `pytestmark = pytest.mark.requires_slurm`; `real_slurm_backend` fixture guards via `sbatch`-on-PATH + `AUTOMIL_TEST_SLURM_PARTITION`/`AUTOMIL_TEST_SLURM_ACCOUNT` env vars. Single smoke test `test_real_slurm_submit_completes`.

**test_contract_real_ray.py**: `pytestmark = pytest.mark.requires_ray`; `real_ray_backend` fixture guards via `RAY_ADDRESS` env var. Single smoke test `test_real_ray_submit_completes`. No `ray.shutdown()` in teardown (operator owns real cluster per D-161).

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest tests/backends/ --collect-only -q` | 85 tests collected, no errors |
| `uv run pytest --markers \| grep requires_slurm\|requires_ray` | Both markers listed |
| `uv run pytest tests/ --collect-only \| tail -1` | 829 tests collected (788 → +41) |
| Phase 5 baseline (`-x -q --ignore` new stubs) | 779 passed, 37 skipped |
| `grep -r "autobench\|AUTOBENCH_\|benchmarks/" new test files` | Zero matches |
| Conftest chain: `grep -c "elif request.param ==" = 2` | PASS |
| Conftest chain: `grep -c 'else:  # request.param == "ray"' = 1` | PASS |
| `test_contract_real_slurm/ray` default run | 2 skipped (markers not selected) |

## RED State (Nyquist)

Tests that fail when run because implementations don't exist yet (correct per plan):
- All 3 `test_slurm_directives.py` tests → `ImportError: cannot import _validate_slurm_directives` (created in plan 06-03)
- All 3 `test_running_namespace.py` tests → `AttributeError: ExperimentOrchestrator has no _backend_running_dir` (plan 06-06)
- `test_archive_run_log_slurm`, `test_archive_run_log_ray` → `ImportError: automil.backends.slurm / .ray` (plans 06-04, 06-05)
- `test_log_iter_close_60s_timeout` → `ImportError: _drain_log_iter_with_timeout` (plan 06-07)
- All 3 `test_node_0176_smoke.py` tests → `ImportError: tests.backends._smoke_helpers` (plan 06-09)
- `test_archive_run_log_local` → SKIPPED (explicit `pytest.skip`, deferred to Wave 4)

## Extras Skip Behavior

With no `[slurm]` or `[ray]` extras installed:
- `backend[slurm]` and `backend[ray]` parametrisations: **SKIP** via `pytest.importorskip("submitit")` / `pytest.importorskip("ray")` — no collection error
- `test_archive_run_log_slurm`, `test_archive_run_log_ray`, `test_node_0176_smoke[slurm-debug]`, `test_node_0176_smoke[ray-local]`: **SKIP** via function-body `pytest.importorskip`

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — this plan creates no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. All new files are test scaffolding only.

## Known Stubs

All test stubs are intentional Nyquist scaffolding (RED state by design). Each maps to a specific implementation plan:

| Stub | File | Resolved By |
|------|------|-------------|
| `_validate_slurm_directives` | test_slurm_directives.py | plan 06-03 |
| `SlurmDirectivesIncompleteError` | test_slurm_directives.py | plan 06-02 |
| `_walltime_to_timeout_min` | test_slurm_directives.py | plan 06-04 |
| `ExperimentOrchestrator._backend_running_dir` | test_running_namespace.py | plan 06-06 |
| `automil.backends.slurm.SLURMBackend` | test_log_unification.py | plan 06-04 |
| `automil.backends.ray.RayBackend` | test_log_unification.py | plan 06-05 |
| `_atomic_write_lines` | test_log_unification.py | plan 06-07 |
| `_drain_log_iter_with_timeout` | test_log_unification.py | plan 06-07 |
| `tests.backends._smoke_helpers.run_node_0176_smoke` | test_node_0176_smoke.py | plan 06-09 |

## Self-Check: PASSED

Files exist:
- tests/backends/test_slurm_directives.py: FOUND
- tests/backends/test_running_namespace.py: FOUND
- tests/backends/test_log_unification.py: FOUND
- tests/backends/test_node_0176_smoke.py: FOUND
- tests/backends/test_contract_real_slurm.py: FOUND
- tests/backends/test_contract_real_ray.py: FOUND

Commits exist:
- 8d55b8e: test(phase-06): register pytest markers + extend backend fixture to 4 params
- fcce916: test(phase-06): add Wave 0 stubs for slurm_directives, running_namespace, log_unification, node_0176_smoke
- 83e4ff7: test(phase-06): add real-cluster contract stubs with requires_slurm/requires_ray markers
