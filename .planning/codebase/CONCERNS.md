# Codebase Concerns

**Analysis Date:** 2026-04-30

This document catalogs technical debt, fragile invariants, security-relevant
boundaries, performance concerns, and historically buggy areas in the autoMIL
framework. Items are scoped to the framework itself (`src/automil/`) and the
autobench harness it drives (`benchmarks/src/autobench/`, `benchmarks/scripts/`).

---

## Tech Debt

### Hot-reload of orchestrator config silently swallows malformed YAML

- Issue: `_reload_orchestrator_config()` wraps `yaml.safe_load` in
  `try/except Exception: return`. A bad edit to `automil/config.yaml` (broken
  indentation, accidental tab) causes the daemon to keep its old values forever
  with no log line and no operator-visible signal — and the next legitimate
  edit looks like it had no effect.
- Files: `src/automil/orchestrator.py:640-674`
- Impact: GPU-saturation tuning is invisible-fail. Operator bumps
  `max_concurrent_per_gpu` from 4 → 8, sees throughput unchanged, blames the
  scheduler instead of the config file.
- Fix approach: log a `WARNING` on YAML parse failure and emit
  `Config reload skipped: <error>` so the failure is visible in
  `orchestrator.log`.

### Naive `.env` parser in orchestrator

- Issue: `_load_dotenv()` does a manual `line.partition("=")` with
  `value.strip()`. It does not handle:
  - Surrounding single/double quotes (`KEY="value with spaces"` keeps the quotes)
  - `export KEY=value` prefixes (key becomes `export KEY`, never matches)
  - Backslash escapes
  - Multi-line values
- Files: `src/automil/orchestrator.py:222-250`
- Impact: A `benchmarks/.env` written by anyone used to dotenv conventions
  silently leaks the wrong value into worktree subprocesses. Failure mode is
  the path-not-found error documented in CLAUDE.md, but the root cause looks
  like a missing variable instead of a parser issue.
- Fix approach: depend on `python-dotenv` (already common in scientific Python)
  or strip matched leading/trailing quotes and recognize the `export ` prefix.

### Hardcoded technique map drifts from research vocabulary

- Issue: `ExperimentGraph.DEFAULT_TECHNIQUE_MAP` hard-codes ~30 substring →
  tag mappings (`"focal" → "focal_g1"`, `"trans_mil" → "trans_mil"`, etc.).
  Every new technique introduced by an experiment proposal needs an entry
  here, otherwise the technique-novelty score in `recalculate_scores()` is
  zero for it (the proposal looks "novel forever" or "stale forever",
  depending on which side of the bug you fall on).
- Files: `src/automil/graph.py:19-30`, `src/automil/graph.py:395-402`
- Impact: Scoring drift. The standing user expectation is that every batch
  includes a literature-driven idea (`feedback_research_before_submit.md`),
  so the tag set churns rapidly and this map becomes stale within days.
- Fix approach: derive technique tags from `--techniques` flags supplied on
  `automil propose`/`submit` instead of from substring scraping of free-text
  descriptions. The substring scraper should be a fallback at most.

### `mark_running` is a hard assertion, not a guard

- Issue: `ExperimentGraph.mark_running()` uses
  `assert node["type"] == "proposed" and node["status"] == "pending"`. If the
  orchestrator (or any caller) ever invokes it on an already-running or
  already-executed node, the entire daemon crashes.
- Files: `src/automil/graph.py:184-188`
- Impact: One bad reconcile can kill the daemon and orphan every running
  experiment.
- Fix approach: replace the assert with a logged early-return; the orchestrator
  is the wrong place for `assert`-style preconditions.

### `prune_stale_worktrees` swallows all errors

- Issue: `Runner.prune_stale_worktrees()` runs `git worktree prune` with
  `capture_output=True` but never inspects `returncode` or `stderr`. Same for
  `cleanup_worktree`'s fallback path.
- Files: `src/automil/runner.py:74-94`
- Impact: If git is misconfigured (corrupt `.git/worktrees/` index, permissions
  problem, etc.) we silently keep stale references that later cause
  `git worktree add` to fail with `already exists` for a recycled node id.
