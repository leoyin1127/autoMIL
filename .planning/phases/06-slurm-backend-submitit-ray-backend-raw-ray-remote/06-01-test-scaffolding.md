---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - tests/backends/conftest.py
  - tests/backends/test_slurm_directives.py
  - tests/backends/test_running_namespace.py
  - tests/backends/test_log_unification.py
  - tests/backends/test_node_0176_smoke.py
  - tests/backends/test_contract_real_slurm.py
  - tests/backends/test_contract_real_ray.py
  - pyproject.toml
autonomous: true
requirements: [BCK-05, BCK-06]

must_haves:
  truths:
    - "All 8 Wave-0 stubs collect under pytest (RED — they fail because implementations land in Wave 1+)."
    - "tests/backends/conftest.py params list extends to ['local', 'mock_slurm', 'slurm', 'ray']; SLURM/Ray param branches use pytest.importorskip so missing extras skip cleanly."
    - "pyproject.toml registers requires_slurm + requires_ray pytest markers."
    - "Existing 779-test Phase 5 baseline + the not-yet-skipped scaffolding stubs equal the new collected total (no test_*.py file accidentally green-on-empty)."
  artifacts:
    - path: tests/backends/conftest.py
      provides: "Backend fixture parametrised over ['local', 'mock_slurm', 'slurm', 'ray'] with importorskip + ray.shutdown teardown."
    - path: tests/backends/test_slurm_directives.py
      provides: "Stubs for test_check_rejects_todo, test_check_accepts_complete, test_walltime_seconds_to_timeout_min."
      contains: "from automil.backends.errors import SlurmDirectivesIncompleteError"
    - path: tests/backends/test_running_namespace.py
      provides: "Stubs for test_running_dir_per_backend, test_daemon_refuses_flat_running, test_namespace_isolation."
    - path: tests/backends/test_log_unification.py
      provides: "Stubs for test_archive_run_log_local, test_archive_run_log_slurm, test_archive_run_log_ray, test_log_iter_close_60s_timeout."
    - path: tests/backends/test_node_0176_smoke.py
      provides: "Acceptance smoke parametrised over ['local', 'slurm-debug', 'ray-local'] asserting composite within ±0.005."
    - path: tests/backends/test_contract_real_slurm.py
      provides: "@pytest.mark.requires_slurm contract test against real cluster (skipped in CI)."
    - path: tests/backends/test_contract_real_ray.py
      provides: "@pytest.mark.requires_ray contract test against real cluster (skipped in CI)."
    - path: pyproject.toml
      provides: "Registers requires_slurm + requires_ray pytest markers."
      contains: "requires_slurm: requires SLURM cluster"
  key_links:
    - from: tests/backends/conftest.py
      to: automil.backends.slurm.SLURMBackend
      via: import inside fixture branch (post pytest.importorskip)
      pattern: "from automil.backends.slurm import SLURMBackend"
    - from: tests/backends/conftest.py
      to: automil.backends.ray.RayBackend
      via: import inside fixture branch (post pytest.importorskip)
      pattern: "from automil.backends.ray import RayBackend"
    - from: pyproject.toml
      to: pytest marker registry
      via: '[tool.pytest.ini_options] markers'
      pattern: "requires_slurm:|requires_ray:"
---

<objective>
Wave 0 (Nyquist) — land all 8 test stubs and pytest marker registrations BEFORE any implementation runs. Per VALIDATION.md `## Wave 0 Requirements` and the Wave-cadence-target in the planning_context, this plan installs the failing-test scaffolding that subsequent waves flip green. No implementation code lands here; the contract tests will collect as RED until Wave 1+ ships the real backends.

Purpose: every D-179 acceptance clause is paired with an automated test. By writing the tests first we (a) prove every Phase 6 success criterion is observable, (b) hand executors a precise expected signature for the new types they create, and (c) prevent silent scope drift. Per Leo's CLAUDE.md "Verification Before Done", a feature is not done until a green test asserts it.

