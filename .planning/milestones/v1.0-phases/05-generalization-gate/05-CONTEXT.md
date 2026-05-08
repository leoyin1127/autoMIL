# 05-CONTEXT.md — Generalization gate

**Phase:** 5 — Generalization gate
**Goal (from ROADMAP):** A candidate variant is only promoted to the parent's registered variants directory after improving on ≥K held-out cells (declared BEFORE search starts), measured by a paired statistical test — defending the F2 reviewer attack "you overfit to the search cell."
**Depends on:** Phase 4 (cap contract + cells/registry — gate runs against cells; gate evaluations submit through the same Backend path the agent uses, so they inherit the cap)
**Requirements:** GTE-01..06

## Engineering decisions (LOCKED — no Leo input needed)

These follow directly from requirements + Pitfall 6 defence + existing codebase shape (registry from Phase 1, backend from Phase 2, cells from Phase 4). The planner can treat them as fixed.

### D-135: Package layout — `src/automil/gate/`
New package mirroring `src/automil/cells/` from Phase 4:
- `gate/manifest.py` — `GateManifest` frozen dataclass + `read_manifest`, `write_manifest`, `load_or_create_manifest`. Persists to `automil/gate/<parent_id>.gate_manifest.json` (top-level under automil/, sibling of `cells/`).
- `gate/nominate.py` — `nominate(node_id)` mutates graph node status from `keep` → `candidate`. Idempotent. Pure registry write + graph save.
- `gate/evaluate.py` — `evaluate_candidate(candidate_node_id, manifest, backend)` — spawns N held-out eval-nodes via `backend.submit()`, polls for completion, returns the per-cell result matrix. Long-running but bounded by Phase 4's per-cell cap.
- `gate/promote.py` — `promote(candidate_node_id)` — runs `evaluate_candidate`, applies the statistical test, mutates status to `registered` if pass / back to `keep` if fail, emits a `promotion_rate` event.
- `gate/stats.py` — pure-function `paired_wilcoxon_with_bootstrap(deltas, p_threshold, bootstrap_reps)` and `bonferroni_correct(p_values, K)`. No I/O. Standalone-testable.

### D-136: Node status taxonomy
Extend the existing graph node status enum with `candidate` between `keep` and `registered`:
```
running → executed/{keep,discard,crash} → candidate → registered (or back to keep on gate fail)
```
Compatibility: existing `keep`/`discard`/`crash` semantics unchanged. `_reevaluate_descendants` cascade rule is unchanged (Pareto check on auc/bacc/composite). The `candidate` state is purely additive — it does NOT affect descendant cascade or keep/discard scoring.

### D-137: gate_manifest.json schema (per-parent, not per-candidate)
Manifests live at `automil/gate/<parent_id>.gate_manifest.json`. **One manifest per parent**, not per candidate — this is what makes pre-registration meaningful (the manifest exists before the agent starts proposing children of `parent_id`, and every candidate child of that parent is gated against the SAME manifest).

```json
{
  "parent_id": "node_0176",
  "created_at": "2026-05-05T...Z",
  "git_committed_at_sha": "<the commit sha that landed this manifest>",
  "held_out_cells": [
    {"cell_id": "abc123...", "dataset": "ccrcc", "encoder": "uni_v2", "task": "high_grade"},
    ...
  ],
  "K": 2,
  "p_threshold": 0.05,
  "bootstrap_reps": 1000,
  "win_definition": "delta_composite > 0 AND p < p_threshold (paired Wilcoxon, Bonferroni-corrected over K held-out cells)",
  "schema_version": "gate-v1"
}
```

