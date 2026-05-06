---
phase: "03"
plan: "03-09"
subsystem: "trajectory"
tags: [cli, trajectory, export, tdd, recorder]
dependency_graph:
  requires: ["03-01", "03-04", "03-08"]
  provides: ["trajectory-cli-record", "trajectory-cli-export", "export-bundle"]
  affects: ["src/automil/cli/__init__.py", "src/automil/cli/trajectory.py", "src/automil/trajectory/export.py"]
tech_stack:
  added: []
  patterns:
    - "Lazy imports inside Click command body (PATTERNS §8 / D-69)"
    - "Click group + subcommands file (cancel.py analog)"
    - "exit 0 for soft-fail, exit 1 for hard errors (D-94 exit code contract)"
    - "tar.gz bundle with tempdir staging + tarfile.open w:gz"
key_files:
  created:
    - src/automil/cli/trajectory.py
    - tests/trajectory/test_recorder.py
    - tests/trajectory/test_record_cli.py
    - tests/trajectory/test_export_cli.py
  modified:
    - src/automil/trajectory/export.py
    - src/automil/cli/__init__.py
decisions:
  - "exit-0-soft-fail: record CLI exits 0 for both success and soft-fail per D-94 (hook scripts use || true)"
  - "at-filepath-convention: @prefix reads event JSON from file, not Click's argument file syntax"
  - "export-re-redacts: export_bundle re-runs redact_event on every line to defend against rule additions since capture"
  - "manifest-schema-version: manifest.json includes schema_version field alongside redaction_rule_hash"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-04T05:56:37Z"
  tasks_completed: 4
  files_changed: 6
requirements_addressed: [TRJ-04, TRJ-05]
---

# Phase 03 Plan 09: `automil trajectory` CLI Group + record/export + Recorder Tests + Export Implementation Summary

## One-liner

`automil trajectory record/export` CLI with D-94 exit-code contract, full tar.gz bundle export with re-redaction + manifest, and 10 new tests covering all Nyquist acceptance criteria (TRJ-04, TRJ-05).

## What Was Built

### T-03-09-01: `src/automil/cli/trajectory.py`

Click group registered as `@main.group("trajectory")` with two subcommands:

- **`record`**: Parses event JSON (string or `@filepath`), checks `AUTOMIL_NODE_ID` env, resolves archive_dir from `AUTOMIL_DIR` env or walks up for `automil/config.yaml`, calls `record_event()`. Exits 0 for both success and soft-fail (D-94); exits 1 for JSON parse error or missing `AUTOMIL_NODE_ID`.
- **`export`**: Resolves archive_dir the same way, calls `export_bundle()`, prints bundle path. Hard-fails on `FileNotFoundError` or unexpected exceptions.

### T-03-09-02: `src/automil/trajectory/export.py`

Replaced the 03-01 stub with full `export_bundle()` implementation:
- Collects `trajectory*.jsonl` files via glob (primary + rotated siblings)
- Re-runs `redact_event()` on every line (D-94 defence against rule additions since capture)
- Validates non-header lines via `validate_event()`
- Produces `manifest.json` with `node_id`, `schema_version`, `exported_at`, `redaction_rule_hash` (SHA-256 of concatenated pattern strings, first 16 hex chars), and per-file line counts
- Stages in `tempfile.TemporaryDirectory()`, writes tarball via `tarfile.open(w:gz)`

### T-03-09-03: `src/automil/cli/__init__.py`

Added `from automil.cli import trajectory` alphabetically between `submit` and `viz`.

### T-03-09-04: Three test files

- `tests/trajectory/test_recorder.py`: 5 tests — append creates 2-line file, secrets redacted, 5 events → 6 lines, soft-fail on missing required fields, read_metadata returns correct header
- `tests/trajectory/test_record_cli.py`: 4 tests — exit 0 valid event, exit 0 soft-fail (bad event), exit 1 JSON parse error, exit 1 missing AUTOMIL_NODE_ID
- `tests/trajectory/test_export_cli.py`: 1 test — tarball contains trajectory.jsonl + manifest.json, manifest has correct node_id and redaction_rule_hash

## Commits

| Hash | Message |
|------|---------|
| 09ede64 | feat(03-09): automil trajectory record/export CLI + recorder tests + export bundle (TRJ-04, TRJ-05) |

## Test Results

```
514 passed, 9 skipped (baseline: 504 + 9 skipped)
New tests: 10 (5 recorder + 4 record CLI + 1 export CLI)
Trajectory tests: 51 passed
```

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None. `export_bundle()` is fully implemented.

## Threat Flags

None. The three threat mitigations from the plan's STRIDE analysis are implemented:
- T-03-09-S01: @filepath reads text JSON only; binary/non-JSON triggers parse error (exit 1)
- T-03-09-S02: export_bundle re-runs redact_event on every exported line
- T-03-09-S03: node_id is used as a path component only within archive_dir boundary

## Self-Check: PASSED

Files verified:
- src/automil/cli/trajectory.py: EXISTS
- src/automil/trajectory/export.py: EXISTS (full implementation)
- src/automil/cli/__init__.py: trajectory import registered
- tests/trajectory/test_recorder.py: EXISTS
- tests/trajectory/test_record_cli.py: EXISTS
- tests/trajectory/test_export_cli.py: EXISTS
- Commit 09ede64: FOUND
- 514 passed, 9 skipped: VERIFIED
