---
phase: "01"
plan: "01-12"
subsystem: "cli/lifecycle, tests/fixtures"
tags: [verify-repro, repro-manifest, acceptance-gate, phase-1-complete, REG-08, REG-09, CLI-09]
dependency_graph:
  requires: [01-01, 01-02, 01-03, 01-04, 01-05, 01-06, 01-07, 01-08, 01-09, 01-10, 01-11]
  provides: [verify-repro-command, repro-manifest-schema, synthetic-consumer-fixture, phase-1-acceptance]
  affects: [cli/lifecycle/verify_repro.py, cli/lifecycle/port_variant.py, tests/fixtures/synthetic_consumer]
tech_stack:
  added: []
  patterns: [subprocess-worktree-isolation, atomic-tempfile-rename, whitelisted-subprocess-env]
key_files:
  created:
    - tests/fixtures/__init__.py (0 lines)
    - tests/fixtures/synthetic_consumer/__init__.py (0 lines)
    - tests/fixtures/synthetic_consumer/program.py (82 lines)
    - tests/fixtures/synthetic_consumer/automil/config.yaml (17 lines)
    - tests/fixtures/synthetic_consumer/automil/variants/synthstub/.gitkeep (0 lines)
    - tests/test_verify_repro.py (313 lines)
    - tests/test_synthetic_consumer_roundtrip.py (366 lines)
  modified:
    - src/automil/cli/lifecycle/verify_repro.py (stub replaced, 212 lines)
    - src/automil/cli/lifecycle/port_variant.py (mutations tuple fix)
    - tests/test_lifecycle_skeleton.py (verify-repro removed from stubs list)
decisions:
  - "verify-repro uses sys.executable instead of bare 'python' to ensure the framework venv is used in subprocess"
  - "port_variant.py mutations rendering fixed: (,) is syntactically invalid; now () for empty, (x,) for non-empty"
  - "test_lifecycle_skeleton.py updated: all lifecycle commands now fully implemented, stub list empty"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-05-02"
---

# Phase 1 Plan 12: verify-repro + Synthetic Mini-Consumer Round-Trip Summary

**One-liner:** JWT-free reproduction gate — `automil verify-repro` runs consumer's program.py in a clean git worktree, atomically writes repro_manifest.yaml, exits 0/non-zero on pass/fail; synthetic mini-consumer in tests/fixtures/ exercises the full CLI-05→CLI-08→CLI-01→CLI-09 pipeline end-to-end.

## PHASE 1 ACCEPTANCE GATE PASSED

`tests/test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes` PASSED via the REAL CLI pipeline — no mock injection of `variant_spec` into graph.json (BLOCKER-02 contract from Plan 01-11 honoured).

## Files Created / Modified

| File | Lines | Action | Description |
|------|-------|--------|-------------|
| `src/automil/cli/lifecycle/verify_repro.py` | 212 | modified (stub replaced) | Full `verify-repro` command implementation |
| `src/automil/cli/lifecycle/port_variant.py` | 314 | modified (bug fix) | Fix mutations tuple rendering `(,)` → `()` |
| `tests/test_lifecycle_skeleton.py` | ~110 | modified | Remove verify-repro from stubs list (all implemented) |
| `tests/fixtures/__init__.py` | 0 | created | Makes tests/fixtures importable |
| `tests/fixtures/synthetic_consumer/__init__.py` | 0 | created | Package marker |
| `tests/fixtures/synthetic_consumer/program.py` | 82 | created | Torch-free deterministic training stub |
| `tests/fixtures/synthetic_consumer/automil/config.yaml` | 17 | created | Pre-init config with registry section |
| `tests/fixtures/synthetic_consumer/automil/variants/synthstub/.gitkeep` | 0 | created | Variant directory placeholder |
| `tests/test_verify_repro.py` | 313 | created | 9 tests for verify-repro |
| `tests/test_synthetic_consumer_roundtrip.py` | 366 | created | 3 round-trip acceptance tests |

## Tests Added (12 net-new)

### tests/test_verify_repro.py (9 tests)

| Test | Assertion |
|------|-----------|
| `test_happy_path_pass` | composite=0.5 → manifest status=pass, exit 0 |
| `test_manifest_schema` | all 8 D-39 fields present: node_id, expected_composite, actual_composite, tolerance, status, git_sha, runtime_seconds, generated_at |
| `test_tolerance_fail` | expected=0.7, actual=0.5 → status=fail, exit non-zero |
| `test_tolerance_override_pass` | same drift + --tolerance 0.5 → status=pass |
| `test_atomic_write_no_tmp` | no repro_manifest*.tmp leftover after run |
| `test_missing_node_lists_available` | non-existent node_id → exit non-zero + "available" in output |
| `test_missing_config_hard_fail` | no automil/config.yaml → exit non-zero |
| `test_help_quality` | --help mentions "after porting" or "porting" + "tolerance" |
| `test_check_recognises_repro_manifest` | after verify-repro, `automil check` no longer warns about missing manifest |

