# Phase 8: Decoupling Completion + Acceptance -- Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/automil/graph.py` (dict-spread refactor) | model/transform | CRUD | `src/automil/graph.py:119-145, 198-222` (named-field write site) | exact |
| `src/automil/schemas/result.schema.json` | config/schema | transform | `src/automil/gate/manifest.py` (validate-on-load pattern) | role-match |
| `src/automil/graph.py` (jsonschema ingestion call) | model/transform | request-response | `src/automil/gate/manifest.py:48-74` (validate_manifest_dict) | role-match |
| `src/automil/cli/check.py` (_validate_env_required) | utility/validator | request-response | `src/automil/cli/check.py:23-57` (_validate_slurm_directives) | exact |
| `src/automil/backends/_orchestrator_daemon.py` (env passthrough purge) | service | request-response | `src/automil/backends/_orchestrator_daemon.py:700-722` (_build_env) | exact |
| `src/automil/templates/config.yaml.j2` (env.required block) | config | transform | `src/automil/templates/config.yaml.j2:96-104` (existing env.passthrough block) | exact |
| `examples/sklearn-iris/train.py` | utility/consumer | request-response | `benchmarks/src/autobench/pipeline/clam/train.py:1-80` (result.json write pattern) | partial |
| `tests/acceptance/test_final_phase8_acceptance.py` | test/aggregator | request-response | `tests/skills/test_phase7_acceptance.py` + `tests/backends/test_phase6_acceptance.py` | exact |
| `tests/test_framework_purity.py` | test/lint | batch | `tests/gate/test_framework_purity.py` + `tests/test_backend_isolation_lint.py` + `tests/backends/test_phase6_acceptance.py:190-212` | exact |

---

## Pattern Assignments

### `src/automil/graph.py` -- dict-spread refactor (D-200)

**Analog:** `src/automil/graph.py:119-145` (add_executed) and `src/automil/graph.py:198-222` (promote)

**Current named-field copy pattern** (graph.py lines 129-138, the target for removal):
```python
        node = {
            ...
            "composite": composite,
            "global_delta": metrics.get("global_delta", metrics.get("delta", 0.0)),
            "parent_delta": composite - parent_composite,
            "test_auc": metrics.get("test_auc", 0.0),
            "test_bacc": metrics.get("test_bacc", 0.0),
            "val_auc": metrics.get("val_auc", 0.0),
            "val_bacc": metrics.get("val_bacc", 0.0),
            "vram_gb": metrics.get("vram_gb", 0.0),
            "elapsed_min": metrics.get("elapsed_min", 0.0),
            ...
        }
```

**Target dict-spread pattern** (replace the named-field copy block with):
```python
        node = {
            "id": nid,
            "parent_id": parent_id,
            "type": "executed",
            "status": status,
            "description": description,
            "techniques": techniques,
            # Framework-owned scalars (D-200): preserved, not spread
            "composite": composite,
            "parent_delta": composite - parent_composite,
            "global_delta": metrics.get("global_delta", metrics.get("delta", 0.0)),
            # Consumer metrics stored as opaque dict (D-200)
            "metrics": dict(metrics),
            "commit": commit,
            "archive_id": nid,
            "config_hash": config_hash,
            "potential": 0.0,
            "child_count": 0,
            "created_at": datetime.now().isoformat(),
        }
```

**Same pattern applies in promote()** (graph.py lines 205-219). Replace:
```python
        node["test_auc"] = metrics.get("test_auc", 0.0)
        node["test_bacc"] = metrics.get("test_bacc", 0.0)
        node["val_auc"] = metrics.get("val_auc", 0.0)
        node["val_bacc"] = metrics.get("val_bacc", 0.0)
        node["vram_gb"] = metrics.get("vram_gb", 0.0)
        node["elapsed_min"] = metrics.get("elapsed_min", 0.0)
```
with `node["metrics"] = dict(metrics)`.

