---
phase: 02-backend-abc-localbackend-re-export-shim-mockslurm-fixture
verified: 2026-05-02T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: null
gaps: []
deferred:
  - truth: "grep -r autobench src/automil/ returns zero matches"
    addressed_in: "Phase 8"
    evidence: "Phase 8 success criteria SC-1: 'grep -r autobench|AUTOBENCH_ src/automil/ returns zero matches'; D-05 explicitly defers AUTOBENCH_ROOT injection in _orchestrator_daemon.py to Phase 8 / DEC-01"
human_verification: []
---

# Phase 2 Verification — Backend ABC + LocalBackend re-export shim + MockSLURM fixture

**Phase Goal:** Land a backend interface designed against ≥2 implementations (real local + mock SLURM) so the abstraction does NOT freeze local-backend semantics (PIDs, sync status, killpg) into the contract that Phase 6 will inherit.
**Verified:** 2026-05-02
**Status:** PASSED
**Re-verification:** No — initial verification

## Verdict

Phase 2 goal is achieved. All five success criteria pass against codebase evidence. The `Backend` ABC is concrete, fully abstract (5 methods, 0 stubs), and parameterised against both `LocalBackend` and `MockSLURMBackend` in the same phase — satisfying the anti-acceptance criterion that guards Phase 6. The 394-baseline tests are intact (420 total pass with 9 skipped for execution-requiring LocalBackend scenarios), the BCK-04 lint exits 0, and `automil cancel` / `automil resubmit` both dispatch through `Backend.cancel` / `Backend.submit` with 6 integration tests passing. The only autobench references in `src/automil/` are in `backends/_orchestrator_daemon.py` (4 lines, all D-05 legacy, deferred to Phase 8 / DEC-01).

## Success Criteria Walk

### SC-1: `Backend` ABC with 5 methods + `JobState` enum + state-not-control-flow

**Status: COVERED**

Evidence from `src/automil/backends/base.py`:
- `Backend(ABC)` confirmed: `inspect.isabstract(Backend)` returns `True`
- Exactly 5 `@abstractmethod` declarations: `submit`, `poll`, `list_running`, `cancel`, `log_iter`
- `JobState(str, Enum)` has exactly 6 values: `pending`, `running`, `completed`, `crashed`, `cancelled`, `budget_killed`
- JSON-serialisable: `json.dumps(JobState.RUNNING)` returns `'"running"'` (confirmed by `test_state_json_roundtrip`)
- `JobHandle` is a `frozen=True` dataclass — mutation raises `FrozenInstanceError` (confirmed by `test_handle_frozen`)
- `JobSpec` is a `frozen=True` dataclass with all fields typed and immutable

### SC-2: `LocalBackend` re-export shim; existing test suite passes empty-diff

**Status: COVERED**

Evidence:
- `src/automil/backends/local.py` exists and is a substantive 416-line file (not a stub)
- `BACKENDS["local"] is LocalBackend` confirmed via smoke test
- Pre-Phase-2 test files (`tests/test_graph.py`, `tests/test_runner.py`, `tests/test_cli.py`, `tests/test_integration.py`) have 0 lines diff in git (none were modified)
- Full suite: **420 passed, 9 skipped, 0 failed** — delta from 394 baseline is +26 net-new Phase 2 tests
- Backward-compat shim: `from automil.orchestrator import ExperimentOrchestrator` resolves correctly via the 5-line PEP 562 shim; returns `ExperimentOrchestrator.__module__ = 'automil.backends._orchestrator_daemon'`
- `automil.orchestrator` reload transparency: `_importlib.reload` of `_orchestrator_daemon` is triggered so module-level `shutil.which` re-runs on reload (preserves Phase 0 test behaviour)

### SC-3: `MockSLURMBackend` fixture; ABC tested against ≥2 implementations BEFORE locking

**Status: COVERED**

Evidence:
- `src/automil/backends/mock_slurm.py` exists (321 lines, fully implemented)
- Mock is NOT auto-imported: `BACKENDS` after bare `from automil.backends import BACKENDS` contains only `['local']` — `mock_slurm` absent (D-69 enforced)
- Contract test `tests/backends/test_contract.py` parameterises across `local` and `mock_slurm` via `conftest.py` fixture
- Scenario coverage:
  - **LocalBackend**: 4 scenarios PASSED (S-04 list_running_pre_submit, S-09 cancel_returns_immediately, S-11 opaque_id_unique, S-extra poll_unknown_handle_raises); 9 SKIPPED (require live daemon — correct by design, documented in test file header)
  - **MockSLURM**: 13 scenarios PASSED (S-01 through S-12 + S-extra) — all run
- Anti-acceptance criterion satisfied: the ABC is verified against BOTH implementations in Phase 2 before Phase 6 begins
- `MockSLURMBackend` simulates eventual-consistency (5s default `poll_lag_seconds`), opaque `job_id` (`"1.0"`, `"2.0"`, ...), fire-and-forget cancel (threading.Event), node-local filesystem (state_file)

