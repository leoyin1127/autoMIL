---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: 02
subsystem: runtime
tags: [signal-handler, sigterm, runtime-helpers, fold-count, cells, cap]

requires:
  - phase: 03-trajectory-capture
    provides: "module header style (runtime.py pattern), lazy-import discipline"

provides:
  - "automil.runtime_helpers.register_sigterm_flush() — idempotent SIGTERM handler installer"
  - "automil.runtime_helpers.get_fold_count() — AUTOMIL_FOLD_COUNT env reader with 5 fallback"
  - "automil.cells package scaffold (__init__.py + reconcile.py)"
  - "automil.cells.reconcile.aggregate_folds() — pure fold aggregation per D-119"

affects:
  - 04-05 (reconcile.py full implementation — builds on cells package scaffold)
  - 04-06 (daemon tick — composes with SIGTERM flush via returncode=0)
  - 04-11 (integration test — fires register_sigterm_flush() end-to-end)

tech-stack:
  added: []
  patterns:
    - "Module-level _SIGTERM_REGISTERED bool guard for idempotent signal handler registration"
    - "Lazy import inside signal handler body — keeps module importable before dependency lands"
    - "sys.exit(0) for graceful SIGTERM flush — daemon distinguishes 0 (flush) from non-zero (kill)"
    - "aggregate_folds() pure function — reads fold_*_result.json from directory, returns result dict"

key-files:
  created:
    - src/automil/runtime_helpers.py
    - src/automil/cells/__init__.py
    - src/automil/cells/reconcile.py
    - tests/cells/__init__.py
    - tests/cells/test_runtime_helpers.py
  modified: []

key-decisions:
  - "sys.exit(0) NOT 130 in SIGTERM handler — returncode 0 signals graceful flush to daemon (D-121)"
  - "Lazy import of aggregate_folds inside _handler body — allows runtime_helpers to be imported in Wave 1 before cells.reconcile is fully implemented"
  - "cells package scaffolded early (Rule 3) — subprocess Test 4 needs aggregate_folds resolvable at call time; plan says handler needs it AT CALL TIME, so scaffold lands here"
  - "aggregate_folds() pure function in cells/reconcile.py — no I/O side effects, all callers write result.json themselves"

patterns-established:
  - "Signal handler idempotency via module-level bool guard: _SIGTERM_REGISTERED = False"
  - "Subprocess-based signal handler test: Popen + send_signal(SIGTERM) + communicate + assert returncode==0"
  - "Fold aggregation contract: 0 folds → crashed, 1..K-1 folds → partial, K folds → completed"

requirements-completed: [CAP-03]

duration: 12min
completed: 2026-05-05
---

# Phase 4 Plan 02: runtime_helpers — SIGTERM flush helper and fold count accessor

**SIGTERM handler (register_sigterm_flush) with sys.exit(0) flush contract and aggregate_folds pure function bootstrapping the cells package**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-05T00:00:00Z
- **Completed:** 2026-05-05T00:12:00Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 5 created

## Accomplishments

- `register_sigterm_flush()` installs a SIGTERM handler that aggregates fold files, writes result.json, and exits 0 — not 130 — so the daemon sees a graceful completion
- `get_fold_count()` reads AUTOMIL_FOLD_COUNT env var with fallback 5; idempotency guard via `_SIGTERM_REGISTERED` module-level bool
- `automil.cells` package scaffolded (cells/__init__.py + reconcile.py with full aggregate_folds implementation per D-119)
- All 4 TDD tests green including subprocess Test 4 which fires the full SIGTERM chain; 391-test baseline preserved

## Task Commits

Each task was committed atomically:

1. **Task 1: Write tests/cells/test_runtime_helpers.py (RED)** - `6487643` (test)
2. **Task 2: Implement src/automil/runtime_helpers.py (GREEN)** - `67e9184` (feat)

_TDD plan: RED commit then GREEN commit_

## Files Created/Modified

