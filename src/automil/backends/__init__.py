"""Backend abstraction (BCK-01..04 / D-51..D-77).

Plan 02-01 ships the public re-export surface (Backend ABC + dataclasses +
BackendError).  Plan 02-02 extends this with BACKENDS registry dict,
``register`` decorator, and ``_clear_backends`` test utility.
"""
from __future__ import annotations

import logging

from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends.errors import BackendError

logger = logging.getLogger(__name__)

__all__ = ["Backend", "JobHandle", "JobSpec", "JobState", "BackendError"]
