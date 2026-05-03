---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
last_updated: "2026-05-03T00:00:19.903Z"
progress:
  total_phases: 9
  completed_phases: 2
  total_plans: 27
  completed_plans: 25
  percent: 93
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

**Current focus:** Phase 01 — variant-registry-config-driven-train-py-ccrcc-reproduction-s

## Current Position

Phase: 01 (variant-registry-config-driven-train-py-ccrcc-reproduction-s) — EXECUTING
Plan: 1 of 12

- **Phase:** 0 — Tier 2 cleanup + CLI split + compat shim
- **Plan:** none yet (run `/gsd-plan-phase 0` to decompose)
- **Status:** Executing Phase 01
- **Progress:** [█████████░] 93%

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

**Last action:** Phase 02 Plan 02-07 executed (`5b88e76`). Contract test (14 scenarios, S-01..S-12 parameterised over LocalBackend + MockSLURMBackend), BCK-04 AST lint script (`scripts/check_backend_isolation.py`), always-on pytest gate (`tests/test_backend_isolation_lint.py`). Fixed MockSLURMBackend deadlock in `_transition()`. 414 tests green (394 → 414 +20 passed, 9 skipped).

**Next action:** Continue Phase 02 execution (Wave 5: remaining plans — cancel/resubmit CLI, acceptance gate).

**Resume file:** None

**To resume in a fresh session:** Read this file first, then `.planning/ROADMAP.md`, then the phase's `00-CONTEXT.md`, then plan files under `.planning/phases/00-tier-2-cleanup-cli-split-compat-shim/plans/` (created by `/gsd-plan-phase`).

---
*State initialised: 2026-05-01 after roadmap creation*
*Phase 0 context gathered: 2026-05-01*
*Mode: yolo, granularity: fine, parallelization: true*
