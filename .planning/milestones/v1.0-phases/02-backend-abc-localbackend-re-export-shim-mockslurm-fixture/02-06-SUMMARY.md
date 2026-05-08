---
phase: 02
plan: 06
subsystem: backends
tags: [mock, threading, test-fixture, eventual-consistency, BCK-03]
dependency_graph:
  requires: [02-01, 02-02]
  provides: [mock_slurm_backend, slurm_fixture]
  affects: [02-07-contract-test]
tech_stack:
  added: [threading.Timer, threading.Event, threading.Lock]
  patterns: [eventual-consistency-fixture, state-file-restart-recovery, fire-and-forget-cancel]
key_files:
  created:
    - src/automil/backends/mock_slurm.py
  modified: []
decisions:
  - "PENDING/RUNNING jobs at restart → CRASHED (no timer resumption; matches real SLURM head-node restart behaviour)"
  - "log_iter polls internally (0.05s tick) when non-terminal to match SLURM's log-on-completion model without requiring caller to pre-wait"
  - "_persist_state() uses inline atomic tempfile+rename rather than importing _atomic_write_text to keep mock_slurm.py self-contained and avoid cli.lifecycle import in backends layer"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02"
  tasks_completed: 3
  files_created: 1
  files_modified: 0
---

# Phase 02 Plan 06: MockSLURMBackend Eventual-Consistency Fixture Summary

**One-liner:** `threading.Timer` chain simulates SLURM poll-lag with `threading.Event` cancel flag, atomic `state_file` persistence, and PENDING/RUNNING→CRASHED restart semantics.

---

## What Was Built

`src/automil/backends/mock_slurm.py` (~230 lines) implementing the `Backend` ABC as an eventual-consistency test fixture for Plan 02-07's parameterised contract test. The file is registered as `"mock_slurm"` in `BACKENDS` via `@register("mock_slurm")` but is NOT auto-imported in `backends/__init__.py` (D-69).

---

## Threading Model

| Primitive | Purpose | Thread-Safety |
|-----------|---------|---------------|
| `threading.Lock` (`_lock`) | Guards `_jobs` dict (mutable state) | Reentrant-safe; acquired by main thread AND timer callbacks, never nested |
| `threading.Event` (`cancel_requested`) | Per-job cancel flag | `.set()` is atomic across threads (T-02-06-S02) |
| `threading.Timer` (`daemon=True`) | Drives PENDING→RUNNING→terminal transitions | Killed automatically on process exit (T-02-06-S03) |

**Deadlock prevention (T-02-06-S01):** Timer callbacks (`_transition`, `_finish`) acquire `_lock` exactly once, write `job.state`, and release. They do NOT call `poll()`, `cancel()`, or any other `Backend` method while holding the lock. `poll()` acquires lock for a snapshot read only — no nested acquisition possible.

---

## State Machine

| Phase | Trigger | Timer | State After |
|-------|---------|-------|-------------|
| Submit | `submit()` call | schedule `_transition` after `poll_lag_seconds` | `PENDING` |
| First tick | `_transition` fires | schedule `_finish` after `poll_lag_seconds` | `RUNNING` (or `CANCELLED` if flag set) |
| Second tick | `_finish` fires | none | `COMPLETED` / `CRASHED` / `CANCELLED` |

**Command stub semantics (D-63):**
- `"--crash"` or `"--error"` in command → `CRASHED`
- `cancel_requested.is_set()` → `CANCELLED` (checked at both ticks)
- otherwise → `COMPLETED`

---

## Key Invariants

| Invariant | Where Enforced |
|-----------|---------------|
| `cancel()` returns `None` immediately | No blocking; only `job.cancel_requested.set()` |
| `poll()` is a pure snapshot | Never modifies `job.state`; no side effects |
| `opaque_id` is monotonically unique | `f"{self._counter}.0"` under lock; counter persisted in state_file |
| `mock_slurm` not in `BACKENDS` before explicit import | D-69; verified by `python -c "..."` smoke test |
| No `Popen/os.kill/os.killpg/.pid` in `mock_slurm.py` | BCK-04; verified by grep |
| PENDING/RUNNING → CRASHED on `_from_json` reload | Timer threads cannot be resumed; matches real SLURM restart |

