---
phase: "03"
plan: "03-04"
subsystem: trajectory
tags: [rotation, atomic-rename, size-threshold, soft-fail, tdd]
dependency_graph:
  requires: ["03-01"]
  provides: ["full RotationManager with soft/hard thresholds + atomic rename"]
  affects: ["src/automil/trajectory/recorder.py (rotation_manager.check_and_rotate calls)"]
tech_stack:
  added: []
  patterns:
    - "os.rename for POSIX-atomic file rotation (same filesystem)"
    - "frozen dataclass for immutable configuration"
    - "fd_cache eviction before rename to prevent stale flock release"
    - "soft-fail discipline: all errors return True (safe pass-through) except hard limit"
key_files:
  created:
    - tests/trajectory/test_rotation.py
  modified:
    - src/automil/trajectory/rotation.py
decisions:
  - "Used os.rename (not os.replace) per D-84 / 03-PATTERNS §5 — POSIX atomicity on same filesystem"
  - "fd_cache eviction happens BEFORE os.rename so the old fd's flock is released cleanly"
  - "Metadata header copy uses a fresh O_APPEND fd; recorder.py opens its own fd on next write"
  - "Hard limit CRITICAL log + return False; experiment process never killed (D-84 soft-fail discipline)"
  - "_next_rotation_index scans for smallest free N to avoid overwriting existing rotated siblings"
metrics:
  duration: "~3 minutes"
  completed: "2026-05-03"
  tasks_completed: 3
  files_modified: 2
---

# Phase 03 Plan 04: Full Rotation Manager (5 MB soft / 50 MB hard) Summary

## One-liner

Atomic `os.rename`-based rotation manager replacing stub: 5 MB soft to `trajectory.<n>.jsonl` with metadata copy, 50 MB hard returns False + logs CRITICAL (D-84).

## What Was Built

Replaced the placeholder `rotation.py` stub (from 03-01) with the complete `RotationManager` implementation:

**`src/automil/trajectory/rotation.py`** — Full implementation:
- `RotationManager` — frozen dataclass with `soft_bytes` (5 MB default) and `hard_bytes` (50 MB default)
- `check_and_rotate(path, fd_cache)` — gate function called by `recorder.py` before every write
  - Returns `True` if file is below soft threshold or does not exist
  - On soft threshold: delegates to `_do_soft_rotate` → returns `True`
  - On hard threshold: logs CRITICAL, returns `False` (caller drops the event)
  - Any I/O exception: caught, logged at WARNING, returns `True` (safe pass-through)
- `_do_soft_rotate(path, fd_cache)` — atomic rename sequence:
  1. Reads first-line metadata bytes before rename
  2. Evicts and closes cached fd (prevents stale fd after rename)
  3. `os.rename(path, trajectory.<n>.jsonl)` — POSIX atomic
  4. Copies metadata header to new `trajectory.jsonl` via fresh O_APPEND fd
  5. Returns `True`; on any failure returns `True` (experiment continues)
- `_next_rotation_index(traj_path)` — scans existing siblings for smallest free N >= 1
- `_read_first_line(path)` — reads raw bytes for metadata copy; returns None on error

**`tests/trajectory/test_rotation.py`** — 9 unit tests covering the Nyquist matrix:
- `test_soft_rotate_triggers_on_threshold` — soft threshold triggers `trajectory.1.jsonl`
- `test_soft_rotate_copies_metadata_header` — new file starts with schema + runtime metadata
- `test_soft_rotate_atomicity` — skips `.1` and `.2` when pre-existing, uses `.3`
- `test_next_rotation_index_increments_correctly` — returns smallest free N with gap handling
- `test_hard_rotate_returns_false` — hard threshold returns False
- `test_hard_rotate_does_not_rename` — hard limit does not create `.1` sibling
- `test_no_file_returns_true` — non-existent path returns True
- `test_small_file_returns_true` — below soft threshold, no rotation, no `.1`
- `test_fd_cache_evicted_on_rotation` — fd evicted from cache on soft rotation

## Verification

```
tests/trajectory/test_rotation.py  9 passed in 0.07s
Full suite: 441 passed, 9 skipped in 19.75s  (no regressions)
```

## Deviations from Plan

None — plan executed exactly as written. Implementation matches the spec verbatim from the plan's code block.

## Known Stubs

None — `rotation.py` is fully implemented. The stub has been entirely replaced.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns outside `archive/<node_id>/`, or schema changes at trust boundaries. The threat model in the plan (T-03-04-S01..S04) covers all relevant rotation-specific risks; no new surface introduced.

## Self-Check: PASSED

- [x] `src/automil/trajectory/rotation.py` exists and contains `os.rename`
- [x] `tests/trajectory/test_rotation.py` exists and contains `test_soft_rotate_triggers`
- [x] Commit `782fbc8` in git log
- [x] No unexpected file deletions
- [x] `uv run pytest tests/trajectory/test_rotation.py -v` — 9/9 PASSED
- [x] `uv run pytest tests/ -x -q` — 441 passed, 9 skipped
