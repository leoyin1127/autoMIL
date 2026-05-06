---
phase: "06"
plan: "05"
subsystem: backends
tags: [ray, backend, BCK-06, distributed, opt-in]
dependency_graph:
  requires: ["06-01", "06-02", "06-03"]
  provides: ["RayBackend", "_run_experiment_ray", "_was_cap_cancel"]
  affects: ["src/automil/backends/ray.py"]
tech_stack:
  added: ["ray>=2.55.1 (@ray.remote, ray.wait, ray.cancel, ray.is_initialized)"]
  patterns: ["hybrid-init", "force-cancel", "WorkerCrashedError-aware-poll", "atomic-write"]
key_files:
  created:
    - src/automil/backends/ray.py
  modified: []
decisions:
  - "RESEARCH.md OQ-2: ignore_reinit_error=True; local_mode is deprecated in Ray 2.55+"
  - "RESEARCH.md OQ-3: three separate except clauses in poll(): RayTaskError, WorkerCrashedError (force=True), TaskCancelledError (force=False)"
  - "RESEARCH.md OQ-4: worktree_path + log_path as explicit args to _run_experiment_ray, not JobSpec fields"
  - "W-4: subprocess.run(cwd=str(target_dir)) — NOT os.chdir; avoids Ray worker CWD mutation"
  - "B-1: runner.create_worktree(spec.base_commit, spec.node_id) + separate apply_overlay call"
  - "_we_started_ray=True ONLY in local-fallback branch; close() calls ray.shutdown() conditionally"
  - "force=True on ray.cancel valid for @ray.remote FUNCTIONS (not actors) per D-162 design confirmation"
metrics:
  duration_seconds: 1369
  tasks_completed: 1
  files_created: 1
  completed_date: "2026-05-05"
---

# Phase 06 Plan 05: RayBackend on raw @ray.remote Summary

**One-liner:** RayBackend on raw `@ray.remote` with hybrid cluster init, WorkerCrashedError-aware three-way poll, and explicit worktree-path dispatch (D-161..D-167, all RESEARCH.md OQ-2..4 corrections applied inline).

## What Was Built

`src/automil/backends/ray.py` (429 lines) implements the complete Phase 2 Backend ABC for Ray dispatch:

- **`_run_experiment_ray(spec, worktree_path, log_path)`** — top-level `@ray.remote` function; subprocess.run with `cwd=str(target_dir)` (not os.chdir); sub_env built from dict(_os.environ) + spec.env without mutating shared state.
- **`_was_cap_cancel(handle, automil_dir)`** — reads `running/ray/<node_id>.json` to discriminate `BUDGET_KILLED` vs `CANCELLED` for cap-cancel paths.
- **`RayBackend`** — registered as `BACKENDS["ray"]` via `@register("ray")`:
  - `__init__`: hybrid init (try RAY_ADDRESS/"auto", ConnectionError → local fallback if allowed); `_we_started_ray` flag set only on local-fallback branch.
  - `submit`: 2-step `runner.create_worktree` + `runner.apply_overlay`; fractional `num_gpus`; atomic JSON persist to `running/ray/`.
  - `poll`: `ray.wait(timeout=0)` non-blocking; three distinct except clauses.
  - `cancel`: `ray.cancel(ref, force=True, recursive=True)`; warns on non-None signal.
  - `list_running`: scans `running/ray/*.json`; D-167 limitation documented.
  - `log_iter`: tails `running/ray/<node_id>.log` with 1s tick; drains on terminal.
  - `close`: calls `ray.shutdown()` only if `_we_started_ray=True`.

## Deviations from Plan

None - plan executed exactly as written with all five critical API corrections applied inline.

## Known Stubs

None. `ray.py` makes no UI-visible calls and has no data stubs. The `list_running()` method correctly notes the D-167 ObjectRef restoration limitation in comments but this is intentional documented behavior, not a stub.

## Threat Flags

None. `ray.py` introduces no new network endpoints, auth paths, or file access patterns beyond what is documented in the plan's threat model (RAY_ADDRESS env poisoning + log path traversal, both addressed by existing framework mitigations).

## Verification Results

All plan-specified verifications passed:

| Check | Command | Result |
|-------|---------|--------|
| BCK-04 lint | `uv run python scripts/check_backend_isolation.py src/automil/` | PASS: no violations |
| Framework purity | `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/ray.py` | PASS: zero matches |
| OQ-2 (no local_mode) | `grep -nE "local_mode\s*=\s*True" src/automil/backends/ray.py` | PASS: zero matches |
| OQ-3 (WorkerCrashedError) | `grep -nE "ray\.exceptions\.WorkerCrashedError" src/automil/backends/ray.py` | PASS: line 291 |
| Syntax valid | `uv run python -c "import ast; ast.parse(...)"` | PASS: ok |
| Three except clauses | `grep -cE "except ray\.exceptions\.\w+" src/automil/backends/ray.py` | PASS: 3 |
| Line count | `wc -l src/automil/backends/ray.py` | PASS: 429 lines (>= 250 min) |

**Key grep verifications:**
- `ignore_reinit_error=True`: lines 9 (docstring), 173, 179
- `WorkerCrashedError`: line 291 (except clause)
- `force=True`: line 365 (`ray.cancel(ref, force=True, recursive=True)`)
- `runner.create_worktree(spec.base_commit, spec.node_id)`: line 199
- `subprocess.run(` / `cwd=str(target_dir)`: lines 113 / 115

**Pre-existing failures (out-of-scope, not caused by ray.py):**
- `tests/backends/test_running_namespace.py` (2 failures): tests for `_backend_running_dir` method not yet implemented in daemon (Phase 6 plan 06-06+ scope)
- `tests/backends/test_log_unification.py::test_log_iter_close_60s_timeout`: tests for `_drain_log_iter_with_timeout` not yet implemented
- `tests/test_tick_cells.py` (3 failures): tests for orchestrator namespace changes not yet made

These failures existed before `ray.py` was added (confirmed by temporarily removing ray.py and re-running the same tests).

## Self-Check

### Created files exist:
- `src/automil/backends/ray.py`: FOUND
- Commit `f71e203` exists in git log: FOUND

## Self-Check: PASSED
