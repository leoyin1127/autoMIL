---
phase: 02
status: block
checked_at: 2026-05-02
checker: gsd-plan-checker
blockers: 5
warnings: 4
info: 3
---

# Phase 2 Plan Check — Iteration 1

## Verdict

BLOCK. The 8 plans are architecturally sound and cover all Phase 2 requirements, but five issues require revision before execution: the wave assignment for Plan 02-05 is structurally impossible (it is declared wave 2 but depends on plan 02-04 which is also wave 2), the dependency graph for 02-08 is missing 02-07, the RESEARCH.md Open Questions section is unresolved per Dimension 11, Plan 02-04's verification step will incorrectly fail on legitimate callers in cli/orchestrator.py and cli/check.py, and the BCK-04 lint script will exit 1 on first run because viz/server.py contains three unaccounted os.kill calls outside the allowlist with no remediation task in any plan.

---

## Goal Coverage

### SC-1: `Backend` ABC with five methods + `JobState` enum

**Owner:** Plan 02-01 (ABC + dataclasses), Plan 02-02 (registry).

SC-1 is fully covered. `base.py` defines all five abstract methods per D-55–D-58. `JobState` is a six-value `str`-Enum. `JobHandle` and `JobSpec` are frozen dataclasses. `from automil.backends import Backend, JobHandle, JobSpec, JobState` resolves after 02-01 lands. The method contract docstrings encode fire-and-forget, snapshot-not-blocking, eventually-consistent semantics.

**Status:** COVERED.

---

### SC-2: `LocalBackend` ships as re-export shim; existing 387-test suite passes with empty behavioural diff

**Owner:** Plan 02-04 (git mv + shim), Plan 02-05 (thin adapter).

Plan 02-04 renames orchestrator.py to `backends/_orchestrator_daemon.py` via `git mv` and creates the 5-line PEP 562 re-export shim. Plan 02-05 wraps `ExperimentOrchestrator` as `LocalBackend(Backend)`. The 387-test baseline is the verification criterion (RESEARCH.md §5 "Behavioral equivalence test"). Plans correctly identify that `LocalBackend.__init__` must not trigger `_recover_orphans`.

One structural issue (wave assignment) is noted under BLOCKERs but the semantic coverage of SC-2 is otherwise complete.

**Status:** COVERED (wave blocker noted separately).

---

### SC-3: `MockSLURMBackend` fixture; ABC tested against ≥2 implementations BEFORE locking

**Owner:** Plan 02-06 (MockSLURMBackend), Plan 02-07 (contract test).

Plan 02-06 implements the `threading.Timer` + `threading.Event` eventual-consistency fixture per D-62/D-63. Plan 02-07 implements ≥12 parameterised scenarios (S-01..S-12) against both `LocalBackend` and `MockSLURMBackend`. The "ABC locked only after contract test passes against both" anti-acceptance criterion (ROADMAP.md Phase 2 anti-acceptance note) is honoured by sequencing: 02-07 is Wave 3 (after both implementations land).

The parameterised fixture explicitly tests `poll_lag_seconds=0.05` to keep suite under 10s. Restart recovery scenario (`test_restart_recovery_mock_slurm_only`) covers RESEARCH.md §7 semantics.

**Status:** COVERED.

---

### SC-4: Lint blocks `os.kill | Popen | pid` references outside allowlist

**Owner:** Plan 02-07 (lint script + pytest gate).

The `scripts/check_backend_isolation.py` AST walker is designed per D-64 with the correct FORBIDDEN_NAMES/FORBIDDEN_OS_ATTRS sets and allowlist. The pytest gate (`test_no_process_control_outside_allowlist`) wraps it as always-on CI enforcement per D-65.

**Critical gap:** `viz/server.py` has 3 `os.kill(pid, ...)` calls at lines 235, 301, and 316. These are OUTSIDE the allowlist (`backends/local.py` and `backends/_orchestrator_daemon.py`). The lint script will exit 1 on first run. Plan 02-07 T-02-07-03 acknowledges "if violations found, fix them before committing" but provides no task to handle viz/server.py. This is a BLOCKER (see B-04).

**Status:** PARTIALLY COVERED — blocker on viz/server.py.

