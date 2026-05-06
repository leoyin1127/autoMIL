---
phase: 06-slurm-backend-submitit-ray-backend-raw-ray-remote
plan: 06
type: execute
wave: 3
depends_on: ["06-01", "06-04", "06-05"]
files_modified:
  - src/automil/backends/_orchestrator_daemon.py
  - src/automil/backends/local.py
  - src/automil/cli/cancel.py
  - src/automil/cli/reconcile.py
  - src/automil/cli/cell.py
  - src/automil/graph.py
  - CHANGELOG.md
autonomous: true
requirements: [BCK-05, BCK-06]

must_haves:
  truths:
    - "Daemon resolves `running_dir = orch_dir / 'running' / backend_name` per-backend at tick time (D-169); no more flat `self.running_dir = orch_dir / 'running'`."
    - "Daemon `run()` startup raises `SystemExit` with the BREAKING CHANGE message when flat `running/*.json` exists with no namespaced subdirs (D-168)."
    - "`LocalBackend._running_dir` resolves to `running/local/`; `LocalBackend.list_running()` scans only `running/local/*.json`."
    - "`automil cancel <node_id>` reads `running/<backend>/<node_id>.json` (with backend_name resolved from node.metadata.backend, default 'local')."
    - "`automil reconcile` `running_dir` traversal uses `rglob('*.json')` so it finds files across `running/local/`, `running/slurm/`, `running/ray/`."
    - "`automil cell` `_count_running_in_cell` uses `rglob('*.json')` over `running/`."
    - "Wave-0 stub `test_running_dir_per_backend` flips RED→GREEN."
    - "Wave-0 stub `test_daemon_refuses_flat_running` flips RED→GREEN."
    - "Wave-0 stub `test_namespace_isolation` flips RED→GREEN."
    - "CHANGELOG.md gains a 6.0.0 BREAKING entry per CONTEXT.md `<specifics>` template."
    - "Phase 5 779-test baseline preserved (no LocalBackend regression)."
  artifacts:
    - path: src/automil/backends/_orchestrator_daemon.py
      provides: "Per-backend running_dir resolution + flat-running guardrail + _backend_running_dir helper."
      contains: "_backend_running_dir"
    - path: src/automil/backends/local.py
      provides: "LocalBackend reads running/local/* (D-169)."
    - path: CHANGELOG.md
      provides: "6.0.0 BREAKING entry with operator recovery instructions."
      contains: "BREAKING"
  key_links:
    - from: src/automil/backends/_orchestrator_daemon.py
      to: src/automil/backends/_orchestrator_daemon.py::_backend_running_dir
      via: per-backend path resolution helper
      pattern: "def _backend_running_dir"
    - from: src/automil/backends/_orchestrator_daemon.py::run
      to: SystemExit
      via: flat-running guardrail
      pattern: "BREAKING CHANGE"
    - from: src/automil/cli/cancel.py
      to: running/<backend>/<node>.json
      via: per-backend path resolution after backend_name lookup
      pattern: "running.*backend_name"
---

<objective>
Wave 3 — execute the breaking `running/` namespace migration (D-168, D-169). After this plan: each backend writes its own `running/<backend>/*.json`; the daemon refuses to start if it finds Phase-5-style flat `running/*.json` files (forcing operators to drain in-flight runs before upgrade per CHANGELOG); `automil cancel` / `reconcile` / `cell` all resolve paths per-backend.

Purpose: D-168 is a Leo-explicit BC-hack-rejection ("autoMIL 6.x does NOT auto-migrate flat → namespaced" / CLAUDE.md "Avoid backwards-compatibility hacks"). The startup guardrail prevents a half-migrated state from corrupting live runs (e.g., daemon starts, sees flat files, treats them as legacy local entries while new submits land under `running/local/` — instant data race). The drain-before-upgrade discipline is the operator-facing contract.

Output: 6 source files modified + CHANGELOG entry. This is a multi-touch wave, but every change is small (single attribute, single glob → rglob, single path-resolution helper). Wave-execution constraint: this plan touches files that were NOT touched by 06-04 (slurm.py) or 06-05 (ray.py), so it is wave-3 (after wave-2 ships the backend implementations).
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

# Files this plan modifies (all 5 source + 1 doc):
@src/automil/backends/_orchestrator_daemon.py
@src/automil/backends/local.py
@src/automil/cli/cancel.py
@src/automil/cli/reconcile.py
@src/automil/cli/cell.py
@src/automil/graph.py

# Wave-0 stubs flipped green by this plan:
@tests/backends/test_running_namespace.py

