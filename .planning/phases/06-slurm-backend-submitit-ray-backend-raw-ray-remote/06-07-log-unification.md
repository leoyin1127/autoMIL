---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 07
type: execute
wave: 4
depends_on: ["06-04", "06-05", "06-06"]
files_modified:
  - src/automil/backends/_orchestrator_daemon.py
autonomous: true
requirements: [BCK-05, BCK-06]

must_haves:
  truths:
    - "`_atomic_write_lines(path, lines)` helper is defined at module scope in `_orchestrator_daemon.py`; uses `tempfile.mkstemp` neighbour + `os.replace`; rollback uses `os.unlink` (NEVER `git checkout` — Leo memory `feedback_never_blind_checkout`)."
    - "`_drain_log_iter_with_timeout(backend, handle, timeout=60.0)` helper is defined at module scope; spawns a daemon thread to consume `backend.log_iter()`; force-closes after `timeout` seconds and returns the lines collected so far."
    - "On terminal-state observation in `_handle_completion` (and `_handle_timeout`), the daemon resolves `backend = BACKENDS[backend_name]`, reconstructs the JobHandle, drains `backend.log_iter(handle)` with a 60s timeout, and writes the result to `archive/<node_id>/run.log` via `_atomic_write_lines` (D-170)."
    - "For SLURM nodes, `archive/<id>/slurm-stdout.out` and `archive/<id>/slurm-stderr.err` are created as symlinks (NOT copies) into `submitit-logs/` per D-171."
    - "Wave-0 stubs `test_log_iter_close_60s_timeout`, `test_archive_run_log_slurm`, `test_archive_run_log_ray` flip RED→GREEN (assuming submitit/ray installed for the latter two — they `importorskip`)."
    - "Phase 5 779-test baseline preserved (`_handle_completion` for LocalBackend nodes still produces `archive/<id>/run.log` correctly)."
  artifacts:
    - path: src/automil/backends/_orchestrator_daemon.py
      provides: "Cross-backend log unification: orchestrator drains backend.log_iter into archive/<id>/run.log."
      contains: "_atomic_write_lines"
  key_links:
    - from: src/automil/backends/_orchestrator_daemon.py::_handle_completion
      to: src/automil/backends/_orchestrator_daemon.py::_atomic_write_lines
      via: terminal-state log drain to archive
      pattern: "_atomic_write_lines\\(.*run\\.log"
    - from: src/automil/backends/_orchestrator_daemon.py::_drain_log_iter_with_timeout
      to: backend.log_iter
      via: timeout-bounded drain wrapper
      pattern: "log_iter\\(handle\\)"
---

<objective>
Wave 4 — orchestrator-owned log unification (D-170, D-171). After this plan: every terminal-state node — local, SLURM, or Ray — has `archive/<id>/run.log` written by the daemon via `_atomic_write_lines`, regardless of which backend dispatched it. SLURM additionally gets symlinks to submitit's native log files.

Purpose: D-170 keeps backends as pure surface-providers (`log_iter()` is the contract; backends do not write to archive). The orchestrator owns the archive. This makes downstream consumers (viz, status, retrospective) backend-agnostic — they just read `archive/<id>/run.log`. The 60s timeout on `log_iter()` drain prevents a pathological backend (one whose iterator never closes) from blocking the daemon tick forever.

Output: 1 file modified (`_orchestrator_daemon.py`), with two new module-level helpers + a small extension to `_handle_completion` (and `_handle_timeout`) that calls them on terminal observation. This is the smallest plan in the phase by file-count but is the most architecturally important — it cements the orchestrator-owned-archive contract.
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

# The file modified:
@src/automil/backends/_orchestrator_daemon.py

# Atomic-write reference patterns (Phase 0 D-25):
@src/automil/cli/lifecycle/_shared.py

# Wave-0 stubs flipped green:
@tests/backends/test_log_unification.py

<interfaces>
<!-- Public surface created. Plan 06-09 (smoke) and viz/dashboard rely on archive/<id>/run.log existing. -->

