---
status: complete
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
source:
  - 04-01-SUMMARY.md
  - 04-02-SUMMARY.md
  - 04-03-SUMMARY.md
  - 04-04-SUMMARY.md
  - 04-05-SUMMARY.md
  - 04-06-SUMMARY.md
  - 04-07-SUMMARY.md
  - 04-08-SUMMARY.md
  - 04-09-SUMMARY.md
  - 04-10-SUMMARY.md
started: "2026-05-05T08:00:00Z"
updated: "2026-05-05T09:50:00Z"
verifier: autonomous (Auto mode — bash-verifiable surfaces only)
---

## Current Test
<!-- All 21 tests complete; nothing pending -->

## Tests

### 1. CLI surface: `automil --help` exposes `cell` and `submit` groups
**Expected:** `automil --help` lists `cell` (Cell budget-cap management commands) and `submit` (Snapshot changed files and queue an experiment).
**Result:** PASS — both groups present in help output.

### 2. CLI surface: `automil cell --help` shows `status` and `list` subcommands
**Expected:** `automil cell --help` lists `status` (Show budget state for one cell) and `list` (Short-form cell listing).
**Result:** PASS — both subcommands present.

### 3. CLI surface: `automil submit --help` shows `--budget-seconds` and `--safety-buffer-seconds`
**Expected:** Help text documents both flags as D-134 per-cell overrides honored only on cell creation.
**Result:** PASS — both flags present with D-134 reference and "honored only on cell creation" docstring.

### 4. `automil init` creates a config with `cap:` section
**Expected:** Fresh `automil init` in a clean git repo writes `automil/config.yaml` containing a `cap:` section.
**Result:** PASS — `cap:` section present with `budget_seconds: 21600` and `safety_buffer_seconds: 1800`.

### 5. `cap:` comment block tells operator values are theirs to change (paper-campaign-vs-framework rule)
**Expected:** Comment block above `cap:` mentions "consumer's choice", "follow-up paper would pick different numbers", and "values are entirely the consumer's choice".
**Result:** PASS — comment explicitly says "the *values* are entirely the consumer's choice", names "lab with different time budgets, a follow-up paper" as alternative consumers, and references D-134 per-cell override.

### 6. `training:` section now includes `fold_count: 5`
**Expected:** Rendered config has `fold_count: 5` inside the `training:` section (not a duplicate top-level key).
**Result:** PASS — `fold_count: 5` rendered at line 49 of config.yaml.j2 inside `training:` with explanatory comment ("sklearn-iris demo would set 1; PathBench-MIL uses 5x5").

### 7. Empty `automil cell list` returns `(no cells)`
**Expected:** On a fresh init with no submits, `automil cell list` prints `(no cells)`.
**Result:** PASS.

### 8. `automil cell status nonexistent` errors gracefully
**Expected:** Error message about no cells found, no traceback.
**Result:** PASS — returns `(no cells)` cleanly, exits 0 (status without arg shows all cells, returning empty list when registry is empty).

### 9. Live submit creates a cell file at `automil/cells/<cell_id>.json`
**Expected:** `automil submit --node node_0001 --desc "..." --files <file> --budget-seconds 7200 --safety-buffer-seconds 600` creates a cell JSON file with the user-supplied budget (NOT the framework default 21600).
**Result:** PASS — cell JSON contains `"budget_seconds": 7200, "safety_buffer_seconds": 600, "status": "active"`. cell_id derived as 16-char sha256 prefix `94140925a55e6c96`.

### 10. `automil cell list` after submit shows the new cell
**Expected:** Tabular output with `cell_id`, `status`, `consumed/budget`.
**Result:** PASS — `94140925  active  00:00:00/02:00:00`.

### 11. `automil cell status` (no arg) shows verbose all-cells view
**Expected:** Tabular output including `cell_id`, `dataset`, `encoder`, `parent`, `started`, `consumed/budget`, `status`, `running`.
**Result:** PASS — all 8 columns rendered correctly with stdlib f-string formatting (no rich/tabulate dependency).

