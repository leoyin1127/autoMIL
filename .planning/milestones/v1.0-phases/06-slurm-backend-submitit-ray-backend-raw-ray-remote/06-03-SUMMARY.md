---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 03
subsystem: backend
tags: [slurm, ray, config-template, cli-check, validation, BCK-05, BCK-06]

# Dependency graph
requires:
  - phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
    plan: 02
    provides: "SlurmDirectivesIncompleteError in backends/errors.py (D-178)"
provides:
  - "config.yaml.j2 backend: block with TODO_FILL_IN sentinels, walltime_seconds=21600, no signal key"
  - "_validate_slurm_directives(config) pure-function helper in cli/check.py"
  - "_validate_ray_backend(config, issues, warnings) advisory helper in cli/check.py"
  - "automil check SLURM directive validation at check-time (D-172)"
  - "automil check Ray reachability advisory (D-173)"
affects:
  - "06-04 — SLURMBackend reads walltime_seconds from same config schema"
  - "06-07 — contract tests exercise SLURM backends, slurm directive validation in check.py"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TODO_FILL_IN sentinel pattern for operator-required config values (forces explicit fill before submit)"
    - "Lazy import of SlurmDirectivesIncompleteError inside helper function (avoids hard dependency at module load)"
    - "Pure-function validator extracted from CLI command for direct unit-test access without Click"

key-files:
  created: []
  modified:
    - src/automil/templates/config.yaml.j2
    - src/automil/cli/check.py

key-decisions:
  - "walltime_seconds: 21600 is the paper-campaign default; framework reads from config (consumer-overridable), not hardcoded"
  - "signal key absent from directives template — framework-mandated at B:TERM@30; _validate_slurm_directives rejects if operator tries to set it"
  - "_validate_slurm_directives is a pure function (no Click, no I/O) so Wave-0 unit tests exercise it directly"
  - "Ray reachability advisory is non-blocking (warnings only, not issues) per D-173"
  - "backend: block placed after gate: block (after cap: and gate: from prior plans)"

patterns-established:
  - "Config sentinel pattern: TODO_FILL_IN string triggers SlurmDirectivesIncompleteError at automil check time"
  - "Forbidden-key guard: _FORBIDDEN_SLURM_DIRECTIVE_KEYS = [signal] appended to missing_keys on violation"
  - "Backend dispatch in check(): local (no-op) | slurm (validate) | ray (advisory) | unknown (warning)"

requirements-completed: [BCK-05, BCK-06]

# Metrics
duration: 20min
completed: 2026-05-06
---

# Phase 6 Plan 03: config.yaml.j2 backend block + cli/check.py SLURM/Ray validators Summary

**config.yaml.j2 gains a top-level `backend:` block with TODO_FILL_IN sentinels for required SLURM directives; `automil check` gains `_validate_slurm_directives` (raises `SlurmDirectivesIncompleteError` on TODO/missing keys) and `_validate_ray_backend` (advisory-only Ray reachability check)**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-06T18:00:00Z
- **Completed:** 2026-05-06T18:19:14Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Extended `config.yaml.j2` with `backend:` block: `name: "local"`, `slurm:` subsection with `walltime_seconds: 21600` and `directives:` with `partition`/`account` as `TODO_FILL_IN` sentinels, plus `ray:` with `allow_local_fallback: true`
- Added `_REQUIRED_SLURM_DIRECTIVES`, `_FORBIDDEN_SLURM_DIRECTIVE_KEYS`, `_TODO_SENTINEL` module-level constants to `check.py`
- Added `_validate_slurm_directives(config: dict)` pure helper that raises `SlurmDirectivesIncompleteError` listing exact missing/forbidden keys
- Added `_validate_ray_backend(config, issues, warnings)` advisory helper for Ray backend selection (missing extra → issue; unreachable cluster → warning)
- Extended `check()` body with backend dispatch block: SLURM validates directives, Ray checks reachability, unknown backend emits warning
- Wave-0 stubs `test_check_rejects_todo` and `test_check_accepts_complete` flip from RED to GREEN

## Task Commits

1. **Task 1: Extend config.yaml.j2 with backend: block** - `072392f` (feat)
2. **Merge main** - `e545a09` (merge — resolved conflict to keep cap:/gate: from main + new backend: block)
3. **Task 2: Add _validate_slurm_directives + _validate_ray_backend to check.py** - `1cc7b59` (feat)

