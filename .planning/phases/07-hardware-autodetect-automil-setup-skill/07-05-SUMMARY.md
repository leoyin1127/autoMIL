---
phase: 07-hardware-autodetect-automil-setup-skill
plan: 05
subsystem: cli
tags: [healthcheck, init, LocalBackend, jinja2, config-yaml, vram-estimation]

requires:
  - phase: 07-03
    provides: LocalBackend.healthcheck() returning HealthReport with gpu_count, gpu_vram_gb, accelerator, detection_status

provides:
  - --no-healthcheck flag on automil init (CI skip path)
  - _format_health_report helper (human-readable HealthReport stdout)
  - _stamp_healthcheck_defaults helper (empirical quantile_95 or conservative min(vram)/8.0)
  - config.yaml.j2 cap: section with default_vram_estimate_gb and max_concurrent_per_gpu
  - config.yaml.j2 hardware: section with accelerator, gpu_count, min_vram_gb
  - 5 integration tests in tests/cli/test_init_healthcheck.py

affects: [07-08, 07-09, 07-10, 07-11]

tech-stack:
  added: [csv (stdlib, for results.tsv reading), numpy.quantile (empirical VRAM path)]
  patterns:
    - healthcheck runs between --update guard and template render (D-191 insertion point)
    - lazy LocalBackend import inside init() body (consistent with existing lazy-import pattern)
    - --update with healthcheck re-renders config.yaml fresh; --update with --no-healthcheck preserves existing config.yaml verbatim
    - vram_gb column (not peak_vram_mb) read from results.tsv per _orchestrator_daemon.py:1289 resolution

key-files:
  created:
    - tests/cli/test_init_healthcheck.py
  modified:
    - src/automil/cli/init.py
    - src/automil/templates/config.yaml.j2
    - tests/agent_assets/test_init_runtime.py

key-decisions:
  - "Pass project_root and automil_dir to LocalBackend() in init to avoid _find_automil_dir() failure on fresh init (config.yaml does not exist yet)"
  - "--update with healthcheck re-renders config.yaml from template (D-191); --update with --no-healthcheck preserves existing config.yaml verbatim to allow user to preserve customizations"
  - "Pre-existing em/en-dashes in init.py docstrings and echo strings fixed inline (CLAUDE.md gate; not new code)"
  - "vram_gb column confirmed via _orchestrator_daemon.py:1289+1300; no MB->GB conversion needed in consumer"
  - "conservative_vram = max(8.0, min(gpu_vram_gb) / 8.0); max_concurrent = max(1, int(min_vram // conservative_vram))"

requirements-completed: [STP-02, STP-03]

duration: 55min
completed: 2026-05-07
---

# Phase 07 Plan 05: automil init healthcheck wiring Summary

**LocalBackend.healthcheck() wired into automil init with empirical VRAM quantile_95 from results.tsv vram_gb column, --no-healthcheck CI bypass, and cap/hardware sections stamped in config.yaml.j2**

## Performance

- **Duration:** 55 min
- **Started:** 2026-05-07T22:00:00Z
- **Completed:** 2026-05-07T22:53:23Z
- **Tasks:** 3
- **Files modified:** 4 (init.py, config.yaml.j2, test_init_healthcheck.py [new], test_init_runtime.py)

## Accomplishments

- D-191 healthcheck insertion point: after --update guard, before template render; runs on both fresh init and --update
- config.yaml.j2 extended with `cap.default_vram_estimate_gb`, `cap.max_concurrent_per_gpu`, and `hardware:` section using Jinja `| default(...)` filters
- 5 integration tests covering D-198 clauses 2 and 3 all pass, including empirical quantile_95 path via mocked subprocess.run
- Conservative fallback `max(8.0, min(gpu_vram_gb) / 8.0)` used when results.tsv has fewer than 10 rows or is absent
- Pre-existing em/en-dashes in init.py and config.yaml.j2 cleaned up (CLAUDE.md gate compliance)

## Task Commits

1. **Task 1: --no-healthcheck flag, helpers, healthcheck call in init()** - `30ab8f3` (feat)
2. **Task 2: extend config.yaml.j2 with cap and hardware sections** - `1278f96` (feat)
3. **Task 3: 5 integration tests + --update config re-stamp fix** - `8e91dba` (feat)

## Files Created/Modified

- `src/automil/cli/init.py` - Added `--no-healthcheck` is_flag, `_format_health_report`, `_stamp_healthcheck_defaults` helpers, D-191 healthcheck block between update-guard and template render. Lines 176-262 (helpers), 313-334 (healthcheck block), 336-380 (restructured template rendering with `elif not no_healthcheck:` path for --update re-stamp).
- `src/automil/templates/config.yaml.j2` - Added `cap.default_vram_estimate_gb` and `cap.max_concurrent_per_gpu` with Jinja `| default()` filters; new `hardware:` section with `accelerator`, `gpu_count`, `min_vram_gb`. Fixed pre-existing em-dashes in section headers and SLURM directive comments.
- `tests/cli/test_init_healthcheck.py` - 5 new integration tests for D-198 clauses 2+3.
- `tests/agent_assets/test_init_runtime.py` - Updated `test_init_update_does_not_overwrite_config` to use `--no-healthcheck` (reflecting new D-191 semantics where --update + healthcheck re-stamps config.yaml).

## Decisions Made

