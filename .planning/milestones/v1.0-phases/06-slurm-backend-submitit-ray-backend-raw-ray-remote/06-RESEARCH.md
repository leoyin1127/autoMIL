# Phase 6: SLURM Backend (submitit) + Ray Backend (raw ray.remote) — Research

**Researched:** 2026-05-06
**Domain:** Distributed job backends — submitit>=1.5.3 (SLURM) + ray>=2.55.1 (Ray)
**Confidence:** HIGH (Context7, official Ray docs, submitit GitHub source)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
D-152..D-188 — all 37 engineering decisions are locked. See 06-CONTEXT.md `<decisions>` block.
Key locked choices relevant to the API surface this research verifies:
- D-152: `slurm.py` on submitit>=1.5.3, `ray.py` on ray>=2.55.1, both in `src/automil/backends/`
- D-153: guarded import pattern in `backends/__init__.py`
- D-154: `[slurm]` and `[ray]` extras in pyproject.toml
- D-155: `submitit.AutoExecutor(folder=...)` + `update_parameters(time=..., signal="B:TERM@30", ...)`
- D-156: `executor.submit(_run_experiment_subprocess, spec)` returns a `submitit.Job`
- D-157: `job.state` string → `JobState` mapping
- D-158: `job.cancel()` for SLURM cancel
- D-159: `log_iter` tails `{job_id}_0_log.out` with 1s tick
- D-160: `list_running()` scans `running/slurm/*.json`; stale handle → CRASHED
- D-161: `RayBackend.__init__` with hybrid `RAY_ADDRESS` → fallback local init
- D-162: one `@ray.remote` function per submit; `ref.hex()` as opaque_id
- D-163: one actor per submit (NOT placement groups)
- D-164: `ray.wait([ref], timeout=0)` non-blocking poll
- D-165: `ray.cancel(ref, force=True, recursive=True)`
- D-166: per-actor log file in `running/ray/{node_id}.log`
- D-167: ObjectRef not restorable → CRASHED on restart
- D-168..D-169: `running/` namespace migration (breaking); daemon-refusal-to-start guardrail
- D-170..D-171: orchestrator-owned log unification via `_atomic_write_lines`
- D-172..D-173: `automil check` extensions for SLURM directives + Ray reachability
- D-174..D-176: contract test parametrisation; in-process simulation
- D-177: submitit Checkpointable NOT used
- D-178: new error types `BackendNotInstalledError`, `SlurmDirectivesIncompleteError`, `RayClusterUnreachableError`
- D-179: 11-clause acceptance gate
- D-180..D-188: explicit out-of-scope deferrals

### Claude's Discretion
None — all 37 decisions locked per Leo's "decide engineering, ask features" directive.

### Deferred Ideas (OUT OF SCOPE)
D-180: Real SLURM cluster CI runner | D-181: Multi-fold Ray placement groups |
D-182: SLURM array jobs | D-183: Cross-backend rebalancing | D-184: Backend.healthcheck |
D-185: Trajectory hooks | D-186: SLURM cluster autodiscovery | D-187: Ray Tune |
D-188: Submitit Checkpointable
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BCK-05 | `SLURMBackend` on submitit>=1.5.3; opt-in via `[slurm]` extra; `--time --signal=B:TERM@30` SLURM directives match framework wall-clock contract | §submitit API, §signal parameter pitfall, §D-155 correction |
| BCK-06 | `RayBackend` on ray>=2.55.1 raw `ray.remote`; opt-in via `[ray]` extra; `ray.cancel(force=True)` honors wall-clock contract | §ray.cancel pitfall (D-165 correction), §ray.init exception type, §local_mode status |
</phase_requirements>

---

## Summary

Phase 6 lands two opt-in distributed backends by plugging into the locked Phase 2 ABC. This research verifies the concrete API surface that D-152..D-188 assume and surfaces implementation-blocking pitfalls.

**Five findings require planner attention:**

1. **D-155 `signal` kwarg is WRONG.** `update_parameters()` has no `signal=` parameter. The `--signal=B:TERM@30` directive must be passed via `slurm_additional_parameters={"signal": "B:TERM@30"}`. The `signal_delay_s` kwarg exists but maps to `--signal=USR2@N`, not `--signal=B:TERM@30`.

2. **D-159 log file name is WRONG.** submitit names logs `{job_id}_0_log.out` (task suffix `_0_`), not `{job_id}_log.out`. The `log_iter` implementation must use `job.paths.stdout` (a `Path` property from `JobPaths`) rather than a hardcoded name.

3. **D-165 `ray.cancel(force=True)` is INCOMPATIBLE with actors.** D-162 uses `@ray.remote` *functions*, not Ray actors — so `force=True` IS valid for functions. But if D-162 were changed to use actors in future, `force=True` raises `ValueError`. This research confirms D-162's function-based design must be preserved.

4. **`ray.init(local_mode=True)` is "no longer supported"** in Ray 2.55+. The parameter still exists (not fully removed) but emits a deprecation warning and the feature is unreliable. D-174's CI test strategy for RayBackend needs an alternative in-process approach.

5. **`ray.cancel(force=True)` raises `WorkerCrashedError` on `ray.get()`**, not `TaskCancelledError`. D-164's poll exception mapping must catch both.

