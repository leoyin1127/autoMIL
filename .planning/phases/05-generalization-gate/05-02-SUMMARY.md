---
phase: 05-generalization-gate
plan: "02"
subsystem: gate
tags: [manifest, persistence, atomic-write, git-commit, frozen-dataclass, tdd]
dependency_graph:
  requires: ["05-01"]
  provides:
    - GateManifest frozen dataclass
    - write_manifest (atomic write)
    - write_manifest_committed (atomic write + git commit + path.unlink rollback)
    - retire_manifest (rename + git commit, cached-payload rollback)
    - read_manifest / load_manifest
    - validate_manifest_dict
  affects:
    - src/automil/gate/__init__.py (additive exports)
    - tests/gate/test_manifest.py (17 tests)
tech_stack:
  added: []
  patterns:
    - "frozen dataclass: cells/state.py analog — @dataclass(frozen=True) + dataclasses.asdict/replace"
    - "atomic write: tempfile.mkstemp(dir=str(target)) + os.replace — same FS guaranteed"
    - "git commit pattern: subprocess.run list argv (injection-safe), check=True, capture_output=True"
    - "rollback discipline: path.unlink() — NEVER git checkout (Leo memory: feedback_never_blind_checkout)"
    - "D-138 #4: SHA backfill via SECOND commit (no amend — pre-registration timestamp preserved)"
key_files:
  created:
    - src/automil/gate/manifest.py
    - tests/gate/test_manifest.py
  modified:
    - src/automil/gate/__init__.py
decisions:
  - "Test 13 checks all commit messages (git log --format=%s, not -1) to handle two-commit backfill pattern; the backfill commit is the latest HEAD"
  - "17th test (test_11b) from plan-checker iter-1 covers retire rollback: RuntimeError + active restored + no git checkout"
  - "write_manifest returns Path (not None) to allow callers to inspect the written path without re-constructing it"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-06T00:41:37Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 5 Plan 02: GateManifest Persistence Layer Summary

GateManifest frozen dataclass + atomic write + atomic-write-PLUS-git-commit with path.unlink rollback (Leo memory: feedback_never_blind_checkout) + retire flow + schema validation — all 17 tests green.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 (RED) | Failing tests for manifest persistence | 948a125 | tests/gate/test_manifest.py (17 tests) |
| 2 (GREEN) | GateManifest implementation | a86b729 | src/automil/gate/manifest.py, gate/__init__.py |

## What Was Built

### `src/automil/gate/manifest.py`

**GateManifest frozen dataclass (D-137):**
- 9 fields: parent_id, created_at, git_committed_at_sha, held_out_cells (tuple-of-tuples), K, p_threshold, bootstrap_reps, win_definition, schema_version
- `SCHEMA_VERSION = "gate-v1"`, `BOOTSTRAP_REPS_FLOOR = 100`

**validate_manifest_dict:** K >= 1, K <= len(held_out_cells), p_threshold in (0, 1], bootstrap_reps >= 100, schema_version == "gate-v1"; raises ValueError with descriptive messages.

**write_manifest:** Atomic via tempfile.mkstemp(dir=str(manifests_dir)) + os.replace — same-filesystem guaranteed. Returns Path. Validates before writing.

**read_manifest / load_manifest:** Full JSON round-trip; tuple-of-tuples reconstruction for held_out_cells.

**retire_manifest:** Writes .retired.gate_manifest.json atomically with retired_reason + retired_at ISO timestamp; git add + git commit; on git failure restores active manifest from in-memory cached payload (NEVER git checkout per Leo memory).

**write_manifest_committed:** Atomic write + git add + git commit (initial registration); refuses overwrite (FileExistsError with retire-manifest hint); on git failure removes manifest via path.unlink() (NEVER git checkout); D-138 #4: SHA backfill via SECOND commit (no amend — pre-registration timestamp preserved in history).

### `src/automil/gate/__init__.py` (additive)
Added manifest exports alphabetically: GateManifest, load_manifest, read_manifest, retire_manifest, validate_manifest_dict, write_manifest, write_manifest_committed.

### `tests/gate/test_manifest.py` (17 tests)
- Test 1: frozen — FrozenInstanceError on mutation
- Test 2: round-trip — write + read preserves all fields including tuple-of-tuples
- Test 3: source-level tempfile.mkstemp pattern confirmed
- Tests 4-9: validate_manifest_dict — K, held_out_cells, p_threshold, bootstrap_reps, schema_version
- Test 10: load_manifest by parent_id + FileNotFoundError
- Test 11: retire rename, JSON annotations, SHA returned
- **Test 11b**: retire rollback on git failure — active restored, retired absent, NO git checkout (Leo memory enforced)
- Test 12: tmp file cleanup on write exception
- Test 13: write_manifest_committed returns 40-char SHA; registration commit in log with K= and p<
- Test 14: refuse overwrite — FileExistsError with "retire-manifest"
- Test 15: git-failure rollback — manifest absent post-failure, no git checkout in mock call history
- **Test 16**: source-level — path.unlink() present, "git", "checkout" absent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test 13 commit-message assertion adjusted for two-commit pattern**
- **Found during:** GREEN phase run
- **Issue:** Test 13 used `git log --format=%s -1` which returns the backfill commit message ("gate: backfill commit SHA for node_0001"), not the registration commit. The K=2 and p<0.05 are in the registration commit.
- **Fix:** Changed assertion to check all commit messages (`git log --format=%s` without -1) so both the registration and backfill messages are searched.
- **Files modified:** tests/gate/test_manifest.py
- **Commit:** a86b729 (included in GREEN commit)

## Verification

All plan acceptance criteria met:

```
@dataclass(frozen=True):         1 (required: 1)
tempfile.mkstemp(dir=str(:       3 (required: >=2)
os.replace(tmp_path, str(:       3 (required: >=2)
SCHEMA_VERSION = "gate-v1":      1 (required: 1)
BOOTSTRAP_REPS_FLOOR = 100:      1 (required: 1)
autobench/AUTOBENCH_/benchmarks: 0 (required: 0)
path.unlink():                   4 (required: >=1)
"git", "checkout":               0 (required: 0)
feedback_never_blind_checkout:   5 (required: >=1)
git add calls:                   3 (required: >=2)
git commit calls:                3 (required: >=2)
dataclasses.replace backfill:    1 (required: 1)
BCK-04 lint (kill/pid/Popen):    0 (required: 0)
```

17/17 tests pass. Full suite: 3 pre-existing failures in test_tick_cells.py (unrelated to this plan — confirmed by checking base branch).

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries beyond what is specified in the plan's threat model (T-05-02-01..06). The rollback anti-tamper (T-05-02-04) is enforced both in source (path.unlink) and in test (Test 16 source-inspection, Test 15 call-history assertion).

## Self-Check: PASSED

- `src/automil/gate/manifest.py` exists: FOUND
- `tests/gate/test_manifest.py` exists: FOUND
- `src/automil/gate/__init__.py` updated: FOUND
- Commits 948a125 (RED) and a86b729 (GREEN) exist: FOUND
