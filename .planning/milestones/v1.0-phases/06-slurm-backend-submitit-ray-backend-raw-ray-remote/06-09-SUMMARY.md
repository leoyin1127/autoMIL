---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: "09"
subsystem: backends/testing
tags: [acceptance-smoke, D-176, D-179, BCK-05, BCK-06]
dependency_graph:
  requires: ["06-01", "06-04", "06-05", "06-06", "06-07"]
  provides: ["tests/backends/_smoke_helpers.py"]
  affects: ["tests/backends/test_node_0176_smoke.py"]
tech_stack:
  added: []
  patterns: ["subprocess-direct local dispatch (W-8 acceptable shortcut)", "worktree path via Runner convention"]
key_files:
  created:
    - tests/backends/_smoke_helpers.py
  modified: []
decisions:
  - "Local path runs train.py via subprocess directly (no live daemon in fixture) — exactly what the daemon would do; W-8 acceptable shortcut"
  - "Worktree path resolved via Runner convention (project_root/.automil_worktrees/<node_id>) rather than reading running JSON — avoids timing dependency"
  - "result.json read from worktree path post-completion for both SLURM-debug and ray-local backends"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-06T19:59:49Z"
  tasks_completed: 1
  files_changed: 1
---

# Phase 06 Plan 09: Acceptance Smoke Helper (_smoke_helpers.py) Summary

Implemented `tests/backends/_smoke_helpers.py` with three backend dispatch paths for the D-176 acceptance smoke. The Wave-0 stub `test_node_0176_smoke.py` now flips green for the `local` parametrisation and skips cleanly for `slurm-debug`/`ray-local` when their extras are absent.

## What Was Built

`run_node_0176_smoke(backend_name, project_root, automil_dir) -> float` dispatches the synthetic train.py (composite=0.502 deterministically) via three paths:

1. **local** — `_run_local()`: copies train.py into a workdir, runs via `subprocess.run(["python", "train.py"], ...)`, reads `result.json` from that workdir. No daemon required.
2. **slurm-debug** — `_run_slurm_debug()`: constructs `SLURMBackend(debug_in_process=True)`, calls `submit()` (DebugExecutor runs synchronously), polls until COMPLETED, reads `result.json` from `project_root/.automil_worktrees/smoke_slurm_debug/`.
3. **ray-local** — `_run_ray_local()`: constructs `RayBackend(allow_local_fallback=True)`, calls `submit()`, polls until COMPLETED, reads `result.json` from `project_root/.automil_worktrees/smoke_ray_local/`. Respects `_we_started_ray` for shutdown discipline.

## Verification Results

```
tests/backends/test_node_0176_smoke.py::test_node_0176_equivalent_composite_within_tolerance[local]       PASSED
tests/backends/test_node_0176_smoke.py::test_node_0176_equivalent_composite_within_tolerance[slurm-debug] SKIPPED
tests/backends/test_node_0176_smoke.py::test_node_0176_equivalent_composite_within_tolerance[ray-local]   SKIPPED
```

Composite returned by local path: 0.502. Tolerance assertion `abs(0.502 - 0.502) <= 0.005` evaluates True.

Full baseline: 784 passed, 42 skipped (the 1 pre-existing failure in `test_tick_cells.py::test_tick_cells_active_to_refusing_new` is unrelated to this plan — confirmed pre-existing via git stash check).

## Deviations from Plan

**1. [Rule 1 — Design simplification] Worktree path via Runner convention, not running JSON**
- **Found during:** Implementation of `_run_slurm_debug`
- **Issue:** Plan suggested reading `worktree_path` from `running/slurm/<node_id>.json`, but for DebugExecutor (synchronous), `_persist_running` is called after the job completes — the running JSON is always available. However, reading it requires parsing JSON from disk and coupling to `running/slurm/` path layout.
- **Fix:** Used `project_root / ".automil_worktrees" / node_id` directly (Runner.worktree_path() convention), which is simpler, always correct, and not timing-dependent.
- **Files modified:** `tests/backends/_smoke_helpers.py`

**2. [Out of scope] Pre-existing test failure in test_tick_cells.py**
- `test_tick_cells::test_tick_cells_active_to_refusing_new` was already failing before this plan (confirmed via git stash).
- Logged to deferred items — not caused by Plan 06-09 changes.

## Known Stubs

None — `result.json` composite 0.502 is fully wired from the synthetic train.py.

## Threat Flags

None — test-only file; no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `tests/backends/_smoke_helpers.py` exists: FOUND
- Commit `b379902` exists: FOUND
- `run_node_0176_smoke` defined with all three dispatch paths: VERIFIED
- `_VALID_BACKEND_NAMES = {"local", "slurm-debug", "ray-local"}`: VERIFIED
- Unknown backend raises ValueError: VERIFIED (raises with sorted hint)
- local test passes, slurm/ray skip cleanly: VERIFIED
