# Feature Research

**Domain:** Agent-driven autonomous ML experiment framework (autoMIL refactor — features being added in this milestone)
**Researched:** 2026-05-01
**Confidence:** HIGH for ecosystem positioning of mature features (variant registry, pluggable backends, hardware autodetect, hard caps); MEDIUM for novel-axis claims (multi-runtime, generalization gate, search-scope mode, autonomous setup skill) since these intersect emerging agentic-ML tooling that has shipped in the last 12 months and isn't yet a settled pattern.

**Scoping note:** This is a SUBSEQUENT milestone on a brownfield framework. The experiment tree, GPU bin-packing scheduler, git-worktree overlay runner, and 3D viz dashboard are ALREADY shipped (`.planning/PROJECT.md` "Validated" section). They are not categorized below — this document only categorizes the NEW features in the active set. For each, "table stakes" means table-stakes-vs-the-named-comparators, not "vs ourselves yesterday."

**Comparator set (what every feature is benchmarked against):**

| Comparator | Type | Year | Relevance |
|---|---|---|---|
| Optuna | Hyperparameter AutoML | mature | Closest-shape competitor in the "trial loop" abstraction; menu-level search |
| Ray Tune | Distributed HPO | mature | Multi-backend execution reference; trial timeout reference |
| Weights & Biases Sweeps | HPO + tracking | mature | Sweep agent / artifact lineage / trace reference |
| AutoML-Zero | Evolutionary code search | 2020 | Code-level search precedent; no agent, no infra |
| AlphaEvolve / OpenEvolve | LLM-driven evolutionary code search | 2025 | Closest "agent edits code in a search loop" precedent; weak on infra |
| MLE-STAR | Kaggle ML engineering agent | 2025 (NeurIPS) | Closest "agent iterates on a single ML task" — but per-task, not per-cell × per-parent |
| AI-Scientist v2 (Sakana) | Agentic tree search for ML research | 2025 (ICLR) | Closest in *philosophy* (tree search + multi-stage validation); single-machine, single-runtime |
| PathBench-MIL | MIL-specific Optuna AutoML | Dec 2025 | Direct competitor for the F1 use case; menu-level only |
| nnMIL (Stanford) | Fixed-recipe MIL benchmark | 2025 (arXiv) | Recipe baseline; not adaptive |

## Feature Landscape

### Table Stakes (Must Have or autoMIL Is a Toy vs the Comparator Set)