- Fix approach: log non-zero returncodes; keep the function non-fatal but
  visible.

### Viz frontend is a 670-line single-file vendored bundle

- Issue: `src/automil/viz/static/app.js` is 670 lines of hand-rolled
  Three.js + 3d-force-graph code with vendored d3/three/three-spritetext at
  fixed versions (recent commit `137aa70`).
- Files: `src/automil/viz/static/app.js`,
  `src/automil/viz/static/vendor/`
- Impact: No build pipeline, no dependency manager, no version pinning beyond
  whatever was last copy-pasted. Security/stability of vendored JS is opaque.
- Fix approach: long-term, move to a small build step (e.g. esbuild) so that
  upgrades are tracked in a manifest. Acceptable to defer while the surface
  is small.

### TODO markers in init templates

- Issue: Four `TODO:` markers ship in the rendered `automil/config.yaml` for
  new projects (description, encoder dim, editable list, readonly list).
- Files: `src/automil/templates/config.yaml.j2:7,26,53,54`
- Impact: Low — the templates exist *to* prompt the operator. But the
  `automil check` command does not assert that the TODOs have been replaced,
  so an experiment can run against an empty `files.editable` list and
  silently capture "ALL changed files" via fallback (which then includes
  benchmarks lib edits that may not be intended for this experiment).
- Fix approach: have `automil check` flag any literal `TODO:` substrings in
  `config.yaml` as warnings.

---

## Known Fragile Invariants

### `_recover_orphans()` MUST NOT run during construction

- The invariant is documented in CLAUDE.md and enforced by
  `_load_state(recover=False)` in the constructor and a separate
  `self._recover_orphans()` call in `run()` (line 704).
- Files: `src/automil/orchestrator.py:196-198`,
  `src/automil/orchestrator.py:701-704`
- Why fragile: A future contributor adding a new CLI command (e.g.
  `cmd_inspect`) that constructs `ExperimentOrchestrator()` would not be
  warned away from the recovery path. The only protection is
  `_load_state`'s default-`True` recover parameter, which the constructor
  overrides — easy to miss.
- Why this matters: `cmd_status` and `cmd_stop` are called concurrently with
  a live daemon. If they trigger `_recover_orphans()`, every running spec
  in `running/` gets archived as a "crash", its worktree removed out from
  under the live process, and `results.tsv` poisoned with fake crash rows.
  This has happened before — see "Areas Where Mistakes Have Happened" below.
- Fix approach: rename `_recover_orphans` to `_recover_orphans_for_daemon`
  and add a precondition assertion that the PID file points at the current
  process. Make the dangerous helper hard to call from CLI commands.

### `results.tsv` is written ONLY by the orchestrator

- The invariant is documented in CLAUDE.md and pyproject docs.
- Files: `src/automil/orchestrator.py:611-636` (sole writer);
  `benchmarks/scripts/run_experiment.py:218-227` (writes `result.json` only,
  never `results.tsv`)
- Why fragile: There is no enforcement. A well-meaning training script could
  start appending to `results.tsv` and the orchestrator would never notice;
  rows would interleave under concurrent writes. The orchestrator's
  truncation logic at line 620 (`if not exists or stat().st_size == 0`)
  treats a single-byte file as fresh and re-writes the header — clobbering
  any rows another writer added.
- Fix approach: chmod `results.tsv` to read-only for non-orchestrator
  processes, or move it to `automil/orchestrator/results.tsv` so the path
  is obviously orchestrator-owned.

### Path validation in `automil submit`

- Files: `src/automil/cli.py:347-361`
- Current guards:
  - `os.path.isabs(f)` rejects absolute paths
  - `".." in Path(f).parts` rejects parent traversal
  - `src.resolve().relative_to(git_root.resolve())` rejects symlink escape
- Auto-detect excludes `automil/` and `.claude/`
  (`src/automil/cli.py:316-319`).
