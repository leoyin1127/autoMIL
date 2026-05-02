---
phase: "01"
plan: "01-08"
subsystem: "cli/lifecycle"
tags: [cli, refactor, wave-safety, skeleton, tdd]
dependency_graph:
  requires: [01-01, 01-02, 01-03]
  provides: [cli/lifecycle/ package with 6 stub commands + _shared helpers]
  affects: [cli/__init__.py (import now resolves package not file)]
tech_stack:
  added: []
  patterns: [Click command per-file registration, atomic tempfile+rename write, TDD RED/GREEN]
key_files:
  deleted:
    - src/automil/cli/lifecycle.py (12 lines — Phase 0 stub)
  created:
    - src/automil/cli/lifecycle/__init__.py (28 lines)
    - src/automil/cli/lifecycle/_shared.py (97 lines)
    - src/automil/cli/lifecycle/apply.py (27 lines)
    - src/automil/cli/lifecycle/revert_baseline.py (26 lines)
    - src/automil/cli/lifecycle/refresh_registry.py (34 lines)
    - src/automil/cli/lifecycle/port_variant.py (40 lines)
    - src/automil/cli/lifecycle/promote_variant.py (26 lines)
    - src/automil/cli/lifecycle/verify_repro.py (33 lines)
    - tests/test_lifecycle_skeleton.py (263 lines)
  modified: []
decisions:
  - "Package-per-command split (option a) for wave-safety: each downstream plan owns one file"
  - "_shared.py provides three helpers so plans 01-09/10/11/12 don't duplicate boilerplate"
  - "os.replace() used for atomic write (POSIX atomic, no .tmp leftovers)"
  - "lifecycle/__init__.py import list locked by this plan; downstream plans MUST NOT modify it"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02"
  tasks_completed: 2
  files_created: 9
  files_modified: 0
  files_deleted: 1
  tests_added: 29
  tests_total: 262
---

# Phase 01 Plan 08: Lifecycle Package Skeleton Summary

Six CLI stub commands registered in a per-command package replacing a 12-line stub file — wave-safety enabler for Plans 01-09/10/11/12.

## What Was Built

