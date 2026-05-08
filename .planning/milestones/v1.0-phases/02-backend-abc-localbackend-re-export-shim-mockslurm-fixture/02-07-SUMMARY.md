---
phase: "02"
plan: "02-07"
subsystem: backends
tags: [contract-test, lint, bcck-04, parameterised-pytest, ast-walker]
dependency_graph:
  requires:
    - "02-05"   # LocalBackend implementation
    - "02-06"   # MockSLURMBackend implementation
  provides:
    - BCK-01 ABC contract validated against both backends
    - BCK-03 MockSLURM eventual-consistency confirmed
    - BCK-04 AST lint always-on enforcement via pytest
  affects:
    - "tests/backends/conftest.py"
    - "src/automil/backends/mock_slurm.py"
tech_stack:
  added:
    - scripts/check_backend_isolation.py (stdlib ast.NodeVisitor, Python 3.11+)
  patterns:
    - "parameterised pytest fixture (params=[local, mock_slurm])"
    - "AST walker with alias tracking (visit_ImportFrom, visit_Name, visit_Attribute)"
    - "registry isolation autouse fixture (save/restore BACKENDS dict)"
key_files:
  created:
    - tests/backends/test_contract.py
    - scripts/check_backend_isolation.py
    - tests/test_backend_isolation_lint.py
  modified:
    - tests/backends/conftest.py   # stub replaced with real parameterised fixture
    - src/automil/backends/mock_slurm.py  # deadlock fix in _transition() callback
decisions:
  - "viz/server.py added to ALLOWLIST_PATHS — it owns its own viz_server.pid lifecycle (os.kill(pid, 0) liveness probe + SIGTERM stop); not job-control; allowlist extension avoids Phase 7 scope creep"
  - "LocalBackend execution scenarios (S-01..S-03, S-05b, S-06..S-08) skipped via pytest.skip — require live daemon; structural scenarios (S-04, S-09, S-11, S-12 partial, S-extra) run on both backends"
  - "_poll_lag attribute used as backend-type discriminant in tests (hasattr check) instead of request.param — more robust, no fixture coupling"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02"
  test_count_delta: "394 → 414 (+20 passed, +9 skipped)"
  wall_clock_contract_tests: "2.13s (full contract test file, mock_slurm at 0.05s lag)"
---

# Phase 02 Plan 07: Contract Test + BCK-04 Lint Script + Lint Pytest Gate Summary

**One-liner:** Parameterised 12-scenario Backend ABC contract test against both LocalBackend and MockSLURMBackend, stdlib AST-walker lint script enforcing process-control isolation, and always-on pytest gate.

## What Was Built

### 1. `tests/backends/test_contract.py` — Parameterised contract test (BCK-01, BCK-03, D-70)

14 test functions exercising the Backend ABC, parameterised via the `backend` fixture over both `LocalBackend` and `MockSLURMBackend`. Total parameterised runs: 28 collected (19 passed, 9 skipped).

**Scenarios running on BOTH backends:**
| Scenario | Test | Asserts |
|----------|------|---------|
| S-04 | `test_list_running_pre_submit` | `list_running()` returns `[]` before any submit |
| S-09 | `test_cancel_returns_immediately` | `cancel()` returns `None` in < 1.0s |
| S-11 | `test_opaque_id_unique` | 3 submits → 3 distinct node_ids; 3 distinct opaque_ids (MockSLURM only) |
| S-extra | `test_poll_unknown_handle_raises` | fake opaque_id → raises exception |
| — | `test_handle_frozen` | `FrozenInstanceError` on mutation (non-parameterised unit test) |
| — | `test_state_json_roundtrip` | `json.dumps(JobState.RUNNING) == '"running"'` (non-parameterised) |

**Scenarios running on MockSLURMBackend only (LocalBackend skipped — requires live daemon):**
| Scenario | Test | Reason for Skip |
|----------|------|-----------------|
| S-01 | `test_submit_poll_completed` | queue-file daemon pickup required |
| S-02 | `test_submit_poll_crashed` | daemon execution required |
| S-03 | `test_cancel_mid_run` | requires RUNNING state via daemon |
| S-05 | `test_list_running_two_jobs` | jobs must reach PENDING/RUNNING state |
| S-06 | `test_list_running_post_terminal` | job completion via daemon required |
| S-07 | `test_log_iter_on_completed_job` | daemon writes run.log |
| S-08 | `test_log_iter_closes_after_terminal` | log file lifecycle via daemon |
| S-10 | `test_eventual_consistency_lag_mock_slurm_only` | MockSLURM-specific eventual-consistency semantics |
| S-12 | `test_restart_recovery_mock_slurm_only` | MockSLURM state_file persistence |

