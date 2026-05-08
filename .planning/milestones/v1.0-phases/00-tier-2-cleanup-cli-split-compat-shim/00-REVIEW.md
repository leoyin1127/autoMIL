---
phase: 00-tier-2-cleanup-cli-split-compat-shim
reviewed: 2026-05-01T00:00:00Z
depth: deep
files_reviewed: 18
files_reviewed_list:
  - src/automil/orchestrator.py
  - src/automil/compat.py
  - src/automil/graph.py
  - src/automil/cli/__init__.py
  - src/automil/cli/_helpers.py
  - src/automil/cli/check.py
  - src/automil/cli/control.py
  - src/automil/cli/init.py
  - src/automil/cli/lifecycle.py
  - src/automil/cli/orchestrator.py
  - src/automil/cli/propose.py
  - src/automil/cli/reconcile.py
  - src/automil/cli/status.py
  - src/automil/cli/submit.py
  - src/automil/cli/viz.py
  - tests/test_compat.py
  - tests/test_orchestrator_dotenv.py
  - tests/test_orchestrator_env_whitelist.py
  - tests/test_orchestrator_nvidia_smi.py
  - tests/test_orchestrator_pid_starttime.py
  - tests/test_recompute_best.py
findings:
  critical: 0
  warning: 5
  info: 2
  total: 7
status: issues_found
---

# Phase 00: Code Review Report

**Reviewed:** 2026-05-01
**Depth:** deep
**Files Reviewed:** 18 source files + 6 test files (all 108 tests pass)
**Status:** issues_found

## Summary

Phase 0 delivers five targeted fixes (CLN-02 through CLN-07) plus the 725-line
`cli.py` decomposition into a `cli/` package. The env-whitelist implementation
is correct in its core contract: operator secrets (OPENAI_API_KEY, WANDB_API_KEY,
etc.) do not reach experiment subprocesses. The PID+starttime cross-check logic
is structurally sound. The dotenv replacement works correctly. The CLI split
introduces no import cycles and all 108 tests pass.

Five warnings are filed below. None block correctness in the nominal path; the
two most actionable ones (WR-01 and WR-02) affect operator-facing diagnostics
and a subtle spec-injection vector for orchestrator-owned env vars.

---

## Warnings

### WR-01: `check.py` GPU detection uses bare `"nvidia-smi"` — inconsistent with CLN-05 pin

**File:** `src/automil/cli/check.py:67`

**Issue:** The `automil check` GPU-count probe calls `["nvidia-smi", ...]` by bare
name, not via the `NVIDIA_SMI_PATH` constant that CLN-05 resolved at module import.
On a shimmed host this means `automil check` can report "GPUs detected: N" from the
shim's output while the orchestrator sees a completely different view — the diagnostic
intended to give operators confidence that scheduling will work cannot be trusted on
the exact hosts where CLN-05 is most needed. The `NVIDIA_SMI_PATH` constant is
already imported later in the same function (line 86), making this an oversight
rather than a design decision.

**Fix:**
```python
# Replace line 67 in check.py
from automil.orchestrator import NVIDIA_SMI_PATH
result = subprocess.run(
    [NVIDIA_SMI_PATH, "--query-gpu=index", "--format=csv,noheader"],
    capture_output=True, text=True, timeout=5,
)
```
Move the `from automil.orchestrator import NVIDIA_SMI_PATH` import to the top of
the `check()` function body (it is already done at line 86 for the display section;
just reuse it for the probe call too).

---

### WR-02: `cmd_status` reads `gpu_state_file` without JSON error handling — crashes operator diagnostic

**File:** `src/automil/orchestrator.py:1008`

**Issue:** `cmd_status` calls `json.loads(self.gpu_state_file.read_text())` with no
`try/except`. If `gpu_state.json` is truncated mid-write (e.g., the daemon was
killed during `_save_state`) or otherwise corrupt, the `status` command raises an
unhandled `json.JSONDecodeError` and prints a Python traceback instead of a clean
message. `_load_state` (line 413–417) correctly wraps the same file in a
`try/except`; `cmd_status` should too. The same guard is already applied to every
other JSON read in the codebase.

**Fix:**
```python
# orchestrator.py cmd_status, around line 1007
if self.gpu_state_file.exists():
    try:
        state = json.loads(self.gpu_state_file.read_text())
    except (json.JSONDecodeError, OSError):
        print("(gpu_state.json unreadable — daemon may be mid-write)")
        state = {}
    print(f"\nLast updated: {state.get('last_updated', 'unknown')}")
    # ... rest of display logic unchanged
```

---

### WR-03: `spec.env` can override orchestrator-injected keys not in `_SPEC_ENV_BLOCKED`

**File:** `src/automil/orchestrator.py:566-579`

**Issue:** `_SPEC_ENV_BLOCKED` is `{"AUTOMIL_GPU", "CUDA_VISIBLE_DEVICES"}` — only
two keys. The layering comment in `_build_subprocess_env` says step-4 is
"last-write-wins, except `_SPEC_ENV_BLOCKED`", but several orchestrator-injected
keys from step 3 are equally critical and are not blocked:

- `AUTOMIL_RESULTS_DIR` — tells training scripts where to write checkpoints;
  overriding it redirects per-fold artifacts to an attacker-chosen path.