- `src/automil/runtime_helpers.py` — register_sigterm_flush(), get_fold_count(), _SIGTERM_REGISTERED guard
- `src/automil/cells/__init__.py` — cells package header (scaffold for Phase 4 plans 03–10)
- `src/automil/cells/reconcile.py` — aggregate_folds() pure function per D-119: 0 folds → crashed, partial → partial, all → completed
- `tests/cells/__init__.py` — empty, mirrors tests/trajectory/__init__.py pattern
- `tests/cells/test_runtime_helpers.py` — 4 tests: default fold count, env-override, idempotency, subprocess SIGTERM chain

## Decisions Made

- `sys.exit(0)` in handler (NOT 130): daemon's `_handle_completion` distinguishes returncode 0 (graceful flush) from non-zero (killed-before-flush). This is load-bearing for CAP-04 reconciliation (D-121).
- Lazy import of `aggregate_folds` inside `_handler` body: keeps `runtime_helpers` importable in Wave 1 before `cells.reconcile` is fully populated; the handler only needs the import resolvable at CALL TIME (when SIGTERM actually fires, well after Wave 2 in a real run).
- `cells` package scaffolded in this plan (Rule 3 deviation): Test 4 fires the handler in a subprocess, which needs `aggregate_folds` importable at subprocess start. The full implementation follows D-119 exactly so Plan 04-05 merely needs to add reconcile_budget_kill() rather than rewrite aggregate_folds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Scaffolded automil.cells package with aggregate_folds early**
- **Found during:** Task 2 (GREEN — implementing runtime_helpers.py)
- **Issue:** Test 4 spawns a subprocess that registers the SIGTERM handler, sleeps 30s, receives SIGTERM. The handler calls `from automil.cells.reconcile import aggregate_folds` at runtime. If the cells package doesn't exist, the subprocess exits non-zero, Test 4 fails, and the GREEN acceptance criteria ("all 4 tests pass") cannot be met. The plan states cells.reconcile "lands in Plan 04-05" but also requires all 4 tests green in this plan.
- **Fix:** Created `src/automil/cells/__init__.py` (package scaffold header) and `src/automil/cells/reconcile.py` with the full `aggregate_folds()` implementation per D-119. The implementation is not a stub — it follows the D-119 spec exactly (0 folds → crashed, 1..K-1 → partial, K → completed; per-key metric mean; max VRAM; sum elapsed). Plan 04-05 will add `reconcile_budget_kill()` to this module.
- **Files modified:** src/automil/cells/__init__.py (new), src/automil/cells/reconcile.py (new)
- **Verification:** Test 4 subprocess fires SIGTERM, exits 0, writes result.json with status=partial, partial_folds=2, expected_folds=5. All 4 tests pass.
- **Committed in:** 67e9184 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking)
**Impact on plan:** Necessary for Test 4 to be executable. The cells scaffold follows the D-119 spec verbatim so Plan 04-05 adds on top rather than replacing anything.

## Issues Encountered

None beyond the Rule 3 blocking issue documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `automil.runtime_helpers` is fully functional; training scripts can call `register_sigterm_flush()` at startup
- `automil.cells.reconcile.aggregate_folds()` is implemented per D-119 spec — Plan 04-05 adds `reconcile_budget_kill()` on top
- `automil.cells` package is scaffolded — Plans 04-01 (state + registry), 04-03 (cap state machine), 04-04 (cap tests) can all create their modules inside `src/automil/cells/`
- 391-test baseline preserved; no regressions

## Threat Flags

No new network endpoints, auth paths, or unexpected trust boundaries introduced. The SIGTERM handler reads only local fold files and writes only result.json to CWD — consistent with the threat model in the plan (T-04-04, T-04-05, T-04-06).

## Self-Check: PASSED

Files verified:
- `src/automil/runtime_helpers.py` — FOUND
- `src/automil/cells/__init__.py` — FOUND
- `src/automil/cells/reconcile.py` — FOUND
- `tests/cells/__init__.py` — FOUND
- `tests/cells/test_runtime_helpers.py` — FOUND

Commits verified:
- `6487643` (test RED) — FOUND
- `67e9184` (feat GREEN) — FOUND

Test results: 4/4 cells tests pass; 391/391 full suite passes.

---
*Phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation*
*Completed: 2026-05-05*
