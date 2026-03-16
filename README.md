# autoMIL

Autonomous LLM-agent experiment loop for optimizing Multiple Instance Learning models.

autoMIL uses an LLM agent (Claude Code) to iteratively improve ML training pipelines
through open-ended search: modifying architecture, loss functions, augmentation,
regularization, and training recipes, guided by persistent knowledge accumulation
and literature-informed strategy generation.

## Key Features

- **Open-ended search**: The agent modifies code directly, not just hyperparameters.
  It can implement novel loss functions, architectural changes, and techniques from
  recent papers. No predefined search space.

- **Persistent knowledge**: A `learnings.md` file accumulates insights across sessions.
  The agent avoids repeating failures and builds on what works, unlike stateless AutoML.

- **Git-based checkpointing**: Every experiment is a git commit. Improvements are kept,
  regressions are discarded via `git reset`. The full exploration trajectory is
  reproducible and auditable.

- **Simplicity criterion**: The agent rejects complex changes with marginal gains.
  Code simplicity is valued alongside metric improvement.

- **Session continuity**: A stop hook prevents the agent from halting mid-loop.
  State files enable seamless restart across sessions.

## Quick Start

### 1. Set up a new experiment

```bash
# Copy framework templates to your experiment directory
cp -r framework/templates/ experiments/my_task/

# Edit config.yaml with your project settings
cd experiments/my_task/
vi config.yaml

# Replace train_template.py and prepare_template.py with your scripts
mv train_template.py train.py
mv prepare_template.py prepare.py
# Edit train.py and prepare.py for your dataset and model
```

### 2. Install the Claude Code skill and hook

```bash
# Copy skill to your Claude Code skills directory
mkdir -p .claude/skills/autoMIL/
cp framework/skill/SKILL.md .claude/skills/autoMIL/

# Copy hook (update paths in the hook script if needed)
cp framework/hooks/on_stop.sh experiments/my_task/hooks/
chmod +x experiments/my_task/hooks/on_stop.sh
```

### 3. Run autoMIL

```bash
# Create experiment branch
git checkout -b autoMIL/my-run

# Start the loop (in Claude Code)
# Type: /autoresearch
# Or say: "start autoresearch"
```

### 4. Monitor progress

```bash
# Check experiment count and best metric
tail -5 experiments/my_task/results.tsv

# Read agent's accumulated knowledge
cat experiments/my_task/learnings.md

# Check current state
cat experiments/my_task/state.json
```

## Repository Structure

```
autoMIL/
  framework/           Reusable framework (copy templates/ to start)
    templates/           Config, program, train/prepare skeletons
    hooks/               Session continuity hook
    skill/               Claude Code skill definition
  experiments/         Paper experiments (one directory per dataset)
    ovarian_hrd/         Ovarian cancer HRD prediction
    lung_clwd/           Lung adenocarcinoma subtyping
    dataset_3/           (placeholder)
  baselines/           Comparison experiments (Optuna, random search)
  analysis/            Paper figures and analysis scripts
  scripts/             Utilities (dataset download, feature extraction)
```

## How It Works

```
        +------------------+
        | strategies.json  |  Pick next strategy
        +--------+---------+
                 |
                 v
        +------------------+
        |  Modify train.py |  Agent edits code
        +--------+---------+
                 |
                 v
        +------------------+
        |  git commit      |  Checkpoint
        +--------+---------+
                 |
                 v
        +------------------+
        |  Run experiment  |  5-fold CV
        +--------+---------+
                 |
                 v
        +------------------+
        |  Parse results   |  Auto-logged to results.tsv
        +--------+---------+
                 |
          +------+------+
          |             |
     improved?     worse/equal?
          |             |
          v             v
     git keep      git reset --hard HEAD~1
          |             |
          +------+------+
                 |
                 v
        +------------------+
        | Update state,    |  Persistent knowledge
        | learnings,       |
        | strategies       |
        +--------+---------+
                 |
                 v
             REPEAT
```

## Results

### Ovarian HRD Prediction

| Metric | Baseline | autoMIL Best | Improvement |
|--------|----------|-------------|-------------|
| Composite | 0.814 | 0.851 | +4.5% |
| Test AUC | 0.836 | 0.873 | +4.4% |
| Test BACC | 0.792 | 0.830 | +4.8% |

178 experiments, best config discovered autonomously:
R-Drop(a=1.0) + focal(g=1.0) + no instance eval + gradient clipping(0.5)
+ step LR(halve/20ep) + coordinate positional encoding.

## Requirements

- Python 3.10+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (for the autonomous agent loop)
- PyTorch
- [uv](https://docs.astral.sh/uv/) (recommended for dependency management)

## Citation

```bibtex
@article{autoMIL2026,
  title={autoMIL: Autonomous LLM-Driven Optimization of Multiple Instance Learning},
  author={TODO},
  year={2026}
}
```

## License

MIT
