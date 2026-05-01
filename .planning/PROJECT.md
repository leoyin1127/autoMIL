# autoMIL

## What This Is

autoMIL is a generic, agent-driven framework for autonomous experiment search over machine learning training scripts. It provides an experiment-tree, GPU + multi-node orchestrator, and git-worktree overlay runner so an LLM agent can iteratively propose, run, and learn from experiments under a hard time budget. Originally built for Multiple Instance Learning (MIL) benchmarks in computational pathology, the framework is intentionally domain-agnostic and plugs into any benchmark suite or training script.

## Core Value

An agent can autonomously discover model improvements — architectural and training-recipe — for any user's existing training code under a 6-hour-per-cell budget, and the discovered variants are **reproducible, attributable to their parents, and portable across machines and LLM runtimes**.

## Requirements

### Validated

<!-- Inferred from .planning/codebase/ (mapped 2026-04-30). Locked. -->

- ✓ Experiment-tree state machine with UCB-inspired scoring and Pareto-dominance keep/discard — `src/automil/graph.py`
- ✓ Single-machine GPU orchestrator with best-fit bin packing — `src/automil/orchestrator.py`
- ✓ Git-worktree overlay runner for isolated parallel experiments — `src/automil/runner.py`
- ✓ Click-based CLI: `init / submit / propose / rank / reconcile / status / orchestrator / viz` — `src/automil/cli.py`
- ✓ aiohttp + SSE 3D dashboard with vendored d3/three/three-spritetext — `src/automil/viz/`
- ✓ Claude Code skill assets shipping with `automil init` — `src/automil/claude_assets/`
- ✓ 48 passing tests across graph / runner / cli / integration — `tests/`
- ✓ CCRCC benchmark proving the loop on 195+ experiments; honest best `node_0176` (composite 0.8074)
- ✓ Tier 1 framework hardening (gitignore, mark_running guard, process-group kill on timeout, YAML reload logging, best_node correction) — completed 2026-05-01

### Active

<!-- This milestone: framework refactor for F2-readiness. Hypotheses until shipped. -->

- [ ] **Variant registry**: shared library files never edited; mutations land as committed variant modules selected via config. Resolves cross-dataset contamination at the root.
- [ ] **Config-driven `train.py`**: hyperparameters read from YAML; no `args.X = literal` overrides in code.
- [ ] **CLI extensions**: `apply <node>`, `revert-baseline`, `cancel <node>`, `resubmit <node>`, `port-variant <node>`, `promote-variant <node>`, `reconcile --recompute-best`.
- [ ] **6h per-cell hard cap**: framework-enforced wall-clock budget. Orchestrator refuses new submits and terminates running ones when the cell budget hits zero.
- [ ] **Pluggable orchestrator backends**: `local` (default, current code behind a clean interface), `slurm` (HPC), `ray` (cloud / k8s / multi-node general).
- [ ] **Multi-runtime agent support**: reorganize `claude_assets/` → `agent_assets/{claude,codex,opencode,deepseek,...}/`; `automil init` detects/asks which runtime and installs that runtime's skill scaffolding.
- [ ] **Trajectory instrumentation**: every submit snapshots agent prompt + tool-call trajectory to `archive/<node_id>/trajectory.jsonl` for "as-protocol" reproducibility.
- [ ] **Generalization gate inside search loop**: candidate variants must improve on ≥K held-out cells before being promoted to the parent's registered variants directory.
- [ ] **Search-scope mode**: `architecture-preserving` (F1-classic, identity-locked) and `free` (F2-style, full code-level). Same registry, different pre-submit validators.
- [ ] **Decouple framework from autobench**: zero autobench paths, env vars, or training-script schema in `src/automil/`. autobench becomes one of many possible consumers.
- [ ] **`/automil-setup` skill**: bootstraps autoMIL on any existing project — inspects repo, identifies training entry point, drafts config + agent prompt, scaffolds registry, picks defaults from detected hardware. One-shot, autonomous, idempotent.
- [ ] **Hardware auto-detection**: GPU count, accelerator type, available VRAM detected at `init`/start; portable from single-laptop to multi-node HPC without manual config.
- [ ] **Reproduction sanity check**: post-migration, CCRCC `node_0176` reproduces (composite within ±0.005) on the new registry-driven path.

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Full F2 experimental grid (5 parents × 18 cells × 4 recipes × 25 measurements) — own future milestone after the framework is F2-ready
- Paper writing and venue submission — own future milestone
- F1 as originally proposed (architecture-preserving recipe-only standardization paper) — denied; subsumed into F2-style architectural exploration with a `--mode=architecture-preserving` flag for the F1 use case
- Mac / MPS / non-CUDA accelerators — Linux + CUDA only for v1; revisit when there's a real user pulling for it
- Containerized execution (podman / docker isolation) — security-relevant but a major lift; defer
- Anti-starvation aging in the scheduler — defer until observed in practice
- O(N²) → O(N) `recalculate_scores` — defer until graphs exceed ~1k nodes
- Fully orchestrated multi-LLM concurrent runs — multi-runtime *support* is in scope; running e.g. Claude and Codex against the same problem in parallel is a paper-time ablation, not a framework feature

