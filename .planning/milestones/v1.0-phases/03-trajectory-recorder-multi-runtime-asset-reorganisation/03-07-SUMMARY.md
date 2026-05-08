---
phase: "03"
plan: "03-07"
subsystem: "cli/init"
tags: ["multi-runtime", "cli", "init", "AGENTS.md", "auto-detect"]
dependency_graph:
  requires: ["03-05"]
  provides: ["automil init --runtime", "automil init --update", "AGENTS.md rendering"]
  affects: ["src/automil/cli/init.py", "src/automil/cli/submit.py"]
tech_stack:
  added: []
  patterns:
    - "Click option with choices for runtime selection"
    - "is_flag for --update bypass pattern"
    - "Auto-detection via directory existence probing"
    - "Per-runtime asset installation helper function"
key_files:
  created:
    - "tests/agent_assets/test_init_runtime.py"
  modified:
    - "src/automil/cli/init.py"
    - "src/automil/cli/submit.py"
decisions:
  - "Excluded AGENTS.md and .opencode/.codex dirs from submit auto-detect (Rule 1 fix)"
  - "Extracted _install_runtime_assets() and _register_claude_hooks() as helpers"
  - "deepseek-via-* runtimes delegate to their base runtime (opencode or codex)"
  - "--update bypasses scaffold (config.yaml/program.md/learnings.md preserved) but re-renders assets"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-03"
  tasks_completed: 4
  files_changed: 3
---

# Phase 03 Plan 07: `automil init --runtime` + `--update` Flag Summary

## One-liner

Extended `automil init` with `--runtime` Click choice option and `--update` flag, implementing D-91 auto-detection, D-92 bypass guard, and D-90 AGENTS.md project-root generation.

## What Was Built

### src/automil/cli/init.py

- Added `--runtime` Click option: choices `[claude, opencode, codex, deepseek-via-opencode, deepseek-via-codex, all]`, default None (auto-detect)
- Added `--update` is_flag: when True, bypasses the `ClickException` already-initialized guard and skips scaffold (config.yaml/program.md/learnings.md), proceeds directly to asset re-install
- Extracted `_register_claude_hooks()` helper from the inline settings.json block
- Extracted `_install_runtime_assets(rt, project_root, package_dir, merge_skill)` helper implementing:
  - `claude`: merges skills via `merge_skill()`, copies hooks, writes `.claude/CLAUDE.md` with `@AGENTS.md` first line, registers stop hook
  - `opencode`: creates `.opencode/AGENTS.md` from `_shared/AGENTS.md`
  - `codex`: creates `.codex/instructions.md` from `_shared/AGENTS.md`
  - `deepseek-via-*`: delegates to base runtime (opencode or codex)
- D-91 auto-detection logic: probes `.claude/`, `.opencode/`, `.codex/` dirs; defaults to claude with banner if none found
- D-90 AGENTS.md generation: writes `_shared/AGENTS.md` content to project root on every init invocation
- Lazy import of `merge_skill` inside command body per D-92

### src/automil/cli/submit.py (Rule 1 auto-fix)

Extended the auto-detect exclusion list: `AGENTS.md` (framework-managed, rendered by init) and `.opencode/`, `.codex/` directories are excluded alongside the existing `automil/` and `.claude/` exclusions. This prevents init-generated files from appearing as changed files in subsequent submit calls.

### tests/agent_assets/test_init_runtime.py

13 integration tests covering:
- Explicit runtimes: claude, opencode, codex, all
- DeepSeek routing: deepseek-via-opencode, deepseek-via-codex
- Auto-detection: single dir, multiple dirs, no dirs (banner + default)
- `--update` bypass: guard check + config.yaml preservation
- AGENTS.md content validation (D-90)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] submit.py auto-detect picks up AGENTS.md as changed file**
- **Found during:** T-03-07-04 full test suite run
- **Issue:** `automil init` now writes `AGENTS.md` to project root (untracked). `submit.py` auto-detect includes `git ls-files --others --exclude-standard` which picks up untracked files. This caused `test_empty_submit_rejected` to fail because AGENTS.md appeared as a "changed file."
- **Fix:** Extended the exclusion filter in submit.py to also exclude `AGENTS.md`, `.opencode/`, and `.codex/` from auto-detect, consistent with the existing `.claude/` exclusion pattern.
- **Files modified:** `src/automil/cli/submit.py`
- **Commit:** bd47bc2 (same task commit)

## Test Results

```
497 passed, 9 skipped (484 baseline + 13 new), 1 warning
```

All 13 new tests in `tests/agent_assets/test_init_runtime.py` pass. No regressions on the 484+9 baseline.

## Acceptance Criteria Verification

- [x] `init.py` has `--runtime` Click option with choices matching D-92
- [x] `init.py` has `--update` is_flag option
- [x] Already-initialized guard is bypassed when `update=True`
- [x] Auto-detection probes `.claude/`, `.opencode/`, `.codex/` existence
- [x] `AGENTS.md` is generated at project root on every init invocation
- [x] `.claude/CLAUDE.md` first line is `@AGENTS.md` for claude runtime
- [x] `.opencode/AGENTS.md` created for opencode runtime
- [x] `.codex/instructions.md` created for codex runtime
- [x] `--runtime all` installs all three runtimes
- [x] `tests/agent_assets/test_init_runtime.py` has 13 tests (>= 8 required)
- [x] `uv run pytest tests/agent_assets/test_init_runtime.py -v` exits 0
- [x] `uv run pytest tests/ -x -q` exits 0 with 497 tests passing

## Self-Check: PASSED

Files exist:
- FOUND: src/automil/cli/init.py
- FOUND: src/automil/cli/submit.py
- FOUND: tests/agent_assets/test_init_runtime.py

Commits exist:
- FOUND: bd47bc2