**Primary recommendation:** Planner should treat items 1, 2, 4, and 5 as concrete API corrections to be written into the wave-1 plan files. Item 3 is a design confirmation (function-based is correct). All corrections are localized; the architecture remains as locked in D-152..D-188.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Job dispatch to SLURM | API / Backend (`slurm.py`) | SLURM daemon (remote) | submitit serializes the function + args and calls `sbatch`; compute runs on SLURM worker node |
| Job dispatch to Ray | API / Backend (`ray.py`) | Ray cluster (remote) | `@ray.remote` function + `ray.init()` handles routing to Ray scheduler |
| Log streaming | API / Backend (iterator) | Orchestrator (consumer) | Backend owns `log_iter()` generator; orchestrator drains it into `archive/<id>/run.log` |
| `running/` namespace | API / Backend (each backend writes its own subdirectory) | — | D-168: breaking layout change, each backend writes `running/<backend>/<id>.json` |
| Cap enforcement (timing) | Orchestrator | Backend (signal delivery) | Orchestrator owns the 30s timing window (D-115); backend's `cancel()` is the signal mechanism |
| In-process CI simulation | Test infrastructure | — | submitit DebugExecutor (`cluster="debug"`) for SLURM; `ray.init()` no-args for Ray |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| submitit | >=1.5.3 | SLURM job dispatch via Python; AutoExecutor, Job, JobPaths | Facebook/FAIR's production SLURM Python wrapper; widely used in ML research |
| ray | >=2.55.1 | Distributed compute; `@ray.remote`, `ray.wait`, `ray.cancel` | Industry standard for Python distributed ML; native GPU fraction support |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses (stdlib) | — | `JobSpec` frozen dataclass pickling by both backends | Already in use; no new dependency |
| cloudpickle | (transitively via ray/submitit) | Serializes `JobSpec` for remote dispatch | Implicit — verify pickling of `Path` fields |

**Installation (new extras):**
```bash
pip install -e '.[slurm]'   # adds submitit>=1.5.3
pip install -e '.[ray]'     # adds ray>=2.55.1
```

**pyproject.toml target (D-154):**
```toml
[project.optional-dependencies]
ml   = [...]                              # unchanged
slurm = ["submitit>=1.5.3"]              # BCK-05
ray   = ["ray>=2.55.1"]                  # BCK-06
```

**Version verification:** [VERIFIED: Context7 / submitit docs, Ray 2.55.0 release docs] Both floor versions are confirmed current-stable as of research date.

---

## Architecture Patterns

### System Architecture Diagram

```
automil orchestrator daemon (_tick loop)
           │
           ├── [backend="slurm"] ──> SLURMBackend
           │                              │ submit()
           │                              │  submitit.AutoExecutor.submit(_run_experiment_subprocess, spec)
           │                              │  → sbatch → SLURM worker node
           │                              │    worker: chdir(worktree), setenv(spec.env), subprocess.run(command)
           │                              │    writes result.json to working_dir
           │                              │
           │                         poll() ──> submitit.Job(folder, job_id).state → "PENDING|RUNNING|COMPLETED|..."
           │                         log_iter() ──> tail job.paths.stdout ({job_id}_0_log.out)
           │                         cancel() ──> job.cancel() → scancel
           │
           └── [backend="ray"] ──> RayBackend
                                        │ submit()
                                        │  _run_experiment_ray.remote(spec)  [@ray.remote(num_gpus=...)]
                                        │  → Ray scheduler → Ray worker
                                        │    worker: chdir(worktree), os.environ.update(spec.env), subprocess.run(command)
                                        │    writes result.json + stdout to running/ray/{node_id}.log
                                        │
                                   poll() ──> ray.wait([ref], timeout=0) → non-blocking snapshot
                                   log_iter() ──> tail running/ray/{node_id}.log
                                   cancel() ──> ray.cancel(ref, force=True)
```

### Recommended Project Structure (backends/ extension)
```
src/automil/backends/
├── __init__.py              # add guarded imports for slurm + ray (D-153)
├── base.py                  # unchanged ABC
├── errors.py                # extend with 3 new error types (D-178)
├── local.py                 # update list_running → scan running/local/*.json (D-169)
├── mock_slurm.py            # unchanged fixture
├── slurm.py                 # NEW: SLURMBackend (BCK-05)
├── ray.py                   # NEW: RayBackend (BCK-06)
└── _orchestrator_daemon.py  # update running_dir → per-backend (D-169)

tests/backends/
├── conftest.py              # extend params to ["local", "mock_slurm", "slurm", "ray"]
├── test_contract.py         # parametrised over 4 backends (unchanged scenarios)
├── test_node_0176_smoke.py  # NEW: acceptance smoke (D-176)
├── test_contract_real_slurm.py  # NEW: @requires_slurm (D-175)
└── test_contract_real_ray.py    # NEW: @requires_ray (D-175)
```

### Pattern 1: submitit AutoExecutor construction + signal directive

**Critical correction to D-155:** The `signal=` kwarg does not exist in `update_parameters()`. Use `slurm_additional_parameters`:

```python
# Source: Context7 /facebookincubator/submitit + https://github.com/facebookincubator/submitit/blob/main/submitit/slurm/slurm.py
import submitit

executor = submitit.AutoExecutor(
    folder=automil_dir / "orchestrator" / "running" / "slurm" / "submitit-logs",
    cluster="slurm",        # explicit; avoids auto-detect confusion on PATH
)
executor.update_parameters(
    timeout_min=walltime_seconds // 60,          # D-155: "time" → correct kwarg is "timeout_min"
    mem_gb=config["backend"]["slurm"]["directives"]["mem_gb"],
    cpus_per_task=config["backend"]["slurm"]["directives"]["cpus_per_task"],
    gpus_per_node=config["backend"]["slurm"]["directives"].get("gpus_per_node", 1),
    slurm_partition=config["backend"]["slurm"]["directives"]["partition"],
    slurm_account=config["backend"]["slurm"]["directives"]["account"],
    slurm_qos=config["backend"]["slurm"]["directives"].get("qos"),
    slurm_additional_parameters={
        "signal": "B:TERM@30",  # framework-mandated; matches Phase 4 D-115
    },
)
```

