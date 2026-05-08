# Phase 8: Decoupling Completion + Final Acceptance, Research

**Researched:** 2026-05-07
**Domain:** Framework decoupling audit, JSON-Schema validation, second-consumer proof, milestone acceptance gate
**Confidence:** HIGH (all critical claims verified against committed source; jsonschema/scipy/jinja already vendored; sklearn already in `[ml]` extra)
**Mode:** Auto-bootstrapped per Leo's standing directive `feedback_decide_engineering_ask_features`. Engineering decisions in CONTEXT.md (D-199..D-208) are LOCKED; this research operates on top of them.

## Summary

Phase 8 is the milestone-acceptance phase. The CONTEXT.md decisions (D-199..D-208) lock the
engineering shape. This research closes the remaining ambiguities the planner needs:

1. The graph.py named-field-copy migration is mechanical but has a long migration delta. Six call
   sites in `graph.py` (lines 132-135, 210-213, 562-565, 617-620, 695-698, plus the bootstrap
   loader at 779-799) write the four named keys; an additional six call sites in `graph.py`
   (lines 254-265, 547-552, 676-680) READ those keys for Pareto dominance computation. Outside
   `graph.py`, the readers are: `viz/static/app.js:228-229` (sparkline display),
   `_orchestrator_daemon.py:1055` (cap reconcile fallback) and `_orchestrator_daemon.py:1289-1298`
   (results.tsv writer). All test files exercise the OUTPUT shape (`metrics={...}` input dict
   continues to carry these keys for autobench consumers, that is fine, the change is on the
   storage shape inside the node).

2. `jsonschema 4.26.0` is already in `uv.lock` as a transitive dependency (4.10.3 in current dev
   env). Phase 5's gate manifest used a hand-rolled `validate_manifest_dict` rather than
   `jsonschema.validate`, so this is the first place the framework actually uses the library
   directly. The recommended insertion point is the orchestrator's result.json ingestion path
   (`_orchestrator_daemon.py:1087-1108`), BEFORE the node mutation in graph.py, so a malformed
   payload never produces an inconsistent graph.

3. The env.passthrough scaffolding already exists (`check.py:211-227`,
   `_orchestrator_daemon.py:429-450`, `_orchestrator_daemon.py:700-722`). What is MISSING is
   `env.required` validation. The Phase 6 `_validate_slurm_directives` pattern at `check.py:23-57`
   is the exact analog: a pure function that reads the config dict, raises a typed exception on
   miss, and is called early in the `check` command flow.

4. The sklearn-iris consumer is the load-bearing decoupling proof. A ~70-line `train.py`
   suffices: `load_iris` + `train_test_split` + `LogisticRegression` + `signal.signal(SIGTERM, ...)`
   + write `result.json`. Sklearn is already in the `[ml]` optional extra at `>=1.3`; no new
   top-level dep. A new `[examples-iris]` extra is recommended ONLY if Leo wants the example to
   install standalone without dragging in the rest of `[ml]`.

5. Final acceptance gate (D-205) splits cleanly into three sub-gates: A (CCRCC, requires Leo's
   workstation, marker `requires_ccrcc_data`), B (sklearn-iris, runs in CI), C (composability,
   both in same tmp project). The marker mechanism is already in `pyproject.toml:42-44` (lines
   declaring `requires_slurm` and `requires_ray`); add `requires_ccrcc_data` alongside.

6. Framework purity grep gate (D-206) has three existing analogs:
   `tests/gate/test_framework_purity.py` (file-walk + token check),
   `tests/agent_assets/test_smoke_two_runtimes.py:297` (subprocess grep),
   `tests/skills/test_phase7_acceptance.py:342-358` (file-walk grep + bad_terms tuple). The CONTEXT
   D-206 spec is closest to the subprocess-grep + allowlist-filter pattern.

**Primary recommendation:** Execute Phase 8 as 8 plans in 4 waves: W1 (schemas/ + jsonschema
ingestion + dict-spread refactor + reader migration, parallel-friendly within graph.py), W2
(env.required validator + config.yaml.j2 template update + daemon AUTOBENCH purge), W3
(sklearn-iris consumer + docs/training-script-contract.md + framework-purity grep gate), W4 (final
acceptance test aggregator + CHANGELOG + STATE/ROADMAP completion). Total estimate ~3 days
single-threaded, ~1.5 days with parallelism.

---

## Phase Boundary Recap

Verbatim from `08-CONTEXT.md` boundary block. The planner MUST honor these as authoritative
scope:

> Phase 8 is the milestone-acceptance phase. Three workstreams converge:
>
> 1. **Decoupling cleanup** (DEC-01, DEC-03, DEC-04, DEC-05): purge autobench leakage from
>    `src/automil/`, ship config-driven composite scoring with JSON-Schema validation, declare and
>    validate required env vars in config.
> 2. **Second consumer proof** (DEC-02): plug a sklearn-iris training script into autoMIL via
>    the documented contract; run an experiment loop end-to-end.
> 3. **Contract documentation** (DEC-06) + **final acceptance** (DEC-07): write
>    `docs/training-script-contract.md`; final acceptance gate = clean checkout, registry path,
>    fresh worktree, all phases composed produce CCRCC `node_0176` reproduction within +-0.005
>    AND sklearn-iris consumer end-to-end.
>
> **Out of scope:** Multi-language consumers (R, Julia); composite-formula DSL beyond simple
> weighted-sum; AutoML metric selection; CCRCC dataset re-curation; sklearn dataset selection
> beyond iris.

Locked decisions D-199 through D-208 cover purge surface, dict-spread storage, JSON-Schema, env
validation, sklearn-iris layout, contract doc, acceptance gate, purity gate, BCK-04 lint
extension, and the final ship checklist. This research does NOT relitigate them; it surfaces the
implementation-specific evidence the planner needs.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions

D-199 through D-208 in `.planning/phases/08-decoupling-completion-acceptance/08-CONTEXT.md`.
Summary table for the planner's quick reference (full text in CONTEXT.md):

| ID | Subject | Verdict |
|----|---------|---------|
| D-199 | autobench-leakage purge surface | Remove `_orchestrator_daemon.py:718-721` (AUTOBENCH_ROOT inject) and `:777-780` (PYTHONPATH manipulation). Replace with generic `env.passthrough` driven from config. Two informational comments retained on allowlist. |
| D-200 | Composite scoring storage | `node["metrics"] = dict(metrics)` full dict spread; framework-owned scalars (`composite`, `parent_delta`, `global_delta`, `best_composite`, `baseline_composite`) preserved at top level. `scoring.formula` is documentation-only. |
| D-201 | result.json JSON-Schema validation | New `automil/schemas/result.schema.json` (Draft 2020-12). Validate at ingestion via `jsonschema.validate(...)`; on failure, transition to `crashed` with schema-pointer in error message. `additionalProperties: true`. |
| D-202 | env.required + env.passthrough validators | `automil check` validates `env.required`; subprocess env honors `env.passthrough`. Missing required var fails fast, not deep in train.py. |
| D-203 | sklearn-iris second consumer | New `examples/sklearn-iris/` directory: `automil/config.yaml`, `automil/program.md`, `automil/variants/classifier_v0/logistic_v0.py` starter, `train.py` (~80 lines), `README.md`. |
| D-204 | training-script contract docs | New `docs/training-script-contract.md` covers 6 contract items: config read, CUDA_VISIBLE_DEVICES honor, AUTOMIL_GPU honor, SIGTERM clean exit, result.json schema, env.required declarations. |
| D-205 | final acceptance gate | `tests/acceptance/test_final_phase8_acceptance.py` with sub-gates A (CCRCC, marker `requires_ccrcc_data`), B (sklearn-iris, CI-default), C (composability, both consumers same project). |
| D-206 | framework purity grep gate | `tests/test_framework_purity.py` runs grep + filters allowlist; only the 2 informational comments at `_orchestrator_daemon.py:54` and `cli/lifecycle/verify_repro.py:84` are permitted. |
| D-207 | BCK-04 lint extension | `src/automil/schemas/` allowlisted as PURE (no process control). `graph.py` already in allowlist. |
| D-208 | Phase 8 acceptance | 11-clause ship checklist; CHANGELOG 8.0.0 (env.required mandatory IS a breaking change for existing autobench consumers). |

### Claude's Discretion

The CONTEXT.md decisions are exhaustive. Fine-grained discretion items the planner can decide:

- Naming convention for the new `examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py`
  starter (D-203 suggests `logistic_v0.py`; planner may choose `classifier_v0_baseline.py` or
  similar if it serves the contract demo better).
- Docstring style of `train.py` and the variant starter (project-default Google-style).
- Whether to ship a `[examples-iris]` extra in `pyproject.toml` (recommendation below: yes, but
  only if it does not require splitting the existing `[ml]` extra).
- Test parametrization style for the framework-purity grep gate (subprocess vs in-process
  rglob; CONTEXT D-206 mentions subprocess; the in-process rglob analog at
  `tests/gate/test_framework_purity.py` is also valid).
- Whether sub-gate A in `test_final_phase8_acceptance.py` invokes `automil verify-repro
  node_0176` (which already exists) or runs an inline submit + assert composite. Recommendation:
  reuse `verify-repro` because the Phase 1 D-50 gate already validates that path.

### Deferred Ideas (OUT OF SCOPE)

Verbatim from CONTEXT.md `<deferred>` block:

