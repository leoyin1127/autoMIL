---
phase: 05-generalization-gate
plan: 11
subsystem: testing
tags: [gate, held-out-isolation, pitfall-6, anti-acceptance, tdd, framework-purity, bck-04, d-149]

# Dependency graph
requires:
  - phase: 05-generalization-gate
    provides: "Wave 1-10 gate package: stats, manifest, nominate, evaluate, promote, CLI"
provides:
  - "Pitfall-6 anti-acceptance gate test (D-149) — 9-assertion end-to-end verifier for Phase 5"
  - "Framework purity guards for gate/ (D-148)"
  - "BCK-04 lint extension targeting gate/ specifically (test_backend_isolation_lint.py)"
affects:
  - phase: 06-calibration-pilot (depends on Phase 5 gate working)
  - phase: 08-acceptance (this test IS the Phase 5 acceptance gate)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Goal-backward test: single test function covering all 9 D-149 assertions in sequence"
    - "_RecordingBackend: real JobHandle(node_id, backend, opaque_id, submitted_at) signature"
    - "AST-based purity checks avoid false positives from docstring mentions of forbidden patterns"
    - "lru_cache hygiene: cache_clear() called between subtests to prevent stale held-out sets"
    - "K=5 held-out cells with p_threshold=0.2 — proven statistical setup for deterministic PASS"

key-files:
  created:
    - tests/gate/test_pitfall6_held_out_isolation.py
    - tests/gate/test_framework_purity.py
  modified:
    - tests/test_backend_isolation_lint.py

key-decisions:
  - "K=5 held-out cells instead of K=2: Wilcoxon signed-rank requires n>=5 to achieve p<=0.04; K=2 minimum achievable p=0.25 makes PASS path statistically impossible"
  - "AST-based process-control detection for purity tests: avoids false positives from docstring mentions (e.g. 'BCK-04 clean: no os.kill') that raw string search would flag"
  - "Three test functions: PASS path (all 9 assertions), FAIL path (assertion 7 fail leg), redactor-isolation (assertions 4+8)"
  - "The test_gate_clean_per_bck04_allowlist extension to test_backend_isolation_lint.py asserts gate/ is explicitly in scope of BCK-04 and has zero allowlisted files"

patterns-established:
  - "Pitfall-6 test pattern: inject fake held-out nodes with numeric IDs matching _NODE_ID_RE = r'\bnode_\d{4,}\b'; string IDs with letter suffixes don't get redacted"
  - "Composite stamping pattern: monkeypatch _read_eval_composite to stamp graph.nodes[child_id]['composite'] from per-cell backend fixture before the original function reads it"
  - "Framework purity test pattern: __file__-relative GATE_DIR discovery (works regardless of pytest cwd)"

requirements-completed: [GTE-01, GTE-02, GTE-03, GTE-04, GTE-05, GTE-06]

# Metrics
duration: 35min
completed: 2026-05-05
---

# Phase 05 Plan 11: Pitfall-6 Anti-Acceptance Gate Summary

**Pitfall-6 anti-acceptance gate test (D-149): 9-assertion end-to-end held-out isolation verifier + AST-based framework purity guards for gate/ — Phase 5 goal-backward verifier is green**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-05T00:00:00Z
- **Completed:** 2026-05-05T00:35:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- D-149 anti-acceptance gate test: all 9 assertions in one test function; PASS path + FAIL path + redactor-isolation companion tests
- Framework purity (D-148): 4 lint guards (autobench-free, process-control-free, no blind checkout, file discovery)
- BCK-04 extension: `test_gate_clean_per_bck04_allowlist` in `test_backend_isolation_lint.py` — gate/ explicitly targeted

## Task Commits

Each task was committed atomically:

1. **Task 1: Pitfall-6 9-assertion test** - `2417769` (test)
2. **Task 2: Framework purity + BCK-04 extension** - `d11ddd5` (test)

## Files Created/Modified
- `tests/gate/test_pitfall6_held_out_isolation.py` - Load-bearing 9-assertion D-149 anti-acceptance gate (3 test functions, 806 lines)
- `tests/gate/test_framework_purity.py` - 4 framework purity guards for gate/: autobench-free, process-control-free (AST), no blind checkout, dir discovery
- `tests/test_backend_isolation_lint.py` - Extended with `test_gate_clean_per_bck04_allowlist` asserting gate/ is in BCK-04 scope

