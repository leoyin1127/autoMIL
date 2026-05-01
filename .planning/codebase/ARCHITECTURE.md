<!-- refreshed: 2026-04-30 -->
# Architecture

**Analysis Date:** 2026-04-30

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          Coding Agent (Claude)                          │
│   reads `automil/program.md`, `automil/learnings.md`, `graph.json`      │
│   edits files in user repo, then invokes the `automil` CLI              │
└────────────┬────────────────────────────────────────────────────────────┘
             │ propose / submit / reconcile / rank / status
             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     CLI Layer  `src/automil/cli.py`                     │
│  init │ submit │ propose │ rank │ reconcile │ status │ check │ start-loop│
│  orchestrator {start,stop,status} │ viz {start,stop,status}             │
└──┬──────────────────────────────────────────────┬──────────┬────────────┘
   │ writes graph nodes                           │ writes   │ reads graph
   ▼                                              ▼ queue/   │ + gpu_state
┌──────────────────────────┐    ┌──────────────────────────┐ │
│  Experiment Graph        │    │  Spec Queue              │ │
│  `src/automil/graph.py`  │    │  `automil/orchestrator/  │ │
│  graph.json (UCB +       │    │   queue/<id>.json`       │ │
│  Pareto keep/discard)    │    │                          │ │
└──────────┬───────────────┘    └─────────┬────────────────┘ │
           │ reconcile()                   │ poll            │
           │ scans archive/completed       ▼                 │
           │                  ┌────────────────────────────┐ │
           │                  │  Orchestrator Daemon       │ │
           │                  │  `src/automil/             │ │
           │                  │   orchestrator.py`         │ │
           │                  │  best-fit GPU bin packing  │ │
           │                  └────┬───────────────────────┘ │
           │                       │ git worktree add        │
           │                       ▼                         │
           │             ┌───────────────────────────┐       │
           │             │  Runner                   │       │
           │             │  `src/automil/runner.py`  │       │
           │             │  worktree + overlay copy  │       │
           │             └────┬──────────────────────┘       │
           │                  │ create_worktree              │
           │                  ▼                              │
           │     ┌────────────────────────────────────────┐  │
           │     │ Detached git worktree at base_commit   │  │
           │     │ `.automil_worktrees/<node_id>/`        │  │
           │     │  + overlay files copied from archive/  │  │
           │     └──────────┬─────────────────────────────┘  │
           │                │ subprocess.Popen               │
           │                │ CUDA_VISIBLE_DEVICES=<phys>    │
           │                │ AUTOMIL_GPU=0                  │
           │                ▼                                │
           │     ┌────────────────────────────────────────┐  │
           │     │ Training script (`run.script` or       │  │
           │     │ `run.command` from config.yaml)        │  │
           │     │ writes `result.json` in worktree cwd   │  │
           │     └──────────┬─────────────────────────────┘  │
           │                │                                │
           │                ▼ collect_result()               │
           │     ┌────────────────────────────────────────┐  │
           │     │ archive/<id>/{spec,result,run.log}     │  │
           │     │ completed/<id>.json (notification)     │  │
           │     │ results.tsv (sole writer = orch)       │  │
           │     └──────────┬─────────────────────────────┘  │
           └────────────────┘                                │
                            ▲                                │
                            │ promotes proposed → executed   │
                            │ Pareto keep/discard            │
                            ▼                                │
                ┌────────────────────────────┐               │
                │ graph.json                 │◄──────────────┘
                └──────────┬─────────────────┘
                           │ inotify (watchdog)
                           ▼
              ┌──────────────────────────────────────────┐
              │ Viz Server  `src/automil/viz/server.py`  │
              │ aiohttp + SSE on port 8420               │
              │ overlays gpu_state.json running status   │
              │ static dashboard `viz/static/app.js`     │
              │ (3D force graph)                         │
              └──────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| ExperimentGraph | Append-only directed tree of nodes (proposed/executed), UCB potential scoring, Pareto keep/discard, technique stats, atomic JSON persistence, reconciliation against orchestrator state | `src/automil/graph.py` |
