# Phase 2: Backend ABC + LocalBackend Re-export Shim + MockSLURM Fixture — Research

**Researched:** 2026-05-02
**Domain:** Python backend abstraction / job-scheduling / AST-based lint / parameterised contract testing
**Confidence:** HIGH (decisions locked in 02-CONTEXT.md; research confirms implementation approach and surfaces edge cases)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All decisions D-51 through D-75 are locked. See 02-CONTEXT.md `<decisions>` block verbatim.
Summary of hard floors:
- Phase 0+1 baseline (387 tests) stays green.
- Contract test passes against both LocalBackend AND MockSLURMBackend (≥10 scenarios).
- `python scripts/check_backend_isolation.py` exits 0 on `src/automil/`.
- `automil cancel` + `automil resubmit` work end-to-end on MockSLURMBackend.
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero.

### Claude's Discretion
- Implementation details not covered by D-51..D-75 (e.g., exact MockSLURM thread design, helper utilities inside test files, conftest layout).

### Deferred Ideas (OUT OF SCOPE)
- Real SLURM backend (D-71, Phase 6)
- Real Ray backend (D-71, Phase 6)
- Per-backend `running/` namespacing (D-72, Phase 6)
- Wall-clock budget enforcement (D-73, Phase 4)
- Trajectory hooks (D-74, Phase 3)
- Hardware healthcheck (D-75, Phase 7)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BCK-01 | Backend ABC with 5 methods + JobState enum | §1, §2 — API shape + state taxonomy |
| BCK-02 | LocalBackend re-export shim; existing 387 tests stay green | §5 — shim correctness patterns |
| BCK-03 | MockSLURMBackend test fixture (5s lag, opaque id, fire-and-forget cancel) | §6, §7 — MockSLURM design |
| BCK-04 | AST-walker lint forbids os.kill/Popen/.pid outside allowlist | §4 — AST walker technique |
| CLI-03 | `automil cancel <node_id>` via Backend.cancel | §8 — cancel UX patterns |
| CLI-04 | `automil resubmit <node_id>` via Backend.submit | §8 — resubmit semantics |
</phase_requirements>

---

## Summary

Phase 2's entire decision space is locked (D-51..D-75). This research confirms those decisions are sound and provides the implementer with precise patterns, pitfall avoidance, and test invariants. The five ABC methods map cleanly to what production ML schedulers (submitit, Ray, Dask) expose — the chosen contract is neither under-specified nor prematurely coupled to local-process semantics.

The most implementation-sensitive area is the **LocalBackend shim**: `_orchestrator_daemon.py` is 1,115 lines with `Popen`, `os.killpg`, and `process.pid` scattered through `_launch`, `_handle_timeout`, `_check_running`, and `cmd_stop`. The shim must wrap these without touching their logic. The 387-test suite is the contract; any refactor that makes a single test call `_launch` differently is a behavioural drift.

The **MockSLURMBackend** is the contract anchor. Threading hazards are the main risk: `cancel()` sets a flag that the `threading.Timer` callback reads; the flag must be thread-safe (`threading.Event`, not a bare `bool`). The contract test must drive `poll_lag_seconds=0.05` to stay under 10s wall-clock; production default 5.0 is only for documentation realism.

