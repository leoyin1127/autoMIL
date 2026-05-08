---
phase: "03"
plan: "03-11"
subsystem: "tests/agent_assets"
tags: ["smoke-test", "multi-runtime", "acceptance-gate", "pitfall-3", "D-99"]
dependency_graph:
  requires: ["03-10"]
  provides: ["Phase 3 acceptance gate green", "D-99 full conjunction verified"]
  affects: ["tests/agent_assets/"]
tech_stack:
  added: []
  patterns: ["subprocess.run with stdin payload for real hook script invocation", "venv-local binary resolution via Path(sys.executable).parent / 'automil'"]
key_files:
  created:
    - tests/agent_assets/test_smoke_two_runtimes.py
  modified: []
decisions:
  - "Use Path(sys.executable).parent / 'automil' instead of python -m automil.cli because automil.cli is a package (no __main__.py); the installed binary is co-located with the venv Python"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03"
  tasks_completed: 2
  files_changed: 1
---

# Phase 03 Plan 11: Two-Runtime Smoke Test + Phase 3 Acceptance Gate Summary

One-liner: Phase 3 acceptance gate (D-99) — 9-test suite exercising real `on_stop.sh` stdin contract, opencode plugin static-content check, CLI delivery for both runtimes, forward-compat, and four hard-floor verifications.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| T-03-11-01 | Write `tests/agent_assets/test_smoke_two_runtimes.py` with all 9 tests | 15be5b8 | Done |
| T-03-11-02 | Run acceptance gate + hard floors + full suite | (verified in run) | Done |

## Test Coverage

| Test | REQ | What it proves |
|------|-----|---------------|
| `test_smoke_claude_hook_script` | MRT-05, D-95/D-96 | Real `bash on_stop.sh` stdin contract end-to-end |
| `test_smoke_opencode_plugin_static_content` | MRT-05 | Plugin has `tool.execute.after` + `automil trajectory record` + Bun `$` + `AUTOMIL_RUNTIME` |
| `test_smoke_record_cli_for_runtime[claude_cli]` | MRT-05, TRJ-01 | CLI delivery + runtime metadata correct |
| `test_smoke_record_cli_for_runtime[opencode_cli]` | MRT-05, TRJ-01 | CLI delivery + runtime metadata correct |
| `test_trajectory_metadata_forward_compat[claude-code]` | TRJ-01 | `read_metadata()` v1 forward-compat |
| `test_trajectory_metadata_forward_compat[opencode]` | TRJ-01 | `read_metadata()` v1 forward-compat |
| `test_no_opentelemetry_sdk_installed` | D-106, D-99 conjunct 4 | No OTel SDK runtime dep |
| `test_no_claude_assets_outside_compat` | D-99 conjunct 6 | `claude_assets` only in `compat.py` |
| `test_no_autobench_in_trajectory_or_agent_assets` | TRJ-05, D-99 conjunct 7 | Framework-only modules |

## D-99 Acceptance Gate Verification

| Conjunct | Verification | Result |
|----------|-------------|--------|
| 1. `pytest tests/trajectory/` green | Passes in full suite | PASS |
| 2. `pytest tests/agent_assets/` green | `uv run pytest tests/agent_assets/ -v` | PASS |
| 3. Two-runtime smoke test green | `uv run pytest tests/agent_assets/test_smoke_two_runtimes.py -v` — 9/9 pass | PASS |
| 4. No OTel SDK dep | `python -c "import opentelemetry"` → `ModuleNotFoundError` | PASS |
| 5. Phase 0+1+2 baseline green | `uv run pytest tests/ -x -q` → 523 passed, 9 skipped | PASS |
| 6. `claude_assets` only in compat.py | `grep -r "claude_assets" src/automil/ --include="*.py" -l \| grep -v compat.py \| wc -l` → 0 | PASS |
| 7. No autobench in trajectory/agent_assets | `grep -r "autobench\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/` → no output | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `python -m automil.cli` fails — automil.cli is a package**

- **Found during:** T-03-11-02 first run (`test_smoke_record_cli_for_runtime` failed)
- **Issue:** The plan specified `[sys.executable, "-m", "automil.cli", ...]` but `automil.cli` is a package directory with no `__main__.py`, so Python refuses to execute it directly
- **Fix:** Replaced with `[str(Path(sys.executable).parent / "automil"), ...]` — resolves the `automil` CLI binary co-located with the venv Python interpreter (installed via `pip install -e .`)
- **Files modified:** `tests/agent_assets/test_smoke_two_runtimes.py`
- **Commit:** 15be5b8 (same commit — fixed before first task commit)

## Known Stubs

None. All tests exercise real code paths with real files.

## Threat Flags

None. Test-only file; no new network endpoints, auth paths, or trust-boundary surface introduced.

## Self-Check: PASSED

- `tests/agent_assets/test_smoke_two_runtimes.py` — FOUND
- Commit `15be5b8` — FOUND
- `uv run pytest tests/agent_assets/test_smoke_two_runtimes.py -v` — 9/9 PASSED
- `uv run pytest tests/ -x -q` — 523 passed, 9 skipped, 0 failures
