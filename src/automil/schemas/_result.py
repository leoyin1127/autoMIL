"""result.json schema validation (D-201 / DEC-03).

Wraps jsonschema.Draft202012Validator with a module-level pre-compiled validator
instance. Caller surfaces `automil/schemas/result.schema.json` in error messages
so the consumer can self-correct.

The schema file is the single source of truth; this module only loads + binds.
"""
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as _ValidationError

# Re-export for callers; do NOT import jsonschema directly elsewhere in
# src/automil/. Centralising the import keeps the dependency surface auditable.
ValidationError = _ValidationError

_SCHEMA_PATH: Path = Path(__file__).parent / "result.schema.json"
RESULT_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text())
_VALIDATOR: Draft202012Validator = Draft202012Validator(RESULT_SCHEMA)


def validate_result(payload: dict) -> None:
    """Validate result.json payload against the D-201 schema.

    Args:
        payload: the dict parsed from a worktree's result.json (or assembled
            in-memory by the orchestrator's status-synthesis fallback path).

    Raises:
        ValidationError: payload violates the schema. ``exc.message`` carries
            a single human-readable cause; ``exc.json_path`` carries the
            JSON Pointer to the offending node. Caller surfaces both plus
            the literal pointer ``automil/schemas/result.schema.json``.
    """
    _VALIDATOR.validate(payload)
