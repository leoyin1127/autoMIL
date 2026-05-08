---
phase: 03-trajectory-recorder-multi-runtime-asset-reorganisation
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - src/automil/trajectory/__init__.py
  - src/automil/trajectory/schema.py
  - src/automil/trajectory/redactor.py
  - src/automil/trajectory/recorder.py
  - src/automil/trajectory/rotation.py
  - src/automil/trajectory/export.py
  - src/automil/runtime.py
  - src/automil/agent_assets/_overlay.py
  - src/automil/agent_assets/__init__.py
  - src/automil/cli/init.py
  - src/automil/cli/show_skill.py
  - src/automil/cli/trajectory.py
  - src/automil/cli/submit.py
  - src/automil/cli/__init__.py
  - src/automil/compat.py
  - src/automil/agent_assets/claude/hooks/on_stop.sh
  - src/automil/agent_assets/opencode/plugins/automil-trajectory.ts
  - src/automil/templates/.gitignore.j2
  - src/automil/templates/config.yaml.j2
  - tests/trajectory/test_recorder.py
  - tests/trajectory/test_record_cli.py
  - tests/trajectory/test_export_cli.py
  - tests/trajectory/test_redactor.py
  - tests/trajectory/test_schema.py
  - tests/trajectory/test_rotation.py
  - tests/agent_assets/test_overlay.py
  - tests/agent_assets/test_show_skill.py
  - tests/agent_assets/test_init_runtime.py
  - tests/agent_assets/test_smoke_two_runtimes.py
  - tests/test_compat.py
  - tests/test_runtime.py
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-05-03
**Depth:** standard
**Files Reviewed:** 23 production + 11 test files
**Status:** issues_found

## Summary

Phase 3 ships the trajectory recorder (`recorder.py`, `redactor.py`, `rotation.py`, `schema.py`, `export.py`), multi-runtime asset reorganisation (`agent_assets/_overlay.py`, `cli/init.py`, `on_stop.sh`, `automil-trajectory.ts`), and the `compat.py` `claude_assets` shim. The D-86 fd-cache architecture is correctly implemented — open fds are cached per trajectory path, never opened-and-closed per event, and `atexit` closes all cached fds on process exit. The hard floor grep checks all pass: no `opentelemetry`, no `claude_assets` outside `compat.py`, no `autobench` in `trajectory/`/`agent_assets/`.

Two blockers were found: an `IndexError` crash in the public `read_metadata` API on empty/post-rotation files, and a schema version check logic gap that silently accepts `trajectory-v3`, `trajectory-v11`, `trajectory-v99`, etc. when they should raise `TrajectorySchemaError`. Five warnings cover redaction false-positives on common shell variables, a mismatch between the Claude Code stop-hook payload schema and the `gen_ai.*` schema expected by `trajectory record`, misleading documentation in `config.yaml.j2`, an unconditional overwrite of `AGENTS.md`, and an unlocked mutation of `_FD_CACHE` during soft rotation.

---

## Critical Issues

### CR-01: `read_metadata` raises bare `IndexError` on empty or blank-first-line file

**File:** `src/automil/trajectory/recorder.py:180`

**Issue:** `read_metadata` is a public API. It calls `path.read_text().splitlines()[0]` with no guard. When the trajectory file is empty (which is a real post-rotation scenario: `_do_soft_rotate` only writes the metadata header if `first_line` is truthy at line 122; if `_read_first_line` returns `None` due to any read error, the rotated-in `trajectory.jsonl` is empty), this raises an unguarded `IndexError` — not a `TrajectorySchemaError`. Callers (including `export_bundle`, the smoke tests, and user code) do not expect `IndexError` from this function.

```python
# recorder.py line 180-191 — current (broken)
line = path.read_text(encoding="utf-8").splitlines()[0]   # IndexError if empty
meta = json.loads(line)                                    # JSONDecodeError if blank line
```

**Fix:**
```python
def read_metadata(path: Path) -> dict:
    from automil.trajectory.schema import TrajectorySchemaError
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    if not lines or not lines[0].strip():
        raise TrajectorySchemaError(
            f"Trajectory file {path} is empty or has a blank first line; "
            "cannot read metadata header (D-80)"
        )
    line = lines[0]
    meta = json.loads(line)          # json.JSONDecodeError propagates to caller as-is
    version = meta.get("schema_version", "")
    ...
```

---

### CR-02: Schema version check silently accepts `trajectory-v3`, `trajectory-v11`, `trajectory-v99`