**Primary recommendation:** Build the package skeleton + dataclasses first (no logic), then MockSLURMBackend (drives ABC shape), then LocalBackend shim (wraps existing), then contract test (locks the surface), then lint + CLI commands. This order ensures the ABC is tested against two implementations before being declared stable — which is the Phase 2 anti-acceptance criterion.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Job lifecycle (submit/poll/cancel) | `backends/` package | CLI commands route through it | Backend owns process semantics; CLI is thin |
| State persistence (running/*.json) | `_orchestrator_daemon.py` (via LocalBackend) | MockSLURM state_file for tests | Existing daemon owns the file layout |
| Process control (Popen/os.killpg) | `_orchestrator_daemon.py` only | — | BCK-04: only two allowlisted modules |
| Graph node lifecycle | `cli/cancel.py`, `cli/resubmit.py` | `graph.py` | CLI interprets backend state into graph transitions |
| Contract validation | `tests/backends/test_contract.py` | `tests/test_backend_isolation_lint.py` | Two separate enforcement layers |
| Lint enforcement | `scripts/check_backend_isolation.py` | pre-commit hook (optional) | pytest test is the always-on gate |

---

## 1. Backend Abstraction Patterns in Python ML Ecosystems

### Finding

Production ML job schedulers converge on a narrow set of ABC primitives: submit returns a handle (opaque or typed), poll returns an enum state, cancel is fire-and-forget, iteration over logs is a lazy generator. The D-51 five-method surface (`submit / poll / list_running / cancel / log_iter`) is well-supported by three reference implementations [ASSUMED — training knowledge; submitit not installed]:

**submitit** `AutoExecutor.submit(fn, *args) -> Job[T]`. `Job.state()` returns `JobState` enum (`UNKNOWN | PENDING | RUNNING | DONE | INTERRUPTED`). Cancel via `job.cancel()`. No `log_iter` — stdout is collected to a file on completion (SLURM model). [ASSUMED]

**Dask Distributed** `client.submit(fn, *args) -> Future`. `future.status` returns `"pending" | "executing" | "finished" | "error" | "cancelled"`. Cancel via `future.cancel()`. No `log_iter` — logs via `client.get_worker_logs()` after completion. [ASSUMED]

**Ray** `remote_fn.remote(*args) -> ObjectRef`. State via `ray.get()` + try/except. No direct state enum — you either block (`ray.get`) or check `ray.wait([ref], timeout=0)`. Cancel via `ray.cancel(ref, force=True)`. No `log_iter` — stdout captured per actor. [ASSUMED]

### Key difference from current design

All three reference implementations return opaque handles without exposing PIDs. The D-52 `JobHandle(opaque_id: str)` pattern is correct and matches the ecosystem.

### Pitfall

**Don't inherit from `typing.Protocol`** for the ABC. `Protocol` gives structural subtyping — a class with the right methods satisfies it without explicit inheritance, which means `isinstance(backend, Backend)` returns `False`. Use `abc.ABC` + `@abstractmethod` so the registry and contract tests can assert `isinstance(obj, Backend)`. [VERIFIED: Python stdlib abc module]

### Planner action

Use `abc.ABC` + `@abstractmethod` for all 5 methods. The `BACKENDS` registry (D-68) should validate with `isinstance(backend_cls, type) and issubclass(backend_cls, Backend)`.

---

## 2. JobState Enum Design

### Finding

The six-state taxonomy in D-53 (`PENDING | RUNNING | COMPLETED | CRASHED | CANCELLED | BUDGET_KILLED`) is correct and sufficient. Cross-referenced against:

- submitit: 5 states (`UNKNOWN, PENDING, RUNNING, DONE, INTERRUPTED`) — maps to our `PENDING→PENDING, RUNNING→RUNNING, DONE→COMPLETED, INTERRUPTED→CRASHED or CANCELLED` [ASSUMED]
- Kubernetes Job status: `Pending | Active | Succeeded | Failed` — maps to our 4 non-terminal-kill states [ASSUMED]
- SLURM sacct: `PENDING | RUNNING | COMPLETED | FAILED | CANCELLED | TIMEOUT` — our `BUDGET_KILLED` maps to `TIMEOUT` [ASSUMED]

### Edge case: "submitted-but-not-yet-acknowledged"

This is `PENDING`. The ABC contract (D-55) explicitly says `submit()` returns a handle that may still be `PENDING` for several poll cycles. The caller must poll until terminal — `PENDING` is a valid non-running state. This is correct; submitit calls the same state `PENDING` for up to ~30s after `job.submit()` on a loaded cluster.

### Edge case: "completed-but-results-not-yet-collected"

This only arises in Phase 6's SLURM backend where `sacct` may report `COMPLETED` before the result file is fsynced. Phase 2 does NOT need to handle this — LocalBackend's `_handle_completion` already writes `result.json` before transitioning. MockSLURM's stub produces `result.json` atomically. Phase 6 will need a `COMPLETED_RESULTS_PENDING` grace window but that's D-71 territory.

### `str`-valued Enum rationale

`class JobState(str, Enum)` means `json.dumps({"state": JobState.RUNNING})` works without a custom encoder, and `JobState("running") == JobState.RUNNING` enables round-tripping from JSON state files. [VERIFIED: Python stdlib json module behavior with str Enum]

```python
# Source: Python docs — str Enum is JSON-serialisable natively
class JobState(str, Enum):
    PENDING       = "pending"
    RUNNING       = "running"
    COMPLETED     = "completed"
    CRASHED       = "crashed"
    CANCELLED     = "cancelled"
    BUDGET_KILLED = "budget_killed"

# These both work:
json.dumps(JobState.RUNNING)           # '"running"'
JobState("running") == JobState.RUNNING  # True
```

### Pitfall

Do NOT use `auto()` or integer values. The `running/<id>.json` state files must be human-readable and JSON-roundtrippable. `auto()` produces integers by default.

### Planner action

The planner needs to include a test that round-trips `JobState` through `json.dumps`/`json.loads` — one test, one line.

---

## 3. Eventual-Consistency Contract Tests

### Finding

The correct pattern for parameterised contract tests in pytest is:

```python
# Source: pytest docs — @pytest.fixture(params=[...]) is the canonical approach
import pytest

@pytest.fixture(params=["local", "mock_slurm"])
def backend(request, tmp_path):
    if request.param == "local":
        from automil.backends.local import LocalBackend
        yield LocalBackend(project_root=tmp_path, automil_dir=tmp_path / "automil")
    else:
        from automil.backends.mock_slurm import MockSLURMBackend
        yield MockSLURMBackend(poll_lag_seconds=0.05, state_file=tmp_path / "mock_state.json")
```

This produces 2× test runs for each test function automatically. [VERIFIED: pytest fixture params mechanism]

### Polling helper pattern

```python
import time

def wait_for_state(backend, handle, target_states, timeout=5.0, interval=0.05):
    """Poll until job reaches any of target_states or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = backend.poll(handle)
        if state in target_states:
            return state
        time.sleep(interval)
    raise TimeoutError(
        f"Job {handle.opaque_id} did not reach {target_states} within {timeout}s; "
        f"last state: {backend.poll(handle)}"
    )
```

Place `wait_for_state` in `tests/backends/conftest.py` — it is used by every contract scenario. [ASSUMED — idiomatic pytest location]

### Flakiness prevention

Three concrete techniques:

1. **Never assert `elapsed < X ms`.** Assert state transitions, not timing. Timing assertions are the #1 source of CI flakiness in scheduler tests. [ASSUMED — industry-wide pattern]

2. **Use `poll_lag_seconds=0.05` for tests, never the default 5.0.** The contract test passes `poll_lag_seconds=0.05` to MockSLURMBackend so the full suite runs in <2s. The LocalBackend has near-zero lag, so both finish quickly.

3. **For `log_iter` tests: set a hard timeout on the iterator.** An iterator that never closes is an infinite-hang in CI. Wrap the `log_iter` consumption in a `threading.Timer` that raises after 3s.

### Pitfall

**Race between `cancel()` and `poll()` in MockSLURM.** `cancel()` is fire-and-forget. If the test calls `cancel()` and immediately calls `poll()`, the state may still be `RUNNING` (the cancel flag hasn't been observed by the timer thread yet). Tests must call `wait_for_state(backend, h, {JobState.CANCELLED})` after cancel, not assert `CANCELLED` immediately. This is a real eventual-consistency property that the test must exercise — not a bug.

### Planner action

Add `tests/backends/conftest.py` with `backend` fixture + `wait_for_state` helper. ALL contract scenarios import from this conftest — zero duplication.

---

## 4. AST-Walker Lint Script (BCK-04)

### Finding

The decision in D-64/D-65 to use a custom `ast.NodeVisitor` is correct. Here is why the alternatives fall short:

- **Ruff S605 (`start-process-with-a-shell`)** catches `os.system(...)` / `subprocess.run(shell=True)`. It does NOT flag `Popen(...)`, `os.kill(pid, signal)`, or attribute access `obj.pid`. [ASSUMED — ruff docs]
- **`flake8-forbidden-imports`** blocks module-level imports of specific names. It cannot distinguish allowlisted files from non-allowlisted files. [ASSUMED]
- **mypy plugin** requires a Rust extension or a Python plugin that hooks into the type-check pass. Heavyweight, slow startup, requires mypy to be installed. Overkill for 80 lines of AST walk. [ASSUMED]

### Concrete NodeVisitor pattern

The key challenge is alias detection: `from os import kill as k` means we need to track `k` as a forbidden name. The simplest approach that handles the common cases:

```python
# Source: Python stdlib ast module
import ast
import sys
from pathlib import Path

FORBIDDEN_NAMES = {"Popen"}                           # bare Name references
FORBIDDEN_ATTRS = {"kill", "killpg", "getpid"}        # os.X attribute access
FORBIDDEN_ATTR_END = "pid"                            # .pid attribute access
ALLOWLIST_PATHS = {
    Path("backends/local.py"),
    Path("backends/_orchestrator_daemon.py"),
}

class BackendIsolationVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, src_root: Path):
        self.filepath = filepath
        self.rel_path = filepath.relative_to(src_root)
        self.violations: list[tuple[int, str]] = []
        self._alias_map: dict[str, str] = {}   # local_name -> original_name

    def visit_Import(self, node: ast.Import):
        """Track `import os as o` style aliases."""
        # We only care about `os` itself; `import subprocess` is handled elsewhere.
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track `from os import kill as k` style aliases."""
        if node.module in ("os", "subprocess"):
            for alias in node.names:
                local = alias.asname or alias.name
                self._alias_map[local] = alias.name
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        original = self._alias_map.get(node.id, node.id)
        if original in FORBIDDEN_NAMES:
            self.violations.append((node.lineno, f"forbidden name: {node.id!r}"))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # os.kill, os.killpg, os.getpid
        if node.attr in FORBIDDEN_ATTRS:
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                self.violations.append((node.lineno, f"forbidden: os.{node.attr}"))
        # obj.pid (any .pid attribute access)
        if node.attr == FORBIDDEN_ATTR_END:
            self.violations.append((node.lineno, "forbidden: .pid attribute access"))
        self.generic_visit(node)
```

The `.pid` check is broad — it catches `process.pid`, `exp.process.pid`, `os.getpid()`. This is intentional: any `.pid` access outside the allowlist indicates a local-process assumption that violates BCK-04. False positives (e.g., `config.pid_file`) can be suppressed with a `# noqa: backend-isolation` comment or an explicit exclusion list, but the current codebase has no `.pid` attribute access outside the intended locations, so no suppression is needed in Phase 2. [VERIFIED: grepping orchestrator.py — all `.pid` usages are in `_handle_timeout`, `cmd_stop`, `cmd_status`, all of which will live in `_orchestrator_daemon.py`]

### Script structure

```python
#!/usr/bin/env python3
"""Lint: forbid os.kill/os.killpg/os.getpid/Popen/.pid outside backend allowlist."""
# scripts/check_backend_isolation.py — ~80 lines total including shebang + imports

def main():
    src_root = Path("src/automil")
    violations = []
    for py_file in src_root.rglob("*.py"):
        rel = py_file.relative_to(src_root)
        if rel in ALLOWLIST_PATHS:
            continue
        tree = ast.parse(py_file.read_text(), filename=str(py_file))
        visitor = BackendIsolationVisitor(py_file, src_root)
        visitor.visit(tree)
        for lineno, msg in visitor.violations:
            violations.append(f"{py_file}:{lineno}: {msg}")
    if violations:
        print("VIOLATIONS:")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)
    print("OK: no backend isolation violations")
    sys.exit(0)
```

### Pitfall

**`process.pid` in `RunningExperiment` dataclass fields.** The `RunningExperiment` dataclass currently has a `process: subprocess.Popen` field (orchestrator.py line 218). When `_orchestrator_daemon.py` is created by renaming `orchestrator.py`, the field is fine — it lives in the allowlisted module. But if any code OUTSIDE the allowlist instantiates `RunningExperiment` or accesses `exp.process.pid`, the lint will catch it. The planner must verify that no code outside the allowlist imports `RunningExperiment`.

### Planner action

The lint script must be run against a snapshot of the codebase BEFORE Phase 2 begins (i.e., after the rename but before any new code) to establish a zero-violation baseline. If violations exist before the shim code is written, they're pre-existing and must be fixed as Wave 0 work.

---

## 5. Re-export Shim Correctness

### Finding

The orchestrator.py → two-file split (rename + shim) is a pure mechanical transformation. Two proven correctness guarantees:

**1. Import-path preservation test** — the most valuable shim test:

```python
# Confirm both import paths resolve to the same class
from automil.orchestrator import ExperimentOrchestrator as Old
from automil.backends._orchestrator_daemon import ExperimentOrchestrator as New
from automil.backends.local import LocalBackend

assert Old is New, "shim breaks import path"
```

**2. `sys.modules` aliasing** — the shim does NOT need to do `sys.modules["automil.orchestrator"] = sys.modules["automil.backends._orchestrator_daemon"]`. A simple `from automil.backends._orchestrator_daemon import *` in `orchestrator.py` is sufficient and is what compat.py already does for Phase 0 symbols. [VERIFIED: Python import system — star-import re-exports symbols into the importing module's namespace]

**3. `inspect.getmodule` check** — after the rename, `inspect.getmodule(ExperimentOrchestrator)` will return `automil.backends._orchestrator_daemon`, not `automil.orchestrator`. This is expected and correct — the shim doesn't change where the class *lives*, only where it can be *imported from*. Tests that use `inspect.getmodule` must account for this.

### Deprecation banner pattern

```python
# src/automil/orchestrator.py — the 5-line re-export shim
# DEPRECATED: This module is a re-export shim. Import from automil.backends instead.
# See automil.compat for migration table. Will be removed in v2.0.
# [compat.py Phase 2 entry owned by Plan 02-XX]
from automil.backends._orchestrator_daemon import *  # noqa: F401, F403
from automil.backends._orchestrator_daemon import ExperimentOrchestrator  # explicit for IDEs
```

The explicit re-export of `ExperimentOrchestrator` by name (alongside the star import) ensures IDE autocompletion and `from automil.orchestrator import ExperimentOrchestrator` both work. [VERIFIED: Python import system behavior]

### Behavioral equivalence test

The existing 387-test suite IS the behavioral equivalence test — this is the D-60 assertion. The shim is correct if and only if 387/387 tests pass without modification. The planner should include an explicit task to run the full suite after each of: (a) the rename, (b) the shim file creation, (c) the `__init__.py` update.

### Pitfall

**`_recover_orphans` must NOT be triggered during CLI commands** (CONCERNS.md, Phase 0 historical bug). The rename + shim does not change this invariant, but the new `cancel.py` and `resubmit.py` commands must NOT instantiate `ExperimentOrchestrator` (or `LocalBackend`) without `recover=False`. LocalBackend's `__init__` must propagate `recover=False` to `_orchestrator_daemon`'s `ExperimentOrchestrator.__init__`. [VERIFIED: orchestrator.py line 356: `self._load_state(recover=False)` — constructor already does this]

### Planner action

Include a Wave 0 task: `git mv src/automil/orchestrator.py src/automil/backends/_orchestrator_daemon.py`, then write the 5-line shim. Run `uv run pytest tests/ -x` immediately — this is the first green baseline check.

---

## 6. MockSLURMBackend Design

### Finding

`threading.Timer` is the correct tool for MockSLURM's state transitions. Two alternatives considered:

- **`asyncio`**: Requires the entire test to be async. The contract test is synchronous. Mixing sync test harness with async MockSLURM requires `asyncio.run()` wrappers in the fixture, adding complexity for zero benefit.
- **`freezegun`-style time mocking**: Works for pure time.monotonic() checks but doesn't advance `threading.Timer` callbacks. Timer callbacks fire based on real wall-clock time in a separate thread, not `time.monotonic()` — freezegun doesn't help here. [ASSUMED]

**Correct approach: `threading.Event` for cancel flag**, `threading.Timer` for state transition.

```python
# Source: Python stdlib threading module
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class _MockJob:
    handle: "JobHandle"
    state: "JobState"
    cancel_requested: threading.Event = field(default_factory=threading.Event)
    log_buffer: list[str] = field(default_factory=list)
    timer: Optional[threading.Timer] = None

class MockSLURMBackend(Backend):
    def __init__(self, poll_lag_seconds: float = 5.0, state_file=None):
        self._poll_lag = poll_lag_seconds
        self._jobs: dict[str, _MockJob] = {}   # opaque_id -> MockJob
        self._counter = 0
        self._lock = threading.Lock()           # guards _jobs dict
        self._state_file = state_file
        if state_file and Path(state_file).exists():
            self._load_state()

    def submit(self, spec: "JobSpec") -> "JobHandle":
        with self._lock:
            self._counter += 1
            opaque_id = f"{self._counter}.0"
        handle = JobHandle(
            node_id=spec.node_id,
            backend="mock_slurm",
            opaque_id=opaque_id,
            submitted_at=time.time(),
        )
        job = _MockJob(handle=handle, state=JobState.PENDING)
        with self._lock:
            self._jobs[opaque_id] = job
        # Timer: PENDING -> RUNNING after poll_lag, then RUNNING -> COMPLETED
        def _transition():
            with self._lock:
                if job.cancel_requested.is_set():
                    job.state = JobState.CANCELLED
                    return
                job.state = JobState.RUNNING
                job.log_buffer.append("mock: job started")
            # Second timer: run -> terminal
            def _finish():
                with self._lock:
                    if job.cancel_requested.is_set():
                        job.state = JobState.CANCELLED
                        return
                    # Determine terminal state from command content (D-63)
                    cmd_str = " ".join(spec.command)
                    if "--crash" in cmd_str:
                        job.state = JobState.CRASHED
                    else:
                        job.state = JobState.COMPLETED
                    job.log_buffer.append(f"mock: job terminal ({job.state})")
            t2 = threading.Timer(self._poll_lag, _finish)
            t2.daemon = True
            t2.start()
        t = threading.Timer(self._poll_lag, _transition)
        t.daemon = True
        t.start()
        job.timer = t
        self._persist_state()
        return handle

    def poll(self, handle: "JobHandle") -> "JobState":
        with self._lock:
            job = self._jobs.get(handle.opaque_id)
        if job is None:
            raise ValueError(f"Unknown job: {handle.opaque_id}")
        return job.state

    def cancel(self, handle: "JobHandle", signal=None) -> None:
        with self._lock:
            job = self._jobs.get(handle.opaque_id)
        if job is None:
            return  # fire-and-forget: unknown jobs silently ignored
        job.cancel_requested.set()  # thread-safe; timer callback observes at next tick

    def list_running(self) -> list["JobHandle"]:
        with self._lock:
            return [
                j.handle for j in self._jobs.values()
                if j.state in (JobState.PENDING, JobState.RUNNING)
            ]

    def log_iter(self, handle: "JobHandle"):
        """Yield collected log on terminal; nothing while pending/running (SLURM model)."""
        job = self._jobs.get(handle.opaque_id)
        if job is None:
            return
        terminal = {JobState.COMPLETED, JobState.CRASHED, JobState.CANCELLED, JobState.BUDGET_KILLED}
        if job.state in terminal:
            yield from job.log_buffer
```

### Key design points

- `_lock` guards `_jobs` dict. The timer callback acquires `_lock` before mutating state. [VERIFIED: threading.Lock is reentrant-safe for this pattern]
- `cancel_requested` is `threading.Event`, not `bool` — `.set()` is atomic across threads. [VERIFIED: threading.Event docs]
- `daemon=True` on timers: if the test process exits, daemon threads are killed automatically — no test hangs. [VERIFIED: Python threading docs]

### Pitfall

**Re-entrancy trap in timer callbacks.** If the `_finish` callback tries to acquire `_lock` while the main thread is inside a `with self._lock:` block that's inside `wait_for_state`, the timer fires and deadlocks (both holding the same non-reentrant lock). Solution: timers only SET state under the lock — they don't call `poll()`, `cancel()`, or any other Backend method while holding the lock. The test harness always calls Backend methods from the main thread only.

### Planner action

Include a test scenario that creates a `MockSLURMBackend` with `state_file`, runs a job to `COMPLETED`, then creates a new instance with the same `state_file` and asserts `list_running()` is empty (job already completed — not re-added as running). This validates restart-recovery semantics.

---

## 7. Backend Recovery on Daemon Restart

### Finding

LocalBackend's restart-safety comes from `running/<id>.json` files already written at submit time by `_orchestrator_daemon._launch` (orchestrator.py line 678-681). On daemon restart, `list_running()` should scan `running/*.json` to rebuild the live set. [VERIFIED: orchestrator.py lines 455-478 — `_recover_orphans` already does this scan]

The current `_recover_orphans` marks orphans as CRASHED. For `LocalBackend.list_running()`, the semantics differ: it should return handles for jobs that have specs in `running/` — letting the caller decide whether to poll, reap, or abandon. The Backend ABC has `list_running()` return handles; what to do with those handles is the orchestrator's scheduling logic, not the Backend's.

### Restart test invariant

```python
# Testable restart invariant
def test_list_running_restart_safe(tmp_path):
    """list_running() on a fresh backend instance returns jobs in running/."""
    backend1 = LocalBackend(project_root=tmp_path, automil_dir=tmp_path / "automil")
    handle = backend1.submit(make_spec("node_test", command=["sleep", "60"]))
    # Confirm running/node_test.json exists
    assert (tmp_path / "automil/orchestrator/running/node_test.json").exists()
    # Create fresh instance — simulates daemon restart
    backend2 = LocalBackend(project_root=tmp_path, automil_dir=tmp_path / "automil")
    running = backend2.list_running()
    assert any(h.node_id == "node_test" for h in running)
```

### MockSLURM restart

MockSLURM persists `_jobs` to `state_file` as JSON via `_persist_state()`. On construction with `state_file`, it reads the file and restores `_jobs` — but jobs in terminal state are loaded as-is (not re-added to running set). Jobs in `PENDING|RUNNING` state at restart time: MockSLURM cannot resume their timers (the timer thread is gone). The correct behaviour: on restart with a `PENDING|RUNNING` job in state_file, MockSLURM marks it `CRASHED` (simulating "scheduler lost the job"). This matches real SLURM's behaviour when `sacct` shows `FAILED` for a job that had `RUNNING` status before a head-node restart.

### Pitfall

**JSON serialization of `threading.Event`** — don't try to serialize the Event. Only serialize state (as string), log_buffer (as list), and opaque_id. The `cancel_requested` flag is runtime-only state.

### Planner action

`_MockJob._to_json()` and `_MockJob._from_json()` methods that exclude `cancel_requested` and `timer`. On load, `cancel_requested` is always a fresh `threading.Event()`.

---

## 8. CLI cancel/resubmit UX Patterns

### Finding

Production job scheduling CLIs (SLURM `scancel`, LSF `bkill`, PBS `qdel`) follow a consistent error model:

| Error case | Standard response |
|-----------|-------------------|
| Node ID doesn't exist | Non-zero exit, diagnostic "no such job" |
| Node in terminal state | Non-zero exit, "job already completed" |
| Cancel timeout | Non-zero exit, "cancel sent but not confirmed" + current state |
| Corrupted state | Non-zero exit, prompt operator to reconcile |

[ASSUMED — cross-referencing with production scheduler behavior]

### cancel workflow (per D-66)

```python
# cli/cancel.py skeleton matching Phase 1 PATTERNS.md §1 and §7

@main.command()
@click.argument("node_id")
@click.option("--timeout", default=30, help="Seconds to wait for cancelled state")
def cancel(node_id: str, timeout: int):
    """Terminate a running experiment via the backend."""
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph
    from automil.backends import BACKENDS

    graph = ExperimentGraph(path=str(adir / "graph.json"))
    node = graph.get_node(node_id)

    # Hard fail: unknown node
    if node is None:
        raise click.ClickException(
            f"Refusing to cancel: {node_id} not found in graph.json. "
            f"Check node ID or run 'automil status'."
        )

    # Hard fail: wrong state
    if node.get("status") != "running":
        state = node.get("status", "unknown")
        raise click.ClickException(
            f"Refusing to cancel: {node_id} is in state '{state}', not 'running'. "
            f"Only running experiments can be cancelled."
        )

    # Resolve backend
    backend_name = node.get("metadata", {}).get("backend", "local")
    BackendClass = BACKENDS.get(backend_name)
    if BackendClass is None:
        raise click.ClickException(
            f"Unknown backend: '{backend_name}'. Available: {list(BACKENDS.keys())}"
        )
    backend = BackendClass(project_root=_find_git_root(), automil_dir=adir)

    # Reconstruct handle from metadata
    from automil.backends.base import JobHandle
    meta = node.get("metadata", {})
    handle = JobHandle(
        node_id=node_id,
        backend=backend_name,
        opaque_id=meta["opaque_id"],
        submitted_at=meta["submitted_at"],
    )

    # Fire-and-forget cancel
    backend.cancel(handle)

    # Wait for state transition (D-66 step 6)
    from automil.backends.base import JobState
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = backend.poll(handle)
        if state == JobState.CANCELLED:
            break
        time.sleep(1.0)
    else:
        raise click.ClickException(
            f"cancel sent to {node_id} but state did not transition to CANCELLED "
            f"within {timeout}s (last state: {backend.poll(handle)}). "
            f"The process may still be running. Investigate with 'automil status'."
        )

    # Atomic graph update (Pattern §3 from 01-PATTERNS.md)
    import time as _time
    node["status"] = "cancelled"
    node.setdefault("metadata", {})["cancelled_at"] = datetime.now().isoformat()
    node["metadata"]["cancel_reason"] = "cli"
    graph.save()

    # Move running spec to archive (D-66 step 8)
    running_spec = adir / "orchestrator" / "running" / f"{node_id}.json"
    if running_spec.exists():
        archive_dir = adir / "orchestrator" / "archive" / node_id
        archive_dir.mkdir(parents=True, exist_ok=True)
        running_spec.rename(archive_dir / f"{node_id}_running_spec.json")

    click.echo(f"Cancelled {node_id}.")
```

### resubmit workflow (per D-67)

Key difference from the existing submit: resubmit reads the overlay from `archive/<node_id>/` — all the snapshotted files are already there. It creates a new graph node, writes a new queue spec, and prints the new node_id. [VERIFIED: orchestrator.py's archive layout — spec.json and overlay files co-located]

### Pitfall: metadata fields must be written at submit time

`cancel.py` reconstructs `JobHandle` from `node.metadata.opaque_id` and `node.metadata.submitted_at`. These must be written to the graph node at submit time (when the handle is created). Currently, `cli/submit.py` does NOT write `opaque_id` or `backend` to the graph node (it only writes `config_hash`, `parent_id`, `techniques`). **This is a Phase 2 gap that the planner must address**: the `submit.py` command must be extended to persist `backend`, `opaque_id`, and `submitted_at` into the node's `metadata` dict when queuing. Without this, `cancel.py` cannot reconstruct the handle.

The right fix: when `backend.submit(spec)` is called, the returned `JobHandle.opaque_id` must be written to `graph.json`. For the legacy submit path (which currently writes a queue file), the `opaque_id` is not known until the daemon launches the job. For Phase 2's contract: `cancel` works only for jobs submitted via the new `Backend.submit()` path (new CLI commands that call `backend.submit()`). Legacy queue-path jobs (submitted via current `cli/submit.py`) do not have `opaque_id` in metadata and should fail gracefully: "Node was submitted via legacy path; opaque_id not available. Use direct process management."

### Planner action

The planner must include a task that extends `cli/submit.py` (or a new `cli/cancel.py` path) to write `backend`, `opaque_id`, and `submitted_at` to the graph node's `metadata` dict after the backend returns a handle. Alternatively, the cancel/resubmit integration test uses a graph fixture pre-populated with the correct metadata — matching D-70's "synthetic graph fixture" approach for testing.

---

## Architecture Patterns

### Recommended Project Structure

```
src/automil/backends/
    __init__.py                   # BACKENDS registry dict, @Backend.register decorator
    base.py                       # Backend ABC, JobSpec, JobHandle, JobState
    local.py                      # LocalBackend(Backend) — thin shim over _orchestrator_daemon
    mock_slurm.py                 # MockSLURMBackend(Backend) — eventual-consistency fixture
    _orchestrator_daemon.py       # current orchestrator.py renamed (git mv)

src/automil/orchestrator.py       # 5-line re-export shim for backward compat
src/automil/cli/cancel.py         # automil cancel <node_id>
src/automil/cli/resubmit.py       # automil resubmit <node_id>
scripts/check_backend_isolation.py  # BCK-04 AST lint

tests/backends/
    __init__.py                   # (empty)
    conftest.py                   # backend fixture (params=["local", "mock_slurm"])
                                  # wait_for_state() helper
    test_contract.py              # ≥10 parameterised scenarios
tests/test_backend_isolation_lint.py  # pytest wrapper for check_backend_isolation.py
tests/test_cli_cancel_resubmit.py     # end-to-end CLI test against MockSLURM + synthetic graph
```

### Pattern: Backend Registry (D-68)

```python
# src/automil/backends/__init__.py
from automil.backends.base import Backend

BACKENDS: dict[str, type[Backend]] = {}

def register(name: str):
    """Class decorator: @Backend.register("local") registers LocalBackend."""
    def decorator(cls: type[Backend]):
        if not issubclass(cls, Backend):
            raise TypeError(f"{cls.__name__} must subclass Backend")
        BACKENDS[name] = cls
        return cls
    return decorator
```

This mirrors Phase 1's registry pattern exactly — module-level dict + decorator. [VERIFIED: Phase 1 01-PATTERNS.md §1 — module-level registration pattern]

### Pattern: LocalBackend shim (D-60/D-61)

```python
# src/automil/backends/local.py
from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends import register

@register("local")
class LocalBackend(Backend):
    """Thin wrapper over ExperimentOrchestrator for local GPU execution."""

    def __init__(self, project_root, automil_dir):
        from automil.backends._orchestrator_daemon import ExperimentOrchestrator
        self._daemon = ExperimentOrchestrator(
            project_root=project_root,
            automil_dir=automil_dir,
        )
        # _daemon constructor calls _load_state(recover=False) — safe for CLI commands

    def submit(self, spec: JobSpec) -> JobHandle:
        # Map JobSpec fields to the queue spec dict that _launch expects,
        # then call _launch directly (bypassing the file-based queue for direct invocation).
        # OR: write to queue/ and let daemon pick it up (existing async path).
        # D-60: thin call into _orchestrator_daemon's existing methods.
        ...

    def poll(self, handle: JobHandle) -> JobState:
        # Read running/<handle.opaque_id>.json for RUNNING;
        # archive/<handle.node_id>/result.json for terminal.
        ...

    def cancel(self, handle: JobHandle, signal=None) -> None:
        # Call _daemon._handle_timeout equivalent, or send signal to process.
        # This is inside the allowlisted local.py — os.kill IS permitted here.
        ...

    def list_running(self) -> list[JobHandle]:
        # Scan running/*.json — same as _recover_orphans but read-only.
        ...

    def log_iter(self, handle: JobHandle):
        # Tail archive/<node_id>/run.log (created by _launch).
        ...
```

### Anti-Patterns to Avoid

- **`isinstance(backend, LocalBackend)` branches in orchestrator/graph code** — the entire point of the ABC. If scheduling logic branches on backend type, the abstraction has failed (Pitfall 2 warning sign).
- **Calling `_recover_orphans` from CLI commands** — LocalBackend's `__init__` must pass `recover=False` (enforced by existing orchestrator constructor; do not override).
- **`from automil.backends._orchestrator_daemon import *` anywhere except `src/automil/orchestrator.py`** — the star-import is only for the backward-compat shim. LocalBackend should import named symbols explicitly.
- **`mock_slurm` auto-imported in BACKENDS** — D-69: MockSLURM is NOT auto-registered. The contract test explicitly imports it; production config cannot accidentally select `backend.name = "mock_slurm"` without a deliberate `import`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe job state | bare `bool` cancel flag | `threading.Event` | `.set()` is atomic; bare bool is a race condition |
| AST traversal | manual string matching of source | `ast.parse()` + `ast.NodeVisitor` | Handles strings in source, comments, and multi-line expressions correctly |
| JSON-safe enums | custom `__json__` hooks | `class JobState(str, Enum)` | str Enum is natively JSON-serialisable without encoder |
| Atomic graph writes | `graph.write_text(json.dumps(...))` | `ExperimentGraph.save()` | tempfile+rename is already implemented; bypass causes corruption under crash |
| Frozen dataclass serialisation | custom `to_dict()` | `dataclasses.asdict(handle)` | stdlib, handles nested types correctly |

---

## Common Pitfalls

### Pitfall 1: ABC Designed Against One Impl (Pitfall 2 from PITFALLS.md)
**What goes wrong:** LocalBackend is built first. Its `submit()` signature accepts a raw dict (matching the existing queue spec format). MockSLURMBackend must then also accept a raw dict, but its backend semantics don't fit. The ABC freezes dict-based specs.
**Why it happens:** Starting with LocalBackend instead of defining the ABC against two implementations simultaneously.
**How to avoid:** Write `base.py` (ABC + dataclasses) first. Then write MockSLURMBackend against the ABC. THEN write LocalBackend as an adapter from ABC types to `_orchestrator_daemon` types. The order enforces the anti-acceptance criterion.
**Warning signs:** `LocalBackend.submit()` takes `spec: dict` instead of `spec: JobSpec`.

### Pitfall 2: `_recover_orphans` Race on CLI Commands
**What goes wrong:** `cancel.py` or `resubmit.py` constructs `LocalBackend`. If the backend constructor triggers `_recover_orphans`, running jobs get marked as crashed.
**Why it happens:** Forgetting to pass `recover=False`.
**How to avoid:** `LocalBackend.__init__` always constructs `ExperimentOrchestrator(..., recover=False)` (or sets `_daemon._load_state(recover=False)` explicitly). Test: run `automil cancel <running_node_id>` while daemon is running; verify running job is not marked crashed.
**Warning signs:** Running jobs disappear from `running/` after a `cancel` invocation.

### Pitfall 3: MockSLURM Timer Deadlock
**What goes wrong:** Timer callback acquires `_lock` while main-thread test is inside `wait_for_state` which also acquires `_lock` via `poll()`. Deadlock.
**Why it happens:** `poll()` acquires lock; timer callback also acquires lock; both block.
**How to avoid:** Timer callback sets state under lock, then exits. It does NOT call any other Backend method. `poll()` acquires lock for a read only — no nested lock acquisition.
**Warning signs:** Test hangs past 5s in CI.

### Pitfall 4: Lint Script Misses Star-Import Aliases
**What goes wrong:** `from subprocess import Popen` is caught. `from subprocess import Popen as P` is caught via `_alias_map`. But `import subprocess; Popen = subprocess.Popen; Popen(...)` introduces `Popen` as a local Name — caught by `visit_Name`. However, `from subprocess import *` would import `Popen` into the namespace silently. The `visit_ImportFrom` handler tracks `from X import Y` but not `from X import *`.
**How to avoid:** Add a check: if `node.module in ("os", "subprocess") and any(alias.name == "*" for alias in node.names)`, flag it as a violation. Star-import of `os` or `subprocess` outside the allowlist is always forbidden.
**Warning signs:** Lint passes but `Popen` is accessible via star-import.

### Pitfall 5: opaque_id Not Persisted at Submit Time
**What goes wrong:** `cancel.py` tries to reconstruct `JobHandle` from `node.metadata.opaque_id` but the field is `None` (never written at submit time). Cancel fails with `KeyError`.
**Why it happens:** The current `cli/submit.py` writes `graph_metadata` but not `opaque_id` or `backend`.
**How to avoid:** Phase 2 must either (a) extend `cli/submit.py` to call `backend.submit()` and persist the returned handle, or (b) limit `automil cancel` to nodes submitted via the new backend path. The integration test must exercise this path end-to-end.
**Warning signs:** `automil cancel <node_id>` raises `KeyError: 'opaque_id'`.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed via uv workspace) |
| Config file | `pyproject.toml` (workspace root) |
| Quick run command | `uv run pytest tests/backends/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |
| Phase gate command | `uv run pytest tests/ -q && python scripts/check_backend_isolation.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| BCK-01 | JobHandle is frozen, hashable, JSON-serialisable | unit | `uv run pytest tests/backends/test_contract.py::test_handle_frozen -x` | Wave 0 |
| BCK-01 | JobState round-trips through JSON | unit | `uv run pytest tests/backends/test_contract.py::test_state_json_roundtrip -x` | Wave 0 |
| BCK-01 | submit→poll terminal (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_submit_poll_completed -x` | Wave 0 |
| BCK-01 | mid-run cancel → CANCELLED state (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_cancel_mid_run -x` | Wave 0 |
| BCK-01 | list_running pre/post submit (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_list_running_pre_post_submit -x` | Wave 0 |
| BCK-01 | list_running empty after terminal (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_list_running_post_terminal -x` | Wave 0 |
| BCK-01 | log_iter closes on terminal state (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_log_iter_terminal_close -x` | Wave 0 |
| BCK-01 | eventual-consistency lag (MockSLURM only) | contract | `uv run pytest tests/backends/test_contract.py::test_eventual_consistency_lag -x` | Wave 0 |
| BCK-01 | fire-and-forget cancel timing (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_cancel_returns_immediately -x` | Wave 0 |
| BCK-01 | opaque_id uniqueness across submits (both backends) | contract | `uv run pytest tests/backends/test_contract.py::test_opaque_id_unique -x` | Wave 0 |
| BCK-02 | existing 387 tests still green | regression | `uv run pytest tests/ -x -q` | Existing |
| BCK-02 | import path backward compat | unit | `uv run pytest tests/backends/test_contract.py::test_import_path_compat -x` | Wave 0 |
| BCK-03 | restart recovery — MockSLURM | contract | `uv run pytest tests/backends/test_contract.py::test_restart_recovery -x` | Wave 0 |
| BCK-04 | AST lint exits 0 on current src/automil/ | lint | `python scripts/check_backend_isolation.py` | scripts/ |
| BCK-04 | pytest wrapper for lint | unit | `uv run pytest tests/test_backend_isolation_lint.py -x` | Wave 0 |
| CLI-03 | cancel happy path (MockSLURM) | integration | `uv run pytest tests/test_cli_cancel_resubmit.py::test_cancel_happy_path -x` | Wave 4 |
| CLI-03 | cancel non-existent node → non-zero | integration | `uv run pytest tests/test_cli_cancel_resubmit.py::test_cancel_unknown_node -x` | Wave 4 |
| CLI-03 | cancel terminal node → non-zero | integration | `uv run pytest tests/test_cli_cancel_resubmit.py::test_cancel_terminal_node -x` | Wave 4 |
| CLI-03 | cancel timeout → non-zero + diagnostic | integration | `uv run pytest tests/test_cli_cancel_resubmit.py::test_cancel_timeout -x` | Wave 4 |
| CLI-04 | resubmit happy path → new node_id printed | integration | `uv run pytest tests/test_cli_cancel_resubmit.py::test_resubmit_happy_path -x` | Wave 4 |

### Parameterised Contract Test Scenarios (≥10 per D-70)

| # | Scenario | Asserts | Defends Against |
|---|---------|---------|-----------------|
| S-01 | submit → poll → COMPLETED | final state is COMPLETED; no intermediate assertion | Synchronous assumption in poll() |
| S-02 | submit → poll → CRASHED (--crash command) | final state is CRASHED | Only testing happy path |
| S-03 | submit → cancel mid-run → CANCELLED | cancel() returns immediately; later poll() = CANCELLED | cancel() blocking |
| S-04 | list_running pre-submit = [] | baseline empty list | Stale state from previous test |
| S-05 | submit 2 jobs → list_running has 2 handles | count matches | list_running lying about live set |
| S-06 | job completes → list_running doesn't include it | eventually-consistent removal | COMPLETED job still in list |
| S-07 | log_iter on COMPLETED job yields ≥1 line | log not empty | log_iter returning empty on terminal |
| S-08 | log_iter closes (exhausts iterator) | no StopIteration hang | Infinite iterator on terminal state |
| S-09 | cancel() returns in <100ms | timing constraint | cancel() blocking on backend round-trip |
| S-10 | poll() returns PENDING then RUNNING (MockSLURM only) | state sequence observed | Skipping PENDING state |
| S-11 | opaque_id differs per submit | uniqueness | opaque_id collision |
| S-12 | fresh backend instance → list_running matches persisted state | restart recovery | In-memory-only state lost on restart |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/backends/ tests/test_backend_isolation_lint.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** `uv run pytest tests/ -q && python scripts/check_backend_isolation.py && grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/ | wc -l | xargs test 0 -eq`

### Wave 0 Gaps (files that must be created before other plans can land)

- [ ] `src/automil/backends/__init__.py` — BACKENDS dict + register decorator
- [ ] `src/automil/backends/base.py` — Backend ABC + JobSpec/JobHandle/JobState
- [ ] `tests/backends/__init__.py` — empty, makes pytest discover the subdirectory
- [ ] `tests/backends/conftest.py` — backend fixture + wait_for_state helper
- [ ] `scripts/check_backend_isolation.py` — BCK-04 AST lint script (pre-conditions for test_backend_isolation_lint.py)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Popen` exposed in orchestrator loop | Backend ABC + opaque handle | Phase 2 | SLURM/Ray backends become feasible |
| Single `orchestrator.py` monolith | `_orchestrator_daemon.py` + thin shim | Phase 2 | Phase 6 adds backends without touching daemon |
| No structured cancel | `automil cancel <id>` via Backend.cancel | Phase 2 | Agent can self-correct misconfigured batches |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | All tests | via uv | (workspace dep) | — |
| threading | MockSLURM, lint | stdlib | always | — |
| ast | lint script | stdlib | always | — |
| submitit | Phase 6 only | not installed | — | not needed Phase 2 |
| ray | Phase 6 only | not installed | — | not needed Phase 2 |

No missing dependencies block Phase 2 execution.

---

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` per config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | BCK-04 lint enforces process-control isolation |
| V5 Input Validation | yes | JobSpec frozen dataclass rejects post-construction mutation; node_id validated before graph write |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `cancel` sends SIGTERM to wrong PID (PID reuse) | Spoofing | PID-file starttime cross-check (already in `_orchestrator_daemon.py`) |
| `resubmit` overwrites completed archive | Tampering | D-67: new node_id; old archive untouched |
| MockSLURM leaking into production config selection | Elevation of privilege | D-69: mock_slurm NOT auto-imported; must be explicitly imported |
| cancel.py triggering `_recover_orphans` race | Tampering | LocalBackend always passes `recover=False` |
| opaque_id guessing (CLI cancel against wrong process) | Tampering | `JobHandle.node_id` cross-checked against graph before cancel; wrong opaque_id fails poll() not signal |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | submitit JobState has 5 values | §2 | Low — Phase 6 will verify; Phase 2 only needs mock |
| A2 | Dask/Ray cancel is fire-and-forget (not confirmed this session) | §1 | Low — Phase 2 only needs mock; ABC contract is fire-and-forget regardless |
| A3 | ruff S605 does not flag `Popen(...)` | §4 | Medium — if wrong, ruff could substitute for custom AST; but custom is still preferred for allowlist logic |
| A4 | freezegun doesn't advance threading.Timer | §6 | Medium — if wrong, freezegun could be used; threading.Timer approach is simpler anyway |
| A5 | `from subprocess import *` star-import catches needed | §4 | Low — codebase grep confirms no star-import of subprocess anywhere in src/automil/ |

---

## Open Questions (RESOLVED 2026-05-02 — see CONTEXT.md D-76 + D-77)

1. **submit.py backward compat for cancel** — RESOLVED via D-76.
   - Resolution: `cli/submit.py` is extended in Plan 02-03 (Wave 1) to write `metadata.backend = "<config>"` (default `"local"`) into `queue/<id>.json` at submit time. `metadata.opaque_id` is NOT written at submit time (PID unknown until launch); it is written by the daemon into `running/<id>.json` when `_launch` returns. `cancel.py` reads `running/<id>.json` to reconstruct the `JobHandle`. Legacy nodes without `metadata.backend` default to `"local"`.

2. **LocalBackend.submit() uses queue-file path or direct `_launch` path?** — RESOLVED via D-77.
   - Resolution: `LocalBackend.submit(spec)` writes to `queue/<id>.json` (preserves existing daemon-pickup model). Returns `JobHandle(opaque_id="pending")`; daemon updates to real PID on launch. `LocalBackend.poll(handle)` reads `running/<id>.json` (running) or `archive/<id>/result.json` (terminal). LocalBackend is a **thin protocol adapter** over the daemon's on-disk state machine, NOT a re-implementation. No daemon mocking needed for tests; LocalBackend.submit works against a real (synthetic-fixture-scoped) daemon directory.

---

## Sources

### Primary (HIGH confidence)

- `src/automil/orchestrator.py` (1115 lines) — verified all `os.kill`, `os.killpg`, `.pid`, `Popen` usages
- `src/automil/runner.py` — verified worktree API
- `src/automil/cli/submit.py` — verified graph metadata shape
- `.planning/phases/01-*/01-PATTERNS.md` — verified CLI patterns (§1, §3, §7)
- `.planning/research/PITFALLS.md §Pitfall 2` — leaky backend ABC design
- `.planning/codebase/CONCERNS.md` — PID-file stale detection, process-group issue
- Python stdlib documentation (threading, abc, ast, json) [VERIFIED via training knowledge, stable APIs]

### Secondary (MEDIUM confidence)

- Submitit, Ray, Dask API shapes — [ASSUMED — training knowledge, not verified this session]
- Ruff S605 coverage — [ASSUMED — not installed in environment]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — dataclasses, abc, threading are stdlib; patterns verified against codebase
- Architecture: HIGH — locked decisions verified against existing code; no contradictions found
- Pitfalls: HIGH — Pitfalls 1-5 verified against actual code paths in orchestrator.py

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (stable Python stdlib patterns; submitit/Ray surface is LOW confidence but not needed until Phase 6)
