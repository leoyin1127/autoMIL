# Phase 2: Backend ABC + LocalBackend re-export shim + MockSLURM fixture — Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 14 new/modified files
**Analogs found:** 14 / 14

---

## Integration map

| New/Modified File | Role | Data Flow | Closest Existing Analog | Match Quality |
|-------------------|------|-----------|-------------------------|---------------|
| `src/automil/backends/__init__.py` | package, registry | request-response | `src/automil/registry/__init__.py` | exact |
| `src/automil/backends/base.py` | ABC + dataclasses | request-response | `src/automil/registry/variants/model.py` + `src/automil/registry/spec.py` | exact |
| `src/automil/backends/local.py` | shim, service | CRUD | `src/automil/compat.py` + `src/automil/registry/registrar.py` | role-match |
| `src/automil/backends/_orchestrator_daemon.py` | service (rename) | CRUD | `src/automil/orchestrator.py` | exact (git mv) |
| `src/automil/backends/mock_slurm.py` | fixture, service | event-driven | `src/automil/registry/validators/purity.py` (class+state) | partial |
| `src/automil/orchestrator.py` (shim) | re-export shim | — | `src/automil/compat.py` (PEP 562 pattern) | exact |
| `src/automil/cli/cancel.py` | CLI command | request-response | `src/automil/cli/lifecycle/apply.py` | exact |
| `src/automil/cli/resubmit.py` | CLI command | request-response | `src/automil/cli/lifecycle/apply.py` | exact |
| `scripts/check_backend_isolation.py` | lint script | batch | `src/automil/registry/validators/purity.py` (AST walker) | role-match |
| `tests/backends/__init__.py` | test package | — | `tests/fixtures/__init__.py` | exact |
| `tests/backends/test_contract.py` | parameterised contract test | request-response | `tests/test_synthetic_consumer_roundtrip.py` | role-match |
| `tests/test_backend_isolation_lint.py` | lint enforcement test | batch | `tests/test_registry_singleton.py` | role-match |
| `tests/test_cli_cancel_resubmit.py` | CLI integration test | request-response | `tests/test_lifecycle_skeleton.py` | exact |
| `src/automil/compat.py` (D-08 promotion) | re-export shim update | — | `src/automil/compat.py` current | exact |

---

## Pattern catalog

### 1. ABC + abstractmethod design

**Reference:** `src/automil/registry/variants/model.py:1-55`

```python
from abc import ABC, abstractmethod
from typing import Any, Optional

class ModelVariant(ABC):
    """Per-parent model variant."""

    @abstractmethod
    def forward(self, features: Any, coords: Optional[Any] = None) -> Any:
        """Forward pass on a bag of feature vectors."""

    def instance_attention(self, features: Any, coords: Optional[Any] = None) -> Optional[Any]:
        """Optional method with default. Override to surface attention weights."""
        return None
```

**Rule:** Abstract methods use `@abstractmethod`. Optional methods provide a default implementation (return `None`). Type-only imports (`TYPE_CHECKING` block) keep the module loadable without heavy dependencies. Module docstring names the REQ-ID and relevant decisions.

**Phase 2 application:** `Backend` ABC in `backends/base.py` — five abstract methods (`submit`, `poll`, `list_running`, `cancel`, `log_iter`). No optional methods in Phase 2 (Phase 7 adds `healthcheck`). Use `TYPE_CHECKING` block if `Iterator` or `Optional` hint requires stdlib `typing` only.

---

### 2. Frozen dataclass spec

**Reference:** `src/automil/registry/spec.py:1-36`

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

@dataclass(frozen=True)
class VariantSpec:
    name: str
    kind: Kind
    parent: Optional[str]
    base_commit: str
    composite: float
    node_id: str
    created_at: str
    mutations: tuple[str, ...] = field(default_factory=tuple)
```

**Rule:** `frozen=True` makes the dataclass hashable and prevents post-construction mutation. Use `tuple` (not `list`) for sequence fields — tuples are immutable and JSON-serialisable via `dataclasses.asdict`. No `__post_init__` unless invariant checking is needed.

**Phase 2 application:** `JobHandle` and `JobSpec` in `backends/base.py` follow this pattern exactly (D-52, D-54). `JobHandle` uses `tuple` fields for `overlay_files` and `env`. `JobSpec.env` is `tuple[tuple[str, str], ...]` for ordered, hashable env additions.

---

### 3. Module-level registry dict + `@register` decorator

**Reference:** `src/automil/registry/_state.py:1-40` and `src/automil/registry/registrar.py:1-101`

```python
# _state.py — singleton storage
MODEL_VARIANTS: dict[tuple[str, str], type[ModelVariant]] = {}

