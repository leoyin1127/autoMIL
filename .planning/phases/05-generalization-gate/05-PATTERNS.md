# Phase 5: Generalization gate - Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 20 (8 new gate/ + 3 new cli/ + 1 template + 9 modified/extended)
**Analogs found:** 18 / 20 (gate/stats.py and tests/gate/test_stats.py are greenfield — no scipy usage currently in src/automil/)

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `src/automil/gate/__init__.py` | package surface | — | `src/automil/cells/__init__.py` | exact |
| `src/automil/gate/manifest.py` | model + service | CRUD + file-I/O | `src/automil/cells/state.py` | exact (frozen dataclass + atomic write) |
| `src/automil/gate/nominate.py` | service | CRUD | `src/automil/cells/registry.py` (get_or_create_cell idempotent pattern) | role-match |
| `src/automil/gate/evaluate.py` | service | request-response (Backend.submit poll loop) | `src/automil/backends/local.py` submit path | role-match |
| `src/automil/gate/promote.py` | service | CRUD + event-driven | `src/automil/cells/registry.py` + `cli/lifecycle/promote_variant.py` | partial-match (composes both) |
| `src/automil/gate/stats.py` | utility | transform (pure function) | `src/automil/cells/cap.py` (pure-function discipline) | role-match |
| `src/automil/cli/gate.py` | CLI group | request-response | `src/automil/cli/cell.py` | exact |
| `src/automil/cli/nominate.py` | CLI command | request-response | `src/automil/cli/propose.py` (top-level @main.command) | exact |
| `src/automil/cli/promote.py` | CLI command | request-response | `src/automil/cli/lifecycle/promote_variant.py` (top-level command structure) | role-match |
| `src/automil/templates/config.yaml.j2` | config template | — | itself (extend existing `cap:` section pattern) | exact |
| `src/automil/graph.py` | model | CRUD | itself — additive: new helpers `nominations_in_window`, `promotion_rate`, held_out filter | exact |
| `src/automil/cli/__init__.py` | CLI registry | — | itself — add `gate`, `nominate`, `promote` imports | exact |
| `src/automil/cli/propose.py` (rank cmd) | CLI command | request-response | itself — extend `rank()` with held-out filter | exact |
| `src/automil/trajectory/redactor.py` | middleware | transform | itself — extend `_PATTERNS` + `_walk` with held-out node-id lookup | exact |
| `src/automil/viz/server.py` | service | SSE / event-driven | itself — add `/api/promotion-rate` route alongside `/events` | exact |
| `src/automil/backends/base.py` (JobSpec) | model | — | itself — additive: kw-only `metadata` field | exact |
| `tests/gate/conftest.py` | test fixture | — | `benchmarks/tests/conftest.py` + pattern from `tests/test_graph.py` tmp_path | role-match |
| `tests/gate/test_manifest.py` | test | — | `tests/test_graph.py` (graph + tmp_path fixtures) | role-match |
| `tests/gate/test_stats.py` | test | — | no existing scipy tests — greenfield | no-analog |
| `tests/gate/test_pitfall6_held_out_isolation.py` | test (load-bearing) | — | `tests/test_integration.py` (end-to-end graph fixture + mock) | partial-match |

---

## Pattern Assignments

---

### `src/automil/gate/__init__.py` (package surface)

**Analog:** `src/automil/cells/__init__.py` (lines 1-47)

**Public surface pattern** (lines 1-47):
```python
"""Gate generalization subpackage (GTE-01..06 / D-135..D-151).

Public surface:
    05-01: GateManifest, read_manifest, write_manifest, load_or_create_manifest
    05-02: nominate
    05-03: evaluate_candidate
    05-04: promote
    05-05: paired_wilcoxon_with_bootstrap, bonferroni_correct
"""
from __future__ import annotations
import logging

from automil.gate.manifest import GateManifest, read_manifest, write_manifest_committed, load_manifest
from automil.gate.nominate import nominate
from automil.gate.evaluate import evaluate_candidate
from automil.gate.promote import promote
from automil.gate.stats import paired_wilcoxon_with_bootstrap, bonferroni_correct

logger = logging.getLogger(__name__)

__all__ = [
    "GateManifest",
    "bonferroni_correct",
    "evaluate_candidate",
    "load_manifest",
    "nominate",
    "paired_wilcoxon_with_bootstrap",
    "promote",
    "read_manifest",
    "write_manifest_committed",
]
```

**Copy from:** `src/automil/cells/__init__.py:1-47` — increment-per-plan docstring style; alphabetical `__all__`; lazy imports at module level (not inside functions) because gate/ modules are small and have no circular-import risk.

---

### `src/automil/gate/manifest.py` (model + service, CRUD + file-I/O)

**Primary analog:** `src/automil/cells/state.py`
**Secondary analog:** `src/automil/cli/lifecycle/promote_variant.py` (git subprocess pattern, lines 104-126)

