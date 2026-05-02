# Phase 1 — Codebase Patterns

**Mapped:** 2026-05-01
**Files analyzed:** 18 new/modified files (12 plans: 3 ABC files, registry singleton, 3 validator files, 3 variant modules + manifests, config edits, 6 CLI commands, check extension, train.py refactor, verify-repro command)
**Analogs found:** 18 / 18 (every new surface has a strong role-match)

---

## Integration map (where Phase 1 code lands)

| New file/module | Closest existing analog | Pattern to reuse |
|-----------------|-------------------------|------------------|
| `src/automil/registry/__init__.py` (singleton) | `src/automil/graph.py` (module-level `logger`) | Module-level singleton, `logging.getLogger(__name__)` |
| `src/automil/registry/variants/__init__.py` | `src/automil/cli/__init__.py` | Import-side-effect registration, `__all__` |
| `src/automil/registry/spec.py` (`VariantSpec`) | `src/automil/orchestrator.py` `GPUInfo` dataclass | Frozen `@dataclass`, typed fields |
| `src/automil/registry/validators/interface.py` | `src/automil/cli/submit.py` path validation block | Hard-fail with `raise click.ClickException` / `sys.exit(2)`, concrete error message with file:line |
| `src/automil/registry/validators/purity.py` | `src/automil/cli/submit.py` path validation block | Same hard-fail semantics |
| `src/automil/registry/validators/identity.py` | `src/automil/orchestrator.py` `_build_subprocess_env` | Run-time check with structured error output |
| `src/automil/cli/lifecycle.py` (6 commands) | `src/automil/cli/reconcile.py`, `src/automil/cli/control.py` | `@main.command()` + `_find_automil_dir()` + lazy graph import |
| `src/automil/cli/check.py` (extended) | `src/automil/cli/check.py` (current Phase 0 base) | `issues` + `warnings` lists, report at bottom |
| `benchmarks/experiments/ccrcc/automil/config.yaml` | `benchmarks/experiments/ccrcc/automil/config.yaml` (current) | `yaml.safe_load`, extend existing sections |
| `benchmarks/experiments/ccrcc/automil/variants/clam_mb/clam_mb_v0176.py` | `benchmarks/lib/CLAM/models/model_clam.py` (overlay in archive/node_0176) | Byte-identical body wrapped in ABC subclass |
| `benchmarks/experiments/ccrcc/automil/variants/_losses/ce_smooth008.py` | `benchmarks/lib/CLAM/utils/core_utils.py` (overlay) | Same |
| `benchmarks/experiments/ccrcc/automil/variants/_policies/sam_lookahead.py` | `benchmarks/lib/CLAM/utils/core_utils.py` + `benchmarks/src/autobench/pipeline/clam/train.py` (overlay) | Same |
| `benchmarks/src/autobench/pipeline/clam/train.py` (refactored) | current dirty-diff version in archive/node_0176 | Strip `args.model/loss/policy = literal`; read from registry via config |
| `src/automil/compat.py` (Phase 1 placeholder promoted) | `src/automil/compat.py` current | Promote TBD-Phase-1 entry per D-08 rule |

---

## Pattern catalog

### 1. CLI command file organization

**Reference:** `src/automil/cli/reconcile.py:1-79`, `src/automil/cli/control.py:1-34`, `src/automil/cli/propose.py:1-77`

**Pattern:** Every CLI file follows an identical structure:

```python
"""<verb> command: <one-line purpose>."""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir  # and/or _find_git_root


@main.command()
@click.option("--flag", is_flag=True, default=False, help="...")
def command_name(flag: bool):
    """<Short imperative docstring shown in --help>."""
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph   # lazy import — avoids circular
    ...
    click.echo("...")
```

Key rules:
- `from automil.cli import main` — all commands register on the same group object
- `from automil.cli._helpers import _find_automil_dir, _find_git_root` — never re-implement
- Lazy imports (`from automil.graph import ...` inside the function body) to avoid circular imports at module load time (`src/automil/cli/reconcile.py:39`, `src/automil/cli/propose.py:23`, `src/automil/cli/submit.py:235`)
- No `@click.pass_context` in existing commands; state is threaded via `_find_automil_dir()` return value
- `@main.command("hyphenated-name")` for commands with hyphens (`src/automil/cli/control.py:14`)
- Subgroups use `@main.group(name="...")` + `@<group>.command("...")` (`src/automil/cli/orchestrator.py:10-17`)

