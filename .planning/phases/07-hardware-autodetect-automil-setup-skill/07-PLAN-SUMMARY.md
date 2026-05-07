# Phase 7 , Plan Summary

**Generated:** 2026-05-07
**Last revised:** 2026-05-07 (Iter-2 fixes applied: F-01..F-05)
**Phase:** 07-hardware-autodetect-automil-setup-skill
**Total plans:** 12 (was 11; 07-04b added in Iter-2 for F-05)
**Total waves:** 7 (Waves 1..7; 1-indexed per GSD convention)
**Requirements:** STP-01, STP-02, STP-03, STP-04, STP-05, STP-06, STP-07

---

## Wave Map

| Wave | Plans (parallel within wave) | Theme |
|------|------------------------------|-------|
| **Wave 1** | `07-01` ‖ `07-02` | Foundations, parallel: HealthReport ABC + dataclass (07-01) and `--max-time SECONDS` flag (07-02). File-disjoint. |
| **Wave 2** | `07-03` | LocalBackend.healthcheck implementation + 6 D-198 clause-1 unit tests. |
| **Wave 3** | `07-04` ‖ `07-04b` | SLURM/Ray/MockSLURM NotImplementedError stubs + deferred-contract test (07-04) ‖ Parametrised healthcheck contract case in `tests/backends/test_contract.py` (07-04b; F-05 fix). File-disjoint. Closes the 07-01 ABC gate fully. |
| **Wave 4** | `07-05` | `automil init` integration: --no-healthcheck flag, _stamp_healthcheck_defaults, config.yaml.j2 stamping, 5 integration tests. |
| **Wave 5** | `07-06` ‖ `07-07` | Skill content rewrite (_shared/automil-setup/SKILL.md) ‖ Codex empty-frontmatter overlay + propagation tests. File-disjoint. |
| **Wave 6** | `07-08` ‖ `07-09` ‖ `07-10` | Idempotency tests ‖ dry-run gate tests (real-CLI-surface, F-02 fix) ‖ Pitfall 8/9 anti-acceptance tests. File-disjoint (each writes its own test file under tests/skills/). |
| **Wave 7** | `07-11` | Acceptance gate: 11-clause D-198 verification in single test file (clause 9 rewritten per F-03; clause 8 anchored per F-04) + CHANGELOG 7.0.0 (heading shape locked per F-04). |

**Parallel pairs (file-disjoint per execute-phase wave-execution model):**
- Wave 1: `07-01` (src/automil/backends/base.py) ‖ `07-02` (src/automil/cli/submit.py + tests/cli/test_submit_max_time.py) , disjoint ✓
- Wave 3: `07-04` (src/automil/backends/slurm.py + ray.py + mock_slurm.py + tests/backends/test_distributed_healthcheck_deferred.py) ‖ `07-04b` (tests/backends/test_contract.py) , disjoint ✓
- Wave 5: `07-06` (src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md) ‖ `07-07` (src/automil/agent_assets/codex/skills/automil-setup/SKILL.md + tests/agent_assets/test_overlay_propagation_phase7.py) , disjoint ✓
- Wave 6: `07-08` (tests/skills/__init__.py + conftest.py + test_setup_idempotency.py) ‖ `07-09` (tests/skills/test_setup_dry_run_gate.py) ‖ `07-10` (tests/skills/test_setup_pitfall_anti_acceptance.py) , file-disjoint ✓ (07-08 owns __init__.py and conftest.py, 07-09 and 07-10 only WRITE their own test files)

