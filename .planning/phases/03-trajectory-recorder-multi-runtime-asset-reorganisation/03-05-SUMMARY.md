---
phase: "03"
plan: "03-05"
subsystem: agent_assets
tags: [overlay, section-replacement, markdown-merge, pure-function, MRT-01]
dependency_graph:
  requires: ["03-02"]
  provides: ["merge_skill() in src/automil/agent_assets/_overlay.py"]
  affects: ["03-07 (init --runtime)", "03-08 (show-skill)"]
tech_stack:
  added: []
  patterns:
    - "H2 regex split (re.MULTILINE) for section-keyed markdown merge"
    - "Pure function with no I/O — all reads via caller-supplied Path arguments"
    - "Ordered dict preserves shared section order; overlay appended in overlay order"
key_files:
  created:
    - src/automil/agent_assets/_overlay.py
    - tests/agent_assets/__init__.py
    - tests/agent_assets/test_overlay.py
  modified: []
decisions:
  - "D-89 implementation: regex H2 split (not AST parser); ~65 lines with docstrings"
  - "Code-block false-split accepted as known limitation; documented in module docstring + dedicated test"
  - "merge_skill(runtime, shared_path, None) returns shared_text unchanged (no-overlay fast path)"
  - "overlay with no H2 sections (preamble-only file) also returns shared_text unchanged"
metrics:
  duration: "~5 minutes"
  tasks_completed: 3
  files_created: 3
  files_modified: 0
  completed_date: "2026-05-04"
---

# Phase 03 Plan 05: Overlay Merger (_overlay.py) + Test Suite Summary

## One-liner

Regex-based H2 section-replacement merger: overlay wins on matching header, shared sections pass through, new overlay sections appended — pure function, no I/O, 95 lines.

## What Was Built

### src/automil/agent_assets/_overlay.py

Pure utility module implementing the D-89 section-replacement merge algorithm:

- `_parse_sections(text) -> (preamble, {header: body})` — splits markdown on `^## ` in MULTILINE mode; returns the preamble (H1 + content before first H2) and an ordered dict of section bodies keyed by exact header text.
- `merge_skill(runtime, shared_path, overlay_path) -> str` — reads shared and overlay files, builds merged result: shared sections in shared order (replaced by overlay where matching), then new-only overlay sections appended. Returns shared text unchanged when overlay_path is None or does not exist. Overlay with no H2 sections also returns shared unchanged.
- Module docstring documents the code-block false-split known limitation.

### tests/agent_assets/__init__.py

Empty package marker.

### tests/agent_assets/test_overlay.py

11 tests covering:

| Test | What it verifies |
|------|-----------------|
| `test_parse_sections_basic` | preamble + two sections correctly split |
| `test_parse_sections_no_h2` | no H2 = empty sections dict |
| `test_merge_skill_no_overlay_returns_shared` | None overlay returns shared unchanged |
| `test_merge_skill_nonexistent_overlay_returns_shared` | missing overlay file returns shared unchanged |
| `test_overlay_replaces_matching_section` | matching H2 replaced, non-matching preserved |
| `test_shared_sections_without_override_pass_through` | shared sections with no overlay pass through |
| `test_overlay_appends_new_sections` | novel overlay sections appended after shared; order correct |
| `test_h1_always_from_shared` | result starts with shared H1 title |
| `test_case_sensitive_header_matching` | case mismatch = no replacement + append |
| `test_overlay_empty_h2_sections_returns_shared` | preamble-only overlay returns shared unchanged |
| `test_known_limitation_code_block_false_split` | documents + asserts false-split of `## ` inside fenced code block |

## Deviations from Plan

None — plan executed exactly as written.

The plan specified `~40 lines` for `_overlay.py`; actual implementation is 95 lines including the full module docstring with WARNING block, inline comments, and logger debug calls. The logic itself is ~40 lines as specified; the extra lines are documentation. No functional deviation.

An additional test (`test_overlay_empty_h2_sections_returns_shared`) was added beyond the plan's 8-test minimum to cover the `if not overlay_sections` fast-path in `merge_skill`. This is Rule 2 (missing critical coverage) applied at low cost.

## Known Stubs

None. `merge_skill()` is fully implemented with real logic; no hardcoded empty returns or TODOs in the implementation path.

## Threat Flags

None. `_overlay.py` performs only in-memory string manipulation on caller-supplied Path objects. No new network endpoints, auth paths, or schema changes at trust boundaries.

## Self-Check: PASSED

- `src/automil/agent_assets/_overlay.py` exists: FOUND
- `tests/agent_assets/__init__.py` exists: FOUND
- `tests/agent_assets/test_overlay.py` exists: FOUND
- Commit 064b9e0 exists: FOUND
- `uv run pytest tests/agent_assets/test_overlay.py -v` exits 0: 11/11 passed
- `uv run pytest tests/ -x -q` exits 0: 443 passed, 9 skipped (no regressions)
