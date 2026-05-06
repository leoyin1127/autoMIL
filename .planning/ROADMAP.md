# Roadmap: autoMIL — F2-readiness framework refactor

**Created:** 2026-05-01
**Granularity:** fine (9 phases)
**Mode:** yolo, parallelization: true
**Total v1 requirements:** 69 (mapped 100%)
**Source:** Requirements at `.planning/REQUIREMENTS.md`; phase ordering rationale at `.planning/research/SUMMARY.md`.

## Core Value

An agent can autonomously discover model improvements for any user's training code under a 6-hour-per-cell budget, with discovered variants reproducible, attributable to their parents, and portable across machines and LLM runtimes.

## Phases

- [ ] **Phase 0: Tier 2 cleanup + CLI split + compat shim** — close CONCERNS HIGH-severity items, split monolithic `cli.py`, add `compat.py` re-export so all 48 tests stay green
- [ ] **Phase 1: Variant registry + config-driven train + reproduction sanity** — keystone phase; ports CCRCC dirty edits to registered variants, validates with ±0.005 reproduction of `node_0176`
- [x] **Phase 2: Backend ABC + LocalBackend re-export + MockSLURM fixture** — design backend interface against ≥2 implementations before locking; ABC bounds Phase 6 (completed 2026-05-03)
- [x] **Phase 3: Trajectory recorder + multi-runtime asset reorg** — JSONL trajectories with OTel `gen_ai.*` keys + redaction; `agent_assets/_shared/` + per-runtime overlays; ≥2 runtimes validated end-to-end
- [x] **Phase 4: 6h per-cell hard cap + cell-concept formalization** — first-class `cell_id`, two-tier cap (refuse-new at T-buffer, terminate at T), per-fold checkpoint protocol, partial-result reconciliation (completed 2026-05-05)
- [x] **Phase 5: Generalization gate** — `candidate` node status, pre-registered `gate_manifest.json`, paired Wilcoxon + bootstrap CI + Bonferroni, manual nomination default, promotion-rate metric (completed 2026-05-06; calibration pilot K-determination deferred to Leo follow-up)
- [ ] **Phase 6: SLURM backend (submitit) + Ray backend (raw ray.remote)** — opt-in extras; honor wall-clock contract via `--signal=B:TERM@30` (SLURM) and `ray.cancel(force=True)` (Ray); parallel-friendly with Phase 7
- [ ] **Phase 7: Hardware autodetect + /automil-setup skill** — `LocalBackend.healthcheck()` reports detected hardware (warn-not-decide); idempotent setup skill across runtimes; mandatory dry-run gate
- [ ] **Phase 8: Decoupling completion + acceptance** — `grep -r autobench src/automil/` returns zero; sklearn-iris consumer runs end-to-end; final CCRCC `node_0176` ±0.005 reproduction on registry path

## Phase Details

### Phase 0: Tier 2 cleanup + CLI split + compat shim
**Goal**: Clear CONCERNS HIGH-severity backlog and prepare the codebase shape so new commands and modules have a place to land without disturbing existing tests.
**Depends on**: Nothing (first phase)
**Requirements**: CLN-01, CLN-02, CLN-03, CLN-04, CLN-05, CLN-06, CLN-07, CLI-07
**Success Criteria** (what must be TRUE):
  1. `git status` is clean of HIGH-severity CONCERNS runtime artefacts (Tier 2 follow-ups beyond the Tier 1 fixes shipped 2026-05-01); subprocess `env` no longer leaks full `os.environ` to children, `python-dotenv` parses `.env`, PID-file checks process start time, `nvidia-smi` invocation is path-pinned-or-reported.
  2. `automil <subcommand>` invocations are unchanged from a user perspective, but `cli.py` is split into per-command-group files under `src/automil/cli/` with a thin `__init__.py` aggregator (no individual file >300 lines).
  3. `from automil.X import Y` import paths from before the split still resolve via `compat.py` re-export shim; deprecation table is documented at the top of that file.
  4. `automil reconcile --recompute-best` rebuilds `meta.best_node_id` from the honest non-leaky composite by walking only `executed/keep` nodes (closes the T2 backlog from earlier this session).
  5. All 48 existing tests pass green; no new behaviour is introduced beyond the cleanup + restructure + reconcile flag.