These are "if we ship without this, we're behind 2024-era tooling." Every named comparator has them. autoMIL's refactor must close these gaps.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Variant registry (committed code, never edits shared library files)** | Optuna *has no need for it* (search space = numeric params, code untouched). But the moment you do code-level search — AlphaEvolve, OpenEvolve, AI-Scientist v2, MLE-STAR — you MUST persist candidates as committed, named, attributable code units. AlphaEvolve calls this its "Program Database"; AI-Scientist v2 calls it the BFTS node store. We currently store overlays in `archive/<id>/` which is gitignored runtime state — this is sub-table-stakes for a code-search framework. | MEDIUM | Resolves the cross-dataset contamination root cause directly (Q1 in `tasks/automil_qa.md`). Depends on: `port-variant` / `promote-variant` CLI to move from archive to registry. |
| **Config-driven `train.py` (no `args.X = literal`)** | Every comparator runs trials by varying config, never by editing the script. Optuna passes hyperparameters via `trial.suggest_*`; Ray Tune via `tune.with_parameters`; W&B via sweep config. Our current state — `args.drop_out = 0.42` hardcoded in `train.py` (`tasks/automil_qa.md` Q1) — is below 2015-era HPO floor. | LOW | Mechanical refactor: every `args.X = Y` in `pipeline/clam/train.py` and `run_experiment.py` becomes a YAML key. Depends on: nothing; should be done first. |
| **Per-trial wall-clock hard cap (timeout)** | Optuna supports `timeout=` on `study.optimize()` and per-trial via `TrialPruned`. Ray Tune has `time_budget_s` and per-trial actor timeouts. W&B agent supports run-time limits. AI-Scientist v2 has BFTS stage budgets. Without it, one runaway trial eats your daily budget — a known Optuna footgun the docs warn about. We have `timeout_min` per spec (`orchestrator.py`) but NO per-cell aggregate cap. | LOW–MEDIUM | The 6h-per-cell cap is novel to autoMIL only because of the per-cell granularity; the *concept* of a wall-clock budget is universal. Depends on: cell concept being formalized in graph schema. |
| **Pluggable orchestrator backend (local + at least one HPC/distributed)** | Ray Tune ships local + distributed Ray as one runtime; integrates with SLURM, Kubernetes, YARN. Optuna pairs with `stune`/`submitit` for SLURM. W&B sweep agents run anywhere. PathBench-MIL inherits Optuna's. **An ML experiment framework that only runs on one laptop is not a framework — it's a script wrapper.** Yeonwoo/Keishi/Ryan onboarding is the forcing function. | LARGE | The local backend is most of what's already in `orchestrator.py`. SLURM (via `submitit`) and Ray are stable, well-documented integration targets. Depends on: clean `OrchestratorBackend` ABC; `local` backend extracted from the current monolith first. |
| **Hardware auto-detection (GPU count, VRAM, accelerator type)** | AutoGluon, H2O AutoML, NVIDIA TAO, LocalAI all auto-detect at startup. Optuna/Ray Tune assume the user configured resources, but their sweep agents auto-detect via `nvidia-smi`/CUDA. PathBench-MIL inherits. Hardcoding `max_concurrent_per_gpu=8` in config (current state) is acceptable for a single user; unacceptable for "framework Yeonwoo can drop onto her cluster." | LOW | We already shell out to `nvidia-smi` for free-VRAM polling (`orchestrator.query_gpus()`). Detecting count + total VRAM at `init` and writing into `config.yaml` is a 50-line addition. Depends on: nothing. |
| **Reproducible trajectory logging (per-trial inputs/outputs/decisions)** | AI-Scientist v2 saves "all relevant experimental outputs (training and validation metrics, losses, etc.) into structured numpy files" + per-stage replication. W&B Weave traces every agent step ("inspect detailed agent trajectories at every step"). Optuna persists trials in a study DB. We have `archive/<id>/{spec,result,run.log}` but NO snapshot of the agent's prompt/tool-call trajectory. F2's "as-protocol reproducibility" claim collapses without this. | MEDIUM | New: `trajectory.jsonl` written per submit with `{ts, prompt_hash, tool_calls, tool_results}`. Depends on: the agent runtime exposing a hook for trajectory capture (Claude Code has `Stop` hook + `transcript.jsonl`; Codex has session logs; OpenCode has its own). |
| **CLI for variant lifecycle: apply / revert / cancel / resubmit** | W&B has `wandb sweep --cancel` / `--resume`. Optuna has `study.tell()` for retroactive runs and `--prune-trials`. Ray Tune has `tune.run(resume=True)`. Our `tasks/automil_qa.md` Q2 — "How do I re-apply the winning changes? Manual `cp` only" — is genuine table-stakes failure. | LOW | Five small CLI commands wrapping graph + filesystem ops. Depends on: variant registry (so `apply <node>` knows where to read from). |

### Differentiators (Real Moat vs Optuna / Ray Tune / PathBench-MIL / AI-Scientist v2)

