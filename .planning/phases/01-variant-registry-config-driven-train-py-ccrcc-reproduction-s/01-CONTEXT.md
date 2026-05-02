# Phase 1: Variant registry + config-driven train.py + CCRCC reproduction sanity - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning
**Mode:** Engineering decisions locked per production best practice (Leo's directive 2026-05-02 — "decide engineering questions yourself; ask only user/feature questions"). All decisions below are technical implementation choices, not feature/UX questions.

<domain>
## Phase Boundary

Establish the registry — the single piece of structural infrastructure that everything else in the milestone depends on. After Phase 1:

1. Architectural / loss / training-policy mutations live as **committed code modules** in `benchmarks/experiments/<dataset>/automil/variants/`, never as dirty edits to shared library files.
2. Shared library files (`benchmarks/lib/CLAM/`, baseline `benchmarks/src/autobench/pipeline/clam/train.py`) become read-only at the agent layer; `automil submit` hard-fails on overlays touching them.
3. The benchmark's `train.py` reads model class, loss class, and training policy from `automil/config.yaml` via the registry — variant selection by short name, no `args.X = literal` overrides remain in the architectural surface.
4. CCRCC's current dirty edits are ported to three registered variant modules with a manifest pinning `(parent_commit, composite, node_id)`.
5. The reproduction sanity gate is a CLI command (`automil verify-repro`) + committed manifest — clean checkout + registry path produces `node_0176`'s composite within ±0.005.
6. CLI lifecycle commands `apply`, `revert-baseline`, `port-variant`, `promote-variant`, `refresh-registry`, `check` (extended) are wired and tested.

**Hard floors:**
- Phase 0 baseline (108 tests + 5 Nyquist additions = 113 tests) stays green.
- Reproduction sanity is the acceptance gate — Phase 1 does not ship until `verify-repro` produces a committed manifest with composite within ±0.005 of `node_0176`'s recorded value (0.8074 from `benchmarks/experiments/ccrcc/automil/graph.json`).
- `grep -r "args\.\(model\|loss\|policy\)\s*=" benchmarks/src/autobench/pipeline/` returns zero matches for the architectural surface (training/inference hyperparameter overrides like `args.lr` are pragmatic-pass; see D-36).
- `src/automil/` remains autobench-free: registry, validators, and CLI commands take consumer-side paths via config, never hardcode `benchmarks/`.

**Wave-cadence target:** ~12 plans across 4–5 waves. Granularity stays `fine`. The big serial dependency is Wave 5 (CCRCC port → train.py refactor → reproduction sanity); everything before it parallelises across `files_modified` boundaries.

</domain>

<decisions>
## Implementation Decisions

> **Numbering:** D-21 onward continues from Phase 0's D-01..D-20. Each decision is a locked engineering choice; downstream agents (researcher, planner, executor) honour these verbatim.

### Variant ABC family (REG-01)

- **D-21:** Three sibling ABCs in `src/automil/registry/variants/` (NOT one polymorphic ABC). The single-`Variant`-with-optional-methods pattern violates the Liskov substitution principle (a `LossVariant` cannot satisfy `forward(features, coords) -> AggregatorOutput`) and would force consumer-side training code into runtime isinstance checks. Three ABCs with one shared `VariantSpec` is the production-grade interface segregation.
  - `ModelVariant(ABC)` — `forward(features: Tensor, coords: Optional[Tensor]) -> AggregatorOutput` (required); `instance_attention(features, coords) -> Tensor | None` (optional). Subclassed by per-parent variants under `variants/<parent>/`.
  - `LossVariant(ABC)` — `__call__(logits: Tensor, targets: Tensor, *, instance_logits=None, instance_labels=None) -> Tensor` (required). Parent-agnostic.
  - `PolicyVariant(ABC)` — `wrap_optimizer(opt: Optimizer) -> Optimizer` (required); `wrap_scheduler(sched) -> sched` (optional); `step(loss: Tensor, opt: Optimizer) -> None` (required, default delegates to opt.step()). Parent-agnostic.
- **D-22:** `VariantSpec` is a **frozen** `@dataclass(frozen=True)` in `src/automil/registry/spec.py`:
  ```python
  @dataclass(frozen=True)
  class VariantSpec:
      name: str                            # short name, e.g. "clam_mb_v0176"
      kind: Literal["model", "loss", "policy"]   # exhaustive over Phase 1 ABCs
      parent: Optional[str]                # only for kind="model"; None otherwise
      base_commit: str                     # short SHA of the parent's last clean commit
      composite: float                     # composite at port time
      node_id: str                         # source node in graph.json
      created_at: str                      # ISO-8601 UTC
      mutations: tuple[str, ...] = ()      # tuple of human-readable mutation descriptors
  ```
  Frozen because `VariantSpec` is a registry key and provenance record — accidental mutation must be impossible. Tuple (not list) for the same reason.
- **D-23:** `kind` taxonomy is **Phase 1 exhaustive** (`model | loss | policy`). The roadmap's broader 4-tuple (`architectural | recipe | training-policy | inference`) is REG-01 *forecasting* — `recipe` is a composition of (loss, policy, hyperparameters), and `inference` is a Phase 5+ concept (gate-time inference variants). Phase 1 ships with `Literal["model", "loss", "policy"]`; widening to a `Literal[...]` with `recipe` / `inference` is a Phase 5 / Phase 8 concern when those become real surfaces. **No `recipe` ABC in Phase 1.**
- **D-24:** `AggregatorOutput` is **not** introduced in Phase 1. CLAM's existing return shape (`logits, Y_prob, Y_hat, instance_dict`) is too parent-specific to lock as a framework type today, and dragging an `AggregatorOutput` dataclass through Phase 1 forces a benchmark-side rewrite that would be undone in Phase 8 when the second consumer (sklearn-iris) lands. Phase 1's `ModelVariant.forward` returns whatever the parent returns; the parent's wrapper (in `train.py`) is responsible for the conversion. Phase 8 (`DEC-03` `result.json` JSON-Schema) is the right place to formalise the framework-level output contract.

### Variant module layout (REG-02, REG-08)

- **D-25:** All variant modules live under `<consumer>/<dataset>/automil/variants/` with kind-specific subdirectories:
  ```
  benchmarks/experiments/ccrcc/automil/variants/
    clam_mb/                     # ModelVariant — per-parent subdirectory
      __init__.py                # auto-generated by `automil refresh-registry`
      clam_mb_v0176.py
    _losses/                     # LossVariant — parent-agnostic, leading underscore signals "shared"
      __init__.py                # auto-generated
      ce_smooth008.py
    _policies/                   # PolicyVariant — parent-agnostic
      __init__.py                # auto-generated
      sam_lookahead.py
  ```
  This **deviates from REG-08's literal text** which named `losses/variants/ce_smooth008.py` and `training/policies/sam_lookahead.py` as siblings of `variants/`. The flat-with-kind-subdirs structure is cleaner for three reasons: (1) one root for `automil refresh-registry` to scan instead of three; (2) underscore-prefixed `_losses` / `_policies` follows Python convention for "shared infrastructure" subpackages; (3) symmetry with `variants/<parent>/` keeps the layout learnable. **Deviation documented in DISCUSSION-LOG.md; planner honours this layout, not REG-08's text.**
- **D-26:** Each variant module is a **single `.py` file**, NOT a package. Multiple files per variant is a refactor smell — if the variant is large enough to split, it's two variants. Header docstring is mandatory and follows the schema:
  ```python
  """<one-line description>.

  Parent: <parent_name>          # for ModelVariant only
  Base commit: <short SHA>
  Composite: <float>
  Node ID: <node_xxxx>
  Mutations: <comma-separated list>
  """
  ```
  Manifest is a sibling JSON file (D-44).

### Registry singleton + `@register` decorator (REG-02, CLI-08)

- **D-27:** `Registry` is a **module-level singleton** in `src/automil/registry/__init__.py`. Three keyed dicts: `MODEL_VARIANTS`, `LOSS_VARIANTS`, `POLICY_VARIANTS`. Population is via `@register(VariantSpec(...))` decorator on the class definition. The decorator validates the spec at import time, asserts uniqueness of `(kind, name)`, and inserts.
- **D-28:** `importlib.metadata.entry_points` cross-project discovery is **deferred to Phase 7 / `STP-04`**. Phase 1 ships in-process discovery only — `automil refresh-registry` does `pkgutil.iter_modules` over `<consumer>/<dataset>/automil/variants/` and `importlib.import_module` on each, which triggers the `@register` decorator as a side-effect. Reasoning: entry_points become useful when third-party variant packages are pip-installable (Phase 7's setup-skill scope). Adding entry_points support in Phase 1 ships infrastructure with no consumer.
- **D-29:** `automil refresh-registry` regenerates per-directory `__init__.py` files with **imports-only**, NOT a hardcoded dict:
  ```python
  # AUTO-GENERATED by `automil refresh-registry` at <ISO-8601>. DO NOT EDIT.
  # Re-run the command after adding or renaming a variant module.
  from . import clam_mb_v0176  # noqa: F401
  ```
  The dict lives in the registry singleton; `__init__.py` is just an import-side-effect manifest. Deterministic ordering (alphabetic on `module_name`). Idempotent (regenerating produces byte-identical output if the directory hasn't changed). Header timestamp goes in a separate `# generated-at: <ts>` comment line that the idempotence check ignores.

### Validator chain (REG-03, REG-06)

- **D-30:** Three validators in `src/automil/registry/validators/`. Run-time split:
  | Validator | What it checks | When it runs | Static? |
  |---|---|---|---|
  | `interface` | Variant class is a subclass of the correct ABC; required methods are defined; method signatures match the ABC's. AST + `inspect.signature` walk. | **Submit time** (pre-queue) | Yes |
  | `purity` | Module has no top-level I/O (`open`, `requests`, `urllib`); no top-level network or filesystem side-effects on import; module-level state is read-only after import (constants OK, mutable globals not). | **Submit time** (pre-queue) | Yes |
  | `identity` | (Architecture-preserving mode) parameter count within tolerance of parent; output tensor shape matches parent on a stub forward; (Free mode) only output dimensionality validated, not parameter count. Per `registry.identity_constraints` in `automil/config.yaml`. | **Instantiate time** (in `train.py`, before first epoch) | No (needs runtime tensor shapes) |
- **D-31:** Mode flag (`registry.mode: free | architecture-preserving`, default `free` per Phase 0 STATE.md decisions log) selects the **identity validator's strictness**. `interface` and `purity` always run regardless of mode — they're hygiene, not policy. In `free` mode, `identity` enforces only that the variant produces tensors of compatible dtype and rank with the parent's loss expectations; in `architecture-preserving` mode, it adds parameter-count tolerance (default ±5% configurable per project) and per-layer shape audit per `registry.identity_constraints`.
- **D-32:** Validator failure semantics: **hard-fail** at submit time (interface/purity) and **hard-fail with checkpoint to disk** at instantiate time (identity). Soft-warn substitutes for required gates defeat Pitfall 1 ("still uses old path"). Submit-time failures print the ABC violation with file:line and exit non-zero from `automil submit`. Instantiate-time identity failures write a `validation_failure.json` to `archive/<node_id>/` with the parent expected vs variant actual shapes, and the experiment exits with a `result.json` of `{status: "validation_failed", composite: 0.0}` so the orchestrator records the attempt without hanging.

### Protected files (REG-04, REG-05)

- **D-33:** `registry.protected: [path_glob, ...]` lives in **consumer-side `automil/config.yaml`**, NOT in framework defaults. `src/automil/` ships no protected list — per "autoMIL is generic" memory, the framework can't know what's load-bearing for an arbitrary project. CCRCC's config will populate it:
  ```yaml
  registry:
    protected:
      - "benchmarks/lib/CLAM/**"
      - "benchmarks/src/autobench/pipeline/clam/train.py"
      - "benchmarks/src/autobench/pipeline/clam/_imports.py"
  ```
  Path globs use `pathlib.PurePath.match` semantics (relative to project root). Empty list = no protection (a fresh `automil init` ships an empty list with a TODO comment).
- **D-34:** `automil submit` enforcement is **hard-fail**, no override flag. The submit pre-validator checks each `--files` path against `registry.protected`; any match aborts with exit 2 and a message naming the matched protected pattern. `automil check` reports git-status of every protected path — both staged AND unstaged dirty count as a check failure (REG-05). The check failure prints the diff hunk count per file so the operator knows the scope to revert. No `--force` escape hatch in Phase 1 (a future phase can add one if a real workflow demands it; speculation isn't a v1 feature).

### `train.py` config-driven contract (REG-07)

- **D-35:** `train.py` reads variant selection by **short name** via the registry, not by import path or full class dict:
  ```yaml
  # benchmarks/experiments/ccrcc/automil/config.yaml
  model:
    variant: "clam_mb_v0176"   # registry.MODEL_VARIANTS[("clam_mb", "clam_mb_v0176")]
    parent: "clam_mb"          # disambiguates lookup; required for model variants
  loss:
    variant: "ce_smooth008"    # registry.LOSS_VARIANTS["ce_smooth008"]
  policy:
    variant: "sam_lookahead"   # registry.POLICY_VARIANTS["sam_lookahead"]
  ```
  `train.py` calls `registry.resolve_model("clam_mb", "clam_mb_v0176")(args)`, etc. Dataset-derived params (`n_classes`, `feat_dim`) come from a separate `dataset:` section already present in the existing config. Missing variant in registry → hard-fail at `train.py` startup with the available names listed.
- **D-36:** "Zero `args.X = literal` overrides" interpreted **pragmatically as: zero architectural overrides**. Concretely:
  - **Banned (architectural surface):** `args.model_type = "clam_mb"`, `args.loss = "ce_smooth"`, `args.optimizer = "sam"`, etc. These select code paths and MUST come from config.
  - **Allowed (tunable hyperparameters):** `args.lr = 1e-4`, `args.batch_size = 1`, `args.dropout = 0.25`, etc. — these are numeric values that variants override via VariantSpec or per-experiment overlay, not architectural choices.
  - **Verification:** `grep -E "args\.(model|loss|optimizer|policy|aggregator)\s*=" benchmarks/src/autobench/pipeline/clam/train.py` returns zero matches at Phase 1 acceptance. Numeric hyperparam grep is NOT a gate (Phase 5 GTE may tighten if needed).

### CCRCC port (REG-08)

- **D-37:** Port preserves **variant body byte-identical** with adapted **wrapper-layer**:
  - The 263-insertion / 46-deletion dirty diff across (`model_clam.py`, `core_utils.py`, `run_experiment.py`, `train.py`) is split by mutation kind. Each chunk's *behavioural code* is copied verbatim into the variant module. Only the *function signature* changes (free-function-edit → ABC subclass override).
  - Specifically:
    - Architectural diff in `model_clam.py` (CLAM_MB attention head changes) → `clam_mb_v0176.py` `ModelVariant.forward` body byte-identical, wrapped in subclass.
    - Loss diff in `core_utils.py` (label smoothing 0.08) → `ce_smooth008.py` `LossVariant.__call__` body byte-identical.
    - Optimizer diff in `core_utils.py` + `train.py` (SAM + Lookahead) → `sam_lookahead.py` `PolicyVariant.wrap_optimizer` byte-identical.
    - `run_experiment.py` diff (config plumbing) → revert to baseline; the new config-driven path replaces the dirty plumbing.
- **D-38:** Reproduction safety: the port is **not "done" until `automil verify-repro` produces a manifest within ±0.005**. If the port produces a composite outside tolerance, the port is wrong (the byte-identical-body rule is the lever to pull — find the dirty hunk that didn't make it across). Plan ordering: port-CCRCC → train.py-refactor → verify-repro is Wave 4–5 serial.

### Reproduction sanity (REG-09)

- **D-39:** Gate is a **CLI command + committed manifest**, NOT a CI test. Concretely:
  - `automil verify-repro <node_id>` (new command) reads the node from `graph.json`, fetches the recorded composite, runs a fresh experiment via the registry path on a clean worktree (the orchestrator's standard worktree mechanism), and writes `<consumer>/<dataset>/automil/repro_manifest.yaml` with `{node_id, expected_composite, actual_composite, tolerance, git_sha, runtime_seconds, generated_at, status}`. Tolerance default ±0.005 from `automil/config.yaml: registry.repro_tolerance`.
  - Phase 1 acceptance: `repro_manifest.yaml` for CCRCC `node_0176` exists with `status: "pass"`. Manifest is committed to git.
  - **Why not CI:** A 4h training is untenable as a per-PR test; running it once on a clean checkout, committing the manifest, and re-verifying only on demand is the production pattern for expensive integration tests.
  - **Why not pure recorded-result:** Skipping the rerun entirely defeats the gate — REG-09 demands proof the registry path actually produces the composite, not just a claim.
- **D-40:** `automil check` (extended) reads `repro_manifest.yaml` if present and reports `status` + `actual_composite` vs `expected_composite`. If the manifest is missing or stale (older than the latest variant module's mtime), check warns but does not fail (failing on missing manifest blocks normal development; the gate only fires when explicitly run via `verify-repro`).

### CLI lifecycle commands (CLI-01, CLI-02, CLI-05, CLI-06, CLI-08, CLI-09)

- **D-41:** `automil apply <node_id>` edits **`automil/config.yaml`** (variant selection in `model.variant` / `loss.variant` / `policy.variant`), NOT the codebase. Variant *code* already lives in committed `variants/` modules; "apply" means "make this node's selection the active config for the next submit." Idempotent. Backs up existing config to `automil/config.yaml.bak` once, atomic write via tempfile+rename.
  - **Reasoning:** Apply-as-codemod (the obvious-looking interpretation) breaks the registry-first invariant. Once variants are committed code, "apply" is ALWAYS a config-level operation.
  - The "config delta" in CLI-01's text refers to the variant's recorded hyperparameter overrides in `VariantSpec.mutations` — these flow into `train.py:overrides:` section of config, not into source files.
- **D-42:** `automil revert-baseline` runs `git checkout <base_commit> -- <paths>` for paths the agent has touched, where "the agent has touched" = `git status --porcelain` output filtered against `registry.protected`. Anti-protected is the implicit "editable" set. Per Leo's "Never blind-checkout after submit" memory, the command's safety net is mandatory: it stashes any uncommitted changes to a named stash (`automil-revert-<timestamp>`) BEFORE the checkout, surfacing the stash name in stdout. Re-runnable.
- **D-43:** `automil port-variant <node_id>` converts a node's overlay to a variant module:
  - Auto-naming: `<parent>_v<node_id_short>` (e.g., `clam_mb_v0176`). `--name` flag overrides.
  - Auto-kind: inferred from which protected-or-not paths the overlay touches; if ambiguous (multi-kind overlay), command prints a kind table and requires `--kind model|loss|policy` to be passed.
  - Output: `<consumer>/<dataset>/automil/variants/<kind_dir>/<name>.py` + sibling `<name>.json` manifest.
  - **Idempotent:** if the variant module already exists with matching `VariantSpec.node_id`, command is a no-op with exit 0. Mismatched node_id with same name is a hard-fail (don't silently overwrite a port from a different node).
  - Calls `automil refresh-registry` at the end to regenerate the kind-dir's `__init__.py`.
- **D-44:** Manifest format — sibling JSON file `<name>.json` next to `<name>.py`:
  ```json
  {
    "spec": { /* VariantSpec serialized */ },
    "source_node": "node_0176",
    "source_overlay_files": ["benchmarks/lib/CLAM/models/model_clam.py", ...],
    "ported_at": "2026-05-02T10:00:00Z",
    "tool_version": "automil 0.X.Y"
  }
  ```
  JSON not YAML for parser stability and the `tool_version` field for forward-compat. Loaded at registry-refresh time and cross-checked against the variant module's docstring; mismatch → registry consistency check fails.
- **D-45:** `automil promote-variant <node_id>` is a Phase 1 stub with full implementation: moves a variant from `variants/_candidates/` (which Phase 5 GTE will populate) to canonical `variants/<parent>/`. Phase 1 ships the command + the `_candidates/` directory existence (with a `.gitkeep`); the actual gate-passing pipeline is Phase 5. Promotion is a `git mv` + manifest update + `refresh-registry` + stage for commit (does NOT auto-commit; operator commits with their own message).
- **D-46:** `automil check` extension (Phase 1 additions on top of Phase 0's nvidia-smi + env whitelist visibility):
  - protected-files clean (REG-05): every path in `registry.protected` shows as unmodified in `git status` (both staged and unstaged dirty fail).
  - registry consistency: every `variants/**/*.py` is importable, has `@register`, and matches its sibling manifest. Stale `variants/__init__.py` (out of sync with directory contents) fails check with the recommendation `automil refresh-registry`.
  - reproduction manifest: warn-not-fail if `repro_manifest.yaml` is missing or older than newest variant module mtime (D-40).
  - **Deferred:** "env vars declared" (Phase 8 / DEC-05); "runtime asset present" (Phase 3 / MRT-01); "sample-size sanity" (Phase 4 / CAP-06 — cells don't exist in Phase 1). Phase 1's `check` warns about these as TODO with the owning phase named.

### Test posture and commit cadence

- **D-47:** Test posture:
  - Phase 0's 113-test baseline stays green at every commit.
  - Phase 1 net-new tests target ≥30 (registry singleton roundtrip, three-ABC subclass detection, validator chain (interface+purity static, identity stub-forward), protected-files submit reject, refresh-registry idempotence, port-variant naming + kind-detection, apply config edit, revert-baseline stash safety, manifest schema validation, plus per-CLI-command happy-path + reject-path tests).
  - **Reproduction-sanity test is NOT in the Python test suite.** It runs as `automil verify-repro` against a real GPU and lands in the committed manifest; CI cost is too high.
- **D-48:** Commit cadence: target ~12 commits across the wave (one per plan, matching `fine` granularity). Each plan's tests must pass before the merge. Wave-level post-merge `pytest tests/` gate (matching Phase 0 pattern) catches cross-plan integration. CCRCC port + verify-repro is one logical commit with a long message documenting the dirty-diff-to-variant-module mapping.

### Claude's Discretion (engineering details — planner picks)

- Internal dataclass / typing choices for the registry's three keyed dicts (e.g., `dict[str, type[ModelVariant]]` vs a `RegistryEntry` wrapper).
- Concrete `pkgutil.iter_modules` vs `pathlib.Path.rglob` for variant discovery — whichever is simpler.
- `git checkout`-via-`subprocess` vs `git`-via-`pygit2`-or-`dulwich` for `revert-baseline` — subprocess preferred unless dependency cost is justified.
- Logger names per module (`__name__`-based per Python convention).
- Test fixture refactor for the registry singleton (likely a `monkeypatch.setattr(registry, ...)` pattern so each test gets an isolated registry).
- Exact `inspect.signature` mechanics for the `interface` validator (planner-side detail).

</decisions>

<specifics>
## Specific Ideas

- **CCRCC variant naming:** `clam_mb_v0176` (model) + `ce_smooth008` (loss, 0.008 = label smoothing magnitude) + `sam_lookahead` (policy, SAM + Lookahead optimizer wrapping). The two-character prefix `_v` distinguishes node-derived names from arbitrary developer names.
- **Validator order at submit:** `interface` first (cheap fail, structural), then `purity` (cheap fail, AST-walk). `identity` only at instantiate-time. No ordering tricks; submit pre-validator is short-circuit on first failure with the failed validator's name in the error.
- **Registry singleton + fork safety:** the orchestrator forks worker processes per experiment. Variant modules are imported per-process at `train.py` startup, so the registry is repopulated in each worker. No cross-fork shared state; no fork-safety dance needed.
- **REG-09 ±0.005 tolerance — why this number:** CCRCC's recorded composite is 0.8074. ±0.005 is ~0.6% relative tolerance, larger than typical run-to-run noise on a fixed seed but tight enough that a real porting bug shows up. If the port is correct and the recorded run was deterministic, the rerun should be byte-identical or off by floating-point summation order only.
- **`apply` config backup:** single `.bak` rolling backup, NOT a stack. The agent runs `apply` repeatedly during search; a stack of `.bak.0`, `.bak.1`, etc. would balloon the project dir. One `.bak` rolls forward.
</specifics>

<deferred>
## Deferred Ideas

- **`importlib.metadata.entry_points` cross-project variant discovery** — Phase 7 / `STP-04` (when third-party variant pip-packages become realistic).
- **`recipe` and `inference` ABCs** — Phase 5 (`GTE-04` paired test) and Phase 8 (`DEC-04` config-driven scoring) introduce these concepts; Phase 1 stays at `model | loss | policy`.
- **`AggregatorOutput` dataclass** — Phase 8 / `DEC-03` JSON-Schema validation of `result.json` is the right place to formalise framework-level output contracts.
- **`automil submit --force`** to bypass protected-files check — speculation; add only when a real workflow demands it.
- **CI integration of `verify-repro`** — current production pattern is operator-triggered + committed manifest. Revisit if a real CI runner becomes available with GPU budget.
- **Per-numeric-hyperparameter "no `args.X = literal`" enforcement** — pragmatic interpretation (D-36) limits the rule to architectural surface. Phase 5 / GTE may tighten if hyperparameter drift becomes a problem.
- **`registry.editable` explicit allowlist** — implicit anti-protected (D-42) covers the v1 case. Promote to explicit list if a project ever needs a third tier (protected | editable | ignored).
</deferred>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context
- `.planning/PROJECT.md` — milestone definition, validated/active sets, key decisions including registry-first
- `.planning/REQUIREMENTS.md` — REG-01..09 + CLI-01/02/05/06/08/09 with v1 traceability
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, anti-acceptance notes (Pitfall 1)
- `.planning/STATE.md` — milestone status, mode default `free` recommendation
- `.planning/phases/00-tier-2-cleanup-cli-split-compat-shim/00-CONTEXT.md` — Phase 0 locked decisions D-01..D-20 (env whitelist, compat.py, CLI structure)
- `CLAUDE.md` — Leo's standing directives (registry-first, autoMIL is generic, never blind-checkout, GPU saturation, architectural-not-hyperparameter)

### Phase 1 implementation seeds (codebase pointers)
- `src/automil/cli/lifecycle.py` — Phase 0 stub awaiting Phase 1 commands (apply, revert-baseline, port-variant, promote-variant, refresh-registry)
- `src/automil/cli/check.py` — Phase 0 base (nvidia-smi report, env whitelist visibility); Phase 1 extends
- `src/automil/cli/_helpers.py` — `_find_automil_dir`, `_find_git_root`; lift to `automil/paths.py` if registry/validators need git-root lookup
- `src/automil/cli/submit.py` — submit pre-validator hook point; registry validator chain integrates here
- `src/automil/graph.py` — `ExperimentGraph.add_executed`, `add_proposed_then_execute`; Phase 1 consults `node.changes` for port-variant
- `src/automil/runner.py` — git-worktree overlay; reused by `verify-repro`
- `benchmarks/src/autobench/pipeline/clam/train.py` — REG-07 target; current 163-line dirty diff split into variant modules
- `benchmarks/experiments/ccrcc/automil/config.yaml` — registry.protected + registry.mode + registry.repro_tolerance + variant selection land here
- `benchmarks/experiments/ccrcc/automil/graph.json` — node_0176 source for the CCRCC port (composite 0.8074 expected at REG-09)
- `benchmarks/lib/CLAM/{models/model_clam.py, utils/core_utils.py}` — protected; the 263-insertion / 46-deletion dirty diff is the port source

### Locked-decision lineage
- `D-01..D-03` (Phase 0 CLI split) — Phase 1 `cli/lifecycle.py` placement honours D-01
- `D-07..D-09` (Phase 0 compat.py) — Phase 1 promotes the placeholder Phase 1 entry from `_PLANNED_MIGRATIONS` to Active if it relocates any name (Phase 1 currently relocates none; placeholder stays in `_PLANNED_MIGRATIONS`)
- `D-15..D-18` (Phase 0 PID + nvidia-smi + dotenv) — orthogonal; no Phase 1 interaction

</canonical_refs>

---

*Phase: 01-variant-registry-config-driven-train-py-ccrcc-reproduction-s*
*Context gathered: 2026-05-02 via /gsd-discuss-phase 1 --all (engineering decisions self-locked per Leo's directive)*
*Decisions logged: D-21 through D-48 (28 decisions covering ABC family, layout, registry, validators, protected files, train.py contract, CCRCC port, reproduction sanity, CLI lifecycle, check extension, test posture)*
