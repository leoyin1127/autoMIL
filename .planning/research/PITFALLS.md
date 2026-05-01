# Pitfalls Research

**Domain:** Brownfield refactor of an LLM-driven autonomous experiment framework — registry pattern, pluggable scheduler backends, multi-runtime agent support, hard wall-clock budgets, trajectory snapshots, generalization gates, framework decoupling, hardware auto-detection.
**Researched:** 2026-04-30
**Confidence:** HIGH (most pitfalls are directly evidenced in `tasks/automil_qa.md`, `.planning/codebase/CONCERNS.md`, the F2 proposal, and the same refactor patterns are well-documented in 2025-era SLURM/Ray/Parsl, OpenAI Codex / Anthropic Skills, and ML-checkpoint literature).
**Scope note:** The fragilities already catalogued in `.planning/codebase/CONCERNS.md` (process-group leak, naive `.env` parser, hard `mark_running` assert, O(N²) scoring, viz vendoring, `_recover_orphans` race, results.tsv ownership) are NOT re-listed here. The pitfalls below are NEW failure modes that the refactor itself introduces, plus regressions that the refactor could trigger if executed naively.

---

## Critical Pitfalls

### Pitfall 1: "Still uses old path" — registry exists but shared library files keep getting edited

**What goes wrong:**
The variant registry is built. Variant modules ship in `experiments/<dataset>/registry/`. But `train.py`, `core_utils.py`, and `model_clam.py` are still importable, still mutable, and still on the agent's path. The agent (or a future contributor) edits them anyway because the existing skill instructions, the Q&A document, every prior CCRCC commit, and the muscle memory of 195 prior experiments all point at editing those files. The new registry runs alongside an old direct-edit pathway that nobody disabled.

**Why it happens:**
Brownfield refactors that introduce a new pattern without disabling the old one almost always end with both patterns coexisting. The agent has 195 prior experiment archives in its training context (literally — every `archive/<node_id>/spec.json` lists files like `benchmarks/lib/CLAM/utils/core_utils.py`); the path of least resistance is to re-edit those same files. Documented exactly in `automil_qa.md:14-30`: "the per-dataset config.yaml configs are almost cosmetic — the actual behavior is baked into the shared Python files."

**How to avoid:**
1. Phase the refactor as **disable-old → enable-new**, not enable-new-and-hope-old-fades. The submit pre-validator must reject any overlay touching paths in a `registry.protected` list. `automil check` must fail loudly if the working tree has uncommitted edits to protected files.
2. Update **every** skill prompt, every example in agent_assets, the `learnings.md`, and the `automil propose --desc` template to remove references to direct edits of `core_utils.py` / `train.py`.
3. Make the registry the **only** way to introduce architectural mutation: training script reads variant from `config.yaml`, imports it from registry, and the variant module is the only place mutation lives. No env-gated switches in shared libs.
4. Reproduction sanity check (CCRCC node_0176 reproduces ±0.005) MUST run against a clean checkout where the protected files are guaranteed unmodified — otherwise it accidentally validates the dirty path.

**Warning signs:**
- A submitted overlay's `files` list contains anything under `benchmarks/lib/` or `benchmarks/src/autobench/pipeline/clam/train.py`.
- Two consecutive winning nodes share a config but differ in their modifications — meaning the modification is not in the config-tracked variant.
- `git diff base_commit benchmarks/lib/` is non-empty after a "fresh start."
- New dataset onboarding (Yeonwoo / Keishi / Ryan) starts with "first apply the CCRCC patch."

**Phase to address:**
Registry refactor phase (Variant Registry + Config-Driven Train). Type: **design-time gotcha** — the disable-old gate must be in place before the registry is declared shipped.

---

### Pitfall 2: Backend ABC leaks SLURM / Ray / local semantics into common code

**What goes wrong:**
The `OrchestratorBackend` ABC is designed against the local backend (which is what exists today). Two months later when the SLURM backend is added, four "small" leaks surface: (a) local backend uses live PIDs to detect crashes; SLURM uses `sacct` lookups that may be hours stale, so a generic `is_running()` returns `True` for jobs that died at 03:00 and got billed and reaped. (b) Local can SIGTERM-then-SIGKILL a process; SLURM `scancel` is fire-and-forget and the job keeps running for the grace period. (c) Local sees a single shared filesystem; SLURM workers may have node-local scratch with eventual sync to home. (d) Ray's actor model wants long-lived workers; the current code spawns a fresh `subprocess.Popen` per experiment. The ABC becomes a leaky abstraction (in [Ray's own SLURM-deployment docs](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html), this is documented as "unintuitive" — Ray expects head/worker, SLURM expects independent task copies).

**Why it happens:**
Designing an ABC against one implementation freezes that implementation's assumptions into the interface. The local backend's `_handle_timeout(SIGTERM → sleep 5 → SIGKILL)` from `orchestrator.py:578-587` is a control-flow, not a state-machine — porting it to SLURM means the ABC must allow asynchronous "termination requested, status pending" states. The local backend's `running_on` dict assumes a process can be looked up by PID at any instant; SLURM workers do not expose PIDs to the head node.

**How to avoid:**
1. **Implement two backends in parallel before locking the ABC.** Even if the second is a "MockSLURM" that simulates: (a) eventual-consistency status (5s lag), (b) no PID, only opaque job_id, (c) fire-and-forget cancel that takes 30s to reflect, (d) node-local filesystem (worktree path differs per worker), (e) outputs uploaded asynchronously. Any ABC method that doesn't survive both implementations is leaky.
2. Make state, not control-flow, the unit of abstraction. `submit()` returns a `JobHandle`; `poll()` returns `JobState ∈ {QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, UNKNOWN}` — the orchestrator's main loop reconciles state to actions, not the other way around.
3. Forbid `os.kill`, `os.killpg`, PID, and direct `subprocess.Popen` access from the orchestrator main loop. Those are local-backend implementation details, not orchestrator interface.
4. Result collection MUST be filesystem-mediated (`result.json` at agreed path) and MUST NOT depend on PID-attached stdout — SLURM stdout is per-step files, Ray actor stdout is captured via Ray's own log-aggregation.
5. Concurrency-per-GPU is a **local-backend concept**, not a backend-agnostic one. SLURM does the bin-packing at the cluster level; pushing local's bin-packer onto the SLURM backend reinvents what SLURM already does correctly. The ABC should accept "schedule N independent jobs against a resource specification" and let the backend decide how.

**Warning signs:**
- The ABC has a `process` attribute, returns `Popen` objects, or exposes PIDs.
- Local backend tests pass; mocked-SLURM backend tests reveal "this method assumes synchronous status."
- A new method gets added with a `# only for local backend` comment.
- The orchestrator main loop has `if isinstance(backend, LocalBackend):` branches.
- Bin-packing logic (`_find_best_gpu`, `MAX_CONCURRENT_PER_GPU`, `safety_margin_gb`) referenced from non-local backend.

**Phase to address:**
Pluggable Backends phase. Type: **design-time gotcha** — once the ABC is shipped and one backend is in production, retrofitting changes is a major lift. Build local + mock-SLURM together.

---

### Pitfall 3: Multi-runtime skill scaffolding ships, but only Claude is actually tested