---

### SC-5: `automil cancel` + `automil resubmit` wired through `Backend.cancel/submit`

**Owner:** Plan 02-08, prereq Plan 02-03 (metadata.backend in queue spec).

Plan 02-03 extends `cli/submit.py` to write `metadata.backend` into the queue spec (D-76). Plan 02-08 implements `cancel.py` (D-66 steps 1–8) and `resubmit.py` (D-67 steps 1–7). Both use `_get_node_or_die` + "Refusing to X" ClickException format per PATTERNS.md §7. Both use lazy BACKENDS imports per PATTERNS.md §8.

Integration tests use MockSLURMBackend + synthetic graph fixture, satisfying D-70 point 5. Five test cases cover happy path + all error cases.

**Status:** COVERED (dependency gap 02-08 missing 02-07 noted under BLOCKERs).

---

## Requirement Coverage

| REQ | Description | Plan(s) | Tests | Status |
|-----|-------------|---------|-------|--------|
| BCK-01 | Backend ABC + 5 methods + JobState | 02-01, 02-02 | `test_submit_poll_completed[local/mock_slurm]`, `test_handle_frozen`, `test_state_json_roundtrip`, import smoke | COVERED |
| BCK-02 | LocalBackend re-export shim; 387 tests green | 02-04, 02-05 | `uv run pytest tests/ -x -q` (387 baseline), `test_submit_poll_completed[local]`, import-path compat check | COVERED |
| BCK-03 | MockSLURMBackend; validated against ≥2 impls | 02-06, 02-07 | `test_submit_poll_completed[mock_slurm]`, `test_eventual_consistency_lag_mock_slurm_only`, `test_restart_recovery_mock_slurm_only`, `test_cancel_mid_run[mock_slurm]` | COVERED |
| BCK-04 | AST lint blocks os.kill/Popen/.pid outside allowlist | 02-07 | `test_no_process_control_outside_allowlist`, `python scripts/check_backend_isolation.py` | BLOCKED (viz/server.py) |
| CLI-03 | `automil cancel <node_id>` via Backend.cancel | 02-03, 02-08 | `test_cancel_happy_path`, `test_cancel_unknown_node`, `test_cancel_terminal_node`, `test_cancel_timeout` | COVERED |
| CLI-04 | `automil resubmit <node_id>` via Backend.submit | 02-03, 02-08 | `test_resubmit_happy_path` | COVERED (only 1 test scenario vs D-67's multi-step workflow; WARNING noted) |

---

## Issues

### BLOCKERs (must fix before execution)

**B-01: [dependency_correctness] Plan 02-05 wave=2 is structurally impossible — it depends on 02-04 which is also wave 2**

- Plan: 02-05
- Details: 02-05 `depends_on: ["02-01", "02-02", "02-04"]`. Plan 02-04 is wave 2. By the wave rule `wave = max(deps_wave) + 1`, 02-05 must be wave 3 (max(1,1,2)+1=3), not wave 2. The frontmatter states `wave: 2` and `parallel_with: ["02-06"]`. This is self-contradictory: 02-05 cannot run in parallel with 02-06 (wave 2) because it depends on 02-04 (wave 2) completing first.
- Downstream impact: 02-07's wave assignment is also wrong. With corrected 02-05 at wave 3, 02-07 should be wave 4 (max(3,2)+1=4), not wave 3. The true wave structure is: Wave 1 (01,02,03), Wave 2 (04,06), Wave 3 (05), Wave 4 (07), Wave 5 (08).
- Fix: Set 02-05 `wave: 3`. Set 02-07 `wave: 4`. Set 02-08 `wave: 5`. Update `parallel_with` fields accordingly: 02-05 is NOT parallel with 02-06; 02-06 is parallel with 02-04 only.

---

**B-02: [dependency_correctness] Plan 02-08 missing `02-07` in `depends_on` — wave assignment has no backing**

- Plan: 02-08
- Details: 02-08 `depends_on: ["02-05", "02-06", "02-03"]` — plan 02-07 is omitted. Plan 02-07 is the contract test + lint gate, which is the Phase 2 acceptance condition (D-70). Running 02-08 (cancel/resubmit CLI) before 02-07 (lint enforcement) means cancel.py and resubmit.py could be committed before the BCK-04 isolation guarantee is verified. Additionally, 02-08 is labelled `wave: 4` but with the corrected wave structure (02-05 → wave 3, 02-07 → wave 4), 02-08 should be `wave: 5` and must list 02-07 in `depends_on`.
- Fix: Add `"02-07"` to 02-08's `depends_on`. Set `wave: 5`.

---

**B-03: [research_resolution] RESEARCH.md has unresolved Open Questions — not marked `(RESOLVED)`**

- File: `02-RESEARCH.md`
- Details: The file contains `## Open Questions` (no `(RESOLVED)` suffix) with two unresolved items: (1) "submit.py backward compat for cancel" — whether Phase 2 extends submit.py to go through `backend.submit()` or limits cancel to nodes submitted via the new path; (2) "LocalBackend.submit() uses queue-file path or direct `_launch` path?" The "Recommendation" in each entry points at an approach but these are not closed decisions with explicit RESOLVED markers. Per Dimension 11, an unresolved Open Questions section is a BLOCKER.
  
  Note: The plans themselves have chosen approaches (02-03 adds `metadata.backend` to queue spec; 02-05 uses the queue-file path per D-77), so these are de facto resolved — but the RESEARCH.md document is not updated to reflect this, which means the executor may see conflicting guidance.
- Fix: Mark the section `## Open Questions (RESOLVED)` and annotate each question with the resolution decision (e.g., "RESOLVED: Plan 02-03 writes `metadata.backend` to queue spec; cancel uses opaque_id from node.metadata; legacy nodes fall back to 'local'" and "RESOLVED: LocalBackend.submit() uses queue-file path per D-77").

---

**B-04: [requirement_coverage] BCK-04 lint script will exit 1 on first run — `viz/server.py` has 3 `os.kill` calls outside the allowlist; no plan remediates them**

- Plan: 02-07
- Details: `src/automil/viz/server.py` contains `os.kill(pid, 0)` at lines 235 and 301, and `os.kill(pid, signal.SIGTERM)` at line 316. The BCK-04 allowlist in `scripts/check_backend_isolation.py` only covers `backends/local.py` and `backends/_orchestrator_daemon.py`. Plan 02-07 T-02-07-03 acknowledges that pre-existing violations "must be fixed before committing" but no plan contains a task to fix `viz/server.py`. This means the executor either (a) encounters a mystery failure on first lint run and must improvise a fix, or (b) silently expands the allowlist to include viz/server.py, defeating the BCK-04 intent.
- Fix: Add a task to Plan 02-07 (or an earlier plan) to either: (a) move the `viz/server.py` PID-management logic to a helper function in `backends/local.py` (preferred — viz should delegate to the backend's stop logic), or (b) add `viz/server.py` to the allowlist with a comment explaining why it has legitimate process-control needs (simpler, acceptable if reviewed). The choice must be made explicit; it cannot be left as "fix if violations found."

---

**B-05: [task_completeness] Plan 02-04 T-02-04-04 verification step will falsely fail — grep expects zero callers but cli/orchestrator.py and cli/check.py are legitimate shim consumers**

- Plan: 02-04, Task T-02-04-04
- Details: The verification step states: `grep -r "from automil.orchestrator\|import automil.orchestrator" src/ --include="*.py" | grep -v "backends/_orchestrator_daemon\|orchestrator.py"` — "must return zero lines." However, the current codebase has 5 lines in `src/` importing from `automil.orchestrator`:
  - `src/automil/cli/orchestrator.py` lines 19, 29, 39: `from automil.orchestrator import ExperimentOrchestrator`
  - `src/automil/cli/check.py` lines 86, 97: `from automil.orchestrator import NVIDIA_SMI_PATH`, `from automil.orchestrator import (_SYSTEM_ENV_WHITELIST_LITERAL, ...)`
  
  These are VALID uses of the re-export shim (the shim is the whole point of keeping the old path working), not violations. But the grep filter only excludes the shim itself (`orchestrator.py`) and `_orchestrator_daemon`, not the legitimate callers. The verification step will produce 5 unexpected lines and confuse the executor into thinking the rename broke something.
- Fix: Change the T-02-04-04 verification step to a conceptually correct check. Either: (a) change the intent to "these callers are expected and acceptable — verify they still work" and add `python -c "from automil.cli.check import check"` as an import smoke; or (b) change the grep filter to exclude `src/automil/cli/` from the zero-callers assertion (incorrect intent) and instead note that cli/ callers are explicitly permitted consumers of the shim. The acceptance criterion "no internal code imports the old path" is factually wrong and must be updated.

---

### WARNINGs (advisory; consider before execution)

**W-01: [dependency_correctness] Wave 1 file conflict: 02-01 and 02-02 both write `backends/__init__.py` in the same wave**

- Plans: 02-01, 02-02
- Details: 02-01 creates `backends/__init__.py` as a placeholder; 02-02 rewrites it with BACKENDS registry content. The plan acknowledges this: "Plan 02-01 creates the file with the re-export surface; Plan 02-02 ADDS the registry content." The 02-02 task note says "Execution order within Wave 1 must be 02-01 first, then 02-02 extends the file." Within a parallel wave, execution order is not guaranteed. The plans note this but do not resolve it structurally.
- Fix: Either (a) move the `__init__.py` population into 02-01 (consolidate), or (b) mark 02-02 `depends_on: ["02-01"]` and assign it wave 2 (correct the wave assignment to reflect the sequential dependency). The current "soft ordering" note is insufficient for a parallel executor.

---

**W-02: [task_completeness] Plan 02-08's `resubmit` integration tests cover only the happy path; error cases from D-67 are under-tested**

- Plan: 02-08, Task T-02-08-05
- Details: The plan lists 5 integration tests but only 1 covers `resubmit`: `test_resubmit_happy_path`. D-67 specifies hard-fails for: (a) node not found, (b) node in non-terminal state (e.g., running). Neither case has a named test. The CLI-04 Nyquist row in the plan also only maps to `test_resubmit_happy_path`. Compare: cancel has 4 tests (happy + 3 error cases); resubmit has 1.
- Fix: Add `test_resubmit_unknown_node` (non-existent node_id → non-zero + "not found") and `test_resubmit_running_node` (running node → non-zero + "Refusing to resubmit") to the test list in T-02-08-05.

---

**W-03: [scope_reduction] RESEARCH.md §8 "Pitfall 5" identifies opaque_id not persisted at submit time, but Plan 02-03 only writes `metadata.backend` to `queue/<id>.json`, not to `graph.json`**

- Plans: 02-03, 02-08
- Details: D-76 says `metadata.backend` is written to `queue/<id>.json` at submit time (Plan 02-03). The `opaque_id` is written by the daemon to `running/<id>.json` when `_launch_experiment` returns. Plan 02-08's cancel.py reads `opaque_id` from `node.metadata.opaque_id` (i.e., from `graph.json`). But Plan 02-03 explicitly says: "Do NOT write `backend` to the `graph.json` node at submit time — only to the `queue/<id>.json` spec." 
  
  This creates a gap: `cancel.py` reads `node.metadata.opaque_id` from the graph, but neither Plan 02-03 nor any other plan includes a task for the daemon to write `opaque_id` back into `graph.json` at launch time. Plan 02-08's integration test sidesteps this by using a pre-populated synthetic `graph.json` fixture, but the production path (legacy submit → daemon launches → cancel) will hit `KeyError: 'opaque_id'` unless the daemon is extended.
  
  The Pitfall 5 handling in Plan 02-08 T-02-08-02 step 5 covers the case where `opaque_id` is None (legacy node), but does not address the case where a NEW node (submitted via cli/submit.py after Phase 2) also has no `opaque_id` in `graph.json` because the daemon-side write is not planned.
- Fix: Either (a) add a task to Plan 02-05 or 02-08 that extends `_orchestrator_daemon._launch_experiment` to write `opaque_id` (the PID as string) back into `graph.json` node metadata after launch, or (b) document explicitly in Plan 02-08 that `automil cancel` only works for nodes submitted via direct `backend.submit()` call (not via the legacy queue-file path), and add a test for this boundary.

---

**W-04: [pattern_compliance] Plan 02-07 contract test `test_cancel_returns_immediately` uses a timing assertion (< 0.5s) contradicting RESEARCH.md §3 "never assert timing"**

- Plan: 02-07, T-02-07-02
- Details: RESEARCH.md §3 explicitly states "Never assert `elapsed < X ms`. Assert state transitions, not timing. Timing assertions are the #1 source of CI flakiness in scheduler tests." Yet the contract test plan includes: `test_cancel_returns_immediately: measure time before/after cancel() → assert elapsed < 0.5 seconds`. This contradicts the research's own guidance and could produce flaky CI failures on a loaded machine (0.5s is still a hard wall-clock bound).
- Fix: Replace the timing assertion with a structural check: `assert cancel_result is None` (cancel returns None per D-57) and remove the elapsed-time assertion. If fire-and-forget semantics need verification, use `threading.Timer` mock to confirm the timer was NOT blocked. The 0.5s wall-clock check should be removed or changed to a very loose 30s timeout that would only fire on genuine hangs.

---

### INFO (observations, no action required)

**I-01: [key_links_planned] Plan 02-02's `__init__.py` auto-import TODO placeholder is a soft ordering requirement that should be explicitly documented in executor notes**

- Plans: 02-02, 02-05
- Details: Plan 02-02 leaves a comment `# TODO(Plan-02-05): from automil.backends import local as _local_backend` that Plan 02-05 activates. This is a documented intra-plan coupling. The executor should read 02-02's action note before 02-05 to understand the full file shape. No structural issue — just a note for executor awareness.

---

**I-02: [scope_sanity] Plan 02-07 is the highest-scope plan (4 files, 14+ tests, AST script) and carries the most execution risk; recommend a dedicated Wave 4 slot as per the corrected wave structure**

- Plan: 02-07
- Details: Plan 02-07 modifies 4 files (test_contract.py, check_backend_isolation.py, test_backend_isolation_lint.py, conftest.py), implements 14+ tests, and creates a non-trivial AST script. The RESEARCH.md §4 code skeleton is well-specified. This plan is within scope (under 5 tasks / 4 files within each task) but is the highest-risk execution target. The corrected wave structure (wave 4) gives it a clean dedicated slot after both backend implementations.

---

**I-03: [verification_derivation] Plan 02-06 MockSLURMBackend `log_iter` does not yield content while job is PENDING/RUNNING; this means `test_log_iter_on_completed_job` requires `wait_for_state` before calling `log_iter` — the test scenario should make this explicit**

- Plan: 02-07 test scenario `test_log_iter_on_completed_job`
- Details: D-58 / RESEARCH.md §6 specifies `log_iter` yields nothing while pending/running (SLURM model). The test name implies calling `log_iter` on a completed job, which requires first polling to terminal state. The test plan correctly uses `wait_for_state({COMPLETED})` before `list(log_iter(h))`, so this is correct by design — just worth noting for the executor so they don't accidentally test log_iter before the job completes.

---

## Recommendation

**REVISE.** Return to planner with the 5 BLOCKERs above. The fixes are mechanical:

1. **B-01** (wave assignment): correct 02-05 to wave 3, 02-07 to wave 4, 02-08 to wave 5; update `parallel_with` on 02-05 and 02-06.
2. **B-02** (02-08 missing dep): add `"02-07"` to 02-08 `depends_on`; set `wave: 5`.
3. **B-03** (Open Questions): mark `## Open Questions (RESOLVED)` in 02-RESEARCH.md with the two resolutions.
4. **B-04** (viz/server.py lint): add a task to Plan 02-07 (new T-02-07-00 or Wave 0 task) to handle the 3 `os.kill` calls in `viz/server.py` — either expand allowlist with rationale or migrate logic.
5. **B-05** (T-02-04-04 false-positive grep): correct the verification step to expect the 5 cli/ callers (they are valid shim consumers) and reframe the assertion.

WARNINGs W-01 (Wave 1 file conflict) and W-03 (opaque_id→graph.json gap) should also be addressed before execution — W-01 to prevent parallel-executor corruption and W-03 to prevent a production bug after Phase 2 ships.

