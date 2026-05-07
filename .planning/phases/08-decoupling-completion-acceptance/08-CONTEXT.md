# Phase 8: Decoupling completion + final acceptance, Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Mode:** Auto-bootstrapped per Leo's standing directive `feedback_decide_engineering_ask_features` (engineering decisions locked autonomously per production best-practice; only feature/user decisions go to Leo).

## Phase Boundary

Phase 8 is the milestone-acceptance phase. Three workstreams converge:

1. **Decoupling cleanup** (DEC-01, DEC-03, DEC-04, DEC-05): purge autobench leakage from `src/automil/`, ship config-driven composite scoring with JSON-Schema validation, declare and validate required env vars in config.
2. **Second consumer proof** (DEC-02): plug a sklearn-iris training script into autoMIL via the documented contract; run an experiment loop end-to-end.
3. **Contract documentation** (DEC-06) + **final acceptance** (DEC-07): write `docs/training-script-contract.md`; final acceptance gate = clean checkout, registry path, fresh worktree, all phases composed produce CCRCC `node_0176` reproduction within +-0.005 AND sklearn-iris consumer end-to-end.

**Out of scope:** Multi-language consumers (R, Julia); composite-formula DSL beyond simple weighted-sum; AutoML metric selection; CCRCC dataset re-curation; sklearn dataset selection beyond iris.

<decisions>
## Implementation Decisions

### D-199, autobench-leakage purge surface (DEC-01)

Concrete autobench refs found in `src/automil/`:

- `backends/_orchestrator_daemon.py:54`: comment about consumer-specific vars (informational, ASCII-only, retain but soften wording)
- `backends/_orchestrator_daemon.py:718-780`: AUTOBENCH_ROOT env injection block + PYTHONPATH manipulation (PURGE)
- `cli/lifecycle/verify_repro.py:84`: comment about AUTOBENCH_ leakage (informational, retain)

**Resolution:**

- The `AUTOBENCH_ROOT` env injection block (`_orchestrator_daemon.py:718-721`) and PYTHONPATH manipulation block (`_orchestrator_daemon.py:777-780`) are REMOVED. Replaced by a generic env-passthrough mechanism that reads `automil/config.yaml: env.passthrough` (D-202).
- Consumer-side `benchmarks/src/autobench/` may set `AUTOBENCH_*_ROOT` via its own `.env` propagation (Phase 0 dotenv loader); the framework does NOT inject them.
- `verify_repro.py:84` comment is retained as historical note (one ASCII line, no AUTOBENCH_ value reference).

**Acceptance grep:** `grep -rE "AUTOBENCH_" src/automil/ | grep -v "^Binary file"` returns at most 2 matches (both informational comments).

### D-200, config-driven composite scoring (DEC-04)

Current state: `graph.py` hardcodes `val_auc`/`val_bacc`/`test_auc`/`test_bacc` field copying from `metrics` to node payload (lines 134-135, 212-213, 564-565, 619-620, 697-698). The framework reads `metrics["composite"]` directly (consumer writes the scalar in `result.json`). The leakage is the **named-field copy**, not the composite computation itself.

**Resolution:**

- `graph.py` stores ALL metric keys on the node via `node["metrics"] = dict(metrics)` (full dict spread), instead of named-field copy. Existing `node["composite"]`, `node["parent_delta"]`, `node["best_composite"]` stay (they are framework-owned).
- Consumers that emit `{val_auc, val_bacc, ...}` keep their viz/CLI reads working through `node["metrics"]["val_auc"]`. Generic consumers (sklearn-iris) emit `{accuracy: 0.97}` and the framework treats it identically.
- `automil/config.yaml: scoring.formula` is OPTIONAL config that documents the consumer's composite recipe (e.g., `(val_auc + val_bacc + test_auc + test_bacc) / 4` for autobench, `accuracy` for sklearn-iris). Framework does NOT compute composite; consumer's training script writes `composite` scalar to `result.json`. Config exists for documentation + JSON-Schema validation hints only.
- D-04 result.json schema (Phase 0) extended in D-201 to require: `composite: float`, `metrics: dict[str, float]`, optional `status`, `elapsed_seconds`, `peak_vram_mb`. JSON-Schema-validated at ingestion (D-201).

**Why dict spread, not allowlist:** allowlists couple framework to consumer's field names. Dict spread keeps framework agnostic; viz/CLI consumers know their own metric names.

