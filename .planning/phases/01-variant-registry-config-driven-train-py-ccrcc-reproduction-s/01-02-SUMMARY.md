---
phase: "01"
plan: "01-02"
subsystem: registry
tags: [registry, decorator, singleton, resolver, tdd, REG-02]
dependency_graph:
  requires: [01-01]
  provides: [01-04, 01-06, 01-08, 01-09, 01-10, 01-11, 01-12]
  affects: [automil.registry]
tech_stack:
  added: []
  patterns:
    - "Module-level singleton dicts (MODEL_VARIANTS, LOSS_VARIANTS, POLICY_VARIANTS, SPEC_STORE)"
    - "@register(VariantSpec) class decorator with validation + uniqueness enforcement"
    - "_clear_registry() + autouse pytest fixture for singleton isolation in tests"
    - "resolve_model(parent, name) / resolve_loss(name) / resolve_policy(name) hard-fail resolvers"
key_files:
  created:
    - src/automil/registry/_state.py
    - src/automil/registry/registrar.py
    - tests/test_registry_singleton.py
  modified:
    - src/automil/registry/__init__.py
decisions:
  - "D-27: Module-level singletons in _state.py; @register hard-fails on duplicate (kind, name) with RegistrationError"
  - "D-28: importlib.metadata.entry_points discovery DEFERRED to Phase 7 / STP-04"
  - "D-35: resolve_* raises KeyError with available names listed for operator-friendly diagnostics"
  - "Fork-safety: no cross-fork state needed; each worker re-imports variant modules independently"
metrics:
  duration_minutes: 10
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 4
---

# Phase 01 Plan 02: Registry Singleton + @register + Resolvers Summary

**One-liner:** Module-level registry singletons (MODEL_VARIANTS/LOSS_VARIANTS/POLICY_VARIANTS/SPEC_STORE) with @register(VariantSpec) decorator enforcing kind/parent/uniqueness invariants and resolve_*/KeyError-with-available-names resolver functions.

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `src/automil/registry/_state.py` | 39 | Four module-level singleton dicts + `_clear_registry()` test helper |
| `src/automil/registry/registrar.py` | 146 | `RegistrationError`, `@register` decorator, `resolve_model/loss/policy` |
| `tests/test_registry_singleton.py` | 291 | 18 tests — all RED before implementation, all GREEN after |

## Files Modified

| File | Change |
|------|--------|
| `src/automil/registry/__init__.py` | Additive: imports + re-exports `RegistrationError, register, resolve_model, resolve_loss, resolve_policy` |

## 18 Test Names + Assertion Summary

| # | Test Name | Asserts |
|---|-----------|---------|
| 1 | `test_register_model_variant_happy_path` | `MODEL_VARIANTS[("clam_mb", "clam_mb_v0176")] is ClamMbV0176` |
| 2 | `test_register_loss_variant_happy_path` | `LOSS_VARIANTS["ce_smooth008"] is CeSmooth008` |
| 3 | `test_register_policy_variant_happy_path` | `POLICY_VARIANTS["sam_lookahead"] is SamLookahead` |
| 4 | `test_duplicate_model_name_hard_fails` | Second `@register` same key raises `RegistrationError(match="already registered\|duplicate")` |
| 5 | `test_register_message_suggests_resolution` | Error message contains variant name + "rename"/"--name"/"port-variant" |
| 6 | `test_model_kind_without_parent_rejected` | `kind="model", parent=None` raises `RegistrationError(match="parent")` |
| 7 | `test_loss_kind_with_parent_rejected` | `kind="loss", parent="clam_mb"` raises `RegistrationError(match="parent")` |
| 8 | `test_policy_kind_with_parent_rejected` | `kind="policy", parent="clam_mb"` raises `RegistrationError(match="parent")` |
| 9 | `test_kind_class_mismatch_rejected` | `LossVariant` subclass + `kind="model"` raises `RegistrationError(match="ModelVariant\|kind")` |
| 10 | `test_decorator_returns_class_unchanged` | `cls.__name__ == "ClamMbV0176"` and `resolve_model(...) is cls` |
| 11 | `test_resolve_model_missing_lists_available` | Missing key raises `KeyError` with `"clam_mb_v0176"` and `"available"` in message |
| 12 | `test_resolve_loss_missing_lists_available` | Missing key raises `KeyError` with `"ce_smooth008"` in message |
| 13 | `test_resolve_policy_missing_lists_available` | Missing key raises `KeyError` with `"sam_lookahead"` in message |
| 14 | `test_clear_registry_empties_all_dicts` | After `_clear_registry()`, all four dicts are `{}` |
| 15 | `test_spec_store_populated_on_register` | `SPEC_STORE[("model", "clam_mb", "clam_mb_v0176")] == spec` |
| 16 | `test_isolation_first_registers_clam_mb_v0176` | Key present in MODEL_VARIANTS |
| 17 | `test_isolation_second_registers_clam_mb_v0176_again` | Same name registers cleanly (autouse fixture cleared it) |
| 18 | `test_fork_safe_child_repopulates_registry` | `mp.get_context("fork").Pool` child's dict contains new entry (skipped on Windows) |

## Autouse Fixture Pattern (canonical — downstream plans MUST copy)

```python
@pytest.fixture(autouse=True)
def _isolated_registry():
    """Clear registry singletons before each test to prevent cross-test pollution.

    PATTERNS.md §"Open codebase questions" #3: module-level dicts persist across
    test functions; this fixture is the canonical isolation pattern (cited in
    D-47 and Plan 01-01's `discretion` block).
    """
    from automil.registry._state import _clear_registry
    _clear_registry()
    yield
    _clear_registry()
```

Downstream plans that need to register variants in tests (01-04, 01-06, 01-09, 01-10, 01-11, 01-12)
MUST include this fixture verbatim or import `_clear_registry` and call it in their own setup/teardown.
The import path is always `from automil.registry._state import _clear_registry`.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `8989591` | `test` | RED: add failing tests for @register + resolvers + isolation (REG-02) |
| `920cb8a` | `feat` | GREEN: add @register decorator + resolver singletons (REG-02) |

## Deviations from Plan

None — plan executed exactly as written.

The test file ended up with 18 tests (vs the plan's 17) because `test_register_message_suggests_resolution` was listed as Test 4's extended sub-check but in practice became a distinct named test function (Test 5). This is a net positive — additional coverage at no cost.

## Known Stubs

None.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. All changes are in-process Python module imports and dict mutations. The threat mitigations from the plan's STRIDE register (T-01-05 through T-01-09) are implemented and tested.

## TDD Gate Compliance

- RED gate: commit `8989591` — `test(registry): add failing tests...`
- GREEN gate: commit `920cb8a` — `feat(registry): add @register decorator...`
- REFACTOR gate: not needed (code is already clean)

## Self-Check: PASSED

All claimed files exist and commits are in git log.