### D-138: Pre-registration enforcement (Pitfall 6 defence)
`automil gate register-manifest <parent_id>` is a CLI command that:
1. Validates the manifest dict (schema-valid, K ≤ len(held_out_cells), p_threshold > 0, bootstrap_reps ≥ 100).
2. Writes the manifest atomically (`tempfile.mkstemp` + `os.rename` — same pattern as `cells/state.write_cell`).
3. **Stages and commits the manifest to git in the SAME atomic operation.** If `git add` fails or `git commit` fails, the manifest file is removed (rolled back). The commit message is `gate: register manifest for <parent_id> (held_out: N cells, K=N, p<0.05)`.
4. Records the commit SHA back into the manifest's `git_committed_at_sha` field (second commit if needed). This SHA is the cryptographic timestamp the F2 paper can cite.
5. **Refuses to overwrite an existing manifest** for the same parent_id. Once registered, the manifest is immutable. To change parameters, the operator must `automil gate retire-manifest <parent_id>` (which commits a new file `<parent_id>.retired.gate_manifest.json` annotating WHEN and WHY) before registering a new one.

### D-139: Held-out cell isolation (Pitfall 6 defence #1: agent must be blind)
The agent's view of the experiment graph (via `automil rank`, the trajectory recorder, and `automil status`) MUST be filtered to exclude held-out cell results until the candidate is nominated. Implementation:
- The orchestrator tags every `gate_eval` node with `metadata.held_out: true` AND `metadata.parent_gate_manifest: <parent_id>`.
- `automil rank` filters out `metadata.held_out: true` nodes by default. An override flag `--include-held-out` exists for human operator inspection but logs a WARNING + records to trajectory.
- The trajectory redactor (Phase 3 redactor.py extension) replaces held-out node IDs with `<HELD_OUT>` placeholders in stdout/stderr capture.
- Test: spawn a search loop, run a gate eval, then dump the trajectory.jsonl — assert no held-out cell composite appears anywhere except in the gate-promote event itself.

### D-140: `gate_eval` edge type (GTE-03)
The graph adds a new edge kind `gate_eval` (sibling to existing parent→child relationships). When `evaluate_candidate(candidate_id, manifest, backend)` spawns N held-out evaluations:
- For each held-out cell in the manifest, it calls `backend.submit(spec)` where `spec.metadata.gate_eval = true`, `spec.metadata.gate_parent_node = candidate_id`, `spec.metadata.cell_id = held_out_cell.cell_id`.
- Each returned `JobHandle` corresponds to a graph node with `parent_id = candidate_id` and `edge_type = "gate_eval"` (vs default `edge_type = "search"`).
- This means held-out evals reuse the SAME Backend.submit() pathway as agent submits (GTE-03 explicit) — no parallel mechanism, no opportunity for backend semantics to drift.

### D-141: Statistical test — paired Wilcoxon + bootstrap CI + Bonferroni
Per GTE-04, the test is locked:
- For each held-out cell `i`: `delta_i = candidate_composite_i - parent_composite_i` (paired by cell).
- Wilcoxon signed-rank test on the K paired deltas (using `scipy.stats.wilcoxon` — already in deps via scikit-learn).
- 1000-bootstrap of the delta distribution to compute 95% CI on the median delta.
- Bonferroni correction across K held-out cells: effective `p_threshold_corrected = p_threshold / K`.
- **Wins** iff: Wilcoxon p-value ≤ p_threshold_corrected AND lower bootstrap CI bound > 0 (delta is positive with confidence) AND ≥ K cells show delta > 0 individually.

### D-142: Manual nomination as default (GTE-05)
- Default config: `gate.auto_nominate: false`.
- Agent loop does NOT call `nominate()` — only the operator does, via `automil nominate <node_id>` CLI.
- Reason: prevents the agent from gaming the gate by nominating only its best candidate (selection-bias-on-nomination). Operator-driven nomination forces an explicit human decision that gets recorded in trajectory.
- Opt-in: setting `gate.auto_nominate: true` in `automil/config.yaml` enables agent-driven nomination for cases where the operator trusts the search loop. Auto-nomination logs every nomination with `agent_initiated: true` flag in trajectory for audit.

