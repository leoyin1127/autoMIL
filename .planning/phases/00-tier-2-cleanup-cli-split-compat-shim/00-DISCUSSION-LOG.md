# Phase 0: Tier 2 cleanup + CLI split + compat shim - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 0 - Tier 2 cleanup + CLI split + compat shim
**Areas discussed:** CLI split shape, Env whitelist policy (CLN-02), compat.py scope (CLN-07), reconcile --recompute-best contract (CLI-07)

---

## CLI split shape

| Option | Description | Selected |
|--------|-------------|----------|
| By audience | agent.py / operator.py / framework.py — read 'who triggers this' to find a command. Submit goes in agent.py and may exceed 300 lines, would extract submit.py. | |
| By lifecycle stage | setup.py / experiment.py / control.py / observability.py — mirrors operator's mental flow setup→run→observe. | |
| Per-command-group, fine | submit.py / init.py / check.py / propose.py / lifecycle.py / orchestrator.py / viz.py / control.py / status.py — verb-not-audience naming. Each file <150 lines. New command → new file. | ✓ |

**User's choice:** Per-command-group, fine.
**Notes:** Verb-not-audience naming. Easiest growth path for Phase 1+ commands. Costs more import boilerplate in `cli/__init__.py` but that's acceptable.

### Follow-up — shared CLI helpers location

| Option | Description | Selected |
|--------|-------------|----------|
| `cli/_helpers.py` | Private module inside cli package. Keeps framework namespace clean. | ✓ |
| `automil/paths.py` | Lift to public path-resolution module. Backends/registry could share. | |

**User's choice:** `cli/_helpers.py`.
**Notes:** Phase 1+ may lift to `automil/paths.py` if backends or registry need git-root lookup. Phase 0 keeps them package-private to minimize blast radius.

---

## Env whitelist policy (CLN-02)

| Option | Description | Selected |
|--------|-------------|----------|
| System minimal + config.yaml env.passthrough | Hardcoded system whitelist + config-driven passthrough list. Anticipates DEC-05 (Phase 8) without locking the field name. (Recommended) | ✓ |
| Drop-in spec.env only | System-minimal + per-spec env. Pushes env knowledge into autobench's submit path. | |
| Allowlist regex in config.yaml | env.allowlist_patterns matched as glob/regex. Higher footgun ratio. | |

**User's choice:** Recommended (option 1), with delegation note.
**Notes:** Leo deferred to recommendation: "actually there are no need to discuss all these 4, you could decide which one is the best for user friendly." Locked option 1. Field name `env.passthrough` chosen distinct from Phase 8's `env.required` (DEC-05). `AUTOBENCH_ROOT` injection at `orchestrator.py:426` deferred to Phase 8 / DEC-01.

---

## compat.py scope (CLN-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Pattern-only stub | Header docstring + one example entry stub. Phase 0 has nothing to alias. (Recommended initially) | |
| Pre-populate Phase 1–3 forecasted aliases (literal) | Live `DeprecationWarning` shims for forecasted paths whose targets don't exist yet. | |
| Skip compat.py | Don't ship in Phase 0. Risk: CLN-07 requires it. | |

**User's choice:** Pre-populate (option 2) — initially.
**Notes:** Claude pushed back on import-time fragility (live shims for non-existent targets either break at import or require try/except + lazy proxies; Phase 2 API redesigns invalidate forecasts). Proposed refined version below.

### Refined compat.py shape

| Option | Description | Selected |
|--------|-------------|----------|
| Refined: active + planned table | Empty Active section + populated `_PLANNED_MIGRATIONS` doc table. Pure documentation, not imported. Each phase promotes entries Planned → Active. | ✓ |
| Literal pre-populated live aliases | Live shims for forecasted paths with try/except + lazy attribute proxies. Higher fragility but strongest commitment. | |

