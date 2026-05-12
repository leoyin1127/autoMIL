<div align="center">

# autoMIL

**Autonomous Agent-Driven Multiple Instance Learning**

*Let AI agents run your ML experiments while you sleep.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Milestone v1.0](https://img.shields.io/badge/milestone-v1.0%20shipped-brightgreen.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-950%20collected-brightgreen.svg)](#)

---

**autoMIL** is a plug-and-play experiment framework for computational pathology
and beyond. It overlays onto your existing ML project and lets any coding agent
autonomously design, run, and learn from experiments under a hard wall-clock
budget, with discovered variants reproducible, attributable to their parents,
and portable across machines and LLM runtimes.

[Getting Started](#quick-start) | [How It Works](#how-it-works) | [Training-Script Contract](docs/training-script-contract.md) | [Documentation](docs/getting-started.md)

</div>

---

## The Problem

Manual ML development is a grind: tweak hyperparameters, edit code, run training,
check results, repeat. AutoML tools like Optuna search parameter spaces, but they
can't invent new architectures, combine techniques creatively, or learn from
what failed last time.

## The Solution

autoMIL gives coding agents the infrastructure to run experiments autonomously:

<table>
<tr>
<td width="50%">

**What the agent does:**
- Reads your codebase
- Designs experiments
- Modifies any file (models, losses, augmentations)
- Submits experiments via CLI
- Learns from results
- Repeats forever

</td>
<td width="50%">

**What autoMIL handles:**
- GPU scheduling (best-fit bin packing)
- Parallel execution (git worktree isolation)
- Experiment tracking (directed tree, not flat log)
- Knowledge persistence (learnings.md)
- Result evaluation (Pareto-dominance keep/discard)
- 3D visualization (live dashboard)

</td>
</tr>
</table>

> **Real result:** On ovarian cancer HRD prediction, autoMIL autonomously ran
> 189 experiments and improved the composite score from 0.814 to 0.851 (+4.5%),
> discovering techniques like R-Drop, focal loss, gradient clipping, and
> coordinate positional encoding that human researchers hadn't tried.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Plug-and-play** | Overlays onto any existing ML project. No restructuring needed. |
| **Multi-runtime agents** | First-class skills for Claude Code, Codex, OpenCode, and DeepSeek (routed via opencode/codex). `automil init --runtime` auto-detects or installs explicitly. |
| **Full-codebase scope** | Agent edits any file: architectures, losses, augmentations, optimizers. |
| **Git worktree isolation** | Each experiment runs in a snapshot. Only changed files stored. |
| **Pluggable backends** | `local` (default), `slurm` (submitit, opt-in via `[slurm]` extra), `ray` (raw `@ray.remote`, opt-in via `[ray]` extra). Same `Backend` ABC; same cap contract. |
| **Hardware autodetect** | `automil init` probes CUDA / ROCm / CPU via `LocalBackend.healthcheck()` and stamps detected GPU count, VRAM, and concurrency defaults into `config.yaml`. |
| **Variant registry** | Architectural changes ship as committed variant modules (`automil/variants/<parent>/<name>.py`) selected via config. Registry-only path reproduces a node end-to-end via `automil verify-repro`. |
| **6h per-cell hard cap** | Two-tier wall-clock budget (`refusing-new` at T-buffer, `terminating` at T) with per-fold checkpoints. Budget-killed runs reconcile to `executed` with partial composite, never `crash`. |
| **Generalization gate** | Pre-registered held-out manifest + paired Wilcoxon + bootstrap CI + Bonferroni, ships a `candidate` node status, manual nomination by default, promotion-rate metric exposed via SSE. |
| **Trajectory recorder** | Per-submit JSONL using OpenTelemetry `gen_ai.*` keys with secret redaction (`sk-…`, `hf_…`, AWS keys) and bounded rotation (5 MB soft / 50 MB hard). |
| **Multi-GPU orchestrator** | Background daemon with bin packing, OOM detection, crash recovery, namespaced `running/<backend>/`. |
| **Experiment tree** | UCB-inspired scoring balances exploitation and exploration across branches; Pareto-dominance keep/discard via consumer-supplied `composite` scalar. |
| **3D dashboard** | Interactive Three.js visualization with live SSE updates (`localhost:8420`). |
| **Persistent learnings** | Knowledge accumulates across sessions. Agents don't repeat mistakes. |
| **Setup validation** | `automil check` validates protected files, registry purity, backend directives, and `env.required` before experiments run. |

---

## Quick Start

### 1. Install

```bash
# Install as a global CLI tool (recommended)
uv tool install git+https://github.com/leoyin1127/autoMIL.git

# Or install from a local clone
git clone https://github.com/leoyin1127/autoMIL.git
cd autoMIL
uv tool install -e .
```

> **Note:** If you haven't installed `automil` globally via `uv tool install`,
> prefix all commands with `uv run` (e.g., `uv run automil init`).
> This applies when developing within the autoMIL repo itself.

### 2. Initialize in your project

```bash
cd /path/to/your/project    # any existing git repo
automil init                 # creates automil/ subdirectory
```

### 3. Setup

<details>
<summary><b>With Claude Code (recommended)</b></summary>

```bash
claude
# Type: /automil-setup
```

The agent scopes your codebase, configures everything, verifies the training
contract, and establishes a baseline. Fully autonomous. The setup skill
follows a documented idempotency protocol and runs a 1-minute dry-run gate
before declaring done.

</details>

<details>
<summary><b>With another runtime (Codex, OpenCode, DeepSeek)</b></summary>

```bash
automil init --runtime codex                   # or opencode, deepseek-via-opencode, deepseek-via-codex
automil show-skill --runtime codex             # render merged per-runtime skill to stdout
```

`automil init` auto-detects from existing `.claude/`, `.codex/`, `.opencode/`
directories when `--runtime` is omitted. The canonical skill content lives
in `_shared/`; per-runtime overlays only carry diffs.

</details>

<details>
<summary><b>Manual setup</b></summary>

Edit `automil/config.yaml`. Minimum sections you must touch:

```yaml
run:
  script: "train.py"          # your training script (any name)

files:
  editable: ["train.py", "models/", "losses/*.py"]   # files, dirs, or globs
  readonly: ["evaluate.py"]                          # what must not change

baseline:
  composite: 0.814             # your starting performance

env:
  required: []                 # vars that MUST be set before submit
  passthrough: [AUTOMIL_*]     # vars forwarded to experiment subprocesses

scoring:
  formula: "(val_auc + val_bacc + test_auc + test_bacc) / 4"   # documentation only

cap:
  budget_seconds: 21600        # 6h per-cell hard cap
  safety_buffer_seconds: 1800  # 30min refuse-new buffer
```

Ensure your training script honors the
[training-script contract](docs/training-script-contract.md) (writes
`result.json` matching `automil/schemas/result.schema.json`, exits cleanly
on SIGTERM with a partial result). Then validate:

```bash
automil check
```

</details>

### 4. Run

Use **tmux** to keep the orchestrator and agent running in the background:

```bash
# Terminal 1: orchestrator (must stay running)
tmux new -s orchestrator
automil orchestrator start
# Ctrl-b d to detach

# Terminal 2: visualization (optional)
tmux new -s viz
automil viz start            # dashboard at localhost:8420
# Ctrl-b d to detach

# Terminal 3: agent loop
tmux new -s automil
claude --dangerously-skip-permissions   # autonomous mode, no permission prompts
# Type: /automil
```

### 5. Watch

```bash
automil status               # quick summary
automil rank                 # top proposals
# Open http://localhost:8420  # 3D experiment tree
```

---

## How It Works

```
  Your Project (unchanged)          autoMIL Overlay
  ========================          ===============
  src/models/clam.py           -->  automil/config.yaml
  src/train.py                      automil/program.md
  src/data_loader.py                automil/learnings.md
  ...                               automil/orchestrator/
                                       queue/ -> running/ -> archive/
                                       completed/
```

**The experiment cycle:**

```
Agent designs experiment
    |
    v
automil submit --files train.py models/clam.py
    |  (snapshots only changed files)
    v
Orchestrator picks up from queue
    |  (creates git worktree at base commit)
    |  (overlays changed files on top)
    v
Runs on GPU in isolation
    |  (CUDA_VISIBLE_DEVICES masked)
    v
Collects result.json
    |  (Pareto dominance: keep or discard?)
    v
Updates experiment graph
    |  (UCB scoring across branches)
    v
Agent reads results + learnings --> designs next experiment
```

Each experiment stores **only its diff**, not the full repo. A worktree provides
the complete project context at runtime.

---

## Training Script Contract

The seam between autoMIL and your code is the
[training-script contract](docs/training-script-contract.md): write a
`result.json` matching `automil/schemas/result.schema.json` before exiting,
honor `SIGTERM` for partial flush, declare required env vars in
`automil/config.yaml: env.required`. Any language, any ML library qualifies.

The minimum valid payload is `{"composite": <float>}`. A full autobench
example:

```json
{
  "status": "completed",
  "metrics": {
    "val_auc": 0.870,
    "val_bacc": 0.810,
    "test_auc": 0.872,
    "test_bacc": 0.830
  },
  "composite": 0.851,
  "elapsed_seconds": 4098,
  "peak_vram_mb": 4500
}
```

The schema is JSON Schema 2020-12 and is validated at ingest by the
orchestrator; malformed payloads transition the node to `crashed` with a
schema-location pointer.

<details>
<summary><b>Environment variables available to your script</b></summary>

| Variable | Value | Description |
|----------|-------|-------------|
| `CUDA_VISIBLE_DEVICES` | Physical GPU ID | Masked by orchestrator. |
| `AUTOMIL_GPU` | `0` | Logical device, always 0 because masking is already applied. |
| `AUTOMIL_NODE_ID` | `node_0042` | Experiment identifier. |
| `AUTOMIL_DESC` | `"try focal loss"` | Experiment description. |
| `AUTOMIL_RUNTIME` | `claude` / `codex` / ... | Runtime declared by the agent for trajectory tagging. |

Vars listed under `env.passthrough` in `config.yaml` are forwarded from the
orchestrator process to each experiment subprocess. `AUTOBENCH_ROOT`-style
auto-injection was removed in v1.0 (Phase 8 / DEC-01); declare what you need.

</details>

---

## CLI Reference

```
# Project setup + validation
automil init [--runtime <r>] [--no-healthcheck]   Overlay automil/ on current repo
automil check                                     Validate setup (protected files, env.required, backend, registry)
automil show-skill --runtime <r>                  Render merged per-runtime skill file to stdout

# Experiment lifecycle
automil submit --node <id> --desc "..." [--files <f>] [--max-time SEC]
                                                  Snapshot changed files and queue
automil cancel <node_id>                          Cancel a running experiment
automil resubmit <node_id>                        Re-queue a terminal experiment as a new node
automil rank                                      Show top-ranked proposals (UCB)
automil propose --parent <id> --desc "..."        Add a brainstormed proposal
automil reconcile [--recompute-best]              Sync graph with orchestrator state
automil status                                    Show experiment summary

# Variant registry (Phase 1)
automil port-variant <node_id>                    Convert a node's overlay into a registered variant module
automil promote-variant <variant_id>              Move a gate-passing candidate to canonical
automil refresh-registry                          Regenerate per-kind variants/__init__.py deterministically
automil apply <node_id>                           Apply a node's variant selection to config.yaml
automil revert-baseline                           Reset registry.protected paths to base_commit (mandatory pre-stash)
automil verify-repro <node_id>                    Reproduce a node via the registry path; assert |actual - expected| < tolerance

# Cell budget cap (Phase 4)
automil cell list / status / show <id>            Inspect cell budget state and consumed seconds

# Generalization gate (Phase 5)
automil nominate <node_id>                        Mark keep-status node as a gate candidate
automil promote <candidate_id>                    Run Stage B gate (paired Wilcoxon + bootstrap CI + Bonferroni)
automil gate manifest / status                    Manage / inspect the gate manifest

# Trajectory recorder (Phase 3)
automil trajectory record / export / status       JSONL trajectory capture and redacted export bundle

# Loop + daemons
automil start-loop / stop-loop                    Control agent loop flag
automil orchestrator start / stop / status        GPU scheduler daemon (best-fit bin packing)
automil viz start / stop / status                 3D visualization dashboard at localhost:8420
```

Run `automil <command> --help` for full flag listings.

---

## Project Structure

```
your-project/                    # your repo (untouched)
  src/
  models/
  train.py
  ...
  automil/                       # added by automil init
    config.yaml                  # project settings (run, files, env, scoring, cap, gate, backend, hardware)
    program.md                   # agent instructions for the loop
    learnings.md                 # accumulated insights
    graph.json                   # experiment tree (gitignored)
    cells/                       # cell budget state (Phase 4)
    variants/                    # registered variant modules (Phase 1)
      <parent>/                  #   one subdir per registered parent
        <name>.py                #   committed code; selected via config
        __init__.py              #   regenerated by `automil refresh-registry`
    orchestrator/
      queue/                     # pending
      running/<backend>/         # per-backend live job specs (Phase 6)
      archive/                   # permanent record
        node_0001/
          train.py               # only changed files
          spec.json              # experiment spec
          run.log                # stdout/stderr (orchestrator-owned, drained from backend.log_iter)
          result.json            # metrics
          trajectory.jsonl       # agent prompt + tool-call events (Phase 3, gitignored by default)
      completed/                 # notifications
```

---

## Agent Compatibility

| Runtime | Support Level | How to Start |
|---------|:------------:|-------------|
| **Claude Code** | First-class | `automil init --runtime claude` then `/automil-setup`, then `/automil` |
| **Codex** | First-class | `automil init --runtime codex`; per-runtime SKILL/AGENTS overlay shipped |
| **OpenCode** | First-class | `automil init --runtime opencode`; per-runtime SKILL/AGENTS overlay shipped |
| **DeepSeek** | First-class (routed) | `automil init --runtime deepseek-via-opencode` (or `deepseek-via-codex`); DeepSeek is a model accessed through a host runtime |
| **Cursor / Aider / Windsurf** | Compatible | Point the agent at `automil/program.md` and the [contract](docs/training-script-contract.md), any agent that can read files, edit code, and run shell commands works |

The canonical skill content lives under `_shared/`; per-runtime directories
ship only diffs/overlays. `automil show-skill --runtime <r>` renders the
merged result to stdout. See the [Agent Compatibility Guide](docs/agent-compatibility.md).

---

## Examples

| Example | Task | Library | Notes | Result |
|---------|------|---------|-------|--------|
| [`sklearn-iris`](examples/sklearn-iris/) | 3-class iris classification | scikit-learn | Reference second-consumer (~80 LOC, no `automil.*` imports) demonstrating the [training-script contract](docs/training-script-contract.md) | composite ≈ 0.95 |
| [`ovarian_hrd`](examples/ovarian_hrd/) | Binary HRD classification | CLAM-MB / H-optimus-1 | Pre-v1.0 autonomous run | 0.814 → 0.851 (+4.5%, 189 experiments) |
| [`clwd`](examples/clwd/) | 7-class lung subtype classification | autobench | Skeleton | - |
| [`placeholder`](examples/placeholder/) | - | - | Template emitted by `automil init` | - |

---

## Documentation

- **[Getting Started](docs/getting-started.md)**, full setup, configuration, and usage
- **[Training-Script Contract](docs/training-script-contract.md)**, the seam between framework and consumer (6 contract items + SIGTERM patterns)
- **[Agent Compatibility](docs/agent-compatibility.md)**, per-runtime setup, overlay merge model, multi-runtime asset layout
- **[Implementation Report](docs/implementation-report.md)**, v1.0 architecture, design decisions, and the 9-phase refactor that produced it
- **[CHANGELOG](CHANGELOG.md)**, v1.0 milestone release notes (BREAKING migration paths included)

---

<div align="center">

**[Get Started](docs/getting-started.md)** | **[View Examples](examples/)** | **[Report Issues](https://github.com/leoyin1127/autoMIL/issues)**

Apache 2.0 License

</div>
