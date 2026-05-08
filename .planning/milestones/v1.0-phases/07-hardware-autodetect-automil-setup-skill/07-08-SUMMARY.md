---
phase: 07-hardware-autodetect-automil-setup-skill
plan: "08"
subsystem: tests/skills
tags: [testing, idempotency, skill, STP-05, D-198]
dependency_graph:
  requires: [07-05]
  provides: [tests/skills/__init__.py, tests/skills/conftest.py, tests/skills/test_setup_idempotency.py]
  affects: [tests/skills/]
tech_stack:
  added: []
  patterns: [pytest fixture sharing via conftest.py, CliRunner subprocess mocking with patch]
key_files:
  created:
    - tests/skills/__init__.py
    - tests/skills/conftest.py
    - tests/skills/test_setup_idempotency.py
  modified: []
decisions:
  - "Used CliRunner + patch('subprocess.run') rather than subprocess.run(['automil']) so tests run without installing automil globally and the mock intercepts healthcheck probes cleanly"
  - "fake_nvidia_smi_3gpu placed in conftest.py as a plain function (not a fixture) so 07-09 and 07-10 can import it directly via 'from tests.skills.conftest import fake_nvidia_smi_3gpu'"
  - "test_skill_idempotency_ignores_comment_only_diffs tests the value-tree diff property directly (yaml.safe_load round-trip) rather than driving --update, per the plan note that interactive 3-way diff is LLM-execution-time behavior not unit-testable here"
metrics:
  duration: "< 5 minutes"
  completed: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
  tests_added: 3
---

# Phase 7 Plan 08: Skill Idempotency Tests Summary

STP-05 test coverage: 3 tests verifying that re-running the setup CLI sequence produces zero unprompted changes, value-tree diff ignores comments, and results.tsv changes surface as legitimate diffs.

## Test Outcomes

All 3 tests pass in 0.65s.

### test_skill_idempotency_zero_unprompted_changes

D-198 clause 4 gate. Two `automil init` then `automil init --update` calls with identical `fake_nvidia_smi_3gpu` inputs produce byte-identical `automil/config.yaml`. Verified by string equality assertion after both CliRunner invocations.

The 3-GPU workstation mock (49140 MB x3) drives the conservative VRAM path: `min_vram=47.99 GB`, `conservative_vram=max(8.0, 47.99/8.0)=8.0`, `max_concurrent=5`. Both runs stamp `default_vram_estimate_gb: 8.0` from the conservative formula (no results.tsv present), producing identical output.

### test_skill_idempotency_ignores_comment_only_diffs

OQ-4 property: `yaml.safe_load` is invariant to comment injection. The test prepends `# User notes: this run is for project Foo.\n` to the rendered config.yaml, then verifies that `yaml.safe_load(augmented)` equals `yaml.safe_load(drafted_from_jinja)`. Both parse to the same dict, confirming that the skill's value-tree diff mechanism correctly ignores comment-only edits and does not trigger re-stamp.

### test_skill_idempotency_detects_results_tsv_change

OQ-2 / inverse-of-idempotency direction. After initial `automil init` (conservative path, `default_vram_estimate_gb=8.0`), 30 rows of results.tsv are seeded with `vram_gb` values in `[12.0, 12.3, ..., 20.7]`. The `--update` run switches to the empirical path (`len(vram_values)=30 >= 10`): `numpy.quantile([12.0+i*0.3 for i in range(30)], 0.95) = 20.43 GB`.

**Observed values:**
- v1 `default_vram_estimate_gb`: `8.0` (conservative, no results.tsv)
- v2 `default_vram_estimate_gb`: `20.43` (empirical quantile_95 from seeded tsv)
- Assertion: `abs(v2 - 20.43) <= 0.05` passes

## conftest.py Fixture Sharing Strategy

`tests/skills/conftest.py` provides:

1. `tmp_git_repo` fixture: creates a temp git repo with `train.py` (single `torch.nn.Module` subclass + result.json writer) and a committed `README.md`. Used by 07-08, 07-09, 07-10 without modification.

2. `fake_nvidia_smi_3gpu` plain function: dispatches on `"mig.mode.current" in str(argv)` to cover both the CUDA memory query and the MIG mode check in `LocalBackend._healthcheck_cuda()`. Used as `side_effect=fake_nvidia_smi_3gpu` for `patch("subprocess.run")`. 07-09 and 07-10 import it via `from tests.skills.conftest import fake_nvidia_smi_3gpu`.

No fixture-name collision: `tests/conftest.py` does not exist at the top level; the `tmp_git_repo` name is introduced fresh in `tests/skills/conftest.py`.

## Deviations from Plan

None. Plan executed exactly as written. The test code in the plan was used verbatim with one formatting adjustment (backslash string concatenation replaced with parenthesized form to satisfy PEP 8 line-length, no logic change).

## Pre-existing Baseline Note

`tests/gate/test_evaluate.py::test_evaluate_calls_backend_submit_per_held_out_cell` errors with `TypeError: Can't instantiate abstract class RecordingBackend with abstract method healthcheck`. This error pre-dates 07-08 (confirmed via git stash); it is a deferred fixture update from Wave 4-5 adding the `healthcheck` ABC. Out of scope for 07-08. Deferred item logged.

Final count: 203 passed, 51 skipped (pre-existing baseline) + 3 new tests passing = 206 passed.

## Self-Check: PASSED

- tests/skills/__init__.py: FOUND
- tests/skills/conftest.py: FOUND
- tests/skills/test_setup_idempotency.py: FOUND
- Commit a58f56f (Task 1): FOUND
- Commit 420c070 (Task 2): FOUND