**Sequential dependencies:**
- 07-03 depends on 07-01 (uses HealthReport import).
- 07-04 depends on 07-01 (and 07-03 closes the local subclass; 07-04 closes distributed).
- 07-04b depends on 07-01, 07-03, 07-04 (parametrised case asserts both LocalBackend HealthReport return path AND distributed NotImplementedError; needs both ends of the contract in place).
- 07-05 depends on 07-03 (init.py imports + calls LocalBackend().healthcheck()).
- 07-06 depends on 07-02 (skill body invokes `--max-time 60` flag) and 07-05 (skill body references `vram_gb` column resolution).
- 07-07 depends on 07-06 (skill content rewrite must land BEFORE the Codex overlay is stamped against it).
- 07-08 depends on 07-05 (uses init.py + _stamp_healthcheck_defaults).
- 07-09 depends on 07-02 (uses --max-time), 07-05 (uses init), and 07-08 (uses tmp_git_repo fixture from tests/skills/conftest.py).
- 07-10 depends on 07-03 (MIG warning behavior) and 07-05 (rendered config.yaml hardware: section).
- 07-11 depends on ALL prior plans (it is the aggregator gate; depends_on now lists 11 plans including 07-04b).

---

## Plan-by-Plan Files Modified

| Plan | Wave | Files | Requirements |
|------|------|-------|--------------|
| `07-01-PLAN.md` | 1 | `src/automil/backends/base.py` | STP-01 |
| `07-02-PLAN.md` | 1 | `src/automil/cli/submit.py`, `tests/cli/test_submit_max_time.py` | STP-06 |
| `07-03-PLAN.md` | 2 | `src/automil/backends/local.py`, `tests/backends/test_local_healthcheck.py` | STP-01, STP-03 |
| `07-04-PLAN.md` | 3 | `src/automil/backends/slurm.py`, `src/automil/backends/ray.py`, `src/automil/backends/mock_slurm.py`, `tests/backends/test_distributed_healthcheck_deferred.py` | STP-01 |
| `07-04b-PLAN.md` | 3 | `tests/backends/test_contract.py` | STP-01 |
| `07-05-PLAN.md` | 4 | `src/automil/cli/init.py`, `src/automil/templates/config.yaml.j2`, `tests/cli/test_init_healthcheck.py` | STP-02, STP-03 |
| `07-06-PLAN.md` | 5 | `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md` | STP-04, STP-05, STP-06, STP-07 |
| `07-07-PLAN.md` | 5 | `src/automil/agent_assets/codex/skills/automil-setup/SKILL.md`, `tests/agent_assets/test_overlay_propagation_phase7.py` | STP-07 |
| `07-08-PLAN.md` | 6 | `tests/skills/__init__.py`, `tests/skills/conftest.py`, `tests/skills/test_setup_idempotency.py` | STP-05 |
| `07-09-PLAN.md` | 6 | `tests/skills/test_setup_dry_run_gate.py` | STP-06 |
| `07-10-PLAN.md` | 6 | `tests/skills/test_setup_pitfall_anti_acceptance.py` | STP-02, STP-03, STP-04, STP-05 |
| `07-11-PLAN.md` | 7 | `tests/skills/test_phase7_acceptance.py`, `CHANGELOG.md` | STP-01..07 (all) |