- Composite formula DSL (`scoring.formula: "0.4*val_auc + 0.6*val_bacc"`).
- JSON-Schema `entry_point` (Python module returns schema dynamically).
- Per-fold result.json validation (only top-level is validated; `fold_results` is opaque).
- AutoML metric selection.
- Multi-language consumers (R, Julia).
- CCRCC dataset re-curation.
- viz dashboard generic-metric rendering (auto-detect available metric keys for sparkline).
- `automil migrate-config-yaml` CLI helper (operator runs CHANGELOG instructions manually).

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEC-01 | `grep -r "autobench\|AUTOBENCH_" src/automil/` returns zero matches; verified in CI | OQ-1, OQ-6, Migration Delta Punch List section, daemon purge sites at `_orchestrator_daemon.py:718-721, 777-780` |
| DEC-02 | sklearn-iris training script plugs into autoMIL via documented contract; runs experiment loop end-to-end | OQ-4, sklearn-iris skeleton in Reusable Patterns; sklearn already in `[ml]` extra (`pyproject.toml:24-29`) |
| DEC-03 | `result.json` JSON-Schema-validated at ingestion; orchestrator rejects malformed with clear pointer | OQ-2, jsonschema 4.26.0 in `uv.lock:1369-1380`, validation insertion point at `_orchestrator_daemon.py:1087-1108` |
| DEC-04 | Composite scoring config-driven; not hardcoded to autobench's 4-key recipe | OQ-9, dict-spread refactor in graph.py at lines 132-135, 210-213, 562-565, 617-620, 695-698 (per D-200) |
| DEC-05 | Required env vars declared in `automil/config.yaml: env.required` and validated by `automil check`; missing vars fail fast | OQ-3, `_validate_slurm_directives` analog at `check.py:23-57`; passthrough wiring exists at `check.py:211-227` and daemon at `_orchestrator_daemon.py:429-450` |
| DEC-06 | `docs/training-script-contract.md` documents 6 contract items | OQ-4, contract sections derived from `runtime_helpers.py:32-58` SIGTERM pattern + `_orchestrator_daemon.py:712-722` injected env + D-201 schema |
| DEC-07 | Final reproduction sanity: CCRCC `node_0176` reproduces +-0.005 AND same harness runs sklearn-iris | OQ-5, three-sub-gate pattern derived from `tests/skills/test_phase7_acceptance.py` (Phase 7) and `tests/backends/test_phase6_acceptance.py` (Phase 6) |

---

## Open Questions for the Planner

The CONTEXT.md decisions answer the architecture questions. The OQs below resolve
implementation-specific choices the planner needs to commit to in PLAN.md task actions.

### OQ-1: Where exactly does the JSON-Schema validation hook into the ingestion path?

**Question:** D-201 says "graph.py validates result.json at ingestion via
`jsonschema.validate(...)`. On `ValidationError`, the orchestrator transitions the node to
crashed". But the actual ingestion path involves both the orchestrator daemon (which collects
`result.json` from worktree at `_orchestrator_daemon.py:1088`) AND the graph's recovery loop
(`graph.py:651-712`). Where does the validate call go?

**Evidence reviewed:**

- `_orchestrator_daemon.py:1087-1108` (live ingestion):
  ```
  result = self.runner.collect_result(wt_path, archive)
  if result is None: ... # synthesize a status-only result
  if "status" not in result: result["status"] = "completed" if returncode == 0 else "crash"
  completion = { "id": node_id, "status": ..., "composite": result.get("composite", 0), ... }
  ```
- `graph.py:651-712` (archive-based recovery, used for orphan recovery on daemon restart):
  ```
  for node_dir in archive_path.iterdir():
      result_file = node_dir / "result.json"
      if node_id_r not in self.nodes and result_file.exists():
          try: result = json.loads(result_file.read_text())
  ```

**Recommendation:** Validate in BOTH places. The live path
(`_orchestrator_daemon.py:1087-1108`) is where most validations fire (every completed
experiment). The recovery path (`graph.py:651-712`) is a slower/rarer path but handles operator
restart of an orchestrator with stale archives, and a pre-existing malformed result.json must
not silently corrupt graph.json on recovery either.

Concrete insertion: define `automil/schemas/result.py` with module-level `RESULT_SCHEMA` (loaded
from `automil/schemas/result.schema.json` once at import time) and a `validate_result(payload:
dict) -> None` helper that wraps `jsonschema.validate`. Both ingestion paths call it. On
`jsonschema.exceptions.ValidationError`, the daemon writes the failure-case result.json with
`status="crash"` and the schema-pointer error string; the recovery path skips the node and
appends the error to `archive/<node_id>/INVALID_RESULT.txt` (do not mutate graph.json with a
half-validated entry).

**Confidence:** HIGH (both code paths visible at the cited line numbers; jsonschema lib confirmed
present).

### OQ-2: jsonschema validate vs Draft202012Validator: which API?

**Question:** D-201 spec uses `jsonschema.validate(...)`. The library also exposes
`Draft202012Validator(schema).validate(payload)` and an iter_errors variant. Which is canonical
for this codebase?

**Evidence reviewed:**

- `python3 -c "from jsonschema import validate; help(validate)"` shows `validate(instance,
  schema, cls=None, *args, **kwargs)`; this signature first verifies that the SCHEMA itself is
  valid (slower per call).
- For repeated validation against the same schema, `Validator.validate(instance)` is the
  recommended pattern per the docstring: "If you know you have a valid schema already,
  especially if you intend to validate multiple instances with the same schema, you likely would
  prefer using the `Validator.validate` method directly on a specific validator (e.g.
  `Draft7Validator.validate`)."
- result.json validation runs once per experiment completion (potentially 100+ times per
  campaign). Schema is fixed, no dynamic mutation.

**Recommendation:** Use `Draft202012Validator`:

```python
# automil/schemas/result.py
from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

_SCHEMA_PATH = Path(__file__).parent / "result.schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)

def validate_result(payload: dict) -> None:
    """Raise jsonschema.ValidationError on contract violation.

    Schema location: automil/schemas/result.schema.json (D-201).
    """
    _VALIDATOR.validate(payload)
```

The `_VALIDATOR` instance pre-compiles the schema once at module import. Each call is just
`_VALIDATOR.validate(payload)`. Caller catches `ValidationError`, surfaces
`exc.json_path` + `exc.message` in the operator-facing error, and points at the schema file.

**Confidence:** HIGH (jsonschema library present, signature verified, performance reasoning
straightforward).

### OQ-3: Where does `_validate_env_required` insert in `cli/check.py`?

**Question:** `check.py` is ~336 lines, runs many validators. Where in the flow does
`_validate_env_required` go, and does it raise or accumulate into the issues list?

**Evidence reviewed:**

- `check.py:97-115` opens with config load, then runs run.script existence, data path placeholders,
  files.editable, baseline.composite checks (lines 113-144). All append to `issues` or `warnings`
  lists.
- `check.py:165-185` runs the Phase 6 `_validate_slurm_directives` block (which DOES raise
  `SlurmDirectivesIncompleteError`, caught at line 170 and appended to `issues`).
- `check.py:211-227` runs the existing env.passthrough validator (already in place since CLN-02).
- The pattern at `check.py:165-185` is the closest analog: a pure helper raises a typed
  exception, the command body catches it and appends to `issues`.

**Recommendation:** Add `_validate_env_required(config)` as a top-level function in `check.py`,
mirroring `_validate_slurm_directives`. Place the call after the env.passthrough block (line 227)
because it is logically the same section. The validator returns a list of missing var names; the
command body iterates and appends to `issues`.

```python
# Insertion at check.py: after line 227

def _validate_env_required(config: dict) -> list[str]:
    """Return names of env vars declared in env.required but not set in os.environ.

    Pure function: no Click, no I/O. Wave-0 unit tests exercise it directly.
    """
    env_section = (config or {}).get("env") or {}
    raw_required = env_section.get("required", []) or []
    if not isinstance(raw_required, list):
        return []  # warnings list captures the type error elsewhere
    required = [str(k) for k in raw_required]
    return [k for k in required if k not in os.environ]


# In check() body, after the env.passthrough block at line 227:
missing_required = _validate_env_required(config)
for name in missing_required:
    issues.append(
        f"Missing required env var: {name}; see automil/config.yaml: env.required. "
        f"Set the variable before running 'automil submit' or 'automil orchestrator start'."
    )
```

This raises the var-by-var error that D-202 demands. NOTE: existing Phase 6 pattern raises a
single typed exception with all missing keys; D-202's text says "for each missing var, emits a
clear error" so the per-var iteration is correct.

**Confidence:** HIGH (file structure visible, pattern analog at check.py:23-57 verified).

### OQ-4: sklearn-iris train.py skeleton: SIGTERM handler and config read

**Question:** D-203 specifies the train.py is ~80 lines, SIGTERM-clean-exit, honors
CUDA_VISIBLE_DEVICES (no-op on CPU), reads config. The contract doc D-204 lists 6 items
including "honor `AUTOMIL_GPU=N`". For sklearn (CPU-only), what is the minimal but correct
SIGTERM pattern, and does the script need to use `automil.runtime_helpers.register_sigterm_flush`
or a stand-alone signal handler?

**Evidence reviewed:**

- `runtime_helpers.py:32-58` documents `register_sigterm_flush` and notes its dependency on
  `automil.cells.reconcile.aggregate_folds`, which assumes per-fold result files
  (`fold_<i>_result.json`). Sklearn-iris is single-shot, no folds, so `register_sigterm_flush`
  is the WRONG choice for the demo (it would aggregate zero folds).
- Standalone signal pattern: `signal.signal(signal.SIGTERM, _handler)` where `_handler` writes
  `result.json` with `status: "budget_killed"` and `partial: true`, then `sys.exit(0)`. Mirrors
  the spirit of D-121 (sys.exit(0), NOT 130) so the daemon treats SIGTERM as graceful flush.

**Recommendation:** sklearn-iris uses a stand-alone signal handler, NOT
`register_sigterm_flush`. The handler closes over a partial-result builder. The contract doc
DEC-06 should document BOTH patterns (multi-fold via runtime_helpers; single-shot via inline
signal handler) and explain when to use each.

Recommended skeleton (~70 lines, planner can refine):

