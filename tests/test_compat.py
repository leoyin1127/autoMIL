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
    """
    from automil import compat
    assert isinstance(compat._PLANNED_MIGRATIONS, dict)
    # Phase 2 entry promoted — must NOT appear in _PLANNED_MIGRATIONS any more
    assert "automil.orchestrator.ExperimentOrchestrator" not in compat._PLANNED_MIGRATIONS, (
        "Phase 2 migration was promoted to Active aliases; should be removed from "
        "_PLANNED_MIGRATIONS per D-08 rule."
    )
    # Phase 3 entry — still planned
    assert "automil.claude_assets" in compat._PLANNED_MIGRATIONS
    phase3 = compat._PLANNED_MIGRATIONS["automil.claude_assets"]
    assert phase3["owning_phase"] == 3
    # Phase 1 placeholder entry — still planned
    assert any(v["owning_phase"] == 1 for v in compat._PLANNED_MIGRATIONS.values()), (
        "Expected at least one Phase 1 placeholder entry."
    )
    # At least 2 remaining planned entries (Phase 1 placeholder + Phase 3)
    assert len(compat._PLANNED_MIGRATIONS) >= 2, (
        "Expected at least two remaining forecasted entries (Phase 1 placeholder, Phase 3 agent assets)."
    )


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
