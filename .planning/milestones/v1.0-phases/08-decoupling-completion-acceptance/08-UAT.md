---
phase: 08-decoupling-completion-acceptance
uat_date: 2026-05-08
mode: autonomous-bash-verifiable
result: 30 passed, 0 failed
issues: 0
---

# Phase 8 UAT: Decoupling completion + final acceptance

**Mode:** Autonomous bash-verifiable surfaces (mirroring Phase 6 / Phase 7 UAT pattern)
**Runner:** `/tmp/phase8_uat_runner.py`
**Result:** 30 / 30 PASS, 0 issues

## Test results

| # | Surface | Result | Maps to |
|---|---------|--------|---------|
| T01 | Framework purity grep gate (`tests/test_framework_purity.py`) | PASS | DEC-01 / D-206 |
| T02 | `examples/sklearn-iris/train.py` exists | PASS | DEC-02 / D-203 |
| T03 | `examples/sklearn-iris/automil/config.yaml` exists | PASS | DEC-02 / D-203 |
| T04 | `train.py` length <= 80 lines (D-203 length cap) | PASS | DEC-02 / D-203 |
| T05 | `train.py` zero `automil.*` imports (framework-pure) | PASS | DEC-02 |
| T06 | `src/automil/schemas/result.schema.json` exists | PASS | DEC-03 / D-201 |
| T07 | `automil.schemas.validate_result` importable | PASS | DEC-03 / D-201 |
| T08 | Schema validation tests pass | PASS | DEC-03 / D-201 |
| T09 | `graph.py` zero named val_auc/val_bacc copies | PASS | DEC-04 / D-200 |
| T10 | `graph.py` uses `node["metrics"] = dict(metrics)` pattern | PASS | DEC-04 / D-200 |
| T11 | Dict-spread regression tests pass | PASS | DEC-04 / D-200 |
| T12 | `_validate_env_required` in `cli/check.py` | PASS | DEC-05 / D-202 |
| T13 | `config.yaml.j2` has `env:` block | PASS | DEC-05 / D-202 |
| T14 | `config.yaml.j2` has `scoring:` block (F-07 fix) | PASS | DEC-04 / F-07 |
| T15 | env.required validator tests pass (incl. F-05 non-list warning) | PASS | DEC-05 / F-05 |
| T16 | `docs/training-script-contract.md` exists | PASS | DEC-06 / D-204 |
| T17 | Contract docs cover 6 contract items (test_phase8_docs_exist) | PASS | DEC-06 / D-204 |
| T18 | Sub-gate B sklearn-iris end-to-end PASS via real orchestrator subprocess | PASS | DEC-07 / D-205 / F-04 |
| T19 | `_orchestrator_daemon.py` zero AUTOBENCH_ROOT injection | PASS | DEC-01 / D-199 |
| T20 | `_orchestrator_daemon.py` zero PYTHONPATH benchmarks injection | PASS | DEC-01 / D-199 |
| T21 | D-208 11-clause acceptance gate PASS (11/11) | PASS | DEC-01..07 / D-208 |
| T22 | CHANGELOG.md has `## 8.0.0` heading | PASS | F-04 |
| T23 | CHANGELOG has 4-cell migration matrix (F-06) | PASS | F-06 |
| T24 | `[examples-iris]` extra defined in pyproject.toml | PASS | DEC-02 |
| T25 | `requires_ccrcc_data` marker registered | PASS | D-205 |
| T26 | STATE.md `status: complete` | PASS | milestone close |
| T27 | ROADMAP shows v1.0 SHIPPED 2026-05-08 | PASS | milestone close |
| T28 | git tag `v1.0` exists | PASS | milestone close |
| T29 | `milestones/v1.0-ROADMAP.md` archived | PASS | milestone close |
| T30 | Zero em/en dashes in Phase 8 src files | PASS | feedback_no_em_dashes |

## Summary

All 30 bash-verifiable surfaces PASS. The single failure during initial run (T21 D-208 clause 11) was a milestone-close artifact: REQUIREMENTS.md had been archived to `milestones/v1.0-REQUIREMENTS.md` per the standard `/gsd-complete-milestone` workflow, but the acceptance test was still anchored to the original path. Fix at commit `2c50b54` extends clause 11 to honor the archive layout (falls back to milestones/v1.0-REQUIREMENTS.md when REQUIREMENTS.md is absent post-close).

## Gaps (deferred, not UAT blockers)

These items remain workstation-data-gated and were documented in the milestone audit + STATE.md Deferred Items section:

1. **Sub-gate A: CCRCC `node_0176` ±0.005 reproduction** — requires `AUTOBENCH_CCRCC_ROOT` env var pointing to real CCRCC dataset. Test exists at `tests/acceptance/test_final_phase8_acceptance.py::test_subgate_a_ccrcc_node_0176_reproduction` behind `@pytest.mark.requires_ccrcc_data`. Skips cleanly when data unavailable.
2. **Sub-gate C: heterogeneous consumers** — sklearn-iris + CCRCC variants registered side-by-side in same project. Body is `pytest.skip()` per 08-09 deferred decision; workstation completion needed.
3. **Real SLURM cluster verification** (BCK-05 success criterion 5) — `tests/backends/test_contract_real_slurm.py` behind `@pytest.mark.requires_slurm`, runs nightly when Leo provisions a real cluster.
4. **Real Ray multi-node cluster verification** (BCK-06) — same pattern with `@pytest.mark.requires_ray`.
5. **External hardware shapes** (CPU-only laptop, ROCm system) per Phase 7 D-197 MEDIUM portability.
6. **3 pre-existing tick_cells failures** (Phase 4-origin) — documented as Phase 6 follow-up #1.
7. **Phase 5 calibration pilot K-determination** — Leo runs with CCRCC + CLWD cells.

## Recommended next steps

Phase 8 acceptance is complete. The deferred items are workstation-environment-dependent and do not block v1.0 shipping (already tagged at `v1.0`).

- Run sub-gates A/C when next on workstation: `AUTOBENCH_CCRCC_ROOT=... uv run pytest tests/acceptance/test_final_phase8_acceptance.py -v`
- Provision SLURM/Ray clusters and run nightly: `uv run pytest tests/backends/ -m requires_slurm` (or `requires_ray`)
- For v1.1+, address the 3 pre-existing tick_cells failures and the calibration pilot K-determination

`v1.0` is shipped. `git push origin v1.0` to publish the tag.
