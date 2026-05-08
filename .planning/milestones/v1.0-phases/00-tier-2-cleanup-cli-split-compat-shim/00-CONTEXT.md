# Phase 0: Tier 2 cleanup + CLI split + compat shim - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the HIGH-severity CONCERNS items remaining after Tier 1 shipped (subprocess env-leak, naive `.env` parser, PID-reuse race, unpinned `nvidia-smi`). Restructure the 725-line monolithic `cli.py` into a `cli/` package so Phase 1+ commands (`apply`, `revert-baseline`, `port-variant`, `promote-variant`, `cancel`, `resubmit`, `nominate`, `cell`, `trajectory`, `refresh-registry`) have a place to land. Add `automil reconcile --recompute-best` to close the T2 backlog from earlier this session. Introduce `compat.py` with an empty Active section + populated Planned-migrations table for Phase 1–3.

**Hard floor:** all 48 existing tests stay green; no behaviour change beyond the cleanup items + restructure + the `--recompute-best` flag. Per-CLN/CLI-item commit cadence (8 commits, matches `fine` granularity). User-facing `automil <subcommand>` invocations are byte-identical before vs after.

</domain>

<decisions>
## Implementation Decisions

### CLI module split (CLN-06)

- **D-01:** `cli.py` becomes a `cli/` package using **per-command-group, fine** organisation. Each command (or tightly-related pair) gets its own file, named by verb not audience. Concrete files:
  - `cli/__init__.py` — defines the `main` Click group, imports each command module, and re-exports `main` so `from automil.cli import main` keeps working.
  - `cli/submit.py` — `submit` (largest single command, ~250 lines today; isolating it keeps every other file <150 lines).
  - `cli/init.py` — `init`.
  - `cli/check.py` — `check`.
  - `cli/propose.py` — `propose`, `rank` (paired by lifecycle).
  - `cli/lifecycle.py` — placeholder for Phase 1 additions (`apply`, `revert-baseline`, `port-variant`, `promote-variant`, `refresh-registry`); Phase 0 ships an empty stub with a header docstring so Phase 1 has somewhere to land without touching `cli/__init__.py` structurally.
  - `cli/orchestrator.py` — `orchestrator` subgroup (`start`, `stop`, `status`).
  - `cli/viz.py` — `viz` subgroup (`start`, `stop`, `status`).
  - `cli/control.py` — `start-loop`, `stop-loop`, `cancel` (Phase 2), `resubmit` (Phase 2). Phase 0 only ships `start-loop` + `stop-loop`; the file gets cancel/resubmit in Phase 2.
  - `cli/status.py` — `status`.
  - `cli/reconcile.py` — `reconcile` (incl. the new `--recompute-best` flag).
- **D-02:** Shared CLI helpers (`_find_automil_dir`, `_find_git_root`, `_matches_scope`) live in `cli/_helpers.py` (private to the package). Phase 1+ may lift `_find_automil_dir` / `_find_git_root` to `automil/paths.py` if the registry or backends modules need git-root lookup; for Phase 0 they stay package-private to keep blast radius small.
- **D-03:** No file exceeds 300 lines. The split is verified by a CI/lint check (or by `wc -l` in the phase verification step).

### Subprocess environment whitelist (CLN-02)

- **D-04:** Replace `env = {**os.environ, ...}` at `orchestrator.py:419-431` with a **system-minimal hardcoded whitelist + config-driven `env.passthrough` list**.
  - **Hardcoded system whitelist:** `PATH`, `HOME`, `USER`, `SHELL`, `LANG`, `LC_*` (glob), `TZ`, `TMPDIR`, `LD_LIBRARY_PATH`, `CUDA_*` (glob), `NVIDIA_*` (glob), `AUTOMIL_*` (glob), `PYTHONPATH`. The `*` glob form means the whitelist is matched as a prefix-glob, not a regex.
  - **Orchestrator-injected (unchanged):** `CUDA_VISIBLE_DEVICES`, `AUTOMIL_GPU`, `AUTOMIL_DESC`, `AUTOMIL_NODE_ID`, `AUTOMIL_RESULTS_DIR`.
  - **Config-driven passthrough:** new `automil/config.yaml` field `env.passthrough: [VAR_NAME, ...]` (list of literal var names; no globs at the config layer to keep the surface tight). Each listed var, if present in the orchestrator's `os.environ`, is added to the subprocess env. Missing keys are logged at WARN at orchestrator startup, not at submit time, and never block scheduling.
  - **Per-spec env (`spec.env`):** still flows through unchanged (used by `apply_overlay`-style call sites). `spec.env` overrides match-anything from passthrough (last-write-wins).
