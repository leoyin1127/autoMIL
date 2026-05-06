---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 04
type: execute
wave: 2
depends_on: ["06-01", "06-02", "06-03"]
files_modified:
  - src/automil/backends/slurm.py
autonomous: true
requirements: [BCK-05]

must_haves:
  truths:
    - "`SLURMBackend` is registered as `BACKENDS['slurm']` after `from automil.backends import slurm` succeeds."
    - "`SLURMBackend(automil_dir, config)` constructs a `submitit.AutoExecutor(folder=..., cluster='slurm'|'debug')` based on `config['backend']['slurm']['debug_in_process']`."
    - "`update_parameters` is called with `timeout_min=max(1, walltime_seconds // 60)` (NOT `time=`) and `slurm_additional_parameters={'signal': 'B:TERM@30'}` (NOT `signal=`) per RESEARCH.md OQ-1 corrections."
    - "`submit(spec)` creates the worktree via `runner.Runner` BEFORE `executor.submit(_run_experiment_subprocess, spec, worktree_path)`; worktree path is an explicit function argument, NOT a JobSpec field (RESEARCH.md OQ-4)."
    - "`poll(handle)` reconstructs `submitit.Job(folder=..., job_id=handle.opaque_id)` and maps `.state` through `_SLURM_STATE_MAP`."
    - "`log_iter(handle)` tails `job.paths.stdout` (NOT a hardcoded `{job_id}_log.out`) per RESEARCH.md OQ-2."
    - "`cancel(handle, signal=None)` calls `submitit.Job.cancel()`; honors a custom-signal warning per Phase 2 D-57."
    - "`list_running()` scans `running/slurm/*.json` (D-169 namespacing); restart-recovery transitions stale handles → CRASHED with `crash_reason='lost-from-slurm'`."
    - "Zero `os.kill | os.killpg | Popen | .pid` references in slurm.py (BCK-04 lint clean — submitit APIs are sufficient)."
    - "Zero `autobench`/`AUTOBENCH_`/`benchmarks/` references in slurm.py (framework purity per project_automil_is_generic memory)."
    - "Wave-0 stub `test_walltime_seconds_to_timeout_min` flips RED→GREEN."
  artifacts:
    - path: src/automil/backends/slurm.py
      provides: "SLURMBackend on submitit AutoExecutor with framework-mandated signal directive."
      contains: "@register(\"slurm\")"
      min_lines: 250
  key_links:
    - from: src/automil/backends/slurm.py
      to: submitit.AutoExecutor.update_parameters
      via: framework-mandated signal directive
      pattern: 'slurm_additional_parameters=\\{"signal": "B:TERM@30"\\}'
    - from: src/automil/backends/slurm.py
      to: submitit.Job.paths.stdout
      via: log_iter tail source
      pattern: "job\\.paths\\.stdout"
    - from: src/automil/backends/slurm.py
      to: src/automil/runner.Runner
      via: worktree creation in submit()
      pattern: "from automil\\.runner import Runner|self\\._runner"
---

<objective>
Wave 2A — SLURMBackend implementation. This is one of the two load-bearing implementations in Phase 6. After this plan: a SLURM-installed user can `pip install -e '.[slurm]'`, set `backend.name: slurm` + valid directives in config.yaml, and submit a CCRCC variant; the contract test parametrised on `slurm` (DebugExecutor) passes ≥10 scenarios.

Purpose: ship the SLURM dispatch path on submitit's library API, with all four RESEARCH.md API corrections applied inline (timeout_min not time, slurm_additional_parameters not signal=, paths.stdout not hardcoded filename, worktree path passed explicitly to remote function). The framework-mandated `--signal=B:TERM@30` directive couples the cap contract (Phase 4 D-115) into SLURM's native signal-delivery machinery.

Output: ~250–350-line `src/automil/backends/slurm.py` with all five Backend ABC methods + `_run_experiment_subprocess` top-level function + `_SLURM_STATE_MAP` constant + `_walltime_to_timeout_min` helper. Plan 06-08 (Wave 5) extends `tests/backends/test_contract.py` to cover this backend; plan 06-09 covers the acceptance smoke.
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
@.planning/phases/02-backend-abc-localbackend-re-export-shim-mockslurm-fixture/02-CONTEXT.md
@CLAUDE.md

