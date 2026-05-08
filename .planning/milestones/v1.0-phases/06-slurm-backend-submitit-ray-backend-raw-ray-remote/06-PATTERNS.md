# Phase 6: SLURM backend (submitit) + Ray backend (raw ray.remote) — Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 18 (new + modified)
**Analogs found:** 18 / 18

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/automil/backends/slurm.py` | backend (service) | request-response + event-driven | `src/automil/backends/mock_slurm.py` | exact (same role, SLURM timing model) |
| `src/automil/backends/ray.py` | backend (service) | request-response + event-driven | `src/automil/backends/mock_slurm.py` | exact (same role, same ABC) |
| `src/automil/backends/__init__.py` | config/registry | — | self (existing guarded pattern at line 72-73) | exact |
| `src/automil/backends/errors.py` | utility (errors) | — | self (existing `BackendError`) | exact |
| `src/automil/backends/_orchestrator_daemon.py` | service/daemon | event-driven | self (refactor 8+ `running_dir` references) | self-refactor |
| `src/automil/backends/local.py` | backend (service) | CRUD | self (`list_running` scan update) | self-update |
| `src/automil/cli/cancel.py` | CLI command | request-response | self (line 84 path update) | self-update |
| `src/automil/cli/reconcile.py` | CLI command | CRUD | self (line 74 `running_dir` update) | self-update |
| `src/automil/cli/cell.py` | CLI command | CRUD | self (`_count_running_in_cell` scan) | self-update |
| `src/automil/cli/check.py` | CLI command | request-response | self (extend existing check structure) | exact |
| `src/automil/templates/config.yaml.j2` | config | — | self (existing `backend:` region not yet present) | role-match |
| `pyproject.toml` | config | — | self (existing `[project.optional-dependencies]`) | exact |
| `tests/backends/conftest.py` | test fixture | — | self (existing `params=["local", "mock_slurm"]` fixture) | exact |
| `tests/backends/test_contract.py` | test | contract | self (extend `params=`) | exact |
| `tests/backends/test_slurm_directives.py` | test | unit | `tests/test_backend_isolation_lint.py` | role-match (AST/config validation style) |
| `tests/backends/test_running_namespace.py` | test | unit | `tests/backends/test_contract.py` | role-match |
| `tests/backends/test_log_unification.py` | test | integration | `tests/backends/test_contract.py` (S-07, S-08) | role-match |
| `tests/backends/test_node_0176_smoke.py` | test | integration | `tests/test_synthetic_consumer_roundtrip.py` | exact (end-to-end roundtrip pattern) |
| `tests/backends/test_contract_real_slurm.py` | test | contract | `tests/backends/test_contract.py` | exact |
| `tests/backends/test_contract_real_ray.py` | test | contract | `tests/backends/test_contract.py` | exact |
| `CHANGELOG.md` | doc | — | git commit message conventions (no file analog) | none |

---

## Pattern Assignments

### `src/automil/backends/slurm.py` (backend, request-response + event-driven)

**Analog:** `src/automil/backends/mock_slurm.py`

**Imports pattern** (mock_slurm.py lines 30-43):
```python
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Iterator, Optional

from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends import register

logger = logging.getLogger(__name__)
```

**Registration pattern** (mock_slurm.py lines 111-112):
```python
@register("mock_slurm")
class MockSLURMBackend(Backend):
```
Adaptation: use `@register("slurm")` — BUT registration is guarded (see `__init__.py` pattern below). The `slurm.py` module itself still uses `@register("slurm")` at class definition; the guard lives in `__init__.py`.

**Core Backend ABC implementation shape** (mock_slurm.py lines 150-273, abridged skeleton):
```python
def submit(self, spec: JobSpec) -> JobHandle:
    # ... create executor job, persist to running/slurm/<id>.json
    return JobHandle(node_id=spec.node_id, backend="slurm",
                     opaque_id=str(job.job_id), submitted_at=time.time())

def poll(self, handle: JobHandle) -> JobState:
    # ... query job.state, map through _SLURM_STATE_MAP
    return _SLURM_STATE_MAP.get(state_str, JobState.PENDING)

def cancel(self, handle: JobHandle, signal: Optional[int] = None) -> None:
    # ... fire-and-forget; log warning if signal != SIGTERM
    job.cancel()

def list_running(self) -> list[JobHandle]:
    # ... scan running/slurm/*.json; return one handle per file
    ...

def log_iter(self, handle: JobHandle) -> Iterator[str]:
    # ... tail job.paths.stdout with 1s tick; close on terminal
    ...
```

**Atomic write to `running/slurm/<id>.json`** — copy from `local.py` lines 157-173:
```python
import os
import tempfile

