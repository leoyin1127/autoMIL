---
phase: 00-tier-2-cleanup-cli-split-compat-shim
plan: 01
subsystem: cli
tags: [click, refactor, package-split, cli, python]

requires:
  - phase: pre-phase-0
    provides: Tier 1 mechanical fixes shipped (5 commits, 2026-05-01); 62 baseline tests green; cli.py at 725 lines as single monolith
provides:
  - src/automil/cli/ package replacing the 725-line cli.py monolith
  - 10 per-command modules (verb-not-audience naming) + _helpers.py + Click main group in __init__.py
  - Empty cli/lifecycle.py stub reserved for Phase 1 (apply, revert-baseline, port-variant, promote-variant, refresh-registry)
  - Backwards-compat re-export of `main` so `from automil.cli import main` still resolves
  - Zero behavior change to user-facing `automil <subcommand>` invocations
affects:
  - phase-00-other-plans
  - phase-01-registry
  - phase-02-backends
  - phase-03-multi-runtime

tech-stack:
  added: []
  patterns:
    - "Per-command-group fine CLI package layout (D-01): one module per command/lifecycle-pair"
    - "Subgroup name= keyword to decouple Click name from Python identifier (orchestrator_group, viz_group)"
    - "Module-level register-on-import: __init__.py imports sibling modules for side-effect Click registration"

key-files:
  created:
    - src/automil/cli/__init__.py
    - src/automil/cli/_helpers.py
    - src/automil/cli/submit.py
    - src/automil/cli/init.py
    - src/automil/cli/check.py
    - src/automil/cli/propose.py
    - src/automil/cli/reconcile.py
    - src/automil/cli/status.py
    - src/automil/cli/control.py
    - src/automil/cli/orchestrator.py
    - src/automil/cli/viz.py
    - src/automil/cli/lifecycle.py
  modified: []
  deleted:
    - src/automil/cli.py

key-decisions:
  - "Single CLN-06 commit per D-20, not per-task; all 3 plan tasks ship as one atomic refactor commit because intermediate states (cli.py + cli/ co-existing or cli/ with empty stubs) are knowingly broken"
  - "Path(__file__).parent.parent in init.py to reach automil/templates and automil/claude_assets — the package was the parent before; now cli/ is a subpackage so resources need one more level up"
  - "Click subgroup name= keyword (name='orchestrator', name='viz') with Python identifier orchestrator_group/viz_group avoids module-vs-callable shadowing"
  - "lifecycle.py ships as a 12-line empty stub today so Phase 1 commands land additively without restructuring __init__.py"

patterns-established:
  - "Pattern 1: Each per-command file is <300 lines (D-03) — submit.py is the largest at 267 lines; everything else <130 lines"
  - "Pattern 2: Lazy heavy imports stay inside command bodies (e.g., `from automil.graph import ExperimentGraph`) preserved verbatim from cli.py"
  - "Pattern 3: Path-validation guards in cli/submit.py copied byte-identical from cli.py:347-365 — security-sensitive code, no behavior change"

requirements-completed: [CLN-01, CLN-06]

duration: 5min
completed: 2026-05-01
---

# Phase 00 Plan 01: CLI Split Summary

**Split the 725-line src/automil/cli.py monolith into a 12-file src/automil/cli/ package using per-command-group, fine organisation; all 62 tests green; user-facing CLI byte-identical.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-01T13:50:06Z
- **Completed:** 2026-05-01T13:55:34Z
- **Tasks:** 3 (executed as single atomic commit per D-20)
- **Files created:** 12
- **Files deleted:** 1 (cli.py)

## Accomplishments

- src/automil/cli.py (725 lines) deleted; replaced by src/automil/cli/ package with 12 files
- All 62 existing tests pass green at the commit boundary (CCRCC test count is 62, plan-time count was 48 — refactor preserved every assertion)
- `from automil.cli import main` continues to resolve via package __init__.py re-export (D-02 backwards-compat)
- `uv run automil --help` lists every original command: submit, init, check, propose, rank, reconcile, status, start-loop, stop-loop, orchestrator, viz
- `uv run automil orchestrator --help` and `uv run automil viz --help` expose the same start/stop/status subcommands as before
- No file in src/automil/cli/ exceeds 300 lines (D-03): submit.py = 267 (largest), every other module <130 lines
- cli/lifecycle.py shipped as empty Phase 1 placeholder so future plans land additively without touching __init__.py
- Path-validation guards in cli/submit.py copied byte-identical from cli.py:347-365 (T-00-01 mitigation per threat model)
- automil_rel + .claude/ exclusion in cli/submit.py copied byte-identical (T-00-03 mitigation)

