---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: "02"
subsystem: backends
tags: [extras-gate, error-types, guarded-import, pyproject, BCK-05, BCK-06]

dependency_graph:
  requires: [06-01]
  provides: [extras-gate, D-153-guarded-import, D-154-extras, D-178-error-types]
  affects: [06-04, 06-05, 06-03]

tech_stack:
  added: []
  patterns:
    - guarded try/except ImportError for optional backend extras (D-153)
    - typed error subclass hierarchy (BackendError base)
    - pyproject.toml optional-dependencies extras gate

key_files:
  created:
    - tests/backends/test_errors_phase6.py
    - tests/backends/test_extras_gate.py
  modified:
    - pyproject.toml
    - src/automil/backends/errors.py
    - src/automil/backends/__init__.py

decisions:
  - "Guarded imports mirror D-69 mock_slurm precedent: silent pass on ImportError, no warnings"
  - "New error types re-exported via __all__ in backends/__init__.py for consumer convenience"
  - "SLURMBackend/RayBackend NOT added to __all__ — conditionally available names not safe to export at module level"

metrics:
  duration: "~15 minutes"
  completed: "2026-05-05"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
---

# Phase 6 Plan 02: pyproject extras + 3 typed errors + guarded import Summary

**One-liner:** Opt-in SLURM/Ray extras gate with `submitit>=1.5.3`/`ray>=2.55.1` floors, three `BackendError` subclasses carrying structured attributes, and guarded `try/except ImportError` blocks in `backends/__init__.py` following the D-69 mock_slurm precedent.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add [slurm] + [ray] extras to pyproject.toml | 51ed5ec | pyproject.toml |
| 2 | Extend backends/errors.py with 3 typed error subclasses | 7cd105d | src/automil/backends/errors.py, tests/backends/test_errors_phase6.py |
| 3 | Add guarded slurm + ray imports to backends/__init__.py | 9233381 | src/automil/backends/__init__.py, tests/backends/test_extras_gate.py |

## pyproject.toml diff

Added to `[project.optional-dependencies]` (lines 30-31):
```toml
slurm = ["submitit>=1.5.3"]   # BCK-05 — opt-in SLURM backend
ray   = ["ray>=2.55.1"]       # BCK-06 — opt-in Ray backend
```
Neither appears in `[project.dependencies]` or `[dependency-groups.dev]`. The pytest markers block (`requires_slurm`, `requires_ray`) was already present from plan 06-01 — not modified.

## Error class additions (src/automil/backends/errors.py)

Three new subclasses appended after the existing `BackendError`:

- `BackendNotInstalledError(BackendError)`: `extra_name` attribute + `pip install -e '.[<extra>]'` recovery hint in message
- `SlurmDirectivesIncompleteError(BackendError)`: `missing_keys: list[str]` attribute + directive path hint
- `RayClusterUnreachableError(BackendError)`: `address: str` attribute + fallback config hint

All three verified with `issubclass(X, BackendError) == True` and attribute access in `test_errors_phase6.py`.

## Guarded import block placement (src/automil/backends/__init__.py)

Inserted after the `local` + `LocalBackend` imports (line 77-79), before `__all__`:

```python
try:
    from automil.backends import slurm as _slurm_backend  # noqa: F401
except ImportError:
    pass  # [slurm] extra not installed — backend unavailable

try:
    from automil.backends import ray as _ray_backend  # noqa: F401
except ImportError:
    pass  # [ray] extra not installed — backend unavailable
```

Follows verbatim D-69/D-153 pattern. `slurm.py` and `ray.py` don't exist yet — both `ImportError` branches fire on every import in the current checkout, which is the expected no-extras behavior.

The three new error types are re-exported via `__all__` (alphabetised: `BackendNotInstalledError`, `RayClusterUnreachableError`, `SlurmDirectivesIncompleteError`). `SLURMBackend`/`RayBackend` are NOT added to `__all__` — availability depends on extras; names won't exist if import failed.

## Test count delta

- Before plan 06-02: 829 collected (includes Wave 0 stubs from 06-01)
- After plan 06-02: 834 collected (+5 new tests: 3 error-type + 2 extras-gate)
- Tests passing: 785 (up from 778 baseline after stubs)
- 7 pre-existing stub failures (Wave 0 from 06-01 requiring plans 06-03/04/05/06) — all confirmed pre-existing, none caused by this plan

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None introduced by this plan. The guarded import blocks reference `automil.backends.slurm` and `automil.backends.ray` which don't exist yet — those land in plans 06-04 and 06-05 respectively. This is the designed behavior, not a stub.

## Threat Flags

None. This plan adds no network endpoints, no auth paths, no file access patterns, and no schema changes at trust boundaries. Error class definitions and pyproject.toml extras are purely declarative.

## Self-Check: PASSED

- `pyproject.toml` extras lines present: verified via grep
- `src/automil/backends/errors.py` 3 new classes: verified via pytest 3/3 pass
- `src/automil/backends/__init__.py` guarded imports + re-exports: verified via import test
- `tests/backends/test_errors_phase6.py` exists and passes
- `tests/backends/test_extras_gate.py` exists and passes
- Commits 51ed5ec, 7cd105d, 9233381 exist in git log
- `grep -rn "autobench|AUTOBENCH_|benchmarks/" src/automil/backends/errors.py src/automil/backends/__init__.py` = 0 matches
