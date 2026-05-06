"""Runtime declaration module tests (TRJ-04 / D-87)."""
from __future__ import annotations

import pytest


def test_get_runtime_returns_env_var(monkeypatch) -> None:
    """When AUTOMIL_RUNTIME is set, get_runtime() returns it unchanged."""
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    from automil.runtime import get_runtime
    assert get_runtime() == "claude-code"


def test_get_runtime_opencode(monkeypatch) -> None:
    """get_runtime() works for opencode value."""
    monkeypatch.setenv("AUTOMIL_RUNTIME", "opencode")
    from automil.runtime import get_runtime
    assert get_runtime() == "opencode"


def test_get_runtime_returns_unknown_when_unset(monkeypatch) -> None:
    """When AUTOMIL_RUNTIME is not set, get_runtime() returns 'unknown'."""
    monkeypatch.delenv("AUTOMIL_RUNTIME", raising=False)
    from automil.runtime import get_runtime
    assert get_runtime() == "unknown"


def test_get_runtime_is_case_sensitive(monkeypatch) -> None:
    """AUTOMIL_RUNTIME is case-sensitive — wrong-case returns as-is (not normalised)."""
    monkeypatch.setenv("AUTOMIL_RUNTIME", "Claude-Code")  # wrong case
    from automil.runtime import get_runtime
    result = get_runtime()
    # Returns the env var exactly as set — does NOT normalise to "claude-code"
    assert result == "Claude-Code"
    assert result != "claude-code"


def test_get_runtime_deepseek_via_opencode(monkeypatch) -> None:
    """Deepseek routing values pass through unchanged."""
    monkeypatch.setenv("AUTOMIL_RUNTIME", "deepseek-via-opencode")
    from automil.runtime import get_runtime
    assert get_runtime() == "deepseek-via-opencode"


def test_get_runtime_never_infers(monkeypatch) -> None:
    """get_runtime() reads env var only — no sys.argv or package inspection (D-87)."""
    import sys
    monkeypatch.delenv("AUTOMIL_RUNTIME", raising=False)
    # Even if we manipulate sys.argv[0] to look like a runtime, get_runtime stays "unknown"
    original_argv = sys.argv[:]
    try:
        sys.argv[0] = "claude"
        from automil.runtime import get_runtime
        assert get_runtime() == "unknown"
    finally:
        sys.argv[:] = original_argv