**Frozen dataclass pattern** (cells/state.py lines 31-69):
```python
# Copy this frozen-dataclass structure exactly
@dataclass(frozen=True)
class Cell:
    cell_id: str
    dataset: str
    # ...
    status: CellStatus
```
Apply as:
```python
@dataclass(frozen=True)
class GateManifest:
    """Immutable snapshot of a pre-registered gate manifest (D-137).

    Frozen so instances cannot be mutated. Schema mutations go through
    retire-manifest (write new file) + register-manifest (new instance).
    Hashable + JSON-serialisable via dataclasses.asdict(manifest).
    """
    parent_id: str
    created_at: str            # ISO-8601 UTC
    git_committed_at_sha: str  # "PENDING" until commit resolves; second commit backfills
    held_out_cells: tuple[tuple[str, str, str, str], ...]  # (cell_id, dataset, encoder, task)
    K: int                     # minimum cells that must pass
    p_threshold: float         # pre-Bonferroni alpha (default 0.05)
    bootstrap_reps: int        # default 1000
    win_definition: str        # human-readable string for paper citation
    schema_version: str        # "gate-v1"
```

**Atomic write pattern** (cells/state.py lines 94-116 — copy verbatim, change class name):
```python
def write_manifest(manifest: GateManifest, manifests_dir: Path) -> None:
    manifests_dir.mkdir(parents=True, exist_ok=True)
    path = manifests_dir / f"{manifest.parent_id}.gate_manifest.json"
    payload = json.dumps(dataclasses.asdict(manifest), indent=2)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(manifests_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

**Atomic write + git commit pattern** (NEW — composing state.py:94-116 + promote_variant.py:104-126):
```python
# promote_variant.py lines 104-126: the git-stage half (no commit)
result = subprocess.run(
    ["git", "mv", str(src), str(dst)],
    cwd=git_root, capture_output=True, text=True,
)
if result.returncode != 0:
    raise click.ClickException(...)

# For gate/manifest.py: extend this to include commit + rollback
# subprocess.run form: ["git", ...] list (NOT shell string — injection-safe)
# check=True raises CalledProcessError; capture_output=True provides stderr for diagnostics
subprocess.run(["git", "add", str(path)], cwd=git_root, check=True, capture_output=True, text=True)
subprocess.run(["git", "commit", "-m", msg], cwd=git_root, check=True, capture_output=True, text=True)
sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_root, check=True, capture_output=True, text=True).stdout.strip()
# On CalledProcessError: path.unlink() — NEVER git checkout (Leo memory: feedback_never_blind_checkout)
```

**Immutability guard** (NEW — D-138 #5):
```python
if path.exists():
    raise FileExistsError(
        f"Manifest already exists for {manifest.parent_id}. "
        f"Run `automil gate retire-manifest {manifest.parent_id} --reason '...'` first."
    )
```

**Imports pattern** for manifest.py:
```python
from __future__ import annotations
import dataclasses
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
```

---

### `src/automil/gate/nominate.py` (service, CRUD)

**Analog:** `src/automil/cells/registry.py` (get_or_create_cell idempotent pattern, lines 31-82)

**Idempotent status mutation pattern** (registry.py lines 54-82):
```python
# cells/registry.py: idempotency via early-return if already in target state
if path.exists():
    cell = read_cell(path)
    if cell.budget_seconds != budget_seconds ...:
        logger.info("Cell %s already open ...; ignoring override", ...)
    return cell
```
Apply as:
```python
def nominate(node_id: str, graph: ExperimentGraph) -> None:
    """Mutate graph node status keep -> candidate. Idempotent (D-136, D-142).

    Appends to node["history"] with timestamp so the trajectory captures
    the nomination event. Does NOT call graph.save() — caller must save
    after any sequence of mutations (same discipline as cells/registry.py).
    """
    node = graph.get_node(node_id)
    if node is None:
        raise ValueError(f"Node {node_id!r} not found in graph")
    if node.get("status") == "candidate":
        logger.info("nominate: %s already candidate; no-op", node_id)
        return
    if node.get("status") not in ("keep",):
        raise ValueError(
            f"Cannot nominate {node_id}: status={node.get('status')!r}; "
            f"only 'keep' nodes can be nominated (D-136 status flow)"
        )
    node["status"] = "candidate"
    node.setdefault("history", []).append({
        "event": "nominated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_initiated": False,  # overridden to True if auto_nominate=true (D-142)
    })
