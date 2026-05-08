# Phase 8 Plan Summary, Decoupling completion + final acceptance

**Generated:** 2026-05-07
**Phase:** 08-decoupling-completion-acceptance
**Total plans:** 10
**Total waves:** 4 (1-indexed)
**Requirements:** DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07
**Source artifacts:** 08-CONTEXT.md (D-199..D-208), 08-RESEARCH.md (9 OQs + Pitfall 7 + Migration Delta), 08-PATTERNS.md (9 analog rows)

---

## Wave Map

| Wave | Plans (parallel within wave) | Theme | File-disjointness |
|------|------------------------------|-------|-------------------|
| **Wave 1** | `08-01` ‖ `08-02` ‖ `08-03` | Foundation refactors: schemas package + graph.py dict-spread + viz reader migration | `src/automil/schemas/` vs `src/automil/graph.py` vs `src/automil/viz/static/app.js`, disjoint OK |
| **Wave 2** | `08-04` ‖ `08-05` | Validators + AUTOBENCH purge: env.required + daemon-side schema validation + AUTOBENCH purge | `src/automil/cli/check.py` + `templates/config.yaml.j2` vs `src/automil/backends/_orchestrator_daemon.py` + `tests/test_orchestrator_env_whitelist.py`, disjoint OK |
| **Wave 3** | `08-06` ‖ `08-07` ‖ `08-08` | Second consumer + contract doc + framework purity gate | `examples/sklearn-iris/` vs `docs/training-script-contract.md` vs `tests/test_framework_purity.py`, disjoint OK |
| **Wave 4** | `08-09` -> `08-10` | Final acceptance gate (sequential): sub-gates + 11-clause aggregator + CHANGELOG + STATE/ROADMAP completion | `tests/acceptance/test_final_phase8_acceptance.py` + `pyproject.toml` (08-09) -> `tests/acceptance/test_phase8_acceptance.py` + `CHANGELOG.md` + `.planning/STATE.md` + `.planning/ROADMAP.md` (08-10), sequential |

**Parallel pairs file-disjointness audit (per execute-phase wave-execution model):**

- Wave 1 (`08-01` vs `08-02` vs `08-03`):
  - 08-01 owns: `src/automil/schemas/__init__.py`, `src/automil/schemas/_result.py`, `src/automil/schemas/result.schema.json`, `tests/test_result_schema_validation.py`
  - 08-02 owns: `src/automil/graph.py`, `tests/test_graph_dict_spread.py`
  - 08-03 owns: `src/automil/viz/static/app.js`, `tests/viz/test_app_js_metrics_reader.py`, `tests/viz/__init__.py`
  - Verdict: file-disjoint OK
- Wave 2 (`08-04` vs `08-05`):
  - 08-04 owns: `src/automil/cli/check.py`, `src/automil/templates/config.yaml.j2`, `tests/cli/test_check_env_required.py`
  - 08-05 owns: `src/automil/backends/_orchestrator_daemon.py`, `tests/test_orchestrator_env_whitelist.py`, `tests/backends/test_daemon_result_schema_validation.py`
  - Verdict: file-disjoint OK
- Wave 3 (`08-06` vs `08-07` vs `08-08`):
  - 08-06 owns: `examples/sklearn-iris/` (6 files)
  - 08-07 owns: `docs/training-script-contract.md`, `tests/test_phase8_docs_exist.py`
  - 08-08 owns: `tests/test_framework_purity.py`
  - Verdict: file-disjoint OK
- Wave 4 sequential (`08-09` then `08-10`):
  - 08-09 owns: `tests/acceptance/__init__.py`, `tests/acceptance/conftest.py`, `tests/acceptance/test_final_phase8_acceptance.py`, `pyproject.toml`
  - 08-10 owns: `tests/acceptance/test_phase8_acceptance.py`, `CHANGELOG.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`
  - Verdict: file-disjoint, but 08-10 invokes 08-09's test via subprocess and the D-208 aggregator depends on 08-09's marker + fixtures landing first; sequential ordering required.

**Sequential dependencies:**

