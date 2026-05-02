"""MockSLURMBackend — eventual-consistency test fixture (BCK-03 / D-62 / D-63 / D-69).

Simulates SLURM's poll-lag, opaque job_id, fire-and-forget cancel, and
node-local filesystem behaviour using ``threading.Timer`` + ``threading.Event``.

NOT auto-registered in ``backends/__init__.py`` — import this module explicitly
in tests to avoid leaking a test fixture into production config selection (D-69):

    from automil.backends.mock_slurm import MockSLURMBackend

Threading model:
- ``_lock`` (threading.Lock) guards ``_jobs`` dict; acquired by main thread and
  timer callbacks, but never nested.
- ``cancel_requested`` (threading.Event) per job — ``.set()`` is atomic.
- All threading.Timer instances are ``daemon=True`` to prevent test hangs.
- Deadlock prevention (T-02-06-S01): timer callbacks acquire ``_lock`` once,
  mutate state, then release.  They NEVER call poll(), cancel(), or any other
  Backend method while holding the lock.

State machine (D-63):
  submit() → PENDING
    after poll_lag_seconds → RUNNING
    after poll_lag_seconds → COMPLETED | CRASHED | CANCELLED

Command stub semantics (D-63):
  command containing "--crash" → CRASHED terminal
  cancel_requested set          → CANCELLED terminal
  all others                    → COMPLETED terminal
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends import register

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal job record
# ---------------------------------------------------------------------------

@dataclass
class _MockJob:
    """Mutable per-job state (NOT frozen — state and log_buffer change over time).

    ``cancel_requested`` and ``timer`` are runtime-only; they are excluded from
    JSON serialisation (T-02-06-S05).
    """

    handle: JobHandle
    state: JobState
    cancel_requested: threading.Event = field(default_factory=threading.Event)
    log_buffer: list[str] = field(default_factory=list)
    timer: Optional[threading.Timer] = field(default=None, repr=False)

    def _to_json(self) -> dict:
        """Serialise to JSON.  Excludes ``cancel_requested`` and ``timer`` (runtime-only)."""
        return {
            "node_id": self.handle.node_id,
            "backend": self.handle.backend,
            "opaque_id": self.handle.opaque_id,
            "submitted_at": self.handle.submitted_at,
            "state": self.state.value,
            "log_buffer": self.log_buffer,
        }

    @classmethod
    def _from_json(cls, data: dict) -> "_MockJob":
        """Deserialise from JSON.

        PENDING/RUNNING jobs at restart → CRASHED (RESEARCH.md §7):
        the timer thread is gone; jobs cannot resume their state transitions.
        This matches real SLURM behaviour when a head-node restart drops
        in-flight jobs.
        """
        handle = JobHandle(
            node_id=data["node_id"],
            backend=data["backend"],
            opaque_id=data["opaque_id"],
            submitted_at=data["submitted_at"],
        )
        state = JobState(data["state"])
        if state in (JobState.PENDING, JobState.RUNNING):
            logger.warning(
                "MockSLURMBackend restart: job %s was in state %s at shutdown; "
                "marking as CRASHED (no timer resumption possible).",
                data["node_id"],
                data["state"],
            )
            state = JobState.CRASHED
        return cls(handle=handle, state=state, log_buffer=data.get("log_buffer", []))


# ---------------------------------------------------------------------------
# MockSLURMBackend
# ---------------------------------------------------------------------------

_TERMINAL_STATES = frozenset(
    {JobState.COMPLETED, JobState.CRASHED, JobState.CANCELLED, JobState.BUDGET_KILLED}
)


@register("mock_slurm")
class MockSLURMBackend(Backend):
    """Eventual-consistency backend fixture that simulates SLURM semantics (BCK-03 / D-62).

    Parameters
    ----------
    poll_lag_seconds:
        Duration of each simulated lag phase (PENDING→RUNNING, RUNNING→terminal).
        Production default is 5.0 s (matches real SLURM sacct cache lag).
        Tests should pass 0.05 s to keep the suite fast.
    state_file:
        Optional path to persist and reload job state.  On construction, if
        the file exists its contents are loaded.  On every state transition the
        file is atomically updated.  Enables the restart-recovery scenario in
        the contract test (BCK-03 / S-12).
    """

    def __init__(
        self,
        poll_lag_seconds: float = 5.0,
        state_file: Optional[Path] = None,
    ) -> None:
        self._poll_lag = poll_lag_seconds
        self._jobs: dict[str, _MockJob] = {}   # opaque_id → _MockJob
        self._counter = 0
        self._lock = threading.Lock()
        self._state_file = Path(state_file) if state_file is not None else None
        if self._state_file is not None and self._state_file.exists():
            self._load_state()

    # ------------------------------------------------------------------
    # Backend ABC implementation
    # ------------------------------------------------------------------

    def submit(self, spec: JobSpec) -> JobHandle:
        """Submit a job; spawn a PENDING→RUNNING→terminal timer chain (D-62 / D-55)."""
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

        # --- Timer chain (RESEARCH.md §6 skeleton) ---
        # Deadlock prevention: callbacks acquire _lock ONCE, write state, release.
        # They do NOT call poll(), cancel(), or any other Backend method.

        def _finish() -> None:
            """Second tick: RUNNING → terminal state."""
            with self._lock:
                if job.cancel_requested.is_set():
                    job.state = JobState.CANCELLED
                else:
                    cmd_str = " ".join(spec.command)
                    if "--crash" in cmd_str or "--error" in cmd_str:
                        job.state = JobState.CRASHED
                        job.log_buffer.append("simulated crash")
                    else:
                        job.state = JobState.COMPLETED
                        job.log_buffer.append(
                            f"mock_slurm job {spec.node_id} completed"
                        )
                job.log_buffer.append(f"mock: job terminal ({job.state.value})")
            self._persist_state()

        def _transition() -> None:
            """First tick: PENDING → RUNNING; schedule second tick."""
            with self._lock:
                if job.cancel_requested.is_set():
                    job.state = JobState.CANCELLED
                    job.log_buffer.append("mock: job cancelled before start")
                    self._persist_state()
                    return
                job.state = JobState.RUNNING
                job.log_buffer.append("mock: job started")
            self._persist_state()
            # Second timer: RUNNING → terminal
            t2 = threading.Timer(self._poll_lag, _finish)
            t2.daemon = True
            t2.start()

        t = threading.Timer(self._poll_lag, _transition)
        t.daemon = True
        t.start()
        job.timer = t

        self._persist_state()
        logger.debug("MockSLURM submitted %s → opaque_id=%s", spec.node_id, opaque_id)
        return handle

    def poll(self, handle: JobHandle) -> JobState:
        """Return a snapshot of the job's current state (D-56 — pure, never blocking)."""
        with self._lock:
            job = self._jobs.get(handle.opaque_id)
        if job is None:
            raise ValueError(f"Unknown job: {handle.opaque_id!r}")
        return job.state

    def cancel(self, handle: JobHandle, signal: Optional[int] = None) -> None:  # noqa: ARG002
        """Fire-and-forget cancel: set the cancel flag; return None immediately (D-57).

        The next timer tick observes ``cancel_requested.is_set()`` and
        transitions the job to CANCELLED.  Unknown jobs are silently ignored
        (consistent with SLURM's ``scancel`` behaviour for stale ids).
        """
        with self._lock:
            job = self._jobs.get(handle.opaque_id)
        if job is None:
            return  # silently ignored (D-57)
        job.cancel_requested.set()  # threading.Event — atomic across threads

    def list_running(self) -> list[JobHandle]:
        """Return handles for all PENDING or RUNNING jobs (D-59).

        Snapshot under lock so callers see a consistent set.
        """
        with self._lock:
            return [
                j.handle
                for j in self._jobs.values()
                if j.state in (JobState.PENDING, JobState.RUNNING)
            ]

    def log_iter(self, handle: JobHandle) -> Iterator[str]:
        """Yield collected log once terminal; nothing while pending/running (D-58).

        Matches SLURM's stdout-on-completion model.  Callers should use
        ``wait_for_state`` from ``tests/backends/conftest.py`` before calling
        ``log_iter`` if they need to block until completion.
        """
        job = self._jobs.get(handle.opaque_id)
        if job is None:
            return
        if job.state in _TERMINAL_STATES:
            yield from job.log_buffer
            return
        # Non-terminal: poll until terminal, then yield
        while job.state not in _TERMINAL_STATES:
            time.sleep(0.05)
        yield from job.log_buffer

    # ------------------------------------------------------------------
    # State persistence helpers
    # ------------------------------------------------------------------

    def _persist_state(self) -> None:
        """Atomically write ``_jobs`` to ``state_file`` if configured."""
        if self._state_file is None:
            return
        with self._lock:
            data = [j._to_json() for j in self._jobs.values()]
        import os
        import tempfile

        path = self._state_file
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                f.write(json.dumps(data, indent=2))
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _load_state(self) -> None:
        """Read ``state_file`` and restore ``_jobs`` (for restart-recovery)."""
        assert self._state_file is not None
        try:
            raw = self._state_file.read_text()
            records: list[dict] = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "MockSLURMBackend: could not load state_file %s: %s; starting fresh.",
                self._state_file,
                exc,
            )
            return
        for item in records:
            job = _MockJob._from_json(item)
            self._jobs[job.handle.opaque_id] = job
            # Update counter to avoid opaque_id collisions on new submits
            try:
                numeric = int(job.handle.opaque_id.split(".")[0])
                if numeric > self._counter:
                    self._counter = numeric
            except (ValueError, IndexError):
                pass
        logger.debug(
            "MockSLURMBackend: loaded %d job(s) from state_file %s",
            len(records),
            self._state_file,
        )