**Plans**: 7 plans
  - [x] 00-01-PLAN.md — split src/automil/cli.py into per-command-group cli/ package (CLN-01, CLN-06)
  - [x] 00-02-PLAN.md — replace inline dotenv parser with python-dotenv (CLN-01, CLN-03)
  - [x] 00-03-PLAN.md — pin nvidia-smi path with shutil.which + automil check report (CLN-01, CLN-05)
  - [x] 00-04-PLAN.md — add compat.py with empty Active section + populated _PLANNED_MIGRATIONS dict (CLN-01, CLN-07)
  - [x] 00-05-PLAN.md — replace os.environ leak with explicit env whitelist + env.passthrough (CLN-01, CLN-02)
  - [x] 00-06-PLAN.md — PID-file JSON shape with starttime_ticks cross-check via /proc/<pid>/stat (CLN-01, CLN-04)
  - [x] 00-07-PLAN.md — automil reconcile --recompute-best with --dry-run flag (CLI-07)
**Estimated**: 2–3 days

### Phase 1: Variant registry + config-driven train.py + CCRCC reproduction sanity
**Goal**: Establish the keystone — variants live as committed code modules selected via config, shared library files become read-only, and the registry-only path reproduces CCRCC's honest best within ±0.005 from a clean checkout.
**Depends on**: Phase 0
**Requirements**: REG-01, REG-02, REG-03, REG-04, REG-05, REG-06, REG-07, REG-08, REG-09, CLI-01, CLI-02, CLI-05, CLI-06, CLI-08, CLI-09
**Success Criteria** (what must be TRUE):
  1. `Variant` ABC + frozen `VariantSpec` dataclass + internal `Registry` class with `@register` decorator + `importlib.metadata.entry_points` discovery exists; `automil refresh-registry` regenerates per-parent `variants/__init__.py` deterministically and idempotently.
  2. The submit pre-validator runs the validator chain (`identity`, `interface`, `purity`) and rejects any overlay touching `registry.protected` paths (e.g., `benchmarks/lib/CLAM/`); `automil check` fails on uncommitted edits to those paths and on missing env declarations.
  3. `train.py` reads model class, loss class, training policies, and hyperparameters from `automil/config.yaml`; zero `args.X = literal` overrides remain in framework code (verifiable via grep).
  4. CCRCC's current dirty edits are ported to registered variant modules at `experiments/ccrcc/automil/variants/clam_mb/clam_mb_v0176.py` + `losses/variants/ce_smooth008.py` + `training/policies/sam_lookahead.py` with a manifest committing parent commit, composite, and node id.
  5. **Reproduction sanity check passes**: from a clean checkout (no shared-file edits in working tree), CCRCC `node_0176` reproduces composite within ±0.005 via the registry-driven path.
  6. Variant lifecycle CLI is wired: `apply`, `revert-baseline`, `port-variant` (idempotent, rejects already-registered nodes), `promote-variant`, `refresh-registry`, `check` are all available and tested.
**Plans**: 12 plans across 6 waves (D-49 framework-only scope; CCRCC port deferred to consumer follow-up per D-50)
  - [x] 01-01-PLAN.md — Variant ABC family + VariantSpec frozen dataclass (REG-01)
  - [x] 01-02-PLAN.md — Registry singleton + @register decorator + resolvers (REG-02)
  - [x] 01-03-PLAN.md — Config schema + variants/ scaffolding to automil init (REG-04, REG-06, REG-07)
  - [x] 01-04-PLAN.md — Static validators: interface + purity (REG-03)
  - [x] 01-05-PLAN.md — Identity validator + mode-aware strictness (REG-03 identity, REG-06)
  - [x] 01-06-PLAN.md — Variant scanner + manifest schema (REG-02 scan, REG-08 manifest)
  - [x] 01-07-PLAN.md — Submit hook (protected-files reject + validator chain) + check extension (REG-03, REG-04, REG-05)
  - [x] 01-08-PLAN.md — Convert lifecycle.py stub to lifecycle/ package + register six command stubs (CLI-01/02/05/06/08/09)
  - [x] 01-09-PLAN.md — Implement apply (CLI-01) + refresh-registry (CLI-08)
  - [x] 01-10-PLAN.md — Implement revert-baseline with mandatory pre-stash (CLI-02)
  - [x] 01-11-PLAN.md — Implement port-variant (CLI-05) + promote-variant (CLI-06)
  - [x] 01-12-PLAN.md — Implement verify-repro + synthetic mini-consumer round-trip (REG-08, REG-09, CLI-09 — Phase 1 acceptance)
