# Milestones

## v1.0 F2-readiness framework refactor (Shipped: 2026-05-08)

**Phases completed:** 9 phases, 92 plans, 54 tasks

**Key accomplishments:**

- Split the 725-line src/automil/cli.py monolith into a 12-file src/automil/cli/ package using per-command-group, fine organisation; all 62 tests green; user-facing CLI byte-identical.
- `_load_dotenv` now delegates to `python-dotenv`'s `dotenv_values`, fixing silent value-corruption on quoted strings, `export` prefixes, and inline `# comments` that the legacy `partition("=")` parser mishandled.
- 1. [Rule 3 — Blocking] Plan literal code vs. plan verification regex were inconsistent
- Two-section deprecation-shim module shipped empty-but-documented for Phase 1/2/3 future relocations, plus 4 new pytest tests covering importability and shape — zero behavioural change, zero new dependencies.
- System-minimal env whitelist + literal-name passthrough replaces `{
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- 1. [Rule 1 - Bug] test_lifecycle_skeleton.py stub tests blocked GREEN suite
- 1. [Rule 1 - Bug] git rev-parse --verify does not check commit existence
- One-liner:
- One-liner:
- One-liner:
- Before (16 lines):
- One-liner:
- 1. [Rule 2 - Missing Critical Functionality] Added `_kill_experiment()` to ExperimentOrchestrator
- One-liner:
- One-liner:
- 1. [Rule 2 - Missing functionality] MockSLURMBackend
- One-liner:
- Positive-case parametrize — 9 cases across 7 leak classes:
- 1. [Rule 1 - Bug] submit.py auto-detect picks up AGENTS.md as changed file
- 1. [Rule 1 - Bug] `python -m automil.cli` fails — automil.cli is a package
- Cell frozen dataclass + CellStatus str-Enum + atomic JSON IO via tempfile+os.replace — the foundational cells.state module that every Phase 4 cap layer imports
- SIGTERM handler (register_sigterm_flush) with sys.exit(0) flush contract and aggregate_folds pure function bootstrapping the cells package
- One-liner:
- Canonical D-119 aggregate_folds implementation + D-123 reconcile_budget_kill stub with metadata.budget_killed=True tagging
- One-liner:
- 1. [Rule 2 - Missing Logic] fold_count merged into existing training: section
- One-liner:
- One-liner:
- One-liner:
- One-liner:
- GateManifest frozen dataclass (D-137):
- `src/automil/gate/nominate.py`
- One-liner:
- One-liner:
- `src/automil/gate/promote.py`
- `src/automil/cli/gate.py`
- 1. [Rule 1 - Bug] Test T-7 pass path failed with K=2 (Wilcoxon mathematically blocked)
- HTTP API (viz/server.py):
- Pitfall-6 anti-acceptance gate test (D-149): 9-assertion end-to-end held-out isolation verifier + AST-based framework purity guards for gate/ — Phase 5 goal-backward verifier is green
- `tests/gate/test_calibration_pilot_smoke.py`
- pyproject.toml:
- One-liner:
- config.yaml.j2 gains a top-level `backend:` block with TODO_FILL_IN sentinels for required SLURM directives; `automil check` gains `_validate_slurm_directives` (raises `SlurmDirectivesIncompleteError` on TODO/missing keys) and `_validate_ray_backend` (advisory-only Ray reachability check)
- 1. [Rule 1 - Bug] Module-level `import submitit` prevented importing pure helpers without extras
- One-liner:
- Before/After summary (8+ running_dir reference sites):
- `_atomic_write_lines(path: Path, lines: list[str]) -> None`
- One-liner:
- 1. [Rule 1 — Design simplification] Worktree path via Runner convention, not running JSON
- One-liner:
- Generated:
- 1. [Rule 3 - Worktree mismatch] Committed to main repo instead of worktree
- src/automil/cli/submit.py
- Three backend stub additions (Task 1)
- Parametrised test_healthcheck_returns_health_report extends test_contract.py to lock all 4 BCK-01 backends against the D-189 HealthReport shape and NotImplementedError message contract
- LocalBackend.healthcheck() wired into automil init with empirical VRAM quantile_95 from results.tsv vram_gb column, --no-healthcheck CI bypass, and cap/hardware sections stamped in config.yaml.j2
- 1. [Rule 1 - Bug] Consolidated multiline bash command to single line
- [Rule 1 - Adaptation] _required_h2_sections() uses 2 sections instead of 7
- One-liner:
- 1. [Rule 2 - Missing Critical Functionality] TODO-substring check uses YAML-value-level assertion, not raw text
- One-liner:
- Generated:
- 1. [Rule 3 - Blocking] jsonschema not installed in virtual environment
- One-liner:
- Task 1: app.js metric reader (1 line changed)
- One-liner:
- 1. [Rule 1 - Bug] Comment text contained AUTOBENCH_ token triggering purity grep gate
- One-liner:
- 1. [Rule 1 - Bug] --non-interactive flag does not exist
- One-liner:
- Generated:

---