<interfaces>
<!-- Public surface created. Plan 06-07 (log unification) builds on _backend_running_dir helper. -->

From src/automil/backends/_orchestrator_daemon.py (after this plan):
```python
class ExperimentOrchestrator:
    # New helper:
    def _backend_running_dir(self, backend_name: str) -> Path:
        """Return orch_dir / 'running' / backend_name. Idempotent; creates dir on demand."""

    # run() startup additions:
    def run(self) -> None:
        # D-168 guardrail: refuse to start if flat running/*.json without namespaced subdirs.
        ...
        # existing _recover_orphans() etc.
```

From src/automil/backends/local.py (after this plan):
```python
class LocalBackend(Backend):
    # __init__:
    self._running_dir = self._orch_dir / "running" / "local"  # NOT flat
```

CHANGELOG.md gains a 6.0.0 entry (verbatim from CONTEXT.md `<specifics>`).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Daemon migration — _backend_running_dir helper, per-backend resolution, startup guardrail</name>
  <files>src/automil/backends/_orchestrator_daemon.py</files>
  <read_first>
    - src/automil/backends/_orchestrator_daemon.py (full file — 1200 lines; identify all 8+ `running_dir` references at lines 287, 472, 474, 709, 771, 816, 852, 857, 917, 980)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"src/automil/backends/_orchestrator_daemon.py" lines 418-514 — exact refactor pattern + guardrail code)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-168 — guardrail message wording; D-169 — list of 8+ reference sites)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md (Pitfall 11 — guardrail must check `glob("*.json")` at top level only, NOT recursively)
    - tests/backends/test_running_namespace.py (Wave-0 stubs from plan 06-01 — exact API expected)
  </read_first>
  <behavior>
    - Test 1: `daemon._backend_running_dir("local") == orch_dir / "running" / "local"` (Wave-0 stub).
    - Test 2: `daemon._backend_running_dir("slurm") == orch_dir / "running" / "slurm"`.
    - Test 3: `daemon.run()` raises `SystemExit` with `match="BREAKING CHANGE"` when flat `running/*.json` exists without namespaced subdirs (Wave-0 stub).
    - Test 4: All existing daemon-tick behaviors continue to work — Phase 5 779-test baseline preserved.
    - Test 5: A flat `running/*.json` file IN ADDITION TO `running/local/*.json` (mixed state) still triggers the guardrail because the guardrail check is "any flat *.json AND no namespaced subdirs". Once `running/local/` exists, flat files are tolerable but never written by the new code.
  </behavior>
  <action>
**Step A — Replace the flat `self.running_dir` attribute** (line 287). Change:
```python
self.running_dir = self.orch_dir / "running"
```
to:
```python
# D-169: running_dir is no longer a single attribute — resolved per-backend
# via _backend_running_dir(name). The base running root remains for the
# startup guardrail check (D-168) and log unification (D-170).
self.running_root = self.orch_dir / "running"
# Backwards alias used internally where backend is implicitly "local"; new code
# should call self._backend_running_dir(backend_name) instead.
self.running_dir = self.running_root / "local"
```

The reason for keeping `self.running_dir` as a backward alias: the daemon's existing internal launch path (line 709 `self.running_dir / f"{node_id}.json"`) is used for LocalBackend dispatch in production. Pointing it at `running/local/` is the correct semantics post-migration AND minimizes the diff. New code (cancel.py, reconcile.py, cell.py, log unification) MUST call `_backend_running_dir(name)`.

**Step B — Add the `_backend_running_dir` helper** as an instance method on `ExperimentOrchestrator` (insert near `__init__`):
```python
def _backend_running_dir(self, backend_name: str) -> Path:
    """Return orch_dir / 'running' / <backend_name>; create on demand (D-169).

    Per-backend namespacing was introduced in Phase 6 (BCK-05/06). Default
    fallback is 'local' for legacy nodes without metadata.backend (Phase 2 D-76).
    """
    if not backend_name:
        backend_name = "local"
    path = self.running_root / backend_name
    path.mkdir(parents=True, exist_ok=True)
    return path
```