**Downstream reader impact (must update in same PR):** Any code reading `node["val_auc"]` directly must become `node["metrics"].get("val_auc", 0.0)`. Search scope: `viz/server.py`, `cli/show_skill.py`, gate flows.

---

### `src/automil/schemas/result.schema.json` (D-201)

**Analog:** `src/automil/gate/manifest.py:48-74` (validate_manifest_dict -- inline Python schema)

The gate manifest uses inline Python validation. Phase 8 uses a static JSON file instead (simpler, surfaceable in error messages). The schema dict from D-201 is the authoritative spec:

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

`additionalProperties: true` is intentional -- consumers may add fields the framework does not interpret. `src/automil/schemas/` is a NEW directory; add it to the BCK-04 lint extension allowlist as PURE (D-207).

---

### `src/automil/graph.py` -- jsonschema ingestion call (D-201)

**Analog:** `src/automil/gate/manifest.py:104-107` (read_manifest validate-on-load)

```python
# gate/manifest.py lines 104-107: validate on load before constructing
def read_manifest(path: Path) -> GateManifest:
    d = json.loads(path.read_text())
    validate_manifest_dict(d)
    # ... construct dataclass
```

**Phase 8 pattern** -- add to graph.py ingestion path (before node mutation):
```python
import importlib.resources
import jsonschema

_RESULT_SCHEMA_PATH = Path(__file__).parent / "schemas" / "result.schema.json"

def _validate_result_json(result: dict) -> None:
    """Validate result.json against automil/schemas/result.schema.json (D-201).

    Raises jsonschema.ValidationError on schema mismatch; callers transition
    node to crashed with error: result.json failed schema validation: <detail>
    """
    schema = json.loads(_RESULT_SCHEMA_PATH.read_text())
    jsonschema.validate(instance=result, schema=schema)
```

Call site in orchestrator ingestion (before calling `graph.promote()`):
```python
try:
    _validate_result_json(result_data)
except jsonschema.ValidationError as exc:
    self._mark_crashed(
        node_id, spec,
        f"result.json failed schema validation: {exc.message}; "
        f"see automil/schemas/result.schema.json"
    )
    return
```

---

### `src/automil/cli/check.py` -- _validate_env_required helper (D-202)

**Analog:** `src/automil/cli/check.py:23-57` (_validate_slurm_directives)

```python
# cli/check.py lines 23-57: template to mirror exactly
def _validate_slurm_directives(config: dict) -> None:
    """Raise SlurmDirectivesIncompleteError if SLURM config is incomplete (D-172).

    Pure function: no I/O, no Click. Wave-0 unit tests exercise it directly.
    """
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
        elif isinstance(val, str) and val == _TODO_SENTINEL:
            missing.append(key)

    if missing:
        raise SlurmDirectivesIncompleteError(missing)
```

**Phase 8 analog** (_validate_env_required to add in check.py):
```python
def _validate_env_required(config: dict) -> list[str]:
    """Return list of missing required env vars declared in config (D-202).

    Pure function: no I/O, no Click. Returns names of vars that are declared
    under env.required but absent from os.environ. Empty list = all present.
    """
    env_section = (config or {}).get("env") or {}
    required: list[str] = env_section.get("required", []) or []
    return [name for name in required if name not in os.environ]
```

Call site added to check() body, mirroring the slurm block pattern (lines 166-179):
```python
    missing_env = _validate_env_required(config)
    for name in missing_env:
        issues.append(
            f"Missing required env var: {name}; "
            f"see automil/config.yaml: env.required"
        )
```

---

### `src/automil/backends/_orchestrator_daemon.py` -- AUTOBENCH_ROOT purge (D-199)

**Analog:** `src/automil/backends/_orchestrator_daemon.py:700-722` (_build_env body)