- `08-05` depends_on `08-01` (uses `from automil.schemas import validate_result, ValidationError`).
- `08-06` depends_on `08-01` (result.json shape validates against schemas/result.schema.json; train.py does NOT import the validator at runtime, but its output must validate).
- `08-07` depends_on `08-01` (doc cross-links result.schema.json file path).
- `08-08` depends_on `08-04` AND `08-05` (allowlist line numbers post-AUTOBENCH purge; coordination with config.yaml.j2 inline-example comment if retained).
- `08-09` depends_on all of 08-01..08-08 (sub-gate B copies examples/sklearn-iris/, validates result.json schema, exercises end-to-end).
- `08-10` depends_on all of 08-01..08-09 (D-208 11-clause aggregator subprocess-invokes the prior test files; CHANGELOG entry references all DEC requirements; STATE/ROADMAP marked complete only after gate green).

---

## Plan-by-Plan Files Modified

| Plan | Wave | Files | Requirements | Lines (approx body) |
|------|------|-------|--------------|---------------------|
| `08-01-PLAN.md` | 1 | `src/automil/schemas/__init__.py`, `src/automil/schemas/_result.py`, `src/automil/schemas/result.schema.json`, `tests/test_result_schema_validation.py` | DEC-03 | ~140 |
| `08-02-PLAN.md` | 1 | `src/automil/graph.py`, `tests/test_graph_dict_spread.py` | DEC-04 | ~250 |
| `08-03-PLAN.md` | 1 | `src/automil/viz/static/app.js`, `tests/viz/test_app_js_metrics_reader.py`, `tests/viz/__init__.py` | DEC-04 | ~80 |
| `08-04-PLAN.md` | 2 | `src/automil/cli/check.py`, `src/automil/templates/config.yaml.j2`, `tests/cli/test_check_env_required.py` | DEC-05 | ~190 |
| `08-05-PLAN.md` | 2 | `src/automil/backends/_orchestrator_daemon.py`, `tests/test_orchestrator_env_whitelist.py`, `tests/backends/test_daemon_result_schema_validation.py` | DEC-01, DEC-03 | ~280 |
| `08-06-PLAN.md` | 3 | `examples/sklearn-iris/train.py`, `examples/sklearn-iris/automil/config.yaml`, `examples/sklearn-iris/automil/program.md`, `examples/sklearn-iris/automil/variants/classifier_v0/__init__.py`, `examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py`, `examples/sklearn-iris/README.md` | DEC-02 | ~240 |
| `08-07-PLAN.md` | 3 | `docs/training-script-contract.md`, `tests/test_phase8_docs_exist.py` | DEC-06 | ~190 |
| `08-08-PLAN.md` | 3 | `tests/test_framework_purity.py` | DEC-01 | ~140 |
| `08-09-PLAN.md` | 4 | `tests/acceptance/__init__.py`, `tests/acceptance/conftest.py`, `tests/acceptance/test_final_phase8_acceptance.py`, `pyproject.toml` | DEC-02, DEC-07 | ~270 |
| `08-10-PLAN.md` | 4 | `tests/acceptance/test_phase8_acceptance.py`, `CHANGELOG.md`, `.planning/STATE.md`, `.planning/ROADMAP.md` | DEC-01..07 (all) | ~380 |

**File-disjointness across the entire phase:** every modified path appears in at most ONE plan's `files_modified` frontmatter. The only exception is plans that read from but do not write to a shared file (e.g. 08-08's allowlist references content that 08-04 may have placed in `config.yaml.j2`; the line-number coordination is a runtime check, not a write conflict).

---

## DEC Requirement Coverage

Every Phase 8 DEC requirement is mapped to >=1 plan via the `requirements:` frontmatter:

| Req ID | Description | Primary Plan(s) | Verification Plan |
|--------|-------------|-----------------|--------------------|
| DEC-01 | zero autobench refs in src/automil/ | 08-05 (purge), 08-08 (CI gate) | 08-10 clause 1 + clause 7 |
| DEC-02 | sklearn-iris second consumer end-to-end | 08-06 (consumer), 08-09 (acceptance sub-gate B) | 08-10 clause 5 + clause 8 |
| DEC-03 | result.json JSON-Schema-validated | 08-01 (schema + validator), 08-05 (daemon ingest hook) | 08-10 clause 2 |
| DEC-04 | composite scoring config-driven | 08-02 (graph dict-spread), 08-03 (viz reader) | 08-10 clause 3 |
| DEC-05 | env.required validated by automil check | 08-04 (validator + template) | 08-10 clause 4 |
| DEC-06 | training-script contract documented | 08-07 (docs) | 08-10 clause 6 |
| DEC-07 | final reproduction sanity (CCRCC + sklearn-iris) | 08-09 (3 sub-gates) | 08-10 clause 8 |

