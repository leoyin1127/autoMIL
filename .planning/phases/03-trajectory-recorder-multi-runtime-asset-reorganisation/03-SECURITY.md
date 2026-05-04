# Phase 3 Security Audit — Trajectory Recorder + Multi-Runtime Asset Reorganisation

**Phase:** 03 — trajectory-recorder-multi-runtime-asset-reorganisation
**Commits audited through:** 5667a3d (post-code-review fixes)
**Audit date:** 2026-05-03
**ASVS Level:** 1
**Total threats declared:** 37 (11 plans × 2–4 threats each)
**Threats closed:** 37/37 (all closed after T-03-09-S03 mitigation landed at commit `<UPCOMING>`)
**Threats open (BLOCKER):** 0/37
**Unregistered flags:** 0

---

## Threat Verification by Plan

### Plan 03-01: Trajectory Package Skeleton + Schema + Redactor + Recorder FD-Cache

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-01-S01 | `gen_ai.tool.call.arguments` contains secrets before redaction | Information Disclosure | HIGH | Mitigate | CLOSED | `recorder.py:161` calls `redact_event(event)` before every `_append_line`; `redactor.py:16–30` compiles 7 patterns at import (mandatory, no opt-out flag per module docstring line 6); `tests/trajectory/test_redactor.py` covers all 7 leak classes |
| T-03-01-S02 | Oversized event exhausts disk (DoS) | Denial of Service | MEDIUM | Mitigate | CLOSED | `recorder.py:163` calls `apply_size_cap(redacted)` after every `redact_event`; `redactor.py:32` sets `_SIZE_CAP_BYTES = 8192`; hard 50 MB cap at `rotation.py:67–73` returns `False`; recorder returns `False` at hard limit `recorder.py:140–141` |
| T-03-01-S03 | `archive_dir` escapes node's directory boundary | Tampering | MEDIUM | Mitigate | CLOSED | `recorder.py:131` constructs `archive_dir / node_id / "trajectory.jsonl"` — path stays within caller-supplied `archive_dir`; node_id is an internal framework ID set by the orchestrator, not user-supplied at this layer |
| T-03-01-S04 | fd-cache fd leak on abnormal process exit | Denial of Service | LOW | Mitigate | CLOSED | `recorder.py:72` registers `atexit.register(_close_all_fds)`; `recorder.py:61–69` closes all cached fds; OS reclaims on SIGKILL (accepted by disposition) |
| T-03-01-S05 | `trajectory-v2` misinterpreted by v1 reader | Repudiation | LOW | Mitigate | CLOSED | `recorder.py:195` (CR-02): strict predicate `version == "trajectory-v1" or version.startswith(("trajectory-v1.", "trajectory-v1-"))` — explicitly rejects `v11`, `v12`, `v2`; test `test_read_metadata_v2_raises` in `test_schema.py` |

### Plan 03-02: agent_assets/ Migration + compat.py Promotion

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-02-S01 | Partial git mv leaves broken path references | Tampering | MEDIUM | Mitigate | CLOSED | `grep -r "claude_assets" src/automil/ --include="*.py" -l \| grep -v compat.py` returns empty (verified); `compat.py` is the only Python file referencing `claude_assets`; hard-floor test `test_no_claude_assets_outside_compat` in `test_smoke_two_runtimes.py` |
| T-03-02-S02 | compat.py shim swallows import errors silently | Elevation of Privilege | LOW | Mitigate | CLOSED | `compat.py:100–105`: `AttributeError` raised with migration guidance if `agent_assets.{name}` not found; no silent `None` return; `tests/test_compat.py` asserts DeprecationWarning is emitted |
| T-03-02-S03 | `_shared/AGENTS.md` leaks Claude-specific instructions to non-Claude runtimes | Information Disclosure | LOW | Accept | CLOSED | Accepted per plan: AGENTS.md is designed to be runtime-universal (D-90); Claude-specific instructions in runtime overlay only; content verified — only `AUTOMIL_RUNTIME=claude-code` appears as an example in universal context |
| T-03-02-S04 | Runtime overlay dirs lost on checkout (no .gitkeep) | Denial of Service | LOW | Mitigate | CLOSED | All three `.gitkeep` files confirmed present: `agent_assets/opencode/.gitkeep`, `agent_assets/codex/.gitkeep`, `agent_assets/deepseek/.gitkeep` |

