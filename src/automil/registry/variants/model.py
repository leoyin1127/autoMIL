"""ModelVariant ABC — per-parent model variants (REG-01 / D-21).

Subclasses live under `<consumer>/<dataset>/automil/variants/<parent>/<name>.py`
and are registered via the `@register` decorator (Plan 01-02). They are
instantiated by `train.py` after the registry resolves the variant's class.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Type-only import — keeps this module loadable without torch installed
    # (D-24: framework does NOT depend on torch; the synthetic mini-consumer
    # in Plan 01-12 is torch-free, and Phase 8 / DEC-03 owns the framework
    # output type).
    from torch import Tensor  # noqa: F401

logger = logging.getLogger(__name__)


class ModelVariant(ABC):
    """Per-parent model variant.

    Subclasses MUST implement `forward`. Return shape is whatever the parent
    model returns (D-24) — Phase 1 does NOT introduce an `AggregatorOutput`
    framework type. CLAM, for example, returns `(logits, Y_prob, Y_hat,
    instance_dict)`; sklearn-iris (Phase 8 / DEC-02) returns its own shape.
    The parent's wrapper code in `train.py` is responsible for any conversion.
    """

    @abstractmethod
    def forward(self, features: Any, coords: Optional[Any] = None) -> Any:
        """Forward pass on a bag of feature vectors.

        Args:
            features: Tensor of shape (N, D) where N=instances, D=feature dim.
            coords: Optional spatial coordinates of shape (N, 2) for
                    positional models. May be None for parents that ignore
                    spatial structure.

        Returns:
            Whatever the parent model returns (D-24).
        """

    def instance_attention(self, features: Any, coords: Optional[Any] = None) -> Optional[Any]:
        """Optional per-instance attention output. Default returns None.

        Variants that compute per-instance attention (CLAM, AB-MIL, DSMIL)
        override this to surface the attention weights for downstream
        interpretability / clustering / gate-eval tooling.
        """
        return None
