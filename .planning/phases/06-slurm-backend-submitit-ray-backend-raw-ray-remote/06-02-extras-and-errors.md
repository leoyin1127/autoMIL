---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 02
type: execute
wave: 1
depends_on: ["06-01"]
files_modified:
  - pyproject.toml
  - src/automil/backends/errors.py
  - src/automil/backends/__init__.py
autonomous: true
requirements: [BCK-05, BCK-06]

must_haves:
  truths:
    - "`pip install -e .` (no extras) installs cleanly without pulling submitit OR ray (D-179 clause 4)."
    - "`pip install -e '.[slurm]'` installs submitit>=1.5.3 and makes `import automil.backends.slurm` work (D-179 clause 5)."
    - "`pip install -e '.[ray]'` installs ray>=2.55.1 and makes `import automil.backends.ray` work (D-179 clause 6)."
    - "errors.py exposes `BackendNotInstalledError`, `SlurmDirectivesIncompleteError`, `RayClusterUnreachableError`, all subclassing `BackendError` (D-178)."
    - "backends/__init__.py guarded import follows D-69 precedent: missing extras → silent ImportError catch, no runtime explosion, no tracebacks at startup."
  artifacts:
    - path: pyproject.toml
      provides: "[project.optional-dependencies] block with [slurm] and [ray] extras (D-154)."
      contains: "submitit>=1.5.3"
    - path: src/automil/backends/errors.py
      provides: "Three new error subclasses with structured error attributes."
      contains: "class BackendNotInstalledError(BackendError)"
    - path: src/automil/backends/__init__.py
      provides: "Guarded imports for slurm + ray (no auto-failure when extras absent)."
      contains: "try:\n    from automil.backends import slurm"
  key_links:
    - from: src/automil/backends/__init__.py
      to: src/automil/backends/slurm.py
      via: guarded try/except ImportError
      pattern: "try:\\n\\s+from automil.backends import slurm"
    - from: src/automil/backends/__init__.py
      to: src/automil/backends/ray.py
      via: guarded try/except ImportError
      pattern: "try:\\n\\s+from automil.backends import ray"
    - from: src/automil/backends/errors.py
      to: src/automil/backends/errors.py::BackendError
      via: subclass inheritance
      pattern: "class \\w+Error\\(BackendError\\)"
---

<objective>
Wave 1A — install the opt-in extras gate and error type hierarchy that the rest of Phase 6 depends on. After this plan: a no-extras install works (no submitit/ray pulled); `pip install -e '.[slurm]'` and `pip install -e '.[ray]'` install the right floors; the three new error types are importable; the guarded `__init__.py` block is in place so when slurm.py and ray.py land in Wave 2 they auto-register without breaking unprivileged installs.

Purpose: D-179 clauses 4/5/6 are the "extras gate intact" anti-failure modes. If we land slurm.py without the guarded import, `pip install -e .` (no extras) breaks `automil --help` for every operator who never wanted SLURM. The guard is THE most load-bearing engineering choice in Phase 6.

Output: pyproject.toml extras block + errors.py extension + backends/__init__.py guarded import block. No backend implementations land here — those come in Wave 2 (06-04 + 06-05).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md
@CLAUDE.md

# Existing patterns this plan extends:
@src/automil/backends/__init__.py
@src/automil/backends/errors.py
@pyproject.toml

<interfaces>
<!-- Public surface this plan creates. Plan 06-04/06-05 import from here. -->

From src/automil/backends/errors.py (after this plan):
```python
class BackendError(Exception):
    """Existing — unchanged."""

class BackendNotInstalledError(BackendError):
    extra_name: str  # public attribute; carries pip hint
    def __init__(self, backend_name: str, extra_name: str) -> None: ...

class SlurmDirectivesIncompleteError(BackendError):
    missing_keys: list[str]
    def __init__(self, missing_keys: list[str]) -> None: ...

class RayClusterUnreachableError(BackendError):
    address: str
    def __init__(self, address: str) -> None: ...
```

