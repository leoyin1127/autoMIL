"""record_event unit tests (TRJ-01, TRJ-04 / D-85, D-86)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from automil.trajectory import record_event, read_metadata
from automil.trajectory.schema import GEN_AI_PROVIDER_NAME, GEN_AI_EVENT_NAME, GEN_AI_EVENT_TIMESTAMP


@pytest.fixture
def archive_dir(tmp_path: Path):
    node_id = "node_test_01"
    d = tmp_path / "archive"
    d.mkdir()
    return d, node_id


def _make_event(provider: str = "claude-code") -> dict:
    return {
        GEN_AI_PROVIDER_NAME:   provider,
        GEN_AI_EVENT_NAME:      "tool_call",
        GEN_AI_EVENT_TIMESTAMP: "2026-05-03T00:00:00.000000Z",
        "gen_ai.tool.name":     "Bash",
    }


def test_record_event_appends_to_file(archive_dir, monkeypatch) -> None:
    """record_event creates trajectory.jsonl with metadata + event line."""
    d, node_id = archive_dir
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    result = record_event(node_id=node_id, event=_make_event(), archive_dir=d)
    assert result is True
    traj = d / node_id / "trajectory.jsonl"
    assert traj.exists()
    lines = traj.read_text().splitlines()
    assert len(lines) == 2  # line 0: metadata, line 1: event
    metadata = json.loads(lines[0])
    assert metadata["schema_version"] == "trajectory-v1"
    assert metadata["runtime"] == "claude-code"


def test_record_event_redacts_secrets(archive_dir, monkeypatch) -> None:
    """Secrets in event fields are redacted before appending."""
    d, node_id = archive_dir
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    event = _make_event()
    event["gen_ai.tool.call.arguments"] = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstu"
    record_event(node_id=node_id, event=event, archive_dir=d)
    content = (d / node_id / "trajectory.jsonl").read_text()
    assert "sk-abcdefghijklmnopqrstu" not in content
    assert "[REDACTED]" in content


def test_record_event_multiple_events(archive_dir, monkeypatch) -> None:
    """Multiple record_event calls append multiple lines."""
    d, node_id = archive_dir
    monkeypatch.setenv("AUTOMIL_RUNTIME", "opencode")
    for i in range(5):
        event = _make_event("opencode")
        event[GEN_AI_EVENT_TIMESTAMP] = f"2026-05-03T00:00:0{i}.000000Z"
        record_event(node_id=node_id, event=event, archive_dir=d)
    lines = (d / node_id / "trajectory.jsonl").read_text().splitlines()
    assert len(lines) == 6  # 1 metadata + 5 events


def test_record_event_soft_fail_on_missing_required_field(archive_dir) -> None:
    """Missing REQUIRED_FIELDS causes soft-fail (returns False, no raise)."""
    d, node_id = archive_dir
    bad_event = {"gen_ai.tool.name": "Bash"}  # missing provider.name, event.name, timestamp
    result = record_event(node_id=node_id, event=bad_event, archive_dir=d)
    assert result is False  # soft-fail


def test_read_metadata_returns_first_line(archive_dir, monkeypatch) -> None:
    """read_metadata returns the parsed first-line metadata dict."""
    d, node_id = archive_dir
    monkeypatch.setenv("AUTOMIL_RUNTIME", "claude-code")
    record_event(node_id=node_id, event=_make_event(), archive_dir=d)
    traj = d / node_id / "trajectory.jsonl"
    meta = read_metadata(traj)
    assert meta["schema_version"] == "trajectory-v1"
    assert meta["runtime"] == "claude-code"
