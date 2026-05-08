---
phase: 00-tier-2-cleanup-cli-split-compat-shim
plan: 03
subsystem: orchestrator/cli
tags: [CLN-05, security, subprocess, path-pinning, shutil.which]
requires:
  - 00-01-PLAN  # cli/ package structure (cli/check.py target)
provides:
  - automil.orchestrator.NVIDIA_SMI_PATH  # module-level constant
  - automil check reports nvidia-smi path
affects:
  - src/automil/orchestrator.py  # query_gpus uses NVIDIA_SMI_PATH
  - src/automil/cli/check.py     # imports + reports NVIDIA_SMI_PATH
tech_stack:
  added: []
  patterns: [module-level shutil.which path resolution, defensive subprocess argv pinning]
key_files:
  created:
    - tests/test_orchestrator_nvidia_smi.py
  modified:
    - src/automil/orchestrator.py
    - src/automil/cli/check.py
decisions:
  - D-18 enacted: shutil.which("nvidia-smi") resolved once at import; INFO on success, WARN on fallback, never raises.
  - Constant is exposed at column-0 (NVIDIA_SMI_PATH = _resolved or "nvidia-smi") so the verification regex `^NVIDIA_SMI_PATH\s*=` matches.
  - `automil check`'s GPU-count probe (cli/check.py:65 — bare "nvidia-smi") was left unchanged. It is its own diagnostic on a different code path, not the orchestrator's bin-packer signal source. The plan scoped CLN-05 to `query_gpus`; the check probe is OUT OF SCOPE for this commit and a Rule 4 architectural decision if revisited (deferred).
metrics:
  duration_sec: 169
  duration_min: 2
  completed: "2026-05-01T14:06:08Z"
  tests_added: 4
  tests_total: 76
commits:
  - hash: 30131b4
    type: test
    message: "test(00-03): add failing tests for nvidia-smi path pinning (CLN-05)"
  - hash: 0ed0111
    type: fix
    message: "fix(orchestrator): pin nvidia-smi path with shutil.which (CLN-05)"
---

# Phase 0 Plan 03: Pin nvidia-smi to absolute path Summary

Defends the orchestrator's GPU-saturation invariant against PATH-shim spoofing on shared hosts. `query_gpus` now invokes the absolute path resolved by `shutil.which("nvidia-smi")` at module import; if detection fails, it WARNs and falls back to bare PATH lookup so the orchestrator stays operable. `automil check` surfaces whichever path is in use so operators can see whether path pinning is in effect.

## Objective Recap

Replace the bare `"nvidia-smi"` argv[0] in `query_gpus` (`orchestrator.py:101-111`) with a module-level `NVIDIA_SMI_PATH` constant resolved once via `shutil.which` (D-18), and surface the resolved path through `automil check` so operators can detect spoofing risk without reading the orchestrator log.

## Implementation

### `src/automil/orchestrator.py`

Stdlib import group: added `import shutil` between `shlex` and `signal`.

Module-level pin block (immediately after `logger = logging.getLogger(__name__)`):

```python
# ---------------------------------------------------------------------------
# nvidia-smi path pinning (CLN-05)
# ---------------------------------------------------------------------------
# Resolve nvidia-smi's absolute path once at module import. On a shared host a
# PATH-shim could otherwise return spoofed VRAM numbers and trick the
# bin-packer (CONCERNS.md §"nvidia-smi invocation has no path pinning"). If
# detection fails we fall back to bare PATH lookup with a WARN — never silent
# (D-18). Resolution happens here (module-level), not on every query_gpus
# call, so the cost is paid once and tests can re-resolve via importlib.reload.
_resolved_nvidia_smi = shutil.which("nvidia-smi")
NVIDIA_SMI_PATH = _resolved_nvidia_smi or "nvidia-smi"
if _resolved_nvidia_smi:
    logger.info("nvidia-smi resolved to %s", NVIDIA_SMI_PATH)
else:
    logger.warning(
        "nvidia-smi not found via shutil.which; falling back to bare PATH lookup. "
        "GPU state may be unreliable on hosts with shimmed PATH."
    )
```

`query_gpus` body (only argv[0] changes; rest is byte-identical):

```python
def query_gpus() -> list[GPUInfo]:
    """Query nvidia-smi for GPU state.

    Uses the path resolved at module import (NVIDIA_SMI_PATH) to defend
    against PATH-shim spoofing on shared hosts (CLN-05).
    """
    try:
        result = subprocess.run(
            [
                NVIDIA_SMI_PATH,
                "--query-gpu=index,memory.total,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        ...  # rest unchanged
```

### `src/automil/cli/check.py`

Net-new report block, appended after the orchestrator-directory check, before the issues/warnings summary:

```python
# CLN-05: report the resolved nvidia-smi path so operators can see whether
# path pinning is in effect (D-18). The constant is set at orchestrator.py
# module import via shutil.which('nvidia-smi') — see Plan 03.
from automil.orchestrator import NVIDIA_SMI_PATH

if NVIDIA_SMI_PATH != "nvidia-smi":
    click.echo(f"nvidia-smi: {NVIDIA_SMI_PATH}")
else:
    click.echo("nvidia-smi: bare PATH lookup (path detection failed)")
```

Placement note: the report is emitted before the ISSUES/WARNINGS summary so the `nvidia-smi:` line stays visually grouped with `GPUs detected:` (the existing GPU diagnostic on line 72), keeping all GPU-related diagnostics adjacent in the operator's mental model.

### Live `automil check` output (Leo's workstation)