# Closest analog (mock_slurm.py is the contract-test partner; local.py shows worktree+launch pattern):
@src/automil/backends/mock_slurm.py
@src/automil/backends/local.py
@src/automil/backends/base.py
@src/automil/runner.py

# Wave-0 stub this plan flips green:
@tests/backends/test_slurm_directives.py

<interfaces>
<!-- Public surface created by this plan. Plan 06-08 (contract test) and 06-09 (smoke) consume these. -->

From src/automil/backends/slurm.py (after this plan):
```python
from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends.errors import BackendError
from automil.backends import register

# Top-level function — picklable for submitit dispatch (NOT a class method).
def _run_experiment_subprocess(spec: JobSpec, worktree_path: Path) -> int:
    """Inside the SLURM worker: chdir into worktree, set env, subprocess.run(spec.command)."""
    ...

def _walltime_to_timeout_min(walltime_seconds: int) -> int:
    """RESEARCH.md OQ-1: max(1, walltime_seconds // 60). Pure helper for unit tests."""
    return max(1, walltime_seconds // 60)

_SLURM_STATE_MAP: dict[str, JobState] = { ... }  # see PATTERNS.md lines 116-132

@register("slurm")
class SLURMBackend(Backend):
    def __init__(self, automil_dir: Path, config: dict) -> None: ...
    def submit(self, spec: JobSpec) -> JobHandle: ...
    def poll(self, handle: JobHandle) -> JobState: ...
    def list_running(self) -> list[JobHandle]: ...
    def cancel(self, handle: JobHandle, signal: Optional[int] = None) -> None: ...
    def log_iter(self, handle: JobHandle) -> Iterator[str]: ...
```

Critical API corrections (RESEARCH.md OQ-1..4) APPLIED inline:
- `update_parameters(timeout_min=..., slurm_additional_parameters={"signal": "B:TERM@30"}, ...)` — NOT `time=` and NOT `signal=`.
- `submitit.AutoExecutor(folder=..., cluster="slurm")` explicitly (NOT auto-detect, which falls back to local on dev machines without sbatch).
- `cluster="debug"` when `config["backend"]["slurm"]["debug_in_process"] == True` (DebugExecutor for CI).
- `job.paths.stdout` for log path (NOT hardcoded `{job_id}_log.out`).
- worktree path passed as explicit function arg to `_run_experiment_subprocess` (NOT JobSpec field — JobSpec is frozen and locked from Phase 2).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement SLURMBackend class + _run_experiment_subprocess + helpers</name>
  <files>src/automil/backends/slurm.py</files>
  <read_first>
    - src/automil/backends/mock_slurm.py (full file — closest analog for backend lifecycle, _TERMINAL_STATES, eventual-consistency JobHandle pattern)
    - src/automil/backends/local.py (lines 270-360 — `cancel()` with custom-signal warning + `list_running()` scan + `log_iter()` tail loop)
    - src/automil/backends/base.py (full file — Backend ABC + JobHandle + JobSpec + JobState contracts)
    - src/automil/runner.py (full file — Runner.create_worktree pattern; SLURMBackend.submit creates the worktree before dispatch)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"src/automil/backends/slurm.py" lines 39-211 — full pattern map with code excerpts)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md (Pitfalls 1, 2, 3, 7, 8, 10; Code Examples §"SLURMBackend skeleton")
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-155, D-156, D-157, D-158, D-159, D-160 — five SLURM decision blocks)
  </read_first>
  <behavior>
    - Test 1: `from automil.backends.slurm import SLURMBackend, _walltime_to_timeout_min, _SLURM_STATE_MAP` succeeds (after `pip install submitit`).
    - Test 2: `_walltime_to_timeout_min(0) == 1`, `(60) == 1`, `(120) == 2`, `(21600) == 360` (Wave-0 stub flips green).
    - Test 3: `SLURMBackend(automil_dir, config_with_debug=True)` constructs without raising; `_executor` is a `submitit.AutoExecutor` with `cluster="debug"`.
    - Test 4: `SLURMBackend(...).submit(spec)` returns a JobHandle whose `backend == "slurm"`, `node_id == spec.node_id`, `opaque_id` is non-empty.
    - Test 5: After `submit`, `running/slurm/<node_id>.json` exists with `{"node_id", "backend", "opaque_id", "submitted_at", "spec_path", "cap_cancel_pending": false}`.
    - Test 6: `poll(handle)` returns `JobState.COMPLETED` after the DebugExecutor finishes the synthetic command.
    - Test 7: `_SLURM_STATE_MAP["TIMEOUT"] == JobState.BUDGET_KILLED`; `_SLURM_STATE_MAP["FAILED"] == JobState.CRASHED`.
    - Test 8: BCK-04 lint clean — `python scripts/check_backend_isolation.py src/automil/` exits 0 (slurm.py NOT in allowlist; submitit APIs are sufficient).
    - Test 9: framework purity — `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/slurm.py` returns 0.
  </behavior>
  <action>
