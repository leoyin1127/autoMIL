---
phase: 02
status: warn
reviewed_at: 2026-05-02
reviewer: gsd-code-reviewer (sonnet)
critical: 1
warnings: 2
info: 5
files_reviewed: 15
loc_reviewed: ~2400
---

# Phase 2 Code Review

## Verdict

Phase 2 delivers a well-structured Backend ABC with correct abstract method enforcement, a working BACKENDS registry, a thoroughly documented MockSLURMBackend, and passing cancel/resubmit CLI commands. The BCK-04 lint gate is sound. However, one **Critical** functional bug was found: `LocalBackend.submit()` discards `spec.overlay_dir` (the absolute path to the overlay files) and instead hardcodes `"archive/<spec.node_id>"` in the daemon queue spec. When `automil resubmit` calls `LocalBackend.submit` with `node_id=new_node_id` but `overlay_dir=archive/<old_node_id>/`, the daemon applies the overlay from the wrong (empty) directory — silently running the experiment on base-commit code with no variant files applied. Two additional Warnings involve the `orchestrator.py` shim firing spurious `DeprecationWarning`s for Python-internal dunder attributes (`__path__`, `__test__`, `__bases__`), and the use of the deprecated `datetime.utcfromtimestamp()` API (removal-scheduled in Python 3.12+).

---

## High-risk surface spot-checks

**1. Backend ABC contract correctness (`base.py`):** COVERED. All 5 methods carry `@abstractmethod`. `JobState(str, Enum)` has exactly 6 values, is JSON-serialisable (`json.dumps(JobState.RUNNING) == '"running"'`). `JobHandle` and `JobSpec` are `frozen=True` dataclasses with `tuple` (not `list`) sequence fields — hashable and JSON-serialisable. Method docstrings encode fire-and-forget cancel, snapshot poll, and eventual-consistency contracts. No issues found.

**2. Registry + decorator (`__init__.py`):** COVERED. `register()` checks `issubclass(cls, Backend)` and rejects duplicates with `BackendError`. `_clear_backends()` is prefixed with `_` and has a "Never call in production" docstring. `mock_slurm` is not auto-imported per D-69. Import order is safe: `BACKENDS` and `register` are defined before the `from automil.backends import local` at line 72. Verified empirically: `BACKENDS == {'local': LocalBackend}` on clean import.

**3. LocalBackend (`local.py`) — highest risk:** PARTIAL. The state machine (RUNNING > result.json > PENDING priority order) is correct. `cancel()` properly handles pending-job queue-file removal and delegates to `_daemon._kill_experiment()` (method verified to exist at `_orchestrator_daemon.py:810`). `log_iter()` terminates cleanly on terminal state. One Critical bug found: `submit()` ignores `spec.overlay_dir` and writes `"overlay_dir": f"archive/{spec.node_id}"` to the queue spec — the absolute path in `JobSpec.overlay_dir` is never used. See CR-01.

**4. MockSLURMBackend (`mock_slurm.py`):** COVERED. The deadlock fix is correctly in place: both `_transition()` and `_finish()` callbacks call `_persist_state()` **outside** the `with self._lock:` block (comments confirm this). All `threading.Timer` instances have `daemon=True`. State-file restart recovery degrades PENDING/RUNNING → CRASHED correctly. `cancel_requested` uses `threading.Event` (atomic set). One lockless read of `job.state` in `log_iter()` is technically a data race but safe under CPython's GIL for enum value reads — acceptable for a test fixture.

**5. CLI cancel/resubmit (`cancel.py`, `resubmit.py`):** COVERED. W-03 fix is correct: `cancel.py` reads `opaque_id` from `running/<node_id>.json` (not graph metadata). Hard-fail messages use "Refusing to <verb>: ..." format per PATTERNS.md §7. Graph mutations are atomic (mkstemp + os.replace). Cancel poll loop exits cleanly — the `final_state is None` case is handled via `"unknown"` sentinel. Cancel timeout error reports current state clearly. `resubmit.py` generates a new `node_id` and sets `metadata.resubmitted_from`. One Info item: `resubmit.py` uses `__import__("datetime")` inline rather than a top-level import.

