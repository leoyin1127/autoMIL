"""Schema version forward-compat + validate_event tests (TRJ-01, TRJ-06 / D-80, D-81)."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from automil.trajectory.schema import (
    validate_event,
    TrajectorySchemaError,
    REQUIRED_FIELDS,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_EVENT_NAME,
    GEN_AI_EVENT_TIMESTAMP,
)
from automil.trajectory.recorder import read_metadata


# --- validate_event ---

def test_validate_event_passes_with_all_required_fields() -> None:
    """Event with all REQUIRED_FIELDS passes validation silently."""
    event = {
        GEN_AI_PROVIDER_NAME:   "claude-code",
        GEN_AI_EVENT_NAME:      "tool_call",
        GEN_AI_EVENT_TIMESTAMP: "2026-05-03T00:00:00.000000Z",
    }
    validate_event(event)  # must not raise


def test_validate_event_passes_with_unknown_extra_fields() -> None:
    """Extra unknown fields pass silently — forward-compat per D-80."""
    event = {
        GEN_AI_PROVIDER_NAME:   "claude-code",
        GEN_AI_EVENT_NAME:      "tool_call",
        GEN_AI_EVENT_TIMESTAMP: "2026-05-03T00:00:00.000000Z",
        "unknown_future_field": "some_value",
        "gen_ai.new_v1_5_field": 42,
    }
    validate_event(event)  # must not raise


@pytest.mark.parametrize("missing_field", sorted(REQUIRED_FIELDS))
def test_validate_event_fails_on_missing_required_field(missing_field: str) -> None:
    """Missing any required field raises TrajectorySchemaError."""
    event = {
        GEN_AI_PROVIDER_NAME:   "claude-code",
        GEN_AI_EVENT_NAME:      "tool_call",
        GEN_AI_EVENT_TIMESTAMP: "2026-05-03T00:00:00.000000Z",
    }
    del event[missing_field]
    with pytest.raises(TrajectorySchemaError, match="Required fields missing"):
        validate_event(event)


# --- schema version forward-compat (D-80) ---

def test_read_metadata_v1_with_extra_field_ok(tmp_path: Path) -> None:
    """trajectory-v1 file with an extra field is readable — forward-compat."""
    metadata = {
        "schema_version": "trajectory-v1",
        "runtime": "claude-code",
        "runtime_version": "claude-opus-4-7@2026-04-30",
        "tool_schema_version": "claude-2026-04",
        "automil_version": "0.1.0",
        "automil_runtime_env": {"AUTOMIL_RUNTIME": "claude-code"},
        "new_field_v1_5": "some_extra_info",  # unknown field — must be tolerated
    }
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text(json.dumps(metadata) + "\n")
    result = read_metadata(traj)
    assert result["schema_version"] == "trajectory-v1"
    assert result["new_field_v1_5"] == "some_extra_info"  # returned as-is


def test_read_metadata_v1_minor_ok(tmp_path: Path) -> None:
    """trajectory-v1.5 (minor bump) is readable — forward-compat."""
    metadata = {
        "schema_version": "trajectory-v1.5",
        "runtime": "opencode",
        "runtime_version": "unknown",
        "tool_schema_version": "unknown",
        "automil_version": "0.2.0",
        "automil_runtime_env": {},
    }
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text(json.dumps(metadata) + "\n")
    result = read_metadata(traj)
    assert result["schema_version"] == "trajectory-v1.5"


def test_read_metadata_v2_raises(tmp_path: Path) -> None:
    """trajectory-v2 raises TrajectorySchemaError — breaking change per D-80."""
    metadata = {
        "schema_version": "trajectory-v2",
        "runtime": "claude-code",
        "runtime_version": "unknown",
        "tool_schema_version": "unknown",
        "automil_version": "1.0.0",
        "automil_runtime_env": {},
    }
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text(json.dumps(metadata) + "\n")
    with pytest.raises(TrajectorySchemaError, match="trajectory-v2"):
        read_metadata(traj)


def test_required_fields_set_has_three_entries() -> None:
    """REQUIRED_FIELDS contains exactly the three fields from D-81."""
    assert REQUIRED_FIELDS == frozenset({
        "gen_ai.provider.name",
        "gen_ai.event.name",
        "gen_ai.event.timestamp",
    })


def test_gen_ai_provider_name_not_gen_ai_system() -> None:
    """Phase 3 uses gen_ai.provider.name (not deprecated gen_ai.system) per research finding."""
    from automil.trajectory.schema import GEN_AI_PROVIDER_NAME
    assert GEN_AI_PROVIDER_NAME == "gen_ai.provider.name"
    assert "gen_ai.system" not in REQUIRED_FIELDS