Output: 6 new test files + extended conftest.py + pyproject.toml marker block. After this plan: `uv run pytest tests/backends/ --collect-only -q` reports the new test IDs; `uv run pytest tests/backends/ -x` shows the new stubs failing with informative messages (NOT erroring on collection).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-VALIDATION.md
@CLAUDE.md

# Existing fixtures, contracts, and patterns the stubs reuse:
@tests/backends/conftest.py
@tests/backends/test_contract.py
@src/automil/backends/base.py
@pyproject.toml

<interfaces>
<!-- Public surface this plan asserts (will be created in later waves). Stubs reference these names; ImportError is acceptable until the implementations land. -->

From src/automil/backends/errors.py (created in Wave 1, plan 06-02):
```python
class BackendNotInstalledError(BackendError):
    extra_name: str
class SlurmDirectivesIncompleteError(BackendError):
    missing_keys: list[str]
class RayClusterUnreachableError(BackendError):
    address: str
```

From src/automil/cli/check.py (extended in Wave 1, plan 06-03):
```python
def _validate_slurm_directives(config: dict) -> None:
    """Raises SlurmDirectivesIncompleteError if any required directive missing or contains 'TODO_FILL_IN'."""
```

From src/automil/backends/slurm.py (Wave 2, plan 06-04):
```python
class SLURMBackend(Backend):
    def __init__(self, automil_dir: Path, config: dict) -> None: ...
```

From src/automil/backends/ray.py (Wave 2, plan 06-05):
```python
class RayBackend(Backend):
    _we_started_ray: bool
    def __init__(self, automil_dir: Path, config: dict) -> None: ...
    def close(self) -> None: ...
```

API correction notes (apply in stub assertions):
- D-155 corrected: `update_parameters(timeout_min=max(1, walltime_seconds // 60), slurm_additional_parameters={"signal": "B:TERM@30"}, ...)` — NOT `time=` and NOT `signal=` kwarg.
- D-174 corrected: `ray.init(ignore_reinit_error=True)` — NOT `ray.init(local_mode=True)` (deprecated in Ray 2.55+).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Register pytest markers + extend conftest backend fixture</name>
  <files>pyproject.toml, tests/backends/conftest.py</files>
  <read_first>
    - tests/backends/conftest.py (lines 100-152 — existing `params=["local", "mock_slurm"]` fixture, `_isolated_backends` autouse, registry-isolation pattern PATTERNS.md §11)
    - pyproject.toml (lines 37-38 existing `[tool.pytest.ini_options]`)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"tests/backends/conftest.py" lines 746-810 — exact extension shape)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md (Pitfall 5 — `local_mode=True` deprecated; use plain `ray.init(ignore_reinit_error=True)` + teardown `ray.shutdown` if `_we_started_ray`)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-VALIDATION.md (Wave 0 Requirements bullets 1, 8, 9)
  </read_first>
  <action>
