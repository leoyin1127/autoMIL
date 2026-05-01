# Project Research Summary

**Project:** autoMIL — F2-readiness framework refactor
**Domain:** Brownfield refactor of an autonomous, agent-driven ML experiment framework (variant registry, pluggable orchestrator backends, multi-runtime agent support, 6h hard cap, trajectory instrumentation, generalization gate, autobench decoupling, autonomous setup skill, hardware autodetect)
**Researched:** 2026-04-30 / 2026-05-01
**Confidence:** HIGH overall — every recommendation grounded in either reference-class implementations (timm, TorchX, submitit, FAIR), live ecosystem standards (AGENTS.md/SKILL.md, OTel `gen_ai.*`, JSONL trajectories), or evidence already in `.planning/codebase/CONCERNS.md` and `tasks/automil_qa.md`.

## Executive Summary

This is a brownfield refactor on a working framework, not a greenfield design exercise. The existing experiment-tree, GPU bin-packing scheduler, git-worktree runner, viz dashboard, and 48-test suite are validated and locked (`.planning/codebase/`). The milestone adds nine new architectural components on top of that floor. The single most important architectural insight from the research is that **the variant registry is the keystone** — six other features (lifecycle CLI, search-scope mode, generalization gate, autobench decoupling, setup skill, reproduction sanity check) depend on it, and it is the structural fix for the cross-dataset contamination problem documented in `automil_qa.md`. The single most important *moat* is **multi-runtime agent support as a v1 framework property**, not a paper-time ablation — it is the only feature in the active set that no comparator (Optuna, Ray Tune, AI-Scientist v2, AlphaEvolve, MLE-STAR, PathBench-MIL) attempts, and it directly defends F2's predictable "this is a Claude paper" reviewer attack.

The recommended approach is prescriptive: a thin internal `Registry` class (timm-shape, decorator + explicit-import; **not** pluggy, **not** Hydra-zen) for variants; a TorchX-shaped `Backend` ABC with `LocalBackend` shipped as a re-export shim over today's orchestrator code (**not** a rewrite); `submitit 1.5.3` as the SLURM impl and `ray 2.55.1` (raw `ray.remote` + placement groups, **not** `ray.tune`) as the Ray impl; a `_shared/SKILL.md` + per-runtime overrides asset layout (**not** N parallel Jinja templates); JSONL trajectories using OpenTelemetry `gen_ai.*` field names with bounded-compaction (**not** raw transcript dump, **not** `opentelemetry-sdk` runtime dep); and a generalization gate implemented as a node-status transition (`candidate` → `registered`) on the existing graph (**not** a parallel candidates graph). Build order is dictated by structural dependencies: registry → CCRCC reproduction sanity check → backend ABC → trajectory recorder → multi-runtime reorg → 6h cap → generalization gate → SLURM → Ray → setup skill → hardware autodetect.

Risk mitigation must be designed into the roadmap up front, not retrofitted. Five pitfalls require *design-time* prevention rather than fix-on-discovery: (1) old direct-edit pathway coexisting with the new registry, (2) the `Backend` ABC freezing local-backend semantics (PIDs, sync status, killpg) into the abstraction, (3) the 6h cap killing experiments mid-fold and corrupting `results.tsv` plus the descendant cascade, (4) the autobench decoupling shipping with autobench's idioms (4-key composite, 5×5 CV, `metrics.val_auc` magic key) frozen into the abstract API, and (5) trajectory capture leaking secrets, exploding disk, or fossilizing a single runtime's tool schema. Three more — multi-runtime untested-but-claimed, generalization-gate calibration (too strict / too loose / leaky held-out), and `/automil-setup` mis-scaffolding — are *ongoing-discipline* failures that have to be re-validated on every cohort/runtime/model change. The roadmap MUST treat these as gates, not as backlog items.

## Key Findings

### Recommended Stack

The existing stack (Python 3.10+, click, aiohttp, watchdog, jinja2, pyyaml, hatchling, uv workspace, vendored d3/three) is locked per `.planning/codebase/STACK.md` and is not re-litigated. New components add only what is structurally required, with zero new deps for the registry and core ABC layers.

**Core technologies (NEW only):**

