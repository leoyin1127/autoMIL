"""Trajectory capture subpackage (TRJ-01..06 / D-78..D-87)."""
from __future__ import annotations

import logging

from automil.trajectory.schema import (
    TrajectorySchemaError,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    validate_event,
    GEN_AI_PROVIDER_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_EVENT_NAME,
    GEN_AI_EVENT_TIMESTAMP,
    GEN_AI_TOOL_NAME,
    GEN_AI_TOOL_ARGUMENTS,
    GEN_AI_TOOL_RESULT,
    GEN_AI_USAGE_INPUT,
    GEN_AI_USAGE_OUTPUT,
)
from automil.trajectory.recorder import record_event, read_metadata
from automil.trajectory.rotation import RotationManager

logger = logging.getLogger(__name__)

__all__ = [
    "TrajectorySchemaError",
    "REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "validate_event",
    "GEN_AI_PROVIDER_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_EVENT_NAME",
    "GEN_AI_EVENT_TIMESTAMP",
    "GEN_AI_TOOL_NAME",
    "GEN_AI_TOOL_ARGUMENTS",
    "GEN_AI_TOOL_RESULT",
    "GEN_AI_USAGE_INPUT",
    "GEN_AI_USAGE_OUTPUT",
    "record_event",
    "read_metadata",
    "RotationManager",
]
