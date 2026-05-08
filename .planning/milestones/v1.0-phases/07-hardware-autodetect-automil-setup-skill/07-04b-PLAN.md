---
phase: 07-hardware-autodetect-automil-setup-skill
plan: 04b
type: execute
wave: 3
depends_on: [07-01, 07-03, 07-04]
files_modified:
  - tests/backends/test_contract.py
autonomous: true
requirements: [STP-01]

must_haves:
  truths:
    - "tests/backends/test_contract.py is extended with a parametrised `test_healthcheck_returns_health_report(backend)` case covering all four BCK-01 backends."
    - "For LocalBackend the test asserts `isinstance(report, HealthReport)` and that the dataclass fields match the D-189 frozen-shape contract."
    - "For MockSLURMBackend / SLURMBackend / RayBackend the test asserts `pytest.raises(NotImplementedError, match=<locked D-189 message>)`."
    - "Phase 6 contract suite continues to pass: the BCK-01 scenarios S-01..S-12 are unchanged; only one new parametrised case is appended."
  artifacts:
    - path: tests/backends/test_contract.py
      provides: "Parametrised healthcheck contract case (PATTERNS.md §365-369; F-05 fix)"
      contains: "def test_healthcheck_returns_health_report"
  key_links:
    - from: tests/backends/test_contract.py
      to: src/automil/backends/base.py
      via: imports HealthReport and asserts the parametrised contract
      pattern: "HealthReport"
    - from: tests/backends/test_contract.py
      to: src/automil/backends/local.py
      via: indirectly through the parametrised `backend` fixture's local branch
      pattern: "LocalBackend"
---

<objective>
F-05 fix: PATTERNS.md §"tests/backends/test_contract.py (extend)" prescribes a parametrised
`test_healthcheck_returns_health_report(backend)` case that covers all four BCK-01 backends in
ONE test (matching the Phase 6 S-01..S-12 pattern). The original Phase 7 plan set shipped two
separate test files (`test_local_healthcheck.py` for LocalBackend in 07-03; `test_distributed_healthcheck_deferred.py`
for SLURM/Ray/MockSLURM in 07-04) but never extended `test_contract.py` itself. This plan closes
that gap with a single small task.

Purpose: PATTERNS.md is the contract from research to plan; deviating from it without explicit
rationale weakens the verification chain. Phase 6 used the parametrised contract test as the
BCK-01 cornerstone; Phase 7's healthcheck must get the same treatment so the parametrised
suite remains the single source of truth for "every backend honours the BCK-01 contract."

Output: 1 file modified (`tests/backends/test_contract.py`), 1 new test function (parametrised
across 4 backends, so 4 test cases collected, of which 2 SKIP cleanly when `[slurm]` / `[ray]`
extras are absent).

Wave 3 placement, file-disjoint from 07-04: 07-04 modifies `slurm.py`, `ray.py`,
`mock_slurm.py`, and `tests/backends/test_distributed_healthcheck_deferred.py`. 07-04b
modifies ONLY `tests/backends/test_contract.py`. Zero `files_modified` overlap; both plans
can run in the same wave once 07-01 and 07-03 are green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/07-hardware-autodetect-automil-setup-skill/07-CONTEXT.md
@.planning/phases/07-hardware-autodetect-automil-setup-skill/07-RESEARCH.md
@.planning/phases/07-hardware-autodetect-automil-setup-skill/07-PATTERNS.md
@CLAUDE.md

@tests/backends/test_contract.py
@tests/backends/conftest.py
@src/automil/backends/base.py
@src/automil/backends/local.py

<interfaces>
<!-- The parametrised `backend` fixture in tests/backends/conftest.py yields
     LocalBackend / MockSLURMBackend / SLURMBackend / RayBackend across four
     parameter values: "local", "mock_slurm", "slurm", "ray". The slurm and
     ray branches use pytest.importorskip so missing extras skip cleanly. -->

Locked D-189 NotImplementedError message (byte-identical match expected; both 07-04 source
edits and the assertion below use this string):

```
healthcheck deferred to Phase 7+ for distributed backends (use `salloc`/`ray status` directly)
```

For the regex `match=` argument we use only the prefix `healthcheck deferred to Phase 7\+ for distributed backends`
to avoid backtick escaping in the pattern. The full byte-identical check is performed by 07-04's
dedicated `test_distributed_healthcheck_deferred.py`; 07-04b's contract test only asserts that
the prefix is present in the raised message.

