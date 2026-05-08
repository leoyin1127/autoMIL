# Phase 6: SLURM backend (submitit) + Ray backend (raw ray.remote) — Context

**Gathered:** 2026-05-06
**Status:** Ready for planning
**Mode:** Engineering decisions locked per production best practice (Leo 2026-05-06: "no need to discuss the engineering/coding level question with me, only feature and user level question needed. You may decide based on best practice and production level experiences"). Every decision below is a technical implementation choice; there are no open user/feature questions for Phase 6.

<domain>
## Phase Boundary

Land two **opt-in distributed backends** on top of the locked Phase 2 ABC so the framework runs identically on a single laptop, a SLURM HPC cluster, and a Ray cluster. Both honor the Phase 4 wall-clock cap contract.

After Phase 6:

1. **`SLURMBackend`** ships at `src/automil/backends/slurm.py` on top of `submitit>=1.5.3`. Opt-in via `pip install -e '.[slurm]'`. SLURM directives include framework-mandated `--time` (derived from cap budget) and `--signal=B:TERM@30` (matches Phase 4 D-115 cap-cancel-via-SIGTERM contract). Cluster-specific directives (`partition`, `account`, `qos`, `cpus-per-task`, `mem`, `gres`) come from `automil/config.yaml: backend.slurm.directives` — operator-supplied with `automil check` enforcing TODO-sentinel removal before run.
2. **`RayBackend`** ships at `src/automil/backends/ray.py` on top of `ray>=2.55.1`. Opt-in via `pip install -e '.[ray]'`. Uses raw `@ray.remote` (NOT `ray.tune`); init lifecycle is hybrid (try `ray.init(address="auto")` against `RAY_ADDRESS`, fall back to local `ray.init()` for laptop deploys). `ray.cancel(force=True)` honors the wall-clock contract.
3. **Shared parameterised contract test** at `tests/backends/test_contract.py` extends Phase 2's suite to cover `[LocalBackend, MockSLURMBackend, SLURMBackend, RayBackend]` (parametrised). SLURM runs via submitit's `DebugExecutor` (in-process); Ray runs via `ray.init(local_mode=True)` (single-process). Real-cluster tests gated behind `@pytest.mark.requires_slurm` / `@pytest.mark.requires_ray` (nightly / pre-release only, not CI).
4. **Per-backend `running/` namespacing.** `orchestrator/running/<backend>/<id>.json` replaces the flat `orchestrator/running/<id>.json` from Phases 0–5. Breaking change (per CLAUDE.md "Avoid backwards-compatibility hacks"); operators drain via `automil revert-baseline` before upgrading, documented in CHANGELOG.
5. **Cross-backend log unification.** `archive/<id>/run.log` is produced by the orchestrator (NOT the backend) on terminal-state observation: orchestrator drains `backend.log_iter(handle)` into the file via Phase 0 atomic-write pattern. Backends own log surface only via the iterator.
6. **CCRCC `node_0176`-equivalent variant runs end-to-end** on `SLURMBackend` (DebugExecutor) + `RayBackend` (local_mode) in CI; result.json composite within ±0.005 of LocalBackend baseline. This is the Phase 6 acceptance smoke.
7. **Framework purity preserved.** `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero. BCK-04 process-control lint extends to `slurm.py` + `ray.py` only if absolutely necessary (submitit/ray APIs should make this unnecessary; if either implementation needs `os.kill`/`Popen`/`.pid` we treat it as a code smell and refactor to use the library).

**Hard floors:**

- 779-test Phase 5 baseline stays green; new tests are additive.
- Contract test passes against ALL FOUR backends in CI via parameterisation.
- `pip install -e .` (no extras) installs without pulling submitit OR ray; `automil --help` works.
- `python scripts/check_backend_isolation.py` reports zero out-of-place process-control references in `src/automil/`.
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero.
- Acceptance smoke: `node_0176`-equivalent runs end-to-end on both backends (DebugExecutor + local_mode) with composite within ±0.005 of LocalBackend.

**Wave-cadence target:** ~9–11 plans across 6–7 waves. Granularity `fine`. Dependency shape:
extras + ABC re-exports → (SLURMBackend ‖ RayBackend skeletons) → (running/ namespacing) → (log unification) → (contract test extension) → (acceptance smoke + CHANGELOG).

</domain>

<decisions>
## Implementation Decisions

> **Numbering:** D-152 onward continues from Phase 5's D-135..D-151. Each decision is a locked engineering choice; downstream agents (researcher, planner, executor) honour these verbatim. Where a choice was framed as a "gray area" before bootstrap, the rationale block records why the locked option won — citing prior phase decisions, Leo's standing memories, and production patterns.

### Backend module layout (BCK-05, BCK-06)

- **D-152:** Two new modules under `src/automil/backends/`:
  ```
  src/automil/backends/
    slurm.py        # SLURMBackend on submitit>=1.5.3 (opt-in via [slurm] extra)
    ray.py          # RayBackend on ray>=2.55.1 (opt-in via [ray] extra)
  ```
  Both classes inherit `Backend` (D-51) and live alongside `local.py`, `mock_slurm.py`, `_orchestrator_daemon.py`. Neither auto-registers in `backends/__init__.py` — registration happens via guarded import (D-153).

- **D-153:** **Guarded import in `backends/__init__.py`** mirrors Phase 2 D-69's MockSLURM precedent for missing-extra handling:
  ```python
  # backends/__init__.py
  try:
      from . import slurm  # registers SLURMBackend via @Backend.register("slurm")
  except ImportError:
      pass  # [slurm] extra not installed; backend unavailable at runtime

  try:
      from . import ray  # registers RayBackend via @Backend.register("ray")
  except ImportError:
      pass  # [ray] extra not installed; backend unavailable at runtime
  ```
  When operator selects `backend.name: slurm` in config without `[slurm]` installed, runtime resolution raises a typed `BackendNotInstalledError` (extends `errors.py`) with operator-recovery hint: `pip install -e '.[slurm]'`.

### `pyproject.toml` extras (BCK-05, BCK-06 — opt-in installation)

- **D-154:** Two new extras alongside the existing `[ml]` group:
  ```toml
  [project.optional-dependencies]
  ml = [...]                               # unchanged
  slurm = ["submitit>=1.5.3"]              # BCK-05
  ray   = ["ray>=2.55.1"]                  # BCK-06
  ```
  No version pin tighter than the floor (production pattern; let consumers upgrade). Neither extra appears in `[project.dependencies]` or `[dependency-groups.dev]` — the contract is "framework runs without them; install only if backend selected".

### SLURMBackend implementation (BCK-05)

- **D-155:** **`SLURMBackend.__init__(automil_dir: Path, config: dict)`** constructs a `submitit.AutoExecutor` from `config["backend"]["slurm"]`:
  ```python
  self._executor = submitit.AutoExecutor(folder=automil_dir / "orchestrator" / "running" / "slurm" / "submitit-logs")
  self._executor.update_parameters(
      time=config["backend"]["slurm"]["directives"]["time"],
      signal="B:TERM@30",  # framework-mandated; matches Phase 4 D-115 cap-cancel contract
      slurm_partition=config["backend"]["slurm"]["directives"]["partition"],
      slurm_account=config["backend"]["slurm"]["directives"]["account"],
      slurm_qos=config["backend"]["slurm"]["directives"].get("qos"),
      cpus_per_task=config["backend"]["slurm"]["directives"]["cpus_per_task"],
      mem_gb=config["backend"]["slurm"]["directives"]["mem_gb"],
      gpus_per_node=config["backend"]["slurm"]["directives"].get("gpus_per_node", 1),
  )
  ```
  `time` and `signal` are framework-mandated (couple to cap contract); cluster-specific keys are operator-supplied via config and validated by `automil check`.

- **D-156:** **`submit(spec)`** uses submitit's function-execution model:
  ```python
  job = self._executor.submit(_run_experiment_subprocess, spec)
  handle = JobHandle(node_id=spec.node_id, backend="slurm", opaque_id=str(job.job_id), submitted_at=time.time())
  _persist_to_running(handle, spec, automil_dir / "orchestrator" / "running" / "slurm")
  return handle
  ```
  `_run_experiment_subprocess(spec)` is a top-level function that `chdir`s into the worktree, sets env from `spec.env`, and `subprocess.run(spec.command, ...)`. submitit pickles + dispatches; SLURM runs it on the allocated node. Inside the subprocess, the existing daemon-side launch path is reused (no SLURM-specific launch code in `_orchestrator_daemon.py`).

- **D-157:** **`poll(handle)` maps `submitit.Job.state` → `JobState`:**
  ```python
  job = submitit.Job(folder=submitit_logs_dir, job_id=handle.opaque_id)
  state_str = job.state  # "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | "TIMEOUT" | ...
  return _SLURM_STATE_MAP[state_str]
  ```
  `_SLURM_STATE_MAP`: `PENDING → PENDING`, `RUNNING → RUNNING`, `COMPLETED → COMPLETED`, `FAILED → CRASHED`, `CANCELLED → CANCELLED`, `TIMEOUT → BUDGET_KILLED` (cap fired), `OUT_OF_MEMORY → CRASHED`, plus a default `→ PENDING` for unknown states (with a one-time logged warning per backend instance).

- **D-158:** **`cancel(handle, signal=None)`** calls `submitit.Job.cancel()` (which calls `scancel`). The `signal` argument is honoured: when `signal=SIGTERM` (Phase 4 cap path), submitit's `--signal=B:TERM@30` directive guarantees SLURM emits SIGTERM 30s before time limit AND `scancel --signal=TERM` on explicit cancel. When `signal=None` (default), `scancel` (SIGKILL after grace) is used. Custom signals other than SIGTERM are accepted with a one-time-per-backend logged warning per Phase 2 D-57.

- **D-159:** **`log_iter(handle)`** tails `submitit_logs_dir/{job_id}_log.out` with `tail -f` semantics (backend yields line-at-a-time as lines appear). Closes when SLURM job state reaches terminal (`COMPLETED`/`FAILED`/`CANCELLED`/`TIMEOUT`/`OUT_OF_MEMORY`). Idle-yield with 1s tick to keep the iterator non-blocking from the framework's perspective.

- **D-160:** **`list_running()`** scans `automil_dir / "orchestrator" / "running" / "slurm" / "*.json"` and returns one `JobHandle` per persisted spec. Restart-safe (Phase 2 D-59 contract): a fresh `SLURMBackend` instance recovers the live set from disk, then `poll(handle)` re-validates each via SLURM's `sacct`. Stale handles (job no longer in SLURM) transition `PENDING|RUNNING → CRASHED` with `crash_reason: "lost-from-slurm"` recorded.

### RayBackend implementation (BCK-06)

- **D-161:** **`RayBackend.__init__(automil_dir: Path, config: dict)`** uses **hybrid init** (production pattern: try-existing-then-fallback-local):
  ```python
  if not ray.is_initialized():
      ray_address = os.environ.get("RAY_ADDRESS", "auto")
      try:
          ray.init(address=ray_address, ignore_reinit_error=True, log_to_driver=False)
      except ConnectionError:
          # No existing cluster; auto-init local for laptop / single-machine demos
          ray.init(ignore_reinit_error=True, log_to_driver=False)
  self._jobs: dict[str, ray.ObjectRef] = {}  # in-memory; persisted to running/ray/ for restart recovery
  ```
  Reasoning: matches FSDP/accelerate pattern. Operator with a multi-node Ray cluster sets `RAY_ADDRESS=ray://head:10001`; a laptop-only operator gets a local cluster on first submit. **No `ray.shutdown()`** in autoMIL — the daemon is long-lived and the cluster is operator-owned (autoMIL never tears down a cluster it didn't start; we track `_we_started_ray` and only shutdown on `RayBackend.close()` if we did the local init).

