# Stack Research — F2-Readiness Refactor

**Domain:** Brownfield framework refactor adding (a) variant registry, (b) pluggable orchestrator backends (local/SLURM/Ray), (c) multi-runtime agent harnesses, (d) per-cell wall-clock cap, (e) trajectory instrumentation, (f) generalization gate, (g) autobench decoupling.
**Researched:** 2026-05-01
**Confidence:** HIGH for SLURM/Ray/agent-harness formats; MEDIUM for telemetry serialization (multiple credible options, no clear winner); HIGH for plugin patterns.
**Scope discipline:** This document recommends ONLY new stack for the new components listed above. The existing autoMIL stack (Python 3.10+, Click, aiohttp, watchdog, jinja2, pyyaml, hatchling, uv workspace, vendored d3/three frontend) is **locked** per `.planning/codebase/STACK.md` — do not re-litigate.

---

## Recommended Stack

### Core Technologies (NEW components only)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python `entry_points` (setuptools/PEP 621) + light internal registry** | stdlib + already pulled in | Variant registry: model / loss / training-policy modules registered by name | Zero new deps. Already used by every Python plugin system worth naming (pytest, conda, jupyter). Variant modules can self-register either via `[project.entry-points."automil.variants"]` in `pyproject.toml` (for cross-project sharing) **or** a thin module-decorator pattern (`@register("clam.attn_v2")`) for in-tree variants. Don't reach for `pluggy` — we have no need for hookspec arity checks across plugins; a one-page `Registry` class is simpler. |
| **submitit** | 1.5.3 (Dec 2025 release; actively maintained, 1,586 stars) | SLURM backend: submit Python callables as sbatch jobs, poll status, collect results | Industry standard from FAIR. `concurrent.futures`-shaped API (`AutoExecutor`, `Job.result()`), supports preemption/requeue, captures stdout/stderr, Python-native (no shell-script generation). Drop-in replacement for `subprocess.Popen` in `orchestrator.py:374` while keeping the existing best-fit-bin-pack outer loop intact. |
| **ray[default] + ray.tune (optional)** | 2.55.1 (April 2026; supports Python 3.10–3.14) | Ray backend: distributed actor execution across heterogeneous clusters (k8s, GCP, AWS) | The only mature Python-native option for "single laptop → multi-node cloud" without writing two orchestrators. We use **`ray.remote`** for execution + **placement groups** for GPU reservation. We do NOT use `ray.tune` for scheduling — autoMIL's experiment graph already does UCB / Pareto, and `tune.Tuner` would force a foreign trial-state model. Ray is the *executor*, not the *search controller*. |
| **AGENTS.md (open standard, Linux Foundation)** | spec v1, governed by Agentic AI Foundation as of 2025 | Universal "instructions for coding agents" file | 25+ tools support it (Codex, Cursor, Copilot, Aider, opencode, goose, Zed, Windsurf, Junie, Gemini CLI, Factory, …). Plain markdown, no frontmatter. **Use as the *common substrate*** for runtime-agnostic project instructions — every supported runtime reads it. |
| **Per-runtime skill scaffolding** (Claude `SKILL.md` + opencode `agents/*.md` + Codex AGENTS.md, see §Multi-Runtime) | n/a (file-format spec) | Runtime-specific overlays for invocable workflows on top of AGENTS.md | Each runtime has its own format. AGENTS.md alone gives you "Claude reads this to understand the project"; runtime-specific skills give you "the agent can invoke `/automil-setup`." We need both. |
| **OpenTelemetry GenAI semantic conventions (`gen_ai.*` attrs)** | semconv current spec (active development, GA-bound late 2026) | Trajectory schema: span/event names + attribute keys for prompts, tool calls, completions | Vendor-neutral. Datadog, Phoenix/Arize, Traceloop, Honeycomb, OneUptime all map to it. Choosing OTel semconv now means Leo's `trajectory.jsonl` files can be replayed/diffed by any OTel-aware tool later — including LangSmith, Phoenix, AgentOps. We do NOT add `opentelemetry-sdk` as a runtime dep; we just emit the **field names** they use. |
| **JSONL one-step-per-line trajectory format** | n/a (convention) | Per-submit `archive/<node_id>/trajectory.jsonl` | SWE-agent, OpenHands, SWE-Gym, Nebius SWE-rebench all use JSONL-per-step. Append-friendly, grep-able, no schema migration when fields are added. Each line = one tool call or one LLM message; `gen_ai.*` keys for content. |
| **subprocess + signal escalation (SIGTERM → grace → SIGKILL), per-process-group** | stdlib | Wall-clock budget enforcement | Already implemented at the *experiment* level in `orchestrator.py:578-587`. We need the same pattern at the *cell* level: a `cell_budget.py` watcher that the orchestrator consults each tick. SLURM does the same (`scancel` → `KillWait` 30s → SIGKILL); we mirror this for portability across backends. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **submitit** | 1.5.3 | SLURM backend | Required only when `orchestrator.backend: slurm` in `automil/config.yaml`. Lazy-imported inside `backends/slurm.py`. |
| **ray** | 2.55.1 (extras: `ray[default]` for dashboard; bare `ray` for runtime only) | Ray backend | Required only when `orchestrator.backend: ray`. Lazy-imported inside `backends/ray.py`. Bare install ≈ 60 MB; full install ≈ 400 MB. Use bare install in autoMIL's pyproject `[project.optional-dependencies].ray`. |
| **psutil** | 7.0+ | Cross-platform process tree introspection (alternative to `os.killpg` on edge cases); peak-VRAM/CPU sampling | Already a transitive dep via TRIDENT/`nvidia-ml-py`. Worth promoting to direct for the budget-enforcement watcher and graceful tree-kill on backends that don't expose `setsid`. |
| **filelock** | 3.16+ | Atomic state mutations from multiple writers (Ray drivers, SLURM array tasks) | Needed when Ray/SLURM workers may write `running/<id>.json` concurrently. Stdlib `os.rename` atomicity (already used at `graph.py:740-754`) plus `filelock` for compare-and-swap on the cell-budget counter file. |
| **pydantic v2** | 2.9+ | Schema validation for spec.json, result.json, trajectory.jsonl entries, variant manifest | Optional but worth adding. Variant registry needs typed manifests (`base_class`, `parent_module`, `mutation_dimension`) and pydantic gives error messages humans (and agents) can act on. v2 is fast enough that schema-checking every tool-call line in trajectory.jsonl is fine. **Caveat:** Ray < 2.56 still pulls pydantic v1; v2 coexistence works in practice. |
| **rich** | 13.7+ | Pretty progress / status output for `automil status` and the new `automil cell budget` command | Already a transitive dep via Click 8.3 (no, Click does NOT depend on rich — bring it in deliberately). Strictly UX polish; not load-bearing. |
| **python-dotenv** | (already pulled in by autobench) | `.env` propagation to SLURM/Ray workers | Same pattern as today's `_load_dotenv()` in `orchestrator.py:222`; ensure SLURM `--export=ALL` and Ray runtime env carry the loaded vars. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **pytest** (already in stack) | Test runner | New backends each get their own marker (`@pytest.mark.slurm`, `@pytest.mark.ray`) and skip when the backend isn't installed. |
| **respx / pytest-httpserver** | Mock LLM API endpoints during trajectory-instrumentation tests | We won't ship LLM clients in the framework, but the trajectory recorder needs to be exercised against fixture data. |
| **mypy or pyright (strict)** | Type-check the new ABCs (`Backend`, `Variant`, `BudgetEnforcer`, `TrajectoryRecorder`) | Critical for the registry: a typo in a `register()` call should fail at type-check time, not at experiment-launch time. |
| **ruff 0.7+** (already in stack via dev) | Lint new code | Required, no exceptions. Set `select = ["E","F","I","B","UP","SIM","RUF"]` for the new modules. |