## Task Commits

Per D-20 the entire plan ships as ONE refactor commit, not three. The plan's task structure was conceptual/staged for clarity, not commit cadence:

1. **Tasks 1+2+3 (CLI split + delete cli.py)** — `01fbee2` refactor(00-01): split cli.py into per-command-group cli/ package

## Files Created/Modified

**Created (12 files, 841 total lines incl. blanks):**

| File | Lines | Role |
|------|-------|------|
| `src/automil/cli/__init__.py` | 31 | Click main group + re-export of `main`; sibling-module imports for register-on-import |
| `src/automil/cli/_helpers.py` | 58 | `_find_automil_dir`, `_find_git_root`, `_matches_scope` (verbatim from cli.py:18-65) |
| `src/automil/cli/submit.py` | 267 | submit command (verbatim semantic copy from cli.py:188-437; largest file, well under 300-line cap) |
| `src/automil/cli/init.py` | 127 | init command (verbatim from cli.py:73-185, with `Path(__file__).parent.parent` for templates/claude_assets resource resolution) |
| `src/automil/cli/check.py` | 97 | check command (verbatim from cli.py:569-652; Plan 03/05 will extend) |
| `src/automil/cli/propose.py` | 77 | propose + rank commands paired by lifecycle (verbatim from cli.py:440-507) |
| `src/automil/cli/reconcile.py` | 28 | reconcile command (verbatim from cli.py:510-524; Plan 07 adds `--recompute-best`) |
| `src/automil/cli/status.py` | 29 | status command (verbatim from cli.py:527-546) |
| `src/automil/cli/control.py` | 34 | start-loop + stop-loop (verbatim from cli.py:549-566); reserves space for Phase 2 cancel/resubmit |
| `src/automil/cli/orchestrator.py` | 43 | orchestrator subgroup (start/stop/status); uses `name="orchestrator"` keyword |
| `src/automil/cli/viz.py` | 38 | viz subgroup (start/stop/status); uses `name="viz"` keyword |
| `src/automil/cli/lifecycle.py` | 12 | empty Phase 1 placeholder |

**Deleted:**

- `src/automil/cli.py` (725 lines) — fully replaced by the package

## Decisions Made

- **Single commit, not per-task** (D-20): The plan's intermediate states are knowingly broken (cli.py + cli/__init__.py co-exist; or cli/ with stubs and no commands registered). Committing those would leave the test suite red. The plan explicitly calls out this single-commit cadence in Task 3 Step 6.
- **`Path(__file__).parent.parent` in init.py** for resolving `templates/` and `claude_assets/`: the original cli.py lived at `automil/` so `parent` was `automil/`. After the split, `cli/init.py` lives at `automil/cli/` so `parent.parent` = `automil/`. This is purely a location-correction; no semantic change. Tests covering init (test_creates_automil_subdir, test_no_train_py_or_prepare_py, test_check_*) all passed, confirming templates and claude_assets still resolve correctly.
- **Click subgroup `name=` keyword** (`@main.group(name="orchestrator")` + `def orchestrator_group()`) avoids the Python-identifier-vs-module-name collision: `automil.cli.orchestrator` is now a module path, so the callable can't share the name. User-facing `automil orchestrator <sub>` is preserved exactly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resource path resolution after package nesting**
- **Found during:** Task 2 (init.py migration)
- **Issue:** `Path(__file__).parent / "templates"` and `Path(__file__).parent / "claude_assets"` would resolve to `src/automil/cli/templates/` and `src/automil/cli/claude_assets/` after the split — but those resources actually live one level up at `src/automil/templates/` and `src/automil/claude_assets/`. The original cli.py was at `src/automil/cli.py` so `parent` was `src/automil/`.
- **Fix:** Replaced both occurrences with `Path(__file__).parent.parent` in `cli/init.py:48` (`templates_dir`) and `cli/init.py:69` (`package_dir`).
- **Verification:** `tests/test_cli.py::TestInit::test_creates_automil_subdir` and `test_no_train_py_or_prepare_py` both pass post-fix; without the fix they would FileNotFoundError on jinja template loading.
- **Committed in:** 01fbee2 (the single plan commit)

