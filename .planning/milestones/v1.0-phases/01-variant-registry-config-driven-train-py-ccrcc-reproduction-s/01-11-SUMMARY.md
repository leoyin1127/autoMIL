---
plan: 01-11
phase: 01
subsystem: cli/lifecycle
tags: [port-variant, promote-variant, CLI-05, CLI-06, D-43, D-44, D-45, BLOCKER-02-fix]
dependency_graph:
  requires: [01-01, 01-02, 01-03, 01-06, 01-08, 01-09]
  provides: [port-variant-CLI-05, promote-variant-CLI-06]
  affects: [apply (01-09 consumer), verify-repro (01-12 reader), Phase-5-GTE]
tech_stack:
  added: []
  patterns: [atomic-tempfile-rename, ExperimentGraph.save, git-mv-staging, CLI-TDD-RED-GREEN]
key_files:
  created:
    - tests/test_lifecycle_port_variant.py
    - tests/test_lifecycle_promote_variant.py
  modified:
    - src/automil/cli/lifecycle/port_variant.py
    - src/automil/cli/lifecycle/promote_variant.py
    - tests/test_lifecycle_skeleton.py
decisions:
  - "port-variant writes variant_spec into graph.json via ExperimentGraph.save() (atomic) before refresh-registry — idempotence check on existing manifest means re-run is safe"
  - "promote-variant uses git mv (not shutil.move) to preserve rename semantics in git history; stages but never auto-commits (D-45)"
  - "test_lifecycle_skeleton.py stub list updated to remove port-variant and promote-variant entries now that they are fully implemented (Rule 1 auto-fix)"
metrics:
  duration: ~25 minutes
  completed: 2026-05-02
  tasks_completed: 3
  files_changed: 5
---

# Phase 01 Plan 11: port-variant + promote-variant (CLI-05 + CLI-06) Summary

**One-liner:** Full port-variant (overlay→variant module+manifest+graph.json) and promote-variant (git mv _candidates→canonical dir, stage, no auto-commit) implementations with 30 net-new tests and apply↔port integration closure.

## Objective

Implement the last two of the six lifecycle commands introduced in Plan 01-08:

- `automil port-variant <node_id>` (CLI-05 / D-43, D-44): Converts a node's submitted overlay into a registered variant module + sibling JSON manifest, writes `node['variant_spec']` into `graph.json` so `automil apply` can consume it, and calls `refresh-registry` so the new variant is immediately importable.
- `automil promote-variant <node_id>` (CLI-06 / D-45): Moves a gate-passing candidate from `variants/_candidates/` to the canonical `variants/<parent>/` (or `_losses/`, `_policies/`) via `git mv`, regenerates affected `__init__.py` files, and stages (but never auto-commits) the changes.

## Tasks Executed

| # | Task | Status | Commits |
|---|------|--------|---------|
| 1 | RED tests for port-variant | Done | 79f6343 |
| 2 | RED tests for promote-variant | Done | 3db1e0f |
| 3 | GREEN: implement port_variant.py + promote_variant.py | Done | c5be659, 8f21b48 |

## Files Modified

| File | Lines | Role |
|------|-------|------|
| `src/automil/cli/lifecycle/port_variant.py` | 188 | Full port-variant implementation replacing Phase 1 stub |
| `src/automil/cli/lifecycle/promote_variant.py` | 116 | Full promote-variant implementation replacing Phase 1 stub |
| `tests/test_lifecycle_port_variant.py` | 419 | 20 tests for port-variant |
| `tests/test_lifecycle_promote_variant.py` | 277 | 10 tests for promote-variant |
| `tests/test_lifecycle_skeleton.py` | -2 | Removed port-variant + promote-variant from stub list |

## Test Names + Assertion Summary

### test_lifecycle_port_variant.py (20 tests)

