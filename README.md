<div align="center">

# autoMIL

**Autonomous Agent-Driven Multiple Instance Learning**

*Let AI agents run your ML experiments while you sleep.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-49%20passing-brightgreen.svg)](#)

---

**autoMIL** is a plug-and-play experiment framework for computational pathology.
It overlays onto your existing ML project and lets any coding agent autonomously
design, run, and learn from experiments, pushing your models further than
manual iteration ever could.

[Getting Started](#quick-start) | [How It Works](#how-it-works) | [Documentation](docs/getting-started.md)

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
| **Agent-agnostic** | Claude Code (first-class), Cursor, Codex, Aider, Windsurf, or any agent. |
| **Full-codebase scope** | Agent edits any file: architectures, losses, augmentations, optimizers. |
| **Git worktree isolation** | Each experiment runs in a snapshot. Only changed files stored. |
| **Multi-GPU orchestrator** | Background daemon with bin packing, OOM detection, crash recovery. |
| **Experiment tree** | UCB-inspired scoring balances exploitation and exploration across branches. |
| **3D dashboard** | Interactive Three.js visualization with live SSE updates. |
| **Persistent learnings** | Knowledge accumulates across sessions. Agents don't repeat mistakes. |
| **Setup validation** | `automil check` catches config issues before experiments run. |

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/leoyin1127/autoMIL.git
cd autoMIL
pip install -e .
```

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
contract, and establishes a baseline. Fully autonomous.

</details>

<details>
<summary><b>Manual setup</b></summary>

Edit `automil/config.yaml`:

```yaml
run:
  script: "train.py"          # your training script (any name)

files:
  editable: ["train.py", "models/"]   # what the agent can modify
  readonly: ["evaluate.py"]           # what must not change

baseline:
  composite: 0.814             # your starting performance
```

Ensure your training script writes [`result.json`](#training-script-contract)
before exiting, then validate:

```bash
automil check
```

</details>

### 4. Run

```bash
automil orchestrator start   # GPU scheduler
automil viz start            # 3D dashboard at localhost:8420 (optional)
```

```bash
claude                       # or any coding agent
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

The only thing autoMIL needs from your code: write `result.json` before exiting.

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

<details>
<summary><b>Environment variables available to your script</b></summary>

| Variable | Value | Description |
|----------|-------|-------------|
| `CUDA_VISIBLE_DEVICES` | Physical GPU ID | Masked by orchestrator |
| `AUTOMIL_GPU` | `0` | Logical device (always 0) |
| `AUTOMIL_NODE_ID` | `node_0042` | Experiment identifier |
| `AUTOMIL_DESC` | `"try focal loss"` | Experiment description |

</details>

---

## CLI Reference

```
automil init                                    Add autoMIL to current repo
automil check                                   Validate project setup
automil submit --node <id> --desc "..." --files <f>   Queue an experiment
automil rank                                    Show top proposals
automil propose --parent <id> --desc "..."      Add a proposal
automil reconcile                               Sync graph with orchestrator
automil status                                  Show experiment summary
automil start-loop / stop-loop                  Control agent loop
automil orchestrator start / stop / status      GPU scheduler daemon
automil viz start / stop / status               3D visualization dashboard
```

---

## Project Structure

```
your-project/                    # your repo (untouched)
  src/
  models/
  train.py
  ...
  automil/                       # added by autoMIL
    config.yaml                  # project settings
    program.md                   # agent instructions
    learnings.md                 # accumulated insights
    graph.json                   # experiment tree (gitignored)
    orchestrator/
      queue/                     # pending
      archive/                   # permanent record
        node_0001/
          train.py               # only changed files
          spec.json              # experiment spec
          run.log                # stdout/stderr
          result.json            # metrics
      completed/                 # notifications
```

---

## Agent Compatibility

| Agent | Support Level | How to Start |
|-------|:------------:|-------------|
| **Claude Code** | First-class | `/automil-setup` then `/automil` |
| **Cursor** | Full | Add `automil/program.md` to rules |
| **Codex** | Full | Include `automil/program.md` in context |
| **Aider** | Full | `/read automil/program.md` |
| **Windsurf** | Full | Add `automil/program.md` to Cascade |

Any agent that can read files, edit code, and run shell commands works.
See [Agent Compatibility Guide](docs/agent-compatibility.md) for details.

---

## Examples

| Example | Task | Dataset | Experiments | Result |
|---------|------|---------|:-----------:|--------|
| [`ovarian_hrd`](examples/ovarian_hrd/) | Binary HRD classification | 206 ovarian WSIs | 189 | 0.814 -> 0.851 (+4.5%) |
| [`clwd`](examples/clwd/) | 7-class subtype classification | 408 lung WSIs | - | Skeleton |
| [`placeholder`](examples/placeholder/) | - | - | - | Template |

---

## Documentation

- **[Getting Started](docs/getting-started.md)** - Full setup, configuration, and usage
- **[Agent Compatibility](docs/agent-compatibility.md)** - Per-agent setup instructions
- **[Implementation Report](docs/implementation-report.md)** - Architecture and design decisions

---

<div align="center">

**[Get Started](docs/getting-started.md)** | **[View Examples](examples/)** | **[Report Issues](https://github.com/leoyin1127/autoMIL/issues)**

Apache 2.0 License

</div>
