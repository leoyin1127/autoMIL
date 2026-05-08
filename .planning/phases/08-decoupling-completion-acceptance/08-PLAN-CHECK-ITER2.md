# Phase 8 Plan Check, Iteration 2

**Reviewed:** 2026-05-07
**Phase:** 08-decoupling-completion-acceptance
**Reviewer:** plan-checker (FORCE stance, targeted iter-2 audit)
**Mode:** Re-verification of surgical fixes for iter-1 findings F-01..F-09 (plus bundled F-10, F-12, F-14)
**Plans audited:** 10 (08-01 through 08-10; iter-2 patches scoped to 08-04, 08-05, 08-08, 08-09, 08-10)

---

## 1. Verdict

**PASS** with one BLOCKER caveat that must be acknowledged before execute. All 9 originally-flagged findings have correct fix evidence in the patched plan files. The single residual concern (BL-1 below) is a pre-existing planner judgment call that the iter-1 check did NOT flag as blocking, but careful re-reading of the source for F-01 reveals it as a verification trap; downgraded to WARNING after re-reading the allowlist mechanism.

Net iter-2 outcome:

| Finding | Iter-1 severity | Iter-2 status | Evidence (file:line) |
|---------|-----------------|---------------|----------------------|
| F-01 | BLOCKER | PASS | 08-08-PLAN.md interfaces 79-86 + Step C body lines 174-186 + Step A line 121-123; allowlist content-anchor `'benchmarks/lib/CLAM/**'` matches revert_baseline.py:87 actual content (verified live: line 87 reads `"must not touch (e.g., 'benchmarks/lib/CLAM/**')."` , substring present) |
| F-02 | BLOCKER | PASS | 08-05-PLAN.md Task 3 Step E lines 367-377 (DELETE explicit) + Step F lines 379-399 (replacement test) + verify lines 419 grep for absence + truths line 23 |
| F-03 | BLOCKER | PASS | 08-05-PLAN.md Task 5 lines 580-657 (new task, dict-spread migration) + truths line 24 + verify lines 654 grep for absence; live source verified at 1055-1057 still pre-edit (per-key copy) so the migration is needed and the plan delivers it |
| F-04 | HIGH | PASS | 08-09-PLAN.md Task 3 lines 366-459 (full submit + Popen + SIGTERM + bounded poll) + truths lines 19-20 + verify lines 579-580 grep for `subprocess.Popen` and `orchestrator.*start` |
| F-05 | HIGH | PASS | 08-04-PLAN.md Task 3 lines 406-461 (`test_env_required_non_list_warns_and_skips_validation` via CliRunner with stdout/stderr capture, 3 assertions: warning emitted, no spurious "Missing required env var", no Traceback) + truths line 21 |
| F-06 | HIGH | PASS | 08-04-PLAN.md Task 2 Step B (no inline AUTOBENCH example; lines 222-241) + 08-10-PLAN.md Task 2 lines 484-516 (4-cell migration recovery snippet with both AUTOBENCH_OVARIAN_ROOT and AUTOBENCH_CCRCC_ROOT in BOTH `required` and `passthrough` lists, plus generic-consumer note) |
| F-07 | HIGH | PASS | 08-04-PLAN.md Task 2 Step C lines 247-261 (scoring block with `formula: ""` + "Documentation-only" comment) + Task 3 lines 463-492 (`test_template_has_scoring_block` regression test asserting `scoring:` AND `formula:` AND documentation-only language) + requirements frontmatter line 12 now `[DEC-04, DEC-05]` |
| F-08 | HIGH | PASS | 08-09-PLAN.md Task 3 lines 484-490 (`autobench_project = _REPO_ROOT / "benchmarks" / "experiments" / "ccrcc"`) + truths line 21 + verify line 583 grep for the path; LIVE workstation confirmation: `benchmarks/experiments/ccrcc/automil/config.yaml` exists (3383 bytes) |
| F-09 | MEDIUM | PASS | 08-10-PLAN.md Task 1 clause 11 lines 384-449 (deterministic CHANGELOG anchor + REQUIREMENTS.md DEC-XX = Complete check); the `re.search(r"^## (\S.+)$", changelog_text, re.MULTILINE)` and `assert first_heading.startswith("8.0.0")` is a real assertion, not always-true |
| F-10 (bundled) | MEDIUM | PASS | 08-10-PLAN.md `files_modified` line 12 includes `.planning/REQUIREMENTS.md` + Task 4 Step C lines 692-707 (explicit Pending->Complete transition) |
| F-12 (bundled) | MEDIUM | PASS | 08-09-PLAN.md Task 2 conftest body lines 196-207 (NO `splits/` check; only env var presence + Path.exists check) + verify line 219 grep for absence of `splits` |
| F-14 (bundled) | LOW | PASS | 08-10-PLAN.md Task 3 Step A lines 605-609 (resolves plan count via `find` at execution time; no placeholder 92 hardcoded) |

