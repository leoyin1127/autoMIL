# Phase 2: Backend ABC + LocalBackend re-export shim + MockSLURM fixture - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning
**Mode:** Engineering decisions locked per production best practice (Leo's directive 2026-05-02 — "decide engineering questions yourself; ask only user/feature questions"). Every decision below is a technical implementation choice; there are no open user/feature questions for Phase 2.

<domain>
## Phase Boundary

Land the **Backend abstraction layer** so Phase 6's SLURM/Ray work has a stable, well-tested contract to plug into — and so Phase 1's framework stays cleanly decoupled from local-process semantics.

After Phase 2:

1. **`Backend` ABC** lives at `src/automil/backends/base.py` with five operations: `submit(spec) → JobHandle`, `poll(handle) → JobState`, `list_running() → list[JobHandle]`, `cancel(handle, signal=None) → None`, `log_iter(handle) → Iterator[str]`. State-not-control-flow `JobState` enum surfaces `pending | running | completed | crashed | cancelled | budget_killed`.
2. **`LocalBackend`** ships as a re-export shim in `src/automil/backends/local.py`. The existing `src/automil/orchestrator.py` (1115 lines after Phase 0; ROADMAP's "750-line" estimate is stale) is **renamed to `_orchestrator_daemon.py`** and wrapped — zero behavioural drift; the existing 387-test suite (113 Phase 0 + 274 Phase 1) stays green.
3. **`MockSLURMBackend`** lives at `src/automil/backends/mock_slurm.py` (NOT under `tests/` — it doubles as a docs/example backend). Eventual-consistency status (configurable `poll_lag_seconds`, default 5.0); opaque `job_id`; fire-and-forget `cancel`; node-local fixture filesystem.
4. **Shared parameterised contract test** `tests/backends/test_contract.py` exercises the same scenarios against both backends (submit→poll-until-terminal, mid-run cancel, list_running consistency, log_iter terminal close, restart recovery). The ABC is **locked only after** the contract suite passes against both — defending Phase 2 anti-acceptance pitfall ("designing against one impl freezes its semantics").
5. **Lint enforcement** — a tiny AST walker (`scripts/check_backend_isolation.py`) rejects `os.kill | Popen | os.killpg | .pid` references outside `backends/local.py` and `backends/_orchestrator_daemon.py`. Wired as a pre-commit hook AND a CI assertion (BCK-04). Ruff is the wrong tool for this — it polices warning categories, not regex AST forbids — so a 60-line custom script is the production-grade choice.
6. **`automil cancel <node_id>`** + **`automil resubmit <node_id>`** route through `Backend.cancel()` / `Backend.submit()`. Cancelled nodes archive with `status: cancelled`; resubmits get a fresh worktree and new node_id (with `metadata.resubmitted_from = <old_node_id>` for traceability).

**Hard floors:**

- Phase 0+1 baseline (387 tests) stays green — `LocalBackend` is behaviourally identical to current `orchestrator.py`.
- Contract test passes against both `LocalBackend` AND `MockSLURMBackend` (≥10 parameterised scenarios per backend).
- `python scripts/check_backend_isolation.py` reports zero out-of-place `os.kill | Popen | .pid | os.killpg` references in `src/automil/`.
- `automil cancel` + `automil resubmit` work end-to-end on `MockSLURMBackend` against a synthetic graph fixture.
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero — backends are framework-only by construction.

**Wave-cadence target:** ~7–9 plans across 5 waves. Granularity `fine`. Dependency shape: ABC + dataclasses → (LocalBackend shim ‖ MockSLURMBackend) → contract test + lint script → cancel/resubmit CLI → acceptance gate.

</domain>

<decisions>
## Implementation Decisions

> **Numbering:** D-51 onward continues from Phase 1's D-21..D-50. Each decision is a locked engineering choice; downstream agents (researcher, planner, executor) honour these verbatim.

### Backend abstraction shape (BCK-01)

- **D-51:** Three modules under a new `src/automil/backends/` package:
  ```
  src/automil/backends/
    __init__.py                 # public surface re-exports + BACKENDS registry
    base.py                     # Backend ABC + JobSpec + JobHandle + JobState
    local.py                    # LocalBackend (wraps _orchestrator_daemon)
    mock_slurm.py               # MockSLURMBackend (fixture + docs example)
    _orchestrator_daemon.py     # current orchestrator.py renamed; ONLY local.py imports it
  ```
  `src/automil/orchestrator.py` becomes a thin **module-level re-export** for backward compat (existing `from automil.orchestrator import ExperimentOrchestrator` continues to resolve), with a `# DEPRECATED:` banner pointing to `automil.backends`.

- **D-52:** `JobHandle` is a **frozen dataclass** in `backends/base.py`:
  ```python
  @dataclass(frozen=True)
  class JobHandle:
      node_id: str          # autoMIL graph node_id (framework-owned)
      backend: str          # backend name, e.g. "local", "mock_slurm"
      opaque_id: str        # backend-internal id (PID for local, fake "1234.0" for mock_slurm)
      submitted_at: float   # unix epoch seconds
  ```
  `JobHandle` is hashable + JSON-serialisable (via `dataclasses.asdict`). It carries no live process objects, no file handles, no signal state — backends look up rich state via `opaque_id`. Frozen because handles are passed across the daemon/CLI boundary and must not mutate.

- **D-53:** `JobState` is a `str`-valued `Enum` (JSON-safe, comparable):
  ```python
  class JobState(str, Enum):
      PENDING       = "pending"
      RUNNING       = "running"
      COMPLETED     = "completed"
      CRASHED       = "crashed"
      CANCELLED     = "cancelled"
      BUDGET_KILLED = "budget_killed"
  ```
  Six values exhaust Phase 2 + forward-looking Phase 4 (`BUDGET_KILLED`). State is **status-not-control-flow**: backends report state, the framework owns transitions and routing logic. `BUDGET_KILLED` is reserved for Phase 4's two-tier cap; Phase 2 backends never produce it (would be returned by the cap-enforcement layer wrapping `Backend.cancel(signal=SIGTERM)`).

- **D-54:** `JobSpec` is a frozen dataclass — the input to `submit()`:
  ```python
  @dataclass(frozen=True)
  class JobSpec:
      node_id: str
      base_commit: str               # short SHA the worktree checks out
      overlay_files: tuple[str, ...] # file paths under the overlay (relative to overlay_dir)
      overlay_dir: Path              # archive/<node_id>/ holding the overlay snapshot
      command: tuple[str, ...]       # argv for the experiment process (e.g. ("python", "train.py"))
      env: tuple[tuple[str, str], ...]  # whitelisted env additions (ordered for determinism)
      working_subdir: str            # subdirectory of the worktree to chdir into
      gpu_estimate_gb: float         # for backend-side packing (LocalBackend uses this; SLURM ignores)
      walltime_seconds: int          # framework's wall-clock contract
  ```
  Frozen + tuple types so the spec is hashable and serialisable to `running/<node_id>.json`. `gpu_estimate_gb` is advisory (LocalBackend respects it for bin-packing; SLURM/Ray map to their own `--gpus` directives).

### Per-operation contract (BCK-01)

- **D-55:** `submit(spec: JobSpec) → JobHandle` is **eventually-consistent**: a fresh handle may transition `pending → running` after a backend-defined lag. Backends do NOT block on actual job start. LocalBackend's lag is effectively zero (`Popen` returns immediately with `process.pid`); MockSLURM simulates 5s. Caller responsibility: poll until terminal.

- **D-56:** `poll(handle: JobHandle) → JobState` is **a snapshot, never blocking**. May return `pending` for several poll cycles after `submit` on eventually-consistent backends. Idempotent — calling `poll` does not advance the job, only reports its current state.

- **D-57:** `cancel(handle: JobHandle, signal: Optional[int] = None) → None` is **fire-and-forget**. Default `signal=None` means "use the backend's standard cancel" (SIGTERM for local with 30s grace then SIGKILL; `scancel` for SLURM; `ray.cancel(force=True)` for Ray). Custom `signal` is local-backend-specific and ignored by SLURM/Ray (with a one-time logged warning, not an exception — defending Pitfall 2 by explicitly accepting the divergence in the ABC contract). State transition to `CANCELLED` is observed via subsequent `poll()` calls — `cancel` itself returns `None` immediately.

- **D-58:** `log_iter(handle: JobHandle) → Iterator[str]` yields lines as available; the iterator closes when the job reaches a terminal state (`completed | crashed | cancelled | budget_killed`). LocalBackend tails the live log file (`tail -f` semantics). MockSLURM returns the entire collected log on completion (simulates SLURM's stdout-on-completion model). For `pending | running` states with no log content yet, the iterator may block briefly but MUST surface lines within ~1s of them appearing (no infinite buffering). LocalBackend is test-friendly: yields with a 0.1s tick.

- **D-59:** `list_running() → list[JobHandle]` is the **backend's source of truth for live jobs**. It is restart-safe: a fresh `Backend()` instance can recover the live set by reading on-disk state. LocalBackend reads `running/<id>.json` files written at submit time. MockSLURM persists in-process state to `mock_slurm_state.json` (test fixture; survives backend restart in the same test). Daemon recovery (Phase 0's `_recover_orphans`) calls `list_running()` to repopulate state.

### LocalBackend shim (BCK-02)

- **D-60:** `LocalBackend` is **a re-export shim**, not a rewrite. Concretely:
  - `src/automil/orchestrator.py` is renamed to `src/automil/backends/_orchestrator_daemon.py` (the ONLY internal module allowed to use `Popen | os.kill | .pid | os.killpg` per BCK-04).
  - `src/automil/backends/local.py` defines `class LocalBackend(Backend)`. Each method is a **thin call** into `_orchestrator_daemon.py`'s existing class methods (`ExperimentOrchestrator._launch_experiment`, `_kill_experiment`, etc.).
  - `src/automil/orchestrator.py` becomes a 5-line re-export shim: `from automil.backends._orchestrator_daemon import *  # noqa: F401, F403` + a deprecation comment block. Every existing `from automil.orchestrator import X` import path keeps working — Phase 0's compat.py philosophy applies.
  - The 387-test suite is the contract: zero edits to existing tests required; if a test breaks, the shim is wrong.

- **D-61:** `LocalBackend.__init__` takes **the same arguments** as today's `ExperimentOrchestrator.__init__` (`project_root`, `automil_dir`). Internally it instantiates `ExperimentOrchestrator` and stores it as `self._daemon`. Methods delegate. Reasoning: any change to the constructor signature is a behavioural change = forbidden in Phase 2.

### MockSLURMBackend (BCK-03)

- **D-62:** `MockSLURMBackend` simulates eventual-consistency SLURM behaviour for the contract test, NOT a real SLURM. Constructor takes `poll_lag_seconds: float = 5.0`, `state_file: Optional[Path] = None`. Behaviour:
  - `submit()` writes a `pending` entry to in-memory state + (optionally) `state_file`. Returns `JobHandle(opaque_id=f"{counter}.0")`. Spawns a **threading.Timer** that after `poll_lag_seconds` flips state to `running`, runs the command (or a stub), then flips to `completed | crashed`.
  - `poll()` reads state without touching the timer — pure snapshot.
  - `cancel()` requests cancellation; the Timer thread observes the flag at next tick and transitions to `cancelled`. Fire-and-forget — `cancel` returns immediately.
  - `log_iter()` returns the full collected stdout buffer once the job reaches a terminal state; yields nothing while `pending | running` (matches SLURM's log-on-completion model).
  - `list_running()` returns handles for all jobs in `pending | running`.
  - Restart simulation: instantiating a fresh `MockSLURMBackend(state_file=...)` reads `state_file` and resumes the live set.

- **D-63:** MockSLURM does NOT actually execute the command. Its job-execution stub returns a deterministic `result.json`-equivalent payload determined by `JobSpec.command` content (e.g., a command containing `"sleep"` finishes after `poll_lag_seconds * 2`; a command with `"--crash"` produces a crashed terminal state). This keeps the contract test fast (target: full suite under 10s wall-clock) while still exercising the state machine.

### Lint enforcement (BCK-04)

- **D-64:** Lint script lives at `scripts/check_backend_isolation.py` — a **plain `ast.NodeVisitor`-based** AST walker, NOT a ruff plugin or mypy plugin. ~80 lines. Walks every `src/automil/**/*.py` and reports any `Attribute` access of the form `os.kill | os.killpg | os.getpid` and any `Name` reference to `Popen | subprocess.Popen` and any `Attribute` access ending in `.pid` (modulo `attr_name == 'pid'`). Allowlist: `backends/local.py`, `backends/_orchestrator_daemon.py`. Exit 0 if all references are inside the allowlist; exit 1 otherwise with file:line diagnostics.

- **D-65:** Wired as **both** a pre-commit hook (`.pre-commit-config.yaml`) AND a pytest test (`tests/test_backend_isolation_lint.py::test_no_process_control_outside_allowlist`). The pytest test is the production-grade enforcement — pre-commit is optional convenience.

  Reasoning: Ruff custom rules require a Rust extension (out of scope); ruff `select`/`ignore` is for warning categories, not regex AST forbids; mypy plugins are heavyweight and slow. A 80-line stdlib-only AST script is exactly right for this — explicit, fast, version-controlled, debuggable.

### CLI commands (CLI-03, CLI-04)

- **D-66:** `automil cancel <node_id>` lives at `src/automil/cli/cancel.py` (Phase 0's CLI split pattern). Workflow:
  1. Look up `node_id` in `graph.json`. Hard-fail if unknown (per Phase 1 PATTERNS.md §7).
  2. If node status is not `running`, hard-fail with "Refusing to cancel: node {id} is in state {state}, not 'running'."
  3. Read `node.metadata.backend` (defaults to `"local"` for legacy nodes); resolve via `backends.BACKENDS[name]`.
  4. Reconstruct `JobHandle` from `node.metadata.{opaque_id, submitted_at}` (persisted at submit time).
  5. Call `backend.cancel(handle)`.
  6. Wait up to 30 seconds polling for state transition to `CANCELLED`. If timeout, exit non-zero with diagnostics (state didn't transition; operator must investigate).
  7. Update graph node atomically: `status: cancelled`, `cancelled_at: <iso8601>`, `cancel_reason: "cli"`.
  8. Move `running/<node_id>.json` → `archive/<node_id>/`.

- **D-67:** `automil resubmit <node_id>` lives at `src/automil/cli/resubmit.py`. Workflow:
  1. Look up `node_id`; hard-fail if not in terminal state (`completed | crashed | cancelled`).
  2. Read the archived overlay from `archive/<node_id>/`.
  3. Generate **a new** `node_id` (graph-assigned). DO NOT reuse the old one.
  4. Build `JobSpec` from the archived overlay + new node_id.
  5. Call `backend.submit(spec)`.
  6. Insert new node with `parent_id = <old_node>.parent_id`, `metadata.resubmitted_from = <old_node_id>`.
  7. Print new node_id to stdout for operator capture.

  **Not** a re-run of the same id — that would corrupt graph history. Resubmit is "spawn a sibling with the same overlay."

### Backend registry + discovery

- **D-68:** Backend registry follows Phase 1's variant-registry pattern: a module-level `BACKENDS: dict[str, type[Backend]]` in `backends/__init__.py`, populated via `@Backend.register(name)` decorator. `automil/config.yaml: backend.name = "local"` (default) selects the active backend at runtime. SLURM/Ray plug in via `from automil_slurm import SLURMBackend` import in Phase 6 (extras-installed).

- **D-69:** Phase 2 ships ONE production backend (`local`) and ONE test backend (`mock_slurm`). `mock_slurm` is registered but NOT auto-imported in the public surface — `automil/config.yaml: backend.name = "mock_slurm"` works only after `import automil.backends.mock_slurm` happens (which the contract test does explicitly). Reasoning: a test fixture leaking into production config selection would be a UX trap.

### Acceptance gate (BCK-01..04, CLI-03/04)

- **D-70:** Phase 2 acceptance is the conjunction of:
  1. `tests/backends/test_contract.py` passes against `LocalBackend` AND `MockSLURMBackend` via parameterisation. Scenarios (≥10): submit-poll-completed, submit-poll-crashed, mid-run cancel, list_running pre/post submit, list_running pre/post terminal, log_iter terminal-close, restart recovery, eventual-consistency lag, fire-and-forget cancel timing, opaque_id uniqueness.
  2. Existing 387-test suite (Phase 0+1) stays green — `LocalBackend` is a behavioural identity over `_orchestrator_daemon`.
  3. `python scripts/check_backend_isolation.py` exits 0 on `src/automil/`.
  4. `pytest tests/test_backend_isolation_lint.py` passes.
  5. `automil cancel` + `automil resubmit` integration test (`tests/test_cli_cancel_resubmit.py`) drives end-to-end against MockSLURM + a synthetic graph.json — covers happy path + state-machine edge cases.
  6. `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns zero matches.

### Submit-path integration (closes researcher's open questions)

- **D-76:** `cli/submit.py` is **extended** in Phase 2 to write `metadata.backend = "<name>"` (read from `automil/config.yaml: backend.name`, default `"local"`) into the `queue/<id>.json` spec at submit time. This is a 3-line addition to `cli/submit.py`. The framework needs `metadata.backend` on every node so `cancel.py` and `resubmit.py` know which backend's `BACKENDS[name]` to dispatch to.

  `metadata.opaque_id` is NOT written at submit time (the daemon doesn't know the PID until it launches the process). It is written by the daemon into `running/<id>.json` when `_launch_experiment` returns. `cancel.py` reads `running/<id>.json` to reconstruct the `JobHandle`.

  **Backward compat:** legacy nodes without `metadata.backend` are treated as `"local"` (the only backend that existed before Phase 2). `cancel.py` and `resubmit.py` apply this default with a one-line fallback, no migration script needed.

- **D-77:** `LocalBackend.submit(spec)` **writes to `queue/<id>.json`** — preserves the existing daemon-pickup model. Returns a `JobHandle(opaque_id="pending")` that the daemon updates to the real PID on launch. `LocalBackend.poll(handle)` reads `running/<id>.json` (running) or `archive/<id>/result.json` (terminal) to surface state — these are the daemon's source of truth.

  This makes `LocalBackend` a **thin protocol adapter** over the daemon's existing on-disk state machine, NOT a re-implementation of the lifecycle. No daemon-mocking infrastructure needed for tests; `LocalBackend.submit` works against a real (but synthetic-fixture-scoped) daemon directory.

  MockSLURM owns its own state machine (in-memory + optional `state_file`). The two backends share NO on-disk state.

### Out of scope (Phase 2)

- **D-71:** Real SLURM/Ray backends — Phase 6.
- **D-72:** Per-backend `running/<id>.json` namespacing (`running/local/`, `running/slurm/`, `running/ray/`) — Phase 6, when multi-backend coexistence becomes real.
- **D-73:** Wall-clock contract (the 30s grace + budget-killed transition) — Phase 4. Phase 2's `cancel(signal)` accepts a custom signal but the budget-kill orchestration is the cap layer's job, not the backend's.
- **D-74:** Trajectory hooks — Phase 3.
- **D-75:** Hardware healthcheck — Phase 7.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § Phase 2 (success criteria 1–5)
- `.planning/REQUIREMENTS.md` BCK-01..04, CLI-03, CLI-04
- `.planning/PROJECT.md` § Key decisions (pluggable orchestrator)

### Existing framework code (the shim wraps these)
- `src/automil/orchestrator.py` (1115 lines) — current local orchestrator; rename target
- `src/automil/runner.py` (95 lines) — git worktree manager; backends call into it
- `src/automil/cli/__init__.py` — Click main group; cancel.py + resubmit.py register here
- `src/automil/cli/submit.py` — submit pathway; resolves which backend to use

### Phase 1 patterns (continue them)
- `.planning/phases/01-…/01-PATTERNS.md` § 1 "CLI command file organization"
- `.planning/phases/01-…/01-PATTERNS.md` § 3 "Atomic write for state mutations"
- `.planning/phases/01-…/01-PATTERNS.md` § 7 "ClickException error format"

### Anti-pattern reference
- `.planning/research/PITFALLS.md` § Pitfall 2 — leaky backend ABC (designing against one impl)
- `.planning/codebase/CONCERNS.md` § "PID-file stale-detection" — the `os.kill | .pid` surface BCK-04 isolates

</canonical_refs>

<specifics>
## Specific Ideas

- **Renaming `orchestrator.py` → `_orchestrator_daemon.py`** is a `git mv` so blame history is preserved. Phase 0's compat shim approach is the precedent: keep the old import path resolving via re-export (`src/automil/orchestrator.py` becomes 5 lines).
- **MockSLURM's `poll_lag_seconds` default of 5.0** matches the SLURM `sacct` cache lag in real clusters. Tests that need faster runs pass `poll_lag_seconds=0.05`.
- **`JobState.BUDGET_KILLED`** is reserved in Phase 2 but unused — defends Phase 4's contract by making the value already part of the public surface, so Phase 4 doesn't have to widen the enum (= API churn).
- **Synthetic graph fixture** for cancel/resubmit tests can be a copy of the Phase 1 synthetic-consumer pattern (`tests/fixtures/`) — pre-populated `graph.json` with one running node, one completed node, one crashed node.
- **Pre-commit hook** is opt-in (`pre-commit install` to enable). The pytest test in `tests/test_backend_isolation_lint.py` is the always-on enforcement.

</specifics>

<deferred>
## Deferred Ideas

- **Real SLURM backend** (`backends/slurm.py` via `submitit>=1.5.3`) — Phase 6.
- **Real Ray backend** (`backends/ray.py` via raw `ray.remote`) — Phase 6.
- **Per-backend `running/` namespacing** (`running/local/`, `running/slurm/`) — Phase 6.
- **`Backend.healthcheck()` method** on the ABC — Phase 7 (`STP-01`); Phase 2's ABC is intentionally minimal (5 methods) so Phase 7 can extend cleanly.
- **Trajectory hooks on submit/cancel** — Phase 3 (TRJ-01).
- **Cap-layer `BUDGET_KILLED` orchestration** — Phase 4. The state value is reserved; the cap-fires-cancel-with-budget-flag flow is Phase 4 work.

</deferred>

---

*Phase: 02-backend-abc-localbackend-re-export-shim-mockslurm-fixture*
*Context bootstrapped autonomously 2026-05-02 per Leo's "decide engineering, ask features" directive. No open questions for Leo at planning time.*
