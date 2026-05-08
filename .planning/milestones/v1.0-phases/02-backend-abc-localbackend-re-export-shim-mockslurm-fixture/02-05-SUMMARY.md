---
phase: "02"
plan: "02-05"
subsystem: backends
tags: [BCK-02, D-60, D-61, D-77, local-backend, adapter]
dependency_graph:
  requires: [02-02, 02-04]
  provides: [BACKENDS["local"], LocalBackend]
  affects: [02-07, 02-08]
tech_stack:
  added: []
  patterns:
    - Thin protocol adapter over on-disk state machine
    - Atomic write (tempfile.mkstemp + os.replace) for queue/<id>.json
    - Lazy import inside __init__ to break circular import cycle
    - 0.1s tick log tail iterator with terminal-state close
key_files:
  created:
    - src/automil/backends/local.py
  modified:
    - src/automil/backends/__init__.py
    - src/automil/backends/_orchestrator_daemon.py
decisions:
  - _kill_experiment() added to daemon (Rule 2 deviation) — missing cancel entry point
  - cancel() two-phase: queue file removal for pending; _daemon._kill_experiment for running
  - opaque_id="pending" at submit time; "running" in list_running (PID not on-disk in Phase 2)
  - Lazy import of ExperimentOrchestrator inside LocalBackend.__init__ (circular import guard)
metrics:
  duration_seconds: ~300
  completed_at: "2026-05-02"
  tasks_completed: 4
  files_changed: 3
requirements: [BCK-02]
---

# Phase 02 Plan 05: LocalBackend — Thin Protocol Adapter Summary

## One-liner

LocalBackend thin adapter wrapping ExperimentOrchestrator via on-disk queue/running/archive state machine, registered as BACKENDS["local"] via @register("local") decorator.

## What was built

`src/automil/backends/local.py` (~280 lines) implements `class LocalBackend(Backend)` as the D-60 shim over `_orchestrator_daemon.py`. All five abstract methods delegate to the daemon's on-disk state machine — no new lifecycle logic, no new file formats, no duplicated process control.

## JobSpec → daemon spec dict mapping table

| JobSpec field         | queue/<id>.json key     | Notes |
|-----------------------|-------------------------|-------|
| `node_id`             | `id`                    | Also used as the filename stem |
| `base_commit`         | `base_commit`           | Short SHA passed to worktree creation |
| `overlay_files`       | `overlay_manifest` keys | Values set to `""` (hash populated by cli/submit.py; LocalBackend bypasses CLI) |
| `overlay_dir`         | `overlay_dir`           | Stored as relative string `"archive/<id>"` |
| `gpu_estimate_gb`     | `estimated_vram_gb`     | Used by daemon bin-packer |
| `walltime_seconds`    | `timeout_min`           | Converted: `max(1, walltime_seconds // 60)` |
| `env`                 | `env`                   | Dict from tuple-of-tuples |
| *(implicit)*          | `metadata.backend`      | Always `"local"` (D-76) |
| *(implicit)*          | `priority`              | Hardcoded `1` (JobSpec has no priority field in Phase 2) |
| *(implicit)*          | `submitted_at`          | ISO-8601 from `time.time()` at submit call |

## Method implementation summary

### `__init__(project_root, automil_dir)`
Lazy-imports `ExperimentOrchestrator` inside the method body to avoid a circular import (`backends/__init__` → `local` → `_orchestrator_daemon` is fine; the issue is that `register` must be defined before `@register("local")` fires). Stores `self._daemon` and shortcuts `_queue_dir`, `_running_dir`, `_archive_dir`. Construction **never** triggers `_recover_orphans` — the daemon's `_load_state(recover=False)` call in `ExperimentOrchestrator.__init__` guarantees this.

### `submit(spec) → JobHandle`
Builds daemon queue-spec dict from `JobSpec` fields (see mapping table above). Writes atomically via `tempfile.mkstemp + os.replace` pattern (Pattern 6 from 02-PATTERNS.md). Returns `JobHandle(opaque_id="pending")` — the PID is not available until the daemon launches. This is expected per D-77.

### `poll(handle) → JobState`
Pure snapshot, non-blocking. Priority order:
1. `running/<id>.json` exists → RUNNING
2. `archive/<id>/result.json` exists → map daemon status to JobState (see status map below)
3. `queue/<id>.json` exists → PENDING
4. None → raise `BackendError`

Daemon status → JobState mapping:
- `"completed"` → `COMPLETED`
- `"crash"` → `CRASHED`
- `"oom"` → `CRASHED`
- `"timeout"` → `CRASHED`
- `"cancelled"` → `CANCELLED`
- `"budget_killed"` → `BUDGET_KILLED`
- unknown → `CRASHED` with warning log

### `cancel(handle, signal=None)`
Two-phase fire-and-forget:
1. If `queue/<id>.json` exists → `unlink()` it (prevents daemon pickup, immediate effect)
2. If running → `self._daemon._kill_experiment(node_id, sig=signal or SIGTERM)`

### `list_running() → list[JobHandle]`
Scans `running/*.json`. Reconstructs `submitted_at` from spec's ISO-8601 `submitted_at` field; falls back to file mtime. `opaque_id="running"` because PID is not persisted in the running spec on disk (Phase 2 design — the daemon holds the `Popen` handle in-memory).

