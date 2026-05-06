---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: "06"
subsystem: cli/submit + cells/registry + templates
tags: [submit, cell-refusal, metadata, cli-flags, click-options, cap]

dependency_graph:
  requires: ["04-05"]
  provides: ["submit-path cell refusal", "metadata.cell_id", "--budget-seconds flag"]
  affects: ["src/automil/cli/submit.py", "src/automil/templates/config.yaml.j2"]

tech_stack:
  added: []
  patterns:
    - "3-tier CLI flag > config > framework fallback precedence for cap values"
    - "lazy import inside submit() body (from automil.cells import ...)"
    - "spec.setdefault('metadata', {})['cell_id'] = _cell.cell_id"

key_files:
  created:
    - tests/test_submit_cell_refusal.py
  modified:
    - src/automil/cli/submit.py
    - src/automil/templates/config.yaml.j2

decisions:
  - "fold_count: 5 merged into existing training: section in config.yaml.j2 (not a duplicate key)"
  - "D-134 validation still fires on second submit — only get_or_create_cell ignores override; validation guard is always active"
  - "Test 5 uses --budget-seconds 60 --safety-buffer-seconds 10 to pass validation, verifying cell retains original 21600"

metrics:
  duration: "~15 minutes"
  completed: "2026-05-05"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
  tests_added: 6
  tests_passing: 615
  tests_skipped: 9
---

# Phase 04 Plan 06: Submit-path cell refusal hook + metadata.cell_id + cap config

One-liner: Cell refusal hook wired into submit.py with --budget-seconds/--safety-buffer-seconds flags, metadata.cell_id stamp, and config.yaml.j2 cap: section with consumer-facing comments.

## What Was Built

### Task 1: src/automil/cli/submit.py

Four additions to the submit command:

1. Two new Click options — `--budget-seconds` and `--safety-buffer-seconds` (both `default=None`, honoring D-134 first-submit-wins semantics).
2. 3-tier cap default resolution: CLI flag > `config.yaml cap.*` > framework fallback (21600/1800).
3. Validation: `budget > 0` and `0 < buffer < budget` (T-04-15 mitigation).
4. Cell refusal hook via lazy import of `get_or_create_cell`, `is_refusing_new`, `consumed_seconds` — fires BEFORE queue spec is written. ClickException includes cell_id prefix, status.value, consumed/budget context (Pitfall-9 defence).
5. `spec.setdefault("metadata", {})["cell_id"] = _cell.cell_id` — symmetric to metadata.backend and metadata.runtime (D-117).

### Task 2: src/automil/templates/config.yaml.j2

- Added `cap:` section with `budget_seconds: 21600` and `safety_buffer_seconds: 1800`.
- Added consumer-facing comment block explicitly stating "NOT framework-mandated" with sklearn-iris, external-lab, and PathBench-MIL counter-examples.
- Added `fold_count: 5` to the existing `training:` section (D-120 — aggregate_folds reads this).

### Task 3: tests/test_submit_cell_refusal.py

6 integration tests covering the full submit-cell pathway:
- `test_submit_opens_cell_on_first_call` — cell file created with active status, correct dataset/encoder
- `test_submit_writes_metadata_cell_id` — queue spec metadata.cell_id matches cell
- `test_submit_rejects_when_cell_refusing_new` — refusing-new cell raises ClickException with cell_id + budget context
- `test_submit_cli_budget_override_on_creation` — --budget-seconds honored on first submit
- `test_submit_cli_budget_override_ignored_on_existing_cell` — D-134 first-submit-wins
- `test_submit_validation_fails_on_invalid_buffer` — T-04-15 guards (buffer>=budget, budget<=0)

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f211646 | feat | submit.py: cell refusal hook + metadata.cell_id + budget flags |
| 73c2d38 | feat | config.yaml.j2: cap: section + fold_count in training: |
| c2bc5de | test | test_submit_cell_refusal.py: 6 integration tests |

## Verification

```
uv run pytest tests/test_submit_cell_refusal.py -x    # 6/6 PASS
uv run pytest tests/ -x                               # 615 passed, 9 skipped
grep -c '"--budget-seconds"' src/automil/cli/submit.py  # 1
grep -c "from automil.cells import get_or_create_cell" src/automil/cli/submit.py  # 1
grep -c "^cap:" src/automil/templates/config.yaml.j2    # 1
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Logic] fold_count merged into existing training: section**
- **Found during:** Task 2
- **Issue:** config.yaml.j2 already had a `training:` section with ML hyperparameters. Adding a new `training:` block would create a duplicate YAML key.
- **Fix:** Added `fold_count: 5` into the existing `training:` section rather than creating a second `training:` block.
- **Files modified:** src/automil/templates/config.yaml.j2

**2. [Rule 1 - Bug] Test 5 validation interaction with D-134**
- **Found during:** Task 3 (first test run)
- **Issue:** test_submit_cli_budget_override_ignored_on_existing_cell passed `--budget-seconds 60` alone; the validation check `0 < buffer < budget` fired before get_or_create_cell because the buffer (1800 from config) exceeded the new budget (60). The D-134 ignore-on-existing logic never ran.
- **Fix:** Updated test to pass `--budget-seconds 60 --safety-buffer-seconds 10` (a valid combo) to verify first-submit-wins behavior. The validation check is intentionally always active — it's a security guard independent of whether the cell exists.
- **Files modified:** tests/test_submit_cell_refusal.py

## Threat Mitigations Applied

| Threat ID | Mitigation |
|-----------|-----------|
| T-04-15 | `_resolved_budget <= 0` and `0 < _resolved_buffer < _resolved_budget` ClickException guards |
| T-04-16 | get_or_create_cell returns existing cell unchanged on second submit (D-134) |
| T-04-17 | cell_id is sha256 of public dataset/encoder/parent_id — non-secret by design |

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced beyond what the plan specified.

## Known Stubs

None — all plumbing is wired. metadata.cell_id flows into queue specs. Cap budget resolution reads from config. Cell files are created on disk.

## Self-Check: PASSED