Create `src/automil/backends/slurm.py` with the structure below. This is the FULL file; do not modify any other source.

**Top of file — module docstring + imports**:
```python
"""SLURMBackend on submitit>=1.5.3 (BCK-05 / D-152..D-160, D-179).

Opt-in via ``pip install -e '.[slurm]'``. Implements the Phase 2 Backend ABC
(D-51..D-58) by dispatching jobs to a SLURM cluster through submitit's
AutoExecutor. The framework-mandated ``--signal=B:TERM@30`` SLURM directive
couples the Phase 4 D-115 cap contract into SLURM's native signal delivery.

Critical API decisions (RESEARCH.md OQ-1..4 corrections applied inline):
  - ``update_parameters(timeout_min=...)`` NOT ``time=`` (AutoExecutor uses the shared param name)
  - ``slurm_additional_parameters={"signal": "B:TERM@30"}`` NOT ``signal=`` kwarg
  - ``cluster="slurm"`` explicitly (not auto-detect; fails loudly if sbatch absent)
  - ``cluster="debug"`` when ``config['backend']['slurm']['debug_in_process']`` (CI)
  - ``job.paths.stdout`` for log-file path (NOT hardcoded ``{job_id}_log.out``)
  - worktree path passed explicitly to ``_run_experiment_subprocess`` (NOT a JobSpec field)

BCK-04: zero ``os.kill | os.killpg | Popen | .pid`` references — submitit APIs
are sufficient for the entire dispatch + state lifecycle.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Iterator, Optional

import submitit  # opt-in via [slurm] extra; ImportError caught by backends/__init__.py

from automil.backends import register
from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends.errors import BackendError

logger = logging.getLogger(__name__)
```

**Pure helpers + state map**:
```python
def _walltime_to_timeout_min(walltime_seconds: int) -> int:
    """RESEARCH.md OQ-1 / D-155 corrected: convert walltime_seconds → timeout_min.

    Pure function so Wave-0 ``test_walltime_seconds_to_timeout_min`` can exercise
    it without instantiating the backend or submitit.
    """
    return max(1, walltime_seconds // 60)


_TERMINAL_STATES: frozenset[JobState] = frozenset({
    JobState.COMPLETED, JobState.CRASHED,
    JobState.CANCELLED, JobState.BUDGET_KILLED,
})


# D-157 + RESEARCH.md §"SLURM state map".
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
    "UNKNOWN":        JobState.PENDING,  # fall-through; see _state_str_to_jobstate
}
```

**Top-level remote function (picklable; runs on the SLURM worker)**:
```python
def _run_experiment_subprocess(spec: JobSpec, worktree_path: Path) -> int:
    """Inside the SLURM worker process — runs the experiment.

    RESEARCH.md OQ-4 / Pitfall 8: worktree_path is passed explicitly because
    JobSpec is frozen (Phase 2 D-54) and we cannot add a worktree-path field.

    Steps:
      1. chdir into ``worktree_path / spec.working_subdir``.
      2. Set env from ``spec.env`` (whitelisted at orchestrator-side per CLN-02 D-04).
      3. ``subprocess.run(spec.command, check=False)``; return retcode.

    Notes:
      - We do NOT use ``Popen`` (BCK-04). ``subprocess.run`` is sufficient.
      - stdout/stderr land in submitit's ``{job_id}_0_log.out`` (D-159 corrected via
        ``job.paths.stdout``); log_iter tails that file.
      - SIGTERM (from ``--signal=B:TERM@30``) propagates to the subprocess; the
        user training script's ``register_sigterm_flush()`` (Phase 4 D-122)
        handles the per-fold partial-write.
    """
    import subprocess  # noqa: PLC0415; needed inside remote
    import os as _os    # noqa: PLC0415

    target_dir = worktree_path / spec.working_subdir if spec.working_subdir else worktree_path
    # Build subprocess env without mutating os.environ (DebugExecutor runs in-process
    # under pytest; mutating shared state pollutes subsequent tests).
    sub_env = dict(_os.environ)
    for k, v in spec.env:
        sub_env[k] = v
    # cwd= passes the chdir down to the child only — does NOT mutate the parent CWD
    # (avoids cross-test contamination under DebugExecutor / Ray local cluster).
    completed = subprocess.run(list(spec.command), cwd=str(target_dir), env=sub_env, check=False)
    return completed.returncode
```