### D-143: Two-stage gate (Pitfall 6 defence #4)
Promotion to `registered` requires BOTH stages:
- **Stage A (Pareto on search cells):** the existing keep/discard logic from `_reevaluate_descendants`. A candidate must already have `status: keep` on its parent_id at nomination time. Already enforced by D-136 status flow (`keep → candidate → registered`).
- **Stage B (held-out generalization):** the paired-Wilcoxon test from D-141 against the manifest's held-out cells.
The two stages use disjoint data (search cells vs held-out cells), so passing both is meaningful. Stage A budget = search-loop budget (Phase 4 cap). Stage B budget = additional gate-eval budget, allocated separately when `automil promote` runs.

### D-144: `promotion_rate` metric (GTE-06)
- Defined as: `promoted / nominated` over a rolling window (default: 30 days, configurable).
- Surfaces in `automil status` (text), viz dashboard (`/api/promotion-rate` SSE endpoint), and `automil gate stats` CLI subcommand.
- Search-health interpretation: `< 5%` for two consecutive weeks → "gate too strict OR search space too narrow", flag in `automil status` warnings. `> 50%` → "gate too loose OR pre-registration didn't capture genuinely-held-out cells", same flag.
- Implementation: read all nodes from graph.json with status in `{candidate, registered, keep}`, count nominations (status transitioned to candidate at any time, tracked via timestamp in node["history"]) and promotions (status now `registered`), divide.

### D-145: CLI surface (mirrors `automil cell` from Phase 4)
- `automil gate register-manifest <parent_id>` — interactive: prompts for held-out cells, K, p_threshold; validates; commits.
- `automil gate retire-manifest <parent_id> --reason "..."` — supersedes existing manifest with reason recorded.
- `automil gate status [parent_id]` — show manifest details + per-candidate gate state.
- `automil gate stats` — show promotion_rate, search-health flags.
- `automil nominate <node_id>` — top-level command (sibling of `automil submit`), shorter than `automil gate nominate` because operators use it more often.
- `automil promote <candidate_id>` — top-level, runs Stage B and applies result.

### D-146: File touches (planner reference)
**New files:**
- `src/automil/gate/__init__.py`, `manifest.py`, `nominate.py`, `evaluate.py`, `promote.py`, `stats.py`
- `src/automil/cli/gate.py` (the `@main.group("gate")` analog of `cli/cell.py`)
- `src/automil/cli/nominate.py` (top-level command)
- `src/automil/cli/promote.py` (top-level command)
- `src/automil/templates/config.yaml.j2` — extend with `gate:` section (auto_nominate, default K, default p_threshold, bootstrap_reps)
- `src/automil/redactor.py` extension for held-out node-id redaction (D-139) — or new submodule
- `src/automil/viz/server.py` extension for `/api/promotion-rate` endpoint
- Tests under `tests/gate/`: `test_manifest.py`, `test_nominate.py`, `test_evaluate.py` (with mock backend), `test_promote.py`, `test_stats.py`, `test_held_out_isolation.py`, `test_two_stage_gate.py`, plus integration tests for the full nomination → eval → promote flow.

**Modified files:**
- `src/automil/graph.py` — extend with `gate_eval` edge type + `candidate` status; helper `nominations_in_window(days)`.
- `src/automil/cli/__init__.py` — register `gate`, `nominate`, `promote` groups.
- `src/automil/cli/rank.py` — filter held-out nodes (D-139).
- `src/automil/trajectory/redactor.py` — held-out-id placeholder replacement.

### D-147: Backward compatibility
- Existing graphs without `candidate` status work unchanged (the new state is opt-in via nomination).
- Existing trajectories without held-out tagging are not retroactively redacted (acceptable; pre-Phase-5 trajectories have no held-out concept).
- `automil/config.yaml` upgrade: legacy configs without a `gate:` section get framework-fallback defaults; `automil init` for new projects writes the section explicitly.

### D-148: BCK-04 + framework purity
- `src/automil/gate/` MUST contain zero `autobench`/`AUTOBENCH_`/`benchmarks/` references (framework purity check, same as Phase 4 enforced for `cells/`).
- BCK-04 lint allowlist does NOT need extension — the gate module does not touch process control.