**Why scoring.formula stays optional:** the composite is consumer-computed; framework does not re-evaluate. Adding formula DSL evaluation invites injection bugs and complicates schemas. Keep it as documentation.

### D-201, result.json JSON-Schema validation (DEC-03)

`automil/schemas/result.schema.json` is added with this contract:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["composite"],
  "properties": {
    "composite": {"type": "number"},
    "metrics": {"type": "object", "additionalProperties": {"type": "number"}},
    "status": {"type": "string", "enum": ["completed", "crash", "budget_killed", "cancelled"]},
    "elapsed_seconds": {"type": "number", "minimum": 0},
    "peak_vram_mb": {"type": "number", "minimum": 0},
    "fold_results": {"type": "array"},
    "partial": {"type": "boolean"}
  },
  "additionalProperties": true
}
```

`additionalProperties: true` is intentional, consumers may add fields the framework does not interpret.

`graph.py` validates `result.json` at ingestion via `jsonschema.validate(...)`. On `ValidationError`, the orchestrator transitions the node to `crashed` with `error: result.json failed schema validation: <detail>; see automil/schemas/result.schema.json`. Schema location is surfaced in the error message so consumers can self-correct.

`jsonschema` is already a transitive dep (Phase 5 used it for `gate_manifest.json`); no new top-level dependency.

### D-202, env.required + env.passthrough validators (DEC-05)

`automil/config.yaml: env.required` is a list of env var names that MUST be set at startup. Example:

```yaml
env:
  required:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
  passthrough:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    - HF_HOME
