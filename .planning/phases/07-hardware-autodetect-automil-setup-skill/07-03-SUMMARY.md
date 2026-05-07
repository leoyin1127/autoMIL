---
phase: 07-hardware-autodetect-automil-setup-skill
plan: "03"
subsystem: backends
tags: [healthcheck, cuda, rocm, cpu-fallback, unit-tests, D-189, D-190, D-198, STP-01, STP-03]
dependency_graph:
  requires: [07-01]
  provides: [LocalBackend.healthcheck implementation, D-198 clause-1 tests]
  affects: [src/automil/backends/local.py, tests/backends/test_local_healthcheck.py]
tech_stack:
  added: []
  patterns: [subprocess.run mock pattern, lazy-import inside method, NVIDIA_SMI_PATH constant reuse]
key_files:
  created: [tests/backends/test_local_healthcheck.py]
  modified: [src/automil/backends/local.py]
decisions:
  - "_healthcheck_cuda lazily imports NVIDIA_SMI_PATH inside the method body to keep the module-level import graph acyclic (matching existing __init__ pattern)"
  - "_healthcheck_rocm exception handler returns None instead of partial tuple on format failure (any exception is best-effort; clean fallback)"
  - "MIG probe failure is silently ignored since MIG is disabled on Leo's workstation and the warning is advisory-only"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-07T22:29:43Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 7 Plan 03: LocalBackend.healthcheck Implementation Summary

Implements `LocalBackend.healthcheck()` per D-190 probe order and ships the 6 D-198 clause-1 unit tests: CUDA probe via path-pinned NVIDIA_SMI_PATH, ROCm best-effort fallback, CPU terminal fallback with 'failed' status when CUDA_VISIBLE_DEVICES is set.

## Test Outcomes

All 6 tests pass: `uv run pytest tests/backends/test_local_healthcheck.py -v` reports 6 passed in 0.07s.

| Test | D-198 Clause | Status |
|------|-------------|--------|
| test_healthcheck_cuda_3_gpu_happy_path | 1.1 | PASS |
| test_healthcheck_cuda_no_gpus_falls_through_to_cpu | 1.2 | PASS |
| test_healthcheck_rocm_fallback | 1.3 | PASS |
| test_healthcheck_cpu_only | 1.4 | PASS |
| test_healthcheck_partial_detection | 1.5 | PASS |
| test_healthcheck_full_failure_prompts_override | 1.6 | PASS |

## Actual GPU/VRAM on Leo's Workstation

```
HealthReport(
  gpu_count=3,
  gpu_vram_gb=(47.98828125, 47.98828125, 47.98828125),
  accelerator='cuda',
  python_version='3.11.13',
  automil_version='0.1.0',
  detection_status='ok',
  detection_warnings=(),
  detected_at=datetime.datetime(2026, 5, 7, 22, 29, 35, ...)
)
```

3 GPUs, ~48 GB VRAM each (48 GB cards, memory.total=49140 MiB / 1024 = 47.99 GB). No MIG mode active, no partial-status warnings.

## BCK-04 Lint Count

- Before plan: 1 reference (`os.kill | Popen | .pid` in pre-existing module docstring)
- After plan: 1 reference (unchanged)
- New healthcheck code uses only `subprocess.run` and `os.environ.get` (both allowed everywhere)

## Deviations from Plan

None. Plan executed exactly as written.

The pre-existing `test_mockslurmbackend_metadata_round_trip` failure in `tests/backends/test_jobspec_metadata.py` is out of scope (MockSLURMBackend.healthcheck is Wave 3 per execution rules). Confirmed pre-existing by stash-test.

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, or file-access patterns introduced. Healthcheck is read-only subprocess invocation with no secrets.

## Self-Check: PASSED

- `src/automil/backends/local.py` exists with `def healthcheck`, `def _healthcheck_cuda`, `def _healthcheck_rocm`
- `tests/backends/test_local_healthcheck.py` exists with 6 test functions
- Task 1 commit `c3f4984` exists
- Task 2 commit `6036a2b` exists
- 6 tests pass: confirmed by `uv run pytest tests/backends/test_local_healthcheck.py -v`
- `LocalBackend()` instantiates without TypeError (abstract method gate closed)