**User's choice:** Refined (option 1).
**Notes:** Phase 0 ships empty Active section. Planned table covers: `automil.orchestrator.ExperimentOrchestrator` → `automil.backends.local.LocalBackend` (Phase 2), `automil.claude_assets.*` → `automil.agent_assets.{_shared,claude}.*` (Phase 3). Phase 1 entry held as `TBD-Phase-1` placeholder until Phase 1's CONTEXT.md locks the registry layout. Each future phase promotes its entry as part of its own implementation.

---

## reconcile --recompute-best contract (CLI-07) — walk semantics

| Option | Description | Selected |
|--------|-------------|----------|
| executed AND keep only | Walks only `type=executed` AND `status=keep` nodes. Discarded nodes excluded. Matches roadmap success-criterion language. (Recommended) | ✓ |
| executed regardless of keep/discard | Walks all executed nodes. Useful as debug tool; risks resurrecting bug-elected nodes. | |
| Cap-aware (executed + partial) | Includes Phase 4 partial nodes. Equivalent to option 1 today. Forward-compatible. | |

**User's choice:** executed AND keep only.
**Notes:** Strict Pareto-respecting walk. Tie-break: lex-min on `node_id`. Audit-trail intent matches the roadmap's "honest non-leaky composite" phrasing.

### Output behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Always-write + print before/after | Default writes after one-line summary. Print IS the audit. (Recommended) | |
| --dry-run flag | Default writes; --dry-run prints diff and exits without writing. Splits surface area. | ✓ |

**User's choice:** --dry-run flag.
**Notes:** Leo overrode the recommendation. Concrete contract: without `--dry-run`, walks → writes `meta.best_node_id` + `meta.best_composite` → prints diff line. With `--dry-run`, prints same line, exits 0, no write.

### Tie-break

| Option | Description | Selected |
|--------|-------------|----------|
| Lex by node_id | Lower node_id wins. Stable across reconciles. (Recommended) | ✓ |
| Earliest by submitted_at | Older submission wins. Equivalent in practice but explicit. | |

**User's choice:** Lex by node_id.
**Notes:** Deterministic, stable, matches existing convention.

---

## Claude's Discretion

- **CLN-03 (`.env` parser):** add `python-dotenv >= 1.0` runtime dep; replace `_load_dotenv` body with `dotenv.dotenv_values()` + `os.environ.setdefault` loop.
- **CLN-04 (PID-file):** JSON `{pid, starttime_ticks, starttime_iso}`; `psutil.Process.create_time()` if `psutil` is already a dep, else `/proc/<pid>/stat` field 22.
- **CLN-05 (`nvidia-smi`):** `shutil.which` at module import; INFO-log resolved path; bare-PATH fallback with WARN; report in `automil check` output.
- **Test posture (D-19):** existing 48 stay green; +6 to +10 new tests for the new behaviours.
- **Commit cadence (D-20):** 8 commits, one per CLN/CLI item, matching `fine` granularity.
- **Internal dataclass / Pydantic / logger / fixture decisions** within each item — Claude picks per simplicity.
- **`psutil` vs `/proc` final choice** — decided at planning time after pyproject.toml inspection.

## Deferred Ideas

- **Phase 1 entry in `_PLANNED_MIGRATIONS`** — placeholder `TBD-Phase-1` until Phase 1 commits the registry layout.
- **`AUTOBENCH_ROOT` removal from `orchestrator.py:426`** — Phase 8 / DEC-01.
- **Composite scoring formula audit** — Phase 8 / DEC-04.
- **Lifting `_find_automil_dir` / `_find_git_root` to `automil/paths.py`** — Phase 1 or Phase 2 if registry/backends need it.
- **CI lint rule blocking `os.kill`/`Popen`/`pid` outside `backends/local.py`** — Phase 2 / BCK-04.
- **`automil check` warning on literal `TODO:` substrings in `config.yaml`** — backlog; revisit with `check` in Phase 1 or Phase 7.
- **O(N²) `recalculate_scores`** — explicitly deferred per PROJECT.md "Out of Scope".
- **Containerized execution (podman/docker)** — explicitly out of v1 scope.
