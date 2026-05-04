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

import warnings as _warnings

# ---------------------------------------------------------------------------
# Active aliases (D-07)
# ---------------------------------------------------------------------------
# Future phases promote entries from `_PLANNED_MIGRATIONS` below into this
# section by adding a live re-export that emits DeprecationWarning on USE.
# See module docstring for the promotion rule.
#
# Phase 0 ships zero entries: cli.py was renamed to a cli/ package and
# cli/__init__.py re-exports `main`, so `from automil.cli import main` keeps
# resolving without a compat shim.
#
# Phase 2 (D-60): automil.orchestrator.ExperimentOrchestrator ->
#   automil.backends._orchestrator_daemon.ExperimentOrchestrator
# The full re-export shim lives at src/automil/orchestrator.py (the old path);
# existing `from automil.orchestrator import ExperimentOrchestrator` call sites
# continue to resolve via that shim. See also Plan 02-04.

# --- Active deprecated path: automil.claude_assets (promoted Phase 3 / D-88) ---
def __getattr__(name: str):
    """PEP 562: redirect automil.claude_assets.* imports to automil.agent_assets (D-88)."""
    # WR-01 pattern: short-circuit dunder probes BEFORE issuing DeprecationWarning.
    # The import machinery and pytest collection probe __path__, __spec__, etc.
    # on every module access; warning on each one floods the test output.
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    _warnings.warn(
        _DEPRECATION_MESSAGE_FORMAT.format(
            old_path=f"automil.claude_assets.{name}",
            new_path="automil.agent_assets._shared or automil.agent_assets.claude",
            phase=3,
            date="2027-06",
        ),
        DeprecationWarning,
        stacklevel=2,
    )
    # Attempt to redirect to agent_assets equivalent
    import importlib as _importlib
    try:
        return _importlib.import_module(f"automil.agent_assets.{name}")
    except ModuleNotFoundError:
        raise AttributeError(
            f"automil.claude_assets.{name!r} has no equivalent in automil.agent_assets; "
            f"check the Phase 3 migration guide."
        )

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
    # NOTE: "automil.orchestrator.ExperimentOrchestrator" was promoted to Active
    # in Phase 2 (Plan 02-04 / D-60). Removed from this dict per the D-08 rule.
    # NOTE: "automil.claude_assets" was promoted to Active in Phase 3 (Plan 03-02
    # / D-88). The live __getattr__ shim is in the Active aliases section above.
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
