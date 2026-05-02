---
phase: 00
slug: tier-2-cleanup-cli-split-compat-shim
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-01
tests_total: 113
tests_added: 5
gaps_resolved: 4
gaps_manual_only: 1
---

# Phase 00 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_cli.py -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~4 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_cli.py -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~4 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 00-01 | 01 | 1 | CLN-06 | T-00-02 / — | `from automil.cli import main` resolves; all 11 subcommands registered | unit | `uv run pytest tests/test_cli.py::TestCliHelp -q` | ✅ | ✅ green |
| 00-01 | 01 | 1 | T-00-01 (abs path) | T-00-01 | submit rejects absolute --files argument | unit | `uv run pytest tests/test_cli.py::TestSubmitPathValidation::test_submit_rejects_absolute_path -q` | ✅ | ✅ green |
| 00-01 | 01 | 1 | T-00-01 (dotdot) | T-00-01 | submit rejects --files containing `..` | unit | `uv run pytest tests/test_cli.py::TestSubmitPathValidation::test_submit_rejects_dotdot_traversal -q` | ✅ | ✅ green |
| 00-01 | 01 | 1 | T-00-01 (escape) | T-00-01 | submit rejects symlink resolving outside git root | unit | `uv run pytest tests/test_cli.py::TestSubmitPathValidation::test_submit_rejects_escape_via_resolve -q` | ✅ | ✅ green |
| 00-01 | 01 | 1 | T-00-03 | T-00-03 | auto-detect excludes `automil/` and `.claude/` from overlay manifest | unit | `uv run pytest tests/test_cli.py::TestSubmitPathValidation::test_submit_auto_detect_excludes_automil_dir -q` | ✅ | ✅ green |
| 00-02 | 02 | 1 | CLN-03 | — | dotenv parser loads .env into subprocess env | unit | `uv run pytest tests/test_orchestrator_dotenv.py -q` | ✅ | ✅ green |
| 00-03 | 03 | 1 | CLN-05 | — | nvidia-smi is pinned; falls back gracefully | unit | `uv run pytest tests/test_orchestrator_nvidia_smi.py -q` | ✅ | ✅ green |
| 00-04 | 04 | 1 | CLN-04 | — | PID + starttime staleness check prevents false-alive | unit | `uv run pytest tests/test_orchestrator_pid_starttime.py -q` | ✅ | ✅ green |
| 00-05 | 05 | 1 | CLN-02 | — | subprocess env uses explicit whitelist, not os.environ passthrough | unit | `uv run pytest tests/test_orchestrator_env_whitelist.py -q` | ✅ | ✅ green |
| 00-06 | 06 | 1 | CLN-07 | — | compat.py shim re-exports ExperimentGraph without breakage | unit | `uv run pytest tests/test_compat.py -q` | ✅ | ✅ green |
| 00-07 | 07 | 1 | CLI-07 | — | reconcile --recompute-best recomputes best-of-tree composite | unit | `uv run pytest tests/test_recompute_best.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No stub files needed; pytest is already installed and configured.

*All phase behaviors have automated verification except CLN-01 (see Manual-Only section below).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No stray `print()` debug statements in non-CLI modules | CLN-01 dead-code/print sweep (Tier-1 mechanical pre-flight) | `print()` calls in `cmd_start`, `cmd_status`, `cmd_stop` in orchestrator.py are **intentional** CLI output. A blanket grep would produce false positives on every intentional print. The sweep was a one-time mechanical verification at the start of Phase 0, not an ongoing invariant with an automatable threshold. | `grep -rn "^[[:space:]]*print(" src/automil/ --include="*.py"` then manually audit each hit against the list of intentional CLI-output prints: `orchestrator.py:cmd_start`, `orchestrator.py:cmd_stop`, `orchestrator.py:cmd_status`. Any print outside those three functions and outside cli/ `click.echo` calls is a bug. |

---

## Gap Resolution Summary

| Gap ID | Description | Resolution | Status |
|--------|-------------|------------|--------|
| CLN-01 | Dead-code/print sweep | Manual-only (intentional prints in orchestrator CLI) | SKIP (justified) |
| CLN-02 | Subprocess env whitelist | Covered by `tests/test_orchestrator_env_whitelist.py` (12 tests) | FILLED |
| CLN-03 | Dotenv parser | Covered by `tests/test_orchestrator_dotenv.py` (6 tests) | FILLED |
| CLN-04 | PID + starttime | Covered by `tests/test_orchestrator_pid_starttime.py` (8 tests) | FILLED |
| CLN-05 | nvidia-smi pin | Covered by `tests/test_orchestrator_nvidia_smi.py` (4 tests) | FILLED |
| CLN-06 | CLI split regression sentinel | `tests/test_cli.py::TestCliHelp::test_main_help_lists_all_11_subcommands` | FILLED |
| CLN-07 | compat.py | Covered by `tests/test_compat.py` (4 tests) | FILLED |
| CLI-07 | reconcile --recompute-best | Covered by `tests/test_recompute_best.py` (12 tests) | FILLED |
| T-00-01 | submit path validation | `tests/test_cli.py::TestSubmitPathValidation` (3 tests) | FILLED |
| T-00-03 | Auto-detect excludes automil/+.claude/ | `tests/test_cli.py::TestSubmitPathValidation::test_submit_auto_detect_excludes_automil_dir` | FILLED |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 4s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-01
