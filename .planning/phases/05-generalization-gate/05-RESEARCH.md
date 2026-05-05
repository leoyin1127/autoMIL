# Phase 5: Generalization gate - Research

**Researched:** 2026-05-05
**Domain:** Statistical generalization gate for autonomous experiment search (paired Wilcoxon + bootstrap CI + Bonferroni; pre-registered held-out cell manifests; gate-eval via Backend ABC)
**Confidence:** HIGH (codebase verified line-by-line; scipy probed at runtime; CLI surface enumerated; ABC + cells contract read; only O-01..O-05 carry residual user-decision uncertainty)

## Summary

Phase 5 lays a `gate/` package next to the existing `cells/` package to enforce generalization at promotion time. A candidate variant must beat its parent on >=K **pre-registered** held-out cells via paired Wilcoxon signed-rank test + 1000-sample bootstrap CI on the median delta + Bonferroni-corrected p_threshold. Held-out evaluations spawn through `Backend.submit()` so they inherit Phase 4's per-cell cap mechanism without forking a parallel scheduler path. Held-out node IDs are tagged `metadata.held_out=true` and filtered out of the agent's `automil rank`/trajectory views, defending Pitfall 6c (held-out leak into agent loop).

Engineering correctness is verified end-to-end: scipy 1.17.1 is already installed in the workspace via transitive deps (autobench, scikit-image, scikit-learn, trident — `[CITED: pip show scipy]`); the Backend ABC's `JobSpec` has no fixed `metadata` attribute (it accepts arbitrary metadata via the queue spec dict that LocalBackend builds — needs an extension), the graph node model has free-form `status` strings (so `candidate` is additive without enum changes), and edges are implicit via `parent_id` (so D-140's `gate_eval` "edge type" lands as a NEW field on the child node, not a new collection). The atomic-write-plus-git-commit pattern in D-138 is novel (`promote_variant.py` stages but does NOT commit) and needs a dedicated helper.

**Primary recommendation:** Build the `gate/` package as five pure modules (manifest, nominate, evaluate, promote, stats) mirroring `cells/`'s split. Reuse `tempfile.mkstemp` + `os.replace` for atomic manifest writes. Add scipy to `automil`'s core dependencies (currently transitive only). Extend `JobSpec` with a `metadata` tuple field OR add a queue-spec-level `metadata` passthrough on LocalBackend (the latter is less invasive and matches how cell_id is already stamped at line 348 of `cli/submit.py`). Add `edge_type: str = "search"` and `held_out: bool` keys directly on the graph node dict — no schema-version bump needed because graph.json is already free-form.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Manifest persistence + git commit | `gate/manifest.py` | `gate/cli` (operator-driven `register-manifest`) | Atomic-write pattern lives where state lives; CLI orchestrates user interaction |
| Held-out cell isolation from agent view | `cli/propose.py rank()` filter + `trajectory/redactor.py` extension | `gate/evaluate.py` (tags nodes at submit time) | Filter at the read site; tag at the write site — symmetric to how `metadata.cell_id` works |
| Statistical decision (Wilcoxon + bootstrap + Bonferroni) | `gate/stats.py` (pure functions) | `gate/promote.py` (composes them) | Pure math is testable without I/O, fixtures, or scipy mocks |
| Spawning held-out evaluations | `gate/evaluate.py` -> `Backend.submit()` | `cells/registry.py` (auto-creates cells) | Reuses Phase 2 ABC + Phase 4 cell machinery; zero parallel pathway |
| Status taxonomy mutation (`keep`->`candidate`->`registered`) | `gate/nominate.py` + `gate/promote.py` mutate `graph.nodes[id]["status"]` directly | `graph.py` (no helper change needed — status is free-form) | Additive to existing `keep`/`discard`/`crash` semantics |
| Promotion-rate metric | `graph.py` helper `nominations_in_window(days)` + `viz/server.py` SSE endpoint + `cli/status.py` | `gate/promote.py` (writes status history with timestamps) | Metric reads ground truth from graph; no separate counter to drift |
| Pitfall 6 anti-acceptance | `tests/gate/test_pitfall6_held_out_isolation.py` | All gate modules (each must support synthetic-graph fixture) | One load-bearing test analogous to Phase 4's `test_cap_fires_with_partial_fold_recovery.py` |

## Standard Stack

