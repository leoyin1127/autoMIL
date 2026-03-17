---
name: automil
description: Start or stop the autonomous MIL experiment loop
---

# autoMIL Skill

## First-time setup

If `automil/config.yaml` doesn't exist or has placeholder values:

1. Run `automil init` (if not already done)
2. Follow Phase 1 (Setup) in `automil/program.md`:
   - Scope the codebase
   - Configure `automil/config.yaml` (especially `run.script` and `files.editable`)
   - Verify the training script writes `result.json`
   - Run `automil check` to validate
   - Establish baseline via `automil submit`
3. Run `automil start-loop`
4. Start `automil orchestrator start`

## Resuming the loop

1. Read `automil/config.yaml`, `automil/graph.json`, `automil/learnings.md`, `automil/program.md`
2. Run `automil reconcile`
3. Continue the experiment loop (Phase 2 in program.md)

## Stopping

Run `automil stop-loop` to allow the agent to exit.

## Rules

- Follow `automil/program.md` exactly
- Use `automil submit` to queue experiments
- Use `automil rank` to get top proposals
- Use `automil reconcile` to sync state
- NEVER STOP while `.automil_active` exists