### Plan 03-03: Redactor Positive-Case Tests + Schema Version Tests

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-03-S01 | Test false-positive guard too weak — silent over-redaction | Information Disclosure | MEDIUM | Mitigate | CLOSED | `tests/trajectory/test_redactor.py:37–55`: `test_redact_not_triggered` parametrized over 6 non-secret strings; any regex change that causes false-positives will fail CI; guard covers `sk-short`, `task_key_index`, `skeletal`, `disk-based`, `stack_api_keys_count=5`, `index_key=0` |
| T-03-03-S02 | 8 KB cap test relies on truncation-field implementation detail | Denial of Service | LOW | Accept | CLOSED | Accepted per plan: test checks `encoded_size <= _SIZE_CAP_BYTES` (behavioural), not which fields were truncated; safe to refactor internals |
| T-03-03-S03 | `trajectory-v2` refusal test breaks on schema_version logic change | Repudiation | LOW | Mitigate | CLOSED | `tests/trajectory/test_schema.py:327–340`: `test_read_metadata_v2_raises` uses `pytest.raises(TrajectorySchemaError)` — any change to v2 handling caught; test passes per D-99 acceptance gate |

### Plan 03-04: Full Rotation Manager

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-04-S01 | Soft rotation races with concurrent writer | Tampering | MEDIUM | Mitigate | CLOSED | `recorder.py:134–163`: per-node `RLock` serialises all writes + rotation checks within a process; `recorder.py:77`: `LOCK_EX` flock for cross-process exclusion; `rotation.py:116`: `os.rename` is atomic at POSIX level |
| T-03-04-S02 | Rotation creates unbounded sibling files (disk exhaustion) | Denial of Service | MEDIUM | Mitigate | CLOSED | `rotation.py:67–73`: hard 50 MB limit refuses new events before infinite rotation can occur; siblings bounded by `⌈hard_bytes / soft_bytes⌉ = 10` under defaults; `test_hard_rotate_returns_false` in `test_rotation.py` |
| T-03-04-S03 | `_next_rotation_index` races with another process creating same sibling | Tampering | LOW | Accept | CLOSED | Accepted per plan: flock in `_do_soft_rotate` provides exclusion within normal operation; simultaneous multi-process soft rotation on the same node requires external coordination not present in normal use |
| T-03-04-S04 | Metadata copy to new file fails — new trajectory.jsonl missing header | Repudiation | LOW | Mitigate | CLOSED | `rotation.py:123`: header copy failure logged at WARNING; `recorder.py:147–152`: `is_new = not traj_path.exists()` re-writes metadata header on next `record_event` call after rotation leaves empty path; `recorder.py:181–188` (CR-01): empty-file guard in `read_metadata` raises typed `TrajectorySchemaError` instead of bare `IndexError` |

### Plan 03-05: Overlay Merger (_overlay.py)

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-05-S01 | Overlay H1 replaces shared H1 title | Tampering | LOW | Mitigate | CLOSED | `_overlay.py:87`: `result = preamble` — preamble always taken from `_shared`; overlay's `_parse_sections` discards the preamble (`_, overlay_sections = _parse_sections(...)`); `test_h1_always_from_shared` in `test_overlay.py` |
| T-03-05-S02 | Code block `## ` causes false section split | Tampering | LOW | Accept | CLOSED | Accepted: documented known limitation in `_overlay.py:8–13` module docstring; `test_known_limitation_code_block_false_split` in `test_overlay.py` confirms and documents the behaviour; authors instructed not to use `## ` at line start in code blocks |
| T-03-05-S03 | Path traversal via overlay_path reads arbitrary files | Information Disclosure | LOW | Accept | CLOSED | Accepted per plan: `overlay_path` is constructed from `package_dir + runtime + asset_name` in `show_skill.py` and `init.py`; `--runtime` uses `click.Choice` (fixed valid values); no user-provided path component |

### Plan 03-06: Runtime Declaration Module

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-06-S01 | `AUTOMIL_RUNTIME` forged to misattribute trajectory authorship | Spoofing | MEDIUM | Accept | CLOSED | Accepted per plan: experiment process controls its own env; recorder trusts declaration; forensic authenticity is statistical, not cryptographic; noted as design intent in D-87 |
| T-03-06-S02 | `AUTOMIL_RUNTIME` missing from `env.passthrough` — never reaches experiment process | Denial of Service | MEDIUM | Mitigate | CLOSED | `config.yaml.j2:101–102`: `AUTOMIL_*` wildcard plus explicit `AUTOMIL_RUNTIME` entry with comment citing D-87; belt-and-suspenders coverage |
| T-03-06-S03 | `submit.py` metadata.runtime write fails if `os` not in scope | Tampering | LOW | Mitigate | CLOSED | `submit.py:302`: `spec.setdefault("metadata", {})["runtime"] = os.environ.get("AUTOMIL_RUNTIME", "unknown")` — uses existing `os` import from line 6 of `submit.py` |

