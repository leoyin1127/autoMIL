# Phase 6 — Plan Summary

**Generated:** 2026-05-06
**Phase:** 06-slurm-backend-submitit-ray-backend-raw-ray-remote
**Total plans:** 10
**Total waves:** 7 (Waves 1–7; 1-indexed per GSD convention)
**Requirements:** BCK-05, BCK-06

---

## Wave Map

| Wave | Plans (parallel within wave) | Theme |
|------|------------------------------|-------|
| **Wave 1** | `06-01` | Test scaffolding — 8 stubs land RED so implementation plans flip them to GREEN |
| **Wave 2** | `06-02` ‖ `06-03` | Foundations — extras + errors (parallel) and config-template + check (parallel) |
| **Wave 3** | `06-04` ‖ `06-05` | Backend implementations — SLURMBackend (parallel) and RayBackend (parallel) |
| **Wave 4** | `06-06` | `running/` namespace migration — breaking change with daemon-refusal-to-start guardrail |
| **Wave 5** | `06-07` | Cross-backend log unification — orchestrator-owned `archive/<id>/run.log` |
| **Wave 6** | `06-08` ‖ `06-09` | Test extensions — contract test parametrise (parallel) and node_0176 smoke (parallel) |
| **Wave 7** | `06-10` | Acceptance gate — single-file 11-clause D-179 verifier |

**Parallel pairs (file-disjoint per execute-phase wave-execution model):**
- Wave 2: `06-02` (pyproject.toml + errors.py + __init__.py) ‖ `06-03` (config.yaml.j2 + cli/check.py) — disjoint ✓
- Wave 3: `06-04` (slurm.py only) ‖ `06-05` (ray.py only) — disjoint ✓
- Wave 6: `06-08` (test_contract.py) ‖ `06-09` (test_node_0176_smoke.py + _smoke_helpers.py) — disjoint ✓

---

## Plan-by-Plan Files Modified

| Plan | Wave | Files | Requirements |
|------|------|-------|--------------|
| `06-01-test-scaffolding.md` | 0 | `tests/backends/conftest.py`, `tests/backends/test_slurm_directives.py`, `test_running_namespace.py`, `test_log_unification.py`, `test_node_0176_smoke.py`, `test_contract_real_slurm.py`, `test_contract_real_ray.py`, `pyproject.toml` | BCK-05, BCK-06 |
| `06-02-extras-and-errors.md` | 1 | `pyproject.toml`, `src/automil/backends/errors.py`, `src/automil/backends/__init__.py` | BCK-05, BCK-06 |
| `06-03-config-template-and-check.md` | 1 | `src/automil/templates/config.yaml.j2`, `src/automil/cli/check.py` | BCK-05, BCK-06 |
| `06-04-slurm-backend.md` | 2 | `src/automil/backends/slurm.py` | BCK-05 |
| `06-05-ray-backend.md` | 2 | `src/automil/backends/ray.py` | BCK-06 |
| `06-06-running-namespace-migration.md` | 3 | `src/automil/backends/_orchestrator_daemon.py`, `src/automil/backends/local.py`, `src/automil/cli/cancel.py`, `src/automil/cli/reconcile.py`, `src/automil/cli/cell.py`, `src/automil/graph.py`, `CHANGELOG.md` | BCK-05, BCK-06 |
| `06-07-log-unification.md` | 4 | `src/automil/backends/_orchestrator_daemon.py` | BCK-05, BCK-06 |
| `06-08-contract-test-extension.md` | 5 | `tests/backends/test_contract.py` | BCK-05, BCK-06 |
| `06-09-node-0176-smoke.md` | 5 | `tests/backends/_smoke_helpers.py`, `tests/backends/test_node_0176_smoke.py` | BCK-05, BCK-06 |
| `06-10-acceptance-gate.md` | 6 | `tests/backends/test_phase6_acceptance.py`, `CHANGELOG.md` | BCK-05, BCK-06 |

**File-disjointness audit:** Wave 2 (06-02 vs 06-03) is disjoint *except* both touch `pyproject.toml` is FALSE — only 06-02 touches pyproject.toml. (06-01 also touches pyproject.toml but Wave 1 runs alone.) Wave 6 (06-08 vs 06-09) — disjoint ✓. Wave 3 (06-04 vs 06-05) — disjoint ✓. No multi-plan-per-wave file conflicts detected.

---

## D-179 Acceptance Gate Cross-Reference

The 11-clause D-179 acceptance gate (CONTEXT.md `<decisions>` § Acceptance) maps to plan satisfaction:

| Clause | Description | Satisfied by |
|--------|-------------|--------------|
| 1 | Contract test passes parametrised over `[Local, MockSLURM, SLURM-DebugExecutor, Ray-local]` (≥10 scenarios per backend) | `06-08` (parametrise extension) — verified by `06-10` |
| 2 | Phase 5's 779-test baseline stays green | All plans (regression-free) — verified by `06-10` |
| 3 | `scripts/check_backend_isolation.py src/automil/` exits 0 (no new process-control refs in slurm.py / ray.py) | `06-04`, `06-05` (no allowlist additions) — verified by `06-10` |
| 4 | `pip install -e .` (no extras) installs cleanly; `automil --help` works; `import automil.backends.slurm` raises ImportError | `06-02` (extras gating) — verified by `06-10` |
| 5 | `pip install -e '.[slurm]'` enables `backend.name: slurm` end-to-end against DebugExecutor | `06-02`, `06-04` — verified by `06-10` |
| 6 | `pip install -e '.[ray]'` enables `backend.name: ray` end-to-end against local cluster | `06-02`, `06-05` — verified by `06-10` |
| 7 | `tests/backends/test_node_0176_smoke.py` passes for all three CI-runnable backends; composite within ±0.005 of LocalBackend baseline | `06-09` — verified by `06-10` |
| 8 | `running/` is namespaced (`running/local/`, `running/slurm/`, `running/ray/`); daemon refuses to start with flat layout | `06-06` (migration + guardrail) — verified by `06-10` |
| 9 | `archive/<id>/run.log` exists for every terminal node; orchestrator-owned via `_atomic_write_lines` | `06-07` (log unification) — verified by `06-10` |
| 10 | `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero matches | `06-04`, `06-05` (purity at write time) — verified by `06-10` |
| 11 | CHANGELOG entry surfaces the breaking `running/` layout change with operator recovery steps | `06-06` (initial draft) + `06-10` (finalize) |

---

## API Corrections Applied (RESEARCH.md → plan body inline)

The planner integrated all 5 API corrections from `06-RESEARCH.md` § Open Questions for the Planner directly into wave-1+ plan bodies, NOT deferred to executors:

| Correction | Locked decision | Plan(s) where applied |
|------------|-----------------|----------------------|
| `timeout_min` (NOT `time=`) | D-155 | `06-04` (SLURM update_parameters) |
| `slurm_additional_parameters={"signal": "B:TERM@30"}` (NOT `signal=`) | D-155 | `06-04` (SLURM update_parameters) |
| `job.paths.stdout` (NOT manual `{job_id}_log.out`) | D-159 | `06-04` (SLURM log_iter) |
| Catch `WorkerCrashedError` in poll exception map | D-164/D-165 | `06-05` (Ray poll exception handler) |
| `ray.init(ignore_reinit_error=True)` (NOT `local_mode=True`) | D-174 | `06-01` (conftest), `06-05` (RayBackend init) |
| Worktree path as explicit function arg (NOT JobSpec field) | D-156, D-162 (RESEARCH OQ-4) | `06-04`, `06-05` (worktree_path arg in remote-exec wrappers) |

---

## Dependency Graph

```
06-01 (Wave 1: scaffolding)
   │
   ├─► 06-02 (Wave 2: extras + errors) ─┐
   │                                    │
   ├─► 06-03 (Wave 2: config + check) ──┤
   │                                    │
   │      ┌─► 06-04 (Wave 3: SLURM) ───┐│
   │      │                            ││
   │      └─► 06-05 (Wave 3: Ray) ─────┤│
   │                                   │ │
   │      ┌─► 06-06 (Wave 4: namespace migration) ─┐
   │      │                                        │
   │      ├─► 06-07 (Wave 5: log unification) ─────┤
   │      │                                        │
   │      ├─► 06-08 (Wave 6: contract test) ───────┤
   │      └─► 06-09 (Wave 6: node_0176 smoke) ─────┤
   │                                               │
   └────────────────► 06-10 (Wave 7: acceptance) ─┘
```

---

## Estimated Execution Cadence

- **Wave 1** (scaffolding): ~30 min — single mechanical plan, RED stubs
- **Wave 2** (foundations, parallel ‖): ~25 min wall — 06-02 ‖ 06-03 in worktrees
- **Wave 3** (backends, parallel ‖): ~45 min wall — 06-04 ‖ 06-05 in worktrees (heaviest plans by line count)
- **Wave 4** (namespace migration): ~30 min — 7-file refactor with guardrail
- **Wave 5** (log unification): ~25 min — single-file _orchestrator_daemon.py extension
- **Wave 6** (test extensions, parallel ‖): ~25 min wall — 06-08 ‖ 06-09 in worktrees
- **Wave 7** (acceptance): ~20 min — single test file aggregating clause checks
- **Total estimated wall-clock:** ~3.0 hours of focused execution
- **Total plans:** 10
- **Wave-execute parallelism savings:** ~30% (3 of 7 waves run 2 plans in parallel)

---

## Plan Quality Self-Audit

**Format compliance:**
- ✓ All 10 plans have valid frontmatter (`wave`, `depends_on`, `files_modified`, `autonomous: true`, `requirements`)
- ✓ All plans declare BCK-05 and/or BCK-06 in `requirements:` (every Phase 6 REQ-ID covered)
- ✓ All tasks include `<read_first>` (analog file from PATTERNS.md + the file being modified + locked-decision file)
- ✓ All tasks include `<acceptance_criteria>` with grep-verifiable conditions
- ✓ All `<action>` blocks contain concrete values (no "align X with Y" without specifics)
- ✓ Wave assignments respect file-disjointness for parallel execution

**Anti-shallow execution defenses:**
- ✓ API corrections applied inline (not deferred to executors)
- ✓ Memory-aligned patterns enforced (atomic-write rollback uses `path.unlink`, never git checkout; framework purity grep gates; BCK-04 lint clean)
- ✓ Wave 1 RED-stubs ensure every implementation task has a failing test it can flip
- ✓ Clause-by-clause D-179 cross-reference in 06-10 makes acceptance gate programmatic, not subjective

**Ready for plan-checker verification.**
