---
phase: 05-generalization-gate
plan: 01
subsystem: gate/stats
tags: [statistics, pure-function, scipy, bonferroni, wilcoxon, bootstrap, tdd]
dependency_graph:
  requires: []
  provides:
    - "automil.gate.paired_wilcoxon_with_bootstrap"
    - "automil.gate.bonferroni_correct"
    - "automil.gate.diagnose_gate_health"
    - "tests/gate/conftest.py fixtures (deterministic_seed, positive_deltas, mixed_deltas, all_zero_deltas)"
  affects:
    - "Phase 5 plans 02-12: all downstream gate plans import from automil.gate"
tech_stack:
  added:
    - "scipy.stats.wilcoxon (already installed transitively 1.17.1; now used in gate/stats.py)"
    - "scipy.stats.bootstrap (BCa method, n_resamples=1000)"
  patterns:
    - "Pure-function discipline mirroring cells/cap.py (no I/O, no clock reads, caller injects all state)"
    - "TDD red/green with source-inspection tests for literal API surface verification"
key_files:
  created:
    - src/automil/gate/__init__.py
    - src/automil/gate/stats.py
    - tests/gate/__init__.py
    - tests/gate/conftest.py
    - tests/gate/test_gate_package.py
    - tests/gate/test_stats.py
  modified: []
decisions:
  - "Bonferroni direction: divide alpha by K (alpha/K), never multiply p-values — enforced by test_bonferroni_direction anti-test"
  - "Docstring must not contain literal 'time.time(' to avoid tripping the purity source-inspection test (Rule 1 deviation; changed 'no time.time()' to 'no clock reads')"
  - "stats.py only imports from __future__, numpy, scipy.stats — zero other dependencies"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-06T00:31:46Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 0
---

# Phase 5 Plan 01: Gate Stats Core Summary

**One-liner:** Pure-function scipy gate stats (paired Wilcoxon + BCa bootstrap + Bonferroni alpha/K) with 13-test TDD coverage and source-inspection purity guards.

## What Was Built

The `src/automil/gate/` package was created from scratch with two files:

1. **`src/automil/gate/stats.py`** — The only scipy importer in `src/automil/`. Three pure functions:
   - `paired_wilcoxon_with_bootstrap(deltas, p_threshold, bootstrap_reps=1000, rng_seed=None)` — One-sided Wilcoxon signed-rank (`alternative="greater"`) + BCa bootstrap CI (`method="BCa"`) on per-cell deltas. Returns `(passes, p_value, (ci_low, ci_high), individual_wins)`. Handles empty array and all-zero array as `(False, 1.0, (0.0, 0.0), 0)` (never raises).
   - `bonferroni_correct(p_threshold, K)` — Divides alpha by K (Wikipedia convention). Raises `ValueError` for K < 1. Never multiplies p-values (Pitfall 4 enforced by anti-test).
   - `diagnose_gate_health(promotion_rate_30d, threshold_low=0.05, threshold_high=0.5)` — Returns human-readable "too strict / too loose / healthy" diagnostic for `automil status` (D-144 / Pitfall 6).

2. **`src/automil/gate/__init__.py`** — Package skeleton re-exporting the three stats symbols. Alphabetic `__all__`, module docstring tracks plan increments (05-01 through 05-07).

3. **`tests/gate/`** — New test package with:
   - `__init__.py` — package marker
   - `conftest.py` — four pytest fixtures: `deterministic_seed`, `positive_deltas`, `mixed_deltas`, `all_zero_deltas`
   - `test_gate_package.py` — 2 import/`__all__` tests
   - `test_stats.py` — 13 tests covering Bonferroni direction, Wilcoxon pass/fail/edge, BCa/n_resamples/alternative source assertions, diagnose_gate_health, and purity

## Test Results

```
tests/gate/test_stats.py::test_bonferroni_direction PASSED
tests/gate/test_stats.py::test_bonferroni_rejects_K_lt_1 PASSED
tests/gate/test_stats.py::test_paired_wilcoxon_all_positive PASSED
tests/gate/test_stats.py::test_paired_wilcoxon_mixed_borderline PASSED
tests/gate/test_stats.py::test_paired_wilcoxon_all_zero_returns_false PASSED
tests/gate/test_stats.py::test_paired_wilcoxon_empty_returns_false PASSED
tests/gate/test_stats.py::test_alternative_is_greater PASSED
tests/gate/test_stats.py::test_bootstrap_uses_BCa_method PASSED
tests/gate/test_stats.py::test_bootstrap_n_resamples_is_passed_through PASSED
tests/gate/test_stats.py::test_diagnose_gate_health_low PASSED
tests/gate/test_stats.py::test_diagnose_gate_health_high PASSED
tests/gate/test_stats.py::test_diagnose_gate_health_healthy PASSED
tests/gate/test_stats.py::test_no_filesystem_io PASSED
13 passed in 0.88s
```

Full suite: **666 passed, 9 skipped** (no regressions).

## Acceptance Criteria Verification

| Check | Result |
|-------|--------|
| `from automil.gate import bonferroni_correct, diagnose_gate_health, paired_wilcoxon_with_bootstrap` | PASS (exits 0) |
| `grep -c 'p_threshold / K' src/automil/gate/stats.py` | 1 (Bonferroni divide-direction) |
| `grep -c 'p_threshold \* K' src/automil/gate/stats.py` | 0 (multiply direction absent) |
| `grep -c 'alternative="greater"' src/automil/gate/stats.py` | 1 |
| `grep -c 'method="BCa"' src/automil/gate/stats.py` | 1 |
| `grep -c 'n_resamples=bootstrap_reps' src/automil/gate/stats.py` | 1 |
| Purity: no `open(`, `tempfile`, `subprocess`, `time.time(` | PASS (0 hits) |
| Framework purity: no `autobench`/`AUTOBENCH_`/`benchmarks/` | PASS (0 hits) |
| BCK-04: no `os.kill`/`os.getpid`/`Popen`/`.pid` | PASS (0 hits) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring literal triggered purity source-inspection test**
- **Found during:** Task 2 test run (Test 13 `test_no_filesystem_io`)
- **Issue:** The module docstring said `"no time.time()"` which contains the literal string `time.time(` — the exact pattern the purity test checks for. Test 13 failed on the docstring, not production code.
- **Fix:** Changed docstring phrase from `"no time.time()"` to `"no clock reads"` — semantically equivalent, doesn't trigger the purity guard.
- **Files modified:** `src/automil/gate/stats.py` (line 4 of module docstring)
- **Commit:** bcee250 (included with Task 2 commit)

## Known Stubs

None — all three functions are fully implemented with correct scipy calls. No placeholder values, no TODO items, no hardcoded empty returns in the production path (the empty/all-zero guard returns are intentional semantics, not stubs).

## Threat Flags

None — `src/automil/gate/stats.py` is a pure-function module with no network endpoints, no auth paths, no file access, and no schema changes at trust boundaries.

## Self-Check: PASSED

- `src/automil/gate/__init__.py` — FOUND
- `src/automil/gate/stats.py` — FOUND
- `tests/gate/__init__.py` — FOUND
- `tests/gate/conftest.py` — FOUND
- `tests/gate/test_stats.py` — FOUND
- Task 1 commit 28e16fa — FOUND (`git log --oneline | grep 28e16fa`)
- Task 2 commit bcee250 — FOUND (`git log --oneline | grep bcee250`)