**Why `cluster="slurm"` explicitly:** `AutoExecutor` auto-detects based on whether `srun` is on PATH. On a dev machine without SLURM installed, it falls back to `local`. Passing `cluster="slurm"` forces the intent and fails loudly if `sbatch` is absent.

### Pattern 2: submitit log file path

**Critical correction to D-159:** Log files are `{job_id}_0_log.out`, not `{job_id}_log.out`.

```python
# Source: https://github.com/facebookincubator/submitit/blob/main/submitit/core/utils.py
# JobPaths.stdout → folder / f"{job_id}_0_log.out"
# Access via:
job = submitit.Job(folder=submitit_logs_dir, job_id=handle.opaque_id)
stdout_path: Path = job.paths.stdout   # resolves to {job_id}_0_log.out
stderr_path: Path = job.paths.stderr   # resolves to {job_id}_0_log.err
```

`job.stdout()` is a blocking read of the whole file. For `log_iter()`, tail `job.paths.stdout` directly with open() + readline loop (same pattern as LocalBackend).

### Pattern 3: submitit Job reconstruction across restart

```python
# Source: https://github.com/facebookincubator/submitit/blob/main/submitit/core/core.py
# Job(folder, job_id, tasks=(0,)) reconstructs state from disk.
# The folder must contain the submitit pickle files written at submit time.
import submitit

job = submitit.Job(
    folder=submitit_logs_dir,
    job_id=stored_job_id_str,   # from running/slurm/{node_id}.json "opaque_id"
)
state = job.state               # re-queries SLURM sacct on access
```

`job.state` re-queries `sacct` on each access (with caching). Reconstruction is **safe across daemon restarts** as long as `submitit-logs/` directory persists. The logs directory must NOT be inside the git worktree (it would be torn down).

### Pattern 4: Ray hybrid init + `@ray.remote` function dispatch

```python
# Source: https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html
import ray, os

def _init_ray():
    if ray.is_initialized():
        return
    ray_address = os.environ.get("RAY_ADDRESS", "auto")
    try:
        ray.init(address=ray_address, ignore_reinit_error=True, log_to_driver=False)
    except ConnectionError:           # VERIFIED: exact exception per Ray 2.55 docs
        ray.init(ignore_reinit_error=True, log_to_driver=False)

# Submitting a function (NOT an actor):
@ray.remote
def _run_experiment_ray(spec):
    import os, subprocess
    os.chdir(worktree_path)           # must happen inside the remote function
    for k, v in spec.env:
        os.environ[k] = v
    # Redirect stdout to per-node log file BEFORE running command
    log_path = spec.overlay_dir.parent / "running" / "ray" / f"{spec.node_id}.log"
    with open(log_path, "w") as logf:
        subprocess.run(list(spec.command), stdout=logf, stderr=subprocess.STDOUT)
```

### Pattern 5: ray.cancel for functions (force=True is valid)

```python
# Source: https://docs.ray.io/en/latest/ray-core/api/doc/ray.cancel.html
# force=True is VALID for @ray.remote functions (NOT for Ray Actors).
# D-162 uses functions → force=True is correct.
ray.cancel(ref, force=True, recursive=True)

# ray.get() on a force-cancelled function raises WorkerCrashedError (NOT TaskCancelledError)
# Source: https://docs.ray.io/en/latest/ray-core/api/doc/ray.cancel.html
try:
    ray.get(ref, timeout=0)
except ray.exceptions.WorkerCrashedError:
    return JobState.BUDGET_KILLED    # or CANCELLED depending on cap_cancel_pending flag
except ray.exceptions.TaskCancelledError:
    return JobState.BUDGET_KILLED    # soft-cancel (force=False) path
except ray.exceptions.RayTaskError:
    return JobState.CRASHED          # task raised an exception
```

**Critical for D-164:** The poll exception mapping in D-164 only catches `TaskCancelledError`. With `force=True` (D-165), `WorkerCrashedError` is raised instead. Both must be caught and disambiguated via the `cap_cancel_pending` flag in `running/ray/{node_id}.json`.

### Pattern 6: non-blocking ray.wait poll

```python
# Source: Context7 /ray-project/ray
ready, not_ready = ray.wait([ref], timeout=0)   # timeout=0 is valid for non-blocking
if not_ready:
    return JobState.RUNNING    # Ray collapses PENDING|RUNNING (D-164)
# ref is in ready; call ray.get to get result or exception
```

`timeout=0` is confirmed valid — returns immediately with current state.

### Anti-Patterns to Avoid

