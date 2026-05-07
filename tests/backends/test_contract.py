"""Parameterised Backend ABC contract test — BCK-01, BCK-03, BCK-05, BCK-06, D-70.

This file locks the Backend ABC against all four implementations:
  LocalBackend, MockSLURMBackend, SLURMBackend (submitit DebugExecutor),
  and RayBackend (local cluster) — Phase 6 extension of Phase 2 anti-acceptance
  criterion: "ABC must be designed against >=2 implementations IN THE SAME PHASE".

Scenarios S-01..S-12 from RESEARCH.md section 3 / D-70 point 1:
  S-01  submit -> poll -> COMPLETED
  S-02  submit -> poll -> CRASHED (--crash command)
  S-03  submit -> cancel mid-run -> CANCELLED (cancel returns None)
  S-04  list_running empty before any submit
  S-05  submit 2 jobs -> list_running has 2 handles
  S-06  job completes -> list_running excludes it
  S-07  log_iter on COMPLETED job yields >=1 line
  S-08  log_iter closes (iterator exhausts, no infinite hang)
  S-09  cancel() returns in <1.0s (fire-and-forget timing)
  S-10  eventual-consistency lag observed (MockSLURM only)
  S-11  opaque_id differs per submit
  S-12  restart recovery -- fresh instance sees completed job as not running

Additional unit tests (not backend-parameterised):
  test_handle_frozen         -- frozen dataclass mutation raises FrozenInstanceError
  test_state_json_roundtrip  -- JobState is JSON-serialisable and round-trippable

Phase 6 BCK-05/BCK-06 specific tests (not parameterised):
  test_slurm_signal_directive_set               -- D-155 signal=B:TERM@30 wired
  test_slurm_state_map_covers_phase4_terminal_states -- D-157 state map completeness
  test_ray_poll_catches_worker_crashed_error    -- RESEARCH.md OQ-3 / D-164

Requirements coverage:
  BCK-01: S-01..S-09, S-11, test_handle_frozen, test_state_json_roundtrip
  BCK-03: S-10, S-12
  BCK-04: see tests/test_backend_isolation_lint.py
  BCK-05: test_slurm_signal_directive_set, test_slurm_state_map_covers_phase4_terminal_states
  BCK-06: test_ray_poll_catches_worker_crashed_error

Note on LocalBackend execution scenarios (S-01..S-03, S-05..S-08):
  These require a live dispatcher to pick up and run submitted jobs.  Since no
  live daemon is running in the test fixture, these scenarios are skipped for
  LocalBackend via isinstance(backend, LocalBackend) check.  All structural
  scenarios (S-04, S-09, S-11) run on ALL backends.  SLURMBackend (DebugExecutor)
  and RayBackend (local cluster) run all execution scenarios when their extras
  are installed; they skip cleanly via pytest.importorskip in conftest when
  submitit/ray are absent.
"""
from __future__ import annotations

import dataclasses
import json
import time

import pytest

from automil.backends.base import HealthReport, JobHandle, JobState
from automil.backends.local import LocalBackend
from tests.backends.conftest import make_spec, wait_for_state

# Terminal states -- used throughout the test file.
_TERMINAL = {JobState.COMPLETED, JobState.CRASHED, JobState.CANCELLED, JobState.BUDGET_KILLED}


# ---------------------------------------------------------------------------
# S-01: submit -> poll -> COMPLETED
# ---------------------------------------------------------------------------


