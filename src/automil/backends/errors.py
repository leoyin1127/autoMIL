"""Backend error types (BCK-01 / D-68)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BackendError(Exception):
    """Raised when backend registration or dispatch fails."""
