---
phase: "03"
plan: "03-10"
subsystem: "agent_assets / cli / templates"
tags: [trajectory, hooks, claude-code, opencode, codex, runtime-integration, gitignore]
dependency_graph:
  requires: ["03-07", "03-09"]
  provides: ["claude-hook-trajectory", "opencode-ts-plugin", "codex-readme", "init-hook-install", "gitignore-trajectory"]
  affects: ["03-11"]
tech_stack:
  added: ["TypeScript/Bun plugin (automil-trajectory.ts — only TS file in codebase)"]
  patterns: ["stdin hook delivery (HOOK_EVENT=$(cat))", "Bun $ shell API soft-fail (.nothrow())", "tool.execute.after plugin hook"]
key_files:
  created:
    - src/automil/agent_assets/opencode/plugins/automil-trajectory.ts
    - src/automil/agent_assets/codex/README.md
  modified:
    - src/automil/agent_assets/claude/hooks/on_stop.sh
    - src/automil/cli/init.py
    - src/automil/templates/.gitignore.j2
decisions:
  - "D-96 CORRECTED: Claude Code delivers hook payload on stdin; HOOK_EVENT=$(cat) is the only correct read mechanism — NOT an env var"
  - "D-95: opencode integration is TypeScript/Bun plugin (tool.execute.after), not a shell hook — opencode has no shell hook API"
  - "D-98: trajectory files gitignored by default; automil trajectory export is the share pathway"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03"
  tasks_completed: 6
  files_created: 2
  files_modified: 3
---

# Phase 03 Plan 10: Runtime Hook Integration (Claude Code + opencode) + gitignore Extension Summary

## One-liner

Claude Code stdin hook + opencode Bun TypeScript plugin both wired to `automil trajectory record` with soft-fail discipline; codex CLI-fallback documented; gitignore extended with 3 trajectory patterns.

## What Was Built

### T-03-10-01: Extended `agent_assets/claude/hooks/on_stop.sh`
Extended the existing `.automil_active` guard script to also capture trajectory events. The critical fix (D-96 CORRECTED): Claude Code delivers hook payload on **stdin**, read via `HOOK_EVENT="$(cat)"` — NOT via an environment variable. Trajectory recording fires only when `AUTOMIL_NODE_ID`, `AUTOMIL_RUNTIME`, and `HOOK_EVENT` are all non-empty (orchestrated sessions only). Soft-fail via `|| true` so a recorder error never breaks Claude Code's hook chain.

### T-03-10-02: Created `agent_assets/opencode/plugins/automil-trajectory.ts`
The only TypeScript file in the codebase. opencode runs on Bun and supports only TypeScript plugins (no shell hook API). The plugin uses `tool.execute.after` — fires after each tool execution — and Bun's `$` shell API to invoke `automil trajectory record`. Soft-fail via `.nothrow()`. If `AUTOMIL_NODE_ID` is absent (non-orchestrated session), the plugin returns immediately without recording.

### T-03-10-03: Created `agent_assets/codex/README.md`
Documents CLI-fallback trajectory capture for Codex. Codex's hook API is unstable as of 2026-05 (D-100); Phase 3 delivers documentation only. Phase 4 target for native Codex hook integration.

### T-03-10-04: Extended `cli/init.py` opencode block
`automil init --runtime opencode` now copies `automil-trajectory.ts` to `.opencode/plugins/` in addition to installing AGENTS.md. Creates the `plugins/` subdirectory automatically. Prints installation confirmation.

### T-03-10-05: Extended `templates/.gitignore.j2`
Added 3 trajectory gitignore patterns per D-98:
- `archive/*/trajectory.jsonl`
- `archive/*/trajectory.*.jsonl`
- `archive/*/trajectory.err.log`

## Commits

| Hash | Message |
|------|---------|
| e3f7e59 | feat(03-10): Claude hook + opencode TS plugin + codex README + gitignore trajectory entries (TRJ-04, TRJ-05) |

## Deviations from Plan

None — plan executed exactly as written. All 5 implementation tasks completed in a single atomic commit per plan spec.

## Test Results

- 514 passed, 9 skipped — baseline maintained exactly (Phase 0+1+2 baseline)
- No regressions introduced by asset-only changes

## Known Stubs

None. All files are complete implementations, not placeholders.

## Threat Flags

No new security-relevant surface beyond what the plan's threat model covers (T-03-10-S01 through T-03-10-S04).

## Self-Check: PASSED

Files exist:
- FOUND: src/automil/agent_assets/claude/hooks/on_stop.sh
- FOUND: src/automil/agent_assets/opencode/plugins/automil-trajectory.ts
- FOUND: src/automil/agent_assets/codex/README.md
- FOUND: src/automil/cli/init.py (modified)
- FOUND: src/automil/templates/.gitignore.j2 (modified)

Commit exists: e3f7e59 confirmed in git log.
