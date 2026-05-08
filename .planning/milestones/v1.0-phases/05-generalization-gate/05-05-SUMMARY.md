---
phase: 05-generalization-gate
plan: "05"
subsystem: trajectory/redactor + cli/propose
tags: [held-out-isolation, redaction, rank-filter, D-139, GTE-01, Pitfall-6c]
dependency_graph:
  requires: []
  provides:
    - trajectory.redactor._held_out_ids_cached (mtime-keyed lru_cache)
    - trajectory.redactor.redact() held-out ID substitution
    - cli.propose.rank --include-held-out flag
    - cli.propose.rank default held-out filter
  affects:
    - automil rank (CLI output filtered for agent safety)
    - trajectory.jsonl (held-out IDs replaced with <HELD_OUT>)
tech_stack:
  added: []
  patterns:
    - mtime-keyed lru_cache for graph.json held-out ID lookup
    - Dynamic redaction appended after static _PATTERNS loop
    - graph._data["nodes"] dict comprehension filter before rank_proposals
key_files:
  created:
    - tests/trajectory/test_redactor_held_out.py
    - tests/test_rank_held_out_filter.py
  modified:
    - src/automil/trajectory/redactor.py
    - src/automil/cli/propose.py
decisions:
  - "mtime-keyed lru_cache(maxsize=1) chosen over TTL cache: graph.json mtime is the natural invalidation signal; avoids stale-read window except within a single event-capture tick"
  - "graph._data['nodes'] mutated in-place before rank_proposals(); graph.save() never called by rank — no persistence side-effect"
  - "Soft-fail discipline: _held_out_ids() returns frozenset() on any exception so redact() degrades gracefully to static-only mode when no project is found"
metrics:
  duration: "~22 minutes"
  completed_date: "2026-05-06T00:51:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 2
---

# Phase 05 Plan 05: Held-out Isolation (D-139 / Pitfall-6c) Summary

**One-liner:** mtime-cached held-out node-ID redaction in trajectory + default-on rank filter defending Pitfall-6c held-out leak into agent loop.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | redactor held-out tests | 488e294 | tests/trajectory/test_redactor_held_out.py |
| 1 (GREEN) | redactor implementation | f1ed2cd | src/automil/trajectory/redactor.py, tests/trajectory/test_redactor_held_out.py |
| 2 (RED) | rank filter tests | 6bf963a | tests/test_rank_held_out_filter.py |
| 2 (GREEN) | rank filter implementation | 1f56928 | src/automil/cli/propose.py, tests/test_rank_held_out_filter.py |

## What Was Built

### Task 1: redactor.py held-out node-id substitution

Extended `src/automil/trajectory/redactor.py` with three additions:

1. `_NODE_ID_RE = re.compile(r"\bnode_\d{4,}\b")` — matches any node ID pattern.
2. `_held_out_ids_cached(graph_mtime: float) -> frozenset` — `@functools.lru_cache(maxsize=1)` keyed by `graph.json` mtime; reads `automil/graph.json`, returns IDs where `metadata.held_out=True`. Soft-fail returns `frozenset()` on any exception.
3. `_held_out_ids() -> frozenset` — dispatches to cache after reading current mtime; returns `frozenset()` when no project found.
4. `redact(s)` extended: after static `_PATTERNS` loop, calls `_held_out_ids()` and substitutes `<HELD_OUT>` for any matched ID in the held-out set.

The existing `redact_event` and `_walk` call `redact()` for all string leaves — no changes needed there.

### Task 2: cli/propose.py rank --include-held-out

Extended `rank()` command in `src/automil/cli/propose.py`:

1. Added `--include-held-out` flag (`is_flag=True, default=False`).
2. When flag is absent: filters `graph._data["nodes"]` to remove `metadata.held_out=True` nodes before `rank_proposals()`.
3. When flag is present: logs `WARNING` citing D-139 ("this MUST NOT be used during the agent search loop").
4. `graph.save()` is never called — no persistence side-effect.

## Test Results

- `tests/trajectory/test_redactor_held_out.py`: 7 new tests — all pass
- `tests/test_rank_held_out_filter.py`: 5 new tests — all pass
- `tests/trajectory/` full suite: 91 tests pass (84 existing + 7 new)
- Full suite: **712 passed, 9 skipped** — no regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test string too short for sk- pattern**
- **Found during:** Task 1 GREEN verification
- **Issue:** `sk-secret1234567890key` is only 19 chars after prefix; `_PATTERNS[0]` requires 20+. Test 7 assertion `assert "sk-[REDACTED]" in result` failed.
- **Fix:** Changed to `sk-secretsecret12345678key` (21 chars after prefix).
- **Files modified:** tests/trajectory/test_redactor_held_out.py
- **Commit:** f1ed2cd

**2. [Rule 1 - Bug] Test fixture used wrong node type/status**
- **Found during:** Task 2 RED → GREEN transition
- **Issue:** `rank_proposals()` only returns `type="proposed"`, `status="pending"` nodes. Initial fixture used `type="executed"`, `status="keep"` — test nodes never appeared in output.
- **Fix:** Changed fixture nodes to `type="proposed"`, `status="pending"` and added `scoring` key to graph `meta` (required by `recalculate_scores()`).
- **Files modified:** tests/test_rank_held_out_filter.py
- **Commit:** 6bf963a → 1f56928

**3. [Rule 1 - Bug] max-per-branch capped output to 2 nodes**
- **Found during:** Task 2 GREEN verification
- **Issue:** Default `max_per_branch=2` with all 3 nodes under `parent_id="root"` limited output to 2 nodes. Test 2 expected all 3.
- **Fix:** Passed `--max-per-branch 10` in tests 2 and 3 to decouple from branch-cap behavior.
- **Files modified:** tests/test_rank_held_out_filter.py
- **Commit:** 1f56928

## Known Stubs

None — both implementations are fully wired.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond those described in the plan's threat model (T-05-05-01..05).

## Self-Check: PASSED

Files exist:
- [x] `src/automil/trajectory/redactor.py` — FOUND, contains `<HELD_OUT>`, `_held_out_ids_cached`, `_NODE_ID_RE`
- [x] `src/automil/cli/propose.py` — FOUND, contains `include-held-out`, `D-139`
- [x] `tests/trajectory/test_redactor_held_out.py` — FOUND (161 lines)
- [x] `tests/test_rank_held_out_filter.py` — FOUND (153 lines)

Commits exist:
- [x] 488e294 — test(05-05): add failing tests for held-out node-id redaction (RED)
- [x] f1ed2cd — feat(05-05): extend redactor with held-out node-id placeholder (GREEN)
- [x] 6bf963a — test(05-05): add failing tests for rank --include-held-out filter (RED)
- [x] 1f56928 — feat(05-05): add --include-held-out flag to rank command (GREEN)
