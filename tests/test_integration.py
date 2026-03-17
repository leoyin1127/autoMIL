"""End-to-end integration tests."""

import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from automil.cli import main


class TestEndToEnd:
    def test_init_submit_rank_flow(self, tmp_path, monkeypatch):
        """Full flow: init project, submit experiment, check archive."""
        runner = CliRunner()

        # Init project
        proj = tmp_path / "e2e_test"
        result = runner.invoke(main, ["init", str(proj)])
        assert result.exit_code == 0, result.output

        monkeypatch.chdir(proj)

        # Verify scaffold
        assert (proj / "config.yaml").exists()
        assert (proj / "train.py").exists()
        assert (proj / "prepare.py").exists()
        assert (proj / "program.md").exists()
        assert (proj / "learnings.md").exists()
        assert (proj / ".gitignore").exists()

        # Verify git repo with initial commit
        git_log = subprocess.run(
            ["git", "log", "--oneline"], cwd=proj,
            capture_output=True, text=True,
        )
        assert git_log.returncode == 0
        assert "initialize" in git_log.stdout.lower()

        # Verify runtime files are gitignored
        git_status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=proj,
            capture_output=True, text=True,
        )
        assert git_status.stdout.strip() == "", f"Dirty working tree: {git_status.stdout}"

        # Modify train.py and submit
        (proj / "train.py").write_text("print('experiment 1')\n")
        result = runner.invoke(
            main,
            ["submit", "--node", "node_0001", "--desc", "test exp",
             "--files", "train.py"],
        )
        assert result.exit_code == 0, result.output

        # Verify archive structure
        archive = proj / "orchestrator" / "archive" / "node_0001"
        assert (archive / "train.py").exists()
        assert (archive / "train.py").read_text() == "print('experiment 1')\n"

        # Verify queue spec
        queue_files = list((proj / "orchestrator" / "queue").glob("*.json"))
        assert len(queue_files) == 1
        spec = json.loads(queue_files[0].read_text())
        assert spec["id"] == "node_0001"
        assert "base_commit" in spec
        assert "overlay_manifest" in spec

        # Status should work
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0, result.output

    def test_no_internal_paths_in_package(self):
        """Verify no institution-specific paths leaked into the package."""
        import automil
        pkg_dir = Path(automil.__file__).parent

        for f in pkg_dir.rglob("*"):
            if f.is_file() and f.suffix in (".py", ".md", ".yaml", ".j2", ".html", ".js"):
                content = f.read_text()
                assert "/mnt/pool" not in content, f"Internal path in {f}"
                assert "/home/jma" not in content, f"Home path in {f}"

    def test_multiple_submits(self, tmp_path, monkeypatch):
        """Multiple experiments can be submitted sequentially."""
        runner = CliRunner()
        proj = tmp_path / "multi_test"
        runner.invoke(main, ["init", str(proj)])
        monkeypatch.chdir(proj)

        for i in range(3):
            (proj / "train.py").write_text(f"print('experiment {i}')\n")
            result = runner.invoke(
                main,
                ["submit", "--node", f"node_{i:04d}", "--desc", f"exp {i}",
                 "--files", "train.py"],
            )
            assert result.exit_code == 0, result.output

        # All 3 should be in queue
        queue_files = list((proj / "orchestrator" / "queue").glob("*.json"))
        assert len(queue_files) == 3

        # All 3 archives should exist with different content
        for i in range(3):
            archive = proj / "orchestrator" / "archive" / f"node_{i:04d}"
            assert (archive / "train.py").read_text() == f"print('experiment {i}')\n"

    def test_propose_and_rank(self, tmp_path, monkeypatch):
        """Propose experiments and rank them."""
        runner = CliRunner()
        proj = tmp_path / "rank_test"
        runner.invoke(main, ["init", str(proj)])
        monkeypatch.chdir(proj)

        # Create a graph with a root node
        from automil.graph import ExperimentGraph
        graph = ExperimentGraph(path=str(proj / "graph.json"))
        root = graph.add_executed(
            parent_id=None,
            description="baseline",
            techniques=["baseline"],
            metrics={"test_auc": 0.85, "test_bacc": 0.80, "composite": 0.825},
            status="keep",
        )
        graph.save()

        # Propose via CLI
        result = runner.invoke(
            main,
            ["propose", "--parent", root, "--desc", "try focal loss",
             "--techniques", "focal"],
        )
        assert result.exit_code == 0, result.output

        # Rank should show the proposal
        result = runner.invoke(main, ["rank"])
        assert result.exit_code == 0, result.output
        assert "focal" in result.output

    def test_start_stop_loop(self, tmp_path, monkeypatch):
        """start-loop and stop-loop manage the flag file."""
        runner = CliRunner()
        proj = tmp_path / "loop_test"
        runner.invoke(main, ["init", str(proj)])
        monkeypatch.chdir(proj)

        result = runner.invoke(main, ["start-loop"])
        assert result.exit_code == 0
        assert (proj / ".automil_active").exists()

        result = runner.invoke(main, ["stop-loop"])
        assert result.exit_code == 0
        assert not (proj / ".automil_active").exists()
