"""Runtime declaration — reads AUTOMIL_RUNTIME env var (TRJ-04 / D-87).

Runtime is EXPLICIT, never inferred.
get_runtime() returns "unknown" if AUTOMIL_RUNTIME is not set.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def get_runtime() -> str:
    """Return the declared runtime identifier.

    Reads AUTOMIL_RUNTIME environment variable.
    Returns "unknown" if unset — explicit declaration is required; never inferred (D-87).
    Valid values: "claude-code" | "opencode" | "codex" |
                  "deepseek-via-opencode" | "deepseek-via-codex" | "unknown"
    Never raises.
    """
    return os.environ.get("AUTOMIL_RUNTIME", "unknown")
