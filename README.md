# autoMIL

Autonomous agent-driven Multiple Instance Learning for computational pathology.

autoMIL is a plug-and-play framework that overlays onto your existing ML project.
A coding agent autonomously designs experiments, edits your codebase, and the
framework handles GPU scheduling, parallel execution, result tracking, and
knowledge accumulation. You bring the project; autoMIL brings the experiment
infrastructure.

## Why autoMIL?

Manual ML development is slow: try an idea, edit code, run training, check
results, repeat. AutoML tools like Optuna can search hyperparameters, but they
can't invent new architectures, combine techniques creatively, or learn from
failed experiments.

autoMIL bridges this gap. It gives a coding agent the tools to:

- **Explore multiple branches** simultaneously, not just iterate linearly
- **Remember what worked** across sessions via persistent learnings
- **Run experiments in parallel** across GPUs without file conflicts
- **Track the full experiment tree** with scoring that balances exploitation and exploration

## How It Works

```
Your existing project repo
    |
    | automil init (adds automil/ subdirectory)
    v
Agent reads codebase, scopes editable files
    |
    | automil submit (snapshots changed files)
    v
Orchestrator creates git worktree + overlay
    |
    | runs on GPU in isolation
    v
result.json --> graph promotion --> learnings update --> next experiment
```

1. **Setup** (`/automil-setup`): The agent scopes your codebase, configures
   `automil/config.yaml`, verifies the training contract, and establishes a baseline.
2. **Loop** (`/automil`): The agent designs experiments, edits files, submits via CLI.
   The orchestrator runs each in an isolated git worktree with only the changed files
   overlaid. Results feed back into the experiment graph for the next iteration.

Each experiment stores only its diff (the files that changed), not the full repo.
The orchestrator creates a temporary git worktree at the base commit and overlays
the changed files on top, so experiments run in a complete project environment
without copying the entire codebase.

## Features

- **Plug-and-play**: Overlays onto any existing ML project. No restructuring required.
- **Agent-agnostic**: Works with Claude Code (first-class), Cursor, Codex, Aider,
  Windsurf, or any agent with file editing and shell access.
- **Full-codebase scope**: The agent can modify any file, not just a single training
  script. Architecture changes, new model files, loss functions, all captured.
- **Configurable training script**: Set `run.script` in config to point at your
  entry point, whatever it's called.
- **Experiment graph**: Tree-based tracking with UCB-inspired scoring for
  multi-branch exploration. Pareto-dominance keep/discard.
- **Git worktree isolation**: Each experiment runs in a snapshot. Only changed
  files are stored per experiment. Parallel execution without conflicts.
- **GPU orchestrator**: Background daemon with best-fit bin packing across GPUs.
  Handles OOM detection, timeouts, crash recovery, and orphan cleanup.
- **3D visualization**: Interactive Three.js dashboard for exploring the
  experiment tree in real time via Server-Sent Events.
- **Persistent knowledge**: Learnings accumulate in `learnings.md` across sessions.
  The agent reads past failures and successes before designing new experiments.
- **Setup validation**: `automil check` validates your project configuration
  before you start running experiments.

## Installation

```bash
git clone https://github.com/leoyin1127/autoMIL.git
cd autoMIL
pip install -e .
```

## Quick Start

### 1. Initialize in your project

```bash
cd /path/to/your/project    # must be an existing git repo
automil init                 # creates automil/ subdirectory
```

### 2. Setup (agent-driven or manual)

**With Claude Code:**
```bash
claude
# Type: /automil-setup
```

The agent will scope your codebase, fill in `automil/config.yaml`, verify the
training contract, and establish a baseline. This runs once.

**Manual setup:**
Edit `automil/config.yaml`:
- Set `run.script` to your training script (e.g., `"train.py"`, `"src/main.py"`)
- Set `data.*` paths to your features, splits, and metadata
- Set `files.editable` to the files the agent can modify
- Set `files.readonly` to files that must not change
- Set `baseline.*` to your starting model's performance