```python
#!/usr/bin/env python3
"""sklearn-iris training script: minimal autoMIL contract demo.

DEC-02 / DEC-06: this file is the shipped reference for plugging a non-autobench
training script into autoMIL. See docs/training-script-contract.md for the
contract this script honors.
"""
from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path

import yaml
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

# Honor CUDA_VISIBLE_DEVICES (no-op on CPU) and AUTOMIL_GPU (logical device 0)
# AUTOMIL_NODE_ID lets the script discover its archive via AUTOMIL_RESULTS_DIR.
RESULTS_DIR = Path(os.environ.get("AUTOMIL_RESULTS_DIR", os.getcwd()))

# State held by SIGTERM handler. Updated as training progresses.
_state = {"completed": False, "accuracy": 0.0, "f1": 0.0}


def _write_result(status: str, partial: bool) -> None:
    payload = {
        "status": status,
        "composite": _state["accuracy"],
        "metrics": {"accuracy": _state["accuracy"], "f1": _state["f1"]},
        "partial": partial,
    }
    (RESULTS_DIR / "result.json").write_text(json.dumps(payload, indent=2))


def _sigterm_handler(signum: int, frame: object) -> None:
    """SIGTERM clean exit: write partial result.json, exit 0."""
    _write_result(status="budget_killed", partial=not _state["completed"])
    sys.exit(0)  # NOT sys.exit(130); 0 signals graceful flush to daemon


def main() -> None:
    signal.signal(signal.SIGTERM, _sigterm_handler)

    # Read config (D-204 contract item 1)
    config_path = Path("automil/config.yaml")
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text()) or {}
    else:
        config = {}
    seed = (config.get("data") or {}).get("seed", 42)

    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=seed
    )
    clf = LogisticRegression(max_iter=200, random_state=seed).fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    _state["accuracy"] = float(accuracy_score(y_test, y_pred))
    _state["f1"] = float(f1_score(y_test, y_pred, average="macro"))
    _state["completed"] = True

    _write_result(status="completed", partial=False)


if __name__ == "__main__":
    main()
```

The SIGTERM handler MUST be installed BEFORE any compute. The handler is idempotent if SIGTERM
fires after `_state["completed"] = True` (write completed-status, not budget_killed; planner can
add the conditional in the task action).

**Confidence:** HIGH (sklearn API stable; signal pattern straightforward; file paths and env vars
verified against `_orchestrator_daemon.py:712-722` injected env).

### OQ-5: Final acceptance test fixture: marker semantics and skip-on-data-absent

**Question:** D-205 defines three sub-gates. Sub-gate A (CCRCC) requires real data only on Leo's
workstation. How does the test discover whether CCRCC data is present, and what is the marker
strategy?

**Evidence reviewed:**

- Existing markers: `pyproject.toml:42-44`:
  ```
  markers = [
    "requires_slurm: requires SLURM cluster (skip in CI; nightly only)",
    "requires_ray: requires real Ray cluster (skip in CI; nightly only)",
  ]
  ```
- Phase 1 `tests/test_synthetic_consumer_roundtrip.py` runs the FULL CCRCC-equivalent pipeline
  on a SYNTHETIC consumer fixture (deterministic 0.502 forward), independent of real CCRCC
  data. This is the synthetic gate that already exists and runs in CI.
- Real CCRCC data lives at `${AUTOBENCH_CCRCC_ROOT}` (consumer .env, not in git, not in CI).

**Recommendation:** Add three markers to `pyproject.toml`:

```
markers = [
    "requires_slurm: requires SLURM cluster (skip in CI; nightly only)",
    "requires_ray: requires real Ray cluster (skip in CI; nightly only)",
    "requires_ccrcc_data: requires real CCRCC dataset at $AUTOBENCH_CCRCC_ROOT (workstation only)",
    "requires_external_data: requires consumer-managed data not in git (workstation only)",
]
```

The acceptance test checks `os.environ.get("AUTOBENCH_CCRCC_ROOT")` and the existence of
`Path(env_var) / <known-marker-file>`. Skip with `pytest.skip(...)` if either is missing.

```python
@pytest.fixture
def ccrcc_root() -> Path:
    """Resolve CCRCC dataset root or skip the test."""
    raw = os.environ.get("AUTOBENCH_CCRCC_ROOT")
    if not raw:
        pytest.skip("AUTOBENCH_CCRCC_ROOT not set; sub-gate A requires CCRCC data")
    root = Path(raw)
    if not root.exists():
        pytest.skip(f"AUTOBENCH_CCRCC_ROOT={raw} does not exist")
    # Optional: probe for splits_dir or features_dir as a sanity check
    if not (root / "splits").exists():
        pytest.skip(f"CCRCC root {raw} does not have expected splits/ subdirectory")
    return root


@pytest.mark.requires_ccrcc_data
def test_subgate_a_ccrcc_node_0176_reproduction(tmp_path, ccrcc_root):
    """Sub-gate A (D-205): CCRCC node_0176 reproduces +-0.005."""
    ...
```

CI runs `pytest -m "not requires_ccrcc_data and not requires_slurm and not requires_ray"`; only
sub-gate B runs. Leo's workstation runs the unfiltered set; all three sub-gates execute.

Sub-gate C (composability) is also marked `requires_ccrcc_data` because it pre-requires CCRCC
to register node_0176 in the same project as iris_001. There is no fall-back; if data is
absent, sub-gates A and C both skip with the same message. CI green if B passes; full green
required for milestone v1.0 declaration.

**Confidence:** HIGH (marker pattern verified at `pyproject.toml:42-44`; existing skip-on-data
patterns visible at `test_synthetic_consumer_roundtrip.py:163` and across the integration tests).

### OQ-6: Framework purity grep gate: subprocess vs in-process rglob, false positive risk

**Question:** D-206 spec uses `subprocess.run(["grep", "-rE", ...])`. The existing analog at
`tests/gate/test_framework_purity.py:38-55` uses in-process `Path.rglob("*.py")` plus
`for token in ...`. Which is canonical, and what is the line-drift risk for the allowlist
mechanism?

**Evidence reviewed:**

- D-206 explicit spec:
  ```python
  result = subprocess.run(
      ["grep", "-rE", "autobench|AUTOBENCH_|benchmarks/", "src/automil/"],
      capture_output=True, text=True
  )
  allowed = {
      "src/automil/backends/_orchestrator_daemon.py:54",
      "src/automil/cli/lifecycle/verify_repro.py:84",
  }
  matches = [line for line in result.stdout.splitlines() if not _is_in_allowlist(line, allowed)]
  ```
- The in-process pattern at `tests/gate/test_framework_purity.py:44-55`:
  ```python
  for path in GATE_FILES:
      content = path.read_text()
      for token in ("autobench", "AUTOBENCH_", "benchmarks/"):
          if token in content:
              offenders.append((path.relative_to(_REPO_ROOT), token))
  ```
- Subprocess grep produces output of the form `path/to/file:LINE_NUMBER:matched_text`. The
  CONTEXT D-206 spec uses path:line as the allowlist key. This is fragile to line drift.
- In-process rglob produces (path, token, line_number) tuples. Same fragility BUT trivially
  refactorable to (path, token) only, dropping line numbers, removing the drift risk.

**Recommendation:** The CONTEXT D-206 spec is fine, but the planner should use line-NUMBERED
keys ONLY for the two known informational-comment exceptions, AND add a regression-prevention
test that fails LOUDLY if the comment moves (so the operator updates the allowlist deliberately,
not via a green test passing through lucky coincidence).

Concrete pattern:

```python
# tests/test_framework_purity.py
import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_AUTOMIL = _REPO_ROOT / "src" / "automil"

# Hardcoded allowlist: file:line keys with a comment-content anchor for line-drift detection.
# If the comment moves, the line check fails AND the content check fires on
# the new line, triggering an explicit "update allowlist" failure.
_ALLOWLIST: dict[str, str] = {
    # path:line  ->  expected substring on that exact line
    "src/automil/backends/_orchestrator_daemon.py:54": "Consumer-specific vars (e.g. AUTOBENCH_*_ROOT)",
    "src/automil/cli/lifecycle/verify_repro.py:84": "no AUTOBENCH_* leakage",
}


def test_framework_purity_no_autobench_refs():
    """D-206 / DEC-01: grep src/automil/ returns at most the allowlisted comment lines."""
    result = subprocess.run(
        ["grep", "-rEn", "autobench|AUTOBENCH_|benchmarks/", str(_SRC_AUTOMIL)],
        capture_output=True, text=True,
    )
    # grep returns 1 if no matches, 0 if matches, 2 on error
    assert result.returncode in (0, 1), f"grep failed: {result.stderr}"

    matches = []
    for line in result.stdout.splitlines():
        # Format: /abs/path:LINE:content
        # Convert to repo-relative path for comparison
        m = re.match(r"^(.*?):(\d+):(.*)$", line)
        if not m:
            matches.append(line)
            continue
        abs_path, line_no, content = m.group(1), m.group(2), m.group(3)
        rel_path = Path(abs_path).relative_to(_REPO_ROOT)
        key = f"{rel_path}:{line_no}"
        expected_substring = _ALLOWLIST.get(key)
        if expected_substring and expected_substring in content:
            continue  # allowlisted
        matches.append(f"{rel_path}:{line_no}:{content}")

    assert not matches, (
        f"Framework purity (DEC-01 / D-206) violated:\n  "
        + "\n  ".join(matches)
        + "\n\nautoMIL is generic; autobench is one consumer. "
        "Move the leaked reference to consumer-side code, or update _ALLOWLIST "
        "in tests/test_framework_purity.py if it is a deliberate informational comment."
    )
```

The substring anchor (e.g. `"Consumer-specific vars (e.g. AUTOBENCH_*_ROOT)"`) means line drift
within the same file does NOT silently bypass the test: the line still matches grep, the
allowlist key check fails (because line number drifted), the substring check kicks in, and the
substring still matches because the comment content is the same. Result: the offender is added
to `matches` and the test fails with a clear "update allowlist" message.

**Confidence:** HIGH (subprocess pattern verified, in-process analog verified, line-drift attack
vector reasoned through).

### OQ-7: viz dashboard reader migration delta after D-200

**Question:** After `node["val_auc"]` becomes `node["metrics"]["val_auc"]`, the viz frontend
breaks until `viz/static/app.js` is updated. What is the minimal change set?

**Evidence reviewed:**

- `viz/static/app.js:227-237`:
  ```javascript
  var metricFields = [
      ['test_auc', 'Test AUC'], ['test_bacc', 'Test BACC'],
      ['val_auc', 'Val AUC'], ['val_bacc', 'Val BACC']
  ];
  metricFields.forEach(function (pair) {
      var val = node[pair[0]];
      ...
  });
  ```
- The frontend reads `node[fieldname]` directly. After the dict-spread refactor,
  `node[fieldname]` is `undefined` for the four named-metric keys; the values now live at
  `node.metrics[fieldname]`.
