---
status: complete
phase: 05-generalization-gate
source:
  - 05-01-SUMMARY.md
  - 05-02-SUMMARY.md
  - 05-03-SUMMARY.md
  - 05-04-SUMMARY.md
  - 05-05-SUMMARY.md
  - 05-06-SUMMARY.md
  - 05-07-SUMMARY.md
  - 05-08-SUMMARY.md
  - 05-09-SUMMARY.md
  - 05-10-SUMMARY.md
  - 05-11-SUMMARY.md
  - 05-12-SUMMARY.md
started: "2026-05-06T02:00:00Z"
updated: "2026-05-06T02:30:00Z"
verifier: autonomous (Auto mode — bash-verifiable surfaces only)
---

## Current Test
<!-- All 20 tests complete; nothing pending -->

## Tests

### 1. CLI surface: `automil --help` exposes `gate`, `nominate`, `promote`
**Expected:** `automil --help` lists all three commands with descriptions.
**Result:** PASS — `gate` (group), `nominate` (top-level command), `promote` (top-level command) all present.

### 2. CLI surface: `automil gate --help` shows 4 subcommands
**Expected:** `register-manifest`, `retire-manifest`, `status`, `stats`.
**Result:** PASS — all 4 subcommands listed.

### 3. CLI surface: `automil nominate --help`
**Expected:** Help text says "Nominate a keep-status node as a gate candidate (D-142)".
**Result:** PASS — D-142 cited; usage clear; idempotent property mentioned.

### 4. CLI surface: `automil promote --help` includes `--calibrate`
**Expected:** D-151 dry-run flag present + `--backend` option.
**Result:** PASS — both flags documented.

### 5. `automil init` creates a config with `gate:` section
**Expected:** Fresh `automil init` writes `automil/config.yaml` containing a `gate:` section with K, p_threshold, bootstrap_reps, auto_nominate.
**Result:** PASS — `gate:` section present with `auto_nominate: false`, `K: 2`, `p_threshold: 0.05`, `bootstrap_reps: 1000`.

### 6. `gate:` comment block uses paper-campaign-vs-framework framing
**Expected:** Comment says "consumer-supplied (NOT framework constants)" and explicitly mentions "Leo's autoMIL-paper defaults".
**Result:** PASS — exact text "Leo's autoMIL-paper defaults; another consumer with a different statistical-power requirement supplies different values" present.

### 7. Manifest registration end-to-end (programmatic via `write_manifest_committed`)
**Expected:** Manifest written to `automil/gate/<parent_id>.gate_manifest.json` AND committed to git in same atomic operation.
**Result:** PASS — manifest file exists; git log shows `gate: register manifest for node_0001 (held_out: 3 cells, K=2, p<0.05)`.

### 8. Manifest schema (D-137 fields)
**Expected:** parent_id, created_at, git_committed_at_sha, held_out_cells (list of 4-tuples), K, p_threshold, bootstrap_reps, win_definition, schema_version.
**Result:** PASS — all 9 fields present with correct types.

### 9. Manifest committed to git (cryptographic timestamp for F2 paper)
**Expected:** `git log` shows the manifest commit.
**Result:** PASS — commit `4ea02c0 gate: register manifest for node_0001 (held_out: 3 cells, K=2, p<0.05)` present.

### 10. Manifest immutability (refuse overwrite)
**Expected:** Second `write_manifest_committed` for the same parent_id raises `FileExistsError` with operator-recovery hint to use `retire-manifest`.
**Result:** PASS — exact error: `FileExistsError: Manifest already exists: ... Run 'automil gate retire-manifest node_0001 --reason '...'' first.`

### 11. `automil gate stats` works on empty graph
**Expected:** Graceful message when no `graph.json` exists (no crash, no traceback).
**Result:** PASS — `No graph.json found — no experiments have run yet.`

### 12. `automil gate status <parent_id>` shows manifest details
**Expected:** Tabular output with parent_id, created_at, git_committed_at_sha, K, p_threshold, bootstrap_reps, held_out_cells listed.
**Result:** PASS — all 7 fields rendered; held-out cells displayed in 4-column table (cell_id-prefix, dataset, encoder, task).

### 13. Framework purity: zero `autobench`/`AUTOBENCH_`/`benchmarks/` in `gate/` + gate CLI files
**Expected:** Recursive grep returns zero matches in `src/automil/gate/`, `cli/nominate.py`, `cli/promote.py`, `cli/gate.py`.
**Result:** PASS — zero matches.