### D-149: Pitfall 6 anti-acceptance gate (the goal-backward test)
A test in `tests/gate/test_pitfall6_held_out_isolation.py` that:
1. Creates a synthetic 3-cell experiment graph: 1 search cell, 2 held-out cells.
2. Registers a gate_manifest declaring the 2 held-out cells.
3. Runs a synthetic search loop that proposes 3 candidates, each with composites on the search cell only.
4. Asserts: the agent's trajectory + `automil rank` output for those 3 candidates contains the search cell's composites BUT zero references to held-out cell composites or held-out cell IDs.
5. Operator nominates candidate #2; calls `automil promote candidate_2`.
6. The promote pathway spawns 2 `gate_eval` nodes via Backend.submit() (verified via mock backend assertion); waits for completion; runs paired Wilcoxon.
7. Asserts: BEFORE promotion, candidate_2 has status `candidate`. AFTER promotion (assuming pass): status `registered`. AFTER promotion (assuming fail): status reverts to `keep`. Status transitions logged in node["history"] with timestamps.
8. Asserts: trajectory.jsonl from steps 3-5 still contains zero held-out cell IDs after the promote completes (the held-out evaluation results stay in the gate-internal log path, NOT trajectory).

This test is load-bearing for Phase 5 in the same way `test_cap_fires_with_partial_fold_recovery` was for Phase 4.

### D-150: gate_eval budget (interaction with Phase 4 cap)
Each held-out evaluation consumes its own per-cell budget (the held-out cell's existing budget; if the cell doesn't exist yet, it's auto-created at first gate-eval submit per Phase 4's `get_or_create_cell`). The gate-eval budget is NOT a separate concept — it reuses the per-cell budget machinery. This means: if a held-out cell already had agent submits earlier, gate-eval shares the remaining budget with those. If the held-out cell is fresh, gate-eval starts a new clock.

### D-151: Calibration pilot — within-Phase-5 sub-task
Per ROADMAP success criterion #4, an initial K must be calibrated empirically before locking. The pilot:
- Reuses Leo's existing `node_0176` from CCRCC as the "known-good" change.
- Picks 3-5 fresh cells (different dataset/encoder pairs) from CLWD or other available datasets.
- Submits a gate-eval-equivalent workload manually (via `automil promote --calibrate`) — this is a sub-mode that runs the eval but does NOT promote anything; it just emits the win/loss matrix.
- Operator inspects the matrix, picks K such that `node_0176`-equivalent improvements would consistently pass.
- Locks the chosen K in the framework default + a calibration log committed to `.planning/phase-05-calibration.md`.
- This pilot is its own plan (likely the last plan before the anti-acceptance gate plan).

## OPEN — Leo to lock during planning review

Three genuine product/scientific decisions where engineering best practice can't decide for Leo. Marked clearly so the planner sees them and Leo can patch CONTEXT.md before plans land:

### O-01: Initial K threshold (default before calibration)
Pre-calibration framework default for K. Options:
- (a) `K = max(2, len(held_out_cells) // 3)` — generous, lets calibration tighten.
- (b) `K = max(3, len(held_out_cells) // 2)` — strict majority. F1 paper would default here for "improvement".
- (c) `K = 1` — deliberately too-loose during pilot, gets tightened post-calibration.

**Engineering recommendation:** (a) — generous starting point, calibration narrows. K=2 is the absolute floor; below that the gate is statistically meaningless.

### O-02: p_threshold default (before Bonferroni correction)
- (a) `p_threshold = 0.05` — F1 paper convention, conventional α.
- (b) `p_threshold = 0.01` — stricter; appropriate if K is small (Bonferroni divides by K, so 0.01/K is tiny for K=2).

**Engineering recommendation:** (a) 0.05; Bonferroni handles multiplicity.

### O-03: Held-out cell selection strategy
- (a) **Random sample** of N cells from the available pool (simplest).
- (b) **Stratified** by (dataset, encoder) — ensures held-out covers each dataset×encoder combination at least once.
- (c) **Operator-curated** — the operator hand-picks held-out cells per parent.
**Engineering recommendation:** (b) stratified — defends against the "all held-out are CCRCC, candidate overfits to CLWD" mode. Stratification is implementable as a CLI flag on `automil gate register-manifest`.

