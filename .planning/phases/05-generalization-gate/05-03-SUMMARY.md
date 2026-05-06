---
phase: 05-generalization-gate
plan: "03"
subsystem: backends
tags: [jobspec, metadata, backend-abc, tdd, gte-03, d-140]
dependency_graph:
  requires: []
  provides: [JobSpec.metadata field, LocalBackend metadata merge, MockSLURMBackend metadata introspection]
  affects: [src/automil/backends/base.py, src/automil/backends/local.py, src/automil/backends/mock_slurm.py]
tech_stack:
  added: []
  patterns: [frozen-dataclass kw-only-by-position field with default, tuple-of-tuples metadata passthrough, backend stamp ordering for tamper mitigation]
key_files:
  created:
    - tests/backends/test_jobspec_metadata.py
  modified:
    - src/automil/backends/base.py
    - src/automil/backends/local.py
    - src/automil/backends/mock_slurm.py
decisions:
  - "Merge spec.metadata FIRST then stamp backend='local' LAST — framework key wins over caller-provided 'backend' (T-05-03-01)"
  - "Keyed _metadata_by_node_id by handle.node_id (framework-owned) not opaque_id (backend-internal) — matches plan 06 gate test access pattern"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-05"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 4
---

# Phase 05 Plan 03: JobSpec.metadata Passthrough Summary

JobSpec extended with `metadata: tuple[tuple[str,str],...] = ()` — frozen, backward-compat, kw-only-by-position — so gate/evaluate.py can stamp `gate_eval`, `held_out`, `gate_parent_node`, `cell_id`, and `edge_type` through `Backend.submit()` without a parallel mechanism (GTE-03).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for JobSpec.metadata | 3e2cfd5 | tests/backends/test_jobspec_metadata.py |
| 1 (GREEN) | JobSpec.metadata + LocalBackend + MockSLURMBackend | 0f0330c | base.py, local.py, mock_slurm.py |

## What Was Built

### JobSpec.metadata (base.py)
Added as the last field in the frozen dataclass — kw-only by position with default `()`:
```python
metadata: tuple[tuple[str, str], ...] = ()
```
Mirrors the existing `env` field shape. All existing positional/keyword construction sites remain unbroken (no call sites needed updating).

### LocalBackend.submit() (local.py)
Merges `spec.metadata` into `queue_spec["metadata"]` BEFORE stamping `backend="local"`:
```python
for k, v in spec.metadata:
    queue_spec.setdefault("metadata", {})[k] = v
queue_spec.setdefault("metadata", {})["backend"] = "local"
```
Security ordering: caller-provided `"backend"` key is overridden by framework stamp (T-05-03-01).

### MockSLURMBackend (mock_slurm.py)
Added `_metadata_by_node_id: dict[str, dict[str, str]] = {}` in `__init__` and populated it in `submit()` after handle construction:
```python
self._metadata_by_node_id[handle.node_id] = dict(spec.metadata)
```
Plan 06 gate tests will assert: `mock_backend._metadata_by_node_id[handle.node_id]["gate_eval"] == "true"`.

## Test Results

- 7/7 new tests pass (`tests/backends/test_jobspec_metadata.py`)
- 35/35 (+ 9 skipped) backends suite passes
- 653 total / 9 skipped full suite — baseline preserved

## Deviations from Plan

### Plan note: merge ordering (T-05-03-01 executor note)
The plan's `<action>` section described merging AFTER the backend stamp, but the `<threat_model>` section and the executor note correctly identified that merge must happen BEFORE the stamp so `backend="local"` wins. Implementation follows the threat model note — merge first, stamp last.

No other deviations. Plan executed exactly as written (with the intended ordering per threat model).

## Known Stubs

None — all fields wired through. `spec.metadata` defaults to `()` (no-op) for all existing callers.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes beyond what is in the plan's threat model.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| src/automil/backends/base.py | FOUND |
| src/automil/backends/local.py | FOUND |
| src/automil/backends/mock_slurm.py | FOUND |
| tests/backends/test_jobspec_metadata.py | FOUND |
| Commit 3e2cfd5 (RED gate) | FOUND |
| Commit 0f0330c (GREEN implementation) | FOUND |
