# Phase 7 Plan Check, Iteration 1

**Reviewed:** 2026-05-07
**Phase:** 07-hardware-autodetect-automil-setup-skill
**Reviewer:** plan-checker (goal-backward audit, FORCE stance)
**Plans audited:** 11 (07-01 through 07-11)
**Source artifacts read:** 07-CONTEXT.md, 07-RESEARCH.md (partial 1-350), 07-PATTERNS.md, 07-PLAN-SUMMARY.md, REQUIREMENTS.md, ROADMAP.md, src/automil/{backends/base.py, backends/_orchestrator_daemon.py, cli/init.py, cli/submit.py, cli/check.py, agent_assets/_overlay.py}, plus directory listings for tests/cli, tests/skills, tests/agent_assets, src/automil/agent_assets/codex.

---

## 1. Verdict

**RETRY** (1 BLOCKER + 4 HIGH + 3 MEDIUM + 2 LOW; surgical fixes required before execute).

The plans are well-structured, decision-traceable, and substantially correct. Wave layout is honest and file-disjoint. The single BLOCKER is a NameError-grade ordering bug in plan 07-09. The HIGH list catches reality drifts where the plan claims orchestrator behaviour that does not exist in source, plus a CHANGELOG bracket-format ambiguity, plus a clause-9 self-skip that effectively shorts out part of D-198, plus a contract-test extension that is in PATTERNS.md but absent from any plan body.

This is NOT a fundamental rework; the planner can patch all 5 BLOCKER+HIGH findings in one targeted revision pass.

---

## 2. Findings by Severity

| Severity | Count | What it means |
|----------|-------|---------------|
| **BLOCKER** | 1 | Plan WILL fail when executed; must fix before kickoff. |
| **HIGH** | 4 | Plan is likely to deviate or short out a D-198 clause; should fix. |
| **MEDIUM** | 3 | Correctness risk; nice to fix in same revision. |
| **LOW** | 2 | Style/clarity; ship as-is acceptable. |

