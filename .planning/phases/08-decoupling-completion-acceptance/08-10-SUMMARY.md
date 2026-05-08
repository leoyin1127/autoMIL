---
phase: 08-decoupling-completion-acceptance
plan: 10
subsystem: acceptance-gate
tags: [acceptance, changelog, milestone, state-update, requirements]
dependency_graph:
  requires: [08-01, 08-02, 08-03, 08-04, 08-05, 08-06, 08-07, 08-08, 08-09]
  provides: [D-208-acceptance-gate, CHANGELOG-8.0.0, milestone-v1.0-complete]
  affects: [tests/acceptance, CHANGELOG.md, .planning/STATE.md, .planning/ROADMAP.md]
tech_stack:
  added: []
  patterns: [single-file-aggregator, changelog-as-migration-surface, deterministic-anchor-testing]
key_files:
  created:
    - tests/acceptance/test_phase8_acceptance.py
  modified:
    - CHANGELOG.md
    - .planning/STATE.md
    - .planning/ROADMAP.md
decisions:
  - "F-09: clause 11 anchors on CHANGELOG content + REQUIREMENTS.md DEC rows, not circular ROADMAP/STATE"
  - "F-06: 4-cell migration matrix in CHANGELOG with explicit AUTOBENCH_OVARIAN_ROOT + AUTOBENCH_CCRCC_ROOT"
  - "REQUIREMENTS.md DEC-01..07 were already Complete from prior plans; no change needed"
metrics:
  duration: 5m
  completed: 2026-05-08
---

# Phase 8 Plan 10: D-208 Acceptance Gate + Milestone v1.0 SUMMARY

**One-liner:** 11-clause D-208 acceptance gate green (all PASS); CHANGELOG 8.0.0 with BREAKING migration matrix; STATE.md and ROADMAP.md mark milestone v1.0 complete.

## What Was Shipped

### Task 1: D-208 acceptance gate (tests/acceptance/test_phase8_acceptance.py)

Created `tests/acceptance/test_phase8_acceptance.py` with exactly 11 test functions mapping 1:1 to D-208 clauses:

| Test | D-208 Clause | Outcome |
|------|-------------|---------|
| test_d208_clause_01_framework_purity | Zero autobench refs in src/automil/ | PASS |
| test_d208_clause_02_result_schema_validation | result.schema.json exists + daemon validates | PASS |
| test_d208_clause_03_graph_dict_spread | node["metrics"] = dict(metrics) + composite-only Pareto | PASS |
| test_d208_clause_04_env_required_validator | _validate_env_required in check.py + template scoring block | PASS |
| test_d208_clause_05_sklearn_iris_consumer_exists | examples/sklearn-iris/ complete scaffolding | PASS |
| test_d208_clause_06_training_script_contract_doc | docs/training-script-contract.md exists | PASS |
| test_d208_clause_07_framework_purity_grep_gate | test_framework_purity.py has _ALLOWLIST with all 3 entries | PASS |
| test_d208_clause_08_final_acceptance_gate | sub-gate B (sklearn-iris end-to-end) PASS; A+C SKIP cleanly | PASS |
| test_d208_clause_09_baseline_plus_10_tests | >=858 tests collected (Phase 7 848 + Phase 8 10+) | PASS |
| test_d208_clause_10_changelog_8_0_0 | CHANGELOG has ## 8.0.0 + BREAKING + env.required + metrics dict | PASS |
| test_d208_clause_11_state_roadmap_complete | CHANGELOG head == 8.0.0; DEC-01..07 all Complete | PASS |

**Iter-2 / F-09 fix applied:** clause 11 anchors on CHANGELOG.md head section heading (must start with "8.0.0") + explicit AUTOBENCH_OVARIAN_ROOT/AUTOBENCH_CCRCC_ROOT in CHANGELOG + REQUIREMENTS.md DEC-01..07 rows marked Complete. The previous circular logic (asserting ROADMAP/STATE which this same plan updates) is removed.

### Task 2: CHANGELOG 8.0.0 entry

Added `## 8.0.0 - Phase 8 decoupling completion + final acceptance (unreleased)` above the 7.0.0 entry. Contains:

- **3 BREAKING subsections**: env.required now mandatory, node["metrics"] storage migration, AUTOBENCH_ROOT auto-injection removed
- **Iter-2 / F-06 4-cell migration matrix**: explicit AUTOBENCH_OVARIAN_ROOT + AUTOBENCH_CCRCC_ROOT in both `required` and `passthrough` lists; sklearn-iris case documented as empty lists
- **Added, Verification, Compatibility sections**

Zero em-dashes in the new 8.0.0 section.

### Task 3: STATE.md milestone v1.0 complete

- Frontmatter: `status: complete`, `completed_phases: 9`, `percent: 100`, `total_plans: 92` (resolved at execution time via `find`)
- Current Position: Phase 08 COMPLETE, milestone v1.0 complete, ready to ship
- Phase 8 follow-ups section: 5 deferred items (sub-gate C, schema_version bump, results.tsv generalization, viz generic rendering, allowlist neighbor cleanup)
- Session continuity updated with Phase 8 completion record

### Task 4: ROADMAP.md Phase 8 success criteria

- All 5 success criteria annotated `[x]` with clause verification references
- Plans line updated from "TBD" to "10 across 4 waves"
- REQUIREMENTS.md DEC-01..07 rows were already Complete from prior plans (no edit needed; F-10 is satisfied)

## Deviations from Plan

None - plan executed exactly as written.

The only deviation from the template: REQUIREMENTS.md DEC-01..07 were already marked `Complete` by earlier plans in this phase, so Task 4 Step C required no edits. The clause 11 assertion still passes because the rows ARE marked Complete as required.

## Known Stubs

None. The acceptance gate runs real tests; CHANGELOG content is substantive; planning docs are fully updated.

## Threat Flags

None. This plan creates test infrastructure and updates planning docs only; no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

Files created/modified:
- tests/acceptance/test_phase8_acceptance.py: FOUND
- CHANGELOG.md: FOUND (## 8.0.0 heading confirmed)
- .planning/STATE.md: FOUND (status: complete, completed_phases: 9)
- .planning/ROADMAP.md: FOUND (Phase 8 criteria all [x])
- .planning/REQUIREMENTS.md: FOUND (DEC-01..07 Complete, no edit needed)

Commits:
- 08451d1: test(08-10): add D-208 11-clause acceptance gate test file
- 036d8a5: feat(08-10): add CHANGELOG 8.0.0 entry with BREAKING migration text
- 546a068: feat(08-10): mark Phase 8 complete in ROADMAP + STATE, milestone v1.0

Acceptance gate result: `uv run pytest tests/acceptance/test_phase8_acceptance.py -v` -> 11 passed in 33.23s