### Core (already in workspace, used as-is)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `scipy.stats.wilcoxon` | scipy 1.17.1 | Paired Wilcoxon signed-rank test on per-cell deltas | F1 paper convention §4.4; locked in GTE-04. **`[VERIFIED: uv run python -c]`** scipy 1.17.1 importable; signature `wilcoxon(x, y=None, zero_method='wilcox', correction=False, alternative='two-sided', method='auto', *, axis=0, nan_policy='propagate', keepdims=False)` |
| `scipy.stats.bootstrap` | scipy 1.17.1 | 1000-sample bootstrap CI on median delta | scipy provides BCa (bias-corrected accelerated) by default; standard approach. **`[VERIFIED]`** signature `bootstrap(data, statistic, *, n_resamples=9999, ..., confidence_level=0.95, alternative='two-sided', method='BCa', rng=None, ...)` |
| `numpy` | already a scipy dep | Array machinery for delta vectors | Required by scipy |
| `click` | 8.1+ | CLI surface (mirrors existing `automil cell` pattern) | Already in core deps |
| `tempfile.mkstemp` + `os.replace` | stdlib | Atomic manifest write | Same pattern as `cells/state.py:write_cell` lines 106-116 — proven correct under concurrent access |
| `subprocess.run(["git", ...])` | stdlib | Stage + commit manifest | Same pattern as `cli/lifecycle/promote_variant.py:107-126` (which stages but doesn't commit) and `cli/lifecycle/revert_baseline.py:140` |

### Supporting (used inline, no new deps)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` (frozen) | stdlib | `GateManifest` immutable shape | Mirror `Cell` dataclass at `cells/state.py:32-69` |
| `enum` | stdlib | NOT needed — graph status is free-form string already | `candidate` is just another string value; see `graph.py:127` |
| `json` | stdlib | Manifest + graph.json IO | Existing pattern |
| `pathlib.Path` | stdlib | Path manipulation | Existing pattern |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual `alpha / K` Bonferroni | `statsmodels.stats.multitest.multipletests` | statsmodels adds ~80 MB transitive deps for a 1-line divide. **`[VERIFIED]`** scipy 1.17.1 has `false_discovery_control` (FDR/Benjamini-Hochberg) but no Bonferroni helper. Manual divide is the standard idiom. |
| `scipy.stats.bootstrap` with `method='BCa'` | `np.percentile` on resampled medians | BCa is statistically superior (corrects bias + skewness); scipy already has it; no reason to hand-roll. |
| New JSON schema for `gate_eval` edges | Add `edge_type: str` + `gate_parent_node: str` keys to existing node dict | Graph node is already a free-form dict (see `graph.py:122-145`); adding two keys requires zero schema migration. **Locks D-140 implementation: edge_type is a node field, not a separate `edges` collection.** |
| `pytest-mock` for Backend.submit mocking | Pass an instance of `MockSLURMBackend` | MockSLURM is the canonical fixture from Phase 2 (`tests/backends/test_contract.py`); reusing keeps the contract test surface coherent. |

**Installation:**
```bash
# Add scipy to core deps in pyproject.toml — currently only in [project.optional-dependencies.ml]
# Manually edit pyproject.toml:
[project]
dependencies = [
    "aiohttp>=3.9",
    "watchdog>=4.0",
    "jinja2>=3.1",
    "click>=8.1",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "torch>=2.10.0",
    "scipy>=1.11",  # NEW — lift from optional [ml]; required by gate/stats.py
]
```

**Version verification:**
- scipy 1.17.1 verified installed via `pip show scipy` (Required-by: autobench, scikit-image, scikit-learn, trident). **`[VERIFIED: pip show scipy 2026-05-05]`**
- scipy 1.11+ has both `wilcoxon` (since 1.4) and `bootstrap` (since 1.7) — minimum bound `>=1.11` matches the existing `[ml]` pin and is conservative.

## Architecture Patterns

### System Architecture Diagram

```
                                       OPERATOR
                                          |
                  +-----------------------+-----------------------+
                  |                       |                       |
                  v                       v                       v
     [automil gate register-manifest]  [automil nominate]  [automil promote]
                  |                       |                       |
                  v                       v                       v
   gate/manifest.py:write_manifest   gate/nominate.py        gate/promote.py
   - atomic JSON write                - status: keep         - call evaluate_candidate()
   - git stage + commit               -> candidate           - run gate/stats.py
   - immutable per parent_id          - record in history    - status: candidate
                  |                                            -> registered (pass)
                  v                                            -> keep (fail)
   automil/gate/<parent_id>.gate_manifest.json                 |
   (committed to git)                                          v
                                                  gate/evaluate.py:evaluate_candidate
                                                  - for each held_out_cell in manifest:
                                                      Backend.submit(spec) with
                                                      metadata.gate_eval=true
                                                      metadata.held_out=true
                                                      metadata.cell_id=<...>
                                                      metadata.gate_parent_node=<candidate_id>
                                                      edge_type="gate_eval"
                                                  - poll until terminal
                                                  - return per-cell composite matrix
                                                          |
                                                          v
                                          gate/stats.py:paired_wilcoxon_with_bootstrap
                                          - deltas = candidate_i - parent_i (paired by cell_id)
                                          - p = scipy.stats.wilcoxon(deltas).pvalue
                                          - ci = scipy.stats.bootstrap((deltas,), np.median,
                                                  n_resamples=1000).confidence_interval
                                          - p_corrected = p_threshold / K  (Bonferroni)
                                          - return (passed, p, ci, per_cell_wins)


   AGENT VIEW (search loop, MUST be blind to held-out):
   automil rank
      |
      v
   cli/propose.py:rank() filters out nodes where metadata.held_out=true
   trajectory/redactor.py replaces held-out node_ids with <HELD_OUT> placeholder
   automil status omits gate_eval edges from in-progress display
```

### Recommended Project Structure

```
src/automil/gate/                         # NEW package — mirrors cells/
├── __init__.py                           # public surface (read_manifest, write_manifest, nominate, promote, evaluate_candidate, paired_wilcoxon_with_bootstrap, bonferroni_correct, GateManifest)
├── manifest.py                           # GateManifest frozen dataclass + atomic JSON IO + git stage/commit helper + retire-manifest
├── nominate.py                           # nominate(node_id) — keep -> candidate; appends to node["history"]
├── evaluate.py                           # evaluate_candidate(candidate_id, manifest, backend) -> (per_cell_results, skipped_cells)
├── promote.py                            # promote(candidate_id, backend) — composes evaluate + stats + status mutation
└── stats.py                              # paired_wilcoxon_with_bootstrap, bonferroni_correct (pure functions)

src/automil/cli/
├── gate.py                               # NEW — @main.group("gate") with register-manifest, retire-manifest, status, stats subcommands
├── nominate.py                           # NEW — top-level @main.command("nominate")
└── promote.py                            # NEW — top-level @main.command("promote")  (NOT to be confused with existing "promote-variant")

src/automil/graph.py                      # MODIFY — add nominations_in_window(days), promotion_rate(); add filter helper for held_out=true; allow status="candidate"/"registered"
src/automil/cli/propose.py                # MODIFY — rank() filters metadata.held_out=true unless --include-held-out
src/automil/trajectory/redactor.py        # EXTEND — add held-out-id placeholder pattern (config-driven via env or graph lookup)
src/automil/viz/server.py                 # EXTEND — /api/promotion-rate SSE endpoint
src/automil/templates/config.yaml.j2      # EXTEND — gate: section
src/automil/cli/__init__.py               # REGISTER — import gate, nominate, promote modules

tests/gate/                               # NEW — mirrors tests/cells/
├── __init__.py
├── conftest.py                           # synthetic graph + manifest + cells fixtures using tmp_path
├── test_manifest.py                      # atomic write, git commit, immutability, retire flow
├── test_nominate.py                      # status transition, idempotency, audit log
├── test_evaluate.py                      # MockSLURM backend; assert metadata.gate_eval=true; per-cell skipping on cap exhaustion
├── test_promote.py                       # full pass/fail flow; status reverts on fail
├── test_stats.py                         # pure scipy paired Wilcoxon + bootstrap correctness; Bonferroni divisor; edge cases (K=1, all ties, partial folds)
├── test_held_out_isolation.py            # rank filter; trajectory redaction
├── test_two_stage_gate.py                # Stage A (Pareto on search) + Stage B (held-out paired test)
└── test_pitfall6_held_out_isolation.py   # LOAD-BEARING anti-acceptance gate (D-149)

tests/test_backend_isolation_lint.py      # MODIFY — assert zero os.kill/getpid/Popen/.pid in src/automil/gate/
```

### Pattern 1: Atomic write + git commit (NEW — D-138)

The cells package atomically writes to disk but never commits. Phase 5 must do both, with rollback on git failure. No existing automil pattern combines them. Skeleton:

```python
# Source: gate/manifest.py — composing cells/state.py:write_cell + cli/lifecycle/promote_variant.py:107-126
import os
import subprocess
import tempfile
from pathlib import Path

def write_manifest_committed(manifest: GateManifest, manifests_dir: Path, git_root: Path) -> str:
    """Atomically write manifest AND commit to git. Returns commit SHA. Rollback on any failure."""
    manifests_dir.mkdir(parents=True, exist_ok=True)
    path = manifests_dir / f"{manifest.parent_id}.gate_manifest.json"

    # Refuse to overwrite existing manifest (D-138 #5)
    if path.exists():
        raise FileExistsError(
            f"Manifest already exists: {path}. Run `automil gate retire-manifest "
            f"{manifest.parent_id} --reason '...'` first."
        )

    # 1. Atomic write via tempfile + os.replace (mirrors cells/state.py:106-116)
    payload = json.dumps(dataclasses.asdict(manifest), indent=2)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(manifests_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(path))
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise

    # 2. git add + git commit, with rollback on failure
    try:
        subprocess.run(["git", "add", str(path)], cwd=git_root, check=True, capture_output=True, text=True)
        msg = (
            f"gate: register manifest for {manifest.parent_id} "
            f"(held_out: {len(manifest.held_out_cells)} cells, K={manifest.K}, "
            f"p<{manifest.p_threshold})"
        )
        subprocess.run(["git", "commit", "-m", msg], cwd=git_root, check=True, capture_output=True, text=True)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_root, check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError as e:
        # Rollback: remove the file from working tree (NOT git checkout — Leo memory: "never blind-checkout")
        try: path.unlink()
        except OSError: pass
        raise RuntimeError(f"git commit failed: {e.stderr}; manifest file removed") from e

    return sha