These are where autoMIL has a defensible position. Each one is genuinely absent or only weakly present in the comparator set.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Multi-runtime agent support (Claude / Codex / OpenCode / DeepSeek-via-X)** as a v1 framework property | This is the strongest moat. (a) Optuna, Ray Tune, W&B Sweeps don't run an LLM agent at all. (b) AlphaEvolve, OpenEvolve, MLE-STAR, AI-Scientist v2 run an LLM agent but each is *coupled* to one runtime (AlphaEvolve = Gemini API; AI-Scientist v2 = Claude Sonnet via the Anthropic API; OpenEvolve = configurable provider but single-provider-per-run; MLE-STAR = via Google Cloud Vertex). (c) Multi-runtime orchestration platforms exist (Ruflo, Composio agent-orchestrator, nori-cli) but they orchestrate *coding* agents, not *ML-experiment-loop* agents. **What multi-runtime does for autoMIL that Optuna/Ray Tune don't even attempt:** it makes the experiment loop *runtime-portable* — if the F2 paper claims "autoMIL discovered these variants," the runtime-portability defense is "and the discovery process reproduces under Codex and OpenCode at within-noise composite." That's a defense Optuna/Ray Tune don't need (no agent) and AI-Scientist v2 can't make (Claude-locked). It's also a *practical* deployment property: a lab without Claude API access can run the framework with DeepSeek via OpenRouter and get the same loop. | LARGE | Reorganize `claude_assets/` → `agent_assets/{claude,codex,opencode,...}/`. Each runtime gets its own SKILL/prompt/hook scaffolding. The `automil` CLI is the contract; runtimes are interchangeable behind it. Concurrent-multi-runtime (running Claude AND Codex on the same cell) is explicitly Out of Scope per `PROJECT.md` — paper-time ablation, not framework feature. Depends on: nothing structural — it's mostly file reorganization and per-runtime prompt authoring. |
| **Search-scope mode flag (`architecture-preserving` vs `free`)** | Same registry, two different pre-submit validators. F1 papers want "we never touched `forward()`"; F2 papers want "we modified anything within identity bounds." No comparator splits the search-space-validity check from the search engine itself: Optuna's space is purely numeric; PathBench-MIL's is menu-pick; AlphaEvolve and OpenEvolve are "anything goes within the eval function." A *typed, validated* code-search-space mode flag is genuinely novel for ML experiment frameworks. | MEDIUM | Pre-commit AST validator: in `architecture-preserving` mode, reject any diff that touches a `forward()` body (whitelist: optimizer wrappers, loss-add layers outside `forward`, schedulers). In `free` mode, only reject identity-violations (param-count delta > 20%, module-graph macro-replacement, signature change). Depends on: variant registry (the validator runs at port-variant time). |
| **Generalization gate inside the search loop (≥K held-out cells before promotion)** | AI-Scientist v2 "launches multiple replications of the selected best experiments at the conclusion of each stage" (per-stage replication for stats), but this is per-cell variance, not cross-cell generalization. Optuna and Ray Tune optimize a single objective per study. PathBench-MIL evaluates across datasets but doesn't *gate promotion on cross-cell improvement*. nnMIL fixes one recipe and *measures* generalization but doesn't search. **autoMIL's generalization gate is novel: a candidate variant is only promoted to the parent's registered variants directory if it improves on ≥K held-out cells beyond the search cell.** This directly defends F2's reviewer attack "you overfit the variant to the search cell." | MEDIUM | New post-search hook: when a candidate dominates its parent on the search cell, automatically schedule it on K held-out cells; promote to registry only if it beats parent on ≥⌈K/2⌉ of them. Depends on: variant registry; pluggable backend (cross-cell scheduling); cell concept formalized. |
| **Per-cell hard cap with framework enforcement (not agent discipline)** | Universal HPO budgets are *per study* (Optuna `timeout`, Ray Tune `time_budget_s`). AI-Scientist v2 has stage budgets but they're agent-honored, not enforced. **autoMIL's twist: per-cell aggregate wall-clock cap, framework-enforced, kills running trials at exhaustion.** This bounds search budget *deterministically per (dataset, encoder, parent) cell* — directly underwrites F1/F2's identical-effort protocol claim. The deterministic-budget argument is a paper-relevant primitive, not just an ops feature. | LOW–MEDIUM | Cell budget = sum of `elapsed_seconds` across all node submissions tagged with that cell's id. Orchestrator refuses new submits when budget hit; SIGTERM running ones. Depends on: cell concept formalized; trajectory instrumentation (so we can attribute wall-clock per cell). |
| **Decoupled framework / consumer split (autoMIL = generic, autobench = one consumer)** | PathBench-MIL is *welded* to slideflow + MIL pipeline shape; un-welding it would be a fork. AI-Scientist v2's experiment harness is welded to its template structure. Optuna, Ray Tune, W&B Sweeps are already generic — but they're generic *for HPO* not for code-level search. **autoMIL's positioning: a generic agent-driven code-search framework whose first consumer is autobench-MIL, but whose contract is purely (a) git repo + entry script + result.json + cell concept.** A reviewer asking "would this work for protein-MIL? for radiology-MIL? for non-MIL ML?" gets a clean yes if this decoupling holds. | MEDIUM | Audit + remove every `autobench`/`AUTOBENCH_` reference from `src/automil/`. Move dataset-pathway helpers to `benchmarks/src/autobench/automil_glue/`. Depends on: nothing structural — it's a refactor + grep -r. |
| **`/automil-setup` autonomous bootstrap skill** | Ray Tune, Optuna, W&B require manual config + per-project glue. PathBench-MIL has YAML scaffolding but you write it by hand. AI-Scientist v2 has a CLI but you must lay out templates yourself. **A skill that, given an arbitrary repo, identifies the entry point, drafts config + agent prompt, scaffolds the registry, and picks defaults from detected hardware — in one autonomous pass — is how Yeonwoo/Keishi/Ryan onboard in <30 min instead of <3 days.** This is the operational moat: "anyone can drop autoMIL onto an existing project." Closest analog is `nnUNetv2_plan_and_preprocess` (which is the inspiration for the F1 framing per `tasks/automil_proposal.md`); generalizing that auto-config trick to *the search loop itself* is the contribution. | MEDIUM | Skill that runs at `automil init`: walks the repo, finds `train.py` candidates by entry-point heuristic + git log + import graph, drafts `config.yaml`, generates the agent's `program.md` from the codebase summary, scaffolds `variants/` registry. Depends on: hardware autodetect; variant registry; framework decoupling. The "skill" form (vs CLI subcommand) is justified by `PROJECT.md`'s context-economics argument: setup is one-shot per project, doesn't need to fit in the running agent's context. |