- `viz/server.py` does NOT touch the four named keys (it reads graph.json verbatim and pipes via
  SSE).

**Recommendation:** Single-line change in `app.js:232`:

```javascript
// BEFORE
var val = node[pair[0]];

// AFTER (D-200 migration)
var val = (node.metrics || {})[pair[0]];
```

The CONTEXT D-200 deferred section explicitly notes: "viz dashboard generic-metric rendering
(auto-detect available metric keys for sparkline display), Phase 8 keeps viz showing existing
autobench keys via `node["metrics"]` access; full dashboard rewrite for generic metric rendering
deferred to post-v1." So the planner does NOT need to make viz dataset-agnostic; just route the
reads through `node.metrics`.

The `(node.metrics || {})` defensive guard handles legacy graph.json files written before D-200
(empty object falls back to undefined per-field, same behavior as before).

**Confidence:** HIGH (file content verified, change is mechanical).

### OQ-8: results.tsv writer migration: fresh consumer's tsv columns

**Question:** `_orchestrator_daemon.py:1289-1306` writes a header line with the four named metric
columns:
```
header = "node_id\tval_auc\tval_bacc\ttest_auc\ttest_bacc\tcomposite\tvram_gb\telapsed_min\tstatus\tdescription\n"
```
For the sklearn-iris consumer (which writes `metrics.accuracy` and `metrics.f1`, NOT
val_auc/val_bacc/test_auc/test_bacc), this header is wrong. Does Phase 8 require results.tsv to
be generic, or does it stay autobench-shaped?

**Evidence reviewed:**

- CONTEXT D-200 deferred: "viz dashboard generic-metric rendering ... full dashboard rewrite for
  generic metric rendering deferred to post-v1." results.tsv shares this property.
- `init.py:226-250` reads `vram_gb` from results.tsv via `csv.DictReader` to compute
  `default_vram_estimate_gb`. The column name `vram_gb` is the load-bearing read.
- Sklearn-iris does not write `vram_gb` (CPU-only; peak_vram_mb=0; vram_gb=0.0). The downstream
  init logic falls back to conservative defaults when fewer than 10 rows are available, so a
  CPU-only consumer with all-zero vram_gb is degenerate-but-correct.

**Recommendation:** Defer results.tsv schema generalization to post-v1. The current writer keeps
the autobench-shaped header AND writes 0.0 for missing keys (per `metrics.get('val_auc', 0)` at
line 1295). For a sklearn-iris consumer the row reads:
```
node_iris_0001  0.0000  0.0000  0.0000  0.0000  0.97  0.0  0.0  keep  iris baseline
```

The composite is correct; the four named-metric columns are 0.0 (consumer-irrelevant). The viz
sparkline displays 0.0 (correct: there is no auc to show). This is acceptable for v1; any user
who plugs in a non-autobench consumer reads the contract doc and understands the columns are
autobench-vestigial.

The acceptance test (sub-gate B) asserts `composite >= 0.90`, NOT specific column values; it is
unaffected by this columnar quirk.

DECISION FOR THE PLANNER: do not touch the results.tsv writer in Phase 8. Add a code comment at
`_orchestrator_daemon.py:1289` flagging this as autobench-shaped legacy and pointing at a future
roadmap item.

**Confidence:** HIGH (file structure verified, downstream consumer at `init.py:226-250` only
reads `vram_gb`, deferred decision aligns with CONTEXT.md).

### OQ-9: graph.py Pareto dominance reader migration (D-200 follow-on)

**Question:** D-200 changes the WRITE shape (named-field copy becomes dict spread). The READ
shape inside `graph.py` itself has six call sites that read `parent.get("test_auc")` and
`child.get("test_bacc")` for Pareto dominance (`graph.py:254-255, 264-265, 547-552, 676-680`).
What happens to these after the dict-spread refactor?

**Evidence reviewed:**

- After D-200, `node["test_auc"]` is no longer set (the named-field copy block is removed). The
  data lives at `node["metrics"]["test_auc"]` for autobench consumers, and is missing for
  sklearn-iris consumers (which writes `node["metrics"]["accuracy"]` instead).
- The Pareto dominance check `(c_auc >= p_auc and c_bacc >= p_bacc and c_comp > p_comp)` is
  meaningful ONLY when both parent and child wrote the same metric keys. For
  cross-consumer trees (sklearn-iris node parented to a CCRCC node, hypothetically) the check is
  semantically undefined.
- For SAME-CONSUMER trees, the check should still work after D-200 if it reads from
  `node.get("metrics", {}).get("test_auc", 0)`.

**Recommendation:** Migrate ALL six in-graph reader sites to read `node["metrics"][key]`. For
backwards compatibility with PRE-D-200 graph.json files (older nodes written with named-field
copy), use a fall-back read:

```python
# Helper for D-200 migration: read from metrics dict, fall back to top-level.
def _node_metric(node: dict, key: str, default: float = 0.0) -> float:
    metrics = node.get("metrics") or {}
    if key in metrics:
        return metrics[key]
    # Pre-D-200 graphs stored named keys at top level; fall back for compat.
    return node.get(key, default)
```

All six readers call `_node_metric(parent, "test_auc")` instead of `parent.get("test_auc", 0)`.
This keeps the Phase 1 D-50 reproduction sanity test green (the CCRCC node_0176 graph node was
written pre-D-200; reading post-D-200 falls back to the top-level keys).

For the sklearn-iris case, the Pareto check evaluates against `metrics.accuracy` for both
parent and child IF both consumers happen to write `accuracy`. For mixed-consumer trees, the
default is 0.0 on missing keys (which means everyone dominates everyone with status="discard"
unless composite alone tilts the result). This is acceptable v1 behavior; the planner should NOT
attempt cross-consumer dominance.

**Migration option (planner discretion):** instead of preserving 4-key Pareto, simplify to
1-key Pareto on `composite` only. The dominance becomes `c_comp > p_comp` (drop the per-metric
checks). This is GENERIC across consumers and matches D-200's spirit: framework computes
composite-based dominance; consumer's named metrics are display-only via `node.metrics`.

The planner should pick one of:
- **Option A (compatibility):** `_node_metric` helper + 4-key Pareto preserved for autobench.
- **Option B (simplification):** drop 4-key Pareto, dominance becomes `composite > parent_composite`.

CONTEXT D-200 says the framework "stores ALL metric keys on the node via `node["metrics"] =
dict(metrics)` ... existing `node["composite"]`, `node["parent_delta"]`, `node["best_composite"]`
stay (they are framework-owned)." This text suggests Option B (composite is framework-owned;
the four named keys are consumer-owned and live under `metrics`). I recommend **Option B** for
v1.0 with a clear CHANGELOG note. The behavioral change is small (the keep/discard rate may
shift slightly because the AUC/BACC monotonicity guard is gone) but the architectural cleanup is
worth it.

**Confidence:** MEDIUM (Option A is safe and known-good; Option B is cleaner but slightly
changes keep/discard semantics; CONTEXT D-200 leans Option B but is not explicit). The planner
should commit to one and document the choice in the PLAN.md task action.

---

## Reusable Patterns

### Pattern 1: jsonschema validate-on-load (Phase 5 analog adapted to Phase 8)

`gate/manifest.py` validates `gate_manifest.json` payloads with a hand-rolled
`validate_manifest_dict`. Phase 8 ships the FIRST jsonschema-based validation. Source pattern at
`gate/manifest.py:48-74`:

```python
def validate_manifest_dict(d: dict) -> None:
    """Schema validator -- raises ValueError on violation.

    Called by write_* before persistence. All fields required; validated in order.
    """
    if not isinstance(d.get("K"), int) or d["K"] < 1:
        raise ValueError(f"K must be >= 1; got {d.get('K')!r}")
    held = d.get("held_out_cells", [])
    if not held:
        raise ValueError("held_out_cells must be non-empty")
    ...
```

The Phase 8 jsonschema-based version (recommended):

```python
# src/automil/schemas/__init__.py
from automil.schemas._result import validate_result, RESULT_SCHEMA  # noqa: F401

# src/automil/schemas/_result.py
from __future__ import annotations
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as _ValidationError

ValidationError = _ValidationError  # re-export for callers

_SCHEMA_PATH = Path(__file__).parent / "result.schema.json"
RESULT_SCHEMA = json.loads(_SCHEMA_PATH.read_text())
_VALIDATOR = Draft202012Validator(RESULT_SCHEMA)

def validate_result(payload: dict) -> None:
    """Validate result.json payload against automil/schemas/result.schema.json (D-201).

    Raises:
        ValidationError: with full json_path; caller should surface
            'see automil/schemas/result.schema.json' in the operator message.
    """
    _VALIDATOR.validate(payload)
```

### Pattern 2: env.required validator (Phase 6 _validate_slurm_directives analog)

Source at `cli/check.py:23-57`:

```python
def _validate_slurm_directives(config: dict) -> None:
    """Raise SlurmDirectivesIncompleteError if SLURM config is incomplete (D-172)."""
    from automil.backends.errors import SlurmDirectivesIncompleteError

    backend_cfg = config.get("backend", {}) or {}
    slurm_cfg = backend_cfg.get("slurm", {}) or {}
    directives = slurm_cfg.get("directives", {}) or {}

    walltime = slurm_cfg.get("walltime_seconds")
    missing: list[str] = []
    if not isinstance(walltime, int) or walltime <= 0:
        missing.append("walltime_seconds")
    for key in _REQUIRED_SLURM_DIRECTIVES:
        val = directives.get(key)
        if val is None:
            missing.append(key)
    ...
    if missing:
        raise SlurmDirectivesIncompleteError(missing)
```

Phase 8 `_validate_env_required` is simpler (no error type needed; returns missing list,
caller appends to issues):

```python
def _validate_env_required(config: dict) -> list[str]:
    """Return env.required vars not set in os.environ (D-202).

    Pure function. No I/O, no Click, no exceptions. Caller appends to issues list
    via per-name iteration so each missing var produces a distinct user-facing message.
    """
    env_section = (config or {}).get("env") or {}
    raw_required = env_section.get("required", []) or []
    if not isinstance(raw_required, list):
        return []  # type-mismatch handled as a warning at call site
    required = [str(k) for k in raw_required]
    return [k for k in required if k not in os.environ]