def test_submit_poll_completed(backend, tmp_path):
    """S-01: submit a normal job; poll until COMPLETED.

    MockSLURM: PENDING -> RUNNING -> COMPLETED via timer chain.
    SLURMBackend (DebugExecutor) + RayBackend (local cluster): run in-process.
    LocalBackend: skipped (requires live daemon -- no daemon in fixture).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-01 requires live dispatcher -- LocalBackend skipped (no daemon in fixture)"
        )

    spec = make_spec("node_s01", tmp_path, command=("echo", "hello"))
    handle = backend.submit(spec)

    # Structural: handle must have correct fields.
    assert handle.node_id == "node_s01"
    assert handle.backend in {"mock_slurm", "slurm", "ray"}
    assert handle.opaque_id  # non-empty
    assert handle.submitted_at <= time.time()

    final = wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=5.0)
    assert final == JobState.COMPLETED


# ---------------------------------------------------------------------------
# S-02: submit -> poll -> CRASHED (--crash command)
# ---------------------------------------------------------------------------


def test_submit_poll_crashed(backend, tmp_path, request):
    """S-02: submit with '--crash' in command; poll until CRASHED.

    MockSLURM interprets '--crash' as a simulated crash (D-63).
    SLURMBackend (DebugExecutor) + RayBackend: run an actual failing process.
    LocalBackend: skipped (requires live daemon -- no daemon in fixture).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-02 requires live dispatcher -- LocalBackend skipped (no daemon in fixture)"
        )

    spec = make_spec("node_s02", tmp_path, command=("echo", "--crash"))
    handle = backend.submit(spec)

    final = wait_for_state(backend, handle, {JobState.CRASHED}, timeout=5.0)
    assert final == JobState.CRASHED


# ---------------------------------------------------------------------------
# S-03: submit -> cancel mid-run -> CANCELLED
# ---------------------------------------------------------------------------


def test_cancel_mid_run(backend, tmp_path, request):
    """S-03: submit; cancel; poll until CANCELLED; cancel() returns None.

    MockSLURM: fire-and-forget -- sets cancel_requested flag; timer observes
    it on next tick and transitions to CANCELLED.
    SLURMBackend (DebugExecutor) + RayBackend: cancel dispatched job in-process.
    LocalBackend: skipped (requires live daemon -- no daemon in fixture).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-03 requires live dispatcher -- LocalBackend skipped (no daemon in fixture)"
        )

    spec = make_spec("node_s03", tmp_path, command=("sleep", "60"))
    handle = backend.submit(spec)

    # cancel() must return None immediately (D-57).
    result = backend.cancel(handle)
    assert result is None

    final = wait_for_state(backend, handle, {JobState.CANCELLED}, timeout=5.0)
    assert final == JobState.CANCELLED


# ---------------------------------------------------------------------------
# S-04: list_running empty before any submit
# ---------------------------------------------------------------------------


def test_list_running_pre_submit(backend, tmp_path):
    """S-04: list_running() returns [] before any submit.

    Verifies no stale state from fixture construction.
    Runs on BOTH backends.
    """
    running = backend.list_running()
    assert running == [], f"Expected empty list; got {running!r}"


# ---------------------------------------------------------------------------
# S-05: submit 2 jobs -> list_running has 2 handles
# ---------------------------------------------------------------------------


def test_list_running_two_jobs(backend, tmp_path, request):
    """S-05: submit 2 jobs; list_running includes both handles.

    MockSLURM: both remain PENDING during the poll_lag_seconds=0.05 window
    if we check immediately after submit.
    SLURMBackend (DebugExecutor) + RayBackend: jobs visible via list_running.
    LocalBackend: jobs are written to queue/; list_running scans running/ (not
    queue/) so this is skipped for LocalBackend (daemon hasn't moved them yet).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-05 requires jobs to reach running state -- LocalBackend skipped (no daemon in fixture)"
        )

    spec_a = make_spec("node_s05a", tmp_path, command=("sleep", "60"))
    spec_b = make_spec("node_s05b", tmp_path, command=("sleep", "60"))
    h_a = backend.submit(spec_a)
    h_b = backend.submit(spec_b)

    # Jobs are PENDING immediately after submit -- list_running includes PENDING + RUNNING.
    running = backend.list_running()
    node_ids = {h.node_id for h in running}
    assert "node_s05a" in node_ids, f"Expected node_s05a in {node_ids}"
    assert "node_s05b" in node_ids, f"Expected node_s05b in {node_ids}"
    assert len(running) >= 2, f"Expected >=2 running; got {len(running)}"

    # Cleanup: cancel to avoid lingering timers.
    backend.cancel(h_a)
    backend.cancel(h_b)