**`SLURMBackend` class — five Backend ABC methods**:

`__init__`:
```python
@register("slurm")
class SLURMBackend(Backend):
    """SLURM dispatch via submitit AutoExecutor (BCK-05 / D-155..D-160)."""

    def __init__(
        self,
        automil_dir: Path,
        config: dict,
        project_root: Optional[Path] = None,
    ) -> None:
        self._automil_dir = Path(automil_dir)
        self._config = config
        self._project_root = Path(project_root) if project_root else self._automil_dir.parent

        backend_cfg = config.get("backend", {}) or {}
        slurm_cfg = backend_cfg.get("slurm", {}) or {}
        directives = slurm_cfg.get("directives", {}) or {}
        debug_in_process = bool(slurm_cfg.get("debug_in_process", False))
        walltime_seconds = int(slurm_cfg.get("walltime_seconds", 21600))

        self._logs_dir = self._automil_dir / "orchestrator" / "running" / "slurm" / "submitit-logs"
        self._logs_dir.mkdir(parents=True, exist_ok=True)
        self._running_dir = self._automil_dir / "orchestrator" / "running" / "slurm"
        self._running_dir.mkdir(parents=True, exist_ok=True)

        # D-155 + RESEARCH.md OQ-1: timeout_min, slurm_additional_parameters.
        cluster = "debug" if debug_in_process else "slurm"
        self._executor = submitit.AutoExecutor(folder=str(self._logs_dir), cluster=cluster)

        update_kwargs: dict = {
            "timeout_min": _walltime_to_timeout_min(walltime_seconds),
            "slurm_additional_parameters": {"signal": "B:TERM@30"},
        }
        # Required directives (validated upstream by automil check / D-172).
        if "cpus_per_task" in directives:
            update_kwargs["cpus_per_task"] = int(directives["cpus_per_task"])
        if "mem_gb" in directives:
            update_kwargs["mem_gb"] = int(directives["mem_gb"])
        if directives.get("gpus_per_node") is not None:
            update_kwargs["gpus_per_node"] = int(directives["gpus_per_node"])
        if directives.get("partition"):
            update_kwargs["slurm_partition"] = directives["partition"]
        if directives.get("account"):
            update_kwargs["slurm_account"] = directives["account"]
        if directives.get("qos"):
            update_kwargs["slurm_qos"] = directives["qos"]

        self._executor.update_parameters(**update_kwargs)
        logger.info("SLURMBackend initialised: cluster=%s timeout_min=%d",
                    cluster, update_kwargs["timeout_min"])
```

