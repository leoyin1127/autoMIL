"""Tests for BACKENDS registry + @register decorator + _clear_backends (BCK-01 / D-68).

Plan 02-02 coverage:
- Happy-path registration populates BACKENDS dict
- Non-Backend class raises BackendError
- Duplicate name raises BackendError
- _clear_backends() empties the BACKENDS dict

Pattern: autouse fixture calls _clear_backends() after each test to prevent
cross-test pollution (mirrors PATTERNS.md §11 registry isolation pattern).
"""
from __future__ import annotations

import pytest

from automil.backends import BACKENDS, BackendError, _clear_backends, register
from automil.backends.base import Backend, JobHandle, JobSpec, JobState


# ---------------------------------------------------------------------------
# Isolation fixture (PATTERNS.md §11)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_registry():
    """Clear BACKENDS before and after every test in this file."""
    _clear_backends()
    yield
    _clear_backends()


# ---------------------------------------------------------------------------
# Minimal concrete Backend for testing (not registered at module load)
# ---------------------------------------------------------------------------

def _make_backend_class(name: str = "TestBackend") -> type:
    """Return a new concrete Backend subclass with stub implementations."""

    class _Stub(Backend):
        def submit(self, spec: JobSpec) -> JobHandle:  # type: ignore[override]
            raise NotImplementedError

        def poll(self, handle: JobHandle) -> JobState:  # type: ignore[override]
            raise NotImplementedError

        def list_running(self) -> list[JobHandle]:  # type: ignore[override]
            return []

        def cancel(self, handle: JobHandle, signal=None) -> None:  # type: ignore[override]
            pass

        def log_iter(self, handle: JobHandle):  # type: ignore[override]
            return iter([])

    _Stub.__name__ = name
    _Stub.__qualname__ = name
    return _Stub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_backend_happy_path():
    """@register populates BACKENDS with the decorated class."""
    TestBackend = _make_backend_class("TestBackend")

    decorated = register("test_backend")(TestBackend)

    assert "test_backend" in BACKENDS
    assert BACKENDS["test_backend"] is TestBackend
    # Decorator returns the class unchanged (identity preserved)
    assert decorated is TestBackend


def test_register_non_backend_raises():
    """Registering a class that does not subclass Backend raises BackendError."""

    class NotABackend:
        pass

    with pytest.raises(BackendError, match="must subclass Backend"):
        register("bad_backend")(NotABackend)

    # Registry must remain clean
    assert "bad_backend" not in BACKENDS


def test_register_duplicate_raises():
    """Registering the same name twice raises BackendError."""
    First = _make_backend_class("FirstBackend")
    Second = _make_backend_class("SecondBackend")

    register("dup_backend")(First)

    with pytest.raises(BackendError, match="already registered"):
        register("dup_backend")(Second)

    # Original registration is preserved
    assert BACKENDS["dup_backend"] is First


def test_clear_backends_helper():
    """_clear_backends() empties the BACKENDS dict."""
    Backend1 = _make_backend_class("Backend1")
    Backend2 = _make_backend_class("Backend2")

    register("b1")(Backend1)
    register("b2")(Backend2)
    assert len(BACKENDS) == 2

    _clear_backends()

    assert len(BACKENDS) == 0
    assert "b1" not in BACKENDS
    assert "b2" not in BACKENDS