- **`update_parameters(signal="B:TERM@30")`** — `signal` is not a recognized kwarg; passes silently, not written to sbatch. Use `slurm_additional_parameters={"signal": "B:TERM@30"}` instead.
- **`update_parameters(time=N)`** — `time` is a SlurmExecutor-only kwarg; `AutoExecutor` uses `timeout_min`. The SlurmExecutor docs show `time=120` but that's not the `AutoExecutor` shared API. Use `timeout_min=walltime_seconds // 60`.
- **`ray.init(local_mode=True)`** for CI tests — "no longer supported" in Ray 2.55+; emits deprecation warnings and is functionally unreliable. Replace with `ray.init()` (no-args = local cluster) + `ignore_reinit_error=True`.
- **`ray.cancel(actor_task_ref, force=True)`** — raises `ValueError` when called on Actor tasks. D-162 uses functions (not actors) so this is safe. Do NOT refactor to Ray Actors without removing `force=True`.
- **Hardcoding log path as `{job_id}_log.out`** — actual pattern is `{job_id}_0_log.out`. Use `job.paths.stdout` from `submitit.Job`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SLURM `sbatch` invocation + state polling | Custom subprocess calls to `sbatch`/`sacct` | `submitit.AutoExecutor` + `submitit.Job.state` | sbatch arg escaping, sacct caching, job array handling, retry logic are all handled by submitit |
| Ray worker scheduling + GPU reservation | Manual `ray.init()` + process spawn | `@ray.remote(num_gpus=...)` | Ray handles fractional GPU reservation, worker placement, and CUDA_VISIBLE_DEVICES injection |
| Cross-process result collection | stdout parsing | `result.json` (existing contract) — backends call `subprocess.run()` inside the remote function | Result contract already designed for filesystem mediation (Phase 2 D-77) |
| Log file tailing | `subprocess.Popen(['tail', '-f', ...])` | Direct Python `open()` + `readline()` loop with sleep — same pattern as LocalBackend | Avoids `Popen` (BCK-04 lint violation), portable across SLURM worker nodes |

**Key insight:** Both submitit and Ray provide library abstractions over the exact primitives BCK-04 forbids (`sbatch`/`scancel` for SLURM; process spawn for Ray). The `check_backend_isolation.py` lint should remain clean because neither `slurm.py` nor `ray.py` needs `os.kill`, `Popen`, or `.pid`.

---

## Common Pitfalls

### Pitfall 1: `signal=` kwarg silently ignored in `update_parameters()`

**What goes wrong:** D-155 writes `update_parameters(..., signal="B:TERM@30", ...)`. `AutoExecutor.update_parameters()` silently ignores unrecognized kwargs (it merges them into a dict; unknown keys become unknown sbatch directives that may or may not pass through). SLURM may or may not receive `--signal=B:TERM@30` depending on submitit version behavior. The cap contract (Phase 4 D-115) breaks silently — cap fires, SIGTERM not sent 30s before timeout.

**Why it happens:** D-155 was written based on training-data knowledge of submitit's `SlurmExecutor.update_parameters(signal=...)`, which IS a valid kwarg for the direct `SlurmExecutor` but NOT for `AutoExecutor`'s shared parameter set.

**How to avoid:** Use `slurm_additional_parameters={"signal": "B:TERM@30"}`. [VERIFIED: submitit source + web search — `additional_parameters` (now `slurm_additional_parameters`) is the canonical pass-through for SLURM-native directives not mapped to shared params]

**Warning signs:** `automil check` passes but a live experiment with cap firing has no SIGTERM 30s before kill.

### Pitfall 2: `timeout_min` vs `time` in `update_parameters()`

**What goes wrong:** D-155 references `time=config[...]`. `SlurmExecutor.update_parameters(time=N)` accepts minutes as `time`. `AutoExecutor.update_parameters()` uses `timeout_min` as the cross-cluster shared name (per Context7 AutoExecutor docs: "shared params include timeout_min"). Passing `time=N` to AutoExecutor either raises or silently maps incorrectly.

**How to avoid:** Always use `timeout_min=walltime_seconds // 60`. Add a minimum of `1` minute (integer) — submitit requires a positive integer.

**Code fix:** `timeout_min=max(1, spec.walltime_seconds // 60)` [CITED: Context7 /facebookincubator/submitit AutoExecutor docs]

### Pitfall 3: Log file naming — `{job_id}_0_log.out` not `{job_id}_log.out`

**What goes wrong:** D-159 mentions tailing `submitit_logs_dir/{job_id}_log.out`. The actual `JobPaths.stdout` produces `{job_id}_0_log.out` (task index suffix). Hardcoding `f"{job_id}_log.out"` opens a non-existent file; `log_iter()` yields nothing; the orchestrator's 60s drain timeout triggers a contract violation warning for every SLURM job.

**How to avoid:** Use `job.paths.stdout` (a `Path`) as the file to tail. Access it via `submitit.Job(folder=..., job_id=...).paths.stdout`. [VERIFIED: submitit/core/utils.py source — `JobPaths.stdout = folder / f"{job_id}_{task_id}_log.out"` where `task_id=0` by default]

### Pitfall 4: `ray.cancel(force=True)` raises `WorkerCrashedError`, not `TaskCancelledError`

**What goes wrong:** D-164's exception map only catches `TaskCancelledError` for cancelled jobs. With `force=True` (D-165), Ray raises `WorkerCrashedError` on `ray.get()`. The poll code falls through to the default `ray.exceptions.RayTaskError` catch, marks the job as `CRASHED` instead of `CANCELLED`/`BUDGET_KILLED`, corrupting the reconcile path.

**How to avoid:** Catch BOTH in `poll()`:
```python
except (ray.exceptions.WorkerCrashedError, ray.exceptions.TaskCancelledError):
    if _was_cap_cancel(handle, automil_dir):
        return JobState.BUDGET_KILLED
    return JobState.CANCELLED
```