`submit`:
```python
    def submit(self, spec: JobSpec) -> JobHandle:
        """Dispatch via submitit. Creates worktree first; passes path to remote function (RESEARCH.md OQ-4)."""
        from automil.runner import Runner  # noqa: PLC0415; lazy to avoid cycles
        runner = Runner(self._project_root)
        # Real Runner API: 2-positional create_worktree, then separate apply_overlay
        # (mirrors _orchestrator_daemon.py:629–642 — the canonical two-step pattern)
        worktree_path = runner.create_worktree(spec.base_commit, spec.node_id)
        if spec.overlay_dir:
            runner.apply_overlay(
                worktree_path,
                spec.overlay_dir,
                deletions=getattr(spec, "deletions", None),
            )
        try:
            job = self._executor.submit(_run_experiment_subprocess, spec, worktree_path)
        except FileNotFoundError as exc:
            raise BackendError(
                "SLURM tools not found on PATH; this machine doesn't appear to have a "
                "SLURM installation. To use SLURMBackend, run on a SLURM-equipped node "
                "or set backend.slurm.debug_in_process=true for in-process testing."
            ) from exc

        opaque_id = str(job.job_id)
        handle = JobHandle(
            node_id=spec.node_id,
            backend="slurm",
            opaque_id=opaque_id,
            submitted_at=time.time(),
        )
        self._persist_running(handle, spec, worktree_path)
        return handle

    def _persist_running(self, handle: JobHandle, spec: JobSpec, worktree_path: Path) -> None:
        """Write running/slurm/<node_id>.json atomically (D-25 / Phase 0 pattern)."""
        payload = {
            "node_id": handle.node_id,
            "backend": "slurm",
            "opaque_id": handle.opaque_id,
            "submitted_at": handle.submitted_at,
            "spec_path": str(spec.overlay_dir / "spec.json"),
            "worktree_path": str(worktree_path),
            "cap_cancel_pending": False,
        }
        path = self._running_dir / f"{handle.node_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)  # path.unlink rollback per memory:feedback_never_blind_checkout
            except OSError:
                pass
            raise
```

`poll`:
```python
    def poll(self, handle: JobHandle) -> JobState:
        """Reconstruct submitit.Job; map state via _SLURM_STATE_MAP."""
        try:
            job = submitit.Job(folder=str(self._logs_dir), job_id=handle.opaque_id)
            state_str = (job.state or "UNKNOWN").upper()
        except Exception as exc:
            logger.warning("SLURMBackend.poll: error querying SLURM for %s: %s",
                           handle.node_id, exc)
            return JobState.PENDING
        return _SLURM_STATE_MAP.get(state_str, JobState.PENDING)
```

`list_running`:
```python
    def list_running(self) -> list[JobHandle]:
        """Scan running/slurm/*.json (D-169 namespacing)."""
        handles: list[JobHandle] = []
        if not self._running_dir.exists():
            return handles
        for spec_file in sorted(self._running_dir.glob("*.json")):
            try:
                payload = json.loads(spec_file.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("SLURMBackend.list_running: skipping %s: %s",
                               spec_file.name, exc)
                continue
            handles.append(JobHandle(
                node_id=payload.get("node_id", spec_file.stem),
                backend="slurm",
                opaque_id=payload.get("opaque_id", ""),
                submitted_at=payload.get("submitted_at", spec_file.stat().st_mtime),
            ))
        return handles
```

`cancel`:
```python
    def cancel(self, handle: JobHandle, signal: Optional[int] = None) -> None:
        """Fire-and-forget SLURM cancel via submitit.Job.cancel().

        Custom-signal warning per Phase 2 D-57.
        """
        if signal is not None:
            import signal as _sig  # noqa: PLC0415
            if signal != _sig.SIGTERM:
                logger.warning(
                    "SLURMBackend.cancel: custom signal %d; the standard "
                    "SIGTERM→scancel→TIMEOUT escalation is bypassed.",
                    signal,
                )
        try:
            job = submitit.Job(folder=str(self._logs_dir), job_id=handle.opaque_id)
            job.cancel()
        except Exception as exc:
            logger.warning("SLURMBackend.cancel: scancel failed for %s: %s",
                           handle.node_id, exc)
```

`log_iter`:
```python
    def log_iter(self, handle: JobHandle) -> Iterator[str]:
        """Tail submitit's stdout file with 1s tick; closes on terminal state.

        RESEARCH.md OQ-2 / D-159 corrected: use ``job.paths.stdout`` (a Path),
        which resolves to ``{job_id}_0_log.out`` — NOT hardcoded ``{job_id}_log.out``.
        """
        try:
            job = submitit.Job(folder=str(self._logs_dir), job_id=handle.opaque_id)
            log_path = Path(job.paths.stdout)
        except Exception as exc:
            logger.warning("SLURMBackend.log_iter: cannot resolve stdout for %s: %s",
                           handle.node_id, exc)
            return

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
                    for line in new_text.splitlines(keepends=True):
                        yield line

            state = self.poll(handle)
            if state in _TERMINAL_STATES:
                if log_path.exists():
                    try:
                        text = log_path.read_text()
                    except OSError:
                        text = ""
                    if len(text) > offset:
                        for line in text[offset:].splitlines(keepends=True):
                            yield line
                return

            time.sleep(1.0)  # 1s tick (vs 0.1s for local — SLURM polling is slower)
```