## Decisions Made
- **K=5 cells instead of K=2:** Wilcoxon signed-rank test requires n>=5 to achieve p-value below Bonferroni-corrected threshold. K=2 minimum achievable p=0.25 which can never pass p_threshold/K=0.1. Used the proven K=5, p_threshold=0.2 setup from test_promote.py (Wilcoxon p=0.031 <= 0.04).
- **AST-based process-control detection:** Raw string search for `os.kill` flags promote.py's docstring `BCK-04 clean: no os.kill...`. Used the same AST visitor pattern as `scripts/check_backend_isolation.py` to parse code nodes only.
- **`_RecordingBackend` composite stamping:** Monkeypatched `_read_eval_composite` to stamp the configured composite on `graph.nodes[child_id]['composite']` at poll time. This is the cleanest injection point — the original function reads from the node, so pre-stamping at the right moment is sufficient.
- **Fake held-out node IDs must be numeric:** The redactor regex `_NODE_ID_RE = r'\bnode_\d{4,}\b'` only matches `node_NNNN` (pure numeric suffix). IDs like `node_held_out_fakea0001` don't match and never get redacted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] K=5 cells for statistical PASS path validity**
- **Found during:** Task 1 (Pitfall-6 test pass path verification)
- **Issue:** Plan specified K=2 held-out cells but Wilcoxon signed-rank on n=2 samples has minimum achievable p=0.25, which can never pass Bonferroni-corrected alpha=0.1 (p_threshold=0.2/K=2). The PASS path would never be achievable.
- **Fix:** Extended fixture to 5 held-out cells with p_threshold=0.2 (proven setup from test_promote.py; Wilcoxon achieves p=0.031 <= 0.04).
- **Files modified:** tests/gate/test_pitfall6_held_out_isolation.py
- **Verification:** test_pitfall6_held_out_isolation_pass_path passes with status='registered'
- **Committed in:** 2417769

**2. [Rule 1 - Bug] Fake held-out node IDs must match _NODE_ID_RE**
- **Found during:** Task 1 (redactor-isolation subtest)
- **Issue:** Used IDs like `node_held_out_fakea0001` which don't match `_NODE_ID_RE = r'\bnode_\d{4,}\b'` (requires pure-numeric suffix). The redactor never replaced them.
- **Fix:** Changed fake node IDs to `node_0091`, `node_0092`, `node_0099` (numeric suffix only).
- **Files modified:** tests/gate/test_pitfall6_held_out_isolation.py
- **Verification:** Both redactor-isolation test and pass-path test pass with `<HELD_OUT>` present in redacted output.
- **Committed in:** 2417769

**3. [Rule 1 - Bug] AST-based purity test to avoid docstring false positive**
- **Found during:** Task 2 (framework purity test verification)
- **Issue:** Raw string search for `os.kill` hits `promote.py` docstring `BCK-04 clean: no os.kill / os.killpg / Popen / .pid references.` — a comment about what's absent, not actual code.
- **Fix:** Used AST visitor (same pattern as scripts/check_backend_isolation.py) which parses code nodes only and never flags string literals.
- **Files modified:** tests/gate/test_framework_purity.py
- **Verification:** test_gate_no_process_control_refs passes; `grep -rE "os\.kill" src/automil/gate/` still shows 1 hit from docstring, but AST test correctly returns 0 violations.
- **Committed in:** d11ddd5

---

**Total deviations:** 3 auto-fixed (3 bugs — statistical setup, regex mismatch, docstring false positive)
**Impact on plan:** All auto-fixes necessary for test correctness. No scope creep. Assertion coverage and structure match plan exactly.

## Issues Encountered
- **Pre-existing test failures:** `tests/test_tick_cells.py` (3 failures) and `tests/test_per_fold_writer.py` (import error for `autobench`) are pre-existing failures from the main branch, not related to Plan 11 changes. Logged in deferred-items.

## Known Stubs
None — all assertions make real code calls; no placeholder logic.

## Threat Flags
None — no new network endpoints, auth paths, or trust boundary changes introduced (tests only).

## Self-Check: PASSED

**Files exist:**
- tests/gate/test_pitfall6_held_out_isolation.py: FOUND
- tests/gate/test_framework_purity.py: FOUND
- tests/test_backend_isolation_lint.py: FOUND (modified)

**Commits exist:**
- 2417769: FOUND
- d11ddd5: FOUND

**Tests pass:**
- `uv run pytest tests/gate/test_pitfall6_held_out_isolation.py tests/gate/test_framework_purity.py tests/test_backend_isolation_lint.py -v`: 9 passed

**D-149 assertion coverage:**
- `grep -cE "Pitfall-6 assertion [1-9]" tests/gate/test_pitfall6_held_out_isolation.py`: 35 (≥9 required)
- `grep -c '<HELD_OUT>' tests/gate/test_pitfall6_held_out_isolation.py`: 7 (≥1 required)
- `grep -c 'gate_eval' tests/gate/test_pitfall6_held_out_isolation.py`: 21 (≥2 required)
- `grep -c 'submitted_specs\|submit_call_count' tests/gate/test_pitfall6_held_out_isolation.py`: 8 (≥1 required)
- `grep -c 'fromisoformat' tests/gate/test_pitfall6_held_out_isolation.py`: 1 (≥1 required)
- `grep -c 'cache_clear' tests/gate/test_pitfall6_held_out_isolation.py`: 11 (≥1 required)
- `grep -c 'D-149\|Pitfall.6' tests/gate/test_pitfall6_held_out_isolation.py`: 60 (≥2 required)

## Next Phase Readiness
- Phase 5 goal-backward verifier is green: held-out isolation contract holds end-to-end
- Phase 6 calibration pilot can proceed with confidence the gate machinery is verified
- Phase 8 acceptance gate can reference `test_pitfall6_held_out_isolation_pass_path` as the Phase 5 acceptance criterion

---
*Phase: 05-generalization-gate*
*Completed: 2026-05-05*