**2. [Rule 1 - Cleanup] Reverted unrelated uv.lock side-effect**
- **Found during:** Final pre-commit `git status`
- **Issue:** `uv run pytest` rewrote `uv.lock` to use absolute path for the local `trident` package (`benchmarks/lib/TRIDENT` → `/home/jma/.../benchmarks/lib/TRIDENT`). This is a uv-in-worktree side effect, not part of the CLI split.
- **Fix:** `git checkout -- uv.lock` before staging.
- **Verification:** `git status` shows only intended cli.py deletion + cli/ additions in the commit.
- **Committed in:** N/A (excluded from commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug, 1 Rule 1 cleanup)
**Impact on plan:** Both fixes were necessary for correctness/cleanliness. No scope creep. The init.py fix is a direct consequence of moving from a top-level module to a subpackage and is plan-anticipated (the plan said "no semantic change" — the resource-path fix preserves that semantic).

## Issues Encountered

- **Worktree base mismatch at startup:** Worktree branch was created at `137aa70` (an older commit on main) instead of the plan's expected base `edcfcf6`. Reset --hard to the correct base before starting per the worktree_branch_check protocol; safe because no agent work had been done yet.
- **Co-existence of cli.py + cli/:** Python's import system prefers a package over a same-named module. The plan's Task 1 (creating cli/__init__.py while cli.py remains) would have left cli.py unreachable for the duration of Tasks 1-2. Solved by following the plan's D-20 single-commit instruction: build the entire cli/ package, delete cli.py, run tests, commit once. No intermediate broken state ever sees the test runner.

## User Setup Required

None — restructure-only refactor; no environment, dependencies, or external services changed.

## Next Phase Readiness

**Ready for parallel-wave plans 00-02 and 00-04** (file-disjoint by plan design — those touch `orchestrator.py` and tests; this plan only touched `cli.py` → `cli/`).

**Ready for Phase 1 (Variant Registry)** to add `apply`, `revert-baseline`, `port-variant`, `promote-variant`, `refresh-registry` to `cli/lifecycle.py` without touching `cli/__init__.py` structurally.

**Ready for Phase 2 (Backend ABC)** to add `cancel`, `resubmit` to `cli/control.py` (placeholder comment already in place).

**Ready for Phase 0 Plan 07 (CLI-07)** to add `--recompute-best` flag to `cli/reconcile.py`.

## Self-Check: PASSED

**Created files exist:**
- src/automil/cli/__init__.py — FOUND
- src/automil/cli/_helpers.py — FOUND
- src/automil/cli/submit.py — FOUND (267 lines)
- src/automil/cli/init.py — FOUND
- src/automil/cli/check.py — FOUND
- src/automil/cli/propose.py — FOUND
- src/automil/cli/reconcile.py — FOUND
- src/automil/cli/status.py — FOUND
- src/automil/cli/control.py — FOUND
- src/automil/cli/orchestrator.py — FOUND
- src/automil/cli/viz.py — FOUND
- src/automil/cli/lifecycle.py — FOUND

**Deleted file:**
- src/automil/cli.py — confirmed absent (`test ! -f src/automil/cli.py` succeeds)

**Commit exists:**
- 01fbee2 — FOUND in `git log --oneline -1`

**Verification commands (all PASS):**
- `uv run pytest tests/ -v` → 62 passed
- `python -c "from automil.cli import main; print(main.name)"` → prints `main`
- `uv run automil --help` → lists all 11 commands (submit, init, check, propose, rank, reconcile, status, start-loop, stop-loop, orchestrator, viz)
- `for f in src/automil/cli/*.py; do wc -l "$f"; done` → all ≤ 300 lines (max 267 in submit.py)
- `test ! -f src/automil/cli.py` → exits 0
- `git log --oneline -1` → `01fbee2 refactor(00-01): split cli.py into per-command-group cli/ package`

---
*Phase: 00-tier-2-cleanup-cli-split-compat-shim*
*Completed: 2026-05-01*
