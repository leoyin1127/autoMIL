"""Backend ABC + JobHandle + JobSpec + JobState (BCK-01 / D-51..D-58).

Defines the five-method contract that every backend must implement.  Plans
02-05 (LocalBackend) and 02-06 (MockSLURMBackend) subclass `Backend` here.
Plan 02-07's parameterised contract test drives both implementations against
the invariants described in D-55..D-58.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    """Terminal / non-terminal job lifecycle states (D-53).

    String-valued so `json.dumps(JobState.RUNNING)` returns ``'"running"'``
    without a custom encoder.  Six values exhaust Phase 2; `BUDGET_KILLED` is
    reserved for Phase 4's two-tier cap (Phase 2 backends never produce it).
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CRASHED = "crashed"
    CANCELLED = "cancelled"
    BUDGET_KILLED = "budget_killed"


@dataclass(frozen=True)
class JobHandle:
    """Immutable reference to a submitted job (D-52).

    Carries no live process objects — backends look up rich state via
    `opaque_id`.  Frozen and hashable; safe to use as a dict key or set
    member.  JSON-serialisable via ``dataclasses.asdict(handle)``.
    """

    node_id: str
    """autoMIL graph node_id (framework-owned)."""

    backend: str
    """Backend name, e.g. ``"local"`` or ``"mock_slurm"``."""

    opaque_id: str
    """Backend-internal identifier (PID string for local, counter for MockSLURM)."""

    submitted_at: float
    """Unix epoch seconds at submit time."""


@dataclass(frozen=True)
class JobSpec:
    """Immutable input record passed to ``Backend.submit()`` (D-54).

    Frozen + tuple sequence fields so the spec is hashable and serialisable
    to ``running/<node_id>.json``.  ``gpu_estimate_gb`` is advisory — LocalBackend
    uses it for bin-packing; SLURM/Ray map it to their own ``--gpus`` directive.
    """

    node_id: str
    """autoMIL graph node_id for the experiment being submitted."""

    base_commit: str
    """Short SHA the worktree checks out before overlay application."""

    overlay_files: tuple[str, ...]
    """File paths under the overlay (relative to ``overlay_dir``)."""

    overlay_dir: Path
    """``archive/<node_id>/`` holding the overlay snapshot.  ``Path`` is
    hashable, so ``frozen=True`` is unaffected."""

    command: tuple[str, ...]
    """argv for the experiment process (e.g. ``("python", "train.py")``)."""

    env: tuple[tuple[str, str], ...]
    """Whitelisted env additions — ordered for determinism (D-54 / T-02-01-S01)."""

    working_subdir: str
    """Subdirectory of the worktree to ``chdir`` into before launch."""

    gpu_estimate_gb: float
    """Advisory GPU memory estimate in GB (for backend-side bin-packing)."""

    walltime_seconds: int
    """Framework wall-clock contract; backends may enforce or ignore."""

    metadata: tuple[tuple[str, str], ...] = ()
    """Arbitrary backend-agnostic metadata — passes through Backend.submit unchanged.

    Tuple-of-tuples (NOT dict) so the frozen dataclass stays hashable. Convert
    to dict via ``dict(spec.metadata)``. Default ``()`` = no metadata.

    Used by gate/evaluate.py (D-140) to stamp gate-eval flags::

        metadata=(
            ("gate_eval", "true"),
            ("held_out", "true"),
            ("gate_parent_node", "node_0212"),
            ("cell_id", "abc12345"),
            ("edge_type", "gate_eval"),
        )
    """


class Backend(ABC):
    """Abstract base class for autoMIL job backends (BCK-01 / D-51..D-58).

    All five methods are abstract; subclasses must implement them.  Phase 7
    will add an optional ``healthcheck()`` method.  Phase 2 ships `LocalBackend`
    (wrapping the existing orchestrator daemon) and `MockSLURMBackend` (fixture
    + docs example).
    """

    @abstractmethod
    def submit(self, spec: JobSpec) -> JobHandle:
        """Submit a job and return a handle immediately (D-55).

        Eventually-consistent: the handle may reflect ``pending`` for several
        poll cycles after submission.  Backends do NOT block on actual job start.
        Caller responsibility: poll until terminal state.
        """

    @abstractmethod
    def poll(self, handle: JobHandle) -> JobState:
        """Return a snapshot of the job's current state without blocking (D-56).

        Idempotent — calling ``poll`` does not advance the job.  May return
        ``pending`` for several cycles after ``submit`` on eventually-consistent
        backends (e.g. MockSLURM with default ``poll_lag_seconds=5.0``).
        """

    @abstractmethod
    def list_running(self) -> list[JobHandle]:
        """Return handles for all live (pending + running) jobs (D-59).

        Restart-safe: a fresh ``Backend()`` instance can recover the live set
        by reading on-disk state (LocalBackend reads ``running/<id>.json``;
        MockSLURM reads optional ``state_file``).
        """

    @abstractmethod
    def cancel(self, handle: JobHandle, signal: Optional[int] = None) -> None:
        """Request cancellation of a running job — fire-and-forget (D-57).

        Returns ``None`` immediately.  State transition to ``CANCELLED`` is
        observed via subsequent ``poll()`` calls, not from this return value.
        Default ``signal=None`` means "backend's standard cancel" (SIGTERM +
        grace for local; ``scancel`` for SLURM).
        """

    @abstractmethod
    def log_iter(self, handle: JobHandle) -> Iterator[str]:
        """Yield log lines as available; closes on terminal state (D-58).

        For ``pending | running`` states with no log content yet the iterator
        may block briefly but MUST surface lines within ~1s of appearance.
        LocalBackend tails the live log file; MockSLURM returns the full
        collected buffer once the job reaches a terminal state.
        """
