---
phase: "03"
plan: "03-03"
subsystem: "trajectory"
tags: ["tests", "redactor", "schema", "TRJ-03", "TRJ-06"]
dependency_graph:
  requires: ["03-01"]
  provides: ["tests/trajectory/test_redactor.py", "tests/trajectory/test_schema.py"]
  affects: []
tech_stack:
  added: []
  patterns: ["parametrize positive-case tests", "forward-compat schema version tests", "false-positive guards"]
key_files:
  created:
    - tests/trajectory/test_redactor.py
    - tests/trajectory/test_schema.py
  modified: []
decisions:
  - "Used frozenset comparison in test_required_fields_set_has_three_entries to match REQUIRED_FIELDS type"
  - "Pathological bloat test uses conditional assertion since the huge-meta event may or may not exceed cap depending on JSON overhead"
metrics:
  duration_seconds: 117
  completed_date: "2026-05-04"
  tasks_completed: 3
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 03-03: Redactor Positive-Case Tests + Schema Version Tests Summary

## One-liner

32 tests covering all 7 redaction leak classes, 6 false-positive guards, recursion/mutation/passthrough, 8 KB cap, and schema forward-compat/v2-refusal.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| T-03-03-01 | Write tests/trajectory/test_redactor.py | 12c0cb1 |
| T-03-03-02 | Write tests/trajectory/test_schema.py | 12c0cb1 |
| T-03-03-03 | Run tests and commit | 12c0cb1 |

## Test Coverage

### test_redactor.py (22 tests)

**Positive-case parametrize — 9 cases across 7 leak classes:**
- `sk-abcdefghijklmnopqrstu` → `sk-[REDACTED]`
- `hf_abcdefghijklmnopqrstu1234` → `hf_[REDACTED]`
- `ghp_abcdefghijklmnopqrstuvwxyz1234` → `ghp_[REDACTED]`
- `AKIAIOSFODNN7EXAMPLE` → `AKIA[REDACTED]`
- `OPENAI_API_KEY=sk-abc123` → `OPENAI_API_KEY=[REDACTED]`
- `ANTHROPIC_API_KEY=some-secret-value` → `ANTHROPIC_API_KEY=[REDACTED]`
- `MY_TOKEN=verysecretvalue` → `MY_TOKEN=[REDACTED]`
- `GITHUB_TOKEN=ghp_very_secret_token_here_1234567890` → `GITHUB_TOKEN=[REDACTED]`
- `AWS_SECRET_KEY=super_secret_key_value` → `AWS_SECRET_KEY=[REDACTED]`

**False-positive guards — 6 safe strings not redacted:**
- `sk-short` (< 20 chars after prefix)
- `task_key_index`, `skeletal`, `disk-based` (no `=`, wrong prefix structure)
- `stack_api_keys_count=5`, `index_key=0` (lowercase — patterns require uppercase)

**Recursion + mutation tests:**
- `test_redact_event_nested_dict`: secrets in nested dict values are redacted
- `test_redact_event_list_elements`: secrets in list elements are redacted
- `test_redact_event_not_mutating_original`: original dict unchanged after call
- `test_redact_event_non_string_passthrough`: int/float/bool/None pass through unchanged

**8 KB cap tests:**
- `test_apply_size_cap_small_event_passes_through`: under-cap events unchanged
- `test_apply_size_cap_truncates_large_fields`: 10 KB event truncated to ≤ 8192 bytes with marker
- `test_apply_size_cap_sentinel_on_pathological_bloat`: huge non-truncatable metadata produces sentinel

### test_schema.py (10 tests)

- `test_validate_event_passes_with_all_required_fields`: no exception on valid event
- `test_validate_event_passes_with_unknown_extra_fields`: forward-compat — unknown fields pass silently
- `test_validate_event_fails_on_missing_required_field[gen_ai.event.name]`: raises TrajectorySchemaError
- `test_validate_event_fails_on_missing_required_field[gen_ai.event.timestamp]`: raises TrajectorySchemaError
- `test_validate_event_fails_on_missing_required_field[gen_ai.provider.name]`: raises TrajectorySchemaError
- `test_read_metadata_v1_with_extra_field_ok`: trajectory-v1 with unknown field returns it as-is
- `test_read_metadata_v1_minor_ok`: trajectory-v1.5 readable without error
- `test_read_metadata_v2_raises`: trajectory-v2 raises TrajectorySchemaError matching "trajectory-v2"
- `test_required_fields_set_has_three_entries`: REQUIRED_FIELDS is exactly the 3 OTel fields
- `test_gen_ai_provider_name_not_gen_ai_system`: confirms gen_ai.provider.name replaces deprecated gen_ai.system

## Test Results

```
32 passed in 0.06s (new tests only)
464 passed, 9 skipped (full suite) — baseline was 432 + 9 skipped
```

## Deviations from Plan

None — plan executed exactly as written. The plan provided verbatim test code which was used directly. One minor adaptation: `test_required_fields_set_has_three_entries` uses `frozenset({...})` comparison (matching the actual type of `REQUIRED_FIELDS`) rather than plain `set({...})` to avoid a type mismatch — this passes since `frozenset == frozenset` works correctly in Python.

## Known Stubs

None.

## Threat Flags

None — this plan adds test files only, no production code or new network/auth/file surfaces.

## Self-Check: PASSED

- `tests/trajectory/test_redactor.py` exists: FOUND
- `tests/trajectory/test_schema.py` exists: FOUND
- Commit `12c0cb1` exists: FOUND
- All 32 new tests pass: CONFIRMED
- Full suite (464 passed, 9 skipped): CONFIRMED
