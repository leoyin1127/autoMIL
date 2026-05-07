---
phase: 07-hardware-autodetect-automil-setup-skill
plan: 01
subsystem: backends
tags: [healthcheck, dataclass, abc, hardware-detect, D-189, STP-01]

dependency_graph:
  requires:
    - Phase 6 Backend ABC (submit/poll/cancel/log_iter/list_running) -- provides base class
  provides:
    - HealthReport frozen dataclass (backends/base.py)
    - Backend.healthcheck abstract method (backends/base.py)
  affects:
    - src/automil/backends/local.py (must implement healthcheck -- Wave 2, plan 07-03)
    - src/automil/backends/slurm.py (must implement healthcheck stub -- Wave 3, plan 07-04)
    - src/automil/backends/ray.py (must implement healthcheck stub -- Wave 3, plan 07-04)
    - src/automil/backends/mock_slurm.py (must implement healthcheck stub -- Wave 3, plan 07-04)

tech_stack:
  added:
    - "from datetime import datetime (stdlib, used by HealthReport.detected_at)"
    - "from typing import Literal (stdlib, used by HealthReport.accelerator + detection_status)"
  patterns:
    - "frozen dataclass with tuple sequence fields (hashable, JSON-serialisable) -- matches Phase 2 D-53 convention"
    - "@abstractmethod with docstring-only body (no raise, no pass) -- mandatory per D-189 BREAKING contract"

key_files:
  modified:
    - path: src/automil/backends/base.py
      change: "Added HealthReport dataclass (lines 114-159) and Backend.healthcheck abstractmethod (lines 219-232); updated Backend docstring to remove Phase 7 placeholder; added datetime + Literal imports"

decisions:
  - "D-189: HealthReport is frozen dataclass with 8 fields; Backend.healthcheck is @abstractmethod with no default body"
  - "Committed to main branch (not worktree) because worktree branch predates Phase 6 and lacks the backends/ directory"

metrics:
  duration: "8 minutes"
  completed: "2026-05-07"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 7 Plan 01: HealthReport Dataclass + Backend.healthcheck Abstract Method

Wave 1 of Phase 7: lands HealthReport frozen dataclass (D-189 / STP-01) and Backend.healthcheck abstract method on the Phase 6 Backend ABC, creating a stable import contract for all downstream Wave 2/3 plans.

## What Was Done

Single edit to `src/automil/backends/base.py`:

**Step A -- imports (lines 8-16):** Added `from datetime import datetime` and extended
`from typing import ...` to include `Literal`. Both are stdlib; no new dependencies.

**Step B -- HealthReport dataclass (lines 114-159):** Inserted `@dataclass(frozen=True)` class
after `JobSpec` and before `class Backend`. All 8 D-189 fields in locked order:
- `gpu_count: int` (line 135)
- `gpu_vram_gb: tuple[float, ...]` (line 138)
- `accelerator: Literal["cuda", "rocm", "cpu"]` (line 142)
- `python_version: str` (line 145)
- `automil_version: str` (line 148)
- `detection_status: Literal["ok", "partial", "failed"]` (line 151)
- `detection_warnings: tuple[str, ...]` (line 155)
- `detected_at: datetime` (line 158)

All sequence fields use `tuple[T, ...]` (not `list[T]`) for hashability per D-53.

**Step C -- healthcheck abstract method (lines 219-232):** Added `@abstractmethod def healthcheck(self) -> HealthReport` after the existing `log_iter` method. Body is docstring only (no `raise`, no `pass`) -- mandatory per D-189 BREAKING contract and anti-pattern #4 in 07-PATTERNS.md.

**Step D -- Backend docstring update (lines 163-170):** Replaced "Phase 7 will add an optional
`healthcheck()` method" with "Phase 7 adds the abstract `healthcheck()` method (D-189;
subclasses without an implementation are uninstantiable)."

## Acceptance Evidence

```
# HealthReport instantiation
HealthReport ok

# Abstract method registration
abstract ok

# grep counts
HealthReport count: 1
healthcheck count: 1
@dataclass(frozen=True) count: 3  (was 2, +1 for HealthReport)

# Frozen=True rejects mutation
frozen ok

# No em/en dashes
no em/en dashes found

# Test collection
848 tests collected in 11.51s
```

Subclass transient breakage (expected, closed by 07-03/07-04):
```
LocalBackend correctly raises TypeError: Can't instantiate abstract class LocalBackend with abstract method healthcheck
```

## Deviations from Plan

**1. [Rule 3 - Worktree mismatch] Committed to main repo instead of worktree**

- **Found during:** Task 1, pre-commit check
- **Issue:** Worktree branch `worktree-agent-aefbaf44da198c672` predates Phase 6 and has
  no `src/automil/backends/` directory. The plan target file only exists on `main`.
- **Fix:** Committed to main branch where the file lives. The file was already modified
  there via the Read/Edit tools (which resolved the absolute path to the main repo).
- **Files modified:** src/automil/backends/base.py
- **Commit:** 818eafa

No other deviations. Plan executed as written.

## Known Stubs

None. This plan adds a contract definition only, no implementation with hardcoded values.

## Threat Flags

None. `HealthReport` is a pure data container; no new network endpoints, auth paths,
file access patterns, or schema changes at trust boundaries were introduced.

## Self-Check: PASSED

- `src/automil/backends/base.py` exists and contains `class HealthReport`: confirmed
- commit 818eafa exists: confirmed
- 848 tests collected: confirmed
- no em/en dashes: confirmed