From src/automil/backends/__init__.py (after this plan):
```python
# Existing exports unchanged: Backend, JobHandle, JobSpec, JobState, BackendError,
# BACKENDS, register, _clear_backends, LocalBackend.
# NEW: BackendNotInstalledError, SlurmDirectivesIncompleteError, RayClusterUnreachableError
# also exported via errors.py re-export.
# Guarded imports added at bottom; no new public symbols if extras missing.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add [slurm] + [ray] extras to pyproject.toml</name>
  <files>pyproject.toml</files>
  <read_first>
    - pyproject.toml (lines 23-29 — existing `[project.optional-dependencies]`)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-154 — exact extras names + version floors)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md (§"Standard Stack" — version verification)
  </read_first>
  <behavior>
    - Test 1 (manual): `pip install -e .` (no extras) succeeds in a fresh venv WITHOUT pulling submitit or ray (verified by `pip list | grep -iE "submitit|ray"` returning nothing in that venv).
    - Test 2 (manual): `pip install -e '.[slurm]'` pulls submitit>=1.5.3 (verifiable via `pip show submitit`).
    - Test 3 (manual): `pip install -e '.[ray]'` pulls ray>=2.55.1 (verifiable via `pip show ray`).
  </behavior>
  <action>
Add two new entries to `[project.optional-dependencies]` after the existing `ml = [...]` block per D-154 verbatim:
```toml
[project.optional-dependencies]
ml = [
    "torch>=2.0",
    "scikit-learn>=1.3",
    "scipy>=1.11",
    "h5py>=3.9",
]
slurm = ["submitit>=1.5.3"]   # BCK-05 — opt-in SLURM backend
ray   = ["ray>=2.55.1"]       # BCK-06 — opt-in Ray backend
```

Do NOT pin tighter than the floor (production pattern; let consumers upgrade — RESEARCH.md §"Standard Stack").
Do NOT add submitit or ray to `[project.dependencies]` (line 12-21) or `[dependency-groups.dev]` (line 41-45). The contract is "framework runs without them; install only if backend selected" (CONTEXT.md D-154).
Do NOT modify the `[tool.pytest.ini_options]` block — markers were already registered in plan 06-01.
  </action>
  <verify>
    <automated>grep -E '^slurm = \["submitit&gt;=1\.5\.3"\]$' pyproject.toml &amp;&amp; grep -E '^ray\s+= \["ray&gt;=2\.55\.1"\]$' pyproject.toml &amp;&amp; ! grep -E "submitit|^ray\b" pyproject.toml | grep -v "optional-dependencies\|^slurm\|^ray\s"</automated>
  </verify>
  <done>
    `[project.optional-dependencies]` block contains exactly three entries: `ml`, `slurm`, `ray`. `slurm = ["submitit>=1.5.3"]` and `ray = ["ray>=2.55.1"]` lines present (grep returns 1 each). No submitit/ray reference in `[project.dependencies]` (grep returns 0). `pip install -e .` in this checkout still succeeds (sanity-check; do not actually rebuild a venv — `python -c "import automil"` is sufficient).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Extend backends/errors.py with three new typed error subclasses (D-178)</name>
  <files>src/automil/backends/errors.py</files>
  <read_first>
    - src/automil/backends/errors.py (full file — existing `BackendError` shape and the docstring style)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-178 — exact attribute names + recovery-hint message wording)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"src/automil/backends/errors.py" lines 357-413 — full code excerpt)
    - tests/backends/test_slurm_directives.py (the Wave-0 stub from plan 06-01 — confirms the expected `missing_keys` attribute access)
  </read_first>
  <behavior>
    - Test 1: `from automil.backends.errors import BackendNotInstalledError, SlurmDirectivesIncompleteError, RayClusterUnreachableError` succeeds.
    - Test 2: All three are subclasses of `BackendError` (`issubclass(BackendNotInstalledError, BackendError) == True` etc).
    - Test 3: `BackendNotInstalledError("slurm", "slurm")` carries `.extra_name == "slurm"` and message contains `pip install -e '.[slurm]'`.
    - Test 4: `SlurmDirectivesIncompleteError(["partition", "account"])` carries `.missing_keys == ["partition", "account"]`.
    - Test 5: `RayClusterUnreachableError("ray://head:10001")` carries `.address == "ray://head:10001"`.
  </behavior>
  <action>
Append three new classes to `src/automil/backends/errors.py` (the existing `BackendError` class is unchanged). Use the verbatim code from PATTERNS.md §"src/automil/backends/errors.py" lines 374-413, reproduced here:

```python
class BackendNotInstalledError(BackendError):
    """Raised when the selected backend's extra is not installed.

    Carries ``extra_name`` attribute so callers can surface the pip hint.
    """
    def __init__(self, backend_name: str, extra_name: str) -> None:
        self.extra_name = extra_name
        super().__init__(
            f"Backend {backend_name!r} requires the [{extra_name}] extra. "
            f"Install it with: pip install -e '.[{extra_name}]'"
        )


