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


# --- T-03-09-S03 (Phase 3 security audit) regression tests ---

@pytest.mark.parametrize("malicious_node_id", [
    "../../etc",                   # parent traversal
    "../etc/passwd",
    "/etc/passwd",                 # absolute path
    "/tmp",
    "node/../../escape",           # embedded ..
    "..",                          # bare dotdot
    ".",                           # bare dot
    "",                            # empty
    "node\\windows\\path",         # backslash
    "node/with/slash",             # forward slash
])
def test_export_rejects_path_traversal(
    tmp_path: Path,
    cli_runner: CliRunner,
    monkeypatch,
    malicious_node_id: str,
) -> None:
    """T-03-09-S03 regression: `automil trajectory export` MUST reject any
    node_id that is a path or contains parent-directory traversal. Without
    this guard, `archive_dir / "../../etc"` resolves to /etc and the
    bundler would package any matching files found there.
    """
    automil_dir = tmp_path / "automil"
    archive_dir = automil_dir / "archive"
    archive_dir.mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AUTOMIL_DIR", str(automil_dir))

    result = cli_runner.invoke(
        main, ["trajectory", "export", malicious_node_id, "--out", str(tmp_path / "out.tar.gz")]
    )

    # Click error exit code is 1 for ClickException.
    assert result.exit_code != 0, (
        f"export accepted malicious node_id {malicious_node_id!r} (exit 0). "
        f"Path-traversal guard regressed."
    )
    # Verify the error message names the rejection class — no silent failure.
    assert "Invalid node_id" in result.output or "must be a graph identifier" in result.output, (
        f"Rejection message missing for {malicious_node_id!r}; got: {result.output!r}"
    )
    # Verify NO tarball was created at the would-be output path.
    assert not (tmp_path / "out.tar.gz").exists()


def test_export_accepts_valid_node_id_shape(
    tmp_path: Path,
    cli_runner: CliRunner,
    monkeypatch,
) -> None:
    """T-03-09-S03 regression: valid graph-identifier-shaped node_ids must
    still be accepted (no over-rejection)."""
    automil_dir = tmp_path / "automil"
    archive_dir = automil_dir / "archive"
    archive_dir.mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("")

    node_id = "node_0176"
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