---

## `_MockJob` Serialisation

`_to_json()` explicitly lists: `node_id`, `backend`, `opaque_id`, `submitted_at`, `state`, `log_buffer`. Excludes `cancel_requested` (threading.Event — not JSON-serialisable) and `timer` (threading.Timer — runtime-only). T-02-06-S05 mitigated.

`_from_json()` constructs a fresh `threading.Event()` for `cancel_requested`, restores `state` as `JobState(str)`, and applies PENDING/RUNNING→CRASHED restart policy (RESEARCH.md §7).

---

## `state_file` Persistence

When `state_file` is set:
- Constructor calls `_load_state()` if the file exists (restart recovery)
- Every state transition calls `_persist_state()` via `os.replace(tmp, state_file)` atomic write
- Counter is restored from the highest opaque_id seen in the file (prevents collisions on new submits after restart)

---

## Test Count Delta

| Metric | Value |
|--------|-------|
| Baseline before this plan | 394 tests |
| Tests added this plan | 0 (standalone tests per plan spec; contract tests in 02-07) |
| Final count | 394 tests |
| Baseline status | 394/394 PASSED |

**Wall-clock for full suite:** ~24s (dominated by orchestrator integration tests). MockSLURM-specific smoke tests ran in <0.5s with `poll_lag_seconds=0.05`.

---

## Acceptance Criteria

- [x] `src/automil/backends/mock_slurm.py` exists with `class MockSLURMBackend(Backend)` registered as `"mock_slurm"`
- [x] Constructor takes `poll_lag_seconds=5.0`, `state_file=None`; loads persisted state if file exists
- [x] `submit()` spawns `threading.Timer` chain; `cancel_requested` is `threading.Event`; all timers are `daemon=True`
- [x] `cancel()` returns immediately (fire-and-forget); sets `cancel_requested` event
- [x] `_MockJob._to_json()` excludes `cancel_requested` and `timer`; `_from_json()` marks PENDING/RUNNING as CRASHED on restart
- [x] `mock_slurm` NOT imported in `backends/__init__.py`; `BACKENDS["mock_slurm"]` only populated after explicit import
- [x] `uv run pytest tests/ -x -q` exits 0 with 394 tests (baseline preserved)
- [x] No `Popen`, `os.kill`, `os.killpg`, `.pid` references in `mock_slurm.py`
- [x] Single `feat(backends/mock_slurm):` commit lands cleanly

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Intentional Deviations

**1. `_persist_state()` uses inline atomic write instead of importing `_atomic_write_text`**
- **Reason:** Importing from `automil.cli.lifecycle._shared` would introduce a `cli` → `backends` layer-violation (backends should not depend on CLI internals). The pattern is identical (tempfile + `os.replace`) but kept self-contained in `mock_slurm.py`.
- **Impact:** Zero — same atomicity guarantee, slightly more code.

**2. `log_iter()` includes a polling loop for non-terminal state**
- **Reason:** The plan spec says "yields nothing while pending/running; callers use `wait_for_state` before calling." However, a bare `return` for non-terminal makes `log_iter` silent even if the caller blocks on it — confusing for contract test scenarios where the test drives `log_iter` concurrently. The loop (0.05s tick) matches D-58's "iterator may block briefly but MUST surface lines within ~1s."
- **Impact:** `log_iter` works correctly whether called before or after terminal state.

---

## Known Stubs

None — `MockSLURMBackend` is fully implemented. No hardcoded empty values flow to UI.

---

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| (none) | — | No new network endpoints, auth paths, or trust boundaries introduced |

---

## Self-Check

### Created files exist:
- `src/automil/backends/mock_slurm.py`: FOUND

### Commit exists:
- `4b08912` (`feat(backends/mock_slurm): MockSLURMBackend eventual-consistency fixture (BCK-03)`): FOUND

### D-69 gate:
- `python -c "from automil.backends import BACKENDS; assert 'mock_slurm' not in BACKENDS"` → PASSED
- `python -c "from automil.backends.mock_slurm import MockSLURMBackend; ..."` → PASSED

### BCK-04 gate:
- `grep "Popen\|os\.kill\|os\.killpg\|\.pid" mock_slurm.py` → no output (clean)

## Self-Check: PASSED
