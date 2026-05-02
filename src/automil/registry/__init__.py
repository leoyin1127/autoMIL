"""Variant registry subpackage (REG-01 / REG-02 / REG-04 / REG-06 / REG-07).

Plan 01-01 ships ABCs + VariantSpec. Plan 01-03 adds RegistryConfig + loader.
Plan 01-02 will add the @register decorator + module-level singleton dicts
(MODEL_VARIANTS, LOSS_VARIANTS, POLICY_VARIANTS) + resolver functions
(resolve_model, resolve_loss, resolve_policy). This file's import surface is
forward-compatible with Plan 01-02 — only the public API that exists today
is exported.
"""
from __future__ import annotations

import logging

from automil.registry.config import RegistryConfig, load_registry_config
from automil.registry.spec import Kind, VariantSpec
from automil.registry.variants import LossVariant, ModelVariant, PolicyVariant

logger = logging.getLogger(__name__)

__all__ = [
    "Kind",
    "VariantSpec",
    "ModelVariant",
    "LossVariant",
    "PolicyVariant",
    "RegistryConfig",
    "load_registry_config",
]
