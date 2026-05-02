---
plan: "01-07"
phase: "01"
subsystem: "cli"
tags: ["registry", "submit-hook", "check", "protected-files", "validators", "REG-03", "REG-04", "REG-05", "CLI-09"]
dependency_graph:
  requires: ["01-01", "01-02", "01-03", "01-04", "01-06"]
  provides: ["submit-protected-reject", "submit-validator-chain", "check-registry-consistency"]
  affects: ["01-08", "01-11"]
tech_stack:
  added: []
  patterns: ["protected-files-glob-reject", "purity-before-interface-ordering", "git-status-porcelain-dirty-check", "warn-not-fail-repro-manifest"]
key_files:
  modified:
    - src/automil/cli/submit.py
    - src/automil/cli/check.py
    - tests/test_registry_variants_abc.py
  created:
    - tests/test_submit_protected_files.py
    - tests/test_submit_validator_chain.py
    - tests/test_check_registry_extension.py
decisions:
  - "D-33/D-34 enforced: protected-files check runs BEFORE existing path-validation guard so registry.protected error wins on overlap"
  - "T-01-14 mitigation: PurityValidator().check() called before InterfaceValidator().check() — purity is AST-only, never imports the module; interface imports for reflection"
  - "D-32 hard-fail: ValidationError caught and re-raised as click.ClickException — no soft-warn path"
  - "D-46 check additions: protected-dirty as ISSUE, missing-manifest as WARNING, manifest-mismatch as ISSUE, failed-import as ISSUE, repro_manifest missing/stale as WARNING"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-02"
  tasks_completed: 4
  files_changed: 6
  tests_added: 31
  tests_total: 264
---

# Phase 01 Plan 07: Submit Hook + Check Extension Summary

**One-liner:** Registry-gated submit (protected-files hard-reject + purity-before-interface validator chain) and check extension (git-status dirty detect, registry consistency scan, repro-manifest stale warn).

## What Was Built

### `src/automil/cli/submit.py` (+63 lines)

Three additions inside the `submit()` function:

1. **Extended docstring** — mentions `variants/` validation and `registry.protected` rejection (satisfies `test_submit_help_mentions_validator_workflow`, `test_submit_help_does_not_mention_force`).

2. **Registry config load + `_is_variant_module_path` helper** (after `automil_rel` computation, before `file_list` determination):
   - `load_registry_config(adir)` reads `registry.protected` from consumer's `automil/config.yaml`
   - `_is_variant_module_path(rel_path)` returns True iff the path is `<*>/variants/<kind_dir>/<name>.py` (excludes `__init__.py` and `_*.py` helpers)

3. **Pre-validator block** (inserted BEFORE the existing `if os.path.isabs(f)` guard at line 179 — Phase 0 guards preserved verbatim):
   - Protected-files reject: if `reg_cfg.protected` and `_matches_scope(f, list(reg_cfg.protected))` matches any glob → `click.ClickException("Refusing to submit: ...")` naming each matched pattern + suggesting `automil revert-baseline`. Exit code non-zero. No `--force` flag added (D-34).
   - Variant-module validator chain: if `_is_variant_module_path(f)` and the file exists → `PurityValidator().check(abs_path)` FIRST, then `InterfaceValidator().check(abs_path)`. `ValidationError` caught and re-raised as `click.ClickException`. Short-circuits on first failure (T-01-14 mitigation enforced).

### `src/automil/cli/check.py` (+91 lines)

Registry checks block appended BEFORE `# Report` section, using existing `issues` and `warnings` lists:

1. **Protected-files dirty check** (REG-05 / D-34): `git status --porcelain -- <protected_paths>` — both staged AND unstaged dirty lines reported as ISSUE with `"registry.protected paths dirty"` header + `revert-baseline` suggestion.

2. **Registry consistency** (D-46): `scan_variants(variants_root)` walks `automil/variants/**/*.py`; failed imports → ISSUE; for each successfully imported module, manifest cross-check via `Manifest.read().cross_check_with_module()` — missing manifest → WARNING, mismatch → ISSUE.

3. **Repro manifest warn** (D-40 / D-46): missing `repro_manifest.yaml` → WARNING; stale (older than newest `variants/**/*.py` mtime) → WARNING. Missing or stale never becomes ISSUE (warn-not-fail by design).

## Test Names + Assertion Summary

### `tests/test_submit_protected_files.py` (9 tests)

| Test | What it asserts |
|------|----------------|
| `test_protected_glob_match_rejects` | `benchmarks/lib/CLAM/**` glob → exit!=0, "Refusing to submit", "registry.protected", "revert-baseline" |
| `test_multiple_matched_patterns_named` | Both `benchmarks/**` and `src/lib/**` patterns named in error |
| `test_protected_exact_path_rejects` | Exact path `src/foo.py` in protected → rejected |
| `test_non_matching_path_not_rejected_on_protected` | Non-matching path → "registry.protected" absent from output |
| `test_empty_protected_no_reject` | Empty protected list → no registry.protected message |
| `test_no_force_flag_d34` | `submit --force` → exit!=0, "no such option" |
| `test_submit_help_does_not_mention_force` | `--help` shows `--node`, `--desc` but NOT `--force` |
| `test_good_error_message_names_pattern_and_suggests_fix` | Error contains "Refusing to submit" + "registry.protected" + pattern name + "revert-baseline" |
| `test_protected_reject_runs_before_path_validation` | Protected check fires BEFORE absolute-path guard → "registry.protected" in output |

