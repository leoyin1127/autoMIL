"""automil.schemas: declared contracts the framework validates at boundaries.

D-201 (Phase 8 / DEC-03) introduces the first JSON-Schema-validated contract:
result.json. The schema lives at result.schema.json; the validator lives in
_result.py. Both are reachable via this package's top-level names.
"""
from automil.schemas._result import (
    RESULT_SCHEMA,
    ValidationError,
    validate_result,
)

__all__ = ["RESULT_SCHEMA", "ValidationError", "validate_result"]