### 14. BCK-04 lint passes (gate/ allowlist extension)
**Expected:** `tests/test_backend_isolation_lint.py` includes `test_gate_clean_per_bck04_allowlist`; both BCK-04 lint tests pass.
**Result:** PASS — 2/2 tests pass.

### 15. Pitfall-6 anti-acceptance gate (load-bearing single-file gate)
**Expected:** All 3 test functions in `tests/gate/test_pitfall6_held_out_isolation.py` pass: pass-path, fail-path-reverts-to-keep, redactor isolation pre-and-post.
**Result:** PASS — 3/3 tests pass in <0.4s; 35 D-149 assertion citations verified across the 3 functions.

### 16. Gate framework purity guards (AST-based)
**Expected:** All 4 tests pass: `test_gate_dir_has_files`, `test_gate_no_autobench_refs`, `test_gate_no_process_control_refs`, `test_gate_no_blind_checkout`.
**Result:** PASS — 4/4 tests pass; AST visitor confirms no `git checkout` literal in `src/automil/gate/`.

### 17. Bonferroni direction is `alpha / K` (DIVIDE), NOT multiply p-values
**Expected:** `bonferroni_correct` returns `p_threshold / K`.
**Result:** PASS — `src/automil/gate/stats.py:68` reads exactly `return p_threshold / K`.

### 18. scipy is in core deps (lifted from `[ml]` optional)
**Expected:** `pyproject.toml` `[project.dependencies]` includes `scipy>=1.11`.
**Result:** PASS — `scipy>=1.11` at line 20 of `[project.dependencies]` with comment `# D-141 GTE-04: paired Wilcoxon + bootstrap CI (gate stats)`.

### 19. Phase 5 sub-suite (gate + held-out isolation + viz/status promotion_rate + JobSpec.metadata)
**Expected:** All 134 Phase-5-introduced tests pass.
**Result:** PASS — 134 passed in 4.85s.

### 20. Full test suite (no regressions)
**Expected:** 779 passed + 9 skipped (Phase 4 baseline 666 + 113 new = 779).
**Result:** PASS — 779 passed, 9 skipped, 17 warnings in 50.54s.

## Summary

**20/20 tests PASS.** All Phase 5 user-observable surfaces verified:
- CLI surfaces (gate group, nominate/promote top-level, all `--help` text) wired correctly
- `automil init` produces a config with the consumer-facing `gate:` section + paper-campaign-vs-framework comment block
- Programmatic manifest registration creates and commits to git in one atomic operation
- Manifest schema honors D-137 (9 fields)
- Manifest immutability enforced (FileExistsError with operator-recovery hint)
- `automil gate status` shows manifest details; `automil gate stats` graceful on empty graph
- Pitfall-6 anti-acceptance gate green (the load-bearing acceptance gate that the F2 paper review depends on)
- Framework purity preserved (zero autobench refs in gate/ + gate CLI files)
- BCK-04 lint extended to gate/ subdirectory (2/2 tests pass)
- Gate framework purity guards green (4/4 AST-based tests)
- Bonferroni applied as alpha/K (DIVIDE direction), not multiply p-values
- scipy lifted to core deps with D-141/GTE-04 citation
- 779 tests pass, 0 regressions from Phase 4's 666 baseline (+113 Phase 5 tests)

## Gaps

None at framework level. Phase 5 ships clean.

## Leo Follow-up (deferred — not a UAT blocker)

The empirical K-threshold determination (D-151 calibration pilot, Plan 05-12) requires Leo to:
1. Choose CCRCC `node_0176` configuration as the known-good change.
2. Pick 3-5 fresh cells (3 CCRCC + 2 CLWD recommended).
3. Register a calibration manifest, submit, run `automil promote --calibrate <candidate_id>`.
4. Inspect the delta matrix in `archive/<candidate_id>/gate_evaluation.jsonl`.
5. Pick K such that `node_0176`-equivalent improvements pass consistently.
6. Update `.planning/phase-05-calibration.md` (scaffold committed at 90011e8) with the chosen K + rationale.

This is a deferred operator action. The framework-side scaffold (smoke test + scaffolding doc) ships in Plan 05-12. The framework-default K=2 is provisionally functional for any consumer who prefers framework defaults until they run their own calibration.
