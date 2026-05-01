# Architecture Research

**Domain:** Autonomous ML experiment framework — refactor of existing brownfield codebase (`src/automil/`)
**Researched:** 2026-04-30
**Confidence:** HIGH for individual patterns (timm, TorchX, OpenEvolve, Hydra, submitit are all reference-class systems with public source). MEDIUM for the integrated layout — the specific composition is opinionated and untested at autoMIL scale; will need a pilot in the migration phase.

This document does NOT re-document the existing experiment-tree, orchestrator, runner, viz, or CLI — those are mapped in `.planning/codebase/ARCHITECTURE.md`. It covers how five new architectural pieces plug into that mapped system:

1. Variant registry layer
2. Backend abstraction over the orchestrator
3. Multi-runtime agent-asset organization
4. Trajectory instrumentation
5. Generalization gate inside the search loop

---

## 1. New Components Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Coding Agent (any runtime)                       │
│   reads agent_assets/<runtime>/ skill, edits VARIANT MODULES (not        │
│   shared library files), invokes `automil` CLI                           │
└─────────────────┬───────────────────────────────────────────────────────┘
                  │ submit / propose (with variant ref) + trajectory.jsonl
                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                   │
│  Existing commands + apply / revert-baseline / cancel / resubmit /       │
│  port-variant / promote-variant / reconcile --recompute-best             │
└──┬───────────────────────────────────┬──────────────────────────────────┘
   │ submit reads & resolves           │ writes spec + captures trajectory
   ▼                                   ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│  REGISTRY LAYER (NEW)    │    │  Spec Queue (existing)   │
│  src/automil/registry/   │    │  + trajectory.jsonl      │
│  • base.py (Variant ABC) │    │  + variant_ref           │
│  • registry.py (lookup)  │    │  + cell_id               │
│  • validators/           │    └─────────┬────────────────┘
│  • discovery (scan dirs) │              │
└──────────────────────────┘              ▼
                                   ┌──────────────────────────┐
                                   │  BACKEND DISPATCHER (NEW)│
                                   │  src/automil/backends/   │
                                   │  • base.py (Backend ABC) │
                                   │  • local.py  (current    │
                                   │      orchestrator behind │
                                   │      the interface)      │
                                   │  • slurm.py  (sbatch)    │
                                   │  • ray.py    (Ray jobs)  │
                                   └────┬─────────────────────┘
                                        │ submit / poll / log_iter / cancel
                                        ▼
                              ┌─────────────────────────┐
                              │  Existing Runner +      │
                              │  worktree + training    │
                              │  subprocess             │
                              └────┬────────────────────┘
                                   │ result.json + trajectory.jsonl
                                   ▼
                              ┌─────────────────────────┐
                              │  Existing Graph + GEN   │
                              │  GATE (NEW): hold the   │
                              │  variant in `candidate` │
                              │  status until ≥K cells  │
                              │  improve, then promote  │
                              │  to registered/         │
                              └─────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation pattern |
|-----------|---------------|------------------------|
| `registry.base.Variant` | ABC for a swap-in module (model variant, loss variant, etc.) — narrow interface, no behavior | `abc.ABC` + `@dataclass`-style frozen metadata |
| `registry.Registry` | Explicit name → factory map. Supports namespacing (`clam.attention.gated_v2`), scoped lookup per parent model. | Decorator-driven registration with explicit `import` triggers (NOT auto-discovery) |
| `registry.validators.*` | Pre-submit checks: identity preservation (architecture-preserving mode), interface conformance, no shared-library edits | Pluggable validator chain, per-mode |
| `backends.base.Backend` | ABC: `submit`, `poll`, `log_iter`, `cancel`, `describe`, `list_running`. Adapts spec → backend-native job. | TorchX-style with submitit/concurrent.futures ergonomics |
| `backends.local.LocalBackend` | Wraps the existing `ExperimentOrchestrator` daemon behind the ABC | Re-export of current code, NOT rewrite |
| `backends.slurm.SlurmBackend` | Renders sbatch scripts, polls `squeue`, tails files | Patterned on TorchX `slurm_scheduler` + submitit |
| `backends.ray.RayBackend` | Submits Ray Jobs via Job Submission SDK | Patterned on TorchX `ray_scheduler` |
| `agent_assets/<runtime>/` | Per-runtime skill bundles (Claude / Codex / OpenCode / Gemini-CLI / DeepSeek-via-X) | Universal `SKILL.md` standard with per-runtime overrides |
| `trajectory.Recorder` | Captures agent prompt + tool-call stream into `archive/<node_id>/trajectory.jsonl` with bounded size | JSONL append + truncation + LFS-pointer for huge nodes |
| `gate.GeneralizationGate` | Holds new variants in `candidate` status; promotes to `registered` only after improving on ≥K held-out cells | Edge in graph + new node `status` value |

---

## 2. Recommended Project Structure (Post-Refactor)

