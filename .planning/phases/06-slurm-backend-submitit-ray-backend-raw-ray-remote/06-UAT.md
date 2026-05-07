---
status: complete
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
source:
  - 06-01-SUMMARY.md
  - 06-02-SUMMARY.md
  - 06-03-SUMMARY.md
  - 06-04-SUMMARY.md
  - 06-05-SUMMARY.md
  - 06-06-SUMMARY.md
  - 06-07-SUMMARY.md
  - 06-08-SUMMARY.md
  - 06-09-SUMMARY.md
  - 06-10-SUMMARY.md
started: "2026-05-07T00:00:00Z"
updated: "2026-05-07T00:30:00Z"
verifier: autonomous (Auto mode — bash-verifiable surfaces only)
---

## Current Test
<!-- All 20 tests complete; nothing pending -->

## Tests

### 1. CLI surface: automil --help works
**Expected:** exit 0 + lists Commands
**Result:** PASS — rc=0, has-Commands=True

### 2. Base install (no extras): import automil works
**Expected:** import succeeds
**Result:** PASS — rc=0, stdout=ok

### 3. Extras gating: BACKENDS['slurm'] absent without extras
**Expected:** BACKENDS dict doesn't contain 'slurm' key when [slurm] extra not installed; module itself imports cleanly (guarded design — see 06-04 SUMMARY Rule-3 deviation)
**Result:** PASS — BACKENDS['slurm']-absent=True, slurm.py-imports=True

### 4. Extras gating: ray.py import raises without extras
**Expected:** ImportError raised; extras-not-installed
**Result:** PASS — rc=1, stderr-tail: ModuleNotFoundError: No module named 'ray'

### 5. Typed errors: 3 new classes importable
**Expected:** from automil.backends.errors import ... succeeds
**Result:** PASS — rc=0, stdout=ok

### 6. Config template: backend: block present
**Expected:** config.yaml.j2 has top-level 'backend:' block
**Result:** PASS — backend-block: True

### 7. Config template: TODO_FILL_IN sentinels for cluster-specific directives
**Expected:** TODO_FILL_IN literal appears in slurm.directives section
**Result:** PASS — todo-sentinels: True