- **D-05:** **Phase 8 deferral noted explicitly:** `AUTOBENCH_ROOT` is currently injected by `orchestrator.py:426`. Phase 0 keeps that line as-is (no new autobench refs in `src/automil/`); Phase 8 / DEC-01 owns its removal. Phase 0 does NOT add the `env.passthrough` mechanism for `AUTOBENCH_*` — autobench's own config will list them under `env.passthrough` once Phase 0 ships.
- **D-06:** Anti-pattern guard: the field name `env.passthrough` is intentionally chosen to be **distinct** from Phase 8's `env.required` (DEC-05). `env.passthrough` = "let these vars through if present, otherwise warn"; `env.required` = "fail fast at startup if missing" (Phase 8 semantic). The two coexist; Phase 0 ships only `env.passthrough`.

### `compat.py` shape (CLN-07)

- **D-07:** `src/automil/compat.py` ships in Phase 0 with **two sections**:
  1. **Active aliases** — Phase 0 ships this section EMPTY. Live re-export shims that emit `DeprecationWarning` at import time. Phase 0 has zero relocations because `cli/__init__.py` re-exports `main` (the only externally-imported name from the old `cli.py`).
  2. **`_PLANNED_MIGRATIONS` doc table** — populated. Pure documentation; not imported. A dict keyed by old-path with `{ new_path, owning_phase, rationale }` values. Forecasted entries:
     - `automil.orchestrator.ExperimentOrchestrator` → `automil.backends.local.LocalBackend` (Phase 2; BCK-02 ABC re-export)
     - `automil.claude_assets` → `automil.agent_assets._shared` + `automil.agent_assets.claude` (Phase 3; MRT-01 reorg)
     - Add Phase 1 entries when Phase 1's CONTEXT.md commits a final registry layout (placeholder TBD entry).
- **D-08:** Each future phase **promotes** its planned entry from `_PLANNED_MIGRATIONS` to Active by adding the live re-export shim with `DeprecationWarning` and removing the entry from the dict. The promotion is the `compat.py` change in that phase's plan.
- **D-09:** Header docstring in `compat.py` documents the two-section pattern, the promotion rule, and the deprecation-message format (`"<old_path> moved to <new_path> in Phase <N>; old import retained for backwards-compat. Update by <date>."`).

### `automil reconcile --recompute-best` (CLI-07)

- **D-10:** **Walk semantics:** strict — only nodes where `type == "executed"` AND `status == "keep"`. Discarded/crashed/cancelled/budget-killed nodes are excluded (matches roadmap success-criterion language "walking only executed/keep nodes" and the audit-trail intent).
- **D-11:** **Composite formula:** uses the existing `composite` field on each node as already populated by `train.py` → `result.json` → orchestrator pipeline. Phase 0 does NOT redefine the formula — that's Phase 8 / DEC-04. The "honest non-leaky" qualifier means Phase 0's flag walks current data; if the data is honest, the result is honest.
- **D-12:** **Tie-break:** lexicographic min on `node_id` (e.g., `node_0048` beats `node_0125` at equal composite). Stable across reconciles, deterministic given the same inputs.
- **D-13:** **Output behavior:** `--dry-run` flag.
  - Without `--dry-run`: walks, writes `meta.best_node_id` and `meta.best_composite` to `graph.json` via `ExperimentGraph.save()` (atomic), prints one-line summary `best_node_id: <old> (composite <old_c:.6f>) → <new> (composite <new_c:.6f>)` if changed, else `best_node_id unchanged: <id> (composite <c:.6f>)`. Exits 0 in both cases.
  - With `--dry-run`: prints the same summary line, exits 0, does NOT write `graph.json`.
- **D-14:** **Existing `automil reconcile` (no flag) behaviour unchanged.** Only orchestrator-state sync (queue / running / completed / archive). `--recompute-best` is opt-in.
- **D-15:** **No telemetry** logged on the recompute itself (no audit trail beyond stdout). Operator runs the command interactively; the print line IS the audit. Future `compat.py`-style migration table can live in `_PLANNED_MIGRATIONS` if we ever want this to be auditable.

### Mechanical CLN items (Claude's Discretion)

