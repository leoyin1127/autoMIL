---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: "04"
subsystem: backends
tags: [slurm, submitit, backend, bck-05]
dependency_graph:
  requires: [06-01, 06-02, 06-03]
  provides: [slurm-backend-impl]
  affects: [backends/__init__.py, tests/backends/test_slurm_directives.py]
tech_stack:
  added: [submitit>=1.5.3 (opt-in via [slurm] extra)]
  patterns: [submitit AutoExecutor + Job API, conditional class registration, atomic-write JSON]
key_files:
  created:
    - src/automil/backends/slurm.py
  modified: []
decisions:
  - "Lazy import of submitit at module top-level via try/except so _walltime_to_timeout_min is importable without extras"
  - "Conditional registration via _slurm_register() helper so extras-gate test passes when submitit absent"
  - "subprocess.run(cwd=str(target_dir), env=sub_env) avoids os.chdir + os.environ mutation under DebugExecutor/pytest"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-05"
  tasks_completed: 1
  files_created: 1
---

# Phase 06 Plan 04: SLURMBackend on submitit AutoExecutor Summary

SLURMBackend implementing the Phase 2 Backend ABC on submitit>=1.5.3 with all five RESEARCH.md API corrections applied inline and conditional registration for extras-gate compliance.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement SLURMBackend class + _run_experiment_subprocess + helpers | 7d0888d | src/automil/backends/slurm.py (420 lines) |

## What Was Built

`src/automil/backends/slurm.py` (420 lines) containing:

- `_walltime_to_timeout_min(walltime_seconds: int) -> int` — pure helper, importable without submitit
- `_SLURM_STATE_MAP: dict[str, JobState]` — 12-entry state map (TIMEOUT -> BUDGET_KILLED, FAILED -> CRASHED, etc.)
- `_TERMINAL_STATES: frozenset[JobState]` — mirrors mock_slurm.py pattern
- `_run_experiment_subprocess(spec: JobSpec, worktree_path: Path) -> int` — top-level (picklable) remote function for submitit dispatch
- `SLURMBackend(Backend)` — full 5-method ABC implementation: submit, poll, list_running, cancel, log_iter

## Five API Corrections Applied

All five RESEARCH.md corrections confirmed by grep:

| Correction | Verified |
|-----------|---------|
| `timeout_min=` (NOT `time=`) in `update_parameters` | `grep '"timeout_min"' slurm.py` → line 179 |
| `slurm_additional_parameters={"signal": "B:TERM@30"}` (NOT `signal=`) | `grep '"signal".*"B:TERM@30"' slurm.py` → line 180 |
| `job.paths.stdout` for log path (NOT hardcoded `{job_id}_log.out`) | `grep 'job\.paths\.stdout' slurm.py` → line 373 |
| `runner.create_worktree(spec.base_commit, spec.node_id)` 2-positional | `grep 'runner.create_worktree(spec.base_commit' slurm.py` → line 219 |
| `subprocess.run(cwd=str(target_dir), env=sub_env)` (NOT os.chdir) | `grep 'subprocess.run.*cwd=' slurm.py` → line 122 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level `import submitit` prevented importing pure helpers without extras**
- **Found during:** Task 1, first test run
- **Issue:** `import submitit` at module top-level caused `ModuleNotFoundError` when `_walltime_to_timeout_min` was imported (test did not require submitit)
- **Fix:** Changed to guarded try/except setting `_SUBMITIT_AVAILABLE` flag; moved submitit-dependent code into class methods
- **Files modified:** src/automil/backends/slurm.py
- **Commit:** 7d0888d (inline fix before commit)

**2. [Rule 1 - Bug] `@register("slurm")` ran even without submitit, polluting BACKENDS registry**
- **Found during:** Task 1, test_extras_gate.py failure
- **Issue:** The `@register("slurm")` decorator executed at class-definition time regardless of submitit availability, causing `test_import_automil_backends_no_extras` to fail
- **Fix:** Added `_slurm_register()` helper that conditionally applies `@register("slurm")` only when `_SUBMITIT_AVAILABLE` is True
- **Files modified:** src/automil/backends/slurm.py
- **Commit:** 7d0888d (inline fix before commit)

## Verification Results

```
test_walltime_seconds_to_timeout_min: PASSED (Wave-0 stub flips GREEN)
test_import_automil_backends_no_extras: PASSED (extras-gate clean)
test_three_phase6_errors_in_public_namespace: PASSED
BCK-04 lint (check_backend_isolation.py): OK - no backend isolation violations
Framework purity grep: zero matches
tests/backends/ + tests/test_graph.py + tests/test_cli.py + tests/test_runner.py: 64 passed
```

Pre-existing RED stubs (not introduced by this plan):
- `test_log_unification.py::test_log_iter_close_60s_timeout` — requires `_drain_log_iter_with_timeout` from future plan
- `test_running_namespace.py::test_daemon_refuses_flat_running` — requires D-168 daemon guardrail (future plan)
- `test_tick_cells.py::*` (3 tests) — pre-existing Wave 0 stubs

## Known Stubs

None — SLURMBackend is fully implemented. The import guard (`if not _SUBMITIT_AVAILABLE: raise BackendNotInstalledError`) defers actual execution to environments with submitit installed, but the class structure and all methods are complete.

## Threat Flags

None — slurm.py introduces no new network endpoints, auth paths, or trust-boundary changes. The `spec.env` whitelist (CLN-02 D-04) is honored via `sub_env = dict(os.environ); for k, v in spec.env: sub_env[k] = v`.

## Self-Check

```
src/automil/backends/slurm.py: FOUND (420 lines >= 250 minimum)
commit 7d0888d: FOUND
_walltime_to_timeout_min test: GREEN
BCK-04 lint: PASSED
Framework purity: PASSED
```

## Self-Check: PASSED