### 12. D-134 first-submit-wins: second submit with different `--budget-seconds` is silently ignored
**Expected:** Second submit to same `(dataset, encoder, parent_id)` cell with `--budget-seconds 1000` does NOT mutate the cell's stored `budget_seconds=7200`.
**Result:** PASS — cell file still shows `"budget_seconds": 7200, "safety_buffer_seconds": 600` after second submit. (Sandbagging vector closed.)

### 13. Validation: `--safety-buffer-seconds >= --budget-seconds` rejected at submit time
**Expected:** Submit with `--budget-seconds 100 --safety-buffer-seconds 200` exits with `Error: --safety-buffer-seconds must satisfy 0 < buffer < budget`.
**Result:** PASS — exact error message matches.

### 14. Pitfall-4 anti-acceptance gate (`test_cap_fires_with_partial_fold_recovery`) green and runs in <30s
**Expected:** Test runs synthetic 5-fold subprocess with `budget_seconds=60`, sends SIGTERM after fold 3, verifies status=partial, composite≈0.82, returncode=0, elapsed_to_exit<30s, descendant cascade against partial composite, metadata.budget_killed=True.
**Result:** PASS — test passes in 0.30s (well within 30s budget).

### 15. CAP-05 daemon-restart: `started_at` + `consumed_seconds` survive kill-9 + restart
**Expected:** All 5 tests in `test_cell_state_survives_daemon_kill_restart.py` pass, including subprocess restart and zero-accumulator static guard.
**Result:** PASS — 5/5.

### 16. End-to-end reconcile + descendant cascade (`test_reconcile_full`) green
**Expected:** All 5 tests pass — partial result.json, crashed result.json, descendant cascade keeps better, descendant cascade discards worse, INFO log marker.
**Result:** PASS — 5/5.

### 17. Framework purity: zero `autobench`/`AUTOBENCH_`/`benchmarks/` in `cells/`, `runtime_helpers.py`, `cli/cell.py`
**Expected:** Recursive grep returns zero matches.
**Result:** PASS — zero matches.

### 18. Zero-accumulator regression guard: no `+= ` on `consumed_seconds` anywhere in `state.py`
**Expected:** Static grep returns zero matches.
**Result:** PASS — zero matches.

### 19. Pitfall-4 budget=60 not 21600 (paper-campaign-vs-framework rule)
**Expected:** `grep -cE '\b21600\b' test_cap_fires_with_partial_fold_recovery.py` returns 0.
**Result:** PASS — zero matches.

### 20. Phase 4 sub-suite (cells/ + per-fold writer + submit-cell-refusal + tick_cells + cli_cell)
**Expected:** All 86 Phase 4-introduced tests pass.
**Result:** PASS — 86 passed in 10.49s.

### 21. Full test suite (no regressions)
**Expected:** 644 passed + 9 skipped (Phase 3 baseline 558 + 86 new = 644).
**Result:** PASS — 644 passed, 9 skipped, 17 warnings in 29.90s.

## Summary

**21/21 tests PASS.** All Phase 4 user-observable surfaces verified:
- CLI surfaces (submit + cell groups, --help, all flags) wired correctly
- `automil init` produces a config with the consumer-facing `cap:` section + paper-campaign-vs-framework comment block
- Live submit creates and persists cells at `automil/cells/<cell_id>.json` with the right schema
- D-134 first-submit-wins enforced (second submit's --budget-seconds silently ignored)
- Submit-time validation rejects `safety-buffer >= budget`
- Three load-bearing acceptance gates green (Pitfall-4, daemon-restart, end-to-end reconcile + cascade)
- Framework purity, zero-accumulator regression, and budget-value framework-purity guards all green
- 644 tests pass, 0 regressions from Phase 3's 558 baseline

## Gaps

None. Phase 4 ships clean.
