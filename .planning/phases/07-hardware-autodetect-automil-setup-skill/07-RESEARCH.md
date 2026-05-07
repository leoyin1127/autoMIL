# Phase 7: Hardware autodetect and /automil-setup skill (Research)

**Researched:** 2026-05-07
**Domain:** Hardware probing (`nvidia-smi` / `rocm-smi` parsing), backend ABC extension, agent-skill scaffolding, idempotent file diffing, multi-runtime overlay propagation
**Confidence:** HIGH (Context7-equivalent: existing in-tree code, official Anthropic/OpenAI/OpenCode docs verified via WebSearch; one ASSUMED claim flagged below)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

D-189..D-198. All 10 engineering decisions are locked. See 07-CONTEXT.md `<decisions>` block. Key locked choices relevant to API surface:

- **D-189**: `Backend.healthcheck() -> HealthReport` is a NEW abstract method on the Phase 2 `Backend` ABC (frozen dataclass payload, `detection_status: Literal["ok", "partial", "failed"]`). SLURM/Ray impls raise `NotImplementedError`.
- **D-190**: Probe order CUDA → ROCm → CPU. CUDA-first via `subprocess.run([NVIDIA_SMI_PATH, "--query-gpu=index,memory.total", "--format=csv,noheader,nounits"])`. ROCm fallback via `rocm-smi --showmeminfo vram --csv`. Detection failures NEVER silently default.
- **D-191**: `automil init` extends to call `LocalBackend().healthcheck()` between `--update` guard (line 213) and config rendering (line 247). Conservative defaults: `default_vram_estimate_gb = max(8.0, min(gpu_vram_gb) / 8.0)`. Stamp values, not comments. Use `click.confirm` (binary) on `failed`, never `click.prompt`.
- **D-192**: Skill drafts EXACTLY `automil/config.yaml` + `automil/program.md` + `automil/variants/` skeleton. Skill does NOT run experiments, choose hyperparameters, or modify the training script.
- **D-193**: Inspection heuristics in priority order: training-script discovery → framework detection (torch/tf/jax/sklearn/lightning) → AST-walk model class detection → env-var grep → `result.json` adapter check.
- **D-194**: Idempotency = three-way per-section diff `existing | drafted | merged`. Per non-trivial diff, present unified diff; ask `overwrite | keep existing | merge interactively`. Never silently overwrite.
- **D-195**: Setup-done gate = `automil check` (must exit 0) THEN `automil submit ... --max-time 60` followed by orchestrator polling until terminal (must reach `executed`, not `crashed`, within 90s wall-clock).
- **D-196**: Per-runtime overlays follow Phase 3 D-79 `_overlay.py` build. Phase 7 only edits `_shared/automil-setup/SKILL.md`; rebuild propagates. Codex format = no frontmatter; Claude/OpenCode/DeepSeek = YAML frontmatter.
- **D-197**: Test matrix shipping with single-shape verification (Leo's 3-GPU CUDA workstation). Portability documented as MEDIUM with override path explicit. External hardware deferred behind `@pytest.mark.requires_external_hardware`.
- **D-198**: Acceptance gate = 8 clauses (6 unit tests for `LocalBackend.healthcheck()`, init-stamping integration test, overlay propagation, idempotency test, dry-run-gate test, 798-test baseline preserved + ≥10 new tests, CHANGELOG entry, `automil check` passes on workstation).

### Claude's Discretion

None. All 10 decisions locked per Leo's "decide engineering, ask features" directive (`feedback_decide_engineering_ask_features`).

### Deferred Ideas (OUT OF SCOPE)

- SLURM `Backend.healthcheck()` (raises `NotImplementedError`)
- Ray `Backend.healthcheck()` (raises `NotImplementedError`)
- External-hardware test matrix (single-GPU laptop, CPU-only, ROCm) behind `@pytest.mark.requires_external_hardware`
- `automil init --slurm` cluster autodiscovery wizard
- Skill auto-detection of CCRCC-style model lattice
- AutoML hyperparameter selection in the skill (explicit non-goal)
- Multi-language training script support (R, Julia)
- Telemetry export of healthcheck → trajectory recorder (deferred; redaction policy review needed)
- `automil status --health` viz dashboard integration (Phase 8 viz polish)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STP-01 | `LocalBackend.healthcheck()` reports detected GPU count, VRAM per GPU, accelerator type (CUDA/ROCm/CPU), Python version, autoMIL version | §nvidia-smi parsing, §rocm-smi fallback, §HealthReport dataclass, §OQ-1 |
| STP-02 | `automil init` consumes healthcheck output and pre-fills `automil/config.yaml` defaults (`max_concurrent_per_gpu`, `default_vram_estimate_gb` from `quantile_95(peak_vram_mb)` of `results.tsv` ≥10 samples else conservative) | §init.py integration patterns, §quantile-95 derivation, §OQ-2 |
| STP-03 | Hardware-detect produces a *report*, not a *decision*: failure prints values + prompts override; never silently uses wrong defaults | §detection_status enum semantics, §click.confirm usage, §Pitfall 8 anti-acceptance |
| STP-04 | `/automil-setup` skill inspects an arbitrary user repo, identifies training entry point, drafts `config.yaml` + `program.md`, scaffolds `variants/` skeleton, picks defaults from healthcheck | §inspection heuristics, §AST-walk model detection, §OQ-3 |
| STP-05 | Skill is idempotent. Re-running diffs and updates rather than overwrites | §three-way-diff library survey, §port-variant idempotency precedent, §OQ-4 |
| STP-06 | After setup, mandatory `automil check` + 1-min dry-run experiment; setup not "done" until both pass | §submit max-time semantics, §timeout_min field already exists, §Pitfall 9 anti-acceptance |
| STP-07 | Per-runtime overlays: `_shared/automil-setup/SKILL.md` canonical, `claude/`, `codex/`, `opencode/`, `deepseek/` overrides | §_overlay.py merge algorithm, §runtime frontmatter conventions verified |
</phase_requirements>

---

## Summary

Phase 7 lands hardware autodetect (`Backend.healthcheck()`) plus the `/automil-setup` skill. The hardware probe is straightforward. It reuses the existing `NVIDIA_SMI_PATH` constant and the same `subprocess.run` CSV parsing pattern already proven in `cli/check.py:147-158` and `_orchestrator_daemon.py:248-272`. The skill is the harder problem: per Pitfall 9, autonomous setup that confidently picks the wrong entry point is worse than one that asks. CONTEXT.md D-193 already locks the interactive-at-every-ambiguity contract.

**Key findings driving the planner:**

1. **Reuse, do not duplicate.** The `nvidia-smi` invocation pattern, `NVIDIA_SMI_PATH` resolution, and the `query_gpus()` helper at `_orchestrator_daemon.py:242` all exist. `LocalBackend.healthcheck()` should call `query_gpus()` directly and lift its return into `HealthReport` rather than re-implementing the subprocess call. This collapses six potential subprocess paths into one.

2. **`pyyaml` 6.0.1 round-trips lose comments.** `yaml.safe_load` → `yaml.safe_dump` strips comments and reorders keys. For D-194's three-way diff, this means the diff would surface every comment as a "change". Two viable resolutions: (a) compute the diff on the *value tree* (parsed dicts), not the textual YAML. `difflib.unified_diff` on `pprint.pformat(d)` works for deterministic flat configs; (b) add `ruamel.yaml` for round-trip-preserving YAML. Recommendation: **option (a). Value-tree diff via stdlib `difflib` + `pprint`**. No new dependency. See OQ-4.

3. **`submit --max-time 60` does NOT exist as a flag.** The existing `--timeout` flag (default 150 minutes) maps to `spec["timeout_min"]` consumed by `local.py:132` as `walltime_seconds // 60`. D-195 specifies `--max-time 60` (seconds). The smallest framework patch: the skill calls `automil submit --timeout 1` (1 minute = 60 seconds rounded up via `local.py`'s `max(1, ...)`), OR Phase 7 adds a `--max-time SECONDS` flag that overrides `--timeout`. **Recommendation: add `--max-time SECONDS`** so the skill semantics match D-195 verbatim. See OQ-5.

4. **Three of four runtimes share SKILL.md frontmatter contract.** Claude Code, OpenCode, and DeepSeek (latter via opencode/codex base) all use YAML frontmatter with required `name` + `description`. Codex uses plain markdown (AGENTS.md style; no frontmatter). The existing `_shared/skills/automil-setup/SKILL.md` already has the correct frontmatter; `_overlay.py:42-95` strips it correctly via the H1 split. Codex overlay must remove the YAML block at write time, that's a 5-line addition to `_overlay.py`.

5. **Pitfall 8 anti-acceptance has empirical-feedback teeth.** PITFALLS.md Pitfall 8 mitigation #2 (empirical VRAM feedback from `results.tsv`) is the load-bearing test for STP-02. Unit-mock a fake `results.tsv` with peak_vram_mb varying across rows; assert `automil init --update` recomputes `default_vram_estimate_gb` from `quantile_95`. Without this test, the codebase ships hardcoded constants disguised as detection.

6. **Pitfall 9 anti-acceptance has an idempotency check.** The mandatory load-bearing test: run `/automil-setup` twice on a tmpdir git repo; assert second run prompts zero unprompted file changes. The diff is the gate. If anything changes silently, idempotency is broken.

**Primary recommendation:** Treat finding #2 (value-tree diff) and finding #3 (`--max-time SECONDS` patch) as Wave-1 work. Findings #1, #4, #5, #6 are wave-content guidance. The architecture matches D-189..D-198 exactly; no decision corrections needed.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hardware probe (CUDA/ROCm/CPU) | Backend (`backends/local.py:healthcheck`) |, | D-189 locates this on the Backend ABC; only LocalBackend implements |
| HealthReport construction | Backend (`backends/base.py:HealthReport`) |, | Frozen dataclass owned by ABC module; immutable per Phase 2 D-53 |
| Init-time defaults stamping | CLI (`cli/init.py:init`) | Templates (`templates/config.yaml.j2`) | D-191: init reads HealthReport, render values into template context |
| Empirical VRAM feedback | CLI (`cli/init.py:init`) | `results.tsv` reader | quantile_95 of `peak_vram_mb` column, ≥10 samples gate |
| Skill content | `agent_assets/_shared/skills/automil-setup/SKILL.md` | `_overlay.py` build | D-196: canonical content lives in `_shared/`; runtime overlays auto-rebuild |
| Skill repo inspection | Skill instructions (markdown) | Agent runtime tools (Read, Grep, Bash) | D-193: heuristics described as instructions; agent uses runtime tools to execute |
| Setup-done gate (subprocess) | Skill body invokes `automil check` + `automil submit --max-time 60` | CLI commands (`check.py`, `submit.py`) | D-195: validation runs CLI, not custom Python paths |
| Three-way idempotency diff | Skill body (instructions) | `difflib` + `pprint` (stdlib) | D-194: per-section diff with user prompt; no new dep |
| Per-runtime frontmatter rendering | `agent_assets/_overlay.py:merge_skill` | `cli/init.py:_install_runtime_assets` | D-196: existing build pipeline; Phase 7 only edits `_shared/` source |

---

## Phase Boundary Recap (verbatim from CONTEXT.md)

> Make autoMIL one-shot deployable onto an arbitrary user repo. Land:
> 1. `Backend.healthcheck()` ABC method (LocalBackend implementation reports detected hardware), STP-01.
> 2. `automil init` consumes healthcheck output, pre-fills config.yaml defaults, STP-02.
> 3. Hardware detect = report-not-decide; failures prompt operator override, STP-03.
> 4. `/automil-setup` skill drafts config + program.md + variants/ skeleton from repo inspection, STP-04.
> 5. Skill is idempotent (diff/update, never overwrite), STP-05.
> 6. Setup-done gate: mandatory `automil check` AND 1-min dry-run experiment both pass, STP-06.
> 7. Per-runtime overlays: `_shared/automil-setup/SKILL.md` canonical, claude/codex/opencode/deepseek overrides, STP-07.
>
> **Out of scope:** SLURM/Ray Backend.healthcheck() (deferred); model selection AutoML; cluster-autodiscovery wizards; non-MIL training script support beyond contract-conformant scripts.

---

## Open Questions for the Planner

These are resolved API/flag/library choices grounded in code-level evidence. Each OQ ends with the recommendation the planner should bake into wave-level plans.

### OQ-1, `nvidia-smi` query field set: minimal vs. extended

**The question:** D-190 specifies `--query-gpu=index,memory.total --format=csv,noheader,nounits`. The existing `query_gpus()` at `_orchestrator_daemon.py:248-272` already queries 4 fields (`index,memory.total,memory.free,utilization.gpu`). Should `LocalBackend.healthcheck()` reuse that 4-field call or issue its own 2-field query?

**Evidence:**

- `_orchestrator_daemon.py:242-272` returns `list[GPUInfo]` with `(index, total_mb, free_mb, utilization)`, already path-pinned via `NVIDIA_SMI_PATH`, already wraps `subprocess.TimeoutExpired | FileNotFoundError | Exception`, already returns `[]` on any failure.
- `cli/check.py:147-158` issues a separate `--query-gpu=index` call and counts lines, duplicate work, inconsistent error semantics.
- D-190 says `index,memory.total` (2 fields). But healthcheck only consumes `(gpu_count, gpu_vram_gb)`, `free_mb` and `utilization` are useful telemetry but not required by `HealthReport`.

**Recommendation:** **Reuse `query_gpus()` directly.** `LocalBackend.healthcheck()` calls `query_gpus()`, slices `(gpu.total_mb / 1024 for gpu in result)` into `gpu_vram_gb`, and counts `len(result)` into `gpu_count`. Rationale: (a) deduplicates the subprocess error-handling logic across three call sites, `query_gpus`, `cli/check.py`, healthcheck; (b) `free_mb` and `utilization` are discarded for HealthReport but cost zero parsing; (c) the existing `query_gpus()` is already covered by tests and CLN-05 path-pinning.

**Caveat, MIG slices:** Per NVIDIA documentation (`docs.nvidia.com/deploy/nvidia-smi/`), on MIG-enabled GPUs the `--query-gpu=memory.total` returns the slice's memory, not the parent device's. For Phase 7 single-shape verification on Leo's workstation (no MIG), this is acceptable. Add a warning in `detection_warnings` if `nvidia-smi --query-gpu=mig.mode.current --format=csv,noheader` returns `Enabled` for any GPU; document portability as MEDIUM per D-197.

**Caveat, ECC reservation:** `memory.total` is reduced by ECC overhead (typically 6-12% on data-center cards). This is *correct behavior* for VRAM scheduling, the ECC-reserved memory is unavailable to user processes. No action needed.

**Caveat, `[Not Supported]`:** Some driver/GPU combinations return `[Not Supported]` for specific fields. The existing `query_gpus()` swallows this in the `except Exception` block returning `[]`. For HealthReport, this should set `detection_status="partial"` if SOME GPUs parse and others fail, which means we need to NOT use the existing `query_gpus()` swallow-all behavior, OR add a wrapper that distinguishes per-GPU failures.

**Final recommendation:** Wrap `query_gpus()` in a new helper `LocalBackend._healthcheck_cuda() -> tuple[int, tuple[float, ...], list[str]]` that re-runs the subprocess (because we need per-GPU pass/fail granularity for `partial` status) but reuses `NVIDIA_SMI_PATH` and the timeout/exception pattern. Cite `query_gpus()` as the structural template, do not import it.

[VERIFIED: in-tree at `src/automil/backends/_orchestrator_daemon.py:248`]
[CITED: NVIDIA docs, https://docs.nvidia.com/deploy/nvidia-smi/]

### OQ-2, Empirical VRAM feedback from `results.tsv`

**The question:** D-191 specifies "Use `quantile_95` of empirical VRAM observations from `results.tsv` (if present and ≥10 samples)" for `default_vram_estimate_gb`. Where does `results.tsv` live and what column do we read?

**Evidence:**

- The Result Contract (CLAUDE.md) has `peak_vram_mb` as a top-level `result.json` key.
- `results.tsv` is "written solely by the orchestrator from `result.json`, never by train.py" (CLAUDE.md). It lives at `<automil_dir>/results.tsv` (consumer-side, not framework-side).
- The orchestrator's reconcile path translates result.json → results.tsv. Check `cli/reconcile.py` for the exact column name. From the standard contract, the column is `peak_vram_mb` (numeric).
- `numpy.quantile([...], 0.95)` is the standard call. NumPy is already a transitive dep via torch.

**Recommendation:** Read `results.tsv` via `csv.DictReader(open(results_tsv, ..., delimiter='\t'))`, filter rows where `peak_vram_mb` is numeric and `> 0`, compute `numpy.quantile(values, 0.95) / 1024.0` (convert MB → GB). Gate: require `len(values) >= 10`; below threshold use conservative default `max(8.0, min(gpu_vram_gb) / 8.0)`.

**Pitfall (from PITFALLS.md #8):** without empirical feedback, hardware "auto-detection" is hardcoded constants in disguise. The unit test must mock a 30-row results.tsv with peak_vram_mb varying [400, 600, 800, ...] and assert the stamped `default_vram_estimate_gb` reflects `quantile_95 / 1024`, not the conservative fallback.

**Edge case:** First-time init has no `results.tsv` (empty repo). Path: `default_vram_estimate_gb = max(8.0, min(gpu_vram_gb) / 8.0)`. Document this in `program.md.j2` so the agent knows the value will improve after ~10 experiments.

[VERIFIED: CLAUDE.md result contract; numpy via `torch>=2.10` transitive]
[ASSUMED: `results.tsv` column name is `peak_vram_mb`, confirm by reading `cli/reconcile.py` during planning]

### OQ-3, AST-walk model class detection: depth, safety, fallback

**The question:** D-193 says "AST-walk training script + import sources; look for `nn.Module` subclasses (torch) / `tf.keras.Model` subclasses (tf) / `BaseEstimator` subclasses (sklearn)." How deep do we walk imports? Do we execute user code? What happens on parse errors?

**Evidence:**

- `ast.parse(source)` is a pure parser, never executes code. This is the correct primitive.
- `_orchestrator_daemon.py` already uses `ast` for trajectory redaction (Phase 3); pattern proven in-tree.
- `registry/validators/purity.py` walks AST top-level statements looking for forbidden patterns (network calls, mutable globals). Same primitive.
- Walking imports recursively risks combinatoric blowup: a training script imports torch.nn, which imports... etc. The skill has no business AST-walking torch internals.

**Recommendation:** **Single-file AST walk, no recursion into imports.** The skill walks ONLY the training script that the user pointed at (or the unambiguous match found via heuristic 1 in D-193). For each `ClassDef`, check `bases` for one of: `nn.Module`, `Module`, `torch.nn.Module`, `tf.keras.Model`, `Model`, `BaseEstimator`, `pl.LightningModule`, `LightningModule`. Report all matches. If multiple, ask the user. If zero, mark "model class: unknown" and proceed with framework label only.

**Why not recurse:** (a) `train.py` typically imports a model from `models/foo.py` which lives at a known path, but the skill is interactive: ask the user "your model class is in which file?" rather than guess. (b) Recursive import walking is the wrong primitive, the user's intent is captured by which file they point the skill at, not by the import graph.

**Decorator anti-pattern:** Some libraries (e.g. `@torch.compile`) decorate classes. Decorators don't execute during `ast.parse`; they're just `Decorator` nodes. Safe.

**Parse-error handling:** Wrap in `try: ast.parse(source) except SyntaxError as e: ...`. On syntax error, mark "model class: parse-error in {path}: {e}; user must specify manually" and proceed.

[VERIFIED: in-tree pattern at `src/automil/registry/validators/purity.py`]
[CITED: Python AST docs, https://docs.python.org/3/library/ast.html]

### OQ-4, Three-way idempotency diff: library choice for D-194

**The question:** D-194 says "Compute three-way per-section diff: `existing | drafted | merged`." Which Python library?

**Evidence:**

| Candidate | Already a dep? | Round-trip preserves comments? | Per-section semantics? | Verdict |
|-----------|----------------|-------------------------------|------------------------|---------|
| `difflib.unified_diff` (stdlib) | yes | n/a (string-level) | line-level only | Use for textual diff display |
| `pyyaml` 6.0.1 (`yaml.safe_load` ↔ `yaml.safe_dump`) | yes | **NO** (strips comments, reorders keys) | dict-level via parsed structure | Use for value-tree comparison |
| `ruamel.yaml` | NO (would be new dep) | yes (round-trip mode) | yes | Heavy; not justified for one phase |
| `deepdiff` | NO (would be new dep) | n/a | yes (path-aware) | Heavy; not justified |
| `dictdiffer` | NO (would be new dep) | n/a | yes | Heavy; not justified |

**Recommendation: stdlib-only path.** Use the following two-stage approach:

```python
# Stage 1: parse both YAML docs into Python dicts (loses formatting; we don't care for the diff).
import yaml, difflib, pprint
existing = yaml.safe_load(existing_text) or {}
drafted = yaml.safe_load(drafted_text) or {}

# Stage 2: render as deterministic Python repr (sorted keys), diff line-by-line.
existing_repr = pprint.pformat(existing, sort_dicts=True, width=120).splitlines()
drafted_repr = pprint.pformat(drafted, sort_dicts=True, width=120).splitlines()
diff_lines = list(difflib.unified_diff(existing_repr, drafted_repr,
                                       fromfile="existing", tofile="drafted", lineterm=""))
```

This produces a unified diff at the value level (comments and key ordering ignored, which is exactly what D-194 wants for "non-trivial diff" detection).

**Per-section interactivity:** A "section" in `config.yaml` is a top-level key (`run`, `data`, `encoders`, `baseline`, `files`, `metrics`, `training`, `cap`, `gate`, `backend`). For each top-level key where `existing[k] != drafted[k]`, present the diff for THAT subtree only. The skill prompts: `[k]eep existing | [o]verwrite | [m]erge interactively | [s]how full diff`.

**Rationale (no new dep):** `pyyaml` and `difflib` are both already imported by autoMIL (`pyyaml` is a core dep; `difflib` is stdlib). Adding `ruamel.yaml` for one phase is unjustified, D-194 only needs to *detect* differences and ask the user; it does not need to *write back* preserving comments because the skill explicitly drafts the config from scratch and the user's edits are surfaced before write.

**One concession:** if Leo's standing memory `feedback_decide_engineering_ask_features` later flags this as a UX miss (users WANT comment-preservation), Phase 8 can add `ruamel.yaml` as an optional dep. Not Phase 7's problem.

[VERIFIED: pyyaml 6.0.1 in pyproject.toml; `difflib` + `pprint` are stdlib]
[CITED: Python `difflib` docs, https://docs.python.org/3/library/difflib.html]

### OQ-5, `submit --max-time SECONDS` flag: smallest framework patch

**The question:** D-195 specifies `automil submit --max-time 60` for the dry-run gate. The existing flag is `--timeout` in MINUTES (default 150, so `--timeout 1` ≈ 60 seconds). What's the smallest patch?

**Evidence:**

- `cli/submit.py:24` declares `@click.option("--timeout", default=150, help="Timeout in minutes")`.
- `cli/submit.py:332` writes `"timeout_min": timeout` into the spec.
- `backends/local.py:132` consumes via `"timeout_min": max(1, spec.walltime_seconds // 60)`, the local backend's MIN floor is 1 minute.
- D-195 says 60 seconds wall-clock; the local backend rounds UP to 1 minute, which matches.
- D-195 says 90s wall-clock for the orchestrator polling timeout, this is a separate concern (the skill's polling budget), not a flag on submit.

**Recommendation:** **Add a NEW `--max-time SECONDS` flag** (NOT replacement of `--timeout`):

```python
# cli/submit.py
@click.option("--timeout", default=150, help="Timeout in minutes")
@click.option("--max-time", "max_time_seconds", type=int, default=None,
              help="Override --timeout with seconds-precision (rounded up to 1 min minimum).")
def submit(... max_time_seconds: int | None ...):
    if max_time_seconds is not None:
        timeout = max(1, (max_time_seconds + 59) // 60)  # ceil-div minutes
```

Rationale: (a) preserves existing `--timeout` semantics for callers; (b) skill body invokes `automil submit --max-time 60`, exactly D-195; (c) ceil-div ensures `--max-time 60` → `timeout=1` (1 minute) → `walltime_seconds=60` after the local backend's `max(1, ...)` floor, consistent end-to-end.

**Alternative considered and rejected:** Reusing `--timeout 1` as the dry-run idiom. Rejected because (a) the skill's invocation would say `--timeout 1` which is ambiguous about units to a reader; (b) D-195 says `--max-time 60` literally; (c) future use cases (CI smoke tests) want seconds precision.

**Patch size:** ~5 lines in `cli/submit.py`. Covered by existing CLI tests (just need `tests/cli/test_submit_max_time.py` for the new flag).

[VERIFIED: `cli/submit.py` ↔ `backends/local.py` walltime path traced]

### OQ-6, Telemetry redaction policy for HealthReport [DEFERRED PER CONTEXT]

**The question:** Phase 3 trajectory recorder mandates redaction of secrets and PII. Does HealthReport contain hardware fingerprinting that should be redacted before trajectory capture?

**Evidence:**

- HealthReport fields (per D-189): `gpu_count`, `gpu_vram_gb`, `accelerator`, `python_version`, `automil_version`, `detection_status`, `detection_warnings`, `detected_at`. None are secrets in the conventional sense.
- BUT: combination of (gpu_count, gpu_vram_gb, python_version, hostname-implied-via-warnings) constitutes a **hardware fingerprint** that uniquely identifies Leo's workstation across published trajectories.
- CONTEXT.md `<deferred>` block: "Telemetry export of healthcheck → trajectory recorder, could leak hardware fingerprint; deferred for redaction policy review."
- Phase 3's redaction policy targets `os.environ.get(...)` values, secret-shaped strings, file paths under `$HOME`. Hardware specs are NOT currently in the redactor's deny-list.

**Recommendation:** **Do not write HealthReport into trajectory output in Phase 7.** Treat it as `detected → log to stdout → stamped into config.yaml → discarded`. If a future phase wants to log HealthReport for debugging across machines, that future phase must:

1. Replace `gpu_count` and `gpu_vram_gb` with bucket labels (e.g., `gpu_count_bucket: "1-4" | "5-8" | "9+"`, `gpu_vram_gb_bucket: "8-16" | "16-32" | "32-64" | "64+"`).
2. Drop `detection_warnings` entirely (warnings can contain hostname-like details).
3. Drop `python_version` patch level (`3.11.9` → `3.11`).

**Phase 7 action:** Add a comment in `backends/base.py:HealthReport` docstring: "Do not serialize this dataclass into trajectory output; see CONTEXT.md deferred-ideas block." This is a 1-line code annotation.

[VERIFIED: CONTEXT.md `<deferred>` block]
[ASSUMED: Phase 3 redactor's deny-list, confirm in `src/automil/trajectory/redactor.py` if that path exists]

---

## Reusable Patterns

The planner should mirror existing patterns rather than invent new ones.

### Pattern 1: Path-pinned subprocess.run (`_orchestrator_daemon.py:79-87` + `:242-272`)

```python
# At module top, resolved once, cached forever:
import shutil
_resolved_nvidia_smi = shutil.which("nvidia-smi")
NVIDIA_SMI_PATH = _resolved_nvidia_smi or "nvidia-smi"
if _resolved_nvidia_smi:
    logger.info("nvidia-smi resolved to %s", NVIDIA_SMI_PATH)
else:
    logger.warning(
        "nvidia-smi not found via shutil.which; falling back to bare PATH lookup. "
        "GPU state may be unreliable on hosts with shimmed PATH."
    )

# In healthcheck, reuse the constant, NEVER re-resolve:
def _healthcheck_cuda(self) -> tuple[int, tuple[float, ...], list[str]]:
    warnings: list[str] = []
    try:
        result = subprocess.run(
            [NVIDIA_SMI_PATH, "--query-gpu=index,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0, (), ["nvidia-smi not available"]
    # ... per-line parsing identical to query_gpus() ...
```

**Why this matters for Phase 7:** D-189 + D-190 explicitly tie healthcheck to CLN-05 path pinning. Reusing the constant means the import-time resolution warning fires once; healthcheck inherits that audit trail.

### Pattern 2: Frozen dataclass payload (`backends/base.py:JobHandle`, `:JobSpec`)

```python
# Existing pattern at backends/base.py:36-110, Phase 7 adds:
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass(frozen=True)
class HealthReport:
    """Immutable hardware-detection report (D-189). Report-not-decision (STP-03).

    Detection branching:
      - ok: probe succeeded, all fields populated.
      - partial: e.g. CUDA found but VRAM unparseable for SOME GPUs.
      - failed: all probes failed AND user has env signal that GPU expected.

    NEVER serialize into trajectory output (CONTEXT.md deferred-ideas, hardware
    fingerprinting redaction policy review pending).
    """
    gpu_count: int
    gpu_vram_gb: tuple[float, ...]
    accelerator: Literal["cuda", "rocm", "cpu"]
    python_version: str
    automil_version: str
    detection_status: Literal["ok", "partial", "failed"]
    detection_warnings: tuple[str, ...]
    detected_at: datetime
```

**Why frozen:** D-53 immutability convention for Phase 2 ABC payloads. Hashable; safe to cache; safe to JSON-serialize via `dataclasses.asdict(report)` (with `datetime` → `isoformat()` adapter).

### Pattern 3: Idempotent CLI command (`cli/lifecycle/port_variant.py:254-269`)

The exact pattern Phase 7's skill must mirror for D-194:

```python
# port_variant.py:254-269, VERBATIM pattern:
if module_path.exists() and manifest_path.exists():
    try:
        existing = Manifest.read(manifest_path)
    except Exception:
        existing = None
    if existing is not None and existing.spec.node_id == node_id:
        click.echo(f"port-variant: {final_name} already ported (node_id match); no-op.")
        return
    if existing is not None and existing.spec.node_id != node_id:
        raise click.ClickException(
            f"Refusing to port: {module_path} already exists with "
            f"node_id={existing.spec.node_id!r}, but you're porting "
            f"node_id={node_id!r}. Names collide. Use `--name <other_name>` "
            f"to disambiguate."
        )
```

**The skill's adaptation:** for each artifact (`config.yaml`, `program.md`, `variants/<class>_v0.py`):

1. If absent → write fresh.
2. If present AND value-tree matches drafted → no-op (the matching is via OQ-4's `pyyaml + pprint + difflib` path).
3. If present AND value-tree differs → present unified diff, prompt user `[k/o/m/s]`.

The "node_id match → no-op" semantic in port_variant becomes "value-tree match → no-op" in setup-skill. The "node_id mismatch → hard fail" semantic becomes "value-tree mismatch → present diff" (skills are interactive; CLIs are not).

### Pattern 4: H2 section-replacement overlay (`agent_assets/_overlay.py:42-95`)

The build pipeline that propagates `_shared/automil-setup/SKILL.md` to per-runtime overlays already exists. Phase 7 only edits `_shared/`; rebuild propagates.

**Caveat (existing in-tree warning at `_overlay.py:7-13`):** The H2 split treats ANY line beginning with `## ` as a section header, INCLUDING lines inside fenced code blocks. Phase 7's skill content MUST NOT contain `## ` at the start of a line inside a fenced bash/python code block. Test exists at `tests/agent_assets/test_overlay.py::test_known_limitation_code_block_false_split`.

**Codex frontmatter stripping:** The Codex runtime expects no YAML frontmatter (per WebSearch verification, Codex AGENTS.md uses plain markdown). The current `_overlay.py:60-70` returns shared text as-is when no overlay exists. For Codex, we either (a) add a `codex/skills/automil-setup/SKILL.md` overlay that has no `---` block (the merge will replace the shared frontmatter with empty frontmatter), or (b) extend `_overlay.py` to strip frontmatter when `runtime == "codex"`. **Recommendation: option (a)**, keep `_overlay.py` runtime-agnostic; Codex overlay file just omits the `---` block. This also means Codex install path renders to `.codex/instructions.md` not `.codex/skills/automil-setup/SKILL.md` (per the existing init.py:153-166 codex branch).

### Pattern 5: subprocess + click.confirm composition (`cli/check.py:154-196`)

```python
# cli/check.py:154, existing pattern Phase 7's init extends:
try:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        warnings.append("nvidia-smi failed. GPU scheduling may not work correctly.")
    else:
        n_gpus = len(result.stdout.strip().splitlines())
        click.echo(f"GPUs detected: {n_gpus}")
except (FileNotFoundError, subprocess.TimeoutExpired):
    warnings.append("nvidia-smi not found. GPU scheduling will use fallback.")

# Phase 7's init.py extension follows D-191:
report = LocalBackend().healthcheck()
click.echo(_format_health_report(report))   # NEW helper, ~20 lines
if report.detection_status == "failed":
    if not click.confirm("Detection failed; use conservative defaults?", default=False):
        raise click.ClickException("Aborted. See `automil check --healthcheck` for details.")
```

---

## External Dependencies

Per `feedback_decide_engineering_ask_features` and CLAUDE.md "Simplicity First": prefer stdlib + existing deps. Adding a new dependency requires explicit justification.

| Library | Version | Already in `pyproject.toml`? | Phase 7 Usage | Verdict |
|---------|---------|-------------------------------|----------------|---------|
| `pyyaml` | 6.0.1 | yes (core dep) | Parse existing/drafted config.yaml for value-tree diff | Use as-is |
| `difflib` | stdlib | n/a | Unified diff generation in skill idempotency check | Use as-is |
| `pprint` | stdlib | n/a | Deterministic dict-repr for diff stability | Use as-is |
| `ast` | stdlib | n/a | Model class detection via AST walk (D-193) | Use as-is |
| `dataclasses` | stdlib | n/a | `HealthReport` frozen dataclass (D-189) | Use as-is |
| `importlib.metadata` | stdlib | n/a | `automil_version` field in HealthReport (`importlib.metadata.version("automil")`) | Use as-is |
| `subprocess` | stdlib | n/a | nvidia-smi / rocm-smi / `automil check` invocation | Use as-is |
| `numpy` | transitive via `torch>=2.10` | yes (transitive) | `quantile_95(peak_vram_mb)` for empirical VRAM feedback | Use as-is |
| `ruamel.yaml` | n/a | NO | Round-trip-preserving YAML edit | **Rejected** (one-phase justification insufficient; OQ-4 stdlib path covers) |
| `deepdiff` | n/a | NO | Path-aware dict diff | **Rejected** (overkill for top-level-key sectioning; OQ-4 stdlib path covers) |
| `dictdiffer` | n/a | NO | Dict diff with patch generation | **Rejected** (overkill; OQ-4 stdlib path covers) |
| `rich` | n/a | NO | Pretty diff display in terminal | **Rejected** (click.echo + ANSI codes if needed; not core to STP-05) |

**Conclusion:** **Zero new dependencies for Phase 7.** All work falls within stdlib + existing core deps. This matches D-198 acceptance gate clause 7 (CHANGELOG entry at 7.0.0 due to Backend ABC breaking change, but no dep additions to call out).

**Version verification command (run during planning):**

```bash
python3 -c "import yaml, difflib, pprint, ast, dataclasses, importlib.metadata, subprocess; print('all stdlib + pyyaml available')"
python3 -c "import numpy; print('numpy', numpy.__version__)"  # transitive via torch
python3 -c "import importlib.metadata; print(importlib.metadata.version('automil'))"  # confirms automil_version path
```

---

## Test Pattern Recommendations

Phase 7 ships ≥10 new tests across 3 test files. Existing test patterns to mirror:

### Pattern A: Mock `subprocess.run` for nvidia-smi/rocm-smi

`tests/test_orchestrator.py` already mocks `subprocess.run` for nvidia-smi. The Phase 7 healthcheck tests follow the same pattern:

```python
# tests/backends/test_local_healthcheck.py
import subprocess
from unittest.mock import patch, MagicMock

def _mock_nvidia_smi(stdout: str, returncode: int = 0):
    """Build a mock subprocess.run side_effect that returns the given stdout."""
    return MagicMock(stdout=stdout, returncode=returncode, stderr="")

def test_healthcheck_cuda_3_gpu_happy_path(monkeypatch):
    """D-198 clause 1.1: cuda-3-gpu happy path."""
    fake_stdout = "0, 49140\n1, 49140\n2, 49140\n"  # 3× 48 GB GPUs
    with patch("subprocess.run", return_value=_mock_nvidia_smi(fake_stdout)):
        report = LocalBackend().healthcheck()
    assert report.gpu_count == 3
    assert report.accelerator == "cuda"
    assert report.detection_status == "ok"
    assert all(48.0 <= v <= 48.5 for v in report.gpu_vram_gb)
    assert report.detection_warnings == ()

def test_healthcheck_cuda_no_gpus_falls_through_to_cpu(monkeypatch):
    """D-198 clause 1.2: cuda-no-gpus fallback."""
    with patch("subprocess.run", return_value=_mock_nvidia_smi("", returncode=1)):
        # Also mock rocm-smi failing:
        with patch("shutil.which", return_value=None):
            report = LocalBackend().healthcheck()
    assert report.gpu_count == 0
    assert report.accelerator == "cpu"
    assert report.detection_status == "ok"  # CPU detection always succeeds

def test_healthcheck_partial_detection(monkeypatch):
    """D-198 clause 1.5: partial-detection (1 GPU detected, 1 GPU CSV unparseable)."""
    fake_stdout = "0, 49140\n1, [Not Supported]\n"  # second GPU's VRAM unparseable
    with patch("subprocess.run", return_value=_mock_nvidia_smi(fake_stdout)):
        report = LocalBackend().healthcheck()
    assert report.gpu_count == 2
    assert len(report.gpu_vram_gb) == 1  # only the parseable one
    assert report.detection_status == "partial"
    assert any("[Not Supported]" in w for w in report.detection_warnings)

def test_healthcheck_full_failure_prompts_override(monkeypatch, tmp_path):
    """D-198 clause 1.6: full-failure-prompts-override.

    `automil init` MUST raise click.ClickException when detection fails AND user
    declines conservative defaults. STP-03: never silently uses wrong defaults.
    """
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")  # signal user expected GPU
    with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi missing")):
        with patch("shutil.which", return_value=None):
            report = LocalBackend().healthcheck()
    assert report.detection_status == "failed"
```

### Pattern B: Tmp git-repo fixture for skill idempotency tests

```python
# tests/skills/test_setup_idempotency.py
import subprocess
from pathlib import Path

@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a tmp git repo with a fake train.py + skeleton files."""
    repo = tmp_path / "fake_project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    (repo / "train.py").write_text(
        "import torch\nclass MyModel(torch.nn.Module): pass\n"
    )
    return repo

def test_setup_skill_idempotent_zero_unprompted_changes(tmp_git_repo, monkeypatch):
    """D-198 clause 4: re-running /automil-setup produces zero unprompted changes.

    The skill is invoked as a sequence of CLI commands (since pytest can't drive
    an LLM agent). We simulate the skill's CLI sequence directly:
      1. automil init (first run)
      2. Stamp config from healthcheck (call _stamp_defaults() helper)
      3. Stamp config from healthcheck again (second run, MUST be no-op)
    """
    monkeypatch.chdir(tmp_git_repo)
    subprocess.run(["automil", "init"], check=True)

    config_path = tmp_git_repo / "automil" / "config.yaml"
    first_text = config_path.read_text()
    first_mtime = config_path.stat().st_mtime

    # Re-run the stamping logic directly (no agent in unit test).
    from automil.cli.init import _stamp_healthcheck_defaults
    _stamp_healthcheck_defaults(tmp_git_repo / "automil", LocalBackend().healthcheck())

    second_text = config_path.read_text()
    # Idempotency assertion: byte-identical AND mtime did not advance (no rewrite).
    assert first_text == second_text
    # NOTE: mtime check may be flaky on FAT32; assert text equality first.
```

### Pattern C: Setup-done gate with synthetic crash (Pitfall 9 anti-acceptance)

```python
# tests/skills/test_setup_dry_run_gate.py
def test_setup_gate_aborts_on_known_bad_config(tmp_git_repo):
    """D-198 clause 5: known-bad config must fail the dry-run gate; skill aborts.

    A 'known-bad' config: train.py raises ImportError on a missing module.
    The setup-done gate runs `automil submit --max-time 60`; the orchestrator
    polls until the spec reaches `crashed`. Assertion: the skill MUST refuse
    to print 'Setup complete.'
    """
    (tmp_git_repo / "train.py").write_text(
        "import nonexistent_module\n"  # ImportError
    )
    # ... setup the orchestrator + run /automil-setup's gate ...
    # Assert: result.json shows status='crash', skill exits non-zero.
```

### Pattern D: HealthReport pickle stability

```python
# tests/backends/test_health_report_immutability.py
def test_health_report_is_frozen_and_hashable():
    """D-53 immutability convention; HealthReport must be safe in dict keys / sets."""
    report = HealthReport(
        gpu_count=3, gpu_vram_gb=(48.0, 48.0, 48.0), accelerator="cuda",
        python_version="3.11.9", automil_version="0.1.0",
        detection_status="ok", detection_warnings=(),
        detected_at=datetime(2026, 5, 7, 12, 0, 0),
    )
    s = {report}  # hashable
    assert report in s
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.gpu_count = 4  # mutation must fail
```

---

## Pitfall 8 + 9 Anti-Acceptance Tests

Beyond CONTEXT.md's coverage, the following load-bearing tests defend the failure modes from `research/PITFALLS.md` Pitfalls 8 + 9.

### Pitfall 8: Hardware mis-detect produces wrong defaults

**Defending tests** (each maps to a PITFALLS.md mitigation #1-6):

1. **`test_healthcheck_warns_on_mig_enabled`** (mitigation 1: detect-and-warn), mock `nvidia-smi --query-gpu=mig.mode.current` returning `Enabled`; assert `detection_warnings` contains a MIG-specific warning string. Otherwise the H100 cluster case silently returns slice-memory.

2. **`test_init_recomputes_default_vram_from_results_tsv`** (mitigation 2: empirical VRAM feedback), fixture: `automil/results.tsv` with 30 rows of varying `peak_vram_mb`. Run `automil init --update`; assert `config.yaml: cap.default_vram_estimate_gb` ≈ `numpy.quantile(peak_vram_mb, 0.95) / 1024` (within ±0.05 GB). This is the load-bearing test that prevents Pitfall 8's "hardcoded constants in disguise" failure.

3. **`test_init_uses_conservative_default_below_10_samples`** (mitigation 2 lower bound), fixture: `results.tsv` with 5 rows. Run `automil init`; assert `default_vram_estimate_gb == max(8.0, min(gpu_vram_gb) / 8.0)` (the conservative path). This guards against tiny-sample quantile noise.

4. **`test_init_emits_loud_warning_on_under_utilization`** (mitigation 5: document failure mode loudly), mock 80 GB GPU + drafted `max_concurrent_per_gpu=8`. Init must emit a click warning string mentioning either "under-utilization" or specific thresholds. Test asserts the warning text appears in `caplog`.

5. **`test_local_healthcheck_does_not_run_on_slurm_backend`** (mitigation 6: defer multi-node detection), instantiate a SLURM backend (mocked); call `.healthcheck()`; assert `NotImplementedError` raised with the exact message from D-189: "healthcheck deferred to Phase 7+ for distributed backends". This prevents local nvidia-smi heuristics leaking into SLURM paths.

### Pitfall 9: Setup skill mis-scaffolds variants / config

**Defending tests** (each maps to PITFALLS.md mitigation #1-6):

1. **`test_skill_idempotency_zero_unprompted_changes`** (mitigation 1: interactive by default; mitigation 6: CLI fallback exists), run skill-equivalent CLI sequence twice on tmp repo; assert second run produces zero file modifications. This is D-198 clause 4's load-bearing test.

2. **`test_skill_asks_on_multiple_train_py_candidates`** (mitigation 2: detect-then-confirm), fixture: tmp repo with `train.py` AND `scripts/train.py` AND `src/foo/main.py`. Skill's heuristic (Inspection step 1 of D-193) must report multi-match and ask user. Test asserts the agent-equivalent code path raises a "user input required" sentinel rather than silently picking.

3. **`test_setup_done_gate_aborts_on_check_failure`** (mitigation 3: validate via `automil check`), fixture: scaffold a config with `data.features_dir: "/path/to/missing"`. Run setup-done gate; assert `automil check` exits non-zero AND skill aborts before running submit.

4. **`test_setup_done_gate_aborts_on_dry_run_crash`** (mitigation 3: validate via dry-run), fixture: scaffold a `train.py` that raises ImportError. Run `automil submit --max-time 60`; orchestrator marks node as `crashed`. Skill MUST NOT print `Setup complete.` Test asserts the absence of that string in stdout.

5. **`test_skill_refuses_long_tail_repos_with_helpful_message`** (mitigation 4: opinionated, not exhaustive), fixture: tmp repo with NO Python files (e.g., R-only). Skill must exit with a message pointing to `<5 keys` the user must set manually, not silently fabricate a Python config.

6. **`test_skill_writes_reasoning_trace_to_planning_dir`** (mitigation 5: log decisions), assert that after running the skill, `.planning/setup-trajectory.md` exists with at minimum: (a) which heuristic matched the training script, (b) which model class was detected, (c) which env vars were detected, (d) what user inputs were collected. This is the audit trail for "scaffold is wrong, why?"

7. **`test_skill_never_produces_TODO_substring_in_config`** (PITFALLS.md warning sign #1), after skill run, grep `automil/config.yaml` for `TODO`; assert zero matches. CONCERNS.md Tech Debt #7 already flags this; the skill must not produce them.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest>=9.0.2` (per `pyproject.toml [dependency-groups].dev`) |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/backends/test_local_healthcheck.py tests/skills/ -x` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STP-01 | LocalBackend.healthcheck cuda-3-gpu happy path | unit | `uv run pytest tests/backends/test_local_healthcheck.py::test_healthcheck_cuda_3_gpu_happy_path -x` | ❌ Wave 0 |
| STP-01 | cuda-no-gpus falls through to cpu | unit | `uv run pytest tests/backends/test_local_healthcheck.py::test_healthcheck_cuda_no_gpus_falls_through_to_cpu -x` | ❌ Wave 0 |
| STP-01 | rocm fallback | unit | `uv run pytest tests/backends/test_local_healthcheck.py::test_healthcheck_rocm_fallback -x` | ❌ Wave 0 |
| STP-01 | cpu fallback always succeeds | unit | `uv run pytest tests/backends/test_local_healthcheck.py::test_healthcheck_cpu_only -x` | ❌ Wave 0 |
| STP-01 | partial detection 1-of-2 GPUs | unit | `uv run pytest tests/backends/test_local_healthcheck.py::test_healthcheck_partial_detection -x` | ❌ Wave 0 |
| STP-01 | full failure prompts override (D-198 clause 1.6) | unit | `uv run pytest tests/backends/test_local_healthcheck.py::test_healthcheck_full_failure_prompts_override -x` | ❌ Wave 0 |
| STP-01 | SLURM/Ray raise NotImplementedError | unit | `uv run pytest tests/backends/test_distributed_healthcheck_deferred.py -x` | ❌ Wave 0 |
| STP-02 | init stamps healthcheck values into config.yaml | integration | `uv run pytest tests/cli/test_init_healthcheck.py::test_init_stamps_gpu_count -x` | ❌ Wave 0 |
| STP-02 | init recomputes default_vram from results.tsv ≥10 samples | integration | `uv run pytest tests/cli/test_init_healthcheck.py::test_init_recomputes_default_vram_from_results_tsv -x` | ❌ Wave 0 |
| STP-02 | init uses conservative default below 10 samples | integration | `uv run pytest tests/cli/test_init_healthcheck.py::test_init_uses_conservative_default_below_10_samples -x` | ❌ Wave 0 |
| STP-02 | --no-healthcheck flag for CI | integration | `uv run pytest tests/cli/test_init_healthcheck.py::test_init_no_healthcheck_flag -x` | ❌ Wave 0 |
| STP-03 | failed detection aborts on user 'no' | integration | `uv run pytest tests/cli/test_init_healthcheck.py::test_init_aborts_on_failed_detection_user_decline -x` | ❌ Wave 0 |
| STP-04 | skill scaffold writes config.yaml + program.md + variants/ skeleton | integration (skill-CLI proxy) | `uv run pytest tests/skills/test_setup_scaffold.py -x` | ❌ Wave 0 |
| STP-05 | second run produces zero unprompted changes (D-198 clause 4) | integration | `uv run pytest tests/skills/test_setup_idempotency.py::test_skill_idempotency_zero_unprompted_changes -x` | ❌ Wave 0 |
| STP-06 | known-bad config aborts dry-run gate (D-198 clause 5) | integration | `uv run pytest tests/skills/test_setup_dry_run_gate.py::test_setup_gate_aborts_on_known_bad_config -x` | ❌ Wave 0 |
| STP-06 | --max-time SECONDS flag exists on submit | unit | `uv run pytest tests/cli/test_submit_max_time.py -x` | ❌ Wave 0 |
| STP-07 | _shared/automil-setup/SKILL.md propagates to claude/codex/opencode/deepseek | integration | `uv run pytest tests/agent_assets/test_overlay_propagation_phase7.py -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/backends/test_local_healthcheck.py tests/cli/test_init_healthcheck.py tests/skills/ -x` (~4-6s wall-clock; subprocess-mocked)
- **Per wave merge:** `uv run pytest tests/ -v` (full 798-baseline + ≥10 new = 808+ tests)
- **Phase gate:** Full suite green before `/gsd-verify-work 7`. CHANGELOG entry at 7.0.0 (Backend ABC breaking) per D-198 clause 7.

### Wave 0 Gaps

- [ ] `tests/backends/test_local_healthcheck.py`, covers STP-01 (6 unit tests per D-198 clause 1)
- [ ] `tests/backends/test_distributed_healthcheck_deferred.py`, SLURM/Ray NotImplementedError stubs
- [ ] `tests/cli/test_init_healthcheck.py`, covers STP-02, STP-03 (5 integration tests)
- [ ] `tests/cli/test_submit_max_time.py`, covers OQ-5 `--max-time SECONDS` flag (~3 tests)
- [ ] `tests/skills/__init__.py`, directory init (none-existing)
- [ ] `tests/skills/test_setup_idempotency.py`, covers STP-05 (D-198 clause 4); load-bearing for Pitfall 9
- [ ] `tests/skills/test_setup_dry_run_gate.py`, covers STP-06 (D-198 clause 5); load-bearing for Pitfall 9
- [ ] `tests/skills/test_setup_scaffold.py`, covers STP-04 (skill-CLI proxy)
- [ ] `tests/skills/test_setup_pitfall_anti_acceptance.py`, covers Pitfall 8 + 9 mitigations beyond core STP requirements
- [ ] `tests/agent_assets/test_overlay_propagation_phase7.py`, covers STP-07 propagation to all 4 runtimes
- [ ] `tests/conftest.py`, extend with `tmp_git_repo` fixture (Pattern B)

---

## Project Constraints (from CLAUDE.md)

The following directives from `CLAUDE.md` and Leo's standing memory bind Phase 7's implementation:

| Directive | Source | Implication for Phase 7 |
|-----------|--------|-------------------------|
| Address Leo at start of any response | CLAUDE.md §0 | All `/gsd-*` agents must comply; researcher already does |
| Plan-first for non-trivial tasks | CLAUDE.md §1 | Phase 7 has 7 STP requirements + ≥10 tests → planner must produce wave-level plan |
| Self-improvement loop after corrections | CLAUDE.md §3 | If Phase 7 lands and Pitfall 8/9 manifests, update `tasks/lessons.md` |
| Verification before done | CLAUDE.md §4 | D-198's 8-clause acceptance gate is the verification; no shortcut to "done" |
| Demand elegance (balanced) | CLAUDE.md §5 | Reuse `query_gpus()` pattern (OQ-1) rather than duplicate; reuse port-variant idempotency (Pattern 3) |
| Simplicity first | CLAUDE.md "Core Principles" | Zero new deps for Phase 7 (per External Dependencies §) |
| No backwards-compatibility hacks | CLAUDE.md (paraphrased; Phase 6 D-168 precedent) | Backend ABC adds abstract method; subclasses without impl raise; bump to 7.0.0 |
| Skills only for autonomous setup; CLI for runtime triggers | `feedback_skills_vs_cli` | `/automil-setup` is the ONLY new skill; everything else is CLI subcommand |
| autoMIL is generic, autobench is one consumer | `project_automil_is_generic` | Phase 7 contributions live in `src/automil/`, NOT `benchmarks/`; healthcheck has zero autobench knowledge |
| Multi-runtime agent support is in scope | `project_multi_runtime_agents` | STP-07 ships overlays for claude + codex + opencode + deepseek; not "claude-only" |
| Decide engineering, ask features | `feedback_decide_engineering_ask_features` | All 10 D-189..D-198 decisions auto-bootstrapped; no Leo questions during planning |
| Paper-campaign values ≠ framework constants | `feedback_paper_campaign_vs_framework` | `default_vram_estimate_gb` is computed (quantile_95 or conservative), NEVER hardcoded |
| No em dashes | `feedback_no_em_dashes` | All Phase 7 prose, comments, docstrings use periods/commas/and; never em-dashes |

**The em-dash directive applies to Phase 7's skill content too.** The current `_shared/skills/automil-setup/SKILL.md` (122 lines) appears clean on review; Phase 7's expanded content must remain so.

---

## Common Pitfalls

### Pitfall A: Re-implementing nvidia-smi parsing

**What goes wrong:** `LocalBackend.healthcheck()` reinvents the subprocess + CSV parse loop already at `_orchestrator_daemon.py:248-272`.

**How to avoid:** Either reuse `query_gpus()` directly (lift its 4-tuple results into `HealthReport`'s 2-tuple), OR factor out a shared `_query_nvidia_smi(query_string: str)` helper. The planner picks the minimum-disruption path.

**Warning sign:** Three `subprocess.run([NVIDIA_SMI_PATH, ...])` calls now appear in three different files (`cli/check.py`, `_orchestrator_daemon.py`, `backends/local.py`). Tests pass, but a future driver change requires three patches.

### Pitfall B: PyYAML round-trip strips comments → idempotency false-positives

**What goes wrong:** Skill's idempotency check parses existing config.yaml via `yaml.safe_load`, dumps via `yaml.safe_dump`, diffs the textual representations. Comments in the original (e.g., `cap:  # 6h budget per cell`) are stripped; the diff says "comment removed" on every run.

**How to avoid:** OQ-4's value-tree diff (parse → `pprint` → `difflib`). Don't compare textual YAML; compare parsed dict structures.

**Warning sign:** Idempotency test passes, but Leo runs `/automil-setup` on a real repo with hand-edited comments and gets prompted on every run.

### Pitfall C: `automil submit --timeout 1` ≠ `automil submit --max-time 60`

**What goes wrong:** The skill body says `automil submit --max-time 60` per D-195. If we don't add the flag (OQ-5), the skill must say `automil submit --timeout 1` instead, readers ask "1 what?" and the skill drifts.

**How to avoid:** Add `--max-time SECONDS` flag in Wave 1 (OQ-5 patch).

**Warning sign:** Skill instructions diverge from spec; reviewers question whether the gate actually runs at the documented time budget.

### Pitfall D: Codex frontmatter accidentally rendered

**What goes wrong:** `_overlay.py` returns `_shared/SKILL.md` verbatim for runtimes without overlay overrides. Codex install path (`init.py:153-166`) writes to `.codex/instructions.md`, Codex accepts this fine but the rendered file has a `---` block at top that Codex either silently ignores or warns about.

**How to avoid:** Either (a) ship `agent_assets/codex/skills/automil-setup/SKILL.md` as a deliberate empty-frontmatter overlay, OR (b) extend `_overlay.py` with a runtime-specific frontmatter strip. Recommendation: option (a), runtime-agnostic merger preserved.

**Warning sign:** Codex skill activation logs show "ignoring unknown YAML directive `name:`" or similar.

### Pitfall E: Skill detects entry point incorrectly on monorepo

**What goes wrong:** D-193's heuristic 1 globs `train.py | main.py | run.py | training/*.py | scripts/train*.py`. On a monorepo with two trainable packages (e.g., autoMIL itself: `src/automil/` AND `benchmarks/src/autobench/`), multiple matches surface. The skill MUST ask. If it picks the first match, every monorepo onboarding mis-scaffolds.

**How to avoid:** D-193 is explicit: "If multiple, ask user to pick." Test `test_skill_asks_on_multiple_train_py_candidates` (Pitfall 9 anti-acceptance #2) defends this.

**Warning sign:** Skill produces a config pointing at a `train.py` that the user did not intend.

### Pitfall F: ROCm parsing assumed CSV; format unstable across versions

**What goes wrong:** Per WebSearch (`rocm-blogs/blogs/software-tools-optimization/amd-smi-overview/`), ROCm-SMI's JSON output is "not perfectly homogeneous and is possibly changing". CSV is more stable but field count varies across ROCm 5 → 6 → 7.

**How to avoid:** Wrap ROCm parsing in a permissive `try: ... except (ValueError, KeyError, IndexError): return ([], "rocm-smi output format unrecognized")` block. ROCm fallback is best-effort per D-190.

**Warning sign:** A user with AMD hardware reports `detection_status="failed"` but expects ROCm support.

### Pitfall G: HealthReport leaked to trajectory recorder

**What goes wrong:** Phase 3 trajectory recorder captures all CLI invocations + JSON payloads. If `automil init`'s output is captured, HealthReport flows through into trajectory JSONL. Combination of `(gpu_count, gpu_vram_gb, python_version, automil_version, detected_at)` uniquely fingerprints Leo's machine across published trajectories.

**How to avoid:** Add docstring annotation on `HealthReport`: "Do not serialize into trajectory output." Add unit test that greps trajectory output (when traced) for `HealthReport` substring; should be zero matches.

**Warning sign:** Published trajectories contain machine-specific fingerprint data.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded `MAX_CONCURRENT_PER_GPU = 8` constant | Stamp from healthcheck + recompute from `quantile_95(peak_vram_mb)` | Phase 7 (this) | Pitfall 8 anti-acceptance; portability across hardware shapes |
| Setup is one-shot autonomous skill | Setup is interactive at every ambiguity, with dry-run gate before "done" | Phase 7 (this) | Pitfall 9 anti-acceptance; honest about uncertainty |
| Per-runtime skills hand-maintained | `_shared/` canonical + `_overlay.py` build to runtime overlays | Phase 3 D-79 (already shipped) | Skill content edited once, propagates to 4 runtimes |
| `nvidia-smi` invoked via bare PATH | Path-pinned via `shutil.which` resolved at module import | Phase 4 CLN-05 (already shipped) | PATH-shim spoofing defense; reused by Phase 7 healthcheck |

**Deprecated/outdated:**

- `--query-gpu --format=csv,noheader` without `nounits`, returns "MiB" suffix in values; current pattern includes `nounits` to get bare numbers.
- ROCm-SMI `--showmeminfo vram --json`, per WebSearch, format is unstable across ROCm versions; `--csv` is preferred for parsing.
- `Backend.healthcheck()` with optional default impl, D-189 makes it abstract (breaking on subclasses). Distributed backends raise `NotImplementedError` deliberately.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `results.tsv` column for peak VRAM is named `peak_vram_mb` | OQ-2 | Empirical VRAM feedback test fails to find the column; conservative default always used. **Mitigation:** read `cli/reconcile.py` during planning to confirm exact column name. |
| A2 | Phase 3 trajectory redactor's deny-list is in `src/automil/trajectory/redactor.py` | OQ-6 | If the redactor lives elsewhere, the path annotation is misdirected. **Mitigation:** grep for redactor files during planning; update annotation before write. |
| A3 | Codex CLI accepts `.codex/instructions.md` plain markdown without YAML frontmatter | Pattern 4, Pitfall D | If Codex 2026 versions later require frontmatter, the empty-frontmatter overlay path breaks. **Mitigation:** test propagation explicitly in `test_overlay_propagation_phase7.py`. |
| A4 | DeepSeek format follows OpenCode skill format (lazy-loaded SKILL.md with YAML frontmatter) | Pattern 4 | If DeepSeek adopts a divergent skill spec, deepseek/automil-setup/SKILL.md needs custom rendering. **Mitigation:** DeepSeek runtime is shipped via opencode/codex base per `cli/init.py:168-171`; this is already opencode-shaped. Risk LOW. |
| A5 | NumPy is installed (transitively via `torch>=2.10`) on every install path | OQ-2, External Deps | If `torch` install fails silently, `numpy` may be absent. **Mitigation:** add `import numpy` in `init.py` lazily; fallback to `statistics.quantiles(values, n=20)[18]` (the 95th percentile via stdlib). |

**If this table grows during planning, planner must surface to Leo as feature questions, not engineering questions.**

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `nvidia-smi` | LocalBackend.healthcheck CUDA probe | ✓ (Leo's workstation) | 545+ assumed | None on missing, fall through to ROCm |
| `rocm-smi` | LocalBackend.healthcheck ROCm probe | ✗ (CUDA-only host) | n/a | Fall through to CPU-only HealthReport |
| `python>=3.10` | All Phase 7 code | ✓ | 3.11.9 (current shell) | None, pyproject.toml requires 3.10 |
| `pyyaml>=6.0` | OQ-4 value-tree diff | ✓ | 6.0.1 | n/a |
| `numpy` | OQ-2 quantile_95 | ✓ (transitive via torch) | 2.2.6+ | `statistics.quantiles` stdlib fallback |
| `git` | tmp_git_repo fixture | ✓ | system git | None, required for all framework tests |
| `pytest>=9.0.2` | All test patterns | ✓ | 9.0.2+ | n/a |

**Missing dependencies with no fallback:** None for Phase 7's single-shape (CUDA workstation) verification.

**Missing dependencies with fallback:**

- `rocm-smi`: not present on Leo's CUDA workstation; ROCm tests use `subprocess.run` mocking. External-hardware ROCm verification deferred per D-197.
- External-hardware test runners (single-GPU laptop, H100, ROCm box): unavailable; portability documented as MEDIUM per D-197 / D-198.

---

## Sources

### Primary (HIGH confidence)

- **In-tree code (verified by Read):**
  - `src/automil/backends/base.py:113-167`, Backend ABC; placeholder comment for healthcheck at line 117
  - `src/automil/backends/_orchestrator_daemon.py:71-87`, NVIDIA_SMI_PATH resolution
  - `src/automil/backends/_orchestrator_daemon.py:240-272`, query_gpus() reusable helper
  - `src/automil/cli/check.py:147-196`, existing nvidia-smi invocation pattern + NVIDIA_SMI_PATH consumer
  - `src/automil/cli/init.py:195-301`, init command extension point (line 213 = guard, line 247 = render)
  - `src/automil/cli/submit.py:24,332`, existing `--timeout` flag and timeout_min field
  - `src/automil/cli/lifecycle/port_variant.py:254-269`, idempotency-via-node-id-match precedent
  - `src/automil/agent_assets/_overlay.py:42-95`, H2 section-replacement merge algorithm
  - `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md`, current 122-line skeleton
  - `pyproject.toml:1-50`, dep audit (no ruamel/deepdiff/dictdiffer)
  - `.planning/research/PITFALLS.md:224-285`, Pitfall 8 + 9 verbatim mitigations
- **CLAUDE.md**, workflow + standing directives
- **CONTEXT.md (this phase)**, D-189..D-198 locked decisions

### Secondary (MEDIUM confidence, WebSearch verified with official source)

- **NVIDIA documentation**, [nvidia-smi reference](https://docs.nvidia.com/deploy/nvidia-smi/) covers `--query-gpu`, ECC reservation, MIG limitations.
- **AMD ROCm documentation**, [Getting to Know Your GPU: A Deep Dive into AMD SMI](https://rocm.blogs.amd.com/software-tools-optimization/amd-smi-overview/README.html); [ROCm SMI CLI reference](https://rocm.docs.amd.com/projects/rocm_smi_lib/en/latest/), JSON format unstable across versions; CSV preferred.
- **Anthropic Claude Code docs**, [Extend Claude with skills](https://code.claude.com/docs/en/skills); [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices); [skill-creator example](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md). YAML frontmatter required `name` + `description`; optional `allowed-tools`, `disable-model-invocation`, `agent`, `license`.
- **OpenAI Codex docs**, [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md); [Agent Skills](https://developers.openai.com/codex/skills). AGENTS.md uses plain markdown (no frontmatter); SKILL.md format follows the Skills standard with frontmatter.
- **OpenCode docs**, [Agent Skills](https://opencode.ai/docs/skills/); [Specification](https://agentskills.io/specification). YAML frontmatter required (name + description ≥20 chars); markdown body unrestricted.

### Tertiary (LOW confidence, flagged for validation in planning)

- **DeepSeek skill format**, no canonical doc found via search; assumed to follow OpenCode/Codex base via `init.py:168-171` deepseek-via-opencode / deepseek-via-codex routing. Marked Assumption A4.

---

## Planner Implementation Hints

This section maps each Phase 7 success criterion to a recommended file + class + method skeleton. The planner can use these as the seed for wave-level task breakdowns.

### Success Criterion 1, `LocalBackend.healthcheck()` with 6 unit tests

**File:** `src/automil/backends/base.py`

```python
# Add at end of base.py, after existing JobSpec/JobHandle/Backend definitions:

@dataclass(frozen=True)
class HealthReport:
    """Immutable hardware-detection report (D-189). See OQ-1, OQ-6.

    DO NOT serialize into trajectory output until redaction policy reviewed
    (see CONTEXT.md deferred-ideas).
    """
    gpu_count: int
    gpu_vram_gb: tuple[float, ...]
    accelerator: Literal["cuda", "rocm", "cpu"]
    python_version: str
    automil_version: str
    detection_status: Literal["ok", "partial", "failed"]
    detection_warnings: tuple[str, ...]
    detected_at: datetime


class Backend(ABC):
    # ... existing 5 abstract methods unchanged ...

    @abstractmethod
    def healthcheck(self) -> HealthReport:
        """Probe hardware and return a report (D-189 / STP-01).

        Distributed backends (SLURM, Ray) MUST raise NotImplementedError with
        the message: "healthcheck deferred to Phase 7+ for distributed backends".
        """
```

**File:** `src/automil/backends/local.py`

```python
def healthcheck(self) -> HealthReport:
    """LocalBackend hardware probe (D-189 / STP-01).

    Probe order CUDA -> ROCm -> CPU per D-190. Returns HealthReport regardless
    of probe success; detection_status surfaces partial/failed cases for
    init.py to branch on (D-191).
    """
    # ... 50 lines: probe CUDA via NVIDIA_SMI_PATH; on returncode != 0,
    # try ROCm via rocm-smi --showmeminfo vram --csv; on missing, return CPU-only.
    # Detect partial via per-line parse failures.
```

**File:** `src/automil/backends/slurm.py` + `ray.py`

```python
def healthcheck(self) -> HealthReport:
    raise NotImplementedError(
        "healthcheck deferred to Phase 7+ for distributed backends "
        "(use `salloc`/`ray status` directly)"
    )
```

**File:** `tests/backends/test_local_healthcheck.py` (new), 6 tests per Test Pattern A.

### Success Criterion 2, `automil init` healthcheck integration

**File:** `src/automil/cli/init.py`

```python
# Insert between line 213 (--update guard) and line 247 (template render).
# New helper:
def _stamp_healthcheck_defaults(
    automil_dir: Path,
    report: HealthReport,
    no_healthcheck: bool = False,
) -> dict:
    """Compute config defaults from HealthReport per D-191. Returns context dict
    for Jinja2 template render. See OQ-2 for empirical VRAM feedback path.
    """
    if no_healthcheck:
        return {"max_concurrent_per_gpu": 4, "default_vram_estimate_gb": 8.0}
    # ... read results.tsv if present; quantile_95 if >=10 samples ...
    # ... else max(8.0, min(gpu_vram_gb) / 8.0) ...

# Add new --no-healthcheck flag for CI:
@click.option("--no-healthcheck", is_flag=True, default=False,
              help="Skip hardware probe (CI / smoke-test path).")

# In init() body, after line 213's --update guard:
if not no_healthcheck:
    from automil.backends.local import LocalBackend
    report = LocalBackend().healthcheck()
    click.echo(_format_health_report(report))
    if report.detection_status == "failed":
        if not click.confirm("Detection failed; use conservative defaults?",
                             default=False):
            raise click.ClickException(
                "Aborted. Run `automil check --healthcheck` for details."
            )
    context.update(_stamp_healthcheck_defaults(automil_dir, report, no_healthcheck))
```

**File:** `tests/cli/test_init_healthcheck.py` (new), 5 integration tests.

### Success Criterion 3, Detect-and-warn pattern (STP-03)

Already covered by Success Criterion 2, `click.confirm` on `failed` status, never silent fallback. The `_format_health_report()` helper (~20 lines) renders all `detection_warnings` to stdout regardless of status.

### Success Criterion 4, `/automil-setup` skill content (STP-04)

**File:** `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md`

Expand from 122 lines to ~250 lines. Sections (each an H2 to interop with `_overlay.py`):

1. `## Architecture` (existing, unchanged)
2. `## Steps` (expanded per D-193 inspection heuristics)
3. `## Inspection Heuristics` (NEW, codify D-193 priority order)
4. `## Drafting Conventions` (NEW, what config.yaml/program.md/variants/ skeleton look like)
5. `## Idempotency Protocol` (NEW, three-way diff per D-194; user prompt format)
6. `## Setup-Done Gate` (NEW, `automil check && automil submit --max-time 60` per D-195)
7. `## Failure Modes` (NEW, Pitfall 9 mitigations 1-6; what to do when ambiguous; CLI fallbacks)

**File:** `src/automil/agent_assets/codex/skills/automil-setup/SKILL.md` (NEW)

Codex overlay with no YAML frontmatter (`---` block omitted) per Pattern 4 / Pitfall D.

**File:** `src/automil/agent_assets/_overlay.py`

No changes needed, existing H2 section-replacement merge handles the new sections automatically.

**File:** `tests/skills/test_setup_scaffold.py` (new), STP-04 integration test (skill-CLI proxy).

### Success Criterion 5, Idempotency (STP-05)

**Per OQ-4, no new code module needed.** The skill's instruction body (`SKILL.md` Step `## Idempotency Protocol`) describes the three-way diff approach using `pyyaml + pprint + difflib`. The agent (Claude Code, Codex, etc.) reads the instructions and uses its built-in tools (Read, Bash, Edit) to execute the protocol.

**File:** `tests/skills/test_setup_idempotency.py` (new), load-bearing test for D-198 clause 4.

### Success Criterion 6, Setup-done gate (STP-06)

**File:** `src/automil/cli/submit.py`

Add `--max-time SECONDS` flag per OQ-5:

```python
@click.option("--max-time", "max_time_seconds", type=int, default=None,
              help="Override --timeout with seconds-precision (rounded up to 1 min minimum).")
def submit(..., max_time_seconds: int | None):
    if max_time_seconds is not None:
        timeout = max(1, (max_time_seconds + 59) // 60)
```

**File:** `tests/cli/test_submit_max_time.py` (new), 3 unit tests for the flag.

**Skill body:** the `## Setup-Done Gate` section in SKILL.md instructs:

```bash
# Required by D-195. Runs check; if exit 0, runs 60-second submit + polls.
automil check || { echo "Setup gate failed at automil check; abort."; exit 1; }
automil submit --node node_setup_validation --desc "setup-validation" --files <minimal> --max-time 60
# Poll until terminal:
for i in {1..18}; do  # 18 * 5s = 90s budget per D-195
    sleep 5
    automil status | grep -q "node_setup_validation.*\(executed\|crashed\)" && break
done
automil status | grep -q "node_setup_validation.*executed" || {
    echo "Setup gate failed at dry-run; abort."; exit 1;
}
echo "Setup complete. Run /automil to begin experimentation."
```

**File:** `tests/skills/test_setup_dry_run_gate.py` (new), load-bearing test for D-198 clause 5.

### Success Criterion 7, Per-runtime overlays (STP-07)

**File rebuild:** running the existing `_overlay.py` build pipeline propagates `_shared/automil-setup/SKILL.md` content to the four runtimes via `cli/init.py:_install_runtime_assets`.

Phase 7 only edits `_shared/automil-setup/SKILL.md` (Success Criterion 4) plus adds `codex/skills/automil-setup/SKILL.md` for the empty-frontmatter case. No changes to `_overlay.py` itself.

**File:** `tests/agent_assets/test_overlay_propagation_phase7.py` (new), verifies all 4 runtimes (claude, codex, opencode, deepseek-via-{opencode,codex}) receive the updated content.

---

## Metadata

**Confidence breakdown:**

- **Standard stack (zero new deps):** HIGH, verified pyproject.toml; reuse stdlib + existing core deps.
- **Architecture (Backend ABC extension):** HIGH, pattern matches Phase 2 D-53 frozen-dataclass + Phase 6 D-189 raises-NotImplementedError-for-distributed precedent.
- **Pitfalls (Pitfall 8 + 9 anti-acceptance):** HIGH, sourced from `.planning/research/PITFALLS.md` verbatim; 7 + 7 mitigations mapped to specific tests.
- **Skill format conventions per runtime:** HIGH for Claude/OpenCode/Codex (verified via WebSearch + official docs); MEDIUM for DeepSeek (Assumption A4; risk LOW because deepseek routes via opencode/codex base).
- **`results.tsv` column name:** MEDIUM, Assumption A1; planner confirms during read of `cli/reconcile.py`.
- **Telemetry redaction policy:** DEFERRED per CONTEXT.md; documented as 1-line annotation in HealthReport docstring.

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (30 days for stable stdlib/in-tree concerns; sooner if Anthropic ships a SKILL.md format change).

---

*Research complete. Planner can now create PLAN.md files for Phase 7 wave decomposition.*