# ---------------------------------------------------------------------------
# S-06: job completes -> list_running excludes it
# ---------------------------------------------------------------------------


def test_list_running_post_terminal(backend, tmp_path, request):
    """S-06: after a job reaches terminal state, list_running no longer includes it.

    MockSLURM: job completes via timer; list_running then returns [].
    SLURMBackend (DebugExecutor) + RayBackend: job completes in-process.
    LocalBackend: skipped (requires live daemon -- no daemon in fixture).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-06 requires job completion -- LocalBackend skipped (no daemon in fixture)"
        )

    spec = make_spec("node_s06", tmp_path, command=("echo", "done"))
    handle = backend.submit(spec)

    wait_for_state(backend, handle, _TERMINAL, timeout=5.0)

    running = backend.list_running()
    node_ids = {h.node_id for h in running}
    assert "node_s06" not in node_ids, (
        f"node_s06 should not be in list_running after terminal; got {node_ids}"
    )


# ---------------------------------------------------------------------------
# S-07: log_iter on COMPLETED job yields >=1 line
# ---------------------------------------------------------------------------


def test_log_iter_on_completed_job(backend, tmp_path, request):
    """S-07: log_iter on a terminal job yields at least one log line.

    MockSLURM: collects log_buffer; yields all on terminal.
    SLURMBackend (DebugExecutor) + RayBackend: log file written by subprocess wrapper.
    LocalBackend: skipped (requires live daemon to write run.log -- no daemon in fixture).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-07 requires live dispatcher to produce log -- LocalBackend skipped (no daemon in fixture)"
        )

    spec = make_spec("node_s07", tmp_path, command=("echo", "hello"))
    handle = backend.submit(spec)
    wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=5.0)

    lines = list(backend.log_iter(handle))
    assert len(lines) >= 1, f"Expected >=1 log line; got {lines!r}"


# ---------------------------------------------------------------------------
# S-08: log_iter closes after terminal -- no infinite hang
# ---------------------------------------------------------------------------


def test_log_iter_closes_after_terminal(backend, tmp_path, request):
    """S-08: log_iter iterator exhausts after terminal; calling list() doesn't hang.

    Using list() with a short-lived job ensures the iterator closes.
    SLURMBackend (DebugExecutor) + RayBackend: verified in-process.
    LocalBackend: skipped (requires live daemon -- no daemon in fixture).
    """
    if isinstance(backend, LocalBackend):
        pytest.skip(
            "S-08 requires live dispatcher -- LocalBackend skipped (no daemon in fixture)"
        )

    spec = make_spec("node_s08", tmp_path, command=("echo", "hello"))
    handle = backend.submit(spec)
    wait_for_state(backend, handle, _TERMINAL, timeout=5.0)

    # list() exhausts the iterator; if log_iter is infinite this would hang.
    # The test runner's timeout provides the guard.
    lines = list(backend.log_iter(handle))
    assert isinstance(lines, list)  # iterator returned and was exhausted


# ---------------------------------------------------------------------------
# S-09: cancel() returns in < 1.0s (fire-and-forget)
# ---------------------------------------------------------------------------


