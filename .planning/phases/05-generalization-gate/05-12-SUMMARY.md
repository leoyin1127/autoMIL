---
phase: 05-generalization-gate
plan: "12"
subsystem: gate/calibrate
tags: [gate, calibration, D-151, GTE-04, GTE-06, smoke-test, scaffold]
dependency_graph:
  requires: ["05-09"]
  provides: ["calibration pilot scaffold", "--calibrate smoke test"]
  affects:
    - tests/gate/test_calibration_pilot_smoke.py
    - .planning/phase-05-calibration.md
tech_stack:
  added: []
  patterns: ["TDD RED/GREEN", "operator-fillable scaffold doc", "CLI smoke via CliRunner + monkeypatch"]
key_files:
  created:
    - tests/gate/test_calibration_pilot_smoke.py
    - .planning/phase-05-calibration.md
  modified: []
decisions:
  - "Smoke test drives --calibrate through CLI (CliRunner) not direct gate.promote, to exercise the full wired path"
  - "Pilot deltas use D-151 spec example: [+0.02, +0.03, -0.02, +0.04, -0.01] (3/5 wins, near-threshold)"
  - "Test 2 reads scaffold from repo root relative path — same cwd assumption as pyproject.toml testpaths"
  - "Task 2 (operator pilot) is NOT blocked on — documented as Leo Follow-up per directive"
metrics:
  duration: "~4m"
  completed: "2026-05-06T02:06:50Z"
  tasks_completed: 1
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 05 Plan 12: Calibration Pilot Scaffold + Smoke Test Summary

## One-liner

`automil promote --calibrate` smoke test (2 tests green) + operator-fillable calibration scaffold doc at `.planning/phase-05-calibration.md` with node_0176 recipe, delta matrix template, and Recommended K section.

## What Was Built

### Task 1: Smoke test + scaffold document (TDD, autonomous)

**`tests/gate/test_calibration_pilot_smoke.py`** — 2 smoke tests:

- `test_calibrate_pilot_synthetic_graph_smoke`: End-to-end CLI test. Builds a fixture
  with 5 held-out cells (3 CCRCC + 2 CLWD, mirroring D-151 spec), mixed deltas
  `[+0.02, +0.03, -0.02, +0.04, -0.01]` (3/5 wins), runs `automil promote node_0002 --calibrate`.
  Asserts: exit 0; node_0002 stays `candidate`; archive JSONL has per-cell + decision records
  covering all 5 cells; parent gate_log absent; output mentions "calibrate" or "dry".

- `test_calibration_doc_scaffold_exists`: Reads `.planning/phase-05-calibration.md`,
  asserts it contains `node_0176`, `Recommended K`, `delta`, and `wins`. Guards against
  accidental deletion of the pilot recipe.

**`.planning/phase-05-calibration.md`** — operator-fillable scaffold with:
- Header fields: status (SCAFFOLD), operator (Leo), known-good change (node_0176)
- Per-cell delta matrix table (5 rows, `_tbd_` placeholders)
- Statistical summary section (`_tbd_` placeholders)
- Recommended K section with fill-in rationale
- Sign-off checklist (3 boxes Leo must check after running pilot)
- Step-by-step 8-point procedure (cell selection → manifest → submit → calibrate → lock K)

### Task 2: Operator pilot (CHECKPOINT — see Leo Follow-up section)

The actual pilot (running node_0176 against 3 fresh CCRCC + 2 fresh CLWD cells) is Leo's
manual action. It is NOT blocked on here. The framework-side scaffold is complete; see
**Leo Follow-up** below.

## Deviations from Plan

None — plan executed exactly as written. The TDD RED phase produced: Test 1 passes (--calibrate already wired from plan 05-09), Test 2 fails (scaffold missing). GREEN phase: scaffold created, both pass.

## Leo Follow-up — Empirical Calibration Pilot (Task 2)

This is the CHECKPOINT from the plan. The executor ships the scaffold and smoke test;
Leo completes the pilot at his convenience.

**What to do:**

1. Pick 3 fresh CCRCC + 2 fresh CLWD cells (`automil cell list` — low `consumed_seconds`).
2. Apply node_0176's changes to each (Phase 1 REG-08 `automil apply node_0176`, or manually copy overlay).
3. Register the manifest for node_0176's parent: `automil gate register-manifest <parent_id> --K 3 ...`
4. Submit all 5 candidates simultaneously (saturate GPUs — ~6h per cell).
5. When complete: `automil nominate <candidate_id>` then `automil promote <candidate_id> --calibrate`
6. Fill in `.planning/phase-05-calibration.md` — replace all `_tbd_` placeholders.
7. If recommended K differs from `max(2, N//3)`, update `src/automil/templates/config.yaml.j2` `gate.K`.
8. Check the sign-off boxes; commit; mark Phase 5 "calibrated" in STATE.md / ROADMAP.md.

**Resume signals (reply with one):**
- "calibration complete; K=N locked" → proceed to Phase 5 sign-off
- "defer calibration; K stays at framework default" → Phase 5 ships with provisional K
- "calibration found pathology X; replan" → switch to revision mode

**Verification command after Leo completes the pilot:**
```bash
grep -c '_tbd_' .planning/phase-05-calibration.md
# Should return 0 (all placeholders filled)
```

## Verification Results

```
uv run pytest tests/gate/test_calibration_pilot_smoke.py -v
2 passed in 0.85s

uv run pytest tests/ -x -q
779 passed, 9 skipped, 17 warnings in 26.08s

test -f .planning/phase-05-calibration.md  → true
grep -c 'node_0176' .planning/phase-05-calibration.md  → 10
grep -c 'Recommended K' .planning/phase-05-calibration.md  → 2
grep -ciE 'delta|wins' .planning/phase-05-calibration.md  → 9
grep -c '_tbd_\|to-be-filled' .planning/phase-05-calibration.md  → 13 (scaffold confirmed)
BCK-04 purity: PASS (no os.kill / Popen / .pid in smoke test)
Framework purity: PASS (no autobench / AUTOBENCH_ / benchmarks/ refs)
```

## Known Stubs

`.planning/phase-05-calibration.md` contains 13 `_tbd_` / `to-be-filled` placeholders —
**intentional**. This is the scaffold Leo fills when running the actual pilot.
The test `test_calibration_doc_scaffold_exists` guards that these placeholders remain
until Leo's pilot is complete. The plan's goal (scaffold + smoke test) is fully achieved;
the placeholder-filling is Leo's Task 2.

## Threat Flags

No new threat surface. T-05-12-01 / T-05-12-02 / T-05-12-03 as per plan's threat model.

## Self-Check: PASSED

Files exist:
- FOUND: tests/gate/test_calibration_pilot_smoke.py
- FOUND: .planning/phase-05-calibration.md

Commits exist:
- FOUND: af48d8a (feat(05-12): calibration pilot smoke test + scaffold doc)
