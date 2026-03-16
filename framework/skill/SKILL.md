---
name: autoMIL
description: Start or stop the autonomous ML experiment loop. Use when the user says "start autoresearch", "run autoresearch", "begin the experiment loop", or "/autoresearch". Activates a stop hook that prevents the agent from stopping between experiments, forcing continuous optimization following program.md.
---

# Autoresearch Loop

Autonomous experiment loop that continuously improves ML models by modifying
the training script, running cross-validation, and keeping/discarding based on
metric improvement.

## Starting the Loop

1. Create the activation flag:
   ```bash
   touch .autoresearch_active
   ```

2. Read the current state (in this order):
   - `state.json` for where you left off (strategy, last experiment, best metric)
   - `learnings.md` for consolidated insights ("What Works" / "What Doesn't Work")
   - `strategies.json` for strategy catalog and experiment history
   - `config.yaml` for project-specific settings
   - Editable files listed in config.yaml for current code state
   - `program.md` for full rules

3. Begin the experiment loop as described in `program.md`. The stop hook at
   `hooks/on_stop.sh` will prevent you from stopping as long as the flag exists.

## Stopping the Loop

The human stops the loop by running:
```bash
rm .autoresearch_active
```

Or by pressing Ctrl+C to kill the session.

## Rules

- Follow `program.md` exactly
- Only modify files listed in `config.yaml` under `files.editable`
- Optimization target: defined in `config.yaml` under `metrics.optimize`
- Keep commits that improve the metric, discard the rest
- Results are auto-logged to `results.tsv` by the training script
- After each experiment: update `state.json` and append to `learnings.md`
- Every 5 experiments: consolidate new patterns in learnings.md top sections
- NEVER STOP while the flag file exists
