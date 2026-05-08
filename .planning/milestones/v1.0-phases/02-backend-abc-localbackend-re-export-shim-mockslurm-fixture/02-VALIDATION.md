---
phase: 02
slug: backend-abc-localbackend-re-export-shim-mockslurm-fixture
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-02
tests_total: 420
tests_added: 0
gaps_resolved: 0
gaps_manual_only: 3
---

# Phase 2 — Validation Strategy

> Nyquist audit completed 2026-05-02. State B reconstruction from 02-CONTEXT.md (D-51..D-77), 02-VERIFICATION.md (5/5 success criteria, 6/6 REQ-IDs satisfied, 420 passed/9 skipped), and 8 PLAN+SUMMARY pairs. No gap-filler tests generated — all 6 requirements had live, passing, behaviorally adversarial test coverage before the audit began. See "Audit Findings" section for 5 edge cases explicitly probed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~21 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------|--------|
| 02-01 | 02-01 | 1 | BCK-01 | T-02-01-S01, T-02-01-S02, T-02-01-S04 | `JobHandle` frozen — `FrozenInstanceError` on mutation; `JobState(str,Enum)` JSON-safe without custom encoder; `Backend` ABC has exactly 5 abstract methods | unit | `uv run pytest tests/backends/test_contract.py::test_handle_frozen tests/backends/test_contract.py::test_state_json_roundtrip -v` | tests/backends/test_contract.py | green |
| 02-02 | 02-02 | 2 | BCK-01 | T-02-01-S02 | `BackendError` fires on non-Backend subclass AND duplicate registration; `_clear_backends()` empties registry; `BACKENDS` dict populated by `@register` decorator | unit | `uv run pytest tests/backends/test_registry.py -v` | tests/backends/test_registry.py | green |
| 02-03 | 02-03 | 1 | BCK-01, CLI-03, CLI-04 | T-02-08-S04 | `cli/submit.py` writes `metadata.backend` at submit time; defaults to `"local"`; no `opaque_id` in queue spec (daemon writes it on launch) | unit | `uv run pytest tests/test_submit_writes_metadata_backend.py -v` | tests/test_submit_writes_metadata_backend.py | green |
| 02-04 | 02-04 | 2 | BCK-02 | — | `from automil.orchestrator import ExperimentOrchestrator` resolves via shim; `ExperimentOrchestrator.__module__` is `automil.backends._orchestrator_daemon`; `DeprecationWarning` emitted; migration entry promoted in `compat.py` | unit | `uv run pytest tests/test_compat.py -v` | tests/test_compat.py | green |
| 02-05 | 02-05 | 3 | BCK-02 | T-02-08-S01 | `LocalBackend` registered as `"local"`; 394-test suite (now 420) stays green empty-diff from baseline; `list_running()` empty pre-submit; `cancel()` fire-and-forget < 1s; `opaque_id` unique (by `node_id`) | integration | `uv run pytest tests/backends/test_contract.py -k "local" -v` | tests/backends/test_contract.py | green |
| 02-06 | 02-06 | 3 | BCK-03 | — | `MockSLURMBackend` fixture; eventual-consistency lag observed (PENDING immediately after submit); restart recovery (fresh instance with `state_file` excludes completed job from `list_running()`); command stub: `--crash` → CRASHED, else COMPLETED | unit | `uv run pytest tests/backends/test_contract.py -k "mock_slurm" -v` | tests/backends/test_contract.py | green |
| 02-07 | 02-07 | 4 | BCK-01, BCK-03, BCK-04 | T-02-01-S03 | Contract test passes against BOTH backends (anti-acceptance gate); `scripts/check_backend_isolation.py` exits 0; pytest lint gate passes | integration | `uv run pytest tests/backends/test_contract.py tests/test_backend_isolation_lint.py -v` | tests/backends/test_contract.py + tests/test_backend_isolation_lint.py | green |
| 02-08 | 02-08 | 5 | CLI-03, CLI-04 | T-02-08-S01, T-02-08-S02, T-02-08-S03, T-02-08-S04, T-02-08-S05 | `automil cancel` dispatches through `BACKENDS[backend_name].cancel(handle)`; reads `opaque_id` from `running/<id>.json` (W-03 fix); polls up to `--timeout` for CANCELLED; `automil resubmit` generates NEW node_id; sets `metadata.resubmitted_from` | integration | `uv run pytest tests/test_cli_cancel_resubmit.py -v` | tests/test_cli_cancel_resubmit.py | green |

