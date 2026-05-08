---
phase: 00-tier-2-cleanup-cli-split-compat-shim
plan: 04
subsystem: infra
tags: [compat-shim, deprecation-warnings, module-relocations, tdd]

# Dependency graph
requires:
  - phase: 00-tier-2-cleanup-cli-split-compat-shim
    provides: "00-CONTEXT.md decisions D-07 (two-section pattern), D-08 (promotion rule), D-09 (deprecation-message format)"
provides:
  - "src/automil/compat.py — two-section module: empty Active aliases + populated _PLANNED_MIGRATIONS dict"
  - "_DEPRECATION_MESSAGE_FORMAT module-level constant carrying the verbatim D-09 format string"
  - "_PLANNED_MIGRATIONS dict with three forecasted entries (Phase 1 placeholder, Phase 2 backend, Phase 3 agent assets)"
  - "tests/test_compat.py — 4 tests asserting importability, empty Active section, dict shape, and docstring format coverage"
affects:
  - phase-01-registry-layer    # promotes the TBD-Phase-1 entry once registry layout is locked
  - phase-02-backend-abc       # promotes automil.orchestrator.ExperimentOrchestrator → automil.backends.local.LocalBackend
  - phase-03-multi-runtime     # promotes automil.claude_assets → automil.agent_assets._shared + .claude

# Tech tracking
tech-stack:
  added: []  # documentation-only module; no new runtime dependencies
  patterns:
    - "Two-section compat module: live Active aliases + doc-only _PLANNED_MIGRATIONS"
    - "Promotion rule: future phase moves an entry from _PLANNED_MIGRATIONS to Active in the same commit"
    - "Deprecation warnings on USE (PEP 562 __getattr__), not on import"
    - "TDD RED → GREEN: failing tests committed first, then implementation"

key-files:
  created:
    - src/automil/compat.py
    - tests/test_compat.py
  modified: []

key-decisions:
  - "Active aliases section ships EMPTY in Phase 0 — no relocations to back-fill since cli/__init__.py re-exports `main` (D-07)"
  - "_PLANNED_MIGRATIONS is documentation-only — never imported, never executed (D-08)"
  - "Module docstring carries the verbatim D-09 deprecation-message format including the four required tokens (<old_path>, <new_path>, <N>, Update by <date>)"
  - "compat.py is NOT auto-imported from automil/__init__.py — preserves the no-barrel-re-exports convention"

patterns-established:
  - "Promotion rule: in a future phase's plan, edit compat.py to add a live alias in the Active section AND remove the corresponding _PLANNED_MIGRATIONS entry in the same commit"
  - "DeprecationWarning fires on USE not on IMPORT — implementers wrap the warning in a PEP 562 __getattr__ at module scope"
  - "Phase 0's TDD cadence: a `test(...)` RED commit precedes the `feat(...)` GREEN commit so the gate ordering is auditable in `git log`"

requirements-completed: [CLN-01, CLN-07]

# Metrics
duration: 2m
completed: 2026-05-01
---

# Phase 0 Plan 4: compat.py shim with empty Active section + populated _PLANNED_MIGRATIONS table (CLN-07)

**Two-section deprecation-shim module shipped empty-but-documented for Phase 1/2/3 future relocations, plus 4 new pytest tests covering importability and shape — zero behavioural change, zero new dependencies.**

## Performance

- **Duration:** 2m 11s
- **Started:** 2026-05-01T13:50:23Z
- **Completed:** 2026-05-01T13:52:34Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 0
- **Files created:** 2 (`src/automil/compat.py`, `tests/test_compat.py`)

## Accomplishments

- Created `src/automil/compat.py` with the two-section pattern: a documented-but-empty Active aliases section and a populated `_PLANNED_MIGRATIONS` doc table.
- Module-level constant `_DEPRECATION_MESSAGE_FORMAT` ships the verbatim D-09 format string ready for future promotions to use.
- Header docstring documents the promotion rule (D-08) and the deprecation-message format (D-09) including all four required tokens.
- `_PLANNED_MIGRATIONS` populated with the three forecasted entries: Phase 2 (`automil.orchestrator.ExperimentOrchestrator → automil.backends.local.LocalBackend`), Phase 3 (`automil.claude_assets → automil.agent_assets._shared + automil.agent_assets.claude`), and a Phase 1 `TBD-Phase-1` placeholder.
- `tests/test_compat.py` ships 4 tests covering importability with zero `DeprecationWarning`, expected entries with correct `owning_phase` values, dict-shape invariants on every entry, and verbatim docstring token coverage.
- Full test suite remains green (66 passing — 62 pre-existing + 4 new compat tests).

## Task Commits

TDD plan — task 1 produced two commits per the gate sequence.

1. **Task 1 RED — failing tests for compat.py module** — `3992f1a` (test)
2. **Task 1 GREEN — compat.py with `_PLANNED_MIGRATIONS` table** — `463dd6e` (feat)

