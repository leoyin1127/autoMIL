# 05-VALIDATION.md — Phase 5 validation matrix (Nyquist compliance)

**Phase:** 5 — Generalization gate
**Source:** Extracted from 05-RESEARCH.md §"Validation Architecture" (committed 5a704f2). Standalone artifact required because `.planning/config.json` sets `workflow.nyquist_validation: true`.

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/gate/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Plan |
|--------|----------|-----------|-------------------|------|
| GTE-01 | `candidate` status exists; manifest format | unit | `pytest tests/gate/test_manifest.py -v` | 05-02 |
| GTE-01 | candidate node carries gate_manifest reference | integration | `pytest tests/gate/test_two_stage_gate.py -v` | 05-07 |
| GTE-02 | manifest pre-registered + git-committed BEFORE search | unit | `pytest tests/gate/test_manifest.py::test_manifest_committed_before_first_candidate` | 05-02 |
| GTE-02 | manifest immutability + retire flow | unit | `pytest tests/gate/test_manifest.py::test_manifest_immutable_retire` | 05-02 |
| GTE-03 | Backend.submit() called with metadata.gate_eval=true | unit (MockSLURM) | `pytest tests/gate/test_evaluate.py::test_evaluate_uses_backend_submit` | 05-06 |
| GTE-03 | gate_eval edge type marked on child nodes | unit | `pytest tests/gate/test_evaluate.py::test_gate_eval_edge_type` | 05-06 |
| GTE-03 | JobSpec.metadata accepts arbitrary key-value tuples | unit | `pytest tests/backends/test_jobspec_metadata.py` | 05-03 |
| GTE-04 | paired Wilcoxon p-value computation | unit (pure scipy) | `pytest tests/gate/test_stats.py::test_paired_wilcoxon` | 05-01 |
| GTE-04 | bootstrap CI on median delta (BCa method, 1000 reps) | unit | `pytest tests/gate/test_stats.py::test_bootstrap_ci` | 05-01 |
| GTE-04 | Bonferroni correction direction (alpha/K, NOT multiply p-values) | unit | `pytest tests/gate/test_stats.py::test_bonferroni_direction` | 05-01 |
| GTE-04 | K and p_threshold are config-set, not hardcoded | unit | `pytest tests/gate/test_manifest.py::test_manifest_carries_K_pthreshold` | 05-02 |
| GTE-05 | manual nomination is default (`gate.auto_nominate: false`) | unit | `pytest tests/gate/test_nominate.py::test_auto_nominate_off_by_default` | 05-04 |
| GTE-05 | `automil nominate <node>` mutates status | unit | `pytest tests/gate/test_nominate.py::test_nominate_mutates_status` | 05-04 |
| GTE-05 | `automil nominate` CLI top-level command | CLI integration | `pytest tests/test_cli_nominate.py` | 05-09 |
| GTE-06 | promotion_rate metric computation | unit | `pytest tests/gate/test_promote.py::test_promotion_rate` | 05-07 |
| GTE-06 | promotion_rate exposed in viz `/api/promotion-rate` SSE | integration | `pytest tests/test_viz_promotion_rate.py` | 05-10 |
| GTE-06 | promotion_rate exposed in `automil status` text output | CLI integration | `pytest tests/test_cli_status_promotion_rate.py` | 05-10 |
| Pitfall 6 (LOAD-BEARING) | held-out cells invisible to agent — full nomination→eval→promote→trajectory-leak verification | acceptance gate | `pytest tests/gate/test_pitfall6_held_out_isolation.py` | 05-11 |
| Held-out isolation | trajectory.jsonl placeholder substitution for held-out node IDs | unit | `pytest tests/trajectory/test_held_out_redaction.py` | 05-05 |
| Held-out isolation | `automil rank` filters held-out by default; `--include-held-out` logs WARNING | CLI integration | `pytest tests/test_cli_rank_held_out.py` | 05-05 |
| BCK-04 (gate) | zero process-control refs (`os.getpid`/`os.kill`/`Popen`/`.pid`) in `src/automil/gate/` | lint | `pytest tests/test_backend_isolation_lint.py` (allowlist extension) | 05-11 |
| Framework purity | zero `autobench`/`AUTOBENCH_`/`benchmarks/` in `src/automil/gate/` | lint | `pytest tests/gate/test_framework_purity.py` (mirrors `tests/cells/` purity check) | 05-11 |
| Calibration pilot (D-151) | empirical K determined against `node_0176`-equivalent change on 3-5 fresh cells | sign-off | `.planning/phase-05-calibration.md` committed | 05-12 |

## ROADMAP Success Criteria → Test Map

Per `.planning/ROADMAP.md` Phase 5 lines 145-149:

| SC# | Criterion | Tests Backing It |
|-----|-----------|------------------|
| 1 | `candidate` status between `executed/keep` and `registered`; gate_manifest committed BEFORE search starts | GTE-01 (test_manifest.py + test_two_stage_gate.py); GTE-02 (test_manifest_committed_before_first_candidate + test_manifest_immutable_retire) |
| 2 | Gate spawns held-out evaluations via `Backend.submit()`; `gate_eval` edge type; auto-nomination OFF by default | GTE-03 (test_evaluate_uses_backend_submit + test_gate_eval_edge_type); GTE-05 (test_auto_nominate_off_by_default) |
| 3 | Paired Wilcoxon + bootstrap CI (1000 reps) + Bonferroni correction; K and p_threshold config-set | GTE-04 (test_paired_wilcoxon, test_bootstrap_ci, test_bonferroni_direction, test_manifest_carries_K_pthreshold) |
| 4 | Promotion-rate metric in viz dashboard + `automil status`; calibration pilot sets initial K | GTE-06 (test_promotion_rate + test_promotion_rate_in_viz_endpoint + test_cli_status_promotion_rate); D-151 (Plan 05-12 calibration pilot sign-off) |
| 5 | Held-out cells NEVER visible to agent during search | LOAD-BEARING test_pitfall6_held_out_isolation.py + test_held_out_redaction + test_cli_rank_held_out |

All 5 ROADMAP success criteria are traceable to at least one plan task with verifiable acceptance criteria.

## Sampling Rate

- **Per task commit:** `uv run pytest tests/gate/test_<focused>.py -x -q` (target: <10s)
- **Per wave merge:** `uv run pytest tests/gate/ -v` (target: <60s; pure-function stats + MockSLURM = no real I/O)
- **Phase gate:** `uv run pytest tests/ -v` full suite green before `/gsd-verify-work`
- **Pitfall-6 single-file gate:** `uv run pytest tests/gate/test_pitfall6_held_out_isolation.py -v` MUST pass independently (load-bearing — single-file failure blocks Phase 5 sign-off)

## Wave 0 Gaps (test artifacts to create)

- [ ] `tests/gate/__init__.py` — package marker (Plan 05-01)
- [ ] `tests/gate/conftest.py` — synthetic graph + tmp_path manifest + MockSLURM fixtures (Plan 05-01)
- [ ] `tests/gate/test_stats.py` — covers GTE-04 (pure scipy, no fixtures beyond np.array) (Plan 05-01)
- [ ] `tests/gate/test_manifest.py` — covers GTE-01, GTE-02 (Plan 05-02)
- [ ] `tests/backends/test_jobspec_metadata.py` — covers JobSpec.metadata extension (Plan 05-03)
- [ ] `tests/gate/test_nominate.py` — covers GTE-05 (Plan 05-04)
- [ ] `tests/trajectory/test_held_out_redaction.py` — covers D-139 redactor extension (Plan 05-05)
- [ ] `tests/test_cli_rank_held_out.py` — covers `automil rank --include-held-out` filter (Plan 05-05)
- [ ] `tests/gate/test_evaluate.py` — covers GTE-03 (uses MockSLURMBackend from tests/backends/) (Plan 05-06)
- [ ] `tests/gate/test_promote.py` — covers GTE-06 + two-stage composition (Plan 05-07)
- [ ] `tests/gate/test_two_stage_gate.py` — covers D-143 Stage A + Stage B composition (Plan 05-07)
- [ ] `tests/test_cli_nominate.py` + `tests/test_cli_promote.py` — covers GTE-05 CLI integration (Plan 05-09)
- [ ] `tests/test_viz_promotion_rate.py` + `tests/test_cli_status_promotion_rate.py` — covers GTE-06 surface (Plan 05-10)
- [ ] `tests/gate/test_pitfall6_held_out_isolation.py` — LOAD-BEARING anti-acceptance gate (Plan 05-11)
- [ ] `tests/gate/test_framework_purity.py` — zero autobench refs (mirrors `tests/cells/` purity) (Plan 05-11)
- [ ] `tests/test_backend_isolation_lint.py` extension — assert no `os.kill`/`Popen`/`.pid` in `src/automil/gate/` (Plan 05-11)

## Feedback Latency

- **Per-task feedback (`<verify><automated>`):** ≤10s — focused test file + grep guards on the modified file
- **Wave-merge feedback:** ≤60s — full `tests/gate/` directory
- **Phase-gate feedback:** ≤30s incremental on Phase 4's 644 baseline (target ~700 tests post-Phase-5)

No new framework install needed (scipy 1.17.1 already transitively installed; promoted to core deps in Plan 05-08; BCK-04 lint already exists, allowlist extended in Plan 05-11).

## Anti-acceptance discipline

The Pitfall-6 anti-acceptance gate (Plan 05-11, `tests/gate/test_pitfall6_held_out_isolation.py`) is the goal-backward verifier for Phase 5. It carries 9 load-bearing assertions in a single file (per D-149) and must pass before Phase 5 ships. If any of the 9 assertions split to a separate file, the single-file load-bearing property is broken and the gate becomes weaker.

## Reference

- 05-RESEARCH.md §"Validation Architecture" (the source of this matrix)
- `.planning/config.json` — `workflow.nyquist_validation: true`
- 05-CONTEXT.md D-149 — Pitfall-6 anti-acceptance test specification
- ROADMAP.md Phase 5 §Success Criteria (lines 145-149)