def test_cancel_returns_immediately(backend, tmp_path):
    """S-09: cancel() returns within 1.0s -- fire-and-forget (D-57).

    This is the ONLY timing assertion in the contract test.  1.0s is loose
    enough to be non-flaky across slow CI environments.

    Runs on ALL backends.
    For LocalBackend: cancel() on a pending job just removes the queue file.
    For MockSLURM: cancel() sets a threading.Event flag and returns.
    For SLURMBackend + RayBackend: cancel() dispatches to executor and returns.
    """
    spec = make_spec("node_s09", tmp_path, command=("sleep", "60"))
    handle = backend.submit(spec)

    t0 = time.monotonic()
    result = backend.cancel(handle)
    elapsed = time.monotonic() - t0

    assert result is None, f"cancel() must return None; got {result!r}"
    assert elapsed < 1.0, f"cancel() took {elapsed:.3f}s; expected < 1.0s (fire-and-forget)"


# ---------------------------------------------------------------------------
# S-10: eventual-consistency lag -- PENDING observed before RUNNING (MockSLURM only)
# ---------------------------------------------------------------------------


def test_eventual_consistency_lag_mock_slurm_only(backend, tmp_path, request):
    """S-10: immediately after submit, poll returns PENDING (not RUNNING).

    This validates MockSLURM's eventual-consistency semantics: submit returns
    immediately with a PENDING handle; actual state transition happens after
    poll_lag_seconds (BCK-03 / D-62).

    MockSLURM only -- LocalBackend submit writes to queue/ and also returns
    PENDING (opaque_id="pending") but the semantic is different.
    """
    if not hasattr(backend, "_poll_lag"):
        pytest.skip("S-10: eventual-consistency lag is MockSLURM-only scenario")

    spec = make_spec("node_s10", tmp_path, command=("echo", "hello"))
    handle = backend.submit(spec)

    # Immediately after submit, before the timer fires, state must be PENDING.
    immediate_state = backend.poll(handle)
    assert immediate_state == JobState.PENDING, (
        f"Expected PENDING immediately after submit; got {immediate_state!r}"
    )

    # Wait for completion to verify state progression was observed.
    final = wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=5.0)
    assert final == JobState.COMPLETED


# ---------------------------------------------------------------------------
# S-11: opaque_id unique across submits
# ---------------------------------------------------------------------------


def test_opaque_id_unique(backend, tmp_path):
    """S-11: submit 3 jobs; all opaque_ids are distinct.

    Runs on ALL backends.
    LocalBackend: all 3 get opaque_id="pending" (queue-file model, D-77).
    The contract test relaxes S-11 for LocalBackend: uniqueness is guaranteed
    by node_id, not opaque_id, for the queue-file path.
    MockSLURM: each submit increments _counter -> distinct "1.0", "2.0", "3.0".
    SLURMBackend + RayBackend: each submit returns a distinct backend-assigned ID.
    """
    specs = [
        make_spec(f"node_s11_{i}", tmp_path, command=("echo", "x")) for i in range(3)
    ]
    handles = [backend.submit(s) for s in specs]

    # node_ids are always unique (they come from the spec).
    node_ids = [h.node_id for h in handles]
    assert len(set(node_ids)) == 3, f"node_ids not unique: {node_ids}"

    # Non-LocalBackend: opaque_ids must also be distinct (each dispatcher assigns a unique ID).
    if not isinstance(backend, LocalBackend):
        opaque_ids = [h.opaque_id for h in handles]
        assert len(set(opaque_ids)) == 3, f"opaque_ids not distinct: {opaque_ids}"

    # Cleanup.
    for h in handles:
        backend.cancel(h)


# ---------------------------------------------------------------------------
# S-12: restart recovery -- MockSLURM only
# ---------------------------------------------------------------------------


