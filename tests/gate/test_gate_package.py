"""Tests for the gate package skeleton (05-01 Task 1 — package import + __all__).

TDD RED phase: these tests will fail until src/automil/gate/__init__.py exists.
"""
from __future__ import annotations


def test_import_three_stats_symbols():
    """Test 1: Three symbols importable from automil.gate."""
    from automil.gate import (  # noqa: F401
        bonferroni_correct,
        diagnose_gate_health,
        paired_wilcoxon_with_bootstrap,
    )


def test_all_is_alphabetically_sorted_and_contains_three_symbols():
    """Test 2: __all__ is alphabetically sorted and contains the three symbols."""
    import automil.gate as gate
    assert hasattr(gate, "__all__"), "__all__ must be defined on automil.gate"
    all_list = gate.__all__
    required = {"bonferroni_correct", "diagnose_gate_health", "paired_wilcoxon_with_bootstrap"}
    assert required.issubset(set(all_list)), f"__all__ missing symbols: {required - set(all_list)}"
    # Verify alphabetical order
    assert all_list == sorted(all_list), f"__all__ must be alphabetically sorted, got: {all_list}"
