---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: "06"
subsystem: backends
tags: [breaking-change, namespace-migration, running-dir, D-168, D-169, BCK-05, BCK-06]
dependency_graph:
  requires: [06-01, 06-04, 06-05]
  provides: [per-backend-running-dir, flat-running-guardrail, CHANGELOG-6.0.0]
  affects: [_orchestrator_daemon, local_backend, cancel_cli, cell_cli, graph_reconcile]
tech_stack:
  added: []
  patterns: [per-backend-namespace, startup-guardrail, rglob-traversal]
key_files:
  created:
    - CHANGELOG.md
  modified:
    - src/automil/backends/_orchestrator_daemon.py
    - src/automil/backends/local.py
    - src/automil/cli/cancel.py
    - src/automil/cli/cell.py
    - src/automil/graph.py
    - tests/test_cli_cancel_resubmit.py
    - tests/test_tick_cells.py
decisions:
  - "D-168: daemon refuses to start on flat running/*.json with no namespaced subdirs — SystemExit with BREAKING CHANGE message"
  - "D-169: running_dir resolved per-backend via _backend_running_dir(name) helper; backward alias running_dir = running_root/local"
  - "__init__ no longer pre-creates running/local/ to preserve guardrail semantics; _backend_running_dir creates on demand"
  - "graph.reconcile uses rglob for running_path traversal; queue_path stays glob (flat)"
metrics:
  duration_seconds: 1271
  completed_date: "2026-05-06T19:44:08Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 7
---

# Phase 06 Plan 06: running/ Namespace Migration Summary

Per-backend `running/` namespacing (D-168, D-169): flat `orchestrator/running/<id>.json` → namespaced `orchestrator/running/<backend>/<id>.json`. Daemon refuses to start if flat files detected. All three Wave-0 stubs flip GREEN. Phase 5 baseline preserved.

## Tasks Completed

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | Daemon _backend_running_dir + D-168 guardrail | 8539d6f | `_orchestrator_daemon.py` |
| 2 | LocalBackend + cancel + cell + graph per-backend paths | 386184f | `local.py`, `cancel.py`, `cell.py`, `graph.py`, 2 test files |
| 3 | CHANGELOG.md 6.0.0 BREAKING entry | 004c210 | `CHANGELOG.md` |

## Changes Per File

### `src/automil/backends/_orchestrator_daemon.py`

**Before/After summary (8+ running_dir reference sites):**

| Line (approx) | Before | After |
|---|---|---|
| 287 | `self.running_dir = self.orch_dir / "running"` (flat) | `self.running_root = orch_dir / "running"` + `self.running_dir = running_root / "local"` (backward alias) |
| 377–384 | `Ensure directories` creates `self.running_dir` (flat) | Creates `self.running_root` only; `running/local/` not pre-created (guardrail preservation) |
| 383–400 | (new) | `_backend_running_dir(name)` helper: returns `running_root/name`, creates dir on demand |
| 470 | `_recover_orphans` uses `self.running_dir` | Unchanged — `self.running_dir` → `running/local/` (backward alias correct) |
| 496 | `_recover_orphans` glob | Unchanged — local orphan recovery only (intentional per D-169) |
| 738–739 | `running_spec = self.running_dir / ...` | Uses `self._backend_running_dir("local")` to ensure dir exists on first write |
| 769–803 | `_tick_cells` TERMINATING path uses `self.running_dir` | Unchanged — backward alias points at `running/local/` (local dispatch only) |
| 843, 884, 944, 1007 | `self.running_dir / f"{node_id}.json"` | Unchanged — backward alias correct |
| 1198–1225 | `run()` starts immediately | D-168 guardrail added: checks `running_root.glob("*.json")` vs namespaced subdirs; raises `SystemExit("BREAKING CHANGE...")` |

### `src/automil/backends/local.py`

Line 82: `self._running_dir = self._daemon.running_dir` → `self._running_dir = self._orch_dir / "running" / "local"` (explicit namespaced path per D-169).

### `src/automil/cli/cancel.py`

Line 84: `running_path = orch_dir / "running" / f"{node_id}.json"` → `running_path = orch_dir / "running" / backend_name / f"{node_id}.json"` (backend_name resolved at step 3 from node.metadata.backend, D-76 default "local").

### `src/automil/cli/cell.py`

Line 34: `running_dir.glob("*.json")` → `running_dir.rglob("*.json")` (traverses `running/local/`, `running/slurm/`, `running/ray/`).

### `src/automil/cli/reconcile.py`

No change — reconcile passes `orch/running` to `ExperimentGraph.reconcile()`; the traversal is owned by graph.py.