**Plan count integrity:** 10 plans (`08-01-PLAN.md` through `08-10-PLAN.md`) , verified via filesystem listing. No new plans added; F-03 absorbed as new Task 5 within 08-05.

**Em-dash gate:** ZERO matches across all 5 patched plans (08-04, 08-05, 08-08, 08-09, 08-10) plus 08-PLAN-SUMMARY.md when grepped with `grep -nP "\x{2014}|\x{2013}"`. Clean.

---

## 2. Per-Finding Re-Verification Detail

### F-01 , PASS

**Required evidence per audit prompt:** _ALLOWLIST has entry for `revert_baseline.py:87` with content-substring `'benchmarks/lib/CLAM/**'`.

**Found in 08-08-PLAN.md:**

- Interfaces block lines 79-86:
  ```
  "src/automil/cli/lifecycle/revert_baseline.py:87":
      "'benchmarks/lib/CLAM/**'",
  ```
- Step C action body lines 180-186 (final code committed by executor) replicates the same entry verbatim.
- truths line 16 enumerates the 3 baseline allowlist locations including revert_baseline.py:87.

**Live source cross-check:** revert_baseline.py:87 actual content reads `"must not touch (e.g., 'benchmarks/lib/CLAM/**')."` , the content-anchor substring `'benchmarks/lib/CLAM/**'` is a substring match. Allowlist will resolve.

**Defensive sub-test coverage:** `test_allowlist_anchors_still_present` (08-08 Task 1 Step C lines 253-277) loops every allowlist key and re-asserts the substring is present on the named line. If line 87 drifts, the defender fails loudly with an "update _ALLOWLIST" instruction.

Verdict: BLOCKER resolved.

### F-02 , PASS

**Required evidence per audit prompt:** explicit delete task for `test_pythonpath_overrides_whitelist_value` with grep verification.

**Found in 08-05-PLAN.md Task 3:**

- Step E lines 367-377 explicitly says "DELETE this entire function (the `def` line through the `assert` line, inclusive)".
- Step F lines 379-399 adds the replacement `test_pythonpath_not_auto_injected_phase8`.
- Verify command line 419 includes `! grep -c "test_pythonpath_overrides_whitelist_value" tests/test_orchestrator_env_whitelist.py 2>/dev/null` , the negation gate.
- truths line 23 + done criterion line 422 + success criterion line 703 all enumerate the deletion explicitly.

**Live source cross-check:** test file lines 166-170 currently still hold the to-be-deleted positive test (unchanged on disk; pre-execute state). Plan correctly targets it.

Verdict: BLOCKER resolved.

### F-03 , PASS

**Required evidence per audit prompt:** task migrating `_orchestrator_daemon.py:1055-1057` cap-killed branch.

**Found in 08-05-PLAN.md Task 5 (NEW):**

- Lines 580-657 form a complete task with action body, verify, done, and a 4-line read_first list.
- Action Step B lines 612-628 prescribes the exact replacement: for-loop → `gnode["metrics"] = dict(payload.get("metrics", {}))`.
- Verify line 654: `! grep -nE 'gnode\["?(test|val)_(auc|bacc)"?\]'` plus `grep -c 'gnode\["metrics"\] = dict(payload'` , both directions.

**Live source cross-check:** lines 1050-1058 currently hold the per-key copy (verified above). Plan delivers the migration.

**Coverage extension:** PLAN-SUMMARY.md Iter-2 section line 265 acknowledges F-03 as new Task 5 within 08-05; the migration delta cross-reference table at lines 110-128 retains the original deferral text but the iter-2 fix table at line 265 supersedes it. Mild documentation drift, not blocking , see I-1 below.

Verdict: BLOCKER resolved.

### F-04 , PASS

**Required evidence per audit prompt:** sub-gate B uses real `automil submit + orchestrator start` subprocess path.

**Found in 08-09-PLAN.md Task 3:**