| ExperimentOrchestrator | Long-running daemon: poll queue, best-fit-bin-pack experiments onto GPUs, launch worktree subprocesses, collect result.json, append results.tsv, recover orphans, hot-reload config | `src/automil/orchestrator.py` |
| Runner | Git worktree create / overlay copy / result collect / cleanup / prune | `src/automil/runner.py` |
| CLI | Click command surface; parses agent intent into graph mutations and queue spec writes; preflight guards (parent must be executed, no overwrite of completed nodes, sibling-dup detection) | `src/automil/cli.py` |
| Viz Server | aiohttp + SSE; watches `graph.json` and `gpu_state.json` via watchdog inotify; pushes diff-only `graph_update` events to browser; overlays running status from orchestrator state | `src/automil/viz/server.py` |
| Viz Frontend | 3D force-directed graph rendering, status colors, run timing | `src/automil/viz/static/app.js` |
| Templates | Jinja2 scaffolding rendered by `automil init` into the user repo's `automil/` subdir | `src/automil/templates/*.j2` |
| Claude assets | Skills (`SKILL.md`) and `Stop` hook installed into `<project>/.claude/` on init | `src/automil/claude_assets/` |

## Pattern Overview

**Overall:** Overlay framework + experiment-tree + GPU scheduler daemon (event-loop poll). The framework is package-isolated under `src/automil/` and is dropped into a host ML repo as a sibling `automil/` directory containing config + runtime state + per-experiment archive. No code in the host repo needs to import from `automil`; integration is via env vars (`AUTOMIL_GPU`, `CUDA_VISIBLE_DEVICES`, `AUTOMIL_RESULTS_DIR`, `AUTOMIL_NODE_ID`, `AUTOMIL_DESC`, `AUTOBENCH_ROOT`, `PYTHONPATH`) and a single output contract: `result.json` written to the process cwd.

**Key Characteristics:**
- File-system as state store. There is no database. `graph.json`, `queue/*.json`, `running/*.json`, `completed/*.json`, `archive/<id>/{spec,result,run.log}`, `results.tsv`, and `gpu_state.json` are the system of record.
- Single-writer-per-file invariant. `graph.json` is written only by CLI commands (`submit`, `propose`, `reconcile`, `rank`); `results.tsv` is written solely by the orchestrator (`_append_results_tsv`); `result.json` is written solely by the training script.
- Atomic writes. `ExperimentGraph.save()` writes to a temp file then `os.rename` (`src/automil/graph.py:740-754`).
- Decoupled control plane (graph, CLI) and data plane (orchestrator, worktrees, training subprocess). They communicate only via files in `automil/orchestrator/`.
- Multi-branch exploration: each node has a `parent_id`; siblings explore alternative interventions on the same lineage. Promotion is Pareto-dominant (`test_auc >= parent`, `test_bacc >= parent`, `composite > parent`).

## Layers

**Agent layer (out of repo):**
- Purpose: Plan experiments by reading the graph and propose / submit them via CLI.
- Location: External (Claude Code, with skills at `.claude/skills/automil/SKILL.md` and stop hook at `.claude/hooks/on_stop.sh`).
- Depends on: CLI surface, `graph.json`, `program.md`, `learnings.md`.

**CLI layer:**
- Purpose: Command surface; mutate graph, write queue specs, preflight guards.
- Location: `src/automil/cli.py`
- Contains: `init`, `submit`, `propose`, `rank`, `reconcile`, `status`, `check`, `start-loop`, `stop-loop`, `orchestrator {start,stop,status}`, `viz {start,stop,status}`.
- Depends on: `graph.py`, `runner.py` (transitively), git, jinja2, click, pyyaml.
- Used by: Coding agent and human operator.