**File:** `src/automil/trajectory/recorder.py:183-190`

**Issue:** The version guard is logically flawed. The intent (per D-80) is: accept `trajectory-v1.*` only; raise on anything else. The current condition is:

```python
# recorder.py lines 183-190 — current (broken logic)
if version.startswith("trajectory-v2") or (
    version and not version.startswith("trajectory-v1")
    and not version.startswith("trajectory-v")
):
    raise TrajectorySchemaError(...)
```

For `"trajectory-v3"`:
- `startswith("trajectory-v2")` → `False`
- `version` is truthy → `True`
- `not startswith("trajectory-v1")` → `True`
- `not startswith("trajectory-v")` → `False` ← **short-circuits to False**

Result: the compound `and` evaluates to `False`, no raise, `trajectory-v3` is silently accepted as a valid v1-reader-compatible file. Same for `trajectory-v11`, `trajectory-v99`, etc.

**Fix:** Use a direct allowlist:
```python
version = meta.get("schema_version", "")
# Accept: trajectory-v1 and trajectory-v1.<minor> only.
# Reject: trajectory-v2+, unknown, empty.
if not version.startswith("trajectory-v1"):
    raise TrajectorySchemaError(
        f"Unsupported schema_version '{version}'; "
        "this reader supports trajectory-v1.* only (D-80)"
    )
```

This is simpler, correct, and matches the stated D-80 contract exactly. The existing test `test_read_metadata_v2_raises` passes with this fix. A new test for `trajectory-v3` should be added.

---

## Warnings

### WR-01: Redaction false-positives on common shell variables

**File:** `src/automil/trajectory/redactor.py:21-23`

**Issue:** The `_KEY`, `_TOKEN`, and `_API_KEY` patterns match any `UPPERCASE_NAME=<non-whitespace>` combination with no minimum value length. The following strings are falsely redacted:

```
CACHE_KEY=abc123        → CACHE_KEY=[REDACTED]    (build cache key — not a secret)
PUBLIC_KEY=/path/to.pub → PUBLIC_KEY=[REDACTED]   (file path — not a secret)
NO_API_KEY=true         → NO_API_KEY=[REDACTED]   (boolean flag — not a secret)
DISK_KEY=path           → DISK_KEY=[REDACTED]      (config value — not a secret)
GIT_TOKEN=github.com    → GIT_TOKEN=[REDACTED]     (URL — not a secret, but redacted)
```

The root cause is the absence of a minimum value length on the right-hand side of the `=`. A real API key is typically ≥16 characters. The test suite covers only positive cases (known token formats) and one false-positive suite (`sk-short`, `task_key_index`), but misses these assignment-form false positives.

**Fix options (ranked by preference):**

1. Add minimum value length `\S{8,}` instead of `\S+` to the `_KEY`/`_TOKEN`/`_API_KEY` patterns:
```python
(re.compile(r"([A-Z][A-Z0-9_]{1,40}_API_KEY)\s*[:=]\s*\S{8,}"), r"\1=[REDACTED]"),
(re.compile(r"([A-Z][A-Z0-9_]{1,40}_TOKEN)\s*[:=]\s*\S{8,}"),   r"\1=[REDACTED]"),
(re.compile(r"([A-Z][A-Z0-9_]{1,40}_KEY)\s*[:=]\s*\S{8,}"),     r"\1=[REDACTED]"),
```

2. Add false-positive guard tests for `CACHE_KEY=abc123`, `NO_API_KEY=true`, `PUBLIC_KEY=/path` to `test_redactor.py::test_redact_not_triggered`.

---

### WR-02: `on_stop.sh` passes raw Claude stop-hook payload to `trajectory record` — events silently dropped in production

**File:** `src/automil/agent_assets/claude/hooks/on_stop.sh:28`

**Issue:** The script captures the Claude Code stop-hook payload (`HOOK_EVENT="$(cat)"`) and passes it directly to `automil trajectory record "$HOOK_EVENT"`. The Claude Code `Stop` hook delivers a control payload on stdin with fields `{session_id, transcript_path, stop_hook_active}` — not the `gen_ai.*` schema that `validate_event` requires. In production, every stop-hook event fails schema validation (`record_event` returns `False`) and is silently dropped. No stop events ever appear in `trajectory.jsonl`.

The acceptance test `test_smoke_claude_hook_script` passes because it pipes a **crafted** `gen_ai.*` event JSON as stdin — not the real Claude stop payload. The test verifies the `stdin → HOOK_EVENT → record` mechanism but not the semantic compatibility with the actual hook payload.

