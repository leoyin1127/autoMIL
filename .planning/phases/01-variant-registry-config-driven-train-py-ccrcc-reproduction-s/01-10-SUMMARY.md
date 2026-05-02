---
phase: "01"
plan: "01-10"
subsystem: "cli/lifecycle"
tags: [cli, lifecycle, revert-baseline, git-safety, stash, tdd]
dependency_graph:
  requires: [01-01, 01-02, 01-03, 01-08]
  provides: [CLI-02, revert-baseline-command]
  affects: [src/automil/cli/lifecycle/revert_baseline.py, tests/test_lifecycle_revert_baseline.py]
tech_stack:
  added: []
  patterns: [git-stash-before-checkout, git-cat-file-existence-check, idempotent-cli-command, tdd-red-green]
key_files:
  created:
    - tests/test_lifecycle_revert_baseline.py (356 lines — 15 tests)
  modified:
    - src/automil/cli/lifecycle/revert_baseline.py (stub → full implementation, 151 lines)
    - tests/test_lifecycle_skeleton.py (remove revert-baseline from stub parametrize list)
decisions:
  - "Use git cat-file -t instead of git rev-parse --verify for SHA existence check (rev-parse --verify accepts any 40-char hex string even if the commit doesn't exist in the repo)"
  - "Commit automil/ overlay dir in test fixture before writing graph.json, so git stash --include-untracked does not sweep it up"
  - "D-42 stash is full-tree (no pathspec), ensuring non-protected uncommitted work is also preserved"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-02"
  tests_added: 15
  tests_total: 322
---

# Phase 01 Plan 10: revert-baseline (CLI-02) Summary

Full implementation of `automil revert-baseline` with mandatory pre-stash safety net enforcing Leo's "never blind-checkout after submit" memory.

## What Was Built

`src/automil/cli/lifecycle/revert_baseline.py` — Full implementation replacing the Plan 01-08 stub. The command:

1. Loads `registry.protected` from `automil/config.yaml` — hard-fails if empty.
2. Derives `base_commit` from the most-recent executed node's `base_commit` field in `graph.json` (lexicographic max on `created_at` ISO-8601) — hard-fails if no graph, no executed nodes, or SHA doesn't exist (`git cat-file -t`).
3. Checks if protected paths are already clean — exits 0 with "nothing to do" if so (idempotent).
4. MANDATORY pre-stash: if any uncommitted changes exist anywhere in the working tree, creates `automil-revert-<YYYYMMDD-HHMMSS>` stash via `git stash push --include-untracked -m <name>`. Prints the stash name and recovery instructions (`git stash list && git stash pop`) BEFORE the checkout so the operator has the name even if checkout crashes.
5. Runs `git checkout <base_commit> -- <protected_paths>` and surfaces `stderr` in the error message on failure.

## Test Coverage (15 tests)

| Test | Assertion |
|------|-----------|
| `test_protected_file_reverted` | Happy path: modified protected file restored to base_commit content |
| `test_mandatory_stash_created` | `git stash list` shows `automil-revert-` entry after dirty run |
| `test_stash_name_format` | stdout matches `automil-revert-\d{8}-\d{6}` regex |
| `test_recovery_message_in_output` | stdout contains `git stash pop` or `git stash list` |
| `test_uncommitted_non_protected_also_stashed` | Non-protected file (staged) absent from working tree; present in `git stash show --name-only` (WARNING-03 strengthening — proves stash is full-tree, not pathspec-limited) |
| `test_untracked_file_included_in_stash` | Untracked `.junk` file gone from tree after command (`--include-untracked`) |
| `test_clean_tree_no_op` | Clean tree → exit 0, "already clean/nothing to do", no stash created |
| `test_idempotent_second_run` | Second run on already-clean protected paths is no-op; exactly 1 stash total |
| `test_no_graph_json_hard_fail` | No graph.json → exit non-zero, message mentions "graph.json" or "executed" |
| `test_no_executed_nodes_hard_fail` | Proposed-only graph → exit non-zero, message mentions "executed" or "base_commit" |
| `test_empty_protected_hard_fail` | Empty `registry.protected` → exit non-zero, message contains "registry.protected is empty" |
| `test_invalid_base_commit_hard_fail` | 40-char fake SHA (not in repo) → exit non-zero, message contains "not a valid git SHA" |
| `test_help_mentions_stash` | `--help` output contains "stash" or "blind" |
| `test_picks_most_recent_executed_node` | Two executed nodes with different base_commits → uses the newer `created_at` node's commit |
| `test_stash_name_printed_before_checkout` | Stash name line appears before revert-confirmation line in stdout (ordering guarantee) |

