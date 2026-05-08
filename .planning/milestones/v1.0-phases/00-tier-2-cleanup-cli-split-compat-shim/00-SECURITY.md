---
phase: 00
slug: tier-2-cleanup-cli-split-compat-shim
status: verified
threats_total: 15
threats_closed: 15
threats_open: 0
accepted_risks: 7
asvs_level: 1
audit_date: 2026-05-01
created: 2026-05-01
---

# Phase 0 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase 0 closes the four HIGH-severity items from `.planning/codebase/CONCERNS.md`
> (env-leak, dotenv parser, PID-stale-detection, nvidia-smi PATH-shim) plus the
> CLI restructure and the reconcile audit-trail flag, with no behavioural surface
> change beyond explicit additions.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| User shell → Click CLI (`automil submit --files ...`) | Operator-supplied path arguments are the only barrier between `--files` and arbitrary FS writes into the experiment archive. | Repo-relative path strings (validated for absolute / `..` / out-of-root). |
| Operator filesystem (`<repo>/.env`, `<repo>/benchmarks/.env`) → orchestrator process env | Operator-trusted `.env` files parsed by `python-dotenv` and merged into `os.environ` via `setdefault` (shell wins over file). | KEY=VALUE pairs, possibly containing secrets — never re-broadcast beyond the orchestrator's own `os.environ`. |
| Operator `$PATH` → orchestrator binary resolution (`nvidia-smi`) | A shimmed binary earlier on `$PATH` could spoof VRAM and trick the bin-packer. | nvidia-smi argv[0] is pinned at module import via `shutil.which`. |
| Operator shell `os.environ` → experiment subprocess `env` | **HIGHEST-severity Phase 0 boundary.** A buggy/untrusted training script (overlay-driven arbitrary code) inherits secrets unless filtered. | Whitelisted system vars + literal-name passthrough only; secrets blocked. |
| Per-spec `spec.env` (queue file) → experiment subprocess `env` | Agent-supplied; trusted-by-construction but bounded by `_SPEC_ENV_BLOCKED` for GPU-mask spoofing. | Arbitrary KEY=VALUE pairs, with hard-blocked keys on GPU masking. |
| `automil/config.yaml: env.passthrough` (operator-authored) → orchestrator → subprocess | Consumer-config-declared. Globs forbidden at config layer; non-list values rejected with WARN. | Literal var names only. |
| Recorded PID file → live process at that PID | After daemon kill + Linux PID rollover, a recorded PID may belong to an unrelated process — `cmd_stop` SIGTERM target must be cross-checked. | `{pid, starttime_ticks, starttime_iso}` JSON; `starttime_ticks` from `/proc/<pid>/stat` field 22. |
| Operator CLI invocation → `graph.json` mutation (`reconcile --recompute-best`) | Atomic write via `tempfile.mkstemp` + `os.rename`; `--dry-run` is the in-band safety. | `meta.best_node_id`, `meta.best_composite`. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-00-01 | T (tampering) | `cli/submit.py` path validation | mitigate | Path guards lifted byte-identical from old cli.py:347-365 — `os.path.isabs(f) or ".." in Path(f).parts` rejection at `src/automil/cli/submit.py:179-180`; `src.resolve().relative_to(git_root.resolve())` boundary check at `src/automil/cli/submit.py:188-191`. | closed |
| T-00-02 | T (tampering) | `cli/__init__.py` import order / package-vs-module shadowing | accept | Restructure-only. Python prefers package (`cli/`) over same-named module — old `cli.py` deleted (verified `test ! -f src/automil/cli.py` succeeds). No new attack surface. | closed |
| T-00-03 | I (information disclosure) | `cli/submit.py` auto-detect filter | mitigate | `automil_rel` derived at `src/automil/cli/submit.py:110-112` (`adir.resolve().relative_to(git_root.resolve()).as_posix() + "/"`); auto-detect exclusion at `src/automil/cli/submit.py:146-148` filters out both `automil_rel` AND literal `.claude/` prefixes — prevents `automil/graph.json` and Claude assets from leaking into experiment overlay archives. | closed |
| T-00-04 | I (information disclosure) | `dotenv` parser swap | accept | Operator-trusted input; replacement-in-place via `python-dotenv>=1.0` at `src/automil/orchestrator.py:29` + `_load_dotenv` body at `src/automil/orchestrator.py:380-407` strictly improves correctness over the deleted `partition("=")` parser. `setdefault` no-override semantic preserved (line 405). | closed |
| T-00-05 | T (tampering) | `query_gpus` subprocess argv resolution (PATH-shim spoofing) | mitigate | `shutil.which("nvidia-smi")` at module import (`src/automil/orchestrator.py:79`); `NVIDIA_SMI_PATH = _resolved_nvidia_smi or "nvidia-smi"` (line 80) used as argv[0] in `query_gpus` (line 238). INFO log on success / WARN on fallback (lines 81-87). 4 tests at `tests/test_orchestrator_nvidia_smi.py`. | closed |
| T-00-06 | I (information disclosure) | `compat.py` module surface | accept | Pure-Python documentation module: empty Active section + `_PLANNED_MIGRATIONS` documentation-only dict at `src/automil/compat.py`. Importing emits zero `DeprecationWarning` (verified by `tests/test_compat.py::test_compat_imports_cleanly`). No runtime side-effects beyond Python's normal module load. | closed |
| T-00-07 | I (information disclosure) — **HIGH** | `_launch` subprocess env (operator-secret exfiltration) | mitigate | `_build_subprocess_env` at `src/automil/orchestrator.py:531-581` replaces `{**os.environ, ...}` (verified ZERO live `{**os.environ` matches in code; only docstring/comment references at lines 543, 547, 629). Hardcoded literal whitelist (line 56-59) + prefix-glob (line 61-63) + config-driven `env.passthrough` (line 314-321) + orchestrator-injected fixed keys (lines 565-574) + per-spec `spec.env` (lines 577-579). `tests/test_orchestrator_env_whitelist.py::test_secrets_do_not_leak` (line 82) explicitly verifies non-leak of OPENAI_API_KEY, WANDB_API_KEY, GITHUB_TOKEN, AWS_SECRET_ACCESS_KEY. | closed |
| T-00-08 | T (tampering) | `automil/config.yaml: env.passthrough` config layer (glob attack widening passthrough surface) | mitigate | Literal-names-only enforced at `src/automil/orchestrator.py:314-321` — `isinstance(raw_passthrough, list)` rejects non-list values with WARN and falls back to empty list (line 315-320). Globs are valid only in the hardcoded `_SYSTEM_ENV_WHITELIST_PREFIX` (operator cannot widen surface from config). 12 tests at `tests/test_orchestrator_env_whitelist.py`. | closed |
| T-00-09 | T (tampering) | `spec.env` GPU-mask spoofing | mitigate | `_SPEC_ENV_BLOCKED = frozenset({"AUTOMIL_GPU", "CUDA_VISIBLE_DEVICES"})` at `src/automil/orchestrator.py:66`; enforcement at `_build_subprocess_env` line 577-579 (`if k not in _SPEC_ENV_BLOCKED`). Test `tests/test_orchestrator_env_whitelist.py::test_spec_env_cannot_override_blocked_keys` (line 145) verifies. | closed |
| T-00-10 | D (denial of service) | `env.passthrough` missing key blocking scheduling | accept | WARN-once-at-startup loop at `src/automil/orchestrator.py:322-328` logs the missing key but never raises; subprocess env simply omits the var. Failure mode reduces to "training script ValueError on missing var" surfaced at orchestrator startup, not deep inside training code. Operator-trusted; documented in plan 00-05. | closed |
| T-00-11 | T (tampering) — **HIGH** | `cmd_stop` signalling wrong process via PID reuse | mitigate | `_is_pid_alive_with_starttime(pid, expected_starttime_ticks)` at `src/automil/orchestrator.py:150-160` cross-checks `/proc/<pid>/stat` field 22 (read via `_read_proc_starttime`, line 137-147; parsed via `_parse_starttime_from_stat_line`, line 119-134, using `rfind(')')` for comm-with-spaces). All 4 PID call sites (`run` line 966-967 unlink, `cmd_start` lines 975-982, `cmd_status` lines 998-1004, `cmd_stop` lines 1037-1056) use the new helpers. ZERO live `os.kill(pid, 0)` matches in orchestrator daemon code (line 155 is in a docstring; line 1052 is the legitimate SIGTERM after starttime cross-check). Test `tests/test_orchestrator_pid_starttime.py::test_is_pid_alive_with_wrong_starttime` (line 52) covers the headline PID-reuse scenario. | closed |
| T-00-12 | D (denial of service) | malformed PID file blocking restart | mitigate | `_load_pid_file` at `src/automil/orchestrator.py:178-195` returns None on legacy plain-int (`json.JSONDecodeError`), missing keys (`{"pid", "starttime_ticks", "starttime_iso"}.issubset(...)`), or non-dict payload. Callers (`cmd_start` lines 980-982, `cmd_stop` lines 1042-1046) unlink the stale file and proceed. Tests `test_load_pid_file_handles_legacy_plain_int`, `test_load_pid_file_handles_invalid_json`, `test_load_pid_file_handles_missing_keys` in `tests/test_orchestrator_pid_starttime.py`. | closed |
| T-00-13 | I (information disclosure) | `starttime_iso` wall-clock timestamp in PID file | accept | `datetime.now().isoformat()` written to `orchestrator.pid` (`src/automil/orchestrator.py:173`); operator-owned debugging aid, not sensitive. PID file lives under operator's automil/ directory. | closed |
| T-00-14 | T (tampering) | `graph.json` atomic-write race during `recompute_best` | accept | Pre-existing `ExperimentGraph.save()` uses `tempfile.mkstemp` + `os.rename` for atomicity (graph.py); `recompute_best` adds no concurrency. Concurrent-restart safety with a live daemon is documented as pre-existing in `.planning/codebase/CONCERNS.md`. Operator-trusted CLI. | closed |
| T-00-15 | I (information disclosure) | `recompute-best` stdout summary line | accept | Operator-owned data (node_id + composite). No telemetry beyond stdout per locked decision D-15. Verbatim Unicode → format enforced by `tests/test_recompute_best.py::test_cli_output_format_changed`. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

