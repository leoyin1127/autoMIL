---
phase: 01
status: clean
reviewed_at: 2026-05-02
reviewer: orchestrator-inline
blockers: 0
warnings: 2
info: 1
note: |
  The dispatched gsd-code-reviewer agent (sonnet) hit the rate-limit before
  writing a full REVIEW.md (~7.5 min runtime, 111 tool calls). This report is
  an orchestrator-inline review of the highest-risk surfaces from the
  reviewer's brief, cross-checked against the verifier's deep audit
  (01-VERIFICATION.md) which independently confirmed all 8 success criteria
  and 15/15 REQ-IDs. A full reviewer pass can be re-run after the rate-limit
  resets if Leo wants additional depth.
---

# Phase 1 Code Review — autoMIL milestone v1.0

> **Scope:** framework code only (`src/automil/registry/`, `src/automil/cli/lifecycle/`, modified `cli/submit.py`/`check.py`/`init.py`, `tests/fixtures/synthetic_consumer/`). Out of scope per D-49: anything under `benchmarks/`.

> **Verdict:** clean. Zero blockers. Two advisory warnings, one informational note. Phase 1 ready to ship from a code-quality standpoint.

## High-risk surface spot-checks

### ✓ port-variant graph.json mutation atomicity (T-01-50 / iter-2 BLOCKER-02 closure)
**File:** `src/automil/cli/lifecycle/port_variant.py:282-300`

Uses `ExperimentGraph.load() → mutate → save()` — `save()` is atomic via tempfile+rename per PATTERNS.md §3. Comment at line 284 explicitly cites the rule. Variant module is written BEFORE the graph mutation, so a mid-write crash leaves an orphan variant module (recoverable: re-run port-variant is idempotent on matching node_id per D-43; mismatched node_id with same name hard-fails per D-43 to prevent silent overwrite). Acceptance test `test_port_variant_writes_variant_spec_to_graph_json` covers the contract.

### ✓ revert-baseline pre-stash safety (Leo's "never blind-checkout" memory)
**File:** `src/automil/cli/lifecycle/revert_baseline.py:120-130` + module docstring lines 3-5

Mandatory pre-stash to `automil-revert-<timestamp>` BEFORE any `git checkout`. Stash name printed to stdout for operator recovery. Module docstring explicitly cites Leo's standing memory. Test `test_uncommitted_non_protected_also_stashed` asserts both protected and non-protected uncommitted files survive in the stash. WARNING-03 from iter-2 plan-check is closed.

### ✓ Hard-fail invariants — zero escape hatches (D-32, D-34)
Grep for `--force | --skip-validators | --no-protect | --bypass` across `src/automil/cli/` and `src/automil/registry/`: only two matches and both are legitimate:
- `cli/submit.py:205` is a comment explicitly stating "no --force escape in Phase 1" (T-01-28 mitigation)
- `cli/lifecycle/verify_repro.py:126` is `git worktree remove --force` (orchestrator cleanup, not a user-facing flag)

No bypass mechanisms exist for protected-files reject, validator-chain failure, or registry-consistency check. Production-grade hard-fail surface clean.

### ✓ Framework-only scope (D-49)
Grep for `ccrcc | node_0176` in `src/automil/`: 3 matches, all in docstrings/comments (`manifest.py:31` example, `verify_repro.py:158` explanatory text, `revert_baseline.py:87` error message naming a likely consumer). Zero code coupling. Verifier independently confirmed via the same grep (its report cites 6 matches but includes additional doc-context lines; the substance is the same).

### ✓ Validator chain ordering (T-01-14)
PurityValidator runs BEFORE InterfaceValidator in `cli/submit.py:225-231`. Reasoning: purity is AST-only and rejects malicious top-level I/O before InterfaceValidator imports the module. Both are short-circuited on first failure. Test `test_submit_validator_chain.py` asserts the ordering.

### ✓ apply config-edit safety (D-41)
**File:** `src/automil/cli/lifecycle/apply.py`

Atomic tempfile+rename via `_atomic_write_text` from `cli/lifecycle/_shared.py`. Rolling single .bak (not stack — D-41 specifics matched). Hard-fails with helpful messages on missing node, missing variant_spec (suggests `port-variant` per error UX), and malformed `model.variant`/`loss.variant`/`policy.variant` config sections.

### ✓ verify-repro clean-checkout semantics (D-39)
**File:** `src/automil/cli/lifecycle/verify_repro.py`

Uses `runner.py`'s git-worktree mechanism (orchestrator's standard isolation). Subprocess invocation uses `sys.executable` (NOT bare `python`) to ensure the active venv is used. Manifest records `git_sha` of the clean state. Synthetic-consumer round-trip (`tests/test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes`) confirms the actual experiment runs on the registry path, not on the operator's working tree.

### ✓ Lazy-torch invariant (D-21 + D-22 forward-compat)
`src/automil/registry/variants/{model,loss,policy}.py` use `TYPE_CHECKING` guard for tensor types. `python -c "from automil.registry import ..."` works without torch installed. Tests validate this invariant at module-load time.

## Warnings (advisory)

### WARNING-01: Doc-comment references to specific consumers in framework code
**Files:** `src/automil/registry/manifest.py:31`, `src/automil/cli/lifecycle/verify_repro.py:158`, `src/automil/cli/lifecycle/revert_baseline.py:87`

Three doc-comments reference CCRCC by name as illustrative examples (e.g., `# e.g., "node_0176"`). These are pedagogically helpful but couple the framework conceptually to one consumer. Phase 8 (`DEC-01`) will surface these when the second consumer (sklearn-iris) lands. **Suggested fix:** replace with generic placeholders ("node_xxxx", "<your_dataset>") in a future cleanup pass — non-blocking.

### WARNING-02: ClickException coverage variance in error formatting
31 `ClickException` raises across the lifecycle package; only 8 follow the literal "Refusing to <verb>" prefix. The remainder use task-specific phrasings (e.g., `"variant_spec missing on node {id}"`, `"Cannot port: ..."`). PATTERNS.md §7 recommends but does not mandate the "Refusing to" prefix. Net effect: error UX is informative, but not stylistically uniform. **Suggested fix:** style-pass during Phase 8 acceptance review.

## Informational

### INFO-01: Synthetic-consumer fixture is torch-free by design
`tests/fixtures/synthetic_consumer/program.py` is 82 lines with no torch import — it computes a deterministic composite from a stub `forward()`. This is correct: it exercises the framework end-to-end without forcing GPU CI cost. The Phase 1 acceptance gate is meaningful because the registry pipeline (port-variant → refresh-registry → apply → verify-repro) is exercised on a REAL CLI chain, even if the variant body is trivial. A future "real-consumer" demonstration (CCRCC port, sklearn-iris in Phase 8) is the next layer of confidence — Phase 1 ships the framework that makes those demonstrations possible.

## Suite-level health

- **387 tests** passing (113 Phase 0 baseline + 274 Phase 1 net-new)
- **Phase 1 acceptance gate** (`test_synthetic_consumer_roundtrip.py::test_full_roundtrip_passes`) green
- **Lazy torch import** invariant maintained (Plan 01-01 D-24)
- **Wave-disjointness** verified post-merge across all 7 waves
- **Atomic writes** for every persisted state mutation (config.yaml, graph.json, manifests, repro_manifest.yaml)

## Recommendation

Phase 1 is clean to ship. The 2 warnings are stylistic / scope-aware notes that belong in a Phase 8 polish pass, not a Phase 1 blocker.