```
src/automil/
├── __init__.py
│
├── core/                       # narrow stdlib-only kernel — no new deps
│   ├── graph.py                # MOVED from src/automil/graph.py
│   │                           #   adds: status='candidate', cell_id field,
│   │                           #         variant_ref field, gate edges
│   ├── runner.py               # MOVED — git worktree primitives unchanged
│   └── ids.py                  # NEW — node_id minting, cell_id derivation
│                               #   (was inline in graph.py)
│
├── cli/                        # SPLIT from monolithic cli.py (~726 lines)
│   ├── __init__.py             # @click.group main
│   ├── _common.py              # _find_automil_dir, _load_config helpers
│   ├── init.py                 # init / check
│   ├── submit.py               # submit / propose / cancel / resubmit
│   ├── reconcile.py            # reconcile / rank / status
│   ├── variants.py             # NEW: apply / revert-baseline / port-variant
│   │                           #      promote-variant / list-variants
│   ├── orchestrator.py         # passthrough to backend daemon
│   └── viz.py                  # passthrough
│
├── registry/                   # NEW LAYER — variant management
│   ├── __init__.py             # exposes register / get / list_variants
│   ├── base.py                 # Variant ABC, VariantSpec dataclass
│   ├── registry.py             # Registry class (explicit, NOT auto-import)
│   ├── discovery.py            # `automil refresh-registry` scans variants/ dirs
│   └── validators/
│       ├── __init__.py
│       ├── identity.py         # F1 architecture-preserving guard
│       ├── interface.py        # type-signature conformance
│       └── purity.py           # forbids edits to shared library files
│
├── backends/                   # NEW LAYER — pluggable execution
│   ├── __init__.py             # get_backend(name) factory
│   ├── base.py                 # Backend ABC
│   ├── local.py                # wraps existing orchestrator.py + runner.py
│   ├── slurm.py                # NEW
│   ├── ray.py                  # NEW
│   └── _orchestrator_daemon.py # MOVED from orchestrator.py — local impl
│                               #   (the polling loop, GPU bin-packing, etc.)
│
├── trajectory/                 # NEW LAYER — agent observability
│   ├── __init__.py
│   ├── recorder.py             # JSONL writer, bounded by size + lines
│   ├── schema.py               # event types: prompt, tool_call, tool_result, edit, decision
│   └── compaction.py           # post-run compactor (drops verbose outputs to summary)
│
├── gate/                       # NEW LAYER — search-loop quality gate
│   ├── __init__.py             # promote_if_generalizes(node, K, threshold)
│   ├── generalization.py       # cross-cell evaluation queue
│   └── promotion.py            # candidate → registered status transition
│
├── agent_assets/               # RENAMED from claude_assets/
│   ├── _shared/                # universal SKILL.md content
│   │   ├── SKILL.md            # canonical base (works in Claude Code, Codex,
│   │   │                       #   Gemini-CLI per universal Agent Skills standard)
│   │   ├── policies/           # cross-runtime guidance (saturation, research, etc.)
│   │   └── hooks/              # generic shell hooks
│   ├── claude/                 # runtime-specific extensions only
│   │   ├── settings.json.j2    # registers Stop hook, etc.
│   │   └── overrides/SKILL.md  # patches over _shared/SKILL.md
│   ├── codex/
│   │   ├── AGENTS.md.j2        # Codex's native instructions filename
│   │   └── overrides/SKILL.md
│   ├── opencode/
│   │   └── overrides/SKILL.md
│   ├── gemini_cli/
│   │   └── overrides/SKILL.md
│   └── deepseek/               # via OpenCode-compatible adapter
│       └── overrides/SKILL.md
│
├── templates/                  # unchanged — Jinja2 init scaffolding
│   ├── config.yaml.j2          # adds backend, runtime, registry blocks
│   ├── program.md.j2
│   └── learnings.md.j2
│
├── viz/                        # unchanged — re-exports under new namespace OK
│   ├── server.py
│   └── static/
│
└── compat.py                   # NEW — re-export shim for old import paths
                                #   (e.g., `from automil.graph import …` still works
                                #    by aliasing to automil.core.graph)
```

### Structure Rationale

- **`core/` is stdlib-only.** No new deps, no backend imports, no registry imports. This keeps `graph.py`'s 48 tests green and makes the kernel reusable from any backend or CLI.
- **CLI split mirrors command groups.** The current `cli.py` at 726 lines is past the point where one file is ergonomic. Splitting by command group keeps each file <300 lines and makes adding `apply` / `revert-baseline` / etc. low-risk.
- **`registry/` and `backends/` are sibling layers, both above `core/`.** Neither depends on the other; both are imported by `cli/` and by `backends/_orchestrator_daemon.py`.
- **`agent_assets/_shared/` first, runtime overrides second.** The universal Agent Skills standard means most content is portable. Per-runtime dirs hold ONLY the diffs (Codex's `AGENTS.md` filename, Claude's `settings.json` hook registration). This avoids 5x duplication of the 200-line core skill.
- **`compat.py` keeps the migration safe.** Existing tests do `from automil.graph import ExperimentGraph`; that import keeps working via re-export. The migration commits move files but leave the public API untouched.

---

## 3. Architectural Patterns

### Pattern 1: Explicit Registry with Variant Modules (NOT auto-discovery)

**What:** A central `Registry` mapping names to factory callables, populated by **explicit imports** in a module-level `variants/__init__.py` per parent model. No metaclass magic, no `pkgutil.walk_packages` auto-discovery.

**When:** For every code-level mutation the agent introduces (model-arch, loss, optimizer, ensembling, training-paradigm). Replaces `args.X = literal` overrides in shared library files.

**Why explicit-import over decorator-only:** Self-registering decorators run as a side effect of `import`. If the agent writes `variants/clam_mb_attention_gated_v2.py` and never imports it, the registry doesn't know it exists. timm solves this with `_model_to_module` + explicit `from .resnet import *` — the module list is the source of truth, decorators just label entries within imported modules. autoMIL adopts the same pattern: `variants/__init__.py` lists imports; the decorator inside each module records the entry. `automil refresh-registry` (CLI) regenerates `__init__.py` from the directory listing, making registration mechanical without being magical.

**Example:**

```python
# src/automil/registry/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class VariantSpec:
    name: str                       # 'clam_mb.attention.gated_v2'
    parent: str                     # 'clam_mb' — for identity-preservation scoping
    kind: str                       # 'attention' | 'loss' | 'optimizer' | 'forward' | ...
    factory: callable               # () -> nn.Module or () -> Loss or () -> Optimizer-builder
    metadata: dict                  # cell origin, agent id, trajectory ref
    parents: tuple[str, ...] = ()   # variant lineage (was-built-on)

class Variant(ABC):
    """Marker base class — concrete variant module exports a `SPEC: VariantSpec`."""
    SPEC: VariantSpec

# src/automil/registry/registry.py
class Registry:
    def __init__(self): self._entries: dict[str, VariantSpec] = {}
    def register(self, spec: VariantSpec) -> None:
        if spec.name in self._entries:
            raise ValueError(f"Duplicate variant {spec.name}")
        self._entries[spec.name] = spec
    def get(self, name: str) -> VariantSpec: return self._entries[name]
    def list_for_parent(self, parent: str, kind: str | None = None):
        return [s for s in self._entries.values()
                if s.parent == parent and (kind is None or s.kind == kind)]

# Per-project: <project>/variants/clam_mb/attention_gated_v2.py
from automil.registry import register, VariantSpec
def _build():
    return GatedAttentionV2(...)
SPEC = VariantSpec(name='clam_mb.attention.gated_v2', parent='clam_mb',
                   kind='attention', factory=_build, metadata={'cell_id': '...'})
register(SPEC)

# Per-project: <project>/variants/clam_mb/__init__.py  (regenerated by CLI)
from . import attention_gated_v2  # noqa
# ... auto-listed by `automil refresh-registry`
```

