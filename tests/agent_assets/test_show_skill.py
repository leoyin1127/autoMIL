"""show-skill command integration tests (MRT-04 / D-93)."""
from __future__ import annotations

import pytest
from click.testing import CliRunner

from automil.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_show_skill_claude_stdout(cli_runner: CliRunner) -> None:
    """show-skill --runtime claude prints SKILL.md content to stdout."""
    result = cli_runner.invoke(main, ["show-skill", "--runtime", "claude"])
    assert result.exit_code == 0, result.output
    # Output must contain markdown content (at least an H1 title)
    assert "#" in result.output
    assert len(result.output) > 20  # non-empty


def test_show_skill_opencode_stdout(cli_runner: CliRunner) -> None:
    """show-skill --runtime opencode prints content to stdout."""
    result = cli_runner.invoke(main, ["show-skill", "--runtime", "opencode"])
    assert result.exit_code == 0, result.output
    assert "#" in result.output


def test_show_skill_agents_asset(cli_runner: CliRunner) -> None:
    """show-skill --asset AGENTS prints AGENTS.md content."""
    result = cli_runner.invoke(main, ["show-skill", "--runtime", "claude", "--asset", "AGENTS"])
    assert result.exit_code == 0, result.output
    assert "automil submit" in result.output  # universal instruction from _shared/AGENTS.md


def test_show_skill_no_write_side_effects(cli_runner: CliRunner, tmp_path, monkeypatch) -> None:
    """show-skill does not create or modify any files (read-only)."""
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    cli_runner.invoke(main, ["show-skill", "--runtime", "claude"])
    after = set(tmp_path.iterdir())
    assert before == after  # no files created


def test_show_skill_pipeable_no_trailing_newline(cli_runner: CliRunner) -> None:
    """Output ends without an extra trailing newline added by click.echo."""
    result = cli_runner.invoke(main, ["show-skill", "--runtime", "claude"])
    assert result.exit_code == 0, result.output
    # click.echo(result, nl=False) — output should not have a double trailing newline
    # A single trailing newline from the markdown content is fine; extra one is not
    if result.output.endswith("\n\n"):
        pytest.fail("Output has double trailing newline — check nl=False in click.echo call")


def test_show_skill_deepseek_via_opencode(cli_runner: CliRunner) -> None:
    """show-skill --runtime deepseek-via-opencode routes to opencode overlay."""
    result = cli_runner.invoke(main, ["show-skill", "--runtime", "deepseek-via-opencode"])
    assert result.exit_code == 0, result.output
    assert "#" in result.output


def test_show_skill_missing_runtime_arg(cli_runner: CliRunner) -> None:
    """show-skill without --runtime arg exits with error."""
    result = cli_runner.invoke(main, ["show-skill"])
    assert result.exit_code != 0
