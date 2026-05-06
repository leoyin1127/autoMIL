---
phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation
plan: "01"
subsystem: cells
tags: [cells, frozen-dataclass, str-enum, atomic-write, sha256, cap, budget]

# Dependency graph
requires:
  - phase: 02-backend-abc-localbackend-re-export-shim-mockslurm-fixture
    provides: frozen dataclass + str-Enum patterns (JobHandle, JobState) mirrored by Cell + CellStatus
  - phase: 00-tier-2-cleanup-cli-split-compat-shim
    provides: atomic write pattern (_atomic_write_text) mirrored by write_cell

provides:
  - Cell frozen dataclass with 8 fields (cell_id, dataset, encoder, parent_id, started_at, budget_seconds, safety_buffer_seconds, status)
  - CellStatus str-Enum (ACTIVE, REFUSING_NEW, TERMINATING, FINALIZED)
  - make_cell_id() deterministic sha256 cell identity
  - consumed_seconds() computed wall-clock (restart-safe, no accumulator)
  - write_cell() + read_cell() atomic JSON IO via tempfile.mkstemp + os.replace
  - automil.cells public surface (__init__.py with __all__)
  - tests/cells/ package + make_cell() factory + cells_dir fixture

affects: [04-02, 04-03, 04-04, 04-05, 04-06, 04-07, 04-08, 04-09, 04-10, 04-11]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CellStatus(str, Enum) — string-valued enum for JSON serialisation without custom encoder"
    - "@dataclass(frozen=True) Cell — immutable snapshot; status transitions via dataclasses.replace + write_cell"
    - "consumed_seconds = time.time() - started_at (computed model, never accumulated)"
    - "tempfile.mkstemp(dir=cells_dir) + os.replace — same-filesystem atomic write (Pitfall 2 defence)"
    - "make_cell_id = sha256(dataset|encoder|parent_id)[:16] — deterministic 16-char hex identity"

key-files:
  created:
    - src/automil/cells/state.py
    - src/automil/cells/__init__.py
    - tests/cells/__init__.py
    - tests/cells/conftest.py
  modified: []

key-decisions:
  - "D-108: Cell is frozen dataclass — status transitions go through dataclasses.replace + write_cell, never in-place mutation"
  - "D-109: cell_id = sha256(dataset|encoder|parent_id)[:16] — same tuple always maps to same cell"
  - "D-110: CellStatus(str, Enum) — four values exhaust the cap state machine"
  - "D-111: consumed_seconds is computed (time.time() - started_at), never accumulated — restart-safe"
  - "D-112: write_cell uses tempfile.mkstemp(dir=cells_dir) to keep tmp on same filesystem, then os.replace"

patterns-established:
  - "cells/state.py: CellStatus(str, Enum) mirrors backends/base.py JobState(str, Enum)"
  - "cells/state.py: Cell @dataclass(frozen=True) mirrors backends/base.py JobHandle"
  - "write_cell: copies _atomic_write_text pattern with dir=cells_dir to guarantee same-filesystem rename"
  - "conftest.py: make_cell() as plain function (not fixture) for inline Cell construction"
  - "conftest.py: cells_dir fixture provides isolated tmp_path / 'cells' directory"

requirements-completed: [CAP-01, CAP-05]

# Metrics
duration: 12min
completed: 2026-05-05
---

# Phase 4 Plan 01: Cell State Primitives Summary

**Cell frozen dataclass + CellStatus str-Enum + atomic JSON IO via tempfile+os.replace — the foundational cells.state module that every Phase 4 cap layer imports**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-05T00:00:00Z
- **Completed:** 2026-05-05T00:12:00Z
- **Tasks:** 3
- **Files modified:** 4 (all created)

## Accomplishments

- `src/automil/cells/state.py` — CellStatus(str, Enum) with four values, Cell frozen dataclass with eight fields per D-108, make_cell_id (sha256 prefix, D-109), consumed_seconds (computed wall-clock, restart-safe, D-111), write_cell + read_cell (atomic IO via tempfile.mkstemp(dir=cells_dir) + os.replace, D-112 + Pitfall 2 defence)
- `src/automil/cells/__init__.py` — public surface re-exporting all six Wave-1 symbols with `__all__`; Wave 2 plans extend by adding lines only
- `tests/cells/__init__.py` + `tests/cells/conftest.py` — pytest package + make_cell() factory + cells_dir fixture; Wave 2-5 test plans import from these

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/automil/cells/state.py** - `3abfb6a` (feat)
2. **Task 2: Create src/automil/cells/__init__.py** - `bb9b5e1` (feat)
3. **Task 3: Create tests/cells/ skeleton + conftest.py** - `9dbcaf8` (feat)

## Files Created/Modified

- `src/automil/cells/state.py` — CellStatus str-Enum, Cell frozen dataclass, make_cell_id, consumed_seconds, write_cell, read_cell
- `src/automil/cells/__init__.py` — public surface with __all__; Wave 2 additions are line-additions only
- `tests/cells/__init__.py` — pytest package marker
- `tests/cells/conftest.py` — cells_dir fixture + make_cell() plain-function factory

## Decisions Made

- Followed D-108..D-112 exactly as locked in 04-CONTEXT.md; no engineering deviations
- `consumed_seconds` is a module-level function, not a Cell method — frozen dataclass equality unaffected
- `make_cell_id()` is idempotent by construction — same (dataset, encoder, parent_id) always maps to same 16-char hex id
- `read_cell()` included in Wave 1 even though not in D-112 explicitly — needed for test round-trip verification and required for registry.get_or_create_cell in Plan 04-06

## Deviations from Plan

None - plan executed exactly as written.

The only minor adjustment: removed `consumed_seconds_at_last_tick += dt` text from a docstring comment (it was describing the anti-pattern to avoid, but would have caused the acceptance grep `grep -c "+= "` to return 1 instead of 0). Replaced with equivalent prose "no counter accumulation" that conveys the same meaning without the literal `+=` character sequence.

## Issues Encountered

None. All three tasks completed on first attempt with no blocking issues.

## Next Phase Readiness

- `automil.cells.state` is the foundation all Phase 4 Wave 2+ plans import from
- Wave 2 plans (04-02 runtime_helpers.py, 04-03 cap.py, 04-04 aggregate_folds, 04-05 reconcile.py, 04-06 registry.py) can now compile
- `tests/cells/` package and `make_cell()` factory are ready for Wave 2 test plans
- No blockers; all acceptance criteria green; 387-test baseline preserved

---
*Phase: 04-6h-per-cell-hard-cap-cell-concept-formalisation*
*Completed: 2026-05-05*