**What goes wrong:**
`agent_assets/{claude,codex,opencode,deepseek}/` is created. `automil init` detects runtime and writes the relevant scaffolding. The Claude skill is the same battle-tested one from CCRCC's 195 experiments. The Codex skill is a copy-paste of the Claude skill with `CLAUDE.md` renamed to `AGENTS.md`. The OpenCode skill is empty TODO. Nobody runs an actual experiment against Codex or OpenCode before declaring multi-runtime "shipped." The proposal in §7 lists "F2's 'this is a Claude paper' reviewer attack" as the threat — but a copy-pasted skill defends nothing if a reviewer actually tries it. The reality of skill formats: per [the Glukhov writeup](https://www.glukhov.org/ai-devtools/claude-code/claude-skills-for-developers/), `.agents/skills` is the cross-client convention, but Claude scans `.claude/skills`, Codex uses `AGENTS.md` with hierarchical configs and a different slash-command system, and OpenCode uses MCP to extend tool capabilities — each runtime has different prompt-injection rules, different tool-call schemas, different context-window limits, different "system prompt" behavior, and (critically) different default tool names.

**Why it happens:**
Skill prompts are small text files; they look portable. They are not. Tool names differ (`Edit` vs `apply_patch` vs `str_replace_editor`), tool argument schemas differ, the model's reasoning style differs, the runtime's slash-command vs file-trigger conventions differ, and prompt-portability across runtimes is an unsolved problem in 2025-26. A prompt that says "use the Read tool" is meaningless to a runtime where the tool is `read_file`.

**How to avoid:**
1. **Multi-runtime is not "ship scaffolding"; it is "validate one experiment end-to-end on each runtime."** The acceptance criterion for the multi-runtime feature is: a single experiment that produced a valid `result.json` was run against ≥2 distinct runtimes (e.g., Claude + Codex), graph reconcile is consistent, trajectories captured for both. Anything less is shelfware.
2. Constrain what skills do to the **runtime-agnostic** parts: read CLAUDE.md / AGENTS.md (provide both as symlinks or one canonical with a runtime-specific frontmatter), call `automil propose / submit / status` via shell. Do not assume tool names. Skills should be ~80% CLI-driven and ~20% prompt-driven.
3. Pin runtime versions in the per-runtime asset dir: `agent_assets/claude/SKILL.md` declares "tested with claude-opus-4-7@2026-04-30". Trajectory snapshots must record the runtime and version (see Pitfall 5).
4. Document the irreducible-difference table somewhere durable: tool-name aliases, slash-command differences, system-prompt placement, max context. This table is the actual deliverable of multi-runtime support.
5. If only Claude is validated end-to-end by milestone close, ship the framework supporting only Claude **explicitly** and mark Codex/OpenCode as "scaffolded, not validated." Don't oversell.

**Warning signs:**
- The Codex / OpenCode / DeepSeek skill files are byte-identical to Claude's after find-replace of `CLAUDE.md` → `AGENTS.md`.
- No experiment in `archive/` has a non-Claude runtime tag in `spec.json`.
- The CCRCC reproduction sanity check is run only on Claude.
- README claim: "supports Claude, Codex, OpenCode, DeepSeek" with no per-runtime test evidence.

**Phase to address:**
Multi-Runtime phase. Type: **ongoing discipline** — every skill update has to be re-validated on each declared-supported runtime. This pitfall returns at every release.

---

### Pitfall 4: 6h cap is a wall-clock guillotine — last fold gets SIGKILL'd, partial result corrupts results.tsv