### Anti-Features (Deliberately NOT Building, with Reasoning)

These are features the comparator set has or could-have-but-shouldn't, that we've explicitly decided against.

| Feature | Why Tempting | Why Problematic | Alternative / What We Do Instead |
|---------|--------------|-----------------|----------------------------------|
| **Concurrent multi-runtime orchestration (Claude AND Codex on the same cell at once)** | Multi-runtime *support* is in scope; the natural follow-on is "run them in parallel and ensemble." Reviewer might also push: "why not?" | Conflates framework capability with paper experimental design. The interesting question — "do different LLM runtimes converge on the same variants?" — is a paper-time *ablation* (run cell-X under Claude, then under Codex, compare) not a framework feature. Building concurrent orchestration adds runtime-coordination complexity (shared registry locking, candidate-deduplication across runtimes) for zero v1 user value. | Per `PROJECT.md` Out of Scope: support is v1, concurrent orchestration is paper-time ablation. Run cell under Claude; later run cell under Codex; statistical compare. |
| **Containerized execution (podman / docker per-trial isolation)** | LLM-generated code is potentially unsafe (writes outside repo, network calls, etc.); standard answer is sandbox each trial. AI-Scientist v2 has a Docker option; OpenEvolve runs in containers; MLE-STAR uses Kaggle's sandbox. | Major lift (image build pipeline, mount-management, GPU passthrough configuration, Apptainer for HPC). Today, autoMIL trusts the agent (Claude in Edit mode) and the host repo. F2 reviewers will ask but the answer "git worktree + AST validator + identity-preservation pre-commit" is defensible without containers for the published-MIL-method search space. | Per `PROJECT.md` Out of Scope: defer until there's a real user pulling for it. The identity-preservation validator + AST validator catch the relevant safety issues for in-search-space mutations. |
| **Mac / MPS / non-CUDA accelerator support** | Local-laptop dev experience; OpenEvolve specifically demos Apple Silicon; broadens contributor base. | Pulls in `torch.backends.mps` plumbing, accelerator-detection branching, second test matrix. Three of three target users (Leo + lab) are Linux+CUDA. Yeonwoo/Keishi/Ryan are HPC=Linux+CUDA. | Per `PROJECT.md` Out of Scope: Linux+CUDA only for v1; revisit when there's a real user. Hardware autodetect surfaces MPS as "unsupported, fail loudly" not silently degrade. |
| **Anti-starvation aging in the GPU scheduler** | Best-fit bin packing can starve a fat job if a stream of small jobs always fits first. Standard scheduler-theory fix is age-based priority. | Hasn't been observed in practice across CCRCC's 195+ experiments. Adding speculative complexity for non-observed problem violates "no laziness, no temporary fixes" CLAUDE.md principle inverted (no premature optimization). | Per `PROJECT.md` Out of Scope: defer until observed in practice. Monitor `orchestrator.log` for queue-time skew during the new milestone's larger grid runs; revisit if signal appears. |
| **Per-trial cost-tracking ($-spend on LLM API calls)** | W&B Weave tracks LLM cost per agent step. AI-Scientist v2's docs note "$15-$20 per run." Useful for budget-bounded research. | Coupled to specific LLM provider billing APIs (Anthropic + OpenAI + DeepSeek + …); we'd be re-implementing OpenLLMetry. Multi-runtime support means N integrations. Agent cost is not the framework's bottleneck (compute time is); the agent runtime (Claude Code, Codex CLI) already exposes its own cost view. | Trajectory instrumentation captures `tool_call.estimated_tokens`; downstream cost computation is an out-of-loop analytics script, not a framework feature. |
| **Distributed agent (multiple agents collaborating on the same cell)** | Sakana / DeepMind / OpenAI all explore multi-agent collaboration; Composio's agent-orchestrator does parallel coding agents. Looks "modern." | Single-agent + tree search (current shape) already gets us multi-branch exploration via the experiment graph — that's where the parallelism should live. Multi-agent on one task explodes coordination complexity (locking, conflict resolution, prompt isolation) for unclear win. Tree search with one-agent-per-branch is the cleaner abstraction. | The experiment graph IS the multi-branch parallelism; siblings are independent agent-driven explorations of the same lineage. No multi-agent-per-task. |
| **Auto-tuning the search algorithm itself (bandit hyperparameters, novelty weight, exploration weight)** | Optuna has TPE meta-parameters that some users tune; Ray Tune has scheduler-of-schedulers. Tempting to make the UCB potential's `w_e=0.005, w_n=0.003` adaptive. | Recursive-tuning rabbit hole. Defaults work well per CCRCC's 195 experiments (`PROJECT.md` Validated). Adding meta-search adds a paper-orthogonal axis nobody asked for. | Constants in `graph.py`. Revisit only if observed-in-practice signal that defaults are biting. |
| **Replacing `/automil-setup` skill with a CLI subcommand** | "Skills are LLM-side; CLI is universal." Looks more portable. | Setup is a multi-step *reasoning* task: identify entry point heuristically, draft prompts based on detected codebase shape, name the registry, propose hyperparameter defaults. A CLI would either be (a) a long heuristic-laden Python script that drifts from how Claude/Codex actually reason, or (b) a thin shell that calls an agent — at which point it's a skill in disguise. Per `PROJECT.md` Key Decisions: "Skills only for autonomous setup; CLI for everything else" — UX *and* context economics (heavy setup logic re-run every session blows the agent's context). | Skill for one-shot setup; CLI for everything triggered repeatedly during the loop (`apply`, `revert-baseline`, `cancel`, `resubmit`, `port-variant`, `promote-variant`). |