**Step A — pyproject.toml**: Replace the existing `[tool.pytest.ini_options]` block (lines 37-38) with:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "requires_slurm: requires SLURM cluster (skip in CI; nightly only)",
    "requires_ray: requires real Ray cluster (skip in CI; nightly only)",
]
```
Do NOT add submitit/ray to dependencies; extras land in plan 06-02.

**Step B — tests/backends/conftest.py**: Extend the existing `backend` fixture (line 100). Replace the `params=["local", "mock_slurm"]` decorator with `params=["local", "mock_slurm", "slurm", "ray"]` and rewrite the dispatch as an explicit if/elif/elif/else chain. The post-edit fixture body MUST be exactly the four-branch structure shown below (do NOT leave the old `else: MockSLURM` branch in place — that would cause `request.param == "ray"` to fall through to MockSLURM):

```python
@pytest.fixture(params=["local", "mock_slurm", "slurm", "ray"])
def backend(request, tmp_path, _isolated_backends):
    if request.param == "local":
        # ... existing LocalBackend body unchanged ...
        yield LocalBackend(...)
    elif request.param == "mock_slurm":
        # ... existing MockSLURMBackend body unchanged (formerly the `else` branch) ...
        yield MockSLURMBackend(...)
    elif request.param == "slurm":
        pytest.importorskip("submitit")
        from automil.backends.slurm import SLURMBackend  # noqa: PLC0415

        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
        (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
        config = {
            "backend": {
                "name": "slurm",
                "slurm": {
                    "debug_in_process": True,  # uses submitit cluster="debug"
                    "walltime_seconds": 300,
                    "directives": {
                        "partition": "debug",
                        "account": "test",
                        "cpus_per_task": 1,
                        "mem_gb": 4,
                    },
                },
            },
        }
        yield SLURMBackend(automil_dir=automil_dir, config=config)
    else:  # request.param == "ray"
        pytest.importorskip("ray")
        import ray  # noqa: PLC0415
        from automil.backends.ray import RayBackend  # noqa: PLC0415

        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True, log_to_driver=False)  # NOT local_mode=True (deprecated; RESEARCH.md Pitfall 5)
        automil_dir = tmp_path / "automil"
        (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
        (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
        backend_instance = RayBackend(
            automil_dir=automil_dir,
            config={"backend": {"name": "ray", "ray": {"allow_local_fallback": True}}},
        )
        yield backend_instance
        if backend_instance._we_started_ray and ray.is_initialized():
            ray.shutdown()
```

**Critical:** the existing `else: MockSLURMBackend` branch becomes `elif request.param == "mock_slurm":` — moved up in the chain. The new `else:` branch matches ONLY `"ray"`. Verify by greppping after the edit: `grep -c "elif request.param ==" tests/backends/conftest.py` must return `2` (one for `mock_slurm`, one for `slurm`); `grep -c "else:  # request.param == \"ray\"" tests/backends/conftest.py` must return `1`.

The `_isolated_backends` autouse fixture (lines 139-152) is unchanged.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/ --collect-only -q 2>&1 | tail -20 && uv run pytest --markers 2>&1 | grep -E "requires_slurm|requires_ray"</automated>
  </verify>
  <done>
    `pyproject.toml` shows `markers = [...]` with both `requires_slurm` and `requires_ray` lines (grep `^\s*"requires_slurm:` and `^\s*"requires_ray:` each return 1 line). conftest.py params list now contains all 4 backend names (grep `params=\["local", "mock_slurm", "slurm", "ray"\]` returns 1 line). `uv run pytest --markers` lists both markers. `uv run pytest tests/backends/ --collect-only` succeeds (no collection errors); existing `local`/`mock_slurm` parametrised tests still appear; new `slurm`/`ray` parametrisations appear with `SKIPPED` markers (because submitit/ray extras are not installed yet — `pytest.importorskip` triggers).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Create 4 backend-test stub files (slurm_directives, running_namespace, log_unification, node_0176_smoke)</name>
  <files>tests/backends/test_slurm_directives.py, tests/backends/test_running_namespace.py, tests/backends/test_log_unification.py, tests/backends/test_node_0176_smoke.py</files>
  <read_first>
    - tests/backends/test_contract.py (lines 1-100 — existing `make_spec`/`wait_for_state` import + scenario style)
    - tests/test_synthetic_consumer_roundtrip.py (lines 32-65 — `_setup_smoke_project` fixture pattern)
    - tests/test_backend_isolation_lint.py (lines 26-50 — `pytest.raises` + structured-error assertion style)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"tests/backends/test_slurm_directives.py" lines 836-866; §"test_running_namespace.py" lines 870-894; §"test_log_unification.py" lines 898-919; §"test_node_0176_smoke.py" lines 923-957)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-VALIDATION.md (lines 65-96 — Wave 0 Requirements + per-test ID list)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-172 — required SLURM directive keys; D-168 — flat-running guardrail; D-170 — log_iter 60s timeout; D-176 — node_0176 ±0.005)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md (OQ-1 — `walltime_seconds → timeout_min = max(1, walltime_seconds // 60)`)
  </read_first>
  <action>
Create each file as a stub: each test function body MUST `pytest.importorskip("submitit")` or `pytest.importorskip("ray")` where the test depends on the extras, then call into the not-yet-written API and assert the expected behavior. The test functions MUST collect (no SyntaxError, no ImportError at module level), and SHOULD fail when run because the implementations don't exist yet — that is the Nyquist RED state.

**Module-level pattern for all 4 files**: place all `from automil.X import Y` imports inside test functions (or behind `pytest.importorskip`) so collection does not error.

**File 1 — `tests/backends/test_slurm_directives.py`** (3 tests, all per D-172, all using `pytest.raises(SlurmDirectivesIncompleteError)`):
```python
"""Wave 0 stubs for D-172 SLURM-directive validation (BCK-05).

These tests assert that automil check refuses to run when backend.slurm.directives
is incomplete or contains the literal 'TODO_FILL_IN' sentinel. The validator
helper _validate_slurm_directives is created in plan 06-03.
"""
from __future__ import annotations

import pytest


def test_check_rejects_todo():
    """D-172: any TODO_FILL_IN sentinel in required directives raises SlurmDirectivesIncompleteError."""
    from automil.backends.errors import SlurmDirectivesIncompleteError
    from automil.cli.check import _validate_slurm_directives

    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "walltime_seconds": 21600,
                "directives": {
                    "partition": "TODO_FILL_IN",
                    "account": "mylab",
                    "cpus_per_task": 8,
                    "mem_gb": 48,
                },
            },
        },
    }
    with pytest.raises(SlurmDirectivesIncompleteError) as exc_info:
        _validate_slurm_directives(config)
    assert "partition" in exc_info.value.missing_keys


def test_check_accepts_complete():
    """D-172: validator returns None when all required keys present and no TODO sentinels."""
    from automil.cli.check import _validate_slurm_directives

    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "walltime_seconds": 21600,
                "directives": {
                    "partition": "compute",
                    "account": "mylab",
                    "cpus_per_task": 8,
                    "mem_gb": 48,
                },
            },
        },
    }
    # Should NOT raise
    _validate_slurm_directives(config)


def test_walltime_seconds_to_timeout_min():
    """RESEARCH.md OQ-1: walltime_seconds → timeout_min = max(1, walltime_seconds // 60)."""
    from automil.backends.slurm import _walltime_to_timeout_min

    assert _walltime_to_timeout_min(0) == 1          # min floor
    assert _walltime_to_timeout_min(30) == 1         # < 60s rounds up to 1
    assert _walltime_to_timeout_min(60) == 1
    assert _walltime_to_timeout_min(120) == 2
    assert _walltime_to_timeout_min(21600) == 360    # 6h
```

**File 2 — `tests/backends/test_running_namespace.py`** (3 tests per D-168, D-169):
```python
"""Wave 0 stubs for D-168/D-169 running/ namespace migration (BCK-05/06)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def _build_minimal_automil(tmp_path: Path) -> Path:
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running").mkdir(parents=True)
    (automil_dir / "orchestrator" / "queue").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    (automil_dir / "orchestrator" / "completed").mkdir(parents=True)
    (automil_dir / "config.yaml").write_text("backend:\n  name: local\n")
    (tmp_path / ".git").mkdir(exist_ok=True)
    return automil_dir


def test_running_dir_per_backend(tmp_path):
    """D-169: daemon resolves running_dir per backend via _backend_running_dir(name)."""
    automil_dir = _build_minimal_automil(tmp_path)
    from automil.backends._orchestrator_daemon import ExperimentOrchestrator
    daemon = ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)
    assert daemon._backend_running_dir("local") == automil_dir / "orchestrator" / "running" / "local"
    assert daemon._backend_running_dir("slurm") == automil_dir / "orchestrator" / "running" / "slurm"
    assert daemon._backend_running_dir("ray") == automil_dir / "orchestrator" / "running" / "ray"


def test_daemon_refuses_flat_running(tmp_path):
    """D-168: daemon.run() raises SystemExit if flat running/*.json exists with no namespaced subdirs."""
    automil_dir = _build_minimal_automil(tmp_path)
    flat_running = automil_dir / "orchestrator" / "running"
    (flat_running / "stale_node.json").write_text(json.dumps({"id": "stale_node"}))
    # Confirm precondition: no namespaced subdirs.
    assert not (flat_running / "local").exists()

    from automil.backends._orchestrator_daemon import ExperimentOrchestrator
    daemon = ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)
    with pytest.raises(SystemExit, match="BREAKING CHANGE"):
        daemon.run()


def test_namespace_isolation(tmp_path):
    """D-169: backend A's running entries don't appear in backend B's list_running()."""
    automil_dir = _build_minimal_automil(tmp_path)
    # Drop a fake JSON file under running/slurm/ — local backend must NOT see it.
    slurm_running = automil_dir / "orchestrator" / "running" / "slurm"
    slurm_running.mkdir(parents=True)
    (slurm_running / "fake_slurm_node.json").write_text(json.dumps({
        "id": "fake_slurm_node",
        "backend": "slurm",
        "opaque_id": "12345",
        "submitted_at": 0.0,
    }))

    from automil.backends.local import LocalBackend
    backend = LocalBackend(project_root=tmp_path, automil_dir=automil_dir)
    handles = backend.list_running()
    assert all(h.node_id != "fake_slurm_node" for h in handles), \
        "LocalBackend.list_running leaked a SLURM-namespaced node"
```

**File 3 — `tests/backends/test_log_unification.py`** (4 tests per D-170, D-171):
```python
"""Wave 0 stubs for D-170/D-171 cross-backend log unification (BCK-05/06)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from automil.backends.base import JobState
from tests.backends.conftest import make_spec, wait_for_state


def _drain_to_archive(backend, handle, archive_root: Path) -> Path:
    """Helper: simulate orchestrator's terminal-state log drain (D-170)."""
    from automil.backends._orchestrator_daemon import _atomic_write_lines
    log_path = archive_root / handle.node_id / "run.log"
    lines = list(backend.log_iter(handle))
    _atomic_write_lines(log_path, lines)
    return log_path


def test_archive_run_log_local(tmp_path):
    """D-170: orchestrator drains LocalBackend.log_iter into archive/<id>/run.log on terminal."""
    pytest.skip("Requires live LocalBackend daemon; covered by integration in Wave 4 plan 06-07.")


def test_archive_run_log_slurm(tmp_path):
    """D-170: orchestrator drains SLURMBackend.log_iter into archive/<id>/run.log on terminal."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    config = {
        "backend": {"name": "slurm", "slurm": {
            "debug_in_process": True, "walltime_seconds": 60,
            "directives": {"partition": "debug", "account": "t", "cpus_per_task": 1, "mem_gb": 1},
        }},
    }
    backend = SLURMBackend(automil_dir=automil_dir, config=config)
    spec = make_spec("node_log_slurm", tmp_path, command=("echo", "hello-slurm"))
    handle = backend.submit(spec)
    wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=10.0)
    log_path = _drain_to_archive(backend, handle, automil_dir / "orchestrator" / "archive")
    assert log_path.exists()
    assert "hello-slurm" in log_path.read_text()


def test_archive_run_log_ray(tmp_path):
    """D-170: orchestrator drains RayBackend.log_iter into archive/<id>/run.log on terminal."""
    pytest.importorskip("ray")
    import ray
    from automil.backends.ray import RayBackend
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, log_to_driver=False)
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    backend = RayBackend(
        automil_dir=automil_dir,
        config={"backend": {"name": "ray", "ray": {"allow_local_fallback": True}}},
    )
    spec = make_spec("node_log_ray", tmp_path, command=("echo", "hello-ray"))
    handle = backend.submit(spec)
    try:
        wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=20.0)
        log_path = _drain_to_archive(backend, handle, automil_dir / "orchestrator" / "archive")
        assert log_path.exists()
        assert "hello-ray" in log_path.read_text()
    finally:
        if backend._we_started_ray:
            ray.shutdown()


def test_log_iter_close_60s_timeout(tmp_path):
    """D-170: orchestrator force-closes log_iter at 60s post-terminal (drain wrapper enforces)."""
    from automil.backends._orchestrator_daemon import _drain_log_iter_with_timeout
    # The helper wraps backend.log_iter() and force-closes after the timeout.
    # A pathological backend that yields forever must be drained in <= timeout + small slack.
    class _ForeverBackend:
        def log_iter(self, _handle):
            while True:
                yield "looping\n"
                time.sleep(0.1)
    start = time.monotonic()
    lines = _drain_log_iter_with_timeout(_ForeverBackend(), handle=None, timeout=2.0)
    elapsed = time.monotonic() - start
    assert elapsed < 3.0, f"drain took {elapsed:.2f}s; expected < 3.0s"
    assert isinstance(lines, list)
```

**File 4 — `tests/backends/test_node_0176_smoke.py`** (1 parametrised test per D-176):
```python
"""Wave 0 stub for D-176 acceptance smoke (BCK-05/06).

Parametrised over [local, slurm-debug, ray-local]; runs a CCRCC node_0176-equivalent
synthetic 1-fold variant; asserts result.json composite within ±0.005 of LocalBackend baseline.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# Synthetic baseline: matches what the synthetic train.py below produces.
_LOCAL_BASELINE_COMPOSITE = 0.502


def _setup_smoke_project(tmp_path: Path) -> tuple[Path, Path]:
    """Init a minimal git repo with a synthetic train.py producing composite=0.502."""
    train_py = tmp_path / "train.py"
    train_py.write_text(
        "import json, pathlib\n"
        "result = {\n"
        "    'status': 'completed',\n"
        "    'metrics': {'val_auc': 0.87, 'val_bacc': 0.81, 'test_auc': 0.87, 'test_bacc': 0.83},\n"
        "    'composite': 0.502,\n"
        "    'elapsed_seconds': 1,\n"
        "}\n"
        "pathlib.Path('result.json').write_text(json.dumps(result))\n"
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=tmp_path, check=True)
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    return tmp_path, automil_dir


@pytest.mark.parametrize("backend_name", ["local", "slurm-debug", "ray-local"])
def test_node_0176_equivalent_composite_within_tolerance(backend_name, tmp_path):
    """D-176: every CI-runnable backend reproduces composite within ±0.005 of LocalBackend baseline."""
    if backend_name.startswith("slurm"):
        pytest.importorskip("submitit")
    if backend_name.startswith("ray"):
        pytest.importorskip("ray")

    project_root, automil_dir = _setup_smoke_project(tmp_path)
    # Implementation in plan 06-09 wires the backend factory and runs the synthetic spec.
    from tests.backends._smoke_helpers import run_node_0176_smoke
    composite = run_node_0176_smoke(backend_name, project_root, automil_dir)
    assert abs(composite - _LOCAL_BASELINE_COMPOSITE) <= 0.005, \
        f"backend={backend_name} composite={composite} drifted > 0.005 from baseline {_LOCAL_BASELINE_COMPOSITE}"
```

The `tests/backends/_smoke_helpers.py` module is created in plan 06-09 (Wave 5) — it will contain `run_node_0176_smoke(backend_name, project_root, automil_dir) -> float`.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_slurm_directives.py tests/backends/test_running_namespace.py tests/backends/test_log_unification.py tests/backends/test_node_0176_smoke.py --collect-only -q</automated>
  </verify>
  <done>
    All 4 stub files exist and import cleanly (no module-level ImportError). `pytest --collect-only` reports 11 collected items (3 + 3 + 4 + 1 parametrised over 3 backends = ≥ 11). Running `pytest tests/backends/test_slurm_directives.py -x` fails with `ImportError` or `AttributeError` referencing the not-yet-existing `_validate_slurm_directives`/`SlurmDirectivesIncompleteError`/`_walltime_to_timeout_min` (RED state per Nyquist). No SyntaxError anywhere.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Create real-cluster contract test stubs (test_contract_real_slurm.py + test_contract_real_ray.py)</name>
  <files>tests/backends/test_contract_real_slurm.py, tests/backends/test_contract_real_ray.py</files>
  <read_first>
    - tests/backends/test_contract.py (full file — the ≥12 scenarios this real-cluster harness re-exercises against actual SLURM/Ray)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-175 — `requires_slurm`/`requires_ray` markers + nightly-only intent)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"test_contract_real_slurm.py" lines 962-988 — pytestmark pattern + identical scenarios)
  </read_first>
  <action>
Both files declare a single module-level `pytestmark = pytest.mark.requires_slurm` (or `requires_ray`) so the entire module is skipped in default CI runs (the markers are NOT in the default `-m` filter, so `pytest tests/` skips them automatically). They define a single smoke test each — the full ≥12 scenario re-run is plan 06-08 (Wave 5) territory, but the stubs already gate the marker registration and prove the file collects.

**File 1 — `tests/backends/test_contract_real_slurm.py`**:
```python
"""@pytest.mark.requires_slurm — real SLURM cluster contract tests (D-175).

Skipped in CI by default (the marker is not selected). Run nightly via:
    uv run pytest tests/backends/test_contract_real_slurm.py -m requires_slurm

Configures SLURMBackend against an actual SLURM cluster on PATH (sbatch/scancel/sacct);
exercises the same S-01..S-12 scenarios as test_contract.py.

Real-cluster fixture config is read from environment variables:
    AUTOMIL_TEST_SLURM_PARTITION   — required
    AUTOMIL_TEST_SLURM_ACCOUNT     — required
    AUTOMIL_TEST_SLURM_QOS         — optional
    AUTOMIL_TEST_SLURM_CPUS        — default "1"
    AUTOMIL_TEST_SLURM_MEM_GB      — default "4"
"""
from __future__ import annotations

import os
import shutil

import pytest

pytestmark = pytest.mark.requires_slurm


@pytest.fixture
def real_slurm_backend(tmp_path):
    """Real SLURMBackend against the cluster on PATH."""
    pytest.importorskip("submitit")
    if shutil.which("sbatch") is None:
        pytest.skip("sbatch not found on PATH; cannot exercise real SLURM cluster")
    partition = os.environ.get("AUTOMIL_TEST_SLURM_PARTITION")
    account = os.environ.get("AUTOMIL_TEST_SLURM_ACCOUNT")
    if not (partition and account):
        pytest.skip("AUTOMIL_TEST_SLURM_PARTITION and AUTOMIL_TEST_SLURM_ACCOUNT must be set")

    from automil.backends.slurm import SLURMBackend
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    config = {
        "backend": {"name": "slurm", "slurm": {
            "debug_in_process": False,  # REAL cluster
            "walltime_seconds": 600,
            "directives": {
                "partition": partition,
                "account": account,
                "qos": os.environ.get("AUTOMIL_TEST_SLURM_QOS"),
                "cpus_per_task": int(os.environ.get("AUTOMIL_TEST_SLURM_CPUS", "1")),
                "mem_gb": int(os.environ.get("AUTOMIL_TEST_SLURM_MEM_GB", "4")),
            },
        }},
    }
    yield SLURMBackend(automil_dir=automil_dir, config=config)


def test_real_slurm_submit_completes(real_slurm_backend, tmp_path):
    """Smoke: real SLURM cluster runs `echo hello` and reaches COMPLETED."""
    from automil.backends.base import JobState
    from tests.backends.conftest import make_spec, wait_for_state
    spec = make_spec("real_slurm_smoke", tmp_path, command=("echo", "hello-real-slurm"))
    handle = real_slurm_backend.submit(spec)
    final = wait_for_state(real_slurm_backend, handle, {JobState.COMPLETED}, timeout=300.0)
    assert final == JobState.COMPLETED
```

**File 2 — `tests/backends/test_contract_real_ray.py`**:
```python
"""@pytest.mark.requires_ray — real Ray cluster contract tests (D-175).

Skipped in CI by default. Run nightly via:
    RAY_ADDRESS=ray://head:10001 uv run pytest tests/backends/test_contract_real_ray.py -m requires_ray
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.requires_ray


@pytest.fixture
def real_ray_backend(tmp_path):
    """Real RayBackend against the cluster at RAY_ADDRESS."""
    pytest.importorskip("ray")
    if not os.environ.get("RAY_ADDRESS"):
        pytest.skip("RAY_ADDRESS must be set to a real cluster (e.g. ray://head:10001)")
    import ray
    from automil.backends.ray import RayBackend
    if not ray.is_initialized():
        ray.init(address=os.environ["RAY_ADDRESS"], ignore_reinit_error=True, log_to_driver=False)
    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "ray").mkdir(parents=True)
    (automil_dir / "orchestrator" / "archive").mkdir(parents=True)
    backend = RayBackend(
        automil_dir=automil_dir,
        config={"backend": {"name": "ray", "ray": {"allow_local_fallback": False}}},
    )
    yield backend
    # NOTE: do NOT ray.shutdown() — operator owns the real cluster (D-161).


def test_real_ray_submit_completes(real_ray_backend, tmp_path):
    """Smoke: real Ray cluster runs `echo hello` and reaches COMPLETED."""
    from automil.backends.base import JobState
    from tests.backends.conftest import make_spec, wait_for_state
    spec = make_spec("real_ray_smoke", tmp_path, command=("echo", "hello-real-ray"))
    handle = real_ray_backend.submit(spec)
    final = wait_for_state(real_ray_backend, handle, {JobState.COMPLETED}, timeout=300.0)
    assert final == JobState.COMPLETED
```
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_contract_real_slurm.py tests/backends/test_contract_real_ray.py --collect-only -q && uv run pytest tests/backends/test_contract_real_slurm.py tests/backends/test_contract_real_ray.py 2>&1 | grep -E "skipped|deselected"</automated>
  </verify>
  <done>
    Both files collect under `pytest --collect-only` (no syntax/import errors at module level). Default `pytest tests/backends/test_contract_real_slurm.py` reports the test as SKIPPED (because `requires_slurm` marker not selected, OR `sbatch` not on PATH). Same for the Ray file. No real cluster is contacted.
  </done>
</task>

</tasks>

<verification>

```bash
# All Wave 0 stubs collect (no SyntaxError, no module-level ImportError)
uv run pytest tests/backends/ --collect-only -q

# Pytest markers registered
uv run pytest --markers 2>&1 | grep -E "requires_slurm|requires_ray"

# Phase 5 baseline preserved
uv run pytest tests/ --collect-only 2>&1 | tail -1
# Expected: ≥789 collected (779 baseline + new stubs minus skips)

# Existing 779-test Phase 5 suite still green
uv run pytest tests/ -x -q --ignore=tests/backends/test_slurm_directives.py --ignore=tests/backends/test_running_namespace.py --ignore=tests/backends/test_log_unification.py --ignore=tests/backends/test_node_0176_smoke.py
```

</verification>

<success_criteria>

- [ ] `pyproject.toml` `[tool.pytest.ini_options]` block contains `markers = [...]` with both `requires_slurm` and `requires_ray` entries.
- [ ] `tests/backends/conftest.py` `backend` fixture parametrises over `["local", "mock_slurm", "slurm", "ray"]`; SLURM/Ray branches use `pytest.importorskip` so missing extras skip cleanly without erroring.
- [ ] All 6 new test files exist and collect cleanly (`pytest --collect-only` reports new test IDs).
- [ ] Stubs are RED (fail with `ImportError`/`AttributeError` referencing not-yet-existing names) — that is the Nyquist hand-off.
- [ ] Phase 5's 779-test baseline remains green; no Phase 5 test regresses.
- [ ] No new ruff/mypy errors; no autobench/AUTOBENCH_/benchmarks/ references in any new test file (`grep -r "autobench\|AUTOBENCH_\|benchmarks/" tests/backends/test_slurm_directives.py tests/backends/test_running_namespace.py tests/backends/test_log_unification.py tests/backends/test_node_0176_smoke.py tests/backends/test_contract_real_slurm.py tests/backends/test_contract_real_ray.py` returns zero matches).

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-01-SUMMARY.md` describing: which stubs were created, which extras-import-skip behaviors were observed, the Phase 5 baseline test count after collection, and any deviations from this plan.
</output>