From src/automil/backends/_orchestrator_daemon.py (after this plan):
```python
def _atomic_write_lines(path: Path, lines: list[str]) -> None:
    """Atomic write of log lines via tempfile.mkstemp + os.replace (D-170, Phase 0 D-25 pattern).

    Rollback uses path.unlink(), NOT git checkout (Leo memory: feedback_never_blind_checkout).
    """

def _drain_log_iter_with_timeout(
    backend, handle, timeout: float = 60.0
) -> list[str]:
    """Spawn a daemon thread to consume backend.log_iter(handle); return lines after timeout.

    The 60s default enforces D-170 contract: backends whose log_iter doesn't close
    within 60s of terminal state are treated as contract violations; the wrapper
    force-closes by abandoning the thread (daemon=True; thread is GC'd on daemon exit).
    """
```

The wrapper is invoked in `_handle_completion` (and `_handle_timeout`) AFTER the
existing local-backend completion handling, conditioned on the experiment having
been dispatched through a non-local backend (e.g., the spec includes
`metadata.backend in {"slurm", "ray"}`). For LocalBackend, the existing
`archive/<id>/run.log` writer is unchanged; we only add the cross-backend drain
for SLURM/Ray cases.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add _atomic_write_lines + _drain_log_iter_with_timeout helpers + wire into terminal-state handler</name>
  <files>src/automil/backends/_orchestrator_daemon.py</files>
  <read_first>
    - src/automil/backends/_orchestrator_daemon.py (full file — focus on `_handle_completion`, `_handle_timeout`, archive routing around lines 836-910)
    - src/automil/cli/lifecycle/_shared.py (lines 21-38 — `_atomic_write_text` reference pattern; copy with modifications for lines)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"src/automil/backends/_orchestrator_daemon.py" lines 462-514 — `_atomic_write_lines` + drain pattern)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-170 — 60s timeout enforcement; D-171 — symlink-not-copy for SLURM)
    - tests/backends/test_log_unification.py (Wave-0 stubs — exact API expected)
  </read_first>
  <behavior>
    - Test 1 (Wave-0): `_drain_log_iter_with_timeout(forever_backend, None, timeout=2.0)` returns within 3s with whatever lines were yielded — does not hang.
    - Test 2 (Wave-0): `test_archive_run_log_slurm` — SLURMBackend `log_iter` is drainable into `archive/<id>/run.log` via `_atomic_write_lines`.
    - Test 3 (Wave-0): `test_archive_run_log_ray` — RayBackend `log_iter` drainable similarly.
    - Test 4: `_atomic_write_lines(path, ["a\n", "b\n"])` writes the path with content `"a\nb\n"`; rollback on exception leaves no partial file.
    - Test 5: For a synthetic SLURM-dispatched node observed terminal, `archive/<id>/run.log` exists post-`_handle_completion`; for SLURM, also `archive/<id>/slurm-stdout.out` exists as a symlink (NOT a copy).
  </behavior>
  <action>
**Step A — Add `_atomic_write_lines` at module scope** (top of file, after the existing imports). Use the verbatim pattern from PATTERNS.md §"_atomic_write_lines helper":

```python
def _atomic_write_lines(path: Path, lines: list[str]) -> None:
    """Atomic write of log lines (D-170 / Phase 0 D-25 atomic-write pattern).

    Uses tempfile.mkstemp neighbour + os.rename (NOT git checkout — Leo memory
    feedback_never_blind_checkout: rollback uses path.unlink()).

    Args:
        path: target path (parent dir created if absent).
        lines: list of strings; pre-existing newline characters are preserved.
            If callers provide raw lines without newlines, the writer does NOT
            add them — this matches LocalBackend's `log_iter()` semantics where
            `splitlines(keepends=True)` is used at yield time.
    """
    import os as _os                # noqa: PLC0415; module-scope helper
    import tempfile as _tempfile    # noqa: PLC0415

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = _tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with _os.fdopen(tmp_fd, "w") as f:
            f.writelines(lines)
        _os.replace(tmp_path, str(path))
    except Exception:
        try:
            _os.unlink(tmp_path)  # rollback per memory:feedback_never_blind_checkout
        except OSError:
            pass
        raise
```

