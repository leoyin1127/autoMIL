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
    """_PLANNED_MIGRATIONS lists the three forecasted Phase 1/2/3 relocations."""
    from automil import compat
    assert isinstance(compat._PLANNED_MIGRATIONS, dict)
    assert len(compat._PLANNED_MIGRATIONS) >= 3, (
        "Expected at least three forecasted entries (Phase 1 placeholder, "
        "Phase 2 backend, Phase 3 agent assets)."
    )
    # Phase 2 entry — concrete
    assert "automil.orchestrator.ExperimentOrchestrator" in compat._PLANNED_MIGRATIONS
    phase2 = compat._PLANNED_MIGRATIONS["automil.orchestrator.ExperimentOrchestrator"]
    assert phase2["owning_phase"] == 2
    assert "LocalBackend" in phase2["new_path"]
    # Phase 3 entry — concrete
    assert "automil.claude_assets" in compat._PLANNED_MIGRATIONS
    phase3 = compat._PLANNED_MIGRATIONS["automil.claude_assets"]
    assert phase3["owning_phase"] == 3
    # Phase 1 entry — placeholder
    assert any(v["owning_phase"] == 1 for v in compat._PLANNED_MIGRATIONS.values()), (
        "Expected at least one Phase 1 placeholder entry."
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