**Reference:** [VERIFIED: https://docs.ray.io/en/latest/ray-core/api/doc/ray.cancel.html — "force=True: `ray.get()` raises `WorkerCrashedError`; force=False: `ray.get()` raises `TaskCancelledError`"]

### Pitfall 5: `ray.init(local_mode=True)` is unreliable in Ray 2.55+

**What goes wrong:** D-174 specifies `ray.init(local_mode=True)` for the CI `ray` backend fixture. In Ray 2.55+, `local_mode` is marked "No longer supported." The parameter still exists in the function signature but behavior is unreliable — it emits deprecation warnings and has known issues with certain APIs.

**How to avoid:** For CI (in-process-like), use plain `ray.init()` (no args) with `ignore_reinit_error=True`. This starts a local single-machine Ray cluster (not in-process like local_mode, but effectively single-node). The test will still need to clean up via `ray.shutdown()` in teardown.

**Corrected fixture:**
```python
# In conftest.py for "ray" param
import ray
from automil.backends.ray import RayBackend
ray.init(ignore_reinit_error=True)
yield RayBackend(automil_dir, config)
# teardown: ray.shutdown() only if RayBackend._we_started_ray
```

**Reference:** [VERIFIED: https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html — "No longer supported. For interactive debugging consider using the Ray distributed debugger."]

### Pitfall 6: `ray.init(address="auto")` raises `ConnectionError` (NOT `RuntimeError`)

**What goes wrong:** D-161 catches `ConnectionError`. This is actually CORRECT — Ray docs confirm: "throw a ConnectionError instead of starting a new local Ray instance." The pitfall is developers assuming it might be `RuntimeError` or `ray.exceptions.RaySystemError`.

**Confirmation:** [VERIFIED: https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html — "throw a ConnectionError"] D-161's hybrid init is correctly typed.

### Pitfall 7: `JobSpec` pickling across SLURM and Ray

**What goes wrong:** submitit pickles the `_run_experiment_subprocess` function AND its arguments (`spec: JobSpec`). Ray pickles the `spec` arg for remote dispatch. `JobSpec` is a frozen dataclass with `Path` fields (`overlay_dir: Path`). 

**Analysis:** `Path` objects are pickle-safe (Python stdlib). `tuple[tuple[str, str], ...]` for `env` is also pickle-safe. submitit uses cloudpickle; Ray uses cloudpickle internally. No pickling pitfalls expected for the `JobSpec` shape. [ASSUMED — not verified against actual submitit/Ray cloudpickle behavior with this exact dataclass, but cloudpickle handles frozen dataclasses and Path objects in standard usage]

**Warning sign:** If submit raises `PicklingError`, inspect the `spec.command` field (which could contain lambda/closure objects if misused).

### Pitfall 8: Ray worker CWD is not the worktree

**What goes wrong:** When `_run_experiment_ray(spec)` runs on a Ray worker, the worker's CWD is Ray's internal worker directory (typically under `/tmp/ray/`). `spec.working_subdir` is relative to the worktree path. Without explicit `os.chdir(worktree_path / working_subdir)`, `subprocess.run(spec.command)` runs in the wrong directory.

**How to avoid:** The `_run_experiment_ray` function MUST explicitly `os.chdir()` into the correct path before invoking `spec.command`. The worktree path must be derived from `spec.overlay_dir` (which is an absolute path in the archive) — wait, the worktree is CREATED from the overlay at run time. The function needs the worktree path passed to it (or creates it inside the function as LocalBackend does). This is a design question the planner must address: does `_run_experiment_ray` receive an already-created worktree path, or create the worktree inside the remote function? [ASSUMED: the design mirrors `_run_experiment_subprocess` for SLURM which creates the worktree inside the remote function using `runner.Runner`]

### Pitfall 9: `.env` file absent in SLURM compute node worktree

**What goes wrong:** `benchmarks/.env` is gitignored and not in the git worktree. On a SLURM compute node, the worktree is created from git history, so `.env` is absent. Without `.env`, any training script that uses `python-dotenv` to load it will fail to find the autobench dataset paths.

**How to avoid:** `JobSpec.env` (the whitelisted env additions) must include all `AUTOBENCH_*` variables at spec-creation time. The orchestrator daemon already loads `benchmarks/.env` via `dotenv_values()` and propagates env through `JobSpec.env`. For SLURM, the `_run_experiment_subprocess` function must set `os.environ[k] = v` for each entry in `spec.env` BEFORE launching the subprocess — NOT via `subprocess.run(env=...)` (which would bypass the whitelist passthrough). [VERIFIED: existing `_orchestrator_daemon.py` env propagation pattern]

### Pitfall 10: SLURM `cluster="slurm"` vs auto-detection

**What goes wrong:** `AutoExecutor(folder=...)` without `cluster=` auto-detects based on whether `srun`/`sbatch` is on PATH. On a developer laptop without SLURM, it silently falls back to `local` executor and submits locally — not to SLURM. This is exactly the opposite of what a `SLURMBackend` should do.

**How to avoid:** Always pass `cluster="slurm"` in `SLURMBackend.__init__`. When `sbatch` is not found, `AutoExecutor` will raise `FileNotFoundError`. Wrap in `BackendError("SLURM tools not found on PATH")` per D-155's specifics block.

### Pitfall 11: Flat `running/*.json` files still present after upgrade

**What goes wrong (D-168):** If the operator upgrades from Phase 5 without draining in-flight runs, the daemon finds both flat `running/*.json` files AND namespaced `running/local/` directory. The startup guardrail must detect flat files at `running/*.json` (NOT files in subdirectories) and refuse with recovery instructions.

**Implementation precision:** The check is `(orch_dir / "running").glob("*.json")` (top-level only). Files in `running/local/*.json` are valid Phase 6 layout and must NOT trigger the guardrail.

---

## Code Examples

### SLURMBackend skeleton (corrected for pitfalls 1 + 2 + 3 + 10)

```python
# Source: Context7 /facebookincubator/submitit + corrections from research
import submitit
from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends.errors import BackendError

class SLURMBackend(Backend):
    def __init__(self, automil_dir, config):
        debug_mode = config["backend"]["slurm"].get("debug_in_process", False)
        logs_dir = automil_dir / "orchestrator" / "running" / "slurm" / "submitit-logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        if debug_mode:
            self._executor = submitit.AutoExecutor(folder=logs_dir, cluster="debug")
        else:
            self._executor = submitit.AutoExecutor(folder=logs_dir, cluster="slurm")

        directives = config["backend"]["slurm"]["directives"]
        walltime_seconds = config["backend"]["slurm"].get("walltime_seconds", 21600)
        self._executor.update_parameters(
            timeout_min=max(1, walltime_seconds // 60),  # NOT time=; use timeout_min
            mem_gb=directives["mem_gb"],
            cpus_per_task=directives["cpus_per_task"],
            gpus_per_node=directives.get("gpus_per_node", 1),
            slurm_partition=directives["partition"],
            slurm_account=directives["account"],
            slurm_qos=directives.get("qos"),
            slurm_additional_parameters={          # NOT signal= kwarg; use additional_parameters
                "signal": "B:TERM@30",
            },
        )

    def poll(self, handle):
        job = submitit.Job(folder=self._logs_dir, job_id=handle.opaque_id)
        state_str = job.state  # re-queries sacct
        return _SLURM_STATE_MAP.get(state_str, JobState.PENDING)  # default PENDING for unknown

    def log_iter(self, handle):
        job = submitit.Job(folder=self._logs_dir, job_id=handle.opaque_id)
        log_path = job.paths.stdout   # {job_id}_0_log.out  NOT {job_id}_log.out
        # ... tail log_path with 1s tick until terminal state
```

### RayBackend skeleton (corrected for pitfalls 4 + 5)

```python
# Source: Context7 /ray-project/ray + corrections from research
import ray, os

class RayBackend(Backend):
    def poll(self, handle):
        ref = self._jobs.get(handle.opaque_id) or self._restore_ref(handle)
        if ref is None:
            # ObjectRef not restorable across restart (D-167)
            return JobState.CRASHED
        ready, not_ready = ray.wait([ref], timeout=0)
        if not_ready:
            return JobState.RUNNING
        try:
            ray.get(ref, timeout=0)
            return JobState.COMPLETED
        except ray.exceptions.RayTaskError:
            return JobState.CRASHED
        except (ray.exceptions.WorkerCrashedError,   # force=True path
                ray.exceptions.TaskCancelledError):  # force=False path (also possible)
            if _was_cap_cancel(handle, self._automil_dir):
                return JobState.BUDGET_KILLED
            return JobState.CANCELLED
```

### SLURM state map (D-157 + additional states)

```python
# Source: SLURM sacct docs + submitit Job.state observations
_SLURM_STATE_MAP: dict[str, JobState] = {
    "PENDING":        JobState.PENDING,
    "RUNNING":        JobState.RUNNING,
    "COMPLETED":      JobState.COMPLETED,
    "FAILED":         JobState.CRASHED,
    "CANCELLED":      JobState.CANCELLED,
    "TIMEOUT":        JobState.BUDGET_KILLED,    # cap fired
    "OUT_OF_MEMORY":  JobState.CRASHED,
    "NODE_FAIL":      JobState.CRASHED,          # D-157 default covers this
    "BOOT_FAIL":      JobState.CRASHED,
    "PREEMPTED":      JobState.CRASHED,          # preempted = effectively crashed for us
    "COMPLETING":     JobState.RUNNING,          # transitional; still running
    "REQUEUED":       JobState.PENDING,          # SLURM will re-run it
    # default: JobState.PENDING with one-time log warning (D-157)
}
```

**Note:** D-157 says "default → PENDING for unknown states with one-time logged warning." This is safe — unknown states are likely transitional SLURM states (`COMPLETING`, etc.) that resolve to terminal within seconds.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `update_parameters(time=N)` for SlurmExecutor | `timeout_min=N` for AutoExecutor | submitit AutoExecutor abstraction | D-155 must use `timeout_min`, not `time` |
| `update_parameters(signal="B:TERM@30")` | `slurm_additional_parameters={"signal": "..."}` | submitit API (never supported as first-class kwarg) | D-155 requires correction |
| `ray.init(local_mode=True)` for single-process testing | `ray.init()` (no-args, starts local cluster) | Ray 2.x deprecation | D-174 test infra needs adjustment |
| `f"{job_id}_log.out"` | `job.paths.stdout` → `{job_id}_0_log.out` | Always been task-indexed; training-data assumption was wrong | D-159 log path correction |

**Deprecated/outdated:**
- `ray.init(local_mode=True)`: "No longer supported" in Ray 2.55+; use `ray.init()` instead for local cluster testing
- `submitit.LocalExecutor` (now accessed via `cluster="local"` or `cluster="debug"` in AutoExecutor)

---

## Runtime State Inventory

> Not applicable — Phase 6 is a greenfield backend implementation. The `running/` namespace migration (D-168..D-169) is a breaking layout change, but it does NOT store any external data requiring migration. The operator is required to drain Phase 5 `running/` before upgrading.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — `running/` JSON files are drained before upgrade per D-168 | None |
| Live service config | None — no external services store autoMIL backend config | None |
| OS-registered state | None | None |
| Secrets/env vars | None — `JobSpec.env` passthrough is runtime-only | None |
| Build artifacts | None — no compiled extension requiring rename | None |

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=9.0.2 |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/backends/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BCK-05 | SLURMBackend passes contract test (DebugExecutor) | unit/contract | `uv run pytest tests/backends/test_contract.py -k slurm -x` | ❌ Wave 0 (extend conftest) |
| BCK-05 | SLURM directives completeness check | unit | `uv run pytest tests/backends/test_slurm_directives.py -x` | ❌ Wave 0 |
| BCK-05 | Acceptance smoke: slurm-debug composite within ±0.005 | integration | `uv run pytest tests/backends/test_node_0176_smoke.py -k slurm -x` | ❌ Wave 0 |
| BCK-05 | `automil check` rejects TODO-containing SLURM directives | unit | `uv run pytest tests/backends/test_slurm_directives.py::test_check_rejects_todo -x` | ❌ Wave 0 |
| BCK-06 | RayBackend passes contract test (local cluster) | unit/contract | `uv run pytest tests/backends/test_contract.py -k ray -x` | ❌ Wave 0 (extend conftest) |
| BCK-06 | Acceptance smoke: ray-local composite within ±0.005 | integration | `uv run pytest tests/backends/test_node_0176_smoke.py -k ray -x` | ❌ Wave 0 |
| BCK-05+06 | `running/` namespace migration guardrail (flat files → refusal) | unit | `uv run pytest tests/backends/test_running_namespace.py::test_daemon_refuses_flat_running -x` | ❌ Wave 0 |
| BCK-05+06 | Log unification: `archive/<id>/run.log` exists for all backends | integration | `uv run pytest tests/backends/test_log_unification.py -x` | ❌ Wave 0 |
| BCK-04 | No process-control outside allowlist (slurm.py + ray.py) | lint | `python scripts/check_backend_isolation.py src/automil/` | ✅ (existing) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/backends/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green + `python scripts/check_backend_isolation.py src/automil/` exits 0 + `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero

### Wave 0 Gaps
- [ ] `tests/backends/conftest.py` — add `"slurm"` and `"ray"` to `params=` list
- [ ] `tests/backends/test_slurm_directives.py` — SLURM directive completeness tests
- [ ] `tests/backends/test_running_namespace.py` — namespace migration + guardrail tests
- [ ] `tests/backends/test_log_unification.py` — `archive/<id>/run.log` unification tests
- [ ] `tests/backends/test_node_0176_smoke.py` — acceptance smoke parametrised over [local, slurm-debug, ray-local]
- [ ] `tests/backends/test_contract_real_slurm.py` — `@pytest.mark.requires_slurm` (nightly only)
- [ ] `tests/backends/test_contract_real_ray.py` — `@pytest.mark.requires_ray` (nightly only)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — add `markers` entry for `requires_slurm`, `requires_ray`
- [ ] `pytest.ini` or `pyproject.toml` markers: `requires_slurm: requires SLURM cluster (skip in CI)`, `requires_ray: requires real Ray cluster (skip in CI)`

---

## Security Domain

> `security_enforcement: true` in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `automil check` validates SLURM directives for TODO-sentinel + required keys; `SlurmDirectivesIncompleteError` on failure |
| V6 Cryptography | no | — |

### Known Threat Patterns for {SLURM + Ray backends}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `spec.env` injection (passing arbitrary env to remote job) | Tampering | `_SPEC_ENV_BLOCKED` whitelist already in `_orchestrator_daemon.py` (D-04); `JobSpec.env` goes through this filter at creation time |
| SLURM job ID spoofing (attacker writes a fake `running/slurm/{id}.json` with malicious `opaque_id`) | Tampering | `opaque_id` is the SLURM job_id string (numeric); `submitit.Job(job_id=...)` calls `sacct` which validates against real SLURM state — spoofed IDs return unknown/empty state |
| Ray `RAY_ADDRESS` env poisoning (attacker sets `RAY_ADDRESS` to a malicious Ray head) | Tampering | `RayClusterUnreachableError` when cluster auth fails; backend-only, no framework secrets on the wire |
| Log file path traversal in `log_iter` | Information Disclosure | `node_id` is a hex slug from the graph; `automil submit` validates no `..` in node_ids (Phase 0 path validation) |

---

## Open Questions for the Planner

### 1. D-155 correction: `timeout_min` vs `time`, and `slurm_additional_parameters` for signal

**Current D-155:** `update_parameters(time=config[...]["time"], signal="B:TERM@30", ...)`
**Corrected API:**
```python
update_parameters(
    timeout_min=max(1, walltime_seconds // 60),   # was: time=...
    slurm_additional_parameters={"signal": "B:TERM@30"},  # was: signal="B:TERM@30"
)
```
The config key `backend.slurm.directives.time` can be repurposed as a `walltime_seconds` integer (or stored as a `timeout_min` integer). The planner should pick `walltime_seconds` (derived from `cap.budget_seconds` + grace buffer) as the canonical config key and compute `timeout_min = walltime_seconds // 60`.

### 2. D-174 correction: `ray.init(local_mode=True)` replacement

**Current D-174:** `config["backend"]["ray"]["local_mode"] = True` → `ray.init(local_mode=True)`
**Corrected approach:** `ray.init(ignore_reinit_error=True)` (no `local_mode`). The CI contract tests will use a real local Ray cluster (single node) rather than in-process. The conftest fixture must call `ray.shutdown()` in teardown if `_we_started_ray`.

**Consequence:** Ray CI tests are no longer truly in-process (they start a local Ray cluster). This is consistent with submitit's DebugExecutor which still does run in-process synchronously. The planner should document this asymmetry in the conftest comment.

### 3. D-164 correction: poll exception map must catch `WorkerCrashedError`

**Current D-164:** only catches `ray.exceptions.RayTaskError` and `ray.exceptions.TaskCancelledError`
**Corrected D-164:** also catch `ray.exceptions.WorkerCrashedError` (raised by `ray.cancel(force=True)`)

### 4. Worktree path propagation to SLURM/Ray workers

**Currently unclear:** how does `_run_experiment_subprocess(spec)` / `_run_experiment_ray(spec)` know the worktree path? LocalBackend creates the worktree via `runner.Runner` and passes the path in the env. For SLURM/Ray, the worktree must exist BEFORE the SLURM job starts (or be created by the remote function). The planner should specify: worktree is created by `SLURMBackend.submit()` / `RayBackend.submit()` in the calling process (same as LocalBackend), and the absolute path is passed to the remote function as part of `spec` (possibly a new field, or derived from `spec.overlay_dir`'s parent).

**Recommendation:** Add `worktree_path: Path` to the `_run_experiment_subprocess` / `_run_experiment_ray` function signature (not to `JobSpec` — which is already frozen and locked). The backend creates the worktree, passes the path explicitly.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `JobSpec` with `Path` fields pickles correctly in both submitit cloudpickle and Ray cloudpickle | Pitfall 7 | Low — cloudpickle handles stdlib Path; only risk is if Path objects contain non-serializable state |
| A2 | `_run_experiment_subprocess` / `_run_experiment_ray` creates the worktree inside the remote function | Open Question 4 | Medium — if worktree creation must happen in the calling process, the remote function needs a different interface |
| A3 | submitit DebugExecutor runs synchronously and blocks on `job.result()` (not asynchronous) | Pattern 1 | Low — confirmed by submitit source: `DebugJob.results()` directly calls `submission.result()` |
| A4 | `job.state` on a reconstructed `submitit.Job(folder, job_id)` correctly re-queries sacct | Pattern 3 | Low — submitit's design is to use folder+job_id as the full state reference; documented |
| A5 | `slurm_additional_parameters={"signal": "B:TERM@30"}` correctly injects `#SBATCH --signal=B:TERM@30` | Pitfall 1 | Medium — verified via submitit source that `additional_parameters` dict injects directly; unverified against specific SLURM version accepting `B:TERM@30` format |
| A6 | `ray.wait([ref], timeout=0)` is non-blocking and safe to call in the daemon tick (does not block) | Pattern 6 | Low — timeout=0 is standard Ray non-blocking pattern, confirmed by Context7 examples |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| submitit | SLURMBackend (`[slurm]` extra) | ✗ (not installed) | — | Not needed until `[slurm]` opt-in |
| ray | RayBackend (`[ray]` extra) | ✗ (not installed) | — | Not needed until `[ray]` opt-in |
| sbatch / scancel | SLURMBackend.submit on SLURM node | ✗ (dev machine) | — | DebugExecutor for CI (`cluster="debug"`) |
| sacct | submitit.Job.state | ✗ (dev machine) | — | DebugExecutor + mock state for CI |

**Missing dependencies with no fallback:** None that block development. Both backends have in-process CI simulation paths (DebugExecutor for SLURM; local `ray.init()` for Ray).

**Missing dependencies with fallback:** submitit/ray are extras — CI uses DebugExecutor and local Ray cluster respectively.

**Current test baseline:** 788 tests collected (confirmed via `uv run pytest --collect-only`). Phase 6 must stay green and add ≥10 new passing tests per backend (D-174/D-179).

---

## Sources

### Primary (HIGH confidence)
- Context7 `/facebookincubator/submitit` — AutoExecutor constructor, update_parameters, Job.done/wait/state, stdout/stderr paths, cluster parameter values
- Context7 `/ray-project/ray` — `@ray.remote`, `ray.wait`, `ray.cancel`, exception types, fractional GPU
- https://github.com/facebookincubator/submitit/blob/main/submitit/core/utils.py — `JobPaths.stdout` → `{job_id}_0_log.out` format
- https://github.com/facebookincubator/submitit/blob/main/submitit/auto/auto.py — AutoExecutor `cluster="debug"` runs in-process
- https://github.com/facebookincubator/submitit/blob/main/submitit/core/core.py — `Job(folder, job_id, tasks)` constructor for restart recovery
- https://docs.ray.io/en/latest/ray-core/api/doc/ray.init.html — `address="auto"` raises `ConnectionError`; `local_mode` "No longer supported"
- https://docs.ray.io/en/latest/ray-core/api/doc/ray.cancel.html — `force=True` raises `WorkerCrashedError`; `force=True` on Actor raises `ValueError`
- https://docs.ray.io/en/latest/ray-core/api/exceptions.html — complete exception class list

### Secondary (MEDIUM confidence)
- Web search: submitit `slurm_additional_parameters={"signal": "B:TERM@30"}` — multiple sources confirm this is the correct pass-through mechanism for SLURM-native directives not in AutoExecutor's shared param set
- https://github.com/ray-project/ray/issues/21850 — local_mode deprecation RFC confirming it was planned for deprecation in Ray 2.0

### Tertiary (LOW confidence)
- A5: `slurm_additional_parameters={"signal": "B:TERM@30"}` produces correct `#SBATCH --signal=B:TERM@30` output — inferred from submitit source pattern but not tested against a live SLURM cluster in this session

---

## Metadata

**Confidence breakdown:**
- submitit API surface: HIGH — verified against Context7 + source files
- Ray API surface: HIGH — verified against Context7 + official docs
- D-155 signal/time kwarg corrections: HIGH — source-verified
- D-159 log file path correction: HIGH — source-verified (JobPaths.stdout)
- D-165 `force=True` raises WorkerCrashedError: HIGH — official Ray docs verified
- D-174 `local_mode` deprecation: HIGH — official Ray 2.55 docs verified
- `slurm_additional_parameters` signal injection: MEDIUM — inferred from pattern, not tested live

**Research date:** 2026-05-06
**Valid until:** 2026-12-06 for submitit (stable API); 2026-08-06 for Ray (fast-moving, check for new deprecations at Ray 2.56+)
