"""Tests for the automil CLI."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from automil.cli import main


@pytest.fixture
def cli_runner():
    return CliRunner()


def _init_git_repo(path: Path):
    """Initialize a git repo with an initial commit at the given path."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=path, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path, capture_output=True,
    )
    # Create a dummy file and commit so HEAD exists
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path, capture_output=True, check=True,
    )


class TestInit:
    def test_creates_automil_subdir(self, cli_runner, tmp_path, monkeypatch):
        """automil init creates an automil/ subdirectory in an existing repo."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(main, ["init"])
        assert result.exit_code == 0, result.output

        adir = tmp_path / "automil"
        assert (adir / "config.yaml").exists()
        assert (adir / "program.md").exists()
        assert (adir / "learnings.md").exists()
        assert (adir / ".gitignore").exists()
        assert (adir / "orchestrator" / "queue").is_dir()
        assert (adir / "orchestrator" / "archive").is_dir()
        assert (adir / "orchestrator" / "completed").is_dir()
        assert (adir / "orchestrator" / "running").is_dir()

    def test_no_train_py_or_prepare_py(self, cli_runner, tmp_path, monkeypatch):
        """automil init does not create train.py or prepare.py."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        cli_runner.invoke(main, ["init"])

        assert not (tmp_path / "automil" / "train.py").exists()
        assert not (tmp_path / "automil" / "prepare.py").exists()
        assert not (tmp_path / "train.py").exists()
        assert not (tmp_path / "prepare.py").exists()

    def test_requires_git_repo(self, cli_runner, tmp_path, monkeypatch):
        """automil init errors if not in a git repo."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path)

        result = cli_runner.invoke(main, ["init"])
        assert result.exit_code != 0
        assert "git repository" in result.output

    def test_errors_if_already_initialized(self, cli_runner, tmp_path, monkeypatch):
        """automil init errors if automil/ already has config.yaml."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        cli_runner.invoke(main, ["init"])
        result = cli_runner.invoke(main, ["init"])
        assert result.exit_code != 0
        assert "already initialized" in result.output

    def test_gitignore_excludes_runtime(self, cli_runner, tmp_path, monkeypatch):
        """Runtime files (graph.json, results.tsv, orchestrator/) are gitignored."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        cli_runner.invoke(main, ["init"])

        gitignore = (tmp_path / "automil" / ".gitignore").read_text()
        assert "graph.json" in gitignore
        assert "results.tsv" in gitignore
        assert "orchestrator/" in gitignore


class TestCheck:
    def test_check_reports_placeholder_paths(self, cli_runner, tmp_path, monkeypatch):
        """automil check warns about placeholder data paths."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        cli_runner.invoke(main, ["init"])
        result = cli_runner.invoke(main, ["check"])
        assert result.exit_code == 0
        assert "placeholder" in result.output.lower() or "ISSUES" in result.output

    def test_check_accepts_existing_relative_data_paths(self, cli_runner, tmp_path, monkeypatch):
        """Relative data paths should be resolved from the project root."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        cli_runner.invoke(main, ["init"])

        features_dir = tmp_path / "data" / "features"
        splits_dir = tmp_path / "data" / "splits"
        mapping_csv = tmp_path / "data" / "mapping.csv"
        features_dir.mkdir(parents=True)
        splits_dir.mkdir(parents=True)
        mapping_csv.write_text("slide_id,label\n")

        config_path = tmp_path / "automil" / "config.yaml"
        config_text = config_path.read_text()
        config_text = config_text.replace("/path/to/features/", "data/features")
        config_text = config_text.replace("/path/to/splits/", "data/splits")
        config_text = config_text.replace("/path/to/mapping.csv", "data/mapping.csv")
        (tmp_path / "train.py").write_text("open('result.json', 'w').write('{}')\n")
        config_text = config_text.replace('script: "train.py"', 'script: "train.py"')
        config_path.write_text(config_text)

        result = cli_runner.invoke(main, ["check"])
        assert result.exit_code == 0
        assert "data.features_dir path does not exist" not in result.output
        assert "data.splits_dir path does not exist" not in result.output
        assert "data.mapping_csv path does not exist" not in result.output


class TestSubmit:
    def test_submit_captures_files(self, cli_runner, tmp_path, monkeypatch):
        """automil submit snapshots specified files to archive."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        cli_runner.invoke(main, ["init"])

        # Create a file to submit
        (tmp_path / "model.py").write_text("print('modified')\n")

        # Submit
        result = cli_runner.invoke(
            main,
            ["submit", "--node", "node_0001", "--desc", "test", "--files", "model.py"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        # Check archive
        archive = tmp_path / "automil" / "orchestrator" / "archive" / "node_0001"
        assert (archive / "model.py").exists()
        assert (archive / "model.py").read_text() == "print('modified')\n"

        # Check spec in queue
        queue_files = list((tmp_path / "automil" / "orchestrator" / "queue").glob("*.json"))
        assert len(queue_files) == 1
        spec = json.loads(queue_files[0].read_text())
        assert spec["id"] == "node_0001"
        assert "base_commit" in spec

    def test_submit_auto_detect_supports_directory_scopes(self, cli_runner, tmp_path, monkeypatch):
        """Directory scopes in files.editable should capture changed files beneath them."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        cli_runner.invoke(main, ["init"])

        config_path = tmp_path / "automil" / "config.yaml"
        config_text = config_path.read_text().replace("editable: []", 'editable: ["models/"]')
        config_path.write_text(config_text)

        (tmp_path / "models").mkdir()
        (tmp_path / "models" / "custom.py").write_text("print('changed')\n")
        (tmp_path / "notes.txt").write_text("ignore me\n")

        result = cli_runner.invoke(
            main,
            ["submit", "--node", "node_scope", "--desc", "dir scope"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0

        archive = tmp_path / "automil" / "orchestrator" / "archive" / "node_scope"
        assert (archive / "models" / "custom.py").exists()
        assert not (archive / "notes.txt").exists()

    def test_submit_warns_for_readonly_glob(self, cli_runner, tmp_path, monkeypatch):
        """Readonly glob patterns should warn when explicit files match them."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        cli_runner.invoke(main, ["init"])

        config_path = tmp_path / "automil" / "config.yaml"
        config_text = config_path.read_text().replace("readonly: []", 'readonly: ["data/*.py"]')
        config_path.write_text(config_text)

        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "prepare.py").write_text("print('readonly')\n")

        result = cli_runner.invoke(
            main,
            ["submit", "--node", "node_ro", "--desc", "readonly", "--files", "data/prepare.py"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "marked readonly" in result.output


class TestRank:
    def test_rank_outputs_proposals(self, cli_runner, tmp_path, monkeypatch):
        """automil rank shows top proposals from graph.json."""
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        cli_runner.invoke(main, ["init"])

        # Create a graph with proposals
        from automil.graph import ExperimentGraph
        graph = ExperimentGraph(path=str(tmp_path / "automil" / "graph.json"))
        root = graph.add_executed(
            parent_id=None,
            description="baseline",
            techniques=["baseline"],
            metrics={"test_auc": 0.85, "test_bacc": 0.80, "composite": 0.825},
            status="keep",
        )
        graph.add_proposed(
            parent_id=root,
            description="try focal loss",
            techniques=["focal"],
        )
        graph.save()

        result = cli_runner.invoke(main, ["rank"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "focal" in result.output
