---
phase: 05-generalization-gate
plan: "09"
subsystem: cli/gate
tags: [cli, gate, nominate, promote, GTE-05, D-142, D-145, D-151]
dependency_graph:
  requires: ["05-04", "05-07", "05-08"]
  provides: ["automil nominate top-level command", "automil promote top-level command"]
  affects: [src/automil/cli/__init__.py, src/automil/cli/nominate.py, src/automil/cli/promote.py]
tech_stack:
  added: []
  patterns: ["TDD RED/GREEN", "Click top-level @main.command decorator", "monkeypatch evaluate_candidate for CLI tests"]
key_files:
  created:
    - src/automil/cli/nominate.py
    - src/automil/cli/promote.py
    - tests/gate/test_cli_nominate.py
    - tests/gate/test_cli_promote.py
  modified:
    - src/automil/cli/__init__.py
decisions:
  - "Tests use 5 held-out cells with p_threshold=0.2 (Bonferroni-corrected alpha=0.04 > Wilcoxon minimum achievable p of 0.031 for n=5); K=2 with p=0.05 is statistically impossible to pass (min p=0.25 for n=2) — consistent with test_promote.py proven setup"
  - "test_cli_promote.py monkeypatches both _resolve_backend (avoids daemon) and evaluate_candidate (controls deltas deterministically) per plan option (b)"
  - "Framework purity comments in docstrings that mention excluded terms were rephrased to avoid false positive grep matches"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-06T01:41:08Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 1
---

# Phase 05 Plan 09: Top-Level nominate + promote CLI Commands Summary

## One-liner

Top-level `automil nominate` and `automil promote` commands wired as D-145 operator shortcuts over gate.nominate/gate.promote; 12 TDD tests green.

## What Was Built

### Task 1: `automil nominate <node_id>` (TDD)

Created `src/automil/cli/nominate.py` — a `@main.command("nominate")` top-level Click command that:
- Takes `node_id` positional argument and hidden `--agent` flag (D-142 audit trail)
- Calls `gate.nominate(node_id, graph, agent_initiated=agent)` then `graph.save()`
- Raises `ClickException` on `ValueError` (unknown node, wrong status)
- Is idempotent (gate.nominate is idempotent; CLI echoes final status)

Registered in `cli/__init__.py` alphabetically after `lifecycle`.

6 tests in `tests/gate/test_cli_nominate.py`:
- T-1 keep→candidate happy path (status=candidate, output contains "Nominated node_0001")
- T-2 --agent flag stamps agent_initiated=True
- T-3 unknown node exits non-zero + "not found"
- T-4 discard node exits non-zero + status hint
- T-5 idempotent (second call exits 0, only one history event)
- T-6 graph.save() called (fresh ExperimentGraph re-read shows candidate)

### Task 2: `automil promote <candidate_id>` (TDD)

Created `src/automil/cli/promote.py` — a `@main.command("promote")` top-level Click command that:
- Takes `candidate_id` positional argument, `--calibrate` flag (D-151 dry-run), `--backend` option
- Calls `gate.promote(candidate_id, backend, graph, manifests_dir, archive_dir, calibrate=calibrate)`
- `_resolve_backend()` helper rejects non-"local" backends with clear error (T-05-09-02 STRIDE)
- `--calibrate` output uses `[calibrate]` prefix + "would-PASS/FAIL (status unchanged: ...)"
- Gate fail returns exit 0 (not a CLI error); missing node/manifest returns non-zero
- Distinct from `automil promote-variant` (Phase 1, lifecycle/promote_variant.py) — both coexist

Registered in `cli/__init__.py` alphabetically before `propose`.

6 tests in `tests/gate/test_cli_promote.py`:
- T-7 pass path (5 positive deltas, p_threshold=0.2/K=5) → status='registered'
- T-8 fail path (5 negative deltas) → exit 0, status='keep'
- T-9 --calibrate → status stays 'candidate', no parent gate_log written
- T-10 keep node (not nominated) → non-zero exit + 'candidate' + 'nominate' hint
- T-11 unknown node → non-zero exit + 'not found'
- T-12 no manifest → non-zero exit + 'manifest' + parent_id hint

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test T-7 pass path failed with K=2 (Wilcoxon mathematically blocked)**
- **Found during:** GREEN phase of Task 2
- **Issue:** With K=2 held-out cells and Bonferroni correction (alpha=0.05/2=0.025), scipy.stats.wilcoxon minimum achievable p-value for n=2 is 0.25 >> 0.025 — gate can never pass statistically
- **Fix:** Changed fixture to 5 held-out cells with p_threshold=0.2 (Bonferroni-corrected alpha=0.04 > Wilcoxon minimum p 0.031 for n=5); identical approach to proven test_promote.py setup
- **Files modified:** tests/gate/test_cli_promote.py
- **Commit:** 378ed69 (test fix bundled with implementation)

**2. [Rule 1 - Bug] Framework purity grep false positive in docstring comments**
- **Found during:** Final acceptance check
- **Issue:** Docstring comment saying "no autobench / AUTOBENCH_ / benchmarks/ references" triggered the very grep it documented
- **Fix:** Rephrased both nominate.py and promote.py docstrings to "generic framework code only — D-148 verified"
- **Files modified:** src/automil/cli/nominate.py, src/automil/cli/promote.py
- **Commits:** included in 2d935b0 and 7edd3d1

## Verification Results

```
uv run pytest tests/gate/test_cli_nominate.py tests/gate/test_cli_promote.py -v
12 passed in 1.16s

uv run pytest tests/ -x -q
769 passed, 9 skipped, 17 warnings in 26.30s

automil nominate --help    → shows NODE_ID
automil promote --help     → shows --calibrate
automil promote-variant --help  → still works (existing command preserved)
grep -rE "autobench|AUTOBENCH_|benchmarks/" src/automil/cli/nominate.py src/automil/cli/promote.py
→ 0 matches (PURITY_CLEAN)
```

## Known Stubs

None — both commands are fully wired to gate.nominate and gate.promote.

## Threat Flags

No new threat surface beyond what the plan's threat model covers. T-05-09-01 and T-05-09-02 mitigations implemented as designed.

## Self-Check: PASSED

Files exist:
- FOUND: src/automil/cli/nominate.py
- FOUND: src/automil/cli/promote.py
- FOUND: tests/gate/test_cli_nominate.py
- FOUND: tests/gate/test_cli_promote.py

Commits exist:
- FOUND: 2d935b0 (Task 1 — nominate)
- FOUND: 378ed69 (Task 2 — promote)
- FOUND: 7edd3d1 (purity fix)
