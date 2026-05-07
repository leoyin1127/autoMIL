---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
last_updated: "2026-05-07T22:35:06.653Z"
progress:
  total_phases: 9
  completed_phases: 7
  total_plans: 82
  completed_plans: 77
  percent: 94
---

# State: autoMIL — F2-readiness framework refactor

## Project Reference

**Project:** autoMIL — F2-readiness framework refactor
**Core Value:** An agent can autonomously discover model improvements for any user's training code under a 6-hour-per-cell budget, with discovered variants reproducible, attributable to their parents, and portable across machines and LLM runtimes.

**Canonical documents** (load these before any phase work):

- `.planning/PROJECT.md` — milestone definition, validated/active/out-of-scope sets, constraints, key decisions
- `.planning/REQUIREMENTS.md` — 69 v1 REQ-IDs across 10 categories (CLN, REG, BCK, TRJ, MRT, CAP, GTE, CLI, STP, DEC) with traceability table
- `.planning/ROADMAP.md` — 9 phases, success criteria, dependency graph, parallel-execution candidates
- `.planning/codebase/` — existing system map (ARCHITECTURE.md, CONCERNS.md, STACK.md). Do NOT re-document.
- `.planning/research/{SUMMARY,STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` — research synthesis informing phase design
- `tasks/automil_qa.md`, `tasks/automil_proposal.md` — design-gap diagnostic + F2 proposal that motivated this milestone
- `CLAUDE.md` — project instructions and Leo's standing directives
- `~/.claude/projects/-home-jma-Documents-yinshuol-autoMIL/memory/MEMORY.md` — Leo's standing memory (saturate GPUs, research before submit, never blind-checkout, architectural-not-hyperparam, never ask continue autonomously)

**Current focus:** Phase 07 — Hardware autodetect + /automil-setup skill (next, depends on Phase 6 framework shape stable)

## Current Position

Phase: 06 (slurm-backend-submitit-ray-backend-raw-ray-remote) — COMPLETE
Plan: 10 of 10

- **Phase:** 06 — SLURM backend (submitit) + Ray backend (raw ray.remote)
- **Plans:** 10 across 7 waves shipped (head `822a146`)
- **Status:** Phase complete — ready for verification
- **Wave execution:** W1 (06-01 scaffolding 6m) → W2 (06-02‖06-03 ~20m wall) → W3 (06-04‖06-05 ~22m wall, both ~420 lines) → W4 (06-06 namespace migration 21m) → W5 (06-07 log unification 15m) → W6 (06-08‖06-09 ~8m wall) → W7 (06-10 acceptance gate 15m). Total wall-clock ~2.0h with parallelism savings from W2/W3/W6.
- **Progress (milestone):** [███████░░░] 78% (7/9 phases shipped, 70/70 plans complete)
- **Next:** `/gsd-verify-work 6` — Phase 6 UAT (autonomous-mode bash-verifiable surfaces).

## Phase 6 follow-ups (deferred — not Phase 6 blockers)

1. **Pre-existing tick_cells failures** (3 tests in `tests/test_tick_cells.py`): `test_tick_cells_active_to_refusing_new`, `test_tick_cells_terminating_fires_cancel_with_cap_reason`, `test_tick_cells_finalized_when_running_empty`. Origin: Phase 4 `_orchestrator_daemon.py:_tick_cells` — the test mocks expect `cells_dir = tmp_path / "automil" / "cells"` but the daemon's actual cells directory resolution may have shifted. Pre-existing at start of Phase 6 session (verified via `git checkout cca0bc0 -- src/automil/backends/_orchestrator_daemon.py` bisection). Not caused by namespace migration. Recommended fix: either (a) Phase 8 cleanup audits Phase 4 wiring, or (b) Leo runs targeted `/gsd-debug` on these 3 specific tests.

2. **Real-cluster verification (BCK-05/06 success criterion 5)**: D-180/D-181 deferred. CCRCC `node_0176`-equivalent end-to-end on a real SLURM cluster + multi-node Ray cluster. Behind `@pytest.mark.requires_slurm`/`requires_ray` markers in `test_contract_real_slurm.py` / `test_contract_real_ray.py` — runs nightly only, not CI.

## Phase 5 Leo Follow-up (deferred — not a blocker for Phase 6)

The calibration pilot (D-151, Plan 05-12) framework-side scaffold is committed at `90011e8`. The actual empirical K-threshold determination requires Leo to:

1. Choose a known-good change (recommended: CCRCC `node_0176` config applied to fresh cells).
2. Pick 3-5 fresh cells (3 CCRCC + 2 CLWD per recommendation).
3. Register a calibration manifest, submit, run `automil promote --calibrate <candidate_id>`.
4. Inspect the delta matrix in `archive/<candidate_id>/gate_evaluation.jsonl` and pick K such that the change passes consistently.
5. Update `.planning/phase-05-calibration.md` with chosen K and rationale; commit.