LocalBackend healthcheck contract (D-189, returned dataclass):
- `gpu_count: int`
- `gpu_vram_gb: tuple[float, ...]`
- `accelerator: Literal["cuda","rocm","cpu"]`
- `python_version: str`
- `automil_version: str`
- `detection_status: Literal["ok","partial","failed"]`
- `detection_warnings: tuple[str, ...]`
- `detected_at: str` (ISO-8601 datetime)

LocalBackend.healthcheck() must NOT raise on a CPU-only host (the conftest fixture provides no
real GPU); it returns a HealthReport with `accelerator="cpu"`, `gpu_count=0`, and
`detection_status` in `{"ok","failed"}` depending on whether `nvidia-smi`/`rocm-smi` are absent
on PATH (fail-clean per D-190 Pitfall A).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend tests/backends/test_contract.py with parametrised healthcheck contract</name>
  <files>tests/backends/test_contract.py</files>
  <read_first>
    - tests/backends/test_contract.py (full file; understand the parametrised pattern at S-01..S-12 and the Phase 6 BCK-05/BCK-06 specific tests at the bottom)
    - tests/backends/conftest.py (the `backend` fixture's 4-branch dispatch + isolated_backends autouse)
    - tests/backends/test_local_healthcheck.py (post 07-03; mirror its assertion shape for the LocalBackend branch)
    - tests/backends/test_distributed_healthcheck_deferred.py (post 07-04; mirror the locked-message regex)
    - .planning/phases/07-hardware-autodetect-automil-setup-skill/07-CONTEXT.md (D-189 message verbatim)
    - .planning/phases/07-hardware-autodetect-automil-setup-skill/07-PATTERNS.md (lines 365-369: the prescription)
  </read_first>
  <action>
**Append** a new parametrised contract test to `tests/backends/test_contract.py`. Place it AFTER the existing `S-extra: poll unknown handle raises BackendError` block (so the file's chronological logical order is S-01..S-12 + S-extra + Phase 6 unit tests + Phase 6 BCK-05/06 + Phase 7 healthcheck). Add the import for `HealthReport` to the existing import block at the top of the file (currently `from automil.backends.base import JobHandle, JobState`):

```python
from automil.backends.base import HealthReport, JobHandle, JobState
```

Then append this section (use the same `# ---` comment-bar style the file already uses):

```python
# ---------------------------------------------------------------------------
# Phase 7 BCK-01: Backend.healthcheck contract (D-189 / STP-01)
# ---------------------------------------------------------------------------
# F-05 fix: PATTERNS.md prescribes a parametrised healthcheck contract case in
# this file (mirroring S-01..S-12). LocalBackend returns a HealthReport;
# distributed backends raise NotImplementedError with the locked D-189 message.


def test_healthcheck_returns_health_report(backend):
    """D-189 / STP-01: LocalBackend returns HealthReport; distributed backends defer.

    Parametrised across all 4 BCK-01 backends via the conftest `backend` fixture:
      - LocalBackend: returns HealthReport with frozen-dataclass fields per D-189.
      - MockSLURMBackend / SLURMBackend / RayBackend: raise NotImplementedError
        with the D-189 locked message.
    """
    locked_prefix = r"healthcheck deferred to Phase 7\+ for distributed backends"

    if isinstance(backend, LocalBackend):
        report = backend.healthcheck()
        assert isinstance(report, HealthReport), (
            f"LocalBackend.healthcheck() must return HealthReport; got {type(report).__name__}"
        )
        # Frozen-dataclass field shape per D-189 (must match the ABC contract).
        expected_fields = {
            "gpu_count", "gpu_vram_gb", "accelerator", "python_version",
            "automil_version", "detection_status", "detection_warnings", "detected_at",
        }
        assert set(report.__dataclass_fields__) == expected_fields, (
            f"HealthReport field shape drift: {set(report.__dataclass_fields__)} "
            f"vs expected {expected_fields}"
        )
        # Reasonableness on a fixture host (no real GPU; nvidia-smi may be absent).
        assert report.accelerator in {"cuda", "rocm", "cpu"}
        assert report.detection_status in {"ok", "partial", "failed"}
        assert isinstance(report.gpu_vram_gb, tuple)
        assert isinstance(report.detection_warnings, tuple)
        return

    # Distributed branch: SLURMBackend, RayBackend, or MockSLURMBackend.
    with pytest.raises(NotImplementedError, match=locked_prefix):
        backend.healthcheck()
```

**Critical, the `LocalBackend` import.** It is already imported at the top of the file
(`from automil.backends.local import LocalBackend`); do NOT duplicate the import. Verify with
`grep -c "from automil.backends.local import LocalBackend" tests/backends/test_contract.py`
and assert exactly `1` after the edit.

**Critical, no new em-dashes / autobench / hardcoded paths.** Run the standard greps:

```bash
grep -nP "\x{2014}|\x{2013}" tests/backends/test_contract.py
grep -nE "autobench|AUTOBENCH_|benchmarks/" tests/backends/test_contract.py
```

The first command may return matches in pre-existing text (Phase 6 era); the count must be
unchanged from the pre-edit baseline. The second command must return zero matches (the file
was framework-pure before; this edit must keep it so).

**Critical, the `backend` fixture's slurm + ray branches use `pytest.importorskip`.** When
`[slurm]` extra is missing, the slurm parametrisation case SKIPS cleanly; same for `[ray]`.
The MockSLURMBackend and LocalBackend cases always run. So this single test function expands
to 4 collected cases, of which at least 2 always run (Local + MockSLURM) and 2 may skip
(SLURM + Ray) on a host without the extras.

**Critical, message-prefix regex.** The full D-189 message contains backticks:
`(use \`salloc\`/\`ray status\` directly)`. Backticks are NOT regex metacharacters; the issue
is escaping them as Python string literals would force \\` sequences. Using only the prefix
`healthcheck deferred to Phase 7\+ for distributed backends` keeps the regex clean and still
gives a precise enough match (07-04's dedicated test asserts the full byte-identical message).
The `\+` escapes the literal `+` in `Phase 7+`.

**Critical, BCK-04 lint.** This is a test file under tests/backends/, NOT in src/automil/backends/.
The Phase 6 D-179 BCK-04 lint applies only to src/automil/backends/ files; this edit is on the
test side and adds zero process-control references.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_contract.py::test_healthcheck_returns_health_report -v 2>&1 | tail -10</automated>
  </verify>
  <done>
    `uv run pytest tests/backends/test_contract.py::test_healthcheck_returns_health_report -v` reports 4 collected cases:
    - `test_healthcheck_returns_health_report[local]` PASSED
    - `test_healthcheck_returns_health_report[mock_slurm]` PASSED
    - `test_healthcheck_returns_health_report[slurm]` PASSED (or SKIPPED if `[slurm]` absent)
    - `test_healthcheck_returns_health_report[ray]` PASSED (or SKIPPED if `[ray]` absent)
    Phase 6 S-01..S-12 + S-extra + BCK-05/06 cases are unchanged. `grep -c "test_healthcheck_returns_health_report" tests/backends/test_contract.py` returns at least `1`. Em-dash count in the file is unchanged from pre-edit. Zero new autobench/AUTOBENCH_/benchmarks/ refs.
  </done>
</task>

</tasks>

<verification>

```bash
# New parametrised contract test passes (or skips cleanly on missing extras)
uv run pytest tests/backends/test_contract.py::test_healthcheck_returns_health_report -v

# Phase 6 contract suite still green (no regressions on S-01..S-12)
uv run pytest tests/backends/test_contract.py -x -q 2>&1 | tail -2

# Em-dash + autobench gate
grep -nP "\x{2014}|\x{2013}" tests/backends/test_contract.py
grep -nE "autobench|AUTOBENCH_|benchmarks/" tests/backends/test_contract.py

# HealthReport import added exactly once
grep -c "HealthReport" tests/backends/test_contract.py
```

</verification>

<success_criteria>

- [ ] `tests/backends/test_contract.py` has a new `test_healthcheck_returns_health_report(backend)` function placed AFTER the existing parametrised cases.
- [ ] All 4 parametrised cases either PASS or SKIP cleanly via `pytest.importorskip` (slurm + ray cases skip when extras absent).
- [ ] `LocalBackend` branch asserts `isinstance(report, HealthReport)` and the frozen-dataclass field shape.
- [ ] Distributed branches assert `pytest.raises(NotImplementedError, match=<D-189 prefix>)`.
- [ ] Phase 6 S-01..S-12 + S-extra + BCK-05/BCK-06 cases continue to pass.
- [ ] No new em-dashes, no autobench/AUTOBENCH_/benchmarks/ refs in the file.
- [ ] `HealthReport` imported alongside the existing `JobHandle, JobState` import (single line edit, no duplicate import).

</success_criteria>

<output>
After completion, create `.planning/phases/07-hardware-autodetect-automil-setup-skill/07-04b-SUMMARY.md` describing: the 4 parametrised case results (Local PASS, MockSLURM PASS, SLURM PASS or SKIP, Ray PASS or SKIP), confirmation that Phase 6 contract suite is unchanged, and the post-edit collection delta (+4 cases collected, of which 2 always run).
</output>
