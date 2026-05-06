"""Shared fixtures for tests/gate/ (Phase 5 — GTE-01..06).

Pattern mirrors tests/cells/conftest.py: tmp_path-based, no real backend,
deterministic via rng_seed=42.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pytest


@pytest.fixture
def deterministic_seed() -> int:
    """Seed for scipy.stats.bootstrap rng to keep CI bounds reproducible."""
    return 42


@pytest.fixture
def positive_deltas() -> np.ndarray:
    """K=5 candidate-better-than-parent deltas — clear pass case."""
    return np.array([0.020, 0.015, 0.010, 0.025, 0.018])


@pytest.fixture
def mixed_deltas() -> np.ndarray:
    """K=5 mixed-sign deltas — typical near-threshold case."""
    return np.array([0.012, 0.008, 0.015, -0.003, 0.011])


@pytest.fixture
def all_zero_deltas() -> np.ndarray:
    """K=4 all-equal deltas — wilcoxon edge case (would raise; gate must handle)."""
    return np.zeros(4)