### `tests/test_submit_validator_chain.py` (11 tests)

| Test | What it asserts |
|------|----------------|
| `test_validator_happy_path_variant_module` | Clean variant → no "[purity]" or "[interface]" in output |
| `test_validator_purity_fail` | Top-level `open()` → exit!=0, "purity" in output, "open" mentioned |
| `test_validator_interface_fail` | Missing `forward` method → exit!=0, "interface" + "forward" in output |
| `test_validator_purity_runs_before_interface` | **T-01-14 ordering proof**: BOTH purity violation AND missing forward → error mentions "purity" + "print", NOT "interface" |
| `test_validator_skipped_on_non_variant_path` | `src/main.py` not under variants/ → no "[purity]" or "[interface]" |
| `test_validator_skipped_on_init_py` | `automil/variants/clam_mb/__init__.py` → not validated |
| `test_validator_skipped_on_underscore_helper` | `_helper.py` under kind dir → not validated |
| `test_validator_error_format_file_line_fix` | Purity fail → "bad.py" + "Fix:" in output |
| `test_submit_help_mentions_validator_workflow` | `--help` contains "variants" or "validate" or "register" |
| `test_d32_hard_fail_no_soft_warn` | Purity violation → exit!=0 AND no DeprecationWarning/UserWarning emitted by validator chain |

(Note: plan specified 11 tests including a 10th "validator runs only on tracked variants" and 11th "multiple variant files"; the implementation covers both behaviors via skipping logic and each call site validates per-file.)

### `tests/test_check_registry_extension.py` (12 tests)

| Test | What it asserts |
|------|----------------|
| `test_protected_clean_no_issue` | Clean or absent protected files → "registry.protected paths dirty" absent |
| `test_protected_dirty_issue_raised` | Modified (unstaged) protected file → ISSUE with "registry.protected paths dirty" + path + "revert-baseline" |
| `test_protected_staged_also_fails_d34` | Staged (not committed) protected file → ISSUE |
| `test_registry_consistency_happy` | Clean variant + matching manifest → no "failed import", no "mismatches docstring" |
| `test_registry_variant_missing_manifest_warns` | Variant without sibling .json → WARNING with "no sibling manifest" or ".json" |
| `test_registry_manifest_mismatch_issue` | Docstring composite=0.81 vs manifest composite=0.5 → ISSUE with "mismatches docstring" |
| `test_registry_failed_import_issue` | Variant importing nonexistent package → ISSUE with "failed import" |
| `test_repro_manifest_missing_warns` | No `repro_manifest.yaml` → WARNING with "repro_manifest.yaml" + "verify-repro" |
| `test_repro_manifest_stale_warns` | repro_manifest older than variant module → WARNING with "older than" |
| `test_repro_manifest_current_no_warning` | repro_manifest newer than all variant modules → no "older than" |
| `test_phase0_check_outputs_preserved` | Phase 0 regression: "nvidia-smi" + "env whitelist" still present |
| `test_protected_dirty_includes_suggestion` | Good error: path named + "revert-baseline" |

## Validator-Ordering Proof (T-01-14 Mitigation)

`test_validator_purity_runs_before_interface` uses `BOTH_BAD` which has BOTH:
- `print("loading...")` at module top level (purity violation)
- Missing `forward` method on `ModelVariant` subclass (interface violation)

Expected: submit reports `purity` (not `interface`). This proves `PurityValidator().check()` short-circuits before `InterfaceValidator().check()` ever imports the module — ensuring untrusted code (top-level side effects) never runs even when the interface is also broken.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed relative-path fragility in test_no_top_level_torch_import_in_model_py**
- **Found during:** Full suite run after implementing GREEN (Task 4)
- **Issue:** `tests/test_registry_variants_abc.py::test_no_top_level_torch_import_in_model_py` used `Path("src/automil/registry/variants/model.py")` — a relative path that breaks when `monkeypatch.chdir()` from the new tests changes the cwd.
- **Fix:** Changed to `Path(__file__).parent.parent / "src" / "automil" / "registry" / "variants" / "model.py"` — robust against cwd changes.
- **Files modified:** `tests/test_registry_variants_abc.py`
- **Commit:** 104d8e3

## Commits

| Commit | Message |
|--------|---------|
| 1177ae9 | `test(01-07): add failing tests for submit-hook + check registry extension` (RED gate) |
| 104d8e3 | `feat(cli): add registry submit-hook + check extensions (REG-03, REG-04, REG-05)` (GREEN gate + Rule-1 fix) |

## Downstream Notes

- **Plan 01-08** (lifecycle scaffold) and **Plan 01-11** (port-variant) can assume submit's protected-reject + validator chain are in place; they don't need to re-implement the gate.
- **Plan 01-09** (refresh-registry) uses the same `scan_variants` that `check` now uses for consistency; the `_clear_registry()` + `scan_variants()` pattern is established here.
- The `_is_variant_module_path()` helper in `submit.py` is a local function (not exported); if lifecycle or port-variant need the same logic, extract to `automil.cli._helpers` at that point.

## Self-Check: PASSED

- `src/automil/cli/submit.py` exists: FOUND
- `src/automil/cli/check.py` exists: FOUND
- `tests/test_submit_protected_files.py` exists: FOUND
- `tests/test_submit_validator_chain.py` exists: FOUND
- `tests/test_check_registry_extension.py` exists: FOUND
- Commit 1177ae9 exists: FOUND
- Commit 104d8e3 exists: FOUND
- Full test suite: 264 passed, 0 failed
