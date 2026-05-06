"""Coverage for src/automil/compat.py: empty Active section + populated _PLANNED_MIGRATIONS (CLN-07)."""
from __future__ import annotations

import warnings


def test_compat_imports_cleanly():
    """compat.py must import without raising (Phase 0 ships zero live shims)."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from automil import compat  # noqa: F401
    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecation_warnings == [], (
        f"Phase 0 compat.py must emit zero DeprecationWarnings on import; got: "
        f"{[str(w.message) for w in deprecation_warnings]}"
    )


def test_planned_migrations_has_expected_entries():
    """_PLANNED_MIGRATIONS lists the remaining forecasted relocations.

    Phase 2 (Plan 02-04 / D-60): the orchestrator.ExperimentOrchestrator entry
    was PROMOTED to Active (see compat.py Active aliases section) — it is no
    longer in _PLANNED_MIGRATIONS per the D-08 promotion rule.

    Phase 3 (Plan 03-02 / D-88): the automil.claude_assets entry was PROMOTED
    to Active — a live __getattr__ shim now handles the redirect. It must NOT
    appear in _PLANNED_MIGRATIONS per the D-08 rule.
    """
    from automil import compat
    assert isinstance(compat._PLANNED_MIGRATIONS, dict)
    # Phase 2 entry promoted — must NOT appear in _PLANNED_MIGRATIONS any more
    assert "automil.orchestrator.ExperimentOrchestrator" not in compat._PLANNED_MIGRATIONS, (
        "Phase 2 migration was promoted to Active aliases; should be removed from "
        "_PLANNED_MIGRATIONS per D-08 rule."
    )
    # Phase 3 entry promoted — must NOT appear in _PLANNED_MIGRATIONS any more (D-88)
    assert "automil.claude_assets" not in compat._PLANNED_MIGRATIONS, (
        "Phase 3 migration (automil.claude_assets -> automil.agent_assets) was promoted "
        "to Active aliases in Plan 03-02; should be removed from _PLANNED_MIGRATIONS per D-08 rule."
    )
    # Phase 1 placeholder entry — still planned
    assert any(v["owning_phase"] == 1 for v in compat._PLANNED_MIGRATIONS.values()), (
        "Expected at least one Phase 1 placeholder entry."
    )
    # At least 1 remaining planned entry (Phase 1 placeholder; Phase 3 was promoted)
    assert len(compat._PLANNED_MIGRATIONS) >= 1, (
        "Expected at least one remaining forecasted entry (Phase 1 placeholder)."
    )


def test_claude_assets_shim_emits_deprecation_warning():
    """Accessing automil.compat.claude_assets emits a DeprecationWarning (D-88, D-09).

    Phase 3 promoted automil.claude_assets from _PLANNED_MIGRATIONS to a live
    __getattr__ shim. This test verifies the shim fires a DeprecationWarning
    on USE (attribute access), not on import.
    """
    import sys

    # Remove compat from sys.modules to get a fresh import
    for key in list(sys.modules.keys()):
        if key == "automil.compat":
            del sys.modules[key]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from automil import compat as fresh_compat  # noqa: F401
    # Importing compat itself must NOT emit DeprecationWarning (warning fires on USE, not import)
    import_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert import_warnings == [], (
        f"compat.py must emit zero DeprecationWarnings on import; got: "
        f"{[str(w.message) for w in import_warnings]}"
    )

    # Accessing fresh_compat.claude_assets triggers the __getattr__ shim (D-88)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            _ = fresh_compat.claude_assets  # noqa: F841
        except AttributeError:
            pass  # expected if automil.agent_assets.claude_assets submodule does not exist
    deprecation_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecation_warnings) == 1, (
        f"Expected exactly 1 DeprecationWarning when accessing compat.claude_assets; "
        f"got {len(deprecation_warnings)}: {[str(w.message) for w in deprecation_warnings]}"
    )
    msg = str(deprecation_warnings[0].message)
    assert "claude_assets" in msg, f"DeprecationWarning must mention 'claude_assets'; got: {msg!r}"
    assert "agent_assets" in msg, f"DeprecationWarning must mention 'agent_assets'; got: {msg!r}"
    assert "2027" in msg, f"DeprecationWarning must mention a removal date (2027); got: {msg!r}"


def test_planned_migrations_shape():
    """Every entry has the required keys + value types."""
    from automil import compat
    for old_path, entry in compat._PLANNED_MIGRATIONS.items():
        assert isinstance(old_path, str)
        assert isinstance(entry, dict)
        assert set(entry.keys()) == {"new_path", "owning_phase", "rationale"}, (
            f"Entry {old_path!r} has unexpected keys: {entry.keys()}"
        )
        assert isinstance(entry["new_path"], str)
        assert isinstance(entry["owning_phase"], int)
        assert isinstance(entry["rationale"], str)


def test_deprecation_message_format_documented():
    """The verbatim D-09 format string is documented in compat.py."""
    from automil import compat
    # The format must mention every required token.
    text = compat.__doc__ or ""
    for token in ["<old_path>", "<new_path>", "<N>", "Update by <date>"]:
        assert token in text, f"Module docstring missing required token {token!r}"