## Context

- **Brownfield refactor.** `automil` framework + `autobench` MIL benchmark in a uv workspace; ~3000 lines of framework code; codebase map at `.planning/codebase/` (7 docs, 2143 lines) committed 2026-04-30.
- **Concrete starting state.** CCRCC has 195+ experiments and a working winning configuration — but the winning state lives in dirty edits to shared library files (`benchmarks/lib/CLAM/utils/core_utils.py`, `model_clam.py`, `train.py`, `run_experiment.py`), in archive directories that are gitignored runtime state, and in graph state that until 2026-05-01 pointed at a leaky Lookahead bug as `best_node_id`. The contamination is real and verified line-by-line.
- **F2 proposal exists** (`tasks/automil_proposal.md`, drafted 2026-04-29) with structural issues: engineering under-budgeted at 5-7 days for a 3-week refactor, compute under-budgeted at 5 min/candidate when CCRCC ran ~4h/candidate, no generalization gate inside search, no multi-runtime defense, no actual MIL-aware framework code despite §6 listing "MILAggregator ABC + registry, 3-4 days." This project addresses the framework-side of those gaps.
- **Q&A document** (`tasks/automil_qa.md`) and **CONCERNS map** (`.planning/codebase/CONCERNS.md`) catalog ~20 known issues across two layers: experiment-level (cross-dataset contamination, no apply/revert CLI, winning-config not version-controlled, stale worktrees) and framework-level (process-group leak, env parser, hard asserts, scoring O(N²), security boundaries). Tier 1 mechanical fixes already shipped; the harder structural ones are this milestone.
- **Team coupling.** Yeonwoo, Keishi, and Ryan are extracting 16 TCGA cohorts but haven't onboarded autoMIL yet. The refactor must be production-grade by the time they do — they're a forcing function for "user-friendly to anyone."

## Constraints

- **Compute**: 3× NVIDIA RTX 6000 Ada (48GB each) on a single machine today; multi-node on the horizon. Framework must scale via pluggable backends.
- **Time per cell**: 6-hour hard wall-clock cap on agent exploration per (dataset, encoder, parent) cell. Framework-enforced, not agent-disciplined. Why: bounds search budget deterministically and forces honest claims about saturating-at-budget.
- **GPU saturation**: target 6–10 CLAM runs per GPU (~0.4 GB each on 48 GB cards). Serial queues are a framework bug, not safety. Carries directly from prior session feedback.
- **Tech stack**: Python (uv workspace), Click, aiohttp, Three.js + vendored frontend libs, pytest. New deps allowed but kept minimal.
- **Portability**: framework cannot hardcode GPU count, model, encoder, training script, or autobench-specific paths. Must run on a single-GPU laptop AND a SLURM cluster.
- **Reproducibility**: trajectory snapshots from day one. Multi-runtime support (Claude / Codex / OpenCode / DeepSeek-via-X) is v1, not deferred.
- **Tests**: changes to existing modules must keep the current 48-test suite green. New modules (registry, backends) require their own tests before promotion.
- **Backwards-compat sanity**: CCRCC `node_0176` (composite 0.8074) must reproduce post-migration on the registry path. Not a promise to preserve every artifact, but a sanity check the migration didn't drift.

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Registry-first, not config-first, for cross-dataset isolation | Config holds values but not callable code; architectural mutations require committed variant modules. Base classes are never edited. | — Pending |
| Skills only for autonomous setup; CLI for everything else | UX (eliminate manual editing) AND context economics (heavy setup logic re-run every session would blow the agent's context). Both reasons compound. | — Pending |
| Pluggable orchestrator backends with `local` as default | Same code path on laptop, SLURM cluster, Ray cluster; no two-orchestrator drift. | — Pending |
| Multi-runtime agent support is in v1, not deferred | F2's "this is a Claude paper" reviewer attack is defended by the framework genuinely running across runtimes — making it a v1 framework property, not a paper-time ablation. | — Pending |
| 6h cap = per-cell-total, framework-enforced | Hard wall clock per `(dataset, encoder, parent)` cell. Orchestrator refuses new submits and kills running ones at budget exhaustion. Bounds search deterministically. | — Pending |
| Search-scope mode flag (`architecture-preserving` \| `free`) | F1 lives but evolves; one registry serves both modes via different pre-submit validators. | — Pending |
| autoMIL is generic; autobench is one consumer | Framework must plug into any training script. No autobench paths, env vars, or schema in `src/automil/`. | — Pending |
| Tier 1 mechanical fixes before structural refactor | Floor-clearing first: gitignore, daemon-killer assert, VRAM-leaking process group, silent YAML failure, best_node misdirection. Quick atomic commits prove the floor. | ✓ Good (5 commits, 2026-05-01) |
| `port-variant` and `promote-variant` are CLI, not skills | Agent triggers them during normal loop operation, possibly several times per session — exactly the runtime-trigger case CLI is for. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-01 after initialization (brownfield, codebase map already in `.planning/codebase/`)*
