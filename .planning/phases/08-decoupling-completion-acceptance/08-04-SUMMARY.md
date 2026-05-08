---
phase: 08-decoupling-completion-acceptance
plan: "04"
subsystem: cli/check + templates
tags: [env-validation, config-template, DEC-05, DEC-04, D-202]
dependency_graph:
  requires: []
  provides:
    - _validate_env_required helper (src/automil/cli/check.py:60)
    - env.required default field in config.yaml.j2
    - scoring.formula default field in config.yaml.j2
  affects:
    - automil check command (validates required env vars at startup)
    - automil init output (new consumers see env.required and scoring.formula)
tech_stack:
  added: []
  patterns:
    - Pure helper returning list[str] of issues, mirroring _validate_slurm_directives pattern
    - Presence-only env var semantics (no value checking, only os.environ membership)
    - CliRunner-based F-05 test for call-site warning emission
key_files:
  created:
    - tests/cli/test_check_env_required.py
  modified:
    - src/automil/cli/check.py
    - src/automil/templates/config.yaml.j2
decisions:
  - Presence-only semantics for env vars: TODO_FILL_IN and empty string both count as present (CONTEXT anti-pattern #6)
  - Type-mismatch (non-list env.required) handled by returning [] from validator + warning at call site
  - No inline AUTOBENCH example in config.yaml.j2 (F-06: framework-pure template)
  - scoring.formula is documentation-only; framework does not evaluate (D-200)
metrics:
  duration: "~2 minutes"
  completed: "2026-05-07"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 8 Plan 04: env.required Validator + Template Blocks Summary

**One-liner:** Adds `_validate_env_required(config) -> list[str]` to `automil check` (D-202 / DEC-05), extends `config.yaml.j2` with `env.required: []` default and `scoring: formula: ""` documentation block (F-06 + F-07), and ships 10 unit tests including F-05 call-site warning test.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add _validate_env_required helper + check() integration | 0411add | src/automil/cli/check.py |
| 2 | Extend config.yaml.j2 with env.required + scoring blocks | 2642f19 | src/automil/templates/config.yaml.j2 |
| 3 | Create 10-test file covering all validator behaviors | 65d4f13 | tests/cli/test_check_env_required.py |

## Implementation Notes

**Task 1 (check.py):**

- `_validate_env_required` inserted at line 60, between `_validate_slurm_directives` and `_validate_ray_backend`, following the established pure-helper pattern.
- Returns `list[str]` of missing var names. Empty list when env.required is empty, absent, or wrong-typed.
- Presence-only semantics: `os.environ` membership check only; any value (including empty string or `TODO_FILL_IN`) counts as present.
- Type-mismatch path: `isinstance(raw_required, list)` guard returns `[]` silently; the call site in `check()` emits the operator-visible warning via `warnings.append(...)`.
- Locked error message used verbatim in the issues list: `"Missing required env var: {name}; see automil/config.yaml: env.required. Set the variable before running 'automil submit' or 'automil orchestrator start'."` Plans 08-09 and 08-10 grep this string.
- `grep -c "_validate_env_required" src/automil/cli/check.py` returns 2 (definition at :60 + call at :265).

**Task 2 (config.yaml.j2):**

- Replaced the env block header comment and added `required: []` above the existing `passthrough:` list.
- F-06: no inline AUTOBENCH example in the template; migration guidance deferred to CHANGELOG.md 8.0.0 BREAKING section (plan 08-10).
- F-07: new `scoring:` block with `formula: ""` default and comment block citing DEC-04 / D-200, clarifying the formula is documentation-only (framework does not evaluate it).
- Framework-pure: `grep -nE "AUTOBENCH_OVARIAN|AUTOBENCH_CCRCC" src/automil/templates/config.yaml.j2` returns zero hits.

**Task 3 (test file):**

- 10 tests, all passing. 8 pure-unit tests + F-05 CliRunner-based test + F-07 template regression test.
- F-05 test (`test_env_required_non_list_warns_and_skips_validation`): builds a minimal tmp project with `env.required: "AUTOBENCH_OVARIAN_ROOT"` (string instead of list), invokes `automil check` via CliRunner, asserts the type-mismatch warning appears in output, no spurious "Missing required env var" issue, and no crash.
- F-07 test (`test_template_has_scoring_block`): reads `config.yaml.j2` at module load time and asserts `scoring:`, `formula:`, and `documentation-only` / `framework does NOT evaluate` are all present.

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed incorrect CliRunner `mix_stderr` kwarg**
- **Found during:** Task 3 test run
- **Issue:** `CliRunner(mix_stderr=False)` raised `TypeError` in the installed Click version; the kwarg does not exist.
- **Fix:** Removed the `mix_stderr=False` argument; combined output via `result.output` only.
- **Files modified:** tests/cli/test_check_env_required.py
- **Commit:** included in 65d4f13

**2. [Rule 1 - Bug] Fixed incorrect CLI import path**
- **Found during:** Task 3 first test run
- **Issue:** `from automil.cli.main import cli` raised `ModuleNotFoundError`; the CLI group lives at `automil.cli.main` as a module but the Click group object is `main`, accessed via `from automil.cli import main`.
- **Fix:** Changed import to `from automil.cli import main as cli` matching the pattern in `test_init_healthcheck.py`.
- **Files modified:** tests/cli/test_check_env_required.py
- **Commit:** included in 65d4f13

## Known Stubs

None. All behavior is fully wired: validator runs, issues are appended, echo output is produced.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced.

## Self-Check: PASSED

- src/automil/cli/check.py exists and contains `_validate_env_required` at line 60 and call at line 265.
- src/automil/templates/config.yaml.j2 exists with `required: []` and `^scoring:` blocks.
- tests/cli/test_check_env_required.py exists with 10 passing tests.
- Commits 0411add, 2642f19, 65d4f13 verified in git log.
- Zero em-dashes in all three modified files (pre-existing em-dashes in check.py are unrelated to this plan's additions).