**What goes wrong:**
The cell budget hits zero at 5h59m. The orchestrator sends SIGTERM to all running experiments. Half of them are mid-fold-4-of-5 (CCRCC took ~4h/run; folds are sequential inside one experiment). The training script has no SIGTERM handler. After the 5-second grace (or `kill_timeout` of 30s), the orchestrator SIGKILLs them. State of the world:
- Worktree partially written: `result.json` not present, but fold 1-3 results are saved as separate JSONs.
- VRAM not released (the existing process-group bug from CONCERNS.md compounds: now there are 8 orphaned processes per GPU).
- The experiment has no row in results.tsv (orchestrator never collected `result.json`).
- The graph node is stuck in `running` forever (no terminal status). On next daemon restart, `_recover_orphans` marks it `crash` with composite=0, which then dominance-kills its already-completed siblings via the cascade described in `_reevaluate_descendants` (CONCERNS.md, Fragile Invariant #6).
- The 6h deadline is a hard cap, so no retry budget remains.

A subtler variant: the agent submits 8 experiments at hour 3 expecting them to take 4h each. The orchestrator accepts because budget shows 3h remaining. At hour 6, all 8 are killed mid-run. Net useful output: zero.

**Why it happens:**
Hard wall-clock budgets without graceful-termination protocols are a well-known anti-pattern (per [Kubernetes #94435](https://github.com/kubernetes/kubernetes/issues/94435), even with declared grace periods, systems regularly fail to honor them; SLURM provides a SIGTERM → SIGKILL signal sequence specifically because graceful is hard). The CV-fold loop is a long uninterruptible scientific computation — the granularity of "useful work unit" is "one fold," not "one experiment." Budgeting at the experiment granularity throws away K-1 folds of work when K hasn't completed. This pitfall is invisible until the first time the cap actually fires in production.

**How to avoid:**
1. **Per-fold checkpoint + `result.json`-on-each-fold.** Training scripts write `fold_<i>_result.json` after each fold completes; the framework's `result.json` aggregator computes composite from however many folds completed. `partial_folds: 3` is a valid result, just with widened confidence intervals. This means a SIGTERM at hour 5h59m leaves a usable result, not zero.
2. **Refuse-new-submits earlier than terminate-running.** Budget `T - safety_buffer` (e.g., 5h0m of a 6h cap) is the submit-refusal point; budget `T` is the kill point. Safety buffer ≥ longest expected single-fold duration. Agent gets clear signal "no more submits this cell" before any kill happens.
3. **SIGTERM handler in train.py that flushes `partial_result.json` and exits cleanly.** Five-second grace is for systems that can checkpoint in five seconds; CLAM training cannot. Either implement fold-granularity checkpointing OR extend the grace period (and accept that the kill is delayed).
4. **Process-group + propagated SIGTERM.** Already a CONCERNS.md issue, but compounded under the cap: every kill must use `start_new_session=True` + `os.killpg`. Without this, partial-fold orphans hold VRAM and the next cell starts contaminated.
5. **The cell-budget timer must continue across daemon restarts.** Operator restart at hour 4 must not reset the budget to 6h (sandbagging). Persist `cell_started_at` to disk.
6. **Distinguish "killed by budget" from "crashed."** Budget-killed nodes must reconcile to `executed` with whatever folds completed, not `crash`. Otherwise the descendant-cascade (CONCERNS.md Fragile Invariant #6) wipes useful sibling data.

**Warning signs:**
- Test of the budget-cap mechanism reveals zero rows in results.tsv when the cap fires mid-experiment.
- Orphaned `running/` specs after every cell-budget exhaustion.
- VRAM doesn't return after a budget-cap kill (running `nvidia-smi` still shows the process's memory after the orchestrator declared it terminated).
- Partial-fold checkpoints exist on disk but no row in results.tsv references them.

**Phase to address:**
6h Cap phase. Type: **design-time gotcha** — the partial-fold protocol has to be designed before the cap is enforced, or the first production cap will lose work.

---

### Pitfall 5: Trajectory snapshots leak API keys, blow up disk, and fossilize one runtime's tool schema

**What goes wrong:**
`archive/<node_id>/trajectory.jsonl` ships. Per the F2 proposal §6, this is for "as-protocol reproducibility." Three failure modes converge:

(a) **Secret leak.** Tool calls include the model's system messages, environment dumps, and (when an agent ran `printenv` or read `.env` to debug a path issue) the raw `OPENAI_API_KEY`, `WANDB_API_KEY`, `HF_TOKEN`. CONCERNS.md already flagged that `subprocess env = {**os.environ, ...}` leaks the parent env into experiments — trajectories serialize that env. Trajectories then commit to git? Get pushed? Get published as a reproducibility artifact for the F2 paper? Each step reveals secrets in a slightly larger blast radius. (Industry-standard mitigations from [LLM observability platforms like MLflow Tracing](https://mlflow.org/llm-tracing/) and [Portkey's observability guide](https://portkey.ai/blog/the-complete-guide-to-llm-observability/) include scrub-rules at capture time, not at publish time.)

(b) **Size explosion.** Each tool call serialized verbatim. A single experiment session with the agent reading 50 files, running 30 bashes, and writing 20 files produces ~5-50 MB of JSONL. 200 experiments × 30 MB = 6 GB. Multiply by future cohorts (Yeonwoo's 16 TCGA cohorts × ~100 experiments each × 30 MB ≈ 50 GB). At that point the archive directory is a compliance liability and a `git status`-slowness liability.

(c) **Format churn / fossilization.** Trajectories captured against `claude-opus-4-7@2026-04-30` use that model's tool schema (Read, Edit, Bash, etc.). Six months later Anthropic ships a new tool schema (e.g., consolidates Read/Write/Edit into a unified `file_op` tool with different argument shapes — this kind of churn happens, see "tool changes affecting execution patterns" in [agent behavior drift](https://docs.bswen.com/blog/2026-03-20-agent-behavior-drift-detection/)). Old trajectories no longer "replay" against the new schema. The F2 reproducibility claim ("we captured the trajectory") is technically true but operationally false — the trajectory cannot be re-executed. Worse: trajectories captured cross-runtime (Codex vs Claude — see Pitfall 3) use different tool schemas, so a trajectory analysis script written against Claude format silently silently mis-parses Codex trajectories.

**Why it happens:**
Trajectory capture sounds like "just write the messages to a file." It is actually three orthogonal hard problems: secret-scrubbing, retention, and format-versioning. None are solved by `json.dumps`.

**How to avoid:**
1. **Scrub at capture.** A redaction pass before write: regex for known secret patterns (`sk-`, `hf_`, `ghp_`, AWS keys, anything matching `*_API_KEY=`), pop env-dump frames entirely, hash file paths if they contain home-dir personal info. Default-deny if uncertain. Required configurable allowlist for env vars that *must* be preserved (e.g., `AUTOBENCH_*`).
2. **Cap size + structured format.** JSONL with explicit `version: "trajectory-v1"`, max bytes/event truncated with `…[truncated]`, max events/session, soft-fail to "trajectory partial" rather than crash the session.
3. **Schema-version per runtime.** `trajectory.jsonl` first line is metadata: `{"runtime": "claude-code", "runtime_version": "...", "tool_schema_version": "claude-2026-04", "automil_version": "..."}`. Replay code MUST gate on this. Schema changes require a new version label and a documented mapping from old → new.
4. **Don't commit trajectories by default.** Trajectories live in `archive/<node_id>/trajectory.jsonl` which is gitignored. Promotion to git is per-trajectory, conscious, and re-scrubbed.
5. **Don't claim replayability you don't have.** "Trajectories captured" ≠ "experiments replayable." Be honest in paper text: trajectories are a forensic artifact; replay is best-effort with a documented success rate.

**Warning signs:**
- A fresh trajectory file contains the substring `sk-` or `_TOKEN=` or `_KEY=`.
- `du -sh archive/` grows >1 GB per ~50 experiments.
- An attempt to replay a trajectory against the same runtime+version fails because of a tool schema mismatch.
- The framework or paper claims "fully reproducible via trajectory replay" but no replay test runs in CI.

**Phase to address:**
Trajectory Snapshots phase. Type: **ongoing discipline** — secret-scrubbing and schema-versioning need to be re-validated every runtime upgrade and every new tool addition.

---

### Pitfall 6: Generalization gate is too strict — search converges to nothing; or too loose — search stays where it was

**What goes wrong:**
The proposal §38 states: "candidate variants must improve on ≥K held-out cells before being promoted." Two tail failures:

(a) **K too high.** With K=18 held-out cells per parent (the F1 grid full size), no candidate ever passes — multi-task generalization is hard, and even a real improvement that wins 12/18 cells is rejected. The search loop appears to run normally (proposes, executes, evaluates) but the registry never grows. Three months in, the headline claim is "we built a search loop and ran 5000 experiments; zero variants promoted." This is the failure mode noted in F2 risk row 5 ("F2 doesn't add gain beyond F1's bounded recipe") amplified by gate strictness.

(b) **K too low.** With K=1 held-out cell, a candidate that wins the held-out cell by overfitting it gets promoted. Now CLAM-autoMIL is a CCRCC-Virchow2-overfit variant masquerading as a general improvement, and the F1 leaderboard shows it winning by a margin that disappears the moment a reviewer evaluates it on TCGA-LUAD. F1's own headline claim ("autoMIL Recipe Set v1.0 reorders ≥40% of pairwise rankings") is at risk of being a reviewer's trivial counterexample.

A third subtle mode: **gate evaluated on the same cells used during search** (no held-out). Looks like a generalization gate; is actually a re-use of training data for validation. This is the same statistical mistake that made `node_0194` (Lookahead leak) appear to score 0.8914 — leaking validation signal into the model. Gate logic that doesn't enforce strict held-out separation just hides leakage one level up.

**Why it happens:**
Held-out generalization gates require: (i) deciding the held-out cell set BEFORE search starts, (ii) committing it cryptographically (signed manifest, not "I promise not to peek"), (iii) keeping the agent's loop blind to held-out outcomes during search, (iv) calibrating K against expected effect sizes. Skipping any of these turns the gate into theatre.

**How to avoid:**
1. **Pre-register held-out cells.** A signed `gate_manifest.json` per parent at search start: `held_out_cells: [...], K_threshold: N, win_definition: "delta_composite > 0 && p<0.05 paired-bootstrap"`. The agent's search-loop prompt does not include held-out cell evaluation results until after the search budget exhausts.
2. **Calibrate K empirically.** Pilot on 3-5 cells with a known-good change (e.g., applying CCRCC's `node_0176` config to fresh cells). Measure what K corresponds to "the kind of improvement we'd want to promote." Don't pull K from gut feel.
3. **Define "wins" as paired-test passing, not raw delta.** Per F1 §4.4 and §5.6, paired Wilcoxon with bootstrap CIs and Bonferroni — the gate must use the same statistical machinery the paper claims, otherwise you build a worse gate now and have to redo it for the paper.
4. **Two-stage gate.** Stage A: candidate passes a quick-and-dirty improvement on the search cells. Stage B: candidate passes the held-out generalization test. Promotion to the registry requires both. Search budget is in Stage A; held-out evaluation budget is in Stage B and is **separate**.
5. **Monitor gate-pass rate as a search-health metric.** If 0/100 candidates pass over a week, the gate is too strict OR the search space is too narrow — both demand action. If 50/100 pass, the gate is too loose.

**Warning signs:**
- Promotion-rate is 0% over a multi-week period.
- Promotion-rate is >30%; promoted variants have wide cross-cell variance.
- Held-out cell results are visible to the agent during search (check the trajectory).
- The gate's "win" definition is `delta > 0` rather than a paired statistical test.
- Held-out cell set is decided after seeing search results.

**Phase to address:**
Generalization Gate phase. Type: **design-time gotcha for the held-out protocol** + **ongoing discipline for K calibration** as cohorts are added.

---

### Pitfall 7: Decoupling autobench breaks tests, hides the bench-specific assumptions, and creates a private API

**What goes vrong:**
"Zero autobench paths, env vars, or training-script schema in `src/automil/`" is the goal (PROJECT.md). What actually happens:

(a) **Test-suite collapse.** The 48 tests heavily exercise `benchmarks/scripts/run_experiment.py` schema implicitly. After purging autobench-isms, tests pass against the new abstract API but no longer prove the framework actually drives a real training script. CCRCC reproduction sanity check is now the only end-to-end test. If it's flaky (it likely will be — 4-hour runtime), the test suite becomes a green-light to ship something that doesn't run.

(b) **Hidden coupling re-emerges.** The framework "doesn't reference autobench paths" but documents `result.json` as the contract. autobench writes `result.json`. Now anyone wanting to plug in a non-autobench training script discovers that the framework expects `metrics.val_auc`, `metrics.test_bacc`, and the four-key composite from `automil/scoring`. That's a private API masquerading as generic. A user trying to plug in image classification (`metrics.top1`) finds the scoring module silently treats a missing `val_auc` as 0 and dominance-discards their experiment.

(c) **Path-and-env decoupling shifts the burden to users.** Today `AUTOBENCH_*` env vars are loaded by orchestrator's `_load_dotenv` (CONCERNS.md, areas of past mistakes #3). After decoupling, the framework promises nothing about env loading. The user's training script works on the user's machine and crashes inside the worktree. Past CCRCC pain repeats for every new user.

(d) **The framework keeps a mental model of "the training run" that's autobench-shaped.** The 5×5 CV grid, the per-fold result aggregation, the "composite" score — these are autobench's idioms. A user with a single train/val/test split has to fake CV to fit the framework's assumptions.

**Why it happens:**
Decoupling is hard. Frameworks designed against one consumer encode that consumer's idioms in the abstract API. The proposal §40 says decouple; doing it cleanly requires identifying every autobench-specific assumption and either generalizing it, parametrizing it, or making it a consumer-side responsibility.

**How to avoid:**
1. **Plug a second consumer before declaring decoupling done.** Even a tiny one — e.g., a sklearn-iris training script that produces `result.json`. If the framework can run it, decoupling is real. If autobench is the only consumer that works, decoupling is just renaming.
2. **Document the contract explicitly.** `docs/training-script-contract.md`: input env vars provided by orchestrator (`AUTOMIL_GPU`, `AUTOMIL_RUN_DIR`, `AUTOMIL_VARIANT`, `CUDA_VISIBLE_DEVICES`), expected outputs (`result.json` schema with required + optional fields), exit-code conventions, signal-handling expectations (Pitfall 4). Treat the contract as the API. Schema-validate `result.json` against a JSON Schema; reject malformed.
3. **Make scoring pluggable.** `composite` cannot be hardcoded as `f(val_auc, val_bacc, test_auc, test_bacc)`. Project's `automil/config.yaml` declares the composite formula or names a Python entry point. Default keeps autobench's behavior.
4. **Env-var declaration in config.** `automil/config.yaml` lists required env vars; `automil check` validates they're set. Decouples "framework loads .env" (autobench-specific path) from "experiment needs X env" (config-declared).
5. **Keep autobench tests as integration tests.** Don't purge them — promote them. Add a contract-test layer that runs against a minimal mock training script, separate from the autobench end-to-end test.

**Warning signs:**
- After the decoupling phase, only autobench experiments produce non-zero composites (because `metrics.val_auc` is the magic key).
- A user asks "how do I add my own metric to the composite?" and the answer requires editing `src/automil/`.
- Test coverage drops in `tests/` after the decoupling commit.
- The framework imports from `autobench` anywhere in `src/automil/`.
- User onboarding requires a person who has seen autobench before.

**Phase to address:**
Autobench Decoupling phase. Type: **design-time gotcha** — once the contract is wrong, every consumer has to work around it. Ship a second consumer at decoupling time.

---

### Pitfall 8: Hardware auto-detection is a 3-RTX-6000 confidence trick

**What goes wrong:**
Auto-detection works on Leo's 3-GPU 48 GB machine because the constants (8 concurrent/GPU, 2 GB safety margin, 0.4 GB/CLAM-run, 1 GB default vram_estimate) were tuned there. The detection logic is `len(nvidia_smi) → MAX_CONCURRENT_PER_GPU = 8`. When Yeonwoo runs it on a single-GPU 24 GB consumer card:
- The default vram estimate of 1 GB × 8 concurrent = 8 GB; minus the 2 GB safety tax = 6 GB schedulable; CLAM run takes ~3 GB peak in some configurations; throughput is 2-3 concurrent at most, not 8. Auto-detection guesses 8 and the GPU OOMs after a flurry of submits.
- On a 16 GB laptop card: every submit is rejected because 1 GB × 8 + 2 GB safety > 16 GB on a quiet day, but on a dirty day with the user's browser open, 1.5 GB is occupied and the math fails.
- On an 80 GB H100 cluster node: 8 concurrent is dramatic under-utilization. Throughput is 1/3 of what the hardware can deliver.
- On a multi-node SLURM allocation: `nvidia-smi` runs on the login node, sees 0 or 8 GPUs depending on which login node, and gets a wrong picture of what the worker node has.

CONCERNS.md already flags the manual-config-leak version of this (`default_vram_estimate_gb` is per-experiment and per-machine; agent must remember to override). Auto-detection promises to fix it but actually replaces explicit config with implicit-and-machine-specific assumptions.

**Why it happens:**
"Hardware auto-detection" usually means "I detected my hardware once and hardcoded constants." True hardware-aware sizing requires per-experiment empirical VRAM measurement (CONCERNS.md, Performance Concerns #1, suggests this — "track empirical peak VRAM in `results.tsv` (already there) and feed back into `default_vram_estimate_gb` automatically"). That's a different feature from "detect GPU count at startup."

**How to avoid:**
1. **Detect-and-warn, not detect-and-decide.** `automil init` reports detected hardware: `Detected: 3× NVIDIA RTX 6000 Ada (48 GB), 64 CPU cores, 256 GB RAM`. Suggested defaults are surfaced; user confirms or overrides. This is honest about uncertainty. Auto-detection that silently picks defaults is auto-failure.
2. **Empirical VRAM feedback loop.** Per CONCERNS.md, `results.tsv` already has `peak_vram_mb`. Use it. After N experiments complete, the orchestrator updates `default_vram_estimate_gb` to `quantile_95(peak_vram_mb) + 0.5 GB`. Logged: "Updated VRAM estimate from 1.0 GB to 0.6 GB based on 30 completed runs."
3. **Per-variant VRAM estimates.** A TransMIL variant with attention has a different VRAM profile than CLAM-MB. Track per-variant. The variant registry (Pitfall 1) is where this lives.
4. **Test on at least three hardware shapes before claiming portability.** Single-GPU laptop, 3-GPU workstation (current), multi-GPU server with a different memory size (e.g., a 24 GB card or an 80 GB H100). Without this, "portability" is "works on Leo's box."
5. **Document the failure mode loudly.** If auto-detection picks values that under- or over-utilize the hardware, the daemon log must say so on first scheduling tick, not silently accept it.
6. **Defer multi-node hardware detection.** SLURM-backend detection is the SLURM backend's job (it knows about `SLURM_GPUS_PER_NODE`, `SLURM_CPUS_PER_TASK`); do not let local-backend's `nvidia-smi` heuristic leak into the SLURM path. (This is also why Pitfall 2's anti-leak discipline matters.)

**Warning signs:**
- A user reports "every submit gets rejected" or "GPU OOMs after 3 minutes."
- `default_vram_estimate_gb` is the same value that shipped at init, after 100 experiments completed.
- Auto-detection's output is `MAX_CONCURRENT_PER_GPU = 8` regardless of GPU memory size.
- The reproduction sanity check (CCRCC node_0176) only runs on the same hardware that produced node_0176.

**Phase to address:**
Hardware Auto-Detection phase. Type: **design-time gotcha for the detect-and-warn pattern** + **ongoing discipline for empirical feedback** (the VRAM estimator drifts as variants change).

---

### Pitfall 9: Skill-based `/automil-setup` swallows context and produces wrong scaffolding silently

**What goes wrong:**
The proposed `/automil-setup` skill (PROJECT.md L41) "inspects repo, identifies training entry point, drafts config + agent prompt, scaffolds registry, picks defaults from detected hardware." On a normal-shaped repo this works. On the actual repos this will encounter — TCGA cohorts in various stages of extraction, mixed-language repos, repos with multiple `train.py` candidates, repos where the training entry point is `python -m something --config foo.yaml`, repos with nested git submodules — it confidently picks the wrong entry point, scaffolds against the wrong file, drafts a config that points at a non-runnable target, and the user's first experiment crashes with a stack trace four levels deep into a worktree.

Worse: the skill is "one-shot, autonomous, idempotent" (PROJECT.md). One-shot means the user runs it once and accepts what comes out. Idempotent means re-running it produces the same wrong output. Autonomous means there's no checkpoint where the user catches the mistake.

**Why it happens:**
Setup-skills are a relatively new pattern (Anthropic's Agent Skills shipped in 2025; cross-runtime conventions are still settling — see Pitfall 3). They fail differently from CLI commands: a CLI command has a defined input/output contract; a skill is a prompt that can hallucinate a plausible-looking config and never report uncertainty. The agent's calibration on "this looks right but isn't" is famously poor in agent-driven setup contexts.

**How to avoid:**
1. **Setup is interactive by default.** The skill drafts; the user reviews each scaffolded file before commit. "Autonomous" means no manual editing of files inside the framework directory; it does not mean no human-in-the-loop review.
2. **Detect-then-confirm at every decision point.** "I see `train.py`, `scripts/run_experiment.py`, and `src/foo/main.py`. Which is your entry point?" Don't let the skill pick.
3. **Validate the scaffolded config by running `automil check` AND a dry-run experiment.** A dry-run experiment is a 1-minute fake run that exercises the orchestrator → worktree → training-script → result.json path with mock data. If the dry-run fails, scaffolding is rejected and the user sees the actual error.
4. **Keep `/automil-setup` opinionated, not exhaustive.** It handles ~80% of cases (single train.py at a known location, single GPU setup, autobench-shaped). For the long tail it bails and asks the user to manually set `<5 keys>. Don't let it pretend to handle everything.
5. **Log the skill's reasoning trace.** The setup skill writes `.planning/setup-trajectory.md` showing every decision and its rationale. If the scaffold is wrong, the user can see why.
6. **CLI fallback exists for everything.** Anything the skill does, the user can do via CLI commands. The skill is convenience, not the only path. The standing memory (`feedback_no_plans_without_permission.md`) and the Project's Key Decisions row 2 ("Skills only for autonomous setup; CLI for everything else") imply this — codify it.

**Warning signs:**
- Setup skill produces a config with a `TODO:` substring (CONCERNS.md, Tech Debt #7 — `automil check` already flags TODOs; setup must not produce them).
- Setup skill scaffolds against a `train.py` that doesn't exist or isn't the training entry point.
- First experiment after setup crashes immediately.
- Setup skill never asks a question even on ambiguous repos.
- A re-run of `/automil-setup` on the same repo produces different scaffolding (non-idempotent).

**Phase to address:**
Setup Skill phase. Type: **design-time gotcha** for the interactive-vs-autonomous boundary; **ongoing discipline** for keeping the skill calibrated as new repo shapes appear.

---

## Technical Debt Patterns

Shortcuts that seem reasonable in this refactor but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Local backend implements ABC; SLURM/Ray are stubs | Ships ABC fast; SLURM is "future work" | ABC freezes around local's PID/sync semantics. Pitfall 2 manifests when SLURM is added later. | NEVER acceptable — build at least a mock-SLURM in parallel. |
| Variant registry runs alongside dirty edits to shared libs | Backward-compat for in-flight CCRCC work | Pitfall 1: muscle memory + skill prompts keep editing shared libs. Both paths drift. | Acceptable for ≤1 week if the dirty edits have a deletion-PR open. |
| Trajectory snapshots written but never replayed | Ship the feature; "as-protocol replay" is paper-time work | Pitfall 5(c): format drift makes the trajectories non-replayable by the time the paper writes the claim. | Acceptable IF the framework explicitly says "trajectories are forensic, not replayable." |
| Hardware "auto-detection" returns hardcoded constants | Most users on similar hardware see correct defaults | Pitfall 8: outlier hardware (laptops, H100s, multi-node) silently gets wrong defaults. | Acceptable IF the detection output is reported and the user can override. |
| Multi-runtime support = scaffolding only, Claude is tested | Defends "this is a Claude paper" attack on paper | Pitfall 3: reviewer or new user actually tries Codex, finds it broken. Reputation damage. | Acceptable IF README explicitly marks Codex/OpenCode as "scaffolded, not validated." Don't claim what's not tested. |
| 6h cap kills mid-fold; partial folds discarded | Simple wall-clock implementation | Pitfall 4: the first cap-firing event loses K-1 folds × N concurrent experiments of work. Catastrophic. | NEVER — partial-fold checkpointing must ship with the cap. |
| Generalization gate uses search-cells for "held-out" | Saves planning effort | Pitfall 6: gate is a no-op or worse, hides leakage. F1/F2 paper claims become indefensible. | NEVER — held-out separation is non-negotiable. |
| Setup skill doesn't ask questions; picks defaults | Faster onboarding | Pitfall 9: silent mis-scaffolding. User's first experiment crashes; they debug for hours. | Acceptable for opinionated cases (single train.py at convention path) IF the skill is honest about non-handling for edge cases. |

---

## Integration Gotchas

Cross-cutting mistakes when wiring the new components together.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Variant registry × `automil submit` overlay | Auto-detect overlay still picks up shared-lib edits because `git diff` doesn't know about registry semantics | Submit pre-validator rejects any path under `registry.protected`; auto-detect filters it (analogous to existing `automil/`/`.claude/` filters) |
| Backend ABC × CONCERNS.md process-group fix | Process-group fix lands in local backend, ABC has no equivalent abstraction → SLURM backend has its own bug | Define `Backend.terminate(handle, grace=...)` semantics that all backends satisfy. Local backend's killpg is the implementation; ABC doesn't expose PIDs. |
| Trajectory capture × runtime detection | Trajectory tagged with whatever runtime was inferred at capture; the inference is wrong (e.g., infers Claude when running Codex via shim) | Runtime declares itself: agent_assets/<runtime>/SKILL.md sets `AUTOMIL_RUNTIME=claude` env var; trajectory captures that env. Don't infer. |
| 6h cap × orchestrator restart | Operator restarts daemon at hour 4; cell timer resets to 6h | `cell_started_at` persisted to disk; daemon reads on startup. Unit test: kill -9 daemon mid-cell, restart, verify timer continues. |
| Generalization gate × scoring decoupling (Pitfall 7c) | Gate uses framework-level `composite`; scoring becomes pluggable; gate breaks for non-default scoring | Gate operates on whatever scalar `composite` resolves to per project config. Test with a non-default composite. |
| Hardware auto-detection × `automil/.env` | Auto-detection runs at `init`; env vars not loaded yet; detection sees no GPUs | Run detection AFTER `_load_dotenv`; document explicitly. Or: have detection re-run on first orchestrator tick. |
| Setup skill × multi-runtime | Skill written for Claude; produces `.claude/skills/` paths; Codex user's setup writes wrong directory | Setup skill detects active runtime first (via env or interactive prompt), writes runtime-appropriate paths. |
| Decoupling × CCRCC reproduction | Reproduction test still imports from autobench; passes in CI; "decoupling" is fake | Reproduction test must run against the public framework API, not autobench internals. If it can't, decoupling is incomplete. |

---

## Performance Traps

Patterns that work at the current 195-experiment scale but break under the F1/F2 grid (~9000 measurements, ~1800 unique runs).

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Trajectory `archive/<id>/trajectory.jsonl` linear-scan to find a session's trace | `automil status` slows to multi-second | Index by node_id at write time; lookup is O(1) | ~500 experiments per cohort × 18 cohorts |
| Generalization-gate held-out evaluation runs serially after every promotion candidate | Promotion latency dominates wall-clock | Batch held-out evals; run promotion in dedicated phase, not online | When promotion candidates exceed ~5/day |
| `recalculate_scores` O(N²) (CONCERNS.md) compounded by larger graphs | Reconcile takes minutes | Build parent→children index once (already in CONCERNS.md backlog) | At ~1000 nodes; F1 grid hits ~1800 |
| Variant registry stored as Python files; import-by-string at runtime | Cold-start import time grows linearly with variants | Lazy-load variants by config name only when needed | At ~50 registered variants |
| Multi-runtime trajectory comparison loads all trajectories into memory | OOM on large cohorts | Stream-and-process; never load all trajectories simultaneously | At ~1000 trajectories |
| 6h cap timer polled every tick (5s) instead of scheduled wakeup | CPU% on idle daemon nontrivial | Use `asyncio` deadline or a single `time.monotonic()` deadline check, not per-experiment polling | Always — but more visible at large concurrency |
| Backend ABC adds an abstraction layer per scheduling decision | Scheduling latency adds 10s of ms per submit | Profile after ABC introduction; ABC overhead must be <5% of tick time | At >20 concurrent experiments |

---

## Security Mistakes

Refactor-specific security issues. (Pre-existing ones in CONCERNS.md not repeated.)

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trajectory capture serializes full env (Pitfall 5a) | API key / token exfiltration when trajectories are committed or published | Scrub-on-capture with regex + allowlist; default-deny unknown keys |
| Multi-runtime skill scaffolds inherit Claude's tool permissions (e.g., `.claude/settings.json` Allow patterns) | Codex/OpenCode skill grants broader filesystem write than user expects | Per-runtime scaffold has minimal permissions; document each runtime's permission model in `agent_assets/<runtime>/PERMISSIONS.md` |
| Variant registry imports user-written Python at runtime | Malicious variant module = arbitrary code execution in orchestrator process | Variant modules execute in the worktree subprocess (already isolated by CONCERNS.md's worktree boundary). Orchestrator MUST NOT `import` variants directly. |
| `/automil-setup` skill scaffolds config containing user's home-dir paths | Trajectories or shared configs leak username + machine layout | Scaffold uses `${ENV_VAR}` references throughout (per existing autobench convention); skill never writes literal `/home/<user>/...` paths |
| Pluggable backend `RemoteBackend` (e.g., Ray) sends config to a remote node | Config may contain secrets; wire transport may be unencrypted | If backends gain remote-execution capability, mandate TLS + secret-redaction on the wire. (Pre-emptive — not in current scope but the ABC opens the door.) |
| Hardware auto-detection runs `nvidia-smi` (existing CONCERNS.md issue) over expanded scope | Auto-detection now runs on potentially shared multi-user hosts; PATH-injection of fake `nvidia-smi` returns inflated values | Pin `nvidia-smi` path explicitly; cross-check via `pynvml` Python binding which doesn't go through PATH |

---

## UX Pitfalls

Common user experience mistakes specific to this refactor.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| `automil apply <node>` command silently overwrites uncommitted local changes | Lost work — explicitly flagged in user memory `feedback_never_blind_checkout.md` | Refuse to apply if working tree dirty; require `--force` or stash-first |
| 6h cap fires; agent gets `submit failed: cell budget exhausted` with no explanation of remaining time / what to do | Agent retries indefinitely or gives up entirely | Error includes: time remaining (0), time-since-start, partial-fold rescue suggestion, "this cell is done" with structured reason code |
| Multi-runtime detection picks wrong runtime; user discovers when first submit fails | Frustrating "what runtime am I on?" debugging | `automil check` reports detected runtime + version; user can override via env var; status display shows active runtime |
| Hardware auto-detection produces concurrency that under-utilizes (Pitfall 8) | User reports "automil is slow" when really it's defaults | Status display shows `Effective concurrency: 2/8 max` — visible utilization. Daemon log periodically reports utilization vs budget. |
| `automil revert-baseline` reverts everything including registry-tracked variants | User loses their registered variants | `revert-baseline` only touches files in `registry.protected`; registry-tracked variants are committed and survive |
| Setup skill produces config that looks done but has TODOs (Pitfall 9 / CONCERNS Tech Debt #7) | User runs first experiment, hits cryptic resolution failure | `automil check` is mandatory in setup flow; refuses to proceed if TODOs present |
| Generalization gate rejects a candidate; agent isn't told why | Agent re-proposes the same idea; budget wasted | Gate rejection includes per-cell win/loss table, paired-test p-values, and structured reason: "failed: 4/18 cells improved, threshold K=10" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete during this refactor but are missing critical pieces.

- [ ] **Variant registry shipped:** Verify shared-lib paths are in `registry.protected` AND submit pre-validator rejects edits to them AND auto-detect filter excludes them AND skill prompts no longer reference them.
- [ ] **Pluggable backend ABC shipped:** Verify a second backend (real or mock SLURM) is implemented to the same ABC AND tests pass for both AND no `Popen`/`PID`/`os.kill` references in orchestrator main loop.
- [ ] **Multi-runtime support shipped:** Verify ≥2 runtimes have a complete end-to-end experiment in archive/ AND trajectory captured AND result.json valid AND graph reconciled correctly. "Scaffolding written" is not "shipped."
- [ ] **6h cap shipped:** Verify a deliberate test of the cap actually firing leaves a usable result (partial folds saved) AND VRAM returns AND descendants don't get spuriously discarded AND timer survives daemon restart.
- [ ] **Trajectory snapshots shipped:** Verify a trajectory file does NOT contain `sk-` / `_TOKEN=` / `_KEY=` substrings AND has version metadata AND scrubbing rules tested AND default location is gitignored.
- [ ] **Generalization gate shipped:** Verify held-out cell set is committed BEFORE search starts AND gate uses paired-test machinery (not `delta > 0`) AND agent does not see held-out evals during search AND K is empirically calibrated.
- [ ] **Autobench decoupled:** Verify a non-autobench training script (sklearn-iris) runs end-to-end AND produces a valid result.json AND graph reconciles AND no `from autobench` imports in `src/automil/`.
- [ ] **Hardware auto-detection shipped:** Verify detection ran on ≥3 hardware shapes (laptop, current 3-GPU, larger/different) AND empirical feedback updates default_vram from results.tsv AND user can override AND output is reported, not silent.
- [ ] **`/automil-setup` skill shipped:** Verify on a non-autobench-shaped repo, the skill produces a config that passes `automil check` AND a dry-run experiment succeeds AND a re-run is idempotent AND the trajectory log explains every decision.
- [ ] **CCRCC node_0176 reproduces (±0.005):** Verify reproduction runs from a clean checkout (no dirty shared-lib edits) AND on the new registry-driven path (not the old direct-edit path) AND in a fresh worktree (not Leo's main checkout). The sanity check accidentally validating the OLD path is the failure mode.
- [ ] **Tier 1 fixes still hold post-refactor:** Verify `mark_running` guard, process-group kill, YAML reload logging, best_node correction, gitignore are all preserved through the refactor; haven't been silently undone by a "cleanup" commit.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Pitfall 1 (still uses old path) | LOW if caught in same week; HIGH after a cohort runs against dirty path | (a) Add path to `registry.protected`. (b) Audit `archive/` for experiments with overlay touching protected paths; flag them. (c) Force-revert protected files; re-run reproduction sanity check. |
| Pitfall 2 (leaky backend ABC) | HIGH | (a) Identify leak (PID exposure, sync assumption, etc). (b) Refactor ABC; bump major version. (c) Re-implement local backend against new ABC. (d) Revalidate all backends. Likely 1-2 weeks. |
| Pitfall 3 (multi-runtime untested) | LOW (if caught before paper); HIGH (if discovered by reviewer) | (a) Pick one non-Claude runtime. (b) Run 1 experiment end-to-end. (c) Document divergences. (d) Either fix or downgrade README claim. |
| Pitfall 4 (mid-fold kill) | HIGH (work lost; possibly cohort-wide if sibling-cascade fires) | (a) Audit graph for nodes stuck in `running` after cap firing. (b) Manually reconcile each: if partial folds exist, mark `executed` with partial composite; else mark `crash`. (c) Fix descendants whose dominance was computed against the bad parent. (d) Implement partial-fold protocol before next cell. |
| Pitfall 5a (secret leaked) | CATASTROPHIC if pushed/published | (a) Revoke the leaked credential immediately. (b) `git filter-branch` or BFG to scrub history. (c) Force-push (with team coordination). (d) Audit all trajectories ever generated; scrub. (e) Implement scrub-on-capture before any further trajectory generation. |
| Pitfall 5b (size explosion) | MEDIUM | (a) Truncate existing trajectories. (b) Implement size cap. (c) Move archive to a separate volume if needed. |
| Pitfall 5c (format drift) | MEDIUM | (a) Document the schema break. (b) Provide a migration script for old trajectories OR mark them as legacy. (c) Don't claim replayability for legacy. |
| Pitfall 6 (gate too strict) | LOW | Lower K; document why; rerun search. |
| Pitfall 6 (gate too loose / leaky) | HIGH (paper claims invalidated) | (a) Disable promotion. (b) Re-evaluate every promoted variant against a pre-registered held-out set. (c) Demote variants that fail. (d) Update paper claims accordingly. |
| Pitfall 7 (decoupling shipped wrong) | MEDIUM | (a) Identify the leaked autobench assumption. (b) Generalize or parametrize. (c) Re-test with second consumer. (d) Update contract docs. |
| Pitfall 8 (hardware mis-detection in production) | LOW per user; HIGH at scale (every onboarding affected) | (a) Have user override defaults for their hardware. (b) Add their hardware shape to test matrix. (c) Update detection heuristics. |
| Pitfall 9 (setup-skill mis-scaffold) | LOW per user | User overrides via CLI; setup skill's calibration improved with their case as a regression test. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Still uses old path | Variant Registry + Config-Driven Train | Submit pre-validator rejects edits to `registry.protected`; reproduction sanity check runs from clean tree on new path; CONCERNS.md `automil_qa.md` design gaps closed. |
| 2. Leaky backend ABC | Pluggable Backends | Two backends (local + mock-SLURM) implemented to ABC; tests pass for both; no `Popen`/PID in orchestrator main loop; lint check forbids `os.kill` outside backend impls. |
| 3. Multi-runtime untested | Multi-Runtime Agent Support | ≥2 runtimes have complete end-to-end experiments in `archive/`; trajectories captured; per-runtime divergence table documented. |
| 4. Mid-fold kill | 6h Per-Cell Hard Cap | Deliberate cap-firing test produces partial-fold result; VRAM returns; descendants not spuriously discarded; timer survives daemon restart. |
| 5. Trajectory leak / bloat / drift | Trajectory Instrumentation | Secret-scrub regex tested; size cap enforced; schema-version metadata in every trajectory; replay test gated on schema match. |
| 6. Gate too strict / loose | Generalization Gate Inside Search Loop | Held-out cells committed BEFORE search; gate uses paired-test (Wilcoxon + bootstrap CI); K calibrated on pilot; promotion-rate monitored. |
| 7. Decoupling broken | Decouple Framework from Autobench | Second consumer (sklearn-iris or equivalent) runs end-to-end; no `from autobench` in `src/automil/`; contract documented; scoring pluggable. |
| 8. Hardware mis-detect | Hardware Auto-Detection | Tested on ≥3 hardware shapes; empirical feedback from `results.tsv` to default_vram; detection output reported, not silent; user override path works. |
| 9. Setup skill mis-scaffolds | `/automil-setup` Skill | Tested on ≥3 repo shapes (autobench, sklearn-iris, mixed-language); passes `automil check`; idempotent re-runs; trajectory log explains decisions. |
| (Cross-cutting) Tier 1 fixes preserved | Every phase's PR review | CI test exercises each Tier 1 fix; no phase silently undoes them. |
| (Cross-cutting) CCRCC reproduction sanity | Final phase / acceptance | node_0176 reproduces ±0.005 on clean checkout via registry path. |

---

## Design-Time vs Ongoing-Discipline Classification

| Pitfall | Type | Why |
|---------|------|-----|
| 1. Still uses old path | **Design-time** + **ongoing discipline** for skill-prompt content | The disable-old gate is a one-shot architectural decision; keeping prompts/skills clean is forever. |
| 2. Leaky backend ABC | **Design-time** | ABCs are hard to change post-ship. Decide right or pay later. |
| 3. Multi-runtime untested | **Ongoing discipline** | Every runtime upgrade, every new tool, every skill update requires re-validation. |
| 4. Mid-fold kill | **Design-time** | Partial-fold protocol is an architectural decision. Once chosen, it's stable. |
| 5a. Trajectory secret leak | **Ongoing discipline** | New env vars, new tool capabilities, new secret formats appear constantly. |
| 5b. Trajectory size explosion | **Ongoing discipline** | Watch as cohorts scale. |
| 5c. Trajectory format drift | **Ongoing discipline** | Every runtime version bump can trigger this. |
| 6. Gate calibration | **Design-time** for held-out protocol; **ongoing discipline** for K calibration | Held-out separation is architectural; K is empirical and re-calibrated as cohorts change. |
| 7. Decoupling broken | **Design-time** | Contracts, once exposed, are hard to change. |
| 8. Hardware mis-detect | **Design-time** for detect-and-warn pattern; **ongoing discipline** for empirical feedback | Pattern is one-shot; the feedback loop runs forever. |
| 9. Setup skill mis-scaffold | **Design-time** for the interactive boundary; **ongoing discipline** for repo-shape coverage | Interactive-vs-autonomous boundary is architectural; new repo shapes appear constantly. |

---

## Cross-References to Existing Docs

- `.planning/codebase/CONCERNS.md` — pre-existing fragilities (process-group leak, naive `.env` parser, hard `mark_running` assert, O(N²) scoring, etc.). NOT re-listed here. The refactor must not regress these. Several of the pitfalls above interact with them (Pitfall 4 compounds the process-group bug; Pitfall 8 inherits the `nvidia-smi` PATH issue; Pitfall 5 expands the env-leak surface).
- `tasks/automil_qa.md` — the design-gap diagnostic that motivated this refactor. Pitfalls 1, 6, and 7 directly correspond to gaps documented there ("Real Design Gaps" §summary table). Recreating any of those gaps post-refactor is a regression.
- `tasks/automil_proposal.md` — F2 reviewer-attack risks (proposal §7). Pitfall 3 (multi-runtime untested) directly defends against the "this is a Claude paper" attack; Pitfall 6 defends "you didn't truly optimize"; Pitfall 7 supports F2.5 generalizability claim.
- `.planning/PROJECT.md` — Active requirements. Each pitfall maps to one or more Active items.

---

## Sources

Internal (primary, HIGH confidence):

- [`tasks/automil_qa.md`](../../tasks/automil_qa.md) — design-gap diagnostic (revised 2026-04-22)
- [`.planning/codebase/CONCERNS.md`](../codebase/CONCERNS.md) — codebase fragilities audit (2026-04-30)
- [`tasks/automil_proposal.md`](../../tasks/automil_proposal.md) — F2 framework proposal & risks (2026-04-29)
- [`.planning/PROJECT.md`](../PROJECT.md) — milestone definition (2026-05-01)

External (MEDIUM-HIGH confidence; cited inline above):

- [Ray on SLURM — official docs](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html) — head/worker vs SLURM task model mismatch, port-binding gotchas
- [Ray issue #19942 — Ray not initializing with Slurm](https://github.com/ray-project/ray/issues/19942) — `--ntasks=8` starts Ray 8 times, must be `--ntasks=1`
- [Ray issue #13607 — ray.init() does not detect local resources correctly on SLURM](https://github.com/ray-project/ray/issues/13607) — resource detection failure modes
- [Parsl Execution docs](https://parsl.readthedocs.io/en/1.1.0/userguide/execution.html) and [Parsl Plugins](https://parsl.readthedocs.io/en/latest/userguide/plugins.html) — example of state-not-control-flow executor abstraction
- [MLflow LLM Tracing](https://mlflow.org/llm-tracing/) — trajectory snapshot patterns and capture-time scrubbing
- [Portkey LLM Observability Guide 2026](https://portkey.ai/blog/the-complete-guide-to-llm-observability/) — prompt logging, secret-scrubbing, tool-call schema versioning
- [BSWEN Agent Behavior Drift Detection 2026-03-20](https://docs.bswen.com/blog/2026-03-20-agent-behavior-drift-detection/) — tool changes affecting execution patterns; prompt drift
- [Claude Skills cross-client portability](https://www.glukhov.org/ai-devtools/claude-code/claude-skills-for-developers/) — `.agents/skills` vs `.claude/skills` convention divergence
- [Awesome Agents — Codex vs Claude Code vs OpenCode](https://awesomeagents.ai/tools/codex-vs-claude-code-vs-opencode/) — runtime extensibility approaches (CLAUDE.md vs AGENTS.md vs MCP)
- [Kubernetes #94435 — terminationGracePeriodSeconds not honored](https://github.com/kubernetes/kubernetes/issues/94435) — SIGTERM grace period failure modes
- [CNMI Yale Checkpointing docs](https://cnmi.wti.yale.edu/docs/misha-checkpoint/) — long-running ML workload checkpointing patterns
- [Docker Compose stop_grace_period](https://oneuptime.com/blog/post/2026-02-08-how-to-use-docker-compose-stopgraceperiod-setting/view) — graceful-then-forceful termination conventions

User memories (HIGH confidence — Leo's standing directives):

- `feedback_never_blind_checkout.md` — `git checkout -- <file>` destroys uncommitted work (informs Pitfall 9 + UX recovery row)
- `feedback_saturate_gpus.md` — concurrency targets (informs Pitfall 8)
- `feedback_research_before_submit.md` — literature-driven mutation (informs Pitfall 6 K-calibration)
- `feedback_architectural_not_hyperparam.md` — mutation-dimension priorities (informs Pitfall 1, 6)

---

*Pitfalls research for: autoMIL framework refactor (registry + backends + multi-runtime + 6h cap + trajectories + gate + decoupling + hardware + setup skill)*
*Researched: 2026-04-30*
