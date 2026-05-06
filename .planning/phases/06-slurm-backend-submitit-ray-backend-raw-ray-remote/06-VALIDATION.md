---
phase: 6
slug: slurm-backend-submitit-ray-backend-raw-ray-remote
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Extracted from `06-RESEARCH.md` § Validation Architecture (lines 547–586) and reconciled against API corrections (D-155, D-159, D-164/165, D-174 — see RESEARCH.md § Open Questions for the Planner).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=9.0.2 (existing — pyproject.toml [dependency-groups.dev]) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `uv run pytest tests/backends/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~50–60 seconds (full suite — Phase 5 baseline 779 + Phase 6 additions) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/backends/ -x -q`
- **After every plan wave:** `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite green + `python scripts/check_backend_isolation.py src/automil/` exits 0 + `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero matches
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Plan IDs (06-01..06-N) are placeholders — populated by gsd-planner. Wave assignments below reflect the dependency-shape sketched in CONTEXT.md `<domain>` (extras + ABC re-exports → SLURM/Ray skeletons → namespacing → log unification → contract test extension → acceptance smoke + CHANGELOG). Tests added in Wave 0 are stubs that fail until the implementing plan lands.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-W0-01 | (Wave 0) | 0 | BCK-05 | V5 / T-06-V5-1 | SLURM directive validator rejects TODO_FILL_IN | unit | `uv run pytest tests/backends/test_slurm_directives.py::test_check_rejects_todo -x` | ❌ Wave 0 | ⬜ pending |
| 06-W0-02 | (Wave 0) | 0 | BCK-05/06 | — | running/ namespace migration guardrail | unit | `uv run pytest tests/backends/test_running_namespace.py -x` | ❌ Wave 0 | ⬜ pending |
| 06-W0-03 | (Wave 0) | 0 | BCK-05/06 | — | conftest extends contract param to [local, mock_slurm, slurm, ray] | unit | `uv run pytest tests/backends/test_contract.py --collect-only -q` | ❌ Wave 0 | ⬜ pending |
| 06-W0-04 | (Wave 0) | 0 | BCK-05/06 | — | log unification stub (archive/<id>/run.log on terminal) | unit | `uv run pytest tests/backends/test_log_unification.py -x` | ❌ Wave 0 | ⬜ pending |
| 06-W0-05 | (Wave 0) | 0 | BCK-05/06 | — | node_0176-equivalent acceptance smoke parametrised | integration | `uv run pytest tests/backends/test_node_0176_smoke.py --collect-only -q` | ❌ Wave 0 | ⬜ pending |
| 06-W0-06 | (Wave 0) | 0 | BCK-05 | T-06-V5-2 | requires_slurm marker registered in pyproject.toml | unit | `uv run pytest --markers \| grep requires_slurm` | ❌ Wave 0 | ⬜ pending |
| 06-W0-07 | (Wave 0) | 0 | BCK-06 | T-06-V5-3 | requires_ray marker registered in pyproject.toml | unit | `uv run pytest --markers \| grep requires_ray` | ❌ Wave 0 | ⬜ pending |
| 06-NN-01 | TBD | 1 | BCK-05 | — | `[slurm]` extra installable; SLURMBackend importable post-install | unit | `pip install -e '.[slurm]' && uv run python -c 'import automil.backends.slurm'` | ❌ | ⬜ pending |
| 06-NN-02 | TBD | 1 | BCK-06 | — | `[ray]` extra installable; RayBackend importable post-install | unit | `pip install -e '.[ray]' && uv run python -c 'import automil.backends.ray'` | ❌ | ⬜ pending |
| 06-NN-03 | TBD | 2 | BCK-05 | — | SLURMBackend passes contract test (DebugExecutor in-process) | contract | `uv run pytest tests/backends/test_contract.py -k slurm -x` | ❌ | ⬜ pending |
| 06-NN-04 | TBD | 2 | BCK-06 | — | RayBackend passes contract test (local cluster) | contract | `uv run pytest tests/backends/test_contract.py -k ray -x` | ❌ | ⬜ pending |
| 06-NN-05 | TBD | 3 | BCK-05/06 | — | running/<backend>/<id>.json namespacing applied across daemon + cli | unit | `uv run pytest tests/backends/test_running_namespace.py -x` | ❌ | ⬜ pending |
| 06-NN-06 | TBD | 4 | BCK-05/06 | — | archive/<id>/run.log unification on terminal-state observation | integration | `uv run pytest tests/backends/test_log_unification.py -x` | ❌ | ⬜ pending |
| 06-NN-07 | TBD | 5 | BCK-05/06 | — | node_0176-equivalent composite within ±0.005 across [local, slurm-debug, ray-local] | integration | `uv run pytest tests/backends/test_node_0176_smoke.py -x` | ❌ | ⬜ pending |
| 06-NN-08 | TBD | 5 | BCK-05/06 | — | BCK-04 lint clean (no process-control in slurm.py + ray.py) | lint | `python scripts/check_backend_isolation.py src/automil/` | ✅ (existing) | ⬜ pending |
| 06-NN-09 | TBD | 6 | BCK-05/06 | — | Framework purity: zero autobench refs in src/automil/backends/ | grep | `! grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` | ✅ (existing) | ⬜ pending |
| 06-NN-10 | TBD | 6 | BCK-05/06 | — | Phase 5 baseline preserved (779 tests + 9 skipped → ≥789 with Phase 6 additions) | full | `uv run pytest tests/ --collect-only \| tail -1` | ✅ (existing) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> Wave 0 (per `references/nyquist.md`): test scaffolding installed BEFORE implementation plans run, so every implementation task has a failing test it can flip to green. The planner must include a Wave 0 plan that lands these stubs.

