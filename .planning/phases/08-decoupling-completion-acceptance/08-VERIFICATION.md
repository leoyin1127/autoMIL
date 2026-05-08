---
phase: 08-decoupling-completion-acceptance
verified: 2026-05-08T04:10:00Z
status: human_needed
score: 11/12 dimensions PASS, 1 PARTIAL
milestone: v1.0
milestone_status: ready_to_ship_pending_workstation_subgates
re_verification:
  previous_status: not_previously_verified
  is_initial_verification: true
overrides_applied: 0
gaps:
  - truth: "Phase 7 baseline test count preserved without new Phase 8 regressions"
    status: partial
    reason: "Phase 8 plan 08-05 dropped pythonpath + worktree_benchmarks kwargs from _build_subprocess_env, but tests/test_tick_cells.py::test_automil_fold_count_injected_into_subprocess_env (Phase 4 commit 0a8ac33) still calls with those kwargs and now fails with TypeError. STATE.md documents 3 pre-existing tick_cells failures from Phase 4 wiring drift; this 4th failure is a Phase 8 regression that was not surfaced or documented."
    artifacts:
      - path: "tests/test_tick_cells.py"
        issue: "Line 477 calls orch._build_subprocess_env(pythonpath=..., worktree_benchmarks=...) which Phase 8 plan 08-05 removed; TypeError on test execution."
    missing:
      - "Update tests/test_tick_cells.py::test_automil_fold_count_injected_into_subprocess_env to drop pythonpath + worktree_benchmarks kwargs (mirror the Phase 8 plan 08-05 _call_build helper update in tests/test_orchestrator_env_whitelist.py)"
      - "Document the 4th tick_cells failure in STATE.md Phase 8 follow-ups OR fix it before tagging v1.0.0"
human_verification:
  - test: "Sub-gate A (CCRCC reproduction)"
    expected: "automil verify-repro node_0176 against benchmarks/experiments/ccrcc reproduces composite within +-0.005 of 0.502"
    why_human: "Requires AUTOBENCH_CCRCC_ROOT env var pointing at real CCRCC dataset; not available in CI. Test marked @pytest.mark.requires_ccrcc_data, SKIPS cleanly in CI. Leo runs this on workstation."
  - test: "Sub-gate C (heterogeneous consumers in same project)"
    expected: "Both sklearn-iris (composite >= 0.90) and CCRCC node_0176 (composite within +-0.005 of 0.502) succeed in the same tmp project tree"
    why_human: "Requires AUTOBENCH_CCRCC_ROOT + a configured CCRCC + sklearn-iris co-registered project layout. Body is currently pytest.skip() per 08-09-SUMMARY decision; workstation completion deferred per STATE.md Phase 8 follow-up #1."
  - test: "v1.0.0 tagging readiness"
    expected: "After sub-gates A+C validate on Leo's workstation AND the tick_cells regression is resolved, tag v1.0.0"
    why_human: "Final go/no-go decision; requires Leo's workstation review and explicit milestone shipment confirmation."
---

# Phase 8: Decoupling Completion + Final Acceptance Verification Report

**Phase Goal:** Audit the framework end-to-end for autobench leakage, prove genericity by plugging in a second consumer (sklearn-iris), and run the final acceptance gate -- CCRCC `node_0176` reproduces +-0.005 on a clean checkout via the registry path with all phases composed together.

**Verified:** 2026-05-08T04:10:00Z
**Status:** human_needed (1 partial gap + 2 CCRCC-data-gated sub-gates)
**Re-verification:** No -- initial verification

## Executive Summary