---

## Multi-Runtime Agent Harness — Per-Runtime Format Reference

This is the load-bearing section: F2's reviewer-defense story is "the framework runs across runtimes." Each runtime has a *different* skill format. Reorganization target: `agent_assets/{claude,codex,opencode,deepseek,...}/` with `automil init --runtime=X` selecting one (with autodetect).

### Common substrate: `AGENTS.md` (project root)

- **Format:** Plain Markdown, no frontmatter, no required sections.
- **Location:** repo root (`AGENTS.md`); nested per-package files override (closest-wins).
- **Purpose:** "README for agents" — project setup, build/test commands, code style, security boundaries.
- **Read by:** OpenAI Codex, GitHub Copilot, Cursor, Aider, opencode, Zed, Warp, Devin, Junie, Amp, Factory, Gemini CLI, Kilo Code, Phoenix, Windsurf, Augment Code, RooCode, Ona — and Claude Code reads it as fallback context.
- **Governance:** Linux Foundation (Agentic AI Foundation) as of 2025. Spec at <https://agents.md>.
- **autoMIL plan:** `automil init` writes a project-root `AGENTS.md` describing the framework's CLI surface (`submit`, `propose`, `reconcile`, etc.) and `result.json` contract. This is the *one file every runtime sees*.

### Runtime: Claude Code → `.claude/skills/<skill-name>/SKILL.md`

- **Format:** YAML frontmatter (between `---` markers) + Markdown body. **`description` is the only field Claude needs to decide whether to invoke.**
- **Locations (precedence: enterprise > personal > project):**
  - Personal: `~/.claude/skills/<skill-name>/SKILL.md`
  - Project: `.claude/skills/<skill-name>/SKILL.md`
  - Plugin: `<plugin>/skills/<skill-name>/SKILL.md`