```

### Pattern 3: sklearn-iris training script skeleton (DEC-02 / D-203)

Full skeleton in OQ-4 (~75 lines). Key structural rules:

1. SIGTERM handler MUST be installed before any heavy compute.
2. `result.json` writer is idempotent (`_write_result(status, partial)`); the SIGTERM handler
   and the success path both call it.
3. `automil/config.yaml` is read but optional (the framework's `automil check` validates
   `data.seed`; the script defaults to 42 if missing).
4. No imports from `automil.*`; the consumer is decoupled.
5. CUDA_VISIBLE_DEVICES is honored implicitly (sklearn does not use CUDA; the env var has no
   effect; this satisfies the contract item "honor CUDA_VISIBLE_DEVICES" via no-op).

### Pattern 4: Acceptance test aggregator (Phase 6 / Phase 7 analog)

Source pattern at `tests/skills/test_phase7_acceptance.py:29-55`:

```python
def test_phase7_acceptance_clause_01_backend_healthcheck_abc_and_6_unit_tests():
    """D-198 clause 1: Backend.healthcheck ABC + 6 LocalBackend tests pass."""
    from automil.backends.base import Backend, HealthReport
    assert "healthcheck" in Backend.__abstractmethods__, ...
```

Phase 8's analog at `tests/acceptance/test_final_phase8_acceptance.py` follows the same
clause-per-function structure for D-208's 11 clauses. Each test function has:

- Docstring referencing `D-208 clause N`
- Single assertion or short bash-verifiable check
- Failure message references the CONTEXT decision id

### Pattern 5: Sub-gate B (sklearn-iris end-to-end via real CLI)

Closest analog: `tests/test_synthetic_consumer_roundtrip.py` (Phase 1 D-50 acceptance gate). The
synthetic-consumer test:

1. Copies `tests/fixtures/synthetic_consumer/` into a tmp dir.
2. `git init`, commit initial.
3. Invokes real CLI commands via `CliRunner`.
4. Asserts terminal state and composite via `repro_manifest.yaml`.

Phase 8 sub-gate B follows the same pattern with `examples/sklearn-iris/` as the fixture source:

```python
def test_subgate_b_sklearn_iris_end_to_end(tmp_path, cli_runner, monkeypatch):
    """Sub-gate B (D-205): sklearn-iris consumer runs end-to-end in CI."""
    # 1. Copy examples/sklearn-iris/ into tmp_path
    fixture_src = _REPO_ROOT / "examples" / "sklearn-iris"
    for item in fixture_src.iterdir():
        ...
    # 2. git init + commit
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    ...
    monkeypatch.chdir(tmp_path)

    # 3. automil init (or pre-stamped automil/ already in fixture)
    # 4. automil submit --node iris_0001 --files train.py --max-time 60
    result = cli_runner.invoke(main, [
        "submit", "--node", "iris_0001",
        "--desc", "iris baseline",
        "--files", "train.py",
        "--max-time", "60",
    ])
    assert result.exit_code == 0

    # 5. Run orchestrator one tick (or use submitter + LocalBackend.run sync helper)
    # 6. Assert terminal state == executed AND composite >= 0.90
    ...
```

The full pattern shape matches Phase 1's `test_full_roundtrip_passes` at
`tests/test_synthetic_consumer_roundtrip.py:163-272`.

---

## External Dependencies

| Library | Version | Source | Phase 8 Use |
|---------|---------|--------|-------------|
| `jsonschema` | 4.26.0 (lock) / 4.10.3 (current dev env) | Already in `uv.lock:1369-1380` (transitive via gate stack) | result.json validation (D-201) |
| `scikit-learn` | 1.7.2 / 1.8.0 (lock) | Already in `[ml]` extra (`pyproject.toml:24-29`) at `>=1.3` | sklearn-iris consumer (D-203) |
| `pyyaml` | (already in core deps) | `pyproject.toml:17` | sklearn-iris config read |
| `python-dotenv` | (already in core deps) | `pyproject.toml:18` | env.required + .env loading reuse |
| `click` | (already in core deps) | `pyproject.toml:16` | check.py CLI surfaces |

**Zero new top-level dependencies required.** All Phase 8 functionality is built on libraries
already vendored.

**Verification commands:**

```bash
# jsonschema present
python3 -c "import jsonschema; print(jsonschema.__version__)"
# -> 4.10.3 (or 4.26.0 after uv sync)

# sklearn extra
grep -A 5 'optional-dependencies' /home/jma/Documents/yinshuol/autoMIL/pyproject.toml
# -> ml = ["torch>=2.0", "scikit-learn>=1.3", ...]
```

**Recommended new extra (optional, Leo's discretion):**

```toml
[project.optional-dependencies]
examples-iris = ["scikit-learn>=1.4", "pyyaml>=6.0"]  # for examples/sklearn-iris/
```

This lets a user run `pip install -e '.[examples-iris]'` to get exactly the deps needed for the
sklearn-iris demo without dragging in the full ML stack via `[ml]`. Strictly optional; if the
planner skips this, sklearn-iris demo users install via `[ml]` and ignore the heavier deps.

---

## Migration Delta Punch List

The full set of files/lines that read or write `val_auc`/`val_bacc`/`test_auc`/`test_bacc` after
the D-200 dict-spread refactor.

### Category A: WRITES (graph.py write sites that disappear after D-200)

These are the named-field copy blocks D-200 explicitly removes:

| File | Lines | Action |
|------|-------|--------|
| `src/automil/graph.py` | 132-135 (add_executed) | REMOVE 4 lines; replace with `"metrics": dict(metrics)` |
| `src/automil/graph.py` | 210-213 (promote) | REMOVE 4 lines; replace with `node["metrics"] = dict(metrics)` |
| `src/automil/graph.py` | 562-565 (reconcile completion ingest) | REMOVE 4 lines from `metrics` dict; the consumer-key passthrough happens via dict-spread upstream |
| `src/automil/graph.py` | 617-620 (recovery loop, archive-based) | REMOVE 4 lines; replace with `"metrics": dict(metrics)` |
| `src/automil/graph.py` | 695-698 (recovery loop, alternate path) | REMOVE 4 lines; replace with `"metrics": dict(r_metrics)` |
| `src/automil/graph.py` | 798-799 (results.tsv bootstrap loader) | KEEP for backwards-compat reads of pre-D-200 results.tsv files; values pass into `add_executed` via metrics dict, which auto-spreads under D-200 |

### Category B: READS inside graph.py (Pareto dominance, OQ-9)

| File | Lines | Action |
|------|-------|--------|
| `src/automil/graph.py` | 254-255 (`_reevaluate_descendants` parent metrics) | If Option A: read via `_node_metric(parent, "test_auc")`. If Option B: drop entirely; dominance becomes composite-only |
| `src/automil/graph.py` | 264-265 (`_reevaluate_descendants` child metrics) | Same as above |
| `src/automil/graph.py` | 547-552 (reconcile completion Pareto check) | Same as above |
| `src/automil/graph.py` | 550-551 (reconcile keep/discard) | Same as above |
| `src/automil/graph.py` | 676-680 (recovery loop Pareto check) | Same as above |
| `src/automil/graph.py` | 678-680 (recovery loop keep/discard) | Same as above |

Six sites. Recommend Option B (drop 4-key Pareto, keep composite-only) per OQ-9 reasoning. Total
diff: ~30 lines removed, ~5 lines added (composite-only check).

### Category C: READS outside graph.py (downstream consumers)

| File | Lines | Reader Type | Action |
|------|-------|-------------|--------|
| `src/automil/viz/static/app.js` | 228-229 + 232 | Frontend display | Change `node[pair[0]]` -> `(node.metrics \|\| {})[pair[0]]` (1-line diff) |
| `src/automil/backends/_orchestrator_daemon.py` | 1055 (cap-killed reconcile fallback) | In-memory mutation | Change `for k in (...): if k in payload.get("metrics", {}): gnode[k] = ...` to `gnode["metrics"] = dict(payload.get("metrics", {}))` |
| `src/automil/backends/_orchestrator_daemon.py` | 1289-1298 (results.tsv writer) | TSV column write | KEEP autobench-shaped (per OQ-8; deferred per CONTEXT D-200) |

### Category D: TEST inputs (no migration; tests provide the autobench-shaped metrics dict)

The following test files PASS the autobench-shaped metrics dict to `add_executed` (which then
calls D-200's dict-spread, storing `node["metrics"]`):

| File | Line count | Action |
|------|------------|--------|
| `tests/test_graph.py` | ~15 occurrences | NO CHANGE (the dict-INPUT shape is unchanged; only the storage shape changes) |
| `tests/test_cli.py` | ~6 occurrences | NO CHANGE |
| `tests/test_integration.py` | ~3 occurrences | NO CHANGE |
| `tests/test_per_fold_writer.py` | ~10 occurrences | NO CHANGE (these test the per-fold writer's metrics dict, not graph storage) |
| `tests/test_runner.py` | 1 occurrence | NO CHANGE |

Tests that DIRECTLY ASSERT `node["test_auc"]` or `node["val_auc"]` (the storage shape) MAY exist
and would need migration. Audit step required: `grep -n 'node\[.test_auc.\]\|node\[.val_auc.\]'
tests/`. Initial grep returned zero hits; the test suite asserts via `node["composite"]` and
top-level fields, not via the four named keys. Confidence: HIGH that no test migration is
needed for D-200, but the planner should re-grep on the ACTUAL post-refactor state to catch
anything missed.

### Category E: AUTOBENCH purge surface (D-199)

| File | Lines | Action |
|------|-------|--------|
| `src/automil/backends/_orchestrator_daemon.py` | 718-721 (`AUTOBENCH_ROOT` injection) | DELETE the 4-line block |
| `src/automil/backends/_orchestrator_daemon.py` | 777-786 (PYTHONPATH manipulation pointing at benchmarks/) | DELETE the 10-line block; PYTHONPATH passthrough now via env.passthrough |
| `src/automil/backends/_orchestrator_daemon.py` | 54 (informational comment about consumer-specific vars) | KEEP (allowlisted in D-206) |
| `src/automil/cli/lifecycle/verify_repro.py` | 84 (comment about AUTOBENCH_ leakage) | KEEP (allowlisted in D-206) |

Daemon delta: ~14 lines removed. The function signature `_build_subprocess_env` already accepts
`worktree_benchmarks` and `pythonpath` params; after purge, those params are likely removable
from the signature, or repurposed (the worktree path manipulation can move to consumer-side via
env.passthrough or direct config).

### Category F: TEST migration for AUTOBENCH purge

| File | Lines | Action |
|------|-------|--------|
| `tests/test_orchestrator_env_whitelist.py` | 133-136 (`test_autobench_root_still_injected_phase0`) | DELETE this test (Phase 0 D-05 is no longer the contract) OR convert it to a NEGATIVE test asserting AUTOBENCH_ROOT is NOT auto-injected |

Recommended: convert to negative test:

```python
def test_autobench_root_not_auto_injected_phase8(orch):
    """D-199 / DEC-01: AUTOBENCH_ROOT is not auto-injected; consumers opt in via env.passthrough."""
    env = _call_build(orch, worktree_benchmarks=Path("/tmp/wt/benchmarks"))
    assert "AUTOBENCH_ROOT" not in env, (
        "AUTOBENCH_ROOT must not be auto-injected after Phase 8 (D-199). "
        "Consumers declare AUTOBENCH_ROOT under env.passthrough in automil/config.yaml."
    )