1. `test_happy_port_model_auto` — model overlay + graph_metadata.parent_id → `.py` + `.json` created under `variants/clam_mb/`
2. `test_auto_name_format` — auto-name is `<parent>_v<short>` (e.g., `clam_mb_v0042`)
3. `test_auto_kind_loss` — `core_utils.py` overlay → kind=loss → `_losses/loss_v0050.py`
4. `test_auto_kind_policy` — `optimizer.py` overlay → kind=policy → `_policies/policy_v0060.py`
5. `test_ambiguous_kind_requires_flag` — model+policy overlay → exit non-zero, mentions `--kind`
6. `test_kind_override_resolves_ambiguity` — same ambiguous overlay + `--kind model` → succeeds
7. `test_name_override` — `--name my_custom_name` → `my_custom_name.py` created
8. `test_parent_override` — `--parent ab_mil` with no graph_metadata parent → `variants/ab_mil/`
9. `test_idempotent_same_node_id` — re-porting same node_id → exit 0 "already ported"; mtime unchanged
10. `test_mismatched_node_id_same_name_hard_fail` — port node_0121 with same name as node_0120 → exit non-zero, both node_ids in message
11. `test_manifest_schema` — written `.json` contains `spec, source_node, source_overlay_files, ported_at, tool_version`
12. `test_module_body_has_register_and_docstring` — `.py` contains `@register`, `ModelVariant`, `Parent: clam_mb`, `Node ID:`
13. `test_calls_refresh_registry` — after port-variant, `variants/clam_mb/__init__.py` imports the new variant
14. `test_missing_spec_json_hard_fail` — no `spec.json` → exit non-zero mentioning `spec.json`
15. `test_empty_overlay_manifest_hard_fail` — empty `overlay_manifest` → exit non-zero mentioning overlay/empty
16. `test_model_without_parent_hard_fail` — kind=model auto-detected, no parent in spec or heuristics → exit non-zero mentioning `--parent`
17. `test_help_quality` — `--help` mentions `--kind`, `--name`, and workflow text
18. `test_variant_spec_written_to_graph_json` — after port-variant, `graph.json.nodes[node_0190].variant_spec` = `{kind, name, parent}` (BLOCKER-02 fix)
19. `test_variant_spec_for_loss_kind` — loss variant → `variant_spec.parent is None`
20. `test_apply_after_port_variant_no_mock` — full lifecycle: port-variant → apply → `config.yaml.model.variant` = `clam_mb_v0501` (NO manual variant_spec injection)

### test_lifecycle_promote_variant.py (10 tests)

1. `test_happy_promote_model` — model candidate → promoted to `variants/clam_mb/`; source gone
2. `test_git_mv_shows_rename` — `git status --porcelain` shows `R` (staged rename), not D+A
3. `test_init_py_regenerated_both_dirs` — destination `__init__.py` imports promoted variant; `_candidates/__init__.py` does not
4. `test_files_staged_not_committed` — `git diff --cached --name-only` includes moved files; commit count unchanged
5. `test_no_auto_commit` — `git log -1 --format=%s` == "add candidate" (fixture's last commit, not automil's)
6. `test_missing_candidate_hard_fail` — no candidate for node_9999 → exit non-zero with "available:"
7. `test_loss_kind_promotes_to_losses` — loss candidate → promoted to `variants/_losses/`
8. `test_idempotent_already_promoted` — re-running promote after already promoted → exit 0 or 1 (no crash)
9. `test_model_without_parent_hard_fail` — model candidate with `parent=None` → exit non-zero with "parent"
10. `test_help_quality` — `--help` mentions "candidate" or "gate"

## Sample Produced Module Body

```python
"""clam_mb_v0176 variant.

Parent: clam_mb
Base commit: abc1234
Composite: 0.5
Node ID: node_0176
Mutations: 
"""
from automil.registry import register, VariantSpec, ModelVariant


@register(VariantSpec(
    name="clam_mb_v0176", kind="model", parent="clam_mb",
    base_commit="abc1234", composite=0.5,
    node_id="node_0176", created_at="2026-05-02T10:00:00+00:00",
    mutations=() if False else (),
))
class ClamMbV0176(ModelVariant):
    def forward(self, features, coords=None):
        # TODO: paste the variant's forward body here.
        # See sources: models/model_clam.py
        raise NotImplementedError("variant body not yet ported")
```

