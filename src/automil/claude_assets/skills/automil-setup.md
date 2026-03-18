---
name: automil-setup
description: Set up autoMIL in an existing project. Scopes codebase, configures experiment framework, validates setup.
---

# autoMIL Setup

One-time setup that prepares an existing project for autonomous experimentation.

## Steps

### 1. Initialize

If `automil/` directory doesn't exist yet:

```bash
automil init
```

This creates `automil/` with config.yaml, program.md, learnings.md, and
orchestrator directories.

### 2. Scope the codebase

Read the project structure thoroughly. Identify:

- **Training script**: the main entry point that trains the model and evaluates it.
  Could be `train.py`, `main.py`, `src/train.py`, or anything else.
- **Model architecture**: files defining the model (layers, attention, pooling)
- **Data loading**: dataset classes, data loaders, preprocessing
- **Loss/optimizer**: loss functions, optimizer configs, learning rate schedules
- **Evaluation**: metrics computation, cross-validation setup
- **Configuration**: hyperparameters, constants, config files

### 3. Configure automil/config.yaml

Update every field:

- `run.script`: path to the training script relative to project root
- `run.command`: (optional) full command override if the script needs special invocation
- `data.*`: paths to features, splits, metadata
- `encoders.*`: available encoders and dimensions
- `baseline.*`: starting model name, framework, and performance metrics
- `files.editable`: list every file the agent is allowed to modify
- `files.readonly`: list files that must not be changed (evaluation code, data splits, etc.)
- `metrics.*`: what metrics to track and how composite is computed
- `training.*`: current hyperparameter values (for agent reference)

### 4. Verify the result.json contract

The training script must write `result.json` to its working directory before
exiting. Check if it already does this. If not, add it.

Required schema:
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

If the training script doesn't write this, modify it to add result.json
output at the end of the training loop.

### 5. Validate

```bash
automil check
```

Fix any issues reported. All checks should pass before starting experiments.

### 6. Establish baseline

Run the unmodified training script as the first experiment:

```bash
automil submit --node node_0001 --desc "baseline" --files <training_script>
```

Wait for the orchestrator to complete it, then verify results:

```bash
automil reconcile
automil status
```

### 7. Done

Setup is complete. Use `/automil` to start the experiment loop.