**Step C — Update `run()` to add the D-168 startup guardrail** (insert at the very top of `run()`, before `_recover_orphans()`):
```python
def run(self) -> None:
    # D-168 (BREAKING in 6.0.0): refuse to start if flat running/*.json files
    # exist AND no namespaced subdirectory exists. autoMIL 6.x does NOT
    # auto-migrate; operators must drain via `automil orchestrator stop` and
    # confirm running/ is empty before upgrading.
    if self.running_root.exists():
        flat_jsons = list(self.running_root.glob("*.json"))  # top-level only
        namespaced = [
            (self.running_root / name)
            for name in ("local", "slurm", "ray")
            if (self.running_root / name).is_dir()
        ]
        if flat_jsons and not namespaced:
            raise SystemExit(
                "BREAKING CHANGE: flat orchestrator/running/*.json files detected. "
                "autoMIL 6.x uses per-backend namespacing (running/<backend>/<id>.json). "
                f"Found {len(flat_jsons)} flat file(s) in {self.running_root}. "
                "Drain in-flight runs with `automil orchestrator stop`, confirm "
                "orchestrator/running/ contains no top-level *.json files, then "
                "restart the daemon. See CHANGELOG.md 6.0.0 for full recovery steps."
            )
    # ... existing run() body (unchanged)
    self._recover_orphans()
    # ... rest of method
```

**Step D — Update `_orchestrator_daemon._launch` and related write sites**: every `self.running_dir / f"{node_id}.json"` reference in the daemon's launch/cancel/cap path uses the LocalBackend dispatch path (the daemon itself only launches LocalBackend jobs; SLURM and Ray dispatch is owned by the backend's `submit()` method). Because `self.running_dir` now points at `running/local/`, these existing references resolve correctly without further modification. Verify by reading lines 472, 474, 709, 771, 816, 852, 857, 917, 980 and confirming each reference is for the LocalBackend (daemon-launched) path. If any of them are reading SLURM/Ray running entries, refactor that specific call to `self._backend_running_dir(spec_metadata.get("backend", "local"))`.

In particular, the `_recover_orphans` method (~line 472) iterates `self.running_dir.glob("*.json")` to recover crashed nodes from a previous daemon. Post-migration, this only recovers LocalBackend orphans — SLURM and Ray orphans are recovered via `SLURMBackend.list_running()` / `RayBackend.list_running()` invoked separately. This is the intended Phase 6 semantics: the daemon only manages local processes; remote backends manage their own running/.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_running_namespace.py::test_running_dir_per_backend tests/backends/test_running_namespace.py::test_daemon_refuses_flat_running -x -v &amp;&amp; uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py --ignore=tests/backends/test_log_unification.py</automated>
  </verify>
  <done>
    `_backend_running_dir(name)` returns `orch_dir/running/<name>` for any name (defaulting to `local` on empty). `daemon.run()` raises `SystemExit("BREAKING CHANGE...")` when flat *.json present without namespaced subdirs. `self.running_dir` (backward alias) now points at `running/local/`. Phase 5 779-test baseline still green. Two of three Wave-0 namespace stubs flip green.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Update LocalBackend + cli/cancel + cli/reconcile + cli/cell + graph.py for per-backend paths</name>
  <files>src/automil/backends/local.py, src/automil/cli/cancel.py, src/automil/cli/reconcile.py, src/automil/cli/cell.py, src/automil/graph.py</files>
  <read_first>
    - src/automil/backends/local.py (lines 50-130 `__init__` — `self._running_dir` assignment site)
    - src/automil/cli/cancel.py (line 84 `running_path = orch_dir / "running" / f"{node_id}.json"`)
    - src/automil/cli/reconcile.py (line 73-77 — `running_dir=str(orch / "running")`)
    - src/automil/cli/cell.py (lines 18-41 `_count_running_in_cell`, line 34 `running_dir.glob("*.json")`)
    - src/automil/graph.py (search for `reconcile` function — `glob("*.json")` over the running dir)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-PATTERNS.md (§"src/automil/cli/cancel.py" lines 549-563; §"reconcile.py" lines 568-591; §"cli/cell.py" lines 596-615)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (D-169)
    - tests/backends/test_running_namespace.py::test_namespace_isolation (Wave-0 stub)
  </read_first>
  <behavior>
    - Test 1 (Wave-0): `test_namespace_isolation` flips green — LocalBackend.list_running() does NOT see fake `running/slurm/*.json` entries.
    - Test 2: `automil cancel <node_id>` reads `running/<backend>/<node_id>.json` with backend resolved from node.metadata.backend.
    - Test 3: `automil reconcile` enumerates ALL backend subdirs (rglob) so completion+archive moves are correct across backends.
    - Test 4: `automil cell status` counts running entries across all backends in a given cell.
    - Test 5: Phase 5 779-test baseline preserved.
  </behavior>
  <action>