- Why fragile: This is the only barrier between an experiment overlay and
  arbitrary file-system writes inside the worktree. The check is correct on
  POSIX but:
  - Symlink resolution depends on the target existing at submit time;
    a symlink created later under a captured path could escape on
    `apply_overlay`.
  - The check runs only on `--files` and on auto-detect output, not on
    `deletions` (paths whose source no longer exists). A `deletions` entry
    `../something.py` is rejected by the same `Path(f).parts` rule, but
    a symlink target inside `git_root` is not re-validated when it is
    eventually `unlink()`-ed inside the worktree.
- Fix approach: re-validate `wt_path / rel` resolves under `wt_path` at the
  point of `unlink()` in `Runner.apply_overlay`, not just at submit time.

### Submit refuses to overwrite executed nodes

- Files: `src/automil/cli.py:208-239`
- Refuses if the target id is already
  `executed`/`keep`/`discard`/`crash`/`completed`/`running`, or if a spec
  for the id already sits in `queue/` or `running/`.
- Why fragile: Relies on `graph.json` being authoritative. If the agent
  hand-edits `graph.json` (or a partial save crashed mid-write), the guard
  can be bypassed. The atomic save in `ExperimentGraph.save()`
  (`src/automil/graph.py:740-754`) is robust but the *read* on line 215 is
  best-effort.
- Fix approach: also enforce on the orchestrator side at `_launch` — refuse
  to launch if `archive/<node_id>/result.json` already exists.

### Submit refuses to launch a child before its parent has executed

- Files: `src/automil/cli.py:241-276`
- Why fragile: Without this guard, the Pareto-dominance keep/discard would
  be computed against `parent.composite = 0`, spuriously labelling almost
  every run as "keep". Documented in the code as the root cause of the
  "0051-0055 → 0048" orphan-subtree incident.
- The guard does NOT cover the case where the parent is still in the queue
  but the agent submits siblings concurrently — the `graph.json` snapshot
  read on line 215 is a single point-in-time view.

### `_reevaluate_descendants` recurses but doesn't dedupe via composite

- Files: `src/automil/graph.py:233-262`
- Why fragile: Children can be promoted before their parent. After parent
  promotion, the framework rewalks descendants and recomputes keep/discard.
  But the comparison only uses `(test_auc, test_bacc, composite)` — if a
  child crashed and was later resurrected with bogus `0.0` metrics, it will
  keep flipping between keep and discard as ancestors change.

### Apply-overlay metadata-file blacklist is name-only, not depth-aware

- Files: `src/automil/runner.py:44-53`
- `metadata_files = {Path("spec.json"), Path("run.log"), Path("result.json")}`
- Comparison uses `if rel in metadata_files`, where `rel` is
  `Path.relative_to(overlay_dir)`. This correctly skips top-level metadata
  but does NOT skip a user file at e.g. `models/result.json` (which is fine).
  However, the filter is positional rather than semantic — if the overlay
  dir layout changes (e.g. metadata moves into a subdir), the filter
  silently stops working.

---

## Security Considerations

### Worktree isolation depends on git correctness, not OS sandboxing

- Files: `src/automil/runner.py:23-35`
- The "isolation" is a `git worktree add --detach` sharing the same
  `.git/` index. A malicious or buggy training script with write access to
  `..` of the worktree can scribble all over the user's main checkout.
  CUDA/PyTorch processes already have the user's full filesystem permissions.
- Mitigation in code: `apply_overlay` rejects paths outside the worktree at
  submit time. After launch the subprocess is unrestricted.
- Recommendation: document this clearly in the framework README. Containerized
  execution (podman/docker) is the proper fix but a major lift.

### Subprocess `env` inherits the full operator environment

- Files: `src/automil/orchestrator.py:419-431`
- `env = {**os.environ, ...}`. Any secret in the operator's shell env
  (e.g. `OPENAI_API_KEY`, `WANDB_API_KEY`) is inherited by every experiment
  subprocess. A buggy or untrusted training script can exfiltrate.
- Recommendation: whitelist required env vars instead of passing the full
  parent env, especially for `AUTOBENCH_*` paths.

