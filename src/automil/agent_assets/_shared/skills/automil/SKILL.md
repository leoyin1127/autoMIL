---
name: automil
description: Run the autonomous MIL experiment loop. Requires setup first (use /automil-setup).
---

# autoMIL Experiment Loop

Run the autonomous experiment loop. Setup must be completed first via
`/automil-setup`.

## Pre-flight

1. `cd` to the directory containing `automil/config.yaml`
2. Verify setup: `uv run automil check` (must pass with no issues)
3. Start orchestrator in a **tmux** session (it must stay running):
   ```bash
   tmux new -s orchestrator
   uv run automil orchestrator start
   # Ctrl-b d to detach
   ```
4. Start the agent loop in another tmux session with `--dangerously-skip-permissions`
   so it can run autonomously without prompts:
   ```bash
   tmux new -s automil
   claude --dangerously-skip-permissions
   # Then type: /automil
   ```
5. Start loop flag: `uv run automil start-loop`
6. **Start a persistent Monitor watcher on the orchestrator log** (critical —
   see "Event-driven loop" below)

## Event-driven loop — start a Monitor watcher

The loop is autonomous and long-running (experiments take 60–240 min
each). You **must** drive it from completion events, not polling.
Immediately after the first `automil submit` in any session, start a
persistent `Monitor` on `automil/orchestrator/orchestrator.log` filtered
to state-transition lines. Without this, GPUs go idle for hours between
submits and the loop stalls.

Use the `Monitor` tool with:

- `persistent: true` (lives for the whole session, not the 5-min default)
- `timeout_ms: 3600000` (ignored when persistent, but set for safety)
- An **absolute** path to the log (Monitor runs in an independent shell)
- `tail -n 0 -F` so you start at EOF and follow through rotation
- `grep --line-buffered` — without this, pipe buffering delays events by
  minutes
- A tight regex: `Completed node_|Launched node_|crash` is enough to
  stay oriented without flooding the chat

Example command:

```bash
tail -n 0 -F /abs/path/to/project/automil/orchestrator/orchestrator.log \
  2>/dev/null \
  | grep --line-buffered -E "Completed node_|Launched node_|crash"
```

When a `Completed` event arrives: reconcile, read the result, update
`learnings.md`, queue the next experiment. Never let the queue go empty
while `.automil_active` exists. If the monitor gets auto-stopped for
volume, restart it with a tighter regex.

For one-shot "wait until this one command finishes" (not the loop),
prefer `Bash(..., run_in_background=true)` — Monitor is for streaming.

## Important: File paths are git-root-relative

All file paths in `files.editable`, `uv run automil submit --files`, and `run.command`
are relative to the **git repo root**, not to where automil/ lives. The
orchestrator creates worktrees from the git root, so overlay paths must match.

## Two standing directives (do not drop these between sessions)

1. **Saturate every GPU — submit experiments until the VRAM bin-packer
   can't fit another one, not until each GPU has one run.** The
   orchestrator's whole purpose is parallel bin-packing. Before every
   batch, measure the actual peak VRAM of a typical run (see
   `automil/orchestrator/archive/<node>/result.json → peak_vram_mb`)
   and set `orchestrator.max_concurrent_per_gpu` and
   `orchestrator.default_vram_estimate_gb` in `config.yaml` so that a
   realistic number of workers fit per card with the safety margin.
   Config hot-reloads live — no daemon restart needed. Then check
   `automil/orchestrator/gpu_state.json` → `schedulable_free_gb` and
   `running` per GPU. If `running` has fewer workers than the cap
   allows while the queue is non-empty and `schedulable_free_gb` is
   large, the loop is running serially and that is a framework bug,
   not a safety feature. Propose and submit more specs until the cap
   binds.

2. **Before every new experiment batch, read recent literature.** Do
   not only hill-climb on hyperparameters. Delegate a short research
   sub-agent (WebSearch + WebFetch) for the most recent (current year
   and prior year) methods relevant to the project's model class and
   bottleneck, pick 1–2 tractable drop-ins that fit the existing
   pipeline (no full rewrites, no data-format changes), and queue
   those alongside the usual hyperparameter sweeps. Aim for a
   portfolio: half regularization / hyperparameter tweaks, half
   structurally novel ideas from the literature. Log the paper title
   and arXiv ID in `automil/learnings.md` whenever you try something
   from a paper, so future sessions don't re-try it blind.

## Run

1. Read `automil/config.yaml`, `automil/graph.json`, `automil/learnings.md`
2. Read the training script and key source files from `files.editable`
3. Run `uv run automil reconcile` to sync graph state

Then follow Phase 2 in `automil/program.md`:

**LOOP FOREVER:**

1. `uv run automil reconcile`
2. `uv run automil rank` to get top proposals. If none, brainstorm new ones.
3. Read `automil/learnings.md` to avoid repeating failures.
4. For each proposal:
   a. Edit project files to implement the idea
   b. `uv run automil submit --node <id> --desc "..." --files <changed files>`
   c. Restore working tree: `git checkout -- <files>`
5. Wait for Monitor completion events (do **not** poll) — the watcher
   streams `Completed node_...` lines as they arrive
6. `uv run automil reconcile` to update graph
7. Update `automil/learnings.md`
8. If improved: commit winning changes
9. If no proposals: brainstorm, `uv run automil propose`
10. Repeat

## Rules

- NEVER STOP while `.automil_active` exists
- Use `uv run automil submit` for every experiment (not manual runs)
- Use `uv run automil rank` to pick experiments (not random)
- Update `automil/learnings.md` after every result
- Commit winning experiments to git
- File paths in submit --files must be relative to git repo root

## Stopping

User runs `uv run automil stop-loop` to allow the agent to exit.
