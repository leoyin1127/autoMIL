---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 10
type: execute
wave: 6
depends_on: ["06-01", "06-02", "06-03", "06-04", "06-05", "06-06", "06-07", "06-08", "06-09"]
files_modified:
  - tests/backends/test_phase6_acceptance.py
  - CHANGELOG.md
autonomous: true
requirements: [BCK-05, BCK-06]

must_haves:
  truths:
    - "tests/backends/test_phase6_acceptance.py is a single test module that programmatically verifies all 11 D-179 clauses; failing any clause fails the phase."
    - "Clause 1 verified: contract test passes ≥10 scenarios per backend across [local, mock_slurm, slurm, ray]."
    - "Clause 2 verified: pytest collects ≥789 tests (Phase 5 baseline 779 + Phase 6 additions ≥10)."
    - "Clause 3 verified: `python scripts/check_backend_isolation.py src/automil/` exits 0; slurm.py + ray.py NOT in allowlist."
    - "Clause 4 verified: `pip install -e .` (no extras) → `import automil.backends.slurm` raises ImportError; `automil --help` succeeds."
    - "Clauses 5-6 verified: with extras installed, the backend imports succeed and contract tests for that backend collect."
    - "Clause 7 verified: tests/backends/test_node_0176_smoke.py passes for [local, slurm-debug, ray-local]."
    - "Clause 8 verified: `running/` is namespaced; the daemon-refusal-to-start guardrail fires on a synthetic flat-running fixture (already covered by Wave-0 stubs)."
    - "Clause 9 verified: every terminal node has archive/<id>/run.log via _atomic_write_lines (Wave-0 stubs cover this)."
    - "Clause 10 verified: `grep -r 'autobench\\|AUTOBENCH_\\|benchmarks/' src/automil/backends/` returns 0 matches."
    - "Clause 11 verified: CHANGELOG.md `## 6.0.0` entry contains the BREAKING running/ namespace section + drain-and-restart steps."
    - "Phase 5 779-test baseline + Phase 6 additions all green; total ≥789."
  artifacts:
    - path: tests/backends/test_phase6_acceptance.py
      provides: "Single-file gate verifying all 11 D-179 clauses programmatically."
      contains: "D-179"
    - path: CHANGELOG.md
      provides: "Finalised 6.0.0 entry post-acceptance."
  key_links:
    - from: tests/backends/test_phase6_acceptance.py
      to: scripts/check_backend_isolation.py
      via: subprocess invocation in clause 3
      pattern: "check_backend_isolation"
    - from: tests/backends/test_phase6_acceptance.py
      to: tests/backends/test_contract.py
      via: pytest exit-code check in clause 1
      pattern: "test_contract"
---

<objective>
Wave 6 — Phase 6 acceptance gate. This plan creates a single test file that programmatically verifies every clause of D-179 (the 11-clause acceptance conjunction). If this test passes, Phase 6 is complete.

Purpose: D-179 is a STRUCTURED conjunction. Without a single load-bearing gate test, an executor or reviewer can claim "Phase 6 done" while having silently dropped, e.g., the autobench-purity grep or the BCK-04 lint. The acceptance test makes every clause a separate `assert` so partial failures are diagnosable. This is the same pattern as Phase 5 D-149's `test_pitfall6_held_out_isolation.py` (35 load-bearing assertions in 9 functions per Phase 5 SUMMARY).

Output: 1 new test file + final CHANGELOG touch-up. After this plan: `uv run pytest tests/backends/test_phase6_acceptance.py -v` is the single command that proves Phase 6 success criteria 1-5 are met. The test file becomes part of the suite, so subsequent maintenance breaks of any clause is detected by routine `pytest tests/`.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md
@.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md
@CLAUDE.md

# Reference: Phase 5's load-bearing acceptance gate
@.planning/phases/05-generalization-gate/05-11-PLAN.md

<interfaces>
<!-- Public surface created. The Phase 6 SUMMARY references this test as the gate. -->

