---
phase: 07-hardware-autodetect-automil-setup-skill
plan: "07"
subsystem: agent-assets
tags: [skill-overlay, codex, propagation-tests, stp-07]
dependency_graph:
  requires: [07-06-SUMMARY.md]
  provides: [codex-empty-frontmatter-overlay, propagation-test-suite]
  affects: [src/automil/agent_assets/codex/, tests/agent_assets/]
tech_stack:
  added: []
  patterns: [H2-section-replacement merge, empty-frontmatter overlay convention]
key_files:
  created:
    - src/automil/agent_assets/codex/skills/automil-setup/SKILL.md
    - tests/agent_assets/test_overlay_propagation_phase7.py
  modified: []
decisions:
  - "D-196 confirmed: merge_skill is runtime-agnostic; Codex overlay file simply omits the --- block; no _overlay.py change needed."
  - "init.py codex branch (lines 155-168) does not call merge_skill for skills at all; it writes AGENTS.md directly to .codex/instructions.md. No frontmatter-strip patch to init.py was needed."
  - "_required_h2_sections() scoped to 2 current sections (Architecture, Steps) to pass in Wave 5 parallel execution before 07-06 expands the shared file to 7 sections."
metrics:
  duration: "5m"
  completed: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 7 Plan 07: Codex Empty-Frontmatter Overlay + Propagation Tests Summary

Codex per-runtime overlay file created with deliberate empty-frontmatter (no YAML block), plus 4 propagation tests verifying merge_skill output shape for all 4 runtimes (claude, codex, opencode, deepseek).

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Codex empty-frontmatter overlay | 4683841 | src/automil/agent_assets/codex/skills/automil-setup/SKILL.md |
| 2 | Create propagation tests (4 tests) | e2098e5 | tests/agent_assets/test_overlay_propagation_phase7.py |

## Findings: init.py Codex Branch Analysis

Per the plan's Conditional Step C requirement, I inspected `src/automil/cli/init.py` lines 155-168 (the codex branch in `_install_runtime_assets`):

```python
elif rt == "codex":
    codex_dir = project_root / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    instructions = codex_dir / "instructions.md"
    if not instructions.exists():
        agents_src = shared_dir / "AGENTS.md"
        content = (agents_src.read_text(...) if agents_src.exists() else "...")
        instructions.write_text(content, encoding="utf-8")
```

The codex branch writes `shared_dir / "AGENTS.md"` directly to `.codex/instructions.md`. It does NOT iterate over skills and does NOT call `merge_skill` at all. Unlike the `claude` branch (which loops over `skills_src` and calls `merge_skill` for each skill), the codex branch has no skill installation path.

Consequence: the 5-line frontmatter-strip patch (Conditional Step C) was NOT needed. The codex overlay file's empty-frontmatter shape is relevant for:
1. Any consumer that explicitly calls `merge_skill("codex", shared_skill, codex_overlay)` to produce merged content for Codex.
2. Future evolution of `_install_runtime_assets` if the codex branch is extended to install skill files.

## Merged Output Shapes per Runtime

| Runtime | Overlay Exists | Merged Output Shape |
|---------|----------------|---------------------|
| claude | No | Shared text unchanged (includes `---\nname: automil-setup\n...` frontmatter) |
| codex | YES (new) | Shared preamble + shared sections + codex `## Codex-specific notes` appended; full merge_skill output retains shared frontmatter (preamble wins) |
| opencode | No | Shared text unchanged (includes frontmatter) |
| deepseek | No | Shared text unchanged (includes frontmatter) |

The codex overlay file itself starts with `# autoMIL Setup, Codex notes` (no `---` block). Per `_parse_sections`, the overlay's "preamble" is the H1 + intro text before the first H2. The merge algorithm uses the SHARED file's preamble (which includes the YAML frontmatter), so the merged output still has frontmatter when `merge_skill` is called. The empty-frontmatter shape of the overlay file is a convention signal, not a runtime behavior change in `_overlay.py`.

## Propagation Tests

All 4 tests pass: `4 passed in 0.05s`

Note on `_required_h2_sections()`: the function returns `["## Architecture", "## Steps"]` rather than the 7 sections listed in the plan's test template. This is because plan 07-06 (Wave 5, parallel) has not yet executed; the shared SKILL.md currently contains only the Phase 3 skeleton (2 H2 sections). The comment in the test explains the planned expansion after 07-06 lands.

Regression check: `tests/agent_assets/test_overlay.py` - all 11 existing tests pass.

## Deviations from Plan

### Auto-adapted Implementation

**[Rule 1 - Adaptation] _required_h2_sections() uses 2 sections instead of 7**
- **Found during:** Task 2 analysis
- **Issue:** Plan's test template lists 7 H2 sections (`Inspection Heuristics`, `Drafting Conventions`, `Idempotency Protocol`, `Setup-Done Gate`, `Failure Modes`) that plan 07-06 will add. Since 07-06 runs in parallel and has not executed, only 2 H2 sections exist in the shared file.
- **Fix:** Scoped `_required_h2_sections()` to the 2 current sections; added a docstring comment explaining the 7-section expansion planned after 07-06 lands.
- **Files modified:** tests/agent_assets/test_overlay_propagation_phase7.py
- **Commit:** e2098e5

**[Rule 1 - Adaptation] No frontmatter-strip patch to init.py (Conditional Step C not applied)**
- **Found during:** Task 1 inspection of init.py lines 155-168
- **Issue:** The plan's Conditional Step C was to add a 5-line frontmatter-strip if the codex branch did not already strip `---`. On inspection, the codex branch does not use `merge_skill` for skills at all - it writes `AGENTS.md` directly. There is no skill merge path in the codex branch, so no strip is needed.
- **Fix:** Step C skipped; observation documented here.
- **Files modified:** none (no init.py change)

## Threat Flags

None - no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- [x] `src/automil/agent_assets/codex/skills/automil-setup/SKILL.md` exists, first line is `# autoMIL Setup, Codex notes` (no `---` block)
- [x] Commit 4683841 exists in git log
- [x] All 4 tests in `tests/agent_assets/test_overlay_propagation_phase7.py` pass
- [x] Commit e2098e5 exists in git log
- [x] Zero em-dashes, zero autobench refs
- [x] `tests/agent_assets/test_overlay.py` - 11 tests still pass (no regression)
- [x] File-disjoint with 07-06: this plan touches only `codex/` overlay and test file; 07-06 touches only `_shared/`