```

### Category G: Template migration

| File | Lines | Action |
|------|-------|--------|
| `src/automil/templates/config.yaml.j2` | 96-104 (existing `env: passthrough:` block) | EXTEND with `env.required: []` field; default empty list (D-202) |
| `src/automil/templates/config.yaml.j2` | 30-38 (existing `metrics:` block with `composite_formula` and `track:`) | KEEP (consumer documentation only per D-200) |

Recommended template addition:

```yaml
# --- Environment passthrough (D-87, TRJ-04) and required vars (DEC-05 / D-202) ---
env:
  # Vars in this list are forwarded from the orchestrator process to each
  # experiment subprocess.  AUTOMIL_RUNTIME must be here so the trajectory
  # recorder inside the experiment sees the declared runtime value.
  passthrough:
    - AUTOMIL_*       # All automil framework variables (includes AUTOMIL_RUNTIME)
    - AUTOMIL_RUNTIME # Runtime declaration: explicit, never inferred (D-87)

  # Vars REQUIRED at startup. `automil check` fails with a clear "Missing
  # required env var: <name>" error if any are unset. Examples for an autobench
  # consumer:
  #   required:
  #     - AUTOBENCH_OVARIAN_ROOT
  #     - AUTOBENCH_CCRCC_ROOT
  required: []
```

---

## Final Acceptance Gate Test Pattern

D-205 splits the gate into three sub-gates. The pattern is a single test file
`tests/acceptance/test_final_phase8_acceptance.py` with three test functions, each marked or
unmarked depending on data availability.

### Sub-gate A: CCRCC reproduction (workstation only)

```python
@pytest.fixture
def ccrcc_data_root() -> Path:
    raw = os.environ.get("AUTOBENCH_CCRCC_ROOT")
    if not raw:
        pytest.skip("AUTOBENCH_CCRCC_ROOT not set; sub-gate A requires CCRCC data")
    root = Path(raw)
    if not root.exists():
        pytest.skip(f"AUTOBENCH_CCRCC_ROOT={raw} does not exist")
    return root


@pytest.mark.requires_ccrcc_data
def test_subgate_a_ccrcc_node_0176_reproduction(tmp_path, ccrcc_data_root, cli_runner):
    """Sub-gate A (D-205): clean checkout reproduces CCRCC node_0176 +-0.005."""
    # Clone repo into tmp_path (clean checkout). Reuse Phase 1 verify-repro pipeline.
    # After the pipeline runs, assert composite within +-0.005 of 0.502.
    # ...
    manifest = yaml.safe_load((adir / "repro_manifest.yaml").read_text())
    assert manifest["status"] == "pass"
    assert abs(manifest["actual_composite"] - 0.502) < 0.005
```

### Sub-gate B: sklearn-iris end-to-end (CI default)

```python
def test_subgate_b_sklearn_iris_end_to_end(tmp_path, cli_runner, monkeypatch):
    """Sub-gate B (D-205): sklearn-iris consumer runs end-to-end in CI."""
    fixture_src = _REPO_ROOT / "examples" / "sklearn-iris"
    # Copy fixture, git init, automil submit + run, assert terminal state.
    # ...
    assert terminal_state == "executed"
    assert composite >= 0.90
```

### Sub-gate C: composability (workstation only)

```python
@pytest.mark.requires_ccrcc_data
def test_subgate_c_heterogeneous_consumers_same_project(tmp_path, ccrcc_data_root, cli_runner):
    """Sub-gate C (D-205): both consumers register side-by-side in same automil/ tree."""
    # Single tmp project; submit BOTH iris_0001 (sklearn) and node_0176 (CCRCC).
    # Run orchestrator; assert both terminal states `executed` and graph contains both nodes.
    # ...
    assert "iris_0001" in graph["nodes"]
    assert "node_0176" in graph["nodes"]
    # Composite values are consumer-specific; just assert both are non-zero.
    assert graph["nodes"]["iris_0001"]["composite"] > 0
    assert graph["nodes"]["node_0176"]["composite"] > 0
```

### CI strategy

`pyproject.toml` adds `requires_ccrcc_data` to markers:

```toml
markers = [
    "requires_slurm: requires SLURM cluster (skip in CI; nightly only)",
    "requires_ray: requires real Ray cluster (skip in CI; nightly only)",
    "requires_ccrcc_data: requires real CCRCC dataset at $AUTOBENCH_CCRCC_ROOT",
]
```

CI runs:

```
uv run pytest -m "not requires_ccrcc_data and not requires_slurm and not requires_ray"
```

Sub-gate B runs unconditionally. Sub-gates A and C skip with clear messages.

Leo's workstation runs:

```
uv run pytest tests/acceptance/test_final_phase8_acceptance.py -v
```

All three sub-gates execute. Phase 8 ships ONLY when:
- CI green for sub-gate B
- Workstation green for A + B + C

This satisfies the D-208 clause 8 contract.

---

## Pitfall 7 Anti-Acceptance Tests

`research/PITFALLS.md` Pitfall 7 ("Decoupling autobench breaks tests, hides the bench-specific
assumptions, and creates a private API") gives 5 warning signs. Each maps to a defended test:

| Pitfall 7 warning sign | Anti-acceptance test |
|------------------------|---------------------|
| (a) "After the decoupling phase, only autobench experiments produce non-zero composites because `metrics.val_auc` is the magic key" | Sub-gate B: sklearn-iris produces `composite >= 0.90` end-to-end. If the framework silently zeros sklearn metrics, this fails. |
| (b) "A user asks 'how do I add my own metric to the composite?' and the answer requires editing `src/automil/`" | Test: `tests/test_consumer_metric_passthrough.py` registers a consumer that writes `metrics.custom_score`; asserts `node["metrics"]["custom_score"]` round-trips. (Defended by D-200 dict spread.) |
| (c) "Test coverage drops in `tests/` after the decoupling commit" | D-208 clause 9 mandates +>=10 new tests. Phase 7 baseline is 838+ tests; Phase 8 adds tests, never removes, except for the AUTOBENCH-ROOT-injection test that becomes a negative test. |
| (d) "The framework imports from `autobench` anywhere in `src/automil/`" | `tests/test_framework_purity.py` (D-206 grep gate). |
| (e) "User onboarding requires a person who has seen autobench before" | `docs/training-script-contract.md` (DEC-06) covers all 6 contract items with sklearn-iris example. The acceptance check on the docs is "all 6 items documented" via inline anchors. |

Recommended additional tests for the Pitfall-7 anti-acceptance suite (planner discretion):

1. `test_pitfall7_anti_acceptance_metrics_passthrough` (Pitfall 7b): submit a consumer that
   writes `{"composite": 0.5, "metrics": {"top1": 0.5, "top5": 0.8}}`; assert
   `graph["nodes"][node_id]["metrics"]["top1"] == 0.5` and `["top5"] == 0.8`. Asserts the dict
   spread does not silently drop unknown keys.

2. `test_pitfall7_anti_acceptance_no_default_zero_for_missing_keys` (Pitfall 7b): submit a
   consumer that writes only `{"composite": 0.7, "metrics": {"top1": 0.7}}`; assert
   `node["metrics"]` has no `val_auc` key (NOT silently defaulted to 0). Asserts the framework
   does not bake autobench-key assumptions.

3. `test_pitfall7_anti_acceptance_env_required_validation_fails_fast` (Pitfall 7c): set
   `env.required: [MY_REQUIRED_VAR]` in config and unset MY_REQUIRED_VAR; assert `automil check`
   exits non-zero with "Missing required env var: MY_REQUIRED_VAR" in output.

4. `test_pitfall7_anti_acceptance_schema_validation_rejects_malformed`: submit a node that
   writes `result.json` lacking the `composite` key; assert orchestrator transitions to
   `crashed` AND error message references `automil/schemas/result.schema.json`.

These four tests defend the warning signs Pitfall 7 names. Combined with sub-gate B (the
canonical Pitfall-7 anti-test per the research synthesis), the Phase 8 anti-acceptance suite has
~5 dedicated Pitfall-7 tests plus the framework-purity grep gate.

---

## Planner Implementation Hints

For each DEC-XX requirement, the recommended file + class + method skeleton.

### DEC-01: zero autobench refs in src/automil/

**Files:** `src/automil/backends/_orchestrator_daemon.py` (delete lines 718-721 + 777-786),
`tests/test_framework_purity.py` (NEW), `tests/test_orchestrator_env_whitelist.py` (convert
existing test to negative).

**Method skeletons:**

```python
# tests/test_framework_purity.py
def test_framework_purity_no_autobench_refs(): ...  # see OQ-6 full skeleton

# tests/test_orchestrator_env_whitelist.py (convert existing test)
def test_autobench_root_not_auto_injected_phase8(orch):
    env = _call_build(orch, ...)
    assert "AUTOBENCH_ROOT" not in env
