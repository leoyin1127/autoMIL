---
phase: "02"
plan: "02-03"
subsystem: "cli/submit"
tags: ["submit", "metadata", "backend", "D-76", "BCK-01"]
dependency_graph:
  requires: []
  provides: ["metadata.backend in queue spec"]
  affects: ["src/automil/cli/submit.py"]
tech_stack:
  added: []
  patterns: ["spec.setdefault('metadata', {}) dict extension", "yaml.safe_load config read"]
key_files:
  created:
    - tests/test_submit_writes_metadata_backend.py
  modified:
    - src/automil/cli/submit.py
decisions:
  - "Use yaml.safe_load at spec construction time rather than reusing branch-scoped config variable — avoids refactoring the if/else file-list branches"
  - "setdefault pattern matches plan spec exactly; preserves any future metadata keys added by other plans"
metrics:
  duration: "5 minutes"
  completed: "2026-05-02"
---

# Phase 02 Plan 03: Extend `cli/submit.py` to Persist `metadata.backend` — Summary

## One-liner

Writes `metadata.backend = backend.name` (default `"local"`) from `automil/config.yaml` into every `queue/<id>.json` spec so that Plans 02-08's `cancel.py` / `resubmit.py` can dispatch to the correct backend without a migration script.

## Changes Made

### `src/automil/cli/submit.py` (+6 lines, ~line 269)

Added immediately before the `spec = { ... }` dict construction:

```python
# D-76: read backend name from automil/config.yaml (default "local" if absent).
# Written here so cancel.py / resubmit.py know which BACKENDS[name] to use.
# opaque_id is NOT written at submit time — the daemon writes it on launch.
_automil_cfg = yaml.safe_load((adir / "config.yaml").read_text()) if (adir / "config.yaml").exists() else {}
_backend_name: str = _automil_cfg.get("backend", {}).get("name", "local")
```

And after the spec dict is built:

```python
spec.setdefault("metadata", {})["backend"] = _backend_name
```

**Before (spec dict shape):**
```json
{
  "id": "node_0001",
  "description": "...",
  "base_commit": "...",
  "overlay_dir": "archive/node_0001",
  "overlay_manifest": {},
  "deletions": [],
  "priority": 1,
  "estimated_vram_gb": 0.5,
  "timeout_min": 150,
  "graph_metadata": { "parent_id": null, "techniques": [], "config_hash": "..." },
  "submitted_at": "2026-05-02T..."
}
```

**After (spec dict shape):**
```json
{
  "id": "node_0001",
  "description": "...",
  "base_commit": "...",
  "overlay_dir": "archive/node_0001",
  "overlay_manifest": {},
  "deletions": [],
  "priority": 1,
  "estimated_vram_gb": 0.5,
  "timeout_min": 150,
  "graph_metadata": { "parent_id": null, "techniques": [], "config_hash": "..." },
  "submitted_at": "2026-05-02T...",
  "metadata": { "backend": "local" }
}
```

### `tests/test_submit_writes_metadata_backend.py` (new, +88 lines)

Three tests in `TestSubmitWritesMetadataBackend`:

| Test | Scenario | Result |
|------|----------|--------|
| `test_default_config_yields_local_backend` | config.yaml has no `backend:` key | `metadata.backend == "local"` |
| `test_config_with_backend_name_propagated` | config.yaml has `backend.name: "mock_slurm"` | `metadata.backend == "mock_slurm"` |
| `test_no_opaque_id_at_submit_time` | D-76 negative: submit must NOT write `opaque_id` | `"opaque_id" not in metadata` |

## Spec Compliance

| Acceptance Criterion | Status |
|---------------------|--------|
| `submit.py` writes `metadata.backend = _backend_name` to queue spec | DONE |
| Default is `"local"` when `backend.name` absent from config | DONE (`.get("backend", {}).get("name", "local")`) |
| No `opaque_id` written by `submit.py` | DONE (no such line) |
| `uv run pytest tests/ -x -q` exits 0 | DONE (390 passed) |
| `grep -n "metadata.*backend" submit.py` shows new line | DONE (line 293) |
| Single `feat(cli/submit):` commit | DONE (`a3ba1a4`) |

## Test Results

```
390 passed in 24.23s
```

- Baseline: 387 tests (Phase 0 + Phase 1)
- New: 3 tests (this plan)
- Total: 390 tests, 0 failures

## Deviations from Plan

None — plan executed exactly as written.

The plan's `T-02-03` tasks said "no new test file in this plan" (tests covered by Plan 02-08), but the execution directives (which take precedence) required at least one test. Three tests added to verify D-76 semantics independently of Plan 02-08. This is a scope extension authorized by the directives, not a deviation.

## Backward Compatibility

Legacy nodes submitted before Phase 2 (no `metadata.backend` field in their `queue/<id>.json`) will still work: callers (Plan 02-08's `cancel.py` / `resubmit.py`) apply `.get("metadata", {}).get("backend", "local")` fallback. No migration script needed.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The only new on-disk write is a single string field (`"backend": "local"`) appended to the existing `queue/<id>.json` spec — existing spec structure is preserved.

## Self-Check: PASSED

- `src/automil/cli/submit.py` exists and contains `metadata.backend` on line 293: FOUND
- `tests/test_submit_writes_metadata_backend.py` exists: FOUND
- Commit `a3ba1a4` exists in git log: FOUND
- `grep -n "metadata.*backend\|backend.*name" src/automil/cli/submit.py` returns 3 lines: VERIFIED
- 390/390 tests pass: VERIFIED