## Performance Metrics

| Metric | Value | Notes |
|---|---|---|
| Total v1 requirements | 69 | Mapped 100% to phases |
| Total phases | 9 | Phase 0 + 8 substantive |
| Estimated wall-clock work | ~36–44 days | Per research/SUMMARY.md sub-totals |
| Granularity | fine | Per `.planning/config.json` |
| Parallelization | enabled | Phase 6 ↔ Phase 7 are the strongest parallel pair |
| Mode | yolo | Auto-approve gates within roadmap; Leo reviews artifacts |
| Phase 02 P02-01 | 6m | 3 tasks | 5 files |
| Phase 02 P02-06 | 8m | 3 tasks | 1 file |
| Phase 02 P02-07 | 8m | 5 tasks | 5 files |
| Phase 02 P02-08 | 25 | 6 tasks | 5 files |
| Phase 06 P01 | 360 | 3 tasks | 8 files |
| Phase 06 P07 | 900 | 1 tasks | 1 files |

## Accumulated Context

### Decisions logged (from PROJECT.md → ROADMAP.md)

- MockSLURMBackend: PENDING/RUNNING→CRASHED on restart (timer threads cannot resume) — ✓ Done (02-06, 2026-05-02)
- BCK-04 lint allowlist includes viz/server.py (viz daemon PID lifecycle, not job-control) — ✓ Done (02-07, 2026-05-02)
- Registry-first, not config-first, for cross-dataset isolation — Pending (Phase 1)
- Skills only for autonomous setup; CLI for everything else — Pending (Phase 7)
- Pluggable orchestrator backends with `local` as default — Pending (Phase 2 ABC, Phase 6 SLURM/Ray)
- Multi-runtime agent support is in v1, not deferred — Pending (Phase 3)
- 6h cap = per-cell-total, framework-enforced — Pending (Phase 4)
- Search-scope mode flag (`architecture-preserving | free`) — Pending (Phase 1, default `free`)
- autoMIL is generic; autobench is one consumer — Pending (audited in Phase 8)
- Tier 1 mechanical fixes before structural refactor — ✓ Done (5 commits, 2026-05-01)
- `port-variant` and `promote-variant` are CLI, not skills — Pending (Phase 1)

### Critical pitfalls to defend (from research/PITFALLS.md → ROADMAP.md anti-acceptance notes)

- Pitfall 1 (still uses old path) → Phase 1 disable-old gate + protected-files validator
- Pitfall 2 (leaky backend ABC) → Phase 2 MockSLURM in parallel with LocalBackend
- Pitfall 3 (multi-runtime untested-but-claimed) → Phase 3 ≥2 runtimes end-to-end smoke test
- Pitfall 4 (mid-fold guillotine) → Phase 4 per-fold checkpoint protocol ships WITH cap
- Pitfall 5 (trajectory leak/bloat/fossilize) → Phase 3 redaction-on-capture + bounded JSONL + schema-version metadata
- Pitfall 6 (gate calibration) → Phase 5 pre-registered held-out manifest + paired statistical test
- Pitfall 7 (decoupling shipped wrong) → Phase 8 sklearn-iris second consumer before sign-off
- Pitfall 8 (hardware mis-detect) → Phase 7 detect-and-warn pattern + ≥3 hardware shapes
- Pitfall 9 (setup skill mis-scaffold) → Phase 7 mandatory `automil check` + 1-min dry-run gate

### Open questions surfaced by research

- Phase 5 K calibration data missing — pilot in Phase 5 (apply CCRCC `node_0176` to 3–5 fresh cells before locking K)
- Phase 3 Codex/OpenCode/Gemini-CLI runtime hooks — Plan B (`automil trajectory record <event>` CLI subcommand) covers runtimes without native hooks
- Phase 7 hardware test matrix — only workstation available today; ship as "tested on workstation, autodetect REPORTED not silent, override path documented" if external hardware unavailable
- Phase 1 mode default — recommendation: `free` as F2-aligned default; opt-in to `architecture-preserving`; confirm in Phase 1 planning

### Todos / blockers

None at roadmap-creation time. All inputs in place; Leo can review the roadmap and run `/gsd-plan-phase 0` to begin decomposition.

## Session Continuity

