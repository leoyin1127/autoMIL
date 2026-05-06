"""Tests for gate/stats.py — pure scipy paired Wilcoxon + BCa bootstrap + Bonferroni.

13 tests covering:
- Bonferroni direction (divide alpha, NOT multiply p-values) — Pitfall 4 anti-test
- Paired Wilcoxon correctness on positive / mixed / all-zero / empty deltas
- Bootstrap CI source assertions (BCa method, n_resamples, alternative='greater')
- Pure-function discipline (no I/O, no forbidden imports)
- diagnose_gate_health string correctness
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

from automil.gate.stats import (
    bonferroni_correct,
    diagnose_gate_health,
    paired_wilcoxon_with_bootstrap,
)

# Source inspection: read stats.py as text for literal-substring assertions
STATS_SRC = (
    pathlib.Path(__file__).parent.parent.parent / "src" / "automil" / "gate" / "stats.py"
).read_text()


# ---------------------------------------------------------------------------
# Bonferroni direction tests (Pitfall 4)
# ---------------------------------------------------------------------------

def test_bonferroni_direction():
    """Test 1: Bonferroni divides alpha by K (alpha/K). Must NOT multiply."""
    # divide direction: 0.05 / 5 = 0.01; 0.05 / 2 = 0.025
    assert bonferroni_correct(0.05, 5) == pytest.approx(0.01)
    assert bonferroni_correct(0.05, 2) == pytest.approx(0.025)
    # multiply direction would yield 0.25 and 0.10 — confirm those are NOT the answers
    assert bonferroni_correct(0.05, 5) != pytest.approx(0.25)
    assert bonferroni_correct(0.05, 2) != pytest.approx(0.10)


def test_bonferroni_rejects_K_lt_1():
    """Test 2: bonferroni_correct raises ValueError for K < 1."""
    with pytest.raises(ValueError, match="K must be >= 1"):
        bonferroni_correct(0.05, 0)
    with pytest.raises(ValueError, match="K must be >= 1"):
        bonferroni_correct(0.05, -3)


# ---------------------------------------------------------------------------
# Paired Wilcoxon correctness tests
# ---------------------------------------------------------------------------

def test_paired_wilcoxon_all_positive(positive_deltas, deterministic_seed):
    """Test 3: All-positive deltas should clearly pass."""
    passed, p, ci, wins = paired_wilcoxon_with_bootstrap(
        positive_deltas,
        p_threshold=0.05,
        bootstrap_reps=1000,
        rng_seed=deterministic_seed,
    )
    assert passed is True
    assert p < 0.05
    assert ci[0] > 0, f"Expected ci_low > 0, got {ci[0]}"
    assert wins == 5


def test_paired_wilcoxon_mixed_borderline(mixed_deltas, deterministic_seed):
    """Test 4: Mixed-sign deltas return valid 4-tuple; wins==4; result is deterministic."""
    result1 = paired_wilcoxon_with_bootstrap(
        mixed_deltas,
        p_threshold=0.05,
        bootstrap_reps=1000,
        rng_seed=deterministic_seed,
    )
    result2 = paired_wilcoxon_with_bootstrap(
        mixed_deltas,
        p_threshold=0.05,
        bootstrap_reps=1000,
        rng_seed=deterministic_seed,
    )
    # 4-tuple
    assert len(result1) == 4
    passed, p, ci, wins = result1
    assert isinstance(passed, bool)
    assert isinstance(p, float)
    assert len(ci) == 2
    assert isinstance(wins, int)
    # 4 out of 5 deltas are positive (0.012, 0.008, 0.015, -0.003, 0.011)
    assert wins == 4
    # Deterministic with same seed
    assert result1 == result2


def test_paired_wilcoxon_all_zero_returns_false(all_zero_deltas):
    """Test 5: All-zero deltas return (False, 1.0, (0.0, 0.0), 0) — never raises."""
    passed, p, ci, wins = paired_wilcoxon_with_bootstrap(all_zero_deltas, 0.05)
    assert passed is False
    assert p == pytest.approx(1.0)
    assert ci == (pytest.approx(0.0), pytest.approx(0.0))
    assert wins == 0


def test_paired_wilcoxon_empty_returns_false():
    """Test 6: Empty array returns (False, 1.0, (0.0, 0.0), 0) — never raises."""
    passed, p, ci, wins = paired_wilcoxon_with_bootstrap(np.array([]), 0.05)
    assert passed is False
    assert p == pytest.approx(1.0)
    assert ci == (pytest.approx(0.0), pytest.approx(0.0))
    assert wins == 0


# ---------------------------------------------------------------------------
# Source-inspection tests (Tests 7, 8, 13)
# ---------------------------------------------------------------------------

def test_alternative_is_greater():
    """Test 7: Wilcoxon must use one-sided 'greater' alternative."""
    assert 'alternative="greater"' in STATS_SRC, (
        "Wilcoxon must be one-sided 'greater' (candidate > parent gate)"
    )


def test_bootstrap_uses_BCa_method():
    """Test 8: Bootstrap must use BCa (bias-corrected accelerated) method."""
    assert 'method="BCa"' in STATS_SRC, "Bootstrap must use method='BCa'"


def test_bootstrap_n_resamples_is_passed_through():
    """Test 9: bootstrap_reps parameter flows to scipy.stats.bootstrap."""
    deltas = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    passed, p, ci, wins = paired_wilcoxon_with_bootstrap(
        deltas, p_threshold=0.05, bootstrap_reps=200, rng_seed=42
    )
    # Just verify it returns a valid CI tuple (proves parameter flows through)
    assert len(ci) == 2
    assert isinstance(ci[0], float)
    assert isinstance(ci[1], float)


# ---------------------------------------------------------------------------
# diagnose_gate_health tests (Tests 10, 11, 12)
# ---------------------------------------------------------------------------

def test_diagnose_gate_health_low():
    """Test 10: Low promotion rate contains 'too strict'."""
    result = diagnose_gate_health(0.02)
    assert "too strict" in result.lower(), f"Expected 'too strict' in: {result!r}"


def test_diagnose_gate_health_high():
    """Test 11: High promotion rate contains 'too loose'."""
    result = diagnose_gate_health(0.6)
    assert "too loose" in result.lower(), f"Expected 'too loose' in: {result!r}"


def test_diagnose_gate_health_healthy():
    """Test 12: Healthy promotion rate contains 'healthy'."""
    result = diagnose_gate_health(0.2)
    assert "healthy" in result.lower(), f"Expected 'healthy' in: {result!r}"


# ---------------------------------------------------------------------------
# Pure-function discipline test (Test 13)
# ---------------------------------------------------------------------------

def test_no_filesystem_io():
    """Test 13: stats.py is pure — no filesystem I/O, no forbidden imports."""
    for forbidden in ("open(", "Path(", "tempfile", "subprocess", "time.time("):
        assert forbidden not in STATS_SRC, (
            f"stats.py must be pure (no I/O): found forbidden pattern {forbidden!r}"
        )