After this plan, `uv run pytest tests/backends/test_phase6_acceptance.py -v` reports 11 PASSED test functions, one per D-179 clause:
  test_d179_clause_01_contract_parametrised_over_4_backends
  test_d179_clause_02_phase5_baseline_preserved
  test_d179_clause_03_bck04_lint_clean
  test_d179_clause_04_no_extras_install_works
  test_d179_clause_05_slurm_extra_enables_backend
  test_d179_clause_06_ray_extra_enables_backend
  test_d179_clause_07_node_0176_smoke_passes
  test_d179_clause_08_running_namespaced
  test_d179_clause_09_archive_run_log_orchestrator_owned
  test_d179_clause_10_framework_purity
  test_d179_clause_11_changelog_breaking_entry
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create tests/backends/test_phase6_acceptance.py with 11 D-179 clause tests</name>
  <files>tests/backends/test_phase6_acceptance.py</files>
  <read_first>
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-179 — verbatim 11-clause conjunction)
    - .planning/phases/05-generalization-gate/05-11-PLAN.md (Phase 5's analog acceptance gate — pattern for "9 D-149 assertions in single file")
    - tests/backends/test_running_namespace.py (Wave-0 stubs — clause 8 references)
    - tests/backends/test_log_unification.py (Wave-0 stubs — clause 9 references)
    - tests/backends/test_node_0176_smoke.py (clause 7 references)
    - scripts/check_backend_isolation.py (clause 3 invokes via subprocess)
  </read_first>
  <behavior>
    - Each clause test passes/fails INDEPENDENTLY so a partial Phase 6 regression localizes immediately.
    - Tests use direct subprocess invocations (`pytest`, `grep`, `python scripts/check_backend_isolation.py`) where appropriate; otherwise they import from `automil` and assert.
    - All 11 tests pass on a fully-shipped Phase 6.
  </behavior>
  <action>
Create `tests/backends/test_phase6_acceptance.py`:

```python
"""Phase 6 D-179 acceptance gate — single load-bearing test file (BCK-05 + BCK-06).

Each test maps to exactly one of the 11 clauses in D-179. Failing ANY clause
fails Phase 6. This is the same load-bearing pattern as Phase 5's
test_pitfall6_held_out_isolation.py.

Run as the final gate:
    uv run pytest tests/backends/test_phase6_acceptance.py -v
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# Repo root resolution: this file lives at tests/backends/test_phase6_acceptance.py
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC_AUTOMIL = _REPO_ROOT / "src" / "automil"
_SCRIPTS = _REPO_ROOT / "scripts"


# ---------------------------------------------------------------------------
# Clause 1 — Contract test parametrised over 4 backends, ≥10 scenarios per backend
# ---------------------------------------------------------------------------

def test_d179_clause_01_contract_parametrised_over_4_backends():
    """D-179 #1: tests/backends/test_contract.py passes parametrised over [local, mock_slurm, slurm, ray]."""
    # Collect-only sanity: confirm all 4 backends appear in parametrisation IDs.
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/backends/test_contract.py", "--collect-only", "-q"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    text = out.stdout + out.stderr
    for backend in ("[local]", "[mock_slurm]", "[slurm]", "[ray]"):
        assert backend in text, f"contract test missing parametrisation {backend}; output: {text[:500]}"


# ---------------------------------------------------------------------------
# Clause 2 — Phase 5 baseline (779 tests + 9 skipped) preserved
# ---------------------------------------------------------------------------

def test_d179_clause_02_phase5_baseline_preserved():
    """D-179 #2: Phase 5's 779-test baseline stays green (Phase 6 additive)."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    # parse "N tests collected" line
    text = (out.stdout + out.stderr).strip()
    # find the 'collected' line
    collected = 0
    for line in text.splitlines():
        if "collected" in line and "test" in line:
            for tok in line.split():
                if tok.isdigit():
                    collected = max(collected, int(tok))
    assert collected >= 789, (
        f"expected ≥789 collected tests (779 baseline + ≥10 Phase 6 additions); got {collected}"
    )


# ---------------------------------------------------------------------------
# Clause 3 — BCK-04 lint clean
# ---------------------------------------------------------------------------

def test_d179_clause_03_bck04_lint_clean():
    """D-179 #3: scripts/check_backend_isolation.py exits 0; slurm.py + ray.py NOT in allowlist."""
    out = subprocess.run(
        [sys.executable, str(_SCRIPTS / "check_backend_isolation.py"), str(_SRC_AUTOMIL)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, f"BCK-04 lint failed: {out.stdout}\n{out.stderr}"
    # Verify slurm.py and ray.py are NOT in the allowlist (read the script source).
    isolation_src = (_SCRIPTS / "check_backend_isolation.py").read_text()
    assert 'Path("backends/slurm.py")' not in isolation_src, "slurm.py must NOT be added to allowlist"
    assert 'Path("backends/ray.py")' not in isolation_src, "ray.py must NOT be added to allowlist"


# ---------------------------------------------------------------------------
# Clause 4 — pip install -e . (no extras) installs cleanly
# ---------------------------------------------------------------------------

def test_d179_clause_04_no_extras_install_works():
    """D-179 #4: import automil works without submitit/ray; automil --help succeeds.

    Verified by: (a) importing automil succeeds in the current process (which
    represents the no-extras install if extras absent), (b) `automil --help`
    runs without error, (c) `import automil.backends.slurm` is gated by the
    extras (raises ImportError if submitit absent).
    """
    import automil  # must succeed
    import automil.backends  # must succeed

    out = subprocess.run(
        [sys.executable, "-m", "automil", "--help"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0, f"automil --help failed: {out.stderr}"


# ---------------------------------------------------------------------------
# Clause 5 — [slurm] extra enables SLURMBackend
# ---------------------------------------------------------------------------

def test_d179_clause_05_slurm_extra_enables_backend():
    """D-179 #5: pip install -e '.[slurm]' makes import automil.backends.slurm work."""
    pytest.importorskip("submitit")
    from automil.backends.slurm import SLURMBackend  # must succeed
    from automil.backends import BACKENDS
    assert BACKENDS.get("slurm") is SLURMBackend, "SLURMBackend not registered as 'slurm'"


# ---------------------------------------------------------------------------
# Clause 6 — [ray] extra enables RayBackend
# ---------------------------------------------------------------------------

def test_d179_clause_06_ray_extra_enables_backend():
    """D-179 #6: pip install -e '.[ray]' makes import automil.backends.ray work."""
    pytest.importorskip("ray")
    from automil.backends.ray import RayBackend  # must succeed
    from automil.backends import BACKENDS
    assert BACKENDS.get("ray") is RayBackend, "RayBackend not registered as 'ray'"


# ---------------------------------------------------------------------------
# Clause 7 — node_0176-equivalent smoke passes across CI-runnable backends
# ---------------------------------------------------------------------------

def test_d179_clause_07_node_0176_smoke_passes():
    """D-179 #7: tests/backends/test_node_0176_smoke.py passes for [local, slurm-debug, ray-local]."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/backends/test_node_0176_smoke.py", "-v"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    text = out.stdout + out.stderr
    # We accept SKIPPED for slurm-debug or ray-local when extras absent; we require
    # PASSED for [local] always; we require NOT FAILED for any param.
    assert "FAILED" not in text, f"node_0176 smoke had failures:\n{text}"
    assert "[local]" in text and ("PASSED" in text or "passed" in text), (
        f"node_0176 smoke [local] did not pass:\n{text[-2000:]}"
    )


# ---------------------------------------------------------------------------
# Clause 8 — running/ namespaced; flat detection guardrail fires
# ---------------------------------------------------------------------------

def test_d179_clause_08_running_namespaced():
    """D-179 #8: running/ is namespaced; daemon refuses to start with flat *.json."""
    # Delegate to the Wave-0 stubs (they exercise the guardrail directly).
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/backends/test_running_namespace.py", "-v"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert out.returncode == 0, f"namespace tests failed: {out.stdout}\n{out.stderr}"


# ---------------------------------------------------------------------------
# Clause 9 — archive/<id>/run.log orchestrator-owned via _atomic_write_lines
# ---------------------------------------------------------------------------

def test_d179_clause_09_archive_run_log_orchestrator_owned():
    """D-179 #9: archive/<id>/run.log exists for terminal nodes; via _atomic_write_lines."""
    from automil.backends._orchestrator_daemon import _atomic_write_lines, _drain_log_iter_with_timeout
    # Both helpers must be defined at module scope.
    assert callable(_atomic_write_lines)
    assert callable(_drain_log_iter_with_timeout)
    # The Wave-0 stubs verify the actual drain behavior; rerun them as part of the gate.
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/backends/test_log_unification.py", "-v"],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert "FAILED" not in (out.stdout + out.stderr), (
        f"log_unification tests had failures: {out.stdout}\n{out.stderr}"
    )


# ---------------------------------------------------------------------------
# Clause 10 — Framework purity: zero autobench refs in src/automil/backends/
# ---------------------------------------------------------------------------

def test_d179_clause_10_framework_purity():
    """D-179 #10: grep -r 'autobench|AUTOBENCH_|benchmarks/' src/automil/backends/ returns 0."""
    backends_dir = _SRC_AUTOMIL / "backends"
    out = subprocess.run(
        ["grep", "-rn", "-E", "autobench|AUTOBENCH_|benchmarks/", str(backends_dir)],
        capture_output=True, text=True,
    )
    # grep returns 1 when no matches, 0 when matches found.
    assert out.returncode != 0 or out.stdout.strip() == "", (
        f"framework purity violated; src/automil/backends/ contains autobench refs:\n{out.stdout}"
    )


# ---------------------------------------------------------------------------
# Clause 11 — CHANGELOG.md 6.0.0 BREAKING entry present
# ---------------------------------------------------------------------------

def test_d179_clause_11_changelog_breaking_entry():
    """D-179 #11: CHANGELOG.md surfaces BREAKING running/ namespace change with recovery steps."""
    changelog = _REPO_ROOT / "CHANGELOG.md"
    assert changelog.exists(), "CHANGELOG.md missing at repo root"
    text = changelog.read_text()
    assert "## 6.0.0" in text, "CHANGELOG.md missing ## 6.0.0 heading"
    assert "BREAKING" in text, "CHANGELOG.md missing BREAKING marker"
    assert "automil orchestrator stop" in text, (
        "CHANGELOG.md must include the operator drain command"
    )
    assert "running/" in text or "namespacing" in text.lower(), (
        "CHANGELOG.md must explain the running/ namespacing change"
    )
```

This file is the single command Leo runs to confirm Phase 6 is complete. Each clause failure is independent so partial regressions are diagnosable. Subsequent maintenance changes that break any D-179 clause will fail this test.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_phase6_acceptance.py -v 2>&1 | tail -30</automated>
  </verify>
  <done>
    `tests/backends/test_phase6_acceptance.py` exists with exactly 11 test functions, one per D-179 clause. Each test passes when its clause is satisfied. Tests for clauses 5, 6, 7 (slurm-debug, ray-local) skip cleanly when extras absent — they don't false-fail on a no-extras dev machine. The full test file's pass/skip mix on this machine reflects what Leo's environment supports.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Final CHANGELOG.md touch-up — add summary at top + acceptance verification line</name>
  <files>CHANGELOG.md</files>
  <read_first>
    - CHANGELOG.md (created by plan 06-06)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-179 — to phrase the verification line)
  </read_first>
  <action>
