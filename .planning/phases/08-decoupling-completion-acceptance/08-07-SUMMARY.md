---
phase: 08-decoupling-completion-acceptance
plan: "07"
subsystem: docs
tags: [documentation, contract, DEC-06, D-204]
dependency_graph:
  requires: ["08-01"]
  provides: ["DEC-06 contract documentation"]
  affects: ["docs/training-script-contract.md", "tests/test_phase8_docs_exist.py"]
tech_stack:
  added: []
  patterns: ["markdown contract documentation", "pytest substring anchor regression"]
key_files:
  created:
    - docs/training-script-contract.md
    - tests/test_phase8_docs_exist.py
  modified: []
decisions:
  - "Used plan's verbatim anchor phrasing for all 6 contract items to coordinate with test assertions"
  - "Em-dash gate passed: zero U+2014 / U+2013 in docs/training-script-contract.md"
  - "Unicode em/en dash literals in test file are string assertion targets, not prose dashes"
metrics:
  duration_minutes: 2
  completed_date: "2026-05-08T03:29:15Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 8 Plan 07: Training-Script Contract Documentation Summary

DEC-06 / D-204 delivered: operator-facing `docs/training-script-contract.md` documenting the 6-item contract every autoMIL-compatible training script must honor, with pytorch skeleton, both SIGTERM patterns, common pitfalls, and cross-links to the schema and sklearn-iris reference.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create docs/training-script-contract.md | 03c978c | docs/training-script-contract.md |
| 2 | Create tests/test_phase8_docs_exist.py | 9002caf | tests/test_phase8_docs_exist.py |

## Artifacts

### docs/training-script-contract.md (253 lines)

8-section structure:

1. Title + overview (framework treats training script as opaque process)
2. The contract (6 numbered items with locked anchor phrasing)
3. Minimal sklearn-iris example (cross-link to examples/sklearn-iris/train.py)
4. Minimal pytorch skeleton (5-line handler pattern + train loop placeholder)
5. SIGTERM handling: Pattern A (register_sigterm_flush multi-fold) + Pattern B (inline signal.signal single-shot)
6. Result.json schema (cross-link to automil/schemas/result.schema.json, minimum payload, full payload example)
7. Required env vars (env.required + env.passthrough yaml block, automil check description)
8. Common pitfalls (2 named: write-after-cleanup, sys.exit without partial)

### tests/test_phase8_docs_exist.py (78 lines)

8 test functions (all passing):

- `test_doc_exists`: file path assertion
- `test_doc_covers_six_contract_items`: all 6 anchor substrings verified
- `test_doc_cross_links_examples_and_schema`: sklearn-iris + schema cross-links
- `test_doc_documents_both_sigterm_patterns`: register_sigterm_flush + signal.signal
- `test_doc_documents_two_named_pitfalls`: Common pitfalls + both named footguns
- `test_doc_references_env_required`: env.required + automil check
- `test_doc_no_em_or_en_dashes`: U+2014 / U+2013 gate
- `test_doc_minimum_length`: >=120 line floor

## Verification Results

```
253  docs/training-script-contract.md
grep 6 contract anchors: all 1 match each
grep examples/sklearn-iris/train.py: 4 matches
grep automil/schemas/result.schema.json: 4 matches
grep register_sigterm_flush: 5 matches
grep signal.signal: 4 matches
grep Common pitfalls: 1 match
grep env.required: 6 matches
em-dash grep: ok (zero matches)
pytest tests/test_phase8_docs_exist.py: 8 passed in 0.03s
```

## Deviations from Plan

None. Plan executed exactly as written. The verbatim body from the plan's `<action>` block was used with content expansion in sections 3 (sklearn-iris), 4 (pytorch), 5 (SIGTERM), 6 (schema), and 7 (env vars) to reach 253 lines while preserving all locked anchor strings.

## Known Stubs

None. The document is purely informational markdown with no data sources to wire.

## Threat Flags

None. Documentation file introduces no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `docs/training-script-contract.md` exists: FOUND
- `tests/test_phase8_docs_exist.py` exists: FOUND
- Commit 03c978c exists: FOUND
- Commit 9002caf exists: FOUND
- 8 tests passing: VERIFIED
