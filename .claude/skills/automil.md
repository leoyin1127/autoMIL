---
name: automil
description: Start or stop the autonomous MIL experiment loop
---

# autoMIL Skill

Start the autonomous experiment loop for improving MIL models.

## Starting the loop

1. Create the activation flag:
   ```bash
   automil start-loop
   ```

2. Read the current state:
   - `config.yaml` for project settings
   - `graph.json` for experiment tree
   - `learnings.md` for accumulated insights
   - `train.py` for current training recipe
   - `program.md` for full loop instructions

3. Start the orchestrator if not running:
   ```bash
   automil orchestrator start
   ```

4. Begin the experiment loop as described in `program.md`.

## Stopping the loop

The human stops the loop by running:
```bash
automil stop-loop
```

## Rules

- Follow `program.md` exactly
- Optimization target: composite = (test_auc + test_bacc) / 2
- Use `automil submit` to queue experiments
- Use `automil rank` to get top proposals
- Use `automil reconcile` to sync state
- NEVER STOP while `.automil_active` exists