| ID | Plan | Severity | One-line description |
|----|------|----------|----------------------|
| F-01 | 07-09 | BLOCKER | `_orchestrator_supports_one_shot` referenced in `@pytest.mark.skipif` decorators before its function definition in the literal source order shown. |
| F-02 | 07-09 | HIGH | `ExperimentOrchestrator` has neither `_process_queue_once` nor `_tick_once`; the helper returns False unconditionally so all 3 dry-run gate tests SKIP, leaving STP-06 without automated coverage at execute time. |
| F-03 | 07-11 | HIGH | Acceptance clause 9 (`automil check` on workstation) is wired to `pytest.skip` when `automil/config.yaml` is absent at repo root; on this repo it WILL skip, so D-198 clause 9 is verified as "skipped", not "passed". |
| F-04 | 07-11 | HIGH | CHANGELOG entry instruction asserts `[7.0.0]` bracket format AND clause-8 test allows either; existing CHANGELOG.md format MUST be inspected first to lock one shape, otherwise revision drift across executors is likely. |
| F-05 | 07-04 | HIGH | Backend contract test (`tests/backends/test_contract.py`) parametrised across all backends per Phase 6, but NO Phase 7 plan extends that file with a `test_healthcheck_returns_health_report` parametrised case despite PATTERNS.md §"tests/backends/test_contract.py (extend)" mapping it as exact-match work. Plan 07-04 ships a separate `test_distributed_healthcheck_deferred.py` only. |
| F-06 | 07-09 | MEDIUM | `_run_gate` helper invokes `automil submit` via CliRunner inside a `_os.chdir` block; this competes with the `monkeypatch.chdir(tmp_git_repo)` at test scope and can leak cwd state when assertions raise. |
| F-07 | 07-05 | MEDIUM | Helper `_stamp_healthcheck_defaults` reads `<automil_dir>/results.tsv`, but `automil_dir` may not exist at first-init time (it's about to be created by the scaffold block); plan instructions place the helper call BEFORE the scaffold runs, so `results_tsv.exists()` returns False on every fresh init even on repos that have a sibling `automil/results.tsv` from a prior re-init. The empirical-VRAM path then never fires for `--update`, contradicting Pitfall 8 mitigation #2. |
| F-08 | 07-02 | MEDIUM | Test `_init_minimal_project` fakes a config.yaml that omits the `cap.default_vram_estimate_gb` key; `automil submit` may pass on this stub today but Phase 7 wave 4 (07-05) adds new required cap keys; the wave-1 tests will silently regress when wave-4 lands unless the stub config includes the new keys. Cross-wave config-drift risk. |
| F-09 | All | LOW | Em-dash audit: 0 em-dashes in any of the 11 plans, in CONTEXT, RESEARCH, or PLAN-SUMMARY. Pre-existing em-dashes survive in `src/automil/backends/base.py` (6) and `07-PATTERNS.md` (34); no plan touches the existing base.py docstrings to remove them, which is fine (out of scope). |
| F-10 | 07-07 | LOW | Plan claims init.py codex branch may already strip `---`; instructs executor to "Re-read init.py lines 145-167" and conditionally edit. The conditional-edit instruction is correct but sub-optimal: deterministic plans pre-resolve such conditions during planning, not at execute time. Recommend: planner verifies actual init.py codex branch behaviour and removes the conditional. |

---

## 3. Per-Finding Details

### F-01 , BLOCKER, plan 07-09 task 1, line 213-272 of plan body

**Description:** The plan's rendered code block places three `@pytest.mark.skipif(not _orchestrator_supports_one_shot(), ...)` decorators on tests at plan-body lines 213-251, then defines the helper function `_orchestrator_supports_one_shot` at plan-body lines 257-271. In Python, decorator argument expressions are evaluated **at function-definition time**, top-to-bottom in module load order. If the executor follows the literal code blocks as ordered, the import will raise `NameError: name '_orchestrator_supports_one_shot' is not defined` and the test file will fail to load.

The plan's prose at line 273-274 ("Place it BEFORE the test functions but AFTER the imports") instructs the correct ordering, but the code-block ordering inside the action block is the load-bearing instruction; the executor can reasonably read either as authoritative. Phase 6 had a similar load-order incident.

**Suggested fix:** In plan 07-09 task 1 action body, reorder the two code blocks: helper first, decorated tests second. Drop the trailing "Place it BEFORE..." prose (it then becomes redundant). This is a 30-second edit.

**Severity rationale:** The plan as currently written is one literal-execution-order miss away from a hard ImportError at pytest collection time, which would break Wave 6 entirely (07-09 cannot pass) and cascade into Wave 7 (07-11 clause 6 subprocess invocation reports non-zero).

---

### F-02 , HIGH, plan 07-09 task 1

**Description:** `_orchestrator_supports_one_shot()` checks for `_process_queue_once` or `_tick_once` on `ExperimentOrchestrator`. Source verification (`grep -n "^    def " src/automil/backends/_orchestrator_daemon.py`) shows neither method exists. The class has `_tick_cells`, `_check_running`, `_handle_completion` and others, but no `_process_queue_once` nor `_tick_once`. Therefore the helper returns False unconditionally; all 3 dry-run gate tests skip on every run.

The plan acknowledges this with "Either all PASS or all SKIP cleanly" but then 07-11 clause 6 accepts `returncode in {0, 5}` (5 = no tests collected/run), so a permanent SKIP also passes the acceptance gate. Net effect: STP-06's automated test coverage at execute-time is exactly zero; only the SKILL.md narrative (LLM-driven content, not testable) covers it.

**Suggested fix (one of):**
- (a) Plan 07-09 should include a Wave-1 or Wave-2 plan task that adds a synchronous `_process_queue_once` entry point on `ExperimentOrchestrator` with a documented contract.
- (b) Re-architect 07-09 to use `automil orchestrator start` in the background with a 90s wall-clock and `automil orchestrator stop` in cleanup; treat as integration test.
- (c) Explicitly downgrade STP-06 to "narrative-only" coverage in this phase and add a follow-up issue. Document this as a known portability gap.

Recommend (b): integration via the real daemon is the closest match to D-195's contract.

**Severity rationale:** D-198 clause 6 ("Setup-done gate test demos a known-bad config fails the dry-run gate; skill aborts") is a load-bearing acceptance gate. Permanent SKIP makes this clause vacuous.

---

### F-03 , HIGH, plan 07-11 task 1, clause 9

**Description:** `test_phase7_acceptance_clause_09_automil_check_passes_on_workstation` does `pytest.skip("autoMIL not initialised at repo root...")` if `_REPO_ROOT / "automil" / "config.yaml"` is absent. autoMIL itself is the framework here; consumer setups live under `benchmarks/experiments/<dataset>/automil/`. The framework repo has NO root-level `automil/config.yaml`, so the test will skip on every CI run.

D-198 clause 8 (CONTEXT.md): "automil check passes on Leo's workstation with healthcheck integrated" , the success criterion is that `automil check` runs cleanly with the new healthcheck wiring on Leo's actual workstation, not that it passes on an arbitrary repo. The skip-on-missing-config behaviour shorts out the verification.

**Suggested fix:** Plan 07-11 should either (a) construct a tmp project with `automil init --no-healthcheck` and run `automil check` against it (within the test), or (b) parametrise the test with a known consumer path like `benchmarks/experiments/ccrcc/automil/` if that exists, or (c) instruct the executor to manually run `automil check` against the user's chosen consumer dir as part of the post-execute SUMMARY (not as a pytest test). Option (a) is preferred for CI determinism.

**Severity rationale:** D-198 clause 9 is one of the 11 acceptance gate clauses; a structural skip means it does not verify anything.

---

### F-04 , HIGH, plan 07-11 task 2

**Description:** Task 2 instructs adding a CHANGELOG entry headed `## [7.0.0] - 2026-05-08`. Task 1's clause-8 test accepts EITHER `[7.0.0]` OR `## 7.0.0` (line 249 of plan body: `assert "[7.0.0]" in text or "## 7.0.0" in text`). The plan also includes "Read CHANGELOG.md first; if Phase 6 used `## [6.0.0]` ... keep the bracket form; if `## 6.0.0` ... match that."

This is a conditional-at-execute-time decision that should be pre-resolved during planning. If the executor picks the wrong shape, the test still passes (because both are accepted), but the CHANGELOG file becomes inconsistent across versions. Worse, two different executors running in parallel could pick opposite shapes if the plan-checker re-tries.

**Suggested fix:** Planner should `head -30 CHANGELOG.md` during plan-checker iteration, lock the actual shape (likely `## [6.0.0]` per Keep-A-Changelog), and rewrite plan 07-11 task 2 with the unconditional shape. Drop the "Read first; if X then Y" prose.

**Severity rationale:** Reproducibility hazard. Acceptance test passes either way, but the artifact diverges. This is a Phase 7 close gate (D-198 clause 7 "CHANGELOG entry at 7.0.0 BREAKING").

---

### F-05 , HIGH, all plans, gap discovered via PATTERNS.md cross-reference

**Description:** PATTERNS.md §"tests/backends/test_contract.py (extend)" (lines 19, 365-369) explicitly maps the parametrised contract test as **exact-match extension** work for Phase 7: "Extend this file with `test_healthcheck_returns_health_report(backend)` parameterised across all backends. For LocalBackend: assert isinstance(report, HealthReport). For MockSLURMBackend/SLURMBackend/RayBackend: assert raises NotImplementedError."

No plan body extends `tests/backends/test_contract.py`. Plan 07-04 ships a separate `tests/backends/test_distributed_healthcheck_deferred.py` (3 tests covering the distributed-defer contract only). Plan 07-03 ships `tests/backends/test_local_healthcheck.py` (6 tests covering LocalBackend only). The parametrised-across-all-backends contract test that PATTERNS.md called for is missing entirely.

**Suggested fix:** Add a new task (in plan 07-04 wave 3, or a small plan 07-04b) that extends `tests/backends/test_contract.py` with the parametrised `test_healthcheck_returns_health_report(backend)` per the PATTERNS.md prescription. Alternatively, document why the parametrised approach was rejected in favour of two separate files.

**Severity rationale:** PATTERNS.md is the contract from research → plan; deviating from it without explicit rationale weakens the verification chain. Phase 6 used the parametrised contract test as the BCK-01 cornerstone; Phase 7's healthcheck not getting the same treatment leaves the contract surface tested by ad-hoc files.

---

### F-06 , MEDIUM, plan 07-09 task 1, `_run_gate` helper

**Description:** The `_run_gate` helper does `_os.chdir(repo)` then runs `runner.invoke(cli_main, [...])` then `_os.chdir(cwd_before)` in a try/finally. The test functions also do `monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)`. If `runner.invoke` raises (e.g. submit fails for an unrelated reason), the `finally` restores cwd, but the `_bootstrap_project` helper above also did its own `_os.chdir`/`_os.chdir` dance. The two chdir scopes are not nested and can leak cwd to the next test if assertions inside `_bootstrap_project` raise (the `_bootstrap_project` does not use try/finally).

**Suggested fix:** Use `pytest.MonkeyPatch.chdir` consistently in both helpers, OR wrap both helpers' bodies in `with contextlib.chdir(repo):` (Python 3.11+; this codebase declares Python 3.11+).

**Severity rationale:** Test isolation hazard, not a correctness bug. Affects only the SKIPPED tests in F-02 path so doesn't block this phase, but leaves a footgun for follow-up phases.

---

### F-07 , MEDIUM, plan 07-05 task 1, healthcheck call insertion order

**Description:** Plan 07-05 inserts the healthcheck call AFTER the `--update` guard (line 214) and BEFORE the `if not update:` scaffold block (line 216). The helper `_stamp_healthcheck_defaults` reads `<automil_dir>/results.tsv` to compute the empirical-VRAM path. On a fresh init (no `--update`), `automil_dir` doesn't yet exist , it's created at line 217 inside the scaffold block. Therefore `results_tsv.exists()` is always False on first-time init.

That's correct behaviour for *first-time* init (no prior runs to draw VRAM from). But on `--update`, `automil_dir` does already exist at line 211 because the guard catches it. The plan's helper insertion is between lines 214 and 216, which IS after the guard, so on `--update` the path exists. So the bug is specific to one edge case: the helper is called BEFORE the scaffold's `automil_dir.mkdir(parents=True, exist_ok=True)` runs on first-time init.

But the plan-body test `test_init_recomputes_default_vram_from_results_tsv` (07-05 task 3) seeds `automil_dir / results.tsv` BEFORE calling `runner.invoke([..., "--update"])`. So the test exercises the `--update` path, which works. Fresh-init path is silently un-tested for empirical recompute.

**Suggested fix:** Either (a) move the healthcheck call to AFTER the scaffold mkdir block (so `automil_dir` exists either way), or (b) add a 1-line `automil_dir.mkdir(parents=True, exist_ok=True)` at the top of `_stamp_healthcheck_defaults` to make the helper self-sufficient.

**Severity rationale:** Pitfall 8 mitigation #2 wants the empirical path to fire whenever there's enough data , this includes `--update` (covered) but the architecture should be uniform across update/fresh modes.

---

### F-08 , MEDIUM, plan 07-02 task 2, `_init_minimal_project` config stub

**Description:** Plan 07-02 ships a stub `config.yaml` in `_init_minimal_project` that includes `cap.budget_seconds` + `cap.safety_buffer_seconds` only. Plan 07-05 wave 4 then adds `cap.default_vram_estimate_gb` and `cap.max_concurrent_per_gpu` as new keys. Some validators in `automil check` may treat missing keys as warnings, but the wave-1 tests in 07-02 will silently regress when wave-4 lands if the stub config doesn't include the new cap keys. The wave-1 plan cannot reference future wave keys, so the executor of 07-02 may legitimately ship a stub that becomes incomplete in wave 4.

**Suggested fix:** Plan 07-02 task 2 should pre-include the `cap.default_vram_estimate_gb` and `cap.max_concurrent_per_gpu` keys with placeholder values in the stub config, citing forward-compatibility with 07-05. Cross-wave coupling should be explicit, not implicit.

**Severity rationale:** Test infrastructure debt; only manifests if 07-02's tests start failing after 07-05 lands.

---

### F-09 , LOW, em-dash audit

**Description:** Em-dash and en-dash counts in Phase 7 plan artifacts: 0 across all 11 plans + CONTEXT.md + RESEARCH.md (chunk read) + PLAN-SUMMARY.md. Pre-existing em-dashes in 07-PATTERNS.md (34) and `src/automil/backends/base.py` (6) survive untouched. Plans correctly include em-dash gates in every plan body's "Critical, no em-dashes" check.

The `feedback_no_em_dashes` rule is fully honoured for new content. Pre-existing dashes in PATTERNS and base.py are out of Phase 7 scope.

**Suggested fix:** Optional , add a note in 07-11 task 2 that the existing em-dashes in `backends/base.py` JobHandle/JobSpec docstrings (lines 40, 63, 84, 96, 135, 151) are pre-Phase-7 and not addressed here; future cleanup phase can sweep them.

**Severity rationale:** Cosmetic; rule is honoured for new code.

---

### F-10 , LOW, plan 07-07 task 1 conditional edit

**Description:** Plan 07-07 instructs "Re-read init.py lines 145-167 to confirm: does the existing Codex branch strip the YAML frontmatter from the merged output? If YES, the empty-frontmatter overlay file is sufficient. If NO, this plan needs an additional small edit." This is a conditional-at-execute-time decision; the planner should pre-resolve.

Source check: `cli/init.py` shows `runtime: str | None` parameter (line 195) and the template render block at lines 232-247 with no codex-branch frontmatter strip visible in the snippet read. The actual `_install_runtime_assets` function (called later in the file) is where merge_skill runs; that part wasn't read. The 5-line frontmatter-strip patch may be needed.

**Suggested fix:** Planner reads init.py end-to-end (the post-template-render `_install_runtime_assets` block) and determines deterministically whether the codex branch strips frontmatter. Updates plan 07-07 to either: drop the conditional and just add the strip, OR drop the strip if it's already there. Removes the "Re-read at execute time" instruction.

**Severity rationale:** Determinism hazard; current text leaves the executor making a non-trivial decision under time pressure.

---

## 4. Goal-Backward Map: STP Requirements → Plans

| STP-ID | Verbatim requirement (REQUIREMENTS.md) | Covering plan(s) | Verification plan | Status |
|--------|----------------------------------------|------------------|-------------------|--------|
| STP-01 | `LocalBackend.healthcheck()` reports detected GPU count, VRAM per GPU, accelerator type, Python version, autoMIL version | 07-01 (ABC), 07-03 (impl), 07-04 (distributed stubs) | 07-11 clause 1 | ✓ covered |
| STP-02 | `automil init` consumes healthcheck output and pre-fills config defaults | 07-05 (init wiring + Jinja stamping) | 07-11 clause 2; 07-08 (idempotency); 07-10 (anti-acceptance) | ✓ covered |
| STP-03 | Hardware-detect = report-not-decide; failures prompt override | 07-03 (status enum + warnings), 07-05 (click.confirm wiring) | 07-11 clause 3 | ✓ covered |
| STP-04 | `/automil-setup` skill inspects user repo, drafts config + program.md + variants/ skeleton | 07-06 (canonical SKILL.md narrative) | 07-11 clause 4 | ✓ covered (LLM-driven, narrative only) |
| STP-05 | Skill is idempotent , diff and update, never overwrite | 07-06 (Idempotency Protocol section), 07-08 (3 idempotency tests) | 07-11 clause 5 | ✓ covered |
| STP-06 | Mandatory `automil check` + 1-min dry-run before "done" | 07-02 (--max-time flag), 07-06 (Setup-Done Gate section), 07-09 (3 gate tests) | 07-11 clause 6 | ⚠ covered but tests permanently SKIP per F-02 |
| STP-07 | Per-runtime overlays: _shared canonical, claude/codex/opencode/deepseek overrides | 07-06 (_shared), 07-07 (codex empty-frontmatter), 4 propagation tests | 07-11 clause 4 | ✓ covered |

All 7 STP requirements have at least one covering plan and at least one verification plan. STP-06 has a coverage caveat (F-02). No requirement is silently dropped.

---

## 5. D-198 11-Clause Acceptance Gate Map

| Clause | D-198 description | Satisfying test (location) | Status |
|--------|-------------------|-----------------------------|--------|
| 1 | Backend.healthcheck ABC + 6 LocalBackend unit tests | `tests/backends/test_local_healthcheck.py` (07-03) + frontmatter check in `test_phase7_acceptance.py` | ✓ direct |
| 2 | automil init --no-healthcheck flag + healthcheck stamping | `tests/cli/test_init_healthcheck.py` (07-05, 5 tests) | ✓ direct |
| 3 | Failed detection prompts override (STP-03) | `test_init_aborts_on_failed_detection_user_decline` in 07-05 | ✓ direct |
| 4 | _shared SKILL.md narrative + overlay rebuild | 07-06 content + `test_overlay_propagation_phase7.py` (07-07, 4 tests) | ✓ direct |
| 5 | tests/skills/test_setup_idempotency.py: zero unprompted changes | 07-08 (3 tests) | ✓ direct |
| 6 | Setup-done gate test demos known-bad config aborts | 07-09 (3 tests) | ⚠ skipped per F-02; effectively unverified |
| 7 | Phase 6 baseline preserved + ≥10 new tests | clause-7 collection-count assertion in 07-11 (asserts ≥808) | ✓ direct |
| 8 | CHANGELOG entry at 7.0.0 BREAKING | 07-11 task 2 (CHANGELOG.md edit) + clause-8 test | ⚠ format under-specified per F-04 |
| 9 | automil check passes on Leo's workstation | clause-9 test in 07-11 | ✗ skipped on this repo per F-03 |
| 10 | SLURM/Ray Backend.healthcheck raise locked NotImplementedError | `tests/backends/test_distributed_healthcheck_deferred.py` (07-04, 3 tests) + clause-10 grep in 07-11 | ✓ direct |
| 11 | Framework purity: zero autobench/AUTOBENCH_/benchmarks/ refs | clause-11 grep in 07-11 across 10 Phase-7 src files | ✓ direct |

**Summary:** 8 of 11 clauses have direct, executable verification with no caveats. Clause 6 is permanently-SKIPPED. Clause 8 has format ambiguity. Clause 9 self-skips on this repo. After F-02/F-03/F-04 fixes, all 11 clauses become directly verified.

---

## 6. Audit Dimensions Recap

| Dimension | Result |
|-----------|--------|
| 1. Goal-backward fidelity | ✓ STP-01..07 each map to a plan; D-198 11-clause acceptance is wired through 07-11. |
| 2. API correctness vs source | ✓ NVIDIA_SMI_PATH location, query_gpus shape, `--max-time` patch site, `_overlay.py` merge_skill all match source. ⚠ ExperimentOrchestrator one-shot helper does not exist (F-02). ⚠ codex/skills/ subdir doesn't exist (created by 07-07; correct). |
| 3. File-disjointness for parallel waves | ✓ Wave 1 (07-01 ‖ 07-02), Wave 5 (07-06 ‖ 07-07), Wave 6 (07-08 ‖ 07-09 ‖ 07-10) all file-disjoint per PLAN-SUMMARY audit table; verified by re-checking files_modified frontmatter. |
| 4. Acceptance criteria are bash-verifiable | ✓ Every plan has `<acceptance_criteria>` or `<done>` blocks with grep/test/python -c one-liners. No "intent met" language. |
| 5. Anti-pattern scan | ✓ Zero em-dashes in plans. ✓ Zero HTML entities in shell snippets. ✓ Zero `git checkout` for rollback. ⚠ One legitimate `os.environ[...]` ref in 07-06 plan body (instruction text describing AST-walk grep target, not a write); not a violation. ✓ Zero `autobench`/`AUTOBENCH_`/`benchmarks/` references except in PROHIBITION grep guards. |
| 6. Frontmatter validity | ✓ All 11 plans have `wave` (1-indexed), `depends_on`, `files_modified`, `autonomous: true`, `requirements`. ✓ `must_haves` block present in every plan. ✓ 1-indexed waves (1..7), no Phase-6 0-indexing regression. |
| 7. Dependency-order soundness | ✓ Each plan's `depends_on` points to lower-numbered (earlier-wave) plans only. ✓ No same-wave or future-wave deps. ✓ 07-11 depends on all prior 10 plans (correct aggregator pattern). |
| 8. Test-stub coverage | ⚠ RESEARCH-cited tests: 6 healthcheck unit + 5 init integration + 3-4 idempotency + 3 dry-run gate + 4 anti-acceptance + 4 overlay propagation + 11 acceptance = 36+. Plans deliver ≈43. ✗ Missing: parametrised contract test extension per F-05. |
| 9. D-198 11-clause aggregator | ✓ Single test file `test_phase7_acceptance.py` per Phase 6 D-179 precedent. ⚠ Clauses 6, 8, 9 have caveats (F-02, F-04, F-03). |
| 10. No regressions | ✓ Phase 6's 848-test baseline is preserved through every plan's "no regression" check. ⚠ 07-01 introduces transient TypeError on backend instantiation; closed by 07-03 (Wave 2) + 07-04 (Wave 3). The transient breakage window is correctly scoped. |
| 11. Backwards-compat (Backend.healthcheck rollout) | ✓ 07-01 makes the method abstract; 07-03 implements LocalBackend (Wave 2); 07-04 stubs SLURM/Ray/MockSLURM (Wave 3) with locked-message NotImplementedError. ✓ All four subclasses become instantiable by Wave 3 close. ✓ Wave-2 testing windows correctly accept the transient RED state. |

---

## 7. Recommended Next Action

**RETRY** , orchestrator should respawn the planner with the F-01 BLOCKER + F-02..F-05 HIGH list. Recommended planner brief:

> Phase 7 plans pass goal-backward audit at 8/11 D-198 clauses with no caveats. Five surgical patches required:
>
> 1. **F-01 (BLOCKER):** In 07-09 task 1 action body, place the `_orchestrator_supports_one_shot` helper code block FIRST (after imports), then the decorated test code block. Drop the trailing "Place it BEFORE..." prose. Verify by visually scanning the rendered code blocks: helper before tests.
>
> 2. **F-02 (HIGH):** In 07-09, replace `_orchestrator_supports_one_shot` skipif gate with a real integration test using `automil orchestrator start --background` + 90s wall-clock + `automil orchestrator stop` cleanup. OR add an explicit, dedicated wave-1 task to ship a synchronous `_process_queue_once` method on ExperimentOrchestrator. Acceptance: dry-run gate tests must actually RUN, not SKIP.
>
> 3. **F-03 (HIGH):** Rewrite 07-11 clause-9 test to construct a tmp project + run `automil init --no-healthcheck` + run `automil check` against it. Drop the `pytest.skip(...)` early-return. Acceptance: clause 9 PASSES (not SKIPS) on a fresh checkout.
>
> 4. **F-04 (HIGH):** Run `head -30 CHANGELOG.md` in plan-checker iteration; lock the actual heading shape (likely `## [X.Y.Z] - YYYY-MM-DD`); rewrite 07-11 task 2 with that single shape. Drop the conditional "if Phase 6 used X then Y" prose.
>
> 5. **F-05 (HIGH):** Add a small task in 07-04 (or new plan 07-04b in Wave 3) extending `tests/backends/test_contract.py` with the parametrised `test_healthcheck_returns_health_report(backend)` that PATTERNS.md prescribes. For LocalBackend: assert `isinstance(report, HealthReport)`. For MockSLURMBackend/SLURMBackend/RayBackend: assert `pytest.raises(NotImplementedError, match="...locked message...")`.
>
> Optional MEDIUM patches (F-06, F-07, F-08) and LOW patches (F-09, F-10) can ship in same revision if convenient.

After the retry, run plan-checker iteration 2. If iteration 2 returns RETRY again, escalate.

---

## 8. Justification for Verdict

**Why RETRY, not PASS:**
- F-01 is a literal NameError-on-import; cannot ship.
- F-02 is a permanent SKIP that hollows out STP-06 verification.
- F-03 is a structural skip that hollows out D-198 clause 9.
- F-04 is a reproducibility hazard at the close-phase artifact level.
- F-05 is a deviation from explicit PATTERNS.md prescription.

**Why RETRY, not BLOCK:**
- All 5 patches are surgical; no fundamental rework.
- Plan structure (waves, dependencies, file-disjointness, must_haves) is sound.
- Decision traceability (D-189..D-198) is direct and verbatim.
- No requirement is silently dropped.
- Em-dash discipline + framework purity discipline + BCK-04 lint discipline are all honoured.
- One-iteration plan-checker turnaround is realistic.

**Iteration:** 1 of (max) 3.

**Recommendation:** orchestrator (Leo) spawns planner-revisor with this PLAN-CHECK.md as input; planner patches F-01..F-05 (and optionally F-06..F-10); plan-checker runs iteration 2; if iteration 2 returns PASS, execute Wave 1.
