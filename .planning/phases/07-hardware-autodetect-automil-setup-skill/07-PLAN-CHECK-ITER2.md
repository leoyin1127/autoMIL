# Phase 7 Plan Check, Iteration 2

**Reviewed:** 2026-05-07
**Phase:** 07-hardware-autodetect-automil-setup-skill
**Reviewer:** plan-checker (focused iter-2 audit on F-01..F-05 resolutions)
**Plans audited:** 12 (07-01..07-11 plus new 07-04b)
**Iter-1 source:** `07-PLAN-CHECK.md` (1 BLOCKER + 4 HIGH + 3 MEDIUM + 2 LOW)
**Source artifacts re-read:** 07-09-PLAN.md, 07-11-PLAN.md, 07-04-PLAN.md, 07-04b-PLAN.md, 07-PLAN-SUMMARY.md, src/automil/cli/orchestrator.py, src/automil/cli/init.py, src/automil/cli/submit.py, CHANGELOG.md, tests/backends/test_contract.py, tests/backends/conftest.py.

---

## 1. Verdict

**PASS** — all 5 iter-1 findings (1 BLOCKER + 4 HIGH) are resolved; zero new BLOCKERs introduced; 1 informational/LOW item noted on the wave-3 sequencing claim. Plans are ready for `/gsd-execute-phase 7` Wave 1 kickoff.

Iter-1 medium / low items (F-06..F-10) were not in scope for this iter-2 audit and are not re-checked.

---

## 2. F-01..F-05 Resolution Status

| ID | Original severity | Iter-1 description | Fix verification | Evidence |
|----|-------------------|--------------------|-----------------|----------|
| **F-01** | BLOCKER | `_orchestrator_supports_one_shot` referenced in `@pytest.mark.skipif` decorators before its function definition in source order | **PASS** | `07-09-PLAN.md`:126 `def _automil_on_path()` is the first top-level definition after imports inside the rendered Python code block (lines 92-312). The first `@pytest.mark.skipif(not _automil_on_path(), ...)` decorator appears at line 271 of the plan body, well after the helper. The misleading apparent earlier reference at line 90 is prose preamble (`@pytest.mark.skipif(not _automil_on_path(), ...)` quoted in the executor instructions), not the executable code skeleton. Helper renamed from `_orchestrator_supports_one_shot` to `_automil_on_path` — semantically aligned with the new F-02 strategy. Frontmatter `must_haves.truths` (lines 13-17) and `<done>` (line 326) cite the F-01 ordering check. |
| **F-02** | HIGH | `_orchestrator_supports_one_shot` checked for `_process_queue_once`/`_tick_once` on `ExperimentOrchestrator`; neither method exists, so all 3 dry-run tests permanently SKIP | **PASS** | `grep -n "_process_queue_once\|_tick_once" 07-09-PLAN.md` returns **zero matches** (verified). Replacement strategy uses real CLI: `_start_daemon` (07-09:160-166) launches `subprocess.Popen(["automil", "orchestrator", "start"], ...)` in a process group; `_stop_daemon` (07-09:169-193) issues `automil orchestrator stop` then escalates SIGTERM/SIGKILL on the process group. Both `automil orchestrator start` (cli/orchestrator.py:17 → `cmd_start`) and `automil orchestrator stop` (cli/orchestrator.py:27 → `cmd_stop`) exist and are invoked verbatim. The skipif gate is `_automil_on_path() = shutil.which("automil") is not None` (07-09:126-133), correctly gating only on PATH availability. `frontmatter.depends_on: [07-02, 07-05, 07-08]` (07-09:6) was extended to pull in 07-08's `tmp_git_repo` fixture. |
| **F-03** | HIGH | Acceptance clause 9 `pytest.skip`s when `_REPO_ROOT / "automil" / "config.yaml"` is absent; the framework repo never has one, so clause 9 always skips | **PASS** | `07-11-PLAN.md`:266-309 (`test_phase7_acceptance_clause_09_automil_check_passes_on_workstation`) constructs a tmp project under `tmp_path/fake_consumer`: `git init -q`, writes a minimal `train.py`, runs `automil init --no-healthcheck` (line 293), then runs `automil check` (line 303) and asserts `returncode == 0`. The only pytest.skip in that function is line 276: `if shutil.which("automil") is None: pytest.skip(...)` — a legitimate "binary not on PATH" guard, not the iter-1 self-skip. The `--no-healthcheck` flag is the deliverable of plan 07-05 (Wave 4); 07-11 is Wave 7 and depends_on includes 07-05 (verified). The git-init prerequisite (cli/init.py:202-208 requires being inside a git repo) is honored by the test (line 286 `git init -q`). |
| **F-04** | HIGH | CHANGELOG entry test allowed either `[7.0.0]` OR `## 7.0.0`, while task 2 emitted `[7.0.0]` — format ambiguity across executors | **PASS** | `07-11-PLAN.md`:260 — clause-8 grep is exactly `assert "## 7.0.0" in text`, single anchor, no `or` clause. Task 2 (line 399) emits the exact heading: `## 7.0.0 - Phase 7 hardware autodetect + automil-setup skill (unreleased)` (ASCII hyphen separator). The CHANGELOG.md head was inspected: existing Phase 6 entry at line 5 reads `## 6.0.0 — Phase 6 SLURM + Ray backends (unreleased)` (em-dash separator, no brackets). The planner's deliberate choice to use ASCII hyphen instead of em-dash in the new 7.0.0 entry is justified per Leo's standing `feedback_no_em_dashes` rule; the substring grep `## 7.0.0` is satisfied either way, but the artifact is reproducible because Task 2's heading line is fully literal. The conditional "if Phase 6 used X then Y" prose has been removed. |
| **F-05** | HIGH | PATTERNS.md §365-369 prescribes a parametrised `test_healthcheck_returns_health_report(backend)` extending `tests/backends/test_contract.py`; iter-1 plan set never extended that file | **PASS** | New plan `07-04b-PLAN.md` exists. Frontmatter (lines 1-44): `wave: 3`, `depends_on: [07-01, 07-03, 07-04]`, `files_modified: [tests/backends/test_contract.py]` (single file). Body (lines 141-174) renders the parametrised test using the existing `backend` fixture (tests/backends/conftest.py parametrises across `local`, `mock_slurm`, `slurm`, `ray` with `pytest.importorskip` for the latter two). LocalBackend branch asserts `isinstance(report, HealthReport)` plus the 8-field frozen-dataclass shape (lines 152-169); distributed branch asserts `pytest.raises(NotImplementedError, match=r"healthcheck deferred to Phase 7\+ for distributed backends")` (lines 171-173). HealthReport import is added to the existing `from automil.backends.base import JobHandle, JobState` line (07-04b:127). 07-11's clause-10 grep was extended to verify the new test (07-11-PLAN.md:327-331). PLAN-SUMMARY.md updated: plan count 11→12, wave map shows `07-04 ‖ 07-04b`, dependency graph notes 07-04b and 07-11.depends_on includes 07-04b. |

