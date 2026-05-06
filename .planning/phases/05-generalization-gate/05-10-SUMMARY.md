---
phase: 05-generalization-gate
plan: 10
subsystem: viz-server + cli-status
tags: [gte-06, d-144, promotion-rate, gate-health, viz, cli]
dependency_graph:
  requires: [05-04, 05-07]
  provides: [GTE-06-surfaces]
  affects: [src/automil/viz/server.py, src/automil/cli/status.py]
tech_stack:
  added: []
  patterns: [aiohttp-json-handler, tdd-red-green]
key_files:
  created:
    - tests/test_viz_promotion_rate.py
    - tests/test_status_promotion_rate.py
  modified:
    - src/automil/viz/server.py
    - src/automil/cli/status.py
decisions:
  - Use loop_context from aiohttp.test_utils instead of pytest-asyncio (not installed)
  - Soft-fail pattern: bare except + safe defaults in both surfaces
  - Reads graph.json per-request (no cached counter that can drift)
metrics:
  duration_minutes: 6
  completed_date: "2026-05-06"
  tasks_completed: 2
  files_modified: 4
  commits: 4
requirements: [GTE-06]
---

# Phase 05 Plan 10: viz + status promotion_rate metric surfaces Summary

Surface GTE-06 (promotion-rate metric, D-144) in two operator-facing places: the viz dashboard `/api/promotion-rate` JSON endpoint and `automil status` CLI text output — pure plumbing onto existing graph helpers with no new business logic.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing tests for /api/promotion-rate | eecee7b | tests/test_viz_promotion_rate.py |
| 1 (GREEN) | /api/promotion-rate endpoint implementation | e3dfcc9 | src/automil/viz/server.py |
| 2 (RED) | Failing tests for automil status promotion line | 9b1baae | tests/test_status_promotion_rate.py |
| 2 (GREEN) | Append promotion_rate line to status output | da9480e | src/automil/cli/status.py |

## Verification Results

```
uv run pytest tests/test_viz_promotion_rate.py tests/test_status_promotion_rate.py -v
→ 9/9 passed

uv run pytest tests/ -q --ignore=tests/gate/test_cli_promote.py
→ 763 passed, 9 skipped (pre-existing failure excluded — see Deferred Issues)
```

Acceptance criteria all green:
- `grep -c '"/api/promotion-rate"' src/automil/viz/server.py` → 1
- `grep -c 'def promotion_rate_handler' src/automil/viz/server.py` → 1
- `grep -c 'diagnose_gate_health' src/automil/viz/server.py` → 2
- `grep -c 'window_days' src/automil/viz/server.py` → 2
- `grep -c '"/events"' src/automil/viz/server.py` → 1 (preserved)
- `grep -c 'Promotion rate' src/automil/cli/status.py` → 2
- `grep -c 'diagnose_gate_health' src/automil/cli/status.py` → 2

## Interface Contract Delivered

**HTTP API (viz/server.py):**
```
GET /api/promotion-rate
  Returns: application/json
  {
    "promotion_rate": float,       // 0.0 when no nominations
    "nominated": int,
    "promoted": int,
    "health_diagnostic": str,      // from diagnose_gate_health() or "no data" message
    "window_days": 30
  }
```

**CLI (automil status output):**
```
Promotion rate (30d): 50.0% (2/4) — gate healthy (promotion_rate_30d=50.0%)
  OR
Promotion rate (30d): no data (zero nominations in 30-day window)
```

Both surfaces soft-fail to safe defaults when graph.json is absent.

## Deviations from Plan

### Pre-existing Test Failure (Out of Scope)

`tests/gate/test_cli_promote.py::test_promote_cli_pass_path` was already failing before this plan (confirmed: my commits did not touch `tests/gate/` or `src/automil/gate/` except reading `stats.py`). This is deferred to the owner of plan 05-07/05-09 as it involves `promote()` orchestrator status-field semantics.

Logged to deferred-items: `tests/gate/test_cli_promote.py::test_promote_cli_pass_path` — expects `status='registered'` after gate pass, gets `'keep'`.

### TDD Gate Compliance

RED commit (test): eecee7b (viz), 9b1baae (status)
GREEN commit (feat): e3dfcc9 (viz), da9480e (status)
Both RED→GREEN gate sequences satisfied.

## Known Stubs

None — both surfaces wire to real graph helpers with real data.

## Self-Check: PASSED

- tests/test_viz_promotion_rate.py: FOUND (169 lines)
- tests/test_status_promotion_rate.py: FOUND (159 lines)
- src/automil/viz/server.py promotion_rate_handler: FOUND
- src/automil/cli/status.py Promotion rate line: FOUND
- Commit eecee7b: FOUND
- Commit e3dfcc9: FOUND
- Commit 9b1baae: FOUND
- Commit da9480e: FOUND