### Dispositions Summary

- **Mitigate (8):** T-00-01, T-00-03, T-00-05, T-00-07, T-00-08, T-00-09, T-00-11, T-00-12 — all verified by grep + test reference.
- **Accept (7):** T-00-02, T-00-04, T-00-06, T-00-10, T-00-13, T-00-14, T-00-15 — all logged in Accepted Risks below.
- **Transfer (0):** none.

### Verification Notes

- **T-00-01:** The plan's `tests/test_integration.py::test_submit_rejects_*` regression tests were aspirational naming — no test functions with that prefix exist in `tests/test_integration.py`. However, the path-validation guards themselves are byte-identically present in `src/automil/cli/submit.py:179-191`, which is the verifiable mitigation requirement. The 108-test baseline suite passes, and any regression in the existing CLI surface around path handling would be caught by `test_init_submit_flow`, `test_multiple_submits`, `test_deleted_file_submission`, and `test_no_internal_paths_in_package`. **Recommendation (informational, not a blocker):** add explicit `test_submit_rejects_absolute_path` and `test_submit_rejects_path_traversal` in a follow-up — current state is mitigation-present, regression-coverage-incidental.
- **T-00-07 & T-00-09 (WR-03 from REVIEW.md):** `_SPEC_ENV_BLOCKED` blocks only `AUTOMIL_GPU` + `CUDA_VISIBLE_DEVICES`. `spec.env` can still override orchestrator-injected `AUTOMIL_RESULTS_DIR` / `AUTOBENCH_ROOT` / `PYTHONPATH` because the per-spec layer (step 4) writes after step 3. **Risk assessment:** does NOT materially weaken T-00-07 (the operator-secret-exfiltration vector is still closed — a hostile spec can only redirect its OWN result paths or imports, not exfiltrate parent-shell secrets that no longer flow through). Does NOT materially weaken T-00-09 (the GPU-mask spoofing scenario is fully blocked). Whether it represents a separate trust-boundary concern (a malicious spec author redirecting their own subprocess writes) is documented in REVIEW.md WR-03 and is out-of-scope for Phase 0's stated CLN-02 goal of "closing the exfiltration vector". Logged as informational; not a Phase 0 mitigation gap.
- **T-00-11 (WR-05 from REVIEW.md):** `_write_pid_file` stores `starttime_ticks=0` when `/proc` is unreadable (non-Linux test env). On Linux production this branch is unreachable (`/proc/self/stat` always readable by owning process), so the live-check is accurate. The edge case where a production daemon runs on a `/proc`-restricted container would silently classify itself as dead — but PROJECT.md Constraints declare Linux-only and `/proc`-available for the orchestrator daemon. Logged as informational; not a Phase 0 mitigation gap.
- **WR-01 from REVIEW.md (`cli/check.py:67` GPU-count probe uses bare `nvidia-smi`):** Out-of-scope per Plan 03 explicit decision — T-00-05 was scoped to `query_gpus()` (the bin-packer signal source), not the diagnostic probe. The orchestrator's pinned-path line `nvidia-smi: <path>` is emitted on the next stdout line, giving operators visibility. NOT a Phase 0 gap.
- **`viz/server.py:235,301` bare `os.kill(pid, 0)`:** Out-of-scope per Plan 06 explicit decision — CLN-04 was scoped to the orchestrator daemon PID file. viz_server has its own simpler PID file. Captured in REVIEW.md as Phase-7 backlog. NOT a Phase 0 gap.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-00-01 | T-00-02 | Restructure-only refactor (cli.py monolith → cli/ package). Python prefers package over same-named module; old `cli.py` was deleted in commit `01fbee2`. Verified: `test ! -f src/automil/cli.py` succeeds. No new attack surface. | Leo (project lead) | 2026-05-01 |
| AR-00-02 | T-00-04 | `python-dotenv>=1.0` library replacement of the inline `partition("=")` parser. `.env` input is operator-owned; library swap strictly improves correctness over the deleted handrolled parser. `setdefault` no-override semantic preserved. | Leo (project lead) | 2026-05-01 |
| AR-00-03 | T-00-06 | `compat.py` is a documentation-only module — empty Active section, `_PLANNED_MIGRATIONS` is a literal dict that's never imported or executed. Importing emits zero DeprecationWarning. No runtime side-effects. | Leo (project lead) | 2026-05-01 |
| AR-00-04 | T-00-10 | `env.passthrough` missing keys WARN at startup but never block scheduling per locked decision D-04. Failure mode reduces to "training script raises on missing var" surfaced at orchestrator startup rather than deep inside training. Operator can audit via `automil check` per-key OK/MISSING report. | Leo (project lead) | 2026-05-01 |
| AR-00-05 | T-00-13 | Wall-clock `starttime_iso` in PID file is a debugging aid alongside the structured `starttime_ticks`. PID file lives under operator's `automil/orchestrator/` directory. Not sensitive data. | Leo (project lead) | 2026-05-01 |
| AR-00-06 | T-00-14 | `graph.json` atomic-write race: pre-existing tempfile+rename atomicity unchanged by `recompute_best`. Concurrent-restart safety with a live daemon is a pre-existing condition documented in `.planning/codebase/CONCERNS.md`. Operator-trusted CLI; not introduced by Phase 0. | Leo (project lead) | 2026-05-01 |
| AR-00-07 | T-00-15 | `recompute-best` stdout summary prints `node_id` + `composite` — both operator-owned. No telemetry beyond stdout per locked decision D-15. Format enforced verbatim with Unicode → by test `test_cli_output_format_changed`. | Leo (project lead) | 2026-05-01 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags (from SUMMARY.md `## Threat Flags` sections)