**Graph layer:**
- Purpose: Directed-tree data structure for proposed/executed experiments. Scoring and Pareto reconciliation.
- Location: `src/automil/graph.py`
- Contains: `ExperimentGraph` class, technique tag map, `recalculate_scores()`, `rank_proposals()`, `reconcile()`, `compute_config_hash()`, `import_from_tsv()`.
- Depends on: stdlib only (json, hashlib, math, tokenize, datetime).
- Used by: CLI commands.

**Orchestrator layer:**
- Purpose: Long-lived daemon that schedules and supervises experiments on GPUs.
- Location: `src/automil/orchestrator.py`
- Contains: `ExperimentOrchestrator`, `GPUInfo`, `RunningExperiment`, `query_gpus()`, `tick()`, `run()`, `cmd_start/status/stop/submit`.
- Depends on: `runner.py`, `nvidia-smi`, optional `pyyaml`.
- Used by: CLI (`automil orchestrator start`).

**Runner layer:**
- Purpose: Git worktree primitives.
- Location: `src/automil/runner.py`
- Contains: `Runner.create_worktree`, `apply_overlay`, `collect_result`, `cleanup_worktree`, `prune_stale_worktrees`, `worktree_path`.
- Depends on: `git` CLI, stdlib (subprocess, shutil, json).
- Used by: orchestrator only.

**Visualization layer:**
- Purpose: Real-time 3D dashboard.
- Location: `src/automil/viz/server.py`, `src/automil/viz/static/`
- Contains: aiohttp app, SSE handler, `GraphWatcher` (watchdog inotify), running-status overlay, vendored d3 / three / 3d-force-graph.
- Depends on: `aiohttp`, `watchdog`.
- Used by: Operator browser.

**Host project:**
- Purpose: The MIL training code being optimized. autoMIL is overlaid onto it.
- Location: Repo root (e.g., `benchmarks/scripts/run_experiment.py` for `autobench`).
- Contract: Read env vars; write `result.json` (see Result Contract below) to cwd.

## Data Flow

### Primary Request Path: agent submits an experiment

1. Agent edits source files in the host repo (e.g., `benchmarks/scripts/run_experiment.py`, models in `benchmarks/lib/CLAM/...`).
2. Agent calls `automil submit --node node_0042 --desc "..." --parent node_0035 [--files ...]` (`src/automil/cli.py:188-437`).
3. `submit` runs preflight guards: refuses if node already executed/queued; refuses if `--parent` is not yet `executed/keep|discard|completed` (`cli.py:208-276`).
4. Auto-detect changed files via `git diff --name-only` + `git ls-files --others --exclude-standard`, intersected with `files.editable` from `automil/config.yaml` (`cli.py:284-330`).
5. `git rev-parse HEAD` captures the `base_commit` (`cli.py:336-339`).
6. Files copied to `automil/orchestrator/archive/<node_id>/<original_path>` (preserving directory structure) (`cli.py:341-366`).
7. SHA-256 manifest + base commit hashed into 16-char `config_hash` (`cli.py:371-376`).
8. Spec JSON written to `automil/orchestrator/queue/<node_id>.json` (`cli.py:378-398`).
9. Node registered in `graph.json` as `type=proposed, status=running` to bump `next_id` and prevent collision (`cli.py:402-426`).

### Orchestrator scheduling tick (`tick()` in `src/automil/orchestrator.py:676-699`)

