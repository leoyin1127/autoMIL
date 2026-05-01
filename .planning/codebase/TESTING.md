# Testing Patterns

**Analysis Date:** 2026-04-30

## Test Framework

**Runner:**
- `pytest >= 9.0.2` (declared in both `pyproject.toml:38-41` and `benchmarks/pyproject.toml:38-41` under `[dependency-groups] dev`).
- Configured per-package via `[tool.pytest.ini_options] testpaths = ["tests"]` in each `pyproject.toml` — so `pytest` from repo root picks up `tests/`, and `pytest` from `benchmarks/` picks up `benchmarks/tests/`.

**Assertion Library:**
- Plain `assert` (pytest's rewriting). `pytest.raises`, `pytest.approx`, `pytest.importorskip`, `pytest.fixture` from the pytest core. No `unittest`, no `hypothesis`.
- Mocking: only `unittest.mock` (`MagicMock`, `patch`) — used in `benchmarks/tests/test_gpu_worker.py:7`. The `automil` test suite avoids mocks entirely and uses real git repos under `tmp_path`.

**Run Commands:**
```bash
# Whole automil suite
uv run pytest tests/ -v

# Whole autobench suite
uv run pytest benchmarks/tests/ -v

# Single file
uv run pytest tests/test_graph.py -v

# Single test
uv run pytest tests/test_integration.py::TestEndToEnd::test_init_submit_flow -v

# Single class
uv run pytest tests/test_graph.py::TestReconciliation -v

# Match by keyword
uv run pytest tests/ -v -k "reconcile"

# With short tracebacks and stop-on-first-fail (handy during dev)
uv run pytest tests/ -x --tb=short
```

The benchmarks suite imports its `_helpers` via `sys.path.insert(0, os.path.dirname(__file__))` in `benchmarks/tests/conftest.py:9`, so always invoke pytest with `benchmarks/tests/` as the root (not arbitrary subpaths).

## Test File Organization

**Locations:**
- autoMIL framework tests: `tests/test_*.py` at the repo root.
- autobench package tests: `benchmarks/tests/test_*.py`.

**autoMIL files (48 tests total):**
| File | Lines | Tests | Coverage |
|------|------:|------:|----------|
| `tests/test_graph.py` | 489 | 26 | graph API, scoring, reconciliation, migration, multi-file config hash |
| `tests/test_runner.py` | 136 | 7 | worktree create/cleanup, overlay, deletion, result collection |
| `tests/test_cli.py` | 400 | 5+ | init, check, submit guards, propose dedup, rank |
| `tests/test_integration.py` | 240 | 10 | full init→submit→archive flow, deletions, propose+rank, start/stop |

**autobench files:** `benchmarks/tests/test_benchmark_*.py`, `test_config.py`, `test_data.py`, `test_encoders.py`, `test_gpu_worker.py`, `test_nnmil_prepare.py`, `test_openslide_pickle.py`, `test_run_feature_extraction.py`, `test_smmile_prepare.py`, `test_splits.py`, plus `_helpers.py` and `conftest.py`.

**Naming:**
- Files: `test_<module-under-test>.py`.
- Classes: `TestSomeBehavior` grouped by concern (e.g. `TestGraphBasics`, `TestNodeLifecycle`, `TestScoring`, `TestPersistence`, `TestReconciliation`, `TestMigration` in `tests/test_graph.py`).
- Methods: `test_<behavior_being_verified>` in snake_case (`test_proposed_to_running_to_executed`, `test_create_and_cleanup`, `test_submit_refuses_proposed_parent`).

## Test Structure

**Suite organisation (typical pattern from `tests/test_graph.py:10-35`):**

```python
class TestGraphBasics:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.graph_path = os.path.join(self.tmpdir, "graph.json")

    def test_create_empty_graph(self):
        g = ExperimentGraph(path=self.graph_path)
        assert g.meta["total_executed"] == 0
        assert g.meta["next_id"] == 1

    def test_add_root_executed(self):
        g = ExperimentGraph(path=self.graph_path)
        nid = g.add_executed(
            parent_id=None, description="baseline", techniques=[],
            metrics={"composite": 0.814, "test_auc": 0.836, ...},
            status="keep",
        )
        assert nid == "node_0001"
```

Patterns:
- `setup_method` is used inside test classes for mutable, per-test state (writable `tmpdir`, a fresh `ExperimentGraph`). Newer tests (`TestNewFeatures` at `tests/test_graph.py:451`) prefer the `tmp_path` fixture instead.
- `pytest.fixture` is the default for autobench tests (e.g. `cli_runner` in `tests/test_cli.py:14-16`, `project_repo`/`runner` in `tests/test_runner.py:13-34`, `synthetic_benchmark` in `benchmarks/tests/test_benchmark_integration.py:42-111`).
- Each test asserts a single coherent behaviour and uses descriptive names that double as documentation.

## Filesystem Isolation

**`tmp_path` everywhere:** Every test that touches the filesystem uses pytest's per-test `tmp_path` fixture; nothing is created inside the repo. See `tests/test_integration.py:36`, `tests/test_cli.py:41`, `tests/test_runner.py:14`, `benchmarks/tests/test_benchmark_integration.py:42`.

**Working directory:** Tests that need the CLI to discover an `automil/` directory use `monkeypatch.chdir(tmp_path)` (`tests/test_cli.py:44`, `tests/test_integration.py:41`) — never call `os.chdir` directly.

**Git worktree fixtures:** Both the CLI and runner suites build a real, minimal git repo for every test via `_init_git_repo` (`tests/test_integration.py:14-32`, `tests/test_cli.py:19-37`) and the `project_repo` fixture (`tests/test_runner.py:13-29`). Each fixture sets local `user.name`/`user.email`, creates a dummy file, and commits so `HEAD` exists. Real `git init`, `git add`, `git commit`, `git worktree add` calls are made — there is no shimming of git.

**Click invocation:** CLI flows are exercised via `click.testing.CliRunner` (`tests/test_cli.py:9`, `tests/test_integration.py:9`). Always check `result.exit_code` and include `result.output` in the failure message:

```python
# tests/test_cli.py:46-47
result = cli_runner.invoke(main, ["init"])
assert result.exit_code == 0, result.output
```

When you want exceptions to propagate uncaught (for debugging), pass `catch_exceptions=False` to `invoke` (e.g. `tests/test_cli.py:157`).

## Mocking Style

**autoMIL framework tests (`tests/`):** No mocking. The suite is intentionally end-to-end — it spins up real git repos, real `ExperimentGraph` instances, and the real `Runner` against a real `git worktree`. This is fast enough because everything runs inside `tmp_path` and the operations are tiny.

**autobench tests (`benchmarks/tests/`):**
- Use `pytest.importorskip("torch")` at the top of any test that needs PyTorch (`benchmarks/tests/test_benchmark_integration.py:15`, `test_benchmark_train.py:9`). This lets the suite run on machines without GPU/torch deps.
- `unittest.mock.patch` / `MagicMock` are used to fake `nvidia-smi` subprocess output in `benchmarks/tests/test_gpu_worker.py:7,56,213`:

```python
# benchmarks/tests/test_gpu_worker.py:54-58
with patch(
    "subprocess.run",
    return_value=MagicMock(stdout=stdout, returncode=returncode),
):
    ...
```

- `monkeypatch.setattr` is used to replace heavy or environment-dependent functions (`benchmarks/tests/test_gpu_worker.py:507-515`).

**Rules of thumb:**
- For autoMIL framework code: prefer real filesystem + real git over mocks. The test suite runs in <5s and the realism catches integration bugs.
- For autobench: mock external commands (`nvidia-smi`) and skip-import expensive deps; use real synthetic data otherwise.

## Fixtures and Factories

**Shared dataset factory** at `benchmarks/tests/_helpers.py:6-79`:

```python
def make_test_ds(**kwargs):
    """Create a minimal DatasetConfig for testing.

    Mirrors the ovarian dataset structure with sensible defaults.
    Override any field via kwargs.
    """
    defaults = dict(
        name="test",
        data_root="/tmp/test",
        ...
    )
    defaults.update(kwargs)
    return DatasetConfig(**defaults)
```

Surfaced as a fixture in `benchmarks/tests/conftest.py:14-17`:

```python
@pytest.fixture
def test_ds():
    return make_test_ds()
```

**Autouse fixtures:** None. All fixtures are explicit.

**conftest scope:** Only `benchmarks/tests/conftest.py` exists; it injects `_helpers` onto `sys.path` and exposes `test_ds`. There is no top-level `conftest.py` for `tests/` — each file sets up what it needs.

**Fixture composition example** (`tests/test_runner.py:13-34`):

```python
@pytest.fixture
def project_repo(tmp_path):
    repo = tmp_path / "project"
    ...  # git init + initial commit
    return repo

@pytest.fixture
def runner(project_repo):
    return Runner(project_root=project_repo)
```

## Synthetic Data for Integration Tests

The autobench integration test (`benchmarks/tests/test_benchmark_integration.py:42-111`) builds a complete synthetic benchmark inside `tmp_path`:
- 30 fake slides with H5 features (dim=64) generated via seeded `numpy.random.RandomState`.
- A mapping CSV with binary BRCA labels (15 / 15 split).
- A `DatasetConfig` constructed via `make_test_ds(...)` overriding only the fields that matter.

This pattern (deterministic seeded synthetic data, on-disk H5/CSV, real `DatasetConfig`) is the template for any new integration test that touches the data pipeline.

## Test Types

**Unit (`tests/test_graph.py`, `tests/test_runner.py`):** Exercise one class / module against an in-memory or `tmp_path`-backed fixture. No CLI, no subprocess (other than git inside the runner tests).

**CLI / functional (`tests/test_cli.py`):** Drive the Click app via `CliRunner.invoke(main, [...])`, asserting both `exit_code` and `output`. Cover positive paths *and* every guard (e.g. `test_submit_refuses_proposed_parent`, `test_submit_refuses_unknown_parent`, `test_propose_refuses_exact_duplicate`).

**Integration (`tests/test_integration.py`, `benchmarks/tests/test_benchmark_integration.py`):** Full init → submit → archive verification, including queue spec contents (`tests/test_integration.py:74-81`), `start-loop`/`stop-loop` flag-file management (`tests/test_integration.py:227-240`), and a synthetic end-to-end CLAM mini-benchmark.

**Migration (`tests/test_graph.py::TestMigration`):** Verifies `ExperimentGraph.import_from_tsv` reconstructs the right tree from a legacy `results.tsv` + `strategies.json` pair.

**E2E (browser / dashboard):** None — the viz frontend (`src/automil/viz/static/app.js`) has no tests.

## Common Patterns

**Asserting on exception messages:** Combine `exit_code != 0` with a substring match against `result.output`:

```python
# tests/test_cli.py:246-247
assert result.exit_code != 0
assert "not been executed" in result.output or "type=proposed" in result.output
```

**Time-sensitive logic:** Manually back-date timestamps rather than mocking `datetime.now()`:

```python
# tests/test_graph.py:335
self.g.get_node(pid)["created_at"] = "2020-01-01T00:00:00"
self.g.reconcile(self.queue_dir, self.running_dir,
                 self.completed_dir, self.archive_dir)
```

**Subprocess git in fixtures:** Always pass `capture_output=True` and (where the test relies on success) `check=True`. Set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env vars in the runner fixture so the commit succeeds even when the host has no global git identity (`tests/test_runner.py:26-28`).

**Guarding uncaught surprises:** When the CLI is expected to succeed, pass `catch_exceptions=False` so any traceback surfaces directly in pytest output (`tests/test_cli.py:157,191,215,297,326,365,371,398`).

## What to Test for New Features

Follow the existing layout — for each new piece of `automil` functionality, add:
1. A focused unit test in `tests/test_<module>.py` exercising the new method against a `tmp_path` fixture.
2. A CLI guard test in `tests/test_cli.py` if it surfaces through the Click app.
3. An end-to-end test in `tests/test_integration.py` covering the user-visible flow.
4. If it touches reconciliation, scoring, or migration, also extend `tests/test_graph.py::TestReconciliation` / `TestScoring` / `TestMigration`.

## Coverage Notes

No coverage tooling (`coverage.py`, `pytest-cov`) is configured and no thresholds are enforced. Coverage is implicit: 48 framework tests covering `ExperimentGraph` (~680 LOC), `Runner` (~95 LOC), and the public CLI surface; autobench has another ~13 test files exercising config, splits, encoders, training, and GPU worker logic.

If you want a one-off coverage report:

```bash
uv run pip install pytest-cov
uv run pytest tests/ --cov=src/automil --cov-report=term-missing
uv run pytest benchmarks/tests/ --cov=benchmarks/src/autobench --cov-report=term-missing
```

Do not commit the coverage config — it is not part of the standing toolchain.

---

*Testing analysis: 2026-04-30*