**Last action:** Phase 06 CONTEXT bootstrapped autonomously 2026-05-06 (commit `fd3bd6b`). Leo's `/gsd-discuss-phase 6` invocation; presented 4 gray areas via AskUserQuestion (SLURM directives source, Ray init lifecycle, `running/` namespace migration, cross-backend test infra). Leo response: "no need to discuss the engineering/coding level question with me, only feature and user level question needed. You may decide based on best practice and production level experiences." Bootstrapped CONTEXT.md with 37 locked engineering decisions (D-152..D-188). Key resolutions: SLURM directives = framework-mandated (`time` from cap budget, `signal=B:TERM@30` matching Phase 4 D-115) + consumer-supplied (cluster-specific via `automil/config.yaml: backend.slurm.directives` with `automil check` enforcing TODO-sentinel removal); Ray init = hybrid (try `RAY_ADDRESS`, fall back to local) matching FSDP/accelerate pattern; `running/` namespacing = breaking change (CLAUDE.md "no BC hacks" + refactor milestone) with daemon-refusal-to-start guardrail; test infra = parametrised over `[Local, MockSLURM, SLURM-DebugExecutor, Ray-local_mode]` in CI + `requires_slurm`/`requires_ray` markers for nightly real-cluster; one-actor-per-submit on Ray (no multi-fold placement groups) matching Local + SLURM semantics; log unification = orchestrator-owned (drains `backend.log_iter()` into `archive/<id>/run.log` via Phase 0 atomic-write pattern); submitit `Checkpointable` NOT used (D-122 framework-doesn't-inject precludes). Phase 5's prior action notes follow below for continuity.

**Phase 05 prior:** Phase 05 fully shipped 2026-05-05/06. Executed 12 plans across 9 waves. Wave 1 parallel (05-01 stats.py + 05-03 JobSpec.metadata extension). Wave 2 (05-02 GateManifest persistence + atomic-write-plus-git-commit). Wave 3 parallel (05-04 nominate + graph helpers + 05-05 held-out isolation in trajectory redactor + rank). Wave 4 (05-06 evaluate_candidate via Backend.submit). Wave 5 (05-07 promote two-stage gate). Wave 6 (05-08 automil gate CLI group + scipy lifted to core deps + config.yaml.j2 gate: section). Wave 7 parallel (05-09 nominate/promote top-level CLI + 05-10 viz/status promotion_rate). Wave 8 (05-11 Pitfall-6 anti-acceptance gate — 9 D-149 assertions in single file: synthetic 3-cell graph, manifest registered, search loop, agent-blind verification, nominate, promote, status transitions, gate_eval submit metadata, post-promote trajectory leak verification). Wave 9 (05-12 calibration pilot scaffold + Leo follow-up). Notable: scipy 1.17.1 was already transitively installed; promoted to core deps. JobSpec.metadata kw-only frozen-dataclass field extension was non-breaking. atomic-write-plus-git-commit pattern rollback uses path.unlink + cached-payload restore (NOT git checkout per Leo memory feedback_never_blind_checkout). Bonferroni applied as alpha/K (DIVIDE direction enforced via grep-acceptance + AST guard). 779 tests + 9 skipped (+113 from Phase 4's 666 baseline). Framework purity preserved: zero autobench/AUTOBENCH_/benchmarks/ refs in src/automil/gate/. BCK-04 lint extended to cover gate/ subdirectory. test_pitfall6_held_out_isolation.py is the load-bearing acceptance gate; 35 Pitfall-6 assertion citations in 3 test functions all green.

**Next action:** `/gsd-execute-phase 6`. Phase 06 has 10 PLAN.md files + PLAN-SUMMARY + plan-checker PASS-iter-2. Wave-based parallel execution: W0→W1‖→W2‖→W3→W4→W5‖→W6. Estimated ~3.0h focused execution.

**Phase 06 prior session log:** `/gsd-discuss-phase 6` (CONTEXT bootstrapped autonomously per `feedback_decide_engineering_ask_features` — 37 D-152..D-188 engineering decisions, fd3bd6b), `/gsd-plan-phase 6` (researcher sonnet → 5 API corrections, 5bdc1f7; VALIDATION.md 9037ff7; pattern-mapper sonnet 6076ac6; planner opus → 10 plans + summary; plan-checker opus iter-1 BLOCK with 1 blocker + 8 warnings → iter-1 fixes applied inline 2e0a886; plan-checker opus iter-2 PASS).

**Resume file:** None

**To resume in a fresh session:** Read this file first, then `.planning/ROADMAP.md`, then the phase's `00-CONTEXT.md`, then plan files under `.planning/phases/00-tier-2-cleanup-cli-split-compat-shim/plans/` (created by `/gsd-plan-phase`).

---
*State initialised: 2026-05-01 after roadmap creation*
*Phase 0 context gathered: 2026-05-01*
*Mode: yolo, granularity: fine, parallelization: true*
