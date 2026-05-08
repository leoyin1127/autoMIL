# Roadmap: autoMIL

## Milestones

- ✅ **v1.0 F2-readiness framework refactor** — Phases 0-8 (shipped 2026-05-08), see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

## Phases

<details>
<summary>✅ v1.0 F2-readiness framework refactor (Phases 0-8) — SHIPPED 2026-05-08</summary>

- [x] Phase 0: Tier 2 cleanup + CLI split + compat shim (7/7 plans, completed 2026-05-01)
- [x] Phase 1: Variant registry + config-driven train + CCRCC reproduction sanity (12/12 plans, completed 2026-05-02)
- [x] Phase 2: Backend ABC + LocalBackend re-export + MockSLURM fixture (8/8 plans, completed 2026-05-03)
- [x] Phase 3: Trajectory recorder + multi-runtime asset reorg (11/11 plans, completed 2026-05-04)
- [x] Phase 4: 6h per-cell hard cap + cell-concept formalization (10/10 plans, completed 2026-05-05)
- [x] Phase 5: Generalization gate (12/12 plans, completed 2026-05-06)
- [x] Phase 6: SLURM backend (submitit) + Ray backend (raw ray.remote) (10/10 plans, completed 2026-05-06)
- [x] Phase 7: Hardware autodetect + /automil-setup skill (12/12 plans, completed 2026-05-07)
- [x] Phase 8: Decoupling completion + acceptance (10/10 plans, completed 2026-05-08)

</details>

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 F2-readiness framework refactor | 9 | 92 | Complete | 2026-05-08 |

## Workstation UAT items deferred to /gsd-verify-work 8

These are workstation-data-gated tests that require Leo's environment with `AUTOBENCH_CCRCC_ROOT` set:

- **Sub-gate A**: CCRCC `node_0176` ±0.005 reproduction (D-205 / DEC-07)
- **Sub-gate C**: heterogeneous consumers (sklearn-iris + CCRCC side-by-side in same project)
- Real SLURM cluster verification (`@pytest.mark.requires_slurm` marker) (BCK-05 success criterion 5)
- Real Ray multi-node cluster verification (`@pytest.mark.requires_ray` marker) (BCK-06)
- External hardware shapes (CPU-only laptop, ROCm system) per Phase 7 D-197 MEDIUM portability

## Pre-existing tech debt for v1.1+

- 3 pre-existing tick_cells failures (Phase 4-origin, documented as Phase 6 follow-up #1)
- Phase 5 calibration pilot K-determination (Leo runs with CCRCC + CLWD cells)
