"""Redaction-on-capture for trajectory events (TRJ-03 / D-82, D-83).

Compiled regex set applied to every string field before append.
Redaction is mandatory — no opt-out flag (Pitfall 5a defence).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Compiled at module-import time — one-time cost, applied to every event (D-82)
_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),                               "sk-[REDACTED]"),
    (re.compile(r"hf_[A-Za-z0-9]{20,}"),                                  "hf_[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"),                                 "ghp_[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                 "AKIA[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_API_KEY)\s*[:=]\s*\S+"),          r"\1=[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_TOKEN)\s*[:=]\s*\S+"),            r"\1=[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_KEY)\s*[:=]\s*\S+"),              r"\1=[REDACTED]"),
]

_SIZE_CAP_BYTES = 8192  # D-83: 8 KB per-event cap


def redact(s: str) -> str:
    """Apply all compiled redaction patterns to a string. Returns a new string."""
    for pattern, replacement in _PATTERNS:
        s = pattern.sub(replacement, s)
    return s


def redact_event(d: dict) -> dict:
    """Walk event dict recursively and redact all string leaves.

    Returns a NEW dict — original is not mutated.
    Handles: dict (recurse values), list/tuple (recurse elements),
    str (apply patterns), int/float/bool/None (pass through).
    Soft-fail discipline: exceptions are caught and logged — never raises.
    """
    try:
        return _walk(d)
    except Exception as exc:
        logger.warning("redact_event failed: %s; returning sentinel event", exc)
        return {"gen_ai.event.name": "redaction_error", "_error": str(exc)}


def _walk(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _walk(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        walked = [_walk(v) for v in obj]
        return type(obj)(walked)
    if isinstance(obj, str):
        return redact(obj)
    return obj


def apply_size_cap(event: dict) -> dict:
    """Enforce the 8 KB per-event cap (D-83) post-redaction.

    If event exceeds _SIZE_CAP_BYTES:
      1. Truncate gen_ai.tool.call.arguments and gen_ai.tool.call.result first.
      2. If still over cap, replace with a minimal sentinel event.
    Soft-fail: exceptions logged, sentinel returned.
    """
    try:
        encoded = json.dumps(event, ensure_ascii=False).encode("utf-8")
        if len(encoded) <= _SIZE_CAP_BYTES:
            return event

        # Attempt field truncation
        truncated = dict(event)
        original_size = len(encoded)
        for field in ("gen_ai.tool.call.arguments", "gen_ai.tool.call.result"):
            if field in truncated and isinstance(truncated[field], str):
                truncated[field] = truncated[field][:512] + f"...[truncated:{original_size}B]"

        encoded2 = json.dumps(truncated, ensure_ascii=False).encode("utf-8")
        if len(encoded2) <= _SIZE_CAP_BYTES:
            return truncated

        # Pathological case: metadata bloat — replace with sentinel
        logger.warning(
            "Event still %d bytes after field truncation (cap %d); dropping to sentinel",
            len(encoded2), _SIZE_CAP_BYTES,
        )
        return {
            "gen_ai.event.name": "truncated",
            "gen_ai.event.timestamp": event.get("gen_ai.event.timestamp", ""),
            "_dropped_size": original_size,
        }
    except Exception as exc:
        logger.warning("apply_size_cap failed: %s", exc)
        return event