1. Hot-reload `automil/config.yaml` orchestrator section (live concurrency / VRAM bumps).
2. Poll running experiments: `process.poll()` for completion; `time.time() > timeout_at` for timeout.
3. On completion: collect `result.json` from worktree, classify status (oom/crash/timeout/completed by scanning `run.log` for "CUDA out of memory"/"OutOfMemoryError"), write `completed/<id>.json` and append `results.tsv`, cleanup worktree.
4. Read pending queue specs sorted by `(priority, submitted_at)`.
5. For each pending spec, find best-fit GPU: `_find_best_gpu()` picks the GPU with the *least* schedulable free VRAM that still fits (`free_gb - safety_margin_gb - sum(running.estimated_vram_gb) >= needed_gb`).
6. `_pre_launch_check()` re-queries `nvidia-smi` immediately before launch for race protection.
7. `_launch()`: `Runner.create_worktree(base_commit, node_id)` adds detached worktree at `.automil_worktrees/<node_id>/`; `Runner.apply_overlay()` copies overlay files (and applies deletions); spawns `subprocess.Popen([sys.executable, run_script], cwd=worktree, env={CUDA_VISIBLE_DEVICES=gpu, AUTOMIL_GPU=0, AUTOMIL_RESULTS_DIR=archive, AUTOBENCH_ROOT=worktree/benchmarks, PYTHONPATH=worktree/benchmarks/src:...})` (`orchestrator.py:374-478`).
8. Save `gpu_state.json` (which the viz watches).

### Reconciliation: agent calls `automil reconcile`

1. Scan `queue/`, `running/`, `completed/` for orchestrator-known IDs (`graph.py:413-421`).
2. For each `completed/<id>.json`: classify keep/discard via Pareto check against parent's `(test_auc, test_bacc, composite)` (`graph.py:455-462`); call `promote(node_id, metrics)` if status in `(keep, discard)` else `mark_failed`.
3. `_reevaluate_descendants()` re-runs Pareto for any executed children that were promoted before their parent (parent metrics started at 0) (`graph.py:233-262`).
4. Archive-based recovery: scan `archive/*/result.json` for nodes missing in graph and reconstruct them (`graph.py:560-622`).
5. Mark orphaned `running` proposals back to `pending` if no longer in queue/running (`graph.py:624-627`).
6. Zombie sweep: cancel `pending` proposals older than 6h with no orchestrator presence and no archive result (`graph.py:629-664`).
7. `recalculate_scores()` updates UCB potential for every node.

### Visualization push

1. Watchdog observer scheduled on `automil/` and `automil/orchestrator/` (`viz/server.py:249-254`).
2. On any modification to `graph.json` or `gpu_state.json`, `_notify()` is called via `loop.call_soon_threadsafe`.
3. Reload `graph.json`, overlay running status from `gpu_state.json` (`server.py:63-84`), diff against previous payload, and emit a `graph_update` SSE event with `{changed, added, removed, full_graph}` to all subscribers.
4. Identical payloads are skipped to avoid d3 force-layout reheats (`server.py:117-121`).

**State Management:**
- All state lives on disk under `<project>/automil/` and `<project>/.automil_worktrees/`.
- In-process state in the orchestrator daemon (`self.running`, `self.gpu_allocations`, `self.counter`) is rebuilt from disk on startup via `_load_state()` and `_recover_orphans()` (the latter only inside `run()`, never on construction — `orchestrator.py:196-198, 254-264, 701-704`).

## Key Abstractions

**Node (graph entry):**
- Purpose: A single experiment, either `type=proposed` (planned) or `type=executed` (run, with metrics).
- Examples: `automil/orchestrator/archive/node_0001/spec.json` and matching entry in `automil/graph.json`.
- Pattern: Append-only with mutations to `status` (`pending` → `running` → `keep|discard|crash|oom|timeout|cancelled`). `archive_id == node_id` for executed nodes; metrics live on the node itself.

**Spec (queue entry):**
- Purpose: Input contract for the orchestrator: what to run.
- Schema: `{id, description, base_commit, overlay_dir, overlay_manifest, deletions, priority, estimated_vram_gb, timeout_min, graph_metadata: {parent_id, techniques, config_hash}, submitted_at}`.
- Example: `benchmarks/experiments/ccrcc/automil/orchestrator/archive/node_0001/spec.json`.
- Pattern: Submit writes to `queue/<id>.json`; orchestrator copies to `running/<id>.json` for orphan recovery; archive copy is the canonical record.