**Step B — Add `_drain_log_iter_with_timeout` at module scope**:
```python
def _drain_log_iter_with_timeout(backend, handle, timeout: float = 60.0) -> list[str]:
    """Drain backend.log_iter(handle) with a hard timeout (D-170).

    Spawns a daemon thread that consumes the iterator. After `timeout` seconds
    the wrapper returns the lines collected so far; backends whose log_iter
    doesn't close within the timeout are treated as a contract violation
    (logged warning). The thread is daemon=True so abandoned drainers are
    cleaned up on daemon exit.
    """
    import threading as _threading  # noqa: PLC0415

    lines: list[str] = []
    done = _threading.Event()

    def _drain() -> None:
        try:
            for line in backend.log_iter(handle):
                lines.append(line)
        except Exception as exc:
            logger.warning("_drain_log_iter_with_timeout: log_iter raised %s", exc)
        finally:
            done.set()

    t = _threading.Thread(target=_drain, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if not done.is_set():
        node_label = getattr(handle, "node_id", "<unknown>")
        logger.warning(
            "log_iter for %s did not close within %.1fs — force-closing (D-170 contract violation).",
            node_label, timeout,
        )
    return lines
```

**Step C — Wire into `_handle_completion`** (and `_handle_timeout` if it exists separately). The existing `_handle_completion` already writes `archive/<id>/run.log` for LocalBackend (~line 640 in the current file: the daemon copies the live log file into archive on completion). For Phase 6, we ADD a non-local-backend path:

Locate the `_handle_completion` method's archive-finalisation block (search for `archive_dir / node_id` references near `result.json` / `run.log` writes). After the existing local archive write, add a conditional drain for non-local backends:

```python
def _handle_completion(self, exp_id: str, retcode: int) -> None:
    # ... existing local archive logic (unchanged)
    
    # D-170: cross-backend log unification. For non-local backends, the
    # orchestrator drains backend.log_iter() into archive/<id>/run.log.
    # The local backend already writes this file inline; we don't override it.
    archive_node_dir = self.archive_dir / exp_id
    archive_node_dir.mkdir(parents=True, exist_ok=True)
    archive_run_log = archive_node_dir / "run.log"

    # Read backend_name from running spec (set by submit at metadata.backend).
    backend_name = self._read_backend_name_for_node(exp_id)
    if backend_name and backend_name != "local" and not archive_run_log.exists():
        try:
            from automil.backends import BACKENDS, JobHandle  # noqa: PLC0415
            BackendCls = BACKENDS.get(backend_name)
            if BackendCls is not None:
                spec_data = self._read_running_spec(exp_id, backend_name)
                handle = JobHandle(
                    node_id=exp_id,
                    backend=backend_name,
                    opaque_id=spec_data.get("opaque_id", ""),
                    submitted_at=spec_data.get("submitted_at", 0.0),
                )
                # Reuse the configured backend instance if attached; otherwise instantiate.
                backend = self.backend if (self.backend and getattr(self.backend, "_backend_name", None) == backend_name) else BackendCls(self.automil_dir, self.config)
                lines = _drain_log_iter_with_timeout(backend, handle, timeout=60.0)
                _atomic_write_lines(archive_run_log, lines)

                # D-171: for SLURM, symlink submitit's native logs into archive/.
                if backend_name == "slurm":
                    _symlink_slurm_logs(self.automil_dir, archive_node_dir, spec_data)
        except Exception as exc:
            logger.warning("D-170 cross-backend log unification failed for %s: %s",
                           exp_id, exc)
```

Add the helper methods `_read_backend_name_for_node`, `_read_running_spec`, and `_symlink_slurm_logs`:

```python
def _read_backend_name_for_node(self, node_id: str) -> str:
    """Read metadata.backend from the running spec (any backend subdir) or archive spec.

    Returns 'local' as fallback (Phase 2 D-76 legacy compatibility).
    """
    for backend_subdir in ("local", "slurm", "ray"):
        candidate = self.running_root / backend_subdir / f"{node_id}.json"
        if candidate.exists():
            try:
                payload = json.loads(candidate.read_text())
                return payload.get("backend") or backend_subdir
            except (json.JSONDecodeError, OSError):
                continue
    archive_spec = self.archive_dir / node_id / "spec.json"
    if archive_spec.exists():
        try:
            payload = json.loads(archive_spec.read_text())
            return payload.get("metadata", {}).get("backend", "local")
        except (json.JSONDecodeError, OSError):
            pass
    return "local"


def _read_running_spec(self, node_id: str, backend_name: str) -> dict:
    """Read running/<backend>/<node>.json; return {} if absent."""
    path = self.running_root / backend_name / f"{node_id}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _symlink_slurm_logs(automil_dir: Path, archive_node_dir: Path, spec_data: dict) -> None:
    """D-171: symlink submitit's native stdout/stderr into archive/<id>/.

    This must NOT be a method of ExperimentOrchestrator; it's a free function
    so it can be tested without instantiating the daemon.
    """
    opaque_id = spec_data.get("opaque_id", "")
    if not opaque_id:
        return
    submitit_logs = automil_dir / "orchestrator" / "running" / "slurm" / "submitit-logs"
    stdout_src = submitit_logs / f"{opaque_id}_0_log.out"
    stderr_src = submitit_logs / f"{opaque_id}_0_log.err"
    stdout_dst = archive_node_dir / "slurm-stdout.out"
    stderr_dst = archive_node_dir / "slurm-stderr.err"
    if stdout_src.exists() and not stdout_dst.exists():
        try:
            stdout_dst.symlink_to(stdout_src.resolve())
        except OSError as exc:
            logger.warning("D-171 stdout symlink failed: %s", exc)
    if stderr_src.exists() and not stderr_dst.exists():
        try:
            stderr_dst.symlink_to(stderr_src.resolve())
        except OSError as exc:
            logger.warning("D-171 stderr symlink failed: %s", exc)
```

`_symlink_slurm_logs` is module-level (not a method); the call site in `_handle_completion` should be `_symlink_slurm_logs(self.automil_dir, archive_node_dir, spec_data)`.

DO NOT remove or modify any existing LocalBackend archive-finalisation logic. The new code only ADDS the cross-backend drain when `backend_name != "local"` AND the archive run.log doesn't already exist (idempotency guard).
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_log_unification.py -x -v &amp;&amp; uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py</automated>
  </verify>
  <done>
    `_atomic_write_lines` and `_drain_log_iter_with_timeout` defined at module scope in `_orchestrator_daemon.py`. `_handle_completion` invokes them when `backend_name != "local"`. `_symlink_slurm_logs` is a module-level function. The 4 Wave-0 stubs in test_log_unification.py either pass (timeout test, slurm/ray drain tests via importorskip) or skip cleanly. The local stub (`test_archive_run_log_local`) explicitly skips per its body. Phase 5 baseline preserved.
  </done>
</task>

</tasks>

<verification>

```bash
# Helpers defined
grep -E "^def _atomic_write_lines|^def _drain_log_iter_with_timeout|^def _symlink_slurm_logs" src/automil/backends/_orchestrator_daemon.py

# Wave-0 stubs green
uv run pytest tests/backends/test_log_unification.py -x -v

# Phase 5 baseline preserved
uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py

# BCK-04 lint clean
python scripts/check_backend_isolation.py src/automil/

# Framework purity
grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/backends/_orchestrator_daemon.py
# Expected: 0 matches.
```

</verification>

<success_criteria>

- [ ] `_atomic_write_lines(path, lines)` exists at module scope in `_orchestrator_daemon.py`.
- [ ] `_drain_log_iter_with_timeout(backend, handle, timeout=60.0)` exists at module scope.
- [ ] `_symlink_slurm_logs(automil_dir, archive_node_dir, spec_data)` exists at module scope.
- [ ] `_handle_completion` (and `_handle_timeout` if separate) invoke the drain + atomic write when the node's backend != "local" AND `archive/<id>/run.log` does not yet exist.
- [ ] Rollback in `_atomic_write_lines` uses `os.unlink(tmp_path)`, NEVER `git checkout`.
- [ ] Wave-0 stub `test_log_iter_close_60s_timeout` flips green; `test_archive_run_log_slurm` and `test_archive_run_log_ray` flip green when extras installed (skip cleanly otherwise).
- [ ] BCK-04 lint clean.
- [ ] Framework purity: zero autobench/AUTOBENCH_/benchmarks/ refs in modified file.
- [ ] Phase 5 779-test baseline preserved.

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-07-SUMMARY.md` describing: helper signatures, terminal-state wiring location, symlink behavior, Wave-0 log-unification stub status.
</output>