### PID-file stale-detection uses `os.kill(pid, 0)`

- Files: `src/automil/orchestrator.py:749-756`,
  `src/automil/orchestrator.py:770-781`,
  `src/automil/viz/server.py:296-306`
- PID reuse on Linux: a long-running session that started a daemon, killed
  it, and waited for PID rollover could see a *different* process at the
  recorded PID. `os.kill(pid, 0)` returns success and `cmd_stop` then
  sends SIGTERM to that unrelated process.
- Mitigation: write the start time of the daemon into the PID file and
  cross-check against `/proc/<pid>/stat` start time before signalling.

### `nvidia-smi` invocation has no path pinning

- Files: `src/automil/orchestrator.py:101-111`
- `subprocess.run(["nvidia-smi", ...])` resolves via `$PATH`. On a
  shared/multi-user host, a `nvidia-smi` shim earlier on PATH can return
  arbitrary VRAM numbers, tricking the bin-packer.
- Severity: low (it is the operator's own machine), but worth noting.

---

## Performance Concerns

### GPU saturation is the codified user expectation, not a hypothesis

- Standing user feedback (`feedback_saturate_gpus.md`) requires 6–10 CLAM
  runs per GPU at 0.4 GB each on 48 GB cards. The framework default is
  `MAX_CONCURRENT_PER_GPU = 8` and the ccrcc config sets it to 4 (recent
  commit `2960692`).
- Files: `src/automil/orchestrator.py:39`,
  `src/automil/orchestrator.py:339-362`,
  `benchmarks/experiments/ccrcc/automil/config.yaml:80-89`
- Concern: any change that quietly downgrades concurrency is a regression,
  not a "safety improvement". Specifically:
  - `_find_best_gpu` returns `None` if `len(running_on) >= self.max_per_gpu`
    OR `schedulable < needed_gb`. Both conditions must be tracked.
    `safety_margin_gb = 2.0 GB` deducted on every check is a flat tax —
    doubling concurrency from 4 → 8 doesn't double the safety margin, but
    on small GPUs the margin can dominate.
  - `default_vram_estimate_gb = 1.0` is a *per-experiment* estimate. If an
    experiment doesn't override it, eight CLAM runs on one GPU each
    estimated at 1 GB sums to 8 GB allocated, triggering early refusal even
    though true peak is ~3.2 GB. The agent must remember to pass
    `--vram 0.5` (or lower) on every submit.
- Fix approach: track empirical peak VRAM in `results.tsv` (already there)
  and feed back into `default_vram_estimate_gb` automatically. Today the
  feedback loop is manual.

### Best-fit bin packing is per-tick, not per-arrival

- Files: `src/automil/orchestrator.py:339-362`,
  `src/automil/orchestrator.py:686-696`
- `tick()` reads the entire pending queue and tries to schedule each spec
  in priority order. With many small jobs and one large pending job, the
  large one can starve: smaller jobs at the same priority sort by
  `submitted_at` and fill the GPU first. There is no anti-starvation aging.
- Impact: Architectural innovations that need more VRAM than a hyperparam
  sweep can wait indefinitely behind a cheap sweep. Aligns directly with
  the standing feedback that hyperparam sweeps must not crowd out
  architectural work (`feedback_architectural_not_hyperparam.md`).
- Fix approach: bump priority on age (e.g. once a spec has been waiting
  >20 min, decrement its priority value).

### `_handle_timeout` blocks the main loop with `time.sleep(5)`

- Files: `src/automil/orchestrator.py:578-587`
- After SIGTERM, the orchestrator sleeps 5 s before SIGKILL. During that
  5 s, the main `tick()` does not run — pending experiments are not
  scheduled, completion checks are skipped, GPU state is not refreshed.
- Impact: At default `poll_interval_sec=5`, a single timeout doubles the
  effective tick interval. Multiple concurrent timeouts add linearly.
- Fix approach: track the SIGTERM time and re-check on the next tick;
  don't block.

### Process-group not used: orphaned children survive timeout kill

- Files: `src/automil/orchestrator.py:440-446`,
  `src/automil/orchestrator.py:578-587`
- `subprocess.Popen` is invoked without `start_new_session=True` /
  `preexec_fn=os.setsid`. `process.terminate()` and `process.kill()` only
  signal the immediate child. PyTorch DataLoader workers, CUDA contexts
  spawned through `multiprocessing`, and the spawn-method shims all become
  orphans of PID 1 and continue holding GPU memory after the timeout
  "cleanup".
- Impact: VRAM leak. Repeated timeouts visibly reduce schedulable VRAM
  until the operator manually `nvidia-smi --gpu-reset` or kills strays.
- Fix approach: `Popen(..., start_new_session=True)` and
  `os.killpg(os.getpgid(exp.process.pid), signal.SIGTERM)` in
  `_handle_timeout`.

### `recalculate_scores` is O(N²) per call

- Files: `src/automil/graph.py:303-340`
- For every node it walks `self.nodes.values()` to count children
  (`siblings_tried`, `child_count`). At ~100 nodes this is fine; at ~10k
  it is noticeable. Called from every `reconcile()`.
- Fix approach: build a parent → children index once, reuse.

### `_recover_orphans` is best-effort and may fail mid-loop

- Files: `src/automil/orchestrator.py:295-321`
- The outer `try/except Exception: continue` swallows EVERY error per file.
  An I/O error on the first file is logged-and-skipped, but a permissions
  error on the worktree directory means the worktree never gets cleaned up
  and the next `git worktree add` for that node id fails.
- Fix approach: log the exception (not just `continue`).

---

## Areas Where Mistakes Have Happened

### Orphan-recovery race during `cmd_status` / `cmd_stop`

- Past mistake: `_recover_orphans` was called from `_load_state(recover=True)`
  in the constructor. Running `automil orchestrator status` while the daemon
  was alive would:
  1. Spawn a new `ExperimentOrchestrator` instance
  2. Trigger `_recover_orphans`
  3. Mark every spec in `running/` as "crash"
  4. Remove the live worktrees
  5. Poison `results.tsv` with fake crash rows
- Current state: constructor passes `recover=False`; recovery only happens
  in the daemon's `run()` after pruning stale worktrees and writing the PID
  file (`src/automil/orchestrator.py:701-705`). The invariant is
  documented in CLAUDE.md.
- Files: `src/automil/orchestrator.py:196-198`,
  `src/automil/orchestrator.py:701-704`
- Reminder: any new CLI command that instantiates `ExperimentOrchestrator`
  MUST verify it does not trigger recovery.

### `results.tsv` ownership confusion

- Past mistake: training scripts used to write their own rows; double-rows,
  interleaved bytes, header repetition.
- Current state: orchestrator is the sole writer
  (`src/automil/orchestrator.py:556-557, 611-636`); training scripts write
  only `result.json` (`benchmarks/scripts/run_experiment.py:218-227`).
- Reminder: do NOT add `results.tsv` writes from any other module. The
  orchestrator's `_append_results_tsv` does not lock — concurrent writers
  will corrupt rows.

### Env-var propagation into worktrees

- Past mistake: `.env` is gitignored, so `git worktree add --detach` produces
  a worktree without `.env`. Training scripts `os.getenv` returned None,
  config resolution raised `ValueError: Environment variable
  ${AUTOBENCH_...} is not set`, every experiment crashed.
- Current state: orchestrator pre-loads `.env` from `<repo>/.env` and
  `<repo>/benchmarks/.env` into its own `os.environ` at startup
  (`src/automil/orchestrator.py:222-250`); subprocess env is built from
  `{**os.environ, ...}` so children inherit
  (`src/automil/orchestrator.py:419-431`).
- Reminder: any new env-var consumer (e.g. a new dataset YAML referencing
  `${MY_NEW_DATA_ROOT}`) must be added to `benchmarks/.env.example` AND
  the operator's `benchmarks/.env`. The orchestrator does not error on
  missing values at startup — it only errors deep inside `autobench.config`
  when the YAML is resolved.

### `PYTHONPATH` and `AUTOBENCH_ROOT` overlay defeat

- Past mistake: Editable install (`pip install -e .`) of `autobench` in the
  parent venv pointed at `<repo>/benchmarks/src/autobench/`. Worktree
  overlays under `benchmarks/src/autobench/` were silently ignored —
  experiments ran the unmodified parent-checkout code while pretending to
  test the overlay.
- Current state: orchestrator forces PYTHONPATH to point at the worktree's
  `benchmarks/src` first, and sets `AUTOBENCH_ROOT` to the worktree's
  `benchmarks/`
  (`src/automil/orchestrator.py:413-428`).
- Files: `src/automil/orchestrator.py:404-428`
- Reminder: the comment block at line 404-412 is critical context. Do not
  remove these env vars when refactoring.

### Submit auto-detect captured `automil/` and `.claude/`

- Past mistake: auto-detect ran `git diff --name-only` and shipped every
  changed file into the overlay, including `automil/graph.json` and
  `.claude/settings.json`. Every experiment effectively re-wrote graph
  state from inside its own worktree, corrupting reconcile.
- Current state: filter at `src/automil/cli.py:316-319` excludes paths
  starting with the resolved `automil/` directory and `.claude/`.
- Reminder: do NOT remove this filter without re-introducing equivalent
  protection. The bug surface is large because the agent submits frequently.

### Children submitted before parents (orphan subtrees)

- Past mistake: nodes 0051-0055 submitted with `--parent 0048` while 0048
  itself was still pending. Pareto check ran against `parent.composite = 0`,
  so 0051-0055 spuriously labelled "keep".
- Current state: submit refuses (`src/automil/cli.py:241-276`) if the
  parent has `type=proposed`, `status=running`, or is missing.
- Reminder: agent batch logic must respect parent topology.

---

## Test Coverage Gaps

### Concurrent-restart safety

- Two orchestrator daemons started near-simultaneously will both pass the
  `pid_file.exists()` check and proceed; the second daemon then overwrites
  the PID file at `src/automil/orchestrator.py:721`. No flock, no atomic
  PID claim.
- Files: `src/automil/orchestrator.py:747-768`
- Risk: `results.tsv` corruption (two appenders), worktree fights
  (two daemons claim the same node id), graph.json races.
- Priority: medium. Manual operator discipline today.

### `_reload_orchestrator_config` type validation

- Files: `src/automil/orchestrator.py:640-674`
- A YAML edit that puts `max_concurrent_per_gpu: "8"` (string) instead of
  `8` (int) will be assigned as a string. `len(running_on) >= "8"` raises
  `TypeError` on the next scheduling tick — caught by the broad
  `except Exception` in `tick()`. The orchestrator keeps "running" but
  schedules nothing.
- Priority: medium.

### Worktree-leftover detection

- If `git worktree remove --force` succeeds but the directory still exists
  (e.g. file held open by another process), `cleanup_worktree` falls back
  to `shutil.rmtree`, which can fail silently per-file. No tests verify
  end-state cleanliness of `.automil_worktrees/`.
- Files: `src/automil/runner.py:74-94`
- Priority: low.

### `_load_dotenv` quoting

- Files: `src/automil/orchestrator.py:222-250`
- No tests covering quoted values, `export ` prefix, or comments after `=`.
- Priority: low–medium (depends on operator's `.env` style).

### Path-validation in `apply_overlay` deletions

- `Runner.apply_overlay` does not re-check that `worktree_path / rel_path`
  resolves under `worktree_path` before `unlink()`-ing.
- Files: `src/automil/runner.py:55-61`
- Priority: medium (security-adjacent).

---

## Runtime Artefacts and Gitignore Coverage

### Root `.gitignore` does NOT exclude `.automil_worktrees/`

- The repo root `.gitignore` (`/.gitignore`) lists `__pycache__/`, `.venv/`,
  `*.log`, `.env`, etc., but does NOT list `.automil_worktrees/`. The
  framework creates this directory at the git root via
  `Runner.__init__` (`src/automil/runner.py:16-17`).
- Files: `/.gitignore` (root); template
  `src/automil/templates/.gitignore.j2` DOES list `.automil_worktrees/`.
- Impact: This repo (autoMIL itself) is currently dirty —
  `git status` shows `.automil_worktrees/` as untracked
  (see "Git status at session start"). Anyone running `git add -A` here
  would commit the worktree base.
- Fix approach: add `.automil_worktrees/` and `.automil_active` to the
  root `.gitignore`. Both are runtime-only artefacts.

### Other runtime files correctly gitignored

- `automil/graph.json`, `automil/results.tsv`, `automil/orchestrator/`,
  `*.pid`, `*.log` are ignored either by the root `.gitignore` or by the
  per-project template (`src/automil/templates/.gitignore.j2`,
  `benchmarks/experiments/ccrcc/automil/.gitignore`).

### `.env` files

- `.env` and `benchmarks/.env` are both gitignored at the root level.
  `benchmarks/.env.example` is the committed template.
- Reminder: do not read `.env` contents from subprocesses or logs.

---

## Dependencies at Risk

### Vendored frontend libs at fixed commits

- Files: `src/automil/viz/static/vendor/` (d3, three, three-spritetext,
  3d-force-graph)
- Risk: no SBOM, no version manifest, no auto-upgrade path. Browser console
  warnings about deprecated three.js APIs will never bubble to a CI signal.
- Fix approach: pin versions in a `package.json` even if no build step is
  used.

### `aiohttp` and `watchdog` as `viz` deps

- Files: `src/automil/viz/server.py:22-33`
- Failure mode is a hard `sys.exit(1)` with a printed install hint. Fine,
  but the framework should at least guard against `viz start` being run
  without these deps via `automil check`.

---

## Missing Critical Features

### No structured cancellation of running experiments

- The orchestrator can timeout an experiment but has no `automil cancel <id>`
  command. The only way to kill a running experiment is to find its PID via
  `automil orchestrator status` and `kill` it manually.
- Impact: when the agent realizes a batch was misconfigured (e.g. wrong
  `--encoder`), it cannot stop it without operator help — which violates
  the autonomous-loop principle.

### No deduplication beyond `config_hash` exact match

- `ExperimentGraph.has_config()` (`src/automil/graph.py:387-392`) does
  exact-match dedup. Two experiments that differ only in comment whitespace
  in non-tokenized files (e.g. the YAML config) will hash differently and
  both run. Two functionally-identical experiments with reordered imports
  hash differently.
- Impact: GPU-time waste; not a correctness issue.

### No `automil resubmit` to retry a crashed node id

- Today the agent must `automil propose` a fresh id and `automil submit`
  against it. The crashed archive is left in place. This makes the graph
  noisy with permanently-failed nodes that will never have descendants.

---

## Concerns Summary

| Severity | Area | Quick handle |
|----------|------|--------------|
| HIGH | Process-group not used → VRAM leak on timeout | `start_new_session=True` |
| HIGH | `.automil_worktrees/` missing from root `.gitignore` | One-line fix |
| HIGH | GPU saturation regression risk (default vram, safety margin tax) | Auto-feedback from `results.tsv` |
| MED | Naive `.env` parser | Use `python-dotenv` |
| MED | `mark_running` hard assert can crash daemon | Replace with logged guard |
| MED | Hot-reload config swallows YAML errors | Log on parse failure |
| MED | PID-reuse race on stop/status | Cross-check process start time |
| MED | Subprocess inherits full env (secret leak) | Whitelist env vars |
| MED | `apply_overlay` deletions skip resolve-validation | Re-check inside worktree |
| MED | Best-fit bin-pack starves large jobs | Age-based priority bump |
| LOW | Vendored JS libs unpinned | Add `package.json` |
| LOW | Hard-coded `DEFAULT_TECHNIQUE_MAP` drifts | Drive from `--techniques` |
| LOW | `recalculate_scores` is O(N²) | Build parent→children index |

---

*Concerns audit: 2026-04-30*