- **D-162:** **`submit(spec)`** wraps the existing daemon-side launch as a `@ray.remote` function:
  ```python
  @ray.remote(num_gpus=spec.gpu_estimate_gb / DEFAULT_GPU_VRAM_GB)
  def _run_experiment_ray(spec):
      # chdir into worktree, set env from spec.env, subprocess.run(spec.command)
      ...
  ref = _run_experiment_ray.remote(spec)
  handle = JobHandle(node_id=spec.node_id, backend="ray", opaque_id=ref.hex(), submitted_at=time.time())
  self._jobs[handle.opaque_id] = ref
  _persist_to_running(handle, spec, automil_dir / "orchestrator" / "running" / "ray")
  return handle
  ```
  `DEFAULT_GPU_VRAM_GB = 24.0` (config-overridable; matches `local.py`'s bin-packing assumption). `num_gpus` is fractional — Ray's GPU scheduler honours fractional reservations (e.g., 0.5 GPU = two actors share one card).

- **D-163:** **One actor per submit (NOT placement groups for multi-fold).** The 5-fold loop runs INSIDE the actor — matching LocalBackend + SLURMBackend semantics (one experiment process = one node = N folds INSIDE that process). Multi-fold placement groups would require cell-level coordination (Phase 4) to refactor; explicit deferral. Phase 6 contract: `JobSpec.gpu_estimate_gb` → `ray.remote(num_gpus=...)` for one actor.

- **D-164:** **`poll(handle)` is a non-blocking snapshot via `ray.wait`:**
  ```python
  ref = self._jobs.get(handle.opaque_id) or self._restore_ref_from_running(handle)
  ready, not_ready = ray.wait([ref], timeout=0)  # 0 = non-blocking
  if not_ready:
      return JobState.RUNNING  # Ray doesn't distinguish PENDING from RUNNING for actors; collapse both
  try:
      ray.get(ref, timeout=0)
      return JobState.COMPLETED
  except ray.exceptions.RayTaskError:
      return JobState.CRASHED
  except ray.exceptions.WorkerCrashedError:
      return JobState.CRASHED
  except ray.exceptions.TaskCancelledError:
      # Discriminate cap-kill vs operator-cancel via running/<id>.json metadata
      if _was_cap_cancel(handle, automil_dir):
          return JobState.BUDGET_KILLED
      return JobState.CANCELLED
  ```
  Ray collapses `PENDING|RUNNING → RUNNING` from the framework's perspective (Ray does have queued tasks but exposes no per-task pre-launch state to the SDK in 2.55+ outside of cluster-state APIs that we deliberately avoid for cross-version stability).

- **D-165:** **`cancel(handle, signal=None)`** calls `ray.cancel(ref, force=True, recursive=True)`. The `signal` argument is **ignored on Ray** (Ray doesn't expose Unix-signal granularity); a one-time-per-backend logged warning fires when called with a non-default signal. Phase 4's cap path passes `signal=SIGTERM`; Ray cancels with `force=True` which terminates the actor via SIGKILL after Ray's internal grace (~1s — shorter than SLURM's 30s). The framework-wide 30s grace on cap-fire is honored at the orchestrator level (D-115 owns the timing); `Backend.cancel` returns immediately per Phase 2 D-57.

- **D-166:** **`log_iter(handle)`** uses Ray's internal log routing. Approach: each `@ray.remote` function wrapper redirects its subprocess stdout/stderr to a per-actor file at `automil_dir / "orchestrator" / "running" / "ray" / f"{node_id}.log"` (the wrapper writes BEFORE invoking the user command). Backend tails that file with the same `tail -f` semantics as SLURM. Closes when actor ref reaches terminal state. Reasoning: avoids dependency on Ray's `ray.util.state.get_log` (which moved between 2.4 → 2.55+ and isn't a stable public API across the supported version range).

- **D-167:** **`list_running()`** scans `automil_dir / "orchestrator" / "running" / "ray" / "*.json"` and reconstructs handles. Restart-safe per Phase 2 D-59. **ObjectRef restoration limitation:** on a fresh process, `ObjectRef.hex()` cannot be re-hydrated into a live `ObjectRef` (Ray refs are process-local). On restart, persisted handles transition `PENDING|RUNNING → CRASHED` with `crash_reason: "ray-ref-not-restorable"`. Operator must `automil resubmit <node_id>` for any in-flight Ray jobs at daemon-restart time. Documented in CHANGELOG + Phase 6 README.

### `running/` namespace migration (Phase 6 success #4)

- **D-168:** **Breaking layout change** — `orchestrator/running/<id>.json` (flat) → `orchestrator/running/<backend>/<id>.json` (namespaced). Per CLAUDE.md "Avoid backwards-compatibility hacks" and Leo's milestone-is-a-refactor framing, autoMIL 6.x does NOT auto-migrate flat → namespaced. Operators upgrading from Phase 5 must:
  1. Drain in-flight runs (`automil orchestrator stop` + wait for terminal).
  2. Confirm `orchestrator/running/` is empty.
  3. Upgrade.
  CHANGELOG entry surfaces this as "BREAKING:" header. `_orchestrator_daemon.py` startup checks: if flat `running/*.json` exists AND no namespaced directories exist, exit non-zero with the recovery instructions.

- **D-169:** **Code-side migration of every `running_dir` reference.** Files that touch `orchestrator/running/`:
  - `src/automil/backends/_orchestrator_daemon.py` — 8+ references; refactor to compute `self.running_dir = self.orch_dir / "running" / backend_name` per-backend at tick time.
  - `src/automil/backends/local.py` — `list_running()` scans `running/local/*.json`.
  - `src/automil/cli/cancel.py:84` — read from `running/<backend>/<id>.json` after backend-name lookup.
  - `src/automil/cli/reconcile.py:74` — pass `running_dir` per-backend.
  - `src/automil/cli/cell.py:30` — same (cell tick reads `running/` for live nodes).
  All reads must resolve `backend_name` first (default `local` for legacy nodes per Phase 2 D-76 fallback) then path into `running/<backend_name>/`.

### Cross-backend log unification (Phase 6 success #4)

- **D-170:** **`archive/<id>/run.log` is orchestrator-owned, NOT backend-owned.** When `_orchestrator_daemon._tick()` observes a node transition to terminal, it:
  1. Resolves `backend = BACKENDS[node.metadata.backend]` and reconstructs `JobHandle`.
  2. Calls `backend.log_iter(handle)` and drains all yielded lines into `archive/<id>/run.log` via `_atomic_write_lines(path, lines)` (Phase 0 atomic-write pattern §3 / D-25 — write to `tempfile.mkstemp` neighbour, `os.rename` on close).
  3. Backends' `log_iter()` MUST close (raise `StopIteration`) within 60s of terminal state — backends that block forever (e.g., a SLURM stdout file that never ends) are a contract violation. The 60s timeout is enforced at the orchestrator with a wrapper that logs the violation and force-closes.

- **D-171:** **Cell-level archival.** `archive/<id>/run.log` ships alongside `archive/<id>/result.json`, `archive/<id>/spec.json`, and (for SLURM) `archive/<id>/slurm-stdout.out`/`slurm-stderr.err` symlinks (NOT copies — submitit's logs already live in `submitit-logs/`; symlink reduces disk usage). Tied directly to existing archive pattern; no new contract surface for archive consumers.

### `automil check` extension (BCK-05)

- **D-172:** `automil check` MUST validate: when `backend.name == "slurm"`, all required `backend.slurm.directives` keys are present AND none contain the literal `TODO_FILL_IN`. Required keys: `time`, `partition`, `account`, `cpus_per_task`, `mem_gb`. Optional keys: `qos`, `gpus_per_node`. `signal` is framework-mandated and rejected if operator tries to override — documented as immutable.

- **D-173:** When `backend.name == "ray"`, `automil check` MUST verify ray import succeeds (extras installed). Optional verification: if `RAY_ADDRESS` is set, attempt a 1s `ray.init(address=..., ignore_reinit_error=True)` connect-test and report success/failure (advisory, not blocking — operator may be intentionally pre-init).

### Test infrastructure (Phase 6 success #3)

- **D-174:** **In-process simulation in CI; real-cluster behind markers.** `tests/backends/test_contract.py` is parameterised `@pytest.mark.parametrize("backend_name", ["local", "mock_slurm", "slurm", "ray"])` with backend factories that:
  - `local` → `LocalBackend(automil_dir, config)` — unchanged from Phase 2.
  - `mock_slurm` → `MockSLURMBackend(state_file=tmp_path / "mock.json", poll_lag_seconds=0.05)` — unchanged.
  - `slurm` → `SLURMBackend(automil_dir, config_with_debug_executor)` where `config_with_debug_executor` triggers submitit's `DebugExecutor` (in-process, no actual sbatch). Implementation: `SLURMBackend.__init__` checks for `config["backend"]["slurm"].get("debug_in_process", False)` and constructs `submitit.LocalExecutor` (in-process subprocess) instead of `AutoExecutor`. The `--signal=B:TERM@30` directive is a no-op under DebugExecutor; signal-handling tests bypass via direct `register_sigterm_flush` invocation.
  - `ray` → `RayBackend(automil_dir, config)` with `config["backend"]["ray"]["local_mode"] = True`. `__init__` calls `ray.init(local_mode=True, ignore_reinit_error=True)` (single-process, single-thread).

- **D-175:** **Real-cluster tests** live at `tests/backends/test_contract_real_slurm.py` and `tests/backends/test_contract_real_ray.py`, both decorated with `@pytest.mark.requires_slurm` / `@pytest.mark.requires_ray` markers. `pytest.ini` adds `markers = requires_slurm: requires SLURM cluster (skip in CI), requires_ray: requires real Ray cluster (skip in CI)`. Default `pytest tests/` run skips both (CI green); nightly/pre-release `pytest tests/ -m "requires_slurm or requires_ray"` runs against real clusters.

- **D-176:** **Acceptance smoke** at `tests/backends/test_node_0176_smoke.py`: parameterised over `[local, slurm-debug, ray-local-mode]`, runs the CCRCC `node_0176`-equivalent variant (synthetic 1-fold version for CI speed; `requires_slurm`/`requires_ray` for full 5-fold). Asserts `result.json` composite within ±0.005 of LocalBackend baseline. This is the load-bearing Phase 6 anti-acceptance gate — proves end-to-end on every backend, not just contract compliance.

### Submitit checkpoint integration (explicit non-decision)

- **D-177:** **autoMIL does NOT use submitit's `Checkpointable` framework.** Phase 4 D-122's `register_sigterm_flush()` is the authoritative checkpoint mechanism — opt-in by the training script, framework-doesn't-inject. Reasoning: coupling our checkpoint protocol to submitit's lifecycle would (a) make Local + Ray backends second-class (they don't have submitit), (b) create framework-injected behaviour in user code (D-122 forbids), (c) complicate the cap contract (Phase 4 owns timing; submitit's checkpoint timing diverges). submitit's role is purely: dispatch a process with the right SLURM directives, route signals via `--signal=B:TERM@30`, surface state via `Job.state`. Our `_run_experiment_subprocess` wrapper invokes the user command in a normal subprocess; the user command's `register_sigterm_flush` handler responds to SIGTERM exactly as it does on LocalBackend.

### Backend-specific error types

- **D-178:** Extend `src/automil/backends/errors.py` with:
  - `BackendNotInstalledError(BackendError)` — raised when operator selects a backend whose extra isn't installed; carries `extra_name` attribute and `pip install -e '.[<extra>]'` recovery hint in the message.
  - `SlurmDirectivesIncompleteError(BackendError)` — raised by `automil check` when required directives are missing or contain `TODO_FILL_IN`; carries the missing key names.
  - `RayClusterUnreachableError(BackendError)` — raised when `RAY_ADDRESS` is set but the cluster isn't reachable AND fallback to local is disabled (config: `backend.ray.allow_local_fallback: false`).
  No new error type needed for SLURM-job-not-found; `BackendError` (Phase 2) covers it.

### Acceptance gate (BCK-05, BCK-06 — Phase 6 acceptance is the conjunction of)

- **D-179:**
  1. `tests/backends/test_contract.py` passes parametrised over `[LocalBackend, MockSLURMBackend, SLURMBackend (DebugExecutor), RayBackend (local_mode)]` — ≥10 scenarios per backend.
  2. Phase 5's 779-test baseline stays green.
  3. `python scripts/check_backend_isolation.py src/automil/` exits 0 (no new process-control references in slurm.py / ray.py — submitit and ray APIs sufficient).
  4. `pip install -e .` (no extras) installs cleanly; `automil --help` works; importing `automil.backends.slurm` raises `ImportError` (extras gate intact).
  5. `pip install -e '.[slurm]'` enables `backend.name: slurm` end-to-end against DebugExecutor.
  6. `pip install -e '.[ray]'` enables `backend.name: ray` end-to-end against `local_mode=True`.
  7. `tests/backends/test_node_0176_smoke.py` passes for all three CI-runnable backends (local, slurm-debug, ray-local-mode); composite within ±0.005 of LocalBackend.
  8. `running/` is namespaced (`running/local/`, `running/slurm/`, `running/ray/`); `_orchestrator_daemon.py` startup refuses to start if flat `running/*.json` exists in the orchestrator dir without namespaced subdirs.
  9. `archive/<id>/run.log` exists for every terminal node regardless of backend; orchestrator-owned via `_atomic_write_lines`.
  10. `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero matches.
  11. CHANGELOG entry surfaces the breaking `running/` layout change with operator recovery steps.

### Out of scope (Phase 6)

- **D-180:** Real SLURM cluster CI runner — cost prohibitive; `requires_slurm` marker for nightly only.
- **D-181:** Multi-fold-spans-multiple-GPUs Ray placement groups — explicit deferral; one-actor-per-submit is the v1 contract (matches Local + SLURM semantics).
- **D-182:** SLURM array jobs (`--array=0-N` for fold-fanout at the SLURM level) — explicit deferral; each `submit()` = one job. Cell-level fanout (Phase 4) handles parallelism via multiple `submit()` calls if a future variant wants it.
- **D-183:** Cross-backend running-queue rebalancing (`running/local/` jobs migrating to `running/slurm/` mid-flight) — explicit deferral; each backend owns its own running/.
- **D-184:** `Backend.healthcheck()` SLURM/Ray probes — Phase 7 (STP-01).
- **D-185:** Trajectory hooks on SLURM/Ray submit — already covered by Phase 3's `cli/submit.py` (backend-agnostic recording at the CLI layer, not the backend layer).
- **D-186:** SLURM-style cluster autodiscovery (auto-fill `partition`/`account` from `sinfo`/`scontrol`) — Phase 7 hardware autodetect (operator gets a `automil init --slurm` flag that runs `sinfo` and pre-fills directives, with confirmation).
- **D-187:** Ray Tune integration — explicit non-goal; we use raw `ray.remote` only. Ray Tune is a hyperparameter-search framework, not a backend, and conflates concerns autoMIL owns elsewhere (graph, scoring, manifest).
- **D-188:** Submitit's `Checkpointable` framework — see D-177; framework-doesn't-inject precludes.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § Phase 6 (success criteria 1–5)
- `.planning/REQUIREMENTS.md` BCK-05, BCK-06
- `.planning/PROJECT.md` § Key decisions (pluggable orchestrator backends with `local` as default)

### Prior phase decisions (the contracts Phase 6 plugs into)
- `.planning/phases/02-backend-abc-localbackend-re-export-shim-mockslurm-fixture/02-CONTEXT.md` — D-51..D-69 (Backend ABC + JobSpec/JobHandle/JobState contracts), D-76 (`metadata.backend`), D-69 (guarded import for unavailable extras), D-57 (cancel custom signal accepted with logged warning)
- `.planning/phases/04-6h-per-cell-hard-cap-cell-concept-formalisation/04-CONTEXT.md` — D-115 (cap-cancel signal=SIGTERM 30s grace then SIGKILL), D-122 (`register_sigterm_flush()` opt-in not framework-injected), D-133 (SLURM `--time` directive integration deferred to here)
- `.planning/phases/05-generalization-gate/05-CONTEXT.md` — D-145 (`JobSpec.metadata` kw-only frozen-dataclass field — backends carry per-job metadata through)

### Existing framework code (Phase 6 extends or wraps these)
- `src/automil/backends/base.py` — locked Backend ABC + JobSpec + JobHandle + JobState (the contract Phase 6 implements)
- `src/automil/backends/local.py` — reference impl pattern (queue/running/archive routing); SLURMBackend + RayBackend mirror the lifecycle without using process-control primitives
- `src/automil/backends/mock_slurm.py` — eventual-consistency simulation pattern; SLURMBackend's contract test partner
- `src/automil/backends/_orchestrator_daemon.py` — current `running_dir` flat-layout owner; Phase 6 refactors `running_dir` resolution to be per-backend
- `src/automil/backends/__init__.py` — guarded-import pattern for opt-in extras
- `src/automil/backends/errors.py` — typed error hierarchy; Phase 6 extends with backend-not-installed + slurm-directives-incomplete + ray-cluster-unreachable
- `scripts/check_backend_isolation.py` — BCK-04 lint; Phase 6 verifies new backends don't add process-control refs
- `src/automil/templates/config.yaml.j2` — target for new `backend:` block with `slurm:` and `ray:` subsections
- `pyproject.toml` — target for new `[slurm]` and `[ray]` extras

### Anti-pattern reference
- `.planning/research/PITFALLS.md` § Pitfall 2 — leaky backend ABC; Phase 6's parametrised contract test is the authoritative defence (≥4 backends pass the same suite, no implementation-specific behaviour leaks)

### External library docs (researcher must consult)
- submitit GitHub: https://github.com/facebookincubator/submitit (AutoExecutor, LocalExecutor=DebugExecutor, Job.state mapping, signal directives `--signal=B:TERM@30`)
- Ray Core docs: https://docs.ray.io/en/latest/ray-core/api/doc/ray.remote.html (`@ray.remote` decorator, `ray.cancel(force=True)`, `ray.wait(timeout=0)`, `local_mode=True` for testing)
- Ray init lifecycle: https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html (`address="auto"` semantics, `ignore_reinit_error`)
- Why NOT Ray Tune: https://docs.ray.io/en/latest/tune/index.html — Ray Tune is a hyperparameter framework that conflates concerns autoMIL owns (D-187)

### Standing memory (Leo's directives)
- `~/.claude/projects/-home-jma-Documents-yinshuol-autoMIL/memory/feedback_decide_engineering_ask_features.md` — Phase 6 has zero feature questions; everything decided autonomously per production patterns.
- `~/.claude/projects/-home-jma-Documents-yinshuol-autoMIL/memory/feedback_paper_campaign_vs_framework.md` — `time` and `signal` couple to framework cap contract (framework-mandated); cluster-specific directives are consumer-supplied.
- `~/.claude/projects/-home-jma-Documents-yinshuol-autoMIL/memory/project_automil_is_generic.md` — backend implementations are framework-only; zero `autobench`/`AUTOBENCH_`/`benchmarks/` refs in `src/automil/backends/`.
- `~/.claude/projects/-home-jma-Documents-yinshuol-autoMIL/memory/feedback_never_blind_checkout.md` — atomic-write-plus-rollback uses `path.unlink()`, never `git checkout`.

</canonical_refs>

<specifics>
## Specific Implementation Notes

- **`SLURMBackend`'s `_executor.update_parameters(signal="B:TERM@30")`** is the framework-mandated wire to Phase 4 D-115. SLURM emits SIGTERM 30s before `--time` expires AND on `scancel --signal=TERM`. Inside the user training script, `register_sigterm_flush()` (D-122) catches SIGTERM and writes the per-fold partial state. End-to-end: cap fires → orchestrator calls `Backend.cancel(handle, signal=SIGTERM)` → SLURMBackend calls `submitit.Job.cancel()` → SLURM emits SIGTERM → user handler flushes → SLURM grace expires → SIGKILL → state transitions to `BUDGET_KILLED`. Identical timing to LocalBackend's process-group SIGTERM-then-SIGKILL.
- **Ray's `force=True` on cancel** terminates the actor's worker process immediately (within Ray's ~1s internal grace). Phase 4's 30s grace is owned by the orchestrator (D-115); on cap fire, the orchestrator gives the user 30s to flush via `register_sigterm_flush` BEFORE calling `Backend.cancel`. So Ray's shorter internal grace doesn't matter — the framework-side timing is what's contract-bound.
- **submitit's DebugExecutor** runs the submitted function in-process (single thread, blocking). Perfect for CI contract tests because: (a) no SLURM cluster needed, (b) deterministic timing, (c) signal handling can be exercised via direct `os.kill` to the test process. Drawback: doesn't exercise SLURM directive parsing — that's a separate `test_slurm_directives.py` test that imports the directive-builder logic without dispatching.
- **`ray.init(local_mode=True)`** runs all tasks single-threaded in the driver. Same logic as DebugExecutor. Tests for actual parallelism semantics live behind `requires_ray` (real cluster).
- **Persisted `running/<backend>/<id>.json` schema** carries: `node_id`, `backend_name`, `opaque_id`, `submitted_at`, `spec_path` (pointer to `archive/<id>/spec.json` for spec restoration), and (Ray-only) `cap_cancel_pending: bool` (set by orchestrator when cap fires; read by `RayBackend.poll` to discriminate `TaskCancelledError` → `BUDGET_KILLED` vs operator-cancel → `CANCELLED`).
- **CHANGELOG breaking change entry** template:
  ```
  ## 6.0.0
  ### BREAKING: Per-backend `running/` namespacing
  `orchestrator/running/<id>.json` (flat) → `orchestrator/running/<backend>/<id>.json` (namespaced).
  Operators upgrading from 5.x must:
  1. Run `automil orchestrator stop` and wait for in-flight runs to terminate.
  2. Confirm `orchestrator/running/` contains zero `.json` files at the top level.
  3. Upgrade.
  Daemon refuses to start if it detects flat `running/*.json` files at upgrade time.
  ```
- **Why guarded import handles `pip install -e '.[slurm]'` on a system without `sbatch` on PATH:** submitit imports cleanly even without SLURM installed; only `AutoExecutor.submit()` invokes `sbatch`. So `pip install -e '.[slurm]'` on a dev laptop gives a working `import automil.backends.slurm`; `automil submit --backend slurm` against a no-SLURM machine fails at submit time with submitit's native `FileNotFoundError: sbatch`. We wrap that in `BackendError("SLURM tools not found on PATH; this machine doesn't appear to have a SLURM installation").` for clearer diagnostics.

</specifics>

<deferred>
## Deferred Ideas

- **Real SLURM cluster CI runner** — D-180; `requires_slurm` for nightly only.
- **Multi-fold Ray placement groups** — D-181; one-actor-per-submit is v1.
- **SLURM array jobs (`--array=0-N`)** — D-182; one submit = one job.
- **Cross-backend running-queue rebalancing** — D-183.
- **`Backend.healthcheck()` SLURM/Ray probes** — D-184; Phase 7.
- **`automil init --slurm` cluster autodiscovery** (auto-fill `partition`/`account` from `sinfo`) — D-186; Phase 7.
- **Ray Tune integration** — D-187; explicit non-goal.
- **Submitit's `Checkpointable` framework** — D-188; framework-doesn't-inject.
- **Per-experiment GPU fractional sharing on SLURM** (`--gres=gpu:fraction`) — Phase 7 / future; SLURM doesn't natively support GPU fractions, would need an MPS-like wrapper.
- **`backends/kubernetes.py` (BCK-07?)** — out-of-scope for v1; not in REQUIREMENTS.md.
- **`backends/dask.py`** — same; not requirement-tracked.

</deferred>

---

*Phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote*
*Context bootstrapped autonomously 2026-05-06 per Leo's "decide engineering, ask features" directive (memory: feedback_decide_engineering_ask_features). No open questions for Leo at planning time. All 4 candidate gray areas resolved by production-pattern reasoning + prior-phase contract continuity.*