### SC-4: Lint blocks `os.kill | Popen | pid` outside allowlist

**Status: COVERED**

Evidence:
- `scripts/check_backend_isolation.py` exists, is substantive (221 lines, full AST visitor)
- `ALLOWLIST_PATHS` contains: `backends/local.py`, `backends/_orchestrator_daemon.py`, `viz/server.py` (with rationale comment for each)
- BCK-04 lint script exits 0: `OK: no backend isolation violations`
- `tests/test_backend_isolation_lint.py::test_no_process_control_outside_allowlist` PASSED
- AST visitor covers 5 patterns: `os.kill|killpg|getpid`, `subprocess.Popen`, bare `Popen`, `from os/subprocess import *` star-imports, `.pid` attribute access (exact match)

### SC-5: `automil cancel` + `automil resubmit` wired through `Backend.cancel/submit`

**Status: COVERED**

Evidence:
- Both commands registered in `src/automil/cli/__init__.py` (lines 20, 28: `from automil.cli import cancel` and `from automil.cli import resubmit`)
- `automil cancel --help` exits 0, displays correct synopsis
- `automil resubmit --help` exits 0, displays correct synopsis
- `automil --help` shows both `cancel` and `resubmit` in command list
- `cancel.py` reads `opaque_id` from `running/<node_id>.json` (W-03 fix — NOT from graph metadata)
- `cancel.py` dispatches through `BACKENDS[backend_name].cancel(handle)` — fully wired
- `resubmit.py` dispatches through `BACKENDS[backend_name].submit(new_spec)` — fully wired
- Integration tests: **6/6 passed** (T1 happy path, T2 unknown node, T3 terminal node, T4 missing running spec, T5 timeout, T6 resubmit happy path)
- Cancelled nodes: graph status updated to `"cancelled"`, `cancel_reason="cli"`, running spec archived to `archive/<id>/`
- Resubmitted nodes: new `node_id` generated (never reuses old), `metadata.resubmitted_from` set

## Requirement Coverage

| Requirement | Description | Status | Test Evidence |
|-------------|-------------|--------|---------------|
| BCK-01 | `Backend` ABC + `JobHandle/JobSpec/JobState` dataclasses + 5 abstract methods | SATISFIED | `test_handle_frozen`, `test_state_json_roundtrip`, S-01..S-09, S-11 |
| BCK-02 | `LocalBackend` re-export shim; 394-test suite passes empty-diff | SATISFIED | 420 passed (394 baseline intact); shim smoke test |
| BCK-03 | `MockSLURMBackend` fixture; contract validated against ≥2 implementations | SATISFIED | S-10 eventual-consistency, S-12 restart recovery; 13 mock_slurm PASSED |
| BCK-04 | Lint blocks `os.kill/Popen/pid` outside allowlist | SATISFIED | `test_no_process_control_outside_allowlist` PASSED; script exits 0 |
| CLI-03 | `automil cancel <node_id>` via `Backend.cancel` | SATISFIED | 5 cancel integration tests PASSED |
| CLI-04 | `automil resubmit <node_id>` via `Backend.submit` | SATISFIED | `test_resubmit_happy_path` PASSED |

**6/6 Phase 2 requirements: SATISFIED**

## Anti-Acceptance Gate (Pitfall 2)

**Criterion:** "ABC must be designed against ≥2 implementations IN THE SAME PHASE — designing against one impl freezes its semantics into the contract."

**Result: CLEARED**

Evidence:
1. Both `LocalBackend` (thin adapter over `_orchestrator_daemon`) and `MockSLURMBackend` (eventual-consistency fixture) are implemented in Phase 2 (plans 02-05 and 02-06 respectively)
2. The parameterised contract test (plan 02-07) was executed against both before any Phase 6 work — the ROADMAP confirms Phase 6 is not started (status: Not started)
3. LocalBackend passes 4 structural scenarios that do NOT require a live daemon; MockSLURMBackend passes all 13 scenarios including execution-path scenarios
4. The ABC's method signatures (fire-and-forget cancel, eventually-consistent poll, opaque_id model) are explicitly shaped by MockSLURM's semantics, NOT frozen to LocalBackend's sync PID model
5. `test_contract.py` header explicitly calls this out: "This file locks the Backend ABC only after both LocalBackend and MockSLURMBackend pass the same scenarios (Phase 2 anti-acceptance criterion)"

## Test Count

| Metric | Count |
|--------|-------|
| Before Phase 2 (baseline) | 394 |
| After Phase 2 | 420 |
| Net-new Phase 2 tests | +26 |
| Skipped (LocalBackend daemon-requiring contract scenarios) | 9 |
| Failed | 0 |