- **Internal `Registry` class + `importlib.metadata.entry_points`** — Variant registry. Zero new deps; one-page implementation; entry_points enables cross-project sharing once `autobench` declares variants. Use timm's pattern (decorator + explicit-import in per-parent `variants/__init__.py`); regenerate `__init__.py` mechanically via `automil refresh-registry`. **Reject `pluggy` (wrong shape — event bus, not alternative-pick), `Hydra-zen` (forces full Hydra config rewrite), `stevedore`, `Dishka`.**
- **`submitit 1.5.3`** — SLURM backend impl. `concurrent.futures`-shaped Job-future API, FAIR production track record, preempt/requeue, Dec 2025 release. **Reject `simple_slurm`/`slurmpy`/`pysbatch` (thin sbatch shellouts, no Job-future API).** Lazy-imported in `backends/slurm.py`, opt-in via `pip install -e '.[slurm]'`.
- **`ray 2.55.1`** — Ray backend impl, used as **raw distributed executor only** (`ray.remote` + placement groups). **Reject `ray.tune` as the search controller** — its `Trial`/`Tuner` model conflicts with autoMIL's experiment graph; two scheduling layers fighting. Lazy-imported in `backends/ray.py`, opt-in via `pip install -e '.[ray]'`.
- **TorchX-shaped `Backend` ABC** — Lowest common denominator across local/SLURM/Ray. Methods: `submit`, `poll`/`describe`, `list_running`, `cancel`, `log_iter`. **Reject submitit-only as the abstraction** (excellent for SLURM, doesn't generalize); **reject Snakemake/Nextflow/Airflow** (workflow engines, wrong altitude); **reject `concurrent.futures.Executor`** (too narrow — no log streaming or cancellation lifecycle).
- **AGENTS.md (Linux Foundation Agentic AI Foundation, 2025)** — Universal "instructions for agents" file. Read by 25+ tools (Codex, Cursor, Copilot, Aider, opencode, Zed, Windsurf, Junie, Gemini CLI, Factory, …). The cheap union for cross-runtime project instructions.
- **Per-runtime skill scaffolding overlays** — Claude `SKILL.md` (YAML frontmatter; `description` is the invocation field), opencode `agents/*.md` + `skills/*/SKILL.md`, Codex `AGENTS.md` + optional skills. DeepSeek is NOT a separate runtime — it is a *model* under one of the above harnesses; `agent_assets/deepseek/README.md` is a pointer doc only.
- **OpenTelemetry `gen_ai.*` semantic conventions (field names only)** — Trajectory schema namespace. **Adopt the names; do NOT add `opentelemetry-sdk` as a runtime dep** (would force OTLP exporters/collectors). Vendor-neutral; replayable into Phoenix/Arize, LangSmith, Datadog later without rename.
- **JSONL one-event-per-line trajectories** — De facto standard (SWE-agent, OpenHands, SWE-Gym, Nebius SWE-rebench). Append-only crash safety, grep-able, schema-additive.
- **Defense-in-depth wall-clock enforcement** — stdlib subprocess + signal escalation (SIGTERM → 30s grace → SIGKILL via `os.killpg`) in framework; SLURM `--time --signal=B:TERM@30`; Ray `ray.get(timeout) + ray.cancel(force=True)`. **Reject `signal.SIGALRM`** (main-thread-only, single-process-only); **reject cgroups** (root/systemd-run privilege; out of scope).

**New direct deps:** `psutil>=7.0`, `filelock>=3.16`, `pydantic>=2.9`.
**Optional extras:** `submitit>=1.5.3` (slurm), `ray>=2.55.1,<3` (ray).
**Dev:** `mypy` or `pyright` strict on new ABCs; `ruff 0.7+` already in stack.

### Expected Features

`FEATURES.md` benchmarks every feature against 9 named comparators (Optuna, Ray Tune, W&B Sweeps, AutoML-Zero, AlphaEvolve/OpenEvolve, MLE-STAR, AI-Scientist v2, PathBench-MIL, nnMIL).

**Must have (table stakes — without these autoMIL is below 2024-era ML tooling floor):**
- **Variant registry (committed code, never edits shared library files)** — code-search precedent: AlphaEvolve "Program Database," AI-Scientist v2 BFTS node store. Resolves cross-dataset contamination at the root.
- **Config-driven `train.py`** — every comparator runs trials by varying config; our `args.X = literal` overrides are below 2015-era HPO floor.
- **Per-trial wall-clock cap** — universal (Optuna, Ray Tune, W&B, AI-Scientist v2).
- **Pluggable orchestrator backend (local + ≥1 HPC/distributed)** — "an experiment framework that only runs on one laptop is not a framework." Yeonwoo/Keishi/Ryan onboarding is the forcing function.
- **Hardware auto-detection** — AutoGluon, H2O, NVIDIA TAO, LocalAI all auto-detect.
- **Reproducible trajectory logging** — F2's "as-protocol reproducibility" claim is empty without it.
- **CLI for variant lifecycle** (`apply` / `revert-baseline` / `cancel` / `resubmit` / `port-variant` / `promote-variant` / `reconcile --recompute-best`) — `automil_qa.md` Q2 ("manual cp only") is a genuine table-stakes gap.

**Should have (real differentiator moat):**
- **Multi-runtime agent support as a v1 framework property** — STRONGEST MOAT. No comparator that runs an agent runs more than one runtime; no multi-runtime orchestrator exists for ML-experiment loops.
- **Search-scope mode flag (`architecture-preserving` | `free`)** — same registry, two pre-submit validators. Genuinely novel.
- **Generalization gate (≥K held-out cells before promotion)** — directly defends F2's "you overfit to the search cell" reviewer attack.
- **Per-cell aggregate hard cap, framework-enforced** — underwrites F1/F2 identical-effort protocol deterministically.
- **Decoupled framework / consumer split** — enables protein-MIL / radiology-MIL / non-MIL plug-ins.
- **`/automil-setup` autonomous bootstrap skill** — operational moat (<30 min onboarding instead of <3 days).

**Defer (v2+, with reasoning):** concurrent multi-runtime orchestration (paper-time ablation), containerized per-trial execution, Mac/MPS, anti-starvation aging, per-trial $-cost tracking, multi-agent collaboration, auto-tuning the search algorithm itself, replacing setup skill with a CLI subcommand.

### Architecture Approach

The new layer plugs **above** today's stdlib-only kernel (`graph.py`, `runner.py`) and **below** the CLI. Five new pieces: registry layer, backend dispatcher (with `LocalBackend` as a re-export shim over the existing 750-line orchestrator), trajectory recorder + compaction, generalization gate (a node-status transition on the existing graph, NOT a separate graph), and `agent_assets/_shared/ + per-runtime overrides`. CLI splits from the 726-line monolith into command-group files under `cli/`. A `compat.py` re-export shim preserves all existing import paths so the 48-test suite stays green through the file moves.

**Major components:**

1. **`core/`** — stdlib-only kernel. `graph.py` (gains `status='candidate'`, `cell_id`, `variant_ref`, gate edges), `runner.py` (unchanged), `ids.py`. Imports nothing else from autoMIL.
2. **`registry/`** — `base.py` (`Variant` ABC, frozen `VariantSpec`), `registry.py` (decorator + entry_points discovery), `discovery.py` (regenerates per-parent `__init__.py`), `validators/{identity,interface,purity}.py` chain.
3. **`backends/`** — `base.py` (TorchX-shaped ABC, state-not-control-flow `JobState` enum), `local.py` (re-export shim — minimal new code), `slurm.py` (submitit), `ray.py` (raw `ray.remote`), `_orchestrator_daemon.py` (moved local impl). **No `Popen`/PID/`os.kill` references in orchestrator main loop or non-local backends.**
4. **`trajectory/`** — `recorder.py` (JSONL append + redaction-on-capture), `schema.py` (OTel `gen_ai.*` keys; first-line metadata `{schema_version, runtime, runtime_version, tool_schema_version, automil_version}`), `compaction.py` (5 MB soft / 50 MB hard rotate; typical 50 MB → 200 KB).
5. **`gate/`** — `generalization.py` (`tick()` polled by daemon; spawns held-out evals via `backend.submit()` — same path as agent submits), `promotion.py` (`candidate` → `registered`). **Manual nomination default; auto-nomination config-gated OFF in shipping defaults.**
6. **`agent_assets/`** — `_shared/SKILL.md` is the canonical content; per-runtime directories hold ONLY diffs. `automil show-skill --runtime <name>` debug command.
7. **`cli/`** — split monolith. New `variants.py` group hosts variant lifecycle commands.
8. **`compat.py`** — re-export shim. v0.4.x removal target for deprecated paths.

### Critical Pitfalls

The five highest-risk pitfalls requiring up-front design (not later fix-on-discovery):

1. **"Still uses old path" (Pitfall 1)** — registry ships, but shared library files remain mutable; agent muscle memory + 195 prior `archive/<id>/spec.json` files keep editing them. **Prevention:** disable-old → enable-new. Submit pre-validator rejects overlays touching `registry.protected`. `automil check` fails on uncommitted edits to protected files. Every skill prompt purged of direct-edit references. Reproduction sanity check runs from clean checkout where protected files are guaranteed unmodified.

2. **Backend ABC leaks `LocalBackend` semantics (Pitfall 2)** — designing the ABC against one impl freezes PID exposure, synchronous status, killpg control flow into the interface. **Prevention:** implement local + a MockSLURM backend in parallel before the ABC is locked. Mock simulates eventual-consistency status (5s lag), opaque job_id, fire-and-forget cancel, node-local filesystem. Lint check forbids `os.kill` / `Popen` / `pid` outside backend impls. State (not control flow) is the unit of abstraction.

3. **6h cap mid-fold guillotine + descendant cascade (Pitfall 4)** — cap fires at 5h59m; experiments killed mid-fold-4-of-5; node stuck `running`; daemon-restart `_recover_orphans` marks `crash` (composite=0); `_reevaluate_descendants` cascade-discards completed siblings. **Prevention designed in:** per-fold checkpoint protocol (`fold_<i>_result.json` aggregated to `result.json`); two-tier cap (refuse-new at `T - safety_buffer`, terminate at `T`); `cell_started_at` persisted across daemon restarts; budget-killed reconciles to `executed` (NOT `crash`); `start_new_session=True` + `os.killpg` reaffirmed in new backends.

4. **Autobench decoupling ships with autobench idioms frozen in the abstract API (Pitfall 7)** — `result.json` schema (`metrics.val_auc`, 4-key composite), 5×5 CV, per-fold aggregation become "private API masquerading as generic." **Prevention:** plug a second consumer (sklearn-iris) before declaring decoupling done. JSON-Schema-validate `result.json`. Pluggable scoring (formula declared in `automil/config.yaml` or named entry point). Env-var declaration in config + `automil check` validation.

5. **Trajectory leak / bloat / fossilize (Pitfall 5)** — (a) tool calls serialize raw env including API keys → publish as F2 artifact = leak; (b) ~30 MB × thousands of experiments = compliance liability; (c) Claude tool schema fossilizes — replay-against-new-schema fails silently. **Prevention:** redaction-on-capture (regex for `sk-`, `hf_`, `ghp_`, AWS keys, `*_API_KEY=`, `*_TOKEN=`); per-event 8 KB cap; per-file 5 MB soft / 50 MB hard rotate; first-line schema-version metadata; gitignored by default; don't claim replayability we don't have.

(Pitfalls 3 multi-runtime untested, 6 gate calibration, 8 hardware mis-detect, 9 setup mis-scaffold are also critical but classified primarily as ongoing-discipline.)

## Implications for Roadmap

Suggested 9-phase structure (Phase 0 cleanup + 8 substantive phases):

### Phase 0: Tier 2 cleanup + CLI split + `compat.py` shim
**Rationale:** No-dependencies. CONCERNS HIGH-severity items + mechanical re-exports. Precondition for new commands to have a place to live.
**Delivers:** Clean tree, split CLI under `cli/<group>.py`, all 48 tests green.
**Estimated:** 2-3 days.

### Phase 1: Variant registry + config-driven `train.py` + reproduction sanity check
**Rationale:** **The keystone.** Six features depend on it. Reproduction sanity check is the milestone exit criterion; running it now validates registry-only migration BEFORE complicating with backends.
**Delivers:** `registry/` layer, `automil refresh-registry`, CCRCC variants ported, reproduction passes ±0.005 on clean checkout via registry path, submit pre-validator + `registry.protected`.
**Avoids:** Pitfall 1.
**Estimated:** 5-7 days.

### Phase 2: Backend ABC + `LocalBackend` re-export + MockSLURM
**Rationale:** Bounding step. ABC must be designed against ≥2 implementations. MockSLURM is the discipline preventing Pitfall 2.
**Delivers:** `backends/{base,local,_orchestrator_daemon}.py` + MockSLURM fixture; lint check forbidding `os.kill`/`Popen`/`pid` outside backend impls.
**Avoids:** Pitfall 2.
**Estimated:** 3-4 days.

### Phase 3: Trajectory recorder + multi-runtime asset reorg
**Rationale:** Trajectory must precede gate (gate spawns evaluations needing capture). Asset reorg precedes setup skill. Both share `AUTOMIL_RUNTIME` declaration.
**Delivers:** `trajectory/` with redaction-on-capture, OTel `gen_ai.*` keys, schema-version metadata, bounded JSONL; `agent_assets/_shared/` + per-runtime overlays; `automil show-skill` debug.
**Avoids:** Pitfall 5; Pitfall 3 ongoing-discipline gate (≥2 runtimes validated end-to-end before sign-off).
**Estimated:** 4-5 days.

### Phase 4: 6h per-cell hard cap + cell-concept formalization
**Rationale:** Depends on cell concept being first-class graph entity and trajectory for per-cell wall-clock attribution. Partial-fold protocol must ship WITH the cap.
**Delivers:** `cells/<dataset>__<encoder>__<parent_id>.json` state files; two-tier cap; per-fold checkpoint protocol; budget-killed = `executed` partial composite; persisted `cell_started_at`.
**Avoids:** Pitfall 4.
**Estimated:** 3-4 days.

### Phase 5: Generalization gate
**Rationale:** Most-dependent feature; composes registry + backend + cell + trajectory.
**Delivers:** `gate/`; `status='candidate'` transition; pre-registered `gate_manifest.json` (held-out committed BEFORE search); paired-test (Wilcoxon + bootstrap CI + Bonferroni); manual nomination default; promotion-rate as search-health metric.
**Avoids:** Pitfall 6.
**Estimated:** 4-5 days.

### Phase 6: SLURM backend (submitit) + Ray backend (raw `ray.remote`)
**Rationale:** Now bounded by the locked ABC and trajectory contract. Parallelizable across two engineers if available.
**Delivers:** `backends/slurm.py`, `backends/ray.py`, opt-in extras, cross-backend log unification, per-backend `running/` ownership.
**Estimated:** 5-7 days.

### Phase 7: Hardware autodetect + `/automil-setup` skill
**Rationale:** Setup needs registry + backend + decoupling proven; autodetect feeds setup defaults.
**Delivers:** `LocalBackend.healthcheck()` reports detected hardware; empirical VRAM feedback (`results.tsv` → quantile_95 + 0.5 GB); per-variant VRAM tracking; **detect-and-warn** (NOT detect-and-decide); interactive setup skill; mandatory `automil check` + 1-min dry-run; idempotent re-runs.
**Avoids:** Pitfall 8, Pitfall 9.
**Estimated:** 4-5 days.

### Phase 8: Decoupling completion + acceptance
**Rationale:** Final phase; audit + second-consumer validation + acceptance test.
**Delivers:** Audit removing all `autobench`/`AUTOBENCH_` from `src/automil/`; sklearn-iris consumer running end-to-end; `docs/training-script-contract.md`; pluggable scoring; final reproduction sanity check (CCRCC `node_0176` ±0.005 on registry path, clean checkout, fresh worktree).
**Avoids:** Pitfall 7.
**Estimated:** 3-4 days.

### Phase Ordering Rationale

- **Registry before everything** — six features depend on it; contamination root cause fixed only after registry + protected-files gate.
- **Backend ABC before SLURM/Ray** — without ABC, SLURM means parallel orchestrator (Pitfall 2). MockSLURM in Phase 2 is the discipline.
- **Variant migration + reproduction sanity in Phase 1** — if registry-only doesn't reproduce CCRCC, find the bug before complicating with backends. Phase 8 sanity check is the final gate.
- **Trajectory before gate** — gate spawns evaluations; those experiments must capture trajectories.
- **Multi-runtime reorg with trajectory** — they share runtime-declaration mechanism (`AUTOMIL_RUNTIME` env var).
- **6h cap before gate** — gate spawns N held-out evals per nomination; without cap those run unbounded.
- **Setup skill last (Phase 7)** — needs the layers below stable; skill calibration depends on framework shape that can't shift after.
- **Decoupling threaded throughout, audited at end** — any phase that imports from autobench has not done its job.

### Research Flags

Phases needing deeper research during planning:
- **Phase 4 (6h cap)** — partial-fold checkpoint protocol design; needs autobench-pipeline review.
- **Phase 5 (gate)** — K calibration via pilot run; "win" definition via paired statistical test the F1 paper claims.
- **Phase 6 (Ray backend)** — Ray-on-SLURM deployment surface (Issues #19942, #13607); pilot before Yeonwoo's onboarding.
- **Phase 7 (setup skill)** — interactive-vs-autonomous boundary; survey of ≥3 repo shapes.

Standard-pattern phases (skip research):
- **Phase 0** — purely mechanical.
- **Phase 1** — timm pattern is reference-class.
- **Phase 2** — TorchX shape is documented.
- **Phase 3** — JSONL + OTel + SKILL.md are standardized.
- **Phase 8** — grep -r + integration-test discipline.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Reference-class implementations (submitit/FAIR, Ray/Anyscale, timm/HF, TorchX/Meta, AGENTS.md/Linux-Foundation, OTel/CNCF). MEDIUM only on telemetry serialization choice (OTel `gen_ai.*` won 2025 standardization but spec still "in development"). |
| Features | HIGH | 9-comparator benchmarking with explicit per-feature presence/absence matrix. MEDIUM on novel-axis claims (multi-runtime, gate, search-scope, setup skill) since these intersect emerging agentic-ML tooling. |
| Architecture | HIGH | Individual patterns are reference-class. MEDIUM on integrated layout — opinionated and untested at autoMIL scale; will need a pilot in migration phase. |
| Pitfalls | HIGH | Every critical pitfall directly evidenced in `automil_qa.md`, `CONCERNS.md`, F2 proposal, OR reference-class case study (Ray-on-SLURM #19942/#13607, K8s #94435 grace period, MLflow/Portkey scrub-on-capture, BSWEN agent drift). |

**Overall confidence: HIGH.**

### Gaps to Address

- **K calibration data missing** — gate threshold informed-guess until pilot. Mitigation: Phase 5 starts with pilot (apply CCRCC `node_0176` to 3-5 fresh cells) before locking K. Surface K as config.
- **Codex/OpenCode/Gemini-CLI runtime hooks** — Claude has documented `Stop` hook + post-tool-use; equivalents partially documented. Plan B (`automil trajectory record <event>` CLI subcommand) covers runtimes without native hooks. Phase 3 deliverable explicitly includes per-runtime hook integration table.
- **Hardware test matrix coverage** — autodetect must work on ≥3 hardware shapes; today only the workstation is available. Mitigation: Phase 7 acceptance gates on at least one external hardware shape; otherwise ship as "tested on workstation, autodetect output REPORTED not silent, override path documented" and mark portability MEDIUM not HIGH.
- **Trajectory schema evolution** — schema-version locked at v1; future runtime tool-schema changes require versioned migrations. Mitigation: ADR documenting trajectories as forensic artifacts (replay best-effort), NOT replayability claims.
- **Mode default (architecture-preserving vs free)** — recommendation: ship `free` as F2-aligned default; opt-in to `architecture-preserving`. Confirm in Phase 1 planning.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md`
- `.planning/codebase/{ARCHITECTURE,CONCERNS,STACK}.md`
- `.planning/research/STACK.md` (476 lines)
- `.planning/research/FEATURES.md` (240 lines)
- `.planning/research/ARCHITECTURE.md` (743 lines)
- `.planning/research/PITFALLS.md` (339 lines)
- `tasks/automil_qa.md`
- `tasks/automil_proposal.md`
- Standing user feedback memory (saturate GPUs, research before submit, never blind-checkout, architectural-not-hyperparam, never ask continue autonomously)

### Secondary (MEDIUM-HIGH, cited inline in source docs)
- submitit (FAIR), Ray on SLURM (Anyscale + GitHub #19942 #13607), AGENTS.md (Linux Foundation), Claude Code Skills, opencode agents+skills, OpenTelemetry GenAI semconv, SWE-bench / SWE-rebench / OpenHands trajectory format, TorchX schedulers (Meta), timm registry source (HuggingFace), MLflow LLM Tracing, Portkey LLM Observability, Kubernetes #94435, Snakemake SLURM executor, LangSmith trajectory evals.

### Tertiary (MEDIUM, sole-source or inference)
- DeepSeek harness routing (devtk.ai blog corroborating official API docs)
- Hydra-zen rejected on brownfield-cost grounds (direct doc read; rejected on cost not capability)

---
*Research synthesis completed: 2026-05-01*
*Ready for roadmap: yes — proceed to requirements scoping (Step 7) and roadmap creation (Step 8)*