```python
# _orchestrator_daemon.py lines 700-722: existing env layering pattern
def _build_env(self, *, gpu_id, node_id, archive, spec, pythonpath, worktree_benchmarks):
    env: dict[str, str] = {}

    # 1. System whitelist (literal + prefix-glob).
    for key, value in os.environ.items():
        if key in _SYSTEM_ENV_WHITELIST_LITERAL or key.startswith(_SYSTEM_ENV_WHITELIST_PREFIX):
            env[key] = value

    # 2. Config-driven passthrough (literal names only).
    for key in self._env_passthrough:
        if key in os.environ:
            env[key] = os.environ[key]

    # 3. Orchestrator-injected (always overrides 1 + 2).
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["AUTOMIL_GPU"] = "0"
    env["AUTOMIL_DESC"] = spec.get("description", "")
    env["AUTOMIL_NODE_ID"] = node_id
    env["AUTOMIL_RESULTS_DIR"] = str(archive.resolve())
    # D-05: AUTOBENCH_ROOT injection stays in Phase 0; Phase 8/DEC-01
    # owns its removal. Consumer configs declare it under env.passthrough
    # to be wired correctly through the transition.
    env["AUTOBENCH_ROOT"] = str(worktree_benchmarks.resolve())  # <-- REMOVE THIS LINE
    env["PYTHONPATH"] = pythonpath                               # <-- REMOVE THIS LINE
```

**Phase 8 action:** Remove lines 721-722 (`AUTOBENCH_ROOT` and `PYTHONPATH` injection). The `_env_passthrough` loop (layer 2) already covers consumer-declared vars if they add `AUTOBENCH_CCRCC_ROOT` etc. to `env.passthrough`. The `PYTHONPATH` manipulation (lines 777-780) referencing `worktree_benchmarks / "src"` is similarly removed; consumers own their own PYTHONPATH via `env.passthrough`. The `worktree_benchmarks` and `pythonpath` parameters to `_build_env` may be removed once no longer referenced.

**After purge**, layer 3 becomes:
```python
    # 3. Orchestrator-injected (always overrides 1 + 2).
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["AUTOMIL_GPU"] = "0"
    env["AUTOMIL_DESC"] = spec.get("description", "")
    env["AUTOMIL_NODE_ID"] = node_id
    env["AUTOMIL_RESULTS_DIR"] = str(archive.resolve())
```

---

### `src/automil/templates/config.yaml.j2` -- env.required block (D-202)

**Analog:** `src/automil/templates/config.yaml.j2:96-104` (existing env.passthrough block)

```yaml
# config.yaml.j2 lines 96-104: existing env section (pattern to extend)
# --- Environment passthrough (D-87, TRJ-04) ---
# Variables in this list are forwarded from the orchestrator process to each
# experiment subprocess.  AUTOMIL_RUNTIME must be here so the trajectory
# recorder inside the experiment sees the declared runtime value.
env:
  passthrough:
    - AUTOMIL_*       # All automil framework variables (includes AUTOMIL_RUNTIME)
    - AUTOMIL_RUNTIME # Runtime declaration: explicit, never inferred (D-87)
```

**Phase 8 addition** -- add `required:` list above `passthrough:`:
```yaml
env:
  # Variables that MUST be set before experiments run (D-202).
  # automil check validates these at startup; missing var fails check.
  # Empty by default (generic consumers like sklearn-iris need no env vars).
  required: []

  # Variables forwarded from orchestrator process into experiment subprocesses.
  passthrough:
    - AUTOMIL_*       # All automil framework variables (includes AUTOMIL_RUNTIME)
    - AUTOMIL_RUNTIME # Runtime declaration: explicit, never inferred (D-87)
```

The `required: []` default is intentional: existing consumers that have not yet added this key get no validation errors; they opt in by populating the list.

---

### `examples/sklearn-iris/train.py` (D-203)

**Analog:** `benchmarks/src/autobench/pipeline/clam/train.py:1-55` (result.json write pattern, seed_everything, signal handling)