def test_restart_recovery_mock_slurm_only(backend, tmp_path, request):
    """S-12: fresh backend instance reads state_file; completed job not in list_running.

    After a job completes, instantiating a new MockSLURMBackend with the same
    state_file must NOT re-add the completed job to list_running.  Jobs that
    were RUNNING at restart are marked CRASHED (RESEARCH.md section 7).

    MockSLURM only (LocalBackend restart-recovery uses running/*.json files and
    is tested separately in test_registry.py).
    """
    if not hasattr(backend, "_poll_lag"):
        pytest.skip("S-12 state_file restart is MockSLURM-only scenario")

    state_file = tmp_path / "mock_state.json"
    # The fixture already constructed backend with state_file=tmp_path/mock_state.json.
    # Re-using the backend directly to run a job to completion.
    spec = make_spec("node_s12", tmp_path, command=("echo", "done"))
    handle = backend.submit(spec)
    wait_for_state(backend, handle, {JobState.COMPLETED}, timeout=5.0)

    assert state_file.exists(), "state_file should have been written"

    # Instantiate a fresh backend with the same state_file.
    from automil.backends.mock_slurm import MockSLURMBackend

    fresh = MockSLURMBackend(poll_lag_seconds=0.05, state_file=state_file)
    running = fresh.list_running()
    node_ids = {h.node_id for h in running}
    assert "node_s12" not in node_ids, (
        f"Completed job node_s12 should not be in list_running on restart; "
        f"got {node_ids}"
    )


# ---------------------------------------------------------------------------
# S-extra: poll unknown handle raises BackendError
# ---------------------------------------------------------------------------


def test_poll_unknown_handle_raises(backend, tmp_path):
    """Poll on a fake handle (non-existent opaque_id) must raise an error.

    Runs on ALL backends.
    LocalBackend: raises BackendError.
    MockSLURM: raises ValueError (poll() raises ValueError for unknown job).
    """
    fake_handle = JobHandle(
        node_id="ghost_node",
        backend="mock_slurm",
        opaque_id="9999.0",
        submitted_at=time.time(),
    )
    with pytest.raises((Exception,)):  # BackendError or ValueError
        backend.poll(fake_handle)


# ---------------------------------------------------------------------------
# Non-parameterised unit tests (JobHandle + JobState invariants)
# ---------------------------------------------------------------------------


def test_handle_frozen():
    """BCK-01: JobHandle is a frozen dataclass -- mutation raises FrozenInstanceError."""
    handle = JobHandle(
        node_id="test_node",
        backend="mock_slurm",
        opaque_id="1.0",
        submitted_at=time.time(),
    )
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        handle.node_id = "mutated"  # type: ignore[misc]


def test_state_json_roundtrip():
    """BCK-01: JobState is JSON-serialisable (str Enum) and round-trips via json.

    json.dumps(JobState.RUNNING) must return '"running"' (D-53 /
    RESEARCH.md section 2 str-Enum rationale).
    """
    assert json.dumps(JobState.RUNNING) == '"running"'
    assert json.dumps(JobState.COMPLETED) == '"completed"'
    assert json.dumps(JobState.CRASHED) == '"crashed"'
    assert json.dumps(JobState.CANCELLED) == '"cancelled"'
    assert json.dumps(JobState.PENDING) == '"pending"'
    assert json.dumps(JobState.BUDGET_KILLED) == '"budget_killed"'

    # Round-trip: JSON string -> JobState enum.
    assert JobState("running") == JobState.RUNNING
    assert JobState(json.loads('"completed"')) == JobState.COMPLETED


# ---------------------------------------------------------------------------
# Phase 6 BCK-05: SLURM-specific signal directive verification
# ---------------------------------------------------------------------------