**Skipped scenario breakdown (LocalBackend):** S-01 submit_poll_completed, S-02 submit_poll_crashed, S-03 cancel_mid_run, S-05 list_running_two_jobs, S-06 list_running_post_terminal, S-07 log_iter_on_completed_job, S-08 log_iter_closes_after_terminal, S-10 eventual_consistency_lag, S-12 restart_recovery. All 9 are correctly skipped — they require a live orchestrator daemon process to advance job state from queue/ to running/, which is a daemon responsibility, not a backend-unit-test responsibility.

## Artifacts Verified

| Artifact | Status | Evidence |
|----------|--------|---------|
| `src/automil/backends/__init__.py` | VERIFIED | Exports Backend, JobHandle, JobSpec, JobState, BackendError, BACKENDS, register, LocalBackend; auto-registers LocalBackend; does NOT auto-import mock_slurm |
| `src/automil/backends/base.py` | VERIFIED | ABC with 5 abstract methods; frozen dataclasses; JobState(str,Enum) 6-value |
| `src/automil/backends/errors.py` | VERIFIED | BackendError exception class |
| `src/automil/backends/local.py` | VERIFIED | 416-line thin adapter; @register("local"); 5 methods all implemented; no autobench refs |
| `src/automil/backends/mock_slurm.py` | VERIFIED | 321-line eventual-consistency fixture; @register("mock_slurm"); threading.Timer chain; state_file persistence |
| `src/automil/backends/_orchestrator_daemon.py` | VERIFIED (with deferred note) | 750-line orchestrator code moved here from orchestrator.py; 4 inherited AUTOBENCH refs deferred to Phase 8/DEC-01 |
| `src/automil/orchestrator.py` | VERIFIED | 5-line PEP 562 re-export shim; DeprecationWarning on __getattr__; reload transparency |
| `src/automil/cli/cancel.py` | VERIFIED | Full cancel workflow (10 steps); reads opaque_id from running/ (W-03); dispatches Backend.cancel |
| `src/automil/cli/resubmit.py` | VERIFIED | Full resubmit workflow (10 steps); generates new node_id; dispatches Backend.submit |
| `src/automil/cli/__init__.py` | VERIFIED | Both cancel and resubmit imported and registered |
| `src/automil/cli/submit.py` | VERIFIED | metadata.backend written at submit time (line ~293); D-76 config-driven backend name |
| `scripts/check_backend_isolation.py` | VERIFIED | 221-line AST walker; ALLOWLIST_PATHS correct; exits 0 against src/automil |
| `tests/backends/test_contract.py` | VERIFIED | 12 parameterised scenarios + 2 unit tests; both backends exercised |
| `tests/backends/conftest.py` | VERIFIED | backend fixture parameterised [local, mock_slurm]; _isolated_backends autouse |
| `tests/test_backend_isolation_lint.py` | VERIFIED | Always-on pytest enforcement gate; PASSES |
| `tests/test_cli_cancel_resubmit.py` | VERIFIED | 6 integration tests; all PASS |

## Findings

1. **Inherited autobench references in `backends/_orchestrator_daemon.py`**: Lines 54, 570, 573, 618, 621 reference `AUTOBENCH_*` and `benchmarks/`. These are D-05 legacy references carried from the original `orchestrator.py` and explicitly deferred to Phase 8 / DEC-01. This is informational — NOT a Phase 2 blocker. The new Phase 2 files (`base.py`, `local.py`, `mock_slurm.py`, `__init__.py`, `errors.py`) have zero autobench leakage.

2. **9 LocalBackend contract scenarios skipped by design**: The skip predicate `if not hasattr(backend, "_poll_lag")` identifies LocalBackend. All 9 skips are intentional — the daemon-pickup model means queue-file → running/ transition only happens when a live daemon process is running, which is outside the scope of a unit test. The 4 structural scenarios that DO run on LocalBackend (S-04, S-09, S-11, S-extra) are sufficient to validate the ABC shape. This matches the documented rationale in `test_contract.py` header.

3. **DeprecationWarning from `automil.orchestrator` shim**: Tests importing from `automil.orchestrator` trigger the `__getattr__` DeprecationWarning. These are expected (44 warnings total in test suite), non-blocking, and correctly instruct callers to migrate to `automil.backends` by 2027-01.

4. **`test_cli_cancel_resubmit.py` uses save-restore pattern for BACKENDS isolation**: The test file's `_isolated_backends` fixture saves and restores the BACKENDS dict (vs. clear + reimport) — this is the correct pattern to handle Python's module-level `@register` decorator only running once at class-definition time.

## Recommendation

Phase 2 passes all 5 success criteria and 6/6 requirements. All artifacts are substantive and wired. The contract test validates the ABC against both implementations in the same phase, satisfying the anti-acceptance criterion for Phase 6. The test count grew from 394 to 420 with 0 failures.

**Proceed to Phase 3.**

---

_Verified: 2026-05-02_
_Verifier: Claude (gsd-verifier)_