- Pass `project_root=project_root, automil_dir=automil_dir` to `LocalBackend()` so fresh-init projects (no config.yaml yet) don't trigger `_find_automil_dir()` RuntimeError.
- `--update` + healthcheck re-renders config.yaml fresh from template. `--update` + `--no-healthcheck` preserves existing config verbatim. This makes D-191 and pre-existing UX expectation coexist cleanly.
- Results.tsv column is `vram_gb` (confirmed by `_orchestrator_daemon.py:1289+1300`); orchestrator converts `peak_vram_mb` to GB at write time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed LocalBackend() construction failure on fresh init**
- **Found during:** Task 3 (test_init_stamps_gpu_count failing)
- **Issue:** `LocalBackend()` with no args calls `_find_automil_dir()` which walks up looking for `automil/config.yaml`. On fresh init, config.yaml doesn't exist yet when healthcheck runs (before template render).
- **Fix:** Pass `project_root=project_root, automil_dir=automil_dir` to `LocalBackend()` so the daemon uses the explicit path and skips auto-detection.
- **Files modified:** src/automil/cli/init.py line 322
- **Verification:** test_init_stamps_gpu_count passes; fresh init produces config.yaml with hardware section.
- **Committed in:** 8e91dba (Task 3 commit)

**2. [Rule 1 - Bug] Fixed --update path not re-stamping config.yaml**
- **Found during:** Task 3 (test_init_recomputes_default_vram_from_results_tsv failing)
- **Issue:** Template rendering was inside `if not update:` block. The `--update` path never re-rendered config.yaml, so empirical VRAM values were never stamped on `--update`.
- **Fix:** Moved template env/context setup outside `if not update:` block; added `elif not no_healthcheck:` branch to re-render config.yaml on `--update` + healthcheck.
- **Files modified:** src/automil/cli/init.py lines 336-380
- **Verification:** test_init_recomputes_default_vram_from_results_tsv passes with --update.
- **Committed in:** 8e91dba (Task 3 commit)

**3. [Rule 1 - Bug] Pre-existing test conflict: test_init_update_does_not_overwrite_config**
- **Found during:** Task 3 (full test suite regression)
- **Issue:** Existing test expected --update to NOT overwrite config.yaml. New D-191 behavior makes --update + healthcheck re-render config.yaml. Direct conflict.
- **Fix:** Updated test to use `--no-healthcheck` flag for both init calls, reflecting correct D-191 semantics: `--update + --no-healthcheck` preserves existing config.yaml verbatim.
- **Files modified:** tests/agent_assets/test_init_runtime.py
- **Verification:** All 18 tests in test_init_runtime.py + test_init_healthcheck.py pass.
- **Committed in:** 8e91dba (Task 3 commit)

**4. [Rule 1 - Bug] Pre-existing em/en-dashes in init.py and config.yaml.j2**
- **Found during:** Task 1, Task 2 (CLAUDE.md em-dash gate)
- **Issue:** Multiple `—` (em-dash) and `–` (en-dash) characters in pre-existing docstrings, comments, and echo strings in init.py and config.yaml.j2.
- **Fix:** Replaced all em/en-dashes with commas, colons, or periods per CLAUDE.md no-em-dash rule.
- **Files modified:** src/automil/cli/init.py, src/automil/templates/config.yaml.j2
- **Verification:** `grep -P "\x{2014}|\x{2013}"` returns zero matches on both files.
- **Committed in:** 30ab8f3 (Task 1), 1278f96 (Task 2)

---

**Total deviations:** 4 auto-fixed (4 x Rule 1 bugs)
**Impact on plan:** All fixes necessary for correctness, test compliance, and CLAUDE.md gate. No scope creep.

## Empirical VRAM Calculation Details

When `results.tsv` has 30 rows with `vram_gb` values `[4.0, 4.5, ..., 18.5]`:
- `numpy.quantile([4.0, ..., 18.5], 0.95)` = approximately 17.575 GB
- Test assertion: `abs(actual - expected) <= 0.05` passes

Conservative fallback (first-time init or fewer than 10 rows):
- `min_vram = 48.0` (49140 MB / 1024 = 47.99 GB on Leo's 48GB workstation)
- `conservative_vram = max(8.0, 48.0 / 8.0) = max(8.0, 6.0) = 8.0`
- `max_concurrent = max(1, int(48.0 // 8.0)) = max(1, 6) = 6`

## Issues Encountered

- `git stash` / stash-pop conflict caused init.py to temporarily lose the `LocalBackend` argument fix during debugging. Detected when tests re-ran and failed. Re-applied the fix deterministically.
- Pre-existing test failures (22 total in gate/test_evaluate.py, gate/test_two_stage_gate.py, test_tick_cells.py) confirmed as pre-existing by stash-before check. Not introduced by this plan.

## Known Stubs

None. All config.yaml.j2 values flow from healthcheck results (or conservative defaults). No placeholder/hardcoded values that prevent the plan's goal.

## Next Phase Readiness

- Wave 5 (07-06, 07-07) can proceed: `_stamp_healthcheck_defaults` provides the `vram_gb` column resolution needed by the skill body.
- Wave 6 (07-08, 07-09, 07-10) can proceed: `_stamp_healthcheck_defaults` is the function under test; `--no-healthcheck` flag is available for idempotency tests.
- `automil init --no-healthcheck` is the recommended form for all Wave 6+ tests that create tmp projects without GPU hardware.

---
*Phase: 07-hardware-autodetect-automil-setup-skill*
*Completed: 2026-05-07*

## Self-Check: PASSED

All files exist and all commits verified:
- src/automil/cli/init.py: FOUND
- src/automil/templates/config.yaml.j2: FOUND
- tests/cli/test_init_healthcheck.py: FOUND
- 07-05-SUMMARY.md: FOUND
- commit 30ab8f3: FOUND
- commit 1278f96: FOUND
- commit 8e91dba: FOUND