The autobench train.py is the contract reference. The sklearn-iris version is a minimal (~80 line) distillation. Key patterns to copy:

**result.json write pattern** (from autobench; extract the shape):
```python
# Write result.json to CWD (orchestrator sets CWD = archive dir)
import json, pathlib, signal, sys

_result: dict = {"status": "budget_killed", "partial": True}

def _write_result() -> None:
    pathlib.Path("result.json").write_text(json.dumps(_result))

def _sigterm_handler(signum, frame):
    _write_result()
    sys.exit(0)

signal.signal(signal.SIGTERM, _sigterm_handler)
```

**Main body pattern** for sklearn-iris (condense from autobench structure):
```python
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

iris = load_iris()
X_train, X_test, y_train, y_test = train_test_split(
    iris.data, iris.target, test_size=0.2, random_state=42
)
clf = LogisticRegression(max_iter=200)
clf.fit(X_train, y_train)
y_pred = clf.predict(X_test)
acc = float(accuracy_score(y_test, y_pred))
f1 = float(f1_score(y_test, y_pred, average="macro"))

_result = {
    "status": "completed",
    "composite": acc,
    "metrics": {"accuracy": acc, "f1": f1},
}
_write_result()
```

**CUDA_VISIBLE_DEVICES** must be consumed (even as a no-op) to satisfy contract item 2 from D-204:
```python
# Honor CUDA_VISIBLE_DEVICES per training-script contract (no-op for CPU sklearn)
_ = os.environ.get("CUDA_VISIBLE_DEVICES", "")
```

---

### `tests/acceptance/test_final_phase8_acceptance.py` (D-205)

**Analog:** `tests/skills/test_phase7_acceptance.py` (Phase 7 D-198 gate) and `tests/backends/test_phase6_acceptance.py` (Phase 6 D-179 gate)

**File-level structure pattern** (from test_phase7_acceptance.py lines 1-23):
```python
"""D-205 acceptance gate (Phase 8 / DEC-01..07).

Single-file aggregator that asserts every clause of D-208 is satisfied. Mirrors
the Phase 7 D-198 / test_phase7_acceptance.py pattern: each clause is a
dedicated test function; passing all N means Phase 8 is shippable.

Run: `uv run pytest tests/acceptance/test_final_phase8_acceptance.py -v`
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
```

**Per-clause function pattern** (from test_phase6_acceptance.py lines 29-39):
```python
def test_phase8_acceptance_clause_01_framework_purity():
    """D-208 #1: framework purity grep returns zero non-allowlisted matches."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_framework_purity.py", "-q", "--tb=line"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0, (
        f"framework purity test failed:\n{out.stdout[-500:]}\n{out.stderr[-500:]}"
    )
```

**Data-gated clause pattern** (from test_phase7_acceptance.py; use for Sub-gate A):
```python
@pytest.mark.requires_ccrcc_data
def test_phase8_acceptance_clause_subgate_a_ccrcc_reproduction():
    """D-205 Sub-gate A: CCRCC node_0176 reproduced within +-0.005."""
    pytest.skip("requires CCRCC data; run on Leo's workstation only")
```

**Test count floor assertion** (from test_phase7_acceptance.py lines 181-203):
```python
def test_phase8_acceptance_clause_baseline_preserved():
    """D-208 #9: Phase 7 baseline (838+ tests) preserved; >=10 new added."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    collected_line = [
        l for l in result.stdout.splitlines()
        if "collected" in l and "test" in l
    ]
    assert collected_line, f"no collection summary:\n{result.stdout[-500:]}"
    count = int(collected_line[-1].split()[0])
    assert count >= 848, (
        f"test count regressed below Phase-7 baseline + 10: got {count}, need >=848"
    )
```

---

### `tests/test_framework_purity.py` (D-206)

**Analog:** `tests/gate/test_framework_purity.py:38-55` (autobench-ref grep pattern) and `tests/test_backend_isolation_lint.py:26-51` (subprocess lint runner) and `tests/backends/test_phase6_acceptance.py:190-212` (scoped purity clause)