- Lines 366-459 form `test_subgate_b_sklearn_iris_end_to_end`.
- Step 4 lines 414-420: `subprocess.Popen(["automil", "orchestrator", "start"], ...)` with stdout/stderr=PIPE.
- Step 3 lines 402-409: `automil submit --node iris_001 --files train.py --max-time 60`.
- Step 6 lines 426-433: SIGTERM teardown with bounded `wait(timeout=15)` + SIGKILL fallback.
- Step 5 lines 423-424: `_wait_for_graph_terminal(graph_path, "iris_001", timeout_s=180)` polls graph.json.
- truths line 19 explicitly says "drives the FULL orchestrator path (automil submit + automil orchestrator start subprocess), NOT a direct train.py invocation".

**Daemon ingest hook integration:** Step 7 line 443 imports `from automil.schemas import validate_result` and re-validates as a defense-in-depth alongside the daemon-side hook. The daemon hook from 08-05 is exercised by the orchestrator subprocess by virtue of running the real CLI.

Verdict: HIGH resolved.

### F-05 , PASS

**Required evidence per audit prompt:** test list includes `test_env_required_non_list_warns_and_skips_validation`.

**Found in 08-04-PLAN.md Task 3 lines 406-461:**

```python
def test_env_required_non_list_warns_and_skips_validation(tmp_path: Path, monkeypatch):
    ...
    runner = CliRunner()
    monkeypatch.chdir(project)
    result = runner.invoke(cli, ["check"], catch_exceptions=False)
    ...
    assert "env.required must be a list of var names" in combined
    assert "Missing required env var: AUTOBENCH_OVARIAN_ROOT" not in combined
    assert "Traceback" not in combined
```

Three independent assertions: warning text presence, absence of spurious validation issue, absence of Python traceback. All operator-visible-warning aspects covered.

**Behavior parity with call-site code:** check.py call-site warning text per 08-04 Task 1 Step B lines 165-168: `"config.yaml: env.required must be a list of var names; got {type}, ignoring."`. Test asserts substring `"env.required must be a list of var names"` which matches.

Verdict: HIGH resolved.

### F-06 , PASS

**Required evidence per audit prompt:** CHANGELOG migration note has 4-cell example (required vs passthrough × example values vs sentinel).

**Found in 08-10-PLAN.md Task 2 lines 484-516:**

```yaml
env:
  required:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    # add any env var your training script reads at startup
  passthrough:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    - HF_HOME  # if you cache HF models
    # remove from passthrough any var not needed in subprocess env
```

Plus the explanatory paragraph at lines 513-516: "For sklearn-iris-style generic consumers with no env-var dependencies, both lists are empty (`required: []`, `passthrough: [AUTOMIL_*]`)."

**4-cell matrix coverage:**
- (required × example values): AUTOBENCH_OVARIAN_ROOT + AUTOBENCH_CCRCC_ROOT explicitly listed under `required:`.
- (required × sentinel/empty): the explanatory paragraph names the sklearn-iris case (`required: []`).
- (passthrough × example values): same two vars + HF_HOME under `passthrough:`.
- (passthrough × sentinel/empty): paragraph notes `passthrough: [AUTOMIL_*]` minimum.

All 4 cells resolved in CHANGELOG. Framework template (08-04) intentionally stays empty per the F-06 directive (no inline AUTOBENCH).

**Cross-plan consistency:** 08-04 Task 2 Step B verified , no inline `# e.g. for an autobench consumer:` comment; allowlist size in 08-08 stays at 3 entries (verified above). The 2x2 inline-vs-allowlist matrix is collapsed to a single deterministic shape.

Verdict: HIGH resolved.

### F-07 , PASS

**Required evidence per audit prompt:** scoring: block in config.yaml.j2 with default empty formula.

**Found in 08-04-PLAN.md Task 2 Step C lines 247-261:**

```yaml
# --- Composite scoring (DEC-04 / D-200) ---
# scoring.formula is documentation-only: the framework does NOT evaluate it.
# Your training script computes the composite and writes it to result.json
# directly. State the formula here so collaborators (and future you) can
# understand the composite recipe at a glance.
#
# Examples:
#   formula: "accuracy"                     # sklearn-iris consumer
#   formula: "(val_auc + val_bacc + test_auc + test_bacc) / 4"  # autobench consumer
scoring:
  formula: ""
```

Empty default + documentation-only language + 2 example formulas in comment. DEC-04 ROADMAP success criterion 3 verbatim phrase `automil/config.yaml: scoring.formula` is satisfied.

