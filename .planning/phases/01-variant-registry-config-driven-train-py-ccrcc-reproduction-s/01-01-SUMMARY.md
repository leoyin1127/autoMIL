---
phase: "01"
plan: "01-01"
subsystem: "registry"
tags: ["registry", "abc", "variant-spec", "frozen-dataclass", "type-system"]
dependency_graph:
  requires: []
  provides:
    - "automil.registry.ModelVariant"
    - "automil.registry.LossVariant"
    - "automil.registry.PolicyVariant"
    - "automil.registry.VariantSpec"
    - "automil.registry.Kind"
  affects: []
tech_stack:
  added:
    - "src/automil/registry/ (new subpackage)"
    - "dataclasses.dataclass(frozen=True)"
    - "abc.ABC + abc.abstractmethod"
    - "typing.Literal (Kind taxonomy)"
    - "typing.TYPE_CHECKING guard (torch-free import)"
  patterns:
    - "Frozen dataclass as immutable registry key + provenance record (D-22)"
    - "Three sibling ABCs with interface segregation (D-21)"
    - "TYPE_CHECKING guard for optional heavy dependencies (D-24)"
    - "module-level logger = logging.getLogger(__name__) (PATTERNS.md §9)"
key_files:
  created:
    - "src/automil/registry/__init__.py"
    - "src/automil/registry/spec.py"
    - "src/automil/registry/variants/__init__.py"
    - "src/automil/registry/variants/model.py"
    - "src/automil/registry/variants/loss.py"
    - "src/automil/registry/variants/policy.py"
    - "tests/test_registry_spec.py"
    - "tests/test_registry_variants_abc.py"
  modified: []
decisions:
  - "D-21: Three sibling ABCs (not one polymorphic) — interface segregation principle"
  - "D-22: VariantSpec @dataclass(frozen=True) with 8 named fields; mutations is tuple not list"
  - "D-23: Kind = Literal['model','loss','policy'] — Phase 1 exhaustive; recipe/inference deferred"
  - "D-24: No AggregatorOutput; ModelVariant.forward returns parent's native return shape"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02T07:32:47Z"
  tasks_completed: 3
  files_created: 8
  tests_added: 22
  tests_total: 135
  baseline_tests: 113
---

# Phase 01 Plan 01: Variant ABC Family + VariantSpec Dataclass Summary

**One-liner:** Three sibling ABCs (ModelVariant, LossVariant, PolicyVariant) + frozen VariantSpec provenance record with Literal["model","loss","policy"] kind taxonomy and TYPE_CHECKING torch guard.

## Files Created

| File | Lines | Role |
|------|-------|------|
| `src/automil/registry/__init__.py` | 24 | Public registry namespace; re-exports ABCs + VariantSpec + Kind |
| `src/automil/registry/spec.py` | 35 | VariantSpec @dataclass(frozen=True) + Kind Literal type alias |
| `src/automil/registry/variants/__init__.py` | 8 | Re-exports the three sibling ABCs |
| `src/automil/registry/variants/model.py` | 54 | ModelVariant(ABC) with forward (abstract) + instance_attention (optional) |
| `src/automil/registry/variants/loss.py` | 39 | LossVariant(ABC) with __call__ (abstract) |
| `src/automil/registry/variants/policy.py` | 34 | PolicyVariant(ABC) with wrap_optimizer (abstract) + wrap_scheduler/step (defaults) |
| `tests/test_registry_spec.py` | ~100 | 10 tests: construction, frozen mutation, tuple immutability, default mutations, loss/policy None parent, Kind Literal exhaustiveness, D-23 guard, equality, hashability |
| `tests/test_registry_variants_abc.py` | ~140 | 12 tests: ABC abstractness, missing-forward rejection, D-24 shape, defaults, torch-free guard, package re-export |

## Test Coverage (22 new tests)

### test_registry_spec.py (10 tests)

| Test | Invariant |
|------|-----------|
| `test_construction_happy_path` | VariantSpec accepts all D-22 fields; attributes match |
| `test_frozen_mutation_refused` | `spec.composite = 0.99` raises `FrozenInstanceError` |
| `test_mutations_tuple_immutable` | `spec.mutations` is `tuple`; `.append()` raises `AttributeError` |
| `test_mutations_default_empty` | Spec built without mutations has `mutations == ()` |
| `test_loss_kind_allows_none_parent` | `kind="loss", parent=None` constructs without error |
| `test_policy_kind_allows_none_parent` | `kind="policy", parent=None` constructs without error |
| `test_kind_type_alias_is_literal_with_three_values` | `get_args(Kind) == {"model","loss","policy"}` |
| `test_phase_1_kind_exhaustiveness_d23` | D-23 guard: "recipe" and "inference" NOT in Kind |
| `test_structural_equality` | Two specs with identical fields are equal |
| `test_hashable_for_dict_key` | `hash(spec)` returns int; usable as dict key |

### test_registry_variants_abc.py (12 tests)

| Test | Invariant |
|------|-----------|
| `test_model_variant_abstract_cannot_instantiate` | `ModelVariant()` raises `TypeError` matching "abstract" |
| `test_loss_variant_abstract_cannot_instantiate` | `LossVariant()` raises `TypeError` matching "abstract" |
| `test_policy_variant_abstract_cannot_instantiate` | `PolicyVariant()` raises `TypeError` matching "abstract" |
| `test_subclass_without_forward_cannot_instantiate` | Subclass without `forward` raises `TypeError` |
| `test_concrete_model_variant_returns_parent_shape_d24` | Concrete subclass returning CLAM 4-tuple works; no AggregatorOutput |
| `test_instance_attention_default_returns_none` | Subclass not overriding `instance_attention` returns None |
| `test_concrete_loss_variant_callable` | Concrete LossVariant `__call__` executes and returns expected value |
| `test_policy_wrap_scheduler_default_identity` | Default `wrap_scheduler` returns input unchanged |
| `test_policy_step_default_delegates_to_opt` | Default `step` calls `opt.step()` exactly once |
| `test_no_top_level_torch_import_in_model_py` | model.py has no top-level torch import outside TYPE_CHECKING block |
| `test_package_re_exports_abcs_and_spec` | `from automil.registry import ModelVariant, LossVariant, PolicyVariant, VariantSpec` resolves |
| `test_variants_subpackage_re_exports_abcs` | `from automil.registry.variants import ...` resolves all three ABCs |

## Commit

| Hash | Message |
|------|---------|
| `0daa6b5` | `feat(registry): add Variant ABC family + VariantSpec dataclass (REG-01)` |

## Deviations from Plan

None — plan executed exactly as written. All D-21/D-22/D-23/D-24 decisions honored verbatim.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. Plan 01-01 ships pure-Python ABCs + a frozen dataclass — no I/O surface. Threat mitigations T-01-01 through T-01-03 implemented as specified (FrozenInstanceError, D-23 exhaustiveness guard, TYPE_CHECKING torch import guard).

## Self-Check: PASSED

- `src/automil/registry/__init__.py` FOUND
- `src/automil/registry/spec.py` FOUND
- `src/automil/registry/variants/__init__.py` FOUND
- `src/automil/registry/variants/model.py` FOUND
- `src/automil/registry/variants/loss.py` FOUND
- `src/automil/registry/variants/policy.py` FOUND
- `tests/test_registry_spec.py` FOUND
- `tests/test_registry_variants_abc.py` FOUND
- Commit `0daa6b5` FOUND
- 135 tests pass (113 baseline + 22 new)