```

**When to use:** any operation that must atomically pair a state change with a git timestamp (Phase 5 manifest registration; future: variant promotion, gate retirement).

### Pattern 2: Pure-function statistical core (mirrors cells/cap.py)

```python
# Source: gate/stats.py — mirrors cells/cap.py:next_status pure-function discipline
import numpy as np
from scipy.stats import wilcoxon, bootstrap

def paired_wilcoxon_with_bootstrap(
    deltas: np.ndarray,
    p_threshold: float,
    bootstrap_reps: int = 1000,
    rng_seed: int | None = None,
) -> tuple[bool, float, tuple[float, float], int]:
    """Pure paired Wilcoxon + bootstrap-CI test on per-cell deltas.

    Args:
        deltas: 1-D array of (candidate_composite_i - parent_composite_i), one per held-out cell.
        p_threshold: Bonferroni-corrected alpha (caller pre-divides by K).
        bootstrap_reps: 1000 per GTE-04 default.
        rng_seed: deterministic if not None (test-friendly).

    Returns:
        (passes_test, p_value, (ci_low, ci_high), individual_wins)
    """
    if len(deltas) < 1:
        return (False, 1.0, (0.0, 0.0), 0)
    if np.all(deltas == 0):
        # scipy.stats.wilcoxon would raise; treat as no signal
        return (False, 1.0, (0.0, 0.0), 0)

    # Wilcoxon signed-rank test (one-sample form: tests whether deltas come from
    # a distribution symmetric around zero). zero_method='wilcox' is the default
    # and standard for small-K paired tests with possible ties.
    wres = wilcoxon(deltas, zero_method="wilcox", alternative="greater")
    # alternative="greater" because we test "candidate > parent" (one-sided gate)

    # Bootstrap CI on the median delta (BCa default — bias-corrected accelerated)
    rng = np.random.default_rng(rng_seed)
    bres = bootstrap(
        (deltas,),
        np.median,
        n_resamples=bootstrap_reps,
        confidence_level=0.95,
        method="BCa",
        rng=rng,
    )
    ci_low, ci_high = float(bres.confidence_interval.low), float(bres.confidence_interval.high)

    individual_wins = int(np.sum(deltas > 0))

    # D-141: passes iff p<=threshold AND ci_low > 0 AND individual_wins >= K
    # (K is enforced by caller; this function returns the trio for caller to combine)
    passes = (wres.pvalue <= p_threshold) and (ci_low > 0)

    return (passes, float(wres.pvalue), (ci_low, ci_high), individual_wins)


def bonferroni_correct(p_threshold: float, K: int) -> float:
    """Bonferroni: divide alpha by number of comparisons. Standard idiom; no scipy helper.

    [VERIFIED] scipy 1.17.1 has `false_discovery_control` (Benjamini-Hochberg)
    but no Bonferroni helper. statsmodels has `multipletests` but is a heavy
    dep. Manual divide is the textbook approach (Bonferroni 1936).
    """
    if K < 1:
        raise ValueError(f"K must be >= 1; got {K}")
    return p_threshold / K