**6. BCK-04 AST walker (`check_backend_isolation.py`):** COVERED. `ALLOWLIST_PATHS` uses `Path` objects with exact equality checks — immune to path normalisation attacks. Star-import detection is present for `os` and `subprocess`. Bare `.pid` attribute check uses exact match (`node.attr == "pid"`), not prefix-match — `pid_file`, `pid_path` are not flagged. Exit codes are correct (0 clean, 1 violations, 2 bad args). Verified: `scripts/check_backend_isolation.py src/automil` exits 0. One gap: the walker does not flag `os.getpid` **by-name** aliases (e.g., `from os import getpid as get_my_pid; get_my_pid()`). FORBIDDEN_OS_ATTRS correctly includes `"getpid"` for attribute access, and `_alias_map` tracking in `visit_Name` handles aliases for `FORBIDDEN_NAMES` (Popen), but the `visit_Name` alias check does NOT extend to `FORBIDDEN_OS_ATTRS`. This is an existing theoretical gap, not a Phase 2 regression.

**7. Re-export shim (`orchestrator.py`):** PARTIAL. The shim correctly star-imports from `_orchestrator_daemon` and explicitly re-exports the private helpers needed by tests. The DEPRECATED banner is present. However, `__getattr__` does not guard against dunder names — Python's import machinery and pytest both probe the module for `__path__`, `__test__`, `__bases__`, etc., causing misleading "automil.orchestrator.__path__ moved to …" `DeprecationWarning`s. This is 14 spurious warnings in the test suite. See WR-01.

**8. Cross-cutting concerns:** COVERED with one issue. No `Popen | os.kill | os.killpg | .pid` references in non-allowlisted Phase 2 files (BCK-04 lint verified). All CLI command functions use lazy imports. All modules have `logger = logging.getLogger(__name__)`. Type hints are comprehensive for public APIs. Error messages include "what went wrong + how to fix" context. One minor issue: `local.py:101` uses `datetime.utcfromtimestamp()` which is deprecated in Python 3.12+. See WR-02.

---

## Critical

### CR-01: `LocalBackend.submit()` ignores `spec.overlay_dir` — resubmit silently loses the variant overlay

**File:** `src/automil/backends/local.py:114`

**Issue:** `LocalBackend.submit()` writes `"overlay_dir": f"archive/{spec.node_id}"` into the daemon queue spec, completely ignoring `spec.overlay_dir` (the `Path` field that callers set to the actual overlay directory). When `automil resubmit` is called, it passes:
- `node_id = new_node_id` (e.g., `"node_0010"`)
- `overlay_dir = orch_dir / "archive" / old_node_id` (e.g., `.../archive/node_0005/`)