Locate the existing `## 6.0.0` heading and insert a new "Verification" subsection RIGHT BEFORE the "Compatibility" subsection. Add:

```markdown
### Verification

Phase 6 is complete when `uv run pytest tests/backends/test_phase6_acceptance.py -v`
reports all 11 D-179 clauses passing (or skipping cleanly when [slurm]/[ray]
extras absent). Each test maps to exactly one clause; partial failures localize
which clause regressed.
```

Do NOT add a release date — this remains "(unreleased)" until Leo cuts a tag. Do NOT modify any other section of CHANGELOG.md.
  </action>
  <verify>
    <automated>grep -E "^### Verification$" CHANGELOG.md && grep -E "test_phase6_acceptance" CHANGELOG.md</automated>
  </verify>
  <done>
    CHANGELOG.md `## 6.0.0` block contains a `### Verification` subsection between `### Added` and `### Compatibility` referencing `test_phase6_acceptance.py` and the 11 D-179 clauses.
  </done>
</task>

</tasks>

<verification>

```bash
# All 11 D-179 clauses pass
uv run pytest tests/backends/test_phase6_acceptance.py -v

# Full suite green
uv run pytest tests/ -x -q

# CHANGELOG verification entry
grep -A3 "### Verification" CHANGELOG.md
```

</verification>

<success_criteria>

- [ ] `tests/backends/test_phase6_acceptance.py` exists with exactly 11 test functions named `test_d179_clause_NN_*`.
- [ ] All 11 clauses pass on a properly-shipped Phase 6 (or skip cleanly for clauses 5-7 when extras absent).
- [ ] `CHANGELOG.md` `## 6.0.0` has a `### Verification` subsection.
- [ ] D-179 acceptance gate for Phase 6: this single test file is the proof.
- [ ] Phase 5 baseline preserved + Phase 6 additions present; total ≥789 collected tests.
- [ ] `python scripts/check_backend_isolation.py src/automil/` exits 0.
- [ ] `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/` returns 0.

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-10-SUMMARY.md` describing: 11 clause results (PASSED/SKIPPED breakdown for the dev-machine run), final test count, CHANGELOG status. This SUMMARY is the Phase 6 sign-off; ROADMAP can flip Phase 6 to `[x]` after this plan ships green.
</output>
