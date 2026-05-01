# Coding Conventions

**Analysis Date:** 2026-04-30

## Naming Patterns

**Files:**
- Source modules: lowercase `snake_case.py` (e.g. `graph.py`, `runner.py`, `orchestrator.py`).
- Test files: `test_<module>.py` mirroring the module under test (`tests/test_graph.py`, `tests/test_runner.py`).
- Templates: `<name>.<ext>.j2` (Jinja2). See `src/automil/templates/config.yaml.j2`, `program.md.j2`, `learnings.md.j2`, `.gitignore.j2`.
- Per-dataset benchmark configs: `benchmarks/datasets/<name>.yaml`.
- Runtime artifacts: `graph.json`, `results.tsv`, the `orchestrator/` subtree — gitignored inside each project (see `src/automil/templates/.gitignore.j2`).

**Modules / packages:**
- Top-level packages live under `src/<package>/` (`src/automil/`, `benchmarks/src/autobench/`).
- Sub-packages use plain lowercase names (`autobench/pipeline/`, `autobench/encoders/`, `automil/viz/`).

**Functions / methods:**
- Public functions: `snake_case` (e.g. `add_executed`, `mark_running`, `apply_overlay`).
- Private helpers: leading underscore (e.g. `_find_automil_dir`, `_find_git_root`, `_matches_scope`, `_update_technique_stats`, `_extract_techniques`).
- Classmethod factories: `load`, `import_from_tsv`, `compute_config_hash` on `ExperimentGraph` in `src/automil/graph.py:59,670,363`.

**Variables:**
- Locals and attributes: `snake_case`.
- Module-level constants: `UPPER_SNAKE_CASE` (e.g. `POLL_INTERVAL_SEC`, `SAFETY_MARGIN_GB`, `DEFAULT_TIMEOUT_MIN`, `MAX_CONCURRENT_PER_GPU` in `src/automil/orchestrator.py:33-40`).
- Class-level "constant" maps live as `DEFAULT_*` class attributes (`ExperimentGraph.DEFAULT_TECHNIQUE_MAP` at `src/automil/graph.py:19`).

**Classes / types:**
- `PascalCase` (e.g. `ExperimentGraph`, `Runner`, `GPUInfo`, `BenchmarkConfig`, `DatasetConfig`, `TaskDef`).
- Test classes: `TestSomeBehavior` grouped per concern (`TestGraphBasics`, `TestNodeLifecycle`, `TestScoring`, `TestPersistence`, `TestReconciliation`, `TestMigration`, `TestEndToEnd`, `TestSubmit`, `TestPropose`, `TestRank`, ...).

## Code Style

**Python version:** Both packages declare `requires-python = ">=3.10"` (see `pyproject.toml:11` and `benchmarks/pyproject.toml:9`). PEP 604 union syntax (`str | Path`, `dict | None`) is used throughout — do **not** import `Optional`/`Union`.

**Future imports:** All non-trivial modules begin with `from __future__ import annotations` (`src/automil/cli.py:3`, `src/automil/graph.py:5`, `src/automil/runner.py:3`, `src/automil/orchestrator.py:14`). Add this on every new module.

**Type hints:**
- Annotate every public function signature and dataclass field.
- Use built-in generics (`list[str]`, `dict[str, str]`, `tuple[int, ...]`) — not `typing.List` etc.
- Allow `None` via `X | None` with a default of `None`.
- Example signatures from `src/automil/graph.py`:

```python
# src/automil/graph.py:32
def __init__(self, path: str | Path,
             technique_map: dict[str, list[str]] | None = None,
             data: dict | None = None):

# src/automil/graph.py:109
def add_executed(self, parent_id: str | None, description: str,
                 techniques: list[str], metrics: dict,
                 status: str = "discard", commit: str | None = None,
                 config_hash: str | None = None,
                 bootstrapped: bool = False) -> str:
```

**Formatter / linter:**
- No `ruff`, `black`, `flake8`, `mypy`, `setup.cfg`, `.pre-commit-config.yaml`, or `pytest.ini` are present at repo root.
- Style is enforced by convention only — match the surrounding file. Indentation is 4 spaces; lines wrap pragmatically around ~100 chars (some signatures and comments run to ~88-100; no hard column limit is enforced).
- Strings: use double quotes consistently (matches existing source — see `src/automil/cli.py`, `src/automil/graph.py`).

**Docstrings:**
- One-line module docstring on every module: `"""Brief purpose."""` (e.g. `src/automil/graph.py:1`, `src/automil/runner.py:1`, `src/automil/cli.py:1`).
- Function/method docstrings: short imperative summary; longer notes wrapped after a blank line. Triple double-quotes. Example at `src/automil/runner.py:37`:

```python
def apply_overlay(self, worktree_path: Path, overlay_dir: Path,
                  deletions: list[str] | None = None) -> None:
    """Copy modified files from overlay_dir on top of worktree.

    Also removes files listed in `deletions` from the worktree to support
    experiments that delete or rename files.
    """
```

## Import Organization

**Order (standard, observed in `src/automil/cli.py:1-15` and `src/automil/orchestrator.py:14-28`):**
1. Module docstring.
2. `from __future__ import annotations`.
3. Standard library imports (alphabetised within group; `import x` before `from x import y` is mixed but generally ordered by package name).
4. Blank line, then third-party imports (`click`, `yaml`, `pytest`, `torch`, `pandas`, `h5py`, `numpy`, `aiohttp`, `jinja2`).
5. Blank line, then first-party imports (`from automil.runner import Runner`, `from autobench.config import DatasetConfig`).

**Local / lazy imports:** Heavy or optional deps are imported inside the function that needs them (e.g. `from jinja2 import Environment, FileSystemLoader` inside `init()` at `src/automil/cli.py:79`; `import hashlib` inside `submit()` at `src/automil/cli.py:200`). Tests use `pytest.importorskip("torch")` (`benchmarks/tests/test_benchmark_integration.py:15`, `test_benchmark_train.py:9`) so the suite still runs without GPU dependencies.

**Path aliases:** None. Use absolute package imports (`from automil.X import Y`, `from autobench.pipeline.X import Y`).

## Error Handling

**CLI surface (`src/automil/cli.py`):** All user-visible errors raise `click.ClickException` with a precise message. Click prints the message and exits non-zero automatically. Examples:

```python
# src/automil/cli.py:225
raise click.ClickException(
    f"Refusing to submit: {node} is already {ntype}/{nstatus}. "
    f"Submitting would overwrite its archive and destroy prior "
    f"results. Use 'automil propose' to create a new proposal, "
    f"then submit against that new node id."
)
```

```python
# src/automil/cli.py:333
if not file_list:
    raise click.ClickException("No changed files to snapshot")
```

**Library / daemon code:** Use `RuntimeError` for unrecoverable invariants (`src/automil/orchestrator.py:52`, `src/automil/orchestrator.py:64`). Use `assert` only for internal state-machine invariants (e.g. `src/automil/graph.py:186` enforcing `proposed/pending` before `mark_running`).

**Subprocess errors:** Use `subprocess.run(..., capture_output=True, check=True)` and let `CalledProcessError` propagate (e.g. `src/automil/runner.py:29-34`). Where graceful degradation is needed, wrap in `try/except subprocess.CalledProcessError` and fall back (`src/automil/runner.py:74-86`).

**JSON I/O:** Tolerate corrupt/missing graph state with `try/except (json.JSONDecodeError, OSError)` (`src/automil/cli.py:214-217`).

## Path-Validation Invariants

Enforced inside `submit` at `src/automil/cli.py:347-365`:

```python
for f in file_list:
    # Reject absolute paths and directory traversal
    if os.path.isabs(f) or ".." in Path(f).parts:
        raise click.ClickException(f"Invalid path (must be relative, no ..): {f}")
    src = git_root / f
    if not src.exists():
        deletions.append(f)
        continue
    # Verify resolved path is inside the git root
    try:
        src.resolve().relative_to(git_root.resolve())
    except ValueError:
        raise click.ClickException(...)
```

Rules to preserve when modifying CLI input handling:
- Reject absolute paths.
- Reject any segment equal to `..`.
- After resolving symlinks, the path **must** be a descendant of the git root (use `Path.resolve().relative_to(git_root.resolve())`).
- Auto-detect mode (no `--files` given) excludes the `automil/` prefix and `.claude/` from changed files (`src/automil/cli.py:316-319`) so framework state never leaks into experiment overlays. The exact prefix is computed via `adir.resolve().relative_to(git_root.resolve()).as_posix() + "/"` (`src/automil/cli.py:280-282`).

## Project Discovery

`_find_automil_dir()` and `_find_git_root()` walk up from `cwd` until they find `automil/config.yaml` and `.git/` respectively (`src/automil/cli.py:18-43`, mirrored in `src/automil/orchestrator.py:45-64`). Anything that needs the project root must use one of these helpers — do not hardcode `Path.cwd()`.

## Gitignored Runtime-File Rule

The init-time `.gitignore` template (`src/automil/templates/.gitignore.j2`, rendered into `automil/.gitignore`) enforces that the following live only on disk and never in git:

- `graph.json` — experiment tree state, written by the framework.
- `results.tsv` — written **solely by the orchestrator** from per-experiment `result.json` (never by `train.py`).
- `orchestrator/` — the entire `queue/`, `running/`, `completed/`, `archive/` subtree.