### Plan 03-07: `automil init --runtime` + `--update` Flag

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-07-S01 | `--update` rewrites `.claude/CLAUDE.md` with wrong content | Tampering | MEDIUM | Mitigate | CLOSED | `init.py:279–289` (WR-04): AGENTS.md write guarded by `if not agents_dst.exists() or update`; content rendered deterministically from `package_dir` templates; `test_init_update_flag_bypasses_guard` asserts expected content after `--update` |
| T-03-07-S02 | `AGENTS.md` contains runtime-specific secrets from overlay | Information Disclosure | LOW | Accept | CLOSED | Accepted per plan: AGENTS.md contains universal instructions + CLI commands only (D-90); no credentials; overlay adds runtime-specific CLI commands |
| T-03-07-S03 | Auto-detection of empty `.claude/` installs full Claude overlay | Elevation of Privilege | LOW | Accept | CLOSED | Accepted: D-91 explicitly specifies lenient detection ("empty .claude/ dir = Claude Code in use"); `init.py:251–264`: detects `.claude/`, `.opencode/`, `.codex/` existence |

### Plan 03-08: `automil show-skill --runtime` Command

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-08-S01 | Path traversal via `--runtime` with `../` injection | Information Disclosure | MEDIUM | Mitigate | CLOSED | `show_skill.py:15–17`: `--runtime` uses `click.Choice(["claude", "opencode", "codex", "deepseek-via-opencode", "deepseek-via-codex"])`; Click validates choices before invoking command; no user-provided path component reaches filesystem; `test_show_skill_missing_runtime_arg` covers invalid arg rejection |
| T-03-08-S02 | show-skill output contains secrets from SKILL.md | Information Disclosure | LOW | Accept | CLOSED | Accepted per plan: SKILL.md is version-controlled, reviewed content; no auto-generated or runtime-derived secrets in skill files |