**Step A — `src/automil/backends/local.py`**: locate the `_running_dir` assignment in `__init__`. Currently `self._running_dir = self._daemon.running_dir` (post-Task-1, this points at `running/local/` already due to the backward alias). To make the intent explicit, change to:
```python
self._running_dir = self._orch_dir / "running" / "local"
```
Ensure `self._orch_dir` exists (it does — `self._daemon.orch_dir`). Touch only the assignment line; no other change to `local.py`.

**Step B — `src/automil/cli/cancel.py`**: line 84 currently:
```python
running_path = orch_dir / "running" / f"{node_id}.json"
```
The backend_name was already resolved at line 80 (`backend_name: str = node.get("metadata", {}).get("backend", "local")`). Change line 84 to:
```python
running_path = orch_dir / "running" / backend_name / f"{node_id}.json"
```
No other change.

**Step C — `src/automil/cli/reconcile.py`**: leave the `running_dir=str(orch / "running")` argument as-is (line 74) — the `ExperimentGraph.reconcile()` method's traversal pattern is what changes. See Step E.

**Step D — `src/automil/cli/cell.py`**: line 34 currently:
```python
for f in running_dir.glob("*.json"):
```
Change to:
```python
for f in running_dir.rglob("*.json"):
```
Single-character change (g → rg). This makes the count traverse `running/local/*.json`, `running/slurm/*.json`, `running/ray/*.json`.

**Step E — `src/automil/graph.py`**: locate `ExperimentGraph.reconcile` (search via `grep -n "def reconcile" src/automil/graph.py`). Inside the method's running-dir traversal, change `glob("*.json")` to `rglob("*.json")` so the reconcile picks up entries across all backend subdirectories. If the method also extracts node_id from the file stem, that stays the same — node_id is unique across backends per Phase 2 D-52.

