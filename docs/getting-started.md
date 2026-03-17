# Getting Started with autoMIL

## Prerequisites

- Python 3.10+
- NVIDIA GPU(s) with CUDA
- Git
- A coding agent (Claude Code recommended, or Cursor/Codex/Aider)

## Installation

```bash
git clone https://github.com/your-org/autoMIL.git
cd autoMIL
pip install -e .
```

## Adding autoMIL to Your Project

autoMIL overlays onto an existing git repository. Navigate to your project
root and run:

```bash
cd /path/to/your/project   # must be a git repo
automil init
```

This creates an `automil/` subdirectory with:
- `config.yaml` - Project configuration (paths, task, encoders, metrics)
- `program.md` - Agent instructions for the experiment loop
- `learnings.md` - Accumulated insights (starts empty)
- `.gitignore` - Excludes runtime files (graph.json, orchestrator/)
- `orchestrator/` - Runtime directories for experiment management

Your existing codebase is untouched. The agent will scope it and determine
what to edit.

## Configuration

The most important field is `run.script` - set this to your training script's
filename (e.g., "train.py", "main.py", "src/experiment.py"). The orchestrator
will run this script for each experiment.

Edit `automil/config.yaml`:

1. **Data paths**: Set `data.features_dir`, `data.splits_dir`, `data.mapping_csv`
2. **Task**: Set `task.name`, `task.type` (binary/multiclass), `task.label_column`
3. **Encoders**: List available encoders with their dimensions
4. **Baseline**: Set your starting performance numbers
5. **Files**: The agent will populate `files.editable` and `files.readonly`
   after scoping the codebase, or you can set them manually

## Training Script Contract

Your training script must write a `result.json` file to its working directory
before exiting:

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

The orchestrator reads `result.json` after the process exits. If the file is
missing, the experiment is marked as crashed.

**GPU handling**: The orchestrator sets `CUDA_VISIBLE_DEVICES` to mask the
physical GPU and `AUTOMIL_GPU=0` (logical device). Your training script
should use `AUTOMIL_GPU` or simply default to `cuda:0`.

## Running the Loop

### 1. Start the orchestrator
```bash
automil orchestrator start
```

### 2. Start the visualization dashboard (optional)
```bash
automil viz start
# Open http://localhost:8420 in your browser
```

### 3. Launch your coding agent

**Claude Code:**
```bash
claude
# Then type: /automil
```

**Other agents:** Point them at `automil/program.md` and tell them to follow
the instructions.

### 4. Monitor progress
```bash
automil status          # Quick summary
automil viz start       # 3D dashboard at localhost:8420
```

## How Experiments Run

1. The agent edits files in your repo (any files, not just one)
2. Runs `automil submit --node node_0001 --desc "try focal loss" --files train.py models/clam.py`
3. The CLI snapshots only the changed files to `automil/orchestrator/archive/node_0001/`
4. The orchestrator creates a git worktree at the base commit, overlays the changed files
5. The experiment runs in isolation on a GPU
6. Results appear in `automil/orchestrator/completed/`
7. The agent runs `automil reconcile` to update the experiment graph

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

## Examples

See `examples/` for reference configurations:
- `ovarian_hrd/automil/` - Binary classification with 189 experiments
- `clwd/automil/` - Multi-class lung adenocarcinoma subtyping
- `placeholder/automil/` - Minimal template