```

### DEC-02: sklearn-iris second consumer

**Files:**
- `examples/sklearn-iris/train.py` (NEW, ~75 lines, see OQ-4 skeleton)
- `examples/sklearn-iris/automil/config.yaml` (NEW)
- `examples/sklearn-iris/automil/program.md` (NEW, narrative)
- `examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py` (NEW, starter variant)
- `examples/sklearn-iris/README.md` (NEW)
- `tests/acceptance/test_final_phase8_acceptance.py::test_subgate_b_sklearn_iris_end_to_end` (NEW)

The variant module skeleton:

```python
# examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py
"""Logistic Regression baseline for iris (DEC-02 starter variant)."""
from sklearn.linear_model import LogisticRegression


def make_classifier(seed: int = 42) -> LogisticRegression:
    """Construct the v0 classifier. Hyperparameters are baseline; agents tune."""
    return LogisticRegression(max_iter=200, random_state=seed)
```

### DEC-03: result.json JSON-Schema validation

**Files:**
- `src/automil/schemas/__init__.py` (NEW; re-export `validate_result`, `RESULT_SCHEMA`)
- `src/automil/schemas/_result.py` (NEW; the validator, see OQ-2 skeleton)
- `src/automil/schemas/result.schema.json` (NEW; the JSON Schema verbatim from D-201)
- `src/automil/backends/_orchestrator_daemon.py` (~line 1090: insert validate call)
- `src/automil/graph.py` (~line 660: insert validate call in recovery loop)
- `tests/test_result_schema_validation.py` (NEW)

**Method skeleton (daemon insertion):**

```python
# _orchestrator_daemon.py, after line 1088 (collect_result)
result = self.runner.collect_result(wt_path, archive)
if result is None:
    # ... existing fall-through to status synthesis
else:
    try:
        from automil.schemas import validate_result, ValidationError
        validate_result(result)
    except ValidationError as exc:
        logger.warning(
            "result.json schema validation failed for %s: %s; "
            "see automil/schemas/result.schema.json",
            node_id, exc.message,
        )
        # Override result with crash + error pointer
        result = {
            "status": "crash",
            "composite": 0.0,
            "metrics": {},
            "error": (
                f"result.json failed schema validation: {exc.message} "
                f"(json_path={exc.json_path}); see automil/schemas/result.schema.json"
            ),
        }
```

### DEC-04: composite scoring config-driven (D-200 dict spread)

**Files:**
- `src/automil/graph.py` (5 write sites + 6 read sites; see Migration Delta Punch List)
- `src/automil/viz/static/app.js` (1-line change at line 232)
- `src/automil/backends/_orchestrator_daemon.py` (1 site at line 1055)
- `tests/test_graph_dict_spread.py` (NEW; asserts `node["metrics"]` round-trips arbitrary keys)

**Method skeleton (graph.py add_executed):**

```python
# graph.py:122-145 (replace named-field copy with dict spread)
def add_executed(self, parent_id, description, techniques, metrics, ...):
    nid = self.next_id()
    parent = self.get_node(parent_id) if parent_id else None
    parent_composite = parent.get("composite", 0.0) if parent else 0.0
    composite = metrics.get("composite", 0.0)

    node = {
        "id": nid,
        "parent_id": parent_id,
        "type": "executed",
        "status": status,
        "description": description,
        "techniques": techniques,
        # Framework-owned scalars (D-200)
        "composite": composite,
        "parent_delta": composite - parent_composite,
        "global_delta": metrics.get("global_delta", metrics.get("delta", 0.0)),
        # Consumer metrics opaque dict (D-200)
        "metrics": dict(metrics),
        # Consumer-orthogonal scalars (kept top level for ergonomics)
        "vram_gb": metrics.get("vram_gb", 0.0),
        "elapsed_min": metrics.get("elapsed_min", 0.0),
        "gpu": metrics.get("gpu", -1),
        "commit": commit,
        "archive_id": nid,
        "config_hash": config_hash,
        "potential": 0.0,
        "child_count": 0,
        "created_at": datetime.now().isoformat(),
    }
    ...
```

`vram_gb`, `elapsed_min`, `gpu` are arguably consumer-orthogonal (orchestrator-measured, not
training-script-measured), so the planner can keep them at top level. `vram_gb` is read by
init.py for empirical defaults, must stay top-level.

### DEC-05: env.required validator

**Files:**
- `src/automil/cli/check.py` (insert `_validate_env_required` after line 22 + call after line 227)
- `src/automil/templates/config.yaml.j2` (extend env block per Category G)
- `tests/test_check_env_required.py` (NEW)

### DEC-06: training-script contract documentation

**File:** `docs/training-script-contract.md` (NEW). Sections:

1. Overview (1 paragraph)
2. The contract (the 6 numbered items from D-204)
3. Minimal sklearn-iris example (link to `examples/sklearn-iris/train.py`)
4. Minimal pytorch example (5-line skeleton)
5. SIGTERM handling (2 patterns: `register_sigterm_flush` for multi-fold, inline handler for
   single-shot)
6. Common pitfalls (writing result.json after cleanup; `sys.exit(0)` without writing partial)
7. result.json schema (link to `automil/schemas/result.schema.json`)
8. Required env vars (cross-link to `automil/config.yaml: env.required`)

The doc's existence is verified by `tests/test_phase8_docs_exist.py` (NEW). Per-section content
verification is via simple substring search.

### DEC-07: final reproduction sanity

**File:** `tests/acceptance/test_final_phase8_acceptance.py` (NEW; see Final Acceptance Gate Test
Pattern section).

---

## State of the Art

The decoupling pattern in Phase 8 mirrors several well-known framework-vs-consumer separations.
Where this codebase historically diverged from those patterns:

| Anti-pattern | Current state (pre-Phase-8) | Phase 8 alignment |
|--------------|------------------------------|-------------------|
| `os.environ` injection of consumer-specific vars | `AUTOBENCH_ROOT` injected at `_orchestrator_daemon.py:721` | Replaced by config-driven `env.passthrough` (D-202) |
| Named-field metric copy | `node["test_auc"] = metrics.get("test_auc", 0.0)` 5x | Replaced by `node["metrics"] = dict(metrics)` (D-200) |
| Schemaless JSON contract | `result.json` validated only by training-script's good behavior | JSON-Schema validated at ingestion (D-201) |
| Implicit env var dependencies | Operator discovers missing `AUTOBENCH_*_ROOT` deep inside train.py | `automil check` validates `env.required` upfront (D-202) |
| One-consumer assumptions | autobench is the only consumer wired through CI | sklearn-iris ships as second consumer; final acceptance asserts both work (D-203, D-205) |

These anti-patterns are not unique to autoMIL; they occur in any framework designed against a
single consumer. The Phase 8 closure is what differentiates a "framework with one user" from a
"framework with one example consumer."

**Deprecated/outdated by Phase 8:**

- `_orchestrator_daemon.py:721` AUTOBENCH_ROOT auto-injection (was: D-05; now: removed)
- `_orchestrator_daemon.py:777-786` PYTHONPATH manipulation pointing at benchmarks/ (was: workaround
  for editable install; now: handled by env.passthrough or consumer-side config)
- `tests/test_orchestrator_env_whitelist.py:133-136` `test_autobench_root_still_injected_phase0`
  (was: positive test for the leaky behavior; now: convert to negative test)
- The four named-key Pareto check in `_reevaluate_descendants` (was: autobench-shaped 4-key
  monotonicity guard; now: composite-only dominance per OQ-9 Option B)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | jsonschema 4.26.0 is fully compatible with Draft202012Validator. [VERIFIED via lock file] | OQ-2 | LOW. Lock file confirms version; library has shipped Draft 2020-12 since 4.0. |
| A2 | sklearn 1.7.x / 1.8.x produces stable `LogisticRegression` results for iris with `random_state=42`. [ASSUMED] | OQ-4 | LOW. iris is stable across sklearn versions; expected test composite ~0.97. Acceptance threshold `>= 0.90` has wide margin. |
| A3 | The graph.json schema_version=1 does not need a bump for the dict-spread refactor. [ASSUMED] | OQ-9 | MEDIUM. Schema bump may be appropriate to mark the migration; planner should consider `schema_version=2` and a one-shot migration helper. CONTEXT does not mandate bump. |
| A4 | Sub-gate A (CCRCC) reuses Phase 1's `verify-repro` pipeline rather than running a fresh submit. [RECOMMENDED] | OQ-5 | LOW. `verify-repro` is the load-bearing Phase 1 D-50 path; reusing it preserves the exact same reproduction semantics across Phases 1 and 8. |
| A5 | Option B (composite-only Pareto dominance) is the correct choice for v1.0. [RECOMMENDED] | OQ-9 | MEDIUM. Option A is a safer migration; Option B is the cleaner architectural cut. CONTEXT D-200 leans Option B but is not explicit. Planner must commit to one. |
| A6 | The 4-key `node["test_auc"]` reads outside graph.py are limited to viz/static/app.js and one daemon site. [VERIFIED via grep] | Migration Delta | LOW. Comprehensive grep across src/automil/, benchmarks/, tests/ produced an exhaustive list. |
| A7 | The two informational comments at `_orchestrator_daemon.py:54` and `verify_repro.py:84` will not drift in normal Phase 8 work. [ASSUMED] | OQ-6 | LOW. Planner schedules the framework-purity gate AFTER the AUTOBENCH purge, so line numbers are settled. |
| A8 | sklearn-iris is sufficient as the "second consumer" for Pitfall 7 anti-acceptance. [VERIFIED via PITFALLS.md] | Pitfall 7 section | LOW. PITFALLS.md §Pitfall 7 explicitly recommends "a tiny one, e.g., a sklearn-iris training script that produces result.json" as the canonical second consumer. |
| A9 | CHANGELOG version bump is 8.0.0 (BREAKING). [VERIFIED via CONTEXT D-208 clause 10] | DEC-05 implementation hint | LOW. env.required becoming mandatory is unambiguously breaking for existing autobench consumers; major bump is correct. |
| A10 | The Phase 7 baseline of 838+ tests does NOT include the new Phase 8 tests. [VERIFIED via STATE.md] | DEC-07 acceptance | LOW. STATE.md confirms 838+ at end of Phase 7; Phase 8 D-208 clause 9 mandates >= 10 new tests. |

Most claims are VERIFIED. The two MEDIUM-risk items (A3 schema bump, A5 Option A vs B) are
deliberate planner discretion points; the planner should pick and document.

---

## Open Questions (residual, planner-resolvable)

1. **Schema version bump for graph.json.** D-200 changes the storage shape but CONTEXT does not
   mandate a `schema_version: 2` bump. Planner discretion. Recommendation: bump, with a one-shot
   migration in `graph.py:_load` that detects v1 and dict-spreads existing nodes' val_auc/etc on
   read. Cost: ~30 lines added; benefit: pre-D-200 graph.json files round-trip cleanly.

2. **Whether to ship `[examples-iris]` extra in pyproject.toml.** Recommended yes (~5 lines
   added; clean install path for sklearn-iris demo without dragging full ML stack). Planner
   discretion.

3. **Pareto dominance: 4-key (Option A) vs composite-only (Option B).** OQ-9. Recommendation:
   Option B for v1.0. Planner commits.

4. **Whether the framework-purity grep test runs as part of `automil check` or only in CI.**
   Recommendation: CI only (it requires the test file structure). `automil check` already
   validates env.required which is the operator-facing genericity guard.

5. **CHANGELOG migration body text.** Planner drafts; recommendation below.

### Recommended CHANGELOG 8.0.0 body

```markdown
## 8.0.0 - Phase 8 decoupling completion + final acceptance (unreleased)

