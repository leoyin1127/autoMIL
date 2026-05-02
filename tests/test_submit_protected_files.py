"""Coverage for `automil submit` registry.protected reject (REG-04 / REG-05 / D-33 / D-34)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    return CliRunner()


def _init_git_repo(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)


def _setup_project(tmp_path: Path, protected: list[str]) -> tuple[Path, Path]:
    _init_git_repo(tmp_path)
    from automil.cli import main
    runner = CliRunner()
    import os
    os.chdir(tmp_path)
    runner.invoke(main, ["init"])

    # Edit config.yaml to set protected.
    adir = tmp_path / "automil"
    cfg_path = adir / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    cfg.setdefault("registry", {})["protected"] = protected
    cfg_path.write_text(yaml.safe_dump(cfg))
    return tmp_path, adir


def test_protected_glob_match_rejects(tmp_path, cli_runner, monkeypatch):
    proj, adir = _setup_project(tmp_path, ["benchmarks/lib/CLAM/**"])
    monkeypatch.chdir(proj)

    # Create the file we'll try to submit.
    target = proj / "benchmarks" / "lib" / "CLAM"
    target.mkdir(parents=True)
    (target / "foo.py").write_text("# whatever\n")

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "test",
               "--files", "benchmarks/lib/CLAM/foo.py"],
    )
    assert result.exit_code != 0, result.output
    assert "Refusing to submit" in result.output
    assert "registry.protected" in result.output
    assert "benchmarks/lib/CLAM" in result.output
    assert "revert-baseline" in result.output


def test_multiple_matched_patterns_named(tmp_path, cli_runner, monkeypatch):
    proj, adir = _setup_project(
        tmp_path,
        ["benchmarks/**", "src/lib/**"],
    )
    monkeypatch.chdir(proj)

    target = proj / "benchmarks" / "lib"
    target.mkdir(parents=True)
    (target / "x.py").write_text("# x\n")

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "t",
               "--files", "benchmarks/lib/x.py"],
    )
    assert result.exit_code != 0
    assert "benchmarks/**" in result.output


def test_protected_exact_path_rejects(tmp_path, cli_runner, monkeypatch):
    proj, adir = _setup_project(tmp_path, ["src/foo.py"])
    monkeypatch.chdir(proj)

    (proj / "src").mkdir()
    (proj / "src" / "foo.py").write_text("# foo\n")

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "t",
               "--files", "src/foo.py"],
    )
    assert result.exit_code != 0
    assert "src/foo.py" in result.output


def test_non_matching_path_not_rejected_on_protected(tmp_path, cli_runner, monkeypatch):
    proj, adir = _setup_project(tmp_path, ["benchmarks/**"])
    monkeypatch.chdir(proj)

    (proj / "src").mkdir()
    (proj / "src" / "main.py").write_text("# main\n")

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "t",
               "--files", "src/main.py"],
    )
    # The submit may still succeed or fail for other reasons (e.g., git
    # tracking). The protected branch must NOT be the cause.
    assert "registry.protected" not in result.output


def test_empty_protected_no_reject(tmp_path, cli_runner, monkeypatch):
    proj, adir = _setup_project(tmp_path, [])
    monkeypatch.chdir(proj)

    (proj / "any.py").write_text("# any\n")

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "t",
               "--files", "any.py"],
    )
    assert "registry.protected" not in result.output


def test_no_force_flag_d34(tmp_path, cli_runner):
    from automil.cli import main
    result = cli_runner.invoke(main, ["submit", "--force", "--node", "x", "--desc", "y"])
    assert result.exit_code != 0
    # Click's default error for unknown flags.
    assert "no such option" in result.output.lower() or "--force" in result.output


def test_submit_help_does_not_mention_force(cli_runner):
    from automil.cli import main
    result = cli_runner.invoke(main, ["submit", "--help"])
    assert result.exit_code == 0
    assert "--force" not in result.output
    # Existing flags still listed.
    assert "--node" in result.output
    assert "--desc" in result.output


def test_good_error_message_names_pattern_and_suggests_fix(tmp_path, cli_runner, monkeypatch):
    """Production-grade: error names what + why + how-to-fix."""
    proj, adir = _setup_project(tmp_path, ["benchmarks/lib/**"])
    monkeypatch.chdir(proj)
    target = proj / "benchmarks" / "lib"
    target.mkdir(parents=True)
    (target / "x.py").write_text("# x\n")

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "t",
               "--files", "benchmarks/lib/x.py"],
    )
    # Three required substrings:
    # 1. WHAT: "Refusing to submit"
    assert "Refusing to submit" in result.output
    # 2. WHY: "registry.protected" + named pattern
    assert "registry.protected" in result.output
    assert "benchmarks/lib/" in result.output
    # 3. HOW: suggestion of revert-baseline
    assert "revert-baseline" in result.output


def test_protected_reject_runs_before_path_validation(tmp_path, cli_runner, monkeypatch):
    """Protected-files reject fires BEFORE the existing path-validation guard.

    The existing guard at submit.py line 179 rejects absolute paths.
    If a protected glob matches an absolute path AND the submit runs the
    protected check first, the error should be the protected message, not
    the path-validation message.  We use a glob that matches all paths under
    /etc/ to test this.
    """
    proj, adir = _setup_project(tmp_path, ["/etc/**"])
    monkeypatch.chdir(proj)

    from automil.cli import main
    result = cli_runner.invoke(
        main, ["submit", "--node", "node_0001", "--desc", "t",
               "--files", "/etc/passwd"],
    )
    assert result.exit_code != 0
    # With protected matching, protected error message fires first
    # (or at minimum, the path-validation error fires — both are non-zero).
    # The key invariant is exit_code != 0; the exact message depends on
    # whether the protected check or path-validation check runs first.
    # This test verifies the ordering: protected BEFORE path-validation.
    assert "Refusing to submit" in result.output
    # If protected check fires first, the output contains "registry.protected".
    # If path-validation fires first (violation!), the output does NOT contain
    # "registry.protected" and does contain "must be relative".
    # The test enforces that the protected message is present.
    assert "registry.protected" in result.output