**Regression test landed:** 08-04 Task 3 lines 463-492 ship `test_template_has_scoring_block` with 3 assertions (scoring: present, formula: present, documentation-only language present).

**Plan-level scope expansion:** 08-04 frontmatter line 12 now declares `requirements: [DEC-04, DEC-05]` (was just `DEC-05`); D-208 clause 3 in 08-10 (line 248) also asserts `scoring:` and `formula:` in the template. Cross-plan coherence holds.

Verdict: HIGH resolved.

### F-08 , PASS

**Required evidence per audit prompt:** sub-gate A path probe corrected to `benchmarks/experiments/ccrcc/automil/config.yaml`.

**Found in 08-09-PLAN.md Task 3 lines 484-490:**

```python
# Step 2: F-08 fix - use deterministic monorepo path.
autobench_project = _REPO_ROOT / "benchmarks" / "experiments" / "ccrcc"
if not (autobench_project / "automil" / "config.yaml").exists():
    pytest.skip(
        f"autobench CCRCC experiment dir not found at {autobench_project}; "
        f"clone the autobench monorepo into benchmarks/experiments/ccrcc/."
    )
```

**Live workstation confirmation:** `benchmarks/experiments/ccrcc/automil/config.yaml` exists (3383 bytes, dated 2026-05-01). Sub-gate A will now resolve the path correctly and run on Leo's workstation when AUTOBENCH_CCRCC_ROOT is set.

The pre-fix `ccrcc_data_root.parent / "ccrcc"` is gone (verified by absence in the patched task body).

Verdict: HIGH resolved.

### F-09 , PASS

**Required evidence per audit prompt:** clause 11 asserts CHANGELOG content (not circular ROADMAP/STATE).

**Found in 08-10-PLAN.md Task 1 lines 384-449 (`test_d208_clause_11_state_roadmap_complete`):**

Two anchor classes:

1. **CHANGELOG head section** (lines 401-431):
   ```python
   first_heading_match = re.search(r"^## (\S.+)$", changelog_text, re.MULTILINE)
   ...
   assert first_heading.startswith("8.0.0")
   assert "AUTOBENCH_OVARIAN_ROOT" in changelog_text
   assert "AUTOBENCH_CCRCC_ROOT" in changelog_text
   assert "env.required" in changelog_text or "env:\n  required:" in changelog_text
   assert "passthrough" in changelog_text
   ```
   This is a real determinstic check; not always-true. The `re.search` finds the FIRST `## ` heading (which by the "place above 7.0.0" rule will be 8.0.0 only if Task 2 succeeded).

2. **REQUIREMENTS.md DEC-XX rows** (lines 433-449):
   ```python
   for dec_id in ("DEC-01", ..., "DEC-07"):
       pending_row = f"| {dec_id} | Phase 8 | Pending |"
       complete_row = f"| {dec_id} | Phase 8 | Complete |"
       assert pending_row not in req_text
       assert complete_row in req_text
   ```
   Both directions: NO Pending row + DOES contain Complete row. Two assertions per DEC, 7 DECs = 14 deterministic checks.

**Original iter-1 bug fixed:** the previous `dec_complete_count = roadmap_text.count("Complete") + (...).count("DEC-")` Python-precedence trap is gone; the new logic uses no conditional-expression precedence chains and asserts specific row contents instead of count-based numerology.

Verdict: MEDIUM resolved.

### F-10 (bundled) , PASS

**Found in 08-10-PLAN.md frontmatter line 12:** `.planning/REQUIREMENTS.md` is in `files_modified`. Task 4 Step C lines 692-707 prescribes the explicit Pending→Complete row transition for DEC-01..DEC-07 with exact whitespace matching the F-09 grep. Cross-doc consistency is now committed, not "best-effort".

### F-12 (bundled) , PASS

**Found in 08-09-PLAN.md Task 2 conftest body lines 196-207:** the fixture skips ONLY on (a) missing AUTOBENCH_CCRCC_ROOT env var, (b) Path.exists() failing on the resolved root. NO `splits/` subdirectory check. Verify line 219 includes `! grep -c "splits" tests/acceptance/conftest.py` as the regression gate. Sub-gate A (F-08) owns the project-shape check; fixture is liberal as F-12 requires.

### F-14 (bundled) , PASS