**Estimated**: 5–7 days

### Phase 2: Backend ABC + LocalBackend re-export shim + MockSLURM fixture
**Goal**: Land a backend interface designed against ≥2 implementations (real local + mock SLURM) so the abstraction does NOT freeze local-backend semantics (PIDs, sync status, killpg) into the contract that Phase 6 will inherit.
**Depends on**: Phase 1
**Requirements**: BCK-01, BCK-02, BCK-03, BCK-04, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. `Backend` ABC defines `submit(spec) -> JobHandle`, `poll(handle) -> JobState`, `list_running() -> [JobHandle]`, `cancel(handle, signal) -> None`, `log_iter(handle) -> Iterator[str]` with a state-not-control-flow `JobState` enum (`pending | running | completed | crashed | cancelled | budget_killed`).
  2. `LocalBackend` ships as a re-export shim over the existing 750-line orchestrator code; the existing 48-test suite passes against it with empty behavioural diff.
  3. `MockSLURMBackend` test fixture simulates eventual-consistency status (5s poll lag), opaque `job_id`, fire-and-forget `cancel`, node-local filesystem; the ABC's contract is exercised against both backends via shared parameterised tests BEFORE the ABC is locked.
  4. A ruff/mypy custom rule lint-blocks `os.kill`, `Popen`, and `pid` references outside `backends/local.py` and `backends/_orchestrator_daemon.py`.
  5. `automil cancel <node_id>` and `automil resubmit <node_id>` are wired through `Backend.cancel` and `Backend.submit`; cancelled nodes archive with `status: cancelled` and resubmits get a fresh worktree.