# registrar.py — decorator
def register(spec: VariantSpec) -> Callable[[T], T]:
    def _decorator(cls: T) -> T:
        if not (isinstance(cls, type) and issubclass(cls, abc_class)):
            raise RegistrationError(...)
        key = key_builder(spec.parent, spec.name)
        if key in store:
            raise RegistrationError(f"... key {key!r} is already registered ...")
        store[key] = cls
        logger.info("Registered %s variant %r ...", spec.kind, spec.name, ...)
        return cls
    return _decorator
```

**Rule:** Registry state lives in a dedicated `_state.py` (not in `__init__.py`) to avoid circular imports. The decorator validates before inserting; raises a named error on conflict. The decorator returns the class unchanged (identity preserved). A `_clear_registry()` test-only function clears all dicts.

**Phase 2 application:** `BACKENDS: dict[str, type[Backend]]` lives in `backends/__init__.py` (simpler than Phase 1's split because there is only one kind). `@Backend.register(name)` is a classmethod-decorator following the same shape: validate subclass, check duplicate name, insert, `logger.info`. `_clear_backends()` test utility for isolation.

---

### 4. Package `__init__.py` as public surface re-export

**Reference:** `src/automil/registry/__init__.py:1-53`

```python
"""Variant registry subpackage (REG-01 / REG-02 / ...)."""
from __future__ import annotations
import logging

from automil.registry.spec import Kind, VariantSpec
from automil.registry.registrar import RegistrationError, register, resolve_model, ...
from automil.registry.errors import ValidationError
from automil.registry.validators import InterfaceValidator, PurityValidator

logger = logging.getLogger(__name__)

__all__ = [
    "Kind", "VariantSpec", "ModelVariant", ...,
    "RegistrationError", "register", "resolve_model", ...,
]
```

**Rule:** `__init__.py` imports only from sibling submodules — never the reverse. `__all__` explicitly lists every exported name. `logger = logging.getLogger(__name__)` is the first non-import line. Comments annotate which plan/phase introduced each surface.

**Phase 2 application:** `backends/__init__.py` re-exports `Backend`, `JobHandle`, `JobSpec`, `JobState`, `LocalBackend`, `MockSLURMBackend`, `BACKENDS`. Comments note D-68/D-69 for why `mock_slurm` is conditionally auto-imported.

---

### 5. Module-level re-export shim (PEP 562 `__getattr__`)

**Reference:** `src/automil/compat.py:57-113` and the planned promotion for `automil.orchestrator`

```python
# compat.py active-aliases section (D-08 promotion rule):
# When Phase 2 promotes `automil.orchestrator.ExperimentOrchestrator`:
import sys, warnings

_DEPRECATION_MESSAGE_FORMAT = (
    "{old_path} moved to {new_path} in Phase {phase}; old import retained "
    "for backwards-compat. Update by {date}."
)