**Allowlist + subprocess grep pattern** (extending the Phase 6 inline clause at test_phase6_acceptance.py lines 190-212):
```python
# test_phase6_acceptance.py lines 190-212: pattern to mirror at file scope
def test_d179_clause_10_framework_purity():
    backends_dir = _SRC_AUTOMIL / "backends"
    for new_backend in ("slurm.py", "ray.py"):
        backend_file = backends_dir / new_backend
        if not backend_file.exists():
            continue
        out = subprocess.run(
            ["grep", "-n", "-E", "autobench|AUTOBENCH_|benchmarks/", str(backend_file)],
            capture_output=True, text=True,
        )
        # grep returns 1 when no matches, 0 when matches found.
        assert out.returncode != 0 or out.stdout.strip() == "", (
            f"framework purity violated; {new_backend} contains autobench refs:\n{out.stdout}"
        )
```

**Full-scope purity test pattern** (from gate/test_framework_purity.py lines 38-55):
```python
def test_gate_no_autobench_refs():
    offenders: list[tuple[Path, str]] = []
    for path in GATE_FILES:
        content = path.read_text()
        for token in ("autobench", "AUTOBENCH_", "benchmarks/"):
            if token in content:
                offenders.append((path.relative_to(_REPO_ROOT), token))

    assert not offenders, (
        f"Framework purity (D-148): {offenders},  "
        "gate/ must be autobench-free. "
    )
```

**Phase 8 combined pattern** (subprocess grep + allowlist, per D-206 spec):
```python
_ALLOWED_LINES: frozenset[str] = frozenset({
    # Permanent informational comments only (no functional references):
    "src/automil/backends/_orchestrator_daemon.py:54",
    "src/automil/cli/lifecycle/verify_repro.py:84",
})

def _is_in_allowlist(grep_line: str, allowed: frozenset[str]) -> bool:
    """Return True if grep_line matches an allowlisted file:lineno prefix."""
    for entry in allowed:
        if grep_line.startswith(entry):
            return True
    return False

def test_framework_purity_no_autobench_leakage():
    """D-206: grep src/automil/ for autobench refs; non-allowlisted hits fail."""
    result = subprocess.run(
        ["grep", "-rn", "-E", "autobench|AUTOBENCH_|benchmarks/", str(_SRC_AUTOMIL)],
        capture_output=True, text=True,
    )
    # POSIX grep exit codes: 0 = matches found, 1 = no matches, 2 = error.
    # "no matches found" (exit 1) is the SUCCESS path here.
    if result.returncode == 2:
        pytest.fail(f"grep error: {result.stderr}")
    matches = [
        line for line in result.stdout.splitlines()
        if line.strip() and not _is_in_allowlist(line, _ALLOWED_LINES)
    ]
    assert matches == [], f"autobench leakage found in src/automil/:\n" + "\n".join(matches)
```

---

## Shared Patterns

### jsonschema import (already transitive, no new top-level dep)

**Source:** `src/automil/gate/manifest.py` (Phase 5 usage)
**Apply to:** `graph.py` result.json validation call
```python
import jsonschema  # transitive dep since Phase 5; no new install required
```

### Pure-function validator + click integration

**Source:** `src/automil/cli/check.py:23-57` + `check.py:165-179`
**Apply to:** `_validate_env_required` in check.py

Pattern: pure function returns problem list; caller integrates into `issues` list; final report block handles exit.

### Atomic write for new schema files

**Source:** `src/automil/gate/manifest.py:86-100` (write_manifest tmpfile + os.replace)
**Apply to:** `src/automil/schemas/result.schema.json` is a static file (no runtime write needed); however any test fixture writing a schema uses the same tmpfile pattern.

### subprocess.run with capture_output + returncode assertion