**Overlay (file-set diff against base commit):**
- Purpose: Capture *only* changed files for a given experiment, layered on top of a clean checkout of `base_commit`.
- Storage: `automil/orchestrator/archive/<node_id>/<rel_path>` mirrors the host repo path. Optional `deletions: [<rel_path>, ...]` removes files.
- Lifecycle: `Runner.apply_overlay()` walks the archive subtree (skipping metadata files `spec.json`, `run.log`, `result.json`) and `shutil.copy2`s each into the worktree (`runner.py:37-60`). Deletions are applied second.
- Hash: `config_hash = sha256(base_commit + sorted manifest entries + DELETE: lines)[0:16]`.

**UCB-inspired potential:**
- Executed: `composite + w_e * sqrt(log(total_executed) / (1 + child_count))` — exploration bonus for under-explored branches (`graph.py:308-319`).
- Proposed: `parent_composite + w_e * sqrt(log(total) / (1 + siblings_tried)) + w_n * mean(1/(1+times_tried))` over techniques — weights novelty by inverse usage (`graph.py:320-340`).
- Defaults: `exploration_weight=0.005`, `novelty_weight=0.003`.

**Pareto keep/discard:**
- A child `keeps` iff `test_auc >= parent.test_auc AND test_bacc >= parent.test_bacc AND composite > parent.composite`. Otherwise `discard`. Computed in both `reconcile()` and `_reevaluate_descendants()`.

## Entry Points

**`automil` CLI (`pyproject.toml` → `automil = "automil.cli:main"`):**
- Location: `src/automil/cli.py:67-70` (Click group)
- Triggers: Operator or coding agent invocation.
- Responsibilities: All graph mutations and queue writes. Subgroups `orchestrator` and `viz` shell out to start/stop the respective daemons.

**Orchestrator daemon (`automil orchestrator start`):**
- Location: `src/automil/orchestrator.py:701-743` (`run()`).
- Triggers: Operator. Persists PID at `automil/orchestrator/orchestrator.pid`.
- Responsibilities: Poll queue every `poll_interval_sec`, schedule launches, supervise running processes, write completion records, append `results.tsv`, persist `gpu_state.json`, handle SIGTERM/SIGINT for graceful drain.

**Viz server (`automil viz start --port 8420`):**
- Location: `src/automil/viz/server.py:222-286` (`cmd_start()`).
- Triggers: Operator. Persists PID at `automil/orchestrator/viz_server.pid`.
- Responsibilities: Serve `static/index.html` at `/`, push SSE events at `/events`, watch `automil/` for `graph.json` and `automil/orchestrator/gpu_state.json` changes.

**Training process (per experiment):**
- Location: Determined by `run.script` (default `train.py`) or `run.command` in `automil/config.yaml`. In `autobench`, this is `benchmarks/scripts/run_experiment.py`.
- Triggers: `subprocess.Popen` launched by `_launch()` (`orchestrator.py:436-446`).
- Responsibilities: Read `AUTOMIL_GPU` (always 0 — physical GPU is masked by `CUDA_VISIBLE_DEVICES`), `AUTOMIL_DESC`, `AUTOMIL_NODE_ID`, `AUTOMIL_RESULTS_DIR`, `AUTOBENCH_ROOT`. Write `result.json` to cwd (the worktree root) before exit.

## Architectural Constraints

