"""Coverage for automil init registry scaffolding (REG-04 / D-25)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    return CliRunner()


def _init_git_repo(path: Path):
    """PATTERNS.md §"Pattern catalog" #2 — fake project root with real git init."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)


def test_variants_losses_gitkeep_created(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    result = cli_runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "automil" / "variants" / "_losses" / ".gitkeep").exists()


def test_variants_policies_gitkeep_created(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    assert (tmp_path / "automil" / "variants" / "_policies" / ".gitkeep").exists()


def test_variants_candidates_gitkeep_created(tmp_path, cli_runner, monkeypatch):
    """D-25: _candidates/ exists for Phase 5 GTE; Phase 1 ships .gitkeep only."""
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    assert (tmp_path / "automil" / "variants" / "_candidates" / ".gitkeep").exists()


def test_variants_root_gitkeep_created(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    assert (tmp_path / "automil" / "variants" / ".gitkeep").exists()


def test_no_parent_dir_at_init_time(tmp_path, cli_runner, monkeypatch):
    """D-25: per-parent <parent>/ created by port-variant on first use."""
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    # No clam_mb/, no ab_mil/ — parent dirs are created by port-variant.
    parents_present = [
        p for p in (tmp_path / "automil" / "variants").iterdir()
        if p.is_dir() and not p.name.startswith("_")
    ]
    assert parents_present == []


def test_config_yaml_has_registry_section(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    cfg_text = (tmp_path / "automil" / "config.yaml").read_text()
    assert "registry:" in cfg_text
    # protected default empty
    assert "protected: []" in cfg_text or "protected:\n" in cfg_text
    # mode default free
    assert 'mode: "free"' in cfg_text or "mode: free" in cfg_text
    # repro_tolerance default 0.005
    assert "repro_tolerance: 0.005" in cfg_text


def test_config_yaml_has_variant_selection(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    cfg_text = (tmp_path / "automil" / "config.yaml").read_text()
    # D-35: variant selection by short name
    assert "model:" in cfg_text
    assert "loss:" in cfg_text
    assert "policy:" in cfg_text
    # YAML parses cleanly
    cfg = yaml.safe_load(cfg_text)
    assert cfg.get("model", {}).get("variant") is None
    assert cfg.get("loss", {}).get("variant") is None
    assert cfg.get("policy", {}).get("variant") is None


def test_init_idempotence_preserves_user_files(tmp_path, cli_runner, monkeypatch):
    """Re-init refuses to overwrite (existing guard at cli/init.py:33-34)."""
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])

    # User adds a variant module post-init.
    user_loss = tmp_path / "automil" / "variants" / "_losses" / "my_loss.py"
    user_loss.write_text("# user added\n")

    # Re-init MUST hard-fail with "already initialized".
    result = cli_runner.invoke(main, ["init"])
    assert result.exit_code != 0
    assert "already initialized" in result.output.lower()
    # User's file is preserved.
    assert user_loss.exists()
    assert user_loss.read_text() == "# user added\n"


def test_scaffold_helper_idempotent(tmp_path):
    """Direct unit test on the scaffolding helper (not via CLI)."""
    adir = tmp_path / "automil"
    adir.mkdir()
    # Call the helper twice.
    from automil.cli.init import _scaffold_variants_skeleton
    _scaffold_variants_skeleton(adir)
    _scaffold_variants_skeleton(adir)
    # Subdirs and .gitkeep all exist; second call is a no-op.
    assert (adir / "variants" / "_losses" / ".gitkeep").exists()
    assert (adir / "variants" / "_policies" / ".gitkeep").exists()
    assert (adir / "variants" / "_candidates" / ".gitkeep").exists()


def test_init_with_custom_path_argument(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    result = cli_runner.invoke(main, ["init", "myautomil"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "myautomil" / "variants" / "_losses" / ".gitkeep").exists()


def test_rendered_config_is_parseable(tmp_path, cli_runner, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    from automil.cli import main
    cli_runner.invoke(main, ["init"])
    cfg_text = (tmp_path / "automil" / "config.yaml").read_text()
    # Should not raise — full YAML is valid.
    cfg = yaml.safe_load(cfg_text)
    assert isinstance(cfg, dict)
    assert "registry" in cfg
