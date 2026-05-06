---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
last_updated: "2026-05-06T03:30:00.000Z"
progress:
  total_phases: 9
  completed_phases: 6
  total_plans: 60
  completed_plans: 60
  percent: 100
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

**Current focus:** Phase 06 — SLURM + Ray backends (next, depends on Phase 02 ABC + Phase 04 cap contract)

## Current Position

Phase: 05 — COMPLETE
Plan: 12 of 12

- **Phase:** 05 — Generalization gate
- **Plans:** 12 across 9 waves shipped
- **Status:** Phase 05 complete (779 tests + 9 skipped, +113 from 666 Phase-4-end baseline; Pitfall-6 anti-acceptance gate green with all 9 D-149 assertions in single file; gate package fully wired — manifest + stats + nominate + evaluate + promote + 4 CLI subcommands + 2 top-level commands + viz/status promotion_rate metric; framework purity preserved; BCK-04 lint extended to gate/; scipy promoted to core deps; calibration pilot scaffold awaits Leo's follow-up to lock empirical K threshold)
- **Progress (milestone):** [██████░░░░] 67% (6/9 phases shipped, 60/60 known plans complete)
- **Next:** `/gsd-discuss-phase 6` (BCK-05/06 — SLURM + Ray backends; depends on Phase 02 backend ABC + Phase 04 cap contract; parallel-friendly with Phase 7)

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

**Last action:** Phase 05 fully shipped 2026-05-05/06. Executed 12 plans across 9 waves. Wave 1 parallel (05-01 stats.py + 05-03 JobSpec.metadata extension). Wave 2 (05-02 GateManifest persistence + atomic-write-plus-git-commit). Wave 3 parallel (05-04 nominate + graph helpers + 05-05 held-out isolation in trajectory redactor + rank). Wave 4 (05-06 evaluate_candidate via Backend.submit). Wave 5 (05-07 promote two-stage gate). Wave 6 (05-08 automil gate CLI group + scipy lifted to core deps + config.yaml.j2 gate: section). Wave 7 parallel (05-09 nominate/promote top-level CLI + 05-10 viz/status promotion_rate). Wave 8 (05-11 Pitfall-6 anti-acceptance gate — 9 D-149 assertions in single file: synthetic 3-cell graph, manifest registered, search loop, agent-blind verification, nominate, promote, status transitions, gate_eval submit metadata, post-promote trajectory leak verification). Wave 9 (05-12 calibration pilot scaffold + Leo follow-up). Notable: scipy 1.17.1 was already transitively installed; promoted to core deps. JobSpec.metadata kw-only frozen-dataclass field extension was non-breaking. atomic-write-plus-git-commit pattern rollback uses path.unlink + cached-payload restore (NOT git checkout per Leo memory feedback_never_blind_checkout). Bonferroni applied as alpha/K (DIVIDE direction enforced via grep-acceptance + AST guard). 779 tests + 9 skipped (+113 from Phase 4's 666 baseline). Framework purity preserved: zero autobench/AUTOBENCH_/benchmarks/ refs in src/automil/gate/. BCK-04 lint extended to cover gate/ subdirectory. test_pitfall6_held_out_isolation.py is the load-bearing acceptance gate; 35 Pitfall-6 assertion citations in 3 test functions all green.

**Next action:** `/gsd-discuss-phase 6` to begin Phase 6 (BCK-05/06 SLURM backend (submitit) + Ray backend (raw ray.remote)). Phase 6 depends on Phase 2 (Backend ABC) + Phase 4 (cap contract). SLURM `--signal=B:TERM@30` honors the wall-clock contract; Ray `ray.cancel(force=True)` does the same. Both opt-in via pip extras. Parallel-friendly with Phase 7 hardware autodetect.

**Resume file:** None

**To resume in a fresh session:** Read this file first, then `.planning/ROADMAP.md`, then the phase's `00-CONTEXT.md`, then plan files under `.planning/phases/00-tier-2-cleanup-cli-split-compat-shim/plans/` (created by `/gsd-plan-phase`).

---
*State initialised: 2026-05-01 after roadmap creation*
*Phase 0 context gathered: 2026-05-01*
*Mode: yolo, granularity: fine, parallelization: true*
