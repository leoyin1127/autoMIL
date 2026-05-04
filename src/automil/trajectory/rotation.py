"""Trajectory rotation manager — 5 MB soft / 50 MB hard (TRJ-03 / D-84).

Full implementation delivered in Plan 03-04.
This stub exposes the public interface so Plans 03-01..03-03 can import without error.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_SOFT_DEFAULT = 5 * 1024 * 1024   # 5 MB
_HARD_DEFAULT = 50 * 1024 * 1024  # 50 MB


@dataclass(frozen=True)
class RotationManager:
    """Manages trajectory file rotation by size threshold (D-84).

    soft_bytes: rotate to trajectory.<n>.jsonl when exceeded
    hard_bytes: refuse new events when exceeded (log CRITICAL, return False)
    """
    soft_bytes: int = _SOFT_DEFAULT
    hard_bytes: int = _HARD_DEFAULT

    def check_and_rotate(self, path: Path, fd_cache: dict) -> bool:
        """Check size thresholds and rotate if needed.

        Returns True if file is ready for writing (including after rotation).
        Returns False if hard limit exceeded (soft-fail — caller logs CRITICAL).
        Full implementation in Plan 03-04.
        """
        # Stub: passes through; 03-04 provides the full implementation
        try:
            if not path.exists():
                return True
            size = path.stat().st_size
            if size >= self.hard_bytes:
                logger.critical(
                    "Trajectory hard limit (%d bytes) reached at %s; refusing new events",
                    self.hard_bytes, path,
                )
                return False
            return True
        except Exception as exc:
            logger.warning("RotationManager.check_and_rotate failed: %s", exc)
            return True  # safe pass-through on error
