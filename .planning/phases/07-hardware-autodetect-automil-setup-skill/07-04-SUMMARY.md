---
phase: 07-hardware-autodetect-automil-setup-skill
plan: 04
subsystem: backends
tags: [backends, healthcheck, slurm, ray, mock-slurm, deferred-contract, TDD]
dependency_graph:
  requires: [07-01, 07-03]
  provides: [SLURMBackend.healthcheck, RayBackend.healthcheck, MockSLURMBackend.healthcheck]
  affects: [tests/backends/test_contract.py, Backend ABC contract gate]
tech_stack:
  added: []
  patterns: [NotImplementedError deferred stub, pytest.importorskip skip pattern]
key_files:
  created:
    - tests/backends/test_distributed_healthcheck_deferred.py
  modified:
    - src/automil/backends/slurm.py
    - src/automil/backends/ray.py
    - src/automil/backends/mock_slurm.py
decisions:
  - "Used raw string r'healthcheck deferred to Phase 7\\+ for distributed backends' as pytest.raises match pattern to escape the '+' regex quantifier"
metrics:
  duration: ~4 minutes
  completed: 2026-05-07
---

# Phase 7 Plan 04: Distributed Backend Healthcheck Stubs Summary

Added `NotImplementedError` healthcheck stubs to `SLURMBackend`, `RayBackend`, and `MockSLURMBackend`, closing the abstract-method contract gate opened by 07-01 for all three distributed backends.

## What Was Built

**Three backend stub additions (Task 1)**

Each of `slurm.py`, `ray.py`, and `mock_slurm.py` received:
- An explicit `HealthReport` import added to the existing `from automil.backends.base import ...` line
- A `healthcheck()` method raising `NotImplementedError` with the D-189 locked message verbatim:
  `"healthcheck deferred to Phase 7+ for distributed backends (use \`salloc\`/\`ray status\` directly)"`

Byte-identical message across all three files confirmed via `grep -c`:
- `src/automil/backends/slurm.py`: 1 match
- `src/automil/backends/ray.py`: 1 match
- `src/automil/backends/mock_slurm.py`: 1 match

**Deferred-contract test file (Task 2)**

Created `tests/backends/test_distributed_healthcheck_deferred.py` with 3 tests:
- `test_mock_slurm_healthcheck_raises_notimplemented`: always runs; asserts the locked message
- `test_slurm_healthcheck_raises_notimplemented`: skips via `pytest.importorskip("submitit")` when extras absent
- `test_ray_healthcheck_raises_notimplemented`: skips via `pytest.importorskip("ray")` when extras absent

Results: 1 passed, 2 skipped (submitit and ray not installed in this environment).

## Verification Results

- `LocalBackend()` and `MockSLURMBackend()` instantiate cleanly (no abstract-method TypeError)
- Phase 6 parametrised contract suite `tests/backends/test_contract.py`: 21 passed, 40 skipped (no regressions)
- Em-dash gate: zero new em-dashes in any modified file
- Autobench/framework purity: zero `autobench|AUTOBENCH_|benchmarks/` refs in modified files
- BCK-04 lint: no new `os.kill|os.killpg|Popen|.pid` calls added

## Deviations from Plan

**1. [Rule 1 - Bug] Escaped '+' in pytest regex match pattern**
- **Found during:** Task 2 test execution
- **Issue:** The match pattern `"healthcheck deferred to Phase 7+ for distributed backends"` fails because `+` is a regex quantifier (one-or-more of the preceding `7`), causing `pytest.raises(match=...)` to not match the actual error message
- **Fix:** Changed to raw string `r"healthcheck deferred to Phase 7\+ for distributed backends"` so `+` is treated as a literal character
- **Files modified:** `tests/backends/test_distributed_healthcheck_deferred.py`
- **Commit:** 7f204e2

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add healthcheck stubs to SLURM/Ray/MockSLURM | b5b971b | slurm.py, ray.py, mock_slurm.py |
| 2 | Add deferred-contract test file | 7f204e2 | test_distributed_healthcheck_deferred.py |

## Self-Check: PASSED

- [x] `src/automil/backends/slurm.py` exists and contains healthcheck stub
- [x] `src/automil/backends/ray.py` exists and contains healthcheck stub
- [x] `src/automil/backends/mock_slurm.py` exists and contains healthcheck stub
- [x] `tests/backends/test_distributed_healthcheck_deferred.py` exists with 3 tests
- [x] Commits b5b971b and 7f204e2 exist in git log
- [x] Phase 6 contract tests green (21 passed, 40 skipped)
