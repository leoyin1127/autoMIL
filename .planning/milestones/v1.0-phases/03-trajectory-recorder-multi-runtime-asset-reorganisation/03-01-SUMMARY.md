---
phase: "03"
plan: "03-01"
subsystem: trajectory
tags: [trajectory, recorder, schema, redactor, flock, fd-cache, stdlib]
dependency_graph:
  requires: []
  provides:
    - "src/automil/trajectory package: record_event, read_metadata, RotationManager, TrajectorySchemaError, validate_event"
  affects:
    - "Plans 03-03 (redactor tests), 03-04 (rotation impl), 03-09 (export/CLI)"
tech_stack:
  added:
    - "src/automil/trajectory/ package (stdlib-only: fcntl, os, threading, atexit, json, re)"
  patterns:
    - "O_APPEND + fcntl.LOCK_EX flock for multi-process JSONL append"
    - "Process-level fd cache keyed by path string (D-86 Linux flock requirement)"
    - "atexit.register(_close_all_fds) for clean fd release on exit"
    - "Compiled regex set at module import time (one-time cost)"
    - "Frozen dataclass for RotationManager"
key_files:
  created:
    - src/automil/trajectory/__init__.py
    - src/automil/trajectory/schema.py
    - src/automil/trajectory/redactor.py
    - src/automil/trajectory/recorder.py
    - src/automil/trajectory/rotation.py
    - src/automil/trajectory/export.py
    - tests/trajectory/__init__.py
  modified: []
decisions:
  - "D-81 enforced: GEN_AI_PROVIDER_NAME = 'gen_ai.provider.name' (deprecated gen_ai.system NOT used)"
  - "D-86 enforced: fd-cache (_FD_CACHE dict) keeps fds open across events per node_id — never open-close per event"
  - "D-106 enforced: no opentelemetry-sdk dependency anywhere in trajectory package"
  - "D-83 enforced: 8 KB per-event size cap via apply_size_cap() with two-tier truncation strategy"
  - "rotation.py and export.py are stubs with correct public interface — full impl in 03-04 and 03-09"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 7
  files_modified: 0
---

# Phase 03 Plan 01: Trajectory Package Skeleton + Schema + Redactor + Recorder FD-Cache Summary

Stdlib-only `src/automil/trajectory/` package with append-only JSONL recorder using O_APPEND + LOCK_EX flock + per-node fd-cache (D-86 Linux flock compliance), OTel `gen_ai.provider.name` field constants (not deprecated `gen_ai.system`), compiled redaction patterns, 8 KB per-event cap, and RotationManager/export_bundle stubs for downstream plans.

## Tasks Completed

| Task | Description | Status | Commit |
|------|-------------|--------|--------|
| T-03-01-01 | Create schema.py, redactor.py, rotation.py, export.py | Done | 4bf838b |
| T-03-01-02 | Create recorder.py with fd-cache + flock + atexit | Done | 4bf838b |
| T-03-01-03 | Create __init__.py + tests/trajectory/__init__.py + verify | Done | 4bf838b |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns beyond plan scope, or schema changes at trust boundaries introduced. The recorder writes only to `archive_dir / node_id / trajectory.jsonl` (D-79). All threat model mitigations T-03-01-S01 through T-03-01-S05 implemented as designed.

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `RotationManager.check_and_rotate()` | `rotation.py` | Stub returning hard-limit check only; full soft-rotation (rename + new fd) deferred to Plan 03-04 |
| `export_bundle()` | `export.py` | Stub raising NotImplementedError; full impl deferred to Plan 03-09 (cli/trajectory.py) |

Both stubs have correct public interfaces — downstream plans (03-03, 03-04, 03-09) can import without error.

## Verification Results

```
uv run python -c "from automil.trajectory import record_event, read_metadata, RotationManager; print('OK')"
# OK

uv run python -c "import opentelemetry"
# ModuleNotFoundError — OK: opentelemetry not installed

uv run python -c "from automil.trajectory.schema import GEN_AI_PROVIDER_NAME; assert GEN_AI_PROVIDER_NAME == 'gen_ai.provider.name'; print('OK')"
# OK

uv run python -c "from automil.trajectory.redactor import redact; assert redact('sk-abcdefghijklmnopqrstu') == 'sk-[REDACTED]'; print('OK')"
# OK

uv run pytest tests/ -x -q
# 425 passed, 9 skipped — zero regressions
```

## Self-Check: PASSED

All 7 files exist on disk. Commit 4bf838b confirmed in git log. No deletions in commit diff. 425 baseline tests green.