Ensure your training script writes `result.json` before exiting (see
[Training Script Contract](#training-script-contract)).

Validate: `automil check`

### 3. Run experiments

```bash
automil orchestrator start   # start GPU scheduler
automil viz start            # optional: 3D dashboard at localhost:8420
```

**With Claude Code:**
```bash
claude
# Type: /automil
```

**With other agents:** Point them at `automil/program.md` and tell them to
follow Phase 2 (Experiment Loop).

### 4. Monitor

```bash
automil status               # quick summary
automil rank                 # see top proposals
# Open http://localhost:8420  for 3D experiment tree
```

### 5. Stop

```bash
automil stop-loop            # lets the agent exit
automil orchestrator stop    # stops GPU scheduler
```

## Training Script Contract

Your training script must write a `result.json` file to its working directory
before exiting. This is the only contract between your code and autoMIL:

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

The orchestrator provides these environment variables to your script:

| Variable | Value | Description |
|----------|-------|-------------|
| `CUDA_VISIBLE_DEVICES` | Physical GPU ID | Masked by orchestrator |
| `AUTOMIL_GPU` | `0` | Logical device (always 0, use `cuda:0`) |
| `AUTOMIL_NODE_ID` | e.g., `node_0042` | Experiment identifier |
| `AUTOMIL_DESC` | e.g., `"try focal loss"` | Experiment description |

If the script crashes before writing `result.json`, the experiment is marked
as crashed. OOM is detected from log content.

## How Experiments Run

1. The agent edits files in your repo (any files in `files.editable`)
2. Runs `automil submit --node node_0001 --desc "try focal loss" --files train.py models/clam.py`
3. The CLI snapshots only the changed files to `automil/orchestrator/archive/node_0001/`
4. The orchestrator creates a git worktree at the base commit
5. Changed files are overlaid on the worktree
6. The experiment runs in isolation on a GPU
7. `result.json` is collected; completion notification written
8. The agent runs `automil reconcile` to update the experiment graph
9. Keep/discard is computed via Pareto dominance (must improve composite AND
   not regress on any tracked metric vs parent)

## CLI Reference

| Command | Description |
|---------|-------------|
| `automil init` | Add autoMIL to current git repo |
| `automil check` | Validate project setup |
| `automil submit --node <id> --desc "..." --files <f>` | Queue an experiment |
| `automil rank` | Show top-ranked proposals |
| `automil propose --parent <id> --desc "..."` | Add a proposal |
| `automil reconcile` | Sync graph with orchestrator |
| `automil status` | Show experiment summary |
| `automil start-loop` | Enable continuous loop |
| `automil stop-loop` | Allow agent to stop |
| `automil orchestrator start/stop/status` | Manage GPU scheduler |
| `automil viz start/stop/status` | Manage 3D dashboard |

## Project Structure

After `automil init`, your project looks like:

```
your-project/               # your existing repo (untouched)
  src/
  models/
  train.py                  # your training script
  ...
  automil/                  # added by autoMIL
    config.yaml             # project configuration
    program.md              # agent instructions
    learnings.md            # accumulated insights
    .gitignore              # excludes runtime files
    graph.json              # experiment tree (runtime, gitignored)
    results.tsv             # flat log (runtime, gitignored)
    orchestrator/
      queue/                # pending experiments
      running/              # active experiments
      archive/              # permanent record per experiment
        node_0001/
          train.py          # only the files that changed
          spec.json
          run.log
          result.json
      completed/            # completion notifications
```

## Agent Compatibility

| Agent | Support | Setup |
|-------|---------|-------|
| Claude Code | First-class (skills + hooks) | `/automil-setup` then `/automil` |
| Cursor | CLI + program.md | Add `automil/program.md` to rules |
| Codex | CLI + program.md | Include program.md in context |
| Aider | CLI + program.md | `/read automil/program.md` |
| Windsurf | CLI + program.md | Add program.md to Cascade |

See [Agent Compatibility Guide](docs/agent-compatibility.md) for detailed setup per agent.

## Examples

Reference configurations in `examples/`:

- **`ovarian_hrd/`** - Binary HRD classification from ovarian cancer WSIs.
  189 experiments, best composite 0.851 (from 0.814 baseline, +4.5% improvement).
- **`clwd/`** - Multi-class lung adenocarcinoma subtyping (7 classes, 408 WSIs).
- **`placeholder/`** - Minimal template showing what `automil init` creates.

## Documentation

- [Getting Started](docs/getting-started.md) - Full setup and usage guide
- [Agent Compatibility](docs/agent-compatibility.md) - Per-agent setup instructions
- [Implementation Report](docs/implementation-report.md) - Architecture and design decisions

## License

Apache 2.0. See [LICENSE](LICENSE).
