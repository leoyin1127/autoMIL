---
phase: 07-hardware-autodetect-automil-setup-skill
plan: "06"
subsystem: agent_assets / skills
tags: [skill, setup, idempotency, hardware-probe, setup-done-gate]
dependency_graph:
  requires: [07-02, 07-05]
  provides: [canonical _shared/automil-setup/SKILL.md content]
  affects: [claude/codex/opencode/deepseek overlays via _overlay.py rebuild]
tech_stack:
  added: []
  patterns: [H2 section-replacement merge via _overlay.py, three-way diff idempotency]
key_files:
  created: []
  modified:
    - src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md
decisions:
  - "Consolidated automil submit --max-time 60 onto single line to satisfy grep acceptance check (line-continuation backslash form failed grep pattern)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-07"
---

# Phase 7 Plan 6: Rewrite _shared/automil-setup/SKILL.md Summary

Rewrote `_shared/skills/automil-setup/SKILL.md` from the 122-line Phase 3 skeleton to a 282-line canonical narrative covering all D-189..D-196 content with 7 H2 sections, idempotency protocol, setup-done gate, and six Pitfall 9 mitigations.

## Final Line Count

282 lines (target was ~250; within the 200-300 acceptance band).

## Seven H2 Sections

All seven sections are present at column 0, outside fenced code blocks:

1. `## Architecture` - existing, revised: added hardware report (D-189) note, removed `uv run` prefix per bare-`automil` CLI convention
2. `## Steps` - reorganized into 7 numbered H3 sub-steps covering hardware probe, codebase scope, scaffolding draft, idempotency check, setup-done gate, and baseline establishment
3. `## Inspection Heuristics` - NEW (D-193): 5 heuristics with priority order: training-script glob, framework detection, AST model-class walk, env-var grep, result.json adapter check
4. `## Drafting Conventions` - NEW (D-192): what config.yaml/program.md/variants/ skeleton look like; vram_gb column reference (not peak_vram_mb) for empirical default computation
5. `## Idempotency Protocol` - NEW (D-194): three-way diff via pprint.pformat + difflib.unified_diff; per-section overwrite/keep/merge prompt; silent-no-op invariant
6. `## Setup-Done Gate` - NEW (D-195): Stage 1 automil check, Stage 2 automil submit --max-time 60 with 90-second polling loop
7. `## Failure Modes` - NEW (Pitfall 9 mitigations): six named failure modes with specific recovery actions

## Overlay False-Split Check

```
overlay-safe ok
```

Zero H2 markers inside fenced code blocks. The Idempotency Protocol code block uses Python with no `## ` lines; the bash blocks use `###` comments or none.

## Acceptance Verification Results

| Check | Result |
|-------|--------|
| Line count (200-300) | 282 - PASS |
| H2 section count = 7 | 7 - PASS |
| `automil submit.*--max-time 60` count >= 1 | 1 - PASS |
| `vram_gb` count >= 2 | 3 - PASS |
| Em-dash count = 0 | 0 - PASS |
| Frontmatter name + description preserved | PASS |
| Overlay-safe (no H2 in fenced blocks) | PASS |
| `peak_vram_mb` not used as results.tsv column | PASS (1 occurrence in Heuristic 5: describes what to grep FOR in the training script, not what to read from results.tsv) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Consolidated multiline bash command to single line**
- **Found during:** Task 1 verification
- **Issue:** `automil submit ... \` + `    --files ... --max-time 60` across two lines fails `grep -c "automil submit.*--max-time 60"` (grep matches single lines)
- **Fix:** Moved all flags onto one line within the bash code block
- **Files modified:** `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md`
- **Commit:** 444c450

## Threat Flags

None. This plan only edits instructional markdown content. No new network endpoints, auth paths, file access patterns, or schema changes.

## Known Stubs

None. This is documentation content; no data stubs apply.

## Self-Check: PASSED

- File exists: `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md` - FOUND
- Commit 444c450 exists - FOUND
