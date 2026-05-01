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