- [ ] `tests/backends/conftest.py` — extend the existing `params=` list to include `"slurm"` and `"ray"` parametrisation. The conftest fixture must:
  - Build `SLURMBackend(automil_dir, config_with_debug=True)` for `"slurm"` (uses submitit `cluster="debug"` AutoExecutor)
  - Build `RayBackend(automil_dir, config)` for `"ray"`; on session-start, `ray.init(ignore_reinit_error=True)`; on session-teardown, `ray.shutdown()` if `_we_started_ray=True`
- [ ] `tests/backends/test_slurm_directives.py` — SLURM directive validator stubs:
  - `test_check_rejects_todo` — `automil check` raises `SlurmDirectivesIncompleteError` when any `backend.slurm.directives.*` value contains `TODO_FILL_IN`
  - `test_check_accepts_complete` — `automil check` passes when all required keys present and no TODO sentinels
  - `test_walltime_seconds_to_timeout_min` — directive builder converts `walltime_seconds` → `timeout_min = max(1, walltime_seconds // 60)` (per RESEARCH.md OQ-1 correction)
- [ ] `tests/backends/test_running_namespace.py` — namespace migration tests:
  - `test_running_dir_per_backend` — daemon resolves `running_dir = orch_dir / "running" / backend_name`
  - `test_daemon_refuses_flat_running` — daemon startup raises if flat `running/*.json` exists with no namespaced subdirs
  - `test_namespace_isolation` — backend A's running entries don't appear in backend B's `list_running()`
- [ ] `tests/backends/test_log_unification.py` — log unification tests:
  - `test_archive_run_log_local` — terminal-state observation drains `LocalBackend.log_iter()` into `archive/<id>/run.log`
  - `test_archive_run_log_slurm` — same for SLURMBackend (DebugExecutor)
  - `test_archive_run_log_ray` — same for RayBackend (local cluster)
  - `test_log_iter_close_60s_timeout` — orchestrator force-closes log iterator at 60s post-terminal (D-170)
- [ ] `tests/backends/test_node_0176_smoke.py` — acceptance smoke parametrised over `[local, slurm-debug, ray-local]`:
  - `test_node_0176_equivalent_composite_within_tolerance` — runs CCRCC `node_0176`-equivalent variant; asserts `result.json` composite within ±0.005 of LocalBackend baseline
- [ ] `tests/backends/test_contract_real_slurm.py` — `@pytest.mark.requires_slurm` (skip in CI; nightly only) — same scenarios as in-process contract test, against real `cluster="slurm"` AutoExecutor
- [ ] `tests/backends/test_contract_real_ray.py` — `@pytest.mark.requires_ray` (skip in CI; nightly only) — same scenarios against real Ray cluster (`RAY_ADDRESS=auto`)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — register markers:
  ```toml
  markers = [
    "requires_slurm: requires SLURM cluster (skip in CI)",
    "requires_ray: requires real Ray cluster (skip in CI)",
  ]
  ```
- [ ] `scripts/check_backend_isolation.py` — already exists (Phase 2 D-64); Wave 0 verifies `slurm.py` + `ray.py` are NOT added to the allowlist (the implementations should not need process-control primitives — submitit + ray APIs are sufficient)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real SLURM cluster end-to-end | BCK-05 success #5 ("SLURM-installed user runs CCRCC variant end-to-end") | Requires actual SLURM cluster; CI uses DebugExecutor only | (a) On a SLURM-equipped machine: `pip install -e '.[slurm]'`; (b) configure `automil/config.yaml: backend.name: slurm` with valid `directives` (partition, account, etc.); (c) `automil submit --node node_0176 --desc "real-cluster smoke"`; (d) verify `result.json` composite matches LocalBackend baseline within ±0.005 |
| Real Ray multi-node cluster | BCK-06 (implicit) | Requires multi-node Ray cluster; CI uses single-node `ray.init()` | (a) Multi-node Ray cluster running with `ray start --head` + workers; (b) `pip install -e '.[ray]'`; (c) `RAY_ADDRESS=ray://head:10001 automil submit --node node_0176`; (d) verify worker actor placement spans nodes; (e) `result.json` composite within ±0.005 |
| `--signal=B:TERM@30` cap-fire end-to-end on real SLURM | BCK-05 success #1 (signal honors cap contract) | Requires real SLURM `scancel --signal=TERM` + 30s grace; DebugExecutor doesn't simulate signals | (a) Set `cap.budget_seconds: 30, cap.safety_buffer_seconds: 5` and submit a node that runs longer than 30s; (b) verify SLURM emits SIGTERM 30s before TIMEOUT; (c) verify `register_sigterm_flush` in user training script runs; (d) verify node terminates with `metadata.budget_killed: true` and `JobState.BUDGET_KILLED` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (TBD by planner — populated when plans are written)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (TBD by plan-checker)
- [ ] Wave 0 covers all MISSING references — see Wave 0 Requirements above (8 stubs + marker registration)
- [ ] No watch-mode flags (uv run pytest is one-shot; no `--watch` in any command)
- [ ] Feedback latency < 60s (full suite ~50s; per-task target ~5s)
- [ ] `nyquist_compliant: true` set in frontmatter (after planner populates per-task verify map for every plan)

**Approval:** pending — populated by gsd-planner Wave 0 plan + gsd-plan-checker Dimension 8 verification.
