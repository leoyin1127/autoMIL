---
phase: 07-hardware-autodetect-automil-setup-skill
plan: "09"
subsystem: tests/skills
tags: [tests, dry-run-gate, stp-06, d-198]
dependency_graph:
  requires: [07-02, 07-05, 07-08]
  provides: [tests/skills/test_setup_dry_run_gate.py]
  affects: []
tech_stack:
  added: []
  patterns: [subprocess-daemon-polling, skipif-gate]
key_files:
  created:
    - tests/skills/test_setup_dry_run_gate.py
  modified: []
decisions:
  - "F-01 fix applied: _automil_on_path() helper defined before first @pytest.mark.skipif decorator"
  - "F-02 fix applied: automil orchestrator start/stop subprocess approach, no private daemon helpers"
  - "Tests PASS (not SKIP) because automil console-script is on PATH under uv run pytest"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-07"
  tasks_completed: 1
  files_changed: 1
---

# Phase 7 Plan 09: Setup Dry-Run Gate Tests Summary

**One-liner:** 3 STP-06 gate tests using real automil CLI subprocess approach (F-01/F-02 fixes applied), all 3 PASSED under uv run pytest.

## What Was Built

Created `tests/skills/test_setup_dry_run_gate.py` with 3 end-to-end tests covering D-198 acceptance gate clause 5 and Pitfall 9 anti-acceptance #4.

### Test Outcomes

All 3 tests PASSED (automil console-script IS on PATH under `uv run pytest`):

1. **test_setup_gate_aborts_on_known_bad_config**: ImportError train.py was submitted, orchestrator ran it, observed status='crash'. Gate correctly identifies failure.

2. **test_setup_gate_passes_on_known_good_config**: A train.py that writes valid result.json was submitted and ran to completion. Observed status='completed'. Gate correctly identifies success.

3. **test_setup_gate_polling_terminates_within_90s**: Bad train.py (ImportError) terminates within the 90s polling budget. Total elapsed time was well under 95s. Status was 'crash' (not 'timeout'), confirming the daemon reached a terminal state.

### Runtime Behavior

- `shutil.which("automil")` returns a valid path under `uv run pytest` (uv adds workspace entry points to PATH automatically).
- All skipif decorators evaluated to `not True = False`, so tests ran rather than skipped.
- The orchestrator daemon launched via `automil orchestrator start`, processed the queued experiment, and exited cleanly after `automil orchestrator stop`.

## F-01 and F-02 Fix Verification

**F-01 (helper-before-decorator ordering):**
- `def _automil_on_path()` is the first top-level definition after imports (line 34).
- First `@pytest.mark.skipif(not _automil_on_path(), ...)` appears at line 161.
- `python3 -c "..."` ordering check: "ordering ok" confirmed.

**F-02 (public CLI surface only):**
- `_start_daemon()` uses `subprocess.Popen(["automil", "orchestrator", "start"], ...)`.
- `_stop_daemon()` uses `subprocess.run(["automil", "orchestrator", "stop"], ...)`.
- Zero references to `_process_queue_once` or `_tick_once` in the file.

## Deviations from Plan

### Auto-resolved Issues

**[Rule 3 - Blocking] tests/skills/conftest.py missing when 07-09 started**
- **Found during:** Pre-implementation check
- **Issue:** 07-08 (parallel wave) had not yet committed conftest.py when this plan began; the `tmp_git_repo` fixture was unavailable.
- **Fix:** Confirmed conftest.py existed in working tree (07-08 had created it as an untracked file in the parallel wave). Used the file as-is; no changes made. Only `tests/skills/test_setup_dry_run_gate.py` was committed.
- **Files modified:** None (conftest.py already existed from 07-08)
- **Commit:** n/a (no change to conftest.py)

## Known Stubs

None. The test file contains no placeholder values or hardcoded stubs.

## Threat Flags

None. This file is a pure test file with no network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- FOUND: tests/skills/test_setup_dry_run_gate.py
- FOUND: commit 037ee41 (test(07-09): add 3 setup dry-run gate tests)
