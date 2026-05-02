"""Variant registry subpackage (REG-01 / REG-02 / REG-04 / REG-06 / REG-07).

Plan 01-01 ships ABCs + VariantSpec. Plan 01-03 adds RegistryConfig + loader.
Plan 01-02 (this plan) adds @register + resolvers + RegistrationError.
Plan 01-04 will add submit-time validators (interface, purity).
Plan 01-05 will add runtime identity validator.
Plan 01-06 will add the directory scanner used by `automil refresh-registry`.
"""
from __future__ import annotations

import logging

# Plan 01-01 surface (preserved):
from automil.registry.config import RegistryConfig, load_registry_config
from automil.registry.spec import Kind, VariantSpec
from automil.registry.variants import LossVariant, ModelVariant, PolicyVariant

# Plan 01-02 surface (additive):
from automil.registry.registrar import (
    RegistrationError,
    register,
    resolve_loss,
    resolve_model,
    resolve_policy,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Types
    "Kind",
    "VariantSpec",
    "ModelVariant",
    "LossVariant",
    "PolicyVariant",
    # Config (Plan 01-03)
    "RegistryConfig",
    "load_registry_config",
    # Registry API (Plan 01-02)
    "RegistrationError",
    "register",
    "resolve_model",
    "resolve_loss",
    "resolve_policy",
]
