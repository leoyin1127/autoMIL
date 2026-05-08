---
phase: 05-generalization-gate
plan: "08"
subsystem: cli/gate
tags: [cli, gate, manifest, scipy, config-template, GTE-01, GTE-02, GTE-04, GTE-06]
dependency_graph:
  requires: [05-02, 05-04, 05-07]
  provides: [automil-gate-cli-surface, scipy-core-dep, config-gate-section]
  affects: [cli/__init__.py, pyproject.toml, templates/config.yaml.j2]
tech_stack:
  added: []
  patterns: [Click-group-subcommand, lazy-imports-in-command-bodies, ClickException-error-pattern, _PARENT_ID_RE-path-traversal-defence]
key_files:
  created:
    - src/automil/cli/gate.py
    - tests/gate/test_cli_gate.py
  modified:
    - src/automil/cli/__init__.py
    - src/automil/templates/config.yaml.j2
    - pyproject.toml
decisions:
  - "scipy lifted to [project.dependencies] core — gate is meaningless without it; making consumers install via [ml] optional is avoidable friction"
  - "gate: config section framed as consumer-supplied (paper-campaign-vs-framework rule) with comment block explicitly labelling values as Leo's autoMIL-paper campaign defaults"
  - "--strategy auto-select raises helpful stub error pointing at calibration pilot (plan 12) rather than silently doing nothing"
  - "_PARENT_ID_RE = re.compile(r'^node_\\d+$') validates ALL parent_id inputs before file/git operations (T-05-08-01 path-traversal defence)"
metrics:
  duration: "9m 14s"
  completed: "2026-05-06T01:27:54Z"
  tasks_completed: 2
  files_changed: 5
---

# Phase 05 Plan 08: Gate CLI Surface Summary

One-liner: `automil gate` subcommand group with 4 operator commands for manifest lifecycle + promotion-rate stats, scipy lifted to core deps, config template extended with gate: section.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Lift scipy + add gate: config section | `101646e` | `pyproject.toml`, `config.yaml.j2`, `tests/gate/test_cli_gate.py` |
| 2 | cli/gate.py — 4 subcommands | `b90debb` | `src/automil/cli/gate.py`, `cli/__init__.py`, `tests/gate/test_cli_gate.py` |

RED commit: `1cb7390` (failing tests added before implementation)

## What Was Built

**`src/automil/cli/gate.py`** — `@main.group("gate")` with four subcommands:

- `register-manifest PARENT_ID` — validates parent_id regex, checks graph.json, builds GateManifest, calls `write_manifest_committed` (atomic write + git commit in one operation). Refuses overwrite with `retire-manifest` hint. Exposes `--strategy stratified|random|operator-curated` (D-145, O-03).
- `retire-manifest PARENT_ID --reason "..."` — calls `retire_manifest()` which renames active to `.retired.gate_manifest.json` + commits.
- `status [parent_id]` — with arg: detailed manifest view; without arg: list all active manifests.
- `stats` — reads `graph.promotion_rate(days=30)` and `diagnose_gate_health()` to show health diagnostic (D-144, GTE-06).

**`src/automil/cli/__init__.py`** — `from automil.cli import gate` added alphabetically between `control` and `init`.

**`src/automil/templates/config.yaml.j2`** — `gate:` section appended after `cap:` with:
```yaml
gate:
  auto_nominate:    false        # D-142 default
  K:                2            # O-01 default
  p_threshold:      0.05         # O-02 default
  bootstrap_reps:   1000         # GTE-04 locked
```
Comment block explicitly labels these as Leo's autoMIL-paper campaign values (paper-campaign-vs-framework rule).

**`pyproject.toml`** — `scipy>=1.11` added to `[project.dependencies]` core (kept in `[ml]` optional for back-compat; back-compat comment omitted since the old entry is just redundant).

## Test Results

12/12 tests pass:
- T-1..4 (Task 1): scipy in core deps, config gate: section YAML-parseable with correct defaults
- T-5..12 (Task 2): CLI subcommand surface via `CliRunner` with cwd-switching fixture
  - T-5: register creates file + git commit
  - T-6: invalid parent_id rejected with error message
  - T-7: overwrite refused with retire-manifest hint
  - T-8: `--strategy` choice parses; all three options in help
  - T-9: retire writes .retired file, git-commits rename
  - T-10: status shows manifest details
  - T-11: status (no arg) lists all active manifests
  - T-12: stats shows promotion_rate% + health diagnostic

## Deviations from Plan

**[Rule 1 - Bug] `CliRunner(mix_stderr=True)` not supported in Click 8.3.1**
- **Found during:** Task 2 GREEN phase
- **Issue:** `CliRunner.__init__()` in Click 8.x does not accept `mix_stderr` kwarg — parameter was removed. Tests used `mix_stderr=True` throughout.
- **Fix:** Replaced all `CliRunner(mix_stderr=True/False)` with `CliRunner()`. Introduced `_run_gate()` helper to handle cwd-switching consistently.
- **Files modified:** `tests/gate/test_cli_gate.py`
- **Commit:** included in `b90debb`

**[Rule 3 - Blocking] Worktree behind main**
- **Found during:** Initial setup
- **Issue:** Worktree was branched at pre-Phase-5 commit; gate/ package (plans 02/04/07) not present.
- **Fix:** `git merge --ff-only main` brought the worktree up to date (058a55c). Fast-forward merge — no divergence.
- **Commit:** not separately committed (pre-existing fast-forward merge)

## Known Stubs

- `--auto-select N` raises a `ClickException` pointing operators at `--held-out-cells` explicit list + calibration pilot (plan 12). This is intentional and documented in the help text — it's not a data-rendering stub but an acknowledged feature deferral.

## Threat Flags

None. `src/automil/cli/gate.py` introduces no new network endpoints. The `_PARENT_ID_RE` regex validates user-supplied `parent_id` strings before any file or git operations (T-05-08-01 mitigated). Held-out cells parsed through pure `split(":")` into tuple data — no shell execution.

## Self-Check: PASSED

- `src/automil/cli/gate.py` — FOUND
- `tests/gate/test_cli_gate.py` — FOUND
- `.planning/phases/05-generalization-gate/05-08-SUMMARY.md` — FOUND
- Commit `b90debb` — FOUND
- Commit `101646e` — FOUND
- Commit `1cb7390` — FOUND
- 12/12 tests GREEN