- `AUTOBENCH_ROOT` — points to the worktree benchmarks; override would silently
  re-use the parent-env stale path, causing all AUTOBENCH library imports to
  resolve outside the worktree and bypassing any overlay changes.
- `PYTHONPATH` — overriding this redirects all Python imports in the experiment
  subprocess.

The `automil submit` command (the normal path) never writes `spec.env`, so this
is only triggerable via a manually crafted or externally injected spec file placed
in the queue directory. However, the stated security goal of CLN-02 is
"closing the exfiltration vector" — incomplete blocking is inconsistent with that goal.

**Fix:** Extend `_SPEC_ENV_BLOCKED` to protect all orchestrator-owned vars:
```python
_SPEC_ENV_BLOCKED: frozenset[str] = frozenset({
    "AUTOMIL_GPU",
    "CUDA_VISIBLE_DEVICES",
    "AUTOMIL_RESULTS_DIR",
    "AUTOMIL_NODE_ID",
    "AUTOBENCH_ROOT",
    "PYTHONPATH",
})
```

---

### WR-04: `init.py` hook command string does not quote path — breaks on project roots with spaces

**File:** `src/automil/cli/init.py:99`

**Issue:**
```python
hook_cmd = f"bash {project_root / '.claude' / 'hooks' / 'on_stop.sh'}"
```
This produces `"bash /path/with spaces/project/.claude/hooks/on_stop.sh"` when
the project root contains a space. The Claude settings runner interprets this as
`bash` invoked with two positional arguments (`/path/with` and `spaces/project/...`)
instead of a single quoted path. The hook silently fails to run — the
`.automil_active` flag is never cleared on agent stop.

**Fix:**
```python
hook_path = project_root / ".claude" / "hooks" / "on_stop.sh"
hook_cmd = f"bash {shlex.quote(str(hook_path))}"
```
(`shlex` is already available in the stdlib; add `import shlex` to the imports.)

---

### WR-05: `_write_pid_file` stores `starttime_ticks=0` fallback — makes the live-check silently inaccurate

**File:** `src/automil/orchestrator.py:163-175`

**Issue:** When `_read_proc_starttime(my_pid)` returns `None` (documented as a
"non-Linux test env" guard), `_write_pid_file` stores `starttime_ticks: 0` in the
PID file. On Linux, `/proc/self/stat` is always readable by the owning process, so
this path is only hit in test environments. However, if it were ever hit in
production (e.g., a container with `/proc` restrictions), subsequent `cmd_start`
and `cmd_stop` calls read the file, call
`_is_pid_alive_with_starttime(pid, 0)`, and compare against the real non-zero
ticks — the comparison fails and the live daemon is classified as dead. A second
daemon instance would start, leading to double-scheduling.

The fallback value `0` is indistinguishable from "no starttime" and should instead
cause `_is_pid_alive_with_starttime` to skip the starttime check rather than
return False. The function currently returns `False` when `actual is None`
(correct), but returns `actual == expected_starttime_ticks` when actual is 0 vs
recorded 0, which is the opposite bug — it would validate a reused PID whose
actual ticks happen to also be 0.

**Fix:** Replace the sentinel value:
```python
# _write_pid_file: use -1 as the "could not determine" sentinel
starttime = _read_proc_starttime(my_pid)
if starttime is None:
    starttime = -1  # /proc unavailable; cross-check disabled
```
Then in `_is_pid_alive_with_starttime`:
```python
def _is_pid_alive_with_starttime(pid: int, expected_starttime_ticks: int) -> bool:
    if expected_starttime_ticks == -1:
        # Starttime was unreadable at write time; fall back to existence check only.
        return _read_proc_starttime(pid) is not None
    actual = _read_proc_starttime(pid)
    if actual is None:
        return False
    return actual == expected_starttime_ticks
```

---

## Info

### IN-01: Redundant `import shutil` inside `_launch` — already imported at module top

**File:** `src/automil/orchestrator.py:679`

**Issue:** `shutil` is imported at module level (line 20) and then re-imported
inside `_launch` at line 679. The inner import is a no-op at runtime (Python
returns the cached module object) but it reads as if `shutil` is only needed
locally, which is misleading to future readers.

**Fix:** Remove line 679 (`import shutil`).

---

### IN-02: `reconcile --recompute-best` silently creates `graph.json` if the file is missing

**File:** `src/automil/cli/reconcile.py:43-65`

**Issue:** If `graph.json` does not exist, `ExperimentGraph.load(graph_path)` creates
an empty in-memory graph. When `--dry-run` is absent, `graph.save()` then writes
this empty graph to disk. The operator gets output "best_node_id unchanged: None
(composite 0.000000)" with no indication that the file was just created. Running
`automil reconcile --recompute-best` in a freshly-cloned project (before any
experiment data exists) would silently produce a confusingly minimal graph.json.

Note: the default (no-flag) `reconcile` path has identical behavior via
`ExperimentGraph(path=str(...))` at line 71. The issue predates Phase 0 but is
exposed here since `--recompute-best` is new.

**Fix:** Add an existence guard before loading:
```python
graph_path = adir / "graph.json"
if not graph_path.exists():
    raise click.ClickException(
        "graph.json not found. Run some experiments first."
    )
graph = ExperimentGraph.load(graph_path)
```

---

_Reviewed: 2026-05-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