class SlurmDirectivesIncompleteError(BackendError):
    """Raised by automil check when required SLURM directives are missing
    or contain the TODO_FILL_IN sentinel.

    Carries ``missing_keys`` list for structured error reporting.
    """
    def __init__(self, missing_keys: list[str]) -> None:
        self.missing_keys = missing_keys
        super().__init__(
            f"SLURM directives incomplete — missing or TODO-sentinel values "
            f"for required keys: {missing_keys}. "
            f"Edit automil/config.yaml: backend.slurm.directives"
        )


class RayClusterUnreachableError(BackendError):
    """Raised when RAY_ADDRESS is set but the cluster is unreachable AND
    allow_local_fallback is False (config: backend.ray.allow_local_fallback).
    """
    def __init__(self, address: str) -> None:
        self.address = address
        super().__init__(
            f"Ray cluster at {address!r} is unreachable and "
            f"backend.ray.allow_local_fallback is False. "
            f"Check RAY_ADDRESS and cluster health."
        )
```

Add corresponding TDD test file at `tests/backends/test_errors_phase6.py`:
```python
"""Phase 6 D-178 error type tests."""
from __future__ import annotations

import pytest

from automil.backends.errors import (
    BackendError,
    BackendNotInstalledError,
    SlurmDirectivesIncompleteError,
    RayClusterUnreachableError,
)


def test_backend_not_installed_error_carries_extra_name():
    exc = BackendNotInstalledError("slurm", "slurm")
    assert exc.extra_name == "slurm"
    assert "pip install -e '.[slurm]'" in str(exc)
    assert isinstance(exc, BackendError)


def test_slurm_directives_incomplete_carries_missing_keys():
    exc = SlurmDirectivesIncompleteError(["partition", "account"])
    assert exc.missing_keys == ["partition", "account"]
    assert "partition" in str(exc)
    assert isinstance(exc, BackendError)


def test_ray_cluster_unreachable_carries_address():
    exc = RayClusterUnreachableError("ray://head:10001")
    assert exc.address == "ray://head:10001"
    assert "ray://head:10001" in str(exc)
    assert isinstance(exc, BackendError)
```

Note: this test file is NEW (not in plan 06-01's stub list). It is a focused TDD file for the error types. Add it to `files_modified` if you split this plan during execution (the executor may add it).
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_errors_phase6.py -x -v</automated>
  </verify>
  <done>
    All three new error classes importable from `automil.backends.errors`. `tests/backends/test_errors_phase6.py` passes 3 tests. `BackendError` itself unchanged (the existing 779 tests still green). Each new class subclasses `BackendError`. Each carries the documented attribute (extra_name / missing_keys / address). Each error message includes the documented recovery hint.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add guarded slurm + ray imports to backends/__init__.py</name>
  <files>src/automil/backends/__init__.py</files>
  <read_first>
    - src/automil/backends/__init__.py (full file — D-68 register decorator + line 72-74 existing guarded LocalBackend import)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-153 — guarded-import precedent + D-69 reasoning for not auto-importing test fixtures)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"src/automil/backends/__init__.py" lines 322-353 — exact extension shape)
  </read_first>
  <behavior>
    - Test 1: `from automil.backends import BACKENDS` works in an environment where neither submitit nor ray is installed (current state of this checkout).
    - Test 2: `BACKENDS` does NOT contain `"slurm"` or `"ray"` keys after a no-extras install (because the guarded imports silently fail).
    - Test 3: When submitit is installed AND `automil.backends.slurm` lands in Wave 2, `BACKENDS["slurm"] is SLURMBackend` (verified by Wave 2's plan 06-04 contract test).
    - Test 4: `import automil` itself never raises ImportError because submitit/ray are absent.
  </behavior>
  <action>
Append to `src/automil/backends/__init__.py` AFTER the existing `from automil.backends import local` block (line 72-74) and BEFORE the `__all__` declaration:

```python
# Opt-in distributed backends (Phase 6 / D-153): guarded imports so
# `pip install -e .` (no extras) never fails. When the extra is missing the
# backend is simply unavailable at runtime; callers attempting to dispatch
# through an unavailable backend get BackendNotInstalledError (raised by the
# config-resolution path, not by import).
try:
    from automil.backends import slurm as _slurm_backend  # noqa: F401  # registers SLURMBackend
except ImportError:
    pass  # [slurm] extra not installed — backend unavailable

try:
    from automil.backends import ray as _ray_backend  # noqa: F401  # registers RayBackend
except ImportError:
    pass  # [ray] extra not installed — backend unavailable