```

**graph.save() discipline** — caller saves, not the mutation function itself. See cells/registry.py: `write_cell(cell, cells_dir)` is called AFTER all mutations, by the caller layer.

---

### `src/automil/gate/evaluate.py` (service, request-response)

**Analog:** `src/automil/backends/local.py` submit path (lines 89-148) + `cells/registry.py:get_or_create_cell`

**Backend.submit call pattern** (local.py lines 89-148 shows queue_spec construction; the gate reuses the same ABC method):
```python
# From local.py lines 140-142: metadata dict is set on the queue_spec
queue_spec.setdefault("metadata", {})["backend"] = "local"
# Gate evaluate.py extends this: spec.metadata carries gate-eval flags
# (via the new JobSpec.metadata field — Option A from RESEARCH.md Pattern 3)
```

**Per-cell submit + poll pattern** (NEW — gate evaluate.py core loop):
```python
def evaluate_candidate(
    candidate_node_id: str,
    manifest: GateManifest,
    backend: Backend,
    graph: ExperimentGraph,
) -> tuple[list[dict], list[str]]:
    """Submit held-out evaluations via backend.submit(); poll to completion.

    Returns:
        (per_cell_results, skipped_cells)
        per_cell_results: list of {cell_id, candidate_composite, parent_composite, delta}
        skipped_cells: list of cell_ids skipped due to cap exhaustion (D-150)
    """
    handles = {}
    skipped = []
    for hc in manifest.held_out_cells:
        cell_id, dataset, encoder, task = hc
        cell = get_or_create_cell(dataset, encoder, candidate_node_id, ...)
        if is_refusing_new(cell):
            skipped.append(cell_id)   # D-150: cap-exhausted cells tracked
            continue
        spec = JobSpec(
            node_id=graph.next_id(),
            # ... overlay = candidate overlay ...
            metadata=(                # Option A: new JobSpec field (D-140)
                ("gate_eval", "true"),
                ("held_out", "true"),
                ("gate_parent_node", candidate_node_id),
                ("cell_id", cell_id),
                ("edge_type", "gate_eval"),
            ),
        )
        handle = backend.submit(spec)
        # Tag child node in graph (additive free-form fields per D-140)
        node = graph.get_node(spec.node_id)
        if node:
            node["edge_type"] = "gate_eval"
            node["metadata"] = dict(spec.metadata)
        handles[cell_id] = handle

    # Poll loop — all submitted in parallel, poll until all terminal
    results = _poll_until_complete(handles, backend, graph, manifest)
    return results, skipped
```

**cap check before submit** (cells/registry.py lines 114-120):
```python
def is_refusing_new(cell: Cell) -> bool:
    return cell.status in (CellStatus.REFUSING_NEW, CellStatus.TERMINATING, CellStatus.FINALIZED)