Phase 8 delivers all 7 DEC requirements (DEC-01..07) and honors all 10 locked engineering decisions (D-199..D-208). The framework is now autobench-purged (5 grep matches, all in the documented allowlist), result.json is JSON-Schema-validated at ingest, graph.py uses dict-spread metric storage with composite-only Pareto, env.required is a first-class config field validated by `automil check`, the sklearn-iris second consumer plugs into the framework end-to-end (sub-gate B PASS in 12.6s), and the D-208 11-clause aggregator passes green (33.23s). The CHANGELOG 8.0.0 entry documents 3 BREAKING changes with a 4-cell migration matrix. ROADMAP, STATE.md, and REQUIREMENTS.md all mark milestone v1.0 complete. **One Phase-8-introduced regression** was found and not documented: `tests/test_tick_cells.py::test_automil_fold_count_injected_into_subprocess_env` now fails with TypeError because plan 08-05 removed `pythonpath`/`worktree_benchmarks` kwargs from `_build_subprocess_env` but did not update this Phase 4 test. CCRCC-data-gated sub-gates A+C require Leo's workstation to validate.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All 7 DEC requirements (DEC-01..07) marked Complete with code+test pair | PASS | REQUIREMENTS.md lines 238-244 all `Complete`; per-DEC plan-test mapping in 08-PLAN-SUMMARY.md verified |
| 2 | All 10 D-199..D-208 engineering decisions honored | PASS | See "D-199..D-208 Honoring Map" below; each decision verified against code |
| 3 | ROADMAP Phase 8 success criterion 1: zero autobench refs in src/automil/ | PASS | grep returns 5 hits, all in `_ALLOWLIST` of `tests/test_framework_purity.py`; test passes |
| 4 | ROADMAP SC-2: sklearn-iris consumer plugs in via documented contract end-to-end | PASS | Sub-gate B PASS (12.6s, composite=1.0); examples/sklearn-iris/ shipped 6 files; docs/training-script-contract.md cross-links it |
| 5 | ROADMAP SC-3: composite scoring config-driven; env.required validated by automil check | PASS | `_validate_env_required` at check.py:60; config.yaml.j2 has env: + scoring: blocks; 10 cli/test_check_env_required tests pass |
| 6 | ROADMAP SC-4: docs/training-script-contract.md documents 6 contract items | PASS | 253-line doc with all 6 anchors; 8 tests in tests/test_phase8_docs_exist.py pass |
| 7 | ROADMAP SC-5: final acceptance (CCRCC + sklearn-iris) | UNCERTAIN | Sub-gate B PASS in CI; sub-gates A+C SKIP cleanly (workstation only) |
| 8 | D-208 11-clause aggregator passes | PASS | tests/acceptance/test_phase8_acceptance.py: 11 passed in 32.35s |
| 9 | Framework purity (test_framework_purity.py) PASSES with allowlist | PASS | 3/3 tests pass; allowlist 5 entries with content anchors |
| 10 | Em-dash gate clean on Phase-8-new files | PASS | grep U+2014/U+2013 across schemas/, sklearn-iris/, contract doc, framework purity test, acceptance/, CHANGELOG 8.0.0 section: zero hits |
| 11 | CHANGELOG 8.0.0 entry exists with breaking changes + migration matrix per F-06 | PASS | CHANGELOG.md lines 5-94: ## 8.0.0 heading, 3 BREAKING subsections, AUTOBENCH_OVARIAN_ROOT + AUTOBENCH_CCRCC_ROOT in both required+passthrough lists |
| 12 | Phase 7 baseline (838+) test count preserved + ≥10 new tests added (D-208 clause 9 floor 858) | PARTIAL | 950 total collected (936 excluding pre-existing autobench-broken file). Phase 8 adds 47+ new tests across 9 new test files. **Regression:** 1 Phase-8-introduced tick_cells test failure from removed `pythonpath` kwargs in `_build_subprocess_env`; not previously documented in STATE.md follow-ups list |