**Source:** `tests/backends/test_phase6_acceptance.py:33-38` (used in every clause)
**Apply to:** All acceptance gate clauses in `tests/acceptance/test_final_phase8_acceptance.py`
```python
out = subprocess.run(
    [sys.executable, "-m", "pytest", "<target>", "-q", "--tb=line"],
    cwd=_REPO_ROOT, capture_output=True, text=True,
)
assert out.returncode == 0, f"<clause> failed:\n{out.stdout[-500:]}\n{out.stderr[-500:]}"
```

---

## No Analog Found

All Phase 8 files have analogs. No new patterns without precedent in the codebase.

| File | Note |
|------|------|
| `docs/training-script-contract.md` | Markdown docs only; no code analog needed. Narrative modeled after `08-CONTEXT.md:D-204` section and the `_shared/automil-setup/SKILL.md` structure. |
| `examples/sklearn-iris/automil/config.yaml` | Instantiated config; use `automil init` output as template base. `env.required: []` + `env.passthrough: []` defaults. |

---

## Caveats / Anti-patterns

### 1. Do NOT validate result.json with custom regex or manual key checks

Use `jsonschema.validate(instance=result, schema=schema)` exactly as shown above. Manual checks like `if "composite" not in result` bypass the schema's `additionalProperties: true` semantics and diverge from the declared contract at `automil/schemas/result.schema.json`. The schema file IS the single source of truth.

### 2. Do NOT add sklearn as a top-level framework dependency

`sklearn` belongs only in a `[examples-iris]` optional extra in `pyproject.toml`. The framework tests that verify the consumer run with `pytest.importorskip("sklearn")` or skip gracefully. The framework itself (`src/automil/`) must never import sklearn.

### 3. Do NOT silence framework purity test on grep exit code 1

POSIX `grep` exits 1 when NO matches are found, which is the SUCCESS path. Exits 0 means matches WERE found, which is the failure path. The pattern `if result.returncode == 2: pytest.fail(...)` handles the error case. Do NOT treat exit 1 as a failure. Concretely: `assert result.returncode != 0` is WRONG in this context; the check is `assert matches == []` after filtering output lines.

### 4. Do NOT migrate viz/server.py metric readers without updating their tests

After the dict-spread refactor, `node["val_auc"]` references in `viz/server.py` and `cli/show_skill.py` become `node["metrics"].get("val_auc", 0.0)`. These readers have existing tests. Update the readers AND the tests in the same commit. Do not defer the reader update: a half-migrated graph.py that stores `node["metrics"]` but leaves readers accessing `node["val_auc"]` directly will produce silent `KeyError` regressions.

### 5. Do NOT execute consumer code during the framework purity grep test

`tests/test_framework_purity.py` uses `subprocess.run(["grep", ...])` -- pure filesystem read. It does not import or execute any consumer module. Do not add `import autobench` or any training-script invocation inside this test file.

### 6. Do NOT add `env.required` keys with TODO sentinel values to the config template

The `_TODO_SENTINEL` pattern from `_validate_slurm_directives` (check.py line 20) applies here too. The `_validate_env_required` function must treat a var that IS set but equals `"TODO_FILL_IN"` as present (env vars do not have sentinel semantics the way YAML config keys do). Env var validation is purely presence-based: `name not in os.environ`.

### 7. Do NOT amend commits when the BCK-04/purity pre-commit hook fails

Per Leo's memory `feedback_never_blind_checkout`: if a hook fails, fix the issue, re-stage, and create a NEW commit. Do not use `git commit --amend` after a hook failure, as it modifies the previous commit.

---

## Metadata

**Analog search scope:** `src/automil/`, `tests/`, `benchmarks/src/autobench/pipeline/clam/`, `scripts/`
**Files scanned:** 10 (all from required_reading list)
**Pattern extraction date:** 2026-05-07
**D-cross-references:** D-199, D-200, D-201, D-202, D-203, D-204, D-205, D-206, D-207, D-208