```

---

### `src/automil/gate/promote.py` (service, CRUD + event-driven)

**Analog:** `src/automil/cells/registry.py` (mutation discipline) + `cli/lifecycle/promote_variant.py` (status flow pattern)

**Status mutation pattern** (graph node dict mutation — same as promote_variant.py line 100-102 which reads source_node):
```python
def promote(
    candidate_node_id: str,
    backend: Backend,
    graph: ExperimentGraph,
    manifests_dir: Path,
) -> bool:
    """Two-stage gate: evaluate held-out cells, run stats, update status.

    Returns True if promoted (status -> 'registered'), False if reverted
    to 'keep' (gate fail) or INCONCLUSIVE (too many cells skipped per D-150).

    Emits promotion_rate event to gate_log.jsonl (separate from trajectory).
    """
    manifest = load_manifest(candidate_node_id, manifests_dir)  # reads parent's manifest
    per_cell_results, skipped = evaluate_candidate(candidate_node_id, manifest, backend, graph)

    K_effective = manifest.K - len(skipped)
    if K_effective < 2:   # D-150 / Pitfall 1: INCONCLUSIVE path
        _record_gate_result(candidate_node_id, "inconclusive", skipped=skipped, ...)
        return False

    deltas = np.array([r["delta"] for r in per_cell_results])
    p_corrected = bonferroni_correct(manifest.p_threshold, K_effective)
    passed, p_val, ci, wins = paired_wilcoxon_with_bootstrap(
        deltas, p_corrected, manifest.bootstrap_reps
    )
    gate_pass = passed and (wins >= K_effective)

    node = graph.get_node(candidate_node_id)
    node["status"] = "registered" if gate_pass else "keep"
    node.setdefault("history", []).append({
        "event": "gate_result",
        "result": "pass" if gate_pass else "fail",
        "p_value": p_val,
        "ci_low": ci[0],
        "ci_high": ci[1],
        "wins": wins,
        "K_effective": K_effective,
        "cells_skipped_due_to_cap": skipped,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    graph.save()
    return gate_pass
```

---

### `src/automil/gate/stats.py` (utility, pure-function transform)

**Analog:** `src/automil/cells/cap.py` (pure-function discipline — no I/O, explicit arg injection)

**Pure-function discipline** (cap.py lines 1-41 — copy docstring style and arg-injection pattern):
```python
# cap.py: no I/O, caller injects time.time() as now_epoch
def next_status(cell: Cell, now_epoch: float, running_count: int) -> CellStatus:
    """Pure function — no I/O, no global state, no time.time() call."""
```
Apply as (D-141 locked implementation from RESEARCH.md Pattern 2):
```python
# Source: gate/stats.py
import numpy as np
from scipy.stats import wilcoxon, bootstrap   # scipy 1.17.1 verified installed

def paired_wilcoxon_with_bootstrap(
    deltas: np.ndarray,
    p_threshold: float,       # caller pre-divides by K via bonferroni_correct()
    bootstrap_reps: int = 1000,
    rng_seed: int | None = None,
) -> tuple[bool, float, tuple[float, float], int]:
    """Pure paired Wilcoxon + BCa bootstrap on per-cell deltas. No I/O."""
    if len(deltas) < 1:
        return (False, 1.0, (0.0, 0.0), 0)
    if np.all(deltas == 0):
        return (False, 1.0, (0.0, 0.0), 0)
    wres = wilcoxon(deltas, zero_method="wilcox", alternative="greater")
    rng = np.random.default_rng(rng_seed)
    bres = bootstrap(
        (deltas,), np.median, n_resamples=bootstrap_reps,
        confidence_level=0.95, method="BCa", rng=rng,
    )
    ci_low = float(bres.confidence_interval.low)
    ci_high = float(bres.confidence_interval.high)
    individual_wins = int(np.sum(deltas > 0))
    passes = (wres.pvalue <= p_threshold) and (ci_low > 0)
    return (passes, float(wres.pvalue), (ci_low, ci_high), individual_wins)


def bonferroni_correct(p_threshold: float, K: int) -> float:
    """Divide alpha by K. One direction only — never multiply p-values (Pitfall 4)."""
    if K < 1:
        raise ValueError(f"K must be >= 1; got {K}")
    return p_threshold / K
```

**Flag for planner:** This is the ONLY file in `src/automil/` that imports scipy. The dependency must be lifted from `[project.optional-dependencies.ml]` to `[project.dependencies]` in `pyproject.toml` (see RESEARCH.md Standard Stack > Installation). scipy 1.17.1 is already installed transitively; this makes it explicit.

---

### `src/automil/cli/gate.py` (CLI group)

**Analog:** `src/automil/cli/cell.py` (lines 1-128 — exact structural match)

**Group registration pattern** (cell.py lines 1-15):
```python
"""cell subgroup: cell budget status and list commands (CAP-06 / D-125)."""
from __future__ import annotations
import json
from pathlib import Path
import click
from automil.cli import main

@main.group("cell")
def cell_group() -> None:
    """Cell budget-cap management commands."""
    pass
```
Apply as:
```python
"""gate subgroup: gate manifest + promotion commands (GTE-01..06 / D-145)."""
from __future__ import annotations
from pathlib import Path
import click
from automil.cli import main

@main.group("gate")
def gate_group() -> None:
    """Generalization gate manifest management commands."""
    pass
```

**Subcommand pattern** (cell.py lines 58-107 — the `@cell_group.command("status")` shape):
```python
@cell_group.command("status")
@click.argument("cell_id", required=False)
@click.option("--no-header", is_flag=True, default=False, help="Suppress header row.")
def cell_status(cell_id: str | None, no_header: bool) -> None:
    """Show budget state for one cell (or all cells if CELL_ID omitted)."""
    from automil.cells import get_cell, list_cells  # lazy import pattern
    ...
```
Apply four subcommands: `register-manifest`, `retire-manifest`, `status`, `stats`. Use `@gate_group.command("register-manifest")` etc.

**Lazy import pattern** (cell.py line 24-26):
```python
from automil.cli._helpers import _find_automil_dir  # lazy
```
All gate module imports inside command bodies — prevents circular import at CLI group definition time.

---

### `src/automil/cli/nominate.py` (top-level CLI command)

**Analog:** `src/automil/cli/propose.py` (lines 10-40 — top-level `@main.command()` pattern)

**Top-level command pattern** (propose.py lines 10-38):
```python
@main.command()
@click.option("--n", default=6, help="Number of proposals to return")
def rank(n: int, max_per_branch: int):
    """Show top-ranked proposals from the experiment graph."""
    adir = _find_automil_dir()
    graph_path = adir / "graph.json"
    if not graph_path.exists():
        click.echo("No graph.json found. ...")
        return
    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(graph_path))
```
Apply as:
```python
@main.command("nominate")
@click.argument("node_id")
@click.option("--agent", is_flag=True, default=False, hidden=True,
              help="Mark as agent-initiated (audit log only).")
def nominate_cmd(node_id: str, agent: bool) -> None:
    """Nominate a keep-status node as a gate candidate (D-142)."""
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph
    from automil.gate import nominate
    graph = ExperimentGraph(path=str(adir / "graph.json"))
    nominate(node_id, graph, agent_initiated=agent)
    graph.save()
    click.echo(f"Nominated {node_id}: status -> candidate")
```

**Error pattern** (propose.py lines 59-68):
```python
raise click.ClickException(
    f"Refusing to propose: {n['id']} already exists under "
    f"--parent {parent} with the same description ..."
)
```

---

### `src/automil/cli/promote.py` (top-level CLI command)

**Analog:** `src/automil/cli/lifecycle/promote_variant.py` (structure), `src/automil/cli/propose.py` (top-level registration)

**Top-level registration** (promote_variant.py line 16-17):
```python
@main.command("promote-variant")
@click.argument("node_id")
def promote_variant(node_id: str):
```
Apply as bare `"promote"` (verified unclaimed in codebase per RESEARCH.md):
```python
@main.command("promote")
@click.argument("candidate_id")
@click.option("--calibrate", is_flag=True, default=False,
              help="Dry-run: evaluate but do not change status (D-151 calibration mode).")
def promote_cmd(candidate_id: str, calibrate: bool) -> None:
    """Run Stage B gate against held-out cells; promote to 'registered' if pass."""
```

**git_root lookup pattern** (promote_variant.py lines 10-12):
```python
from automil.cli._helpers import _find_automil_dir, _find_git_root
adir = _find_automil_dir()
git_root = _find_git_root()
```

---

### `src/automil/templates/config.yaml.j2` (config template extension)

**Analog:** itself — add `gate:` section after the existing `cap:` section (lines 116-128)

**Existing section style** (config.yaml.j2 lines 116-128):
```yaml
# --- Cap configuration — consumer-supplied, NOT framework-mandated. ---
# autoMIL is generic; values below are example defaults Leo's autoMIL-paper
# experiment campaign uses across all its datasets (CCRCC, CLWD, future
# additions). A different consumer (sklearn-iris demo with K=1, an external
# lab with different time budgets, a follow-up paper) would pick different
# numbers. The framework only requires that values are present and validated
# (see D-134); the *values* are entirely the consumer's choice.
cap:
  budget_seconds:        21600
  safety_buffer_seconds: 1800
```
Add after cap section (same comment discipline — frame as consumer-supplied):
```yaml
# --- Gate configuration — consumer-supplied (NOT framework constants). ---
# K, p_threshold, bootstrap_reps are Leo's autoMIL-paper defaults (D-137).
# A different consumer sets their own values per their statistical requirements.
# pre-registration is always enforced (D-138) regardless of these values.
gate:
  auto_nominate:    false        # D-142 default: operator-driven nomination
  K:                2            # O-01 default: max(2, N_cells//3) generous start
  p_threshold:      0.05         # O-02 default: conventional alpha; Bonferroni divides
  bootstrap_reps:   1000         # GTE-04 locked: 1000 per F1 paper §4.4
```

---

### `src/automil/graph.py` (additive modifications)

**Analog:** itself — all modifications are additive (new fields on existing free-form node dict, new helper methods)

**Node dict extension pattern** (graph.py lines 122-145 — free-form dict, additive keys):
```python
node = {
    "id": nid,
    "parent_id": parent_id,
    "type": "executed",
    "status": status,
    # ... existing fields ...
    "created_at": datetime.now().isoformat(),
}
```
New additive fields for gate-eval nodes (D-140):
```python
# Two new fields added by gate/evaluate.py at submit time:
node["edge_type"] = "gate_eval"   # vs default "search" (node.get("edge_type", "search"))
node["metadata"] = {              # gate-eval metadata dict
    "held_out": True,
    "gate_eval": True,
    "gate_parent_node": candidate_id,
    "cell_id": cell_id,
}
```

**graph.save() atomic write pattern** (graph.py lines 787-801):
```python
def save(self):
    self.path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(self._data, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, str(self.path))
        os.utime(str(self.path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

**New helper method signature** (D-144, mirrors existing counting helpers):
```python
def nominations_in_window(self, days: int = 30) -> list[dict]:
    """Return nodes whose history contains a 'nominated' event in the last `days` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for node in self.nodes.values():
        for event in node.get("history", []):
            if event.get("event") == "nominated":
                ts = datetime.fromisoformat(event["timestamp"])
                if ts > cutoff:
                    result.append(node)
                    break
    return result

def promotion_rate(self, days: int = 30) -> float:
    """promoted / nominated over rolling window (D-144). Returns 0.0 if no nominations."""
    nominated = self.nominations_in_window(days)
    if not nominated:
        return 0.0
    promoted = [n for n in nominated if n.get("status") == "registered"]
    return len(promoted) / len(nominated)
```

---

### `src/automil/cli/propose.py` (rank command — extend to filter held-out)

**Analog:** itself (lines 13-38)

**Filter extension** (additive, lines 13-25):
```python
@main.command()
@click.option("--n", default=6, help="Number of proposals to return")
@click.option("--max-per-branch", default=2, help="Max proposals per branch")
@click.option("--include-held-out", is_flag=True, default=False,
              help="Include held-out gate-eval nodes (D-139; logs WARNING).")  # NEW
def rank(n: int, max_per_branch: int, include_held_out: bool):
    ...
    # Filter held-out nodes BEFORE rank_proposals() (D-139)
    if not include_held_out:
        graph._data["nodes"] = {
            k: v for k, v in graph.nodes.items()
            if not v.get("metadata", {}).get("held_out", False)
        }
    else:
        import logging
        logging.getLogger(__name__).warning(
            "--include-held-out: held-out cell composites now visible; "
            "this must NOT be used during the agent search loop (D-139)."
        )
```

---

### `src/automil/trajectory/redactor.py` (extension for held-out node-id redaction)

**Analog:** itself (lines 1-105)

**Pattern list extension** (lines 16-30 — add a new entry to `_PATTERNS` OR extend `redact()` with dynamic lookup):

The held-out redaction is dynamic (IDs are graph-content-dependent, not static regex literals) — this is a NEW mechanism. The approach from RESEARCH.md Pitfall 2:

```python
# Extension to existing redactor.py — add after the static _PATTERNS list

import functools, time as _time

@functools.lru_cache(maxsize=1)
def _held_out_ids_cached(graph_mtime: float) -> frozenset[str]:
    """Load held-out node IDs from graph.json with modification-time cache (TTL via mtime)."""
    from automil.cli._helpers import _find_automil_dir
    try:
        adir = _find_automil_dir()
        import json
        data = json.loads((adir / "graph.json").read_text())
        return frozenset(
            nid for nid, n in data.get("nodes", {}).items()
            if n.get("metadata", {}).get("held_out", False)
        )
    except Exception:
        return frozenset()

def _held_out_ids() -> frozenset[str]:
    """Return current held-out node IDs, cached by graph.json mtime."""
    from automil.cli._helpers import _find_automil_dir
    try:
        path = _find_automil_dir() / "graph.json"
        mtime = path.stat().st_mtime
    except Exception:
        mtime = 0.0
    return _held_out_ids_cached(mtime)
```

Then extend the existing `redact()` function:
```python
# In redact(s: str) -> str — add after the static pattern loop:
_NODE_ID_RE = re.compile(r"\bnode_\d{4,}\b")
def redact(s: str) -> str:
    for pattern, replacement in _PATTERNS:
        s = pattern.sub(replacement, s)
    # Dynamic: redact held-out node IDs (D-139)
    held_out = _held_out_ids()
    if held_out:
        s = _NODE_ID_RE.sub(
            lambda m: "<HELD_OUT>" if m.group(0) in held_out else m.group(0), s
        )
    return s
```

The existing `redact_event(d: dict) -> dict` and `_walk` (lines 42-65) call `redact(s)` for all string leaves — no change needed there; the extension is purely in `redact()`.

---

### `src/automil/viz/server.py` (SSE endpoint extension for promotion_rate)

**Analog:** itself (lines 159-218)

**Existing SSE handler + route registration** (lines 159-218):
```python
async def sse_handler(request):
    response = web.StreamResponse(status=200, headers={
        "Content-Type": "text/event-stream", "Cache-Control": "no-cache", ...
    })
    ...

def create_app() -> web.Application:
    app = web.Application(middlewares=[_no_cache_static])
    app.router.add_get("/", index_handler)
    app.router.add_get("/events", sse_handler)     # existing
    app.router.add_static("/static", STATIC_DIR)
    ...
    return app
```

**New endpoint pattern** (add alongside `/events` in `create_app`):
```python
async def promotion_rate_handler(request):
    """Serve current promotion_rate as JSON (D-144 / GTE-06)."""
    response_data = {"promotion_rate": 0.0, "nominated": 0, "promoted": 0}
    try:
        data = json.loads(GRAPH_FILE.read_text())
        from automil.graph import ExperimentGraph
        g = ExperimentGraph.__new__(ExperimentGraph)
        g._data = data
        g.path = GRAPH_FILE
        rate = g.promotion_rate(days=30)
        nominated = len(g.nominations_in_window(days=30))
        promoted = int(rate * nominated) if nominated else 0
        response_data = {"promotion_rate": rate, "nominated": nominated, "promoted": promoted}
    except Exception:
        pass
    return web.json_response(response_data)

# In create_app():
app.router.add_get("/api/promotion-rate", promotion_rate_handler)   # NEW
```

---

### `src/automil/backends/base.py` — JobSpec extension (D-140 Option A)

**Analog:** itself (lines 58-94)

**Current JobSpec frozen dataclass** (lines 58-94 — NO `metadata` field exists today):
```python
@dataclass(frozen=True)
class JobSpec:
    node_id: str
    base_commit: str
    overlay_files: tuple[str, ...]
    overlay_dir: Path
    command: tuple[str, ...]
    env: tuple[tuple[str, str], ...]
    working_subdir: str
    gpu_estimate_gb: float
    walltime_seconds: int
    # NOTE: NO metadata field — confirmed by reading lines 58-94
```

**Extension pattern** (mirrors `env: tuple[tuple[str, str], ...] = ()` shape at line 83):
```python
# Add as the LAST field, kw-only with default to preserve backward compat (RESEARCH.md A2)
metadata: tuple[tuple[str, str], ...] = ()
"""Gate-eval and other arbitrary metadata passthrough. tuple-of-tuples so frozen=True
holds. Convert to dict via dict(spec.metadata). Default () = no metadata."""
```

`LocalBackend.submit()` then merges at line 142 (after existing `"backend"` stamp):
```python
# After existing: queue_spec.setdefault("metadata", {})["backend"] = "local"
for k, v in spec.metadata:
    queue_spec.setdefault("metadata", {})[k] = v
```

---

### `src/automil/cli/__init__.py` (register new modules)

**Analog:** itself (lines 20-35)

**Registration pattern** (lines 20-35 — alphabetic order, noqa comment style):
```python
from automil.cli import cancel   # noqa: E402,F401
from automil.cli import cell     # noqa: E402,F401  (CAP-06 / D-125)
...
```
Add (insert alphabetically):
```python
from automil.cli import gate     # noqa: E402,F401  (GTE-01..06 / D-145)
from automil.cli import nominate # noqa: E402,F401  (GTE-05 / D-142)
from automil.cli import promote  # noqa: E402,F401  (GTE / D-145)
```
Note: `gate` sits between `control` and `init`; `nominate` after `lifecycle`; `promote` after `propose`.

---

### `tests/gate/` package (test suite)

**Primary analog:** `tests/test_graph.py` + `tests/test_integration.py` (for fixtures) + existing `benchmarks/tests/conftest.py` (for conftest structure)

**conftest.py pattern** (infer from tests/test_graph.py fixture style — uses `tmp_path`):
```python
# tests/gate/conftest.py
import pytest
from pathlib import Path
from automil.graph import ExperimentGraph
from automil.gate.manifest import GateManifest

@pytest.fixture
def tmp_graph(tmp_path) -> ExperimentGraph:
    """Synthetic 3-node graph: 1 keep node (candidate), 2 proposed."""
    g = ExperimentGraph(path=str(tmp_path / "graph.json"))
    # ... add nodes ...
    g.save()
    return g

@pytest.fixture
def tmp_manifest(tmp_path) -> tuple[GateManifest, Path]:
    manifests_dir = tmp_path / "gate"
    manifest = GateManifest(
        parent_id="node_0001",
        created_at="2026-05-05T00:00:00Z",
        git_committed_at_sha="PENDING",
        held_out_cells=(("abc12345", "ccrcc", "uni_v2", "high_grade"),
                        ("def67890", "clwd", "ctranspath", "subtype")),
        K=2, p_threshold=0.05, bootstrap_reps=100,
        win_definition="delta_composite > 0 AND p < p_threshold",
        schema_version="gate-v1",
    )
    return manifest, manifests_dir

@pytest.fixture
def mock_backend():
    """MockSLURMBackend from tests/backends/ — reused per RESEARCH.md Pattern 3."""
    from automil.backends.mock_slurm import MockSLURMBackend
    return MockSLURMBackend()
```

**test_stats.py discipline** (no fixtures needed — pure numpy arrays):
```python
import numpy as np
import pytest
from automil.gate.stats import paired_wilcoxon_with_bootstrap, bonferroni_correct

def test_bonferroni_direction():
    # Pitfall 4: divide alpha, NOT multiply p-values
    assert bonferroni_correct(0.05, 5) == pytest.approx(0.01)
    assert bonferroni_correct(0.05, 2) == pytest.approx(0.025)

def test_paired_wilcoxon_all_positive():
    deltas = np.array([0.02, 0.015, 0.01, 0.025, 0.018])
    passed, p, ci, wins = paired_wilcoxon_with_bootstrap(
        deltas, p_threshold=0.05, bootstrap_reps=100, rng_seed=42
    )
    assert passed
    assert p < 0.05
    assert ci[0] > 0
    assert wins == 5

def test_paired_wilcoxon_all_zero_returns_false():
    deltas = np.zeros(4)
    passed, p, ci, wins = paired_wilcoxon_with_bootstrap(deltas, 0.05)
    assert not passed
```

---

## Shared Patterns

### Atomic file write (tempfile + os.replace)
**Source:** `src/automil/cells/state.py:94-116`
**Apply to:** `gate/manifest.py:write_manifest`, `gate/manifest.py:write_manifest_committed`

```python
# Copy verbatim — proven pattern for same-filesystem atomic rename
tmp_fd, tmp_path = tempfile.mkstemp(dir=str(target_dir), suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w") as fh:
        fh.write(payload)
    os.replace(tmp_path, str(final_path))
except Exception:
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    raise
```
Critical: `dir=str(target_dir)` keeps temp on the same filesystem. Cross-FS rename is NOT atomic.

### git subprocess pattern (list argv, check=True)
**Source:** `src/automil/cli/lifecycle/promote_variant.py:104-126`
**Apply to:** `gate/manifest.py:write_manifest_committed`

```python
# Always list form — never shell=True (injection-safe)
result = subprocess.run(
    ["git", "add", str(path)],
    cwd=git_root, check=True, capture_output=True, text=True,
)
# check=True raises subprocess.CalledProcessError with stderr in exc.stderr
```
Rollback on failure: `path.unlink()` — NEVER `git checkout -- <path>` (Leo memory: feedback_never_blind_checkout.md).

### _find_automil_dir + _find_git_root helpers
**Source:** `src/automil/cli/_helpers.py:15-38`
**Apply to:** All `cli/gate.py` subcommands, `cli/nominate.py`, `cli/promote.py`

```python
from automil.cli._helpers import _find_automil_dir, _find_git_root
adir = _find_automil_dir()      # walks up from cwd looking for automil/config.yaml
git_root = _find_git_root()     # walks up from cwd looking for .git/
```

### click.ClickException error pattern
**Source:** `src/automil/cli/propose.py:59-68`, `src/automil/cli/lifecycle/promote_variant.py:57-64`
**Apply to:** All CLI commands in `cli/gate.py`, `cli/nominate.py`, `cli/promote.py`

```python
raise click.ClickException(
    f"Clear description of what went wrong: {detail!r}. "
    f"Suggest remediation action here."
)
```

### Lazy imports inside Click command bodies
**Source:** `src/automil/cli/cell.py:24-26`, `src/automil/cli/propose.py:48-49`
**Apply to:** All `cli/gate.py` subcommand bodies, `cli/nominate.py`, `cli/promote.py`

```python
@gate_group.command("register-manifest")
def register_manifest_cmd(...):
    from automil.gate import write_manifest_committed  # lazy — inside body
    from automil.graph import ExperimentGraph          # lazy — inside body
```
Prevents circular import at group definition time.

### Pure-function module discipline
**Source:** `src/automil/cells/cap.py:1-41`
**Apply to:** `gate/stats.py` (entire module)

No I/O. No `time.time()`. Caller injects all inputs. Side-effect-free → unit-testable without filesystem fixtures. Return typed tuples, not dicts (preserves IDE autocomplete).

### Frozen dataclass serialization
**Source:** `src/automil/cells/state.py:31-69` + `src/automil/backends/base.py:36-53`
**Apply to:** `gate/manifest.py:GateManifest`

```python
# Serialise: json.dumps(dataclasses.asdict(manifest), indent=2)
# Deserialise: reconstruct with GateManifest(**data) after re-typing nested fields
# Frozen: use dataclasses.replace(manifest, git_committed_at_sha=sha) for single-field updates
```

### Graph save discipline
**Source:** `src/automil/graph.py:787-801`
**Apply to:** `gate/nominate.py`, `gate/promote.py` — mutate node dict in-memory, then caller calls `graph.save()`

Mutation functions do NOT call `graph.save()`. Caller controls when to persist. Same discipline as `cells/registry.py:write_cell()` being called after all mutations.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/automil/gate/stats.py` | utility | transform | No scipy usage exists anywhere in `src/automil/`; pure scipy stats is entirely new to the framework. Pattern discipline (pure-function) copies from `cells/cap.py`, but the scipy API surface is novel. |
| `tests/gate/test_stats.py` | test | — | No existing scipy unit tests in `tests/`; test structure follows standard pytest patterns but the assertion targets (p-values, CI bounds) require domain knowledge from GTE-04. |

---

## Metadata

**Analog search scope:** `src/automil/cells/`, `src/automil/cli/`, `src/automil/backends/`, `src/automil/trajectory/`, `src/automil/viz/`, `src/automil/graph.py`
**Files read:** 14 source files + CONTEXT.md + RESEARCH.md + STRUCTURE.md
**Pattern extraction date:** 2026-05-05

**Critical planner notes:**
1. `JobSpec.metadata` field addition (backends/base.py) must use `field(default_factory=tuple, kw_only=True)` syntax to avoid breaking positional-arg callers (RESEARCH.md Assumption A2). Verify no tests construct `JobSpec` with positional args before adding.
2. scipy MUST move from `[project.optional-dependencies.ml]` to `[project.dependencies]` in root `pyproject.toml` — run `uv sync` after the change.
3. The atomic-write-plus-git-commit pattern in `gate/manifest.py` is genuinely new — no existing file in the repo does both. The RESEARCH.md Pattern 1 skeleton (lines 168-219) is the authoritative reference; this PATTERNS.md excerpts the same pattern for completeness.
4. `tests/gate/test_pitfall6_held_out_isolation.py` is load-bearing (D-149) — the planner should assign this its own plan item, not bundle it with test_held_out_isolation.py.
5. `gate/stats.py` must include `diagnose_gate_health(promotion_rate_30d, threshold_low=0.05, threshold_high=0.5) -> str` per RESEARCH.md Pitfall 6 (code-level addition) — planner should include this in the stats plan, not treat stats.py as stats-only.