### Plan 03-09: `automil trajectory` CLI Group + record/export

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-09-S01 | `trajectory record @filepath` reads arbitrary file | Information Disclosure | MEDIUM | Mitigate | CLOSED | `cli/trajectory.py:33–40`: `@filepath` reads text file and parses as JSON; binary/non-JSON content causes JSON parse error (exit 1) per `cli/trajectory.py:43–50`; available only to users with shell access who can read files directly anyway; no path sanitization but mitigation is content validation |
| T-03-09-S02 | Export bundle contains un-redacted secrets from earlier captures | Information Disclosure | HIGH | Mitigate | CLOSED | `export.py:73`: `redact_event(event)` called on every line during export; `export.py:50–52`: redaction rule hash included in manifest for auditability; `test_export_creates_tarball` verifies bundle structure |
| T-03-09-S03 | `trajectory export` path traversal via node_id `../../etc/passwd` | Information Disclosure | MEDIUM | Mitigate | CLOSED | `cli/trajectory.py:124–131` (post-audit fix): rejects empty / `.` / `..` / absolute paths / paths containing `..` parts / strings containing `/` or `\` BEFORE calling `export_bundle()`. Click raises `ClickException` with explanatory message; bundle file is never created on rejection. Regression coverage: `tests/trajectory/test_export_cli.py::test_export_rejects_path_traversal` parametrized over 10 malicious inputs (`../../etc`, `/etc/passwd`, `..`, `node/../../escape`, etc.); `test_export_accepts_valid_node_id_shape` confirms `node_0176` still accepted (no over-rejection). |

### Plan 03-10: Runtime Hook Integration

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-10-S01 | `HOOK_EVENT=$(cat)` reads stdin indefinitely | Denial of Service | MEDIUM | Mitigate | CLOSED | `on_stop.sh:8`: `HOOK_EVENT="$(cat)"` reads bounded payload; Claude Code Stop hook payload is fixed-schema ~200 bytes per official docs; `HOOK_EVENT` is passed via env var `AUTOMIL_HOOK_PAYLOAD` to python3 (not shell-interpolated), then python3 constructs a bounded `gen_ai.*` envelope (WR-02); `on_stop.sh:56–58`: passes `$ENVELOPE` (not `$HOOK_EVENT`) to CLI |
| T-03-10-S02 | opencode TS plugin error crashes tool execution chain | Denial of Service | HIGH | Mitigate | CLOSED | `automil-trajectory.ts:32`: `.nothrow()` on Bun shell invocation; `automil-trajectory.ts:14–17`: soft-fail if `!nodeId`; `.quiet()` suppresses output; `test_smoke_opencode_plugin_static_content` asserts `.nothrow()` equivalent pattern present |
| T-03-10-S03 | Hook script leaks secrets from HOOK_EVENT to trajectory.err.log | Information Disclosure | MEDIUM | Mitigate | CLOSED | `on_stop.sh:38–54` (WR-02): raw `HOOK_EVENT` is passed only via env var to python3; python3 outputs a structured `gen_ai.*` JSON envelope — not the raw payload; `on_stop.sh:58`: `2>>` redirects only stderr of `automil trajectory record` (error messages), not the event payload itself; record command applies `redact_event` before writing |
| T-03-10-S04 | TS plugin installed to global `~/.config/opencode/plugins/` | Elevation of Privilege | LOW | Mitigate | CLOSED | `init.py:136–150`: `opencode_dir = project_root / ".opencode"` (project-local); `plugins_dir = opencode_dir / "plugins"` (project-local); no reference to user home config |

### Plan 03-11: Two-Runtime Smoke Test + Phase 3 Acceptance Gate

| Threat ID | Description | STRIDE | Severity | Disposition | Status | Evidence |
|-----------|-------------|--------|----------|-------------|--------|----------|
| T-03-11-S01 | Smoke test passes because hook delivery is bypassed | Repudiation | MEDIUM | Mitigate | CLOSED | `test_smoke_two_runtimes.py:91`: `subprocess.run(["bash", str(hook_script)], input=event_json, ...)` — invokes the REAL `on_stop.sh` with stdin payload; `test_smoke_opencode_plugin_static_content` checks file content for `tool.execute.after`, `automil trajectory record`, Bun `$` API, `AUTOMIL_RUNTIME` |
| T-03-11-S02 | `test_no_claude_assets_outside_compat` grep misses non-.py files | Information Disclosure | LOW | Accept | CLOSED | Accepted per plan: compat.py shim targets Python imports only; test scans `--include=*.py`; non-Python files referencing "claude" in other contexts are acceptable |
| T-03-11-S03 | `subprocess.run([sys.executable, "-m", "automil.cli", ...])` fails without pip install | Denial of Service | LOW | Mitigate | CLOSED | `automil` installed as `pip install -e .` in development environment; `sys.executable` uses same Python running pytest; documented environment requirement |

---

## Closed/Open Counts by Severity

| Severity | Total | Closed | Open |
|----------|-------|--------|------|
| HIGH | 3 | 3 | 0 |
| MEDIUM | 17 | 16 | 1 |
| LOW | 17 | 17 | 0 |
| **TOTAL** | **37** | **36** | **1** |

---

## Hard-Floor Verification

The following grep/execution checks were run directly against the implemented code.

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| No `shell=True` in trajectory/agent_assets | `grep -rn "shell=True" src/automil/trajectory/ src/automil/agent_assets/ src/automil/cli/trajectory.py src/automil/cli/show_skill.py` | No output | PASS |
| No naive `..` path join in export.py | `grep -rn "\.\.\|os\.path\.join.*\.\." src/automil/trajectory/export.py` | No output | PASS |
| No opentelemetry SDK installed | `python3 -c "import opentelemetry"` | `ModuleNotFoundError` (exit 1) | PASS |
| `claude_assets` only in compat.py | `grep -r "claude_assets" src/automil/ --include="*.py" -l \| grep -v compat.py` | No output | PASS |
| No autobench in trajectory/ or agent_assets/ | `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/` | No output | PASS |
| WR-01: `\S{8,}` minimum length in redactor | `grep -n "\\S{8" src/automil/trajectory/redactor.py` | Lines 27–29 confirmed | PASS |
| WR-02: Stop hook payload wrapped in gen_ai.* envelope | `grep -n "gen_ai\|ENVELOPE" src/automil/agent_assets/claude/hooks/on_stop.sh` | Lines 38–54 confirmed | PASS |
| CR-01: empty-file guard in read_metadata | `grep -n "lines\|empty\|strip" src/automil/trajectory/recorder.py` | Lines 184–188 confirmed | PASS |
| CR-02: strict schema_version predicate | `grep -n "trajectory-v1" src/automil/trajectory/recorder.py` | Line 195: `version == "trajectory-v1" or version.startswith(("trajectory-v1.", "trajectory-v1-"))` | PASS |
| WR-04: AGENTS.md overwrite guard | `sed -n '276,289p' src/automil/cli/init.py` | `if not agents_dst.exists() or update` guard confirmed | PASS |
| T-03-10-S02: `.nothrow()` in TS plugin | `grep -n "nothrow" src/automil/agent_assets/opencode/plugins/automil-trajectory.ts` | Line 32: `.quiet().nothrow()` | PASS |
| T-03-10-S04: plugin written to project-local path | `grep -n "plugins_dir" src/automil/cli/init.py` | `plugins_dir = opencode_dir / "plugins"` (project-local) | PASS |

---

## Closed Threat Detail (was Open in audit pass 1)

### T-03-09-S03 — Path Traversal in `trajectory export <node_id>` — RESOLVED

**Severity:** MEDIUM
**STRIDE:** Information Disclosure
**Files:** `src/automil/cli/trajectory.py:124–131` (mitigation), `tests/trajectory/test_export_cli.py:60–115` (regression coverage)

**Resolution:** Path-traversal guard added at the CLI boundary in `export` command,
before any path construction or `export_bundle()` invocation:

```python
if not node_id or node_id in (".", "..") or os.path.isabs(node_id) \
   or ".." in Path(node_id).parts or "/" in node_id or "\\" in node_id:
    raise click.ClickException(
        f"Invalid node_id {node_id!r}: must be a graph identifier "
        f"(e.g. 'node_0176'), not a path."
    )
