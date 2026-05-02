"""@register decorator + resolver functions (REG-02 / D-27 / D-35)."""
from __future__ import annotations

import logging
from typing import Callable, TypeVar

from automil.registry._state import (
    LOSS_VARIANTS,
    MODEL_VARIANTS,
    POLICY_VARIANTS,
    SPEC_STORE,
)
from automil.registry.spec import VariantSpec
from automil.registry.variants import LossVariant, ModelVariant, PolicyVariant

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=type)

# Map from kind -> (ABC class, dict, key-builder lambda taking (parent, name) -> dict_key)
_KIND_TABLE: dict[str, tuple[type, dict, Callable[[str | None, str], object]]] = {
    "model": (ModelVariant, MODEL_VARIANTS, lambda parent, name: (parent, name)),
    "loss": (LossVariant, LOSS_VARIANTS, lambda parent, name: name),
    "policy": (PolicyVariant, POLICY_VARIANTS, lambda parent, name: name),
}


class RegistrationError(Exception):
    """Raised when @register fails (duplicate name, kind/class mismatch, parent mismatch).

    Production-grade error messages: name what failed, why it failed, and
    what the operator should do (PATTERNS.md §"Pattern catalog" #7).
    """


def register(spec: VariantSpec) -> Callable[[T], T]:
    """Decorator: validate the spec + class + uniqueness; insert into singleton.

    Args:
        spec: A frozen VariantSpec describing the variant.

    Returns:
        The decorated class itself (decorator pattern — class identity preserved).

    Raises:
        RegistrationError: on any validation failure. The error message names
                           what failed, why it failed, and how to fix it.
    """
    if spec.kind not in _KIND_TABLE:
        raise RegistrationError(
            f"Refusing to register {spec.name!r}: unknown kind {spec.kind!r}. "
            f"Phase 1 supports kinds {list(_KIND_TABLE.keys())} only (D-23). "
            f"Use a future phase to introduce 'recipe' or 'inference' kinds."
        )

    abc_class, store, key_builder = _KIND_TABLE[spec.kind]

    # Parent semantics (D-21):
    #   kind=model  -> parent MUST be set
    #   kind=loss   -> parent MUST be None
    #   kind=policy -> parent MUST be None
    if spec.kind == "model" and spec.parent is None:
        raise RegistrationError(
            f"Refusing to register {spec.name!r}: kind=model requires parent != None. "
            f"Pass `parent=<parent_name>` (e.g., 'clam_mb') in the VariantSpec, or "
            f"use kind='loss'/'policy' for parent-agnostic variants."
        )
    if spec.kind in ("loss", "policy") and spec.parent is not None:
        raise RegistrationError(
            f"Refusing to register {spec.name!r}: kind={spec.kind} must have parent=None "
            f"(loss and policy variants are parent-agnostic per D-21). "
            f"Got parent={spec.parent!r}; remove it or change kind to 'model'."
        )

    def _decorator(cls: T) -> T:
        if not (isinstance(cls, type) and issubclass(cls, abc_class)):
            raise RegistrationError(
                f"Refusing to register {cls.__name__!r}: kind={spec.kind} but class "
                f"is not a subclass of {abc_class.__name__}. "
                f"Either change `kind=` in the spec or subclass the matching ABC."
            )

        key = key_builder(spec.parent, spec.name)
        if key in store:
            existing = store[key]
            raise RegistrationError(
                f"Refusing to register {cls.__qualname__!r} as {spec.kind} "
                f"variant {spec.name!r}: key {key!r} is already registered "
                f"to {existing.__qualname__!r}. Either rename one of them "
                f"or pass --name to port-variant to disambiguate."
            )

        store[key] = cls
        SPEC_STORE[(spec.kind, spec.parent, spec.name)] = spec
        logger.info(
            "Registered %s variant %r (parent=%r) -> %s",
            spec.kind, spec.name, spec.parent, cls.__qualname__,
        )
        return cls

    return _decorator


def resolve_model(parent: str, name: str) -> type[ModelVariant]:
    """Look up a registered model variant by (parent, name).

    Raises:
        KeyError: if (parent, name) is not registered. Message lists every
                  available (parent, name) pair so the operator can correct
                  the config (D-35).
    """
    try:
        return MODEL_VARIANTS[(parent, name)]
    except KeyError:
        available = sorted(MODEL_VARIANTS.keys())
        raise KeyError(
            f"No model variant registered for (parent={parent!r}, name={name!r}). "
            f"available: {available}. "
            f"Run `automil refresh-registry` if you recently added a variant module."
        ) from None


def resolve_loss(name: str) -> type[LossVariant]:
    """Look up a registered loss variant by name."""
    try:
        return LOSS_VARIANTS[name]
    except KeyError:
        available = sorted(LOSS_VARIANTS.keys())
        raise KeyError(
            f"No loss variant registered for name={name!r}. "
            f"available: {available}. "
            f"Run `automil refresh-registry` if you recently added a variant module."
        ) from None


def resolve_policy(name: str) -> type[PolicyVariant]:
    """Look up a registered policy variant by name."""
    try:
        return POLICY_VARIANTS[name]
    except KeyError:
        available = sorted(POLICY_VARIANTS.keys())
        raise KeyError(
            f"No policy variant registered for name={name!r}. "
            f"available: {available}. "
            f"Run `automil refresh-registry` if you recently added a variant module."
        ) from None