- **D-16: CLN-03 (`.env` parser):** add `python-dotenv >= 1.0` as a runtime dep in `pyproject.toml`; replace `_load_dotenv` body in `orchestrator.py:222-249` with `dotenv.dotenv_values(env_file)` + `os.environ.setdefault(k, v)` loop. Tests cover quoted values, `export` prefix, comments after `=`.
- **D-17: CLN-04 (PID-file process start-time):** `orchestrator.py` writes the PID file as JSON `{"pid": <int>, "starttime_ticks": <int>, "starttime_iso": "..."}`. Use `psutil.Process(pid).create_time()` if `psutil` is already a dep; otherwise read `/proc/<pid>/stat` field 22 directly. Stale-detection compares both `pid` and `starttime_ticks` before signalling. Linux-only is acceptable (per Constraints in PROJECT.md).
- **D-18: CLN-05 (`nvidia-smi` path-pin):** `query_gpus()` uses `shutil.which("nvidia-smi")` once at module import; logs the resolved path at INFO; falls back to bare `"nvidia-smi"` invocation with WARN if `which` returns None. The detected/used path is reported in `automil check` output ("nvidia-smi: `/usr/bin/nvidia-smi`" or "nvidia-smi: bare PATH lookup (path detection failed)").
- **D-19: Test posture:** existing 48 tests stay green. Net-new tests added for: `--recompute-best` (walk semantics + tie-break + dry-run); env whitelist (system vars pass, secrets don't, passthrough list works); dotenv corner cases (quoted, `export`, comments after `=`); PID start-time stale-detection. Estimate +6 to +10 tests.
- **D-20: Commit cadence:** one commit per CLN/CLI item (target: 8 commits — CLN-02, CLN-03, CLN-04, CLN-05, CLN-06, CLN-07, CLI-07, plus optional `tests:` consolidation). Matches `fine` granularity in `.planning/config.json`. Each commit's tests must pass before moving on.

### Claude's Discretion

- Internal dataclass / typing choices for the env whitelist (e.g., `EnvWhitelist` Pydantic model vs plain function — Claude picks based on simplicity).
- Logger names within new modules (one logger per module, named after `__name__` per Python convention).
- Specific test fixture refactor needed to support env-whitelist tests (likely a `monkeypatch.setenv` pattern; Claude picks).
- Exact `psutil` vs `/proc` choice for PID start-time (decided at planning time after checking current pyproject deps).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Authoritative scope

- `.planning/ROADMAP.md` §"Phase 0" — phase goal, success criteria, anti-acceptance notes.
- `.planning/REQUIREMENTS.md` §"Cleanup (CLN)" + §"CLI" CLI-07 — CLN-01..CLN-07 and CLI-07 with normative wording for each requirement.
- `.planning/PROJECT.md` §"Key Decisions" — "autoMIL is generic; autobench is one consumer", "Tier 1 mechanical fixes before structural refactor".

### Codebase map (for "where")

- `.planning/codebase/CONCERNS.md` — full HIGH/MED/LOW severity catalog with file:line refs (the source for D-04, D-16, D-17, D-18 fixes).
- `.planning/codebase/ARCHITECTURE.md` — module layout (informs D-01 split shape).
- `.planning/codebase/STACK.md` — runtime dependencies (informs D-16 dotenv add, D-17 psutil-or-/proc choice).
- `.planning/codebase/CONVENTIONS.md` — commit message style, test naming, logging patterns.

### Standing memory & feedback (Leo)

- `~/.claude/projects/-home-jma-Documents-yinshuol-autoMIL/memory/MEMORY.md` — pointers to:
  - `feedback_skills_vs_cli.md` — CLI for runtime triggers (informs D-01 verb-not-audience naming).
  - `project_automil_is_generic.md` — no autobench paths in `src/automil/` (drives D-04, D-05, D-06).
  - `project_multi_runtime_agents.md` — multi-runtime support is in v1 (informs Phase 3 entry in `_PLANNED_MIGRATIONS`).
- `CLAUDE.md` §"Workflow Orchestration" — plan-first, verification-before-done, address-as-Leo.

### Source files touched in Phase 0

- `src/automil/cli.py` (725 lines) — split target.
- `src/automil/orchestrator.py:101-111` (nvidia-smi), `:222-249` (dotenv), `:419-431` (env build), `:721-781` (PID file).
- `src/automil/graph.py` — `meta.best_node_id` write site for `--recompute-best`.
- `src/automil/__init__.py` — confirm export surface unchanged.
- `pyproject.toml` — add `python-dotenv >= 1.0` dep; possibly `psutil` if not already present.
- `tests/test_cli.py`, `tests/test_orchestrator.py` (new file likely), `tests/test_graph.py` — test additions per D-19.

### Phase 1 / 2 / 3 forecast (for `compat.py` `_PLANNED_MIGRATIONS`)

- `.planning/ROADMAP.md` Phase 1 §"Variant registry" — not yet detailed enough to lock a `compat.py` entry; placeholder `TBD-Phase-1` accepted.
- `.planning/ROADMAP.md` Phase 2 §"Backend ABC" — `orchestrator.ExperimentOrchestrator` → `backends.local.LocalBackend` is the documented direction.
- `.planning/ROADMAP.md` Phase 3 §"Multi-runtime asset reorg" — `claude_assets/` → `agent_assets/_shared/` + `agent_assets/claude/`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `_find_automil_dir`, `_find_git_root`, `_matches_scope` (`cli.py:18-65`) — moved verbatim to `cli/_helpers.py`. No semantic change.
- `ExperimentGraph` (`graph.py`) — already has the `composite` field on each node and atomic `save()`. `--recompute-best` adds one method (`recompute_best`) on this class, not a parallel walker.
- `_load_dotenv` call sites (`orchestrator.py:222`) — replaced wholesale; no callers outside the orchestrator.
- `query_gpus()` (`orchestrator.py:98-111`) — pinning is local to the `subprocess.run` call.

### Established Patterns

- **Click subgroups via `@main.group()` + `@<group>.command()`** (`cli.py:656-720`) — orchestrator + viz already follow this; new `cli/orchestrator.py` and `cli/viz.py` keep the same registration pattern, just imported from sibling modules into `cli/__init__.py`.
- **Atomic `graph.json` save** (`graph.py:740-754`) — `--recompute-best`'s write must call `ExperimentGraph.save()`, not bypass it.
- **`ExperimentOrchestrator.__init__(recover=False)`** (`orchestrator.py:196-198`) — Phase 0 must not introduce any new code path that triggers `_recover_orphans` outside the daemon's `run()`. The CLI's `--recompute-best` reads `graph.json` directly via `ExperimentGraph`, never instantiating the orchestrator.
- **Tier 1 patterns already present:**
  - `.gitignore` already covers `.automil_worktrees/` and `.automil_active` (lines 20-21).
  - `_reload_orchestrator_config` already logs WARN on YAML parse failure (`orchestrator.py:669`).
  - `mark_running` is now a logged guard, not an assert.
  - `Popen(..., start_new_session=True)` + `os.killpg` on timeout is in place.
  - `meta.best_node_id` is corrected to `node_0176` (composite 0.8074).

### Integration Points

- `cli/__init__.py` is the **sole** import surface preserved for `from automil.cli import main`. Tests at `tests/test_cli.py:11`, `tests/test_integration.py:11` import that name.
- `pyproject.toml` `[project.scripts]` entry `automil = "automil.cli:main"` resolves through the new package's `__init__.py` re-export — no `pyproject.toml` change needed for the split itself (only for the new `python-dotenv` dep).
- Orchestrator's `_load_dotenv` runs at construction time; replacement must preserve the "don't override existing env vars" semantic (`os.environ.setdefault`, not `os.environ.__setitem__`).
- `automil check` output adds two lines: detected `nvidia-smi` path (D-18) and a per-key "passthrough OK / passthrough MISSING" report for `env.passthrough` entries (D-04).

</code_context>

<specifics>
## Specific Ideas

- **Reconcile output format** (Leo's verbatim concern): operator must be able to predict the output before running. The print line `best_node_id: node_0125 (composite 0.821000) → node_0176 (composite 0.807400)` is the audit, both for `--dry-run` and the writing path.
- **`compat.py` two-section pattern** (Leo's call after pushback): empty Active + populated Planned-migrations table is the literal shape. Future phases promote entries; the file is not a dumping ground for "things that might move".
- **Verb-not-audience CLI file naming** (Leo's call on D-01): `submit.py` not `agent.py`. New contributors find commands by verb, not by who triggers them.
- **No new architecture** in Phase 0. Every change is replacement-in-place or an added flag. The split is restructuring, not redesign.

</specifics>

<deferred>
## Deferred Ideas

- **Phase 1 `compat.py` Planned entry** for the registry layer — not finalisable until Phase 1's CONTEXT.md commits the registry module layout. Phase 0 ships a placeholder `TBD-Phase-1` entry in `_PLANNED_MIGRATIONS`; Phase 1's first commit replaces it with concrete paths.
- **`AUTOBENCH_ROOT` injection at `orchestrator.py:426`** — explicitly held back to Phase 8 / DEC-01. Phase 0 keeps the line; Phase 8 owns the removal.
- **Composite scoring formula audit** — Phase 8 / DEC-04. Phase 0 trusts the existing per-node `composite` value populated by `train.py`.
- **Lifting `_find_automil_dir` / `_find_git_root` to `automil/paths.py`** — deferred to Phase 1 or Phase 2 if the registry/backends layer needs git-root lookup. Phase 0 keeps them in `cli/_helpers.py`.
- **CI lint rule blocking `os.kill`/`Popen`/`pid` outside `backends/local.py`** — that's BCK-04 (Phase 2). Phase 0 doesn't introduce the rule because `backends/` doesn't exist yet.
- **`automil check` warning on literal `TODO:` substrings in `config.yaml`** — CONCERNS catalog item but not in Phase 0's REQ-IDs. Capture for backlog; pick up when revisiting `check` in Phase 1 or Phase 7.
- **O(N²) `recalculate_scores`** — explicitly deferred per PROJECT.md "Out of Scope".
- **Containerized execution / podman / docker** — explicitly out of v1 scope.

</deferred>

---

*Phase: 0 - Tier 2 cleanup + CLI split + compat shim*
*Context gathered: 2026-05-01*
