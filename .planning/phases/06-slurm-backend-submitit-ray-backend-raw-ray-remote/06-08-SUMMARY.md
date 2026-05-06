---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: "08"
subsystem: backends/test-contract
tags: [test, BCK-05, BCK-06, contract-test, parametrisation]
dependency_graph:
  requires: [06-01, 06-04, 06-05, 06-06]
  provides: [D-179-clause-1-gate]
  affects: [tests/backends/test_contract.py]
tech_stack:
  added: []
  patterns:
    - "isinstance(backend, LocalBackend) skip guard replaces hasattr(backend, '_poll_lag')"
    - "pytest.importorskip in conftest handles missing slurm/ray extras cleanly"
    - "Non-parameterised SLURM/Ray-specific tests (importorskip at top of each)"
key_files:
  created: []
  modified:
    - tests/backends/test_contract.py
decisions:
  - "S-10 and S-12 retain hasattr guard: these are semantically MockSLURM-only scenarios (eventual-consistency lag, state_file restart). SLURM/Ray don't have a poll_lag attribute and these scenarios test MockSLURM-specific invariants."
  - "S-11 opaque_id uniqueness broadened from hasattr to not isinstance so SLURMBackend and RayBackend unique-ID contracts are also verified."
  - "Three new non-parameterised tests (test_slurm_signal_directive_set, test_slurm_state_map_covers_phase4_terminal_states, test_ray_poll_catches_worker_crashed_error) added at file end; each gates on pytest.importorskip."
metrics:
  duration: "~5 minutes"
  completed: "2026-05-06"
  tasks_completed: 1
  files_modified: 1
---

# Phase 6 Plan 08: Contract Test Extension — 4-Backend Parametrisation Summary

**One-liner:** Skip-guard refactor from `hasattr(backend, "_poll_lag")` to `isinstance(backend, LocalBackend)` extends contract test reach from 2 to 4 backends, adding BCK-05/BCK-06 SLURM/Ray-specific verification tests.

## What Was Done

`tests/backends/test_contract.py` was the only file modified. The conftest fixture from plan 06-01 already parametrises the `backend` fixture over `["local", "mock_slurm", "slurm", "ray"]`. The contract test's scenario skip logic used `hasattr(backend, "_poll_lag")` to detect MockSLURM (the only backend with that attribute), skipping scenarios requiring a live dispatcher. This pattern blocked SLURMBackend and RayBackend from running those same scenarios.

### Changes Made

**Skip-guard refactor (8 sites: S-01 through S-08):**

| Scenario | Old guard | New guard |
|----------|-----------|-----------|
| S-01 submit->COMPLETED | `not hasattr(backend, "_poll_lag")` | `isinstance(backend, LocalBackend)` |
| S-02 submit->CRASHED | same | same |
| S-03 cancel->CANCELLED | same | same |
| S-05 list_running two jobs | same | same |
| S-06 list_running post-terminal | same | same |
| S-07 log_iter >=1 line | same | same |
| S-08 log_iter closes | same | same |

S-10 (eventual-consistency lag) and S-12 (state_file restart) retain `hasattr` — both are semantically MockSLURM-only tests verifying MockSLURM-specific invariants.

**S-01 backend assertion broadened:**
- Before: `assert handle.backend == "mock_slurm"`
- After: `assert handle.backend in {"mock_slurm", "slurm", "ray"}`

**S-11 opaque_id uniqueness broadened:**
- Before: `if hasattr(backend, "_poll_lag"):` (MockSLURM only)
- After: `if not isinstance(backend, LocalBackend):` (all dispatching backends)

**LocalBackend import added:**
```python
from automil.backends.local import LocalBackend
```

**Three new non-parameterised BCK-05/BCK-06 tests added:**
1. `test_slurm_signal_directive_set` — verifies `signal=B:TERM@30` is wired into SLURMBackend executor parameters (D-155 / RESEARCH.md OQ-1). Skips if submitit absent.
2. `test_slurm_state_map_covers_phase4_terminal_states` — verifies `_SLURM_STATE_MAP` maps TIMEOUT->BUDGET_KILLED, FAILED->CRASHED, CANCELLED->CANCELLED, COMPLETED->COMPLETED (D-157). Skips if submitit absent.
3. `test_ray_poll_catches_worker_crashed_error` — verifies `RayBackend.poll` source contains `WorkerCrashedError`, `TaskCancelledError`, `RayTaskError` (RESEARCH.md OQ-3 / D-164). Skips if ray absent.

## Test Results

```
57 collected test rows
19 passed, 38 skipped (submitit and ray extras not installed in this environment)
```

When submitit + ray are installed, the effective count grows:
- 12 scenarios × 3 dispatch-capable backends (mock_slurm, slurm, ray) = ~36 execution rows
- Plus S-04, S-09, S-11, S-extra on all 4 backends = additional pass rows
- Plus 3 new non-parametrised tests = 3 more rows
- Total: 57 rows; >=30 PASSED expected with extras installed

## Baseline Verification

Full suite: `788 passed, 43 skipped, 3 failed` — identical pre-existing tick_cells failures, no regression introduced.

## Deviations from Plan

None — plan executed exactly as written. The only implementation note: the Write tool was used instead of Edit due to a tooling issue where Edit changes were silently reverted between application and git staging. Final file state is correct.

## Self-Check: PASSED

- `tests/backends/test_contract.py` exists: FOUND
- `isinstance(backend, LocalBackend)` appears 9 times in file: FOUND
- Commit `1afbc4b` exists: FOUND