### tests/test_synthetic_consumer_roundtrip.py (3 tests)

| Test | Assertion |
|------|-----------|
| `test_full_roundtrip_passes` (PHASE 1 ACCEPTANCE GATE) | Full pipeline port-variant→refresh-registry→apply→verify-repro produces status=pass manifest; BLOCKER-02 contract exercised |
| `test_full_roundtrip_fail_exceeds_tolerance` | Same pipeline with composite drift (0.502 actual vs 0.700 expected) → status=fail, exit non-zero |
| `test_port_variant_writes_variant_spec_to_graph_json` | BLOCKER-02 regression-prevention: port-variant populates graph.json→nodes[id]→variant_spec |

## synthetic_consumer/program.py Key Flow

1. Locates `automil/` dir from cwd or walking up
2. Loads `automil/config.yaml` → reads `model.parent` + `model.variant`
3. Calls `_clear_registry()` + `scan_variants(automil_dir / "variants")` to load registered modules
4. If `name` and `parent` configured: `resolve_model(parent, name)` → instantiates variant → calls `forward(features=[1,2,3,4])` → returns float composite
5. If no variant configured: composite = 0.5 (baseline)
6. Writes `result.json` with composite + status=completed

## Sample repro_manifest.yaml (from round-trip test)

```yaml
node_id: node_0001
expected_composite: 0.502
actual_composite: 0.502
tolerance: 0.005
status: pass
git_sha: <sha>
runtime_seconds: 0.123
generated_at: 2026-05-02T08:35:30.640946+00:00
```

## Test Counts

- Prior suite (Wave 1–6): 375 tests
- This plan adds: 12 tests (+1 stub test replaced by `test_stub_error_format_none_remaining`)
- **Total: 387 tests, all passing**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed port_variant.py mutations tuple rendering**
- **Found during:** Task 4 (GREEN — first round-trip run)
- **Issue:** `mutations=({mutations_field},) if {bool(spec.mutations)} else ()` rendered as `mutations=(,) if False else ()` for empty mutations — syntactically invalid Python (SyntaxError at line 16 of generated module)
- **Fix:** Changed template to render `()` for empty mutations, `("x",)` for non-empty tuples — valid Python in all cases
- **Files modified:** `src/automil/cli/lifecycle/port_variant.py` (mutations_field calculation)
- **Commit:** c6b9947 (same acceptance commit)

**2. [Rule 1 - Bug] Fixed subprocess uses sys.executable not bare "python"**
- **Found during:** Task 4 — environment analysis
- **Issue:** The plan interface used `["python", ...]` in subprocess. In the test environment, bare `python` resolves to system Python3 which does not have automil installed; the venv Python does.
- **Fix:** Changed to `[sys.executable, ...]` — resolves to the active Python interpreter that has automil installed
- **Files modified:** `src/automil/cli/lifecycle/verify_repro.py`
- **Commit:** c6b9947

**3. [Rule 1 - Update] Updated test_lifecycle_skeleton.py**
- **Found during:** Task 4 — full suite run
- **Issue:** `test_stub_error_format[verify-repro-01-12]` expected verify-repro to still be a stub. With the implementation shipped, this was a false failure.
- **Fix:** Replaced the parametrized stub test with `test_stub_error_format_none_remaining` confirming all lifecycle commands are now implemented
- **Files modified:** `tests/test_lifecycle_skeleton.py`
- **Commit:** c6b9947

## Phase 1 Acceptance Summary

All Phase 1 success criteria from ROADMAP.md are met:
- [x] Variant ABC + frozen VariantSpec + Registry singleton + @register
- [x] refresh-registry deterministic + idempotent
- [x] Submit pre-validator + protected-files reject + check fails on uncommitted edits
- [x] mode flag selects validator chain (free / architecture-preserving)
- [x] train.py contract — framework provides resolve_model API
- [x] CCRCC port deferred per D-49 / D-37
- [x] Reproduction sanity check passes — synthetic mini-consumer round-trip per D-50
- [x] Variant lifecycle CLI wired: apply, revert-baseline, port-variant, promote-variant, refresh-registry, check, verify-repro

## Commit

`c6b9947` — `feat(cli): implement verify-repro + synthetic mini-consumer round-trip (REG-08, REG-09, CLI-09 — Phase 1 acceptance)`

Closes REG-08, REG-09, CLI-09. **PHASE 1 COMPLETE.**

## Self-Check: PASSED

- [x] `src/automil/cli/lifecycle/verify_repro.py` exists
- [x] `tests/fixtures/synthetic_consumer/program.py` exists
- [x] `tests/fixtures/synthetic_consumer/automil/config.yaml` exists
- [x] `tests/test_verify_repro.py` exists (9 tests)
- [x] `tests/test_synthetic_consumer_roundtrip.py` exists (3 tests)
- [x] Commit c6b9947 exists
- [x] `test_full_roundtrip_passes` PASSED
- [x] Full suite: 387 passed, 0 failed
- [x] `cli/lifecycle/__init__.py` UNTOUCHED
