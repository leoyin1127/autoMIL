"""automil trajectory record CLI tests (TRJ-04 / D-94)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from automil.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


def _valid_event() -> str:
    return json.dumps({
        "gen_ai.provider.name":   "claude-code",
        "gen_ai.event.name":      "tool_call",
        "gen_ai.event.timestamp": "2026-05-03T00:00:00.000000Z",
        "gen_ai.tool.name":       "Bash",
    })


def test_record_cli_exits_0_on_valid_event(tmp_path: Path, cli_runner: CliRunner, monkeypatch) -> None:
    """Valid event exits 0 (success)."""
    automil_dir = tmp_path / "automil"
    (automil_dir / "archive").mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOMIL_NODE_ID", "node_0001")
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    monkeypatch.setenv("AUTOMIL_DIR", str(automil_dir))
    result = cli_runner.invoke(main, ["trajectory", "record", _valid_event()])
    assert result.exit_code == 0, result.output


def test_record_cli_exits_0_on_soft_fail(tmp_path: Path, cli_runner: CliRunner, monkeypatch) -> None:
    """Recorder soft-fail exits 0 (not a user error per D-94)."""
    automil_dir = tmp_path / "automil"
    (automil_dir / "archive").mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOMIL_NODE_ID", "node_0001")
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    monkeypatch.setenv("AUTOMIL_DIR", str(automil_dir))
    # Bad event (missing required fields) -- record_event returns False (soft-fail)
    bad_event = json.dumps({"gen_ai.tool.name": "Bash"})
    result = cli_runner.invoke(main, ["trajectory", "record", bad_event])
    assert result.exit_code == 0  # soft-fail = exit 0


def test_record_cli_exits_1_on_json_parse_error(cli_runner: CliRunner, monkeypatch) -> None:
    """JSON parse error exits 1 (hard error per D-94)."""
    monkeypatch.setenv("AUTOMIL_NODE_ID", "node_0001")
    result = cli_runner.invoke(main, ["trajectory", "record", "not-valid-json{{{"])
    assert result.exit_code == 1


def test_record_cli_exits_1_on_missing_node_id(cli_runner: CliRunner, monkeypatch) -> None:
    """Missing AUTOMIL_NODE_ID exits 1 (hard error per D-94)."""
    monkeypatch.delenv("AUTOMIL_NODE_ID", raising=False)
    result = cli_runner.invoke(main, ["trajectory", "record", _valid_event()])
    assert result.exit_code == 1