---

## 3. Side-Effect Scan (new issues from iter-2 fixes)

Each iter-2 patch was scanned for collateral damage. Findings:

### 3a. F-02 daemon-subprocess approach — PATH dependency

The new 07-09 strategy invokes `automil` as a console-script via PATH (`subprocess.Popen(["automil", ...])`). Risk: in stripped CI images without the entry point installed, all 3 tests skip. **Mitigated correctly:** the skipif decorator gates on `shutil.which("automil") is not None`; under `uv run pytest` and `pip install -e .` shells (Leo's actual workstation per CLAUDE.md "Commands" block), `automil` IS on PATH. The plan's `<done>` block (07-09:326) explicitly accepts both PASS (PATH available) and clean SKIP (PATH absent). No new issue.

A more robust alternative (`subprocess.run([sys.executable, "-m", "automil", ...])`) would avoid the PATH dependency, but the current `pyproject.toml` defines the entry point only via `[project.scripts]` not as `python -m automil`, so `python -m automil` would fail. The PATH-based approach is the correct call given current packaging.

### 3b. F-03 tmp-project fixture — git init requirement

`cli/init.py:202-208` raises `ClickException("Not inside a git repository...")` if `_find_git_root` walks fail. The new clause-9 test explicitly runs `git init -q`, configures `user.email`/`user.name` (required for the auto-commit Phase 6 may emit), stages, and commits before invoking `automil init --no-healthcheck` (07-11-PLAN.md:286-290). **No issue.** The test honors the precondition.

A minor note: the test does NOT change CWD into `repo`; instead it passes `cwd=repo` to each subprocess. Since `automil init` calls `Path.cwd()` (cli/init.py:199) which is the subprocess CWD (set by Popen `cwd=`), this works. No collision with parent-test CWD.

### 3c. F-05 07-04b file-disjointness with 07-04

`07-04`'s `files_modified` (07-04-PLAN.md:7-11): `slurm.py`, `ray.py`, `mock_slurm.py`, `tests/backends/test_distributed_healthcheck_deferred.py`. `07-04b`'s `files_modified` (07-04b-PLAN.md:7-8): `tests/backends/test_contract.py` only. **Zero overlap** — file-disjoint confirmed.

**Sequencing note (LOW / informational, not an issue):** 07-04b's `depends_on: [07-01, 07-03, 07-04]` includes 07-04. The PLAN-SUMMARY's wave map (line 18) labels these as `07-04 ‖ 07-04b` (parallel within Wave 3), but the dependency graph (line 33) accurately states 07-04b depends on 07-04 having landed first. In practice the wave executor will run 07-04 first then 07-04b within Wave 3, which is sequential not parallel. This is internally inconsistent but file-disjoint and harmless: if the executor honors `depends_on` it sequences correctly; if it ignores `depends_on` and runs them in parallel, file-disjointness still prevents conflict (07-04b's parametrised test only fails if 07-04's source edits haven't landed, which would be caught at test-execute time, not commit-time). **Not a BLOCKER, not a HIGH; LOW informational note for the orchestrator.** Suggested copy-edit (out of scope for iter-2): change wave-map line 18 to `07-04 → 07-04b` to match the dependency graph.

### 3d. PLAN-SUMMARY dependency graph

PLAN-SUMMARY.md was correctly updated:
- Plan count 11→12 (line 6)
- Wave map shows 07-04b in Wave 3 (line 18)
- Dependency arrows under "Dependency Graph" (lines 149-178) include 07-04b at the right level
- 07-11 depends_on (07-11-PLAN.md:6) lists `[07-01, 07-02, 07-03, 07-04, 07-04b, 07-05, 07-06, 07-07, 07-08, 07-09, 07-10]` — 11 deps, matches summary claim of "ALL prior 11 plans"
- Test count trajectory updated to include the new +4 cases from 07-04b (line 205)
- "Iter-2 fixes applied" table at lines 105-112 enumerates F-01..F-05 with file/region pointers

No graph corruption. No missing entries.

---

## 4. Plan Count + Integrity

- **`ls 07-*-PLAN.md | wc -l` = 12** ✓ (was 11; 07-04b added)
- **Em-dash gate:** `grep -nP "\x{2014}|\x{2013}" .planning/phases/07-*/*-PLAN.md` returns **zero matches** across all 12 plans ✓
- **07-04b frontmatter:** `wave: 3`, `depends_on: [07-01, 07-03, 07-04]`, `files_modified: [tests/backends/test_contract.py]`, `autonomous: true`, `requirements: [STP-01]`, `must_haves` block present ✓
- **Frontmatter validity (other 11 plans):** unchanged from iter-1 (passed); spot-checked 07-09 (depends_on extended to `[07-02, 07-05, 07-08]`) and 07-11 (depends_on extended with 07-04b) ✓

---

## 5. Cross-Cuts Verified

| Concern | Source of truth | Plan location | Status |
|---------|-----------------|---------------|--------|
| `automil orchestrator start/stop` exist | `src/automil/cli/orchestrator.py:17,27` | 07-09:163,172 | ✓ exists |
| `automil submit --max-time` flag | added by 07-02 (Wave 1) | 07-09:223 | ✓ depends_on chain valid |
| `automil init --no-healthcheck` flag | added by 07-05 (Wave 4) | 07-11:293, 07-09:142 | ✓ 07-11 depends on 07-05; 07-09 depends on 07-05 |
| `tests/backends/conftest.py` `backend` fixture | exists with 4-branch local/mock_slurm/slurm/ray | 07-04b:141 (uses fixture by name) | ✓ matches existing pattern |
| `HealthReport` dataclass field shape | added by 07-01 (Wave 1) | 07-04b:157-161, 07-11:157-161 | ✓ both consumers cite the same 8-field set |
| Locked D-189 NotImplementedError prefix | added by 07-04 (Wave 3) | 07-04b:149 (regex `Phase 7\+`) | ✓ regex prefix matches the 07-04 message |
| CHANGELOG existing heading shape inspected | `CHANGELOG.md:5` (`## 6.0.0 — Phase 6 ...`) | 07-11:399 chooses `## 7.0.0 - Phase 7 ...` (ASCII hyphen) | ✓ deliberate divergence justified by no-em-dash rule |

---

## 6. Recommended Action

**Proceed to `/gsd-execute-phase 7`.**

All 5 iter-1 findings (F-01 BLOCKER + F-02..F-05 HIGH) are resolved with concrete, evidence-backed fixes. No new BLOCKERs or HIGHs were introduced by the patches. One LOW informational note on the wave-3 sequencing label is non-blocking and can be addressed by a future copy-edit if desired.

Wave 1 plans are 07-01 (HealthReport ABC + dataclass on `src/automil/backends/base.py`) and 07-02 (`--max-time SECONDS` flag on `src/automil/cli/submit.py`). Both are file-disjoint and can run in parallel.

**Iteration:** 2 of (max) 3. Verdict reached at iteration 2; no further plan-check round needed before execute.

---

## 7. Optional Follow-Ups (not blocking)

These were noted during iter-2 audit but are out of scope for the F-01..F-05 verification:

1. PLAN-SUMMARY.md wave-map line 18: change `07-04 ‖ 07-04b` to `07-04 → 07-04b` to match the actual dependency graph (07-04b depends_on includes 07-04). Cosmetic; the executor honors depends_on regardless.
2. Iter-1 MEDIUM findings (F-06 cwd-leak in `_run_gate`, F-07 `_stamp_healthcheck_defaults` insertion order, F-08 cross-wave config-stub drift) and LOW findings (F-09 pre-existing em-dashes in base.py, F-10 conditional codex frontmatter strip) were not re-audited per iter-2 scope; the orchestrator may choose to address them in a follow-up revision or accept them as pre-existing technical debt.
