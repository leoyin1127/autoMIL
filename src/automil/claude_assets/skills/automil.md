---
name: automil
description: Run the autonomous MIL experiment loop. Requires setup first (use /automil-setup).
---

# autoMIL Experiment Loop

Run the autonomous experiment loop. Setup must be completed first via
`/automil-setup`.

## Pre-flight

1. Verify setup: `automil check` (must pass with no issues)
2. Start orchestrator: `automil orchestrator start`
3. Start loop flag: `automil start-loop`

## Run

1. Read `automil/config.yaml`, `automil/graph.json`, `automil/learnings.md`
2. Read the training script and key source files from `files.editable`
3. Run `automil reconcile` to sync graph state

Then follow Phase 2 in `automil/program.md`:

**LOOP FOREVER:**

1. `automil reconcile`
2. `automil rank` to get top proposals. If none, brainstorm new ones.
3. Read `automil/learnings.md` to avoid repeating failures.
4. For each proposal:
   a. Edit project files to implement the idea
   b. `automil submit --node <id> --desc "..." --files <changed files>`
   c. Restore working tree: `git checkout -- <files>`
5. Wait for completions in `automil/orchestrator/completed/`
6. `automil reconcile` to update graph
7. Update `automil/learnings.md`
8. If improved: commit winning changes
9. If no proposals: brainstorm, `automil propose`
10. Repeat

## Rules

- NEVER STOP while `.automil_active` exists
- Use `automil submit` for every experiment (not manual runs)
- Use `automil rank` to pick experiments (not random)
- Update `automil/learnings.md` after every result
- Commit winning experiments to git

## Stopping

User runs `automil stop-loop` to allow the agent to exit.
