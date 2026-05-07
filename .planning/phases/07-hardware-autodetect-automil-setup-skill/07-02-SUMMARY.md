---
phase: 07-hardware-autodetect-automil-setup-skill
plan: 02
subsystem: cli
tags: [cli, submit, max-time, D-195, STP-06]
dependency_graph:
  requires: []
  provides: [--max-time SECONDS flag in automil submit]
  affects: [src/automil/cli/submit.py, tests/cli/test_submit_max_time.py]
tech_stack:
  added: []
  patterns: [click option with dest rename, ceil-div timeout translation]
key_files:
  created:
    - tests/cli/__init__.py
    - tests/cli/test_submit_max_time.py
  modified:
    - src/automil/cli/submit.py
decisions:
  - "tests/cli/ subdirectory created with __init__.py as specified in plan contract; flat tests/ layout is existing convention but plan explicitly required the subdir path"
metrics:
  duration: 8m
  completed: 2026-05-07
---

# Phase 7 Plan 02: Add --max-time SECONDS Flag to automil submit Summary

Added `--max-time SECONDS` click option to `automil submit` with ceil-div translation to `timeout_min`, satisfying D-195 / RESEARCH.md OQ-5 for the STP-06 setup-done gate.

## What Was Built

**src/automil/cli/submit.py** (17 lines inserted, 1 line modified):

- Option decorator added at lines 27-28 (after `--timeout`):
  ```python
  @click.option("--max-time", "max_time_seconds", type=int, default=None,
                help="Override --timeout with seconds-precision (rounded up to 1 min minimum, D-195).")
  ```
- Function signature extended at line 30: `max_time_seconds: int | None` added between `timeout` and `parent`.
- Translation block inserted at lines 40-52 (before `import hashlib`):
  - Negative values raise `click.ClickException` immediately.
  - Ceil-div: `translated = max(1, (max_time_seconds + 59) // 60)`.
  - When `--timeout` was explicitly passed (not default 150), `click.echo` warning emitted: `--max-time wins`.
  - `timeout = translated` rebinds the variable; the existing `"timeout_min": timeout` spec dict line (now line ~294) requires no modification.

**Ceil-div boundary correctness:**
- 0s -> `max(1, 0)` = 1 min
- 60s -> `max(1, 1)` = 1 min
- 61s -> `max(1, 2)` = 2 min
- 120s -> `max(1, 2)` = 2 min
- 121s -> `max(1, 3)` = 3 min

**tests/cli/test_submit_max_time.py** (4 tests):
1. `test_max_time_60_seconds_yields_timeout_min_1` -- flag accepted; spec timeout_min == 1.
2. `test_max_time_121_seconds_ceil_to_3_min` -- ceil-div arithmetic verified.
3. `test_max_time_overrides_timeout_with_warning` -- --max-time wins over explicit --timeout; warning printed.
4. `test_max_time_negative_rejected` -- negative value exits non-zero with "must be non-negative" message.

## Test Count Delta

Phase 6 baseline: 387 tests (in flat tests/ layout in this worktree).
After plan 07-02: 391 tests (4 new in tests/cli/).

## Acceptance Evidence

```
uv run automil submit --help | grep -- '--max-time'  -> 1 match
uv run pytest tests/cli/test_submit_max_time.py -x -q -> 4 passed in 0.50s
grep -P "em-dash pattern" submit.py test_file          -> no new em-dashes in added code
grep -E "autobench|AUTOBENCH_" submit.py test_file     -> zero matches
```

## Deviations from Plan

**1. [Rule 2 - Scope adjustment] tests/cli/ created per plan contract despite flat layout**
- The existing tests live in a flat `tests/` directory (no subdirectories except `tests/fixtures/`).
- The plan contract explicitly specified `tests/cli/test_submit_max_time.py`; followed exactly.
- Created `tests/cli/__init__.py` for pytest package discovery.
- No behavioral deviation; purely a path layout choice mandated by the plan.

**2. [Pre-existing em-dash] Line 60 of submit.py has a pre-existing em-dash**
- `# re-run it and clobber its archive/result.json -- destroying prior data`
- This is pre-existing code not touched by this plan; out of scope per scope boundary rule.
- No em-dashes in any code added by this plan.

## Known Stubs

None. The flag is fully wired: click parses it, translation runs before spec dict, downstream `timeout_min` carries the correct value.

## Threat Flags

None. This change adds no new network endpoints, auth paths, or trust boundaries. The new option is a pure in-process integer translation.

## Self-Check: PASSED

- src/automil/cli/submit.py modified: FOUND
- tests/cli/test_submit_max_time.py created: FOUND
- Commits: 7e5580d (feat submit.py), f675b61 (feat tests)
- 4/4 tests pass
- --max-time in help: confirmed
