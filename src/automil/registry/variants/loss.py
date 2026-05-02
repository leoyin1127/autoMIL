"""LossVariant ABC — parent-agnostic loss variants (REG-01 / D-21)."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LossVariant(ABC):
    """Parent-agnostic loss variant.

    Loss variants do not depend on the parent model architecture — they
    receive logits + targets and (optionally) per-instance logits + labels
    from the model's bag-attention output.
    """

    @abstractmethod
    def __call__(
        self,
        logits: Any,
        targets: Any,
        *,
        instance_logits: Optional[Any] = None,
        instance_labels: Optional[Any] = None,
    ) -> Any:
        """Compute loss.

        Args:
            logits: Bag-level logits.
            targets: Bag-level targets.
            instance_logits: Optional per-instance logits (e.g., CLAM's instance
                             classifier). Loss may use these if not None.
            instance_labels: Optional pseudo-labels for instance_logits.

        Returns:
            A scalar loss tensor.
        """
