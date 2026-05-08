---
phase: "03"
plan: "03-06"
subsystem: "runtime-declaration"
tags: ["runtime", "trajectory", "submit", "TRJ-04", "D-87", "D-97"]
dependency_graph:
  requires: []
  provides:
    - "src/automil/runtime.py (get_runtime() -> str, reads AUTOMIL_RUNTIME, default unknown)"
    - "submit.py metadata.runtime field (symmetric to metadata.backend)"
    - "config.yaml.j2 env.passthrough section with AUTOMIL_RUNTIME"
  affects:
    - "src/automil/trajectory/recorder.py (will import get_runtime for D-85 record_event)"
    - "src/automil/cli/submit.py (metadata.runtime now in every queue spec)"
tech_stack:
  added: []
  patterns:
    - "Explicit env-var-only runtime declaration (D-87) — no heuristics, no process inspection"
    - "Symmetric metadata fields in submit.py spec (backend + runtime side by side)"
    - "YAML env.passthrough whitelist pattern for orchestrator → subprocess propagation"
key_files:
  created:
    - "src/automil/runtime.py"
    - "tests/test_runtime.py"
  modified:
    - "src/automil/cli/submit.py"
    - "src/automil/templates/config.yaml.j2"
decisions:
  - "D-87 honoured verbatim: get_runtime() is a 1-line os.environ.get() — no sys.argv, no process tree inspection, no package name detection"
  - "D-97 honoured verbatim: metadata.runtime placed immediately after metadata.backend (same setdefault pattern)"
  - "os import already present in submit.py at line 5 — used directly, no _os_runtime alias needed"
  - "env.passthrough in config.yaml.j2 lists both AUTOMIL_* wildcard and AUTOMIL_RUNTIME explicitly per belt-and-suspenders T-03-06-S02 mitigation"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 2
  tests_added: 6
  baseline_before: "425 passed, 9 skipped"
  baseline_after: "431 passed, 9 skipped"
---

# Phase 03 Plan 06: Runtime Declaration Module + submit.py Extension + config.yaml.j2 Summary

## One-liner

Stdlib-only `runtime.py` module exposing `get_runtime()` (reads `AUTOMIL_RUNTIME` env var, default `"unknown"`) with symmetric `metadata.runtime` injection in `submit.py` queue spec and `env.passthrough` section in `config.yaml.j2`.

## What Was Built

Three targeted additions with zero new dependencies:

1. **`src/automil/runtime.py`** — 3-line stdlib module per D-87. `get_runtime()` reads `AUTOMIL_RUNTIME` and returns it as-is; returns `"unknown"` if unset. Never infers from `sys.argv`, process tree, or installed packages. Satisfies TRJ-04 runtime-declaration contract.

2. **`src/automil/cli/submit.py` patch** — 4-line addition immediately after the `metadata.backend` line (D-76). Uses the existing top-level `os` import. Every queue spec written to `orchestrator/queue/<node>.json` now carries `metadata.runtime`.

3. **`src/automil/templates/config.yaml.j2` patch** — Adds an `env:` section with `passthrough:` list containing `AUTOMIL_*` (wildcard) and `AUTOMIL_RUNTIME` (explicit comment). Belt-and-suspenders coverage per T-03-06-S02 mitigation.

4. **`tests/test_runtime.py`** — 6 tests covering: env-declared, opencode value, unset returns unknown, case-sensitive passthrough, deepseek-via-opencode, never-infers (sys.argv manipulation).

## Commits

| Hash | Message |
|------|---------|
| de2aa34 | feat(03-06): runtime.py + submit.py metadata.runtime + config.yaml.j2 passthrough (TRJ-04) |

## Test Results

```
431 passed, 9 skipped, 1 warning in 23.54s
```

New tests: 6 (all in `tests/test_runtime.py`). Baseline (425 + 9 skipped) fully preserved.

## Deviations from Plan

None — plan executed exactly as written.

The one implementation note: `submit.py` already had `import os` at line 5, so the plan's fallback `_os_runtime` alias was not needed. Used the existing import name directly, which is cleaner.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced by this plan. `runtime.py` is a pure env-var reader. `submit.py` adds one string field to an existing dict. `config.yaml.j2` adds a documentation-only YAML section (no runtime behavior change to the template renderer).

## Self-Check

Files exist:
- `src/automil/runtime.py` — created
- `tests/test_runtime.py` — created
- `src/automil/cli/submit.py` — modified (metadata.runtime line present)
- `src/automil/templates/config.yaml.j2` — modified (env.passthrough section present)

Commit de2aa34 exists and contains all 4 files (2 created, 2 modified, 0 deleted).
