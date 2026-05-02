---
phase: "01"
plan: "01-05"
subsystem: registry/validators
tags: [validator, identity, tdd, registry, torch]
dependency_graph:
  requires: [01-01, 01-02, 01-03, 01-04]
  provides: [IdentityValidator, validation_failure.json]
  affects: [01-08, 01-12]
tech_stack:
  added: []
  patterns:
    - "Lazy torch import inside method body (Plan 01-01 invariant preserved)"
    - "PATTERNS.md §3 atomic write: tempfile.mkstemp + os.rename for validation_failure.json"
    - "TDD: RED commit 7b6dbc8, GREEN commit d46d472"
key_files:
  created:
    - src/automil/registry/validators/identity.py
    - tests/test_registry_validator_identity.py
  modified:
    - src/automil/registry/validators/__init__.py
decisions:
  - "D-30: identity validator runs at instantiate-time (not submit-time) — implemented as a standalone class callers invoke before first epoch"
  - "D-31: mode='free' validates dtype + rank only; mode='architecture-preserving' adds param_count_pct + per-constraint check"
  - "D-32: hard-fail with atomic-write validation_failure.json + raise ValidationError; no soft-warn substitute"
  - "Unknown constraint kinds are logged and skipped for forward compatibility (future phases add output_rank, layer_shape)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 15
  prior_tests: 233
  total_tests: 248
---

# Phase 01 Plan 05: Identity Validator + Mode-Aware Strictness Summary

**One-liner:** Runtime stub-forward identity validator with free/architecture-preserving mode flag, atomic validation_failure.json checkpoint, and lazy torch import.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `7b6dbc8` | test | RED: 15 failing tests for IdentityValidator (constraints parsing, lazy torch, free mode, arch-preserving, schema, atomic write, re-export) |
| `d46d472` | feat | GREEN: identity.py + validators/__init__.py — all 248 tests pass |

## Files Created / Modified

| File | Lines | Role |
|------|-------|------|
| `src/automil/registry/validators/identity.py` | 394 | `IdentityValidator` + `IdentityConstraint` + `_parse_constraints` + `_atomic_write_json` |
| `tests/test_registry_validator_identity.py` | 360 | 15 tests covering all behavior branches |
| `src/automil/registry/validators/__init__.py` | +3 | Additive re-export of `IdentityValidator` |

## Test Status (15 net-new tests)

| Test | Category | Status |
|------|----------|--------|
| `test_constraints_parsing_happy` | constraints | PASS |
| `test_constraints_parsing_malformed` | constraints | PASS |
| `test_constraints_empty_ok` | constraints | PASS |
| `test_no_top_level_torch_in_identity_module` | lazy torch | PASS |
| `test_identity_validator_imports_without_torch` | lazy torch | PASS |
| `test_free_mode_happy_path` | free mode | PASS (torch) |
| `test_free_mode_rank_mismatch` | free mode | PASS (torch) |
| `test_free_mode_dtype_mismatch` | free mode | PASS (torch) |
| `test_free_mode_skips_param_count` | free mode | PASS (torch) |
| `test_arch_preserving_param_count_happy` | arch-preserving | PASS (torch) |
| `test_arch_preserving_param_count_fail` | arch-preserving | PASS (torch) |
| `test_arch_preserving_no_constraints_degrades_to_dtype_rank` | arch-preserving | PASS (torch) |
| `test_validation_failure_json_schema` | failure JSON | PASS (torch) |
| `test_validation_failure_json_atomic_write` | failure JSON | PASS (torch) |
| `test_validators_init_re_exports_identity` | re-export | PASS |

- 9 tests are `@requires_torch` guarded (skip on torch-less machines)
- 6 tests are always-on (constraints parsing, lazy torch, re-export)
- Full suite: 248 tests, 0 failures

## validation_failure.json Schema

```json
{
  "validator_name": "identity",
  "mode": "free",
  "variant_class": "BadVariant",
  "parent_class": "Parent",
  "reason": "output rank mismatch: variant=1, parent=2",
  "expected": {"rank": 2, "dtype": "torch.float32"},
  "actual":   {"rank": 1, "dtype": "torch.float32"},
  "constraints_evaluated": [],
  "timestamp": "2026-05-02T11:00:00+00:00"
}
```

Written atomically via `tempfile.mkstemp` + `os.rename` (PATTERNS.md §3). No `.tmp` leftover on failure.

## Deviations from Plan

None — plan executed exactly as written. The test count increased from 13 to 15 (added `test_constraints_empty_ok` as a bonus coverage case for the empty-tuple path); this exceeds the ≥10 net-new requirement.

## TDD Gate Compliance

- RED gate: `test(01-05)` commit `7b6dbc8` — 15 tests all failing before implementation
- GREEN gate: `feat(registry)` commit `d46d472` — all 15 tests passing, 248 total

## Known Stubs

None — no placeholder data, no hardcoded empty returns affecting behavior. `IdentityValidator.check()` returns `None` on success (convention matches `InterfaceValidator`/`PurityValidator`).

## Threat Flags

No new network endpoints, auth paths, file access patterns, or trust boundary crossings beyond those already in the plan's threat model (T-01-19, T-01-20, T-01-21, T-01-22).

## Consumer Follow-up Note

Per D-49 and plan key_links: `IdentityValidator().check(...)` integration into the consumer's `train.py` (BEFORE first epoch) is deferred to Plan 01-12 (synthetic mini-consumer). Phase 1 ships the validator API; the training-script integration is post-Phase-1.

## Self-Check: PASSED

- `src/automil/registry/validators/identity.py`: FOUND
- `tests/test_registry_validator_identity.py`: FOUND
- Commit `7b6dbc8`: FOUND
- Commit `d46d472`: FOUND
- 248 tests passing: CONFIRMED
