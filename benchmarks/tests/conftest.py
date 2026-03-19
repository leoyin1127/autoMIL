"""Shared test fixtures for autobench tests."""

import os
import sys

import pytest

# Ensure the tests directory is importable for _helpers
sys.path.insert(0, os.path.dirname(__file__))

from _helpers import make_test_ds  # noqa: E402


@pytest.fixture
def test_ds():
    """Pytest fixture returning a standard test DatasetConfig."""
    return make_test_ds()