### O-04: Pilot scope details
- Which exact 3-5 cells? Engineering can't decide which datasets Leo has access to.
- What "known-good" change to evaluate? `node_0176` config is suggested, but is the change itself well-defined enough to apply to fresh cells?
- Does the pilot block Phase 5 completion (calibration must finish before Phase 5 marks done) or run as a follow-up?

**Engineering recommendation:** Calibration pilot is its OWN plan inside Phase 5 (e.g., 05-NN-PLAN.md), runs against 3 cells from CCRCC + 2 from CLWD if available. Pilot completion is a Phase 5 success criterion; without it, K stays at the framework default and the gate is provisionally functional but not paper-publishable.

### O-05: Auto-nomination opt-in trigger
GTE-05 says manual nomination is default. Should `gate.auto_nominate: true` be a per-parent-manifest setting (so different parents can have different nomination policies) or a global config setting (one knob for the whole project)?

**Engineering recommendation:** Per-manifest. Manifests already live per-parent; auto-nomination naturally scopes there. Lets Leo experiment with auto-nomination on a single parent before turning it on globally.

## Pitfall defences (anti-acceptance reminders)

- **Pitfall 6a (gate too strict):** Calibration pilot mitigates. Promotion-rate metric (D-144) catches it post-launch.
- **Pitfall 6b (gate too loose):** Pre-registration (D-138) + git commit + manifest immutability (D-138 #5) make manipulation auditable. Bonferroni correction (D-141) prevents K-too-small from inflating type-I error.
- **Pitfall 6c (held-out leak into agent loop):** D-139 isolation + D-149 anti-acceptance test.
- **Pitfall 5 (trajectory leak/bloat):** Held-out node IDs redacted in trajectory (D-139); promotion events logged with full detail in a SEPARATE gate log path, not trajectory.
- **Phase 4 cap interaction (D-150):** Gate-eval submits inherit the per-cell cap. Means a slow gate-eval on a near-exhausted cell will hit the cap and produce a partial result — which then breaks the Wilcoxon test (you can't pair against a partial composite). Plan must define behaviour: SKIP the held-out cell from the test (treat as "no signal"), OR fail the entire gate? Engineering recommendation: SKIP and reduce K accordingly; record `cells_skipped_due_to_cap` in the gate result; if `K_passed >= K - skipped`, pass. Document this in D-141 once Leo confirms.

## Test discipline

Every plan in Phase 5 must produce tests that:
- Use `tmp_path` for graph + manifest + cells fixtures (no real backend).
- Mock `Backend.submit()` for evaluate.py tests; assert it was called with the right `metadata.gate_eval=true` flag.
- Use stdlib `scipy.stats.wilcoxon` (already in deps) — no new dependencies.
- Assert framework purity: zero `autobench`/`AUTOBENCH_`/`benchmarks/` in `src/automil/gate/`.
- BCK-04 lint clean (no os.getpid/os.kill/Popen/pid in `src/automil/gate/`).

## Estimate
4-5 days (per ROADMAP), distributed roughly:
- Day 1: D-135..137 foundation (gate package + manifest dataclass + atomic write)
- Day 2: D-138, D-145 CLI + pre-registration commit machinery
- Day 3: D-140, D-141 evaluate + statistical test + bootstrap
- Day 4: D-139 held-out isolation + D-144 promotion_rate + viz
- Day 5: D-149 anti-acceptance gate + D-151 calibration pilot

## Reference
- Pitfall 6 — research/PITFALLS.md (gate too strict / too loose / held-out leak)
- F1 paper §4.4 + §5.6 — paired Wilcoxon + bootstrap CI + Bonferroni machinery (locked by GTE-04)
- Phase 4 SUMMARY files for cells/registry analog (gate package mirrors cells package shape)
- Phase 3 redactor.py for held-out-id redaction extension pattern
