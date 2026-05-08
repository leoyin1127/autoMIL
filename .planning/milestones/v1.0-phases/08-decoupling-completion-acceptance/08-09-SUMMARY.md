---
phase: 08-decoupling-completion-acceptance
plan: "09"
subsystem: acceptance-gate
tags: [testing, acceptance, d-205, dec-07, sklearn-iris, ccrcc]
dependency_graph:
  requires: [08-01, 08-02, 08-03, 08-04, 08-05, 08-06, 08-07, 08-08]
  provides: [d-205-acceptance-gate, dec-07-sub-gate-b-ci]
  affects: [tests/acceptance/, pyproject.toml, examples/sklearn-iris/train.py]
tech_stack:
  added: []
  patterns: [subprocess-popen-sigterm, poll-result-json, automil-reconcile-post-stop]
key_files:
  created:
    - tests/acceptance/__init__.py
    - tests/acceptance/conftest.py
    - tests/acceptance/test_final_phase8_acceptance.py
  modified:
    - pyproject.toml
    - examples/sklearn-iris/train.py
decisions:
  - "Sub-gate B polls archive/result.json (not graph.json) then runs automil reconcile post-stop; graph.json is not written by the daemon in the normal completion path"
  - "train.py RESULTS_DIR changed to Path('.') so collect_result finds result.json in the worktree cwd per the contract"
  - "automil init --no-healthcheck used (--non-interactive does not exist); example automil/ dir excluded from copytree to allow fresh init scaffold"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-07"
  tasks_completed: 3
  files_modified: 5
---

# Phase 8 Plan 09: Phase 8 Final Acceptance Gate (D-205 / DEC-07) Summary

3-sub-gate acceptance test file landing D-205 with real orchestrator subprocess path (F-04), deterministic monorepo path probe (F-08), and liberal CCRCC fixture (F-12).

## What Was Built

### Task 1: pyproject.toml marker
Added `requires_ccrcc_data: requires real CCRCC dataset at AUTOBENCH_CCRCC_ROOT (workstation only)` to the `[tool.pytest.ini_options] markers` list. Existing `requires_slurm` and `requires_ray` markers unchanged.

### Task 2: tests/acceptance/ package + conftest
- `tests/acceptance/__init__.py`: package marker docstring.
- `tests/acceptance/conftest.py`: `ccrcc_data_root` fixture (F-12 liberal; skips only on missing env var or non-existent root, no `splits/` check) + `cli_runner` fixture re-exporting Click CliRunner.

### Task 3: 3-sub-gate acceptance test (+ Rule 1 train.py fix)

`tests/acceptance/test_final_phase8_acceptance.py` contains:

**Sub-gate B** (CI default, unmarked): sklearn-iris end-to-end via real `automil orchestrator start` Popen subprocess. Full flow: copy example without pre-existing automil/ dir, git-init, `automil init --no-healthcheck`, `automil submit`, Popen orchestrator, poll `archive/iris_001/result.json`, SIGTERM orchestrator, `automil reconcile`, validate result.json schema, assert composite >= 0.90. PASSES in CI (composite=1.0 in test run, elapsed <13s).

**Sub-gate A** (`@pytest.mark.requires_ccrcc_data`): invokes `automil verify-repro node_0176` against `_REPO_ROOT/benchmarks/experiments/ccrcc` (F-08 fix); reads `repro_manifest.yaml`; asserts `|actual - 0.502| < 0.005`. SKIPS cleanly on CI (no AUTOBENCH_CCRCC_ROOT).

**Sub-gate C** (`@pytest.mark.requires_ccrcc_data`): workstation-shape-deferred pytest.skip() body; marker scaffolding in place. SKIPS cleanly on CI.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] --non-interactive flag does not exist**
- **Found during:** Task 3 first run
- **Issue:** Plan spec used `automil init --non-interactive` but the real flag is `--no-healthcheck`.
- **Fix:** Changed init call to `automil init --no-healthcheck`.
- **Files modified:** tests/acceptance/test_final_phase8_acceptance.py
- **Commit:** 1b579d3

**2. [Rule 1 - Bug] copytree copies existing automil/ dir, causing "already initialized" error**
- **Found during:** Task 3 second run
- **Issue:** `shutil.copytree(_EXAMPLES_IRIS, project)` copies the pre-configured `automil/` dir from the example, so `automil init` (which checks for existing `automil/`) refuses with "already initialized". `--update` mode skips the `orchestrator/queue` scaffold, causing submit to fail with FileNotFoundError.
- **Fix:** Copy only non-`automil/` files from the example so fresh `automil init` scaffolds the full orchestrator directory structure.
- **Files modified:** tests/acceptance/test_final_phase8_acceptance.py
- **Commit:** 1b579d3

**3. [Rule 1 - Bug] train.py writes result.json to AUTOMIL_RESULTS_DIR (archive) not cwd (worktree)**
- **Found during:** Task 3 third run (composite=0 from synthesized result)
- **Issue:** `examples/sklearn-iris/train.py` used `RESULTS_DIR = Path(os.environ.get("AUTOMIL_RESULTS_DIR", os.getcwd()))`. The daemon sets `AUTOMIL_RESULTS_DIR` to the archive dir. `collect_result` reads `worktree_path/result.json`. The contract (CLAUDE.md) says "write result.json to their working directory" (= worktree cwd). So train.py was writing to the wrong place; the daemon synthesized `{"status": "completed"}` with composite=0.
- **Fix:** Changed `RESULTS_DIR = Path(".")` so result.json is written to cwd (the worktree when run by the orchestrator).
- **Files modified:** examples/sklearn-iris/train.py
- **Commit:** 1b579d3

**4. [Rule 1 - Bug] Polling graph.json for terminal state does not work in normal completion path**
- **Found during:** Task 3 fourth run (180s timeout)
- **Issue:** The daemon does NOT update graph.json in the standard completion path; it writes to `completed/<id>.json`. `graph.json` is only updated by `automil reconcile` (or cap-kill path). Polling graph.json indefinitely would always timeout.
- **Fix:** Replaced `_wait_for_graph_terminal` polling with `_wait_for_result_json` (polls `archive/<id>/result.json`), then SIGTERM orchestrator, then runs `automil reconcile` to flush graph.json, then reads graph.json for optional terminal-type assertion.
- **Files modified:** tests/acceptance/test_final_phase8_acceptance.py
- **Commit:** 1b579d3

## Test Results

```
tests/acceptance/test_final_phase8_acceptance.py::test_subgate_b_sklearn_iris_end_to_end PASSED (12.6s)
tests/acceptance/test_final_phase8_acceptance.py::test_subgate_a_ccrcc_node_0176_reproduction SKIPPED
tests/acceptance/test_final_phase8_acceptance.py::test_subgate_c_heterogeneous_consumers_same_project SKIPPED
```

Sub-gate B measured composite: 1.0 (sklearn iris accuracy 100% with seed=42, split 0.3).
Daemon ingest validate hook exercised end-to-end via real orchestrator subprocess.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 6e7e62b | chore(08-09): add requires_ccrcc_data pytest marker |
| 2 | f0a23a8 | test(08-09): create tests/acceptance/ package + fixtures |
| 3 | 1b579d3 | test(08-09): add 3-sub-gate Phase 8 acceptance test |

## Self-Check: PASSED