---

## D-208 11-Clause Acceptance Gate Cross-Reference

The 11-clause D-208 ship checklist (CONTEXT.md `<decisions>` § D-208) maps to plan satisfaction:

| Clause | Description | Satisfied by | Verified by |
|--------|-------------|--------------|-------------|
| 1 | zero autobench/AUTOBENCH_/benchmarks/ in src/automil/ (allowlisted) | 08-05 (purge), 08-08 (gate) | 08-10 clause 1 (subprocess-invokes 08-08) |
| 2 | result.schema.json exists; daemon validates at ingest | 08-01, 08-05 | 08-10 clause 2 (schema dict + daemon source grep + 08-01 tests) |
| 3 | graph.py dict-spread storage; framework-owned scalars preserved | 08-02 | 08-10 clause 3 (graph source grep + 08-02 tests) |
| 4 | env.required validator + env.passthrough; config.yaml.j2 extended | 08-04 | 08-10 clause 4 (check.py + template grep + 08-04 tests) |
| 5 | examples/sklearn-iris/ exists with train.py + scaffolding | 08-06 | 08-10 clause 5 (path checks + decoupled-imports check) |
| 6 | docs/training-script-contract.md covers 6 contract items | 08-07 | 08-10 clause 6 (subprocess-invokes 08-07's docs-exist test) |
| 7 | tests/test_framework_purity.py PASSES with hardcoded allowlist | 08-08 | 08-10 clause 7 (subprocess-invokes 08-08) |
| 8 | tests/acceptance/test_final_phase8_acceptance.py sub-gate B PASSES; A+C skip cleanly | 08-09 | 08-10 clause 8 (subprocess-invokes 08-09 sub-gate B) |
| 9 | Phase 7 baseline 838+ preserved; >=10 new tests added | All Wave 1-3 plans add tests | 08-10 clause 9 (collect-only test count >=858) |
| 10 | CHANGELOG entry at 8.0.0 (BREAKING) | 08-10 (Task 2) | 08-10 clause 10 (CHANGELOG grep) |
| 11 | ROADMAP + STATE updated to Phase 8 + milestone v1.0 complete | 08-10 (Tasks 3+4) | 08-10 clause 11 (STATE.md + ROADMAP.md grep) |

D-208 has 11 clauses. The single verifying test file is `tests/acceptance/test_phase8_acceptance.py` (created by plan 08-10) per Phase 6 D-179 and Phase 7 D-198 precedent.

---

## Migration Delta Cross-Reference (graph.py reader-site assignments per OQ-9)

Per RESEARCH OQ-9 + Migration Delta Punch List, the graph.py named-field reader migration is split across plans as follows:

| Site | File:Lines | Action | Plan |
|------|------------|--------|------|
| add_executed write site | graph.py:122-145 | replace named-field copy with `"metrics": dict(metrics)` | 08-02 |
| promote write site | graph.py:205-219 | replace named-field copy with `node["metrics"] = dict(metrics)` | 08-02 |
| reconcile completion ingest | graph.py:559-571 | dict-spread metrics dict into add_executed/promote input | 08-02 |
| archive recovery loop A | graph.py:607-630 | replace named-field copies with `dict(comp_metrics)` | 08-02 |
| archive recovery loop B | graph.py:670-705 | replace named-field copies with `dict(r_metrics)` | 08-02 |
| results.tsv bootstrap loader | graph.py:779-810 | KEEP for backwards-compat; metrics dict carries 4-key shape into add_executed | 08-02 |
| `_reevaluate_descendants` Pareto | graph.py:254-270 | OQ-9 Option B: composite-only dominance | 08-02 |
| reconcile Pareto | graph.py:547-552 | OQ-9 Option B: composite-only dominance | 08-02 |
| archive-recovery Pareto | graph.py:676-681 | OQ-9 Option B: composite-only dominance | 08-02 |
| viz/static/app.js metric reader | viz/static/app.js:227-237 | `node[key]` -> `(node.metrics || {})[key]` | 08-03 |
| `_orchestrator_daemon.py:1055` cap-killed reconcile | (per OQ-7) | dict-spread payload metrics into gnode | NOT migrated this phase, deferred per OQ-8 |
| `_orchestrator_daemon.py:1289-1298` results.tsv writer | autobench-shaped | KEEP (per OQ-8 deferred decision) | NOT migrated this phase |

All 9 graph.py migration sites + 1 viz site are owned by plans 08-02 and 08-03. The 2 deferred daemon sites are explicitly out-of-scope per CONTEXT D-200 deferred section.

---

## API Corrections Applied (RESEARCH.md OQ resolutions inline in plan bodies)

The planner integrated all RESEARCH.md OQ resolutions and Pitfall corrections directly into wave-1+ plan bodies, NOT deferred to executors:

| Correction | Source | Locked Decision | Plan(s) where applied |
|------------|--------|-----------------|----------------------|
| `Draft202012Validator` (NOT `jsonschema.validate(...)`) for repeated-validation perf | OQ-2 lines 204-249 | D-201 / OQ-2 | 08-01 (validator construction) |
| Validate at daemon ingest path (NOT graph.py recovery loop) for v1; recovery loop validation deferred | OQ-1 lines 161-201 | D-201 / OQ-1 | 08-05 (daemon insertion site) |
| `_validate_env_required` returns list (NOT raises typed exception); per-name iteration in caller produces one issue per missing var | OQ-3 lines 252-301 | D-202 / OQ-3 | 08-04 (validator return shape + caller iteration) |
| Sklearn-iris uses inline `signal.signal` (NOT `register_sigterm_flush` which assumes per-fold files); idempotent late-SIGTERM-after-completion | OQ-4 lines 304-408 | D-203 / OQ-4 | 08-06 (train.py SIGTERM handler) |
| `requires_ccrcc_data` marker + `ccrcc_data_root` fixture; CI runs `not requires_ccrcc_data and not requires_slurm and not requires_ray` | OQ-5 lines 410-475 | D-205 / OQ-5 | 08-09 (marker + conftest fixture) |
| Subprocess-grep + content-anchor allowlist (NOT in-process rglob) for line-drift detection | OQ-6 lines 478-578 | D-206 / OQ-6 | 08-08 (allowlist with content anchors) |
| viz reader: single-line change `(node.metrics || {})[pair[0]]` (NOT full dashboard rewrite); generic-metric rendering deferred | OQ-7 lines 580-622 | D-200 deferred | 08-03 (single-line change in app.js) |
| results.tsv writer KEEPS autobench-shaped 4-key columns; sklearn-iris writes 0.0 for absent keys (correct degenerate behavior) | OQ-8 lines 624-666 | D-200 deferred | NOT migrated; documented in 08-02 frontmatter `must_haves` and 08-PLAN-SUMMARY `Migration Delta` |
| Pareto dominance: OQ-9 Option B (composite-only) chosen for v1.0 over Option A (4-key with helper) | OQ-9 lines 668-731 | D-200 / planner discretion | 08-02 (3 Pareto sites) |
| jsonschema is transitive (no new top-level dep); Phase 5 lockfile confirms 4.26.0 | External Deps lines 906-928 | D-201 + RESEARCH | 08-01 (no pyproject edits) |
| Sklearn already in `[ml]` extra; `[examples-iris]` recommended but not required | External Deps + Open Q #2 | RESEARCH discretion | NOT shipped (kept simple; sklearn-iris users install via `[ml]` or directly) |

**Phase-6 / Phase-7 precedent:** all RESEARCH OQ resolutions are pre-applied at plan-writing time, not deferred to executor agents. Executors implement against the resolved API; checker agents verify; no second pass needed.

---

## Dependency Graph

```
08-01 (W1: schemas package + validator) ────┐
08-02 (W1: graph.py dict-spread) ────────────┤  (Wave 1, file-disjoint)
08-03 (W1: viz reader migration) ────────────┤
                                             │
08-04 (W2: env.required validator) ──────────┼──┐
08-05 (W2: AUTOBENCH purge + daemon validate)┘  │  (W2 depends on W1 for schemas import)
                                                │
                          ┌─────────────────────┘
                          │
08-06 (W3: sklearn-iris consumer) ───┐
08-07 (W3: contract doc) ────────────┤  (Wave 3, file-disjoint, depends on W1+W2)
08-08 (W3: framework purity gate) ───┘  (depends on 08-04 + 08-05 for allowlist coordination)
                          │
                          ▼
08-09 (W4: 3 sub-gates + marker) ──────►  08-10 (W4: 11-clause aggregator + CHANGELOG + STATE/ROADMAP)
                                          (Wave 4 sequential; 08-10 ships milestone v1.0 acceptance)
```

---

## Estimated Wall-Clock Cadence

- **Wave 1** (parallel ‖‖): ~50 min wall, 08-01 (schema + 8 tests, ~25 min) ‖ 08-02 (graph.py refactor + 6 tests, the heavy plan, ~50 min) ‖ 08-03 (1-line viz + 3 tests, ~15 min)
- **Wave 2** (parallel ‖): ~45 min wall, 08-04 (helper + template + 8 tests, ~30 min) ‖ 08-05 (AUTOBENCH purge + ingest validate + test conversion + 6 tests, the load-bearing decoupling commit, ~45 min)
- **Wave 3** (parallel ‖‖): ~40 min wall, 08-06 (6 consumer files + smoke test, ~30 min) ‖ 08-07 (~150-line doc + 8 tests, ~30 min) ‖ 08-08 (3 tests, ~15 min)
- **Wave 4** (sequential): ~50 min, 08-09 (3 sub-gate tests + conftest + marker, ~25 min) -> 08-10 (11-clause aggregator + CHANGELOG + STATE + ROADMAP, ~30 min)
- **Total estimated wall-clock:** ~3.0 hours of focused execution (Phase 7 was ~3.5h with 12 plans; Phase 8 has 10 plans with similar size).
- **Wave-execute parallelism savings:** ~40% (3 of 4 waves run multiple plans in parallel).

---

## Test Count Trajectory

| Stage | Test count | Delta | Cumulative |
|-------|-----------|-------|------------|
| Phase 7 close baseline | 848+ | , | 848+ |
| 08-01 (test_result_schema_validation: 8 tests) | +8 | 856 | 856 |
| 08-02 (test_graph_dict_spread: 6 tests) | +6 | 862 | 862 |
| 08-03 (test_app_js_metrics_reader: 3 tests) | +3 | 865 | 865 |
| 08-04 (test_check_env_required: 8 tests) | +8 | 873 | 873 |
| 08-05 (test_daemon_result_schema_validation: 6 tests) | +6 | 879 | 879 |
| 08-07 (test_phase8_docs_exist: 8 tests) | +8 | 887 | 887 |
| 08-08 (test_framework_purity: 3 tests) | +3 | 890 | 890 |
| 08-09 (test_final_phase8_acceptance: 3 sub-gates, 2 may skip) | +3 | 893 | 893 |
| 08-10 (test_phase8_acceptance: 11 clauses) | +11 | 904 | 904 |
| **Phase 8 close target** |  | **+56** | **>=858 (D-208 clause 9 floor)** |

D-208 clause 9 requires ">=10 new tests for DEC-01..07"; Phase 8 ships ~56 across 9 new test files. The 858 floor is conservative; actual test count after Phase 8 is ~904.

---

## Plan Quality Self-Audit

**Format compliance:**

- [x] All 10 plans have valid YAML frontmatter (`wave`, `depends_on`, `files_modified`, `autonomous`, `requirements`).
- [x] All 10 plans declare at least one DEC requirement; every DEC requirement (DEC-01..07) is mapped to >=1 plan.
- [x] All tasks include `<read_first>` citing analog files from PATTERNS.md + the file being modified + the locked-decision document.
- [x] All tasks include `<acceptance_criteria>` with grep-verifiable bash one-liners; literal `&&`, `>` (no HTML entities).
- [x] All `<action>` blocks contain concrete values (no "align X with Y" without specifics); locked error message strings, locked anchor substrings, exact line numbers.
- [x] Wave assignments respect file-disjointness for parallel execution (verified above).
- [x] File naming `08-NN-PLAN.md`; 10 files written.
- [x] Wave numbers 1-indexed (Wave 1, 2, 3, 4); NOT 0-indexed (Phase 6 had this bug).

**Anti-shallow execution defenses:**

- [x] API corrections applied inline (NOT deferred to executors): see "API Corrections Applied" table.
- [x] Memory-aligned patterns enforced: atomic-write rollback uses `path.unlink` (NEVER `git checkout` per `feedback_never_blind_checkout`); framework purity grep gates everywhere; BCK-04 lint clean (no new process-control refs in any new file).
- [x] No em or en dashes anywhere in plan artifacts (per `feedback_no_em_dashes`); each plan body's "Critical, no em-dashes" check enforces inline; em-dash gate `grep -nP U+2014U+2013 .planning/phases/08-*/*-PLAN.md` returns zero matches across all 10 plans (verified post-write; the 08-07 case used U+2014/U+2013 Unicode escapes inside the test code that asserts the absence).
- [x] D-208 11-clause acceptance gate cross-referenced; single test file (08-10) verifies all 11 clauses programmatically per Phase 6 D-179 / Phase 7 D-198 precedent.
- [x] Decision-ID traceability: every locked decision (D-199..D-208) is referenced in at least one plan body action block.
- [x] Resolved RESEARCH.md OQ-1..OQ-9 during planning (not deferred): inline in plan bodies + cross-referenced in API Corrections table.
- [x] Framework-purity-grep-gate coordination between 08-04 (config.yaml.j2 inline AUTOBENCH example comment) and 08-08 (allowlist) explicitly noted in both plans.

**Framework purity verification:**

```bash
# Run after all 10 plans land:
grep -rnE "autobench|AUTOBENCH_|benchmarks/" \
  src/automil/schemas/ \
  src/automil/graph.py \
  src/automil/viz/static/app.js \
  src/automil/cli/check.py \
  src/automil/templates/config.yaml.j2 \
  src/automil/backends/_orchestrator_daemon.py
# Expected: 1-3 hits (only allowlisted comments per plan 08-08's allowlist)
```

**Em-dash gate verification:**

```bash
grep -nP "\u2014|\u2013" .planning/phases/08-decoupling-completion-acceptance/*-PLAN.md
# Expected: zero matches across all 10 plan files (verified post-write).
```

**Ready for plan-checker iteration 1.**

---

## Iter-2 fixes applied (F-01..F-09; from 08-PLAN-CHECK.md)

Following plan-checker iteration 1 (RETRY verdict: 3 BLOCKER + 5 HIGH), the following surgical patches were applied inline. No plan was regenerated; only affected sections were edited.

| Finding | Severity | Plan(s) patched | Fix summary |
|---------|----------|-----------------|-------------|
| F-01 | BLOCKER | 08-08 | `_ALLOWLIST` extended with 3rd entry: `src/automil/cli/lifecycle/revert_baseline.py:87` content-substring `'benchmarks/lib/CLAM/**'` (registry.protected default-help string; allowlist by intent). Plan 08-08 must_haves + interfaces + Step A + Task 1 done criterion all updated. |
| F-02 | BLOCKER | 08-05 | Task 3 expanded with explicit Step E: DELETE `tests/test_orchestrator_env_whitelist.py:166-170` `test_pythonpath_overrides_whitelist_value`. Step F adds replacement `test_pythonpath_not_auto_injected_phase8` so test count net-preserves. Verify command updated to grep both presence (new test) and absence (deleted test). |
| F-03 | BLOCKER | 08-05 | New Task 5 added: migrate `_orchestrator_daemon.py:1055-1057` cap-killed reconcile branch from per-key copy of `(test_auc, test_bacc, val_auc, val_bacc)` to single dict-spread `gnode["metrics"] = dict(payload.get("metrics", {}))`. Framework-owned scalars (composite/type/status) preserved at top level. Post-edit grep confirms zero `gnode["test_auc"]`-style writes. |
| F-04 | HIGH | 08-09 | Sub-gate B body rewritten to drive the FULL orchestrator path: `automil init` + `automil submit` + `automil orchestrator start` Popen + bounded poll for graph terminal state + SIGTERM teardown. Schema validation now exercised end-to-end via daemon ingest hook (08-05) at integration level, not just standalone. |
| F-05 | HIGH | 08-04 | Task 3 test list extended with `test_env_required_non_list_warns_and_skips_validation`: invokes `automil check` via CliRunner against a malformed config (string-shaped env.required); asserts operator-visible warning emission + no crash + no spurious "Missing required env var" issue. |
| F-06 | HIGH | 08-04 + 08-10 | 08-04: dropped the inline `# e.g. for an autobench consumer:` example from `config.yaml.j2` (template stays framework-pure; allowlist size in 08-08 stays at 3 entries). 08-10: CHANGELOG migration note now resolves the 4-cell matrix (env.required vs env.passthrough × example values vs sentinel) explicitly with concrete autobench-shaped recovery snippet (AUTOBENCH_OVARIAN_ROOT + AUTOBENCH_CCRCC_ROOT in both lists). |
| F-07 | HIGH | 08-04 | Task 2 extended: `config.yaml.j2` gains a top-level `scoring:` block with `formula: ""` default and documentation-only comment block. DEC-04 ROADMAP success criterion 3 names `automil/config.yaml: scoring.formula` verbatim; F-07 surfaces the field in fresh `automil init` outputs. Task 3 adds `test_template_has_scoring_block` regression-prevention test. Plan adds DEC-04 to its requirements list (now `[DEC-04, DEC-05]`). |
| F-08 | HIGH | 08-09 | Sub-gate A path probe corrected from the wrong `ccrcc_data_root.parent / "ccrcc"` (assumed AUTOBENCH_CCRCC_ROOT was a project root) to deterministic `_REPO_ROOT / "benchmarks" / "experiments" / "ccrcc"` per CLAUDE.md monorepo layout (verified on Leo's workstation: `benchmarks/experiments/ccrcc/automil/config.yaml` exists). Sub-gate A no longer always-skips silently. |
| F-09 | MEDIUM | 08-10 | Clause 11 (`test_d208_clause_11_state_roadmap_complete`) replaced with deterministic content checks: (a) CHANGELOG.md head section first `## ` heading is `## 8.0.0` AND contains F-06 migration snippet text (AUTOBENCH_OVARIAN_ROOT + AUTOBENCH_CCRCC_ROOT + passthrough), (b) REQUIREMENTS.md has DEC-01..DEC-07 marked Complete (NOT Pending). Removes circular self-reference (clause was asserting ROADMAP/STATE updates that the same plan performs). |

**Bundled sub-fixes (folded into the same revision pass):**
- F-12 (MEDIUM, 08-09): `ccrcc_data_root` fixture in `tests/acceptance/conftest.py` drops the `splits/` subdirectory check (liberal fixture; sub-gate A owns the shape probe via F-08 fix).
- F-10 (MEDIUM, 08-10): `.planning/REQUIREMENTS.md` added to plan 08-10 `files_modified`; Task 4 step C explicitly transitions DEC-01..DEC-07 traceability rows from Pending to Complete (the F-09 anchor depends on this).
- F-14 (LOW, 08-10): Task 3 step A resolves actual plan count via `find .planning/phases -name "*-PLAN.md" | wc -l` at execution time; STATE.md frontmatter uses the resolved integer (NOT placeholder `92`).

**Wave map impact:** No wave shifts. The Iter-2 patches add 1 new task (08-05 Task 5: F-03 cap-killed migration) and expand existing tasks; no new plans, no file-disjointness regressions, no new dependencies introduced. Wave-2 cadence absorbs the F-03 task (~5 minutes of executor work; 08-05 estimate stays ~45 min wall).

**Files modified delta from Iter-1 to Iter-2:**
- 08-04: requirements changed `[DEC-05]` -> `[DEC-04, DEC-05]` (F-07 adds DEC-04 surface).
- 08-10: `files_modified` adds `.planning/REQUIREMENTS.md` (F-10).

**Em-dash audit (post-Iter-2):**

Audit by Unicode codepoint (U+2014 em-dash, U+2013 en-dash). The verification command uses Python regex unicode escapes so the audit text itself does NOT contain literal dashes:

```bash
grep -nP "\x{2014}|\x{2013}" .planning/phases/08-decoupling-completion-acceptance/*.md
# Expected: zero matches across all 10 plan files + CONTEXT + RESEARCH + PATTERNS + PLAN-SUMMARY (verified post-Iter-2 patch).
```

**Test-count trajectory (post-Iter-2):** F-02 net-preserves test count (delete one, add one); F-03 adds zero new tests (regression gate is grep-based); F-05 + F-07 add 2 new tests (08-04: 8 -> 9 tests... wait, actually F-05 and F-07 add 1 test each so 8 -> 10... but the 7th already existed); the actual updated count is 9 tests in 08-04 per the patched done criteria. Phase 8 close target stays >=858 (D-208 clause 9 floor); revised cumulative target ~905-906 (was ~904).

**Ready for plan-checker iteration 2.**
</content>