## Files Created/Modified

- `src/automil/templates/config.yaml.j2` — Added `backend:` block after `gate:` block; 27 lines added; `signal:` key intentionally absent; `walltime_seconds: 21600` is paper-campaign default
- `src/automil/cli/check.py` — Added 2 helper functions + module-level constants + backend dispatch block inside `check()`; 104 lines added

## Decisions Made

- `walltime_seconds: 21600` in template is consumer-supplied paper-campaign default (not a framework constant per `feedback_paper_campaign_vs_framework` memory); any consumer can override
- `_validate_slurm_directives` is a pure function (no Click side effects) to enable Wave-0 unit tests to call it directly without CliRunner overhead
- `signal:` key is absent from the template's `directives:` block; if an operator adds it, `_validate_slurm_directives` detects it via `_FORBIDDEN_SLURM_DIRECTIVE_KEYS` and raises `SlurmDirectivesIncompleteError` with `signal` in `missing_keys`
- Ray reachability advisory does NOT raise — appends to `warnings` list only (D-173: "advisory, non-blocking")
- `walltime_seconds` belongs under `backend.slurm` (not under `backend.slurm.directives`) per RESEARCH.md OQ-1 correction; SLURMBackend converts via `timeout_min = max(1, walltime_seconds // 60)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Merge conflict resolution in config.yaml.j2**

- **Found during:** Task 2 verification (merging main to run Wave-0 tests)
- **Issue:** Worktree branched before 06-01/06-02 commits; main added `cap:` and `gate:` blocks (and `fold_count`, `env:` section) after this worktree was created; conflict at EOF of template
- **Fix:** Resolved conflict by keeping `cap:` and `gate:` from main (already in file from prior plans) and placing the new `backend:` block AFTER `gate:` as specified in the plan
- **Files modified:** `src/automil/templates/config.yaml.j2`
- **Verification:** `grep -E '^backend:|^cap:|^gate:' config.yaml.j2` shows all three blocks present; conflict markers absent
- **Committed in:** `e545a09` (merge commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - Blocking: merge conflict from parallel wave execution)
**Impact on plan:** Required merge into worktree to run Wave-0 tests; conflict resolution preserved all prior work (cap:/gate:/env: from 06-01) and added backend: block in correct position. No scope creep.

## Issues Encountered

- Pre-existing Wave-0 stub failures in `test_tick_cells.py` and `test_running_namespace.py` (unrelated to this plan; stubs for later plans 06-05+)
- `test_per_fold_writer.py` import error (autobench not installed in this worktree — pre-existing, out of scope)
- `test_walltime_seconds_to_timeout_min` intentionally RED (lands in 06-04 per wave-execution model)

## Known Stubs

None — this plan creates validators and config template entries, not data-rendering components. All added functionality is fully implemented.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary schema changes introduced. `_validate_slurm_directives` and `_validate_ray_backend` are purely local config validators with no I/O beyond an optional `ray.init()` advisory connect-test.

## Self-Check: PASSED

- `src/automil/templates/config.yaml.j2` — FOUND
- `src/automil/cli/check.py` — FOUND
- `.planning/phases/.../06-03-SUMMARY.md` — FOUND
- Commit `072392f` (config.yaml.j2 backend block) — FOUND
- Commit `1cc7b59` (check.py validators) — FOUND
- `test_check_rejects_todo` — GREEN
- `test_check_accepts_complete` — GREEN
- `grep -E '^backend:$' config.yaml.j2` — PASSES
- `grep -E 'walltime_seconds: 21600' config.yaml.j2` — PASSES
- `grep -E 'allow_local_fallback: true' config.yaml.j2` — PASSES
- `! grep -E '^\s*signal:' config.yaml.j2` — PASSES (no signal key in directives)
- `check_backend_isolation.py src/automil/` — OK (no violations)

## Next Phase Readiness

- 06-04 (SLURMBackend implementation) can now read `backend.slurm.walltime_seconds` and `backend.slurm.directives.*` from the defined config schema
- `_validate_slurm_directives` is importable and exercised by Wave-0 tests; 06-07 contract tests can rely on it
- Baseline preserved: 775+ tests passing (pre-existing Wave-0 stub failures excluded)

---
*Phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote*
*Completed: 2026-05-06*