```

`required`: validated by `automil check`; missing var fails `check` with explicit name.
`passthrough`: env vars that the orchestrator copies from parent process into experiment subprocess env (replacing the hardcoded `AUTOBENCH_ROOT` injection from D-199). Empty by default.

`automil check` walks `env.required`; for each missing var, emits a clear error `Missing required env var: <name>; see automil/config.yaml: env.required`. Exit non-zero on any miss.

The orchestrator's subprocess env construction reads `env.passthrough`, copies matching keys from `os.environ`, ignores unset keys silently (the `required` validator catches genuinely-missing-and-required ones earlier).

### D-203, sklearn-iris second consumer (DEC-02)

Consumer location: `examples/sklearn-iris/` (NEW directory; sibling of `benchmarks/`). Structure:

```
examples/sklearn-iris/
├── automil/
│   ├── config.yaml         # generic consumer config; no AUTOBENCH_*
│   ├── program.md          # narrative
│   └── variants/
│       └── classifier_v0/
│           └── logistic_v0.py  # starter variant
├── train.py                # MINIMAL training script: load_iris, fit, eval, write result.json
└── README.md
```

`train.py` is ~80 lines: load iris → train_test_split → fit LogisticRegression → predict → compute accuracy → write `{"composite": acc, "metrics": {"accuracy": acc, "f1": f1}, "status": "completed"}`. Must honor:

1. CUDA_VISIBLE_DEVICES (no-op for CPU-only sklearn but accept the env var)
2. SIGTERM clean exit (write partial result.json on signal)
3. result.json contract per D-201 schema

Consumer config: `automil/config.yaml` declares `env.required: []` (sklearn needs no env), `env.passthrough: []`, `scoring.formula: "accuracy"` (documentation only).

End-to-end smoke test: `tests/examples/test_sklearn_iris_consumer.py` runs `automil submit --node iris_001 --files examples/sklearn-iris/train.py --max-time 60` against tmp project; asserts terminal state == `executed` and composite ~0.95.

### D-204, training-script contract documentation (DEC-06)

`docs/training-script-contract.md` (NEW) documents what a training script must do:

1. **Read config** at `automil/config.yaml` (or honor `--config` flag)
2. **Honor `CUDA_VISIBLE_DEVICES`** for GPU masking
3. **Honor `AUTOMIL_GPU=N`** logical-device index passed by orchestrator
4. **Exit cleanly on SIGTERM** with partial-fold output written to result.json (`status: budget_killed`, `partial: true`)
5. **Write `result.json`** matching `automil/schemas/result.schema.json`
6. **Declared env vars** (in `automil/config.yaml: env.required`) ARE present at startup, validated by `automil check` before submit

Document is markdown only (no code generation). Includes:

- Minimal sklearn-iris example (cross-link to D-203's train.py)
- Minimal pytorch example (5-line skeleton)
- SIGTERM handling pattern (signal.signal + atexit)
- Common pitfalls (writing result.json AFTER cleanup; using sys.exit(0) without writing partial)

### D-205, final acceptance gate (DEC-07)

The Phase 8 final acceptance gate runs in CI as a single test file `tests/acceptance/test_final_phase8_acceptance.py`:

**Sub-gate A (CCRCC reproduction):** clean checkout (tmp dir + `git clone . tmp/`), `automil refresh-registry`, `automil submit --node node_0176 --no-headlines`, run via real LocalBackend, assert composite within +-0.005 of 0.502 (Phase 1 D-50 baseline).

**Sub-gate B (sklearn-iris end-to-end):** same harness, `automil submit --node iris_001 --files examples/sklearn-iris/train.py --max-time 60`, assert terminal state `executed` AND composite >= 0.90.

**Sub-gate C (composability):** both sub-gates run in the SAME tmp project (sklearn-iris and CCRCC variants registered side-by-side), proving the framework supports heterogeneous consumers in one tree.

Sub-gates A and C are gated behind `@pytest.mark.requires_ccrcc_data`; B runs in CI unconditionally (sklearn dataset is bundled).

### D-206, framework purity grep gate (DEC-01)

CI gate: `tests/test_framework_purity.py` runs the grep:

```python
result = subprocess.run(
    ["grep", "-rE", "autobench|AUTOBENCH_|benchmarks/", "src/automil/"],
    capture_output=True, text=True
)
allowed = {
    # Permanent informational comments (no functional ref):
    "src/automil/backends/_orchestrator_daemon.py:54",  # consumer-specific vars comment
    "src/automil/cli/lifecycle/verify_repro.py:84",  # AUTOBENCH_ leakage comment
}
matches = [line for line in result.stdout.splitlines() if not _is_in_allowlist(line, allowed)]
assert matches == [], f"autobench leakage found: {matches}"
```

Hardcoded allowlist of comment-only references; ANY new functional ref breaks the test.

### D-207, BCK-04 lint extension to scoring/schemas (DEC-04, DEC-03)

Phase 5 D-149 BCK-04 lint allowlist + Phase 6 extension (slurm.py / ray.py). Phase 8 extends to:

- `src/automil/schemas/` (NEW), pure JSON schemas, no process-control needed; allowlist as PURE
- Any new graph.py composite-handling additions: existing graph.py is already in the allowlist; no change needed

### D-208, acceptance gate (Phase 8 success)

Phase 8 ships when ALL of these are TRUE:

1. `grep -rE "autobench|AUTOBENCH_|benchmarks/" src/automil/ | grep -v allowlisted` returns zero matches (D-201 framework purity)
2. `automil/schemas/result.schema.json` exists; `graph.py` validates result.json on ingestion; malformed result.json transitions node to `crashed` with schema error pointer (DEC-03)
3. `graph.py` stores `node["metrics"] = dict(metrics)` instead of named-field copy; existing node fields (composite, parent_delta, best_composite, baseline_composite) preserved as framework-owned (DEC-04)
4. `automil/config.yaml: env.required` + `env.passthrough` schema added; `automil check` validates required vars; orchestrator subprocess env honors passthrough list (DEC-05)
5. `examples/sklearn-iris/` directory exists with train.py + automil/ scaffolding; sklearn-iris consumer test PASSES end-to-end (DEC-02)
6. `docs/training-script-contract.md` exists and covers all 6 contract items (DEC-06)
7. `tests/test_framework_purity.py` PASSES with hardcoded allowlist (D-206)
8. `tests/acceptance/test_final_phase8_acceptance.py` Sub-gate B (sklearn-iris) PASSES in CI; Sub-gates A and C run on Leo's workstation when CCRCC data available (D-205)
9. Phase 7 baseline preserved (838+ tests passing); ≥10 new tests added for DEC-01..07
10. CHANGELOG entry: 8.0.0 if any consumer-facing breaking change (env.required becomes mandatory in config.yaml IS breaking for existing CCRCC consumer configs); else 7.1.0
11. ROADMAP and STATE updated to mark Phase 8 + milestone v1.0 complete

</decisions>

<code_context>
## Existing Code Insights

**Already in tree (Phases 0-7):**
- `src/automil/graph.py` (~700 lines): contains the named-field copy at lines 134-135, 212-213, 564-565, 619-620, 697-698 (D-200 target)
- `src/automil/backends/_orchestrator_daemon.py:718-721`: AUTOBENCH_ROOT injection (D-199 target)
- `src/automil/backends/_orchestrator_daemon.py:777-780`: PYTHONPATH manipulation pointing to benchmarks/ (D-199 target)
- `src/automil/cli/check.py`: existing structure for adding env.required validator (D-202 hook)
- `src/automil/cli/init.py`: Phase 7 added healthcheck wiring; Phase 8 adds env.required template defaults to config.yaml.j2
- `src/automil/templates/config.yaml.j2`: needs env: block addition
- `src/automil/runtime.py` / `runtime_helpers.py`: framework-side helpers; check for autobench refs
- `jsonschema` library: already a transitive dep (Phase 5 gate_manifest.json validation)

**Reusable assets:**
- Schema validation pattern from `src/automil/gate/manifest.py` (Phase 5), model JSON-Schema validate-on-load on result.json
- env-passthrough idea from Phase 0 CLN-02 (env whitelist for subprocess), extend with consumer-config-driven keys
- Acceptance-gate single-file test pattern from `tests/skills/test_phase7_acceptance.py` (Phase 7 D-198) and `tests/backends/test_phase6_acceptance.py` (Phase 6 D-179)

**Integration points:**
- `graph.py` ingestion path: dispatch JSON-Schema validation BEFORE node mutation; on failure, transition to crashed
- `_orchestrator_daemon.py` subprocess env: replace hardcoded AUTOBENCH_ROOT injection with `env.passthrough` list iteration
- `cli/check.py`: add `_validate_env_required()` helper following existing `_validate_slurm_directives` pattern (Phase 6)
- `automil/templates/config.yaml.j2`: add `env: required: [] passthrough: []` block (empty defaults; consumer fills)

</code_context>

<specifics>
## Specific Ideas

- **Sklearn-iris training script length cap**: ≤80 lines so it serves as a minimal contract demo; longer than CCRCC's would defeat the "minimal second consumer" purpose
- **No NEW top-level dependencies**: jsonschema is transitive; sklearn is dev-only (not in framework deps); add `[examples-iris]` extra for sklearn pin if needed
- **Migration note in CHANGELOG**: env.required becoming mandatory IS a breaking change for existing autobench consumers (their config.yaml must be updated). Document migration: `add `env.required: [AUTOBENCH_OVARIAN_ROOT, AUTOBENCH_CCRCC_ROOT, ...]` to existing automil/config.yaml`.
- **Sub-gate A (CCRCC reproduction) data-availability**: Leo's workstation has CCRCC; CI does not. Use `@pytest.mark.requires_ccrcc_data` marker; nightly run only.
- **graph.py refactor preserves API**: external readers (`viz/server.py`, `cli/show_skill.py`, gate flows) currently access `node["val_auc"]` etc directly. After D-200 migration, those readers MUST be updated to read `node["metrics"]["val_auc"]`. This is a one-shot refactor; the migration is mechanical.

</specifics>

<deferred>
## Deferred Ideas

- **Composite formula DSL** (e.g., `scoring.formula: "0.4 * val_auc + 0.6 * val_bacc"`), explicit non-goal per D-200; framework does not evaluate
- **JSON-Schema entry_point support** (Python module that returns a schema dynamically), out of scope; static `result.schema.json` is sufficient
- **Per-fold result.json validation**, only top-level result.json is validated; fold_results array is opaque-pass-through
- **AutoML metric selection** (e.g., choose between accuracy vs F1 based on dataset balance), out of scope; consumer's job
- **Multi-language consumer support** (R, Julia), out of scope per CONTEXT
- **CCRCC dataset re-curation**, out of scope; v1 milestone uses existing CCRCC layout
- **viz dashboard generic-metric rendering** (auto-detect available metric keys for sparkline display), Phase 8 keeps viz showing existing autobench keys via `node["metrics"]` access; full dashboard rewrite for generic metric rendering deferred to post-v1
- **Migration tool**: `automil migrate-config-yaml` CLI helper that scans existing config.yaml + adds env.required defaults, operator runs manually following CHANGELOG instructions; tooling deferred

</deferred>