```

DO NOT add `SLURMBackend` / `RayBackend` to `__all__` — their availability depends on the extras (the names won't exist at module level if the imports failed). Consumers who installed the extras import them via `from automil.backends.slurm import SLURMBackend` / `from automil.backends.ray import RayBackend`.

DO re-export the three new error types via `__all__`. Update `__all__` to add `"BackendNotInstalledError"`, `"SlurmDirectivesIncompleteError"`, `"RayClusterUnreachableError"` (alphabetised among the other Plan 02-01 names), and add the import at the top of the module:
```python
from automil.backends.errors import (
    BackendError,
    BackendNotInstalledError,
    SlurmDirectivesIncompleteError,
    RayClusterUnreachableError,
)
```

Add a TDD test at `tests/backends/test_extras_gate.py`:
```python
"""Phase 6 D-153 extras-gate tests — `import automil` must never fail when extras absent."""
from __future__ import annotations

import importlib
import sys


def test_import_automil_backends_no_extras():
    """No-extras install: `import automil.backends` succeeds; SLURM/Ray backends absent from BACKENDS."""
    # If submitit/ray aren't installed, BACKENDS should not contain them.
    # If they ARE installed in the dev env, this is permissive — we only assert NO ImportError.
    importlib.import_module("automil.backends")
    from automil.backends import BACKENDS
    if "submitit" not in sys.modules and "ray" not in sys.modules:
        # Pure no-extras case — neither registered.
        assert "slurm" not in BACKENDS
        assert "ray" not in BACKENDS


def test_three_phase6_errors_in_public_namespace():
    """`from automil.backends import BackendNotInstalledError, ...` works."""
    from automil.backends import (
        BackendNotInstalledError,
        SlurmDirectivesIncompleteError,
        RayClusterUnreachableError,
    )
    assert BackendNotInstalledError.__name__ == "BackendNotInstalledError"
    assert SlurmDirectivesIncompleteError.__name__ == "SlurmDirectivesIncompleteError"
    assert RayClusterUnreachableError.__name__ == "RayClusterUnreachableError"
```
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_extras_gate.py -x -v &amp;&amp; uv run python -c "import automil.backends; print('ok')" &amp;&amp; uv run python -c "from automil.backends import BackendNotInstalledError, SlurmDirectivesIncompleteError, RayClusterUnreachableError; print('ok')"</automated>
  </verify>
  <done>
    `tests/backends/test_extras_gate.py` 2 tests green. `import automil.backends` succeeds in the current checkout (no submitit/ray installed); `BACKENDS` dict does NOT contain `"slurm"` or `"ray"` keys. The three new error names are reachable via `from automil.backends import ...`. The existing 779-test Phase 5 baseline still passes (`uv run pytest tests/ -x -q --co --quiet | tail -5` shows ≥781 collected).
  </done>
</task>

</tasks>

<verification>

```bash
# Extras shape
grep -E '^slurm = ' pyproject.toml
grep -E '^ray\s+= ' pyproject.toml

# No-extras import gate
uv run python -c "import automil.backends; print('ok')"

# Error type re-exports
uv run python -c "from automil.backends import BackendNotInstalledError, SlurmDirectivesIncompleteError, RayClusterUnreachableError; print('ok')"

# This plan's tests + the Wave-0 stubs that depend on errors.py now collect cleanly
uv run pytest tests/backends/test_errors_phase6.py tests/backends/test_extras_gate.py -x -v

# Phase 5 baseline preserved
uv run pytest tests/ -x -q
```

</verification>

<success_criteria>

- [ ] `pyproject.toml` `[project.optional-dependencies]` has `slurm = ["submitit>=1.5.3"]` and `ray = ["ray>=2.55.1"]`; submitit/ray do NOT appear in `[project.dependencies]`.
- [ ] `src/automil/backends/errors.py` has 3 new subclasses of `BackendError`: `BackendNotInstalledError`, `SlurmDirectivesIncompleteError`, `RayClusterUnreachableError`.
- [ ] `src/automil/backends/__init__.py` has guarded `try: from automil.backends import slurm` and same for ray; both `pass` on `ImportError`.
- [ ] `from automil.backends import BackendNotInstalledError, SlurmDirectivesIncompleteError, RayClusterUnreachableError` succeeds.
- [ ] `import automil.backends` does NOT raise ImportError when submitit/ray absent (the current checkout state).
- [ ] No autobench/AUTOBENCH_/benchmarks/ refs added: `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/errors.py src/automil/backends/__init__.py` returns 0 matches.
- [ ] BCK-04 lint clean: `python scripts/check_backend_isolation.py src/automil/` exits 0.
- [ ] Phase 5 779-test baseline + new ~5 tests this plan adds → all green.

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-02-SUMMARY.md` describing: pyproject.toml diff, error-class additions verified, guarded-import block placement, total test count delta.
</output>