**Step F — Verify all five files**: run `grep -nE "running\".*\.glob\(\"\\*\\.json\"\)" src/automil/` after the changes — should return ZERO matches in cli/cell.py, cli/reconcile.py callers, and graph.py for traversal sites (the helper for namespace isolation in `_orchestrator_daemon._recover_orphans` is intentional — it ONLY recovers local-backend orphans by design per Task 1 Step D). Backend-specific `list_running()` methods use direct `running/<backend>/*.json` paths and are unaffected.
  </action>
  <verify>
    <automated>uv run pytest tests/backends/test_running_namespace.py -x -v &amp;&amp; uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py --ignore=tests/backends/test_log_unification.py</automated>
  </verify>
  <done>
    All three Wave-0 namespace stubs flip green. `cli/cell.py` uses `rglob`. `cli/cancel.py` resolves backend before reading running spec. `LocalBackend._running_dir` explicitly points at `running/local/`. Phase 5 779-test baseline preserved. `grep -nE 'running.*glob\\("\\*\\.json"\\)' src/automil/cli/cell.py src/automil/cli/reconcile.py` returns 0 (only rglob remains).
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 3: Add CHANGELOG.md 6.0.0 BREAKING entry</name>
  <files>CHANGELOG.md</files>
  <read_first>
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-CONTEXT.md (`<specifics>` section — verbatim CHANGELOG template)
    - .planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-RESEARCH.md (Pitfall 11 — exact guardrail check description)
    - CLAUDE.md (Leo's "Avoid backwards-compatibility hacks" directive — context for why this is breaking)
  </read_first>
  <action>
Create `CHANGELOG.md` if it does not exist (the project does not currently have one — confirmed by `ls CHANGELOG.md 2>&1`). Write the file with this exact content:

```markdown
# Changelog

autoMIL — F2-readiness framework refactor

## 6.0.0 — Phase 6 SLURM + Ray backends (unreleased)

### BREAKING: Per-backend `running/` namespacing

`orchestrator/running/<id>.json` (flat) → `orchestrator/running/<backend>/<id>.json` (namespaced).

**Why:** Phase 6 introduces SLURMBackend and RayBackend (BCK-05, BCK-06). Each
backend owns its own running-spec directory so cross-backend operations cannot
corrupt each other (D-168, D-169). autoMIL 6.x does NOT auto-migrate flat layout
to namespaced layout (per CLAUDE.md "Avoid backwards-compatibility hacks").

**Operators upgrading from 5.x must:**

1. Run `automil orchestrator stop` and wait for in-flight runs to terminate.
2. Confirm `orchestrator/running/` contains zero `.json` files at the top level
   (subdirectories are fine):
   ```bash
   ls automil/orchestrator/running/*.json 2>/dev/null | wc -l
   # Expected: 0
   ```
3. Upgrade autoMIL.
4. Restart the daemon: `automil orchestrator start`.

**Daemon refusal to start:** if the daemon detects flat `running/*.json` at startup
without namespaced subdirectories, it exits with a `BREAKING CHANGE` message
listing the files found. This guardrail prevents a half-migrated state from
corrupting live runs.

### Added

- `SLURMBackend` (`src/automil/backends/slurm.py`) — opt-in via `pip install -e '.[slurm]'`.
  Dispatches via submitit AutoExecutor; honors Phase 4 cap contract via `--signal=B:TERM@30`.
- `RayBackend` (`src/automil/backends/ray.py`) — opt-in via `pip install -e '.[ray]'`.
  Dispatches via raw `@ray.remote` (NOT Ray Tune); hybrid `RAY_ADDRESS` → local fallback.
- `BackendNotInstalledError`, `SlurmDirectivesIncompleteError`, `RayClusterUnreachableError`
  in `automil.backends.errors`.
- `automil check` validates `backend.slurm.directives` completeness (rejects `TODO_FILL_IN`)
  and Ray cluster reachability (advisory).
- Cross-backend log unification: `archive/<id>/run.log` is orchestrator-owned and
  drained from `backend.log_iter()` on terminal-state observation.
- pytest markers `requires_slurm` / `requires_ray` for nightly real-cluster tests.

### Compatibility

- `pip install -e .` (no extras) still works; submitit and ray are NOT pulled.
- `automil --help`, `automil submit`, `automil cancel`, `automil resubmit` work unchanged
  for `backend.name: local` configs.
- Phase 5 generalization gate, Phase 4 cap, Phase 3 trajectory recorder are unchanged.
```

Do NOT modify any other doc file. Do NOT add a `CHANGELOG.md` to the `.gitignore` (it should be tracked).
  </action>
  <verify>
    <automated>test -f CHANGELOG.md &amp;&amp; grep -E "^## 6\.0\.0" CHANGELOG.md &amp;&amp; grep -E "BREAKING" CHANGELOG.md &amp;&amp; grep -E "automil orchestrator stop" CHANGELOG.md</automated>
  </verify>
  <done>
    `CHANGELOG.md` exists at the repo root with a `## 6.0.0` heading containing the BREAKING entry. The entry includes the operator recovery steps verbatim. The `Added` section lists SLURMBackend, RayBackend, the three error types, the `automil check` extensions, the log unification, and the pytest markers. The `Compatibility` section calls out that no-extras install still works.
  </done>
</task>

</tasks>

<verification>

```bash
# All three Wave-0 namespace stubs flip green
uv run pytest tests/backends/test_running_namespace.py -x -v

# Daemon helper present
grep -E "def _backend_running_dir" src/automil/backends/_orchestrator_daemon.py

# Cell uses rglob
grep -E "rglob\(.*\\*\.json" src/automil/cli/cell.py

# Cancel resolves per-backend path
grep -E "running.*backend_name.*node_id" src/automil/cli/cancel.py

# CHANGELOG entry exists
grep -E "BREAKING.*Per-backend.*namespacing" CHANGELOG.md

# Phase 5 baseline preserved
uv run pytest tests/ -x -q --ignore=tests/backends/test_node_0176_smoke.py --ignore=tests/backends/test_log_unification.py
```

</verification>

<success_criteria>

- [ ] `_orchestrator_daemon.py::_backend_running_dir(name)` instance method defined.
- [ ] Daemon `run()` raises `SystemExit("BREAKING CHANGE...")` on flat-running detection.
- [ ] `LocalBackend._running_dir` resolves to `running/local/`.
- [ ] `cli/cancel.py` line ~84 reads `running/<backend_name>/<node_id>.json`.
- [ ] `cli/cell.py` `_count_running_in_cell` uses `rglob`.
- [ ] `graph.py::ExperimentGraph.reconcile` running-dir traversal uses `rglob`.
- [ ] `CHANGELOG.md` exists at repo root with 6.0.0 BREAKING entry.
- [ ] Wave-0 stubs `test_running_dir_per_backend`, `test_daemon_refuses_flat_running`, `test_namespace_isolation` flip green.
- [ ] Phase 5 779-test baseline + Wave-0 stubs green; no regression.
- [ ] `python scripts/check_backend_isolation.py src/automil/` exits 0.

</success_criteria>

<output>
After completion, create `.planning/phases/06-slurm-backend-submitit-ray-backend-raw-ray-remote/06-06-SUMMARY.md` describing: which 8+ daemon reference sites were touched (with line numbers), CHANGELOG entry confirmed, three Wave-0 stubs flipped green.
</output>