### BREAKING: `env.required` is mandatory in `automil/config.yaml`

`automil check` now fails with `Missing required env var: <name>` if any var
declared under `env.required` is unset in the orchestrator's environment. This
catches missing dataset paths (e.g., `AUTOBENCH_CCRCC_ROOT`) BEFORE submit
rather than deep inside the training script.

**Operator recovery:** add an `env:` block to your existing `automil/config.yaml`:

```yaml
env:
  required:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    # ... add any env var your training script reads
  passthrough:
    - AUTOBENCH_OVARIAN_ROOT
    - AUTOBENCH_CCRCC_ROOT
    - HF_HOME  # if you cache HF models
```

The `passthrough` list controls which env vars are forwarded into experiment
subprocesses; the `required` list is what `automil check` enforces at startup.

### BREAKING: `node["test_auc"]` etc no longer at top level

The graph.json node payload migrates the autobench-named metrics
(`val_auc`, `val_bacc`, `test_auc`, `test_bacc`) from top-level fields into a
generic `node["metrics"]` dict. This removes the framework's hardcoded coupling
to autobench's 4-key composite recipe and unblocks non-autobench consumers
(e.g., sklearn-iris).

**Operator recovery:** if you have custom code that reads `node["test_auc"]` etc
from graph.json, change the read to `node["metrics"]["test_auc"]`. The framework's
own viz dashboard and CLI surfaces are migrated.

### Added

- `src/automil/schemas/result.schema.json` (D-201, JSON Schema 2020-12) describing
  the `result.json` contract. Validated at ingestion via `jsonschema`. Malformed
  results transition the node to `crashed` with a pointer to the schema.
- `examples/sklearn-iris/` directory with a ~75-line `train.py` demonstrating the
  contract on a non-autobench consumer.
- `docs/training-script-contract.md` (DEC-06) documenting the 6 contract items.
- `tests/test_framework_purity.py` (D-206) regression-prevents autobench leakage
  in `src/automil/`.
- `tests/acceptance/test_final_phase8_acceptance.py` (D-205) final 3-sub-gate
  acceptance gate.

### Fixed

- `_orchestrator_daemon.py` no longer auto-injects `AUTOBENCH_ROOT` (D-199).
  Consumers declare it via `env.passthrough` in `automil/config.yaml`.
```

The migration paragraph is the load-bearing operator recovery text. The planner can refine.

---

## Sources

### Primary (HIGH confidence, source code)

- `src/automil/graph.py:120-150, 198-225, 254-265, 540-570, 615-630, 690-710, 770-810`, named-field
  copy sites and Pareto dominance readers (D-200 migration target)
- `src/automil/backends/_orchestrator_daemon.py:46-66, 410-450, 700-740, 770-800, 1040-1100,
  1280-1310`, env whitelist, env.passthrough wiring, AUTOBENCH purge sites, results.tsv writer
- `src/automil/cli/check.py:1-336` (full file), env.passthrough validator (existing) and
  `_validate_slurm_directives` analog
- `src/automil/cli/init.py:194-262, 290-380`, config.yaml.j2 render context, init flow
- `src/automil/templates/config.yaml.j2:96-104`, existing `env: passthrough:` block
- `src/automil/runtime_helpers.py:1-60`, SIGTERM flush pattern for multi-fold consumers
- `src/automil/gate/manifest.py:1-100`, Phase 5 schema validation pattern (hand-rolled, not
  jsonschema)
- `src/automil/viz/static/app.js:220-260`, sparkline display reading named keys
- `src/automil/cli/lifecycle/verify_repro.py:60-135`, verify-repro pipeline (sub-gate A reusable)
- `tests/test_synthetic_consumer_roundtrip.py:1-272`, Phase 1 D-50 acceptance gate (sub-gate A
  pattern source)
- `tests/skills/test_phase7_acceptance.py:1-360`, Phase 7 D-198 acceptance gate (clause-per-test
  aggregator pattern)
- `tests/backends/test_phase6_acceptance.py:180-232`, Phase 6 D-179 acceptance gate (framework
  purity grep variant)
- `tests/gate/test_framework_purity.py:1-192`, Phase 5 framework-purity gate (in-process variant)
- `tests/test_orchestrator_env_whitelist.py:1-160`, env whitelist tests (Phase 8 negative-test
  conversion target)
- `pyproject.toml:1-55`, full project config; markers, optional-dependencies, dependency-groups
- `uv.lock:225-320, 1369-1395`, jsonschema and scikit-learn pinned versions
- `CHANGELOG.md:1-60`, current 7.0.0 entry; 8.0.0 will follow

### Secondary (HIGH confidence, planning artifacts)

- `.planning/phases/08-decoupling-completion-acceptance/08-CONTEXT.md` (D-199..D-208 verbatim)
- `.planning/phases/08-decoupling-completion-acceptance/08-PATTERNS.md` (cross-file analog map)
- `.planning/REQUIREMENTS.md:121-127, 238-244` (DEC-01..07)
- `.planning/ROADMAP.md:192-203` (Phase 8 goal + success criteria)
- `.planning/STATE.md:1-138` (current milestone position)
- `.planning/research/PITFALLS.md:185-220, 313-323, 401` (Pitfall 7 detail)

### Tertiary (HIGH confidence, runtime probes)

- `python3 -c "import jsonschema; print(jsonschema.__version__)"` -> 4.10.3 in current dev env
- `grep -rn "AUTOBENCH" src/automil/` -> 5 hits, all expected per CONTEXT D-199
- `grep -rn "val_auc\|test_auc\|val_bacc\|test_bacc" src/automil/ tests/` -> 44+ hits across the
  files enumerated in Migration Delta Punch List section

---

## Metadata

**Confidence breakdown:**
- Standard stack and library versions: HIGH (verified via uv.lock, pyproject.toml, runtime probe)
- Migration delta enumeration: HIGH (verified via comprehensive grep)
- Pattern analogs: HIGH (file:line citations verified)
- Architectural choice for OQ-9 (Option A vs B): MEDIUM (CONTEXT leans B, but is not explicit)
- Schema version bump (residual OQ): MEDIUM (planner discretion)
- sklearn-iris training script details: HIGH (skeleton verified against env injection at
  `_orchestrator_daemon.py:712-722`)
- Acceptance test fixture design: HIGH (Phase 1 / Phase 6 / Phase 7 patterns all visible)

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (jsonschema and sklearn versions are stable; the only churn risk is
new Phase 7 follow-on commits touching the same files; planner should re-grep at execute time if
more than a week elapses)

---

## Project Constraints (from CLAUDE.md)

CLAUDE.md directives that bind Phase 8 work:

| Directive | Phase 8 implication |
|-----------|---------------------|
| Address as "Leo" at start of any response | Applies to every assistant message during execution |
| Plan mode default for non-trivial tasks | Phase 8 has 11 ship clauses (D-208); plan mode is mandatory |
| Subagent strategy: liberal use to keep context clean | Wave-parallel plans should spawn dedicated subagents per area (graph migration, env validator, sklearn-iris, acceptance test) |
| Self-improvement loop: update tasks/lessons.md after corrections | Applies if Leo corrects an implementation choice during execution |
| Verification before done: never mark complete without proving | Each plan's success criteria must demonstrate the change works (test passes, grep returns expected) |
| No em dashes in prose, comments, docs | This RESEARCH.md verifies zero em dashes via post-write grep; planner inherits the same constraint |
| Conventional commits: `type: summary` | All Phase 8 commits follow `docs(08):`, `feat(08):`, `test(08):`, `refactor(08):` prefixes |
| Result contract: `result.json` with status, metrics, composite, elapsed_seconds, peak_vram_mb | This is exactly the D-201 schema; alignment confirmed |
| autoMIL is generic, autobench is one consumer (Leo memory project_automil_is_generic) | The entire Phase 8 thesis; D-199..D-208 enforce |
| Paper-campaign values are not framework constants (Leo memory feedback_paper_campaign_vs_framework) | Default `env.required: []` (no autobench bake-in); consumer fills |
| Skills only for autonomous setup; everything runtime is CLI (Leo memory feedback_skills_vs_cli) | Phase 8 ships zero new skills; all surfaces are CLI (`automil check`, `automil submit`, `automil verify-repro`) or library (`automil.schemas.validate_result`) |
| Decide engineering, ask features (Leo memory feedback_decide_engineering_ask_features) | Engineering choices in this RESEARCH.md are autonomous; only feature-level questions go to Leo (none required for Phase 8) |
| Never blind-checkout (Leo memory feedback_never_blind_checkout) | If any rollback is needed during execution, use `path.unlink()` or `git stash`; never `git checkout --` |