### 8. Config template: walltime_seconds=21600 (paper-campaign default)
**Expected:** walltime_seconds: 21600 line present (Leo's autoMIL-paper default)
**Result:** PASS — walltime: True

### 9. Config template: signal directive NOT in template (framework-mandated)
**Expected:** no 'signal:' yaml key (--signal=B:TERM@30 is framework-mandated)
**Result:** PASS — signal-key-present: False

### 10. CHANGELOG: 6.0.0 BREAKING entry + recovery instructions
**Expected:** CHANGELOG.md has '## 6.0.0', 'BREAKING', and 'automil orchestrator stop' recovery steps
**Result:** PASS — changelog-ok: True

### 11. pyproject: [slurm] extra registered
**Expected:** slurm = ["submitit>=1.5.3"] line in [project.optional-dependencies]
**Result:** PASS — slurm-extra: True

### 12. pyproject: [ray] extra registered
**Expected:** ray = ["ray>=2.55.1"] line in [project.optional-dependencies]
**Result:** PASS — ray-extra: True

### 13. pyproject: pytest markers requires_slurm + requires_ray registered
**Expected:** [tool.pytest.ini_options] markers contains both
**Result:** PASS — markers: True

### 14. BCK-04 lint clean (no process-control in slurm.py/ray.py)
**Expected:** scripts/check_backend_isolation.py exits 0
**Result:** PASS — rc=0

### 15. Framework purity: zero autobench refs in slurm.py + ray.py
**Expected:** grep returns 1 (no matches)
**Result:** PASS — rc=1, hits=

### 16. D-179 acceptance gate: 11 clauses (9 PASSED + 2 SKIPPED for extras)
**Expected:** 11 total clauses, 0 fail
**Result:** PASS — passed=9, skipped=2, rc=0

### 17. Contract test parametrised over [local, mock_slurm, slurm, ray]
**Expected:** test_contract.py collection includes all 4 backend params
**Result:** PASS — all-4-params: True

### 18. node_0176 smoke (local): composite within ±0.005 of 0.502
**Expected:** test_node_0176_smoke[local] PASSES
**Result:** PASS — rc=0, summary=1 passed

### 19. running/ namespace migration: 3 tests pass
**Expected:** test_running_namespace.py 3/3 pass (per-backend, daemon-refuses-flat, isolation)
**Result:** PASS — rc=0, passed=3

### 20. Phase 5 baseline preserved (779-test floor) excluding pre-existing tick_cells
**Expected:** ≥779 passing tests in non-tick_cells suite
**Result:** PASS — passed=793

## Summary

**20/20 tests PASS.** All Phase 6 user-observable surfaces verified:

- CLI surface intact (`automil --help` works post-Phase-6 changes)
- Base install (no extras) imports cleanly; `BACKENDS['slurm']` and `BACKENDS['ray']` registry keys absent without extras (D-179 clause 4 satisfied via the documented Rule-3 design deviation: slurm.py + ray.py modules guard `import submitit`/`import ray` with try/except so pure helpers like `_walltime_to_timeout_min` are testable without extras; conditional `@register("slurm")`/`@register("ray")` only fires when the import succeeds)
- 3 typed errors (`BackendNotInstalledError`, `SlurmDirectivesIncompleteError`, `RayClusterUnreachableError`) reachable from `automil.backends.errors`
- `config.yaml.j2` ships consumer-facing `backend:` block: `walltime_seconds: 21600` (paper-campaign default — Leo's autoMIL-paper memory `feedback_paper_campaign_vs_framework`), `TODO_FILL_IN` sentinels for cluster-specific directives (partition/account), no `signal:` key (framework-mandated `--signal=B:TERM@30` rejected if operator overrides per D-172)
- `CHANGELOG.md` 6.0.0 BREAKING entry with `automil orchestrator stop` recovery instructions for the `running/` namespace migration
- `pyproject.toml` `[slurm]` and `[ray]` extras registered in `[project.optional-dependencies]`; pytest markers `requires_slurm` and `requires_ray` registered in `[tool.pytest.ini_options]`
- BCK-04 process-control lint clean — zero `os.kill | Popen | .pid` references in slurm.py/ray.py (submitit + ray APIs sufficient)
- Framework purity preserved — zero `autobench`/`AUTOBENCH_`/`benchmarks/` references in slurm.py + ray.py
- D-179 11-clause acceptance gate green: 9 PASSED + 2 SKIPPED (clauses 5/6 skip cleanly when `[slurm]`/`[ray]` extras absent — correct gating behavior, not failure)
- Contract test parametrised over 4 backends (`[local, mock_slurm, slurm, ray]`); SLURM/Ray scenarios SKIP cleanly via `pytest.importorskip` when extras absent
- `node_0176`-equivalent acceptance smoke local-dispatch passes (composite within ±0.005 of 0.502 deterministic baseline per D-176)
- `running/<backend>/<id>.json` namespacing migration green (3/3 tests pass: per-backend dir resolution, daemon-refusal-to-start guardrail on flat layout, cross-backend namespace isolation)
- Phase 5 baseline preserved: 793 passing tests in non-tick_cells suite (baseline floor 779 exceeded by +14 from Phase 6 additions; the Wave 0 stub flips green and the conftest 4-param fixture add to passing count)

## Gaps

None at framework level. Phase 6 ships clean.

## Pre-existing failures (NOT Phase 6 regressions — deferred follow-ups)

Three failures in `tests/test_tick_cells.py` predate Phase 6:
- `test_tick_cells_active_to_refusing_new`
- `test_tick_cells_terminating_fires_cancel_with_cap_reason`
- `test_tick_cells_finalized_when_running_empty`

**Origin:** Phase 4 `_orchestrator_daemon.py:_tick_cells` — verified pre-existing via `git checkout cca0bc0 -- src/automil/backends/_orchestrator_daemon.py` bisection at start of Phase 6 session. The 3 failures existed at the Phase 5 completion baseline (`cca0bc0`) and persist through Phase 6's namespace-migration refactor (Wave 4 incidentally fixed 1 of 4, leaving 3). Not caused by any Phase 6 plan; not a regression introduced by this milestone.

**Recommended path forward:** Either (a) Phase 8 cleanup audit picks these up alongside the broader decoupling check, or (b) Leo runs `/gsd-debug tests/test_tick_cells.py` for a targeted root-cause-and-fix in a brief side-session.

## Real-cluster verification (deferred — not a UAT blocker)

Phase 6 success criterion #5 ("a SLURM-installed user runs CCRCC variant end-to-end via `pip install -e '.[slurm]'`") requires a real SLURM cluster. The framework-side test infrastructure ships behind `@pytest.mark.requires_slurm` / `@pytest.mark.requires_ray` markers (skip in CI; nightly only). Real-cluster verification is a Leo follow-up: install extras on a SLURM-equipped node + multi-node Ray cluster, run `tests/backends/test_contract_real_slurm.py` / `test_contract_real_ray.py` against real `cluster="slurm"` AutoExecutor + `RAY_ADDRESS=ray://head:10001`. Documented in CHANGELOG.md `### Verification` subsection.
