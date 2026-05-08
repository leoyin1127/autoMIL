---
plan: 01-09
phase: "01"
subsystem: cli/lifecycle
tags: [cli, lifecycle, apply, refresh-registry, variant-registry, config, atomic-write]
dependency_graph:
  requires: [01-01, 01-02, 01-03, 01-06, 01-08]
  provides: [apply-command, refresh-registry-command]
  affects: [01-11, 01-12]
tech_stack:
  added: []
  patterns: [atomic-tempfile-rename, single-rolling-bak, scan-variants-walk, yaml-safe-dump]
key_files:
  created:
    - tests/test_lifecycle_apply.py
    - tests/test_lifecycle_refresh_registry.py
  modified:
    - src/automil/cli/lifecycle/apply.py
    - src/automil/cli/lifecycle/refresh_registry.py
    - tests/test_lifecycle_skeleton.py
decisions:
  - "D-41: apply edits config.yaml only, single rolling .bak, atomic tempfile+rename"
  - "D-29: refresh-registry uses scan_variants + regenerate_init_py, idempotent, --strict flag"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-02"
  tasks_completed: 3
  files_changed: 5
---

# Phase 01 Plan 09: apply + refresh-registry (CLI-01 + CLI-08) Summary

Implemented `automil apply` (CLI-01) and `automil refresh-registry` (CLI-08) by replacing the Plan 01-08 stub bodies with full implementations. `apply` derives model/loss/policy variant selection from a node's `variant_spec` or `recipe` field and atomic-patches `automil/config.yaml` with a single rolling `.bak` backup; `refresh-registry` scans `automil/variants/` via `scan_variants` + `regenerate_init_py` and regenerates deterministic imports-only `__init__.py` files idempotently.

## Files Modified

| File | Before | After | Role |
|------|--------|-------|------|
| `src/automil/cli/lifecycle/apply.py` | 28 lines (stub) | 144 lines | Full apply implementation |
| `src/automil/cli/lifecycle/refresh_registry.py` | 34 lines (stub) | 70 lines | Full refresh-registry implementation |
| `tests/test_lifecycle_apply.py` | (new) | 391 lines | 14 tests for apply |
| `tests/test_lifecycle_refresh_registry.py` | (new) | 378 lines | 13 tests for refresh-registry |
| `tests/test_lifecycle_skeleton.py` | 120 lines | 120 lines | Removed apply + refresh-registry from stub list |

## Test Coverage (27 new tests)

### apply tests (14):
1. `test_apply_model_only` — `variant_spec` kind=model sets `model.variant` + `model.parent`
2. `test_apply_loss_only` — `variant_spec` kind=loss sets `loss.variant`
3. `test_apply_policy_only` — `variant_spec` kind=policy sets `policy.variant`
4. `test_apply_combined_recipe` — `recipe` list with all three kinds updates all three sections
5. `test_apply_idempotent` — running twice produces byte-identical `config.yaml`
6. `test_apply_single_bak_rolling` — only ONE `.bak` file after repeated applies
7. `test_apply_bak_contains_previous` — `.bak` holds the config from the prior apply
8. `test_apply_no_tmp_leftover` — no `config.yaml*.tmp` after success
9. `test_apply_missing_node_lists_available` — exit non-zero + lists known node IDs
10. `test_apply_malformed_section_rejected` — `model: "string"` triggers "not a mapping" error
11. `test_apply_config_missing` — suggests `automil init`
12. `test_apply_no_codebase_mutation` — no files outside `config.yaml` mutated (D-41 invariant)
13. `test_apply_help_workflow_text` — `--help` mentions "config" and "variant"/"code"
14. `test_apply_node_without_variant_spec` — suggests `port-variant` command

### refresh-registry tests (13):
1. `test_happy_refresh_single_variant` — `clam_mb/v0001.py` → `from . import v0001` in `__init__.py`
2. `test_empty_kind_dir` — empty dir gets header-only `__init__.py`
3. `test_idempotent_rerun` — two consecutive runs → byte-identical bodies (modulo `# generated-at:`)
4. `test_failed_import_default_warns` — bad module → exit 0, "Failed imports" listed
5. `test_failed_import_strict_hard_fails` — bad module + `--strict` → exit non-zero
6. `test_three_kinds_walked` — all three kind dirs get `__init__.py` regenerated
7. `test_variants_dir_missing` — no `automil/variants/` → clear error
8. `test_output_format` — output includes `imported=N failed=M skipped=K`
9. `test_help_workflow_text` — `--help` mentions "after adding/renaming"
10. `test_no_tmp_leftover` — no `*.tmp` in `variants/` after refresh
11. `test_candidates_dir_walked` — `_candidates/` is not skipped
12. `test_per_parent_dirs_walked` — two model parents both get `__init__.py`
13. `test_clears_registry_between_runs` — duplicate variant name lands in `failed`

## Commits

| Hash | Message |
|------|---------|
| `a93b613` | `test(cli): add failing tests for apply + refresh-registry (RED)` |
| `95303f0` | `feat(cli): implement apply (CLI-01)` |
| `0252fc2` | `feat(cli): implement refresh-registry (CLI-08)` |

## Sample Output

```
$ automil refresh-registry
refresh-registry: imported=0 failed=0 skipped=0

$ automil apply node_0001
Applied node node_0001: model.variant=v0001, loss.variant=None, policy.variant=None
Backup: /path/to/automil/config.yaml.bak
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_lifecycle_skeleton.py stub tests blocked GREEN suite**
- **Found during:** Task 3 (GREEN phase), full suite run
- **Issue:** `test_stub_error_format` parametrize list included `apply` and `refresh-registry` with the expectation they respond with "not yet implemented". After implementation, these no longer match the stub pattern.
- **Fix:** Removed `("apply", "01-09")` and `("refresh-registry", "01-09")` from the parametrize list in `tests/test_lifecycle_skeleton.py`. Added a comment explaining they are fully implemented.
- **Files modified:** `tests/test_lifecycle_skeleton.py`
- **Commit:** included in `feat(cli): implement apply (CLI-01)` (95303f0)

## Wave-Safety Invariant

`src/automil/cli/lifecycle/__init__.py` was NOT modified (confirmed by `git diff` — 0 lines changed). This preserves the wave-safety invariant from Plan 01-08.

## Downstream Notes

- **Plan 01-11 (port-variant):** Calls `refresh-registry` at the end of its flow (D-43) — the implementation is now available. Plan 01-11 also populates `node['variant_spec']` in `graph.json` via `ExperimentGraph.save()`, which `apply` reads. The apply tests use mock-injected `variant_spec` in `_write_graph()`; the end-to-end integration (port-variant → apply round-trip) is tested in Plan 01-11.
- **Plan 01-12 (verify-repro):** Reads the active `config.yaml` (the file `apply` mutates). The `model.variant`, `loss.variant`, `policy.variant` fields are now reliably set by `apply`.

## Known Stubs

None — both commands are fully implemented. No placeholder text or hardcoded empty values flow to consumers.

## Threat Flags

None — both commands operate on operator-owned project files with no new network surface or trust-boundary crossings.

## Self-Check: PASSED
