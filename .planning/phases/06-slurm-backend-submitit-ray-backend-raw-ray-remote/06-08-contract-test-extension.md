---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 08
type: execute
wave: 5
depends_on: ["06-01", "06-04", "06-05", "06-06"]
files_modified:
  - tests/backends/test_contract.py
autonomous: true
requirements: [BCK-05, BCK-06]

must_haves:
  truths:
    - "tests/backends/test_contract.py runs against ALL FOUR backends in CI: [local, mock_slurm, slurm (DebugExecutor), ray (local cluster)]."
    - "≥10 of the existing S-01..S-12 scenarios pass against SLURMBackend AND RayBackend (DebugExecutor + local cluster respectively)."
    - "LocalBackend skip-guard pattern updates from `if not hasattr(backend, '_poll_lag')` to `if isinstance(backend, LocalBackend)` so SLURM/Ray get exercised on scenarios that LocalBackend skips."
    - "Total contract-test execution count grows from current ~12-scenario × 2-backend (≤24 effective tests) to ≥36 (12 × 3 effective backends, MockSLURM still skipped on LocalBackend-only scenarios)."
    - "D-179 clause 1 satisfied: 'tests/backends/test_contract.py passes parametrised over [LocalBackend, MockSLURMBackend, SLURMBackend (DebugExecutor), RayBackend (local cluster)] — ≥10 scenarios per backend'."
  artifacts:
    - path: tests/backends/test_contract.py
      provides: "Skip-guard refactor + new BCK-05/06 contract scenario verifying signal directive + state-map coverage."
      contains: "isinstance(backend, LocalBackend)"
  key_links:
    - from: tests/backends/test_contract.py
      to: tests/backends/conftest.py
      via: parametrised backend fixture (params=['local','mock_slurm','slurm','ray'])
      pattern: "params=\\[.*slurm.*ray"
    - from: tests/backends/test_contract.py
      to: automil.backends.local.LocalBackend
      via: isinstance skip guard
      pattern: "isinstance\\(backend, LocalBackend\\)"
---

<objective>
Wave 5A — extend the existing parameterised contract test so SLURMBackend and RayBackend pass the same ≥12 scenarios that LocalBackend and MockSLURMBackend already do (D-179 clause 1). This plan is a NARROW extension of `tests/backends/test_contract.py`: skip-guard refactor + (optionally) one or two new scenarios that exercise SLURM/Ray-specific behavior (e.g., signal directive present, state-map coverage).

Purpose: the Phase 2 anti-acceptance criterion was "ABC must be designed against ≥2 implementations IN THE SAME PHASE". For Phase 6 the equivalent is: ≥4 implementations pass the same suite. This plan is the gate for D-179 clause 1.

Output: 1 file modified — `tests/backends/test_contract.py`. The conftest.py fixture extension was already done in plan 06-01 (Wave 0); this plan only updates the SCENARIO LOGIC to handle the four-backend parametrisation correctly.
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
@CLAUDE.md

# Files this plan modifies:
@tests/backends/test_contract.py

# Reference fixtures (already extended in plan 06-01):
@tests/backends/conftest.py

<interfaces>
<!-- Public surface created. The acceptance gate (plan 06-10) reads pytest output to verify D-179 clause 1. -->

After this plan, `uv run pytest tests/backends/test_contract.py -v` shows test names like:
  test_submit_poll_completed[local]      SKIPPED (LocalBackend skipped)
  test_submit_poll_completed[mock_slurm] PASSED
  test_submit_poll_completed[slurm]      PASSED  (DebugExecutor)
  test_submit_poll_completed[ray]        PASSED  (local cluster)