**Fix:** The hook should construct a `gen_ai.*`-compliant event from the Claude payload fields:

```bash
# In on_stop.sh, replace the direct pass-through:
if [[ -n "${AUTOMIL_NODE_ID:-}" && -n "${AUTOMIL_RUNTIME:-}" && -n "$HOOK_EVENT" ]]; then
    # Wrap the raw stop payload in a gen_ai.* envelope
    TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%S.000000Z 2>/dev/null || echo 'unknown')"
    WRAPPED_EVENT="{\"gen_ai.provider.name\":\"${AUTOMIL_RUNTIME}\",\"gen_ai.event.name\":\"agent_stop\",\"gen_ai.event.timestamp\":\"${TIMESTAMP}\",\"hook_payload\":${HOOK_EVENT}}"
    automil trajectory record "$WRAPPED_EVENT" \
        2>>"${AUTOMIL_DIR:-/tmp}/trajectory.err.log" || true
fi
```

Alternatively, extend `validate_event` to also accept a `hook_payload` fallback schema, or add a `--raw` flag to `trajectory record` that bypasses schema validation for hook payloads.

---

### WR-03: `config.yaml.j2` passthrough declares `AUTOMIL_*` glob as if it enables glob matching — it does not

**File:** `src/automil/templates/config.yaml.j2:100-102`

**Issue:** The template renders this passthrough configuration into every new project's `config.yaml`:

```yaml
env:
  passthrough:
    - AUTOMIL_*       # All automil framework variables (includes AUTOMIL_RUNTIME)
    - AUTOMIL_RUNTIME # Runtime declaration — explicit, never inferred (D-87)
```

The comment claims `AUTOMIL_*` covers all automil framework variables. It does not. The orchestrator's `_build_subprocess_env` (line 559-562 of `_orchestrator_daemon.py`) processes passthrough as **literal key names only** (documented in the code: "Config passthrough — literal names only"). The string `AUTOMIL_*` is checked as `if "AUTOMIL_*" in os.environ` which is always `False`. The glob never matches anything.

Meanwhile, `AUTOMIL_RUNTIME` in the list is also redundant — `AUTOMIL_RUNTIME` is already forwarded by the **system whitelist** (`_SYSTEM_ENV_WHITELIST_PREFIX = ("AUTOMIL_",)` at line 62 of `_orchestrator_daemon.py`), which covers all `AUTOMIL_*`-prefixed vars via `str.startswith`.

**Effect:** The passthrough section is inert for AUTOMIL vars but misleads operators into thinking glob patterns work. Users may add `MY_CUSTOM_*` expecting it to glob-match.

**Fix:** Replace with accurate documentation:
```yaml
env:
  passthrough:
    # Literal variable names only — no glob patterns.
    # AUTOMIL_* vars are forwarded automatically by the orchestrator's system whitelist.
    # Add other env vars your training script needs here, e.g.:
    #   - WANDB_API_KEY
    #   - MLFLOW_TRACKING_URI
```

---

### WR-04: `AGENTS.md` unconditionally overwritten on every `automil init` and `automil init --update`

**File:** `src/automil/cli/init.py:277-281`

**Issue:** The init command writes `AGENTS.md` unconditionally:

```python
# init.py lines 277-281 — current (overwrites unconditionally)
agents_shared = package_dir / "agent_assets" / "_shared" / "AGENTS.md"
if agents_shared.exists():
    agents_content = agents_shared.read_text(encoding="utf-8")
    (project_root / "AGENTS.md").write_text(agents_content, encoding="utf-8")  # NO existence check
    click.echo("  Created: AGENTS.md")
```

Every other asset has an existence guard: skills files (`if not dst.exists():` at line 107), `CLAUDE.md` (`if not claude_md.exists():` at line 124), `.opencode/AGENTS.md` (`if not dst.exists():` at line 143), `.codex/instructions.md` (`if not instructions.exists():` at line 162). `AGENTS.md` is the odd one out.

On `automil init --update`, any user customizations to the project-root `AGENTS.md` are silently destroyed and replaced with the bundled template. The confirmation message still says "Created: AGENTS.md" even when overwriting.

**Fix:**
```python
agents_dst = project_root / "AGENTS.md"
if not agents_dst.exists():          # guard: only write if not already present
    agents_dst.write_text(agents_content, encoding="utf-8")
    click.echo("  Created: AGENTS.md")
elif update:
    # --update explicitly re-renders: overwrite but warn
    agents_dst.write_text(agents_content, encoding="utf-8")
    click.echo("  Updated: AGENTS.md (--update)")
```