Two of seven plan summaries (00-03, 00-04) contain explicit `## Threat Flags` sections; both report **none** / no new attack surface introduced. The remaining five (00-01, 00-02, 00-05, 00-06, 00-07) do not include the section but their per-plan threat models map 1:1 onto the registered T-00-* IDs above. No unregistered surface detected during executor runs.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-01 | 15 | 15 | 0 | Claude Code (gsd-secure-phase / Phase 0 audit) |

### Audit Methodology

- **Per-mitigate verification:** grep against the cited file paths + cross-reference test names from each plan's `<threat_model>` block.
- **Per-accept verification:** entry present in Accepted Risks Log above.
- **Read-only audit:** no implementation files modified. Two REVIEW.md warnings (WR-03, WR-05) assessed against threat scope — neither materially weakens the mitigations they touch.
- **Test corroboration:** 108/108 tests pass (62 baseline + 46 net-new across CLN-02/03/04/05/07 + CLI-07).
- **Implementation gap check:** ZERO live `{**os.environ, ...}` matches in `src/automil/orchestrator.py`; ZERO live `os.kill(pid, 0)` matches in orchestrator daemon code; `NVIDIA_SMI_PATH` resolved at column-0 module level; `_SPEC_ENV_BLOCKED` enforced at the per-spec layer.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-01
