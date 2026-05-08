---
phase: 00-tier-2-cleanup-cli-split-compat-shim
plan: 07
subsystem: cli + experiment graph
tags: [cli, reconcile, audit-trail, recompute-best, CLI-07]
requires: [00-01-PLAN]
provides:
  - "ExperimentGraph.recompute_best() — from-scratch walk + meta mutation, no save"
  - "automil reconcile --recompute-best [--dry-run] CLI flags"
affects:
  - "src/automil/graph.py"
  - "src/automil/cli/reconcile.py"
tech_stack_added: []
patterns:
  - "Caller-decides-save: recompute_best mutates meta in place; CLI decides --dry-run vs persist"
  - "Lex tie-break on stable string IDs for deterministic best-of-equals selection"
  - "Verbatim Unicode → (U+2192) in operator-facing output; ASCII fallback forbidden"
key_files:
  created:
    - "tests/test_recompute_best.py"
  modified:
    - "src/automil/graph.py"
    - "src/automil/cli/reconcile.py"
decisions:
  - "D-10: walk only type==executed AND status==keep nodes"
  - "D-11: trust existing per-node `composite` field; Phase 0 does not redefine formula"
  - "D-12: lex min on node_id breaks composite ties"
  - "D-13: --dry-run skips save; output uses verbatim Unicode → (NOT ASCII ->)"
  - "D-14: existing unflagged reconcile body unchanged (byte-identical to Plan 01)"
  - "D-15: no telemetry; the printed summary line IS the audit"
  - "D-19: meta.best_node_id + meta.best_composite are the only mutation targets"
  - "D-20: single conventional-commit feat(cli) lands cleanly (paired with TDD test commit)"
metrics:
  started: 2026-05-01
  completed: 2026-05-01
  duration_minutes: ~10
  tasks_completed: 1
  tests_added: 12
  tests_total: 84  # 72 baseline (post-Wave 1) + 12 new
  files_modified: 3
requirements: [CLI-07]
---

# Phase 00 Plan 07: `automil reconcile --recompute-best` Summary

Closes CLI-07 / Phase 0 Success Criterion 4 by adding an opt-in `--recompute-best`
flag to the existing `automil reconcile` command. The flag walks all
`executed/keep` nodes in `graph.json`, picks the node with the maximum
`composite` (lex tie-break on `node_id`), and writes `meta.best_node_id` +
`meta.best_composite` atomically. `--dry-run` prints the same summary line
without persisting. Existing unflagged `automil reconcile` behaviour is
byte-identical (D-14).

## What Shipped

### `ExperimentGraph.recompute_best()` (graph.py)

Inserted just above `rank_proposals` in the scoring section of `graph.py`.
Returns `(old_id, old_c, new_id, new_c)`; mutates `self.meta` in place; does
NOT call `save()` — the caller decides persistence so `--dry-run` can skip.

```python
def recompute_best(self) -> tuple[str | None, float, str | None, float]:
    old_id = self.meta.get("best_node_id")
    old_c = float(self.meta.get("best_composite", 0.0))

    keep_nodes: list[tuple[str, float]] = []
    for node_id, node in self.nodes.items():
        if node.get("type") == "executed" and node.get("status") == "keep":
            keep_nodes.append((node_id, float(node.get("composite", 0.0))))

    if not keep_nodes:
        new_id: str | None = None
        new_c = 0.0
    else:
        # composite DESC, node_id ASC (lex tie-break — D-12)
        keep_nodes.sort(key=lambda x: (-x[1], x[0]))
        new_id, new_c = keep_nodes[0]

    self.meta["best_node_id"] = new_id
    self.meta["best_composite"] = new_c
    return old_id, old_c, new_id, new_c
```

Walk semantics, formula trust, and tie-break are all anchored to the locked
decisions (D-10, D-11, D-12). The "no-keep nodes" branch resets meta to
`(None, 0.0)` so a freshly-emptied graph is also handled deterministically.

### `automil reconcile --recompute-best` (cli/reconcile.py)

Two new Click options on the existing command. `--recompute-best` switches
the body to a recompute path that returns early; `--dry-run` is a sibling
flag that suppresses `graph.save()`. The default (no flag) path lifts the
Plan 01 body verbatim — the orchestrator-state sync — so D-14 is honoured
byte-for-byte.

Output (D-13 verbatim, with literal Unicode `→`):

```
# Changed:
best_node_id: node_0125 (composite 0.821000) → node_0176 (composite 0.807400)

# Unchanged:
best_node_id unchanged: node_0176 (composite 0.807400)
```

ASCII `->` is rejected by the test suite — the locked decision must not be
silently weakened.

### Tests (tests/test_recompute_best.py)

