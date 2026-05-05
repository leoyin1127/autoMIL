---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: completed
last_updated: "2026-05-05T11:00:00.000Z"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 60
  completed_plans: 48
  percent: 80
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

**Current focus:** Phase 05 — Generalization gate (PLANNED, ready to execute)

## Current Position

Phase: 05 — PLANNED
Plan: 0 of 12

- **Phase:** 05 — Generalization gate
- **Plans:** 12 across 9 waves (W1: 05-01 stats + 05-03 JobSpec.metadata parallel; W2: 05-02 manifest; W3: 05-04 nominate + 05-05 isolation parallel; W4: 05-06 evaluate; W5: 05-07 promote; W6: 05-08 CLI group + scipy core; W7: 05-09 nominate/promote CLI + 05-10 viz parallel; W8: 05-11 Pitfall-6 anti-acceptance; W9: 05-12 calibration pilot Leo checkpoint)
- **Status:** Phase 05 PLANNED (researcher 5a704f2 HIGH confidence; pattern mapper 95daf7d 20 files mapped; planner 3600339 12 plans; plan-checker 2 BLOCKERS + 4 WARNINGS, all 6 addressed inline at 6f5d88b — RESEARCH Open Questions marked RESOLVED, 05-VALIDATION.md created, JobHandle signature corrected, retire_manifest rollback hardened)
- **Progress (milestone):** [█████░░░░░] 56% (5/9 phases shipped, 48/60 plans complete)
- **Next:** `/gsd-execute-phase 5` (Wave 1 parallel: 05-01 stats.py + 05-03 JobSpec.metadata)

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

**Last action:** Phase 05 PLANNING complete (2026-05-05). CONTEXT bootstrapped at 898b526 with D-135..D-151 engineering-locked decisions plus O-01..O-05 OPEN scientific questions (initial K threshold, p_threshold default, held-out selection strategy, calibration pilot scope, auto-nominate scoping). Researcher 5a704f2 HIGH confidence — verified scipy 1.17.1 transitively installed (must lift to core deps in Plan 05-08), JobSpec.metadata kw-only field extension non-breaking, atomic-write-plus-git-commit is a NEW pattern with rollback via path.unlink (NOT git checkout per Leo memory feedback_never_blind_checkout), Bonferroni alpha/K direction (DIVIDE), BCa bootstrap method, mtime-based lru_cache for held-out IDs in trajectory redactor. Pattern mapper 95daf7d mapped 20 files (15 new + 5 modified) — 18/20 with analogs from cells/, trajectory/, cli/cell.py; gate/stats.py + its test are genuinely novel (first scipy usage in src/automil/). Planner 3600339 produced 12 plans across 9 waves with calibration pilot (D-151) as its own plan (05-12, Leo checkpoint). Plan-checker 2 BLOCKERS + 4 WARNINGS, all 6 addressed inline at 6f5d88b: RESEARCH Open Questions marked RESOLVED, 05-VALIDATION.md created (Nyquist compliance), JobHandle field signature pinned correctly (node_id/backend/opaque_id/submitted_at — no job_id), retire_manifest rollback hardened with cached payload restoration.

**Next action:** `/gsd-execute-phase 5` to execute Wave 1 in parallel (05-01 gate/stats.py paired Wilcoxon + bootstrap + Bonferroni; 05-03 JobSpec.metadata kw-only field extension). Pitfall-6 anti-acceptance gate (Plan 05-11) is the goal-backward verifier — must remain single-file load-bearing through execution. Calibration pilot (05-12) requires Leo's manual judgment on K threshold; cannot be fully autonomous.

**Resume file:** None

**To resume in a fresh session:** Read this file first, then `.planning/ROADMAP.md`, then the phase's `00-CONTEXT.md`, then plan files under `.planning/phases/00-tier-2-cleanup-cli-split-compat-shim/plans/` (created by `/gsd-plan-phase`).

---
*State initialised: 2026-05-01 after roadmap creation*
*Phase 0 context gathered: 2026-05-01*
*Mode: yolo, granularity: fine, parallelization: true*
