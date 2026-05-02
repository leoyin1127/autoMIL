"""Variant registry subpackage (REG-01 / REG-02).

Plan 01-01 ships ABCs + VariantSpec only. Plan 01-02 adds the @register
decorator + module-level singleton dicts (MODEL_VARIANTS, LOSS_VARIANTS,
POLICY_VARIANTS) + resolver functions (resolve_model, resolve_loss,
resolve_policy). This file's import surface is forward-compatible with
Plan 01-02 — only the public API that exists today is exported.
"""
from __future__ import annotations

import logging

from automil.registry.spec import Kind, VariantSpec
from automil.registry.variants import LossVariant, ModelVariant, PolicyVariant

logger = logging.getLogger(__name__)

__all__ = [
    "Kind",
    "VariantSpec",
    "ModelVariant",
    "LossVariant",
    "PolicyVariant",
]