**Phase 1 application:** All 6 lifecycle commands in `cli/lifecycle.py` register on `main` using `@main.command("apply")`, `@main.command("revert-baseline")`, etc. `verify-repro` (if it lands in lifecycle.py) follows the same shape. The stub file already has `from __future__ import annotations` and the module docstring; Phase 1 just adds command functions below the existing comment.

---

### 2. Test fixture conventions

**Reference:** `tests/test_cli.py:14-37` (fixtures + `_init_git_repo`), `tests/test_orchestrator_env_whitelist.py:21-38` (module-level fixture)

**No conftest.py exists.** All fixtures are defined per-test-file. The canonical "fake project root" pattern is:

```python
# Fixture in test_cli.py (used by every TestXxx class)
@pytest.fixture
def cli_runner():
    return CliRunner()

# Local helper (not a fixture) to create a real git repo under tmp_path
def _init_git_repo(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)

# Usage in tests
def test_something(cli_runner, tmp_path, monkeypatch):
    _init_git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)          # make _find_automil_dir() walk from here
    cli_runner.invoke(main, ["init"])     # populate automil/ skeleton
    ...
```

**Lightweight skeleton (no full git repo needed):** For orchestrator/graph tests that don't run git commands (`tests/test_orchestrator_env_whitelist.py:21-38`):

```python
@pytest.fixture
def orch(tmp_path, monkeypatch):
    automil_dir = tmp_path / "automil"
    automil_dir.mkdir()
    (automil_dir / "config.yaml").write_text("orchestrator: {}\nenv:\n  passthrough: [MY_VAR]\n")
    (tmp_path / ".git").mkdir()          # fake .git dir is enough for _find_git_root()
    monkeypatch.setenv("MY_VAR", "value")
    return ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)
```

**graph.json mock pattern** (`tests/test_recompute_best.py:26-58`):

```python
def _make_graph(graph_dir: Path, nodes: list[dict]) -> ExperimentGraph:
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / "graph.json"
    data = {
        "schema_version": 1,
        "meta": {"best_composite": 0.0, "best_node_id": None, ...},
        "nodes": {},
        "technique_stats": {},
    }
    for n in nodes:
        data["nodes"][n["id"]] = {
            "id": n["id"], "type": n["type"], "status": n["status"],
            "composite": n.get("composite", 0.0), ...
        }
    path.write_text(json.dumps(data, indent=2))
    return ExperimentGraph.load(path)
```

**Phase 1 application:** Registry tests should follow the lightweight skeleton (fake `.git` dir + minimal `config.yaml`). For `variants/` directory layout, extend the minimal skeleton:
```python
automil_dir = tmp_path / "automil"
variants_dir = automil_dir / "variants"
(variants_dir / "clam_mb").mkdir(parents=True)
(variants_dir / "_losses").mkdir()
(variants_dir / "_policies").mkdir()
```
Use `monkeypatch.setattr(registry_module, "MODEL_VARIANTS", {})` to isolate registry state between tests (prevents cross-test pollution from the module-level singleton — see D-47, "monkeypatch.setattr(registry, ...) pattern").

---

### 3. Atomic write patterns

**Reference:** `src/automil/graph.py:787-801` (ExperimentGraph.save)

```python
def save(self):
    self.path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(self.path.parent), suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(self._data, f, indent=2)
            f.write("\n")
        os.rename(tmp_path, str(self.path))
        os.utime(str(self.path))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
```