- **Key frontmatter fields:**
  - `description` (recommended; 1,536 char cap including `when_to_use`)
  - `name` (defaults to dir name)
  - `disable-model-invocation: true` for skills only the user should trigger (e.g. `/automil-setup`)
  - `allowed-tools` for tool-permission preapproval (`Bash(automil *)`)
  - `context: fork` + `agent: Explore|Plan|general-purpose` to run in a forked subagent
  - `paths` glob to auto-activate when editing matching files
- **Conformance with Agent Skills open standard:** Claude Code declares conformance + extensions (invocation control, fork, dynamic `!\`cmd\`` injection).
- **autoMIL plan:** Migrate today's `src/automil/claude_assets/skills/automil/SKILL.md` to be the canonical Claude pack: `automil-setup`, `automil-propose`, `automil-reconcile`, etc. Skills under `agent_assets/claude/skills/`.

### Runtime: OpenAI Codex → `AGENTS.md` + `~/.codex/config.toml`

- **Format:** AGENTS.md (above), with optional `AGENTS.override.md` for local overrides. **No frontmatter; no special structure.**
- **Discovery chain (Codex builds at session start):**
  1. Global: `~/.codex/AGENTS.override.md` || `~/.codex/AGENTS.md`
  2. Project: `<repo-root>/AGENTS.override.md` || `<repo-root>/AGENTS.md`
  3. Closest-to-edited-file file wins
  4. Optional: fallback filenames via `~/.codex/config.toml` → `project_doc_fallback_filenames`
- **Skills (separate from AGENTS.md):** Codex has a parallel "Agent Skills" surface documented at <https://developers.openai.com/codex/skills>; format is *not* yet as widely adopted as Claude's SKILL.md. For autoMIL v1, treat AGENTS.md as the integration point and emit a Codex-friendly `AGENTS.md` (build/test/run/CLI sections); add Codex skill files only if/when their format stabilizes.
- **autoMIL plan:** `agent_assets/codex/AGENTS.md` template that gets written to repo root by `automil init --runtime=codex`. CLI invocation lives entirely inside that markdown's "Workflow" section.

### Runtime: opencode → `.opencode/agents/<name>.md` + `.opencode/skills/<name>/SKILL.md`

- **Two surfaces, both Markdown + YAML frontmatter:**

  **Agents** (specialized assistants — primary or subagent):
  - Locations: `~/.config/opencode/agents/` or `.opencode/agents/<name>.md`
  - Filename = agent name (e.g., `review.md` → `review` agent)
  - Frontmatter:
    ```yaml
    ---
    description: Agent purpose
    mode: subagent          # or "primary"
    model: anthropic/claude-sonnet-4-20250514
    temperature: 0.1
    permission:
      edit: deny
      bash: deny
    ---
    You are [role]. Focus on [specific tasks].
    ```

  **Skills** (reusable behaviors — same Open Skills standard as Claude):
  - Locations: `~/.config/opencode/skills/<name>/SKILL.md` or `.opencode/skills/<name>/SKILL.md`
  - Format = same SKILL.md spec (frontmatter + body)
- **autoMIL plan:** Ship both — one opencode `agent` for "the autoMIL operator" and a set of skills mirroring Claude's. `agent_assets/opencode/{agents,skills}/`.

### Runtime: DeepSeek (V4 + V4-Pro) — *no native harness; route via OpenAI-compatible client*

- DeepSeek does not ship its own coding-agent harness. Its OpenAI-ChatCompletions-compatible API (and Anthropic-compatible API as of V4) means it's used as a **backend model** inside Claude Code, opencode, Cursor, Continue.dev, Aider (via LiteLLM), Cline, Roo Code, etc.
- **Practical implication:** "DeepSeek support" in autoMIL means: (1) document the DeepSeek-via-opencode and DeepSeek-via-Claude-Code paths in `agent_assets/deepseek/README.md`; (2) ensure the framework doesn't assume Anthropic-specific tool-call IDs in trajectory recording.
- **autoMIL plan:** `agent_assets/deepseek/` is a thin pointer doc, not its own skill set. The runtime is whichever harness routes to DeepSeek.

### Runtime detection (for `automil init`)

Probe order (first hit wins, prompt user if multiple):
1. `$CLAUDE_CODE_AGENT_TYPE` set OR `~/.claude/` exists OR `.claude/` in repo → Claude
2. `~/.codex/` exists OR `$CODEX_HOME` set → Codex
3. `.opencode/` in repo OR `~/.config/opencode/` exists → opencode
4. None of the above → install AGENTS.md + Claude pack as default; print runtime instructions

---

## Trajectory Instrumentation

### Format: JSONL, one event per line, OTel `gen_ai.*` field names