`LocalBackend.submit()` discards `spec.overlay_dir` and writes `"overlay_dir": "archive/node_0010"` to the queue spec. The daemon (`_orchestrator_daemon.py:586-610`) creates `archive/node_0010/` (empty except for `spec.json`), then calls `apply_overlay(wt_path, orch_dir / "archive/node_0010")`. Since the directory contains only `spec.json` (excluded by `apply_overlay`'s `metadata_files` guard), **no overlay files are copied to the worktree**. The experiment silently runs on base-commit code, not the resubmitted variant.

The test suite (`test_resubmit_happy_path`) does not verify the queue spec's `overlay_dir` value or that the overlay files are present at the expected daemon-side path, so this bug passes all 420 tests.

**Fix:** Either (a) use `spec.overlay_dir.relative_to(self._orch_dir)` to compute the correct relative path, or (b) have `resubmit.py` copy the overlay files to `archive/<new_node_id>/` before calling `Backend.submit()`. Option (b) is architecturally cleaner because it makes the new archive self-contained:

```python
# In resubmit.py, after generating new_node_id:
import shutil

new_archive_dir = orch_dir / "archive" / new_node_id
new_archive_dir.mkdir(parents=True, exist_ok=True)
for overlay_path in overlay_paths:
    shutil.copy2(overlay_path, new_archive_dir / overlay_path.name)

# Then update the JobSpec:
new_spec = JobSpec(
    node_id=new_node_id,
    overlay_files=overlay_file_names,
    overlay_dir=new_archive_dir,  # <-- now points to new node's archive
    ...
)
```

Alternatively, fix it in `local.py` by computing the relative path from `spec.overlay_dir`:

```python
# In LocalBackend.submit(), replace line 114:
try:
    rel_overlay = spec.overlay_dir.relative_to(self._orch_dir)
    overlay_dir_str = str(rel_overlay)
except ValueError:
    overlay_dir_str = f"archive/{spec.node_id}"  # fallback for external paths
queue_spec = {
    ...
    "overlay_dir": overlay_dir_str,
    ...
}
```

---

## Warnings

### WR-01: `orchestrator.py` `__getattr__` fires for Python-internal dunder probes — 14 spurious `DeprecationWarning`s in test suite

**File:** `src/automil/orchestrator.py:47-55`

**Issue:** The PEP 562 `__getattr__` does not filter dunder names. Python's import machinery probes `__path__` (to determine if the module is a package), and pytest probes `__test__`, `__bases__`, etc. when collecting tests. Each probe triggers the `warnings.warn()` inside `__getattr__`, emitting misleading messages like `"automil.orchestrator.__path__ moved to automil.backends._orchestrator_daemon in Phase 2 (D-60). Update imports by 2027-01."` This appears 14 times across the test suite and in `check.py`'s `from automil.orchestrator import ...` statements. Per PEP 562 recommendations, `__getattr__` should raise `AttributeError` for dunder names rather than calling `warnings.warn`.

**Fix:**
```python
def __getattr__(name: str):
    # PEP 562: raise AttributeError for dunder names — Python's import
    # machinery probes __path__, __spec__, etc.; these should not fire warnings.
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    _warnings.warn(
        f"automil.orchestrator.{name} moved to automil.backends._orchestrator_daemon "
        f"in Phase 2 (D-60). Update imports by 2027-01.",
        DeprecationWarning,
        stacklevel=2,
    )
    from automil.backends import _orchestrator_daemon as _mod
    return getattr(_mod, name)
```

### WR-02: `datetime.utcfromtimestamp()` deprecated in Python 3.12+

**File:** `src/automil/backends/local.py:101`

**Issue:** `datetime.utcfromtimestamp(submitted_ts).isoformat()` uses an API deprecated in Python 3.12 and scheduled for removal in a future version. Running under Python 3.12+ with `PYTHONWARNINGS=error` (or `pytest -W error::DeprecationWarning`) would cause `LocalBackend.submit()` to raise. The current test environment uses Python 3.11.13 where this does not surface.

**Fix:**
```python
# Replace line 101 in local.py:
from datetime import timezone  # add to module-level imports
submitted_iso = datetime.fromtimestamp(submitted_ts, tz=timezone.utc).isoformat()
```

---

## Info

### IN-01: `resubmit.py` uses `__import__("datetime")` inline instead of a module-level import

**File:** `src/automil/cli/resubmit.py:197,199`

**Issue:** `__import__("datetime").datetime.now().isoformat()` is used twice for `resubmitted_at` and `created_at`. This is unconventional, harder to read, and bypasses the standard import mechanism. The PATTERNS.md §8 lazy-import convention applies to heavy dependencies to avoid circular import issues at CLI load time, not to stdlib modules.

**Fix:** Add `from datetime import datetime` to the top-level imports (already imported in other CLI modules like `cancel.py`) and replace `__import__("datetime").datetime.now().isoformat()` with `datetime.now().isoformat()`.

### IN-02: `cancel.py` and `resubmit.py` write local-time ISO strings for timestamps instead of UTC

**File:** `src/automil/cli/cancel.py:176`, `src/automil/cli/resubmit.py:197,199`

**Issue:** `datetime.now().isoformat()` produces a naive local-time string (no timezone info), inconsistent with the UTC-based timestamps written by `local.py:101` (`utcfromtimestamp` → naive UTC). `cancel.py` imports `timezone` (line 21) but only uses it for parsing, not writing. This makes the `cancelled_at` and `resubmitted_at` fields ambiguous when interpreted across timezone boundaries.

**Fix:** Use `datetime.now(tz=timezone.utc).isoformat()` for all written timestamp fields.

### IN-03: `cancel.py` poll loop hard-fails if job reaches COMPLETED (not CANCELLED) before timeout

**File:** `src/automil/cli/cancel.py:154-161`

**Issue:** If a job completes naturally (COMPLETED) in the window between the `state == 'running'` guard check (step 2) and the cancel poll loop exiting (step 7), `final_state` will be `JobState.COMPLETED != JobState.CANCELLED`, causing `cancel` to exit with error: `"Cancel sent but state did not transition to 'cancelled' within Ns (current state: 'completed')"`. The user's actual intent (stop the job) was achieved, but the CLI reports failure and does not update the graph. This leaves `graph.json` with `status="running"` and `running/<id>.json` unarchived.

The window is narrow (between graph state check and the cancel's poll loop observing the terminal state), but it is a real inconsistency. A reasonable fix: accept COMPLETED as a "cancel succeeded" outcome in the poll loop, or at minimum emit a warning rather than a hard error.

**Fix (minimal):**
```python
# After the poll loop, before the hard-fail:
if final_state in (JobState.CANCELLED, JobState.COMPLETED, JobState.CRASHED):
    # Job reached a terminal state — accept all terminals as cancel-success
    # (COMPLETED/CRASHED means the job finished before the signal took effect)
    pass  # proceed to graph update
else:
    raise click.ClickException(...)
```

### IN-04: `mock_slurm.py::log_iter()` reads `job.state` without `self._lock`

**File:** `src/automil/backends/mock_slurm.py:258,262`

**Issue:** `log_iter()` reads `job.state` twice without holding `self._lock` (lines 258 and 262). Timer callbacks write `job.state` under `self._lock`. Under CPython's GIL, enum attribute reads are atomic, so this is safe in practice. However, the inconsistency with `poll()` (which acquires `self._lock` to get the job reference) and the rest of the codebase's lock discipline could be surprising to reviewers or when running under a free-threaded Python build. Similarly, `poll()` at line 221 returns `job.state` outside the lock (it acquires the lock only to retrieve the `job` reference, not to read `job.state`).

**Fix:** For consistency and future-proofing, read `job.state` inside the lock in `log_iter` and `poll`:
```python
def log_iter(self, handle: JobHandle) -> Iterator[str]:
    with self._lock:
        job = self._jobs.get(handle.opaque_id)
    if job is None:
        return
    while True:
        with self._lock:
            state = job.state
            is_terminal = state in _TERMINAL_STATES
        if is_terminal:
            yield from job.log_buffer
            return
        time.sleep(0.05)
```

### IN-05: `orchestrator.py` shim triggers spurious `_orchestrator_daemon` reload on first `import automil.orchestrator` if daemon was already loaded

**File:** `src/automil/orchestrator.py:30-31`

**Issue:** Lines 30-31:
```python
if _daemon_name in _sys.modules:
    _importlib.reload(_sys.modules[_daemon_name])
```
This runs at module-load time (not just on `importlib.reload()`). If `automil.backends._orchestrator_daemon` was already in `sys.modules` (e.g., from a `LocalBackend()` construction in a previous test), importing `automil.orchestrator` for the first time will reload `_orchestrator_daemon`, resetting its module-level state (including `NVIDIA_SMI_PATH`, frozensets, etc.). Verified: setting `daemon_mod.NVIDIA_SMI_PATH = "CORRUPTED"`, then importing `automil.orchestrator`, resets it to the `shutil.which()` result.

This is intentional for the `importlib.reload(automil.orchestrator)` test use case (where you want `NVIDIA_SMI_PATH` to re-resolve), but it fires unexpectedly in pytest sessions where backends tests run before orchestrator tests. The 44 DeprecationWarnings and the reload itself are benign in current tests (all 420 pass), but the mechanism is surprising and could cause subtle test ordering issues.

**Fix:** The guard should distinguish between "first import" and "explicit reload". One approach: use a module-level flag.
```python
_SHIM_LOADED = False
if not _SHIM_LOADED:
    _SHIM_LOADED = True
    # first import: do NOT reload; just import
else:
    # explicit reload context: trigger the daemon reload
    if _daemon_name in _sys.modules:
        _importlib.reload(_sys.modules[_daemon_name])
```
However, since this reload behavior is relied on by `test_orchestrator_nvidia_smi.py`, any fix must preserve the explicit-`importlib.reload` path.

---

## Suite-level health

- **Tests:** 420 passed, 9 skipped, 0 failed (Phase 2 baseline)
- **BCK-04 lint:** `scripts/check_backend_isolation.py src/automil` exits 0 — no violations
- **Backwards-compat shim:** 387 baseline tests (pre-Phase-2) still pass — zero regressions
- **Anti-acceptance gate:** ABC tested against LocalBackend and MockSLURMBackend in the same phase; 4 contract scenarios pass on LocalBackend, 13 on MockSLURMBackend (9 LocalBackend scenarios correctly skipped, requiring live daemon)
- **Spurious DeprecationWarnings:** 44 total in suite; 14 from `__getattr__` dunder probes (WR-01), 30 from legitimate deprecated import paths

---

## Recommendation

**Execute `/gsd-code-review-fix` for CR-01 and WR-01 before merging.** The overlay-dir bug (CR-01) makes `automil resubmit` functionally broken for `LocalBackend` — the variant code is never applied. WR-01 produces misleading output that could mask real deprecation warnings. WR-02 and IN-01 through IN-05 are polish items that can be batched into the same fix pass or deferred to Phase 3 cleanup.

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