**Trade-offs:**
- ✅ Pareto-clean separation: shared library files stay clean; mutations are committed modules.
- ✅ Cross-dataset contamination root-caused — different cells reference different variant names; same shared lib.
- ✅ Both `architecture-preserving` and `free` modes use the same registry (different validators).
- ❌ Adds one CLI command (`refresh-registry`) and one trip through the validator chain on submit.
- ❌ Per-project `variants/` lives in the host repo, NOT in `src/automil/` — autoMIL stays generic.

### Pattern 2: Backend ABC with Local as the Reference Implementation

**What:** A `Backend` ABC adapted from TorchX's Scheduler interface, with the existing `ExperimentOrchestrator` daemon repackaged as `LocalBackend` behind it. SLURM and Ray are added later as additional implementations.

**When to use:** Any execution path. CLI's `submit` always goes through `Backend.submit(spec)`; the daemon is local-backend-internal.

**Why TorchX shape (and not Snakemake / submitit-only):** TorchX defines exactly the methods the orchestrator needs (`submit`, `describe`, `list`, `cancel`, `log_iter`) and treats local-as-just-another-backend by default. submitit is excellent for SLURM but doesn't have a local-equivalent abstraction at the same shape. Snakemake is a workflow engine, not a job scheduler — wrong altitude. Ray Jobs is a native fit for the Ray backend but doesn't generalize to SLURM. TorchX's `Scheduler` interface is the lowest common denominator that fits all three.

**Minimum interface:**

```python
# src/automil/backends/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Literal

JobStatus = Literal['pending', 'running', 'completed', 'crash', 'oom', 'timeout', 'cancelled']

@dataclass
class JobHandle:
    backend_id: str           # backend-native identifier (sbatch JOBID, Ray submission_id, local PID)
    node_id: str              # autoMIL node id
    status: JobStatus
    submitted_at: float

class Backend(ABC):
    @abstractmethod
    def submit(self, spec: dict) -> JobHandle: ...
    @abstractmethod
    def describe(self, node_id: str) -> JobHandle | None: ...
    @abstractmethod
    def list_running(self) -> list[JobHandle]: ...
    @abstractmethod
    def cancel(self, node_id: str) -> bool: ...
    @abstractmethod
    def log_iter(self, node_id: str, *, follow: bool = False) -> Iterator[str]: ...
    # Optional / default impls:
    def close(self) -> None: ...
    def healthcheck(self) -> dict: return {'ok': True}
```

**State per backend:**

| Backend | Local state | Remote state | Polling model |
|---------|-------------|--------------|---------------|
| `LocalBackend` | `running/<id>.json`, `gpu_state.json`, in-process `self.running` dict, daemon PID | None | Daemon polls subprocess; CLI reads files |
| `SlurmBackend` | `running/<id>.json` mapping `node_id → JOBID`, sbatch script template | `squeue` output for the user | CLI / daemon polls `squeue -j <jobs> -o ...` |
| `RayBackend` | `running/<id>.json` mapping `node_id → submission_id`, Ray client config | Ray dashboard / Job Submission API | Async — Ray client reports status via SDK |

**Why "Local as reference" matters:** The current ~750-line orchestrator.py becomes the `LocalBackend`'s internal daemon. The ABC abstraction is what makes the SLURM impl bounded — without it, SLURM support means writing a second orchestrator from scratch, which is exactly the failure mode the proposal calls out. Build order: ABC first (1-2 days), Local-behind-ABC second (1-2 days, mostly mechanical re-export), SLURM third (2-3 days as a fresh impl with the contract clear), Ray fourth.

**Trade-offs:**
- ✅ Same code path on laptop, SLURM cluster, Ray cluster.
- ✅ The backend is a single place for `start_new_session=True` (the process-group fix from CONCERNS.md) and other launch-time invariants.
- ✅ Tests can use a `MockBackend` that returns canned results.
- ❌ Hot-reload of orchestrator config (current feature) needs to be re-rooted to `LocalBackend.reload()`.
- ❌ Logging unification across backends is non-trivial — local writes to `archive/<id>/run.log`; SLURM writes to `slurm-<jobid>.out`; Ray streams via SDK. Unify by having `log_iter` always copy into `archive/<id>/run.log` on completion.

### Pattern 3: Universal SKILL.md + Per-Runtime Overrides (NOT flatten or templatize)

