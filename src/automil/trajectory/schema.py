"""Trajectory schema: OTel gen_ai.* field constants + validation (TRJ-01, TRJ-02 / D-78, D-80, D-81).

Field names use the OTel gen_ai.* namespace as plain strings (no opentelemetry-sdk dep — D-106).
gen_ai.provider.name replaces deprecated gen_ai.system (OTel semconv, late 2025 — research finding).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# OTel gen_ai.* field name constants — use as JSONL keys directly
GEN_AI_PROVIDER_NAME   = "gen_ai.provider.name"      # provider: "claude-code"|"opencode"|"codex"
GEN_AI_REQUEST_MODEL   = "gen_ai.request.model"       # e.g. "claude-opus-4-7"
GEN_AI_EVENT_NAME      = "gen_ai.event.name"          # framework-specific: "prompt"|"tool_call"|"tool_result"|"response"
GEN_AI_EVENT_TIMESTAMP = "gen_ai.event.timestamp"     # framework-specific: ISO 8601 microsecond
GEN_AI_TOOL_NAME       = "gen_ai.tool.name"           # "Read"|"Edit"|"Bash"|...
GEN_AI_TOOL_ARGUMENTS  = "gen_ai.tool.call.arguments" # JSON-encoded args (post-redaction)
GEN_AI_TOOL_RESULT     = "gen_ai.tool.call.result"    # JSON-encoded result (post-redaction)
GEN_AI_USAGE_INPUT     = "gen_ai.usage.input_tokens"  # int (when known; absent OK)
GEN_AI_USAGE_OUTPUT    = "gen_ai.usage.output_tokens" # int (when known; absent OK)

REQUIRED_FIELDS: frozenset[str] = frozenset({
    GEN_AI_PROVIDER_NAME,
    GEN_AI_EVENT_NAME,
    GEN_AI_EVENT_TIMESTAMP,
})

SCHEMA_VERSION = "trajectory-v1"


class TrajectorySchemaError(ValueError):
    """Raised when a trajectory event or file fails schema validation (D-80, D-81)."""


def validate_event(d: dict) -> None:
    """Raise TrajectorySchemaError if a required gen_ai.* field is missing.

    Unknown fields pass silently — forward-compat per D-80.
    Reader MUST tolerate trajectory-v1.*; MUST refuse trajectory-v2.
    """
    missing = REQUIRED_FIELDS - set(d.keys())
    if missing:
        raise TrajectorySchemaError(f"Required fields missing: {sorted(missing)}")
