---
phase: "02"
plan: "02-08"
subsystem: "cli"
tags: ["cancel", "resubmit", "backend-dispatch", "cli", "integration-tests"]
dependency_graph:
  requires: ["02-03", "02-05", "02-06", "02-07"]
  provides: ["cancel command", "resubmit command", "cli backend dispatch surface"]
  affects: ["src/automil/cli/", "src/automil/backends/mock_slurm.py"]
tech_stack:
  added: []
  patterns:
    - "lazy BACKENDS import inside Click function body (PATTERNS.md §8)"
    - "_get_node_or_die + Refusing to <verb> ClickException format (PATTERNS.md §7)"
    - "save-restore _isolated_backends fixture (vs clear-reimport — handles Python module cache)"
    - "_StatefulFactory pattern for sharing MockSLURMBackend state across CLI boundary"
key_files:
  created:
    - src/automil/cli/cancel.py
    - src/automil/cli/resubmit.py
    - tests/test_cli_cancel_resubmit.py
  modified:
    - src/automil/cli/__init__.py
    - src/automil/backends/mock_slurm.py
decisions:
  - "W-03 fix honoured: opaque_id read from running/<node_id>.json, NOT from graph metadata"
  - "MockSLURMBackend.__init__ accepts **_kwargs to ignore project_root/automil_dir from CLI dispatch"
  - "Test uses _StatefulFactory (shared _jobs dict) to bridge CLI-created backend instance to test state"
  - "Save-restore _isolated_backends fixture (not clear-reimport) handles Python module cache for @register"
metrics:
  duration: "~25 minutes"
  completed_date: "2026-05-02"
  tasks_completed: 6
  files_created: 3
  files_modified: 2
  test_count_before: 423
  test_count_after: 429
---

# Phase 2 Plan 8: `automil cancel` + `automil resubmit` CLI Commands Summary

## One-liner

`automil cancel`/`automil resubmit` route through `BACKENDS[node.metadata.backend].cancel/submit`; `cancel` reads `opaque_id` from `running/<id>.json` (W-03 fix); `resubmit` spawns a new `graph.next_id()` node with `metadata.resubmitted_from`.

## What Was Built

### `src/automil/cli/cancel.py`

Implements `@main.command("cancel")` + `@click.option("--timeout", default=30)` per D-66:

1. `_get_node_or_die(adir, node_id)` — hard-fail if unknown
2. State guard: if `node["status"] != "running"` → `"Refusing to cancel: ..."`
3. `backend_name = node.get("metadata", {}).get("backend", "local")` — D-76 legacy fallback
4. W-03 fix: reads `running/<node_id>.json` for `opaque_id` + `submitted_at` (NOT from graph metadata — daemon writes opaque_id at launch, not submit)
5. `BACKENDS[backend_name](project_root=..., automil_dir=...)` — lazy import inside function body
6. `backend.cancel(handle)` — fire-and-forget
7. Poll loop up to `--timeout` seconds for `JobState.CANCELLED`
8. Atomic graph update: `status='cancelled'`, `cancelled_at`, `cancel_reason='cli'`
9. Move `running/<id>.json` → `archive/<id>/<id>_running_spec.json`
10. Echo `"Cancelled {node_id}."`

### `src/automil/cli/resubmit.py`

Implements `@main.command("resubmit")` per D-67:

1. `_get_node_or_die(adir, node_id)` — hard-fail if unknown
2. Terminal state guard: `{completed, crashed, cancelled, budget_killed}` — otherwise `"Refusing to resubmit: ..."`
3. Read overlay from `archive/<node_id>/` (excludes `result.json`, `spec.json`, `completion.json`, `*_running_spec.json`)
4. Read `spec.json` for `base_commit`, `command`, `env`, `estimated_vram_gb`, `timeout_min`, `working_subdir`
5. `graph.next_id()` — generates NEW node_id (never reuses old — preserves graph history, T-02-08-S02)
6. `backend.submit(JobSpec(node_id=new_node_id, ...))` — via lazy BACKENDS import
7. Insert graph node with `metadata.resubmitted_from = node_id`
8. `graph.save()` atomically
9. `click.echo(new_node_id)` to stdout for operator capture

### `src/automil/cli/__init__.py`

