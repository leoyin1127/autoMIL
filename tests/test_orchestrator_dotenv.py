"""Coverage for orchestrator._load_dotenv quoted values, export prefix, comments (CLN-03).

Six corner cases the legacy `partition('=')` parser silently mishandled
(see .planning/codebase/CONCERNS.md §"Naive `.env` parser in orchestrator"):

1. Double- and single-quoted values keep embedded spaces and have quotes stripped.
2. `export KEY=value` produces key `KEY`, not `export KEY`.
3. Inline `# comment` after an unquoted value is dropped from the value.
4. Pre-existing `os.environ` entries are NOT overwritten (setdefault semantic).
5. `<root>/.env` is searched before `<root>/benchmarks/.env` (first writer wins).
6. Missing files are silently ignored — constructor never raises.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from automil.orchestrator import ExperimentOrchestrator


def _write_env(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)


@pytest.fixture
def orch_factory(tmp_path, monkeypatch):
    """Build an orchestrator pointed at tmp_path with a minimal automil/ skeleton.

    Returns (factory_callable, project_root_path). Calling the factory
    constructs a fresh ExperimentOrchestrator whose `__init__` invokes
    `_load_dotenv` against `tmp_path`.
    """
    automil_dir = tmp_path / "automil"
    automil_dir.mkdir()
    (automil_dir / "config.yaml").write_text("orchestrator:\n  poll_interval_sec: 5\n")
    (tmp_path / ".git").mkdir()  # so _find_git_root succeeds if walked

    def _factory():
        return ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)

    return _factory, tmp_path


def test_quoted_values(orch_factory, monkeypatch):
    """Double- and single-quoted values keep embedded spaces; quotes are stripped."""
    factory, root = orch_factory
    _write_env(
        root / ".env",
        'QUOTED_DOUBLE="hello world"\nQUOTED_SINGLE=\'single\'\n',
    )
    monkeypatch.delenv("QUOTED_DOUBLE", raising=False)
    monkeypatch.delenv("QUOTED_SINGLE", raising=False)
    factory()  # Constructor calls _load_dotenv
    assert os.environ.get("QUOTED_DOUBLE") == "hello world"
    assert os.environ.get("QUOTED_SINGLE") == "single"


def test_export_prefix(orch_factory, monkeypatch):
    """A line `export KEY=value` produces key `KEY`, not `export KEY`."""
    factory, root = orch_factory
    _write_env(root / ".env", "export EXPORTED_KEY=exported_value\n")
    monkeypatch.delenv("EXPORTED_KEY", raising=False)
    monkeypatch.delenv("export EXPORTED_KEY", raising=False)
    factory()
    assert os.environ.get("EXPORTED_KEY") == "exported_value"
    assert "export EXPORTED_KEY" not in os.environ


def test_no_override_existing_env(orch_factory, monkeypatch):
    """Pre-existing env vars are NOT overwritten — setdefault semantic."""
    factory, root = orch_factory
    _write_env(root / ".env", "PREEXISTING=from_dotenv\n")
    monkeypatch.setenv("PREEXISTING", "from_shell")
    factory()
    assert os.environ.get("PREEXISTING") == "from_shell"


def test_search_order_root_then_benchmarks(orch_factory, monkeypatch):
    """`<root>/.env` is loaded BEFORE `<root>/benchmarks/.env`; first writer wins."""
    factory, root = orch_factory
    _write_env(root / ".env", "OVERLAP=root_wins\n")
    _write_env(
        root / "benchmarks" / ".env",
        "OVERLAP=benchmarks_loses\nONLY_BENCH=ok\n",
    )
    monkeypatch.delenv("OVERLAP", raising=False)
    monkeypatch.delenv("ONLY_BENCH", raising=False)
    factory()
    assert os.environ.get("OVERLAP") == "root_wins"
    assert os.environ.get("ONLY_BENCH") == "ok"


def test_missing_files_is_noop(orch_factory):
    """Missing `.env` AND `benchmarks/.env` is a silent no-op — no exception."""
    factory, _ = orch_factory
    factory()  # Must not raise


def test_comment_after_value(orch_factory, monkeypatch):
    """Inline `# comment` after an unquoted value is stripped from the value.

    The legacy parser kept `actual_value  # trailing` as the entire value.
    python-dotenv strips the inline comment, leaving only `actual_value`.
    """
    factory, root = orch_factory
    _write_env(root / ".env", "COMMENTED=actual_value  # trailing\n")
    monkeypatch.delenv("COMMENTED", raising=False)
    factory()
    assert os.environ.get("COMMENTED") == "actual_value"