```
GPUs detected: 3
nvidia-smi: /usr/bin/nvidia-smi

ISSUES (must fix):
  1. Training script 'train.py' not found at /tmp/nvidia_smi_check_test/train.py

WARNINGS:
  1. files.editable is empty. Auto-detect will capture ALL changed files.
  2. baseline.composite is 0. Set this after running your first experiment.

1 issue(s) must be fixed before running.
```

Resolved path on Leo's workstation at the time of commit:

```
$ which nvidia-smi
/usr/bin/nvidia-smi
```

### `tests/test_orchestrator_nvidia_smi.py` (4 tests, ~110 lines)

| Test | Behaviour | Mechanism |
|------|-----------|-----------|
| `test_path_resolved` | `shutil.which → "/usr/bin/nvidia-smi"` ⇒ `NVIDIA_SMI_PATH == "/usr/bin/nvidia-smi"` | `monkeypatch.setattr(shutil, "which", ...)` + `importlib.reload(orch_mod)` |
| `test_path_missing_fallback_warns` | `shutil.which → None` ⇒ `NVIDIA_SMI_PATH == "nvidia-smi"` AND a WARN log mentioning `nvidia-smi` and `PATH` is emitted at module-import time | `caplog.at_level(WARNING, logger="automil.orchestrator")` |
| `test_subprocess_uses_pinned_path` | `subprocess.run` is invoked with `NVIDIA_SMI_PATH` as argv[0] | `monkeypatch.setattr(subprocess, "run", fake_run)` capturing `argv[0]` |
| `test_check_reports_nvidia_smi_path` | `automil check` stdout contains `"nvidia-smi:"` | `CliRunner` invocation against minimal scaffolded project |

Each test uses an autouse `_restore_orchestrator_module` fixture that reloads `automil.orchestrator` after every test so the module's `NVIDIA_SMI_PATH` stays clean across runs.

## Verification

| Check | Result |
|-------|--------|
| `grep -E "shutil\.which\(['\"]nvidia-smi['\"]\)" src/automil/orchestrator.py` | matches |
| `grep -E "^NVIDIA_SMI_PATH\s*=" src/automil/orchestrator.py` | matches |
| `grep -q "NVIDIA_SMI_PATH" src/automil/cli/check.py` | matches |
| `automil check` programmatic invocation | emits `nvidia-smi: /usr/bin/nvidia-smi` |
| `uv run pytest tests/` | **76 passed** (72 baseline + 4 new) |
| Final-commit message | `fix(orchestrator): pin nvidia-smi path with shutil.which (CLN-05)` |
| TDD gate sequence | RED commit `30131b4` precedes GREEN commit `0ed0111` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Plan literal code vs. plan verification regex were inconsistent**

- **Found during:** Task 1 GREEN step, after first run of the verification grep.
- **Issue:** The plan's literal Step 2 code wrote `NVIDIA_SMI_PATH = …` *inside* an `if/else` block (indented), while the plan's `<verification>` section requires `grep -E "^NVIDIA_SMI_PATH\s*="` (anchored at column 0). The two are mutually exclusive — the regex cannot match indented assignment.
- **Fix:** Restructured the resolution block as a single column-0 assignment using a short-circuit `or`:

  ```python
  _resolved_nvidia_smi = shutil.which("nvidia-smi")
  NVIDIA_SMI_PATH = _resolved_nvidia_smi or "nvidia-smi"
  if _resolved_nvidia_smi:
      logger.info(...)
  else:
      logger.warning(...)
  ```

  Logging behaviour is identical to the plan's literal code. The contract is unchanged: WARN on fallback, INFO on success, never raises.
- **Files modified:** `src/automil/orchestrator.py`
- **Commit:** `0ed0111`

### Out-of-scope items (deferred, NOT fixed)

**`cli/check.py:65` still calls bare `"nvidia-smi"` for the GPU-count probe.** This is a separate code path from `query_gpus` and a separate diagnostic. The plan scoped CLN-05 to `query_gpus` (the bin-packer signal source). Pinning the check probe too would be reasonable but is outside this plan's blast radius — captured here for backlog. Operators reading `GPUs detected: N` followed by `nvidia-smi: /usr/bin/nvidia-smi` will see whether the path is reliable; if `nvidia-smi:` reports the fallback line, the operator already knows the GPU count came from a non-pinned binary.

## Threat Flags

None. The plan's `T-00-05` threat (mitigate disposition) is now closed: `query_gpus` invokes the absolute path resolved at import; bin-packer signal is no longer trivially spoofable by `$PATH` ordering. No new surface introduced.

## TDD Gate Compliance

- RED commit: `30131b4` — `test(00-03): add failing tests for nvidia-smi path pinning (CLN-05)` — all 4 tests fail.
- GREEN commit: `0ed0111` — `fix(orchestrator): pin nvidia-smi path with shutil.which (CLN-05)` — all 4 tests pass; 76/76 total.
- REFACTOR: not performed; the GREEN code is already minimal/elegant (no shape to clean up beyond what was committed).

## Self-Check: PASSED

- `tests/test_orchestrator_nvidia_smi.py` exists (verified via `Read` after Write; 4 tests run and pass).
- `src/automil/orchestrator.py` modifications present (verified via grep on `shutil.which`, `NVIDIA_SMI_PATH`).
- `src/automil/cli/check.py` modifications present (verified via grep on `NVIDIA_SMI_PATH`).
- Commit `30131b4` exists in `git log`.
- Commit `0ed0111` exists in `git log`.
- 76 tests passing.
