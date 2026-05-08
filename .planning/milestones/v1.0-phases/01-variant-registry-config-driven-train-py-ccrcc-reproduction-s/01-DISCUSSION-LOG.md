# Phase 1: Variant registry — Discussion Log

**Date:** 2026-05-02
**Workflow:** `/gsd-discuss-phase 1 --all`
**Mode:** Engineering decisions self-locked (Leo's directive 2026-05-02 — "decide engineering questions yourself; ask only user/feature questions"). No interactive Q&A round; rationale below.

---

## Why no interactive Q&A

Phase 1 is a refactor, not a feature decision. After surveying the 15 REQ-IDs (REG-01..09 + CLI-01/02/05/06/08/09), every gray area I identified was an engineering question with a clear production-best-practice answer:

- ABC shape (one polymorphic vs three sibling) — Liskov + interface segregation answer it.
- Variant module layout — file-organization principles answer it.
- train.py config contract — registry-pattern semantics answer it.
- Validator chain semantics — fail-fast + static-vs-runtime separation answer it.
- Protected files enforcement — security-gate principle (no soft-warn substitutes for required gates) answers it.
- CCRCC port mechanics — byte-identical-body-with-adapted-wrapper is the standard refactor pattern.
- Reproduction sanity gate type — operator-triggered command + committed manifest is the production pattern for expensive integration tests.
- CLI semantics (`apply` edits config not code; `revert-baseline` is anti-protected; `port-variant` auto-names) — registry-first invariant constrains all of them.

Per Leo's directive, none of these warrant blocking on Q&A. Decisions are documented in CONTEXT.md as D-21..D-48 with rationale; downstream agents (researcher / planner / executor) honour them verbatim.

---

## Decisions logged

| ID | Topic | Locked decision | Rationale (one line) |
|---|---|---|---|
| D-21 | Variant ABC shape | Three sibling ABCs (`ModelVariant`, `LossVariant`, `PolicyVariant`) | Single ABC violates Liskov for non-`forward` kinds (loss has no features/coords) |
| D-22 | `VariantSpec` dataclass | `@dataclass(frozen=True)` with `name, kind, parent, base_commit, composite, node_id, created_at, mutations` | Frozen because spec is registry key + provenance record |
| D-23 | `kind` taxonomy | Phase 1: `Literal["model", "loss", "policy"]` only | `recipe` is composition; `inference` is Phase 5+ |
| D-24 | `AggregatorOutput` | NOT introduced in Phase 1 | Locking framework output type now constrains Phase 8's second-consumer (sklearn-iris) integration |
| D-25 | Variant directory layout | Flat under `<consumer>/<dataset>/automil/variants/` with `<parent>/`, `_losses/`, `_policies/` subdirs | Single root for `refresh-registry` scan + Python convention for shared subpackages |
| D-26 | Variant module shape | Single `.py` file per variant (NOT a package) + mandatory header docstring | If too big to fit one file, it's two variants |
| D-27 | Registry storage | Module-level singleton with three keyed dicts populated by `@register` decorator | In-process is enough for Phase 1 |
| D-28 | Cross-project discovery | DEFERRED to Phase 7 / STP-04 | Entry_points become useful when third-party variant packages exist |
| D-29 | `refresh-registry` output | Imports-only `__init__.py` (NOT a hardcoded dict) | Dict lives in singleton; `__init__.py` is just an import-side-effect manifest |
| D-30 | Validator timing split | `interface` + `purity` at submit-time (static); `identity` at instantiate-time (runtime) | Static checks should fail before queueing; shape checks need runtime tensors |
| D-31 | Mode flag effect | Mode (`free` default \| `architecture-preserving`) modulates `identity` strictness only | Hygiene validators (interface, purity) always run regardless of mode |
| D-32 | Validator failure semantics | Hard-fail at submit-time + checkpoint-to-disk hard-fail at instantiate-time | Soft-warn substitutes for required gates defeat Pitfall 1 |
| D-33 | Protected-files config location | Consumer-side `automil/config.yaml: registry.protected`, no framework defaults | "autoMIL is generic" — framework can't know consumer's load-bearing files |
| D-34 | Submit enforcement | Hard-fail with no `--force` escape hatch in Phase 1 | Don't ship escape hatches against speculation |
| D-35 | Variant selection in config | Short name (`model.variant: clam_mb_v0176`) via registry, NOT import path or full class dict | Registry pattern's purpose is to make selection decoupled from filesystem layout |
| D-36 | `args.X = literal` rule | Pragmatic — banned for architectural surface; allowed for tunable hyperparameters | Phase 1's gate is variant-via-config; numeric tuning is GTE's concern |
| D-37 | CCRCC port mechanics | Variant body byte-identical, wrapper adapted (free-function-edit → ABC subclass override) | REG-09 reproduction gate is the safety net |
| D-38 | Port plan ordering | port-CCRCC → train.py-refactor → verify-repro is Wave 4–5 SERIAL | Reproduction safety can't be parallelised |
| D-39 | Reproduction gate type | CLI command (`automil verify-repro`) + committed `repro_manifest.yaml` | 4h training is untenable as CI; pure recorded-result without rerun defeats the gate |
| D-40 | `automil check` repro reporting | Warn-not-fail on missing/stale manifest | Failing on missing blocks normal development |
| D-41 | `automil apply <node_id>` semantics | Edits `automil/config.yaml` variant selection, NOT codebase | Registry-first invariant: variant code is committed; apply is config-only |
| D-42 | `automil revert-baseline` semantics | `git checkout <base_commit> -- <paths_not_in_protected>` with mandatory pre-stash | Per "never blind-checkout" memory + anti-protected = implicit "editable" |
| D-43 | `port-variant` auto-naming | `<parent>_v<node_id_short>` default; `--name` override; idempotent on matching node_id | Auto-name is cheaper than prompts; mismatch is hard-fail to prevent silent overwrite |
| D-44 | Manifest format | Sibling `<name>.json` next to `<name>.py` with VariantSpec + provenance | JSON for parser stability; YAML adds dependency cost without benefit |
| D-45 | `promote-variant` Phase 1 stub | Full implementation + `_candidates/` directory existence; gate-passing pipeline is Phase 5 | Ship the command now to prove the registry path; gate fires when GTE lands |
| D-46 | `automil check` Phase 1 additions | protected-files + registry-consistency + repro-manifest (warn); env-required + runtime-asset + sample-size DEFERRED | Each deferred check is owned by a future phase that creates the surface to check against |
| D-47 | Test posture | ≥30 net-new tests; reproduction-sanity NOT in pytest suite | 4h training is untenable as CI; verify-repro lands in committed manifest |
| D-48 | Commit cadence | ~12 commits across Phase 1 (one per plan) at `fine` granularity | Matches Phase 0 cadence; planner decides plan boundaries |

---

## Notable deviations from REQUIREMENTS.md text

- **REG-08 named layout:** REQ text places losses under `losses/variants/` and policies under `training/policies/` as siblings of `variants/`. Phase 1 deviates: all three live under `variants/` with kind-subdirs (`<parent>/`, `_losses/`, `_policies/`). Reasoning: single scan root for `refresh-registry`; symmetric layout. Documented in D-25 with explicit "deviates from REG-08's literal text" note.
- **REG-01 4-tuple kind taxonomy:** REQ text mentions `architectural | recipe | training-policy | inference`. Phase 1 ships `model | loss | policy` only — `recipe` is composition, `inference` is Phase 5+. Documented in D-23.
- **REG-07 "zero `args.X = literal` overrides":** Phase 1 interprets pragmatically as "zero ARCHITECTURAL overrides" — numeric hyperparameter tuning is allowed. Documented in D-36 with the verification grep pattern.

---

## Open questions for downstream agents (none for Leo)

The researcher and planner may surface implementation questions that emerge once they investigate (e.g., does CLAM's `clam_train()` cleanly accept a registry-resolved model, or does it require argparse-namespace mocking? — investigate at planning time, decide at planner discretion). These are Claude's Discretion items per D-49 (the catch-all in CONTEXT.md's `<decisions>` block).

If any downstream investigation surfaces a question that genuinely needs Leo's vision (a feature/UX decision, not engineering), that agent should escalate via the standard checkpoint mechanism rather than guessing.

---

*Discussion-log written: 2026-05-02 by orchestrator (no interactive Q&A; engineering self-locked per directive).*

---

## 2026-05-02 scope refinement (Leo)

After CONTEXT.md was committed (`4b5a094`) and the plan-phase researcher had been spawned, Leo issued a scope clarification:

> "the exps we done in the /benchmarks/experiments directory are one specific exp case. it is a usecase of our automil framework. what you should develop is the framework itself. if the things you are about to change in the benchmark directory is to fix the previous issues, then is was okay or could be just ignored since the experiment design has been changed. so ensure your focus is the framework itself."

**Effect on Phase 1:**

- `benchmarks/experiments/ccrcc/` is treated as ONE consumer's data, not a framework validation target. The existing dirty edits across `benchmarks/lib/CLAM/{models/model_clam.py, utils/core_utils.py}` and `benchmarks/src/autobench/pipeline/clam/train.py` may be obsolete (the experiment design has drifted).
- REG-08 (CCRCC port) is **deferred** to consumer-side follow-up. Phase 1 ships the framework `port-variant` command + layout + manifest format that ANY consumer (including CCRCC) can use; populating actual CCRCC variant modules is not Phase 1 work.
- REG-09 (CCRCC `node_0176` ±0.005 reproduction) is **reinterpreted**. Phase 1 acceptance is "framework `verify-repro` works correctly on a synthetic mini-consumer in `tests/fixtures/`." CCRCC reproduction demonstration is consumer-side follow-up.
- D-37, D-38, D-39, D-40 amended to reflect the framework-only scope. D-49 and D-50 added to document the refinement explicitly.
- Wave structure collapses from 4–5 to ~4 waves (the CCRCC port + train.py refactor + verify-repro serial chain in old W4–W5 is replaced by a single synthetic-consumer round-trip plan in the new W4).
- Memory updated: `feedback_decide_engineering_ask_features.md` and `project_automil_is_generic.md` (the latter expanded with the 2026-05-02 refinement section).

**Why this didn't surface in the original gray-area sweep:**

I had the "autoMIL is generic, autobench is one consumer" memory but interpreted it as "don't bake autobench-specific names into `src/automil/`," not as "treat existing benchmarks/ artifacts as obsolete unless explicitly load-bearing." Leo's clarification distinguishes those two — the framework code stays clean (which I had right) AND the framework dev target excludes consumer-side cleanup work (which I missed).

**Researcher disposition:**

The in-flight researcher (opus, spawned before this clarification) stalled at 600s with a stream watchdog timeout. RESEARCH.md was never written. Given the scope refinement makes Question 7 (CCRCC port mapping) deprioritized, the researcher is **not** being respawned. The planner proceeds with CONTEXT.md (28 + 2 = 30 decisions) + PATTERNS.md (29KB of codebase analogs).

---

*Scope refinement logged: 2026-05-02. CONTEXT.md updated; planner brief tightened to framework-only.*