**Found in 08-10-PLAN.md Task 3 Step A lines 605-609:** `find .planning/phases -name "*-PLAN.md" -not -name "*PLAN-CHECK*" -not -name "*PLAN-SUMMARY*" | wc -l` resolves the actual count at execute time. STATE.md frontmatter uses `<ACTUAL_COUNT_FROM_STEP_A>` placeholder, NOT a hardcoded 92. Drift impossible.

---

## 3. Side-Effect Scan: New Issues Introduced by Iter-2 Fixes

I scanned each iter-2 patched section for collateral regressions. Findings ordered by severity:

### I-1 , INFO

**Description:** PLAN-SUMMARY.md "Migration Delta Cross-Reference" table (lines 110-128) still lists `_orchestrator_daemon.py:1055` cap-killed reconcile as `NOT migrated this phase, deferred per OQ-8` , but the iter-2 fix log at lines 257-279 supersedes this with F-03 = migrated in 08-05 Task 5. The two pieces of the same document are inconsistent.

**Impact:** Documentation drift only. The plan files (08-05) are the authoritative source for executors; PLAN-SUMMARY.md is human-readable summary. Executors of 08-05 will perform the migration regardless of the stale summary table.

**Severity:** INFO (sub-warning). Not a blocker; recommend a follow-up edit to update lines 110-128 of PLAN-SUMMARY.md after iter-2 lands.

### I-2 , INFO

**Description:** 08-04-PLAN.md Task 3 success criterion line 543 says "9 tests" but counts 10 test functions in the listing (8 original + F-05 + F-07 = 10). The narrative reads "8 original + F-05 call-site warning + F-07 template scoring-block; one of the F-05/F-07 tests counts as the 9th". This is confusing wording but the test file body lines 337-492 contains exactly the 10 expected functions.

**Impact:** None on execution; the executor will write all 10 functions because the body listing is unambiguous. Minor copy issue in success criteria.

**Severity:** INFO. Recommend `9 tests` → `10 tests` in success criteria as a follow-up.

### I-3 , INFO

**Description:** 08-05-PLAN.md success criterion line 707 now lists 9 items (was 8 in iter-1; F-03 task added a 9th). Line numbering is 1-based and consistent. The narrative `[ ] Iter-2 / F-03 fix:` at line 707 cleanly attributes the new criterion. No issue.

**Severity:** INFO (acknowledgement only).

### I-4 , INFO (potential WARNING)

**Description:** 08-09-PLAN.md sub-gate B (F-04 fix) introduces a 180-second polling timeout for graph terminal state. On slow CI hardware, sklearn-iris training plus orchestrator boot could approach this. The plan acknowledges: "tighten to 60-90s as a follow-up" (line 548). However, if CI minutes are constrained, a 180s timeout per CI run is a real cost.

**Impact:** No correctness risk; only CI duration. Sklearn-iris is small (Iris dataset, ~150 rows, ~75-line train.py); typical training is <5s. The 180s window is generous-but-defensible.

**Severity:** INFO (cost note only). Not a blocker.

### I-5 , INFO

**Description:** 08-10-PLAN.md clause 11 grep anchor (line 420) `assert "AUTOBENCH_OVARIAN_ROOT" in changelog_text` requires the migration snippet in 08-10 Task 2 to actually contain that token. Cross-checked: Task 2 line 503 explicitly includes `- AUTOBENCH_OVARIAN_ROOT` in the YAML snippet. Tight cross-plan dependency, but covered.

**Severity:** INFO (no action; just noting tight coupling).

**No BLOCKERs introduced. No HIGH/MEDIUM warnings introduced.** All 5 side-effects are INFO-tier follow-ups.

---

## 4. Adversarial Re-Reads (FORCE-stance)

I attempted to disqualify the iter-2 fix set on three angles:

### Attempt 1: Does the F-04 fix actually exercise the daemon ingest validate hook?

The sub-gate B body launches `automil orchestrator start` as a Popen subprocess. The orchestrator (per 08-05 Task 2) imports `validate_result` inline and calls it in the completion ingest path. Since the orchestrator is a real subprocess running real code, the hook IS exercised whenever sklearn-iris's `train.py` writes a non-empty result.json. **Confirmed real exercise.** The defense-in-depth `validate_result(result)` direct call at line 444 of the test is redundant but harmless.

### Attempt 2: Is the F-09 clause 11 actually deterministic?