_Note: D-20 specified "single conventional-commit `feat(compat): ...`" but the plan's `tdd="true"` task type mandates the RED/GREEN gate ordering documented in the executor-examples reference. Both commits land on the same branch with the GREEN feat commit carrying the canonical D-20 message; the leading RED test commit is additive context, not a deviation from intent._

## Files Created/Modified

- `src/automil/compat.py` (113 lines, NEW) — two-section deprecation-shim module: empty Active aliases section + populated `_PLANNED_MIGRATIONS` doc table + `_DEPRECATION_MESSAGE_FORMAT` constant.
- `tests/test_compat.py` (62 lines, NEW) — 4 tests: importability with no DeprecationWarning, expected forecasted entries, dict-shape invariants, docstring token coverage.

## The compat.py contents (verbatim)

```python
"""Backwards-compatibility shims for inter-phase module relocations (CLN-07).

This module ships in Phase 0 as scaffolding for Phase 1, Phase 2, and Phase 3
relocations. It has TWO sections:

1. **Active aliases** — live re-export shims that emit a ``DeprecationWarning``
   when the deprecated name is accessed so existing ``from automil.X import Y``
   paths keep resolving after a module move. Phase 0 ships this section
   EMPTY (D-07): no relocations happen in Phase 0 because ``cli/__init__.py``
   re-exports ``main`` and that is the only externally-imported name from the
   old ``cli.py``.

2. **``_PLANNED_MIGRATIONS``** — a documentation-only dict (D-08) listing
   relocations that future phases will perform. Each entry is keyed by the
   *old* dotted import path with a value of::

       {
           "new_path": str,        # destination dotted path
           "owning_phase": int,    # phase number that will perform the move
           "rationale": str,       # one-line "why" for the future planner
       }

   This section is **never imported, never executed**. It is a contract between
   phases — the Phase 1 / Phase 2 / Phase 3 plan author reads this dict,
   confirms the relocation is still planned, and PROMOTES the entry to Active
   in their plan's ``compat.py`` edit. After promotion, the Active section
   grows by one live shim and the entry is removed from
   ``_PLANNED_MIGRATIONS``.

## Promotion rule (D-08)

A future phase relocates ``<old_path>`` to ``<new_path>``:

1. Add a live re-export to the Active aliases section that:

   a) imports the new symbol from ``<new_path>``,
   b) re-binds it under the ``<old_path>`` name,
   c) calls
      ``warnings.warn(_DEPRECATION_MESSAGE_FORMAT.format(...), DeprecationWarning, stacklevel=2)``
      inside an ``__getattr__`` (PEP 562) so the warning fires on USE, not on
      ``import automil.compat``.

2. Remove the corresponding entry from ``_PLANNED_MIGRATIONS`` in the same
   commit so the dict stays an honest "still-planned" list.

## Deprecation-message format (D-09)

Every Active alias emits this exact format string when the deprecated name is
accessed:

    <old_path> moved to <new_path> in Phase <N>; old import retained for
    backwards-compat. Update by <date>.

The ``<date>`` is the wall-clock month-year by which the alias should be
deleted (typically the start of the next major milestone or 2 milestones after
the move). Future plan authors set this when promoting an entry.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Active aliases (D-07) — EMPTY in Phase 0
# ---------------------------------------------------------------------------
# Future phases promote entries from `_PLANNED_MIGRATIONS` below into this
# section by adding a live re-export that emits DeprecationWarning on USE.
# See module docstring for the promotion rule.
#
# Phase 0 ships zero entries: cli.py was renamed to a cli/ package and
# cli/__init__.py re-exports `main`, so `from automil.cli import main` keeps
# resolving without a compat shim.

# ---------------------------------------------------------------------------
# Deprecation-message format (D-09)
# ---------------------------------------------------------------------------
_DEPRECATION_MESSAGE_FORMAT = (
    "{old_path} moved to {new_path} in Phase {phase}; old import retained "
    "for backwards-compat. Update by {date}."
)

# ---------------------------------------------------------------------------
# _PLANNED_MIGRATIONS (D-08) — documentation-only
# ---------------------------------------------------------------------------
# Forecasted relocations. Future plan authors PROMOTE entries from here into
# the Active section above; this dict shrinks by one entry per promotion.
# NEVER imported. NEVER executed. Pure documentation.
_PLANNED_MIGRATIONS: dict[str, dict[str, object]] = {
    "automil.orchestrator.ExperimentOrchestrator": {
        "new_path": "automil.backends.local.LocalBackend",
        "owning_phase": 2,
        "rationale": (
            "BCK-02: Phase 2 ships LocalBackend as a re-export shim over the "
            "existing 750-line orchestrator code so the Backend ABC has a real "
            "implementation locked against the MockSLURM fixture."
        ),
    },
    "automil.claude_assets": {
        "new_path": "automil.agent_assets._shared + automil.agent_assets.claude",
        "owning_phase": 3,
        "rationale": (
            "MRT-01: Phase 3 reorganises agent assets so _shared/ holds the "
            "canonical SKILL.md and per-runtime subdirectories (claude/, "
            "codex/, opencode/) hold only diffs/overrides."
        ),
    },
    "TBD-Phase-1": {
        "new_path": "TBD-Phase-1",
        "owning_phase": 1,
        "rationale": (
            "Placeholder for the Phase 1 registry-layer relocation. The "
            "concrete old_path/new_path will be filled in by Phase 1's first "
            "plan once the registry module layout is committed."
        ),
    },
}
```