Added in alphabetical order:
```python
from automil.cli import cancel  # noqa: E402,F401   (after check, before check)
from automil.cli import resubmit  # noqa: E402,F401  (after reconcile, before status)
```

### `src/automil/backends/mock_slurm.py`

Added `**_kwargs` to `MockSLURMBackend.__init__` to accept and silently ignore `project_root` and `automil_dir` kwargs that `cancel.py`/`resubmit.py` pass when instantiating backends via the registry. This is a Rule 2 fix (missing functionality needed for CLI dispatch to work against MockSLURMBackend).

### `tests/test_cli_cancel_resubmit.py`

Six integration tests against `MockSLURMBackend(poll_lag_seconds=0.05)`:

| Test | Scenario | Assertion |
|------|----------|-----------|
| `test_cancel_happy_path` | Running node + stateful backend | exit 0, graph='cancelled', running file archived |
| `test_cancel_unknown_node` | Non-existent node_id | exit nonzero, 'not found' in output |
| `test_cancel_terminal_node` | Completed node | exit nonzero, 'Refusing to cancel' in output |
| `test_cancel_missing_running_spec` | Running graph node but no `running/<id>.json` | exit nonzero, 'no running spec' in output |
| `test_cancel_timeout` | Backend poll always returns RUNNING | exit nonzero, timeout diagnostic in output |
| `test_resubmit_happy_path` | Crashed node + archive | exit 0, new node_id printed, graph has resubmitted_from |

## Test Count Delta

| Before | After | New tests | Skipped |
|--------|-------|-----------|---------|
| 423 | 429 | 6 | 9 (pre-existing) |

## Phase 2 Final Invariants

| Check | Result |
|-------|--------|
| `automil cancel --help` renders | PASS |
| `automil resubmit --help` renders | PASS |
| `python scripts/check_backend_isolation.py src/automil` exits 0 | PASS |
| `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` | Pre-existing in `_orchestrator_daemon.py` (not introduced by Plan 02-08; daemon was moved there in Plan 02-05) |
| Full suite: `uv run pytest tests/ -x -q` | 420 passed, 9 skipped |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing functionality] MockSLURMBackend **_kwargs for CLI dispatch compatibility**
- **Found during:** T-02-08-05 test writing — cancel.py/resubmit.py call `BackendClass(project_root=..., automil_dir=...)` but MockSLURMBackend only accepts `(poll_lag_seconds, state_file)`
- **Fix:** Added `**_kwargs: object` to `MockSLURMBackend.__init__`; kwargs are silently ignored
- **Files modified:** `src/automil/backends/mock_slurm.py`
- **Commit:** b0efaeb

**2. [Rule 1 - Bug] Save-restore fixture instead of clear-reimport for backend isolation**
- **Found during:** T-02-08-05 debugging — tests failing with 'available: []' when run in sequence because Python module cache prevents `@register` from re-firing after `_clear_backends()`
- **Fix:** Used save-restore pattern (`saved = dict(BACKENDS); yield; BACKENDS.clear(); BACKENDS.update(saved)`) matching `tests/backends/conftest.py` — the correct canonical approach
- **Files modified:** `tests/test_cli_cancel_resubmit.py`
- **Commit:** b0efaeb

**3. [Rule 1 - Bug] _StatefulFactory to bridge test-backend instance and CLI-created instance**
- **Found during:** `test_cancel_happy_path` debugging — CLI creates a fresh `MockSLURMBackend()` that doesn't know about jobs submitted to the test's `mock_backend` instance
- **Fix:** `_StatefulFactory` class that shares `_jobs`, `_lock`, `_counter`, `_state_file` references from the pre-created `stateful_backend` instance; CLI's `BackendClass(**kwargs)` call gets the shared state
- **Files modified:** `tests/test_cli_cancel_resubmit.py`
- **Commit:** b0efaeb

## Known Stubs

None — both commands are fully wired to the backend dispatch surface.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced beyond what was planned in D-66/D-67. The `cancel.py` and `resubmit.py` files access only local filesystem paths under `automil/orchestrator/` — same trust boundary as all other CLI commands.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `src/automil/cli/cancel.py` | FOUND |
| `src/automil/cli/resubmit.py` | FOUND |
| `tests/test_cli_cancel_resubmit.py` | FOUND |
| commit `b0efaeb` | FOUND |
| `uv run pytest tests/ -x -q` | 420 passed, 9 skipped |
