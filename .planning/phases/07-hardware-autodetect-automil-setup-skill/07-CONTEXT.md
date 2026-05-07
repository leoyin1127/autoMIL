# Phase 7: Hardware autodetect + /automil-setup skill, Context

**Gathered:** 2026-05-07
**Status:** Ready for planning
**Mode:** Auto-bootstrapped (Leo's standing directive `feedback_decide_engineering_ask_features`: engineering decisions locked autonomously per production best-practice; only feature/user decisions go to Leo)

## Phase Boundary

Make autoMIL one-shot deployable onto an arbitrary user repo. Land:

1. `Backend.healthcheck()` ABC method (LocalBackend implementation reports detected hardware), STP-01.
2. `automil init` consumes healthcheck output, pre-fills config.yaml defaults, STP-02.
3. Hardware detect = report-not-decide; failures prompt operator override, STP-03.
4. `/automil-setup` skill drafts config + program.md + variants/ skeleton from repo inspection, STP-04.
5. Skill is idempotent (diff/update, never overwrite), STP-05.
6. Setup-done gate: mandatory `automil check` AND 1-min dry-run experiment both pass, STP-06.
7. Per-runtime overlays: `_shared/automil-setup/SKILL.md` canonical, claude/codex/opencode/deepseek overrides, STP-07.

**Out of scope:** SLURM/Ray Backend.healthcheck() (deferred to a future phase per Phase 6 deferred items); model selection AutoML; cluster-autodiscovery wizards; non-MIL training script support beyond contract-conformant scripts.

<decisions>
## Implementation Decisions

### D-189, `Backend.healthcheck()` ABC contract (STP-01)

`Backend.healthcheck() -> HealthReport` becomes a NEW abstract method on the Phase 2 Backend ABC. Adds to the contract; backwards-incompatibility on Backend impls is acceptable per CLAUDE.md "no backwards-compatibility hacks" + the milestone's pre-1.0 status. SLURM/Ray impls in Phase 6 raise `NotImplementedError("healthcheck deferred to Phase 7+ for distributed backends")`, they remain submit/poll/cancel/log_iter/list_running compliant.

`HealthReport` is a frozen dataclass:

```python
@dataclass(frozen=True)
class HealthReport:
    gpu_count: int                      # 0 if no GPUs
    gpu_vram_gb: tuple[float, ...]      # per-GPU VRAM in GB; () if no GPUs
    accelerator: Literal["cuda", "rocm", "cpu"]
    python_version: str                 # e.g. "3.11.9"
    automil_version: str                # importlib.metadata
    detection_status: Literal["ok", "partial", "failed"]
    detection_warnings: tuple[str, ...]  # human-readable warnings, never decisions
    detected_at: datetime
```

**Why dataclass not dict:** type-safety in CLI consumers; `frozen=True` matches Phase 2 D-53 immutability convention for ABC payloads.

**Why `detection_status` enum:** STP-03 requires the report to surface failure mode. CLI consumers branch on `failed` to prompt override, on `partial` to print warnings + accept, on `ok` to use silently.

### D-190, Detection probe order + fallback chain (STP-01, STP-03)

LocalBackend.healthcheck() probes in this order:

1. **CUDA**: `subprocess.run([NVIDIA_SMI_PATH, "--query-gpu=index,memory.total", "--format=csv,noheader,nounits"])` (CLN-05 path-pinned). Parse comma-separated MB → GB. If returncode != 0 OR output empty → fall through to ROCm.
2. **ROCm**: `subprocess.run(["rocm-smi", "--showmeminfo", "vram", "--csv"])`. Best-effort. If unavailable → fall through to CPU.
3. **CPU**: always succeeds. `gpu_count=0`, `gpu_vram_gb=()`, `accelerator="cpu"`.

**`detection_status` semantics:**
- `ok`: probe succeeded, all fields populated
- `partial`: probe partially succeeded (e.g. CUDA found but VRAM unparseable for some GPUs)
- `failed`: all probes failed AND user has env signal that GPU expected (e.g. `CUDA_VISIBLE_DEVICES` set but probe returned 0). On `failed`, populate the warning string and let CLI consumer decide whether to abort.

**Why CUDA-first not env-driven:** The Phase 4 CLN-05 work already pinned `nvidia-smi`; consistent with that. ROCm AMD detection is best-effort because Leo's workstations are CUDA-only, but the dispatch shape is in for forward-compat.

**Why no `--gpu-info` JSON parsing:** `nvidia-smi --query-gpu` is more stable across driver versions than the JSON output. Phase 0 already proved the CSV parsing path.

**Detection failures NEVER silently default.** `automil init` ALWAYS prints the report; on `failed`, prompts `[y/N]` to use conservative defaults (`max_concurrent_per_gpu=4`, `default_vram_estimate_gb=8.0`).

### D-191, `automil init` integration (STP-02, STP-03)

`automil init` extends current behavior:

1. After `--update` guard: call `LocalBackend().healthcheck()`.
2. Print HealthReport to stdout in human-readable format.
3. Use `quantile_95` of empirical VRAM observations from `results.tsv` (if present and ≥10 samples) for `default_vram_estimate_gb`. Otherwise: `min(gpu_vram_gb) / 8.0` as conservative concurrent-per-GPU divisor (STP-02 default).
4. On `detection_status == "failed"`: click.confirm("Detection failed; use conservative defaults? [y/N]"). If `n`: abort with non-zero exit and recovery instructions.
5. Stamp the rendered values into config.yaml as defaults (NOT comments, comments don't drive runtime; values do).

**Why stamp-not-comment:** STP-02 says "pre-fills defaults", the operator can edit afterwards. Leaving them as comments forces them to know undocumented runtime defaults.

**Why click.confirm not click.prompt:** Binary choice (continue or abort); STP-03 forbids silent fallback.

### D-192, Skill scope (STP-04)

`/automil-setup` skill drafts EXACTLY these artifacts:

| Artifact | Source |
|----------|--------|
| `automil/config.yaml` | Healthcheck + repo-inspection (training script path, env vars detected) |
| `automil/program.md` | Repo-inspection summary: training entry point, what it does, where logs land |
| `automil/variants/` (skeleton) | One starter variant per discovered model class, marked `# TODO: implement` |

**Skill does NOT:**
- Run experiments (that's `submit` / orchestrator territory)
- Choose hyperparameters (that's the agent loop's job)
- Modify the training script itself (that's `port-variant` / `apply` territory in Phase 1)

**Why one starter variant per model class, not full variants/{model_class}_v0/{loss}_v0/{policy}_v0:** Forces the user-agent to discover the variant lattice via interactive search rather than pre-bake. Matches Phase 1 D-49 "framework-only scope; CCRCC port deferred to consumer follow-up."

### D-193, Skill repo inspection logic (STP-04)

Inspection heuristics (in priority order):

1. **Training script discovery:** glob for `train.py | main.py | run.py | training/*.py | scripts/train*.py`. If multiple, ask user to pick.
2. **Framework detection:** read first 50 lines of training script; grep for `import torch | import tensorflow | import jax | import sklearn | import lightning`. Report detected framework; if none, mark "framework: unknown" and proceed.
3. **Model class detection:** AST-walk training script + import sources; look for `nn.Module` subclasses (torch) / `tf.keras.Model` subclasses (tf) / `BaseEstimator` subclasses (sklearn). If multiple, ask user to pick.
4. **Env-var detection:** grep training script + entry-point modules for `os.environ.get(...)` / `os.environ[...]`. List discovered keys; ask user which are required.
5. **Result-file detection:** does the script write `result.json`? If not, mark "result.json adapter required" and emit an example adapter snippet in `program.md`.

**Skill is interactive, user confirms at every ambiguous decision.** Unambiguous = single match across heuristic. Ambiguous = multiple matches OR no matches (in which case user provides).

### D-194, Idempotency: diff-update mechanism (STP-05)

Re-running `/automil-setup` on an already-initialised project:

1. Detect existing files; if `automil/config.yaml` present → load it.
2. Re-run inspection independently.
3. Compute three-way per-section diff: `existing | drafted | merged`.
4. For each non-trivial diff (excluding whitespace + comment-only changes), present unified diff and ask: `overwrite | keep existing | merge interactively`.
5. Never silently overwrite. Never silently skip.

**Why three-way:** preserves user edits while surfacing newly-detected items. E.g., if user added a `gates.K=5` value and rerun would suggest `gates.K=8`, the diff is shown; not silent overwrite.

### D-195, Setup-done gate (STP-06)

After all artifacts written, skill runs:

1. `automil check` (must exit 0; on failure, surface specific failures and abort)
2. `automil submit --node root --desc "setup-validation" --files <minimal> --max-time 60` followed by orchestrator polling until terminal, must reach `executed` (not `crashed`) within 90s wall-clock.

Both must pass before the skill prints `Setup complete. Run /automil to begin experimentation.`

**Why submit-not-dry-run:** `submit` exercises the actual write-result-json + reconcile + composite-scoring path. A dry-run that doesn't hit those code paths would let bad scripts ship. This is the same rationale as Phase 1 D-49's reproduction sanity check.

**Why 60s training cap:** the goal is to validate end-to-end plumbing, not converge a model. Use minimal fold count (1) + minimal data subset. The training script's responsibility to honor `--max-time`; if it can't, the skill emits a warning before submit.

### D-196, Per-runtime overlay strategy (STP-07)

Phase 3 already shipped `agent_assets/{_shared, claude, codex, opencode, deepseek}/skills/automil-setup/SKILL.md` skeleton. Phase 7 fills the canonical content in `_shared/` and per-runtime frontmatter in the four overlay dirs:

- `_shared/automil-setup/SKILL.md`: canonical narrative, runtime-agnostic. ALL behavioral content lives here.
- `claude/automil-setup/SKILL.md`: thin wrapper with Claude-specific frontmatter (`name`, `description`, optional `tools` allowlist) + `@_shared/automil-setup/SKILL.md` include. Maintained by `_overlay.py` build.
- `codex/automil-setup/instructions.md`: Codex format (no frontmatter; plain markdown intro + body include).
- `opencode/automil-setup/SKILL.md`: OpenCode format.
- `deepseek/automil-setup/SKILL.md`: DeepSeek format (TBD format; placeholder if format unstable).

`_overlay.py` already generates the runtime-specific overlays from `_shared/` at install time. Phase 7 only edits `_shared/` content; rebuild propagates.

**Phase 6 deferred Backend.healthcheck() for SLURM/Ray**, for those backends, healthcheck raises `NotImplementedError("healthcheck deferred for distributed backends, use `salloc`/`ray status` directly").

### D-197, Hardware test matrix (STP-07)

Per Leo's standing memory and ROADMAP "OR portability is documented as MEDIUM": ship with **single-shape verification** on Leo's 3-GPU workstation. Document portability as MEDIUM with override path explicit.

Test matrix:
- ✓ 3-GPU CUDA workstation (Leo's primary, available now)
- ⏭ Single-GPU laptop (deferred, borrow opportunity OR mark as untested)
- ⏭ External hardware shape (CPU-only AND/OR ROCm), deferred behind `@pytest.mark.requires_external_hardware`

Healthcheck unit tests cover failure-mode branching via subprocess mocking on all CI runners.

### D-198, Acceptance gate (Phase 7 success)

Phase 7 ships when ALL of these are TRUE:

1. `Backend.healthcheck()` ABC method exists; LocalBackend.healthcheck() implementation passes 6 unit tests covering: cuda-3-gpu happy path, cuda-no-gpus, rocm fallback, cpu fallback, partial-detection (1 GPU detected, 1 GPU CSV unparseable), full-failure-prompts-override.
2. `automil init` calls healthcheck; new --no-healthcheck flag for CI; integration test verifies stamped config values match HealthReport.
3. `_shared/automil-setup/SKILL.md` updated with the D-189..D-196 narrative; `_overlay.py` rebuild propagates to claude/codex/opencode/deepseek overlay dirs identically modulo frontmatter.
4. `tests/skills/test_setup_idempotency.py` runs `/automil-setup` twice on a tmp project, asserts second run produces zero unprompted changes.
5. Setup-done gate test (`tests/skills/test_setup_dry_run_gate.py`) demos a known-bad config fails the dry-run gate; skill aborts.
6. Phase 6's 798-test baseline preserved (no regressions); ≥10 new tests added for STP-01..07.
7. CHANGELOG entry: 7.0.0 if Backend.healthcheck() is BREAKING (it is; raises on subclasses without impl), else 6.1.0.
8. `automil check` passes on Leo's workstation with healthcheck integrated.

</decisions>

<code_context>
## Existing Code Insights

**Already in tree (Phase 0-6):**
- `src/automil/backends/base.py` line 117 has the placeholder comment: "Phase 7 will add an optional `healthcheck()` method"
- `src/automil/cli/check.py` already invokes `nvidia-smi` (lines 149-158), Phase 7 healthcheck reuses NVIDIA_SMI_PATH constant + same subprocess pattern (don't duplicate)
- `src/automil/orchestrator.py` line 25 references NVIDIA_SMI_PATH module-level constant (CLN-05)
- `src/automil/cli/init.py` is 300 lines; line 195 is the `init` command. Phase 7 hooks healthcheck call between `--update` guard (line 213) and config rendering (line 276)
- `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md` is 122 lines from Phase 3, Phase 7 expands content; structure stays
- `src/automil/agent_assets/_overlay.py` propagates `_shared/` to per-runtime dirs at build time (Phase 3 D-79)
- `.claude/skills/automil-setup/SKILL.md` is the user-installed Claude overlay; Phase 7 doesn't touch it directly (regenerated from _shared)

**Reusable assets:**
- NVIDIA_SMI_PATH constant (CLN-05 path-pinned)
- HealthReport ↔ pattern of frozen dataclass-with-detection-status, model on Phase 2 `JobSpec`/`JobHandle`
- Idempotency-via-diff pattern, model on Phase 1 `automil port-variant` (which already does idempotent variant porting)
- subprocess.run-with-stdout-parsing, model on existing `cli/check.py` nvidia-smi block

**Integration points:**
- `Backend` ABC in `backends/base.py`, adds new abstract method
- `cli/init.py`, extends `init()` function with healthcheck call
- `cli/check.py`, extends with new `--healthcheck` subcommand surfacing detail
- `tests/backends/test_backend_contract.py`, extends contract test with healthcheck-required subset
- `agent_assets/_shared/skills/automil-setup/SKILL.md`, content rewrite

</code_context>

<specifics>
## Specific Ideas

- **Conservative VRAM defaults** when `results.tsv` is empty: `default_vram_estimate_gb = max(8.0, min(gpu_vram_gb) / 8.0)`. Empirical 8GB CLAM-MB per-fold (per autoMIL-paper observations), not hardcoded; just the floor.
- **Setup skill should not modify `.gitignore`**, that's the user's repo concern; `automil init` already adds runtime dirs.
- **Mandatory env-var validation in setup-done gate**, if skill detected `os.environ["AUTOBENCH_X"]` references in the training script, `automil check` validates those keys are declared in `config.yaml: env.required` AND present at runtime. (DEC-04 hook from Phase 8.)
- **Hardware report integration with `automil status`**, show `automil status --health` summary in viz dashboard header (deferred to Phase 8 viz polish; out of scope here).

</specifics>

<deferred>
## Deferred Ideas

- **SLURM Backend.healthcheck()**, surfaces `salloc` / `sinfo` / partition availability. Defers to a post-v1.0 phase; Phase 7 implementations raise `NotImplementedError`.
- **Ray Backend.healthcheck()**, surfaces `ray status` cluster-resource map. Same deferral.
- **External-hardware test matrix**, single-GPU laptop + CPU-only + ROCm shapes. Documented as MEDIUM portability per ROADMAP success criterion 5; deferred behind `@pytest.mark.requires_external_hardware`.
- **`automil init --slurm` cluster autodiscovery wizard**, interactive tour of partition / qos / account. Behind a separate later issue.
- **Skill auto-detection of CCRCC-style model lattice (mb/sb × ce/ce_smooth × sam/no-sam)**, out of scope; Phase 1 D-50 deferred consumer-side variant porting.
- **AutoML hyperparameter selection in the skill**, explicit non-goal. The agent loop chooses.
- **Multi-language training script support** (R, Julia), autobench is Python-only; future consumer-driven phase.
- **Telemetry export of healthcheck → trajectory recorder**, could leak hardware fingerprint; deferred for redaction policy review.

</deferred>