**Plans**: 8 plans across 5 waves
  - [x] 02-01-PLAN.md — Backend ABC + JobHandle/JobSpec/JobState dataclasses + errors.py + test package skeleton (BCK-01) — wave 1
  - [x] 02-02-PLAN.md — BACKENDS registry singleton + @register decorator (extends 02-01's __init__.py) (BCK-01) — wave 2
  - [x] 02-03-PLAN.md — Extend cli/submit.py to write metadata.backend to queue spec (BCK-01, CLI-03/04 prereq) — wave 1
  - [x] 02-04-PLAN.md — git mv orchestrator.py → _orchestrator_daemon.py + 5-line re-export shim + compat.py update (BCK-02) — wave 2
  - [x] 02-05-PLAN.md — LocalBackend thin adapter over _orchestrator_daemon + auto-register (BCK-02) — wave 3
  - [x] 02-06-PLAN.md — MockSLURMBackend eventual-consistency fixture (BCK-03) — wave 3
  - [x] 02-07-PLAN.md — Parameterised contract test (≥12 scenarios × 2 backends) + BCK-04 AST lint script + lint pytest gate (BCK-01, BCK-03, BCK-04) — wave 4 ✓ commit 5b88e76
  - [x] 02-08-PLAN.md — automil cancel + automil resubmit CLI commands + integration tests against MockSLURM (CLI-03, CLI-04) — wave 5
**Estimated**: 3–4 days

### Phase 3: Trajectory recorder + multi-runtime asset reorganisation
**Goal**: Capture per-submit agent prompt + tool-call trajectories as bounded, redacted, schema-versioned JSONL files; reorganise `agent_assets/` so the canonical content lives under `_shared/` with per-runtime overlays only — and prove ≥2 runtimes run an experiment loop end-to-end.
**Depends on**: Phase 2
**Requirements**: TRJ-01, TRJ-02, TRJ-03, TRJ-04, TRJ-05, TRJ-06, MRT-01, MRT-02, MRT-03, MRT-04, MRT-05, MRT-06
**Success Criteria** (what must be TRUE):
  1. `archive/<node_id>/trajectory.jsonl` is the canonical artifact; first line is metadata `{schema_version, runtime, runtime_version, tool_schema_version, automil_version, automil_runtime_env}`; subsequent lines are one event each using OpenTelemetry `gen_ai.*` field names with no runtime `opentelemetry-sdk` dependency.
  2. Redaction-on-capture catches `sk-…`, `hf_…`, `ghp_…`, AWS access keys, `*_API_KEY=…`, `*_TOKEN=…`; per-event 8 KB cap; per-file 5 MB soft / 50 MB hard rotate producing `trajectory.<n>.jsonl` siblings; trajectories are gitignored by default and `automil trajectory export` produces a redacted, schema-validated bundle.
  3. `src/automil/agent_assets/_shared/SKILL.md` is the canonical skill content; `claude/`, `codex/`, `opencode/` directories contain ONLY diffs/overrides; `agent_assets/deepseek/README.md` documents that DeepSeek is a *model* routed via opencode/Codex/etc.
  4. `automil init --runtime <claude|codex|opencode|deepseek-via-X>` works with explicit selection AND auto-detection from existing `.claude/`, `.codex/`, `.opencode/`; `AGENTS.md` is generated at the project root; `automil show-skill --runtime <name>` renders the merged per-runtime SKILL/AGENTS file.
  5. End-to-end smoke test: an experiment loop submits, runs, completes, and writes a valid `result.json` under Claude Code AND under one of {opencode, codex} — trajectories captured for both, schema-version metadata correct, redaction tests cover each leak class.
**Plans**: 11 plans across 5 waves
  - [x] 03-01-PLAN.md — trajectory package skeleton + schema + redactor + recorder fd-cache (TRJ-01, TRJ-02) — wave 1
  - [x] 03-02-PLAN.md — agent_assets/ git mv migration + AGENTS.md + deepseek README + compat shim (MRT-01, MRT-06) — wave 1
  - [x] 03-03-PLAN.md — redactor positive-case tests + schema version forward-compat (TRJ-03, TRJ-06) — wave 2
  - [x] 03-04-PLAN.md — full rotation manager 5MB/50MB + atomic rename + tests (TRJ-03) — wave 2
  - [x] 03-05-PLAN.md — overlay merger _overlay.py + test suite (MRT-01) — wave 2
  - [x] 03-06-PLAN.md — runtime.py + submit.py metadata.runtime + config.yaml.j2 passthrough (TRJ-04) — wave 2
  - [x] 03-07-PLAN.md — automil init --runtime + --update + auto-detect + AGENTS.md render (MRT-02, MRT-03) — wave 3
  - [x] 03-08-PLAN.md — automil show-skill --runtime command (MRT-04) — wave 3
  - [x] 03-09-PLAN.md — automil trajectory record/export CLI + recorder tests + export bundle (TRJ-04, TRJ-05) — wave 3
  - [x] 03-10-PLAN.md — Claude hook + opencode TS plugin + codex README + gitignore trajectory entries (TRJ-04, TRJ-05) — wave 4
  - [x] 03-11-PLAN.md — two-runtime smoke test + Phase 3 acceptance gate (TRJ-05, TRJ-06, MRT-05) — wave 5
**Estimated**: 4–5 days

### Phase 4: 6h per-cell hard cap + cell-concept formalisation
**Goal**: Make `(dataset, encoder, parent_id)` a first-class graph entity with a framework-enforced wall-clock budget; the cap fires gracefully via per-fold checkpoints and budget-killed runs reconcile to `executed` (with partial composite) — never `crash`.
**Depends on**: Phase 3
**Requirements**: CAP-01, CAP-02, CAP-03, CAP-04, CAP-05, CAP-06
**Success Criteria** (what must be TRUE):
  1. `cells/<cell_id>.json` state files persist `started_at`, `budget_seconds`, `consumed_seconds`, status (`active | refusing-new | terminating | finalized`); `cell_started_at` and `consumed_seconds` survive daemon restart (verified via kill-9 + restart test).
  2. Two-tier cap is enforced: at `T - safety_buffer` (default 30 min) the cell enters `refusing-new` and the orchestrator rejects new submits for that cell with a structured reason; at `T` the cell enters `terminating` and running experiments are killed via `Backend.cancel`.
  3. Per-fold checkpoint protocol works: `train.py` writes `fold_<i>_result.json` after each fold; `result.json` aggregates across completed folds with `status: partial | completed`; a deliberate cap-firing test produces a usable partial result, VRAM returns, and descendants are NOT spuriously discarded.
  4. Budget-killed experiments reconcile to `executed` (NOT `crash`) with whatever partial composite is computable; descendant cascade recomputes against the partial composite, not against zero.
  5. `automil cell status [cell_id]` and `automil cell list` surface budget state for operator inspection (started_at, consumed, remaining, refusing-new threshold, status).
**Plans**: 10 plans across 7 waves (Wave 1: 04-01/02/08 parallel; Waves 2-4 serial through cells/__init__.py; Wave 5: 04-06/07 parallel; Wave 6: 04-09; Wave 7: 04-10 anti-acceptance)
  - [ ] 04-01-PLAN.md — cells package skeleton + Cell dataclass + atomic IO + cell_id (CAP-01, CAP-05)
  - [ ] 04-02-PLAN.md — runtime_helpers.py + register_sigterm_flush + get_fold_count (CAP-03)
  - [ ] 04-03-PLAN.md — cap.py pure state machine + exhaustive transition tests (CAP-02)
  - [ ] 04-04-PLAN.md — reconcile.py aggregate_folds + reconcile_budget_kill stub (CAP-03, CAP-04)
  - [ ] 04-05-PLAN.md — registry.py get_or_create_cell + idempotency + restart-safety (CAP-01, CAP-05)
  - [ ] 04-06-PLAN.md — submit.py cell refusal hook + metadata.cell_id + --budget-seconds CLI override + config.yaml.j2 cap: section (CAP-01, CAP-02)
  - [ ] 04-07-PLAN.md — _orchestrator_daemon.py _tick_cells + reconcile integration + AUTOMIL_FOLD_COUNT env injection (CAP-02, CAP-04)
  - [ ] 04-08-PLAN.md — autobench runner.py per-fold writer + run_experiment.py register_sigterm_flush call (CAP-03)
  - [ ] 04-09-PLAN.md — automil cell status / list CLI + cli/__init__.py registration (CAP-06)
  - [ ] 04-10-PLAN.md — Pitfall-4 anti-acceptance gate + daemon-restart test + reconcile-cascade test (CAP-03, CAP-04, CAP-05)
**Estimated**: 3–4 days

### Phase 5: Generalization gate
**Goal**: A candidate variant is only promoted to the parent's registered variants directory after improving on ≥K held-out cells (declared BEFORE search starts), measured by a paired statistical test — defending the F2 reviewer attack "you overfit to the search cell."
**Depends on**: Phase 4
**Requirements**: GTE-01, GTE-02, GTE-03, GTE-04, GTE-05, GTE-06
**Success Criteria** (what must be TRUE):
  1. Node status `candidate` exists between `executed/keep` and `registered`; candidates carry a `gate_manifest.json` listing held-out cells they must improve on; the manifest is committed to git BEFORE search starts (pre-registration).
  2. Gate spawns held-out evaluations via `Backend.submit()` (same path as agent submits, NOT a parallel mechanism); gate node has child eval-nodes with explicit `gate_eval` edge type; auto-nomination is OFF by default — `automil nominate <node>` is the trigger.
  3. Promotion criterion is a paired Wilcoxon (or comparable test from `gate_manifest.json`) with bootstrap CI (1000 reps) and Bonferroni correction across held-out cells; `K` (minimum cells passed) and `p_threshold` are config-set, not gut-feel constants.
  4. Promotion-rate metric (% of nominated candidates that passed gate) is exposed in the viz dashboard and `automil status`; a calibration pilot (CCRCC `node_0176` applied to 3–5 fresh cells) sets initial K before locking.
  5. Held-out cells are NEVER visible to the agent during search (verified via trajectory inspection in CI).
**Plans**: 12 plans across 9 waves
  - [ ] 05-01-PLAN.md (W1) — gate package skeleton + stats.py (paired Wilcoxon + BCa bootstrap + Bonferroni divide direction) (GTE-04)
  - [ ] 05-03-PLAN.md (W1) — JobSpec.metadata field + LocalBackend/MockSLURM passthrough (GTE-03 prerequisite)
  - [ ] 05-02-PLAN.md (W2) — manifest.py: GateManifest frozen dataclass + atomic write + write_manifest_committed (Leo memory rollback via path.unlink) + retire flow (GTE-01, GTE-02)
  - [ ] 05-04-PLAN.md (W3) — gate.nominate keep->candidate idempotent + ExperimentGraph.nominations_in_window/promotion_rate helpers (GTE-01, GTE-05, GTE-06)
  - [ ] 05-05-PLAN.md (W3) — trajectory redactor extension (held-out node-id placeholder, mtime-cached) + cli/propose.py rank held-out filter (GTE-01)
  - [ ] 05-06-PLAN.md (W4) — gate.evaluate_candidate: Backend.submit per held-out cell + concurrent poll + skip-on-cap (GTE-03)
  - [ ] 05-07-PLAN.md (W5) — gate.promote: pass/fail/inconclusive + Bonferroni-corrected paired test + gate_log emission + two-stage gate (GTE-01, GTE-04, GTE-06)
  - [ ] 05-08-PLAN.md (W6) — automil gate group + register/retire/status/stats subcommands + scipy lift to core deps + config.yaml.j2 gate: section (GTE-01, GTE-02, GTE-04, GTE-06)
  - [ ] 05-09-PLAN.md (W7) — automil nominate + automil promote (--calibrate) top-level CLI commands (GTE-05)
  - [ ] 05-10-PLAN.md (W7) — viz /api/promotion-rate endpoint + automil status promotion_rate display (GTE-06)
  - [ ] 05-11-PLAN.md (W8) — Pitfall-6 anti-acceptance test (D-149, 9 load-bearing assertions) + framework-purity guard + BCK-04 lint extension to gate/ (GTE-01..06)
  - [ ] 05-12-PLAN.md (W9) — Calibration pilot smoke test + .planning/phase-05-calibration.md scaffold + Leo CHECKPOINT to run actual pilot (D-151) (GTE-04, GTE-06)
**Estimated**: 4–5 days

### Phase 6: SLURM backend (submitit) + Ray backend (raw ray.remote)
**Goal**: Land two opt-in distributed backends on top of the locked Phase 2 ABC so the framework runs identically on a single laptop, a SLURM HPC cluster, and a Ray cluster. Both honor the wall-clock contract from Phase 4.
**Depends on**: Phase 2 (Backend ABC), Phase 4 (cap contract). Parallel-friendly with Phase 7 — different engineer or session can drive each.
**Requirements**: BCK-05, BCK-06
**Success Criteria** (what must be TRUE):
  1. `SLURMBackend` (`backends/slurm.py`) on top of `submitit>=1.5.3` is opt-in via `pip install -e '.[slurm]'`; SLURM directives include `--time --signal=B:TERM@30` so SLURM kills with a 30s warning that matches the framework's wall-clock contract.
  2. `RayBackend` (`backends/ray.py`) on top of `ray>=2.55.1` uses raw `ray.remote` + placement groups (NOT `ray.tune`); opt-in via `pip install -e '.[ray]'`; `ray.get(timeout=...)` + `ray.cancel(force=True)` honor wall-clock contract.
  3. Both backends pass the same shared parameterised test suite the MockSLURM fixture passes in Phase 2; no `os.kill` / `Popen` / `pid` references in either implementation.
  4. Per-backend `running/<id>.json` ownership is namespaced (`running/local/`, `running/slurm/`, `running/ray/`) so backends do not corrupt each other; cross-backend log unification copies into `archive/<id>/run.log` on completion.
  5. A SLURM-installed user can run a CCRCC variant end-to-end via `pip install -e '.[slurm]'` with no other code changes.
**Plans**: TBD
**Estimated**: 5–7 days

### Phase 7: Hardware autodetect + /automil-setup skill
**Goal**: Make autoMIL one-shot deployable onto an arbitrary user repo: hardware is detected and reported (warn-not-decide), the `/automil-setup` skill drafts config + scaffolds variants from inspection, and setup is not "done" until `automil check` AND a 1-minute dry-run experiment both pass.
**Depends on**: Phase 6 (needs framework shape stable; calibration depends on layers below). Parallel-friendly with Phase 6 in practice — Phase 7 hardware-detect work can begin once Phase 4 cap lands.
**Requirements**: STP-01, STP-02, STP-03, STP-04, STP-05, STP-06, STP-07
**Success Criteria** (what must be TRUE):
  1. `LocalBackend.healthcheck()` reports detected GPU count, VRAM per GPU, accelerator type (CUDA / ROCm / CPU), Python version, autoMIL version; output is a *report*, not a *decision* — `automil init` prints values and prompts override on detection failure, never silently uses wrong defaults.
  2. `automil init` consumes healthcheck output and pre-fills `automil/config.yaml` defaults (`max_concurrent_per_gpu`, `default_vram_estimate_gb` derived from `quantile_95` of empirical `results.tsv` if available, else conservative defaults).
  3. `/automil-setup` skill (Claude `.claude/skills/automil-setup/SKILL.md`) inspects an arbitrary repo, identifies the training entry point, drafts `automil/config.yaml` + `program.md`, scaffolds a starter `variants/` skeleton, picks defaults from healthcheck — interactively confirming at every ambiguous decision point.
  4. Setup is idempotent: re-running on an already-initialised project diffs and updates rather than overwriting; mandatory `automil check` + 1-minute dry-run experiment must both pass before setup reports "done".
  5. Skill ships per-runtime overlays at `_shared/automil-setup/SKILL.md` canonical, with `claude/`, `codex/`, `opencode/` overrides; tested on ≥3 hardware shapes (single-GPU laptop, current 3-GPU workstation, one external) — output reported, not silent — OR portability is documented as MEDIUM with override path documented.
**Plans**: TBD
**Estimated**: 4–5 days

### Phase 8: Decoupling completion + acceptance
**Goal**: Audit the framework end-to-end for autobench leakage, prove genericity by plugging in a second consumer (sklearn-iris), and run the final acceptance gate — CCRCC `node_0176` reproduces ±0.005 on a clean checkout via the registry path with all phases composed together.
**Depends on**: All prior phases (8 audits work threaded through 1–7).
**Requirements**: DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07
**Success Criteria** (what must be TRUE):
  1. `grep -r "autobench\|AUTOBENCH_" src/automil/` returns zero matches; equivalent for any other autobench-specific identifier (verified in CI).
  2. A sklearn-iris training script (the second consumer) plugs into autoMIL via the documented contract and runs an experiment loop end-to-end; `result.json` is JSON-Schema-validated at ingestion and the orchestrator rejects malformed results with a clear pointer to the schema location.
  3. Composite scoring is config-driven (`automil/config.yaml: scoring.formula` or `scoring.entry_point`); no hardcoded coupling to autobench's 4-key (val_auc + val_bacc + test_auc + test_bacc) recipe; required env vars are declared in `automil/config.yaml: env.required` and validated by `automil check` (missing vars fail fast at startup).
  4. `docs/training-script-contract.md` documents the contract: write `result.json`, accept `CUDA_VISIBLE_DEVICES`, exit cleanly on SIGTERM with partial-fold output, declared env vars.
  5. **Final acceptance**: clean checkout, registry path, fresh worktree, all phases composed — CCRCC `node_0176` reproduces composite within ±0.005 AND the same harness runs the sklearn-iris consumer end-to-end as the decoupling proof.
**Plans**: TBD
**Estimated**: 3–4 days

## Phase Dependency Graph

```
Phase 0 (cleanup, CLI split, compat shim, reconcile --recompute-best)
   │
   ▼
Phase 1 (registry + config-driven train + CCRCC reproduction)  ◄── KEYSTONE
   │
   ▼
Phase 2 (Backend ABC + LocalBackend shim + MockSLURM)  ◄── BOUNDS Phase 6
   │
   ▼
Phase 3 (trajectory + multi-runtime reorg)
   │
   ▼
Phase 4 (6h cap + cell formalisation + per-fold protocol)
   │
   ▼
Phase 5 (generalization gate)
   │
   ├──> Phase 6 (SLURM + Ray)        ─┐
   │                                  ├── parallel-friendly
   └──> Phase 7 (autodetect + setup) ─┘
            │
            ▼
        Phase 8 (decoupling audit + sklearn-iris consumer + final acceptance)
```

**Parallel-execution candidates** (with `parallelization: true`):
- **Phase 6 ↔ Phase 7** are the strongest parallel pair: Phase 6 lives entirely under `backends/`, Phase 7 lives under `agent_assets/automil-setup/` + `LocalBackend.healthcheck()`; they touch disjoint files and both depend on the same upstream layers (1–5). Two parallel sessions or worktrees can drive these.
- **Within Phase 3**, the trajectory recorder (`trajectory/`) and the multi-runtime asset reorg (`agent_assets/`) are decoupled implementation areas and can land as separate PRs in parallel; they share only the `AUTOMIL_RUNTIME` env declaration.
- **Within Phase 1**, the registry layer + validators (`registry/`) and the config-driven train.py refactor (`benchmarks/src/autobench/pipeline/clam/train.py` + `run_experiment.py`) are decoupled; the CCRCC variant porting and reproduction sanity check is the join point that requires both done.

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Cleanup + CLI split + compat | 0/7 | Not started | - |
| 1. Registry + config-driven train + CCRCC reproduction | 0/12 | Not started | - |
| 2. Backend ABC + LocalBackend + MockSLURM | 8/8 | Complete   | 2026-05-03 |
| 3. Trajectory + multi-runtime reorg | 11/11 | Complete   | 2026-05-04 |
| 4. 6h per-cell cap + cell formalisation | 0/0 | Not started | - |
| 5. Generalization gate | 0/0 | Not started | - |
| 6. SLURM + Ray backends | 0/0 | Not started | - |
| 7. Hardware autodetect + /automil-setup | 0/0 | Not started | - |
| 8. Decoupling audit + acceptance | 0/0 | Not started | - |

## Coverage

✓ All 69 v1 requirements mapped to exactly one phase
✓ No orphaned requirements
✓ No duplicate requirement → phase mappings
✓ Every phase has a clear goal, mapped requirements, observable success criteria, and explicit upstream dependencies

**Note on requirement count:** The orchestrator-supplied instruction stated "60 v1 REQ-IDs"; the actual REQUIREMENTS.md file lists **69** v1 REQ-IDs (CLN×7 + REG×9 + BCK×6 + TRJ×6 + MRT×6 + CAP×6 + GTE×6 + CLI×9 + STP×7 + DEC×7). All 69 are mapped below.

## Anti-Acceptance Notes (carried from research/PITFALLS.md)

- **Phase 1**: Reproduction sanity check MUST run from a clean checkout where protected files are guaranteed unmodified — otherwise it accidentally validates the dirty path.
- **Phase 2**: ABC must be designed against ≥2 implementations (real local + mock SLURM) IN THE SAME PHASE — designing against one impl freezes its semantics into the contract.
- **Phase 3**: "Multi-runtime support" means an experiment loop runs end-to-end on ≥2 runtimes — not "scaffolding written for ≥2 runtimes." Untested-but-claimed is the F2 reviewer attack.
- **Phase 4**: Cap MUST ship with the per-fold checkpoint protocol; without it the first cap-firing event loses K-1 folds × N concurrent experiments.
- **Phase 5**: Held-out cells MUST be pre-registered AND invisible to the agent during search; gate using same-cells-as-search is theatre that hides leakage.
- **Phase 7**: Hardware autodetect is detect-and-WARN, never detect-and-decide; silent wrong defaults are auto-failure.
- **Phase 8**: Decoupling without a second consumer is "renaming." sklearn-iris must run end-to-end before signing off.

---
*Roadmap created: 2026-05-01 by gsd-roadmapper*
*Phase ordering follows research/SUMMARY.md "Implications for Roadmap" verbatim with rationale preserved.*
