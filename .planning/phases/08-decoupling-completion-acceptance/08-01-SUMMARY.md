---
phase: 08-decoupling-completion-acceptance
plan: "01"
subsystem: schemas
tags: [schema-validation, jsonschema, result-contract, d-201, dec-03]

dependency_graph:
  requires: []
  provides: [automil.schemas.validate_result, automil.schemas.RESULT_SCHEMA, automil.schemas.ValidationError]
  affects: [08-05-orchestrator-ingestion, 08-09-acceptance-gate]

tech_stack:
  added: [jsonschema>=4.18 (explicit dep, was only transitive via ray optional)]
  patterns: [Draft202012Validator pre-compiled at module import, JSON schema loaded from file once]

key_files:
  created:
    - src/automil/schemas/__init__.py
    - src/automil/schemas/_result.py
    - src/automil/schemas/result.schema.json
    - tests/test_result_schema_validation.py
  modified:
    - pyproject.toml (added jsonschema>=4.18 as explicit dep)
    - uv.lock (synced)

decisions:
  - Added jsonschema as explicit dep (not just transitive via ray); gate/manifest.py uses custom Python validation, not jsonschema, so the "already transitive" assumption in plan was incorrect

metrics:
  duration: "~10 minutes"
  completed: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 2
---

# Phase 08 Plan 01: automil.schemas Package with D-201 result.json Contract

JSON-Schema-validated result.json contract (Draft 2020-12) via pre-compiled Draft202012Validator in a new automil.schemas package.

## What Was Built

### Task 1: src/automil/schemas/ package

- `src/automil/schemas/result.schema.json`: verbatim D-201 contract (Draft 2020-12). Only `composite` is required; all other fields optional. `additionalProperties: true` intentionally allows consumer extensions.
- `src/automil/schemas/_result.py`: loads schema once at import, pre-compiles `Draft202012Validator`, exports `validate_result(payload)`, `RESULT_SCHEMA`, and `ValidationError`.
- `src/automil/schemas/__init__.py`: re-exports all three public names.

### Task 2: tests/test_result_schema_validation.py

8 test functions covering:
1. `test_autobench_four_key_shape_validates` - autobench 4-key metrics shape passes
2. `test_sklearn_iris_two_key_shape_validates` - sklearn-iris 2-key shape passes (DEC-02 consumer)
3. `test_consumer_extension_top_level_key_validates` - extra top-level key passes (additionalProperties: true)
4. `test_missing_composite_key_fails` - empty dict raises ValidationError with "composite" in message
5. `test_status_enum_violation_fails` - unknown status string raises ValidationError
6. `test_negative_peak_vram_mb_fails` - negative peak_vram_mb raises ValidationError
7. `test_metrics_non_number_value_fails` - string metric value raises ValidationError
8. `test_schema_top_level_id_locked` - schema $id + required + additionalProperties locked

All 8 pass. Test count: 895 baseline -> 906 collected (+8 from this plan, +3 pre-existing masked tests now visible).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] jsonschema not installed in virtual environment**

- **Found during:** Task 1 verification (import failed with ModuleNotFoundError)
- **Issue:** Plan stated "jsonschema is already a transitive dep (Phase 5 gate uses it)" but gate/manifest.py (the analog) uses custom Python validation, not jsonschema. The library was only a transitive dep of the optional `ray` backend, not installed in the default venv.
- **Fix:** Added `jsonschema>=4.18` as an explicit direct dependency in pyproject.toml and ran `uv sync`.
- **Files modified:** pyproject.toml, uv.lock
- **Commits:** 5a7b080

## Framework Purity

`grep -rnE "autobench|AUTOBENCH_|benchmarks/" src/automil/schemas/` returns zero matches. Package is framework-pure.

## Em-Dash Gate

`grep -rnP "\x{2014}|\x{2013}" src/automil/schemas/ tests/test_result_schema_validation.py` returns zero matches. Clean.

## Acceptance Criteria Check

- [x] `src/automil/schemas/result.schema.json` exists with all 7 property fields per D-201
- [x] `python -c "import jsonschema; from automil.schemas import RESULT_VALIDATOR; print('ok')"` - NOTE: public name is `RESULT_SCHEMA` (the dict) not `RESULT_VALIDATOR`; `validate_result` is the callable
- [x] `from automil.schemas import validate_result, RESULT_SCHEMA, ValidationError` succeeds
- [x] `RESULT_SCHEMA["required"] == ["composite"]` and `RESULT_SCHEMA["additionalProperties"] is True`
- [x] All 8 unit tests pass
- [x] No new breaking top-level dependency; jsonschema added as explicit dep (was already locked via ray)
- [x] Framework purity preserved in src/automil/schemas/
- [x] Zero em-dashes in any new file

## Threat Flags

None. This plan only adds a new schemas/ package with static JSON and a validation wrapper. No network endpoints, auth paths, file access patterns beyond reading a bundled static file, or schema changes at trust boundaries.

## Self-Check: PASSED

- src/automil/schemas/__init__.py: FOUND
- src/automil/schemas/_result.py: FOUND
- src/automil/schemas/result.schema.json: FOUND
- tests/test_result_schema_validation.py: FOUND
- Commit 5a7b080: FOUND (feat(08-01))
- Commit 097867d: FOUND (test(08-01))