For each of the 12 scenarios. Total: 12 × 4 = 48 test rows; ≥30 PASSED + ≤18 SKIPPED (LocalBackend skips daemon-required scenarios per existing pattern).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Refactor skip guards from hasattr → isinstance(LocalBackend) and add SLURM/Ray-specific scenario assertions</name>
  <files>tests/backends/test_contract.py</files>
  <read_first>
    - tests/backends/test_contract.py (full file — every `pytest.skip` location uses the same `if not hasattr(backend, "_poll_lag")` guard; ~12-15 sites)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"tests/backends/test_contract.py" lines 813-833 — skip guard refactor instructions)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-174 — debug_in_process for SLURM, plain ray.init for Ray; D-179 clause 1)
    - tests/backends/conftest.py (the params list already extended in 06-01 — confirm `["local", "mock_slurm", "slurm", "ray"]`)
  </read_first>
  <behavior>
    - Test 1: `pytest tests/backends/test_contract.py -v` lists tests parametrised over all 4 backends.
    - Test 2: Scenarios that previously SKIPPED on LocalBackend (S-01 submit→COMPLETED, S-02 submit→CRASHED, S-03 submit→cancel→CANCELLED, S-07/S-08 log_iter) NOW PASS on SLURM (DebugExecutor) and Ray (local cluster).
    - Test 3: Scenarios that don't require dispatch (S-04 list_running empty, S-09 cancel timing, S-11 opaque_id differs per submit) PASS on all 4 backends.
    - Test 4: ≥30 passing test rows on the contract suite (12 scenarios × 3 dispatch-capable backends, with the LocalBackend skips remaining as-is).
    - Test 5: New scenario `test_slurm_signal_directive_set` (SLURM-only) — verifies submitit's effective parameters dict contains the framework-mandated `signal: "B:TERM@30"` (RESEARCH.md OQ-1 confirmation).
  </behavior>
  <action>
**Step A — Skip-guard refactor**: every `if not hasattr(backend, "_poll_lag"):` in the file (currently ~12-15 sites at lines ~62, 88, 110, etc.) needs replacement. The semantic question is "does this backend execute jobs against a live dispatcher?". MockSLURMBackend has `_poll_lag` and DOES execute (in-process). SLURMBackend with `cluster="debug"` and RayBackend with local cluster ALSO execute. LocalBackend (without a daemon running in the fixture) does NOT.

Add an import at the top of the file:
```python
from automil.backends.local import LocalBackend
```

Replace EVERY occurrence of:
```python
if not hasattr(backend, "_poll_lag"):
    pytest.skip("S-XX requires live daemon — LocalBackend skipped")
```

with:
```python
if isinstance(backend, LocalBackend):
    pytest.skip("S-XX requires live dispatcher — LocalBackend skipped (no daemon in fixture)")
```

The XX placeholder retains the existing scenario number from the surrounding code. Use a single sed/regex pass or hand-edit each site; do NOT change the skip message numbering or the surrounding scenario logic.

**Step B — Update assertion `handle.backend == "mock_slurm"`** in S-01: line ~71 currently asserts `handle.backend == "mock_slurm"`. With 4 backends, change to:
```python
assert handle.backend in {"mock_slurm", "slurm", "ray"}
# (plus the existing node_id and opaque_id assertions)
```
Search for any other backend-name-specific assertion and similarly broaden them to "non-local" sets.

**Step C — Add a SLURM-specific scenario** at the end of the file (NOT in the parametrised body — this is a SLURM-only test):
```python
# ---------------------------------------------------------------------------
# Phase 6 BCK-05: SLURM-specific signal directive verification
# ---------------------------------------------------------------------------

def test_slurm_signal_directive_set(tmp_path):
    """D-155 + RESEARCH.md OQ-1: signal=B:TERM@30 is wired via slurm_additional_parameters."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend

    automil_dir = tmp_path / "automil"
    (automil_dir / "orchestrator" / "running" / "slurm").mkdir(parents=True)
    config = {
        "backend": {"name": "slurm", "slurm": {
            "debug_in_process": True,
            "walltime_seconds": 600,
            "directives": {"partition": "p", "account": "a", "cpus_per_task": 1, "mem_gb": 4},
        }},
    }
    backend = SLURMBackend(automil_dir=automil_dir, config=config)
    # Inspect the executor's effective parameters dict; the exact attribute name
    # is submitit-version-dependent. We try multiple known attribute paths.
    params = (
        getattr(backend._executor, "_executor", None)
        and getattr(backend._executor._executor, "parameters", None)
    ) or getattr(backend._executor, "parameters", None) or {}
    additional = params.get("additional_parameters") or params.get("slurm_additional_parameters") or {}
    assert additional.get("signal") == "B:TERM@30", (
        f"signal directive not propagated to executor parameters; got {params!r}"
    )
```

