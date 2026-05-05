---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: "09"
subsystem: cli/cell
tags: [cli, cell, status, list, click-group, integration-test, CAP-06]

dependency_graph:
  requires:
    - 04-05  # cells.registry — list_cells, get_cell, consumed_seconds
  provides:
    - automil cell status [CELL_ID]
    - automil cell list [--no-header]
  affects:
    - src/automil/cli/__init__.py  # cell group registered alphabetically

tech_stack:
  added: []
  patterns:
    - Click group + subcommands via trajectory.py analog
    - Lazy import inside command body (Phase 1+3 discipline)
    - Stdlib f-string column formatting (no rich/tabulate)
    - running/*.json direct-read for count (no orchestrator instance)
    - CliRunner + monkeypatch.chdir + write_cell fixture pattern

key_files:
  created:
    - src/automil/cli/cell.py
    - tests/test_cli_cell.py
  modified:
    - src/automil/cli/__init__.py

decisions:
  - "Tolerant prefix match: cell_id shorter than 16 chars triggers prefix scan; ambiguous prefix raises ClickException with count"
  - "_count_running_in_cell reads running/*.json directly to avoid instantiating ExperimentOrchestrator at CLI time"
  - "_find_automil_dir wrapped in try/except so running-count gracefully returns 0 when not in automil project"

metrics:
  duration_minutes: 7
  tasks_completed: 3
  files_changed: 3
  completed_date: "2026-05-05"
---

# Phase 04 Plan 09: Cell CLI (cell status + cell list) Summary

`automil cell status/list` — operator-facing tabular view of per-cell budget state with full/prefix id lookup, running-count from disk, and pipe-friendly --no-header mode (CAP-06 / D-125).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement src/automil/cli/cell.py | 079c0b3 | src/automil/cli/cell.py (+127 lines) |
| 2 | Register cell group in cli/__init__.py | de20d59 | src/automil/cli/__init__.py (+1 line) |
| 3 | Write tests/test_cli_cell.py | 4eb86eb | tests/test_cli_cell.py (+372 lines) |

## What Was Built

### `src/automil/cli/cell.py` (127 lines)

Click group `@main.group("cell")` with two subcommands:

- **`cell status [CELL_ID]`** — tabular per-cell view. When no arg, lists all cells. When given a 16-char id, looks up directly via `get_cell()`. Shorter strings trigger tolerant prefix scan across `list_cells()`. Ambiguous prefix -> ClickException with count. Unknown prefix -> ClickException with "No cell found". Columns: `cell_id(8) | dataset(10) | encoder(10) | parent(10) | started(19) | consumed/budget(19) | status(14) | running(7)`.

- **`cell list [--no-header]`** — short pipe-friendly listing: `cell_id(8) | status(14) | consumed/budget(19)`. `--no-header` suppresses both the header row and separator.

Both commands lazy-import `automil.cells` inside the function body (Phase 1+3 discipline).

`_count_running_in_cell()` reads `automil/orchestrator/running/*.json` directly (no orchestrator instance) and counts specs where `metadata.cell_id == cell_id`. Tolerates JSON errors and missing directory.

Formatting via stdlib f-strings. No rich/tabulate added to deps.

### `src/automil/cli/__init__.py` (+1 line)

`from automil.cli import cell    # noqa: E402,F401  (CAP-06 / D-125)` inserted alphabetically after `cancel`, before `check`.

### `tests/test_cli_cell.py` (372 lines, 10 tests)

All 10 tests green:
1. `test_cell_list_empty` — `(no cells)` output when dir is empty
2. `test_cell_list_with_cells` — both cells with active/refusing-new status
3. `test_cell_status_lists_all_when_no_arg` — header + all 3 cells
4. `test_cell_status_specific_id_full` — full 16-char id lookup
5. `test_cell_status_specific_id_short_prefix` — prefix-match path
6. `test_cell_status_unknown_id_errors` — exit != 0, "No cell found"
7. `test_cell_status_ambiguous_prefix_errors` — "Ambiguous prefix" + "matched 2 cells"
8. `test_cell_list_no_header_pipe_friendly` — no header row with `--no-header`
9. `test_cell_status_running_count_from_disk` — counts matching metadata.cell_id
10. `test_cell_status_consumed_grows_with_started_at` — "01:00:" for 1h-old cell

## Verification Results

```
uv run pytest tests/test_cli_cell.py -q: 10 passed
uv run pytest tests/ -q (excluding pre-existing failures): 619 passed, 9 skipped
uv run automil cell --help: lists status + list subcommands
grep -E "autobench|AUTOBENCH_|benchmarks/" src/automil/cli/cell.py | wc -l: 0
```

Pre-existing failing tests (not caused by this plan):
- `tests/test_tick_cells.py::test_tick_cells_active_to_refusing_new` — was failing before this plan's commits (verified via git stash check)
- `tests/test_per_fold_writer.py` — autobench not installed in worktree

## Deviations from Plan

None — plan executed exactly as written.

Minor implementation note: `_count_running_in_cell()` wraps `_find_automil_dir()` in a try/except to return 0 gracefully when not inside an automil project (rather than raising ClickException from within the formatting loop). This is a correctness improvement for the test environment, not a deviation from the plan's intent.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. The CLI is read-only — it reads `cells/*.json` and `orchestrator/running/*.json` without writes.

## Self-Check: PASSED

- [x] `src/automil/cli/cell.py` exists
- [x] `tests/test_cli_cell.py` exists
- [x] Commit `079c0b3` exists (feat cell.py)
- [x] Commit `de20d59` exists (feat __init__.py)
- [x] Commit `4eb86eb` exists (test test_cli_cell.py)
- [x] All 10 tests green
- [x] No autobench imports in cell.py
- [x] BCK-04 lint clean (no os.getpid/os.kill/Popen/pid)