**Score:** 11/12 PASS, 1 PARTIAL (truth 12).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/automil/schemas/__init__.py` | Re-exports validate_result, RESULT_SCHEMA, ValidationError | VERIFIED | 14 lines, public symbols imported and re-exported |
| `src/automil/schemas/_result.py` | Draft202012Validator pre-compiled | VERIFIED | 40 lines; validator built once at module load; raises jsonschema.ValidationError |
| `src/automil/schemas/result.schema.json` | D-201 contract (composite required, additionalProperties: true) | VERIFIED | 25 lines, exact D-201 spec |
| `src/automil/graph.py` | dict-spread `node["metrics"] = dict(metrics)` at 5 sites + composite-only Pareto at 3 sites | VERIFIED | grep `'(test_auc|test_bacc|val_auc|val_bacc)":'` returns only lines 783-784 (bootstrap loader, intentionally retained per OQ-8) |
| `src/automil/backends/_orchestrator_daemon.py` | AUTOBENCH purge complete + validate_result hook at ingest | VERIFIED | Daemon line 1078: inline import + validate_result call; line 1093: schema-pointer error message; AUTOBENCH_ROOT injection block deleted |
| `src/automil/cli/check.py` | `_validate_env_required` at line 60 + caller at line 265 | VERIFIED | grep -c returns 2; missing-env-var error message includes literal "see automil/config.yaml: env.required" pointer |
| `src/automil/templates/config.yaml.j2` | env: required+passthrough block + scoring: formula block | VERIFIED | env: at line 107, scoring: at line 123 |
| `examples/sklearn-iris/train.py` | <=80 lines, sklearn LogisticRegression, writes result.json per D-201 schema | VERIFIED | 80 lines exactly; SIGTERM handler inline; CWD-relative result.json |
| `examples/sklearn-iris/automil/config.yaml` | env.required: [], scoring.formula: "accuracy" | VERIFIED | Consumer-pure config |
| `examples/sklearn-iris/automil/program.md` | Search-space narrative | VERIFIED | 22 lines |
| `examples/sklearn-iris/automil/variants/classifier_v0/__init__.py` | Package marker | VERIFIED | 7 lines, no automil.* imports |
| `examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py` | make_classifier(seed=42) | VERIFIED | 13 lines, plain sklearn |
| `examples/sklearn-iris/README.md` | Quickstart | VERIFIED | 47 lines |
| `docs/training-script-contract.md` | All 6 contract items + sklearn cross-link + pytorch skeleton + 2 SIGTERM patterns + pitfalls | VERIFIED | 253 lines; 8 docs-exist tests PASS |
| `tests/acceptance/test_phase8_acceptance.py` | 11-clause D-208 aggregator | VERIFIED | 11 tests; all PASS in 32.35s |
| `tests/acceptance/test_final_phase8_acceptance.py` | Sub-gates A/B/C with markers | VERIFIED | Sub-gate B PASS (12.6s); A+C SKIP cleanly per requires_ccrcc_data marker |
| `tests/test_framework_purity.py` | DEC-01 D-206 grep gate + 5-entry allowlist | VERIFIED | 3 tests PASS; allowlist content anchors validated by line-drift defender |
| `CHANGELOG.md` | 8.0.0 entry with BREAKING + migration matrix | VERIFIED | Lines 5-94; 3 BREAKING subsections + 4-cell migration matrix |
| `.planning/STATE.md` | status: complete + completed_phases: 9 + percent: 100 | VERIFIED | Frontmatter lines 5-12 confirm milestone v1.0 complete |
| `.planning/ROADMAP.md` | All 9 phases `[x]`; Phase 8 SCs all `[x]` | VERIFIED | Lines 15-23 all checked; lines 197-201 SCs all `[x]` |
| `.planning/REQUIREMENTS.md` | DEC-01..07 all Complete | VERIFIED | Lines 238-244 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `_orchestrator_daemon.py` ingestion path | `automil.schemas.validate_result` | inline import + call at line 1078 | WIRED | Verified by tests/backends/test_daemon_result_schema_validation.py (9 tests PASS); validation runs end-to-end in sub-gate B |
| `automil check` CLI | `_validate_env_required` | call at check.py:265 | WIRED | 10 tests in tests/cli/test_check_env_required.py PASS; CLI smoke test against fresh tmp project succeeds |
| `examples/sklearn-iris/train.py` | result.schema.json | runtime validation by daemon, schema not imported by train.py | WIRED | Sub-gate B exercises full path; result.json validated by daemon ingest hook |
| `automil init` template scaffold | env: + scoring: blocks in config.yaml.j2 | render | WIRED | Smoke test: fresh tmp project gets `env: required: []` + `scoring: formula: ""` in scaffolded config.yaml |
| `tests/test_framework_purity.py` | `src/automil/` grep | subprocess + allowlist | WIRED | All 3 tests PASS; line-drift defender verifies anchor content |
| `tests/acceptance/test_phase8_acceptance.py` clauses 7-8 | `tests/test_framework_purity.py` + `tests/acceptance/test_final_phase8_acceptance.py` | subprocess pytest invocation | WIRED | Both gates exercised; aggregator green |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| automil CLI base command works | `uv run automil --help` | Lists all subcommands incl. orchestrator, check, init | PASS |
| automil init scaffolds env: + scoring: blocks | tmp project + `automil init --no-healthcheck` | env: present at config.yaml line 107; scoring: at line 123 | PASS |
| automil check accepts new schema | tmp project + `automil check` | Errors are placeholder paths only; env.required validation path healthy | PASS |
| Framework purity gate green | `pytest tests/test_framework_purity.py` | 3 passed in 0.08s | PASS |
| D-208 11-clause aggregator green | `pytest tests/acceptance/test_phase8_acceptance.py -v` | 11 passed in 32.35s | PASS |
| Sub-gate B end-to-end (sklearn-iris) | `pytest tests/acceptance/test_final_phase8_acceptance.py -v` | 1 passed (12.6s, composite=1.0), 2 skipped (data-gated) | PASS |
| Phase 8 new test suite | All 47 new tests across 9 files | 47 passed in 0.30s | PASS |
| Graph + env-whitelist regression suite | `pytest tests/test_graph.py tests/test_integration.py tests/test_orchestrator_env_whitelist.py` | 50 passed in 1.95s | PASS |

### DEC-01..07 Delivery Map

| Req ID | Description | Code Delivered | Test Delivered | Status |
|--------|-------------|----------------|----------------|--------|
| DEC-01 | zero autobench refs in src/automil/ | `_orchestrator_daemon.py` AUTOBENCH purge (commits e98bb1b + 4f43f2f) | tests/test_framework_purity.py (3 tests, allowlist) | DELIVERED |
| DEC-02 | sklearn-iris second consumer end-to-end | examples/sklearn-iris/ (6 files) | tests/acceptance/test_final_phase8_acceptance.py sub-gate B | DELIVERED |
| DEC-03 | result.json JSON-Schema-validated | src/automil/schemas/ + daemon ingest hook | tests/test_result_schema_validation.py (8) + tests/backends/test_daemon_result_schema_validation.py (9) | DELIVERED |
| DEC-04 | composite scoring config-driven; graph.py decoupled from autobench 4-key | graph.py dict-spread (5 sites) + composite-only Pareto (3 sites) + viz reader migration + scoring: in template | tests/test_graph_dict_spread.py (6) + tests/viz/test_app_js_metrics_reader.py (3) | DELIVERED |
| DEC-05 | env.required validated by automil check | _validate_env_required helper + config.yaml.j2 env: block | tests/cli/test_check_env_required.py (10) | DELIVERED |
| DEC-06 | training-script contract documented | docs/training-script-contract.md (253 lines, 6 anchors) | tests/test_phase8_docs_exist.py (8) | DELIVERED |
| DEC-07 | final reproduction sanity (CCRCC + sklearn-iris) | tests/acceptance/test_final_phase8_acceptance.py (3 sub-gates) | sub-gate B PASS in CI; A+C workstation-deferred | DELIVERED (CI portion); workstation A+C pending |

### D-199..D-208 Honoring Map

| Decision | Description | Verification | Status |
|----------|-------------|--------------|--------|
| D-199 | AUTOBENCH purge from _orchestrator_daemon.py | `grep AUTOBENCH_ROOT src/automil/backends/_orchestrator_daemon.py` returns zero functional refs (only line 54 informational comment) | HONORED |
| D-200 | dict-spread `node["metrics"] = dict(metrics)`; framework-owned scalars preserved | graph.py 5 write sites + 3 Pareto sites migrated; bootstrap loader retained per OQ-8 | HONORED |
| D-201 | result.schema.json (Draft 2020-12) + daemon validates at ingest | result.schema.json present (25 lines); daemon line 1078 inline import + validate_result; schema-pointer in error msg | HONORED |
| D-202 | env.required + env.passthrough validators | _validate_env_required at check.py:60; passthrough already wired in daemon (Phase 0 CLN-02 extended) | HONORED |
| D-203 | sklearn-iris second consumer at examples/sklearn-iris/ | 6 files shipped; train.py exactly 80 lines; zero `automil.*` imports | HONORED |
| D-204 | docs/training-script-contract.md | 253 lines; 6 contract items, sklearn-iris cross-link, pytorch skeleton, 2 SIGTERM patterns | HONORED |
| D-205 | final acceptance gate (3 sub-gates A/B/C) | tests/acceptance/test_final_phase8_acceptance.py with @pytest.mark.requires_ccrcc_data on A+C | HONORED |
| D-206 | framework purity grep gate | tests/test_framework_purity.py with 5-entry content-anchor allowlist + line-drift defender | HONORED |
| D-207 | BCK-04 lint extension to schemas/ | schemas/ is pure JSON + thin validator wrapper; no process-control refs | HONORED |
| D-208 | 11-clause acceptance gate | tests/acceptance/test_phase8_acceptance.py: 11 clauses 1:1 with D-208; 11 PASS in 32.35s | HONORED |

### Phase 7 Baseline Regression Check

| Metric | Phase 7 Baseline | Phase 8 Current | Delta | Status |
|--------|-----------------|-----------------|-------|--------|
| Total tests collected | 848+ (per ROADMAP) | 950 (936 excl. pre-existing collection error) | +102 | EXCEEDS D-208 clause 9 floor (≥858) |
| Phase 8 new tests | 0 | 47+ across 9 new files | +47 | EXCEEDS DEC-01..07 ≥10 floor |
| Pre-existing failures | 3 tick_cells (Phase 4 wiring drift) | 4 tick_cells (3 pre-existing + 1 Phase-8-introduced) | +1 | **PARTIAL** -- regression below |
| Pre-existing collection errors | 1 (test_per_fold_writer.py, autobench import) | 1 (same) | 0 | OK -- not Phase 8 caused |
| Phase 8 acceptance gates | N/A | All PASS (D-208 11/11; sub-gate B 1/1; framework purity 3/3) | +15 PASS | OK |

**Identified regression (Phase-8-introduced):** `tests/test_tick_cells.py::test_automil_fold_count_injected_into_subprocess_env` fails with `TypeError: ExperimentOrchestrator._build_subprocess_env() got an unexpected keyword argument 'pythonpath'`. Plan 08-05 dropped `pythonpath` and `worktree_benchmarks` kwargs from the daemon's `_build_subprocess_env` signature (Task 1, commit e98bb1b) but did not migrate this Phase 4 test (commit 0a8ac33) along with its sibling tests in `tests/test_orchestrator_env_whitelist.py` (which were updated in Task 3, commit e443b7a). The test was passing pre-Phase-8 and is now broken; STATE.md follow-ups list documents only the 3 pre-existing tick_cells failures, not this 4th one.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_tick_cells.py` | 477 | TypeError -- test calls `_build_subprocess_env` with removed kwargs | WARNING | Pre-existing test no longer collects-and-passes after Phase 8 daemon refactor; 1 test regression |

