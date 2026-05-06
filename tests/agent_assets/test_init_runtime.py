"""automil init --runtime + --update integration tests (MRT-02, MRT-03 / D-91, D-92)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from automil.cli import main


def _init_git_repo(path: Path) -> None:
    """Helper: initialise a bare git repo (copied from test_cli.py pattern)."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)


@pytest.fixture
def project_dir(tmp_path: Path):
    _init_git_repo(tmp_path)
    return tmp_path


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_init_explicit_runtime_claude(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """automil init --runtime claude creates .claude/CLAUDE.md and AGENTS.md."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init", "--runtime", "claude"])
    assert result.exit_code == 0, result.output
    assert (project_dir / "AGENTS.md").exists()
    assert (project_dir / ".claude" / "CLAUDE.md").exists()
    claude_md = (project_dir / ".claude" / "CLAUDE.md").read_text()
    assert "@AGENTS.md" in claude_md


def test_init_explicit_runtime_opencode(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """automil init --runtime opencode creates .opencode/AGENTS.md and AGENTS.md."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init", "--runtime", "opencode"])
    assert result.exit_code == 0, result.output
    assert (project_dir / "AGENTS.md").exists()
    assert (project_dir / ".opencode" / "AGENTS.md").exists()


def test_init_explicit_runtime_codex(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """automil init --runtime codex creates .codex/instructions.md and AGENTS.md."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init", "--runtime", "codex"])
    assert result.exit_code == 0, result.output
    assert (project_dir / "AGENTS.md").exists()
    assert (project_dir / ".codex" / "instructions.md").exists()


def test_init_runtime_all(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """automil init --runtime all installs claude + opencode + codex assets."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init", "--runtime", "all"])
    assert result.exit_code == 0, result.output
    assert (project_dir / "AGENTS.md").exists()
    assert (project_dir / ".claude" / "CLAUDE.md").exists()
    assert (project_dir / ".opencode" / "AGENTS.md").exists()
    assert (project_dir / ".codex" / "instructions.md").exists()


def test_init_autodetect_claude_dir(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """Auto-detection: .claude/ dir present → install claude overlay."""
    (project_dir / ".claude").mkdir()
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (project_dir / ".claude" / "CLAUDE.md").exists()


def test_init_autodetect_opencode_dir(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """Auto-detection: .opencode/ dir present → install opencode overlay."""
    (project_dir / ".opencode").mkdir()
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (project_dir / ".opencode" / "AGENTS.md").exists()


def test_init_autodetect_no_dir_defaults_to_claude(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """Auto-detection: no runtime dirs → install claude + print banner."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    # Should print the "No runtime config detected" banner
    assert "No runtime config detected" in result.output
    # And still install claude by default
    assert (project_dir / ".claude" / "CLAUDE.md").exists()


def test_init_autodetect_multiple_dirs(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """Auto-detection: multiple runtime dirs present → install all detected."""
    (project_dir / ".claude").mkdir()
    (project_dir / ".opencode").mkdir()
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (project_dir / ".claude" / "CLAUDE.md").exists()
    assert (project_dir / ".opencode" / "AGENTS.md").exists()


def test_init_update_flag_bypasses_guard(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """--update skips the already-initialized guard and re-renders assets."""
    monkeypatch.chdir(project_dir)
    # First init
    cli_runner.invoke(main, ["init", "--runtime", "claude"])
    # Second init without --update should fail
    result_fail = cli_runner.invoke(main, ["init", "--runtime", "claude"])
    assert result_fail.exit_code != 0 or "already initialized" in result_fail.output
    # With --update should succeed
    result_update = cli_runner.invoke(main, ["init", "--runtime", "claude", "--update"])
    assert result_update.exit_code == 0, result_update.output


def test_init_update_does_not_overwrite_config(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """--update re-renders assets but does NOT overwrite config.yaml with new content."""
    monkeypatch.chdir(project_dir)
    # First init
    cli_runner.invoke(main, ["init", "--runtime", "claude"])
    config_path = project_dir / "automil" / "config.yaml"
    # Modify config.yaml
    original_content = config_path.read_text()
    config_path.write_text(original_content + "\n# custom user note\n")
    # Run --update
    cli_runner.invoke(main, ["init", "--runtime", "claude", "--update"])
    # Config should still have our custom note (not re-scaffolded)
    updated_content = config_path.read_text()
    assert "# custom user note" in updated_content


def test_agents_md_content_at_project_root(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """AGENTS.md at project root contains the universal autoMIL instructions (D-90)."""
    monkeypatch.chdir(project_dir)
    cli_runner.invoke(main, ["init", "--runtime", "claude"])
    agents_content = (project_dir / "AGENTS.md").read_text()
    assert "automil submit" in agents_content  # universal instruction
    assert "AUTOMIL_RUNTIME" in agents_content  # runtime declaration instruction


def test_init_deepseek_via_opencode(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """--runtime deepseek-via-opencode installs opencode overlay."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init", "--runtime", "deepseek-via-opencode"])
    assert result.exit_code == 0, result.output
    assert (project_dir / ".opencode" / "AGENTS.md").exists()


def test_init_deepseek_via_codex(
    project_dir: Path, cli_runner: CliRunner, monkeypatch
) -> None:
    """--runtime deepseek-via-codex installs codex overlay."""
    monkeypatch.chdir(project_dir)
    result = cli_runner.invoke(main, ["init", "--runtime", "deepseek-via-codex"])
    assert result.exit_code == 0, result.output
    assert (project_dir / ".codex" / "instructions.md").exists()
