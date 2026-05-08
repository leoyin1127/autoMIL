---
phase: 08-decoupling-completion-acceptance
plan: 05
subsystem: backends/orchestrator
tags: [decoupling, autobench-purge, schema-validation, env-whitelist, DEC-01, DEC-03]
dependency-graph:
  requires: [08-01]
  provides: [AUTOBENCH-purged daemon, result.json schema validation at ingestion]
  affects: [src/automil/backends/_orchestrator_daemon.py, tests/test_orchestrator_env_whitelist.py, tests/backends/test_daemon_result_schema_validation.py]
tech-stack:
  added: []
  patterns: [jsonschema inline import at validation site, negative-test contract documentation]
key-files:
  modified:
    - src/automil/backends/_orchestrator_daemon.py
    - tests/test_orchestrator_env_whitelist.py
  created:
    - tests/backends/test_daemon_result_schema_validation.py
decisions:
  - "Inline import of validate_result at validation site to confine hard-dep at the call path"
  - "Comment text trimmed to avoid AUTOBENCH_ token for 08-08 purity grep gate (only line 54 allowed)"
  - "F-03 cap-killed branch already clean from 08-03 Wave 1; verified zero top-level metric writes"
metrics:
  duration: ~15 minutes
  completed: 2026-05-07
  tasks: 5/5
  files: 3
---

# Phase 8 Plan 05: AUTOBENCH Purge + Result Schema Validation Summary

AUTOBENCH_ROOT injection and PYTHONPATH manipulation deleted from daemon; result.json schema-validated at ingestion with crashed-node fallback and schema-pointer error message.

## What Was Done

### Task 1: Purge AUTOBENCH_ROOT injection + PYTHONPATH manipulation

Commit `e98bb1b` + `4f43f2f`.

- Dropped `pythonpath` and `worktree_benchmarks` parameters from `_build_subprocess_env` signature.
- Deleted the `env["AUTOBENCH_ROOT"] = str(worktree_benchmarks.resolve())` line.
- Deleted the `env["PYTHONPATH"] = pythonpath` line.
- Removed `worktree_benchmarks`, `worktree_src`, and `pythonpath` local construction from `_launch` (~6 lines).
- Replaced the old `CLN-02/D-04` comment in `_launch` with a `DEC-01/D-199` comment explaining the migration.
- Added operator-discoverability comment in `_build_subprocess_env` body.
- Post-purge `grep -nE "AUTOBENCH_|autobench|benchmarks/" src/automil/backends/_orchestrator_daemon.py` returns exactly 1 hit at line 54 (the allowlisted informational comment for plan 08-08).

### Task 2: Insert result.json schema validation in ingestion path

Commit `34eeef7`.

- Added `validate_result` hook between `collect_result` call and the `if result is None` fall-through block.
- On `ValidationError`, result is overridden with `{"status": "crash", "composite": 0.0, "metrics": {}, "error": "result.json failed schema validation: ... (json_path=...) ; see automil/schemas/result.schema.json"}`.
- Import is inline (`from automil.schemas import validate_result, ValidationError`) to confine the hard-dep at the call site.
- `logger.warning` fires with `node_id` and `exc.message`.
- The `result is None` fall-through (synthesised minimal payload) skips validation by the `if result is not None:` guard.

### Task 3: Convert AUTOBENCH_ROOT test to negative + delete PYTHONPATH-override test (F-02)

Commit `e443b7a`.

- Updated `_call_build` helper: removed `pythonpath` and `worktree_benchmarks` from defaults dict.
- Replaced `test_autobench_root_still_injected_phase0` (positive) with `test_autobench_root_not_auto_injected_phase8` (negative, asserts `AUTOBENCH_ROOT not in env`).
- Deleted `test_pythonpath_overrides_whitelist_value` (Iter-2 F-02 fix; asserted a contract that no longer exists post-D-199).
- Added `test_pythonpath_not_auto_injected_phase8` asserting orchestrator does not force-set PYTHONPATH to worktree-relative path.
- All 12 tests in `tests/test_orchestrator_env_whitelist.py` pass.

### Task 4: Create tests/backends/test_daemon_result_schema_validation.py

Commit `2159414`.

9 tests (exceeds the 6 minimum required):
1. `test_validate_result_imports_cleanly` - symbol importable from automil.schemas
2. `test_valid_autobench_result_json_passes_validation` - well-formed payload passes
3. `test_valid_minimal_result_json_passes_validation` - minimal payload (composite only) passes
4. `test_malformed_result_json_raises_with_nonempty_message` - ValidationError raised, message non-empty
5. `test_daemon_error_template_contains_schema_pointer` - static-text gate: error string contains schema location
6. `test_daemon_imports_validate_result_inline` - static-text gate: import present in daemon source
7. `test_status_enum_violation_raises_validation_error` - unknown status enum raises
8. `test_negative_peak_vram_mb_raises_validation_error` - negative VRAM raises
9. `test_none_result_skips_validation_by_construction` - guard position verified by source analysis

### Task 5: F-03 cap-killed reconcile branch verification

No code changes needed. The cap-killed branch at daemon line 1037 was already migrated to `gnode["metrics"] = dict(payload["metrics"])` by 08-03 (Wave 1). `grep -nE 'gnode\["?(test|val)_(auc|bacc)"?\]'` returns zero matches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Comment text contained AUTOBENCH_ token triggering purity grep gate**
- Found during: Task 1 post-commit verification
- Issue: The D-199 comment added to `_build_subprocess_env` body mentioned "AUTOBENCH_ROOT" literally, causing the purity grep to return 3 hits instead of 1
- Fix: Rewrote comments to reference "consumer-specific env vars" generically, preserving the D-199/DEC-01 attribution without the banned token
- Files modified: `src/automil/backends/_orchestrator_daemon.py`
- Commit: `4f43f2f`

None others - plan executed within expected parameters.

## Post-purge Grep Gate

```
grep -nE "AUTOBENCH_|autobench|benchmarks/" src/automil/backends/_orchestrator_daemon.py
```

Result: 1 hit at line 54 (allowlisted informational comment: `# Consumer-specific vars (e.g. AUTOBENCH_*_ROOT) are opted in per project via`)

## Test Results

- `tests/test_orchestrator_env_whitelist.py`: 12/12 pass
- `tests/backends/test_daemon_result_schema_validation.py`: 9/9 pass
- `tests/backends/` full suite: 75 passed, 51 skipped, 0 failed

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | e98bb1b | refactor(08-05): purge AUTOBENCH_ROOT injection + PYTHONPATH manipulation from daemon |
| 2 | 34eeef7 | feat(08-05): insert D-201 result.json schema validation in daemon ingestion path |
| 3 | e443b7a | test(08-05): convert AUTOBENCH_ROOT test to negative + delete PYTHONPATH-override test |
| 4 | 2159414 | test(08-05): add daemon result.json schema validation tests (DEC-03 / D-201) |
| 1-fix | 4f43f2f | refactor(08-05): trim AUTOBENCH_ mentions from added comments for purity gate |

## Self-Check

- [x] `src/automil/backends/_orchestrator_daemon.py` exists and modified
- [x] `tests/test_orchestrator_env_whitelist.py` exists and modified
- [x] `tests/backends/test_daemon_result_schema_validation.py` exists and created
- [x] All commits exist in git log
- [x] Purity grep returns exactly 1 hit (line 54)
- [x] No em-dashes in newly added lines
- [x] F-03 verified clean (zero top-level metric key writes)