---

### WR-05: `_do_soft_rotate` mutates `fd_cache` without holding `_DICT_LOCK`

**File:** `src/automil/trajectory/rotation.py:107-113`

**Issue:** `_do_soft_rotate` receives `fd_cache` (which IS `recorder._FD_CACHE`) as a parameter and calls `fd_cache.pop(fd_key)` without acquiring `_DICT_LOCK`:

```python
# rotation.py lines 107-113
fd_key = str(path)
if fd_key in fd_cache:
    fd = fd_cache.pop(fd_key)   # no _DICT_LOCK held here
    try:
        os.close(fd)
    except OSError:
        pass
```

`recorder._close_all_fds` (the `atexit` handler) holds `_DICT_LOCK` while iterating and clearing `_FD_CACHE`. A concurrent `_do_soft_rotate` call (from a different thread, different node) mutating the dict without the lock is technically a data race.

Under CPython's GIL, `dict.pop` is atomic and a double-close cannot occur in practice (the pop removes the entry before `os.close`, so `atexit` never sees it). However, this is a CPython-only safety guarantee. The correct fix documents or enforces it explicitly.

**Fix:** Either acquire `_DICT_LOCK` in `_do_soft_rotate`, or add a module-level comment stating the GIL dependency and make `rotation.py` import and use `_DICT_LOCK` from `recorder.py`. The latter requires a circular-import-safe pattern (e.g., passing the lock as a parameter alongside `fd_cache`).

---

## Info

### IN-01: `export_bundle` accepts `node_id` with path traversal sequences — reads outside `archive_dir`

**File:** `src/automil/trajectory/export.py:34-47`

**Issue:** `export_bundle` constructs `node_archive = archive_dir / node_id` with no validation of `node_id`. A `node_id` containing `..` (e.g., `../../etc`) would traverse outside the archive directory. `node_archive.exists()` would pass for any existing filesystem path, potentially exposing unintended files if `trajectory*.jsonl` patterns match.

The actual attack surface is low (the CLI user controls both `node_id` and `archive_dir`, and requires local filesystem write access), but the default tarball output path `Path.cwd() / f"{node_id}.trajectory.tar.gz"` would write to unexpected locations (e.g., `../../etc/passwd.trajectory.tar.gz` → `/etc/passwd.trajectory.tar.gz`) if `node_id` is path-like.

**Fix:**
```python
# In export_bundle, add after the signature:
from pathlib import PurePosixPath
node_parts = PurePosixPath(node_id).parts
if any(p == ".." for p in node_parts) or PurePosixPath(node_id).is_absolute():
    raise ValueError(f"Invalid node_id {node_id!r}: must be a simple name with no path components")
```

---

### IN-02: `export.py` imports private `_PATTERNS` from `redactor.py`

**File:** `src/automil/trajectory/export.py:13`

**Issue:**
```python
from automil.trajectory.redactor import redact_event, _PATTERNS
```

`_PATTERNS` is a module-private symbol (underscore-prefixed). The import creates a brittle coupling: renaming `_PATTERNS` in `redactor.py` silently breaks `export.py` at import time rather than via a type error. The import is used only for computing the `rule_hash` in the manifest.

**Fix:** Expose a public function in `redactor.py` for the hash:
```python
# redactor.py — add this public function
def redaction_rule_hash() -> str:
    """Return a short deterministic hash of the current compiled redaction rules."""
    return hashlib.sha256(
        "|".join(p.pattern for p, _ in _PATTERNS).encode()
    ).hexdigest()[:16]
```

Then in `export.py`:
```python
from automil.trajectory.redactor import redact_event, redaction_rule_hash
...
rule_hash = redaction_rule_hash()
```

---

## Grep Sanity Results

All D-99 hard floor checks passed:

| Check | Result |
|---|---|
| `grep -rn "os\.kill\|subprocess\.Popen\|\.pid" trajectory/ agent_assets/ runtime.py` | 0 matches |
| `grep -rn "import opentelemetry" src/automil/` | 0 matches |
| `grep -rn "claude_assets" src/automil/ --include="*.py" \| grep -v compat.py` | 0 matches |
| `grep -rn "autobench\|AUTOBENCH_\|benchmarks/" trajectory/ agent_assets/` | 0 matches |

---

_Reviewed: 2026-05-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

---

## REVIEW COMPLETE — 2 Critical, 5 Warning, 2 Info
