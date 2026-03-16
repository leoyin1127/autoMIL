# autoMIL Framework

Reusable templates for setting up an autonomous experiment loop on any ML task.

## Files

| File | Purpose |
|------|---------|
| `templates/config.yaml` | Project configuration (paths, metrics, run command, dataset info) |
| `templates/program.md` | Experiment loop instructions for the agent (generic, references config) |
| `templates/train_template.py` | Training script skeleton (the file the agent modifies) |
| `templates/prepare_template.py` | Data loading and evaluation skeleton (read-only) |
| `templates/strategies.json` | Strategy catalog template (agent picks from and updates this) |
| `templates/learnings.md` | Knowledge accumulation template (agent appends insights) |
| `templates/state.json` | Session restart state template |
| `hooks/on_stop.sh` | Shell hook that prevents the agent from stopping mid-loop |
| `skill/SKILL.md` | Claude Code skill definition for activating the loop |

## Setup for a New Task

1. **Copy templates** to your experiment directory:
   ```bash
   cp -r framework/templates/ experiments/my_task/
   ```

2. **Edit `config.yaml`** with your:
   - Project name and task description
   - Paths to features, splits, and output
   - Metric to optimize and composite formula
   - Run command for your training script
   - Baseline metric value
   - Dataset details

3. **Replace `train_template.py`** with your actual training script:
   - Rename to `train.py`
   - Must print parseable metrics matching `config.yaml`'s `extract_command`
   - Must auto-log to `results.tsv`
   - The agent will modify this file during the loop

4. **Replace `prepare_template.py`** with your data/eval script:
   - Rename to `prepare.py`
   - Defines data loading, CV splits, and evaluation metrics
   - The agent CANNOT modify this file

5. **Populate `strategies.json`** with initial strategies for your domain:
   - Research relevant techniques for your task
   - Add 5-10 strategies with tier, effort, expected gain, and references
   - The agent will add more strategies as it runs out

6. **Install the hook and skill**:
   ```bash
   mkdir -p experiments/my_task/hooks/
   cp framework/hooks/on_stop.sh experiments/my_task/hooks/
   chmod +x experiments/my_task/hooks/on_stop.sh

   mkdir -p .claude/skills/autoMIL/
   cp framework/skill/SKILL.md .claude/skills/autoMIL/
   ```

7. **Run the baseline** to establish the starting metric, then update
   `config.yaml` with the baseline value.

## Customizing Metrics

The `metrics.composite_formula` in config.yaml is a Python expression.
The agent uses this to compute keep/discard decisions. Examples:

```yaml
# Binary classification
composite_formula: "(test_auc + test_bacc) / 2"

# Single metric
optimize: "test_auc"
composite_formula: "test_auc"

# Multi-class with F1
composite_formula: "(test_macro_f1 + test_bacc) / 2"

# Regression
composite_formula: "-test_rmse"  # Negative because lower is better
```

## Customizing the Stop Hook

The hook script uses relative paths from the experiment directory.
If your experiment directory is not a direct child of the repo root,
update the `EXPERIMENT_DIR` line in `on_stop.sh`.
