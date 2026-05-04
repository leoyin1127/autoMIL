"""automil trajectory export CLI tests (TRJ-05 / D-94)."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from automil.cli import main
from automil.trajectory import record_event


@pytest.fixture
def cli_runner():
    return CliRunner()


def test_export_creates_tarball(tmp_path: Path, cli_runner: CliRunner, monkeypatch) -> None:
    """export produces a .tar.gz bundle with trajectory.jsonl + manifest.json."""
    automil_dir = tmp_path / "automil"
    archive_dir = automil_dir / "archive"
    archive_dir.mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("")

    node_id = "node_export_01"
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    record_event(
        node_id=node_id,
        event={
            "gen_ai.provider.name":   "claude-code",
            "gen_ai.event.name":      "tool_call",
            "gen_ai.event.timestamp": "2026-05-03T00:00:00.000000Z",
        },
        archive_dir=archive_dir,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOMIL_DIR", str(automil_dir))
    out_path = tmp_path / f"{node_id}.trajectory.tar.gz"
    result = cli_runner.invoke(main, ["trajectory", "export", node_id, "--out", str(out_path)])
    assert result.exit_code == 0, result.output
    assert out_path.exists()

    with tarfile.open(str(out_path), "r:gz") as tar:
        names = tar.getnames()
        assert "trajectory.jsonl" in names
        assert "manifest.json" in names
        manifest_file = tar.extractfile("manifest.json")
        manifest = json.load(manifest_file)
        assert manifest["node_id"] == node_id
        assert "redaction_rule_hash" in manifest