DO NOT add slurm.py to `scripts/check_backend_isolation.py` allowlist. The implementation above uses NO `os.kill`, NO `Popen`, NO `.pid` — only `subprocess.run(cwd=..., env=...)` (allowed; cwd kwarg avoids mutating parent CWD), `submitit` library calls, filesystem, and `os.replace`/`os.unlink`/`os.fdopen`/`os.environ` reads (none of which are flagged).
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_slurm_directives.py::test_walltime_seconds_to_timeout_min -x -v && python scripts/check_backend_isolation.py src/automil/ && ! grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/slurm.py && uv run python -c "from automil.backends.slurm import SLURMBackend, _walltime_to_timeout_min, _SLURM_STATE_MAP; print('ok')"</automated>
  </verify>
  <done>
    `src/automil/backends/slurm.py` exists with the structure described above (≥250 lines). `_walltime_to_timeout_min` Wave-0 stub flips green. `BACKENDS["slurm"]` is `SLURMBackend` after `from automil.backends.slurm import SLURMBackend` (in environments with submitit installed). BCK-04 lint passes (slurm.py NOT in allowlist). Zero autobench/AUTOBENCH_/benchmarks/ refs. The contract test parametrised on `slurm` (Wave 5 plan 06-08) is the next gate; this plan does NOT itself run the contract suite — its own Wave-0 stub is the only test it flips.
  </done>
</task>

</tasks>

<verification>

```bash
# Wave-0 stub for walltime helper flips green
uv run pytest tests/backends/test_slurm_directives.py::test_walltime_seconds_to_timeout_min -x -v

# BCK-04 lint clean (slurm.py NOT in allowlist; submitit suffices)
python scripts/check_backend_isolation.py src/automil/

# Framework purity
grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/slurm.py
# Expected: zero matches.

# Module imports cleanly post-extras-install
uv run python -c "from automil.backends.slurm import SLURMBackend, _walltime_to_timeout_min, _SLURM_STATE_MAP; print('ok')"

# Phase 5 baseline preserved
uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py
```

</verification>

<success_criteria>

- [ ] `src/automil/backends/slurm.py` exists, ≥250 lines.
- [ ] `_walltime_to_timeout_min(walltime_seconds: int) -> int` is a module-level pure function returning `max(1, walltime_seconds // 60)`.
- [ ] `_SLURM_STATE_MAP["TIMEOUT"] == JobState.BUDGET_KILLED` and `_SLURM_STATE_MAP["FAILED"] == JobState.CRASHED`.
- [ ] `SLURMBackend.__init__` calls `update_parameters` with `timeout_min=...` and `slurm_additional_parameters={"signal": "B:TERM@30"}` — verified by grep:
  `grep -E '"signal":\s*"B:TERM@30"' src/automil/backends/slurm.py | grep -v '^#' | wc -l` ≥ 1.
- [ ] No `time=` kwarg passed to `update_parameters` — `grep -nE 'update_parameters\\(.*\\btime=' src/automil/backends/slurm.py | grep -v '^#'` returns 0.
- [ ] `SLURMBackend.submit` creates a worktree via `runner.Runner` BEFORE calling `executor.submit`.
- [ ] `SLURMBackend.log_iter` uses `job.paths.stdout` — `grep -E 'job\\.paths\\.stdout' src/automil/backends/slurm.py` returns ≥ 1.
- [ ] `@register("slurm")` decorator on the class.
- [ ] BCK-04 lint clean: `python scripts/check_backend_isolation.py src/automil/` exits 0; slurm.py NOT in `ALLOWLIST_PATHS`.
- [ ] Framework purity: `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/slurm.py` returns 0.
- [ ] Wave-0 stub `test_walltime_seconds_to_timeout_min` flips RED → GREEN.
- [ ] Phase 5 baseline preserved.

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-04-SUMMARY.md` describing: file size, test count delta, lint status, API correction confirmations.
</output>
