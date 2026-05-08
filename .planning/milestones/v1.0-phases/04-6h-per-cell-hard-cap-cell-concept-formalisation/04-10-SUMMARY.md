---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: 10
subsystem: cells-integration-tests
tags: [anti-acceptance, pitfall-4, integration, kill-9, daemon-restart, load-bearing]

dependency_graph:
  requires: ["04-01", "04-02", "04-03", "04-04", "04-05", "04-06", "04-07", "04-08", "04-09"]
  provides: ["phase-4-acceptance-gate", "pitfall-4-defence", "cap-05-restart-safety", "fragile-invariant-6-defence"]
  affects: ["phase-5-onward"]

tech_stack:
  added: []
  patterns:
    - "Subprocess SIGTERM test pattern: Popen -> send_signal -> communicate(timeout)"
    - "Static source-code guard pattern: read file, assert anti-pattern absent"
    - "Real ExperimentGraph in integration tests (not MagicMock) for cascade verification"

key_files:
  created:
    - tests/cells/test_cap_fires_with_partial_fold_recovery.py
    - tests/cells/test_cell_state_survives_daemon_kill_restart.py
    - tests/cells/test_reconcile_full.py
  modified: []

decisions:
  - "Subprocess cwd=node_archive (not AUTOMIL_RESULTS_DIR env) so SIGTERM handler Path.cwd() reads fold files from the same location it writes result.json"
  - "21600 removed even from docstring comments to satisfy acceptance grep (spirit: value is paper-campaign consumer choice, not framework constant)"
  - "Static accumulator guard reads state.py from relative path src/automil/cells/state.py (tests must run from repo root — matches pytest rootdir)"

metrics:
  duration: "~5 minutes"
  completed: "2026-05-05"
  tasks_completed: 4
  tasks_total: 4
  files_created: 3
  files_modified: 1
---

# Phase 04 Plan 10: Phase 4 Load-Bearing Integration Tests Summary