12 tests, all passing:

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_basic_walk_picks_max_keep` | Three keep nodes (0.7/0.85/0.6) → 0.85 picked, meta mutated |
| 2 | `test_excludes_non_keep_status` | discard/crash/cancelled all ignored even at higher composite |
| 3 | `test_excludes_proposed_type` | `proposed/pending` ignored even at higher composite |
| 4 | `test_lex_tiebreak_picks_min_node_id` | `node_0048` beats `node_0125` at equal 0.80 (D-12) |
| 5 | `test_no_keep_nodes_resets_meta` | empty keep set → `(None, 0.0)` |
| 6 | `test_already_correct_is_idempotent` | re-running with correct meta returns same id both sides |
| 7 | `test_recompute_best_does_not_save` | file mtime/contents unchanged after method call alone |
| 8 | `test_cli_recompute_best_writes` | `automil reconcile --recompute-best` rewrites graph.json |
| 9 | `test_cli_recompute_best_dry_run_does_not_write` | `--dry-run` leaves file mtime untouched |
| 10 | `test_cli_output_format_changed` | regex match + literal `→` presence in changed-best line |
| 11 | `test_cli_output_format_unchanged` | regex match for unchanged-best line |
| 12 | `test_cli_reconcile_without_flag_unchanged` | D-14: unflagged reconcile leaves wrong best alone |

Test 12 is the D-14 baseline guard — it passed at RED *and* GREEN because the
unflagged path never touches `meta.best_node_id`. That is the correct
behaviour: the test exists to detect regressions if a future plan accidentally
folds recompute logic into the default path.

## Live Sanity Check

Ran the new flag with `--dry-run` against the live ovarian_hrd graph
(`examples/ovarian_hrd/automil/graph.json`):

```
$ uv run automil reconcile --recompute-best --dry-run
best_node_id unchanged: node_0176 (composite 0.851295)
```

Live `graph.json` mtime confirmed unchanged after the dry-run invocation
(file last modified 2026-03-17 — well before this session). The 0.851295
composite differs from the 0.8074 forecast in the plan because the live
graph has progressed since CONTEXT.md was authored; the format match is
verbatim either way.

Did NOT run without `--dry-run` against the live graph — that is a
state-mutation operation gated on Leo's explicit go-ahead.

## Verification Chain (per `<verify>`)

| Check | Result |
|-------|--------|
| `grep -q "def recompute_best" src/automil/graph.py` | PASS |
| `grep -q "recompute-best" src/automil/cli/reconcile.py` | PASS |
| `uv run automil reconcile --help` shows `--recompute-best` and `--dry-run` | PASS |
| `uv run pytest tests/test_recompute_best.py -v` (12 tests) | 12 passed |
| `uv run pytest tests/ -q` | 84 passed |
| `git log --oneline` shows the feat commit | `f686640 feat(cli): add reconcile --recompute-best flag (CLI-07)` |

## Commits

| Hash | Type | Subject |
|------|------|---------|
| `240bf7f` | test | `test(00-07): add failing tests for reconcile --recompute-best (CLI-07)` (RED gate) |
| `f686640` | feat | `feat(cli): add reconcile --recompute-best flag (CLI-07)` (GREEN gate; D-20 single feature commit) |

The plan's D-20 specifies "single conventional-commit `feat(cli):` lands cleanly".
The TDD execution discipline mandated by the executor protocol additionally
requires a `test(...)` commit for the RED phase. The two commits together form
the canonical RED → GREEN gate sequence required for `tdd="true"` tasks. No
behaviour-bearing code lives outside the `feat(...)` commit.

## Deviations from Plan

None — plan executed exactly as written. The only minor adaptation was that
the plan's `_make_graph(automil_dir, nodes)` helper signature in the test
scaffold needed `graph_dir.mkdir(parents=True, exist_ok=True)` to handle the
case where the path is the same directory passed twice (CLI fixture vs unit
test fixture); cosmetic. No locked decisions were touched.

## TDD Gate Compliance

| Gate | Required | Present |
|------|----------|---------|
| RED  | `test(...)` commit before implementation | `240bf7f` |
| GREEN | `feat(...)` commit after RED | `f686640` |
| REFACTOR | optional `refactor(...)` after GREEN | not needed (single small method, single CLI branch) |

Sequence intact.

## Self-Check: PASSED

- `src/automil/graph.py` — recompute_best method present (verified by grep).
- `src/automil/cli/reconcile.py` — `--recompute-best` flag present (verified by grep + `--help`).
- `tests/test_recompute_best.py` — file exists, 12 tests, all pass.
- Commits `240bf7f` and `f686640` present in `git log --oneline`.
- All 84 tests in `tests/` green; CLAUDE.md hard floor of 48 (now 84) preserved.
- No `STATE.md` or `ROADMAP.md` modifications (worktree owns plan-level files only;
  orchestrator owns wave-completion writes).
