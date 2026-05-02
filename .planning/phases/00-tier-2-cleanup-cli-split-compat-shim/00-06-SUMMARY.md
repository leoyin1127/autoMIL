---
phase: 00-tier-2-cleanup-cli-split-compat-shim
plan: "06"
subsystem: orchestrator
tags: [security, pid-file, cln-04, stale-pid, linux-proc]
dependency_graph:
  requires: [00-05-PLAN]
  provides: [CLN-04-mitigation, JSON-pid-file, starttime-cross-check]
  affects: [src/automil/orchestrator.py]
tech_stack:
  added: []
  patterns: [/proc/<pid>/stat-field-22-parsing, JSON-pid-file-format, rfind-for-comm-with-spaces]
key_files:
  created:
    - tests/test_orchestrator_pid_starttime.py
  modified:
    - src/automil/orchestrator.py
decisions:
  - "Used /proc/<pid>/stat field 22 directly (no psutil dep) — D-17 verbatim, minimal impact principle"
  - "PID file JSON shape: {pid, starttime_ticks, starttime_iso} — D-17 verbatim"
  - "rfind(')') to skip comm field — handles process names containing parentheses"
  - "Legacy plain-int format treated as stale on read — one-time upgrade transition"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-02T01:54:56Z"
  tasks_completed: 1
  tasks_total: 1
  tests_added: 8
  tests_total: 108
---

# Phase 00 Plan 06: PID + starttime liveness check (CLN-04) Summary

**One-liner:** JSON PID file with `/proc/<pid>/stat` field-22 starttime cross-check closes HIGH-severity PID-reuse DoS (CLN-04) with zero new deps.

## What Was Built

Replaced the bare `os.kill(pid, 0)` PID-liveness check in `ExperimentOrchestrator` with a `pid + starttime_ticks` cross-check. The orchestrator now:

1. Writes the PID file as JSON `{"pid": int, "starttime_ticks": int, "starttime_iso": str}` instead of a plain integer.
2. Reads `/proc/<pid>/stat` field 22 (starttime in clock ticks since boot) to verify ownership before signalling.
3. Treats any PID where the recorded starttime differs from the live process as stale — refusing to send SIGTERM to an unrelated process.
4. Treats legacy plain-int PID files and malformed/missing-key JSON as stale (unlinks and proceeds).

### Five helper functions added to `orchestrator.py` (module-level, after `_find_git_root`):

| Function | Purpose |
|----------|---------|
| `_parse_starttime_from_stat_line(line)` | Parses field 22 from raw `/proc/<pid>/stat` content; uses `rfind(')')` to handle comm-with-spaces |
| `_read_proc_starttime(pid)` | Reads `/proc/<pid>/stat`, delegates to parser; returns `None` on any error |
| `_is_pid_alive_with_starttime(pid, expected)` | Single source of truth: returns True iff process alive AND starttime matches |
| `_write_pid_file(path)` | Writes JSON PID file at daemon start; graceful fallback if `/proc` unavailable |
| `_load_pid_file(path)` | Loads and validates JSON PID file; returns `None` for legacy/malformed content |

### Four call sites rewritten:

| Method | Before | After |
|--------|--------|-------|
| `run` | `self.pid_file.write_text(str(os.getpid()) + "\n")` | `_write_pid_file(self.pid_file)` |
| `cmd_start` | `os.kill(pid, 0)` liveness check | `_load_pid_file` + `_is_pid_alive_with_starttime` |
| `cmd_status` | `os.kill(pid, 0)` liveness check | `_load_pid_file` + `_is_pid_alive_with_starttime` |
| `cmd_stop` | `os.kill(pid, 0)` then SIGTERM | starttime cross-check before SIGTERM |

## Test Results

108 tests pass (all previous tests green + 8 new):

| Test | Scenario | Platform |
|------|----------|----------|
| `test_proc_starttime_parses_comm_with_spaces` | Synthetic stat line with `(my (weird) name)` parses correctly | Any |
| `test_is_pid_alive_for_current_process` | Current pytest PID + actual starttime → True | Linux |
| `test_is_pid_alive_for_nonexistent_pid` | PID 99999999 → False | Any |
| `test_is_pid_alive_with_wrong_starttime` | Correct PID, wrong starttime (+999999) → False (CLN-04 headline) | Linux |
| `test_pid_file_written_as_json` | `_write_pid_file` produces valid JSON with all 3 keys | Linux |
| `test_load_pid_file_handles_legacy_plain_int` | `"12345\n"` → None | Any |
| `test_load_pid_file_handles_invalid_json` | `"{not valid"` → None | Any |
| `test_load_pid_file_handles_missing_keys` | JSON missing `starttime_ticks` → None | Any |

Observed on Leo's workstation: `starttime_ticks = 462617052` for a live test process — confirms `/proc/<pid>/stat` parsing works correctly against real kernel data.

## Commits

| Hash | Type | Message |
|------|------|---------|
| `b9cc8fa` | test (RED) | test(orchestrator): add failing tests for PID starttime cross-check (CLN-04) |
| `2967c4c` | fix (GREEN) | fix(orchestrator): check pid + start_time for stale PID file detection (CLN-04) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed off-by-one in test scaffold's field count**

- **Found during:** GREEN phase — `test_proc_starttime_parses_comm_with_spaces` failed
- **Issue:** Plan's verbatim test scaffold used `range(2, 21)` (19 placeholders) producing 20 suffix fields (fields 3..22), placing `78901234` at field 23 instead of field 22
- **Fix:** Changed to `range(2, 20)` (18 placeholders) producing 19 suffix fields (fields 3..21), then `78901234` correctly lands at field 22 (index 19 in 0-indexed suffix)
- **Files modified:** `tests/test_orchestrator_pid_starttime.py` (line 27)
- **Commit:** `2967c4c` (included in GREEN commit since it was discovered during GREEN phase, not as a separate deviation commit)

No other deviations.

## TDD Gate Compliance

- RED gate: commit `b9cc8fa` (`test(orchestrator): ...`) — all 8 tests failed
- GREEN gate: commit `2967c4c` (`fix(orchestrator): ...`) — all 8 tests pass, 108 total

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond what the plan's `<threat_model>` documents. The three threats (T-00-11, T-00-12, T-00-13) are all mitigated or accepted as specified.

## Self-Check: PASSED

- `tests/test_orchestrator_pid_starttime.py` exists: YES
- `src/automil/orchestrator.py` contains `starttime_ticks`: YES
- `src/automil/orchestrator.py` contains `_is_pid_alive_with_starttime`: YES
- Bare `os.kill(pid, 0)` in code (not docstrings): ZERO hits
- Commit `b9cc8fa` exists: YES
- Commit `2967c4c` exists: YES
- All 108 tests pass: YES