Validated by `tests/test_cli.py::TestInit::test_gitignore_excludes_runtime` (`tests/test_cli.py:90-100`). Do not commit any of these files in user projects, and do not write `results.tsv` from training scripts.

## CLI Conventions (Click)

- Single root group declared with `@click.group()` returning `main()` at `src/automil/cli.py:67-70`. Subcommands decorated with `@main.command()`.
- Every option uses kebab-case on the wire (`--node`, `--desc`, `--files`, `--parent`, `--techniques`) and snake_case in the function signature.
- Option help strings are short imperative phrases (`"Node ID (e.g., node_0042)"`, `"Files to snapshot (auto-detect if omitted)"` at `src/automil/cli.py:189-196`).
- `multiple=True` is used for repeatable options (`--files`, `--techniques`).
- User-facing logs use `click.echo(...)`. `print()` is reserved for daemon stdout in the orchestrator (which is also captured to `orchestrator.log`).
- Entry point is registered in `pyproject.toml:30` as `automil = "automil.cli:main"`.

## Function Design

- Prefer small focused helpers; extract guards into named `_helper()` functions when they exceed a few lines (e.g. `_matches_scope`, `_find_automil_dir`).
- Methods on `ExperimentGraph` are deliberately ordered by lifecycle: ID generation → reading → writing → scoring → reconciliation → migration → persistence (see grouping comments in `src/automil/graph.py:74,80,108,303,405,670,740`).
- Use module-level dataclasses for record-like structs (`@dataclass class GPUInfo:` at `src/automil/orchestrator.py:70-79`); add `@property` methods for derived values rather than recomputing inline.

## Module Design

- Public surface is whatever is not underscore-prefixed; no `__all__` is declared.
- No barrel `__init__.py` re-exports — import directly from the submodule (`from automil.graph import ExperimentGraph`, `from automil.runner import Runner`).
- Per-package `__init__.py` is intentionally minimal (`src/automil/__init__.py` is 3 lines).

## Comments

- Use comments to record invariants and gotchas (e.g. the long block at `src/automil/cli.py:241-247` documenting why `submit` must refuse `proposed` parents). Reference node IDs / git history in comments where it helps a future reader.
- Ban temporal language ("formerly", "we used to") — describe current state.
- Section dividers are encoded as `# ---------------------------------------------------------------------------` (see `src/automil/orchestrator.py:30-32`, `benchmarks/tests/test_benchmark_integration.py:37-39`).

## Result Contract (Training Scripts)

Training scripts must write `result.json` to their working directory with exactly this shape (consumed by `runner.collect_result` and the orchestrator):

```json
{
  "status": "completed",
  "metrics": {"val_auc": 0.87, "val_bacc": 0.81, "test_auc": 0.87, "test_bacc": 0.83},
  "composite": 0.85,
  "elapsed_seconds": 4098,
  "peak_vram_mb": 4500
}
```

The orchestrator sets `CUDA_VISIBLE_DEVICES` for GPU masking and `AUTOMIL_GPU=0` (logical device). Training scripts never write `results.tsv` — only the orchestrator does, from `result.json`.

## Conventional-Commit Policy

Commit messages follow `type(scope): summary` (lowercase, imperative). Verified scopes / types from recent history (`git log --pretty=format:"%s"`):

```text
feat(viz): overlay live running status and stabilize 3D layout
test(graph): cover reconcile zombie sweep
feat(graph): cancel stale proposals in reconcile zombie sweep
test(cli): cover submit parent guards and propose dedup
feat(cli): guard submit parents and refuse duplicate proposals
feat(orchestrator): saturate GPUs by default and hot-reload config
fix(autobench): honor AUTOBENCH_ROOT for worktree-local imports
chore(viz): vendor d3, three, three-spritetext, 3d-force-graph
docs(ccrcc): add .env setup step and log parallel-batch results
```

**Allowed types observed:** `feat`, `fix`, `test`, `docs`, `chore`, `refactor`. **Allowed scopes observed:** `cli`, `graph`, `orchestrator`, `runner`, `viz`, `autobench`, `benchmarks`, `clam`, `ccrcc`. Use the most specific scope that matches the changed files.

Rules:
- One logical change per commit.
- Use lower-case summary, no trailing period, ≤ ~70 chars.
- Reference node IDs (`node_0004`) when a commit corresponds to an experiment win.
- No "WIP" / "tmp" commits on `main`.

## Environment Variables (`.env`)

Per-dataset paths in `benchmarks/datasets/*.yaml` use `${AUTOBENCH_<DATASET>_ROOT}` placeholders. These are loaded from `benchmarks/.env` by the orchestrator and propagated into experiment subprocesses (see `feat(orchestrator): load .env files for worktree processes` in history). `.env` files are gitignored; never commit them and never read their contents in code that gets logged.

---

*Convention analysis: 2026-04-30*
