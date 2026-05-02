---
phase: 01-variant-registry-config-driven-train-py-ccrcc-reproduction-s
verified: 2026-05-02T08:46:04Z
status: passed
score: 8/8 success criteria verified (15/15 REQ-IDs satisfied)
overrides_applied: 0
re_verification: null
---

# Phase 1: Variant Registry (Framework-Only) — Verification Report

**Phase Goal (reinterpreted per D-49 / D-50):** Establish the framework registry — three sibling Variant ABCs, a registry singleton with `@register` decorator, validator chain (interface + purity + identity), protected-files enforcement on submit, six lifecycle CLI commands, and a synthetic-consumer round-trip that proves the framework's `register → port-variant → refresh-registry → apply → verify-repro` chain works end-to-end with no mocks. Framework-only scope: zero `benchmarks/lib/`, zero `benchmarks/src/autobench/pipeline/clam/train.py` edits, zero CCRCC `node_0176` dependency for Phase 1 acceptance.

**Verified:** 2026-05-02T08:46:04Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Phase 1 Success Criteria)

| #   | Truth                                                                                                          | Status     | Evidence                                                                                                                                                                                                                                                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Three sibling Variant ABCs (`ModelVariant`, `LossVariant`, `PolicyVariant`) + frozen `VariantSpec` dataclass live in `src/automil/registry/`. Liskov-clean (D-21). | ✓ VERIFIED | `src/automil/registry/variants/{model,loss,policy}.py` (54+39+34 lines) each define a distinct `ABC` with required `@abstractmethod` and parent-correct semantics. `src/automil/registry/spec.py:21` is `@dataclass(frozen=True)` with `mutations: tuple[str, ...]` field (frozen tuple, not list). All three exported from `registry/__init__.py:14-17`. |
| 2   | Registry singleton + `@register` decorator + `resolve_*` functions; `automil refresh-registry` regenerates per-kind `__init__.py` deterministically + idempotently (D-27, D-29). | ✓ VERIFIED | `registry/_state.py` — three module-level keyed dicts (`MODEL_VARIANTS` keyed `(parent, name)`, `LOSS_VARIANTS`/`POLICY_VARIANTS` keyed by name) + `SPEC_STORE`. `registry/registrar.py:36` `register()` decorator validates kind, parent semantics, ABC subclass, and uniqueness. `registry/scanner.py:120` `regenerate_init_py` writes deterministic alphabetic imports-only manifest with timestamp on a separate line for byte-identical idempotence; uses tempfile+rename for atomic write (PATTERNS §3). `cli/lifecycle/refresh_registry.py` (70 lines) wires it as a CLI command. Tests: `test_registry_singleton.py`, `test_registry_scanner.py`, `test_lifecycle_refresh_registry.py` all green. |
| 3   | Static validators (interface + purity) + runtime identity validator wired; `automil submit` hard-fails on validator failure or protected-files match (D-30, D-32, D-34). | ✓ VERIFIED | `registry/validators/interface.py` (370 lines), `purity.py` (309 lines), `identity.py` (394 lines). `cli/submit.py:122` loads `RegistryConfig`, then at lines 212-215 hard-rejects any `--files` matching `registry.protected` glob; at 225-231 runs `PurityValidator().check(...)` first then `InterfaceValidator().check(...)`, short-circuiting on failure. Identity validator constructed with `mode` parameter, raises `ValidationError` and writes `archive/<node>/validation_failure.json` atomically (identity.py mode-aware lines 125-263). Tests: `test_submit_protected_files.py`, `test_submit_validator_chain.py`, `test_registry_validator_{interface,purity,identity}.py` all green. |
| 4   | `automil/config.yaml: registry.protected/mode/repro_tolerance` schema in place; `automil init` scaffolds variants/ skeleton (D-31, D-33). | ✓ VERIFIED | `registry/config.py:37-40` defines frozen `RegistryConfig` with `protected: tuple[str, ...] = ()`, `mode: Literal["free","architecture-preserving"] = "free"`, `repro_tolerance: float = 0.005`, `identity_constraints: tuple[str, ...] = ()`. `templates/config.yaml.j2:71-95` ships `registry:` section with empty `protected: []`, `mode: free`, `repro_tolerance: 0.005`, and explicit "no framework defaults" comment (D-33). `cli/init.py:14-29` `_scaffold_variants_skeleton` creates `variants/{.gitkeep, _losses/.gitkeep, _policies/.gitkeep, _candidates/.gitkeep}` (D-25). Tests: `test_registry_config.py`, `test_init_registry_scaffold.py` all green. |
| 5   | All 6 lifecycle CLI commands implemented and tested: apply, revert-baseline, refresh-registry, port-variant, promote-variant, verify-repro (D-41..45). | ✓ VERIFIED | `cli/lifecycle/{apply.py:144, revert_baseline.py:151, refresh_registry.py:70, port_variant.py:315, promote_variant.py:133, verify_repro.py:212}` — all six exist as full implementations (no stubs). `automil --help` shows all six registered with workflow-explaining help text. `automil <cmd> --help` for each renders the workflow. Tests `test_lifecycle_{apply,revert_baseline,refresh_registry,port_variant,promote_variant}.py` + `test_verify_repro.py` (9 tests) all green. |
| 6   | Synthetic-consumer round-trip passes — `tests/test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes` exercises register → port-variant → refresh-registry → apply → verify-repro chain end-to-end with no mocks (D-50, **PHASE 1 ACCEPTANCE GATE**). | ✓ VERIFIED | `tests/test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes PASSED [100%]` (1 passed in 0.28s). Pipeline runs the REAL `port-variant` (which mutates graph.json to add `variant_spec` per BLOCKER-02), `refresh-registry`, `apply` (reads from real graph.json), and `verify-repro` (executes `tests/fixtures/synthetic_consumer/program.py` in a fresh git worktree). Final manifest `status: pass`, `actual_composite ≈ 0.502`, `tolerance: 0.005`. Sibling test `test_full_roundtrip_fail_exceeds_tolerance` asserts the negative case (fail manifest, non-zero exit). Sibling `test_port_variant_writes_variant_spec_to_graph_json` is the BLOCKER-02 regression-prevention test. |
| 7   | Phase 0 baseline (113 tests) preserved + ≥220 net-new tests = ≥333 total. | ✓ VERIFIED | `uv run pytest tests/ -q` reports `387 passed in 12.92s`. Net-new = 387 − 113 = 274 tests (well above the ≥220 floor). Plan 01-12 SUMMARY records 387 across 12 plans; verifier reproduces this exactly. |
| 8   | Framework-only scope: zero `benchmarks/lib/`, zero `benchmarks/src/autobench/pipeline/clam/train.py`, zero `ccrcc`/`node_0176` references in framework code paths (D-49). | ✓ VERIFIED | `grep -rE "args\.(model\|loss\|policy\|optimizer)\s*=" src/automil/` → 0 matches (D-36 architectural surface clean). `grep -rn "benchmarks/lib\|benchmarks/src/autobench/pipeline/clam" src/automil/` → 3 matches, all in user-facing **comments / examples / templates** (`revert_baseline.py:87` error message, `orchestrator.py:621` Phase-0 pre-existing comment, `templates/config.yaml.j2:76` doc-comment example). `grep -rni "ccrcc\|node_0176" src/automil/` → 6 matches, all in **docstrings / examples / explanatory comments** (e.g., `manifest.py:31` `# e.g., "node_0176"`, `verify_repro.py:158` "Real consumers (CCRCC etc.)..."). No code coupling: nothing imports `autobench`, branches on `ccrcc`, or hardcodes a benchmarks path. Framework registry is consumer-agnostic by construction. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/automil/registry/__init__.py` | Public surface re-exports (Kind, VariantSpec, three ABCs, RegistryConfig, register, resolve_*, RegistrationError, ValidationError, validators) | ✓ VERIFIED | 53 lines, `__all__` lists all 13 public names. Import sanity command `python -c "from automil.registry import (ModelVariant, LossVariant, PolicyVariant, VariantSpec, Kind, RegistryConfig, load_registry_config, register, resolve_model, resolve_loss, resolve_policy, RegistrationError); print('all imports ok')"` returns "all imports ok". |
| `src/automil/registry/spec.py` | `@dataclass(frozen=True)` `VariantSpec` with 8 fields including `mutations: tuple[str,...]` | ✓ VERIFIED | 35 lines; `Kind = Literal["model","loss","policy"]`; `VariantSpec` frozen with name/kind/parent/base_commit/composite/node_id/created_at/mutations. |
| `src/automil/registry/variants/{model,loss,policy}.py` | Three sibling ABCs with parent-correct semantics | ✓ VERIFIED | `ModelVariant(ABC)` requires `forward`; optional `instance_attention`. `LossVariant(ABC)` requires `__call__(logits, targets, *, instance_logits=None, instance_labels=None)`. `PolicyVariant(ABC)` requires `wrap_optimizer`; default `step` delegates to `opt.step()`. No torch import at module load time (TYPE_CHECKING guard). |
| `src/automil/registry/_state.py` | Module-level singleton dicts | ✓ VERIFIED | `MODEL_VARIANTS: dict[(parent,name), type]`, `LOSS_VARIANTS: dict[name, type]`, `POLICY_VARIANTS: dict[name, type]`, `SPEC_STORE: dict[(kind,parent,name), VariantSpec]`. Test-only `_clear_registry()` for fixture isolation. |
| `src/automil/registry/registrar.py` | `@register` decorator + `resolve_model/loss/policy` | ✓ VERIFIED | 146 lines; `register()` validates kind/parent/ABC/uniqueness; production-grade error messages naming what failed and how to fix. Three resolvers raise KeyError with sorted available list on miss. |
| `src/automil/registry/config.py` | `RegistryConfig` + `load_registry_config` | ✓ VERIFIED | 118 lines; `RegistryConfig(protected, mode, repro_tolerance, identity_constraints)` frozen dataclass; `load_registry_config(adir)` reads `automil/config.yaml: registry.*`, hard-fails on unknown mode. Defaults exposed (no framework-baked protected list per D-33). |
| `src/automil/registry/manifest.py` | Sibling JSON manifest schema | ✓ VERIFIED | 218 lines; `Manifest` dataclass with spec/source_node/source_overlay_files/ported_at/tool_version. Read/write/validate pathway used by port-variant, refresh-registry, check. |
| `src/automil/registry/scanner.py` | Variant discovery + `__init__.py` regeneration | ✓ VERIFIED | 175 lines; `scan_variants()` walks variants_root via `pkgutil`-style import-by-path; `regenerate_init_py()` writes byte-identical alphabetic imports with timestamp on a separate line for idempotence. Atomic tempfile+rename write. |
| `src/automil/registry/validators/{interface,purity,identity}.py` | Three validators (REG-03) | ✓ VERIFIED | interface (370 lines, AST + reflection), purity (309 lines, AST top-level I/O reject), identity (394 lines, mode-aware: `free` checks dtype/rank only; `architecture-preserving` adds param-count + identity_constraints). |
| `src/automil/cli/submit.py` | Submit hook with protected-files reject + validator chain | ✓ VERIFIED | Lines 122 load registry config; 212-215 hard-reject on protected glob match; 225-231 run PurityValidator first then InterfaceValidator (short-circuit on first failure). |
| `src/automil/cli/check.py` | Phase-1 extension: protected-files clean + registry consistency + repro-manifest awareness | ✓ VERIFIED | Lines 125-209 add: protected-files git-status check, registry consistency (scanner + manifest cross-check), repro_manifest.yaml staleness warn-not-fail (D-46). |
| `src/automil/cli/init.py` | `_scaffold_variants_skeleton` creates variants/.gitkeep + _losses/_policies/_candidates | ✓ VERIFIED | Lines 14-29 + line 67 invocation; idempotent via `mkdir parents=True exist_ok=True`. |
| `src/automil/cli/lifecycle/apply.py` | CLI-01 — config-only edit, idempotent, atomic write, .bak rolling | ✓ VERIFIED | 144 lines; reads `node['variant_spec']` from real graph.json (no scaffolding); rejects on missing variant_spec or missing config.yaml. |
| `src/automil/cli/lifecycle/revert_baseline.py` | CLI-02 — mandatory pre-stash before checkout (Leo's "never blind-checkout") | ✓ VERIFIED | 151 lines; stashes uncommitted changes to `automil-revert-<timestamp>` BEFORE `git checkout`; surfaces stash name in stdout. Hard-fails on empty `registry.protected`. |
| `src/automil/cli/lifecycle/refresh_registry.py` | CLI-08 — scan + regenerate __init__.py | ✓ VERIFIED | 70 lines; `--strict` flag for fail-on-import-error; default warns and continues. Reports imported / failed / skipped counts. |
| `src/automil/cli/lifecycle/port_variant.py` | CLI-05 — auto-name, auto-kind, auto-parent, idempotent, mutates graph.json with variant_spec (BLOCKER-02 contract) | ✓ VERIFIED | 315 lines; auto-name `<parent>_v<short>`; auto-kind detection by overlay paths; `--name/--kind/--parent` overrides; idempotent re-port (no-op on matching node_id); writes variant module + sibling JSON manifest + mutates `graph.json:nodes[id].variant_spec` (REAL CLI tested in synthetic round-trip, no scaffolding). |
| `src/automil/cli/lifecycle/promote_variant.py` | CLI-06 — `git mv` candidate to canonical kind dir + refresh + stage | ✓ VERIFIED | 133 lines; finds candidate by `manifest.source_node == node_id`; `git mv` .py + .json; regenerates affected __init__.py; stages but does NOT auto-commit (D-45). |
| `src/automil/cli/lifecycle/verify_repro.py` | CLI-09 — runs program.py in clean worktree, writes repro_manifest.yaml, exit non-zero on tolerance miss | ✓ VERIFIED | 212 lines; uses `runner.py` worktree mechanism; whitelisted env (no AUTOBENCH_* leakage); `sys.executable` for subprocess (not bare `python`); writes 8-field manifest atomically; `--tolerance` override flag. |
| `tests/fixtures/synthetic_consumer/{program.py, automil/config.yaml, automil/variants/synthstub/.gitkeep}` | Synthetic mini-consumer for D-50 round-trip | ✓ VERIFIED | `program.py` (82 lines) is torch-free; reads config.yaml → `_clear_registry()` + `scan_variants()` → `resolve_model(parent, name)` → instantiates variant → calls `forward()` → writes `result.json`. No mocks. |
| `tests/test_synthetic_consumer_roundtrip.py` | Phase 1 acceptance gate | ✓ VERIFIED | 367 lines, 3 tests; main test wires REAL CLI port-variant → refresh-registry → apply → verify-repro through `CliRunner`; asserts variant_spec written to graph.json, config.yaml mutated, repro_manifest.yaml status=pass. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| Submit pre-validator | RegistryConfig | `from automil.registry.config import load_registry_config` (submit.py:122) | ✓ WIRED | Loaded once per submit; protected glob match aborts with exit 2; validator chain runs purity → interface short-circuit. |
| `@register` decorator | Singleton dicts | `_KIND_TABLE` lookup (registrar.py:21-25) | ✓ WIRED | ABC subclass check + (kind, parent, name) uniqueness check + insert into `MODEL_VARIANTS / LOSS_VARIANTS / POLICY_VARIANTS` + `SPEC_STORE`. |
| `automil refresh-registry` | `scan_variants` + `regenerate_init_py` | `cli/lifecycle/refresh_registry.py` | ✓ WIRED | CLI invokes scanner; on each kind subdir, alphabetic imports re-rendered; tempfile+rename atomic write. |
| `automil port-variant` | `automil refresh-registry` | port_variant.py end-of-flow (D-43) | ✓ WIRED | Auto-invoked at the end so the kind directory's `__init__.py` reflects the new module. |
| `automil port-variant` | `graph.json` | mutate `nodes[id].variant_spec` (BLOCKER-02) | ✓ WIRED | Verified end-to-end by `test_port_variant_writes_variant_spec_to_graph_json` and `test_full_roundtrip_passes`. |
| `automil apply` | `graph.json` | reads `nodes[id].variant_spec` (NO scaffolding) | ✓ WIRED | The synthetic round-trip writes `_write_graph_node_no_variant_spec()` (deliberately no variant_spec) → port-variant must populate it → apply reads it. Test passes. |
| `automil verify-repro` | `runner.py` worktree | clean fresh worktree; subprocess `program.py` | ✓ WIRED | `verify_repro.py:84` strips AUTOBENCH_*, uses sys.executable, runs `program.py` in worktree at `base_commit`. |
| `RegistryConfig.mode` | `IdentityValidator` | constructor `mode=` (identity.py:125-263) | ✓ WIRED | `free` mode skips param-count check; `architecture-preserving` applies identity_constraints + per-constraint check. |
| `automil check` | RegistryConfig + scanner + manifest | check.py:125-209 | ✓ WIRED | git-status of every protected glob; scanner imports + manifest cross-check; repro_manifest.yaml mtime warn. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `port-variant` | `variant_spec` written to graph.json | computed from archive/<node>/spec.json + auto-name + auto-kind detection | Yes — REAL CLI test asserts `variant_spec.kind == "model"`, `variant_spec.parent == "synthstub"`, `variant_spec.name.startswith("synthstub_v")` | ✓ FLOWING |
| `apply` | `cfg["model"]["variant"]` written to config.yaml | reads from `node['variant_spec']` (NOT a stub fixture) | Yes — round-trip test asserts `cfg["model"]["variant"] == variant_name` after running CLI | ✓ FLOWING |
| `verify-repro` | `actual_composite` in manifest | runs `program.py` in clean worktree, parses `result.json` | Yes — synthetic program.py calls `resolve_model().forward()` and returns 0.502; manifest captures it within ±0.005 of expected 0.502 | ✓ FLOWING |
| `refresh-registry` | imports `from . import <variant>` | scans directory, imports each `.py`, re-renders `__init__.py` | Yes — sibling test `test_lifecycle_refresh_registry.py` asserts byte-identical body across runs (idempotence) | ✓ FLOWING |
| `submit` validator chain | rejection reason | `PurityValidator.check` AST + `InterfaceValidator.check` AST+reflection | Yes — `test_submit_validator_chain.py` exercises real validation against malformed and well-formed variant modules | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full test suite passes | `uv run pytest tests/ -q` | `387 passed in 12.92s` | ✓ PASS |
| Phase 1 acceptance gate passes | `uv run pytest tests/test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes -v` | `1 passed in 0.28s` | ✓ PASS |
| All public registry symbols importable | `uv run python -c "from automil.registry import (ModelVariant, LossVariant, PolicyVariant, VariantSpec, Kind, RegistryConfig, load_registry_config, register, resolve_model, resolve_loss, resolve_policy, RegistrationError); print('all imports ok')"` | `all imports ok` | ✓ PASS |
| 6 lifecycle CLI commands registered | `uv run automil --help` | `apply / port-variant / promote-variant / refresh-registry / revert-baseline / verify-repro` all present | ✓ PASS |
| Total command count | `uv run automil --help \| grep -E "^  [a-z]" \| wc -l` | 17 (= 11 prior + 6 new) | ✓ PASS |
| Workflow-explaining `--help` per new command | `automil <cmd> --help` for each | All six render multi-paragraph workflow text | ✓ PASS |
| No architectural-surface `args.X = literal` in framework | `grep -rE "args\.(model\|loss\|policy\|optimizer)\s*=" src/automil/` | 0 matches | ✓ PASS |
| Phase 1 commits exist | `git log --oneline 9f99449..HEAD \| wc -l` | 60 commits | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| REG-01 | 01-01 | Variant ABC + frozen VariantSpec | ✓ SATISFIED | Three sibling ABCs + frozen dataclass; D-21..D-24 honored verbatim. |
| REG-02 | 01-02, 01-06 | Internal Registry + @register + per-kind __init__.py regen | ✓ SATISFIED | `_state.py` + `registrar.py` + `scanner.py` + `cli/lifecycle/refresh_registry.py`. importlib.metadata.entry_points deferred per D-28. |
| REG-03 | 01-04, 01-05, 01-07 | Validator chain (interface, purity, identity) | ✓ SATISFIED | All three validators implemented and integrated into submit hook (purity → interface short-circuit) + identity at instantiate-time per D-30/D-32. |
| REG-04 | 01-03, 01-07 | `registry.protected` config; submit rejects overlays | ✓ SATISFIED | `RegistryConfig.protected` + submit.py:212-215 hard-reject; D-33/D-34 honored. |
| REG-05 | 01-07 | `automil check` fails on uncommitted protected edits | ✓ SATISFIED | check.py:125-159 git-status loop on protected globs; both staged AND unstaged dirty fail. |
| REG-06 | 01-03, 01-05 | Mode flag (free / architecture-preserving) | ✓ SATISFIED | `RegistryConfig.mode` Literal; identity validator dispatches per mode; default `free`. |
| REG-07 | 01-03 | Framework provides registry-resolve API for any consumer's train.py | ✓ SATISFIED | `resolve_model/loss/policy` exported; per D-49 framework-only scope, framework provides API; consumer's train.py refactor is consumer follow-up (autobench's CCRCC train.py is intentionally NOT touched). |
| REG-08 | 01-06, 01-12 | Reinterpreted per D-50: framework provides port-variant + manifest format sufficient for ANY consumer to port — demonstrated in synthetic round-trip | ✓ SATISFIED | port-variant CLI + Manifest schema + tests/fixtures/synthetic_consumer round-trip exercises the chain. CCRCC port deferred per D-37/D-49. |
| REG-09 | 01-12 | Reinterpreted per D-50: framework provides verify-repro that produces in-tolerance manifest, demonstrated against synthetic mini-consumer | ✓ SATISFIED | `automil verify-repro` exits 0 with status=pass manifest; `test_full_roundtrip_passes` asserts `actual_composite ≈ expected_composite ± 0.005`. CCRCC ±0.005 demo deferred to consumer follow-up. |
| CLI-01 | 01-08, 01-09 | `automil apply <node_id>` config-only edit | ✓ SATISFIED | `cli/lifecycle/apply.py`; reads variant_spec from real graph.json; atomic write + rolling .bak per D-41. |
| CLI-02 | 01-08, 01-10 | `automil revert-baseline` idempotent + mandatory pre-stash | ✓ SATISFIED | `cli/lifecycle/revert_baseline.py`; pre-stash to named `automil-revert-<ts>` per Leo's never-blind-checkout memory + D-42. |
| CLI-05 | 01-11 | `automil port-variant` idempotent, rejects already-registered nodes, writes manifest | ✓ SATISFIED | `cli/lifecycle/port_variant.py`; auto-name + auto-kind + auto-parent + manifest sibling JSON + graph.json mutation per D-43/D-44. |
| CLI-06 | 01-11 | `automil promote-variant` git-mv candidate + manifest update + refresh + stage | ✓ SATISFIED | `cli/lifecycle/promote_variant.py`; finds candidate by `manifest.source_node`; stages but does NOT auto-commit per D-45. |
| CLI-08 | 01-08, 01-09 | `automil refresh-registry` deterministic + idempotent | ✓ SATISFIED | `cli/lifecycle/refresh_registry.py`; alphabetic + timestamp-on-separate-line for byte-identical idempotence per D-29. |
| CLI-09 | 01-12 | `automil check` + `automil verify-repro` for project setup validation | ✓ SATISFIED | check.py extended with protected-files / registry consistency / repro-manifest checks per D-46; verify-repro implements the reproduction-sanity command. |

**Coverage:** 15/15 phase REQ-IDs SATISFIED. Zero ORPHANED (all 15 REQ-IDs from CONTEXT.md appear in at least one PLAN's `requirements:` field).

### Locked Decision Audit (D-21..D-50)

| Decision | Honored Verbatim | Evidence |
| -------- | ---------------- | -------- |
| D-21 (three sibling ABCs, not one polymorphic) | ✓ | Three separate files in `registry/variants/`; `MODEL_VARIANTS` keyed (parent,name); LOSS/POLICY keyed by name (parent must be None). |
| D-22 (frozen VariantSpec, tuple mutations) | ✓ | `@dataclass(frozen=True)`; `mutations: tuple[str, ...] = field(default_factory=tuple)`. |
| D-23 (kind taxonomy: model/loss/policy only) | ✓ | `Kind = Literal["model","loss","policy"]`; `register()` rejects unknown kinds with explicit "Phase 1 supports kinds [...] only (D-23)" message. |
| D-24 (no AggregatorOutput in Phase 1) | ✓ | `ModelVariant.forward() -> Any` with docstring deferring to Phase 8/DEC-03. |
| D-25 (variants/<parent>/, _losses/, _policies/, _candidates/) | ✓ | `_scaffold_variants_skeleton` creates exactly these four subdirs; .gitkeep at root + each. |
| D-26 (single .py per variant + docstring header) | ✓ | port-variant template enforces; manifest cross-check at refresh-registry time (D-44 + manifest.py). |
| D-27 (module-level singleton, three keyed dicts + SPEC_STORE) | ✓ | `_state.py` exact match. |
| D-28 (entry_points deferred to Phase 7) | ✓ | scanner uses pkgutil-style import-by-path, NOT entry_points. |
| D-29 (alphabetic imports-only __init__.py with separate-line timestamp) | ✓ | `regenerate_init_py` body is byte-identical across runs; tempfile+rename. |
| D-30 (interface+purity static, identity runtime) | ✓ | submit hook runs purity AST → interface AST+reflection short-circuit; identity at instantiate-time only. |
| D-31 (mode default `free`, identity strictness mode-aware) | ✓ | `RegistryConfig.mode = "free"` default; `IdentityValidator(mode=...)` dispatches per mode. |
| D-32 (hard-fail at submit; checkpoint+result.json on identity fail) | ✓ | submit raises ValidationError; identity validator writes `archive/<node>/validation_failure.json` atomically. |
| D-33 (no framework-baked protected list) | ✓ | `RegistryConfig.protected = ()` default; template comment "autoMIL ships no defaults here". |
| D-34 (hard-fail on protected match, no `--force`) | ✓ | submit.py:212-215 raises with exit 2; no override flag. |
| D-35 (variant selection by short name from config) | ✓ | resolve_model(parent, name) / resolve_loss(name) / resolve_policy(name); KeyError lists available pairs. |
| D-36 (no architectural-surface `args.X = literal` in framework) | ✓ | `grep -rE "args\.(model\|loss\|policy\|optimizer)\s*=" src/automil/` → 0 matches. |
| D-37 (CCRCC port deferred) | ✓ | port_variant emits `NotImplementedError` stub; comment cites D-37; tests/fixtures synthetic consumer is the framework-side acceptance. |
| D-38 (Wave 4-5 collapse to synthetic-consumer round-trip) | ✓ | Wave 4 = single plan 01-12 = synthetic round-trip + verify-repro; no CCRCC port wave exists. |
| D-39 (verify-repro CLI + manifest, ±0.005 default tolerance) | ✓ | `RegistryConfig.repro_tolerance = 0.005` default; verify_repro.py honors `--tolerance` override; 8-field manifest. |
| D-40 (`automil check` warns on missing/stale repro_manifest.yaml) | ✓ | check.py:188-209 warns-not-fails on missing manifest or mtime older than newest variant. |
| D-41 (apply edits config.yaml only, atomic + rolling .bak) | ✓ | apply.py: tempfile+rename atomic write; single `.bak` rolling; idempotent. |
| D-42 (revert-baseline mandatory pre-stash) | ✓ | revert_baseline.py: stashes BEFORE checkout; surfaces stash name in stdout. |
| D-43 (port-variant auto-name `<parent>_v<short>`, idempotent) | ✓ | `_node_id_short()` extracts numeric tail; idempotent re-port no-op on matching node_id; mismatched node_id with same name hard-fails. |
| D-44 (sibling JSON manifest schema) | ✓ | manifest.py defines `Manifest(spec, source_node, source_overlay_files, ported_at, tool_version)`; cross-checked at refresh-registry. |
| D-45 (promote-variant git mv + stage but no auto-commit) | ✓ | promote_variant.py: `git mv` + refresh + `git add` but no `git commit`. |
| D-46 (`automil check` Phase 1 extensions) | ✓ | protected-files git-status, registry consistency (scan + manifest cross-check), repro-manifest mtime warn — all wired. |
| D-47 (Phase 0 baseline preserved + ≥30 net-new) | ✓ | 387 − 113 = 274 net-new tests (well above ≥30 floor; CONTEXT.md hard floor was ≥30, REQUIRED text was ≥220 — both exceeded). |
| D-48 (commit cadence target ~12, conventional commits) | ✓ | 60 commits across 12 plans + planning/tracking commits — well above 12 per-plan floor; messages follow `type(scope):` pattern. |
| D-49 (framework-only scope, no benchmarks/CCRCC code edits) | ✓ | `git status` shows zero src/automil/ → benchmarks coupling; only doc/example references in comments/templates (see Truth #8 detailed grep classification). |
| D-50 (REG-08/REG-09 reinterpreted as synthetic-consumer round-trip) | ✓ | `tests/test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes` is the Phase 1 acceptance gate; passes 1/1. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `src/automil/cli/lifecycle/revert_baseline.py` | 87 | Comment-string example mentions "benchmarks/lib/CLAM/**" | ℹ️ Info | User-facing error message uses an illustrative example glob. Not coupling — framework runs with empty `registry.protected` and no autobench dependency. Acceptable per D-33's "consumer-facing example" pattern. |
| `src/automil/orchestrator.py` | 621 | Pre-existing comment about autobench PYTHONPATH handling | ℹ️ Info | Phase-0 era comment about why PYTHONPATH is set. Not introduced by Phase 1. Phase 8 / DEC-01 will revisit when sklearn-iris consumer lands. |
| `src/automil/templates/config.yaml.j2` | 76 | Doc-comment example "- benchmarks/lib/CLAM/**" | ℹ️ Info | Scaffold-time template for consumer-side config; the example is **commented out** in the rendered config. No runtime coupling. |
| `src/automil/registry/manifest.py` | 31 | Comment `# e.g., "node_0176"` | ℹ️ Info | Field-comment using a representative node_id. No runtime coupling. |
| `src/automil/cli/lifecycle/port_variant.py` | 66, 94 | Doc/comment references "node_0176" / "CCRCC" | ℹ️ Info | Docstring example for `_node_id_short()` and a D-37 "CCRCC byte-identical port deferred" comment. No runtime coupling. |
| `src/automil/cli/lifecycle/verify_repro.py` | 84, 158 | Comment "no AUTOBENCH_* leakage" + docstring "Real consumers (CCRCC etc.)" | ℹ️ Info | First is a **hardening guard** ensuring the worktree env is whitelisted (intentional). Second is a docstring example. No runtime coupling. |
| `src/automil/registry/config.py` | 33 | Docstring "D-39: CCRCC ±0.005 carried as framework default" | ℹ️ Info | Decision-lineage docstring. No runtime coupling. |
| `src/automil/graph.py` | 681 | Pre-existing Phase-0 comment about historical zombie nodes | ℹ️ Info | Not introduced by Phase 1. |

