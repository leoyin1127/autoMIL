---
phase: "03"
plan: "03-08"
subsystem: "cli/agent_assets"
tags: ["cli", "show-skill", "multi-runtime", "MRT-04", "D-93"]
dependency_graph:
  requires: ["03-05"]
  provides: ["show-skill CLI command", "runtime skill inspection"]
  affects: ["src/automil/cli/__init__.py"]
tech_stack:
  added: []
  patterns: ["lazy-import inside Click command body", "click.Choice runtime gating", "pipeable stdout via nl=False"]
key_files:
  created:
    - src/automil/cli/show_skill.py
    - tests/agent_assets/test_show_skill.py
  modified:
    - src/automil/cli/__init__.py
decisions:
  - "show_skill registered between resubmit and status (sh < st alphabetically)"
  - "SKILL asset resolves to _shared/skills/automil/SKILL.md (not _shared/SKILL.md) per plan spec"
  - "deepseek-via-X routes overlay lookup to base runtime dir (opencode or codex)"
metrics:
  duration: "4m"
  completed: "2026-05-03"
  tasks_completed: 4
  files_changed: 3
---

# Phase 03 Plan 08: `automil show-skill --runtime` Command Summary

## One-Liner

Read-only `show-skill` CLI command renders merged per-runtime SKILL.md or AGENTS.md to stdout via lazy `merge_skill()` call; pipeable with no trailing newline.

## What Was Built

`src/automil/cli/show_skill.py` — a Click command registered on `main` as `"show-skill"`:
- `--runtime` (required): `click.Choice` over `["claude", "opencode", "codex", "deepseek-via-opencode", "deepseek-via-codex"]`
- `--asset` (default `SKILL`): `click.Choice(["SKILL", "AGENTS"])`, `show_default=True`
- Lazy import of `merge_skill` from `automil.agent_assets._overlay` inside the command body (D-69 / PATTERNS §8)
- SKILL asset resolves to `_shared/skills/automil/SKILL.md`; AGENTS resolves to `_shared/AGENTS.md`
- `deepseek-via-X` extracts the base runtime for overlay path lookup
- `click.ClickException` raised if shared asset path is missing
- `click.echo(result, nl=False)` — pipeable, no extra trailing newline (D-93)
- No write side-effects

Registration in `src/automil/cli/__init__.py`: `from automil.cli import show_skill  # noqa: E402,F401  (MRT-04 / D-93)` inserted alphabetically between `resubmit` and `status` (sh < st).

`tests/agent_assets/test_show_skill.py` — 7 tests via `CliRunner`:
- `test_show_skill_claude_stdout`: exit 0, `#` in output, len > 20
- `test_show_skill_opencode_stdout`: exit 0, `#` in output
- `test_show_skill_agents_asset`: exit 0, `"automil submit"` in output
- `test_show_skill_no_write_side_effects`: `tmp_path` unchanged after invocation
- `test_show_skill_pipeable_no_trailing_newline`: no double `\n\n` at end
- `test_show_skill_deepseek_via_opencode`: exit 0, `#` in output
- `test_show_skill_missing_runtime_arg`: exit code != 0

## Verification Results

```
tests/agent_assets/test_show_skill.py — 7 passed in 0.21s
Full suite: 491 passed, 9 skipped (baseline 484 + 9 skipped → +7 new, no regressions)
uv run automil show-skill --runtime claude | head -5 → markdown frontmatter output
```

## Commits

| Task | Commit | Files |
|------|--------|-------|
| T-03-08-01/02/03 | 9cb120e | src/automil/cli/show_skill.py, src/automil/cli/__init__.py, tests/agent_assets/test_show_skill.py |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The command reads live package assets from `agent_assets/_shared/` which exist on disk.

## Threat Flags

None. `--runtime` uses `click.Choice` with fixed valid values; no user-provided path components can cause traversal (T-03-08-S01 mitigated by construction). SKILL.md content is version-controlled, not runtime-generated (T-03-08-S02 accepted per plan).

## Self-Check: PASSED

- [x] `src/automil/cli/show_skill.py` exists
- [x] `src/automil/cli/__init__.py` has `from automil.cli import show_skill` 
- [x] `tests/agent_assets/test_show_skill.py` exists with 7 tests
- [x] Commit 9cb120e exists: `git log --oneline | head -1` → `9cb120e feat(03-08): automil show-skill --runtime command (MRT-04)`
- [x] 491 passed, 9 skipped — no regressions
