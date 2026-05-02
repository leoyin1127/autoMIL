---
phase: "02"
plan: "02-04"
subsystem: backends
tags: [rename, re-export-shim, compat, PEP-562, BCK-02]
dependency_graph:
  requires: ["02-01"]
  provides: ["_orchestrator_daemon.py re-export shim", "orchestrator.py backward-compat shim"]
  affects: ["02-05 (LocalBackend imports from _orchestrator_daemon)"]
tech_stack:
  added: []
  patterns: ["PEP 562 __getattr__ shim", "importlib.reload transparency", "D-08 planned-migration promotion"]
key_files:
  created:
    - src/automil/orchestrator.py  # new shim (39 lines)
  modified:
    - src/automil/compat.py        # D-08 promotion: ExperimentOrchestrator entry removed from _PLANNED_MIGRATIONS
    - tests/test_compat.py         # assertion updated to reflect promoted entry
decisions:
  - "Shim includes importlib.reload(_orchestrator_daemon) on-reload to preserve shutil.which re-resolution for test_orchestrator_nvidia_smi.py"
  - "Star-import supplemented with explicit re-exports of private helpers so tests importing _parse_starttime_from_stat_line etc. keep working"
  - "test_compat.py updated (Rule 1) to assert Phase 2 entry NOT in _PLANNED_MIGRATIONS"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02T23:49:47Z"
  tasks_completed: 4
  files_modified: 3
---

# Phase 2 Plan 04: Rename `orchestrator.py` → `_orchestrator_daemon.py` + Re-export Shim Summary

**One-liner:** PEP 562 re-export shim at `automil.orchestrator` with reload-transparent forwarding to `_orchestrator_daemon`; 394/394 tests green; blame history preserved across 5 prior commits.

## What Was Done

### T-02-04-01: git mv rename
The `git mv` of `src/automil/orchestrator.py` → `src/automil/backends/_orchestrator_daemon.py` was already performed by Plan 02-02 in commit `4f667c9` (which ran in parallel in Wave 2 and landed first). This was not a collision — the rename is the intended outcome, and the git blame history is fully preserved.

**Blame preservation evidence (`git log --follow`):**
```
4f667c9 feat(backends): add BACKENDS registry + register decorator (BCK-01, D-68)
2967c4c fix(orchestrator): check pid + start_time for stale PID file detection (CLN-04)
b1e9462 fix(orchestrator): replace os.environ leak with explicit env whitelist (CLN-02)
0ed0111 fix(orchestrator): pin nvidia-smi path with shutil.which (CLN-05)
25ba5de fix(orchestrator): replace inline dotenv parser with python-dotenv (CLN-03)
```

### T-02-04-02: Re-export Shim at `src/automil/orchestrator.py`

Created a 39-line PEP 562 shim. Key design choices:

1. **Explicit re-exports** of all names needed by tests and CLI callers (including private helpers):
   - `ExperimentOrchestrator`, `NVIDIA_SMI_PATH`, `_SYSTEM_ENV_WHITELIST_LITERAL`, `_SYSTEM_ENV_WHITELIST_PREFIX`
   - `_parse_starttime_from_stat_line`, `_is_pid_alive_with_starttime`, `_read_proc_starttime`, `_write_pid_file`, `_load_pid_file`

2. **Star-import fallback** (`from automil.backends._orchestrator_daemon import *`) for any names not explicitly listed

3. **PEP 562 `__getattr__`** fires `DeprecationWarning` for any name accessed via attribute lookup (not in `__dict__` after the star-import). Warning message: `"automil.orchestrator.{name} moved to automil.backends._orchestrator_daemon in Phase 2 (D-60). Update imports by 2027-01."`

4. **Reload transparency** (deviation from plan template — see deviations): the shim calls `importlib.reload(sys.modules["automil.backends._orchestrator_daemon"])` when itself is reloaded. This preserves the behavior of `test_orchestrator_nvidia_smi.py::test_subprocess_uses_pinned_path` and `test_path_missing_fallback_warns`, which patch `shutil.which` and then call `importlib.reload(orch_mod)` expecting fresh `NVIDIA_SMI_PATH` resolution.

### T-02-04-03: compat.py migration table update

Per D-08 promotion rule:
- Added Phase 2 promotion comment in the Active aliases section noting `automil.orchestrator.ExperimentOrchestrator` → `automil.backends._orchestrator_daemon.ExperimentOrchestrator` (D-60)
- Removed `"automil.orchestrator.ExperimentOrchestrator"` entry from `_PLANNED_MIGRATIONS` dict
- Replaced it with a comment explaining the promotion

### T-02-04-04: Final verification

All checks passed:

