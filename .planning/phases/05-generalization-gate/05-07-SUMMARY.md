---
phase: 05-generalization-gate
plan: "07"
subsystem: gate
tags: [gate, promote, two-stage, statistical-test, bonferroni, tdd]
dependency_graph:
  requires:
    - 05-01  # gate/stats.py — paired_wilcoxon_with_bootstrap, bonferroni_correct
    - 05-02  # gate/manifest.py — load_manifest, GateManifest
    - 05-04  # gate/nominate.py — nominate (Stage A)
    - 05-06  # gate/evaluate.py — evaluate_candidate (Stage B eval)
  provides:
    - promote  # gate/promote.py — promote(candidate_id, backend, graph) -> bool
  affects:
    - gate/__init__.py  # re-exports promote
    - tests/gate/test_promote.py
    - tests/gate/test_two_stage_gate.py
tech_stack:
  added: []
  patterns:
    - TDD (RED commit + GREEN feat commit + refactor fix)
    - sys.modules monkeypatching for pytest (module/function name collision workaround)
    - append-only JSONL forensic logs (archive + parent gate_log)
    - Bonferroni divide-direction (p_threshold/K, never multiply p-values)
key_files:
  created:
    - src/automil/gate/promote.py
    - tests/gate/test_promote.py
    - tests/gate/test_two_stage_gate.py
  modified:
    - src/automil/gate/__init__.py
decisions:
  - "promote() calls graph.save() once at end — same caller-discipline as nominate/cells/registry"
  - "inconclusive path (K_effective < K_floor): status stays 'candidate', NOT reverted to keep (D-150)"
  - "calibrate=True writes archive log but NOT parent gate_log (calibration runs not in promotion-rate window)"
  - "parent gate_log path: manifests_dir/<parent_id>.gate_log.jsonl (sibling to manifest, not a separate dir)"
  - "test pass path uses p_threshold=0.2, K=5 to satisfy Wilcoxon minimum-p constraint (n=5 min-p=0.031; 0.2/5=0.04 > 0.031)"
  - "monkeypatch via sys.modules['automil.gate.promote'] to avoid pytest name-resolution collision with function promote"
metrics:
  duration: "~45 minutes"
  completed: "2026-05-05"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 5 Plan 07: promote() gate orchestrator + two-stage composition test Summary

Composed Wave 1+2+3+4 outputs into the actual gate decision: `promote()` loads the parent manifest, runs `evaluate_candidate`, applies Bonferroni-corrected paired Wilcoxon + bootstrap CI, and mutates candidate status to `registered` (pass), `keep` (fail), or stays `candidate` (inconclusive when too many cells skipped).

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 RED | promote() tests | 6f93c58 | tests/gate/test_promote.py (11 tests) |
| 1 GREEN | promote() implementation | c9706b6 | src/automil/gate/promote.py, gate/__init__.py |
| 1 REFACTOR | inline wilcoxon grep | 538c4bb | src/automil/gate/promote.py |
| 2 | Two-stage gate tests | f23919e | tests/gate/test_two_stage_gate.py (4 tests) |

## What Was Built

**`src/automil/gate/promote.py`** — the head of the Phase 5 critical path:
- `promote(candidate_node_id, backend, graph, manifests_dir, archive_dir, K_floor=2, calibrate=False) -> bool`
- Validates status='candidate' (raises ValueError with "nominate first" hint — T-05-07-01 mitigation)
- Loads parent manifest via `load_manifest()` (raises FileNotFoundError if absent)
- Calls `evaluate_candidate()` to get per-cell results and skipped list
- D-150 K_floor check: if `K_effective < K_floor`, logs WARNING, records inconclusive event, status stays 'candidate', returns False
- Bonferroni correction: `p_corrected = bonferroni_correct(p_threshold, K_effective)` — divide alpha by K (never multiply p-values)
- Statistical test: `paired_wilcoxon_with_bootstrap(deltas, p_corrected, bootstrap_reps)`
- Win criterion: `passes_test AND wins >= K_effective`
- Status mutation: `registered` (pass) or `keep` (fail)
- Two logs: `archive/<candidate_id>/gate_evaluation.jsonl` (per-candidate forensic) + `<parent_id>.gate_log.jsonl` (per-parent append-only)
- D-151 calibrate mode: archive log written, no status mutation, no parent gate_log
- `graph.save()` called once at end

**`tests/gate/test_promote.py`** — 11 tests covering all paths + acceptance criteria:
- Tests 1-2: validation errors (non-candidate status, missing manifest)
- Tests 3-4: pass/fail paths with status transitions and history events
- Test 5: inconclusive path (K_effective < K_floor, status stays 'candidate')
- Test 6: Bonferroni spy (K=4, p=0.05 → 0.0125 captured)
- Tests 7-8: archive + parent JSONL log writing + append behaviour
- Test 9: calibrate dry-run (archive yes, parent log no, status unchanged)
- Test 10: graph.save() mtime change
- Test 11: framework purity grep

