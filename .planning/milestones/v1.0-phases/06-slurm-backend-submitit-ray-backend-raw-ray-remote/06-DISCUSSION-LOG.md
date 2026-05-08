# Phase 6 — Discussion Log

**Date:** 2026-05-06
**Mode:** Auto / autonomous bootstrap (no interactive deep-dive — Leo directed engineering decisions to be locked autonomously per memory `feedback_decide_engineering_ask_features`)

## Bootstrap interaction

**Q (workflow):** Phase 6 has 4 implementation gray areas. Which do you want to discuss before I lock CONTEXT.md? (Unselected ones I'll decide autonomously per memory and bootstrap with the recommended option.)

Options presented (multiSelect):
1. **SLURM directives source** (Recommended) — Pure passthrough vs starter template vs hybrid (framework-defaults-plus-consumer-cluster-specific).
2. **Ray cluster init lifecycle** — Auto-init local vs require existing cluster vs hybrid.
3. **`running/` namespace migration policy** — Breaking change vs backward-compat read vs auto-migrate.
4. **Cross-backend test infrastructure scope** — Real-cluster only vs in-process simulation vs hybrid.

**A (Leo, 2026-05-06):** "no need to discuss the engineering/coding level question with me, only feature and user level question needed. You may decide based on best practice and production level experiences."

**Resolution:** All four gray areas are engineering-shape, not feature/user-shape. Bootstrapped CONTEXT.md autonomously with locked engineering decisions (D-152..D-188), citing:
- Phase 2 D-51..D-69 (Backend ABC contract — `JobSpec`/`JobHandle`/`JobState`)
- Phase 4 D-115 (cap-cancel via SIGTERM with 30s grace then SIGKILL)
- Phase 4 D-122 (`register_sigterm_flush()` opt-in not framework-injected)
- Phase 5 D-145 (`JobSpec.metadata` kw-only field)
- CLAUDE.md "Avoid backwards-compatibility hacks" (re: `running/` migration policy)
- Memory `paper_campaign_vs_framework` (re: SLURM directives — `time`/`signal` are framework-mandated; cluster-specific are consumer-supplied)
- Memory `project_automil_is_generic` (re: framework purity in `src/automil/backends/`)
- Production patterns: FSDP/accelerate hybrid Ray init, submitit `DebugExecutor` for in-process testing, `pytest.mark.requires_<backend>` for cluster-gated nightly tests.

## Decisions captured

See `06-CONTEXT.md` § `<decisions>` for the full D-152..D-188 set. Summary:

### SLURM (BCK-05)
- D-152..D-153: module layout + guarded import for missing extras
- D-154: `[slurm] = ["submitit>=1.5.3"]` extras
- D-155..D-160: SLURMBackend implementation — AutoExecutor with framework-mandated `time` + `signal=B:TERM@30`; consumer-supplied cluster directives; SLURM state mapping; `tail -f` log iteration; restart-safe `list_running()`
- D-172: `automil check` enforces TODO-sentinel removal in directives

### Ray (BCK-06)
- D-161: hybrid init (`RAY_ADDRESS` → fallback local)
- D-162..D-167: RayBackend implementation — one actor per submit, `ray.cancel(force=True)`, file-based log tailing, restart-handles-via-resubmit
- D-163: NO multi-fold placement groups (one-actor-per-submit matches Local + SLURM semantics)
- D-178: typed errors (`BackendNotInstalledError`, `RayClusterUnreachableError`)

### `running/` namespace (success criterion #4)
- D-168: breaking change — operators drain via `automil orchestrator stop` before upgrade; daemon refuses to start with flat layout
- D-169: per-backend `running_dir` resolution across `_orchestrator_daemon.py` + `cli/cancel.py` + `cli/reconcile.py` + `cli/cell.py`

### Log unification (success criterion #4)
- D-170: orchestrator drains `backend.log_iter()` into `archive/<id>/run.log` via Phase 0 atomic-write pattern
- D-171: SLURM stdout/stderr archived as symlinks to submitit-logs/ (not copies)

### Test infrastructure (success criterion #3)
- D-174..D-176: parametrised contract test over `[local, mock_slurm, slurm-DebugExecutor, ray-local_mode]`; real-cluster behind `requires_slurm`/`requires_ray` markers; `node_0176`-equivalent acceptance smoke parametrised across CI-runnable backends

### Acceptance gate
- D-179: 11-clause conjunction — contract test on all 4 backends, baseline preserved, BCK-04 lint clean, extras gating intact, `running/` namespaced, log unification verified, framework purity preserved, CHANGELOG breaking entry surfaced.

## Deferred ideas (captured for future phases)

See `06-CONTEXT.md` § `<deferred>`:
- Real SLURM cluster CI runner
- Multi-fold Ray placement groups
- SLURM array jobs
- Cross-backend running-queue rebalancing
- `Backend.healthcheck()` SLURM/Ray probes (Phase 7)
- `automil init --slurm` cluster autodiscovery (Phase 7)
- Ray Tune integration (explicit non-goal)
- Submitit `Checkpointable` framework (framework-doesn't-inject precludes)
- SLURM `--gres=gpu:fraction` (no native SLURM support)
- `backends/kubernetes.py`, `backends/dask.py` (out of scope for v1)

## Claude's discretion items (decided per production patterns, not user request)

- **SLURM directive split** — `time` and `signal=B:TERM@30` are framework-mandated (couple to Phase 4 cap contract); `partition`, `account`, `qos`, `cpus_per_task`, `mem_gb`, `gpus_per_node` are consumer-supplied. Production pattern: framework owns what couples to its contracts; operator owns what's cluster-specific.
- **Ray init = hybrid** (`RAY_ADDRESS`-then-fallback-local) — matches FSDP/accelerate/typical-framework pattern; "just works" on a laptop; honors operator's existing cluster.
- **`running/` migration = breaking** — CLAUDE.md "Avoid backwards-compatibility hacks" + this is a refactor milestone (pre-1.0 semantic-version freedom); document in CHANGELOG with operator recovery steps.
- **Test scope = hybrid** (in-process in CI, real-cluster behind markers nightly) — production pattern; ABC-compliance verified continuously without cluster cost.
- **One-actor-per-submit on Ray** (NOT multi-fold placement groups) — matches Local + SLURM semantics (one experiment process = one node = N-fold-loop INSIDE); placement groups would require Phase 4 cell-level coordination changes.
- **submitit's `Checkpointable` NOT used** — Phase 4 D-122 framework-doesn't-inject precludes; cap mechanism is identical across all backends.
- **Log unification = orchestrator-owned** — backends own log surface only via `log_iter()`; archive/ writes are framework-owned (clean ownership boundary).