**No 🛑 Blockers and no ⚠️ Warnings.** All grep matches against the framework-only scope check resolve to documentation/examples/explanatory comments — none represent runtime coupling, imports, branching, or hardcoded path dependencies. The framework code is consumer-agnostic by construction (empty `registry.protected`, registry-resolve API as the only contract surface, synthetic consumer as the framework-side acceptance fixture).

### Human Verification Required

None. All Phase 1 acceptance criteria are programmatically verifiable:

- ABC family + frozen dataclass: type-system + import test
- Registry singleton + decorator: round-trip test
- Validator chain: AST + reflection tests
- Protected files: integration test with `automil submit` + glob match
- CLI lifecycle commands: full integration tests + `--help` quality tests
- **Synthetic-consumer round-trip: PHASE 1 ACCEPTANCE GATE** — 1 test passes the full register→port→refresh→apply→verify-repro chain end-to-end with no mocks
- Framework-only scope: grep audits + zero benchmarks imports

The only "human follow-up" is a **deferred** demonstration (CCRCC `node_0176` ±0.005 reproduction on real GPU), which is explicitly out of Phase 1 scope per D-49/D-50 and captured as Phase 8 / DEC-07 work.

### Gaps Summary

**Zero gaps.** Phase 1 achieves its (reinterpreted-per-D-49/D-50) goal in full:

1. ✓ Framework registry contract shipped in `src/automil/registry/` (ABCs + spec + singleton + decorator + resolvers + scanner + manifest + 3 validators + config schema).
2. ✓ Six lifecycle CLI commands shipped in `src/automil/cli/lifecycle/` (apply, revert-baseline, refresh-registry, port-variant, promote-variant, verify-repro), each with full implementation, workflow `--help`, and integration tests.
3. ✓ Submit hook hard-rejects protected-file overlays + runs purity → interface validator chain short-circuit.
4. ✓ `automil init` scaffolds the variants/ skeleton + registry config keys.
5. ✓ Phase 1 acceptance gate `test_full_roundtrip_passes` PASSES via the REAL CLI pipeline with NO mock injection — the BLOCKER-02 contract (port-variant mutates graph.json with variant_spec; apply reads it back) is operationally exercised.
6. ✓ 387 total tests passing (113 baseline + 274 net-new vs ≥220 target); 60 commits across 12 plans.
7. ✓ Framework-only scope holds: `src/automil/registry/` and `src/automil/cli/lifecycle/` import zero autobench / ccrcc symbols; benchmarks/ccrcc references in framework code are exclusively in docstrings, examples, or pre-existing Phase-0 comments — not runtime coupling.

### Next-Step Recommendation

**Proceed to Phase 2** (Backend ABC + LocalBackend re-export shim + MockSLURM fixture). Phase 1 is complete and ready to ship; no closure work required.

Suggested operator follow-ups (NOT Phase 1 gates):

- **Consumer-side CCRCC follow-up (deferred per D-49/D-50):** an autobench follow-up may now use `automil port-variant node_0176` to convert the existing dirty edits in `benchmarks/lib/CLAM/` + `benchmarks/src/autobench/pipeline/clam/train.py` into a registered variant module, then `automil verify-repro node_0176` to demonstrate the ±0.005 reproduction on real GPU. This is consumer cleanup work that exercises the framework, not framework work.
- **Phase 2 prep:** the Phase 2 Backend ABC will inherit nothing from Phase 1 except the registry's ability to scope variants per `cell_id` (Phase 4) and gate-passing (`_candidates/` directory, Phase 5). No Phase 1 cleanup is needed before Phase 2 begins.

---

*Verified: 2026-05-02T08:46:04Z*
*Verifier: Claude (gsd-verifier, opus-4-7-1m)*