def __getattr__(name: str):
    if name == "ExperimentOrchestrator":
        warnings.warn(
            _DEPRECATION_MESSAGE_FORMAT.format(
                old_path="automil.orchestrator.ExperimentOrchestrator",
                new_path="automil.backends.local.LocalBackend",
                phase=2,
                date="2027-01",
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        from automil.backends._orchestrator_daemon import ExperimentOrchestrator
        return ExperimentOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Rule:** PEP 562 `__getattr__` fires the deprecation warning on USE, not on `import automil.orchestrator`. The old module becomes 5 lines: `# DEPRECATED: see automil.backends` + `__getattr__` + re-export of `*` for attribute access. `compat.py` is updated to remove the `_PLANNED_MIGRATIONS` entry and promote it to active.

**Phase 2 application:** `src/automil/orchestrator.py` becomes the 5-line shim per D-60. `compat.py` promotes the `"automil.orchestrator.ExperimentOrchestrator"` entry.

---

### 6. `_atomic_write_text` for state file mutations

**Reference:** `src/automil/cli/lifecycle/_shared.py:21-38`

```python
def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

**Rule:** `tempfile.mkstemp(dir=<same_dir>)` ensures the rename is on the same filesystem (POSIX atomic). `os.replace` (not `os.rename`) handles existing-file overwrite on all platforms. Cleanup on exception swallows secondary `OSError`.

**Phase 2 application:** `automil cancel` writes `status: cancelled` + `cancelled_at` to `graph.json` via `ExperimentGraph.save()` (preferred) or `_atomic_write_text` for simpler `running/<id>.json` → `archive/<id>/` moves. `mock_slurm.py` writes `mock_slurm_state.json` via the same pattern.

---

### 7. ClickException hard-fail with "Refusing to X" format

**Reference:** `src/automil/cli/lifecycle/_shared.py:63-97` (`_get_node_or_die`) and `src/automil/cli/submit.py:55-58`

```python
# _get_node_or_die error format:
raise click.ClickException(
    f"Node {node_id!r} not found in graph.json. "
    f"available: {sample}{more}. "
    f"Run `automil status` for the full graph state."
)

# submit hard-fail format:
raise click.ClickException(
    f"Refusing to submit: {node} is already {ntype}/{nstatus}. "
    f"Submitting would overwrite its archive and destroy prior results. "
    f"Use 'automil propose' to create a new proposal."
)
```

**Rule:** Format: `"Refusing to <verb>: <what>. <why>. <suggestion>."` — always three parts. Use `_get_node_or_die` from `cli/lifecycle/_shared.py` for node lookup; do not re-implement. All CLI output via `click.echo()`, never `print()`.

**Phase 2 application (D-66):**
```python
raise click.ClickException(
    f"Refusing to cancel: node {node_id!r} is in state {state!r}, not 'running'. "
    f"Only running nodes can be cancelled. "
    f"Use `automil status` to verify the current state."
)
```
`cancel` and `resubmit` both call `_get_node_or_die(adir, node_id)` before any backend interaction.

---

### 8. CLI command file structure + registration

**Reference:** `src/automil/cli/lifecycle/apply.py:1-20` and `src/automil/cli/lifecycle/__init__.py:1-29`

```python
# Per-command file:
"""cancel command: cancel a running experiment via its backend (CLI-03 / D-66)."""
from __future__ import annotations
import click
from automil.cli import main
from automil.cli._helpers import _find_automil_dir
from automil.cli.lifecycle._shared import _get_node_or_die, _atomic_write_text

@main.command("cancel")
@click.argument("node_id")
def cancel(node_id: str):
    """Cancel a running experiment by node_id."""
    adir = _find_automil_dir()
    from automil.backends import BACKENDS   # lazy import
    ...
```

```python
# cli/__init__.py addition (same pattern as existing imports):
from automil.cli import cancel    # noqa: E402,F401
from automil.cli import resubmit  # noqa: E402,F401
```

**Rule:** Each CLI file is self-contained; registers its command on `main` at import time. Lazy imports (`from automil.backends import ...` inside function body) prevent circular imports at module load. `@click.argument("node_id")` for the required positional ID (matches `apply`, `port-variant` pattern). New commands added to `cli/__init__.py` in alphabetic order with `# noqa: E402,F401`.

---

### 9. AST-walker lint script structure

**Reference:** `src/automil/registry/validators/purity.py:65-107` (class-based AST walk pattern)

```python
import ast
from pathlib import Path

class PurityValidator:
    def check(self, module_path: Path) -> None:
        try:
            source = module_path.read_text()
            tree = ast.parse(source, filename=str(module_path))
        except SyntaxError as e:
            raise ValidationError(...) from e

        for node in tree.body:
            self._check_top_level_node(module_path, node)

    def _check_top_level_node(self, module_path: Path, node: ast.AST) -> None:
        if isinstance(node, ast.Assign):
            for sub_node in ast.walk(node.value):
                if isinstance(sub_node, ast.Attribute) and sub_node.attr == "pid":
                    # report violation
                    ...
```

**Rule:** Use `ast.parse()` (never `importlib.import_module` — don't execute user code). Walk with `for node in ast.walk(tree)` for whole-file traversal. Report `file:line` diagnostics. Exit 1 if violations found, exit 0 if clean. Keep the script stdlib-only (no ruff, no mypy).

**Phase 2 application (`scripts/check_backend_isolation.py`):** Walks every `src/automil/**/*.py`. Detects `Attribute` nodes where `attr in {"kill","killpg","getpid"}` and root is `os`; detects `Name` nodes where `id == "Popen"`; detects `Attribute` nodes where `attr == "pid"`. Allowlist: `backends/local.py`, `backends/_orchestrator_daemon.py`. Use `pathlib.Path.rglob("*.py")`. Emit `f"{path}:{node.lineno}: {reason}"` per violation. `sys.exit(1 if violations else 0)`.

---

### 10. Parameterised contract test + synthetic fixture

**Reference:** `tests/test_synthetic_consumer_roundtrip.py:31-65` (_setup, _init_git_repo, _write_archive_spec) and `tests/test_lifecycle_skeleton.py:49-65` (parametrize)

```python
# Parametrize across backends:
@pytest.mark.parametrize("backend_factory", [
    pytest.param(lambda tmp_path: LocalBackend(project_root=tmp_path, ...), id="local"),
    pytest.param(lambda tmp_path: MockSLURMBackend(poll_lag_seconds=0.05), id="mock_slurm"),
])
def test_submit_poll_completed(backend_factory, tmp_path):
    backend = backend_factory(tmp_path)
    ...

# Synthetic graph fixture (from test_synthetic_consumer_roundtrip.py pattern):
def _write_graph_with_running_node(adir: Path, node_id: str) -> None:
    graph = {
        "schema_version": 1,
        "meta": {"best_node_id": None, ...},
        "nodes": {node_id: {"id": node_id, "status": "running", ...}},
    }
    (adir / "graph.json").write_text(json.dumps(graph, indent=2))
```

**Rule:** Use `@pytest.mark.parametrize` with `id=` labels. `backend_factory` is a callable taking `tmp_path` so each test gets a fresh instance. Synthetic `graph.json` written directly (no CLI invocation needed). For `MockSLURMBackend`, pass `poll_lag_seconds=0.05` to keep the suite under 10s.

**Phase 2 application (`tests/backends/test_contract.py`):** Ten scenarios from D-70 point 1. Each scenario receives both `LocalBackend` and `MockSLURMBackend` via parametrize. Fixture creates a minimal project structure (fake `.git`, `automil/config.yaml`, `automil/orchestrator/` dirs).

---

### 11. Registry singleton isolation fixture

**Reference:** `tests/test_registry_singleton.py:24-35`

```python
@pytest.fixture(autouse=True)
def _isolated_registry():
    from automil.registry._state import _clear_registry
    _clear_registry()
    yield
    _clear_registry()
```

**Rule:** `autouse=True` so every test in the file gets isolated state without having to request the fixture. `_clear_*` called both before and after yield. The clear function lives in `_state.py` as a `test-only` function — production code never calls it.

**Phase 2 application:** `tests/backends/test_contract.py` and `tests/test_cli_cancel_resubmit.py` each define `_isolated_backends` fixture clearing `BACKENDS` dict (or simply clearing `MockSLURMBackend` state) before/after each test.

---

## Shared Patterns

### Error handling (hard-fail)
**Source:** `src/automil/cli/lifecycle/_shared.py:63-97`
**Apply to:** `cancel.py`, `resubmit.py`
Import `_get_node_or_die` directly. Do not re-implement node lookup. Extend with state checks using `raise click.ClickException(f"Refusing to cancel: ...")`.

### Atomic write
**Source:** `src/automil/cli/lifecycle/_shared.py:21-38` (`_atomic_write_text`)
**Apply to:** `cancel.py` (graph.json node update), `mock_slurm.py` (state_file persistence)
Import from `automil.cli.lifecycle._shared`. Do not re-implement.

### Module logger
**Source:** `src/automil/registry/registrar.py:16`, `src/automil/registry/variants/model.py:20`
**Apply to:** All new `backends/*.py` files
```python
logger = logging.getLogger(__name__)
```
First non-import line in every module.

### Lazy imports inside CLI functions
**Source:** `src/automil/cli/lifecycle/apply.py:14-18`, `src/automil/cli/reconcile.py:39`
**Apply to:** `cancel.py`, `resubmit.py`
`from automil.backends import BACKENDS` goes inside the Click function body, not at module top level — prevents circular import at `automil.cli` import time.

---

## No Analog Found

All Phase 2 files have strong analogs. No "no analog" entries.

---

## Anti-patterns to avoid (Phase 2 specific)

1. **Importing `_orchestrator_daemon` from anywhere except `backends/local.py`** — BCK-04 lint script enforces this. The shim `orchestrator.py` re-exports via `__getattr__`, not a bare `import *`.
2. **Putting `Popen | os.kill | .pid | os.killpg` in `backends/base.py` or `backends/mock_slurm.py`** — MockSLURM uses `threading.Timer`, never `Popen`. The lint script will fire on any such reference.
3. **Auto-registering `MockSLURMBackend` at package import** — D-69: `mock_slurm` is NOT imported in `backends/__init__.py`; tests do it explicitly. Leaking a test fixture into production config selection is a UX trap.
4. **`cancel()` blocking until state transitions** — D-57: `cancel` is fire-and-forget, returns `None` immediately. The CLI polls for transition; the backend method itself does not block.
5. **`_recover_orphans()` calls in `LocalBackend.__init__`** — Phase 0 CONTEXT.md invariant: `_recover_orphans()` only runs in the daemon loop (`run()`), never on construction. `LocalBackend.__init__` only instantiates `ExperimentOrchestrator` and stores it as `self._daemon`.
6. **Any `benchmarks/` or `AUTOBENCH_` reference in `src/automil/backends/`** — D-70 hard floor; verified by `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/`.

---

## Metadata

**Analog search scope:** `src/automil/registry/`, `src/automil/cli/lifecycle/`, `src/automil/compat.py`, `src/automil/orchestrator.py`, `src/automil/runner.py`, `tests/`
**Files scanned:** 22 source files + 10 test files
**Pattern extraction date:** 2026-05-02