No blockers found. The regression above is a documentation/test-fixture gap rather than a goal-blocking architectural break -- the daemon refactor itself is correct (other env-whitelist tests were correctly migrated in plan 08-05 Task 3).

### Human Verification Required

#### 1. Sub-gate A (CCRCC `node_0176` reproduction)

**Test:** Run `uv run pytest tests/acceptance/test_final_phase8_acceptance.py::test_subgate_a_ccrcc_node_0176_reproduction -v` on workstation with `AUTOBENCH_CCRCC_ROOT` set to real CCRCC dataset.
**Expected:** `automil verify-repro node_0176` against `benchmarks/experiments/ccrcc` reads `repro_manifest.yaml`, asserts `|actual - 0.502| < 0.005`. Test PASSES.
**Why human:** Requires AUTOBENCH_CCRCC_ROOT env var pointing at real CCRCC dataset; not available in CI. Test is decorated `@pytest.mark.requires_ccrcc_data` and SKIPS cleanly without env. ROADMAP Phase 8 SC-5 is the final acceptance criterion; CI can only verify the sklearn-iris half (sub-gate B).

#### 2. Sub-gate C (heterogeneous consumers in same project)

**Test:** Both sklearn-iris and CCRCC variants registered side-by-side in same tmp project; run `uv run pytest tests/acceptance/test_final_phase8_acceptance.py::test_subgate_c_heterogeneous_consumers_same_project -v` on workstation.
**Expected:** sklearn-iris (composite >= 0.90) and CCRCC node_0176 (composite +-0.005 of 0.502) both succeed in same project tree; framework supports heterogeneous consumers.
**Why human:** Sub-gate C body is currently `pytest.skip()` (workstation-shape-deferred per 08-09-SUMMARY decision and STATE.md Phase 8 follow-up #1). Leo runs manually on workstation; commits the active body when shape is stable.

#### 3. tick_cells regression triage + v1.0.0 tag decision

**Test:** Decide whether to (a) fix `tests/test_tick_cells.py::test_automil_fold_count_injected_into_subprocess_env` before tagging v1.0.0, or (b) document it in STATE.md Phase 8 follow-ups list alongside the 3 pre-existing tick_cells failures and tag anyway.
**Expected:** Either resolution path is acceptable for v1.0.0 -- the regression is a 1-line test-fixture update (drop `pythonpath`/`worktree_benchmarks` kwargs from the test's `_build_subprocess_env` call) and does not affect framework correctness.
**Why human:** Goal-blocking judgment call; trivial to fix but Leo decides whether v1.0.0 ships with the documented-known-issue tick_cells suite or with a clean tick_cells.py. Recommended: 5-min fix, then tag.

### Gaps Summary

The phase substantially achieves its goal. All 7 DEC requirements ship with code+test pairs. All 10 D-199..D-208 engineering decisions are honored in the codebase. The framework is provably autobench-purged (5 grep matches, all in documented allowlist with content anchors and line-drift defender). The sklearn-iris second consumer plugs in end-to-end through the documented contract; sub-gate B exercises the full orchestrator subprocess path including the daemon ingest schema validation hook. The CHANGELOG 8.0.0 entry documents 3 BREAKING changes with the F-06 4-cell migration matrix. ROADMAP, STATE.md, and REQUIREMENTS.md all mark milestone v1.0 complete with 9 phases shipped and 92 plans executed.

**One Phase-8-introduced regression** (4th tick_cells failure) was found and is not currently documented in STATE.md follow-ups. This is a 1-line test-fixture update (`tests/test_tick_cells.py:477` calls `_build_subprocess_env` with two kwargs that plan 08-05 correctly removed from the daemon signature). The regression does not affect framework correctness or any acceptance gate; it is a hygiene gap surfaced by goal-backward verification.

**CCRCC-data-gated sub-gates A and C** require Leo's workstation review; sub-gate B (the CI-runnable half) is green.

## Recommended Next Action

**Verdict: human_needed**

Two distinct human-verification items, both required before v1.0.0 tag:

1. **Run `/gsd-verify-work 8` on Leo's workstation** with `AUTOBENCH_CCRCC_ROOT` set, to validate sub-gates A and C (CCRCC reproduction + heterogeneous-consumers-in-one-project). This is the workstation half of D-205 / DEC-07 final acceptance.

2. **Resolve the tick_cells regression** -- recommended 5-minute fix in `tests/test_tick_cells.py:477` to drop `pythonpath` and `worktree_benchmarks` kwargs from the `_build_subprocess_env` call, mirroring the migration plan 08-05 Task 3 applied to `tests/test_orchestrator_env_whitelist.py`. Alternatively, document as Phase 8 follow-up #6 in STATE.md.

After both items resolve, proceed to milestone audit (`/gsd-milestone-audit`) -> milestone complete (`/gsd-milestone-complete`) -> tag `v1.0.0`.

The CI half of Phase 8 (D-208 11-clause aggregator + framework purity + sub-gate B + 47 new tests) is unconditionally PASS. Phase 8's structural deliverables are complete.

---

_Verified: 2026-05-08T04:10:00Z_
_Verifier: Claude (gsd-verifier, opus-4-7-1m)_
_Verification mode: goal-backward + milestone-acceptance audit_
