# Changelog

autoMIL — F2-readiness framework refactor

## 6.0.0 — Phase 6 SLURM + Ray backends (unreleased)

### BREAKING: Per-backend `running/` namespacing

`orchestrator/running/<id>.json` (flat) → `orchestrator/running/<backend>/<id>.json` (namespaced).

**Why:** Phase 6 introduces SLURMBackend and RayBackend (BCK-05, BCK-06). Each
backend owns its own running-spec directory so cross-backend operations cannot
corrupt each other (D-168, D-169). autoMIL 6.x does NOT auto-migrate flat layout
to namespaced layout (per CLAUDE.md "Avoid backwards-compatibility hacks").

**Operators upgrading from 5.x must:**

1. Run `automil orchestrator stop` and wait for in-flight runs to terminate.
2. Confirm `orchestrator/running/` contains zero `.json` files at the top level
   (subdirectories are fine):
   ```bash
   ls automil/orchestrator/running/*.json 2>/dev/null | wc -l
   # Expected: 0
   ```
3. Upgrade autoMIL.
4. Restart the daemon: `automil orchestrator start`.

**Daemon refusal to start:** if the daemon detects flat `running/*.json` at startup
without namespaced subdirectories, it exits with a `BREAKING CHANGE` message
listing the files found. This guardrail prevents a half-migrated state from
corrupting live runs.

### Verification

Phase 6 is complete when `uv run pytest tests/backends/test_phase6_acceptance.py -v`
reports all 11 D-179 clauses passing (or skipping cleanly when `[slurm]`/`[ray]`
extras absent). Each test maps to exactly one clause; partial failures localize
which clause regressed.

### Added

- `SLURMBackend` (`src/automil/backends/slurm.py`) — opt-in via `pip install -e '.[slurm]'`.
  Dispatches via submitit AutoExecutor; honors Phase 4 cap contract via `--signal=B:TERM@30`.
- `RayBackend` (`src/automil/backends/ray.py`) — opt-in via `pip install -e '.[ray]'`.
  Dispatches via raw `@ray.remote` (NOT Ray Tune); hybrid `RAY_ADDRESS` → local fallback.
- `BackendNotInstalledError`, `SlurmDirectivesIncompleteError`, `RayClusterUnreachableError`
  in `automil.backends.errors`.
- `automil check` validates `backend.slurm.directives` completeness (rejects `TODO_FILL_IN`)
  and Ray cluster reachability (advisory).
- Cross-backend log unification: `archive/<id>/run.log` is orchestrator-owned and
  drained from `backend.log_iter()` on terminal-state observation.
- pytest markers `requires_slurm` / `requires_ray` for nightly real-cluster tests.

### Compatibility

- `pip install -e .` (no extras) still works; submitit and ray are NOT pulled.
- `automil --help`, `automil submit`, `automil cancel`, `automil resubmit` work unchanged
  for `backend.name: local` configs.
- Phase 5 generalization gate, Phase 4 cap, Phase 3 trajectory recorder are unchanged.