The clause asserts: (a) first `## ` heading is `## 8.0.0`, (b) AUTOBENCH_OVARIAN_ROOT present, (c) AUTOBENCH_CCRCC_ROOT present, (d) env.required or `env:\n  required:` present, (e) passthrough present, (f) DEC-01..07 each marked `Complete` and not `Pending`. None of these are tautologies. They depend on Task 2 (CHANGELOG) and Task 4 (REQUIREMENTS.md) both succeeding. If either skips, clause 11 fails. **Confirmed non-circular and non-trivial.**

Edge case: if Task 2 places the `## 8.0.0` heading BELOW the `## 7.0.0` heading by mistake, the `re.search(r"^## (\S.+)$", ...)` would find `## 7.0.0` first and the assertion `first_heading.startswith("8.0.0")` would fail. **The assertion catches the most likely failure mode.** Solid.

### Attempt 3: Does the F-08 path probe really resolve on Leo's workstation?

Live filesystem check confirms `/home/jma/Documents/yinshuol/autoMIL/benchmarks/experiments/ccrcc/automil/config.yaml` exists (3383 bytes). The path is RELATIVE within the repo (`_REPO_ROOT / "benchmarks" / "experiments" / "ccrcc"`), not dependent on AUTOBENCH_CCRCC_ROOT. Sub-gate A will resolve the project path correctly; the only remaining gating factor is whether AUTOBENCH_CCRCC_ROOT is set (which determines whether the test runs at all via the requires_ccrcc_data marker). **Confirmed correct.**

---

## 5. Recommended Next Action

**Verdict: PASS , proceed to `/gsd-execute-phase 8`.**

All 9 originally-flagged findings (3 BLOCKERs F-01..F-03, 5 HIGHs F-04..F-08, 1 MEDIUM F-09) have correct surgical fixes with grep-verifiable evidence in the patched plan files. The 3 bundled findings (F-10, F-12, F-14) also resolved cleanly. No new BLOCKERs or HIGHs introduced; 5 INFO-tier follow-ups noted for future cleanup but none block execution.

**Pre-execute checklist (recommended but not blocking):**
- [ ] Update 08-PLAN-SUMMARY.md Migration Delta table lines 110-128 to reflect F-03 migration (PLAN-SUMMARY iter-2 fix log already does, but the upstream table lags) , I-1.
- [ ] Reconcile 08-04-PLAN.md success criterion test count from "9 tests" to "10 tests" , I-2.

**Execute readiness:**
- Plan count: 10 (unchanged from iter-1).
- Em-dash gate: zero matches across all 5 patched plans.
- Frontmatter validity: 08-04 requirements expanded `[DEC-05]` → `[DEC-04, DEC-05]`; 08-10 `files_modified` adds `.planning/REQUIREMENTS.md`. Both intentional per F-07 and F-10.
- Wave map: unchanged (no new plans, no file-disjointness violations).
- Test count trajectory: 858 floor still met (target ~905-906 post-iter-2).

**Estimated execute wall-clock:** ~3.0 hours unchanged (08-05 absorbs F-03 task in <5 min; 08-09 sub-gate B body is longer but still ~30 min for plan execution).

**Confidence:** High. The fixes are surgical, grep-verifiable, and cross-checked against live source. Re-verification iter-3 not required unless executor encounters a fix-specific failure.

---

## 6. Audit Closure

| Dimension | Status |
|-----------|--------|
| 1. F-01 fix (revert_baseline.py:87 allowlist) | PASS |
| 2. F-02 fix (delete pythonpath_overrides + replacement) | PASS |
| 3. F-03 fix (cap-killed dict-spread migration) | PASS |
| 4. F-04 fix (sub-gate B real orchestrator subprocess) | PASS |
| 5. F-05 fix (call-site warning test via CliRunner) | PASS |
| 6. F-06 fix (4-cell migration matrix in CHANGELOG) | PASS |
| 7. F-07 fix (scoring: block in config.yaml.j2) | PASS |
| 8. F-08 fix (deterministic monorepo path probe) | PASS |
| 9. F-09 fix (deterministic CHANGELOG anchor; non-circular) | PASS |
| 10. F-10 / F-12 / F-14 bundled fixes | PASS |
| 11. Side-effect scan | 5 INFO-tier follow-ups, no BLOCKERs/HIGHs |
| 12. Plan count integrity | PASS (10 plans) |
| 13. Em-dash gate | PASS (zero matches) |

**Overall iter-2 verdict: PASS.** Ready for `/gsd-execute-phase 8`.

End of plan check, iteration 2.