**`tests/gate/test_two_stage_gate.py`** — 4 tests for D-143 two-stage composition:
- Test 1: full keep→nominated→registered trail with ordered history events
- Test 2: Stage A blocks promote without nominate (ValueError)
- Test 3: Stage B can revert to keep (fail path history trail)
- Test 4: disjoint data proof (search-cell composite not in held-out deltas)

## Test Results

- `tests/gate/test_promote.py`: 11/11 passed
- `tests/gate/test_two_stage_gate.py`: 4/4 passed
- `tests/gate/` full suite: 64/64 passed
- `tests/` full suite: 736 passed, 9 skipped, 0 failed

## Acceptance Criteria Verification

```
grep -c 'def promote(' src/automil/gate/promote.py     -> 1 ✓
grep -c 'bonferroni_correct(' src/automil/gate/promote.py -> 1 ✓
grep -c 'paired_wilcoxon_with_bootstrap.*deltas, p_corrected' src/automil/gate/promote.py -> 1 ✓
grep -c 'evaluate_candidate(' src/automil/gate/promote.py -> 1 ✓
grep -c '"registered"' src/automil/gate/promote.py     -> 1 ✓
grep -c 'inconclusive' src/automil/gate/promote.py     -> 6 ✓
grep -c 'calibrate' src/automil/gate/promote.py        -> 9 ✓
grep -cE 'autobench|AUTOBENCH_|benchmarks/' src/automil/gate/promote.py -> 0 ✓
python -c "from automil.gate import promote; print('ok')" -> ok ✓
grep -c 'p_corrected = bonferroni_correct' src/automil/gate/promote.py -> 1 ✓
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wilcoxon minimum p-value constraint in pass-path test**
- **Found during:** Task 1 GREEN phase
- **Issue:** The plan specifies `[0.05, 0.04, 0.06]` for the pass-path mock deltas with K=3. With the Wilcoxon one-sided test, n=3 has a minimum achievable p-value of 0.125, which cannot pass the Bonferroni-corrected threshold of 0.05/3=0.017. The gate correctly fails — but the test was asserting True.
- **Fix:** Changed the pass-path test to use 5 held-out cells with `p_threshold=0.2` (Bonferroni-corrected = 0.04 > Wilcoxon n=5 min-p=0.031). This is a test fixture correction — the implementation is correct.
- **Files modified:** tests/gate/test_promote.py
- **Commit:** c9706b6 (included in GREEN commit)

**2. [Rule 1 - Bug] pytest monkeypatch name-resolution collision**
- **Found during:** Task 1 GREEN phase
- **Issue:** `monkeypatch.setattr("automil.gate.promote.evaluate_candidate", ...)` failed because pytest resolved the string `automil.gate.promote` to the `promote` *function* exported from `__init__.py`, not the `promote` *module*. This is a Python packaging collision when a module and its main export share a name.
- **Fix:** Changed to `monkeypatch.setattr(sys.modules["automil.gate.promote"], "evaluate_candidate", ...)` via a `_get_promote_module()` helper using `sys.modules` + `importlib.import_module` as fallback.
- **Files modified:** tests/gate/test_promote.py
- **Commit:** c9706b6

**3. [Rule 1 - Bug] Framework purity docstring reference**
- **Found during:** Task 1 test run (test_promote_no_autobench_imports)
- **Issue:** The module docstring in promote.py contained the phrase "zero autobench / AUTOBENCH_ / benchmarks/ references" explaining what is absent — but the purity test grep found "autobench" in the source text.
- **Fix:** Rewrote the docstring sentence to "Framework purity: no benchmark-specific references (D-148)".
- **Files modified:** src/automil/gate/promote.py
- **Commit:** c9706b6

**4. [Rule 2 - Missing] Single-line wilcoxon call for grep acceptance**
- **Found during:** Task 1 verification (acceptance check item 12)
- **Issue:** The call `paired_wilcoxon_with_bootstrap(deltas, p_corrected, ...)` was split across two lines, causing the acceptance grep `'paired_wilcoxon_with_bootstrap.*deltas, p_corrected'` to return 0 instead of 1.
- **Fix:** Collapsed to single line with `# noqa: E501`.
- **Files modified:** src/automil/gate/promote.py
- **Commit:** 538c4bb (refactor commit)

## Known Stubs

None — promote() is fully wired. Both log paths are written. Status transitions are implemented.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The two log paths (`archive/<id>/gate_evaluation.jsonl` and `<parent_id>.gate_log.jsonl`) are local filesystem writes — consistent with T-05-07-03 (Information Disclosure: accepted, gate logs are forensic records).

## Self-Check: PASSED

Files created:
- `src/automil/gate/promote.py` — FOUND ✓
- `tests/gate/test_promote.py` — FOUND ✓
- `tests/gate/test_two_stage_gate.py` — FOUND ✓

Commits:
- 6f93c58 (test RED) — FOUND ✓
- c9706b6 (feat GREEN) — FOUND ✓
- f23919e (test two-stage) — FOUND ✓
- 538c4bb (refactor) — FOUND ✓