**File-disjointness audit:** Wave 1 (07-01 vs 07-02) , disjoint ✓ (base.py vs submit.py + tests/cli). Wave 3 (07-04 vs 07-04b) , disjoint ✓ (07-04 owns three src/automil/backends/*.py files + the dedicated deferred test; 07-04b owns ONLY tests/backends/test_contract.py). Wave 5 (07-06 vs 07-07) , disjoint ✓ (_shared SKILL.md vs codex SKILL.md + tests/agent_assets). Wave 6 (07-08 vs 07-09 vs 07-10) , disjoint ✓ (each writes its own tests/skills/test_*.py file; only 07-08 owns the shared conftest + __init__). 07-11 runs alone in Wave 7. No multi-plan-per-wave file conflicts.

---

## STP Requirement Coverage

Every Phase 7 STP requirement is mapped to at least one plan via the `requirements:` frontmatter:

| Req ID | Description | Primary Plan(s) | Verification Plan |
|--------|-------------|-----------------|--------------------|
| STP-01 | LocalBackend.healthcheck reports GPU/CPU/version | 07-01, 07-03, 07-04, 07-04b | 07-11 clauses 1, 10 |
| STP-02 | automil init pre-fills config.yaml from healthcheck | 07-05 | 07-11 clause 2 |
| STP-03 | Hardware detect = report-not-decide; failures prompt override | 07-03, 07-05 | 07-11 clause 3 |
| STP-04 | /automil-setup skill drafts config + program.md + variants/ skeleton | 07-06 | 07-11 clause 4 |
| STP-05 | Skill is idempotent | 07-06 (content), 07-08 (test) | 07-11 clause 5 |
| STP-06 | Mandatory automil check + 1-min dry-run | 07-02 (--max-time flag), 07-06 (skill body), 07-09 (test) | 07-11 clause 6 |
| STP-07 | Per-runtime overlays (claude/codex/opencode/deepseek) | 07-06 (_shared content), 07-07 (codex empty-frontmatter + propagation test) | 07-11 clause 4 |

---

## D-198 Acceptance Gate Cross-Reference

The 11-clause D-198 acceptance gate (CONTEXT.md `<decisions>` § Acceptance, expanded per Phase 6 D-179 precedent to 11 clauses) maps to plan satisfaction:

| Clause | Description | Satisfied by | Verified by |
|--------|-------------|--------------|-------------|
| 1 | Backend.healthcheck ABC + 6 LocalBackend unit tests pass | 07-01, 07-03 | 07-11 (subprocess pytest invocation) |
| 2 | automil init --no-healthcheck flag + healthcheck stamping | 07-05 | 07-11 clause 2 |
| 3 | Failed detection prompts override (STP-03) | 07-05 (test_init_aborts_on_failed_detection_user_decline) | 07-11 clause 3 |
| 4 | _shared/automil-setup/SKILL.md narrative + overlay rebuild propagation | 07-06, 07-07 | 07-11 clause 4 |
| 5 | tests/skills/test_setup_idempotency.py: zero unprompted changes | 07-08 | 07-11 clause 5 |
| 6 | tests/skills/test_setup_dry_run_gate.py: known-bad config aborts | 07-09 (real-CLI-surface, F-02 fix) | 07-11 clause 6 |
| 7 | Phase 6 baseline preserved; >=10 new tests added | All plans (regression-free) | 07-11 clause 7 (collection count >= 808) |
| 8 | CHANGELOG entry at 7.0.0 BREAKING for Backend.healthcheck | 07-11 (CHANGELOG.md edit; heading shape `## 7.0.0` locked per F-04) | 07-11 clause 8 |
| 9 | automil check passes against a tmp project initialised via `automil init --no-healthcheck` | 07-11 (tmp-project rewrite per F-03) | 07-11 clause 9 |
| 10 | SLURM/Ray Backend.healthcheck raise locked NotImplementedError | 07-04 (dedicated deferred test) + 07-04b (parametrised contract case) | 07-11 clause 10 |
| 11 | Framework purity: zero autobench/AUTOBENCH_/benchmarks/ refs | All plans (purity grep gate per plan) | 07-11 clause 11 |

---

## Iter-2 fixes applied (F-01..F-05)

Plan-check iteration 1 (`07-PLAN-CHECK.md`) returned RETRY with 1 BLOCKER + 4 HIGH findings. All 5 are addressed surgically in this revision; no fundamental rework. Each fix is verifiable from the plan files alone (no executor judgment required).

| ID | Severity | Plan | Fix summary | File / region affected |
|----|----------|------|-------------|------------------------|
| F-01 | BLOCKER | 07-09 | Reordered code blocks in Task 1 action body so `_automil_on_path` helper is defined BEFORE the `@pytest.mark.skipif` decorators that reference it. Added a `## Setup helpers (top of file)` block at the file head. Decorator argument expressions evaluate at module-import time, top-to-bottom; helper-after-decorator triggered NameError at pytest collection time. | `07-09-PLAN.md` Task 1 `<action>` body: helper code block now precedes the test-functions code block. New file uses `_automil_on_path()` (renamed from the unworkable `_orchestrator_supports_one_shot()` of Iter-1). |
| F-02 | HIGH | 07-09 | Dropped the `_process_queue_once`/`_tick_once` private-API coupling entirely. `ExperimentOrchestrator` exposes neither; the Iter-1 helper returned False unconditionally and all 3 dry-run gate tests permanently SKIPPED. New strategy uses the public CLI surface: subprocess-launches `automil orchestrator start`, polls `archive/<id>/result.json`, then issues `automil orchestrator stop`. Skipif gate is `automil`-on-PATH (true under `uv run pytest`). | `07-09-PLAN.md` Task 1 `<action>` body, helper section + `_run_gate` rewrite. `frontmatter.depends_on` updated to `[07-02, 07-05, 07-08]` (now needs the tmp_git_repo fixture from 07-08's conftest). |
| F-03 | HIGH | 07-11 | Rewrote clause-9 test (`test_phase7_acceptance_clause_09_automil_check_passes_on_workstation`) to construct a tmp project via `automil init --no-healthcheck` inside `tmp_path` and run `automil check` against THAT, instead of self-skipping when `_REPO_ROOT / "automil" / "config.yaml"` was absent. The framework repo never has a root-level `automil/config.yaml`; the Iter-1 test would skip 100% of the time. | `07-11-PLAN.md` Task 1 `<action>` body, clause-9 function rewrite. Now PASSES (not skips) when `automil` is on PATH. |
| F-04 | HIGH | 07-11 | Locked CHANGELOG heading shape to `## 7.0.0 - Phase 7 hardware autodetect + automil-setup skill (unreleased)` (no brackets, ASCII hyphen separator) by reading `CHANGELOG.md` head during planning. Phase 6's existing entry uses an em-dash separator; Phase 7 uses ASCII hyphen per Leo's no-em-dash rule. The clause-8 test grep is anchored to `## 7.0.0` exactly, no longer `[7.0.0] OR ## 7.0.0`. | `07-11-PLAN.md` Task 1 clause-8 grep + Task 2 `<action>` body (heading line). Phase 7 acceptance clause 8 grep changed to `assert "## 7.0.0" in text`. |
| F-05 | HIGH | NEW: 07-04b | Added new plan `07-04b-PLAN.md` in Wave 3, file-disjoint from 07-04, that extends `tests/backends/test_contract.py` with the parametrised `test_healthcheck_returns_health_report(backend)` case PATTERNS.md §365-369 prescribed. LocalBackend asserts `isinstance(report, HealthReport)`; distributed backends assert `pytest.raises(NotImplementedError, match=<D-189 prefix>)`. SLURM/Ray cases skip cleanly via `pytest.importorskip` per Phase 6 precedent. | NEW file: `.planning/phases/07-hardware-autodetect-automil-setup-skill/07-04b-PLAN.md`. 07-11 Task 1 clause-10 verification extended to grep for `test_healthcheck_returns_health_report` in test_contract.py. |

**Plan count delta:** 11 → 12 (07-04b added).
**Wave map delta:** Wave 3 widened from `07-04` (single plan) to `07-04 ‖ 07-04b` (parallel pair, file-disjoint).
**07-09 depends_on delta:** `[07-02, 07-05]` → `[07-02, 07-05, 07-08]` (now uses tmp_git_repo fixture from 07-08 conftest).
**07-11 depends_on delta:** added `07-04b` to the aggregator dependency list.

**Em-dash gate post-revision:** `grep -E "—|–" .planning/phases/07-*/*-PLAN.md` returns zero matches (verified after writing 07-09, 07-11, 07-04b).

---

## API Corrections Applied (RESEARCH.md → plan body inline)

The planner integrated all RESEARCH.md OQ resolutions and Pitfall corrections directly into wave-1+ plan bodies, NOT deferred to executors:

| Correction | Source | Locked Decision | Plan(s) where applied |
|------------|--------|-----------------|----------------------|
| `--max-time SECONDS` flag (NOT `--timeout 1`) | RESEARCH.md OQ-5 | D-195 / OQ-5 | 07-02 (flag impl), 07-06 (skill body invocation), 07-09 (test usage) |
| `vram_gb` column (NOT `peak_vram_mb`) in results.tsv reads | RESEARCH.md A1 → planner-resolved by reading `_orchestrator_daemon.py:1289` | OQ-2 / A1 | 07-05 (_stamp_healthcheck_defaults reader), 07-06 (skill body), 07-08 (idempotency seed test) |
| `NVIDIA_SMI_PATH` constant (NOT bare "nvidia-smi") | RESEARCH.md OQ-1 + Pitfall A | D-190 | 07-03 (LocalBackend._healthcheck_cuda) |
| Subprocess catch tuple `(TimeoutExpired, FileNotFoundError, OSError)` matching query_gpus | RESEARCH.md Pattern 1 | D-190 | 07-03 |
| `numpy.quantile(.95)` with statistics-stdlib fallback | RESEARCH.md OQ-2 | D-191 | 07-05 |
| Codex overlay = empty-frontmatter file (option (a), runtime-agnostic merger) | RESEARCH.md Pattern 4 + Pitfall D | D-196 | 07-07 |
| Locked NotImplementedError message verbatim across SLURM/Ray/MockSLURM | RESEARCH.md Hint §906-911 | D-189 | 07-04, 07-04b (parametrised contract assertion) |
| HealthReport NEVER serialized to trajectory output (deferred per OQ-6) | RESEARCH.md OQ-6 + CONTEXT deferred | OQ-6 | 07-01 (HealthReport docstring annotation) |
| AST-walk does NOT recurse into imports; SyntaxError handled cleanly | RESEARCH.md OQ-3 | D-193 | 07-06 (skill body), 07-10 (test_ast_walk_handles_syntax_error_without_executing) |
| Conservative VRAM default `max(8.0, min(gpu_vram_gb) / 8.0)` | RESEARCH.md §Specifics | D-191 | 07-05 |
| Real-CLI-surface for dry-run gate test (no private orchestrator coupling) | F-02 fix; orchestrator API verified at `_orchestrator_daemon.py:1351 (tick) + 1379 (run) + 1446 (cmd_start) + 1510 (cmd_stop)` | D-195 / F-02 | 07-09 (subprocess `automil orchestrator start/stop`) |
| CHANGELOG heading shape `## 7.0.0 ...` (no brackets, ASCII hyphen) | F-04 fix; locked by reading CHANGELOG.md head | D-198 clause 7 / F-04 | 07-11 (Task 2 heading line, Task 1 clause-8 grep) |
| Clause-9 tmp-project rewrite (no self-skip on missing repo-root config) | F-03 fix; framework repo never has root-level `automil/config.yaml` | D-198 clause 9 / F-03 | 07-11 (Task 1 clause-9 rewrite) |
| Parametrised healthcheck contract case in test_contract.py | F-05 fix; PATTERNS.md §365-369 prescription | STP-01 / F-05 | 07-04b (NEW plan) |

**Phase-6 precedent:** all RESEARCH OQ resolutions are pre-applied at plan-writing time, not deferred to executor agents. Executors implement against the resolved API; checker agents verify; no second pass needed.

---

## Dependency Graph

```
07-01 (Wave 1: HealthReport + ABC) ─┐
                                    │
07-02 (Wave 1: --max-time flag) ────┘
   │                                    │
   │      ┌───────────────────────────┐ │
   │      │                           │ │
   ├─► 07-03 (Wave 2: LocalBackend impl + 6 tests) ──┐
   │      │                                          │
   │      ├─► 07-04   (Wave 3: SLURM/Ray/MockSLURM stubs + deferred test) ──┐
   │      ├─► 07-04b  (Wave 3: parametrised healthcheck contract case)      │ (file-disjoint with 07-04)
   │      │                                                                 │
   │      └─► 07-05 (Wave 4: init.py + config.yaml.j2 + 5 integration tests) ──┐
   │                                                                           │
   │                                                                           │
   └────► 07-06 (Wave 5: _shared SKILL.md rewrite ~250 lines) ─────────────────┤
                                                                               │
            07-07 (Wave 5: codex overlay + propagation test) ──────────────────┤
                                                                               │
            07-08 (Wave 6: idempotency tests) ─────────────────────────────────┤
                                                                               │
            07-09 (Wave 6: dry-run gate tests, real-CLI-surface) ──────────────┤
                                                                               │
            07-10 (Wave 6: Pitfall 8/9 anti-acceptance tests) ─────────────────┤
                                                                               │
                                                       ┌───────────────────────┘
                                                       │
                                                       ▼
                                          07-11 (Wave 7: 11-clause acceptance gate + CHANGELOG 7.0.0)
```

---

## Estimated Execution Cadence

- **Wave 1** (foundations, parallel ‖): ~25 min wall , 07-01 (small ABC edit, ~10 min) ‖ 07-02 (flag + 4 tests, ~25 min)
- **Wave 2** (LocalBackend impl): ~50 min , 07-03 is the load-bearing plan with subprocess mocking + 6 tests
- **Wave 3** (distributed stubs + parametrised contract, parallel ‖): ~20 min wall , 07-04 (3 small edits + 1 small test file, ~15 min) ‖ 07-04b (single test extension, ~10 min)
- **Wave 4** (init.py wiring): ~50 min , 07-05 has helpers + Jinja template + 5 integration tests with CliRunner
- **Wave 5** (skill content + propagation, parallel ‖): ~40 min wall , 07-06 (~250-line SKILL.md rewrite, ~30 min) ‖ 07-07 (codex overlay 15 lines + 4 propagation tests, ~25 min)
- **Wave 6** (test triplet, parallel ‖‖): ~35 min wall , 07-08 (3 idempotency tests + conftest fixture) ‖ 07-09 (3 dry-run gate tests with skipif gate) ‖ 07-10 (4 Pitfall anti-acceptance tests)
- **Wave 7** (acceptance gate): ~30 min , 07-11 (11-clause aggregator file + CHANGELOG 7.0.0)
- **Total estimated wall-clock:** ~3.5 hours of focused execution
- **Total plans:** 12 (was 11; 07-04b added)
- **Wave-execute parallelism savings:** ~32% (4 of 7 waves run multiple plans in parallel)

---

## Test Count Trajectory

| Stage | Test count | Delta | Cumulative |
|-------|-----------|-------|------------|
| Phase 6 close (verified during planning) | 848 | , | 848 |
| 07-02 (test_submit_max_time.py: 4 tests) | +4 | 852 | 852 |
| 07-03 (test_local_healthcheck.py: 6 tests) | +6 | 858 | 858 |
| 07-04 (test_distributed_healthcheck_deferred.py: 3 tests) | +3 | 861 | 861 |
| 07-04b (test_contract.py parametrised healthcheck: 4 cases, 2 may skip) | +4 | 865 | 865 |
| 07-05 (test_init_healthcheck.py: 5 tests) | +5 | 870 | 870 |
| 07-07 (test_overlay_propagation_phase7.py: 4 tests) | +4 | 874 | 874 |
| 07-08 (test_setup_idempotency.py: 3 tests) | +3 | 877 | 877 |
| 07-09 (test_setup_dry_run_gate.py: 3 tests, may skip) | +3 | 880 | 880 |
| 07-10 (test_setup_pitfall_anti_acceptance.py: 4 tests) | +4 | 884 | 884 |
| 07-11 (test_phase7_acceptance.py: 11 tests) | +11 | 895 | 895 |
| **Phase 7 close target** | | **+47** | **>=870 (D-198 clause 7 floor)** |

D-198 clause 7 requires ">=10 new tests for STP-01..07"; Phase 7 ships ~47 across 10 new test files / extensions (one new file per Wave 1-6 plan + the test_contract.py extension in 07-04b). The 798 figure cited in CONTEXT.md is the Phase 5 close baseline; the 848 figure is the Phase 6 close (verified by `uv run pytest --collect-only -q | tail -5` during planning).

---

## Plan Quality Self-Audit

**Format compliance:**
- [x] All 12 plans have valid YAML frontmatter (`wave`, `depends_on`, `files_modified`, `autonomous`, `requirements`).
- [x] All 12 plans declare at least one STP requirement; every STP requirement (STP-01..07) is mapped to >=1 plan.
- [x] All tasks include `<read_first>` citing analog files from PATTERNS.md + the file being modified + the locked-decision document.
- [x] All tasks include `<acceptance_criteria>` with grep-verifiable bash one-liners; literal `&&`, `>` (no HTML entities).
- [x] All `<action>` blocks contain concrete values (no "align X with Y" without specifics).
- [x] Wave assignments respect file-disjointness for parallel execution (verified above).
- [x] File naming `07-NN-PLAN.md` (and `07-04b-PLAN.md`); 12 files written.

**Anti-shallow execution defenses:**
- [x] API corrections applied inline (NOT deferred to executors): see "API Corrections Applied" table.
- [x] Memory-aligned patterns enforced: atomic-write rollback uses `path.unlink` (NEVER `git checkout` per `feedback_never_blind_checkout`); framework purity grep gates everywhere; BCK-04 lint clean (no new process-control refs in slurm.py / ray.py / mock_slurm.py / submit.py / init.py).
- [x] No em or en dashes anywhere in plan artifacts (per `feedback_no_em_dashes`); each plan body's "Critical, no em-dashes" check enforces inline.
- [x] D-198 11-clause acceptance gate cross-referenced; single test file (07-11) verifies all 11 clauses programmatically per Phase 6 D-179 precedent.
- [x] Wave-1 RED-stubs implicit: 07-01's HealthReport import is consumed by 07-03 + 07-04 + 07-04b + 07-05; the contract gate is enforced by python's import system, no manual fixture stubs needed.
- [x] Decision-ID traceability: every locked decision (D-189..D-198) is referenced in at least one plan body action block.
- [x] Resolved RESEARCH.md A1 during planning (not deferred): `vram_gb` column verified at `_orchestrator_daemon.py:1289 + 1300`; baked into 07-05 and 07-06 plan bodies.
- [x] Iter-2 fixes applied: F-01 (helper-before-decorator ordering), F-02 (real-CLI-surface for dry-run gate), F-03 (clause-9 tmp-project rewrite), F-04 (CHANGELOG heading anchor), F-05 (parametrised contract case in 07-04b).

**Framework purity verification:**

```bash
# Run after all 12 plans land:
grep -rnE "autobench|AUTOBENCH_|benchmarks/" \
  src/automil/backends/base.py \
  src/automil/backends/local.py \
  src/automil/backends/slurm.py \
  src/automil/backends/ray.py \
  src/automil/backends/mock_slurm.py \
  src/automil/cli/init.py \
  src/automil/cli/submit.py \
  src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md \
  src/automil/agent_assets/codex/skills/automil-setup/SKILL.md \
  src/automil/templates/config.yaml.j2
# Expected: zero matches (07-11 clause 11 verifies)
```

**Em-dash gate verification:**

```bash
grep -rnE "—|–" .planning/phases/07-hardware-autodetect-automil-setup-skill/*-PLAN.md
# Expected: zero matches across all 12 plan files (verified after Iter-2 patches).
```

**Ready for plan-checker iteration 2.**