*Status: green · red · flaky*

---

## Nyquist Audit Findings (2026-05-02)

Adversarial stance applied: starting hypothesis was "implementation does not meet requirement." Five edge cases were explicitly probed before marking coverage complete.

### Edge Case 1: `BackendError` fires for BOTH duplicate registration AND non-Backend subclass

**Requirement:** BCK-01 — duplicate name raises `BackendError`; registering a non-`Backend` subclass raises `BackendError`. Both are distinct code paths in `backends/__init__.py::register()`.

**Test:** `tests/backends/test_registry.py::test_register_non_backend_raises` (match `"must subclass Backend"`) + `test_register_duplicate_raises` (match `"already registered"`).

**Probe result:** PASS. `test_register_non_backend_raises` confirms the registry stays clean after the failed registration — `"bad_backend" not in BACKENDS`. Both error paths are distinct and tested with explicit `pytest.raises(BackendError, match=...)` assertions.

### Edge Case 2: BCK-04 lint script actually exits 0 today

**Requirement:** `scripts/check_backend_isolation.py` must exit 0 on `src/automil/` — no `os.kill | Popen | .pid | os.killpg` outside the allowlist.

**Probe:** Re-ran `uv run python scripts/check_backend_isolation.py src/automil/` directly. Output: `OK: no backend isolation violations`. Exit code: 0. Also ran `uv run pytest tests/test_backend_isolation_lint.py -v` — PASSED.

**Probe result:** PASS. The `viz/server.py` addition to the allowlist (with rationale comment) correctly handles the `process.pid` reference in the WebSocket process-manager code, which is a legitimate local-process use.

### Edge Case 3: Contract test passes against BOTH backends — anti-acceptance criterion confirmed

**Requirement:** BCK-03 — ABC must be tested against ≥2 implementations in Phase 2 BEFORE locking. Specifically: MockSLURMBackend must pass all 13 scenarios; LocalBackend must pass ≥4 structural scenarios (with 9 execution-requiring scenarios correctly skipped by design).

**Probe:** `uv run pytest tests/backends/test_contract.py -v`. Confirmed: MockSLURMBackend — 13 PASSED; LocalBackend — 4 PASSED + 9 SKIPPED. The skip predicate `if not hasattr(backend, "_poll_lag")` identifies LocalBackend by structural attribute, not by name — robust to renaming. The 9 skipped scenarios all require a live orchestrator daemon (queue → running/ transition), which is a daemon responsibility outside unit-test scope.

**Probe result:** PASS. Anti-acceptance criterion cleared. The ABC's fire-and-forget cancel, eventually-consistent poll, and opaque_id model were explicitly shaped by MockSLURM's semantics, NOT frozen to LocalBackend's sync PID model.

### Edge Case 4: `automil cancel` correctly reads `opaque_id` from `running/<id>.json` (W-03 fix)

**Requirement:** CLI-03 — `cancel.py` must read `opaque_id` from `running/<node_id>.json`, not from graph metadata (D-76 / W-03 fix: daemon writes `opaque_id` at launch, not at submit time).

**Test:** `tests/test_cli_cancel_resubmit.py::test_cancel_missing_running_spec` — graph node is `status=running` but `running/<id>.json` is deliberately absent; asserts non-zero exit with `"no running spec"` in output.