Rules extracted:
1. `tempfile.mkstemp(dir=<same_dir>, suffix=".tmp")` — temp file must be on same filesystem as target so `os.rename` is atomic
2. `os.fdopen(tmp_fd, "w")` — take ownership of the fd immediately
3. `os.rename(tmp_path, str(self.path))` — POSIX atomic rename
4. Cleanup on exception: `os.unlink(tmp_path)` in the `except` block
5. `os.utime` call after rename — ensures mtime is updated (used by `check`'s stale-manifest detection in D-40)

**Phase 1 application:**
- `apply` command config edit (`automil/config.yaml`): same pattern; write to `config.yaml.tmp` in the same dir, rename.
- `port-variant` manifest write (`<name>.json`): same pattern.
- `refresh-registry` `__init__.py` regeneration: same pattern (write `__init__.py.tmp`, rename).
- `verify-repro` manifest write (`repro_manifest.yaml`): same pattern.

---

### 4. Subprocess invocation patterns

**Reference:** `src/automil/orchestrator.py:229-251` (`query_gpus`), `src/automil/orchestrator.py:583-660` (`_launch`), `src/automil/runner.py:29-35` (`create_worktree`)

**`query_gpus` — simple subprocess.run for reading:**
```python
result = subprocess.run(
    [NVIDIA_SMI_PATH, "--query-gpu=...", "--format=csv,noheader,nounits"],
    capture_output=True,
    text=True,
    timeout=10,
)
```

**`Runner.create_worktree` — subprocess.run with check=True:**
```python
subprocess.run(
    ["git", "worktree", "add", "--detach", str(wt_path), base_commit],
    cwd=self.project_root,
    capture_output=True,
    check=True,
)
```

**`_launch` — Popen for long-running processes:**
```python
process = subprocess.Popen(
    cmd,
    cwd=str(wt_path),
    stdout=log_fh,
    stderr=subprocess.STDOUT,
    env=env,
    start_new_session=True,    # detach from parent's process group
)
```

**Key rules:**
- Always pass `cwd=` explicitly; never rely on implicit cwd
- `capture_output=True` for reads; `start_new_session=True` for daemons
- `check=True` for short commands where failure is fatal; wrap in `try/except subprocess.CalledProcessError` for recoverable failures (`runner.py:82-85`)
- Path to executable comes from a module-level resolved constant (`NVIDIA_SMI_PATH`), never hardcoded bare strings for system tools

**Phase 1 application — `revert-baseline` invokes `git checkout`:**
```python
result = subprocess.run(
    ["git", "checkout", base_commit, "--", *paths],
    cwd=git_root,
    capture_output=True,
    text=True,
    check=True,
)
```
Per D-42, stash first (`git stash push --include-untracked -m "automil-revert-<timestamp>"`), then checkout. The stash call also uses `subprocess.run(..., check=True, cwd=git_root)`.

---

### 5. Config loading patterns

**Reference:** `src/automil/cli/check.py:28-29`, `src/automil/cli/submit.py:119-121`, `src/automil/orchestrator.py:307-321`

**Standard pattern (CLI commands):**
```python
config_path = adir / "config.yaml"
config: dict = {}
if config_path.exists():
    config = yaml.safe_load(config_path.read_text()) or {}
```

**Nested key access with defaults (from check.py:33, submit.py:119, orchestrator.py:307-321):**
```python
# Always use .get() with a fallback; never trust the YAML has a key
run_script = config.get("run", {}).get("script") or "train.py"
readonly = set(config.get("files", {}).get("readonly", []))
env_cfg = config.get("env") or {}
passthrough = env_cfg.get("passthrough", []) or []
```

**No Pydantic:** The entire codebase uses plain `dict` + `.get()` chains; no schema validation layer exists yet in the framework. Phase 1 must continue this pattern — do NOT introduce Pydantic for `config.yaml` reads.

**Phase 1 application — new registry keys:**
```python
registry_cfg = config.get("registry") or {}
protected = registry_cfg.get("protected", [])      # list of glob strings
mode = registry_cfg.get("mode", "free")             # "free" | "architecture-preserving"
repro_tolerance = registry_cfg.get("repro_tolerance", 0.005)  # float
# Variant selection
model_cfg = config.get("model") or {}
model_variant = model_cfg.get("variant")            # "clam_mb_v0176"
model_parent = model_cfg.get("parent")              # "clam_mb"
```
These are additive reads; existing keys are not touched. An old config.yaml without `registry:` returns empty dict → all defaults apply. This preserves the "automil init produces a valid config" invariant.

---

### 6. Path validation patterns

**Reference:** `src/automil/cli/submit.py:177-192`

```python
for f in file_list:
    # 1. Reject absolute paths and .. components
    if os.path.isabs(f) or ".." in Path(f).parts:
        raise click.ClickException(f"Invalid path (must be relative, no ..): {f}")
    src = git_root / f
    if not src.exists():
        deletions.append(f)
        continue
    # 2. Verify resolved path stays inside git root (catches symlinks)
    try:
        src.resolve().relative_to(git_root.resolve())
    except ValueError:
        raise click.ClickException(f"Path escapes repository root: {f}")
```

**Protected-files glob matching (from `_helpers.py:41-58`):**
```python
def _matches_scope(path: str, patterns: list[str] | set[str]) -> bool:
    rel_path = Path(path).as_posix()
    for raw_pattern in patterns:
        pattern = str(raw_pattern).strip().replace("\\", "/")
        if not pattern:
            continue
        if pattern.endswith("/"):
            if rel_path.startswith(pattern):
                return True
            continue
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False
```

**Phase 1 application — protected-files enforcement in `submit`:**
The submit pre-validator calls `_matches_scope(f, protected)` for each file in `file_list`. On match, raise `click.ClickException` with exit code 2 (Click's default for `ClickException`). Use the existing `_matches_scope` helper verbatim — do NOT re-implement. Import from `automil.cli._helpers`.

For `automil check` protected-files check: call `git status --porcelain <path>` via `subprocess.run(["git", "status", "--porcelain", "--", *protected_paths], ...)` and parse output for dirty entries (staged OR unstaged both count per D-34).

---

### 7. Error/exit code conventions

**Reference:** `src/automil/cli/submit.py:55-58`, `src/automil/cli/check.py:27`, `src/automil/cli/propose.py:63-68`

**Exit codes:**
- `0` — success (Click default)
- `1` — `raise click.ClickException("message")` — Click raises SystemExit(1) automatically
- `2` — Click validation errors (wrong arg types, missing required options) — Click raises SystemExit(2) automatically

There is no explicit `sys.exit(2)` in the codebase; Click's own validation uses exit 2 naturally. The convention in this codebase is: **all application-level errors use `raise click.ClickException("message")`** — never `sys.exit()` directly, never `raise SystemExit()`.

**Error message format (from submit.py, propose.py):**
```
Refusing to submit: <node_id> is already <type>/<status>. <one-sentence explanation>. <suggestion for what to do instead>.
```
Pattern: `"Refusing to <verb>: <what>. <why>. <how-to-fix>."` — always includes the corrective action.

**Output format for check.py:**
```python
issues = []
warnings = []
# ... accumulate into lists ...
if issues:
    click.echo("\nISSUES (must fix):")
    for i, issue in enumerate(issues, 1):
        click.echo(f"  {i}. {issue}")
if warnings:
    click.echo("\nWARNINGS:")
    for i, w in enumerate(warnings, 1):
        click.echo(f"  {i}. {w}")
```
Phase 1 check extensions follow this exact pattern: add items to `issues` (hard failures) or `warnings` (soft) lists, then the existing report block at the bottom handles display.

---

### 8. Click command patterns

**Reference:** `src/automil/cli/reconcile.py:16-29`, `src/automil/cli/submit.py:18-29`, `src/automil/cli/control.py:13-19`

**Option style:**
```python
@main.command()
@click.option("--node", required=True, help="Node ID (e.g., node_0042)")       # required string
@click.option("--files", multiple=True, help="Files to snapshot ...")           # multiple
@click.option("--recompute-best", is_flag=True, default=False, help="...")      # bool flag
@click.option("--dry-run", is_flag=True, default=False, help="...")             # bool flag
@click.option("--priority", default=1, help="Priority (lower = higher)")        # int with default
@click.option("--vram", default=0.5, help="Estimated VRAM in GB")               # float with default
def command_name(node: str, files: tuple, recompute_best: bool, ...):
    """Short imperative docstring — first sentence only, ends with period."""
```

**Rules:**
- Options preferred over arguments (except `init` which takes a path argument)
- `required=True` only for options that have no reasonable default
- Help strings: short, lowercase, no period at end (unlike the function docstring which ends with `.`)
- No `@click.pass_context` in existing single-level commands
- Hyphenated option names auto-converted to underscores in Python params (`--recompute-best` → `recompute_best`)
- `click.echo()` for all output — never `print()` anywhere in `cli/`

**Phase 1 application:**
- `automil apply <node_id>` — `@click.argument("node_id")` since it is positional and required (matches the spirit of `init`'s path argument)
- `automil port-variant <node_id>` — same; with `@click.option("--name")` and `@click.option("--kind", type=click.Choice(["model","loss","policy"]))` as optional overrides
- `automil promote-variant <node_id>` — argument style
- `automil refresh-registry` — no required args; optional `@click.option("--path")` for non-default variants dir
- `automil verify-repro <node_id>` — argument style
- `automil revert-baseline` — no args (operates on protected paths from config)

---

### 9. Logger usage

**Reference:** `src/automil/graph.py:18`, `src/automil/orchestrator.py:68`

```python
logger = logging.getLogger(__name__)
```

Module-level singleton, named after `__name__`. Both the 680-line `graph.py` and the 750-line `orchestrator.py` use exactly this one line. No handler configuration — loggers emit to whatever the root handler is (the CLI does not configure basicConfig; the orchestrator daemon does not either).

**Log levels used:**
- `logger.info(...)` — resolved paths, normal operational events (`orchestrator.py:82`)
- `logger.warning(...)` — degraded-but-functional situations (`orchestrator.py:85`, `orchestrator.py:324`)
- `logger.error(...)` — failures that affect an individual experiment but not the daemon (`orchestrator.py:602`, `:657`)

**Phase 1 application:** Every new module (`src/automil/registry/__init__.py`, validators, lifecycle.py) gets:
```python
logger = logging.getLogger(__name__)
```
as its first non-import line. Log `info` for registry population events (`Registered model variant 'clam_mb_v0176'`), `warning` for missing optional config keys, `error` for validator failures that produce a result.json with `status: "validation_failed"`.

---

### 10. The compat.py promotion mechanism

**Reference:** `src/automil/compat.py:85-113`

Current `_PLANNED_MIGRATIONS` has a placeholder:
```python
"TBD-Phase-1": {
    "new_path": "TBD-Phase-1",
    "owning_phase": 1,
    "rationale": "Placeholder for the Phase 1 registry-layer relocation. ...",
},
```

**D-08 promotion rule:** When Phase 1 relocates an existing name (old dotted path → new dotted path), the plan that performs the move must:
1. Add a live re-export shim in the Active section using `__getattr__` (PEP 562) that emits `warnings.warn(_DEPRECATION_MESSAGE_FORMAT.format(...), DeprecationWarning, stacklevel=2)`
2. Remove the corresponding entry from `_PLANNED_MIGRATIONS` in the same commit

**Phase 1 application (D-07/D-08 from 01-CONTEXT.md):** Phase 1 adds new modules (`src/automil/registry/`) without relocating any existing name. The `TBD-Phase-1` placeholder entry should be updated to reflect the concrete registry path layout (new_path = `automil.registry`), or removed and replaced with the Phase 2 backend entry if no name actually moves in Phase 1. Per D-48 (Phase 1 currently relocates none), the TBD entry gets its concrete path filled in (`new_path: "automil.registry"`, `rationale: "Registry singleton is a new module; no relocation occurs in Phase 1. Entry retained for phase bookkeeping."`) — this is a documentation-only change to compat.py, not a live shim addition.

**Test coverage:** `tests/test_compat.py:37-39` asserts `any(v["owning_phase"] == 1 for v in _PLANNED_MIGRATIONS.values())` — Phase 1 must not leave this assertion failing by deleting the Phase 1 entry without a replacement.

---

## Shared Patterns

### Authentication / Authorization
**Source:** N/A — no auth layer exists in this codebase  
**Apply to:** Not applicable for Phase 1

### Error Handling (submit hard-fail)
**Source:** `src/automil/cli/submit.py:55-68`  
**Apply to:** All pre-validator checks in submit (protected-files enforcement), all lifecycle commands  
```python
raise click.ClickException(
    f"Refusing to submit: {node} is already {ntype}/{nstatus}. "
    f"Submitting would overwrite its archive and destroy prior results. "
    f"Use 'automil propose' to create a new proposal."
)
```
Always includes: what failed, why it failed, what to do instead.

### Atomic file write
**Source:** `src/automil/graph.py:787-801`  
**Apply to:** `apply` (config.yaml edit), `port-variant` (manifest write), `refresh-registry` (__init__.py write), `verify-repro` (repro_manifest.yaml write)  
```python
tmp_fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
try:
    with os.fdopen(tmp_fd, "w") as f:
        f.write(content)
    os.rename(tmp_path, str(target))
    os.utime(str(target))
except Exception:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    raise
```

### Config loading
**Source:** `src/automil/cli/check.py:28-29`, `src/automil/cli/submit.py:119-121`  
**Apply to:** All lifecycle commands that read `registry.*` from config  
```python
adir = _find_automil_dir()
config_path = adir / "config.yaml"
config: dict = {}
if config_path.exists():
    config = yaml.safe_load(config_path.read_text()) or {}
registry_cfg = config.get("registry") or {}
```

### Path matching (protected files)
**Source:** `src/automil/cli/_helpers.py:41-58` (`_matches_scope`)  
**Apply to:** `submit` protected-files pre-validator, `check` protected-files status check  
Import `_matches_scope` from `automil.cli._helpers` — do not re-implement.

---

## Overlay manifest shape (for port-variant)

The `spec.json` in `archive/node_0176` (`benchmarks/experiments/ccrcc/automil/orchestrator/archive/node_0176/spec.json`) shows the exact field that `port-variant` reads to know what files the overlay touched:

```json
{
  "overlay_manifest": {
    "benchmarks/lib/CLAM/utils/core_utils.py": "sha256:...",
    "benchmarks/src/autobench/pipeline/clam/train.py": "sha256:...",
    "benchmarks/scripts/run_experiment.py": "sha256:...",
    "benchmarks/lib/CLAM/models/model_clam.py": "sha256:..."
  },
  "deletions": []
}
```

`port-variant` reads `adir / "orchestrator" / "archive" / node_id / "spec.json"`, extracts `overlay_manifest.keys()`, and cross-references against `registry.protected` to determine kind. The `base_commit` field in the spec becomes `VariantSpec.base_commit`.

Node `node_0176` has `composite: 0.8074` in `graph.json` — this is `VariantSpec.composite` at port time.

---

## Anti-patterns to avoid

1. **Re-implementing `_find_automil_dir` or `_find_git_root`** — these helpers exist in `cli/_helpers.py`. Lifecycle commands import them from there; registry and validators should receive paths as constructor arguments, not walk the filesystem themselves. If the registry needs git-root access, pass it in from the CLI layer (D-02 lift to `automil/paths.py` deferred to Phase 1 or 2 if needed).

2. **`env = {**os.environ, ...}` in any subprocess call** — this was the CLN-02 HIGH severity concern fixed in Phase 0. All subprocess env construction goes through `_build_subprocess_env` or a whitelist-based equivalent. `verify-repro` which calls the orchestrator's worktree mechanism should reuse the existing `_launch` path, not build its own env dict.

3. **`graph.json` writes that bypass `ExperimentGraph.save()`** — the atomic tempfile+rename in `save()` is the only sanctioned write path. From Phase 0 CONTEXT.md: "The `--recompute-best`'s write must call `ExperimentGraph.save()`, not bypass it." Same applies to any Phase 1 command that touches graph state.

4. **`os.environ.setitem` instead of `os.environ.setdefault`** — the `.env` loader uses `setdefault` to not override existing vars. Any Phase 1 code that propagates env vars must follow the same semantics.

5. **Mutable `VariantSpec` fields** — `VariantSpec` is `@dataclass(frozen=True)` (D-22). Do not add any mutable field or try to `__setattr__` after construction.

6. **Hardcoding `benchmarks/` paths in `src/automil/`** — "autoMIL is generic" memory + D-33: the framework ships zero protected-file defaults. All paths come from the consumer's `config.yaml`. Any `src/automil/registry/` or `src/automil/cli/lifecycle.py` code that references `benchmarks/` is a defect.

7. **Soft-warn substituting for required validators** — D-32: interface and purity validators are hard-fail at submit time. Printing a warning and continuing would defeat Pitfall 1 ("still uses old path"). The `check=False` / "warn only" pattern is only for `automil check`'s reproduction manifest warning (D-40).

8. **`click.pass_context` for shared state** — no existing command uses it. Thread state through `_find_automil_dir()` return values and local variables.

9. **`print()` instead of `click.echo()`** — all CLI output uses `click.echo()`. The orchestrator daemon uses `print()` for its status output (cmd_start/cmd_stop are interactive; not click commands), but CLI commands never use `print()`.

10. **Triggering `_recover_orphans` outside the daemon loop** — from Phase 0 CONTEXT.md: "`_recover_orphans()` only runs in the daemon loop (`run()`), never on construction." `verify-repro` must not instantiate `ExperimentOrchestrator` with `recover=True` or call `_recover_orphans` directly.

---

## Open codebase questions for the planner

1. **`cli/_helpers.py` lift to `automil/paths.py`:** D-02 deferred this to Phase 1 if registry/validators need git-root access. The registry validators receive a file path argument from the CLI layer; they do NOT need to walk the filesystem. If the planner decides validators stay stateless (path passed in), the lift is unnecessary and `_helpers.py` stays CLI-private. If validators need to locate the project root independently (e.g., for identity validator's worktree stub forward), then lift to `automil/paths.py` in the registry plan's first commit.

2. **`verify-repro` placement:** D-39 says it is a new CLI command. `lifecycle.py` is the natural home per D-01. However, `verify-repro` orchestrates a full experiment run (worktree + subprocess). The planner must decide whether it wraps `ExperimentOrchestrator._launch` directly (reusing all env/worktree machinery) or goes through the queue + daemon path (submit → orchestrator runs it → result). The queue path is safer (existing code path) but requires the orchestrator daemon to be running; the direct-launch path is simpler but duplicates `_launch` logic.

3. **Registry singleton isolation in tests:** The module-level `MODEL_VARIANTS`, `LOSS_VARIANTS`, `POLICY_VARIANTS` dicts are populated as a side-effect of importing variant modules. Tests that import and run `refresh-registry` or `@register` will pollute the singleton across test functions. The planner must add a pytest fixture that clears the registry dicts before each test, using `monkeypatch.setattr` or a `Registry.clear()` classmethod. This is a "Claude's Discretion" item per D-47 but the planner needs to specify the fixture so all registry test files are consistent.

4. **`compat.py` TBD-Phase-1 entry:** The test `tests/test_compat.py:37-39` asserts at least one Phase 1 entry exists in `_PLANNED_MIGRATIONS`. Phase 1 adds new modules without relocating names. The planner must decide: (a) update the TBD entry to reflect the concrete registry path with `rationale` explaining no relocation occurs, keeping the assertion green; or (b) delete the TBD entry and add a new entry forecasting a future relocation (Phase 5+ when `recipe` variants arrive). Option (a) is simpler and keeps the test green with minimal compat.py churn.

5. **`train.py` import of registry at startup:** The CCRCC `train.py` refactor needs to call `importlib.import_module` on variant modules before the registry singleton is populated. The planner must specify where in `train.py`'s startup sequence `refresh-registry` is triggered (or equivalently, where the variants directory `__init__.py` is imported). The simplest pattern is: `train.py` calls `importlib.import_module("path.to.variants.clam_mb")` (or the generated `__init__.py`) at the top of its `main()`, before model construction, so all `@register` decorators run. This avoids a subprocess call to `automil refresh-registry` inside the training script.

---

## Metadata

**Analog search scope:** `src/automil/cli/`, `src/automil/graph.py`, `src/automil/orchestrator.py`, `src/automil/runner.py`, `src/automil/compat.py`, `tests/`, `benchmarks/experiments/ccrcc/automil/`
**Files scanned:** 18 source files + 10 test files
**Pattern extraction date:** 2026-05-01
