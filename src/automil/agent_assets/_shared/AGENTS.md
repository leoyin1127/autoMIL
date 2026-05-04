# AGENTS

This project uses autoMIL — an autonomous experiment framework for ML.

## How to work in this repo

- Read `automil/program.md` for the experiment goals.
- Read `automil/learnings.md` before submitting (avoid repeating dead-ends).
- Submit experiments via `automil submit`. Never run training scripts directly.

## Constraints

- Cap: 6h per cell (framework-enforced, Phase 4).
- Trajectories captured automatically (gitignored by default).

## Runtime

- Set `AUTOMIL_RUNTIME` to declare your runtime (e.g. `export AUTOMIL_RUNTIME=claude-code`).
- Use `automil show-skill --runtime <name>` to view the runtime-specific setup guide.