Path: `automil/orchestrator/archive/<node_id>/trajectory.jsonl`. One file per submit. Append-only.

**Per-line schema (subset of OTel GenAI semconv `gen_ai.*` event/span attributes):**

```jsonl
{"ts": "2026-05-01T14:23:11.123Z", "kind": "session_start", "node_id": "node_0177", "runtime": "claude_code", "gen_ai.system": "anthropic", "gen_ai.request.model": "claude-opus-4-7-20260301"}
{"ts": "...", "kind": "user_message", "gen_ai.input.messages": [{"role":"user","content":"propose ..."}]}
{"ts": "...", "kind": "tool_call", "gen_ai.tool.name": "Bash", "gen_ai.tool.call.id": "tooluse_01abc", "gen_ai.tool.call.arguments": "{...}"}
{"ts": "...", "kind": "tool_result", "gen_ai.tool.call.id": "tooluse_01abc", "gen_ai.output.tool_call.result": "..."}
{"ts": "...", "kind": "completion", "gen_ai.usage.input_tokens": 12345, "gen_ai.usage.output_tokens": 678, "gen_ai.response.finish_reasons": ["stop"]}
{"ts": "...", "kind": "session_end", "node_id": "node_0177", "result": "submitted"}
```

**Why JSONL over a single JSON document:**
- Append-only writes are crash-safe (no partial-write corruption of the whole trajectory).
- `tail -f` works in real-time; agents can stream their own trace.
- Standard for SWE-agent, OpenHands, SWE-Gym, Nebius SWE-rebench, Hermes Agent — Leo's `trajectory.jsonl` will be loadable by every "agent trajectory analyzer" tool published in the next 12 months.

**Why OTel `gen_ai.*` keys over a custom schema:**
- Vendor-neutral; replayable into Phoenix/Arize, LangSmith, Datadog LLM Observability, OneUptime, Honeycomb later without renaming fields.
- Spec is in active development but the `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.*`, `gen_ai.tool.call.*` keys are stable.
- We are NOT pulling in `opentelemetry-sdk` (would force OTLP exporters, collectors, infra). We just adopt the *names*.

**Recorder integration per runtime:**
- **Claude Code:** Stop hook (`.claude/hooks/on_stop.sh`, already exists per `claude_assets/hooks/`) writes `session_end`; tool-use events captured via post-tool hooks (Claude Code documents these in `/en/hooks`).
- **Codex / opencode / others:** Per-runtime adapter under `agent_assets/<runtime>/trajectory_recorder.{sh,py}`. Each adapter normalizes that runtime's tool-call log format to the `gen_ai.*` schema.

---

## Pluggable Orchestrator Backends

### Interface (`src/automil/backends/base.py`)

```python
class Backend(ABC):
    name: str  # "local" | "slurm" | "ray"

    @abstractmethod
    def can_schedule(self, spec: Spec) -> bool: ...
    @abstractmethod
    def launch(self, spec: Spec, env: dict[str, str]) -> Handle: ...
    @abstractmethod
    def poll(self, handle: Handle) -> Status: ...  # running | completed | failed | timeout
    @abstractmethod
    def kill(self, handle: Handle, grace_sec: int = 30) -> None: ...
    @abstractmethod
    def collect(self, handle: Handle) -> Result: ...
```

### `LocalBackend` (default; wraps current code)

- Wraps existing `Runner.create_worktree` + `subprocess.Popen` flow.
- The current `tick()` loop in `orchestrator.py:676-699` becomes `LocalBackend.poll()`-driven.
- **Migration path:** keep `local` as default; existing tests pass unchanged.

### `SlurmBackend` (uses `submitit`)

- `submitit.AutoExecutor(folder="automil/orchestrator/slurm/<node_id>/")` per submit.
- Translates `spec.estimated_vram_gb` and `spec.timeout_min` to `--gres=gpu:1`, `--time`, `--mem`.
- `executor.submit(fn, spec)` returns a `Job`; `Job.state` polls `squeue`; `Job.result()` collects.
- Wall-clock cap: pass `--time=$((cell_budget_remaining))` so SLURM hard-kills if framework misses it; framework also kills proactively at cap-30s.
- `submitit` handles preempt/requeue out of the box (advanced; opt-in via config).
- **Why `submitit` over `simple_slurm`/`slurmpy`/`pysbatch`:** submitit is the only one with (a) Job-future API matching `concurrent.futures`, (b) FAIR-grade production track record, (c) checkpoint-on-preempt, (d) actively maintained (1.5.3 in Dec 2025). The others are thin sbatch shellouts.

### `RayBackend` (uses `ray.remote` + placement groups)