## Feature Dependencies

```
Decouple framework from autobench
    └──enables──> /automil-setup skill (skill must work on arbitrary repos)
    └──enables──> Multi-runtime support (per-runtime assets shouldn't import autobench)

Variant registry
    ├──requires──> Config-driven train.py (so config can name a variant)
    ├──enables──> CLI: apply / revert / port-variant / promote-variant
    ├──enables──> Search-scope mode (validators run at port-variant time)
    └──enables──> Generalization gate (gate decides registry promotion)

Hardware auto-detection
    └──enables──> /automil-setup skill (skill picks defaults from detected hardware)
    └──enables──> Pluggable backend (backend-specific resource defaults)

Pluggable orchestrator backends
    ├──requires──> Decoupled framework (backend interface can't know about autobench)
    ├──enables──> Generalization gate (gate schedules across backend cells)
    └──enables──> Per-cell hard cap (cap is enforced at the backend level)

Per-cell hard cap
    ├──requires──> Cell concept formalized in graph schema
    └──requires──> Trajectory instrumentation (per-cell wall-clock attribution)

Trajectory instrumentation
    ├──requires──> Multi-runtime support contract (each runtime exposes a trajectory hook)
    └──enables──> "as-protocol" reproducibility claim in F2 paper

Multi-runtime support
    └──enables──> /automil-setup skill (setup runs under whichever runtime initiated init)

Search-scope mode (architecture-preserving | free)
    ├──requires──> Variant registry (validators run at promote-variant time)
    └──enables──> F1 paper claim (architecture-preservation guarantee)
                  AND F2 paper claim (identity-preservation bound)
```

### Dependency Notes