| Check | Result |
|-------|--------|
| `uv run pytest tests/ -q` | 394/394 passed, 0 failed |
| `ExperimentOrchestrator.__module__` | `automil.backends._orchestrator_daemon` |
| Direct import from `_orchestrator_daemon` | OK |
| Caller-shim smoke (`cli.orchestrator.*`, `cli.check.*`) | OK |
| `git log --follow _orchestrator_daemon.py` | Shows 5 pre-rename commits |
| `git log orchestrator.py` | Shows only the new shim commit (9bc73aa) |

## Legitimate Caller Sites (Informational — ALL kept working via shim)

```
src/automil/cli/check.py:86    from automil.orchestrator import NVIDIA_SMI_PATH
src/automil/cli/check.py:97    from automil.orchestrator import (_SYSTEM_ENV_WHITELIST_LITERAL, _SYSTEM_ENV_WHITELIST_PREFIX)
src/automil/cli/orchestrator.py:19,29,39  from automil.orchestrator import ExperimentOrchestrator
tests/test_orchestrator_env_whitelist.py:17   from automil.orchestrator import ExperimentOrchestrator
tests/test_orchestrator_nvidia_smi.py:20      import automil.orchestrator as orch_mod
tests/test_orchestrator_pid_starttime.py:12,21,38,46,54,65,78,85,92  (multiple private helpers)
tests/test_orchestrator_dotenv.py:20          from automil.orchestrator import ExperimentOrchestrator
```

All 9 caller files (2 in `src/`, 4 in `tests/`) continue to resolve through the shim.

## Commit

| Hash | Description |
|------|-------------|
| `9bc73aa` | `refactor(backends): rename orchestrator.py -> _orchestrator_daemon.py + re-export shim (BCK-02, D-60)` |

Files in commit: `src/automil/orchestrator.py` (new shim), `src/automil/compat.py` (promotion), `tests/test_compat.py` (assertion update)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reload transparency for test_orchestrator_nvidia_smi.py**
- **Found during:** T-02-04-04 (test run)
- **Issue:** After writing the shim, `test_path_missing_fallback_warns` and `test_subprocess_uses_pinned_path` failed. The tests patch `shutil.which` and call `importlib.reload(orch_mod)` (where `orch_mod` = the shim). A bare star-import shim only re-runs the import statements — it does NOT re-trigger `_orchestrator_daemon`'s module-level `shutil.which("nvidia-smi")` call because `_orchestrator_daemon` stays cached in `sys.modules`.
- **Fix:** Added reload-chain logic to the shim: `if _daemon_name in sys.modules: importlib.reload(sys.modules[_daemon_name])`. This runs before the star-import, so `_orchestrator_daemon` re-resolves `NVIDIA_SMI_PATH` before the shim populates its `__dict__`.
- **Files modified:** `src/automil/orchestrator.py`
- **Outcome:** All 4 nvidia_smi tests pass; total 394/394 green.

**2. [Rule 1 - Bug] test_compat.py assertion needed update after D-08 promotion**
- **Found during:** T-02-04-04 (test run)
- **Issue:** `test_planned_migrations_has_expected_entries` asserted `len(_PLANNED_MIGRATIONS) >= 3` and `"automil.orchestrator.ExperimentOrchestrator" in _PLANNED_MIGRATIONS`. Both assertions fail after the D-08 promotion removes that entry — exactly what's supposed to happen per the plan.
- **Fix:** Updated test to assert the Phase 2 entry is NOT in `_PLANNED_MIGRATIONS` (it was promoted), lowered count floor to 2 (Phase 1 placeholder + Phase 3 agent assets), added comment explaining the promotion.
- **Files modified:** `tests/test_compat.py`
- **Outcome:** `test_compat.py` — all 4 tests pass.

**3. [Context - Plan 02-02 already did git mv]** Plan 02-02 (running in parallel in Wave 2) included the `git mv` of `orchestrator.py` → `_orchestrator_daemon.py` in its commit `4f667c9`. The `git mv` this plan attempted therefore operated on an untracked file and was discarded by git. The end state is identical — `_orchestrator_daemon.py` exists with full blame history. This plan's commit covers only the 3 files that Plan 02-04 uniquely owns.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The shim is a pure Python module re-export — no new I/O surface.

## Known Stubs

None. All re-exports wire directly to real implementations in `_orchestrator_daemon.py`.

## Self-Check: PASSED

- `src/automil/orchestrator.py` exists: FOUND
- `src/automil/backends/_orchestrator_daemon.py` exists: FOUND
- `src/automil/compat.py` updated: FOUND
- Commit `9bc73aa` exists: FOUND
- 394/394 tests green: CONFIRMED