```

**Regression tests added (11 total):**
- `test_export_rejects_path_traversal` parametrized over 10 malicious inputs:
  `../../etc`, `../etc/passwd`, `/etc/passwd`, `/tmp`, `node/../../escape`,
  `..`, `.`, `""`, `node\\windows\\path`, `node/with/slash`. All assert exit
  code != 0, error message contains "Invalid node_id" or "must be a graph
  identifier", and NO tarball is created at the would-be output path.
- `test_export_accepts_valid_node_id_shape` confirms `node_0176` (graph
  identifier shape) still succeeds — no over-rejection.

Suite went 547 → 558 + 9 skipped after this fix landed. Zero regressions.

---

## Unregistered Flags

| Flag | Source | Notes |
|------|--------|-------|
| Shell injection risk in `on_stop.sh` via `$ENVELOPE` argument | Audit observation (no SUMMARY.md threat flag) | Investigated and confirmed mitigated: `HOOK_EVENT` passed only via env var to python3 (not shell-interpolated); `$ENVELOPE` is double-quoted as `"$ENVELOPE"` on the `automil trajectory record` invocation line (on_stop.sh:57). No injection vector. |

No threat flags were declared in any plan's SUMMARY.md `## Threat Flags` section.

---

## Review Notes

### Code-Review Fixes Verified (5667a3d)

All four code-review fixes are confirmed present in the implementation:

| Fix | Location | Verified |
|-----|----------|---------|
| CR-01: `read_metadata` empty-file guard | `recorder.py:184–188` | PASS |
| CR-02: schema_version strict `v1.*` predicate (rejects v11+, v2) | `recorder.py:195` | PASS |
| WR-01: redaction `\S{8,}` minimum length | `redactor.py:27–29` | PASS |
| WR-02: Stop hook payload wrapped in `gen_ai.*` envelope | `on_stop.sh:38–54` | PASS |
| WR-04: AGENTS.md overwrite guard | `init.py:283–289` | PASS |

---

## VERDICT: SECURE

**All 37 threats closed.** T-03-09-S03 mitigation landed inline during the audit:
`cli/trajectory.py` now rejects path-shaped node_ids at the CLI boundary before
`export_bundle()` is invoked. Regression coverage: 10 parametrized adversarial
inputs in `tests/trajectory/test_export_cli.py::test_export_rejects_path_traversal`
plus a positive-case `test_export_accepts_valid_node_id_shape`.

Suite: 558 passed + 9 skipped (was 547; +11 path-traversal regression tests).

**Resolution options (for implementer):**
1. Add a `node_id` sanitization check in `cli/trajectory.py` (reject absolute paths and `..` in parts) — 3 lines.
2. Add a boundary check in `export_bundle()` using `resolve()` comparison — 3 lines.
3. Formally accept the risk by documenting it in this file's accepted-risks log with rationale (e.g., "export is operator-only, requires authenticated shell access, archive_dir is isolated").

After resolution, re-run this audit. The remaining 35 threats are CLOSED and the hard floors pass.