- **Threading:** Orchestrator daemon is single-threaded with a poll loop (`time.sleep(self.poll_interval)`). Viz server is asyncio (`aiohttp`) with a watchdog Observer running in a background thread that posts back to the loop via `loop.call_soon_threadsafe`. Each experiment runs in its own OS process.
- **Single writer per file:** `results.tsv` only by orchestrator (`orchestrator.py:611-636`); `graph.json` only by CLI commands; `result.json` only by training script. Violating this corrupts state.
- **Orphan recovery only in `run()`:** `_recover_orphans()` MUST NOT be called from constructors used by `automil orchestrator status` or `stop` — doing so would mark a live run as crashed. Only `run()` calls it (`orchestrator.py:196-198, 701-704`).
- **No cross-experiment state:** Each subprocess gets a fresh detached worktree at `.automil_worktrees/<node_id>/`. `AUTOMIL_RESULTS_DIR` points to the per-experiment archive so checkpoints don't bleed across runs.
- **`PYTHONPATH` override:** `_launch()` prepends `<worktree>/benchmarks/src` to `PYTHONPATH` so the editable install of `autobench` in the parent venv does NOT shadow worktree-local overlays under `benchmarks/src/autobench/` or `benchmarks/lib/` (`orchestrator.py:413-418`).
- **`.env` propagation:** `_load_dotenv()` reads `<root>/.env` and `<root>/benchmarks/.env` into `os.environ` so child processes inherit them — worktrees never contain `.env` because it's gitignored (`orchestrator.py:222-250`).
- **Tokenizer-based config hash:** Single-script hashes strip COMMENT/NL/INDENT/DEDENT/ENCODING tokens before hashing so cosmetic-only edits dedupe; multi-file overlays use raw SHA-256 (`graph.py:362-385`).
- **Submit guards (immutable graph nodes):** Refuse to submit against an id that is already executed/keep/discard/crash/completed/running, against a non-existent or still-proposed `--parent`, or when a queue/running spec already exists for that id (`cli.py:208-276`).
- **Sibling-dup proposal guard:** `propose` refuses an exact-description match under the same parent that is still pending or running (`cli.py:487-498`).

## Anti-Patterns

### Submitting against an executed node id
**What happens:** `automil submit --node <existing_executed_id>` is called, intending to "rerun" or amend.
**Why it's wrong:** Would overwrite `archive/<id>/result.json` and clobber graph state; loses prior results.
**Do this instead:** Call `automil propose --parent <existing_id> --desc "..."` to mint a new node, then `automil submit --node <new_id>`. CLI now refuses the bad path explicitly (`cli.py:218-230`).

### Submitting a child whose parent is still proposed/running
**What happens:** Agent submits `--parent <pending_id>` to start exploring early.
**Why it's wrong:** Pareto keep/discard at reconcile time compares against `parent.composite=0`, so the child is misclassified as "keep" regardless of actual quality. This was the root cause of orphan subtrees `0051-0055 → 0048` historically (see comment in `cli.py:241-247`).
**Do this instead:** Wait for the parent to finish or pick an already-executed `--parent`. CLI blocks this (`cli.py:248-270`).

### Calling `_recover_orphans()` from `status`/`stop`
**What happens:** Constructing `ExperimentOrchestrator()` for a non-`run` command would mark live experiments as crashed.
**Why it's wrong:** `running/<id>.json` files exist for legitimately-live runs; rewriting them as `crash` corrupts an in-flight session.
**Do this instead:** `_load_state(recover=False)` is called from `__init__`, and only `run()` calls `_recover_orphans()` (`orchestrator.py:196-198, 254-264, 701-704`).

### Writing to `results.tsv` from the training script
**What happens:** Training code appends a row to `results.tsv` to "be helpful."
**Why it's wrong:** Causes interleaved/duplicate rows and breaks orchestrator's append invariant. Per `CLAUDE.md`: "results.tsv is written solely by the orchestrator from `result.json`, never by `train.py`."
**Do this instead:** Training script writes `result.json` to its cwd; orchestrator extracts metrics and appends the row (`orchestrator.py:611-636`).

### Silent reliance on a parent venv `pip install -e .` for autobench
**What happens:** Worktree-local overlays under `benchmarks/src/autobench/` or `benchmarks/lib/` are silently ignored because the parent venv's editable install wins.
**Why it's wrong:** Experiments think they're testing a code change but actually run the unchanged installed package.
**Do this instead:** `_launch()` sets `AUTOBENCH_ROOT` and prepends `<worktree>/benchmarks/src` to `PYTHONPATH` so the worktree wins (`orchestrator.py:413-418`).