running_file = running_dir / f"{spec.node_id}.json"
payload = json.dumps(handle_dict, indent=2)
tmp_fd, tmp_path = tempfile.mkstemp(dir=str(running_dir), suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w") as fh:
        fh.write(payload)
    os.replace(tmp_path, str(running_file))
except Exception:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    raise
```

**State map constant** (pattern from mock_slurm.py line 106-108 + RESEARCH.md §Code Examples):
```python
_TERMINAL_STATES = frozenset({
    JobState.COMPLETED, JobState.CRASHED,
    JobState.CANCELLED, JobState.BUDGET_KILLED,
})

_SLURM_STATE_MAP: dict[str, JobState] = {
    "PENDING":        JobState.PENDING,
    "RUNNING":        JobState.RUNNING,
    "COMPLETED":      JobState.COMPLETED,
    "FAILED":         JobState.CRASHED,
    "CANCELLED":      JobState.CANCELLED,
    "TIMEOUT":        JobState.BUDGET_KILLED,
    "OUT_OF_MEMORY":  JobState.CRASHED,
    "NODE_FAIL":      JobState.CRASHED,
    "BOOT_FAIL":      JobState.CRASHED,
    "PREEMPTED":      JobState.CRASHED,
    "COMPLETING":     JobState.RUNNING,
    "REQUEUED":       JobState.PENDING,
}
```

**`log_iter` tail loop** (local.py lines 404-433 — identical tick pattern, different path source):
```python
offset = 0
while True:
    if log_path.exists():
        try:
            text = log_path.read_text()
        except OSError:
            text = ""
        if len(text) > offset:
            new_text = text[offset:]
            offset = len(text)
            lines = new_text.splitlines(keepends=True)
            for line in lines:
                yield line

    if _is_terminal():
        if log_path.exists():
            try:
                text = log_path.read_text()
            except OSError:
                text = ""
            if len(text) > offset:
                remaining = text[offset:]
                for line in remaining.splitlines(keepends=True):
                    yield line
        return

    time.sleep(1.0)   # 1s tick for SLURM (vs 0.1s for local)
```
Adaptation: path comes from `submitit.Job(folder=..., job_id=handle.opaque_id).paths.stdout` (NOT a hardcoded `f"{job_id}_log.out"` — see RESEARCH.md Pitfall 3). Terminal check uses `_SLURM_STATE_MAP` lookup, not `LocalBackend.poll`.

**`list_running` scan** (local.py lines 322-357):
```python
def list_running(self) -> list[JobHandle]:
    handles: list[JobHandle] = []
    running_dir = self._automil_dir / "orchestrator" / "running" / "slurm"
    if not running_dir.exists():
        return handles

    for spec_file in sorted(running_dir.glob("*.json")):
        try:
            spec = json.loads(spec_file.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("SLURMBackend.list_running: unreadable %s: %s",
                           spec_file.name, exc)
            continue
        # Recover opaque_id (SLURM job_id) + validate against sacct
        opaque_id = spec.get("opaque_id", "")
        # ... poll SLURM state; stale → CRASHED with crash_reason="lost-from-slurm"
        handles.append(JobHandle(
            node_id=spec.get("node_id", spec_file.stem),
            backend="slurm",
            opaque_id=opaque_id,
            submitted_at=spec.get("submitted_at", spec_file.stat().st_mtime),
        ))
    return handles
```

**`cancel` custom-signal warning** (local.py lines 293-300 — copy pattern verbatim):
```python
import signal as signal_module
if signal is not None:
    logger.warning(
        "SLURMBackend.cancel: custom signal %d; "
        "the standard SIGTERM→scancel escalation is bypassed.",
        signal,
    )
```

**Adaptation notes for `slurm.py`:**
- `__init__` takes `(automil_dir: Path, config: dict)` — NOT `(project_root, automil_dir)`. See D-155.
- Use `submitit.AutoExecutor(folder=logs_dir, cluster="debug")` when `config["backend"]["slurm"].get("debug_in_process", False)` is True (for CI).
- Use `timeout_min=max(1, walltime_seconds // 60)` NOT `time=N` (RESEARCH.md Pitfall 2 correction).
- Use `slurm_additional_parameters={"signal": "B:TERM@30"}` NOT `signal=` kwarg (RESEARCH.md Pitfall 1 correction).
- Use `job.paths.stdout` for log path NOT `f"{job_id}_log.out"` (RESEARCH.md Pitfall 3 correction).
- BCK-04: NO `os.kill`, `Popen`, `.pid` — submitit provides all dispatch.
- Zero `autobench`/`AUTOBENCH_`/`benchmarks/` references.

---

### `src/automil/backends/ray.py` (backend, request-response + event-driven)

**Analog:** `src/automil/backends/mock_slurm.py`

**Imports pattern** — same as mock_slurm.py, substitute `ray` for `submitit`:
```python
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Iterator, Optional

import ray
import ray.exceptions

from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends import register

logger = logging.getLogger(__name__)
```

**Registration decorator** — `@register("ray")` on the class (guarded in `__init__.py`).

**Hybrid `ray.init` pattern** (RESEARCH.md Pattern 4, D-161):
```python
def __init__(self, automil_dir: Path, config: dict) -> None:
    self._automil_dir = automil_dir
    self._config = config
    self._jobs: dict[str, ray.ObjectRef] = {}
    self._we_started_ray = False

    if not ray.is_initialized():
        ray_address = os.environ.get("RAY_ADDRESS", "auto")
        try:
            ray.init(address=ray_address, ignore_reinit_error=True,
                     log_to_driver=False)
        except ConnectionError:
            ray.init(ignore_reinit_error=True, log_to_driver=False)
            self._we_started_ray = True
```

**`poll` non-blocking via `ray.wait`** (RESEARCH.md Pattern 5+6, D-164 — with correction):
```python
def poll(self, handle: JobHandle) -> JobState:
    ref = self._jobs.get(handle.opaque_id) or self._restore_ref(handle)
    if ref is None:
        return JobState.CRASHED   # ObjectRef not restorable across restart (D-167)
    ready, not_ready = ray.wait([ref], timeout=0)
    if not_ready:
        return JobState.RUNNING   # Ray collapses PENDING|RUNNING
    try:
        ray.get(ref, timeout=0)
        return JobState.COMPLETED
    except ray.exceptions.RayTaskError:
        return JobState.CRASHED
    except (ray.exceptions.WorkerCrashedError,   # force=True cancel path
            ray.exceptions.TaskCancelledError):  # force=False cancel path
        if _was_cap_cancel(handle, self._automil_dir):
            return JobState.BUDGET_KILLED
        return JobState.CANCELLED
```

**`cancel` with `force=True`** (D-165; signal arg is ignored with logged warning):
```python
def cancel(self, handle: JobHandle, signal: Optional[int] = None) -> None:
    if signal is not None:
        logger.warning(
            "RayBackend.cancel: signal=%d ignored; Ray uses force=True "
            "which terminates via SIGKILL after Ray's ~1s grace.",
            signal,
        )
    ref = self._jobs.get(handle.opaque_id)
    if ref is not None:
        ray.cancel(ref, force=True, recursive=True)
```

**Shutdown in `close()`** (D-161 anti-pattern avoidance):
```python
def close(self) -> None:
    """Shutdown Ray only if WE started the local cluster."""
    if self._we_started_ray and ray.is_initialized():
        ray.shutdown()
```

**`log_iter` tail loop** — same open()+readline loop as local.py and slurm.py, log path is:
```python
log_path = self._automil_dir / "orchestrator" / "running" / "ray" / f"{handle.node_id}.log"
```

**`list_running` scan** — same glob pattern as slurm.py, substitute `"ray"` for `"slurm"`:
```python
running_dir = self._automil_dir / "orchestrator" / "running" / "ray"
```
Stale handles (ObjectRef not restorable) → `CRASHED` with `crash_reason="ray-ref-not-restorable"`.

**Adaptation notes for `ray.py`:**
- `ray.init()` no-args (NOT `local_mode=True`) for local cluster — RESEARCH.md Pitfall 5 correction.
- `_run_experiment_ray` is a **top-level** `@ray.remote` function, NOT a class method.
- `force=True` is valid for `@ray.remote` functions (not for Ray Actors) — D-162 design confirmation.
- BCK-04: NO `os.kill`, `Popen`, `.pid` — ray APIs are sufficient.
- Zero `autobench`/`AUTOBENCH_`/`benchmarks/` references.

---

### `src/automil/backends/__init__.py` (config/registry, guarded import extension)

**Analog:** Self — existing guarded import block (lines 72-74):
```python
from automil.backends import local as _local_backend  # noqa: F401  # D-68: auto-register LocalBackend
from automil.backends.local import LocalBackend  # noqa: F401  # re-export for public surface
# mock_slurm NOT auto-imported here — tests import it explicitly (D-69)
```

**Phase 6 extension pattern** (D-153 — mirror D-69 precedent):
```python
# Opt-in distributed backends: guarded imports so `pip install -e .` (no extras)
# never fails. When the extra is missing, the backend is simply unavailable at
# runtime; BackendNotInstalledError is raised when the config selects it.
try:
    from automil.backends import slurm as _slurm_backend  # noqa: F401
except ImportError:
    pass  # [slurm] extra not installed

try:
    from automil.backends import ray as _ray_backend  # noqa: F401
except ImportError:
    pass  # [ray] extra not installed
```

**`__all__` extension** — add `"SLURMBackend"`, `"RayBackend"` (only if their extras are installed; the guarded try/except means the names won't exist if the import failed, so export them conditionally or add them only in the try block). Simplest pattern: add to `__all__` only what is always importable:
```python
# In __all__, add only the unconditional exports:
"BackendNotInstalledError",  # always available (errors.py)
# SLURMBackend / RayBackend: NOT added to __all__ — consumers who installed the
# extras import from automil.backends.slurm / automil.backends.ray directly.
```

---

### `src/automil/backends/errors.py` (utility, error hierarchy extension)

**Analog:** Self — existing `BackendError` (lines 1-10):
```python
"""Backend error types (BCK-01 / D-68)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BackendError(Exception):
    """Raised when backend registration or dispatch fails."""
```

**Phase 6 extension pattern** (D-178 — add 3 subclasses):
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

---

### `src/automil/backends/_orchestrator_daemon.py` (daemon, running_dir namespace migration)

**Analog:** Self — current flat `running_dir` at line 287 and all 8+ reference sites.

**Current pattern (Phase 5, to be replaced):**
```python
# __init__ (line 287)
self.running_dir = self.orch_dir / "running"

# All reference sites (lines 472, 474, 709, 771, 816, 852, 857, 917, 980):
self.running_dir / f"{node_id}.json"
```

**Phase 6 target pattern** (D-169) — per-backend running_dir resolved at tick time:
```python
# __init__: store orch_dir only; no flat running_dir attribute
self.running_dir = None  # removed; backends own their running/<name>/ subdirs

# In _tick / _launch / _handle_completion / _tick_cells / cap paths:
backend_name = spec.get("metadata", {}).get("backend", "local")
backend_running_dir = self.orch_dir / "running" / backend_name
running_spec = backend_running_dir / f"{node_id}.json"
```

**Startup guardrail pattern** (D-168 — check for flat `running/*.json` before run()):
```python
def run(self) -> None:
    # D-168: refuse to start if flat running/*.json exists (Phase 5 layout)
    flat_running = list((self.orch_dir / "running").glob("*.json"))
    if flat_running and not any(
        (self.orch_dir / "running" / name).is_dir()
        for name in ("local", "slurm", "ray")
    ):
        raise SystemExit(
            "BREAKING CHANGE: flat orchestrator/running/*.json files detected. "
            "autoMIL 6.x uses per-backend namespacing. "
            "Drain in-flight runs with `automil orchestrator stop`, confirm "
            "running/ is empty, then upgrade."
        )
    self._recover_orphans()
    # ... rest of run()
```

**`_atomic_write_lines` helper** — modelled after `_atomic_write_text` (lifecycle/_shared.py lines 21-38):
```python
def _atomic_write_lines(path: Path, lines: list[str]) -> None:
    """Atomic write a list of log lines to path (D-170 / Phase 0 atomic-write pattern).

    Uses tempfile.mkstemp neighbour + os.rename (NOT git checkout — D-25).
    """
    import os, tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.writelines(lines)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

**Terminal-observation log drain** (D-170 — add to `_handle_completion`):
```python
# After terminal state observed, drain backend.log_iter() into archive/<id>/run.log
import signal as _sig
log_archive_path = self.archive_dir / node_id / "run.log"
if self.backend is not None:
    handle = JobHandle(
        node_id=node_id,
        backend=backend_name,
        opaque_id=running_spec.get("opaque_id", ""),
        submitted_at=running_spec.get("submitted_at", 0.0),
    )
    try:
        lines = []
        import threading
        done = threading.Event()
        def _drain():
            for line in self.backend.log_iter(handle):
                lines.append(line)
            done.set()
        t = threading.Thread(target=_drain, daemon=True)
        t.start()
        t.join(timeout=60)
        if not done.is_set():
            logger.warning(
                "log_iter for %s did not close within 60s — force-closing (D-170).",
                node_id,
            )
        _atomic_write_lines(log_archive_path, lines)
    except Exception as exc:
        logger.warning("Could not drain log_iter for %s: %s", node_id, exc)
```

---

### `src/automil/backends/local.py` (backend, `list_running` scan update)

**Analog:** Self — `list_running` lines 322-357.

**Current pattern (line 326):**
```python
for spec_file in sorted(self._running_dir.glob("*.json")):
```
where `self._running_dir = self._daemon.running_dir` (currently flat `orch/running/`).

**Phase 6 target pattern** (D-169):
```python
def list_running(self) -> list[JobHandle]:
    handles: list[JobHandle] = []
    running_dir = self._orch_dir / "running" / "local"  # namespaced per D-169
    if not running_dir.exists():
        return handles
    for spec_file in sorted(running_dir.glob("*.json")):
        # ... rest unchanged
```

`self._running_dir` attribute should point to `running/local/` not flat `running/`. Update the attribute assignment in `__init__`:
```python
self._running_dir: Path = self._orch_dir / "running" / "local"   # was: self._daemon.running_dir
```

Also update `poll()` (line 203): `running_path = self._running_dir / f"{node_id}.json"` — this stays the same since `self._running_dir` is now the namespaced path.

---

### `src/automil/cli/cancel.py` (CLI command, running_dir path update)

**Analog:** Self — line 84:
```python
# Current (line 84):
running_path = orch_dir / "running" / f"{node_id}.json"
```

**Phase 6 target** (D-169):
```python
# Resolve backend name first (D-76 fallback: "local" for legacy nodes)
backend_name: str = node.get("metadata", {}).get("backend", "local")
# ...
running_path = orch_dir / "running" / backend_name / f"{node_id}.json"
```
The `backend_name` is already read at line 80 — the path construction 4 lines later must use it. The rest of cancel.py (steps 5-10) is unchanged.

---

### `src/automil/cli/reconcile.py` (CLI command, `running_dir` per-backend)

**Analog:** Self — line 74:
```python
# Current (line 74):
running_dir=str(orch / "running"),
```

**Phase 6 target** (D-169 — `ExperimentGraph.reconcile` receives the namespaced path):
The reconcile command currently passes `orch/running` to `graph.reconcile()`. Post-migration, `running/` has subdirectories. The reconcile command must either:
1. Pass the parent `orch/running` and let `ExperimentGraph.reconcile` enumerate subdirs, OR
2. Pass per-backend paths for each registered backend.

Simplest pattern (option 1 — least invasive):
```python
running_dir=str(orch / "running"),  # reconcile scans subdirectories
```
`ExperimentGraph.reconcile` itself uses `glob("*.json")` — this must be updated to `rglob("*.json")` so it finds files in `running/local/*.json`, `running/slurm/*.json`, etc. This is the `graph.py` change, not `reconcile.py`.

Alternatively (option 2 — explicit per-backend):
```python
# Pass all registered backend subdirs as a list; ExperimentGraph.reconcile
# accepts either a flat path or a list of paths.
```
**Planner note:** Option 1 with `rglob` in graph.py is simpler and lower-risk. Choose at planning time.

---

### `src/automil/cli/cell.py` (CLI command, `_count_running_in_cell` scan)

**Analog:** Self — `_count_running_in_cell` function lines 18-41:
```python
# Current (line 30-34):
running_dir = adir / "orchestrator" / "running"
if not running_dir.exists():
    return 0
n = 0
for f in running_dir.glob("*.json"):
```

**Phase 6 target** (D-169 — scan all backend subdirs):
```python
running_root = adir / "orchestrator" / "running"
if not running_root.exists():
    return 0
n = 0
for f in running_root.rglob("*.json"):  # rglob to traverse running/local/, running/slurm/, etc.
```
Single-character change: `glob("*.json")` → `rglob("*.json")`.

---

### `src/automil/cli/check.py` (CLI command, SLURM directive validation + Ray reachability)

**Analog:** Self — existing `check()` function structure (lines 15-232).

**Extension pattern** — add two new blocks AFTER the existing registry checks, following the same `issues.append` / `warnings.append` / `click.echo` pattern (lines 64-76 GPU check as model):
```python
# D-172: SLURM directive completeness check
_REQUIRED_SLURM_DIRECTIVES = ["time", "partition", "account", "cpus_per_task", "mem_gb"]
backend_cfg = config.get("backend", {})
if backend_cfg.get("name") == "slurm":
    directives = backend_cfg.get("slurm", {}).get("directives", {})
    for key in _REQUIRED_SLURM_DIRECTIVES:
        val = directives.get(key)
        if val is None:
            issues.append(f"backend.slurm.directives.{key} is missing.")
        elif str(val) == "TODO_FILL_IN":
            issues.append(
                f"backend.slurm.directives.{key} still contains TODO_FILL_IN. "
                f"Set a real value before submitting."
            )
    # framework-mandated signal is NOT operator-overridable
    if "signal" in directives:
        issues.append(
            "backend.slurm.directives.signal must NOT be set by operator "
            "(framework-mandated: B:TERM@30). Remove it from config."
        )

# D-173: Ray cluster reachability advisory
if backend_cfg.get("name") == "ray":
    try:
        import ray  # noqa: PLC0415
    except ImportError:
        issues.append(
            "backend.name is 'ray' but the [ray] extra is not installed. "
            "Run: pip install -e '.[ray]'"
        )
    else:
        ray_address = os.environ.get("RAY_ADDRESS")
        if ray_address:
            # Advisory: try a 1s connect-test (non-blocking)
            try:
                ray.init(address=ray_address, ignore_reinit_error=True,
                         log_to_driver=False)
                click.echo(f"Ray cluster at {ray_address!r}: reachable.")
            except ConnectionError:
                warnings.append(
                    f"RAY_ADDRESS={ray_address!r} set but cluster unreachable "
                    f"(ConnectionError). Advisory only — may be intentionally "
                    f"pre-init."
                )
```

---

### `src/automil/templates/config.yaml.j2` (config template, new `backend:` block)

**Analog:** Self — existing `cap:` and `gate:` blocks (lines 116-138) as structural models:
```yaml
# --- Cap configuration — consumer-supplied, NOT framework-mandated. ---
cap:
  budget_seconds:        21600
  safety_buffer_seconds: 1800
```

**Phase 6 extension** (D-155, D-161 — add after existing `orchestrator:` block):
```yaml
# --- Backend configuration (Phase 6) ---
# Select the job execution backend. Default "local" works on any machine.
# "slurm" requires: pip install -e '.[slurm]' + valid directives below.
# "ray"   requires: pip install -e '.[ray]'   + RAY_ADDRESS env var or local cluster.
backend:
  name: "local"            # "local" | "slurm" | "ray"

  slurm:
    # walltime_seconds is derived from cap.budget_seconds + grace buffer.
    # It maps to submitit's timeout_min (NOT the "time" kwarg — see RESEARCH.md OQ-1).
    walltime_seconds: 21600    # 6h default; override per-campaign
    debug_in_process: false    # set true in CI to use submitit DebugExecutor
    directives:
      time: "TODO_FILL_IN"        # human-readable alias; actual kwarg is timeout_min
      partition: "TODO_FILL_IN"
      account: "TODO_FILL_IN"
      qos: null                   # optional
      cpus_per_task: 8
      mem_gb: 48
      gpus_per_node: 1
      # signal is framework-mandated (B:TERM@30); do NOT set here.

  ray:
    allow_local_fallback: true   # false = raise RayClusterUnreachableError if RAY_ADDRESS unreachable
```

---

### `pyproject.toml` (config, new extras + pytest markers)

**Analog:** Self — existing `[project.optional-dependencies]` (lines 23-29):
```toml
[project.optional-dependencies]
ml = [
    "torch>=2.0",
    "scikit-learn>=1.3",
    "scipy>=1.11",
    "h5py>=3.9",
]
```

**Phase 6 extension** (D-154):
```toml
[project.optional-dependencies]
ml = [...]                              # unchanged
slurm = ["submitit>=1.5.3"]            # BCK-05: opt-in SLURM backend
ray   = ["ray>=2.55.1"]                # BCK-06: opt-in Ray backend
```

**pytest markers extension** (D-175 — existing `[tool.pytest.ini_options]` at line 37-38):
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "requires_slurm: requires SLURM cluster (skip in CI)",
    "requires_ray: requires real Ray cluster (skip in CI)",
]
```

---

### `tests/backends/conftest.py` (test fixture, extend backend parametrisation)

**Analog:** Self — existing `backend` fixture (lines 100-132):
```python
@pytest.fixture(params=["local", "mock_slurm"])
def backend(request, tmp_path):
    if request.param == "local":
        from automil.backends.local import LocalBackend
        # ... build minimal dir tree
        yield LocalBackend(project_root=tmp_path, automil_dir=automil_dir)
    else:
        from automil.backends.mock_slurm import MockSLURMBackend
        yield MockSLURMBackend(poll_lag_seconds=0.05, state_file=...)
```

**Phase 6 extension** — add `"slurm"` and `"ray"` params:
```python
@pytest.fixture(params=["local", "mock_slurm", "slurm", "ray"])
def backend(request, tmp_path):
    if request.param == "local":
        # ... unchanged
    elif request.param == "mock_slurm":
        # ... unchanged
    elif request.param == "slurm":
        pytest.importorskip("submitit")   # skip entire test if [slurm] not installed
        from automil.backends.slurm import SLURMBackend

        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
        config = {
            "backend": {
                "slurm": {
                    "debug_in_process": True,   # uses submitit cluster="debug"
                    "walltime_seconds": 300,
                    "directives": {
                        "partition": "debug", "account": "test",
                        "cpus_per_task": 1, "mem_gb": 4,
                    },
                }
            }
        }
        yield SLURMBackend(automil_dir=automil_dir, config=config)
    else:  # "ray"
        pytest.importorskip("ray")   # skip if [ray] not installed
        import ray
        from automil.backends.ray import RayBackend

        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)   # NOT local_mode=True (deprecated)
        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
        backend_instance = RayBackend(
            automil_dir=automil_dir,
            config={"backend": {"ray": {"allow_local_fallback": True}}},
        )
        yield backend_instance
        # Teardown: shutdown only if RayBackend started Ray locally
        if backend_instance._we_started_ray:
            ray.shutdown()
```

**`wait_for_state` helper** (lines 24-57) — unchanged; used by all backends.
**`make_spec` factory** (lines 64-93) — unchanged.
**`_isolated_backends` fixture** (lines 139-152) — unchanged.

---

### `tests/backends/test_contract.py` (contract test, params extension)

**Analog:** Self — existing `params=["local", "mock_slurm"]` at conftest.py line 100.

**Change:** The `test_contract.py` file itself needs no structural changes. The parametrisation is driven by the `backend` fixture in `conftest.py`. However, some scenario skip guards (`if not hasattr(backend, "_poll_lag")`) must be updated:

Current skip pattern (lines 63-64, 88-89, etc.):
```python
if not hasattr(backend, "_poll_lag"):
    pytest.skip("S-01 requires live daemon — LocalBackend skipped")
```

Phase 6: `SLURMBackend` with `debug_in_process=True` and `RayBackend` with local cluster DO execute jobs (unlike LocalBackend). The skip guard should check for LocalBackend specifically:
```python
from automil.backends.local import LocalBackend
if isinstance(backend, LocalBackend):
    pytest.skip("S-01 requires live daemon — LocalBackend skipped")
```

**Adaptation notes:** Do NOT change the scenario logic — the same S-01..S-12 assertions apply to all four backends. Only the skip guards change from `hasattr(backend, "_poll_lag")` to `isinstance(backend, LocalBackend)`.

---

### `tests/backends/test_slurm_directives.py` (unit test, new file)

**Analog:** `tests/test_backend_isolation_lint.py` (AST/config validation pattern)

**Pattern to copy** (test_backend_isolation_lint.py lines 26-50 — subprocess + assertion style):
```python
def test_check_rejects_todo():
    """automil check raises SlurmDirectivesIncompleteError when directive contains TODO."""
    from automil.backends.errors import SlurmDirectivesIncompleteError
    from automil.cli.check import _validate_slurm_directives   # extracted helper

    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "directives": {
                    "time": "TODO_FILL_IN",
                    "partition": "compute",
                    "account": "mylab",
                    "cpus_per_task": 8,
                    "mem_gb": 48,
                }
            }
        }
    }
    with pytest.raises(SlurmDirectivesIncompleteError) as exc_info:
        _validate_slurm_directives(config)
    assert "time" in exc_info.value.missing_keys
```

**All three tests in this file** use the same `pytest.raises(SlurmDirectivesIncompleteError)` pattern against a helper function extracted from `check.py` (D-172). This avoids spinning up a full Click CLI for unit tests.

---

### `tests/backends/test_running_namespace.py` (unit test, new file)

**Analog:** `tests/backends/test_contract.py` (S-04/S-05 list_running scenarios)

**Pattern to copy** (test_contract.py lines 127-134 — minimal dir setup + assertion):
```python
def test_running_dir_per_backend(tmp_path):
    """Daemon resolves running_dir = orch_dir / "running" / backend_name."""
    from automil.backends._orchestrator_daemon import ExperimentOrchestrator
    # ... set up minimal project dir
    daemon = ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)
    assert daemon.orch_dir / "running" / "local" == daemon._backend_running_dir("local")
    assert daemon.orch_dir / "running" / "slurm" == daemon._backend_running_dir("slurm")
```

```python
def test_daemon_refuses_flat_running(tmp_path):
    """Daemon startup raises if flat running/*.json exists with no namespaced subdirs."""
    # ... write a flat running/somenode.json
    (running_dir / "somenode.json").write_text('{"id": "somenode"}')
    # Start daemon run() — should SystemExit
    import pytest
    with pytest.raises(SystemExit, match="BREAKING CHANGE"):
        daemon.run()
```

---

### `tests/backends/test_log_unification.py` (integration test, new file)

**Analog:** `tests/backends/test_contract.py` S-07 / S-08 (log_iter scenarios, lines 198-235)

**Pattern to copy** (test_contract.py lines 198-212):
```python
def test_archive_run_log_local(backend, tmp_path):
    """Orchestrator drains LocalBackend.log_iter() into archive/<id>/run.log on terminal."""
    if not hasattr(backend, "_poll_lag"):
        pytest.skip("requires mock backend with live log")
    spec = make_spec("node_log_local", tmp_path, command=("echo", "hello"))
    handle = backend.submit(spec)
    wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=5.0)

    # Simulate orchestrator drain via _atomic_write_lines
    lines = list(backend.log_iter(handle))
    log_path = tmp_path / "archive" / "node_log_local" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_lines(log_path, lines)
    assert log_path.exists()
    assert len(log_path.read_text().strip()) > 0
```

---

### `tests/backends/test_node_0176_smoke.py` (integration smoke, new file)

**Analog:** `tests/test_synthetic_consumer_roundtrip.py` (end-to-end roundtrip with `_setup`, `_write_archive_spec`, CliRunner)

**Pattern to copy** — the fixture setup from `test_synthetic_consumer_roundtrip.py` lines 32-65:
```python
def _setup_smoke_project(tmp_path: Path) -> tuple[Path, Path, str]:
    """Set up a minimal project with a synthetic training script."""
    _copy_fixture(tmp_path)
    _init_git_repo(tmp_path)
    # Write a synthetic train.py that always produces result.json composite=0.502
    (tmp_path / "train.py").write_text("""
import json, pathlib
result = {"status": "completed",
          "metrics": {"val_auc": 0.87, "val_bacc": 0.81,
                      "test_auc": 0.87, "test_bacc": 0.83},
          "composite": 0.502, "elapsed_seconds": 10}
pathlib.Path("result.json").write_text(json.dumps(result))
""")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, ...)
    head = ...
    return tmp_path, tmp_path / "automil", head
```

**Test structure** (parametrised over three backends):
```python
@pytest.mark.parametrize("backend_name", ["local", "slurm-debug", "ray-local"])
def test_node_0176_equivalent_composite_within_tolerance(backend_name, tmp_path):
    """Acceptance smoke: composite within ±0.005 of LocalBackend baseline."""
    pytest.importorskip("submitit") if "slurm" in backend_name else None
    pytest.importorskip("ray") if "ray" in backend_name else None
    # ... set up backend, submit, wait, assert composite within ±0.005
    assert abs(result_json["composite"] - LOCAL_BASELINE) <= 0.005
```

---

### `tests/backends/test_contract_real_slurm.py` (real-cluster contract, new file)

**Analog:** `tests/backends/test_contract.py` (exact copy of scenarios, real backend)

**Pattern to copy** — import the same scenarios as functions and re-parametrize:
```python
import pytest

pytestmark = pytest.mark.requires_slurm


@pytest.fixture
def backend(tmp_path):
    """Real SLURMBackend against an actual SLURM cluster."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend
    # config from env or fixture file
    ...
```

All S-01..S-12 test functions are re-used verbatim from `test_contract.py` — no duplication of logic.

---

### `tests/backends/test_contract_real_ray.py` (real-cluster contract, new file)

**Analog:** `tests/backends/test_contract.py` — same as above, substitute Ray:
```python
pytestmark = pytest.mark.requires_ray
```

---

## Shared Patterns

### Atomic Write (D-25 / Phase 0 pattern)
**Source:** `src/automil/cli/lifecycle/_shared.py` lines 21-38
**Apply to:** All backend `running/<backend>/<id>.json` writes, `archive/<id>/run.log` orchestrator drain
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
            os.unlink(tmp_path)    # os.unlink(), NEVER git checkout (memory: feedback_never_blind_checkout)
        except OSError:
            pass
        raise
```
Variant for log lines: `_atomic_write_lines(path, lines: list[str])` — same skeleton, `f.writelines(lines)` instead of `f.write(content)`.

### Backend Registration via Decorator
**Source:** `src/automil/backends/__init__.py` lines 30-60 (`register` decorator)
**Apply to:** `slurm.py` (`@register("slurm")`), `ray.py` (`@register("ray")`)
```python
from automil.backends import register

@register("slurm")   # or "ray"
class SLURMBackend(Backend):
    ...
```

### Guarded Import for Optional Extras
**Source:** `src/automil/backends/__init__.py` lines 72-74 (existing local + mock_slurm precedent)
**Apply to:** `__init__.py` extension for slurm + ray
```python
try:
    from automil.backends import slurm as _slurm_backend  # noqa: F401
except ImportError:
    pass
```

### `pytest.importorskip` for Optional Backend Tests
**Source:** pytest stdlib (`pytest.importorskip("submitit")`)
**Apply to:** `conftest.py` `"slurm"` and `"ray"` fixture branches; `test_node_0176_smoke.py`
```python
pytest.importorskip("submitit")   # whole test is skipped if submitit not installed
pytest.importorskip("ray")        # same for ray
```

### `_TERMINAL_STATES` Frozenset
**Source:** `src/automil/backends/mock_slurm.py` line 106-108
**Apply to:** `slurm.py`, `ray.py` (identical constant)
```python
_TERMINAL_STATES = frozenset({
    JobState.COMPLETED, JobState.CRASHED,
    JobState.CANCELLED, JobState.BUDGET_KILLED,
})
```

### Log Iterator Tail Loop (D-58)
**Source:** `src/automil/backends/local.py` lines 404-433
**Apply to:** `slurm.py` `log_iter` (1s tick, path from `job.paths.stdout`), `ray.py` `log_iter` (1s tick, path from `running/ray/{node_id}.log`)
Core loop pattern is identical; only the path source and tick interval differ.

### Custom-Signal Warning (D-57)
**Source:** `src/automil/backends/local.py` lines 293-300
**Apply to:** `slurm.py` cancel (warns when signal != SIGTERM), `ray.py` cancel (warns and ignores all non-None signals)

### Click `issues.append` / `warnings.append` Pattern
**Source:** `src/automil/cli/check.py` lines 27-76
**Apply to:** SLURM directive validation block and Ray reachability advisory block in `check.py`

---

## No Analog Found

All files in Phase 6 have close analogs. The table below lists cases where the planner should rely primarily on RESEARCH.md patterns rather than codebase analogs:

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `CHANGELOG.md` | doc | — | No existing CHANGELOG; nearest analog is git commit message conventions and the `BREAKING:` header template in CONTEXT.md `<specifics>` |
| `@ray.remote _run_experiment_ray` function | utility | batch | No existing remote-function dispatch in codebase; RESEARCH.md Pattern 4 is the primary reference |
| `_run_experiment_subprocess` function | utility | batch | Closest is `_orchestrator_daemon._launch()` lines 612-710, but the remote-function wrapper shape is new |

---

## Critical API Corrections for Planner

These corrections from RESEARCH.md MUST be applied in the plan files — they override the decisions in CONTEXT.md where the decisions reference deprecated/wrong APIs:

| Decision | Wrong API (D-155/D-159/D-164/D-174) | Correct API (RESEARCH.md OQ-1..4) |
|---|---|---|
| D-155: SLURM time kwarg | `update_parameters(time=N)` | `update_parameters(timeout_min=max(1, walltime_seconds//60))` |
| D-155: SLURM signal kwarg | `update_parameters(signal="B:TERM@30")` | `update_parameters(slurm_additional_parameters={"signal": "B:TERM@30"})` |
| D-159: Log file path | `f"{job_id}_log.out"` | `job.paths.stdout` (resolves to `{job_id}_0_log.out`) |
| D-164: poll exception map | only `TaskCancelledError` | also `WorkerCrashedError` (force=True path) |
| D-174: CI Ray init | `ray.init(local_mode=True)` | `ray.init(ignore_reinit_error=True)` + teardown `ray.shutdown()` |

---

## Metadata

**Analog search scope:** `src/automil/backends/`, `src/automil/cli/`, `src/automil/templates/`, `tests/backends/`, `tests/`, `scripts/`
**Files scanned:** 21 source files + 2 test directories
**Pattern extraction date:** 2026-05-06