- **Variant registry is the keystone.** Six other features depend on it. Build first.
- **Decoupling unlocks the skill + multi-runtime story.** Cannot ship `/automil-setup` while `src/automil/` imports `autobench`. This refactor must precede the skill.
- **Hardware autodetect feeds the skill.** Skill drafts `config.yaml` defaults; defaults need actual hardware numbers, not literal placeholders.
- **Pluggable backend depends on decoupling.** A `SLURMBackend` cannot know about `AUTOBENCH_ROOT`. The backend interface must be in domain-neutral terms (`{cwd, env, resource_request, timeout}`).
- **Per-cell hard cap depends on the cell concept being formalized.** Currently "cell" is implicit (a directory under `benchmarks/experiments/<dataset>/`). Must become a first-class graph-schema entity with `{dataset, encoder, parent_model, budget_remaining_seconds}`.
- **Generalization gate composes registry + backend + cell concept.** It's the most-dependent feature; build last.

## MVP Definition

### Launch With (v1 — this milestone's deliverable)

Minimum viable refactor — what's needed to defend F2's framework-side claims.

- [ ] **Variant registry** — keystone; resolves cross-dataset contamination at the root
- [ ] **Config-driven `train.py`** — sub-table-stakes gap that's mechanical to fix; unblocks registry
- [ ] **Decouple framework from autobench** — cannot publish a "generic agent-driven code-search framework" while `src/automil/` says `AUTOBENCH_ROOT`
- [ ] **CLI: `apply`, `revert-baseline`, `cancel`, `resubmit`, `port-variant`, `promote-variant`, `reconcile --recompute-best`** — table-stakes lifecycle ops
- [ ] **Per-cell 6h hard cap** — bounds search deterministically; underwrites F1/F2 identical-effort protocol
- [ ] **Pluggable orchestrator backends** with `local` default — without this it's not a framework
- [ ] **Multi-runtime support** (Claude + Codex + OpenCode + DeepSeek-via-X scaffolding) — F2's strongest moat; defends "this is a Claude paper" attack
- [ ] **Trajectory instrumentation** — F2's "as-protocol reproducibility" claim is empty without per-submit prompt+tool-call snapshots
- [ ] **Hardware auto-detection** — required so skill can draft hardware-aware defaults
- [ ] **`/automil-setup` skill** — the operational moat; team-onboarding forcing function
- [ ] **Generalization gate inside search loop** — directly defends F2's overfit-to-search-cell attack
- [ ] **Search-scope mode flag** — F1 lives via the `architecture-preserving` validator; F2 via `free`
- [ ] **Reproduction sanity check** — CCRCC `node_0176` reproduces (composite within ±0.005) on the new registry-driven path

### Add After Validation (v1.x)

Features that are obvious next steps once v1 ships and Yeonwoo/Keishi/Ryan are on the framework.

- [ ] **`SLURMBackend` (via submitit)** — second pluggable backend, validates the abstraction with a real HPC user. Trigger: any team member moves a workflow to a SLURM cluster.
- [ ] **`RayBackend`** — third backend; needed only if a deployment doesn't have SLURM (cloud / k8s). Trigger: real cloud-deployment ask.
- [ ] **Cost-aware scheduling (cell budget = wall-clock + LLM-API-spend)** — adds spend-side bound on top of wall-clock bound. Trigger: hitting a real LLM-cost ceiling that wall-clock doesn't capture.
- [ ] **Variant registry mining (cross-dataset variant transfer)** — if CCRCC's winning variant works on TCGA-LUAD without re-search, register it as a "transfer baseline." Trigger: F1 grid completes and we see consistent winners.
- [ ] **Convergence-diagnostic dashboard** (per-cell discovery curves) — viz extension. Trigger: F1 paper writing, when we need the figure.

### Future Consideration (v2+)

Defer until product-market fit (a.k.a. "F1 + F2 papers shipped, framework has external users").

