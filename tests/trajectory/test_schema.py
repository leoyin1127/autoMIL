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


# --- Phase 3 review regression tests (CR-01, CR-02) ---

def test_read_metadata_empty_file_raises_schema_error(tmp_path: Path) -> None:
    """CR-01 regression: read_metadata on an empty trajectory file raises
    TrajectorySchemaError, NOT a bare IndexError. Reachable via soft rotation
    where the metadata header write was skipped (rotation.py:123)."""
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text("")  # empty file
    with pytest.raises(TrajectorySchemaError, match="empty"):
        read_metadata(traj)


def test_read_metadata_blank_first_line_raises_schema_error(tmp_path: Path) -> None:
    """CR-01 regression: a file with only whitespace on line 0 also raises typed."""
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text("   \n")
    with pytest.raises(TrajectorySchemaError, match="empty"):
        read_metadata(traj)


@pytest.mark.parametrize("bad_version", [
    "trajectory-v2",
    "trajectory-v3",
    "trajectory-v11",
    "trajectory-v99",
    "trajectory-v3.0",
    "trajectory-vNext",
    "v1",                   # missing "trajectory-" prefix
    "v2",
    "",                     # empty
    "json-line-v1",         # different schema family
])
def test_read_metadata_rejects_non_v1(tmp_path: Path, bad_version: str) -> None:
    """CR-02 regression: anything that isn't `trajectory-v1.*` MUST raise.
    Previously v3+ was silently accepted because the compound condition
    short-circuited on `not startswith("trajectory-v")`."""
    metadata = {
        "schema_version":      bad_version,
        "runtime":             "claude-code",
        "runtime_version":     "unknown",
        "tool_schema_version": "unknown",
        "automil_version":     "1.0.0",
        "automil_runtime_env": {},
    }
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text(json.dumps(metadata) + "\n")
    with pytest.raises(TrajectorySchemaError, match="Unsupported schema_version"):
        read_metadata(traj)


@pytest.mark.parametrize("good_version", [
    "trajectory-v1",
    "trajectory-v1.0",
    "trajectory-v1.5",
    "trajectory-v1.99",
    "trajectory-v1-rc1",     # any v1.* shape
])
def test_read_metadata_accepts_v1_variants(tmp_path: Path, good_version: str) -> None:
    """CR-02 regression: every `trajectory-v1*` form continues to read OK."""
    metadata = {"schema_version": good_version, "runtime": "claude-code"}
    traj = tmp_path / "trajectory.jsonl"
    traj.write_text(json.dumps(metadata) + "\n")
    meta = read_metadata(traj)
    assert meta["schema_version"] == good_version