Converted `src/automil/cli/lifecycle.py` (Phase 0's 12-line empty stub) into a `src/automil/cli/lifecycle/` package containing:

- `__init__.py` — imports all 6 sub-modules, documenting wave-safety invariant
- `_shared.py` — three shared helpers for downstream plans
- Six per-command stubs, each registering a `@main.command()` that hard-fails with "not yet implemented (Plan 01-NN)"

The existing `from automil.cli import lifecycle` in `cli/__init__.py` required no change — Python's import system naturally prefers the package over the deleted module file.

## Commands Registered

| Command | Implementing Plan | Stub Error Message |
|---------|------------------|--------------------|
| `apply <node_id>` | 01-09 | `not yet implemented (Plan 01-09 will ship it)` |
| `refresh-registry` | 01-09 | `not yet implemented (Plan 01-09 will ship it)` |
| `revert-baseline` | 01-10 | `not yet implemented (Plan 01-10 will ship it)` |
| `port-variant <node_id>` | 01-11 | `not yet implemented (Plan 01-11 will ship it)` |
| `promote-variant <node_id>` | 01-11 | `not yet implemented (Plan 01-11 will ship it)` |
| `verify-repro <node_id>` | 01-12 | `not yet implemented (Plan 01-12 will ship it)` |

## Canonical CLI Sub-Module Shape

Plans 01-09/10/11/12 should clone this pattern for implementing their commands:

```python
"""<command>: <one-line description> (Plan 01-NN)."""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir
from automil.cli.lifecycle._shared import _load_registry_or_die, _get_node_or_die


@main.command("<command-name>")
@click.argument("node_id")
def <function_name>(node_id: str):
    """<Short summary>.

    Workflow: <workflow explanation with key terms>.
    """
    adir = _find_automil_dir()
    # Implementation replaces the raise below:
    raise click.ClickException(
        f"`automil <command> {node_id}` not yet implemented "
        f"(Plan 01-NN will ship it)."
    )
```

## _shared.py Helper Signatures

```python
def _atomic_write_text(path: Path, content: str) -> None:
    """Atomic tempfile + rename write. Creates parent dirs. No .tmp leftovers."""

def _load_registry_or_die(adir: Path) -> Any:
    """Load registry config; raise click.ClickException with fix hint if invalid."""

def _get_node_or_die(adir: Path, node_id: str) -> dict:
    """Return node dict from graph.json; raise ClickException with available: listing if missing."""
```

## Tests Added (29)

| Test | What It Covers |
|------|---------------|
| `test_six_commands_registered` | All 6 commands appear in `automil --help` |
| `test_each_command_has_help[apply]` | Exit 0, output >100 chars |
| `test_each_command_has_help[revert-baseline]` | Exit 0, output >100 chars |
| `test_each_command_has_help[refresh-registry]` | Exit 0, output >100 chars |
| `test_each_command_has_help[port-variant]` | Exit 0, output >100 chars |
| `test_each_command_has_help[promote-variant]` | Exit 0, output >100 chars |
| `test_each_command_has_help[verify-repro]` | Exit 0, output >100 chars |
| `test_stub_error_format[apply-01-09]` | Non-zero exit, "not yet implemented", "01-09" |
| `test_stub_error_format[revert-baseline-01-10]` | Non-zero exit, "not yet implemented", "01-10" |
| `test_stub_error_format[refresh-registry-01-09]` | Non-zero exit, "not yet implemented", "01-09" |
| `test_stub_error_format[port-variant-01-11]` | Non-zero exit, "not yet implemented", "01-11" |
| `test_stub_error_format[promote-variant-01-11]` | Non-zero exit, "not yet implemented", "01-11" |
| `test_stub_error_format[verify-repro-01-12]` | Non-zero exit, "not yet implemented", "01-12" |
| `test_lifecycle_py_file_deleted` | lifecycle.py does not exist as a file |
| `test_lifecycle_package_exists` | __init__.py + all 7 sub-modules present |
| `test_cli_init_imports_lifecycle_package` | lifecycle package exposes apply + revert_baseline attrs |
| `test_atomic_write_helper_available` | Writes correctly, no .tmp leftovers |
| `test_atomic_write_creates_parent_dirs` | Creates nested parent directories |
| `test_atomic_write_overwrites_existing` | Second write wins, no corruption |
| `test_get_node_or_die_missing_lists_available` | Error message contains all node IDs + "available:" |
| `test_get_node_or_die_missing_graph` | Error message mentions graph.json |
| `test_get_node_or_die_returns_node_dict` | Returns correct dict for existing node |
| `test_get_node_or_die_malformed_json` | Error message mentions "malformed" |
| `test_each_command_helpdoc_mentions_workflow[apply-config]` | "config" in apply help |
| `test_each_command_helpdoc_mentions_workflow[revert-baseline-git]` | "git" in revert-baseline help |
| `test_each_command_helpdoc_mentions_workflow[refresh-registry-scan]` | "scan" in refresh-registry help |
| `test_each_command_helpdoc_mentions_workflow[port-variant-manifest]` | "manifest" in port-variant help |
| `test_each_command_helpdoc_mentions_workflow[promote-variant-candidate]` | "candidate" in promote-variant help |
| `test_each_command_helpdoc_mentions_workflow[verify-repro-manifest]` | "manifest" in verify-repro help |

## Commits

| Hash | Message |
|------|---------|
| `0b08ed9` | `test(01-08): add failing tests for lifecycle/ package skeleton (CLI-01/02/05/06/08/09)` |
| `60a7d2a` | `refactor(cli): convert lifecycle.py stub to lifecycle/ package + register six command stubs` |

## Deviations from Plan

None — plan executed exactly as written. The single commit format specified in the plan was split into two commits (RED test commit + GREEN implementation commit) per TDD protocol, which is the correct execution of the `tdd="true"` task attribute.

## Wave-Safety Invariant (CRITICAL for downstream plans)

Plans 01-09/10/11/12 MUST NOT modify `lifecycle/__init__.py`. They modify their per-command file ONLY:

- Plan 01-09: edit `apply.py` + `refresh_registry.py` only
- Plan 01-10: edit `revert_baseline.py` only
- Plan 01-11: edit `port_variant.py` + `promote_variant.py` only
- Plan 01-12: edit `verify_repro.py` only

The import list in `lifecycle/__init__.py` is locked in by this plan. Any modification to it risks conflict with parallel wave executors.

## Known Stubs

All six command bodies are intentional stubs (per plan spec). Each raises `click.ClickException("not yet implemented (Plan 01-NN)")` as the ONLY line of the function body.

These are not incomplete implementations — they are structural placeholders. Full implementations land in Plans 01-09/10/11/12.

## Threat Flags

None — pure structural refactor. No new network endpoints, auth paths, file access patterns beyond the `_shared.py` helpers, or schema changes at trust boundaries.

## Self-Check: PASSED

- `src/automil/cli/lifecycle/__init__.py` FOUND
- `src/automil/cli/lifecycle/_shared.py` FOUND
- `src/automil/cli/lifecycle/apply.py` FOUND
- `src/automil/cli/lifecycle/revert_baseline.py` FOUND
- `src/automil/cli/lifecycle/refresh_registry.py` FOUND
- `src/automil/cli/lifecycle/port_variant.py` FOUND
- `src/automil/cli/lifecycle/promote_variant.py` FOUND
- `src/automil/cli/lifecycle/verify_repro.py` FOUND
- `tests/test_lifecycle_skeleton.py` FOUND
- `src/automil/cli/lifecycle.py` DELETED (confirmed)
- Commit `0b08ed9` FOUND
- Commit `60a7d2a` FOUND
- 262 total tests PASSING
