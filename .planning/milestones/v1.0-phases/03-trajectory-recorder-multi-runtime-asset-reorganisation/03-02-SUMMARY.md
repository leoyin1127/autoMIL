---
phase: "03"
plan: "03-02"
subsystem: "agent_assets"
tags: ["git-mv", "migration", "compat", "multi-runtime", "MRT-01", "MRT-06"]
dependency_graph:
  requires: []
  provides:
    - "src/automil/agent_assets/_shared/skills/automil/SKILL.md"
    - "src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md"
    - "src/automil/agent_assets/claude/hooks/on_stop.sh"
    - "src/automil/agent_assets/_shared/AGENTS.md"
    - "src/automil/agent_assets/deepseek/README.md"
    - "automil.claude_assets live __getattr__ shim in compat.py"
  affects:
    - "src/automil/cli/init.py"
    - "tests/test_compat.py"
tech_stack:
  added: []
  patterns:
    - "PEP 562 module __getattr__ shim for deprecated import paths"
    - "git mv for blame-preserving directory rename"
key_files:
  created:
    - src/automil/agent_assets/__init__.py
    - src/automil/agent_assets/claude/__init__.py
    - src/automil/agent_assets/_shared/AGENTS.md
    - src/automil/agent_assets/deepseek/README.md
    - src/automil/agent_assets/opencode/.gitkeep
    - src/automil/agent_assets/codex/.gitkeep
    - src/automil/agent_assets/deepseek/.gitkeep
  modified:
    - src/automil/compat.py
    - src/automil/cli/init.py
    - tests/test_compat.py
  renamed:
    - "src/automil/claude_assets/skills/automil/SKILL.md → src/automil/agent_assets/_shared/skills/automil/SKILL.md"
    - "src/automil/claude_assets/skills/automil-setup/SKILL.md → src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md"
    - "src/automil/claude_assets/hooks/on_stop.sh → src/automil/agent_assets/claude/hooks/on_stop.sh"
decisions:
  - "D-88: git mv used (not cp+rm) to preserve blame history on SKILL.md and on_stop.sh"
  - "D-88 step 7: automil.claude_assets promoted from _PLANNED_MIGRATIONS to live __getattr__ shim"
  - "D-90: _shared/AGENTS.md written with canonical multi-runtime instruction content"
  - "MRT-06: deepseek/README.md documents DeepSeek as model routed via opencode/Codex"
  - "Preliminary init.py path patch: agent_src + _shared/skills + claude/hooks (full runtime-aware rewrite deferred to 03-07)"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-03"
  tasks_completed: 4
  files_modified: 13
---

# Phase 03 Plan 02: agent_assets/ Migration (git mv) + compat.py Promotion Summary

**One-liner:** `git mv claude_assets→agent_assets` with blame-preserved skeleton, canonical AGENTS.md, deepseek model doc, and live PEP 562 compat shim for `automil.claude_assets`.

## What Was Built

1. **`git mv` migration (T-03-02-01)** — Three-step rename with full blame preservation:
   - `claude_assets/skills/automil` → `agent_assets/_shared/skills/automil`
   - `claude_assets/skills/automil-setup` → `agent_assets/_shared/skills/automil-setup`
   - `claude_assets/hooks` → `agent_assets/claude/hooks`
   - Created `{opencode,codex,deepseek}/.gitkeep` + `__init__.py` package markers
   - Removed empty `claude_assets/` directory

2. **`_shared/AGENTS.md` + `deepseek/README.md` (T-03-02-02)** — Canonical multi-runtime instruction file per D-90; DeepSeek model documentation per MRT-06.

3. **`compat.py` promotion (T-03-02-03)** — Promoted `automil.claude_assets` from `_PLANNED_MIGRATIONS` to a live module-level `__getattr__` shim following the PEP 562 / orchestrator.py pattern. Dunder probe short-circuit prevents flooding test output. Updated `tests/test_compat.py` with `not in _PLANNED_MIGRATIONS` assertion and new `test_claude_assets_shim_emits_deprecation_warning`.

4. **Preliminary `init.py` path patch (T-03-02-03/04)** — Updated `cli/init.py` to point `agent_src`, `skills_src`, and `hooks_src` at the new `agent_assets/` paths so `automil init` continues to install skills and hooks. Full `--runtime` flag rewrite deferred to Plan 03-07.

## Verification Results

| Check | Result |
|-------|--------|
| `grep -r "claude_assets" src/automil/ --include="*.py" -l \| grep -v compat.py \| wc -l` | 0 |
| `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/agent_assets/` | empty (OK) |
| `ls src/automil/agent_assets/_shared/skills/automil/SKILL.md` | exists |
| `ls src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md` | exists |
| `ls src/automil/agent_assets/claude/hooks/on_stop.sh` | exists |
| `grep -i model deepseek/README.md` | DeepSeek is a **model** |
| `uv run pytest tests/test_compat.py -v` | 5 passed |
| `uv run pytest tests/ -x -q` | **426 passed, 9 skipped** (baseline +1 new test) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Preliminary init.py path patch**
- **Found during:** T-03-02-04 hard-floor grep verification
- **Issue:** `cli/init.py` still referenced `claude_assets` at line 90 (`claude_src = package_dir / "claude_assets"`). Since the directory was removed by the migration, `claude_src.exists()` would return `False` and `automil init` would silently skip installing skills and hooks — breaking the primary user-facing workflow.
- **Fix:** Updated `claude_src` → `agent_src`, `skills_src` to `agent_src / "_shared" / "skills"`, and `hooks_src` to `agent_src / "claude" / "hooks"`. Comment avoids the `claude_assets` string to satisfy the hard-floor grep. Full `--runtime` overhaul deferred to 03-07.
- **Files modified:** `src/automil/cli/init.py`
- **Commit:** 1988656

## Known Stubs

None. All content is wired. The `_shared/AGENTS.md` and `deepseek/README.md` contain their final canonical content per D-90 and MRT-06.

## Threat Flags

None. No new network endpoints, auth paths, or trust-boundary schema changes introduced.

## Self-Check: PASSED

- `src/automil/agent_assets/_shared/skills/automil/SKILL.md` — FOUND
- `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md` — FOUND
- `src/automil/agent_assets/claude/hooks/on_stop.sh` — FOUND
- `src/automil/agent_assets/_shared/AGENTS.md` — FOUND
- `src/automil/agent_assets/deepseek/README.md` — FOUND
- `src/automil/agent_assets/{opencode,codex,deepseek}/.gitkeep` — FOUND
- Commit 1988656 — FOUND
- `uv run pytest tests/ -x -q` — 426 passed, 9 skipped