**Probe result:** PASS. The test catches any regression where `cancel.py` might try to fall back to graph metadata for `opaque_id`. The error message path is confirmed by the passing test.

### Edge Case 5: `mock_slurm` NOT auto-imported — D-69 enforcement verified

**Requirement:** D-69 — `mock_slurm` must NOT be auto-registered in the public surface; `BACKENDS` after a bare `from automil.backends import BACKENDS` must contain only `['local']`. Only after `import automil.backends.mock_slurm` should `mock_slurm` appear.

**Probe:** `uv run python -c "from automil.backends import BACKENDS; print(list(BACKENDS.keys()))"` → `['local']`. Then `uv run python -c "from automil.backends import BACKENDS; import automil.backends.mock_slurm; print(list(BACKENDS.keys()))"` → `['local', 'mock_slurm']`.

**Probe result:** PASS. D-69 is structurally enforced: `backends/__init__.py` bottom-imports only `local`, never `mock_slurm`. A user who writes `backend.name: mock_slurm` in `config.yaml` without explicitly importing the module would get a `KeyError` — which is the intended UX trap prevention (test fixture should not leak into production config selection).

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No Wave 0 stub files were needed — Phase 2 was implemented before this Nyquist audit was written (State B reconstruction).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cross-process cancel for LocalBackend (live daemon + real PID SIGTERM) | CLI-03 (D-66 step 9) | Requires a live orchestrator daemon running a real subprocess; cross-process signal delivery cannot be exercised without a live process tree in CI | Start `automil orchestrator start`, submit a long-running experiment, then `automil cancel <node_id>` — verify SIGTERM sent, 30s grace, SIGKILL, `running/<id>.json` archived, graph `status=cancelled` |
| Real SLURM/Ray backend — Phase 6 (D-71) | BCK-03 | No SLURM cluster in CI; `submitit` integration out of scope for Phase 2 | Deferred to Phase 6 acceptance gate |
| Wall-clock budget enforcement — `BUDGET_KILLED` state transition (D-73) | BCK-01 (`JobState.BUDGET_KILLED` reserved) | Cap-layer orchestration is Phase 4 work; Phase 2 only reserves the `BUDGET_KILLED` enum value | Deferred to Phase 4 acceptance gate; `JobState.BUDGET_KILLED = "budget_killed"` is verified present via `test_state_json_roundtrip` |

---

## Validation Sign-Off

- [x] All 8 plans have automated verify command
- [x] Sampling continuity: no 3 consecutive plans without automated verify
- [x] Wave 0: not applicable (State B reconstruction — implementation preceded audit)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (full suite ~21s; incremental per-file <3s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-02

---

## Test File Inventory

Phase 2 net-new test files (26 tests, 6 files):

| File | Tests | REQ-IDs |
|------|-------|---------|
| `tests/backends/__init__.py` | 0 (package marker) | — |
| `tests/backends/conftest.py` | helpers only (wait_for_state, make_spec, backend fixture) | BCK-01, BCK-03 |
| `tests/backends/test_contract.py` | 19 passed + 9 skipped | BCK-01, BCK-03 |
| `tests/backends/test_registry.py` | 4 | BCK-01 |
| `tests/test_backend_isolation_lint.py` | 1 | BCK-04 |
| `tests/test_cli_cancel_resubmit.py` | 6 | CLI-03, CLI-04 |
| `tests/test_submit_writes_metadata_backend.py` | 3 | BCK-01, CLI-03, CLI-04 (D-76) |
| `tests/test_compat.py` | extended (Phase 0 baseline + Phase 2 migration entry) | BCK-02 |

Phase 0+1 baseline (394 tests, preserved):
`test_graph.py` · `test_runner.py` · `test_cli.py` · `test_integration.py` · `test_compat.py` · `test_recompute_best.py` · `test_orchestrator_*.py` · 18 Phase 1 registry/lifecycle files

**Total: 420 passed, 9 skipped** (`uv run pytest tests/ -q` — 20.87s)
