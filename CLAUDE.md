# CLAUDE.md

## Project Overview

autoMIL is an autonomous experiment framework for Multiple Instance Learning in computational pathology. It overlays onto existing ML project repos, enabling coding agents to iteratively improve models through persistent experimentation, knowledge accumulation, and multi-branch exploration.

**Package:** `src/automil/` installed as `automil` via `pip install -e .`
**CLI entry point:** `automil` (defined in `pyproject.toml` as `automil.cli:main`)

## Architecture

autoMIL overlays an `automil/` subdirectory onto an existing git repo. It does NOT create train.py or prepare.py. The agent scopes the full codebase and determines what to edit.

**Core modules:**
- `graph.py` - Experiment tree tracking with UCB-inspired scoring and Pareto-dominance keep/discard
- `runner.py` - Git worktree overlay for isolated parallel experiment execution
- `orchestrator.py` - GPU scheduler daemon with best-fit bin packing
- `cli.py` - Click-based CLI wrapping all operations
- `viz/server.py` - Real-time 3D dashboard (aiohttp + SSE + Three.js)

**Key design decisions:**
- The training script is configurable via `run.script` in config.yaml (defaults to "train.py")
- Experiments are tracked as a directed tree in `graph.json`, not a flat log
- Each experiment stores only its changed files (overlay), not the full repo
- The orchestrator runs experiments in git worktrees, overlaying modified files on a base commit
- Keep/discard is computed by the framework via Pareto dominance, not by the training script
- `results.tsv` is written solely by the orchestrator from `result.json`, never by train.py
- `_recover_orphans()` only runs in the daemon loop (`run()`), never on construction (to prevent `status`/`stop` from corrupting live runs)

## Commands

```bash
# Install
pip install -e .

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_graph.py -v

# Run a specific test
uv run pytest tests/test_integration.py::TestEndToEnd::test_init_submit_flow -v

# CLI usage (inside a project repo)
automil init                    # overlay automil/ onto current repo
automil submit --node <id> --desc "..." --files train.py
automil rank
automil propose --parent <id> --desc "..."
automil reconcile
automil check                   # validate project setup
automil status
automil orchestrator start
automil viz start
```

## Key Files

| File | Lines | Role |
|------|-------|------|
| `src/automil/graph.py` | ~680 | Experiment tree, scoring, reconciliation |
| `src/automil/orchestrator.py` | ~750 | GPU scheduler daemon |
| `src/automil/cli.py` | ~400 | CLI commands |
| `src/automil/runner.py` | ~80 | Git worktree overlay |
| `src/automil/viz/server.py` | ~270 | SSE dashboard server |
| `src/automil/viz/static/app.js` | ~630 | 3D force graph frontend |

## Testing

48 tests across 4 files:
- `test_graph.py` (26) - graph API, scoring, reconciliation, migration
- `test_runner.py` (7) - worktree create/cleanup, overlay, result collection
- `test_cli.py` (5) - init, submit, rank
- `test_integration.py` (10) - end-to-end flows, path sanitization, deletions, scoring

## Conventions

- Commit messages: `type: summary` (conventional commits)
- Template extension: `.j2` (Jinja2)
- Runtime files (`graph.json`, `results.tsv`, `orchestrator/`) are gitignored in project dirs
- The `automil/` subdirectory is the framework's namespace inside user projects
- `_find_project_root()` walks up looking for `automil/config.yaml`
- Path validation: submit rejects absolute paths, `..` traversal, and paths escaping project root
- Auto-detect in submit excludes `automil/` directory from changed file detection

## Result Contract

Training scripts must write `result.json` to their working directory:
```json
{
  "status": "completed",
  "metrics": {"val_auc": 0.87, "val_bacc": 0.81, "test_auc": 0.87, "test_bacc": 0.83},
  "composite": 0.85,
  "elapsed_seconds": 4098,
  "peak_vram_mb": 4500
}
```

The orchestrator sets `CUDA_VISIBLE_DEVICES` for GPU masking and `AUTOMIL_GPU=0` (logical device).