```

**When to use:** every statistical decision in the gate. Pure, testable, no I/O.

### Pattern 3: Backend.submit metadata passthrough (extends Phase 2/4 pattern)

The Backend ABC's `JobSpec` is `frozen=True` with no `metadata` attribute (`backends/base.py:58-93`). However `LocalBackend.submit()` builds a queue spec dict at runtime (lines 121-142 of `backends/local.py`) that DOES carry a `metadata` dict — and `cli/submit.py:340-348` already stamps `metadata.backend`, `metadata.runtime`, `metadata.cell_id` into that dict. **The pattern Phase 5 inherits: stamp gate-related metadata at the same site.**

Two implementation choices:

**Option A (preferred — minimal ABC change):** Extend `JobSpec` with a `metadata: tuple[tuple[str, str], ...] = ()` field (mirrors how `env` is passed at base.py:83). Then `LocalBackend.submit()` merges `dict(spec.metadata)` into `queue_spec["metadata"]`. MockSLURMBackend passes through the same way. This keeps the ABC explicit about what crosses the boundary.

**Option B (zero ABC change):** Don't touch `JobSpec`. Instead, `gate/evaluate.py` builds the queue spec dict directly and writes it to `queue/<id>.json` itself (bypassing `Backend.submit()`). **REJECTED** — violates GTE-03 ("same path as agent submits, NOT a parallel mechanism").

**Recommendation:** Option A. The ABC change is one frozen-dataclass field; LocalBackend and MockSLURMBackend each get a 1-line update; the contract test (`tests/backends/test_contract.py`) gets a metadata-roundtrip assertion. **Locks D-140 across both backends.**

### Anti-Patterns to Avoid

- **Custom statistical implementation:** Don't reimplement Wilcoxon. scipy.stats.wilcoxon is the F1 paper's reference, has 30 years of correctness validation, and handles tie-breaking + zero_method correctly.
- **Per-candidate manifests:** D-137 explicitly forbids this. ONE manifest per parent. Per-candidate manifests defeat pre-registration (the manifest must exist BEFORE search starts, when no candidates exist yet).
- **Held-out cell results in trajectory:** Pitfall 6c. The trajectory is the agent's audit trail; held-out results MUST live in a separate gate log so the trajectory contains zero references that could leak via prompt-context retrieval.
- **Gate runs serially per candidate:** Phase 4's cap is per-cell wall-clock; if gate-eval is serial, latency explodes. Submit all K held-out evaluations in parallel via `Backend.submit()`, then poll concurrently.
- **K decided after seeing results:** Calibration pilot exists for this reason (D-151). K must be locked in the manifest before the search loop sees its first candidate.
- **`git checkout -- <file>` on manifest rollback:** Leo's memory `feedback_never_blind_checkout.md` — destroys uncommitted work. Use `path.unlink()` to remove the working-tree manifest file; never `git checkout` for cleanup.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Paired non-parametric significance test | Custom rank statistic | `scipy.stats.wilcoxon(deltas, alternative='greater', zero_method='wilcox')` | scipy handles ties, zero-differences (zero_method), exact vs approximate p-value selection (`method='auto'`) — all of which are well-known footguns in custom impls |
| Bootstrap confidence interval | Custom resampler with `np.percentile` | `scipy.stats.bootstrap(..., method='BCa', n_resamples=1000)` | BCa (bias-corrected accelerated) is statistically superior to percentile method; scipy's `bootstrap` is parallelizable via `batch=` and uses `np.random.Generator` correctly |
| Atomic JSON write | tempfile + manual rename | `tempfile.mkstemp(dir=destination_dir) + os.replace` | The `dir=` arg keeps temp on the same filesystem so `os.replace` is a POSIX atomic rename. Cross-FS rename is NOT atomic. Already verified in `cells/state.py:106-116` |
| Git commit with rollback | `os.system("git ...")` strings | `subprocess.run(["git", ...], check=True, capture_output=True, text=True)` | `check=True` raises CalledProcessError on non-zero exit; `capture_output=True` keeps stderr available for diagnostics; the `[list, of, args]` form is shell-injection-safe |
| Per-event JSONL append (held-out logging) | Open/close file per write | Reuse `trajectory/recorder.py` cached fd pattern (D-86 in Phase 3) — but write to a SEPARATE `gate/<parent_id>.gate_log.jsonl` file | The Linux flock-fd-cache problem from D-86 applies here too; the recorder pattern solved it |
| `nominations_in_window(days)` time math | hand-rolled timestamp filtering | `datetime.fromisoformat(node["created_at"]) > (now - timedelta(days=...))` | Use stdlib `datetime`; node history already uses ISO format (graph.py:144) |
| Multi-backend submit | branching on `if isinstance(backend, LocalBackend)` | Polymorphic `backend.submit(spec)` — works against MockSLURM and LocalBackend identically | Phase 2 BCK-04 lint forbids backend-specific branches in client code; gate must respect this |

**Key insight:** The hard parts of Phase 5 are statistical correctness, atomicity (write + commit), and isolation (held-out from agent view). Every one of these has a library or established pattern; the gate is glue, not invention.

## Runtime State Inventory

> Phase 5 is greenfield (new `gate/` package, new tests, new CLI surface). It does NOT rename or refactor existing code. The only mutations to existing files are additive (new node fields, new CLI imports, redactor pattern extension, viz endpoint addition). Therefore the rename/refactor inventory is intentionally minimal.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — graph.json gains TWO new node fields (`edge_type`, `held_out`) but these are additive on a free-form dict (no schema_version bump). | None — no migration. Existing nodes will read with `edge_type` defaulted to `"search"` via `node.get("edge_type", "search")`. |
| Live service config | None — no external services. Viz dashboard gets a NEW `/api/promotion-rate` SSE endpoint; existing endpoints unchanged. | Restart `automil viz start` once after deploy to pick up the new route. |
| OS-registered state | None — no Task Scheduler, systemd, launchd, pm2 entries reference gate concepts. | None. |
| Secrets / env vars | None — no new secrets; the trajectory redactor extension adds a regex pattern, but the held-out node-id placeholder is content-driven (read from manifest at runtime), not env-driven. | None. |
| Build artifacts / installed packages | scipy MUST move from `[ml]` optional deps to core deps in pyproject.toml. The `automil` package is `pip install -e .`; after the change, run `uv sync` so scipy resolves to the same 1.17.1 the workspace already uses transitively. | `uv sync` after pyproject.toml edit — verified `pip show scipy` returns 1.17.1 today via transitive autobench/sklearn deps, but core-dep enforcement makes the framework standalone. |

**Verified explicitly:**
- `grep -rn "candidate" src/automil/graph.py` returns zero hits — the `candidate` status string is genuinely new, not colliding with existing semantics.
- `grep -rn "edge_type\|\"edges\"" src/automil/` returns zero hits — no existing edge concept to break.
- `grep "@main.command(\"promote\")" src/automil/cli/` returns only `promote-variant` (hyphenated) — bare `promote` is unclaimed.

## Common Pitfalls

### Pitfall 1: Held-out cell budget exhaustion (interaction with Phase 4 cap)

**What goes wrong:** A held-out cell may already have agent submits earlier in its life (Phase 4 cap shared with gate-eval per D-150). At gate-eval time, the cell's budget could be near-exhausted, causing the gate-eval submit to be REFUSED (`is_refusing_new(cell)`) or return a `partial` result via Phase 4's reconcile path. A partial composite breaks the paired Wilcoxon (you can't pair against a non-comparable result).

**Why it happens:** Phase 5 reuses Phase 4's per-cell budget rather than allocating a separate gate-eval budget (D-150). This is the right choice (one cap mechanism, not two), but it means held-out cells have a SHARED budget surface with the agent loop.

**How to avoid:**
1. `gate/evaluate.py` checks `cells.is_refusing_new(cell)` BEFORE submit; if True, marks that cell `skipped_due_to_cap` in the result matrix.
2. `gate/stats.py` reduces effective K by the skipped count: `K_effective = K - len(skipped_cells)`. If `K_effective < K_floor` (default 2), the gate fails as INCONCLUSIVE rather than fail or pass.
3. `gate/promote.py` records `skipped_cells` in the promotion event so the operator sees why a candidate was inconclusive vs failed.
4. The calibration pilot (D-151) MUST use cells that have not been used by the agent loop — fresh cells only — to avoid this confound during calibration.

**Warning signs:**
- `automil gate stats` shows `inconclusive_rate > pass_rate + fail_rate` — gate is hitting the cap, not the candidates.
- A cell's status is FINALIZED at gate-eval time. (Solution: held-out cells should be reserved at manifest registration, not borrowed from active search cells.)

### Pitfall 2: Trajectory leak via held-out node IDs in stdout

**What goes wrong:** `trajectory/redactor.py` redacts secret patterns in events, but the agent's stdout/stderr capture might include `node_0234`-style IDs that are gate-eval children. Even though `automil rank` filters them, a `cat archive/*/run.log | grep node_` could surface a held-out ID, and that grep result could end up in a future trajectory event.

**Why it happens:** Held-out IDs are framework-internal but indistinguishable from regular node IDs at the string level. The redactor's pattern set (regex for `sk-`, `hf_`, etc.) doesn't know which `node_NNNN` is held-out vs. visible.

**How to avoid:**
1. Build a runtime-resolved redaction layer: `gate/redactor_extension.py` exposes a function `held_out_node_ids() -> set[str]` that scans graph.json for `metadata.held_out=true` nodes.
2. Extend `trajectory/redactor.py:redact()` to also replace any string matching `\bnode_\d{4}\b` IF the matched ID is in the held-out set, using a `<HELD_OUT>` placeholder.
3. The set is recomputed lazily per-event with a TTL cache (e.g., 60s) to avoid re-reading graph.json on every redact.
4. Alternative simpler design: tag held-out IDs with a distinct prefix at creation (`heldout_NNNN` instead of `node_NNNN`) — but this breaks the `next_id()` invariant in `graph.py:79-81`. Not recommended.

**Warning signs:**
- `tests/gate/test_held_out_isolation.py` fails its trajectory grep assertion: `assert "node_<heldout>" not in trajectory_text`.
- The redactor extension performance is bad: graph.json read on every event causes O(N events × M nodes) scaling. Cache + invalidate on graph.save() events.

### Pitfall 3: Manifest commit not actually atomic with file write

**What goes wrong:** `tempfile.mkstemp + os.replace` is atomic at the FS level, but the subsequent `git add + git commit` is NOT in the same transaction. If the process is killed between `os.replace` and `git commit`, the manifest exists in the working tree but is uncommitted — and the next `register-manifest` call refuses to overwrite, leaving a permanently-stuck state.

**Why it happens:** There's no FS-and-git transaction primitive in Python. The closest you get is "write to a uncommitted-but-existing file, then commit, then if commit fails roll back the write."

**How to avoid:**
1. Order matters: write atomically first, THEN commit. If commit fails, roll back via `path.unlink()` (NOT `git checkout` — Leo memory).
2. Add a recovery command: `automil gate register-manifest <parent_id> --force-recover` that detects an uncommitted manifest, validates its content, and commits it (with a recovery message). This handles the SIGKILL-in-the-middle case.
3. Test: `test_manifest.py::test_manifest_recovery_after_partial_failure` — write file, simulate `git commit` failure, assert the file is removed and the next register-manifest succeeds.
4. Two-phase commit: write manifest with `git_committed_at_sha = "PENDING"`, commit, get SHA, then atomically rewrite the manifest with the resolved SHA (D-138 #4 explicitly says "second commit if needed" — so this is already in the design).

**Warning signs:**
- An uncommitted `automil/gate/<parent_id>.gate_manifest.json` in `git status` after a register-manifest run that "succeeded."
- The manifest's `git_committed_at_sha` field is "PENDING" or empty after register completes.

### Pitfall 4: Bonferroni applied wrong direction

**What goes wrong:** Bonferroni correction in published papers is variously stated as "divide alpha by K" OR "multiply each p-value by K." For a single accept/reject decision, BOTH yield the same conclusion if applied correctly. A common bug: divide alpha by K AND multiply p-values by K (double correction) — too strict by factor of K. Or compare the unadjusted p to the unadjusted alpha after K cells (no correction) — too lax.

**Why it happens:** Bonferroni is documented two ways across textbooks (Wikipedia: divide alpha; SciPy/R-style: multiply p-values). The two ways produce equivalent decisions but cannot both be applied. **`[CITED: en.wikipedia.org/wiki/Bonferroni_correction]`**

**How to avoid:**
1. `bonferroni_correct(p_threshold, K)` returns the corrected ALPHA (divide path). In `paired_wilcoxon_with_bootstrap`, compare raw p-value to corrected alpha. ONE direction, applied ONCE.
2. Test: `test_stats.py::test_bonferroni_direction` — assert `bonferroni_correct(0.05, 5) == 0.01`, NOT 0.25.
3. Document the choice in `gate/stats.py` docstring: "We divide alpha by K (Wikipedia convention) rather than multiply p-values by K (multipletests convention) — equivalent for single decisions, less surprising in test logs."

**Warning signs:**
- Promotion rate is impossibly low or high — sign of double or zero correction.
- Test reads "Bonferroni-corrected p=0.001" but K=5 and reported alpha=0.05 — implies multiplied p (raw p=0.0002) vs divided alpha (raw p=0.001 still); inspect carefully.

### Pitfall 5: nominate command race condition

**What goes wrong:** Operator runs `automil nominate node_0234` while the orchestrator daemon is mid-tick processing that node's parent. The daemon writes to graph.json; the nominate command reads, mutates, writes — race condition could lose the nomination OR clobber a daemon update.

**Why it happens:** Graph.json is the agent's sole writer (per its docstring), but in practice the orchestrator daemon ALSO writes (during reconcile). The `tempfile + os.replace` pattern at `graph.py:787-801` makes individual writes atomic, but read-modify-write cycles by separate processes are NOT.

**How to avoid:**
1. `automil nominate` reads graph.json, mutates the in-memory dict, calls `graph.save()` (atomic). If the daemon wrote between read and save, the operator's nomination overwrites the daemon's update. **This is acceptable** because nominate touches `nodes[id]["status"]` from `keep` to `candidate` — the daemon never writes the status `keep` (it writes `running`/`completed`/`crash`/`partial`/etc.); the field is operator-owned in the keep state.
2. Add an optimistic-concurrency check: read `meta.next_id` before mutation; if it differs at save time, abort and ask the operator to re-run. Cheap insurance.
3. Test: `test_nominate.py::test_nominate_concurrent_daemon_write` — simulate a daemon write between read and save; assert nominate either succeeds or aborts with a clear error.

**Warning signs:**
- A nominated node appears reverted to `keep` after a few minutes — daemon's reconcile undid it.
- `automil nominate` succeeds but the status doesn't change in `automil status` immediately afterward.

### Pitfall 6: Gate too strict, search appears stuck (Pitfall 6a re-stated for code)

This is `research/PITFALLS.md` Pitfall 6 directly. The mitigations are designed-in:
- D-144 promotion_rate metric surfaces in `automil status` and viz.
- D-151 calibration pilot sets initial K empirically.
- O-01 default K=`max(2, len(held_out_cells)//3)` is generous — calibration tightens.

**Code-level addition Phase 5 must include:** `gate/stats.py:diagnose_gate_health(promotion_rate_30d, threshold_low=0.05, threshold_high=0.5) -> str` returns a human-readable diagnostic string surfaced in `automil status`. Without this, the metric is a number nobody reads.

## Code Examples

Verified patterns from official sources and the existing codebase:

### Atomic write (cells/state.py mirror)

```python
# Source: src/automil/cells/state.py:94-116 (verified by Read)
def write_cell(cell: Cell, cells_dir: Path) -> None:
    cells_dir.mkdir(parents=True, exist_ok=True)
    path = cells_dir / f"{cell.cell_id}.json"
    payload = json.dumps(dataclasses.asdict(cell), indent=2)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(cells_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(path))
    except Exception:
        try: os.unlink(tmp_path)
        except OSError: pass
        raise
```

### scipy paired Wilcoxon (probed live)

```python
# Source: scipy.stats.wilcoxon docs https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html
# Signature [VERIFIED via inspect.signature]:
# wilcoxon(x, y=None, zero_method='wilcox', correction=False,
#          alternative='two-sided', method='auto', *, axis=0,
#          nan_policy='propagate', keepdims=False)
import numpy as np
from scipy.stats import wilcoxon

# Paired use: pass deltas (= x - y) and y=None — equivalent to wilcoxon(x, y) with paired data.
deltas = np.array([0.012, 0.008, 0.015, -0.003, 0.011])
# alternative='greater' = test "median delta > 0", i.e., candidate beats parent
result = wilcoxon(deltas, alternative='greater', zero_method='wilcox')
print(result.statistic, result.pvalue)
# WilcoxonResult(statistic=14.0, pvalue=0.09375)  # K=5, mostly positive but not significant
```

### scipy bootstrap CI on median (probed live)

```python
# Source: scipy.stats.bootstrap docs https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html
import numpy as np
from scipy.stats import bootstrap

deltas = np.array([0.012, 0.008, 0.015, -0.003, 0.011])
rng = np.random.default_rng(42)
res = bootstrap(
    (deltas,),
    np.median,
    n_resamples=1000,
    confidence_level=0.95,
    method="BCa",  # default, bias-corrected accelerated
    rng=rng,
)
print(res.confidence_interval.low, res.confidence_interval.high)
# Note: parameter is `rng=` in scipy 1.17 (was `random_state=` in older versions; both accepted).
```

### Backend.submit with metadata (Option A pattern)

```python
# Source: src/automil/backends/local.py:121-142 (verified) + proposed JobSpec extension
# JobSpec gets a new field: metadata: tuple[tuple[str, str], ...] = ()
spec = JobSpec(
    node_id="node_0234",
    base_commit="abc1234",
    overlay_files=("automil/config.yaml",),
    overlay_dir=Path("archive/node_0234"),
    command=("python", "train.py"),
    env=(("AUTOMIL_GPU", "0"),),
    working_subdir="benchmarks",
    gpu_estimate_gb=1.0,
    walltime_seconds=21600,
    metadata=(  # NEW
        ("gate_eval", "true"),
        ("held_out", "true"),
        ("gate_parent_node", "node_0212"),
        ("cell_id", "abc12345..."),
        ("edge_type", "gate_eval"),
    ),
)
handle = backend.submit(spec)  # works for LocalBackend AND MockSLURMBackend identically
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled bootstrap with `np.percentile` | `scipy.stats.bootstrap(..., method='BCa')` | scipy 1.7 (2021) | BCa is statistically superior to percentile method; built-in vectorization via `batch=` arg |
| `scipy.stats.wilcoxon(x, y)` paired form | `scipy.stats.wilcoxon(deltas, alternative='greater')` (one-sample form on differences) | Always equivalent — but explicit `alternative='greater'` (added in scipy 1.7) makes the one-sided test direction unambiguous | Test direction explicit; reviewer cannot claim "two-sided test inflated significance" |
| `random_state=` for reproducibility | `rng=` (np.random.Generator) | scipy 1.13 (2024) | Both accepted in 1.17.1 but `rng=` is the modern API; use it for new code |
| No multiplicity correction | Bonferroni `alpha/K` (manual) OR FDR `scipy.stats.false_discovery_control` (1.13+) | scipy 1.13 added FDR | F1/F2 paper convention is Bonferroni for the gate (small K); FDR may be relevant for cross-parent comparisons later |
| `git checkout -- file` to roll back | `path.unlink()` to remove uncommitted file | Leo's memory rule | Never blind-checkout; user has uncommitted work that checkout silently destroys |

**Deprecated/outdated:**
- scipy.stats.wilcoxon's `correction` parameter (continuity correction for normal approximation) is rarely needed at K≥10 and never needed when `method='exact'` triggers automatically at small K. Leave at default `correction=False`.
- scipy < 1.13 used `random_state=` only; we're on 1.17.1, so `rng=` is preferred.

## Project Constraints (from CLAUDE.md)

These are non-negotiable directives for Phase 5 code:

- **Address Leo as "Leo" at the start of every response.** (Standing directive)
- **Plan mode for non-trivial work (3+ steps or architectural decisions).** Phase 5 IS a non-trivial architectural addition; the plan is required.
- **Subagents liberally for research, exploration, parallel analysis.** Per-plan execution may use parallel subagents for the gate/manifest, gate/stats, gate/evaluate triad.
- **Self-improvement loop:** any correction from Leo updates `tasks/lessons.md`. Phase 5's plan reviews must check `tasks/lessons.md` for Phase-4-derived lessons that apply.
- **Verification before done:** every Phase 5 task ends with running `uv run pytest tests/gate/ -v` AND the BCK-04 lint gate AND a framework-purity grep for `autobench`/`AUTOBENCH_`/`benchmarks/`.
- **Demand elegance balanced with simplicity.** The gate is plumbing; reach for elegance where it costs nothing (frozen dataclasses, pure functions, scipy idioms) but don't over-abstract.
- **Tests use `tmp_path` for graph + manifest fixtures.** No real backend; MockSLURMBackend for `evaluate_candidate` tests.
- **Framework purity:** zero `autobench` / `AUTOBENCH_` / `benchmarks/` references anywhere in `src/automil/gate/`. (Same rule as Phase 4 cells.)
- **BCK-04 lint:** zero `os.kill`, `os.killpg`, `os.getpid`, `Popen`, `.pid` in `src/automil/gate/`. The gate does not touch process control; it goes through `Backend.cancel()` if it ever needs to abort an eval.
- **Commit messages:** `gate: <subject>` style — conventional commits with `gate` as the scope prefix.
- **Update `tasks/todo.md` with checkable items** (Leo's task management discipline).
- **autoMIL is generic, autobench is one consumer** (Leo memory): the gate package must NOT contain autobench-shape-specific assumptions. K, p_threshold, held_out_cell selection are all consumer-driven (Leo's autoMIL-paper campaign supplies values; another consumer supplies different values).
- **Paper-campaign values are not framework constants** (Leo memory): K=2, K=3, p<0.05 are Leo's defaults for HIS campaign. The framework default (per O-01..O-02) is conservative; consumers override per project.
- **Decide engineering, ask features** (Leo memory): O-01..O-05 in CONTEXT.md are correctly flagged as Leo-decisions. Engineering choices (which scipy fn, which atomic-write pattern, which test fixture) are decided by research/plan; Leo only weighs in on K/p_threshold/held-out selection policy/calibration scope.

## Assumptions Log

> Claims tagged `[ASSUMED]` in this research. Planner and discuss-phase use this section to identify decisions that need user confirmation.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Adding `scipy>=1.11` to core deps in pyproject.toml will not regress autobench's already-installed scipy 1.17.1 | Standard Stack > Installation | Low — `>=1.11` is a floor; existing 1.17.1 satisfies. Verified 1.17.1 already installed, transitively. |
| A2 | `JobSpec` ABC extension (Option A) won't break existing 644+ tests | Architecture Patterns > Pattern 3 | Medium — adding a frozen-dataclass field with a default value is non-breaking, but tests that construct JobSpec by positional args will break. Mitigation: keyword-only arg with default `()`. |
| A3 | Operator-driven nomination (D-142 default) is sufficient defense against agent gaming the gate | (cited from CONTEXT.md D-142) | Low — D-142 is engineering decision; auto_nominate opt-in exists for trusted cases (O-05). |
| A4 | Bootstrap CI's `method='BCa'` is the right choice over `method='percentile'` or `method='basic'` | Code Examples > scipy bootstrap | Low — BCa is the F1 paper convention and scipy default; reviewer-defensible. |
| A5 | `<HELD_OUT>` placeholder in trajectory redaction is sufficient (vs hashing the ID) | Common Pitfalls > Pitfall 2 | Medium — placeholder loses ordering info that might be useful for debugging. Hashing preserves uniqueness. Either is acceptable; recommend placeholder for simplicity. |
| A6 | Held-out cell selection strategy default = stratified by (dataset, encoder) | Open Questions O-03 | Medium — engineering recommends stratified, but Leo decides per-campaign. |
| A7 | The calibration pilot is its own plan inside Phase 5, not a hard gate on Phase 5 sign-off | Open Questions O-04 | Medium — affects Phase 5 sign-off criteria. CONTEXT.md says "Pilot completion is a Phase 5 success criterion" (D-151); ROADMAP.md success criterion #4 says "calibration pilot ... sets initial K before locking." Recommend treating pilot as required for sign-off. |

**If this table is empty:** Empty would mean every claim was verified or cited. The seven assumptions above are flagged for Leo's confirmation during discuss-phase OR locked at planning time with explicit rationale.

## Open Questions (RESOLVED)

All five open questions surfaced during research are answered below. Each carries a `RESOLVED:` line citing the locking decision (CONTEXT.md D-NNN or downstream plan). The recommendations are the framework defaults the planner uses; Leo can patch CONTEXT.md if he wants to override before plans land.

1. **scipy as core dep — is this a "framework purity" violation?**
   - RESOLVED: D-148 (CONTEXT.md) + Plan 05-08. Add to core deps. scipy is generic scientific tooling, not autobench-specific. The gate is meaningless without it; making consumers install it themselves is friction.

2. **Should `gate/stats.py` accept `bootstrap_reps` as a parameter or hardcode 1000?**
   - RESOLVED: D-137 (CONTEXT.md). Manifest carries `bootstrap_reps` (per-parent override). Framework default 1000. Consumer can override in `register-manifest`. Per-experiment determinism + paper-time flexibility.

3. **Should the `nominate` -> `candidate` transition cascade-affect descendants?**
   - RESOLVED: D-136 (CONTEXT.md). Children stay `keep` until separately nominated. The `candidate` state is purely additive — does NOT trigger Pareto cascade or nominate descendants. The `registered` status is a leaf concept; cascading would require independent held-out tests per descendant. Plan 05-04 documents this in the gate package's README/docstring.

4. **Where does the `gate_log.jsonl` live?**
   - RESOLVED: D-149 + Plan 05-07 (promote.py). Both paths used:
     - Per-parent log at `automil/gate/<parent_id>.gate_log.jsonl` for promotion-rate analysis (one log per gate, all promote events appended).
     - Per-candidate detail at `archive/<candidate_id>/gate_evaluation.jsonl` for forensic reconstruction.
     - Different read paths, different consumers.

5. **Manifest field `git_committed_at_sha` — recursive write?**
   - RESOLVED: D-138 (CONTEXT.md) + Plan 05-02. Separate second commit (no amend). Two-line history is fine for paper-time forensic auditing. Amend would rewrite history; rejected. Plan 05-02 implements as a follow-up `git_committed_at_sha`-stamping commit after the initial manifest write+commit.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| scipy 1.11+ | gate/stats.py (wilcoxon, bootstrap) | ✓ | 1.17.1 | — (no fallback; statsmodels would add ~80MB) |
| numpy | gate/stats.py (deltas array) | ✓ | (transitive via scipy/torch) | — |
| git CLI | gate/manifest.py (atomic write+commit) | ✓ | — | — (project is git-managed; assumed) |
| click 8.1+ | CLI surface | ✓ | already in core | — |
| Backend ABC + LocalBackend | gate/evaluate.py.spawn evals | ✓ | Phase 2 complete | — (Phase 5 depends on Phase 2) |
| cells/registry.py:get_or_create_cell | gate/evaluate.py auto-creates held-out cells | ✓ | Phase 4 complete | — (Phase 5 depends on Phase 4) |
| trajectory/redactor.py | held-out node-id placeholder | ✓ | Phase 3 complete | — (Phase 5 depends on Phase 3) |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — every dep is satisfied by prior-phase deliverables OR already-installed packages.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2+ |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options] testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/gate/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GTE-01 | `candidate` status exists; manifest format | unit | `pytest tests/gate/test_manifest.py -v` | ❌ Wave 0 |
| GTE-01 | candidate node carries gate_manifest reference | integration | `pytest tests/gate/test_two_stage_gate.py -v` | ❌ Wave 0 |
| GTE-02 | manifest pre-registered + git-committed BEFORE search | unit | `pytest tests/gate/test_manifest.py::test_manifest_committed_before_first_candidate` | ❌ Wave 0 |
| GTE-02 | manifest immutability + retire flow | unit | `pytest tests/gate/test_manifest.py::test_manifest_immutable_retire` | ❌ Wave 0 |
| GTE-03 | Backend.submit() called with metadata.gate_eval=true | unit (MockSLURM) | `pytest tests/gate/test_evaluate.py::test_evaluate_uses_backend_submit` | ❌ Wave 0 |
| GTE-03 | gate_eval edge type marked on child nodes | unit | `pytest tests/gate/test_evaluate.py::test_gate_eval_edge_type` | ❌ Wave 0 |
| GTE-04 | paired Wilcoxon p-value computation | unit (pure scipy) | `pytest tests/gate/test_stats.py::test_paired_wilcoxon` | ❌ Wave 0 |
| GTE-04 | bootstrap CI on median delta | unit | `pytest tests/gate/test_stats.py::test_bootstrap_ci` | ❌ Wave 0 |
| GTE-04 | Bonferroni correction direction | unit | `pytest tests/gate/test_stats.py::test_bonferroni_direction` | ❌ Wave 0 |
| GTE-04 | K and p_threshold are config-set | unit | `pytest tests/gate/test_manifest.py::test_manifest_carries_K_pthreshold` | ❌ Wave 0 |
| GTE-05 | manual nomination is default | unit | `pytest tests/gate/test_nominate.py::test_auto_nominate_off_by_default` | ❌ Wave 0 |
| GTE-05 | `automil nominate <node>` mutates status | unit | `pytest tests/gate/test_nominate.py::test_nominate_mutates_status` | ❌ Wave 0 |
| GTE-06 | promotion_rate metric computation | unit | `pytest tests/gate/test_promote.py::test_promotion_rate` | ❌ Wave 0 |
| GTE-06 | promotion_rate exposed in viz | integration | `pytest tests/gate/test_promote.py::test_promotion_rate_in_viz_endpoint` | ❌ Wave 0 |
| Pitfall 6 | held-out cells invisible to agent | LOAD-BEARING | `pytest tests/gate/test_pitfall6_held_out_isolation.py` | ❌ Wave 0 |
| BCK-04 (gate) | zero process-control refs in src/automil/gate/ | lint | `pytest tests/test_backend_isolation_lint.py` (extend allowlist OR allowlist gate/) | ✅ exists; needs extension |
| Framework purity | zero autobench refs in src/automil/gate/ | lint | `pytest tests/gate/test_framework_purity.py` (mirrors cells purity test) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/gate/test_<focused>.py -x -q` (target: <10s)
- **Per wave merge:** `uv run pytest tests/gate/ -v` (target: <60s; pure-function stats + MockSLURM = no real I/O)
- **Phase gate:** `uv run pytest tests/ -v` full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/gate/__init__.py` — package marker
- [ ] `tests/gate/conftest.py` — synthetic graph + tmp_path manifest + MockSLURM fixtures
- [ ] `tests/gate/test_manifest.py` — covers GTE-01, GTE-02
- [ ] `tests/gate/test_nominate.py` — covers GTE-05
- [ ] `tests/gate/test_evaluate.py` — covers GTE-03 (uses MockSLURMBackend from tests/backends/)
- [ ] `tests/gate/test_promote.py` — covers GTE-06
- [ ] `tests/gate/test_stats.py` — covers GTE-04 (pure scipy, no fixtures needed beyond np.array)
- [ ] `tests/gate/test_held_out_isolation.py` — covers D-139 isolation
- [ ] `tests/gate/test_two_stage_gate.py` — covers D-143 Stage A + Stage B composition
- [ ] `tests/gate/test_pitfall6_held_out_isolation.py` — LOAD-BEARING anti-acceptance gate (D-149)
- [ ] `tests/gate/test_framework_purity.py` — zero autobench refs (mirrors `tests/cells/` purity)
- [ ] `tests/test_backend_isolation_lint.py` extension — assert no os.kill/Popen/.pid in `src/automil/gate/`
- [ ] No new framework install needed (scipy is already there; BCK-04 lint already exists)

## Security Domain

> Required because `security_enforcement: true` in `.planning/config.json`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V1 Architecture | yes | Manifest is single-writer (operator via CLI); no concurrent gate writers; threat model documented in `gate/__init__.py` docstring |
| V2 Authentication | no | No auth — single-operator project; manifest is integrity-protected by git commit, not by auth |
| V3 Session Management | no | No sessions — CLI-driven, stateless |
| V4 Access Control | no | No access control — same single-operator assumption as the rest of automil |
| V5 Input Validation | yes | Manifest schema validation: K is int >=1, p_threshold is 0<float<=1, bootstrap_reps int>=100, held_out_cells is non-empty list of valid cell_ids — all validated in `gate/manifest.py:validate_manifest_dict()`. CLI inputs (`--K`, `--p-threshold`) validated by Click types. |
| V6 Cryptography | yes | git commit SHA serves as cryptographic timestamp for pre-registration (D-138 #4). NEVER hand-roll an alternative — the SHA is good enough for the F2 paper's "this manifest existed at this time" claim. |
| V7 Error Handling | yes | Manifest write+commit rollback on failure; soft-fail-with-warning for redaction (Pitfall 2 mitigation); explicit error messages with structured reason codes. |
| V8 Data Protection | partial | Held-out cell IDs are sensitive (leak compromises gate); D-139 isolation + redactor extension protects them. NOT classified as PII or secrets per se, but protected from agent observation. |
| V9 Communication | no | No network I/O in gate/ — all local FS + git |
| V10 Malicious Code | yes | scipy + numpy are trusted scientific libs; no exec/eval; CLI input is type-validated (Click); subprocess calls use list-form argv (not shell strings) |
| V11 Business Logic | yes | Two-stage gate (D-143) prevents single-stage bypass; pre-registration (D-138) prevents post-hoc manifest tampering; promotion-rate metric (D-144) detects gate gaming |
| V12 Files & Resources | yes | tempfile.mkstemp uses correct umask (700); manifest dir created with mkdir(exist_ok=True); no path traversal because parent_id is validated against existing graph node (`graph.get_node(parent_id) is not None`) |
| V13 API | n/a | No web API beyond viz/server.py SSE endpoint, which is read-only |
| V14 Configuration | yes | gate: section in config.yaml.j2 has secure defaults (auto_nominate=false, p=0.05, bootstrap_reps=1000); no secrets in gate config |

### Known Threat Patterns for {gate stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Operator backdates a manifest after seeing search results | Tampering | git commit SHA in `git_committed_at_sha` field is a cryptographic timestamp; D-138 immutability (refuse to overwrite); retire-manifest creates a NEW commit, not silent replacement |
| Agent learns to game the gate by nominating only its best candidate | Bypassing | Manual nomination default (D-142); auto_nominate opt-in carries audit log entry `agent_initiated: true` per D-142 |
| Held-out cell results leak into agent's prompt context | Information Disclosure | D-139 isolation: rank filter + trajectory redactor extension + separate gate log file; D-149 anti-acceptance test asserts trajectory contains zero held-out IDs |
| Path traversal via `parent_id` argument to register-manifest CLI | Tampering | Validate parent_id is a real graph node ID via `graph.get_node(parent_id) is not None` BEFORE writing any file; reject IDs containing `/`, `..`, or non-`node_NNNN` patterns |
| scipy import-time arbitrary code execution (supply-chain) | Tampering | scipy is a trusted PyPI package, locked via `uv.lock`; same trust model as torch/numpy already in deps |
| Manifest immutability bypass via direct file edit | Tampering | git pre-commit hook (optional, future) could refuse manifest edits; primary defense is the git commit SHA in the manifest itself — any edit invalidates the SHA, detectable in `automil gate status` audit |
| Wilcoxon p-value floating-point manipulation | Tampering | scipy.stats.wilcoxon is a deterministic function of input deltas; deltas come from completed `result.json` files committed under `archive/<id>/`; tampering with deltas requires editing committed archive files (visible in git diff) |
| Bootstrap RNG seed leakage compromises reproducibility | Information Disclosure (low impact) | Default `rng=None` is non-deterministic (production); tests pass `rng_seed=42` for determinism; SHA of seed-and-deltas can be logged to gate_log.jsonl for paper-time audit |

## Sources

### Primary (HIGH confidence)

- `[VERIFIED: src/automil/cells/state.py]` — atomic write pattern (lines 94-116) — the proven template for gate/manifest.py
- `[VERIFIED: src/automil/cells/cap.py]` — pure-function state machine (next_status) — template for gate/stats.py purity discipline
- `[VERIFIED: src/automil/cells/registry.py]` — get_or_create_cell idempotency — template for held-out cell auto-creation behavior
- `[VERIFIED: src/automil/cli/cell.py]` — `@main.group("cell")` Click pattern — template for `@main.group("gate")` in cli/gate.py
- `[VERIFIED: src/automil/backends/base.py]` — JobSpec/JobHandle ABC contract; lines 58-93 confirm JobSpec has no `metadata` field today
- `[VERIFIED: src/automil/backends/local.py]` — LocalBackend.submit (lines 89-177) builds queue spec dict with `metadata` passthrough; cli/submit.py:340-348 confirms cell_id stamping pattern
- `[VERIFIED: src/automil/graph.py]` — node dict is free-form (lines 122-145); status is plain string (line 127); no edges collection exists; `tempfile + os.replace` save pattern at line 787
- `[VERIFIED: src/automil/cli/lifecycle/promote_variant.py]` — git mv + git add pattern (lines 105-126); confirms NO existing pattern for atomic-write-PLUS-commit (only stage)
- `[VERIFIED: src/automil/trajectory/redactor.py]` — regex-pattern redaction model that gate redactor extension will mirror
- `[VERIFIED: pip show scipy 2026-05-05]` — scipy 1.17.1 installed via autobench, scikit-image, scikit-learn, trident transitive deps
- `[VERIFIED: uv run python -c]` — scipy.stats.wilcoxon and scipy.stats.bootstrap signatures probed live
- `[VERIFIED: pyproject.toml]` — scipy currently in `[ml]` optional, not core
- `[CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html]` — function signature and zero_method semantics
- `[CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html]` — BCa method default, n_resamples parameter
- `[CITED: en.wikipedia.org/wiki/Bonferroni_correction]` — divide-alpha vs multiply-p-values equivalence
- `[VERIFIED: .planning/research/PITFALLS.md Pitfall 6]` — gate calibration risks; pre-registration requirement; F1 §4.4/§5.6 paired-Wilcoxon citation
- `[VERIFIED: .planning/phases/05-generalization-gate/05-CONTEXT.md]` — D-135..D-151 engineering decisions; O-01..O-05 open questions

### Secondary (MEDIUM confidence)

- `[CITED: arxiv.org/pdf/2002.09227 (García et al.)]` — recent trends in statistical tests for ML algorithm comparison; supports paired Wilcoxon as the standard for K small (≤30 paired samples)
- `[CITED: scikit-posthocs.readthedocs.io/en/latest/generated/scikit_posthocs.posthoc_wilcoxon.html]` — pairwise Wilcoxon with multitest correction; alternate library for cross-comparison if Phase 5 ever extends to many-parent comparison

### Tertiary (LOW confidence — flagged for validation if needed)

- None — every claim in this research has at least one HIGH or MEDIUM source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — scipy verified live; idioms cross-referenced with scipy docs and existing codebase patterns
- Architecture: HIGH — every modify-site read line-by-line; ABC extension proposal is non-breaking; redactor extension follows existing rotation/recorder patterns
- Pitfalls: HIGH for Pitfalls 1-5; MEDIUM for Pitfall 6 (depends on calibration which is itself O-04); the load-bearing test (D-149) is well-specified
- User constraints: HIGH — CLAUDE.md and Leo memory directives translated into concrete code-level rules
- Validation architecture: HIGH — test surface enumerated against requirements; framework already exists; only gate/ test files need creation

**Research date:** 2026-05-05
**Valid until:** 2026-06-04 (30 days; scipy is stable, codebase patterns are stable. Re-verify if scipy minor version bumps cross 1.18 OR if the Backend ABC changes shape in Phase 6 SLURM/Ray work.)
