"""PolicyVariant ABC — parent-agnostic training-policy variants (REG-01 / D-21).

Policies wrap the optimizer / scheduler to implement strategies like SAM,
Lookahead, gradient accumulation, etc. The default `step` delegates to
`opt.step()` so non-SAM-style policies need only override `wrap_optimizer`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class PolicyVariant(ABC):
    """Parent-agnostic training-policy variant."""

    @abstractmethod
    def wrap_optimizer(self, opt: Any) -> Any:
        """Wrap (or replace) the optimizer; return the wrapped instance."""

    def wrap_scheduler(self, sched: Any) -> Any:
        """Optional scheduler wrapping. Default returns the input unchanged."""
        return sched

    def step(self, loss: Any, opt: Any) -> None:
        """Default step: delegate to opt.step() after backward.

        SAM-style two-step policies override this to implement `first_step`
        + `second_step`. The default works for vanilla / Lookahead-only /
        gradient-accumulation policies.
        """
        opt.step()