## The four test cases (verbatim)

| # | Test name | Assertion |
|---|-----------|-----------|
| 1 | `test_compat_imports_cleanly` | `from automil import compat` succeeds and emits zero `DeprecationWarning` (Phase 0 has no live shims). |
| 2 | `test_planned_migrations_has_expected_entries` | `_PLANNED_MIGRATIONS` is a dict with ≥3 entries; the Phase 2 key contains `LocalBackend`, the Phase 3 key is `automil.claude_assets`, and at least one entry has `owning_phase == 1`. |
| 3 | `test_planned_migrations_shape` | Every entry's value is a dict whose keys are exactly `{"new_path", "owning_phase", "rationale"}`; types are `str`, `int`, `str`. |
| 4 | `test_deprecation_message_format_documented` | The module docstring contains all four required tokens: `<old_path>`, `<new_path>`, `<N>`, `Update by <date>`. |

## The three `_PLANNED_MIGRATIONS` entries (for downstream phases to inherit)

| Old path | New path | Owning phase | Rationale (1-liner) |
|----------|----------|-------------:|---------------------|
| `automil.orchestrator.ExperimentOrchestrator` | `automil.backends.local.LocalBackend` | 2 | BCK-02 ABC re-export over the existing 750-line orchestrator. |
| `automil.claude_assets` | `automil.agent_assets._shared + automil.agent_assets.claude` | 3 | MRT-01 reorganises agent assets into `_shared` canonical + per-runtime overlays. |
| `TBD-Phase-1` | `TBD-Phase-1` | 1 | Placeholder; replaced once Phase 1's CONTEXT.md commits the registry module layout. |

## Decisions Made

None - followed plan and locked phase decisions D-07/D-08/D-09 verbatim.

## Deviations from Plan

None - plan executed exactly as written.

The plan's `tdd="true"` flag mandated the RED/GREEN sequence (test commit precedes feat commit), and that produced two commits where the original D-20 commit-cadence note ("single feat commit") implied one. The GREEN commit carries the canonical D-20 message verbatim; the RED commit is additive context. No content or behavioural deviation.

## Issues Encountered

None. Test suite stayed green at every gate (RED: 4 expected failures + 62 prior passing; GREEN: 4 new passing + 62 prior passing = 66 total).

## Verification Evidence

```text
$ uv run pytest tests/ -v 2>&1 | tail -1
============================== 66 passed in 2.70s ==============================

$ uv run python -c "from automil import compat; assert compat._PLANNED_MIGRATIONS; \
    assert len(compat._PLANNED_MIGRATIONS) >= 3; \
    assert all(set(v.keys()) == {'new_path', 'owning_phase', 'rationale'} \
               for v in compat._PLANNED_MIGRATIONS.values()); \
    print('VERIFICATION_OK')"
VERIFICATION_OK

$ grep -c "compat" src/automil/__init__.py
0

$ wc -l src/automil/compat.py tests/test_compat.py
 113 src/automil/compat.py
  62 tests/test_compat.py
```

## User Setup Required

None - no external service configuration required. compat.py is a pure-Python documentation/scaffolding module.

## Next Phase Readiness

- `compat.py` is in place and ready to receive Phase 1's first promotion (most likely the registry-layer relocation, replacing the `TBD-Phase-1` placeholder entry).
- Phase 2 backend ABC plan can promote `automil.orchestrator.ExperimentOrchestrator → automil.backends.local.LocalBackend` by appending a live shim to the Active section and removing the corresponding `_PLANNED_MIGRATIONS` entry in the same commit.
- Phase 3 multi-runtime plan can promote `automil.claude_assets → automil.agent_assets._shared + automil.agent_assets.claude` the same way.
- No blockers for downstream phases. Promotion rule is documented in the module docstring so future plan authors do not need to re-read this SUMMARY.

## Threat Flags

No new security-relevant surface introduced. compat.py is a pure-Python documentation module with one module-level dict literal and one module-level format-string constant; importing it has no side effects beyond Python's normal module load.

## Self-Check: PASSED

- FOUND: `src/automil/compat.py`
- FOUND: `tests/test_compat.py`
- FOUND: `.planning/phases/00-tier-2-cleanup-cli-split-compat-shim/00-04-SUMMARY.md`
- FOUND commit: `3992f1a` (RED — failing tests)
- FOUND commit: `463dd6e` (GREEN — compat.py implementation)

---
*Phase: 00-tier-2-cleanup-cli-split-compat-shim*
*Plan: 04*
*Completed: 2026-05-01*