## Sample Manifest JSON (D-44)

```json
{
  "spec": {
    "name": "clam_mb_v0176",
    "kind": "model",
    "parent": "clam_mb",
    "base_commit": "abc1234",
    "composite": 0.5,
    "node_id": "node_0176",
    "created_at": "2026-05-02T10:00:00+00:00",
    "mutations": []
  },
  "source_node": "node_0176",
  "source_overlay_files": ["models/model_clam.py"],
  "ported_at": "2026-05-02T10:00:00+00:00",
  "tool_version": "automil 0.1.0"
}
```

## Commit SHAs

| Commit | Message |
|--------|---------|
| 79f6343 | test(01-11): add failing tests for port-variant (CLI-05 / D-43, D-44) |
| 3db1e0f | test(01-11): add failing tests for promote-variant (CLI-06 / D-45) |
| c5be659 | feat(cli): implement port-variant (CLI-05) |
| 8f21b48 | feat(cli): implement promote-variant (CLI-06) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_lifecycle_skeleton.py stub list**
- **Found during:** Task 3 (GREEN phase) — full suite run after implementation
- **Issue:** `test_stub_error_format` parameterized test still included `port-variant` and `promote-variant` in the stub list, expecting them to raise "not yet implemented". After implementation, these commands no longer stub-fail, so the test incorrectly failed.
- **Fix:** Removed `("port-variant", "01-11")` and `("promote-variant", "01-11")` from the parametrize list; updated comment to document all fully-implemented commands.
- **Files modified:** `tests/test_lifecycle_skeleton.py`
- **Commit:** c5be659

## Notes for Downstream Plans

### Plan 01-12 (verify-repro)
The manifest written by `port-variant` follows D-44 exactly. Plan 01-12 can read it via `Manifest.read(manifest_path)` where `manifest_path = adir / "variants" / <kind_dir> / f"{name}.json"`. The `source_overlay_files` field lists the original overlay paths for cross-checking the synthetic mini-consumer.

### Phase 5 GTE
`promote-variant` ships the full move plumbing. Phase 5 GTE only needs to call `automil promote-variant <node_id>` after gate-passing — no additional infrastructure needed on the promote side.

### D-37 Deferred (byte-identical port)
The Phase 1 stub body uses `raise NotImplementedError` — this is intentional per D-37. The framework provides the API (ports the VariantSpec + manifest + @register class skeleton); the consumer pastes the actual variant code. The synthetic mini-consumer in Plan 01-12 provides its own body via test fixtures, NOT via port-variant's stub generator.

### git mv partial-failure recovery
If `.py` moves but `.json` fails (extremely rare filesystem race), run:
```bash
git restore --staged variants/_candidates/<name>.py
git mv variants/_candidates/<name>.py variants/<kind_dir>/<name>.py
git mv variants/_candidates/<name>.json variants/<kind_dir>/<name>.json
```

## Threat Flags

No new threat surface introduced. Both commands are operator-owned CLI tools with no network endpoints, auth paths, or file access beyond the automil/ project directory.

## Self-Check: PASSED

- `src/automil/cli/lifecycle/port_variant.py` — EXISTS
- `src/automil/cli/lifecycle/promote_variant.py` — EXISTS
- `tests/test_lifecycle_port_variant.py` — EXISTS (20 tests)
- `tests/test_lifecycle_promote_variant.py` — EXISTS (10 tests)
- Commit 79f6343 — EXISTS
- Commit 3db1e0f — EXISTS
- Commit c5be659 — EXISTS
- Commit 8f21b48 — EXISTS
- `cli/lifecycle/__init__.py` — UNTOUCHED
- 375 total tests passing (347 prior + 28 net-new)