def test_slurm_signal_directive_set(tmp_path):
    """D-155 + RESEARCH.md OQ-1: signal=B:TERM@30 is wired via slurm_additional_parameters."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend  # noqa: PLC0415

    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "debug_in_process": True,
                "walltime_seconds": 600,
                "directives": {
                    "partition": "p",
                    "account": "a",
                    "cpus_per_task": 1,
                    "mem_gb": 4,
                },
            },
        },
    }
    backend = SLURMBackend(automil_dir=automil_dir, config=config)
    # Inspect the executor's effective parameters dict; the exact attribute name
    # is submitit-version-dependent. We try multiple known attribute paths.
    params = (
        getattr(backend._executor, "_executor", None)
        and getattr(backend._executor._executor, "parameters", None)
    ) or getattr(backend._executor, "parameters", None) or {}
    additional = (
        params.get("additional_parameters") or params.get("slurm_additional_parameters") or {}
    )
    assert additional.get("signal") == "B:TERM@30", (
        f"signal directive not propagated to executor parameters; got {params!r}"
    )


def test_slurm_state_map_covers_phase4_terminal_states():
    """D-157: state map MUST include TIMEOUT (cap-fired) and FAILED (crash) and CANCELLED."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import _SLURM_STATE_MAP  # noqa: PLC0415

    assert _SLURM_STATE_MAP["TIMEOUT"] == JobState.BUDGET_KILLED
    assert _SLURM_STATE_MAP["FAILED"] == JobState.CRASHED
    assert _SLURM_STATE_MAP["CANCELLED"] == JobState.CANCELLED
    assert _SLURM_STATE_MAP["COMPLETED"] == JobState.COMPLETED


# ---------------------------------------------------------------------------
# Phase 6 BCK-06: Ray-specific exception coverage verification
# ---------------------------------------------------------------------------


def test_ray_poll_catches_worker_crashed_error():
    """RESEARCH.md OQ-3 / D-164 corrected: poll() must catch WorkerCrashedError (force=True path)."""
    pytest.importorskip("ray")
    import inspect  # noqa: PLC0415

    from automil.backends.ray import RayBackend  # noqa: PLC0415

    src = inspect.getsource(RayBackend.poll)
    assert "WorkerCrashedError" in src, (
        "RayBackend.poll must catch ray.exceptions.WorkerCrashedError per RESEARCH.md OQ-3"
    )
    assert "TaskCancelledError" in src
    assert "RayTaskError" in src


# ---------------------------------------------------------------------------
# Phase 7 BCK-01: Backend.healthcheck contract (D-189 / STP-01)
# ---------------------------------------------------------------------------
# F-05 fix: PATTERNS.md prescribes a parametrised healthcheck contract case in
# this file (mirroring S-01..S-12). LocalBackend returns a HealthReport;
# distributed backends raise NotImplementedError with the locked D-189 message.


def test_healthcheck_returns_health_report(backend):
    """D-189 / STP-01: LocalBackend returns HealthReport; distributed backends defer.

    Parametrised across all 4 BCK-01 backends via the conftest `backend` fixture:
      - LocalBackend: returns HealthReport with frozen-dataclass fields per D-189.
      - MockSLURMBackend / SLURMBackend / RayBackend: raise NotImplementedError
        with the D-189 locked message.
    """
    locked_prefix = r"healthcheck deferred to Phase 7\+ for distributed backends"

    if isinstance(backend, LocalBackend):
        report = backend.healthcheck()
        assert isinstance(report, HealthReport), (
            f"LocalBackend.healthcheck() must return HealthReport; got {type(report).__name__}"
        )
        # Frozen-dataclass field shape per D-189 (must match the ABC contract).
        expected_fields = {
            "gpu_count", "gpu_vram_gb", "accelerator", "python_version",
            "automil_version", "detection_status", "detection_warnings", "detected_at",
        }
        assert set(report.__dataclass_fields__) == expected_fields, (
            f"HealthReport field shape drift: {set(report.__dataclass_fields__)} "
            f"vs expected {expected_fields}"
        )
        # Reasonableness on a fixture host (no real GPU; nvidia-smi may be absent).
        assert report.accelerator in {"cuda", "rocm", "cpu"}
        assert report.detection_status in {"ok", "partial", "failed"}
        assert isinstance(report.gpu_vram_gb, tuple)
        assert isinstance(report.detection_warnings, tuple)
        return

    # Distributed branch: SLURMBackend, RayBackend, or MockSLURMBackend.
    with pytest.raises(NotImplementedError, match=locked_prefix):
        backend.healthcheck()