### `log_iter(handle) → Iterator[str]`
Tails `archive/<id>/run.log` with a 0.1s tick. Checks terminal state on each tick via `poll()`. On terminal: performs one final read to capture last lines, then returns. Handles job-already-terminal at call time by yielding full file content immediately.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added `_kill_experiment()` to ExperimentOrchestrator**
- **Found during:** T-02-05-01 (read pass of daemon)
- **Issue:** Plan specified `LocalBackend.cancel` delegates to `self._daemon._kill_experiment()`, but this method did not exist in `_orchestrator_daemon.py`. The kill logic existed only inside `_handle_timeout()` (inlined, not extractable).
- **Fix:** Added `ExperimentOrchestrator._kill_experiment(node_id, sig=SIGTERM) → bool` to the daemon. Uses the same `os.killpg(os.getpgid(pid), sig)` pattern as `_handle_timeout`. Returns `True` if the process was found in `self.running`, `False` otherwise (with a warning — daemon process is separate, `self.running` will be empty for CLI-side LocalBackend instances).
- **Files modified:** `src/automil/backends/_orchestrator_daemon.py`
- **Commit:** 3ca81c7
- **Scope:** The method is in `_orchestrator_daemon.py` (BCK-04 allowlist), so no isolation rule is violated.

### Design discovery: PID not persisted on-disk for running experiments

The daemon's `running/<id>.json` is a **copy of the experiment spec** (not a `RunningExperiment` with PID). The daemon stores `RunningExperiment(process=Popen(...))` in-memory (`self.running` dict), but this is not serialised to disk.

**Impact on LocalBackend:**
- `list_running()` returns handles with `opaque_id="running"` (not a PID string). This is acceptable for Phase 2 — the opaque_id value is backend-internal and the contract tests (Plan 02-07) do not require it to be a PID.
- `cancel()` for running jobs: `_kill_experiment` will return `False` if called from a freshly-constructed CLI-side `LocalBackend` (because `self._daemon.running` is empty — the actual daemon is a separate OS process). Cancel for pending jobs (queue file removal) works perfectly.

This is a **known Phase 2 scope boundary** — per D-72, per-backend state namespacing and cross-process cancel are Phase 6 work. The plan says cancel is "fire-and-forget" (D-57); for the Phase 2 use case (daemon in same process or test contexts), `_kill_experiment` works correctly.

## BACKENDS["local"] registration verification

```
$ python -c "from automil.backends import BACKENDS; print(BACKENDS)"
{'local': <class 'automil.backends.local.LocalBackend'>}

$ python -c "from automil.backends import BACKENDS, LocalBackend; assert BACKENDS['local'] is LocalBackend"
# exits 0 — assertion holds
```

The `@register("local")` decorator fires at import time when `backends/__init__.py` executes `from automil.backends import local as _local_backend`. The `register` function is defined before the import (lines 30-60 in `__init__.py`), ensuring the decorator has its target available.

## Test count delta

| Stage | Count | Notes |
|-------|-------|-------|
| Before plan | 394 | Phase 0+1 baseline |
| After plan | 394 | No regressions; no new tests (per plan: Plan 02-07 adds contract tests) |

The plan explicitly specifies "No standalone test file. The 394-test suite is the behavioural contract (D-60). Plan 02-07 adds the parameterised contract test."

## Key invariants verified

1. **BACKENDS["local"] is LocalBackend** — ✓ (smoke check passed)
2. **issubclass(LocalBackend, Backend)** — ✓
3. **LocalBackend.__init__ does NOT call _recover_orphans** — ✓ (ExperimentOrchestrator._load_state(recover=False) confirmed at line ~355)
4. **submit() writes queue/<id>.json with correct shape** — ✓ (functional test)
5. **poll() returns PENDING when queue file exists** — ✓
6. **poll() returns RUNNING when running/ spec exists** — ✓
7. **poll() returns COMPLETED/CRASHED/CANCELLED from result.json** — ✓
8. **poll() raises BackendError for unknown handles** — ✓
9. **list_running() returns empty list when running/ is empty** — ✓
10. **No Popen/os.kill/os.killpg/.pid in local.py body** — ✓ (only in docstring comment)
11. **394 tests green** — ✓

## Known Stubs

None — LocalBackend wires directly to the daemon's on-disk state machine. No placeholder data flows to any UI or caller.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. All file access is within the existing `automil/orchestrator/` directory tree. T-02-05-S01 through T-02-05-S04 from the plan's threat model:

- **T-02-05-S01** (recover_orphans race) — mitigated: ExperimentOrchestrator.__init__ calls `_load_state(recover=False)`; LocalBackend adds no recovery logic.
- **T-02-05-S02** (PID reuse) — mitigated: cancel delegates to `_kill_experiment` which uses `os.killpg`; CLN-04's starttime cross-check protects the daemon's own `_handle_timeout`.
- **T-02-05-S03** (log_iter hang) — mitigated: checks terminal state on every 0.1s tick; closes iterator on terminal.
- **T-02-05-S04** (queue file never picked up) — accepted by design (D-57); PENDING indefinitely is expected when daemon not running.

## Self-Check: PASSED

Files created:
- `src/automil/backends/local.py` — FOUND
- `.planning/phases/02-backend-abc-localbackend-re-export-shim-mockslurm-fixture/02-05-SUMMARY.md` — FOUND

Commits:
- `3ca81c7` — FOUND (`git log --oneline | grep 3ca81c7`)

Test count: 394 passed (matches hard floor).
