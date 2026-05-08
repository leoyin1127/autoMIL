# Changelog

autoMIL — F2-readiness framework refactor

## 8.0.0 - Phase 8 decoupling completion + final acceptance (unreleased)

### BREAKING: `env.required` is now mandatory in `automil/config.yaml`

`automil check` fails with `Missing required env var: <name>` if any var
declared under `env.required` is unset in the orchestrator's environment. This
catches missing dataset paths (e.g. AUTOBENCH_CCRCC_ROOT) BEFORE submit
rather than deep inside the training script.

**Operator recovery (F-06 / Iter-2 explicit migration):** after upgrading,
add an `env:` block to your existing `automil/config.yaml`. The 4-cell
matrix (env.required vs env.passthrough x example values vs sentinel) is
resolved as follows: `required` and `passthrough` each receive concrete
example values; consumers fill in the actual list or remove vars they do
not use. Concrete autobench-shaped recovery snippet:

```yaml
env:
  required:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    # add any env var your training script reads at startup
  passthrough:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    - HF_HOME  # if you cache HF models
    # remove from passthrough any var not needed in subprocess env
```

The `passthrough` list controls which env vars are forwarded into experiment
subprocesses; the `required` list is what `automil check` enforces at startup.
For sklearn-iris-style generic consumers with no env-var dependencies, both
lists are empty (`required: []`, `passthrough: [AUTOMIL_*]`).

### BREAKING: `node["test_auc"]` etc no longer at top level

The graph.json node payload migrates the autobench-named metrics
(`val_auc`, `val_bacc`, `test_auc`, `test_bacc`) from top-level fields into a
generic `node["metrics"]` dict. This removes the framework's hardcoded coupling
to autobench's 4-key composite recipe and unblocks non-autobench consumers
(e.g. sklearn-iris).

**Operator recovery:** if you have custom code reading `node["test_auc"]`
directly from graph.json, change to `node["metrics"]["test_auc"]`. The
framework's own viz dashboard and CLI surfaces are migrated. The cap-killed
reconcile branch in `_orchestrator_daemon.py` is also migrated (Iter-2 / F-03);
all node-write sites in the framework now share homogeneous storage shape.

### BREAKING: AUTOBENCH_ROOT no longer auto-injected into experiment env

The orchestrator no longer auto-injects `AUTOBENCH_ROOT` or overlays
`PYTHONPATH` to point at `benchmarks/`. Consumers that need these vars
declare them under `env.passthrough` per the recovery snippet above.

### Added

- `src/automil/schemas/result.schema.json` (D-201, JSON Schema 2020-12)
  describing the `result.json` contract. Validated at ingestion via
  `jsonschema.validate(...)`. Malformed payloads transition the node to
  `crashed` with a pointer to the schema.
- `examples/sklearn-iris/` directory with a ~75-line `train.py` demonstrating
  the contract on a non-autobench consumer.
- `docs/training-script-contract.md` (DEC-06) documenting the 6 contract items.
- `tests/test_framework_purity.py` (D-206) regression-prevents autobench
  leakage in `src/automil/`.
- `tests/acceptance/test_final_phase8_acceptance.py` (D-205) final 3-sub-gate
  acceptance gate. Sub-gate B drives the full submit + orchestrator subprocess
  path so the daemon ingest validate hook is exercised end-to-end (F-04).
- `tests/acceptance/test_phase8_acceptance.py` (D-208) 11-clause acceptance
  aggregator.
- `automil/config.yaml: scoring.formula` field surfaced in the framework
  template `config.yaml.j2` per DEC-04 ROADMAP success criterion 3 (F-07).
  Documentation-only field; consumers describe their composite recipe.

### Verification

Phase 8 is complete when `uv run pytest tests/acceptance/test_phase8_acceptance.py -v`
reports all 11 D-208 clauses PASS (or SKIP cleanly for the 2 data-gated
sub-gates when AUTOBENCH_CCRCC_ROOT is unset).

### Compatibility

- Pre-D-200 graph.json files round-trip via the bootstrap loader; explicit
  schema_version bump deferred (forward-compatible cleanup).
- `pyproject.toml` adds `requires_ccrcc_data` marker. CI default filters
  `not requires_ccrcc_data and not requires_slurm and not requires_ray`.
- `jsonschema` is no new top-level dep; transitive since Phase 5.

## 7.0.0 - Phase 7 hardware autodetect + automil-setup skill (unreleased)

### BREAKING: `Backend.healthcheck` is now an abstract method

Subclasses without a concrete `healthcheck` implementation are uninstantiable
(`TypeError: Can't instantiate abstract class ... with abstract method healthcheck`).

- **`LocalBackend`** implements it (probes hardware via `nvidia-smi` /
  `rocm-smi` / CPU-only fallback per D-190).
- **`SLURMBackend`** and **`RayBackend`** raise `NotImplementedError` with the
  locked message
  `"healthcheck deferred to Phase 7+ for distributed backends (use salloc/ray status directly)"`
  (D-189). Distributed-cluster healthcheck is deferred to a post-v1.0 phase.
- **`MockSLURMBackend`** raises the same `NotImplementedError` for test-fixture parity.

**Operator recovery:** if you maintain a custom Backend subclass outside this
repo, add a `healthcheck` method that returns a `HealthReport` (or raises
`NotImplementedError` with the locked message above for distributed backends).

### Added

- `Backend.healthcheck() -> HealthReport` method on the Backend ABC (D-189 / STP-01).
  `LocalBackend` implements it via `nvidia-smi` (CUDA), `rocm-smi` (ROCm), or
  CPU-only fallback. Detection failures surface via `detection_status='failed'`.
- `automil init` calls `LocalBackend.healthcheck()` between the `--update` guard
  and template render. Detected values flow into `automil/config.yaml`'s `cap:`
  and `hardware:` sections (D-191 / STP-02).
- `automil init --no-healthcheck` flag for CI / smoke-test paths.
- `automil submit --max-time SECONDS` flag for seconds-precision timeouts (D-195).
  `--timeout MINUTES` is preserved verbatim; when both are passed, `--max-time` wins.
- `_shared/automil-setup/SKILL.md` expanded from the 122-line skeleton to ~250
  lines covering Inspection Heuristics, Drafting Conventions, Idempotency
  Protocol, Setup-Done Gate, and Failure Modes (D-192..D-196 / STP-04..06).
- `agent_assets/codex/skills/automil-setup/SKILL.md` empty-frontmatter overlay
  for Codex plain-markdown rendering (D-196 / STP-07 / Pitfall D).

### Fixed

- `automil init`'s template render now stamps detected hardware defaults
  (`max_concurrent_per_gpu`, `default_vram_estimate_gb`) instead of the prior
  hardcoded constants. Per the Pitfall 8 anti-acceptance, `default_vram_estimate_gb`
  is computed from `numpy.quantile(.95)` of empirical `vram_gb` observations in
  `automil/results.tsv` when at least 10 rows are present, and from
  `max(8.0, min(gpu_vram_gb) / 8.0)` otherwise.

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