- `ray.init(address="auto")` for cluster mode; `ray.init()` for local.
- Each spec is an `@ray.remote(num_gpus=1, resources={"vram_gb": vram})` task wrapping the same training entrypoint.
- Placement group reserves GPUs; `ray.get(future, timeout=cell_budget_remaining)` enforces wall clock.
- **NOT using `ray.tune`:** Tune's `Trial`/`Tuner` model would conflict with autoMIL's experiment graph. Use Ray as raw distributed execution only.
- Ray dashboard (`ray[default]`) is optional — useful when debugging multi-node, off by default.

### Backend selection (`automil/config.yaml`)

```yaml
orchestrator:
  backend: local        # local | slurm | ray
  slurm:
    partition: gpu
    qos: normal
    account: leo
  ray:
    address: auto       # or "ray://head:10001"
    namespace: automil
```

---

## Variant Registry Pattern

### Decision: thin internal registry + entry_points for cross-project sharing

```python
# src/automil/registry.py
class Registry:
    def __init__(self): self._entries: dict[str, type] = {}
    def register(self, name: str):
        def deco(cls):
            if name in self._entries:
                raise ValueError(f"variant '{name}' already registered")
            self._entries[name] = cls
            return cls
        return deco
    def get(self, name: str) -> type:
        if name not in self._entries:
            self._discover_entry_points()  # lazy
        return self._entries[name]
    def _discover_entry_points(self):
        from importlib.metadata import entry_points
        for ep in entry_points(group="automil.variants"):
            self._entries[ep.name] = ep.load()

models = Registry(); losses = Registry(); training_policies = Registry()
```

**Variant module example** (`benchmarks/lib/CLAM/variants/clam_attn_v2.py`):

```python
from automil.registry import models
from CLAM.models.model_clam import CLAM_MB

@models.register("clam_mb.attn_v2")
class CLAM_MB_AttnV2(CLAM_MB):
    """Variant: gated attention with rank-reduction. Parent: CLAM_MB."""
    def forward(self, h, ...):
        ...
```

**Config selects variant by name:**
```yaml
model:
  name: clam_mb.attn_v2     # registry lookup
  args:
    n_classes: 2
    dropout: 0.25
```

### Why NOT pluggy / Hydra-zen / Dishka

| Option | Why not |
|--------|---------|
| **pluggy** | Designed for hookspec/hookimpl pattern (one event, many listeners). Variants are not hooks; they're alternatives. Wrong shape. |
| **Hydra-zen** | Pulls in Hydra's full config system (hydra-core, OmegaConf, dataclass plugins). autoMIL already uses pyyaml + jinja2 templates and has its own config-merge logic in `autobench/config.py`. Adopting Hydra would force a rewrite of all dataset YAMLs. |
| **Dishka** | DI container. Solves a different problem (lifecycle management of N coupled services). Variants are stateless callables. |
| **stevedore** | OpenStack's plugin loader. Heavier than `entry_points` for the same job. |

### Cross-dataset sharing via entry_points

When `autobench` declares in `benchmarks/pyproject.toml`:
```toml
[project.entry-points."automil.variants"]
"clam_mb.attn_v2" = "autobench.variants.clam_attn_v2:CLAM_MB_AttnV2"
```
…then any project that has `autobench` installed sees the variant. This is the path for "promote winning variant from CCRCC into the cross-dataset library."

---

## Wall-Clock Budget Enforcement

### Pattern: per-cell counter file + tick-time check + signal escalation

State file: `automil/orchestrator/cells/<dataset>__<encoder>__<parent_id>.json`
```json
{
  "cell_id": "ccrcc__virchow2__node_0001",
  "budget_sec": 21600,           // 6h
  "consumed_sec": 14523,         // updated each orchestrator tick from running experiments' wall time
  "started_at": "2026-05-01T08:00:00Z",
  "exhausted_at": null
}
```

### Enforcement layers (defense-in-depth)

1. **Submit-time check** (`cli.py submit`): if `consumed + spec.timeout_min*60 > budget`, refuse. Tells the agent *why* immediately.
2. **Tick-time check** (orchestrator daemon): each tick, sum running experiments' `wall_now - started_at`, plus historical `consumed_sec`, against `budget_sec`. If `>= budget`:
   - Mark cell `exhausted_at`.
   - Refuse new launches in that cell.
   - For running experiments: `process.terminate()` (SIGTERM) → wait `kill_grace_sec` (default 30) → `os.killpg(pgid, SIGKILL)`.
3. **Backend-level cap (defense in depth):**
   - LocalBackend: existing per-experiment `timeout_at` already in code (`orchestrator.py:578-587`).
   - SlurmBackend: pass `--time=$remaining_min --signal=B:TERM@30` so SLURM kills with 30s warning.
   - RayBackend: `ray.get(future, timeout=remaining_sec)` plus `ray.cancel(force=True)` on TimeoutError.
4. **Process-group isolation:** Subprocess launched with `start_new_session=True` so SIGKILL targets the whole tree (already in code post-Tier-1, per active set in PROJECT.md).

