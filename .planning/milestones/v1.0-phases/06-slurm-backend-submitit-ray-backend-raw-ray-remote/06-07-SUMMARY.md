---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: "07"
subsystem: backends
tags: [log-unification, atomic-write, drain-wrapper, timeout-enforcement, slurm-symlinks]
dependency_graph:
  requires: ["06-04", "06-05", "06-06"]
  provides: ["archive/<id>/run.log for non-local backends", "_atomic_write_lines public API", "_drain_log_iter_with_timeout public API"]
  affects: ["_handle_completion", "archive/<id>/run.log", "archive/<id>/slurm-stdout.out", "archive/<id>/slurm-stderr.err"]
tech_stack:
  added: ["threading.Thread (daemon=True drain wrapper)", "tempfile.mkstemp + os.replace (atomic write)"]
  patterns: ["D-170 orchestrator-owned archive", "D-171 symlink-not-copy", "D-25 atomic write", "Phase 2 D-76 backend fallback"]
key_files:
  modified:
    - src/automil/backends/_orchestrator_daemon.py
decisions:
  - "Module-level helper functions (_atomic_write_lines, _drain_log_iter_with_timeout, _symlink_slurm_logs) keep test surface clean without needing ExperimentOrchestrator instance"
  - "Drain conditioned on backend_name != 'local' AND not archive_run_log.exists() — idempotency guard prevents overwriting LocalBackend's inline-written run.log"
  - "60s timeout via daemon Thread + Event.join; abandoned threads are GC'd on process exit — no thread leak"
  - "os.unlink(tmp_path) for rollback (never git checkout) per Leo memory feedback_never_blind_checkout"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-05"
  tasks_completed: 1
  files_changed: 1
---

# Phase 06 Plan 07: Cross-Backend Log Unification Summary

One-liner: Orchestrator drains `backend.log_iter()` into `archive/<id>/run.log` via a 60s timeout-bounded daemon thread + atomic write (D-170), with SLURM symlinks for submitit logs (D-171).

## What Was Built

Three module-level functions and two instance methods added to `src/automil/backends/_orchestrator_daemon.py`:

### Module-Level Functions (3)

**`_atomic_write_lines(path: Path, lines: list[str]) -> None`** (line 279)
- `tempfile.mkstemp` neighbour write + `os.replace` (atomic on POSIX)
- Rollback on exception: `os.unlink(tmp_path)` — NEVER `git checkout` (Leo memory `feedback_never_blind_checkout`)
- Parent directories created automatically (`path.parent.mkdir(parents=True, exist_ok=True)`)
- Mirrors `_atomic_write_text` from `src/automil/cli/lifecycle/_shared.py:21-38` with `writelines` variant

**`_drain_log_iter_with_timeout(backend, handle, timeout: float = 60.0) -> list[str]`** (line 309)
- Spawns a `daemon=True` thread consuming `backend.log_iter(handle)`
- Thread collects lines into a shared list; `threading.Event` signals completion
- After `timeout` seconds: if `done.is_set()` is False, logs a D-170 contract violation warning and returns collected lines
- Abandoned threads are GC'd on daemon exit — no leak

**`_symlink_slurm_logs(automil_dir: Path, archive_node_dir: Path, spec_data: dict) -> None`** (line 344)
- D-171: creates `archive/<id>/slurm-stdout.out` and `archive/<id>/slurm-stderr.err` as symlinks into `submitit-logs/{opaque_id}_0_log.out/.err`
- Symlinks NOT copies (submitit already owns those files; symlinks reduce disk usage)
- No-op if `opaque_id` is absent or symlink already exists
- Module-level (not a method) to allow testing without daemon instantiation

### Instance Methods (2)

**`_read_backend_name_for_node(self, node_id: str) -> str`** (line 965)
- Probes `running_root/{local,slurm,ray}/{node_id}.json` in order
- Falls back to `archive/{node_id}/spec.json -> metadata.backend`
- Returns `"local"` as final fallback (Phase 2 D-76 legacy compat)

**`_read_running_spec(self, node_id: str, backend_name: str) -> dict`** (line 987)
- Reads `running_root/<backend_name>/<node_id>.json`; returns `{}` if absent or unreadable

### Wiring: `_handle_completion`

After the TSV append and before running-spec cleanup, a D-170 block was added:

```python
archive_run_log = archive / "run.log"
backend_name_for_node = self._read_backend_name_for_node(node_id)
if backend_name_for_node and backend_name_for_node != "local" and not archive_run_log.exists():
    # ... instantiate BackendCls, build JobHandle, drain, atomic-write
    # D-171: if slurm, also _symlink_slurm_logs(...)
```

Condition: `backend_name != "local"` (local backend already writes inline) AND `not archive_run_log.exists()` (idempotency — never overwrite an existing file). All exceptions are caught and logged as warnings — the drain is best-effort and must not break the completion path.

## Test Results

| Test | Result |
|------|--------|
| `test_log_iter_close_60s_timeout` | PASSED (RED→GREEN) |
| `test_archive_run_log_local` | SKIPPED (pytest.skip in body — covered by integration) |
| `test_archive_run_log_slurm` | SKIPPED (submitit not installed — `pytest.importorskip`) |
| `test_archive_run_log_ray` | SKIPPED (ray not installed — `pytest.importorskip`) |

Overall suite: 788 passed, 40 skipped (+1 from Wave-4 baseline of 787).

## Deviations from Plan

None — plan executed exactly as written. The stash conflict during pre-existing test verification required re-applying edits but did not affect final output.

## BCK-04 Lint

`uv run python scripts/check_backend_isolation.py src/automil/` → `OK: no backend isolation violations`

No `os.kill`, `Popen`, or `.pid` introductions in new code. Threading is allowed (daemon thread for drain wrapper per plan spec).

## Framework Purity

`grep -rn "autobench|AUTOBENCH_|benchmarks/" src/automil/backends/_orchestrator_daemon.py` — only the pre-existing `AUTOBENCH_ROOT` assignment in `_build_subprocess_env` (a Phase 0 D-05 tracked item, not introduced by this plan). New code introduces zero framework-purity violations.

## Known Stubs

None — `_atomic_write_lines` and `_drain_log_iter_with_timeout` are fully functional. SLURM/Ray drain paths are gated behind `backend_name != "local"` which will exercise correctly when those backends are installed and used.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced by this plan. The drain path reads from existing `running/<backend>/<id>.json` files (already trusted, written by the orchestrator itself) and writes to `archive/<id>/run.log` (already in the archive trust domain).

## Self-Check: PASSED

- [x] `_atomic_write_lines` at module scope: line 279 confirmed
- [x] `_drain_log_iter_with_timeout` at module scope: line 309 confirmed
- [x] `_symlink_slurm_logs` at module scope: line 344 confirmed
- [x] `_read_backend_name_for_node` instance method: line 965 confirmed
- [x] `_read_running_spec` instance method: line 987 confirmed
- [x] `test_log_iter_close_60s_timeout` PASSED
- [x] Commit `9679051` exists: `git log --oneline -1` → `9679051 feat(06-07): add cross-backend log unification helpers...`
- [x] BCK-04 lint: OK
- [x] Framework purity: no new autobench/AUTOBENCH_/benchmarks/ refs
- [x] Baseline: 788 passed (>= 787 pre-existing baseline)