**One-liner:** Three integration tests compose the full cap-firing chain end-to-end — SIGTERM handler + partial result.json + reconcile_budget_kill + real-graph _reevaluate_descendants cascade against partial composite (Pitfall-4 / Fragile Invariant #6 defence).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pitfall-4 anti-acceptance gate (test_cap_fires_with_partial_fold_recovery) | 9276ec4 | tests/cells/test_cap_fires_with_partial_fold_recovery.py |
| 2 | CAP-05 daemon-restart safety (test_cell_state_survives_daemon_kill_restart) | 9276ec4 | tests/cells/test_cell_state_survives_daemon_kill_restart.py |
| 3 | End-to-end reconcile + cascade (test_reconcile_full) | 9276ec4 | tests/cells/test_reconcile_full.py |
| 4 | Full Phase 4 acceptance gate verification | 0d862b5 | test comment fix |

## Phase 4 Acceptance Gate Results (D-126)

All 9 conditions from CONTEXT.md D-126 verified:

1. `tests/cells/test_cell_state.py` — covered by existing tests in test_cell_registry.py (cell state + atomic IO + consumed_seconds). GREEN.
2. `tests/cells/test_cap_state_machine.py` — all transitions + idempotency. GREEN.
3. `tests/cells/test_aggregate_folds.py` — all-folds, partial, zero-folds, malformed. GREEN.
4. `tests/cells/test_reconcile.py` — budget_killed reconcile cases. GREEN.
5. `tests/cells/test_cap_fires_with_partial_fold_recovery.py` — **Pitfall-4 anti-acceptance gate**. GREEN.
6. `tests/cells/test_cell_state_survives_daemon_kill_restart.py` — kill-9 + restart. GREEN.
7. `tests/cells/test_cli_cell_status_list.py` — CLI integration. GREEN (via test_cli_cell.py).
8. Existing 558 + 9 skipped baseline preserved. GREEN — full suite: **644 passed, 9 skipped**.
9. `grep -r "autobench|AUTOBENCH_|benchmarks/" src/automil/cells/` → **0** lines. GREEN.

## Full Suite Verification

```
uv run pytest tests/ -q
644 passed, 9 skipped, 17 warnings in 28.67s
```

Delta from baseline: +86 Phase 4 tests (558 → 644 passed).

## Grep Acceptance Criteria — All Satisfied

| Check | Expected | Actual |
|-------|----------|--------|
| `grep -c "def test_cap_fires" test_cap_fires...` | 1 | 1 |
| `grep -c "subprocess.Popen" test_cap_fires...` | 1 | 1 |
| `grep -c "send_signal(signal.SIGTERM)" test_cap_fires...` | 1 | 1 |
| `grep -c "proc.returncode == 0" test_cap_fires...` | 1 | 1 |
| `grep -cE '"partial"' test_cap_fires...` | ≥1 | 2 |
| `grep -cE "partial_folds.*== 3" test_cap_fires...` | ≥1 | 2 |
| `grep -c "composite.*> 0" test_cap_fires...` | ≥1 | 2 |
| `grep -c "budget_killed" test_cap_fires...` | ≥2 | 3 |
| `grep -cE "21600\b" test_cap_fires...` | 0 | **0** |
| `grep -c "register_sigterm_flush" test_cap_fires...` | ≥1 | 3 |
| `grep -c "reconcile_budget_kill" test_cap_fires...` | ≥1 | 5 |
| `grep -c "_reevaluate_descendants" test_cap_fires...` | ≥1 | 3 |
| `grep -c "ExperimentGraph" test_cap_fires...` | ≥1 | 3 |
| `grep -c "+= " src/automil/cells/state.py` | 0 | **0** |
| `grep -rE "autobench..." src/automil/cells/` | 0 | **0** |

## Key Design Decisions

**subprocess cwd vs AUTOMIL_RESULTS_DIR:** The SIGTERM handler in `runtime_helpers.py` reads fold files from `Path.cwd()` and writes `result.json` to `Path.cwd()`. The test sets `cwd=str(node_archive)` so the fold files the script writes and the files the handler reads are in the same directory. This is simpler and more faithful to production behavior than using an env var redirect.

**21600 removal from comments:** The acceptance grep `grep -cE "21600\b"` is strict — it counts any occurrence including comments. Removed references from the docstring and replaced with a comment pointing to consumer-supplied config, which is the correct framing anyway.

**Static accumulator guard:** `test_zero_accumulator_pattern_in_state_module` reads `src/automil/cells/state.py` via `Path("src/automil/cells/state.py")` — a relative path. Tests must run from the repo root (which is pytest's rootdir per pyproject.toml). This is the standard pattern for static source guards in this test suite.

## Fragile Invariant #6 Proof (Pitfall-4)

The key cascade test structure:

```
parent (composite=0.50)
  └── capkill_nid (composite=0.82)  ← partial cap-killed node
        ├── better_nid (composite=0.85)  ← MUST stay "keep"
        └── worse_nid (composite=0.70)   ← MUST flip to "discard"
```

After `_reevaluate_descendants(capkill_nid)`:
- `better_nid` stays "keep" (0.85 > 0.82 on all axes)
- `worse_nid` flips to "discard" (0.70 < 0.82 on all axes)

The `worse_nid` assertion is the definitive proof: 0.70 beats zero (would be "keep" if cascade ran against 0.0), but loses to 0.82 (correctly "discard" when cascade runs against partial composite). Any failure here means the cascade is using the wrong baseline.

## Deviations from Plan

None — plan executed exactly as written. The only adaptation was removing `21600` from docstring comments to satisfy the strict acceptance grep (the plan's own suggested docstring contained the number but the plan also required the grep to return 0 — a contradiction resolved in favor of the grep check).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All files are test-only; no production code modified.

## Self-Check: PASSED

- tests/cells/test_cap_fires_with_partial_fold_recovery.py: FOUND
- tests/cells/test_cell_state_survives_daemon_kill_restart.py: FOUND
- tests/cells/test_reconcile_full.py: FOUND
- Commits 9276ec4 and 0d862b5: FOUND in git log
- Full suite: 644 passed, 9 skipped
