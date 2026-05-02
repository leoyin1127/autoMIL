"""Variant ABCs subpackage. Re-exports the three sibling ABCs."""
from __future__ import annotations

from automil.registry.variants.loss import LossVariant
from automil.registry.variants.model import ModelVariant
from automil.registry.variants.policy import PolicyVariant

__all__ = ["ModelVariant", "LossVariant", "PolicyVariant"]