### Why NOT `signal.SIGALRM` inside Python

- SIGALRM is single-process-only and main-thread-only — useless for the orchestrator daemon (multi-threaded with watchdog) and useless for the *child* process (training scripts spawn DataLoader workers).
- Cross-process budget enforcement requires a watcher in the parent (orchestrator) — which we already have.
- Use SIGALRM only inside training scripts that want graceful checkpointing on a soft warning (not in framework code).

### Why NOT cgroups (yet)

- Cgroups give hard CPU/memory walls but require root or systemd-run privileges; SLURM clusters often disallow user cgroups. Out of scope per `Out of Scope: Containerized execution (podman/docker isolation)`.
- Re-evaluate if a real user surfaces "training scripts hit OOM-killer instead of timing out cleanly" — until then signals + SLURM `--time` are sufficient.

---

## Installation

```bash
# Core (already installed; do not re-litigate)
# click, aiohttp, watchdog, jinja2, pyyaml — see codebase/STACK.md

# New direct dependencies (add to src/automil/pyproject.toml [project].dependencies)
uv add psutil>=7.0
uv add filelock>=3.16
uv add 'pydantic>=2.9,<3'      # optional but strongly recommended

# Optional backend extras (add to [project.optional-dependencies])
uv add --optional slurm  'submitit>=1.5.3'
uv add --optional ray    'ray>=2.55.1,<3'

# Dev (add to [dependency-groups].dev)
uv add --dev 'mypy>=1.13'      # or pyright
uv add --dev 'respx>=0.21'     # if testing trajectory recorder against fake LLM endpoints

# Then users opt in:
# pip install -e '.[slurm]'    # for HPC users
# pip install -e '.[ray]'      # for cloud / multi-node users
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `submitit` | `simple_slurm` / `slurmpy` / `pysbatch` | Only if you need raw shell-script generation and don't want a Python-future API. Not our case. |
| `submitit` | Bespoke `subprocess.Popen('sbatch ...')` | Only if you can't add a 3rd-party dep at all. We can. |
| `ray` (raw) | `ray.tune` | If the project had no experiment graph. We have one; using `tune` would be two scheduling layers fighting. |
| `ray` | `dask.distributed` | If workloads were data-parallel rather than embarrassingly-parallel single-GPU jobs. autoMIL is the latter. |
| `ray` | `Celery` + Redis | If we needed a task queue for fine-grained jobs (sub-second). Our tasks are 4h training runs. Celery is overkill and has no GPU-aware scheduling. |
| Internal registry + entry_points | `pluggy` | If we needed multi-plugin event subscription (one event → many listeners). Variants are alternatives, not subscribers. |
| Internal registry | `Hydra-zen` | If the project were greenfield and adopted Hydra config-system holistically. Brownfield: Hydra-zen would force rewriting all dataset YAMLs. |
| OTel `gen_ai.*` JSONL | LangSmith proprietary schema | If you commit to LangChain/LangSmith long-term. We don't and shouldn't (vendor lock-in). LangSmith *consumes* OTel anyway. |
| OTel `gen_ai.*` JSONL | OpenInference (Phoenix/Arize) | Substantively similar to OTel; OTel won the standardization race in 2025. Close runner-up; safe fallback. |
| AGENTS.md + per-runtime overlays | "Just write a single Claude SKILL.md" | Locks the framework to Claude. F2 reviewer attack: "this is a Claude paper." Multi-runtime is the defense. |
| AGENTS.md + per-runtime overlays | Maintain runtime-specific instructions only (no AGENTS.md) | Possible but skips the 25+ tools that read AGENTS.md natively. AGENTS.md is the cheap union. |
| SIGTERM → SIGKILL via `os.killpg` | `psutil.Process.kill()` | Fine alternative; `os.killpg` is stdlib-only. Use psutil if we need sampling/RSS/cpu_percent in the same place. |
| SIGTERM → SIGKILL | Linux cgroups v2 | Stronger isolation but requires privileged setup. Out of scope. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **`simple_slurm`** as primary SLURM wrapper | Thin shell-script generator; no Job-future API, no preempt/requeue, no FAIR-scale validation | `submitit` |
| **`pluggy`** for the variant registry | Wrong abstraction (event-bus, not alternative-pick); extra dep; surprises agents who don't know pytest internals | One-page internal `Registry` class + `importlib.metadata.entry_points` |
| **`Hydra` / `Hydra-zen`** wholesale | Pulls in OmegaConf and forces a config-merge model that conflicts with autobench's existing `_resolve_env_vars` / `_resolve_paths` (`autobench/config.py:30`). Brownfield cost is high. | Stay with pyyaml + jinja2 templates already in use; add registry-by-name lookups in YAML. |
| **`opentelemetry-sdk` / `opentelemetry-exporter-otlp`** as runtime deps | Pulls in 30+ MB of transitive deps and forces collector infrastructure. We don't need export, we need *names*. | Adopt `gen_ai.*` field names only; stay with stdlib JSON. |
| **LangSmith / LangChain** for trajectory storage | Vendor lock-in; "as-protocol reproducibility" requires our trajectory format to be self-contained, not API-call-dependent | Self-hosted JSONL with OTel field names |
| **`ray.tune`** as the search controller | Conflicts with autoMIL's experiment graph; introduces foreign trial-state model | Use Ray as raw executor only; keep autoMIL graph as the search controller |
| **Custom skill format proprietary to autoMIL** | Locks users to autoMIL's runtime; defeats multi-runtime story | AGENTS.md + per-runtime official formats (Claude SKILL.md, opencode agents, Codex AGENTS.md) |
| **`signal.SIGALRM`** for orchestrator-side wall-clock | Main-thread-only, single-process-only, no cross-process semantics | Tick-time watcher + SIGTERM→SIGKILL via process group; SLURM `--time --signal=B:TERM@30` for HPC |
| **Docker / Podman containers per experiment** | Out of scope for v1 (security-relevant but major lift); breaks SLURM HPC where users rarely have container privileges | Trust the host venv + worktree isolation; revisit only if a real user surfaces a reproducibility miss |
| **`os.kill(pid, SIGKILL)`** for timeouts (no process group) | Leaks DataLoader worker processes; root cause of the VRAM-leak fixed at Tier 1 | `os.killpg(os.getpgid(pid), SIG)` (already done; reaffirm in new backends) |

---

## Stack Patterns by Variant

**If `orchestrator.backend == "local"` (default, single-machine):**
- No new deps required.
- `LocalBackend` wraps existing `Runner` + `subprocess.Popen`.
- This is the path Leo runs on the 3× RTX 6000 Ada workstation.

**If `orchestrator.backend == "slurm"` (HPC, e.g., university cluster):**
- Install `submitit>=1.5.3`.
- Set `partition`, `qos`, `account` in config.
- `automil/.env` must be readable from compute nodes (or set `--export=ALL`).
- Worktrees go on a node-shared filesystem (Lustre/NFS) — verify path before first run.
- Per-experiment SLURM job; cell budget enforced both by autoMIL (tick) and SLURM (`--time`).

**If `orchestrator.backend == "ray"` (multi-node cloud):**
- Install `ray>=2.55.1,<3`.
- Bring up a Ray cluster (`ray up cluster.yaml` or k8s operator).
- `ray.init(address="ray://head:10001")` from autoMIL daemon.
- Ray placement groups handle GPU reservation; autoMIL bin-packs by VRAM as today.
- Trajectory and result.json must round-trip through node-local cache → object store; use `ray.put`/`ray.get` for spec, write artifacts to shared FS.

**If runtime == Claude Code:**
- `agent_assets/claude/skills/automil-{setup,propose,reconcile,...}/SKILL.md`
- `.claude/hooks/on_stop.sh` for trajectory `session_end`
- `automil init --runtime=claude` (or auto-detect)

**If runtime == OpenAI Codex:**
- `AGENTS.md` (project root) is the primary surface
- Optionally: skills under Codex's skill format (still maturing in 2026)
- `automil init --runtime=codex`

**If runtime == opencode:**
- `.opencode/agents/automil-operator.md` (primary or subagent)
- `.opencode/skills/automil-{setup,propose,...}/SKILL.md`
- `automil init --runtime=opencode`

**If runtime == DeepSeek (via opencode/Claude Code/Cursor):**
- Treated as a *model* underneath one of the above harnesses.
- `agent_assets/deepseek/README.md` documents which harnesses route to DeepSeek and any tool-call ID quirks.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `submitit 1.5.3` | Python 3.8+, SLURM 20.x+ | Submitit 1.5.x supports current SLURM; older clusters (≤19.x) need 1.4.x |
| `ray 2.55.1` | Python 3.10–3.14, pydantic v1 (Ray drops pydantic v1 in 2.56) | Pydantic v2 coexistence works in practice; explicitly test if the framework adds pydantic v2 schemas |
| `pluggy 1.6.0` (NOT recommended for autoMIL — listed only because pytest pulls it) | Python 3.9+ | Already a transitive dep; do not import directly |
| `pydantic 2.9+` | Python 3.10+ | Independent of Ray's pydantic; coexists. v1 BaseModel imports still work via `pydantic.v1` shim. |
| `psutil 7.0+` | All target platforms (Linux primary) | Required; cross-process introspection |
| `filelock 3.16+` | All platforms | Pure-Python; no C extensions |
| AGENTS.md format | Linux Foundation governance | Stable; non-versioned (markdown) |
| Claude Code SKILL.md format | Claude Code latest | Live-watched; changes apply mid-session |
| OpenTelemetry GenAI semconv | semconv current spec | Field names stable; spec marked "in development" but `gen_ai.*` namespace locked |
| OTel `gen_ai.*` `tool.call.arguments` | Serialized to string per OTel + SWE-rebench convention | Trajectory consumers expect string; deserialize on read |

---

## Sources

- **submitit (FAIR / Meta)** — <https://github.com/facebookincubator/submitit>, <https://pypi.org/project/submitit/>, <https://ai.meta.com/blog/open-sourcing-submitit-a-lightweight-tool-for-slurm-cluster-computation/>. **HIGH** — official + production track record at FAIR + Dec 2025 release.
- **Ray** — <https://docs.ray.io/en/latest/index.html>, <https://github.com/ray-project/ray/releases>, <https://pypi.org/project/ray/>. Verified Ray 2.55.1 released April 22, 2026, supports Python 3.10–3.14. **HIGH**.
- **Ray Tune (rejected as scheduler)** — <https://docs.ray.io/en/latest/tune/api/schedulers.html>, <https://docs.ray.io/en/latest/tune/key-concepts.html>. **HIGH**.
- **AGENTS.md spec** — <https://agents.md/>, <https://developers.openai.com/codex/guides/agents-md>, <https://socket.dev/blog/agents-md-gains-traction-as-an-open-format-for-ai-coding-agents>. Linux Foundation governance, 25+ tools, 20,000+ repos. **HIGH**.
- **Claude Code SKILL.md** — <https://code.claude.com/docs/en/skills>, <https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview>, <https://www.agensi.io/learn/skill-md-format-reference>, <https://deepwiki.com/anthropics/skills/2.2-skill.md-format-specification>. Verified frontmatter fields, location precedence, live change detection. **HIGH**.
- **opencode agents + skills** — <https://opencode.ai/docs/agents/>, <https://opencode.ai/docs/skills/>. Verified file locations (`.opencode/agents/`, `.opencode/skills/`), frontmatter format. **HIGH**.
- **OpenTelemetry GenAI semantic conventions** — <https://opentelemetry.io/docs/specs/semconv/gen-ai/>, <https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/>, <https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-events/>, <https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md>. Spec in development, field namespace stable. **HIGH** for field names; **MEDIUM** for spec stability (still evolving, but `gen_ai.*` keys locked).
- **Trajectory JSONL convention** — <https://huggingface.co/datasets/nebius/SWE-agent-trajectories>, <https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories>, <https://github.com/SWE-Gym/SWE-Gym>, <https://www.swebench.com/SWE-bench/guides/evaluation/>, <https://swe-agent.com/latest/usage/inspector/>. SWE-agent + OpenHands precedent. **HIGH**.
- **Python plugin patterns** — <https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/>, <https://pluggy.readthedocs.io/>, <https://pypi.org/project/pluggy/>. **HIGH**.
- **SLURM signal escalation** — <https://slurm.schedmd.com/scancel.html>, <https://services.criann.fr/en/services/hpc/cluster-myria/guide/signals-sent-by-slurm/>, <https://dhruveshp.com/blog/2021/signal-propagation-on-slurm/>. SIGTERM → 30s grace → SIGKILL is SchedMD default. **HIGH**.
- **Python signal SIGALRM (rejected)** — <https://docs.python.org/3/library/signal.html>, <https://alexandra-zaharia.github.io/posts/function-timeout-in-python-signal/>. Documented main-thread-only limitation. **HIGH**.
- **DeepSeek API + harness routing** — <https://api-docs.deepseek.com/guides/coding_agents>, <https://devtk.ai/en/blog/deepseek-v4-agent-setup-2026/>. DeepSeek is OpenAI/Anthropic-API-compatible; runs under existing harnesses. **MEDIUM** — third-party blog corroborates official docs; compatible-API claim is HIGH.
- **Hydra-zen (rejected as overkill)** — <https://mit-ll-responsible-ai.github.io/hydra-zen/>. **HIGH** — direct doc read; rejected on brownfield-cost grounds, not capability grounds.
- **AGENTS.md adoption + Linux Foundation governance** — <https://socket.dev/blog/agents-md-gains-traction-as-an-open-format-for-ai-coding-agents>, <https://addozhang.medium.com/agents-md-a-new-standard-for-unified-coding-agent-instructions-0635fc5cb759>. **MEDIUM** — third-party but multiple corroborating sources + agents.md/ official.

---

*Stack research for: F2-readiness refactor (variant registry, pluggable backends, multi-runtime, trajectory, wall-clock cap)*
*Researched: 2026-05-01*
*Existing stack (Python 3.10+, click, aiohttp, watchdog, jinja2, pyyaml, hatchling, uv, vendored d3/three) is locked per .planning/codebase/STACK.md and not re-researched here.*