### `src/automil/graph.py`

`reconcile()` method: `running_path.glob("*.json")` → `running_path.rglob("*.json")` using `getattr(d, glob_fn)("*.json")` pattern (queue keeps `glob`, running uses `rglob`).

### `CHANGELOG.md`

Created at repo root. `## 6.0.0` heading with `### BREAKING: Per-backend running/ namespacing`, operator recovery steps (stop, confirm, upgrade, restart), daemon refusal-to-start documentation, Added/Compatibility sections.

## Wave-0 Stubs Status

All three stubs flip RED → GREEN:

| Stub | Status |
|------|--------|
| `test_running_dir_per_backend` | GREEN |
| `test_daemon_refuses_flat_running` | GREEN |
| `test_namespace_isolation` | GREEN |

## Pre-existing tick_cells Failures

**Status: same — 3 failures, same root cause, no regression.**

The 3 pre-existing failures remain unchanged:
1. `test_tick_cells_active_to_refusing_new` — `active` vs expected `refusing-new`
2. `test_tick_cells_terminating_fires_cancel_with_cap_reason` — `refusing-new` vs `terminating`
3. `test_tick_cells_finalized_when_running_empty` — `terminating` vs `finalized`

These failures are unrelated to the namespace migration — they concern the `next_status()` cell-state machine logic in `_tick_cells` which is orthogonal to path resolution. The namespace refactor did not make them worse (confirmed: same count, same messages as Phase 4 origin).

Two tests that WERE newly failing after the namespace change (`test_handle_completion_with_cap_cancel_reason_calls_reconcile`, `test_handle_completion_with_cap_cancel_zero_folds_marks_crash`) were fixed by Rule 1 auto-fix: `_make_orch` helper now creates `orch.running_dir` (= `running/local/`) since `__init__` no longer pre-creates it. These two tests now pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] __init__ pre-created running/local/ defeating the D-168 guardrail**
- **Found during:** Task 1 verification
- **Issue:** `__init__`'s "Ensure directories" loop created `self.running_dir` which, after the backward alias change, created `running/local/`. This caused the guardrail check `if flat_jsons and not namespaced` to evaluate as `False` (because `running/local/` exists), silently skipping the SystemExit.
- **Fix:** Changed "Ensure directories" to create `self.running_root` (= `running/`) instead of `self.running_dir` (= `running/local/`). The `_backend_running_dir` helper creates backend subdirs on demand; `_launch` now calls `_backend_running_dir("local")` before writing the running spec.
- **Files modified:** `_orchestrator_daemon.py`
- **Commit:** 8539d6f

**2. [Rule 1 - Bug] test_cli_cancel_resubmit.py wrote flat running specs**
- **Found during:** Task 2 baseline run
- **Issue:** `_write_running_spec` helper wrote to `running/<id>.json` (flat); cancel.py now reads from `running/<backend>/<id>.json`. Tests `test_cancel_happy_path` and `test_cancel_timeout` failed with `FileNotFoundError`.
- **Fix:** Added `backend_name` parameter to `_write_running_spec`; callers pass `backend_name="mock_slurm"` matching the graph node. Updated assertion in `test_cancel_happy_path` to check namespaced path.
- **Files modified:** `tests/test_cli_cancel_resubmit.py`
- **Commit:** 386184f

**3. [Rule 1 - Bug] test_tick_cells.py _make_orch didn't create running/local/**
- **Found during:** Task 2 baseline run
- **Issue:** Two tests wrote to `orch.running_dir` (now `running/local/`) but the dir didn't exist (since `__init__` no longer creates it). `test_handle_completion_with_cap_cancel_reason_calls_reconcile` and `test_handle_completion_with_cap_cancel_zero_folds_marks_crash` failed with `FileNotFoundError`.
- **Fix:** Added `orch.running_dir.mkdir(parents=True, exist_ok=True)` in `_make_orch` helper, with comment explaining why (D-169 init behavior change).
- **Files modified:** `tests/test_tick_cells.py`
- **Commit:** 386184f

## Known Stubs

None — all data flows are real. No placeholder text or wired-to-empty props.

## Threat Flags

No new network endpoints, auth paths, or trust-boundary crossings introduced. The `running_root.glob("*.json")` in the startup guardrail reads local filesystem only.

## Self-Check: PASSED

All 7 source files + CHANGELOG.md confirmed present. All 3 task commits (8539d6f, 386184f, 004c210) confirmed in git log. All 3 Wave-0 stubs confirmed GREEN. Phase baseline 787 passed + 37 skipped, exactly 3 pre-existing failures.