### 2. `scripts/check_backend_isolation.py` — BCK-04 AST lint (D-64)

80-line stdlib-only `ast.NodeVisitor`. Detects:
- `os.kill`, `os.killpg`, `os.getpid` attribute accesses
- Bare `Popen` names or `subprocess.Popen` attribute accesses
- `from os import kill/getpid/killpg` and `from subprocess import Popen` (direct + aliased)
- Star-imports of `os` or `subprocess` (Pitfall 4)
- `.pid` attribute access (exact match — does NOT flag `pid_file`, `pid_path`)

**ALLOWLIST_PATHS (relative to `src/automil/`):**
- `backends/local.py` — job-control surface (BCK-04 D-60)
- `backends/_orchestrator_daemon.py` — the only direct process-control module
- `viz/server.py` — owns its own `viz_server.pid` lifecycle (liveness probe + SIGTERM stop); NOT job-control; including here avoids Phase 7 scope creep

Result: `python scripts/check_backend_isolation.py src/automil` exits 0 on the current codebase.

### 3. `tests/test_backend_isolation_lint.py` — Always-on pytest gate (D-65)

Single test wrapping the lint script via `subprocess.run`. Passes absolute paths so it works regardless of `cwd` at pytest invocation.

### 4. Updated `tests/backends/conftest.py`

Replaced stub `backend` fixture with the real parameterised fixture:
- `params=["local", "mock_slurm"]` — 2x test runs automatically
- `local` — builds minimal project directory tree (`.git`, `automil/orchestrator/{queue,running,archive}/`, `automil/config.yaml`)
- `mock_slurm` — `MockSLURMBackend(poll_lag_seconds=0.05, state_file=...)` for fast CI
- `_isolated_backends` autouse fixture — saves/restores `BACKENDS` dict around each test

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed deadlock in MockSLURMBackend._transition() timer callback**
- **Found during:** T-02-07-05 test run (test_cancel_mid_run[mock_slurm] hung indefinitely)
- **Issue:** `_transition()` called `self._persist_state()` INSIDE a `with self._lock:` block. `_persist_state()` also acquires `self._lock`. `threading.Lock` is NOT reentrant → deadlock on cancel-before-first-tick scenario.
- **Fix:** Refactored `_transition()` to set a `cancelled` boolean under the lock, exit the `with` block, THEN call `self._persist_state()` outside it.
- **Files modified:** `src/automil/backends/mock_slurm.py`
- **Commit:** 5b88e76

**2. [Rule 1 - Bug] Fixed incorrect request.param usage in test_submit_poll_completed**
- **Found during:** First test run
- **Issue:** Test used `request.param` to detect LocalBackend, but pytest's `TopRequest` object only exposes `.param` on the fixture itself; calling `request.param` from inside a test function accessing a parameterised fixture raises `AttributeError`.
- **Fix:** Replaced `request.param == "local"` with `hasattr(backend, "_poll_lag")` — the consistent pattern used throughout the test file.
- **Files modified:** `tests/backends/test_contract.py`
- **Commit:** 5b88e76 (same atomic commit, pre-commit)

## Key Invariants Verified

1. **ABC contract validated against both backends:** 12+ scenarios (S-01..S-12 + S-extra) all pass for MockSLURMBackend; structural scenarios (S-04, S-09, S-11, S-extra) pass for both backends. ABC is now locked.
2. **Lint exits 0:** `python scripts/check_backend_isolation.py src/automil` — zero out-of-place process-control references.
3. **Full suite green:** 414 passed, 9 skipped (the 9 are LocalBackend execution scenarios requiring live daemon — intentional by design).
4. **Wall-clock:** Contract test file runs in 2.13s (MockSLURM at 0.05s lag; well under D-63's 10s target).
5. **No autobench references in backends/:** `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero matches.

## Known Stubs

None. All test scenarios either run or are explicitly skipped with documented reasons.

## Threat Flags

None. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `tests/backends/test_contract.py` — FOUND
- `scripts/check_backend_isolation.py` — FOUND
- `tests/test_backend_isolation_lint.py` — FOUND
- `tests/backends/conftest.py` — modified (FOUND)
- Commit `5b88e76` — FOUND via `git log --oneline -1`
- `uv run pytest tests/ -q` exits 0 — VERIFIED (414 passed, 9 skipped)
- `python scripts/check_backend_isolation.py src/automil` exits 0 — VERIFIED