**What:** A single canonical `SKILL.md` lives in `agent_assets/_shared/`. Each per-runtime directory contains ONLY the diffs that runtime requires: filename overrides (Codex uses `AGENTS.md`), settings hooks (Claude's `Stop` hook), or front-matter extensions.

**When to use:** Multi-runtime support is V1 not deferred. The Agent Skills universal standard already covers Claude Code, Codex, Gemini CLI, OpenCode, Cursor, Aider, Windsurf, Antigravity, and others — the SKILL.md format is a **lingua franca**, not Claude-specific.

**Why _shared+overrides over flatten or template-per-runtime:**
- **Flatten** (one dir mixing all runtimes' files): brittle ordering, no clear "which file ships where," hard to add a new runtime.
- **Template per runtime** (Jinja for each runtime): forces re-render of identical content N times; identical work surfaces as N different files; review burden compounds.
- **_shared + overrides** (recommended): write skill content once; per-runtime dir is small (<10 lines per file usually); adding a new runtime is a new override directory; same content, different shells.

**Example layout:**

```
agent_assets/_shared/SKILL.md                  # 200-line canonical skill
agent_assets/_shared/hooks/on_stop.sh          # generic shell hook
agent_assets/claude/settings.json.j2           # registers the Stop hook in .claude/
agent_assets/claude/overrides/SKILL.md         # tiny: { "_extends": "_shared/SKILL.md", ... }
agent_assets/codex/AGENTS.md.j2                # Codex reads AGENTS.md, not SKILL.md
agent_assets/codex/overrides/SKILL.md          # tiny extension; renderer concatenates
agent_assets/opencode/overrides/SKILL.md
```

**`automil init --runtime claude` behavior:**
1. Detect runtime via auto-detect (look for `.claude/`, `AGENTS.md`, `.codex/`, etc.) or CLI flag.
2. Read `_shared/SKILL.md` as base.
3. Patch with `<runtime>/overrides/SKILL.md` (a YAML `_extends` directive concat).
4. Write to runtime-native location: `.claude/skills/automil/SKILL.md`, or `AGENTS.md` at repo root, or `.opencode/SKILL.md`, etc.
5. Install runtime-specific hooks (Claude only currently).

**Trade-offs:**
- ✅ Adding a new runtime is `mkdir agent_assets/<name>/overrides/` + a few lines.
- ✅ Same `SKILL.md` content stays in sync across runtimes — bug fixes happen once.
- ✅ Defends F2's "this is a Claude paper" reviewer attack — autoMIL trivially runs across runtimes.
- ❌ Two-level resolution (base + override) is a small mental tax. Mitigated by an `automil show-skill --runtime claude` debug command.

### Pattern 4: Trajectory JSONL with Compaction (NOT raw transcript dump)

**What:** Per-experiment `archive/<node_id>/trajectory.jsonl` captures the agent's prompt + tool-call stream as one JSONL event per agent action, with bounded size via post-run compaction.

**When to use:** Always. Every submit. No opt-out.

**Why JSONL (not single JSON, not Parquet):**
- JSONL is the de facto standard for agent traces (SWE-bench, AgentBench, OpenAI Agents SDK, LangSmith all use it). Tooling exists.
- Append-only — survives crashes mid-run.
- Diff-friendly with `git diff` (rare but useful).
- Size-friendly: bz2 compresses 10:1 typical for repetitive tool I/O.

**Schema (kept narrow):**

```python
# src/automil/trajectory/schema.py
EVENT_TYPES = {
    'prompt',        # initial agent prompt
    'tool_call',     # name + sanitized args (truncate long strings)
    'tool_result',   # truncated output (first 2KB + "[...truncated]")
    'edit',          # file path + line range (NOT contents — overlay archive has those)
    'decision',      # agent reasoning summary if available (Claude can emit these)
    'submit',        # auto-emitted on `automil submit` — captures node_id, parent, cell_id
}
```

**Bounding strategy:**
- Cap any single event's serialized size to 8 KB (truncate, mark `truncated=True`).
- Soft cap whole-file at 5 MB; hard cap at 50 MB.
- On hard cap, the recorder writes a `[COMPACTED]` event and rotates: `trajectory.jsonl` → `trajectory.0.jsonl` and starts fresh.
- `trajectory.compaction` post-run pass: keep all `submit`, `decision`, and the **last** `tool_call/tool_result` per tool name; drop intermediate verbose outputs into a `compacted_at` timestamp + count summary. Typical reduction: 50 MB → 200 KB.

**Storage strategy:**
- Default: live in `archive/<node_id>/trajectory.jsonl` alongside `result.json`. Gitignored same as the rest of the archive (per the existing `automil/.gitignore.j2`).
- Optional: `git-lfs track 'trajectory.jsonl'` for projects that DO commit trajectories — not the default. autoMIL doesn't commit archives anyway; trajectory storage parallels archive storage.
- For paper-time release: a `trajectory_release/` flat collection of compacted trajectories per node, separate command (`automil export-trajectories`).

**Where it plugs in:** The CLI `submit` command opens the recorder; subsequent agent actions in the same shell session append. The recorder uses a Stop hook (already present for Claude) to flush + compact on session end. Codex, OpenCode, Gemini CLI: equivalent stop-hook patterns or a `--trajectory <path>` flag if available; otherwise the agent's wrapper writes events explicitly via `automil trajectory record <event>` CLI subcommand.

**Trade-offs:**
- ✅ Reproducibility "as-protocol": the trajectory shows exactly what the agent did, not just the final overlay.
- ✅ Bounded size: hardware-realistic for thousands of nodes.
- ❌ Requires runtime-specific hook integration. Plan B (`automil trajectory record` subcommand) covers runtimes without hooks.
- ❌ Compaction is lossy. Document that — paper-time analyses use the pre-compaction or live trajectory; long-term archive uses compacted.

### Pattern 5: Generalization Gate as a Node-Status Transition (NOT a separate graph)

**What:** A new node `status='candidate'` value sits between `executed/keep` and `registered`. The gate watches the candidate, fires N evaluation jobs across held-out (dataset, encoder) cells, computes per-cell improvement, and only promotes to `registered` if ≥K cells improve by ≥δ.

**When to use:** Whenever a node achieves `keep` AND the search-scope mode is `free` (F2-style). For `architecture-preserving` mode, the gate runs the recipe across the held-out cells but identity preservation is already enforced by the validator chain — the gate ensures the recipe transfers, not just overfits.

**Why a status transition (NOT a separate graph or external pipeline):**
- The existing graph already encodes parent-child topology, scoring, and Pareto. Adding a separate "candidates graph" duplicates state and breaks `reconcile`.
- A new status value is a **minimal** addition — `mark_running`, `promote`, `mark_failed` already exist; `mark_candidate` and `promote_to_registered` slot in.
- Gate-spawned evaluation runs are normal experiment nodes with `cell_id` set to a held-out cell, parent = the candidate. They flow through the same Pareto check and Backend.

**Topology:**

```
[parent variant] (registered)
       │
       ├── [candidate variant] (status=candidate, cell=CCRCC×Virchow2)
       │         │
       │         ├── [eval clone on TCGA-LUAD×UNI2]   (status=running → keep|discard)
       │         ├── [eval clone on TCGA-BRCA×UNI2]   (status=running → keep|discard)
       │         └── [eval clone on CLWD×Virchow2]    (status=running → keep|discard)
       │                                ↓
       │                       gate evaluates: ≥K out of N improved?
       │                                ↓
       │              YES → candidate promoted to registered (registry)
       │              NO  → candidate marked discard with reason='gate_failed'
       │
       └── ... (other candidates)
```

**The gate is a daemon-side concern, not the agent's:** The agent submits, the experiment finishes, reconcile runs, classifies as `candidate` if metrics warrant, and the gate (`gate.GeneralizationGate.tick()`) wakes up on the orchestrator's tick and fires the held-out evaluations. The agent doesn't need to know about the gate — `program.md` just says "winning variants are registered after held-out validation." This keeps the gate composable with single-cell exploration: in `architecture-preserving` mode, the gate is on; in `free` mode, the gate is on; the agent proposes the same way either way.

**Implementation sketch:**

```python
# src/automil/gate/generalization.py
class GeneralizationGate:
    def __init__(self, graph, registry, backend, *, min_cells: int, min_delta: float):
        self.graph, self.registry, self.backend = graph, registry, backend
        self.min_cells, self.min_delta = min_cells, min_delta

    def tick(self) -> None:
        for node in self.graph.nodes_with_status('candidate'):
            children = self.graph.children_of(node['id'])
            eval_children = [c for c in children if c.get('cell_id') != node['cell_id']]

            if len(eval_children) < self.min_cells:
                # Fire missing evaluations
                self._spawn_evaluations(node, eval_children)
                continue

            if any(c['status'] == 'running' for c in eval_children):
                continue   # wait

            improvements = sum(
                1 for c in eval_children
                if c['composite'] >= c['parent_baseline_composite'] + self.min_delta
            )
            if improvements >= self.min_cells:
                self._promote_to_registered(node)
            else:
                self.graph.mark_failed(node['id'], reason='gate_failed')
```

**Where the gate sits in the runtime layout:** Polled by the local backend's daemon tick (so it has zero new long-running processes). Reconcile already runs at the right cadence; gate runs alongside it. CLI `automil reconcile --recompute-best` triggers a one-shot tick.

**Trade-offs:**
- ✅ Reuses graph topology — no new persistence layer, no two-graph drift.
- ✅ Gate-spawned evals are normal experiments — same Pareto, same archive, same reconcile.
- ✅ Bounds search waste: agents can't claim a winner that only works on one cell.
- ❌ Adds N held-out runs per candidate (N=K×~1.5 typical) — costs ~3-5× a single experiment. This is the right trade for variant promotion but should NOT run on every keep — only on candidates the agent or the framework explicitly nominates.
- ❌ Defining the held-out cells is config — config.yaml needs a `gate.held_out_cells: [...]` list. The agent doesn't pick.

---

## 4. Data Flow Updates

### Updated submit path (registry-driven)

```
agent edits VARIANT MODULE (e.g., variants/clam_mb/attention_gated_v2.py)
    └─> agent runs `automil submit --node node_0042 --variant clam_mb.attention.gated_v2 ...`
            │
            ▼
       CLI submit:
         1. registry.get('clam_mb.attention.gated_v2')   [fail fast if not found]
         2. validators.run_chain(spec, mode='free')      [identity check, purity check]
         3. trajectory.recorder.start(node_id)           [opens trajectory.jsonl]
         4. existing snapshot logic (overlay, base_commit, hash)
         5. spec includes new fields: variant_ref, cell_id, mode
         6. backend.submit(spec)
            │
            ▼
       Backend.submit dispatches:
         • LocalBackend → existing daemon path
         • SlurmBackend → render sbatch + sbatch + record JOBID
         • RayBackend → Ray Job Submission SDK
```

### Updated completion path (with gate)

```
training finishes → result.json written
    │
    ▼
backend.poll() detects completion → archive/<id>/result.json present
    │
    ▼
reconcile (existing):
  • Pareto check vs parent
  • status = keep | discard (existing)
    │
    ▼
gate.tick() (NEW):
  • node has variant_ref AND status==keep AND cell_id==search_cell?
       → promote status from `keep` → `candidate`
       → spawn N held-out evaluations (parent=candidate, cell=held_out_i)
  • all held-out evaluations done?
       → count improvements
       → if ≥K: promote candidate → registered (write to registry)
       → else: mark candidate discarded with reason
```

### Updated viz overlay

The viz already overlays `running` from `gpu_state.json`. New status `candidate` and new edge type `gate_eval` (parent=candidate, child=held-out evaluation) are color-coded in `app.js`. Backwards compat: unknown statuses fall back to grey.

---

## 5. Build Order with Rationale

The dependency tree implies this order. Each step is bounded because the previous step nailed down the contract.

| # | Component | Days | Why this order |
|---|-----------|------|----------------|
| 0 | **Tier 2 cleanup** | 1-2 | CONCERNS.md HIGH-severity items: process-group leak, `.automil_worktrees/` gitignore, hardened daemon assertions. These don't depend on the refactor and break the system if left in. Atomic commits. |
| 1 | **`compat.py` shim + CLI split** | 1-2 | Mechanical. Move `cli.py` → `cli/<groups>.py`, add re-exports. Tests stay green. Pre-condition for everything else because new commands (`apply`, `revert-baseline`, etc.) need a place to live. |
| 2 | **Registry layer (`registry/`)** | 2-3 | Stand-alone module — depends only on stdlib. Add unit tests, CLI integration via `submit --variant <name>`. Ships independently of backends. |
| 3 | **Variant migration (CCRCC sanity check)** | 2-3 | Port the CCRCC `node_0176` winning state into actual variant modules. Validates that the registry can express the historical state and reproduces composite within ±0.005. This is the "registry works for real" gate. |
| 4 | **Backend ABC + LocalBackend re-export** | 2-3 | The ABC is small (~100 lines). LocalBackend is mostly mechanical re-export of `orchestrator.py`. **This is the bounding step that makes SLURM cheap.** Tests stay green. |
| 5 | **Trajectory recorder** | 1-2 | Independent of backends. Add to CLI submit; flush via existing Stop hook. Compaction is post-run, so initial impl doesn't need it. |
| 6 | **Multi-runtime asset reorg** | 1-2 | Mechanical move of `claude_assets/` → `agent_assets/_shared/` + `claude/` overrides. Other runtimes (`codex/`, `opencode/`) are stub directories at this stage; populate as users arrive. |
| 7 | **Generalization gate** | 3-4 | Depends on registry (knows variants) AND backend (spawns evals). Most complex new logic. Reuses graph topology. Test with mocked backend. |
| 8 | **6h per-cell hard cap** | 1-2 | Lives in backend.tick (or daemon); independent module. Adds wall-clock tracking per cell. Defers to gate for whether to discard or just stop spawning. |
| 9 | **SLURM backend** | 3-4 | Now bounded. Render sbatch from spec, poll squeue, copy logs to archive. Submitit reference impl available. |
| 10 | **Ray backend** | 3-4 | Now bounded. Ray Job Submission SDK. |
| 11 | **`/automil-setup` skill (autonomous bootstrap)** | 2-3 | Heavy use of registry + backend abstraction — ships only after they're proven. Idempotent inspect-and-scaffold. |
| 12 | **Hardware auto-detection** | 1 | Lives in `LocalBackend.healthcheck()`; informs `init` defaults. Trivial after the abstraction. |
| 13 | **Reproduction sanity check** | 1 | Run CCRCC `node_0176` on the new path. Measure composite drift. PASS = milestone done. |

**Why backend ABC before SLURM impl (step 4 before step 9):** Without the ABC, SLURM means writing a parallel orchestrator from scratch, with two divergent code paths. The proposal called this out at "5-7 days for engineering" with that risk. With the ABC, SLURM is bounded to "render sbatch + poll squeue" — a 3-4 day implementation against a clear contract.

**Why registry before gate (step 2 before step 7):** The gate operates on registered variants; without a registry, the gate has no input.

**Why variant migration before backend (step 3 before step 4):** The reproduction sanity check (step 13) is the milestone exit criterion. If the registry-only migration doesn't reproduce CCRCC, we found a bug before complicating with backends.

**Why trajectory before gate (step 5 before step 7):** The gate fires evaluation experiments; those experiments must capture trajectories. Adding trajectory after the gate means re-doing the gate's eval-spawn path.

---

## 6. Backwards-Compatibility Path

| Stays as-is | Re-exported via `compat.py` | Deprecated (warn but functional) | Removed |
|-------------|-----------------------------|----------------------------------|---------|
| `automil` CLI entry point | `from automil.graph import ExperimentGraph` (→ `automil.core.graph`) | `automil.claude_assets` import path (→ warn, point to `agent_assets._shared`) | None in v0.2.x |
| Existing CLI commands (init, submit, propose, rank, reconcile, status, check) | `from automil.runner import Runner` (→ `automil.core.runner`) | Direct edits to shared library files (CONCERNS pattern) — submit warns | Direct `args.X = literal` overrides — `automil check` warns; later release errors |
| `automil/config.yaml` schema (extended, not changed) | `from automil.orchestrator import ExperimentOrchestrator` (→ `automil.backends.local.LocalBackend._daemon`) | | |
| All 48 existing tests | | | |
| `result.json` contract | | | |
| `archive/<id>/{spec,result,run.log}` layout | | | |
| `graph.json` schema (additive: new fields with defaults) | | | |

**Migration checklist for users:**
1. `pip install -U automil` — installs new layout.
2. `cd <project>`; `automil refresh-registry` — generates `variants/__init__.py` if `variants/` exists.
3. `automil check --strict` — flags any remaining `args.X = literal` overrides as errors.
4. Existing graph.json reads cleanly; new fields default to `None`.
5. `automil reconcile --recompute-best` — recomputes scores under new logic.

---

## 7. Patterns Adopted vs Patterns Rejected

### Adopted (with rationale)

| Pattern | Why adopted |
|---------|-------------|
| **Explicit-import variant registry (timm-style)** | Mature, batteries-included reference. timm has 1000+ models behind this exact pattern. Composes cleanly with existing graph/CLI. |
| **TorchX-shaped Backend ABC** | Lowest common denominator across local / SLURM / Ray. Avoids reinventing job-scheduling abstractions. |
| **Universal SKILL.md + per-runtime overrides** | Agent Skills is a real cross-runtime standard. Shared content stays in sync; per-runtime diff is small. |
| **JSONL trajectory + compaction** | De facto agent-trace format. Append-only is crash-safe. Compaction bounds long-tail size. |
| **Gate-as-status-transition** | Reuses existing graph topology. No two-graph drift. Eval children are normal experiments. |
| **CLI split by command group** | 726-line cli.py is past ergonomic. Trivial mechanical split, low risk. |

### Rejected (with rationale)

| Pattern | Why rejected |
|---------|-------------|
| **Metaclass-based auto-registering plugins** | "Magic" registration depends on imports running. timm itself doesn't use a metaclass; it uses decorators + explicit `__init__.py` lists. Explicit > implicit, especially when the agent writes the module. |
| **`pkgutil.walk_packages` auto-discovery** | Same problem. Variant modules don't run their decorator unless imported. Forces import-just-for-side-effects pattern that breaks isolation. |
| **Hydra `_target_` for variants** | Adds a new dependency for a problem the registry already solves. Hydra is a config tool, not a registry. autoMIL config stays YAML-flat — no dotpath instantiation. |
| **Submitit as the only backend abstraction** | Excellent for SLURM, doesn't generalize. Ray and local have totally different shapes. TorchX's abstraction is wider. (We can use submitit *inside* SlurmBackend — submitit is the impl, not the abstraction.) |
| **Snakemake / Nextflow / Airflow as the orchestrator** | Workflow engines, not job schedulers. Wrong altitude — they orchestrate DAGs of tasks; autoMIL's "DAG" is the experiment graph, which is not Snakemake's data model. |
| **Per-runtime full Jinja templates for skill assets** | 5x duplication of identical content; review burden compounds; bug fixes apply 5 times. _shared+overrides keeps DRY. |
| **Flat `agent_assets/` with mixed runtime files** | No clear "what ships where" boundary. Adding a runtime is brittle. |
| **Separate `candidates/` graph alongside `graph.json`** | Two graphs drift. Reconcile becomes 2× as hard. The status-transition pattern is strictly less code. |
| **External validation pipeline (separate process / DAG)** | Held-out evaluation IS just another experiment. Spawning it through the same Backend.submit keeps GPU bin-packing, env propagation, and result collection consistent. No reason to externalize. |
| **Raw transcript dump (one big JSON per run)** | Crash-unsafe — partial writes corrupt; can't truncate per-event; tools assume JSONL. |
| **Git LFS by default for trajectories** | Trajectories are gitignored runtime state, like the rest of `archive/`. LFS is opt-in for projects that DO commit them. |
| **Replace `concurrent.futures.Executor` with custom abstraction** | The Backend ABC is wider (job lifecycle, logs, cancellation) than Executor (just submit/result). Don't conflate. |

---

## 8. Anti-Patterns to Avoid (New, beyond CONCERNS.md)

### Anti-Pattern: Variant module mutates shared state

**What people do:** Variant module's factory mutates `args.X` or imports and patches a shared library function.

**Why it's wrong:** Defeats the entire registry: the variant is no longer self-contained. Same cross-dataset contamination root cause autoMIL is fixing.

**Do this instead:** Variant factory returns a fresh, fully-constructed object (model / loss / optimizer-builder). No reach into shared state. Validators in `registry/validators/purity.py` enforce this by AST inspection (forbid `import benchmarks.lib.CLAM.utils.core_utils` from variant modules).

### Anti-Pattern: Backend implementations sharing state files

**What people do:** SlurmBackend writes to `running/<id>.json`; LocalBackend ALSO writes to `running/<id>.json`; both daemons running concurrently corrupt each other.

**Why it's wrong:** The path is shared but ownership is single-writer.

**Do this instead:** Each backend owns its own subdirectory: `running/local/<id>.json`, `running/slurm/<id>.json`. Reconcile reads all backends' running dirs.

### Anti-Pattern: Trajectory recorder runs synchronously inside training

**What people do:** Add `trajectory.record(...)` calls inside the training loop.

**Why it's wrong:** Couples training to trajectory infra. Different runtimes, different recording semantics. Slows training.

**Do this instead:** Trajectory is an **agent-side** concern. The training script writes `result.json` only; the recorder is part of the CLI / agent harness.

### Anti-Pattern: Gate fires on every `keep` automatically

**What people do:** Every keep promotes to candidate, fires N held-out evaluations.

**Why it's wrong:** N=4-6 held-out evals × every keep = 5-7× compute waste on hyperparameter sweeps that don't merit promotion.

**Do this instead:** Gate fires ONLY when the agent (or `automil promote-variant <node>`) explicitly nominates the node OR the framework's auto-nomination criterion fires (config-driven: `gate.auto_nominate.composite_threshold`). Default: manual nomination only.

### Anti-Pattern: Per-runtime SKILL.md files diverge over time

**What people do:** Edit `agent_assets/claude/SKILL.md` directly, not `_shared/SKILL.md`.

**Why it's wrong:** _shared and claude/SKILL.md drift apart; bug fixes apply to one and not the other.

**Do this instead:** `_shared/` is the source of truth. `<runtime>/overrides/` is **diff-only** with explicit `_extends`. `automil show-skill --runtime claude` debug command renders the merged result.

---

## 9. Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| SLURM controller | `sbatch` / `squeue` / `scancel` shell-out from SlurmBackend | Submitit available as impl backbone; native shell-out works for small clusters |
| Ray cluster | Ray Job Submission SDK (HTTP) | Requires Ray version pinning; client lives in RayBackend |
| Git (worktree) | Existing — unchanged | Runner stays in `core/`, used by all backends |
| `nvidia-smi` | Existing — only LocalBackend uses | SlurmBackend trusts `--gres=gpu:N`; RayBackend uses Ray's resource API |
| Agent runtimes | Stop hook (Claude) / `AGENTS.md` (Codex) / equivalent (others) | Recorder integration via runtime-native hook |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI ↔ Registry | Direct Python imports (registry is stdlib) | `automil.registry.get(name)` |
| CLI ↔ Backend | Direct Python imports + spec dict | `automil.backends.get_backend(cfg).submit(spec)` |
| Backend ↔ Daemon (Local only) | Shared filesystem (existing) | `automil/orchestrator/{queue,running,completed}/` |
| Daemon ↔ Gate | In-process call on tick | `gate.tick()` invoked from `LocalBackend._daemon.tick()` |
| Gate ↔ Backend | Spawns evals via `backend.submit(spec)` | Same path as agent submits |
| CLI ↔ Recorder | `trajectory.recorder.open(node_id)` returns file handle | Recorder also has its own CLI subcommand for runtimes without hooks |
| Recorder ↔ Compaction | Post-run, in-process (no daemon) | Triggered by Stop hook or `automil compact-trajectory <node>` |

### Backwards-Compat Boundaries

| Boundary | Mechanism | Removal target |
|----------|-----------|----------------|
| Old `automil.graph` import path | `compat.py` re-export | Never (re-export is cheap; users will hit it) |
| Old `automil.orchestrator` import | `compat.py` re-export with `DeprecationWarning` | v0.4.x |
| `claude_assets/` directory | Symlinked alias to `agent_assets/_shared/` + `claude/` | v0.4.x |
| Direct edits to shared library files | `automil submit` emits warning; `automil check --strict` errors | Hardening to error in v0.3.x |

---

## 10. Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user, 1 machine, ~200 nodes | Current local-only path. No changes. |
| 1 user, 1 machine, ~10k nodes | Build parent→children index in graph (CONCERNS.md item — already known). Compact trajectories. |
| Small team (3-5), 1 cluster, ~50k nodes | SLURM backend lands. Per-user namespace under `archive/`. Trajectory storage moves to LFS or S3. |
| Multi-team, multi-cluster, ~500k+ | Ray backend. Centralize result collection (S3); graph stays per-project. Compaction critical. |

### Scaling Priorities

1. **First bottleneck — graph.json read time and `recalculate_scores` O(N²).** Already known (CONCERNS.md). Build parent→children index (1 day refactor). Hits at ~1k nodes.
2. **Second bottleneck — trajectory archive size.** Compaction is the answer. Hits at ~5k nodes if compaction not run.
3. **Third bottleneck — single LocalBackend daemon polling.** SLURM/Ray distribute the polling — won't hit until single-machine saturates fully.

---

## 11. Risks and Open Questions

| Risk | Mitigation |
|------|------------|
| Registry validator chain too strict — agent can't make legitimate edits | Run validators in `--mode=free` permissively at first; tighten in `architecture-preserving` mode only after F1 grid runs. |
| Gate adds 5x compute per nomination — search becomes slower | Manual nomination by default; auto-nomination thresholds are config. Default config has gate enabled but auto-nominate disabled. |
| Backend log unification fragile across SLURM / Ray | Pin contract: `log_iter` MUST yield bytes-or-str equivalent of run.log; on completion, copy into `archive/<id>/run.log` for unified consumers. |
| Trajectory hooks don't exist for some runtimes | Plan B: `automil trajectory record <event>` CLI subcommand; runtime wraps tool calls explicitly. |
| Variant module pattern doesn't fit all mutation kinds (e.g., changing `forward()` paradigmatically) | F2 explicitly allows `forward()` mods — variant module is a wholesale module replacement, not a sub-class graft. The registry's `kind` field disambiguates. |

### Open Questions for Roadmap Phase Decisions

1. **Mode default**: ship with `architecture-preserving` as the F1 default? Or `free` as the F2 default? Likely `free` with an opt-in stricter validator chain.
2. **Gate's "K cells" default**: K=3 of 5 held-out cells? K=2 of 4? Defaults need pilot data.
3. **Codex / OpenCode hook integration**: do these runtimes have native equivalents to Claude's `Stop` hook, or do we use the CLI-subcommand fallback? Needs runtime-by-runtime check during multi-runtime phase.
4. **Trajectory schema evolution**: lock schema in v1, or version it? Recommend versioning (`{schema_version: 1}` per file).

---

## Sources

- [Codebase Architecture Map (existing autoMIL)](file:///home/jma/Documents/yinshuol/autoMIL/.planning/codebase/ARCHITECTURE.md)
- [Codebase Concerns Map (existing autoMIL)](file:///home/jma/Documents/yinshuol/autoMIL/.planning/codebase/CONCERNS.md)
- [F2 Proposal](file:///home/jma/Documents/yinshuol/autoMIL/tasks/automil_proposal.md)
- [TorchX Schedulers Documentation](https://meta-pytorch.org/torchx/main/schedulers.html)
- [TorchX Slurm Scheduler](https://meta-pytorch.org/torchx/0.1.0rc1/schedulers/slurm.html)
- [TorchX Ray Scheduler](https://meta-pytorch.org/torchx/latest/schedulers/ray.html)
- [Submitit (Meta) — SLURM Python toolbox](https://github.com/facebookincubator/submitit)
- [Hydra `instantiate` Documentation](https://hydra.cc/docs/advanced/instantiate_objects/overview/)
- [timm registry source](https://github.com/huggingface/pytorch-image-models/blob/main/timm/models/_registry.py)
- [timm `create_model` documentation](https://timm.fast.ai/create_model)
- [OpenEvolve / AlphaEvolve architecture](https://github.com/algorithmicsuperintelligence/openevolve)
- [Awesome Agent Skills (cross-runtime SKILL.md ecosystem)](https://github.com/VoltAgent/awesome-agent-skills)
- [Anthropic Claude Code Skills documentation](https://code.claude.com/docs/en/skills)
- [OpenAI Codex Agent Skills documentation](https://developers.openai.com/codex/skills)
- [Python Registry Pattern (decorator-based, explicit imports)](https://dev.to/dentedlogic/stop-writing-giant-if-else-chains-master-the-python-registry-pattern-ldm)
- [Decorated Plugins — explicit-import discussion](https://kaleidoescape.github.io/decorated-plugins/)
- [SWE-bench (trajectory format reference for JSONL agent traces)](https://www.swebench.com/)
- [Ray on SLURM Deployment Guide](https://docs.ray.io/en/latest/cluster/vms/user-guides/community/slurm.html)
- [Reducing Cost of LLM Agents with Trajectory Reduction (arXiv 2509.23586)](https://arxiv.org/abs/2509.23586)
- [Snakemake SLURM Executor Plugin](https://snakemake.github.io/snakemake-plugin-catalog/plugins/executor/slurm.html)
- [LangSmith trajectory evaluations](https://docs.langchain.com/langsmith/trajectory-evals)
- [Better Harness: Hill-Climbing with Evals (LangChain blog)](https://blog.langchain.com/better-harness-a-recipe-for-harness-hill-climbing-with-evals/)

---
*Architecture research for: autoMIL framework refactor (subsequent milestone, brownfield)*
*Researched: 2026-04-30*