## Result Contract

The training script (configured via `automil/config.yaml` → `run.script` or `run.command`, defaulting to `train.py`) MUST write `result.json` to its current working directory (which is the worktree root). The orchestrator reads it via `Runner.collect_result()` (`runner.py:62-72`).

**Schema:**
```json
{
  "status": "completed",
  "metrics": {
    "val_auc": 0.87,
    "val_bacc": 0.81,
    "test_auc": 0.87,
    "test_bacc": 0.83
  },
  "composite": 0.85,
  "elapsed_seconds": 4098,
  "peak_vram_mb": 4500
}
```

**Fields consumed by orchestrator (`orchestrator.py:489-557`, `graph.py:436-491`):**
- `status` (str): One of `completed`, `crash`, `oom`, `timeout`. If absent, orchestrator infers from returncode and log scan for `CUDA out of memory` / `OutOfMemoryError`.
- `metrics` (dict): Keys `val_auc`, `val_bacc`, `test_auc`, `test_bacc` are surfaced into `results.tsv` and the graph.
- `composite` (float): Primary scalar used for Pareto comparisons and best-node tracking.
- `elapsed_seconds` (float): Used for `elapsed_min` in TSV; orchestrator falls back to wall time if missing.
- `peak_vram_mb` (int): Converted to `vram_gb` (mb / 1024) in TSV and graph.
- Optional `graph_metadata` echoed from spec.

**If `result.json` is missing on exit**, orchestrator synthesizes one with `{status: completed|crash|oom|timeout, error: <last 2000 chars of run.log>}` and writes it to the archive (`orchestrator.py:506-523`).

## CUDA / GPU Masking

`_launch()` sets per-process env (`orchestrator.py:419-432`):
- `CUDA_VISIBLE_DEVICES=<physical_gpu_index>` — masks the GPU at the driver level so the child process sees exactly one device.
- `AUTOMIL_GPU=0` — the **logical** device id the script should select (always 0 because of masking). Never use the physical index inside the training script.
- Best-fit bin packing in `_find_best_gpu()` picks the GPU with the *least* schedulable free VRAM that still fits, leaving large headroom on emptier GPUs for fatter jobs (`orchestrator.py:339-362`).
- Default `max_concurrent_per_gpu = 8`; `safety_margin_gb = 2.0`; `default_vram_estimate_gb = 1.0`. All overridable via `automil/config.yaml` → `orchestrator.*`. Hot-reloaded each tick (`orchestrator.py:640-674`).
- `_pre_launch_check()` re-queries `nvidia-smi` immediately before `Popen` to handle the race where another process grabbed memory between scheduling and launch (`orchestrator.py:364-369`).

## Experiment Overlay Model

For monorepo benchmarks, agent edits typically target files under `benchmarks/scripts/`, `benchmarks/src/autobench/pipeline/`, `benchmarks/lib/CLAM/`, etc. The submit pipeline:

1. Per-dataset autoMIL state lives at `benchmarks/experiments/<dataset>/automil/` (e.g., `benchmarks/experiments/ccrcc/automil/`). This directory contains `config.yaml`, `graph.json`, `program.md`, `learnings.md`, `results.tsv`, `orchestrator/{queue,running,archive,completed}/`. Agent runs CLI commands from the dataset directory; `_find_automil_dir()` walks up to find `automil/config.yaml`.
2. `automil submit` snapshots changed files (relative to `git diff` against HEAD) into `automil/orchestrator/archive/<node_id>/<original_path>`, preserving the host-repo directory structure. Example: an edit to `benchmarks/lib/CLAM/models/model_clam.py` is stored as `benchmarks/experiments/ccrcc/automil/orchestrator/archive/node_0042/benchmarks/lib/CLAM/models/model_clam.py`.
3. `automil submit` records the host-repo HEAD as `base_commit` in the spec (the agent's current commit, not the historical baseline).
4. Orchestrator picks up the spec, calls `Runner.create_worktree(base_commit, node_id)` which runs `git worktree add --detach .automil_worktrees/<node_id> <base_commit>` (`runner.py:23-35`). The worktree is a clean checkout of the host repo at that commit, containing the full source tree (including unmodified `benchmarks/lib/CLAM`, etc.).
5. `Runner.apply_overlay()` walks the archive subtree and `shutil.copy2`s each file onto the worktree at the matching relative path, overwriting whatever was there from `base_commit` (`runner.py:37-60`). Files in `spec.deletions` are then `unlink()`-ed.
6. Orchestrator launches the training process with `cwd=<worktree>`. The script reads its inputs (features, splits) via env-var paths (`AUTOBENCH_<DATASET>_ROOT` from `benchmarks/.env`, propagated by `_load_dotenv`).
7. Training script writes `result.json` to `cwd` (the worktree root); orchestrator copies it to `archive/<node_id>/result.json`.
8. Worktree is removed via `git worktree remove --force` after collection (`runner.py:74-86`); failure falls back to `shutil.rmtree` + `git worktree prune`.

The overlay model is what gives autoMIL its multi-branch property: every experiment runs against an independent checkout, so concurrent runs cannot stomp on each other's source tree. The `base_commit` is the experiment's "parent commit"; the overlay is the "delta."

## Error Handling

**Strategy:** Catch-and-log at boundaries, fail-soft so the daemon keeps scheduling.

**Patterns:**
- Tick-level exception barrier in `run()`: `except Exception: logger.error("Tick error", exc_info=True)` — a bad spec doesn't kill the daemon (`orchestrator.py:725-728`).
- Worktree creation failure → `_mark_crashed()` writes a synthetic `result.json` with status=crash to the archive so reconcile can still classify the node (`orchestrator.py:391-395, 589-609`).
- Subprocess launch failure → close log, mark crashed, cleanup worktree (`orchestrator.py:447-452`).
- Timeout → SIGTERM, sleep 5s, SIGKILL, then run normal completion handling with returncode=-9 (`orchestrator.py:578-587`).
- OOM detection → grep `run.log` for `CUDA out of memory` / `OutOfMemoryError` when result.json is missing (`orchestrator.py:509-513`).
- JSON load failures in reconcile → silently skip the bad file (`graph.py:418-421, 425-428, 487-490`).
- Atomic graph save → temp-file + rename, with cleanup on exception (`graph.py:740-754`).

## Cross-Cutting Concerns

**Logging:**
- Orchestrator uses stdlib `logging` configured in `cmd_start()` with file handler `automil/orchestrator/orchestrator.log` and stderr handler (`orchestrator.py:758-766`).
- Per-experiment stdout+stderr captured to `automil/orchestrator/archive/<node_id>/run.log` (file handle attached to `Popen`, no stdout/stderr inheritance).
- Viz server logs to `automil/orchestrator/viz_server.log`.
- Last 20 lines of `run.log` are echoed into `completed/<id>.json` on crash/oom/timeout for agent-side visibility (`orchestrator.py:541-550`).

**Validation:**
- `submit` rejects absolute paths and `..` traversal; resolves and checks paths stay inside git root (`cli.py:348-361`).
- `submit` excludes `automil/` and `.claude/` directories from auto-detect (`cli.py:316-319`).
- `automil check` validates config completeness, training-script existence, data-path placeholders, GPU availability (`cli.py:569-652`).

**Authentication / secrets:**
- `.env` files (gitignored) loaded once at orchestrator startup; never written by autoMIL. Worktrees never contain `.env`.

---

*Architecture analysis: 2026-04-30*