- [ ] **Mac / MPS support** — only if external users ask
- [ ] **Containerized per-trial execution** — only if security review demands
- [ ] **Concurrent multi-runtime orchestration** — paper-time ablation only; not a framework feature
- [ ] **Distributed agent collaboration** — orthogonal to current tree-search-as-parallelism design

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Variant registry | HIGH | MEDIUM | P1 |
| Config-driven `train.py` | HIGH | LOW | P1 |
| Decouple from autobench | HIGH | MEDIUM | P1 |
| CLI lifecycle commands | HIGH | LOW | P1 |
| Per-cell 6h hard cap | HIGH | LOW–MEDIUM | P1 |
| Pluggable orchestrator backends (interface + local) | HIGH | MEDIUM | P1 |
| Multi-runtime support (file reorg + ≥2 runtime scaffolds) | HIGH | LARGE | P1 |
| Trajectory instrumentation | HIGH | MEDIUM | P1 |
| Hardware auto-detection | MEDIUM | LOW | P1 |
| `/automil-setup` skill | HIGH | MEDIUM | P1 |
| Generalization gate | HIGH | MEDIUM | P1 |
| Search-scope mode flag | HIGH | MEDIUM | P1 |
| Reproduction sanity check (CCRCC node_0176) | MEDIUM | LOW | P1 |
| SLURM backend | HIGH | MEDIUM | P2 |
| Ray backend | MEDIUM | MEDIUM | P2 |
| Cost-aware scheduling | LOW | MEDIUM | P3 |
| Mac/MPS support | LOW | MEDIUM | P3 |
| Containerized execution | LOW | LARGE | P3 |

**Priority key:**
- P1: This milestone (v1 refactor)
- P2: Next milestone (HPC onboarding milestone)
- P3: After F1+F2 papers ship

## Competitor Feature Analysis