**Step D — Add a state-map coverage scenario for SLURM** at the end of the file:
```python
def test_slurm_state_map_covers_phase4_terminal_states():
    """D-157: state map MUST include TIMEOUT (cap-fired) and FAILED (crash) and CANCELLED."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import _SLURM_STATE_MAP
    from automil.backends.base import JobState
    assert _SLURM_STATE_MAP["TIMEOUT"] == JobState.BUDGET_KILLED
    assert _SLURM_STATE_MAP["FAILED"] == JobState.CRASHED
    assert _SLURM_STATE_MAP["CANCELLED"] == JobState.CANCELLED
    assert _SLURM_STATE_MAP["COMPLETED"] == JobState.COMPLETED
```

**Step E — Add a Ray exception-map coverage scenario** at the end of the file:
```python
def test_ray_poll_catches_worker_crashed_error():
    """RESEARCH.md OQ-3 / D-164 corrected: poll() must catch WorkerCrashedError (force=True path)."""
    pytest.importorskip("ray")
    import inspect
    from automil.backends.ray import RayBackend
    src = inspect.getsource(RayBackend.poll)
    assert "WorkerCrashedError" in src, (
        "RayBackend.poll must catch ray.exceptions.WorkerCrashedError per RESEARCH.md OQ-3"
    )
    assert "TaskCancelledError" in src
    assert "RayTaskError" in src
```

DO NOT add new scenarios to the parametrised body that would break LocalBackend (the skip pattern handles this). DO NOT remove any existing scenarios.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_contract.py -x -v 2>&amp;1 | tail -50 &amp;&amp; uv run pytest tests/backends/test_contract.py 2>&amp;1 | grep -E "passed|skipped" | tail -2</automated>
  </verify>
  <done>
    `pytest tests/backends/test_contract.py` parametrises over 4 backends. ≥30 test rows pass (3 dispatch-capable backends × ≥10 scenarios). LocalBackend rows still SKIP on daemon-required scenarios (existing behavior preserved). New SLURM-specific tests `test_slurm_signal_directive_set` and `test_slurm_state_map_covers_phase4_terminal_states` pass when submitit installed (skip otherwise). New Ray-specific test `test_ray_poll_catches_worker_crashed_error` passes when ray installed (skip otherwise). Phase 5 baseline preserved.
  </done>
</task>

</tasks>

<verification>

```bash
# All 4 backends parametrised
uv run pytest tests/backends/test_contract.py -v 2>&1 | grep -E "\[(local|mock_slurm|slurm|ray)\]" | head -20

# ≥30 PASSED rows
uv run pytest tests/backends/test_contract.py 2>&1 | grep -E "^\d+ passed"

# Phase 5 baseline preserved
uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py
```

</verification>

<success_criteria>

- [ ] `tests/backends/test_contract.py` skip guard uses `isinstance(backend, LocalBackend)` (NOT `hasattr(backend, "_poll_lag")`).
- [ ] All ~12-15 skip-guard sites updated.
- [ ] Three new SLURM/Ray-specific tests added: `test_slurm_signal_directive_set`, `test_slurm_state_map_covers_phase4_terminal_states`, `test_ray_poll_catches_worker_crashed_error`.
- [ ] Pytest run reports ≥30 PASSED rows from the contract suite (when submitit + ray are installed; when absent, slurm/ray rows skip cleanly via importorskip in conftest).
- [ ] D-179 clause 1 satisfied: ≥10 scenarios pass per backend across [local skipped-where-expected, mock_slurm, slurm, ray].
- [ ] Phase 5 779-test baseline preserved.

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-08-SUMMARY.md` describing: skip-guard sites updated (count), new tests added (3), per-backend pass count from a verbose pytest run.
</output>