## Stash Name Format Example

```
automil-revert-20260502-081234
```

Recover via: `git stash list && git stash pop`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] git rev-parse --verify does not check commit existence**
- **Found during:** Task 2 (GREEN phase), test_invalid_base_commit_hard_fail failure
- **Issue:** `git rev-parse --verify <40-hex-chars>` exits 0 even if the commit doesn't exist in the repo — it only validates format. The command then proceeded to checkout and git reported "reference is not a tree" which didn't match the test assertion "not a valid git SHA".
- **Fix:** Replaced `git rev-parse --verify` with `git cat-file -t` which actually queries the object database for existence.
- **Files modified:** `src/automil/cli/lifecycle/revert_baseline.py`

**2. [Rule 1 - Bug] Test fixture allowed automil/ to be swept by --include-untracked stash**
- **Found during:** Task 2 (GREEN phase), test_idempotent_second_run failure
- **Issue:** `_setup_with_protected` ran `automil init` but did not commit the `automil/` directory. When the first `revert-baseline` run called `git stash push --include-untracked`, it captured `automil/config.yaml`, `automil/graph.json` etc. The second run then failed with "No automil/config.yaml found".
- **Fix:** Updated `_setup_with_protected` to `git add automil/ && git commit -m "add automil overlay"` before writing `graph.json`, so the overlay files are tracked and not captured by stash untracked sweep.
- **Files modified:** `tests/test_lifecycle_revert_baseline.py`

**3. [Rule 1 - Bug] test_lifecycle_skeleton stub parametrize included revert-baseline**
- **Found during:** Task 2 (full suite run)
- **Issue:** `test_lifecycle_skeleton.py::test_stub_error_format` expected `revert-baseline` to exit non-zero with "not yet implemented". Now that the command is fully implemented, this test was a false failure.
- **Fix:** Removed `("revert-baseline", "01-10")` from the parametrize list with a comment noting the stub is replaced.
- **Files modified:** `tests/test_lifecycle_skeleton.py`

## Known Stubs

None. The implementation is complete. `cli/lifecycle/__init__.py` was not modified (wave-safety enforced).

## Downstream Note

The implementation passes `registry.protected` patterns directly to `git checkout <sha> -- <patterns>`. Git's pathspec does NOT auto-expand shell globs like `**`; if a consumer's protected list uses `benchmarks/lib/CLAM/**`, the operator may need `:(glob)benchmarks/lib/CLAM/**` syntax or enumerate files via `git ls-files`. For Phase 1 acceptance (Plan 01-12 synthetic mini-consumer using literal paths), this is correct. Document for Phase 8 / DEC-06 training-script-contract.md when glob patterns are needed.

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns beyond the git operations in scope.

## Self-Check: PASSED

- `src/automil/cli/lifecycle/revert_baseline.py`: FOUND
- `tests/test_lifecycle_revert_baseline.py`: FOUND
- Commit `1020b84` (RED tests): FOUND
- Commit `d08a529` (GREEN implementation): FOUND
- `cli/lifecycle/__init__.py` unmodified: CONFIRMED
- 322 tests pass: CONFIRMED