| Feature | Optuna | Ray Tune | W&B Sweeps | PathBench-MIL | AI-Scientist v2 | AlphaEvolve / OpenEvolve | MLE-STAR | autoMIL (target) |
|---------|--------|----------|------------|---------------|-----------------|--------------------------|----------|------------------|
| **Variant registry (committed code)** | N/A (numeric only) | N/A | N/A (artifacts ≠ code variants) | Menu-pick (no code) | BFTS node store (in-process, ephemeral) | Program Database (committed) | Per-task code blocks | Committed registry per-parent |
| **Config-driven training script** | Yes (define-by-run) | Yes (`tune.with_parameters`) | Yes (sweep config) | Yes (YAML) | Partial (templates) | Yes (problem.py contract) | Yes | Target: yes (we're behind) |
| **Per-trial wall-clock cap** | `timeout=` per study; `TrialPruned` per trial | `time_budget_s` + actor timeouts | Run-time limit per agent | Inherits Optuna | Stage budgets (agent-honored) | Per-eval timeout | Per-step budget | Per-cell aggregate cap (ours) + per-trial (universal) |
| **Pluggable distributed backend** | via Joblib/submitit/Dask | Native: local, SLURM, K8s, YARN | Local + W&B Launch (cloud) | Inherits Optuna | Single-machine | Distributed evolution | Single-machine | Target: local + SLURM + Ray |
| **Hardware auto-detect** | Implicit (user wires) | Yes (`ray init` detects) | Sweep agent detects | Inherits | No (user configures) | No | Partial (Kaggle env) | Target: at `init` |
| **Trajectory logging** | Trial DB (params + metrics) | Trial logger | Weave traces (full agent steps) | Inherits Optuna | Per-stage outputs to numpy | Eval traces | Per-step refinement log | Target: per-submit prompt+tool-call jsonl |
| **CLI lifecycle (apply/revert/cancel)** | `study.tell` / `prune` | `tune.run(resume=True)` | `wandb sweep --cancel/--resume` | Inherits | Stage-level | None visible | None visible | Target: full set |
| **Multi-runtime LLM support** | N/A | N/A | N/A | N/A | Claude-locked | Configurable provider, single-per-run | Vertex-locked | **Target: v1 property** |
| **Search-scope mode (typed validator)** | N/A | N/A | N/A | N/A (menu) | No (templated) | No (anything-goes) | No | **Target: novel** |
| **Generalization gate (cross-cell promotion)** | N/A (single objective) | Multi-objective but no gate | N/A | Multi-dataset eval, no gate | Per-stage replication (variance only) | No | No | **Target: novel** |
| **Per-cell aggregate hard cap** | Per-study only | Per-study only | Per-run only | Inherits | Per-stage | Per-eval | Per-task | **Target: per-cell (granular)** |
| **Autonomous setup skill** | Manual | Manual | Manual + Launch templates | Manual YAML | Templated lay-out | Manual | Kaggle-shape | **Target: novel** |
| **Domain-decoupled** | Yes | Yes | Yes | No (slideflow-welded) | Partial (template-coupled) | Yes (problem.py) | Partial (Kaggle-shape) | **Target: yes** |

## Quality-Gate Self-Check

- [x] Categories distinct (table stakes vs differentiator vs anti-feature) — yes, with explicit reasoning per row
- [x] Each feature compared to ≥2 named existing frameworks — yes, the matrix has 7 named comparators per row; differentiator entries each name 3-5 specific comparators in their value-prop text
- [x] Complexity (LOW/MEDIUM/LARGE) and dependencies noted — yes, per row + explicit dependency graph
- [x] Multi-runtime: what does it do *differentiating-ly* — yes, called out explicitly: "what multi-runtime does for autoMIL that Optuna/Ray Tune don't even attempt: makes the experiment loop runtime-portable, defends F2's 'this is a Claude paper' reviewer attack, and is a practical deployment property (lab without Claude API access can run the loop with DeepSeek via OpenRouter)"

## Sources

- [Optuna documentation — hyperparameter optimization framework](https://optuna.org/)
- [Optuna stopping conditions and timeouts (Discussion #6525)](https://github.com/optuna/optuna/discussions/6525)
- [Ray Tune — Hyperparameter Tuning](https://docs.ray.io/en/latest/tune/index.html)
- [Ray Tune × Optuna integration example](https://docs.ray.io/en/latest/tune/examples/optuna_example.html)
- [stune — Optuna on SLURM clusters](https://github.com/liukidar/stune)
- [ray-tune-slurm-demo](https://github.com/klieret/ray-tune-slurm-demo)
- [Weights & Biases Sweeps documentation](https://docs.wandb.ai/tutorials/sweeps)
- [W&B Weave (agent trajectory traces)](https://wandb.ai/site/agents/)
- [W&B Launch agent (Nebius / Apptainer)](https://nebius.com/third-party-applications/weights-and-biases-launch-agent)
- [AI-Scientist v2 (Sakana, ICLR 2025) — paper PDF](https://pub.sakana.ai/ai-scientist-v2/paper/paper.pdf)
- [AI-Scientist v2 GitHub](https://github.com/SakanaAI/AI-Scientist-v2)
- [AI-Scientist v2 arXiv 2504.08066](https://arxiv.org/abs/2504.08066)
- [AlphaEvolve arXiv 2506.13131](https://arxiv.org/abs/2506.13131)
- [AlphaEvolve technical report (DeepMind)](https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf)
- [OpenEvolve GitHub](https://github.com/algorithmicsuperintelligence/openevolve)
- [OpenEvolve GPU-kernel discovery (Apple Silicon hardware-aware optimization)](https://huggingface.co/blog/codelion/openevolve-gpu-kernel-discovery)
- [MLE-STAR (Google Research blog)](https://research.google/blog/mle-star-a-state-of-the-art-machine-learning-engineering-agents/)
- [MLE-STAR arXiv 2506.15692](https://arxiv.org/abs/2506.15692)
- [MLE-bench (OpenAI) arXiv 2410.07095](https://arxiv.org/abs/2410.07095)
- [PathBench-MIL GitHub (Brussee, LUMC)](https://github.com/Sbrussee/PathBench-MIL)
- [PathBench-MIL arXiv 2512.17517](https://arxiv.org/abs/2512.17517)
- [AutoGluon GPU support documentation](https://auto.gluon.ai/0.4.0/tutorials/tabular_prediction/tabular-gpu.html)
- [LocalAI GPU acceleration (auto-detect)](https://localai.io/features/gpu-acceleration/)
- [Composio agent-orchestrator (multi-runtime coding agents)](https://github.com/ComposioHQ/agent-orchestrator)
- Project context: `/home/jma/Documents/yinshuol/autoMIL/.planning/PROJECT.md`
- F2 proposal: `/home/jma/Documents/yinshuol/autoMIL/tasks/automil_proposal.md`
- Q&A diagnosis of current gaps: `/home/jma/Documents/yinshuol/autoMIL/tasks/automil_qa.md`
- Architecture map: `/home/jma/Documents/yinshuol/autoMIL/.planning/codebase/ARCHITECTURE.md`

---
*Feature research for: agent-driven autonomous ML experiment framework (autoMIL refactor milestone)*
*Researched: 2026-05-01*
