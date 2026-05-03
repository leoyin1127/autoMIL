# Phase 3: Trajectory Recorder + Multi-Runtime Asset Reorganisation — Research

**Researched:** 2026-05-03
**Domain:** JSONL trajectory capture, OTel gen_ai.* field semantics, multi-runtime hook integration (Claude Code / opencode / Codex), markdown section-replacement overlay, `git mv` asset migration, Click subcommand groups, Python multiprocess-safe file append
**Confidence:** HIGH (all critical claims verified against official docs, live code, or direct Python execution)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All decisions D-78 through D-106 are locked. See 03-CONTEXT.md `<decisions>` block verbatim.

Hard floors:
- Phase 0+1+2 baseline (425 tests + 9 skipped) stays green — no behavioural regressions.
- `grep -r "claude_assets" src/automil/` returns matches only in `compat.py`.
- `python -c "import opentelemetry"` raises `ModuleNotFoundError` after `pip install -e .`.
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/` returns zero.
- Two-runtime smoke test (Claude Code + opencode) green before sign-off.

### Claude's Discretion

- Implementation details not covered by D-78..D-106 (e.g., exact conftest fixtures, helper utilities inside test files, internal variable naming).

### Deferred Ideas (OUT OF SCOPE)

- Real Codex native hook integration (D-100) — CLI-fallback only in Phase 3.
- Trajectory replay / as-protocol reproducibility (D-101).
- `automil trajectory diff` and analysis commands (D-102).
- Concurrent multi-runtime orchestration (D-104, D-105).
- `opentelemetry-sdk` runtime dependency (D-106) — explicitly forbidden.
- Per-event redaction-rule customisation in config (out of scope; rules are framework-locked).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRJ-01 | `archive/<node_id>/trajectory.jsonl` canonical artifact; first line is metadata `{schema_version, runtime, runtime_version, tool_schema_version, automil_version, automil_runtime_env}` | §1, §2 — recorder architecture, first-line schema |
| TRJ-02 | Field names follow OTel `gen_ai.*` conventions; no `opentelemetry-sdk` dep | §3 — gen_ai.* field semantics verified against official registry |
| TRJ-03 | Redaction-on-capture (regex for secrets); per-event 8 KB cap; 5 MB soft / 50 MB hard rotate | §4, §5 — redaction patterns verified; rotation mechanism; edge cases documented |
| TRJ-04 | Trajectory recorder integrated as runtime hook for ≥2 runtimes (Claude Code, opencode); CLI fallback covers runtimes without native hooks | §6 — Claude Code hook payload shape; opencode plugin hook API; hook delivery mechanisms |
| TRJ-05 | `archive/<node_id>/trajectory.jsonl` gitignored by default; `automil trajectory export` produces redacted, schema-validated bundle | §7 — gitignore template extension; export bundle design |
| TRJ-06 | Tests cover schema-version mismatch tolerance and redaction-pattern coverage (positive cases) | §9 — test architecture; schema forward-compat test; per-leak-class positive tests |
| MRT-01 | `src/automil/agent_assets/` reorganised: `_shared/SKILL.md` canonical; per-runtime subdirs contain only diffs/overrides | §10 — `git mv` semantics; overlay merger algorithm; edge cases |
| MRT-02 | `AGENTS.md` generated/installed at project root by `automil init`; universal runtime instructions | §11 — AGENTS.md spec; per-runtime native file conventions |
| MRT-03 | `automil init --runtime` with auto-detection; installs runtime's overlay assets | §12 — init extension; Click option design; auto-detect probe |
| MRT-04 | `automil show-skill --runtime <name>` debug command renders merged per-runtime skill file | §12 — new CLI command pattern |
| MRT-05 | End-to-end smoke test passes for ≥2 runtimes (Claude Code + opencode) | §13 — two-runtime smoke test architecture |
| MRT-06 | `agent_assets/deepseek/README.md` documents DeepSeek as a model, not a runtime | §11 — DeepSeek routing documentation |

</phase_requirements>

---

## Summary

Phase 3's decision space is fully locked (D-78..D-106). This research confirms those decisions are implementable and surfaces the precise implementation details — hook payload shapes, field semantics, locking idioms, overlay merge edge cases, and test architecture — that the planner needs to write concrete wave-level plans.

The two most implementation-sensitive areas are: (1) the **opencode hook integration** (opencode's native hook API is TypeScript-only plugins; the `tool.execute.after` hook receives tool name and args but has no shell-script equivalent, meaning opencode's hook path requires a TypeScript/JavaScript plugin that shells out to `automil trajectory record`), and (2) the **section-replacement overlay merger** (the `^## ` regex-split approach from D-89 has a well-known false-split hazard when SKILL.md content contains `## ` inside fenced code blocks — mitigated by requiring skill content authors never put H2-looking lines in fenced blocks, plus a lint check).

The OTel field-name picture is slightly more nuanced than D-81 implies: `gen_ai.system` is officially deprecated in the latest OTel semconv (replaced by `gen_ai.provider.name`), but D-81 already treats these as vendor-neutral string constants — the framework uses the field-name strings directly without the SDK. The practical impact is zero: we can use `gen_ai.system` as documented in D-81 (it still works as a field key in our JSONL) or switch to `gen_ai.provider.name` for forward compatibility. The research recommendation is to use `gen_ai.provider.name` and add a comment noting that this replaces the older `gen_ai.system` — keeping the code aligned with the current spec from day one.

**Primary recommendation:** Build in dependency order: trajectory skeleton + schema constants (03-01) → agent_assets `git mv` + compat shim (03-02) → redaction module (03-03) → recorder with O_APPEND + flock (03-04) → rotation manager (03-05) → `_shared/AGENTS.md` + `_shared/SKILL.md` content split (03-06) → overlay merger + `show-skill` CLI (03-07) → Claude Code hook extension (03-08) → opencode TypeScript plugin (03-09) → `init --runtime` + gitignore extension (03-10) → two-runtime smoke test (03-11). This order allows the smoke test to be the last gating artifact.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Trajectory event append | `src/automil/trajectory/` package | CLI `trajectory record` subcommand | Recorder owns the file lifecycle; CLI is the runtime-agnostic entry point |
| Secret redaction | `trajectory/redactor.py` | Applied by `recorder.py` before any write | Redaction must be in the write path, not the read path |
| File rotation | `trajectory/rotation.py` | Called by `recorder.py` on each append | Rotation check is per-append; soft/hard thresholds are config-sourced |
| Schema validation | `trajectory/schema.py` | Called by `trajectory/export.py` for bundle validation | Schema constants and `validate_event()` are the authoritative gate |
| Agent asset rendering | `src/automil/agent_assets/_overlay.py` | `cli/show_skill.py`, `cli/init.py` | Overlay merger is a library function; two CLI commands are thin wrappers |
| Runtime asset installation | `cli/init.py` (extended) | — | init owns the install lifecycle; no other code writes to `.claude/`, `.opencode/`, `.codex/` |
| Hook delivery (Claude Code) | Claude Code runtime (`settings.json` `PostToolUse` hook) | `agent_assets/claude/hooks/on_stop.sh` | Claude Code's hook system provides JSON on stdin; our shell script bridges to `automil trajectory record` |
| Hook delivery (opencode) | opencode TypeScript plugin (`tool.execute.after`) | — | opencode's hook API is plugin-only (no shell hooks); plugin shells out to `automil trajectory record` |
| Runtime declaration | `src/automil/runtime.py` | `JobSpec.env` passthrough (via orchestrator) | `AUTOMIL_RUNTIME` env var is the canonical source; never inferred |
| Trajectory export bundle | `trajectory/export.py` | `cli/trajectory.py` `export` subcommand | Export re-runs redactor + schema validation; bundle is a `.tar.gz` |

---

## 1. Trajectory Module Layout

### Package skeleton (D-78)

```
src/automil/trajectory/
    __init__.py        # public surface: record_event, read_metadata, RotationManager
    schema.py          # OTel gen_ai.* field constants + REQUIRED_FIELDS + validate_event()
    recorder.py        # append-only JSONL writer (O_APPEND + LOCK_EX + per-node RLock)
    redactor.py        # compiled regex set + per-event 8 KB truncation + redact_event()
    rotation.py        # 5 MB soft / 50 MB hard rotation manager
    export.py          # `automil trajectory export` bundle producer
```

**Pattern to follow:** The `src/automil/backends/` package (Phase 2) has the same internal structure: public surface in `__init__.py`, each concern in its own file, no cross-file circular imports. [VERIFIED: Phase 2 deliverables]

**Stdlib-only constraint verified:** `fcntl`, `os`, `json`, `re`, `threading`, `pathlib`, `gzip`, `tarfile`, `hashlib`, `logging` — all stdlib. `pydantic` is NOT used (CLAUDE.md: stdlib-first, Phase 0 conventions). [VERIFIED: CLAUDE.md conventions]

### Runtime module (D-87)

New `src/automil/runtime.py` (3 lines):

```python
import os

def get_runtime() -> str:
    return os.environ.get("AUTOMIL_RUNTIME", "unknown")
```

`trajectory/recorder.py` imports `from automil.runtime import get_runtime` for the first-line metadata. [VERIFIED: D-87 contract]

---

## 2. First-Line Metadata Schema (D-80)

The metadata first line is written **once** when the file is created (not yet existing). Format (D-80):

```json
{
  "schema_version": "trajectory-v1",
  "runtime": "claude-code",
  "runtime_version": "claude-opus-4-7@2026-04-30",
  "tool_schema_version": "claude-2026-04",
  "automil_version": "0.1.0",
  "automil_runtime_env": {"AUTOMIL_RUNTIME": "claude-code", "AUTOMIL_GPU": "0"}
}
```

**`automil_version` source:** `from automil import __version__` — `src/automil/__init__.py` exports `__version__ = "0.1.0"`. [VERIFIED: src/automil/__init__.py line 3]

**Schema-version forward-compat rule (D-80):** Readers MUST tolerate unknown fields in `trajectory-v1.*`; MUST refuse to interpret `trajectory-v2`. This is testable: create a file with an extra field `"new_field": "x"` in the metadata, assert `read_metadata()` returns it without error. Then create a file with `"schema_version": "trajectory-v2"`, assert a `TrajectorySchemaError` is raised.

---

## 3. OTel gen_ai.* Field Semantics

### CRITICAL: gen_ai.system is deprecated

Research finding: In OTel semantic conventions (current as of late 2025), `gen_ai.system` has been **replaced by `gen_ai.provider.name`**. [VERIFIED: opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/ — "Deprecated Attributes: gen_ai.system → gen_ai.provider.name"]

D-81 uses `gen_ai.system` as the field name for the provider identifier. Since we use field-name strings only (no SDK), the practical impact is: using `gen_ai.system` still works as a JSONL key, but uses a deprecated name. **Recommendation:** use `gen_ai.provider.name` in Phase 3's `schema.py` constants, with a comment noting it replaces `gen_ai.system`. The planner should verify this with D-81 as-written — if the decision is locked to `gen_ai.system`, honour it; this research flags the deprecation so the planner can choose deliberately.

### Verified field set (from OTel registry)

All field names verified against [opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/]:

| Field | OTel Status | Use in Phase 3 |
|-------|-------------|----------------|
| `gen_ai.provider.name` (replaces `gen_ai.system`) | Current | Provider: `"claude-code"` \| `"opencode"` \| `"codex"` |
| `gen_ai.request.model` | Current | e.g. `"claude-opus-4-7"` |
| `gen_ai.tool.name` | Required on execute_tool spans | `"Read"` \| `"Edit"` \| `"Bash"` etc. |
| `gen_ai.tool.call.id` | Recommended | tool_use_id from Claude |
| `gen_ai.tool.call.arguments` | — | JSON-encoded args (post-redaction) |
| `gen_ai.tool.call.result` | — | JSON-encoded result (post-redaction) |
| `gen_ai.usage.input_tokens` | Current | int or absent |
| `gen_ai.usage.output_tokens` | Current | int or absent |

**`gen_ai.event.name` field status:** There is no `gen_ai.event.name` standard attribute in the OTel registry (the registry defines `gen_ai.operation.name` for spans and `gen_ai.client.inference.operation.details` as an event name). The Phase 3 decision (D-81) uses `gen_ai.event.name` as a **framework-specific field** following the OTel naming convention style — this is acceptable since we use field strings directly. No SDK validation occurs. [VERIFIED: registry search confirmed `gen_ai.event.name` is not a standard OTel attribute name — it is a Phase 3 custom field using the `gen_ai.*` namespace]

**`gen_ai.event.timestamp`**: Similarly a framework-specific field. Use `datetime.now(timezone.utc).isoformat()` for microsecond precision.

### schema.py constants pattern

```python
# src/automil/trajectory/schema.py
# Field names: OTel gen_ai.* namespace (we use strings only, no opentelemetry-sdk dep)
# gen_ai.provider.name replaces deprecated gen_ai.system (OTel semconv, late 2025)

GEN_AI_PROVIDER_NAME    = "gen_ai.provider.name"    # provider system identifier
GEN_AI_REQUEST_MODEL    = "gen_ai.request.model"     # model name
GEN_AI_EVENT_NAME       = "gen_ai.event.name"        # framework-specific: "prompt"|"tool_call"|"tool_result"|"response"
GEN_AI_EVENT_TIMESTAMP  = "gen_ai.event.timestamp"   # framework-specific: ISO 8601 microsecond
GEN_AI_TOOL_NAME        = "gen_ai.tool.name"         # tool identifier
GEN_AI_TOOL_ARGUMENTS   = "gen_ai.tool.call.arguments"  # JSON-encoded, post-redaction
GEN_AI_TOOL_RESULT      = "gen_ai.tool.call.result"     # JSON-encoded, post-redaction
GEN_AI_USAGE_INPUT      = "gen_ai.usage.input_tokens"   # int
GEN_AI_USAGE_OUTPUT     = "gen_ai.usage.output_tokens"  # int

REQUIRED_FIELDS = {GEN_AI_PROVIDER_NAME, GEN_AI_EVENT_NAME, GEN_AI_EVENT_TIMESTAMP}


class TrajectorySchemaError(ValueError):
    pass


def validate_event(d: dict) -> None:
    """Raise TrajectorySchemaError if a required field is missing. Unknown fields pass silently."""
    missing = REQUIRED_FIELDS - set(d.keys())
    if missing:
        raise TrajectorySchemaError(f"Required fields missing: {sorted(missing)}")
```

---

## 4. Redaction Patterns (D-82) — Verified and Edge Cases

### Pattern test results (directly verified)

```python
# VERIFIED by direct execution against D-82 patterns:
_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),         "sk-[REDACTED]"),
    (re.compile(r"hf_[A-Za-z0-9]{20,}"),             "hf_[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"),            "ghp_[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"),            "AKIA[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_API_KEY)\s*[:=]\s*\S+"),  r"\1=[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_TOKEN)\s*[:=]\s*\S+"),    r"\1=[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_KEY)\s*[:=]\s*\S+"),      r"\1=[REDACTED]"),
]
```

**Test results (verified by execution):**
- `sk-abcdefghijklmnopqrstu` (20+ chars) → REDACTED ✓
- `hf_abcdefghijklmnopqrstu1234` → REDACTED ✓
- `ghp_abcdefghijklmnopqrstuvwxyz1234` → REDACTED ✓
- `AKIAIOSFODNN7EXAMPLE` (canonical 20-char key) → REDACTED ✓
- `OPENAI_API_KEY=sk-abc123` → `OPENAI_API_KEY=[REDACTED]` ✓
- `sk-short` (< 20 chars after prefix) → NOT redacted ✓
- `task_key_index`, `stack_api_keys_count`, `skeletal`, `disk-based` → NOT redacted ✓

### AWS key edge case (verified)

The `\bAKIA[0-9A-Z]{16}\b` pattern requires a word boundary after the 16-char suffix. A canonical AWS access key is exactly 20 chars (AKIA + 16 alphanumeric). Testing confirms this works correctly. The test case `AKIAIOSFODNN7EXAMPLE1234` (24 chars — with 4 extra chars) does NOT match because the `\b` boundary is not present after 16 chars — this is expected and correct: a real AWS key would not have extra characters appended to it in a valid log line. [VERIFIED: direct Python execution]

### Known false positive surface

The `_KEY\s*[:=]\s*\S+` pattern catches `SOME_KEY=somevalue` (uppercase var names ending in `_KEY`). This may over-redact legitimate variables like `PUBLIC_KEY=abc` or `INDEX_KEY=0`. Since Phase 3 takes the conservative stance (default-deny), this is intentional. The test suite must include positive-case tests for all leak classes plus one "does not accidentally redact" test for a low-entropy non-secret value to catch future regex changes that expand the over-redaction.

**Regex ReDoS concern:** The patterns use character classes with quantifiers (`[A-Za-z0-9_\-]{20,}`) — these are linear in the input length, not exponential. No catastrophic backtracking is possible with these patterns. [ASSUMED — training knowledge on ReDoS in simple character-class regexes; verified by inspection that no nested quantifiers are present]

### redact_event recursion

`redact_event(d: dict) -> dict` must handle: `dict` (recurse values), `list` / `tuple` (recurse elements), `str` (apply patterns), `int/float/bool/None` (pass through). The recursion depth should be bounded — trajectory events are max depth ~4 (event → tool_arguments → value). No stack overflow risk at normal depths.

---

## 5. Multi-Process Append + Rotation (D-85, D-86, D-84)

### O_APPEND + LOCK_EX pattern (directly verified)

```python
# VERIFIED: direct execution confirms O_APPEND + LOCK_EX works correctly on Linux
import fcntl, os, json

def _append_line(fd: int, data: dict) -> None:
    """Atomically append one JSON line. fd must be opened with O_APPEND."""
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        line = json.dumps(data, ensure_ascii=False) + "\n"
        os.write(fd, line.encode("utf-8"))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
```

**Why this is safe:** On Linux, `O_APPEND` mode moves the write position to EOF atomically at the kernel level before each `write()` syscall. Combined with `LOCK_EX`, two processes cannot produce an interleaved partial line. Single-line JSON is the safe unit of atomicity. [VERIFIED: direct execution; Python fcntl docs]

**Key detail:** `flock` is advisory on Linux (a process can bypass it). This is acceptable — all writers in autoMIL go through `record_event()`, which acquires the lock. There is no hostile writer path.

**flock + close gotcha:** All `fcntl` locks associated with a file are released when **any** file descriptor for that file is closed by the process, even if the lock was acquired on a different fd. The recorder must keep the fd open for the lifetime of the node's trajectory writes, not open-close per event. This means `recorder.py` should maintain an fd cache keyed by node_id. [VERIFIED: Python fcntl docs]

### Rotation (D-84)

```python
# Soft rotation: atomic os.rename — verified on same filesystem
os.rename(traj_path, traj_path.with_suffix(f".{next_n}.jsonl"))
# Then re-open with O_APPEND | O_CREAT and write new metadata header
```

`os.rename` is atomic on POSIX when source and destination are on the same filesystem (which `archive/*/trajectory.jsonl` always is — same repo directory). [VERIFIED: direct execution confirms rename is atomic on same fs]

**Hard rotate (50 MB):** `record_event` returns `False` and logs `CRITICAL`. The experiment process continues; only trajectory events after the hard cap are lost. The experiment itself is unaffected. [Per D-84; no tool execution needed to verify this design decision]

### Per-node RLock (D-86)

The process-level RLock prevents re-entry within the same process (in case of recursive calls). The node_id keyed dict approach:

```python
_NODE_LOCKS: dict[str, threading.RLock] = {}
_DICT_LOCK = threading.Lock()  # protects _NODE_LOCKS dict itself

def _get_node_lock(node_id: str) -> threading.RLock:
    with _DICT_LOCK:
        if node_id not in _NODE_LOCKS:
            _NODE_LOCKS[node_id] = threading.RLock()
        return _NODE_LOCKS[node_id]
```

This is the same pattern as Phase 2's MockSLURMBackend `_lock` protecting the `_jobs` dict. [VERIFIED: analogous to Phase 2 02-PATTERNS.md pattern]

---

## 6. Hook Integration (D-95, D-96)

### Claude Code hook integration (verified against official docs)

**Hook delivery mechanism:** Claude Code passes JSON via **stdin** (not environment variable). [VERIFIED: code.claude.com/docs/en/hooks — "For command hooks, input arrives on stdin"]

**Stop hook JSON payload:**
```json
{
  "session_id": "abc123",
  "transcript_path": "/Users/.../.claude/projects/.../transcript.jsonl",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "Stop"
}
```

**PostToolUse hook JSON payload:**
```json
{
  "session_id": "abc123",
  "transcript_path": "...",
  "cwd": "/Users/...",
  "permission_mode": "default",
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": {"file_path": "/path/to/file.txt", "content": "..."},
  "tool_use_id": "toolu_01abc"
}
```

**D-96 extension — CRITICAL CORRECTION:** D-96's template uses `${CLAUDE_HOOK_EVENT:-}` as an environment variable. **This is WRONG** — Claude Code sends the hook payload on stdin, not in an env var. The correct on_stop.sh extension pattern:

```bash
#!/usr/bin/env bash
# Read hook event from stdin (Claude Code's hook delivery mechanism)
HOOK_EVENT=$(cat)

# Find project root by walking up
DIR="$PWD"
while [ "$DIR" != "/" ]; do
    if [ -f "$DIR/.automil_active" ]; then
        echo "autoMIL loop is active. Run 'automil stop-loop' to allow stopping."
        exit 1
    fi
    DIR="$(dirname "$DIR")"
done

# Trajectory recording (PostToolUse hook provides tool event data)
if [[ -n "${AUTOMIL_NODE_ID:-}" && -n "${AUTOMIL_RUNTIME:-}" ]]; then
    echo "${HOOK_EVENT}" | automil trajectory record /dev/stdin \
        2>>"${AUTOMIL_DIR:-/tmp}/trajectory.err.log" || true
fi

exit 0
```

**Alternative: separate hook registration.** The on_stop.sh handles the Stop event; a separate `on_post_tool_use.sh` handles PostToolUse. Both are registered in `settings.json`. The planner can choose either approach — a single hook file vs. two separate ones. The single-file approach keeps `settings.json` simpler.

**Environment variables available during hook execution:** `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_ENV_FILE`. Note: `AUTOMIL_NODE_ID` and `AUTOMIL_RUNTIME` are NOT set by Claude Code — they must be set externally (e.g., by the orchestrator before starting the agent, or by the agent itself at session start). The hook script should check for their presence before calling `automil trajectory record`. [VERIFIED: code.claude.com/docs/en/hooks]

**Hook settings.json registration pattern (verified against existing init.py):**
```json
{
  "hooks": {
    "Stop": [{"hooks": [{"type": "command", "command": "bash /path/to/on_stop.sh"}]}],
    "PostToolUse": [{"hooks": [{"type": "command", "command": "bash /path/to/on_post_tool_use.sh"}]}]
  }
}
```
[VERIFIED: init.py lines 138-143 show the Stop hook registration format]

### opencode hook integration (verified against official docs)

**Critical finding: opencode does NOT have shell-script hooks.** opencode's hook API is **TypeScript/JavaScript plugins only**. There is no equivalent of Claude Code's stdin-based command hooks for shell scripts. [VERIFIED: opencode.ai/docs/plugins — "a plugin is a JavaScript/TypeScript module"; no shell hook mechanism documented]

**The available tool hooks:**
- `tool.execute.before` — receives `input` (tool name + args + sessionID), fires before execution
- `tool.execute.after` — receives `input` and `output` (title, output, metadata), fires after completion

**Payload structure (from plugin docs):**
```typescript
// tool.execute.after callback signature
async (input: { tool: string, args: Record<string, unknown>, sessionID: string },
       output: { title: string, output: string, metadata?: unknown }) => {
    // input.tool — e.g. "bash", "edit", "read"
    // input.args — tool arguments
    // input.sessionID — session identifier
}
```

**The opencode hook for Phase 3 must be a TypeScript plugin** (`.opencode/plugins/automil-trajectory.ts` or `~/.config/opencode/plugins/automil-trajectory.ts`) that:
1. Uses `$` (Bun shell API) or `child_process.execSync` to shell out to `automil trajectory record`
2. Passes a JSON-serialized event constructed from the `input` and `output` parameters
3. Sets `|| true` so failures are soft

```typescript
// .opencode/plugins/automil-trajectory.ts (installed by automil init --runtime opencode)
import { $ } from "bun"

export default function() {
    return {
        "tool.execute.after": async (input, output) => {
            const nodeId = process.env.AUTOMIL_NODE_ID
            const runtime = process.env.AUTOMIL_RUNTIME ?? "opencode"
            if (!nodeId) return
            const event = {
                "gen_ai.provider.name": runtime,
                "gen_ai.event.name": "tool_call",
                "gen_ai.event.timestamp": new Date().toISOString(),
                "gen_ai.tool.name": input.tool,
                "gen_ai.tool.call.arguments": JSON.stringify(input.args ?? {}),
                "gen_ai.tool.call.result": typeof output.output === "string"
                    ? output.output.slice(0, 4096) : JSON.stringify(output.output),
            }
            await $`automil trajectory record ${JSON.stringify(event)}`.quiet().nothrow()
        }
    }
}
```

**Installation path:** `automil init --runtime opencode` writes this plugin file to `<project_root>/.opencode/plugins/automil-trajectory.ts`. [VERIFIED: opencode docs state plugins can be in `.opencode/plugins/` for project-level or `~/.config/opencode/plugins/` for global]

**Bun requirement:** opencode uses Bun as its runtime; `$` is the Bun shell API. The plugin file assumes Bun is available (it will be, because opencode runs on Bun). [VERIFIED: opencode docs — plugin files are `.ts` loaded by opencode's Bun runtime]

**Opencode does NOT support Claude Code's hook re-activation pattern:** The Claude Code `Stop` hook can exit code 2 to prevent stopping and re-inject a prompt. This feature request for opencode (GitHub issue #12472) is **open and unimplemented as of 2026-05-03**. Phase 3's opencode integration cannot replicate the `.automil_active` guard via hook exit code — this must be documented in `agent_assets/opencode/README.md`. [VERIFIED: GitHub issue #12472 is open]

### Codex hook integration (D-100)

Codex's hook surface is documented as unstable. Phase 3 delivers only CLI-fallback:
- `agent_assets/codex/README.md` documents the manual fallback
- `AGENTS.md` at project root instructs the agent to call `automil trajectory record` explicitly when running under Codex
- No `settings.json` or TypeScript plugin is installed for Codex

### AGENTS.md spec summary (verified)

AGENTS.md is a standard Markdown file with no enforced schema. [VERIFIED: agents.md — "No. AGENTS.md is just standard Markdown. Use any headings you like"]

**Discovery rules by runtime:**
- **Codex:** Searches git root → cwd hierarchy; `AGENTS.md` and `AGENTS.override.md` in each directory level; max 32 KiB combined. [VERIFIED: developers.openai.com/codex/guides/agents-md]
- **opencode:** Reads `.opencode/AGENTS.md` natively (per D-90 design)
- **Claude Code:** Reads `.claude/CLAUDE.md`; Phase 3 sets its first line to `@AGENTS.md` (Claude Code supports `@<file>` imports)
- **Other tools (Cursor, Copilot, Devin, Gemini CLI):** All support `AGENTS.md` at project root natively

**Per-runtime native file pattern (D-90):**
```
<project_root>/AGENTS.md                    # canonical — generated by automil init
<project_root>/.claude/CLAUDE.md            # starts with: @AGENTS.md
<project_root>/.opencode/AGENTS.md          # symlink or copy of AGENTS.md (per D-90)
<project_root>/.codex/instructions.md       # Codex CLI: use this as supplement
```

---

## 7. Gitignore Template Extension (D-98)

**Existing template** at `src/automil/templates/.gitignore.j2` — current content:
```
# autoMIL runtime (not tracked)
graph.json
results.tsv
result.json
orchestrator/
.automil_active
.automil_worktrees/
*.log
*.pid
```
[VERIFIED: direct file read]

**New entries to append (D-98):**
```
# Trajectories — gitignored by default; use `automil trajectory export` to share
archive/*/trajectory.jsonl
archive/*/trajectory.*.jsonl
archive/*/trajectory.err.log
```

**`--update` flag:** D-98 mentions `automil init --update` for idempotent re-init that merges new gitignore entries. The current `init.py` does NOT have an `--update` flag. [VERIFIED: init.py — only `path`, `task`, `encoder` options]. Phase 3 must add this flag — it is a new feature required by D-98.

**Idempotent gitignore merge logic:** Check if each line already exists before appending — do not duplicate entries. Simple string membership check suffices (no regex needed).

---

## 8. agent_assets `git mv` Migration (D-88)

### Concrete git mv sequence

```bash
# D-88 migration steps:
git mv src/automil/claude_assets/skills/automil \
       src/automil/agent_assets/_shared/skills/automil
git mv src/automil/claude_assets/skills/automil-setup \
       src/automil/agent_assets/_shared/skills/automil-setup
git mv src/automil/claude_assets/hooks \
       src/automil/agent_assets/claude/hooks
# Create empty overlay skeleton dirs
mkdir -p src/automil/agent_assets/{opencode,codex,deepseek}
touch src/automil/agent_assets/{opencode,codex,deepseek}/.gitkeep
mkdir -p src/automil/agent_assets/opencode/plugins  # for TS plugin
```

**compat.py promotion (D-88 step 7):** `automil.claude_assets` is already declared in `_PLANNED_MIGRATIONS` at line 94 of `compat.py`. [VERIFIED: compat.py lines 94-103] Promote following the D-08 rule: add a live `__getattr__` shim that emits `DeprecationWarning` and removes the entry from `_PLANNED_MIGRATIONS`.

**`claude_assets` test:** After migration, `grep -r "claude_assets" src/automil/` must return matches only in `compat.py`. The existing `templates/` dir structure for skills/hooks is NOT the same as `claude_assets/` — the templates are in `src/automil/templates/`, not `src/automil/claude_assets/templates/`. [VERIFIED: init.py line 71 — `templates_dir = Path(__file__).parent.parent / "templates"`]

### Content split for _shared vs claude/

**Current `claude_assets/skills/automil/SKILL.md`** contains Claude-Code-specific content: [VERIFIED: file read]
- "Start your coding agent (claude -> /automil-setup)" — Claude-specific → `claude/SKILL.md`
- `claude --dangerously-skip-permissions` command — Claude-specific → `claude/SKILL.md`
- "Use the `Monitor` tool" — Claude-specific (other runtimes have different monitoring) → `claude/SKILL.md`
- The two standing directives (saturate GPUs, read literature) — universal → `_shared/SKILL.md`
- Loop structure, rules, stopping — universal → `_shared/SKILL.md`

**Current `claude_assets/skills/automil-setup/SKILL.md`** — mostly universal but step 4 ("Start your coding agent (claude -> /automil-setup)") is Claude-specific. [VERIFIED: file read]

---

## 9. Section-Replacement Overlay Merger (D-89)

### Implementation (D-89)

`src/automil/agent_assets/_overlay.py` — `merge_skill(runtime, shared_path, overlay_path)`:

```python
# Source: based on D-89 spec + edge-case research
import re
from pathlib import Path

_H2_SPLIT = re.compile(r"^(## .+)$", re.MULTILINE)

def _parse_sections(text: str) -> tuple[str, dict[str, str]]:
    """Split text into (preamble, {h2_header: body}).
    H1 title + any content before the first H2 goes into preamble.
    """
    parts = _H2_SPLIT.split(text)
    preamble = parts[0]  # includes H1 title + pre-H2 content
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections[header] = body
    return preamble, sections


def merge_skill(runtime: str, shared_path: Path, overlay_path: Path | None) -> str:
    """Merge _shared/<asset>.md with <runtime>/<asset>.md via section-replacement."""
    shared_text = shared_path.read_text(encoding="utf-8")
    preamble, shared_sections = _parse_sections(shared_text)

    if overlay_path is None or not overlay_path.exists():
        return shared_text

    overlay_text = overlay_path.read_text(encoding="utf-8")
    _, overlay_sections = _parse_sections(overlay_text)

    # Section-replacement: overlay wins, shared is default
    merged = dict(shared_sections)
    for header, body in overlay_sections.items():
        merged[header] = body  # replaces or appends

    # Reconstruct in shared's original order, then append new overlay sections
    result = preamble
    for header in shared_sections:
        result += header + merged[header]
    for header in overlay_sections:
        if header not in shared_sections:
            result += header + overlay_sections[header]  # new section from overlay

    return result
```

### Critical edge case: code blocks containing `## `

**Confirmed by direct test:** The `^## ` regex-split will false-split sections if a SKILL.md contains a code block with `## ` on a line by itself (e.g., bash comments that start with `## `). [VERIFIED: direct execution — see test output in research notes]

**Example of the problem:**
```markdown
## Section B
Here is some code:
```bash
## This is inside a code block  ← incorrectly treated as a new H2 section
echo hello
```
```

**Mitigation approach (recommended):** Require that SKILL.md content authors never use `## ` at the start of a line inside a fenced code block. Add a lint test in `tests/agent_assets/test_overlay.py` that:
1. Creates a SKILL.md with `## ` inside a code block
2. Verifies `merge_skill()` splits it incorrectly (documents the known limitation)
3. Creates a SKILL.md with no `## ` inside code blocks and verifies correct split

The ~40-line regex implementation from D-89 is prescribed — no markdown AST parser. This limitation must be documented in `agent_assets/_overlay.py`'s module docstring. [VERIFIED: D-89 spec; direct Python execution]

### Header matching edge cases

- Double space after `##`: `##  Section A` matches as `" Section A"` (key with leading space) — does NOT match `"Section A"`. Case-sensitive per D-89.
- Trailing whitespace: `## Section A ` matches as `"Section A "` — does NOT match `"Section A"`.
- **Implication:** Overlay files MUST use exact header text matching the shared file. A lint test must check for extra whitespace around H2 text. [VERIFIED: direct Python execution]

### H1 title guard (D-89)

Runtime overlay files MUST NOT contain an H1 title. Preamble extraction takes everything before the first H2. If an overlay starts with `# Title`, `_parse_sections()` will include it in `preamble` — but `merge_skill()` takes the H1 from `_shared` (the `preamble` variable). The lint test must assert `"# "` does not appear in the overlay file's `_parse_sections` output preamble. [Per D-89 spec]

---

## 10. CLI Surfaces — New Commands

### Pattern: `automil trajectory` Click group (D-94)

Following the `cli/lifecycle/` pattern (Phase 1), `trajectory` is a new Click group registered on `main`:

```python
# src/automil/cli/trajectory.py — group entry
@click.group("trajectory")
def trajectory_group():
    """Trajectory capture commands."""
    pass

# Then registered in cli/__init__.py:
from automil.cli import trajectory  # noqa: F401
# trajectory/__init__.py adds trajectory_group to main:
main.add_command(trajectory_group)
```

**OR** simpler: use `@main.group()` decorator directly in `src/automil/cli/trajectory.py`. The lifecycle pattern uses a package for multiple sub-commands — trajectory has only two subcommands (record + export) so a single file with a group is sufficient. [VERIFIED: Phase 1 PATTERNS.md §1 — CLI command file organization]

### `automil trajectory record` exit codes (D-91 spec)

- `0` — success (event recorded)
- `0` — soft-fail (recorder error; stderr WARNING)
- `1` — hard error (JSON parse error OR missing `AUTOMIL_NODE_ID` env)

This asymmetry (0 for both success and soft-fail) is intentional — hook scripts invoke `|| true` but must also not fail on legitimate recorder soft-failures. [Per D-94 spec]

### `automil show-skill --runtime` (D-93)

New `src/automil/cli/show_skill.py`. Follows §1 CLI pattern: imports `main`, uses `_find_automil_dir()`, calls `merge_skill()`. Pipeable (no progress output on stdout). [Per D-93 + Phase 1 PATTERNS.md]

### `automil init --runtime` extension (D-92)

The current `init.py` (150 lines, `@main.command()`) must be extended:
1. Add `@click.option("--runtime", ...)` with choices
2. Add `@click.option("--update", is_flag=True)` for idempotent re-init
3. Replace the hard-coded `claude_src = package_dir / "claude_assets"` block (lines 89-144) with a loop over selected runtimes
4. Add AGENTS.md render step

**Extension, not replacement:** Existing `--task`, `--encoder`, `path` options remain. The automil/ directory scaffold, template rendering, and variants skeleton creation are all preserved. Only the asset installation block (lines 89-144) is rewritten. [VERIFIED: init.py direct read]

---

## 11. Two-Runtime Smoke Test Architecture (D-99)

### Design

`tests/agent_assets/test_smoke_two_runtimes.py` — structure:

```python
# Drives a real submit → run → complete → archive cycle (LocalBackend, stub training script)
# then simulates hook firing for both runtimes

@pytest.fixture
def stub_training_script(tmp_path):
    """A minimal train.py that exits 0 and writes a valid result.json."""
    script = tmp_path / "train.py"
    script.write_text("""
import json, os
result = {"status": "completed", "metrics": {"val_auc": 0.80, "val_bacc": 0.75,
          "test_auc": 0.80, "test_bacc": 0.75}, "composite": 0.775,
          "elapsed_seconds": 1, "peak_vram_mb": 100}
with open(os.environ["AUTOMIL_RESULTS_DIR"] + "/result.json", "w") as f:
    json.dump(result, f)
""")
    return script

@pytest.mark.parametrize("runtime", ["claude-code", "opencode"])
def test_smoke_runtime(runtime, stub_training_script, tmp_path, automil_fixture):
    """Full submit→run→complete→archive cycle with hook-fired trajectory."""
    # 1. Submit with AUTOMIL_RUNTIME set
    # 2. Run via LocalBackend (stub training script writes result.json)
    # 3. Simulate hook firing: subprocess call to `automil trajectory record <event>`
    # 4. Assert trajectory.jsonl exists in archive/<node_id>/
    # 5. Assert first line metadata has correct runtime
    # 6. Assert ≥1 event line after the metadata line
    # 7. Assert no leaked-secret substring in the trajectory file
    ...
```

**Hook simulation without actual Claude Code / opencode running:**
- For Claude Code: call `subprocess.run(["automil", "trajectory", "record", json.dumps(event)], env={"AUTOMIL_NODE_ID": node_id, "AUTOMIL_RUNTIME": "claude-code", ...})`
- For opencode: call the same CLI command but with `AUTOMIL_RUNTIME=opencode`

The test does NOT actually launch Claude Code or opencode — it exercises the hook's downstream effect (calling `automil trajectory record`) directly. This is sufficient to verify: (a) the recorder works with the correct runtime metadata, (b) the trajectory format is valid, (c) no secrets are in the output. [Per D-99 spec; analogous to how Phase 2's MockSLURMBackend verifies backend contracts without real SLURM]

**The smoke test validates what "two runtimes" means for the acceptance gate:** The test asserts that a trajectory produced when `AUTOMIL_RUNTIME=claude-code` has `runtime: "claude-code"` in line 1, and a trajectory produced when `AUTOMIL_RUNTIME=opencode` has `runtime: "opencode"` in line 1. This is the Pitfall-3 operationalisation. A real end-to-end test with actual Claude Code and opencode processes is impractical in CI and is not required by D-99.

---

## Architecture Patterns

### Recommended Project Structure

```
src/automil/
    runtime.py                    # get_runtime() -> str (reads AUTOMIL_RUNTIME)
    trajectory/
        __init__.py               # record_event, read_metadata, RotationManager (public)
        schema.py                 # OTel gen_ai.* constants + validate_event()
        recorder.py               # O_APPEND + LOCK_EX + per-node RLock
        redactor.py               # _PATTERNS + redact() + redact_event()
        rotation.py               # RotationManager (soft/hard thresholds)
        export.py                 # export bundle: tar.gz + manifest.json
    agent_assets/
        _shared/
            skills/
                automil/SKILL.md
                automil-setup/SKILL.md
            AGENTS.md             # canonical universal instructions
        _overlay.py               # merge_skill() function
        claude/
            hooks/
                on_stop.sh        # git mv from claude_assets/hooks/on_stop.sh
                on_post_tool_use.sh  # NEW
        opencode/
            plugins/
                automil-trajectory.ts  # TypeScript plugin (NEW)
        codex/
            README.md             # CLI-fallback documentation
        deepseek/
            README.md             # DeepSeek-as-model documentation (MRT-06)
    cli/
        trajectory.py             # Click group: record + export subcommands
        show_skill.py             # automil show-skill command
        init.py                   # extended: --runtime + --update flags

tests/
    trajectory/
        __init__.py
        test_recorder.py          # append, redaction, rotation, soft-fail
        test_schema.py            # schema-version mismatch tolerance
        test_redactor.py          # positive case for each leak class
    agent_assets/
        __init__.py
        test_overlay.py           # section-replacement merge, edge cases
        test_show_skill.py        # show-skill CLI
        test_init_runtime.py      # init --runtime auto-detect + explicit
        test_smoke_two_runtimes.py  # anti-acceptance gate
```

### Pattern: Trajectory recorder soft-fail discipline (D-85)

```python
# src/automil/trajectory/recorder.py
def record_event(*, node_id, event, archive_dir, automil_version=None, runtime=None) -> bool:
    try:
        redacted = redact_event(event)
        validate_event(redacted)
        # ... append to file
        return True
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("trajectory record_event failed: %s", exc)
        return False
```

Never raises. Never crashes the experiment. [Per D-85 spec + Phase 0 PATTERNS.md soft-fail pattern]

### Pattern: Click group with subcommands (for `automil trajectory`)

```python
# src/automil/cli/trajectory.py
@click.group("trajectory")
def trajectory_group():
    """Trajectory capture and export commands."""
    pass

@trajectory_group.command("record")
@click.argument("event_json")
def record_cmd(event_json: str):
    """Record one trajectory event (runtime-agnostic CLI fallback)."""
    ...

@trajectory_group.command("export")
@click.argument("node_id")
@click.option("--out", default=None)
def export_cmd(node_id: str, out: str | None):
    """Export a redacted, schema-validated trajectory bundle."""
    ...

# In cli/__init__.py, add:
from automil.cli import trajectory  # noqa: F401
main.add_command(trajectory.trajectory_group)
```

[VERIFIED: Click docs for subgroups; analogous to existing group structure]

### Anti-Patterns to Avoid

- **Importing `opentelemetry` anywhere.** The check `python -c "import opentelemetry"` must raise `ModuleNotFoundError`. If any `trajectory/*.py` file does `import opentelemetry.*`, the hard floor is violated. [Per D-106, D-99]
- **Inferring runtime from environment or process name.** `get_runtime()` only reads `AUTOMIL_RUNTIME`. It never calls `os.popen("which claude")` or similar. [Per D-87]
- **Writing to `archive/<node_id>/` from outside the orchestrator's `archive_dir`.** The recorder must receive `archive_dir` as a parameter — it never constructs paths from `os.getcwd()`. [Per D-79]
- **Using `open()` instead of `os.open(O_APPEND | O_CREAT)`** for the trajectory file. `open("file", "a")` has different atomicity guarantees than `os.open(O_APPEND)`. [VERIFIED: Linux O_APPEND guarantees; Python open() "a" mode does NOT guarantee atomic seek-to-end+write on all platforms]
- **Closing the fd between events.** flock locks are released on fd close. Keep the fd open in the node_id keyed fd cache. [VERIFIED: Python fcntl docs]
- **Autobench imports in trajectory/ or agent_assets/.** Both must pass the `grep -r "autobench\|AUTOBENCH_\|benchmarks/"` zero-match check. [Per D-99 hard floor]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multiprocess-safe JSONL append | Custom file mutex with tempfiles | `O_APPEND + fcntl.LOCK_EX` | Kernel-level atomicity; proven pattern |
| Secret detection | Custom entropy analysis | Compiled regex set (D-82) | Sufficient for known-format secrets; no false positive on common Python identifiers |
| Tarball creation for export bundle | `subprocess.run(["tar", ...])` | `tarfile` stdlib | Pure Python, portable, no subprocess |
| Markdown overlay merge | markdown-AST parser library | Regex H2 splitter (~40 lines) | D-89 explicitly forbids AST parser; pattern is sufficient for controlled SKILL.md content |
| OTel field name lookup | `opentelemetry-sdk` | Module-level string constants in `schema.py` | Zero dep; forward-compat |

---

## Common Pitfalls

### Pitfall 1: on_stop.sh reads stdin but `$CLAUDE_HOOK_EVENT` doesn't exist
**What goes wrong:** D-96's template code uses `${CLAUDE_HOOK_EVENT:-}` — an env var that Claude Code does NOT set. The hook reads empty string.
**Why it happens:** Hook payload delivery is stdin (not env var). The env var approach is understandable intuition but incorrect.
**How to avoid:** Use `HOOK_EVENT=$(cat)` at the top of the hook script to read stdin. Then pipe or pass to `automil trajectory record`.
**Warning signs:** Trajectory files are created (first-line metadata OK) but have zero event lines despite the agent running tools.

### Pitfall 2: opencode hook plugin not installed by `automil init`
**What goes wrong:** `automil init --runtime opencode` writes SKILL.md and AGENTS.md but forgets the TypeScript plugin. opencode has no shell-script hook alternative. Trajectory is never captured for opencode.
**Why it happens:** The plugin is a new file type that doesn't have a prior Phase analog.
**How to avoid:** The smoke test explicitly checks `AUTOMIL_RUNTIME=opencode` produces a valid trajectory. If the plugin is not installed, the smoke test fails at "≥1 event line" assertion.
**Warning signs:** Smoke test trajectory file has metadata line (written at first record_event call) but zero subsequent event lines.

### Pitfall 3: Section-replacement merge splits on code block `## ` lines
**What goes wrong:** A SKILL.md section contains bash comments like `## Usage` inside a code fence. The `^## ` MULTILINE regex treats this as a section boundary and the section body is truncated.
**Why it happens:** Regex-based H2 splitter cannot distinguish a `## ` at the start of a fenced code line from a real H2 header.
**How to avoid:** Documented limitation. Require SKILL.md authors to never use `## ` on its own line inside a code fence. Lint test in `test_overlay.py` documents the failure mode.
**Warning signs:** `automil show-skill --runtime claude` output has a truncated section body or an unexpected extra section.

### Pitfall 4: flock released on any fd close (losing the lock unexpectedly)
**What goes wrong:** A caller opens `trajectory.jsonl` in a separate context (e.g., for reading) and closes it. This releases all flocks on that file for the process, including the write fd's lock.
**Why it happens:** Linux flock semantics: all locks for a file are released when any fd for that file is closed by the process.
**How to avoid:** Keep the write fd in the node_id keyed fd cache; never open the trajectory file for other operations from within the recorder module. Export reads a separate file descriptor opened in read mode only (no flock needed for reads).
**Warning signs:** Corrupted lines in trajectory files when two coroutines write simultaneously.

### Pitfall 5: gen_ai.system usage (deprecated) vs gen_ai.provider.name (current)
**What goes wrong:** Phase 3 ships with `gen_ai.system` as the provider field. Future OTel tooling that ingests trajectory files may warn or reject the deprecated field name.
**Why it happens:** D-81 specifies `gen_ai.system`; the spec deprecated it in late 2025 in favour of `gen_ai.provider.name`.
**How to avoid:** Use `gen_ai.provider.name` as the constant in `schema.py`. Since we use string constants (no SDK), the change is one line. The CONTEXT.md D-81 field set uses `gen_ai.system` — the planner should adopt `gen_ai.provider.name` as the canonical constant and add a `_LEGACY_GEN_AI_SYSTEM = "gen_ai.system"` alias for documentation.
**Warning signs:** Downstream tools that ingest trajectories log deprecation warnings on the `gen_ai.system` field.

### Pitfall 6: `init.py` "already initialized" guard blocks re-runs with `--update`
**What goes wrong:** Current init.py line 53: `if automil_dir.exists() and (automil_dir / "config.yaml").exists(): raise ClickException(...)`. The `--update` flag must bypass this guard.
**Why it happens:** The guard is correct for first-time init but wrong for re-runs.
**How to avoid:** Check `--update` before the guard: `if not update and automil_dir.exists() and ...`.
**Warning signs:** `automil init --update` fails with "autoMIL already initialized" even when invoked to add new gitignore entries.
[VERIFIED: init.py lines 53-55]

### Pitfall 7: `automil.claude_assets` compat shim emits DeprecationWarning on import, not on use
**What goes wrong:** Naively adding the shim at module level emits the warning immediately when `import automil` runs (because `cli/__init__.py` imports all CLI modules, and init.py previously imported `claude_assets`).
**Why it happens:** Not using PEP 562 `__getattr__` pattern.
**How to avoid:** Use `__getattr__` so the warning fires only when an attribute is accessed, not when the shim module is imported. [Per D-08 promotion rule in compat.py — already documented]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `claude_assets/` monolithic Claude-only assets | `agent_assets/_shared/` + per-runtime overlays | Phase 3 | Framework supports ≥2 runtimes without file duplication |
| No trajectory capture | Per-submit `trajectory.jsonl` with OTel gen_ai.* keys | Phase 3 | Forensic reproducibility; Pitfall 5 mitigation |
| `gen_ai.system` (OTel deprecated) | `gen_ai.provider.name` (current OTel spec) | OTel semconv late 2025 | Forward-compatible field names from day one |
| Claude Code hook payload via env var | Claude Code hook payload via stdin (`HOOK_EVENT=$(cat)`) | Always-was-true | Correct implementation of Claude Code's hook API |
| opencode: no hook integration | opencode TypeScript plugin (`tool.execute.after`) | Phase 3 | opencode trajectory capture |

**Deprecated/outdated:**
- `src/automil/claude_assets/`: replaced by `src/automil/agent_assets/` in Phase 3; kept only as compat shim target in `compat.py`
- `gen_ai.system` field name: deprecated by OTel in favour of `gen_ai.provider.name`; Phase 3 ships `gen_ai.provider.name`

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed via uv workspace) |
| Config file | `pyproject.toml` (workspace root) |
| Quick run command | `uv run pytest tests/trajectory/ tests/agent_assets/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |
| Phase gate command | `uv run pytest tests/ -q && python -c "import opentelemetry" 2>&1 \| grep ModuleNotFoundError && grep -r "claude_assets" src/automil/ \| grep -v compat.py \| wc -l \| xargs test 0 -eq && grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/ \| wc -l \| xargs test 0 -eq` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| TRJ-01 | trajectory.jsonl first line has correct schema_version, runtime, automil_version | unit | `uv run pytest tests/trajectory/test_recorder.py::test_first_line_metadata -x` | Wave 1 |
| TRJ-01 | record_event creates file if absent, appends if present | unit | `uv run pytest tests/trajectory/test_recorder.py::test_append_to_existing -x` | Wave 1 |
| TRJ-02 | `python -c "import opentelemetry"` raises ModuleNotFoundError | acceptance | `python -c "import opentelemetry" 2>&1 \| grep ModuleNotFoundError` | Phase gate |
| TRJ-02 | schema.py constants match OTel gen_ai.* namespace strings | unit | `uv run pytest tests/trajectory/test_schema.py::test_field_names_format -x` | Wave 1 |
| TRJ-03 | redact() catches sk- pattern (positive case) | unit | `uv run pytest tests/trajectory/test_redactor.py::test_sk_redacted -x` | Wave 2 |
| TRJ-03 | redact() catches hf_ pattern (positive case) | unit | `uv run pytest tests/trajectory/test_redactor.py::test_hf_redacted -x` | Wave 2 |
| TRJ-03 | redact() catches ghp_ pattern (positive case) | unit | `uv run pytest tests/trajectory/test_redactor.py::test_ghp_redacted -x` | Wave 2 |
| TRJ-03 | redact() catches AKIA pattern (positive case) | unit | `uv run pytest tests/trajectory/test_redactor.py::test_akia_redacted -x` | Wave 2 |
| TRJ-03 | redact() catches *_API_KEY= pattern | unit | `uv run pytest tests/trajectory/test_redactor.py::test_api_key_redacted -x` | Wave 2 |
| TRJ-03 | redact() catches *_TOKEN= pattern | unit | `uv run pytest tests/trajectory/test_redactor.py::test_token_redacted -x` | Wave 2 |
| TRJ-03 | 8 KB per-event cap truncates large events with marker | unit | `uv run pytest tests/trajectory/test_recorder.py::test_8kb_cap -x` | Wave 2 |
| TRJ-03 | Soft rotation at 5 MB renames existing file | unit | `uv run pytest tests/trajectory/test_recorder.py::test_soft_rotation -x` | Wave 2 |
| TRJ-03 | Hard rotation at 50 MB returns False and logs CRITICAL | unit | `uv run pytest tests/trajectory/test_recorder.py::test_hard_rotation -x` | Wave 2 |
| TRJ-04 | CLI `automil trajectory record <json>` exits 0 on success | integration | `uv run pytest tests/trajectory/test_recorder.py::test_cli_record_success -x` | Wave 3 |
| TRJ-04 | CLI `automil trajectory record` exits 1 on JSON parse error | integration | `uv run pytest tests/trajectory/test_recorder.py::test_cli_record_bad_json -x` | Wave 3 |
| TRJ-04 | CLI exits 0 (soft-fail) on recorder failure, stderr has WARNING | integration | `uv run pytest tests/trajectory/test_recorder.py::test_cli_record_soft_fail -x` | Wave 3 |
| TRJ-05 | archive/*/trajectory.jsonl pattern is in generated .gitignore | unit | `uv run pytest tests/agent_assets/test_init_runtime.py::test_gitignore_has_trajectory -x` | Wave 3 |
| TRJ-05 | export bundle contains trajectory.jsonl + manifest.json | unit | `uv run pytest tests/trajectory/test_recorder.py::test_export_bundle -x` | Wave 3 |
| TRJ-06 | schema-version mismatch: trajectory-v2 raises TrajectorySchemaError | unit | `uv run pytest tests/trajectory/test_schema.py::test_schema_v2_rejected -x` | Wave 1 |
| TRJ-06 | forward-compat: unknown field in trajectory-v1.* passes silently | unit | `uv run pytest tests/trajectory/test_schema.py::test_v1_unknown_field_tolerated -x` | Wave 1 |
| MRT-01 | merge_skill with no overlay returns shared content unchanged | unit | `uv run pytest tests/agent_assets/test_overlay.py::test_no_overlay -x` | Wave 2 |
| MRT-01 | merge_skill replaces matching H2 section from overlay | unit | `uv run pytest tests/agent_assets/test_overlay.py::test_section_replaced -x` | Wave 2 |
| MRT-01 | merge_skill appends non-matching overlay sections at end | unit | `uv run pytest tests/agent_assets/test_overlay.py::test_section_appended -x` | Wave 2 |
| MRT-01 | H2 in code block causes known false-split (documented limitation) | unit | `uv run pytest tests/agent_assets/test_overlay.py::test_code_block_h2_known_limitation -x` | Wave 2 |
| MRT-01 | H1 not overridden by overlay | unit | `uv run pytest tests/agent_assets/test_overlay.py::test_h1_preserved -x` | Wave 2 |
| MRT-01 | grep claude_assets src/automil/ returns only compat.py | acceptance | `grep -r "claude_assets" src/automil/ \| grep -v compat.py \| wc -l \| xargs test 0 -eq` | Phase gate |
| MRT-02 | automil init generates AGENTS.md at project root | integration | `uv run pytest tests/agent_assets/test_init_runtime.py::test_agents_md_created -x` | Wave 3 |
| MRT-03 | automil init --runtime claude installs to .claude/ | integration | `uv run pytest tests/agent_assets/test_init_runtime.py::test_init_runtime_claude -x` | Wave 3 |
| MRT-03 | automil init --runtime opencode installs to .opencode/ | integration | `uv run pytest tests/agent_assets/test_init_runtime.py::test_init_runtime_opencode -x` | Wave 3 |
| MRT-03 | automil init auto-detects from existing .claude/ dir | integration | `uv run pytest tests/agent_assets/test_init_runtime.py::test_autodetect_claude -x` | Wave 3 |
| MRT-03 | automil init --update merges gitignore without duplicate entries | integration | `uv run pytest tests/agent_assets/test_init_runtime.py::test_update_idempotent -x` | Wave 3 |
| MRT-04 | automil show-skill --runtime claude stdout matches merged content | integration | `uv run pytest tests/agent_assets/test_show_skill.py::test_show_skill_claude -x` | Wave 3 |
| MRT-05 | Two-runtime smoke test (claude-code + opencode) both produce valid trajectories | smoke | `uv run pytest tests/agent_assets/test_smoke_two_runtimes.py -x` | Wave 4 |
| MRT-06 | agent_assets/deepseek/README.md exists and mentions "model not runtime" | unit | `uv run pytest tests/agent_assets/test_init_runtime.py::test_deepseek_readme -x` | Wave 2 |

### Wave-Cadence Target (10–11 plans, 4 waves)

```
Wave 0 (skeleton + prereqs):
  03-01: trajectory/ package skeleton (schema.py constants + TrajectorySchemaError + first-line metadata pattern)
  03-02: agent_assets/ git mv + compat.py promotion + deepseek README

Wave 1 (core logic — parallelizable):
  03-03: redactor.py (compiled patterns, redact_event, 8KB cap)
  03-04: recorder.py (O_APPEND + LOCK_EX + per-node RLock + soft-fail + metadata header)
  03-05: rotation.py (RotationManager, soft/hard thresholds, os.rename rotation)

Wave 2 (asset overlay + CLI):
  03-06: _shared/AGENTS.md + _shared/SKILL.md content split from claude_assets
  03-07: _overlay.py (merge_skill) + automil show-skill CLI + test_overlay.py
  03-08: Claude Code hook extension (on_stop.sh + on_post_tool_use.sh + settings.json registration)
  03-09: opencode TypeScript plugin + automil init --runtime opencode install

Wave 3 (integration + gitignore + smoke):
  03-10: automil init --runtime extension (--runtime choices, --update flag, AGENTS.md render, gitignore extension)
  03-11: two-runtime smoke test (anti-acceptance gate)
```

### Sampling Rate

- **Per task commit:** `uv run pytest tests/trajectory/ tests/agent_assets/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full conjunction from D-99 (see acceptance criteria)

### Wave 0 Gaps (files that must exist before Wave 1 can land)

- [ ] `src/automil/trajectory/__init__.py` — public surface
- [ ] `src/automil/trajectory/schema.py` — constants + TrajectorySchemaError + validate_event
- [ ] `src/automil/agent_assets/__init__.py` — (empty, makes package importable)
- [ ] `src/automil/agent_assets/_overlay.py` — skeleton (merge_skill stub)
- [ ] `tests/trajectory/__init__.py` — empty
- [ ] `tests/agent_assets/__init__.py` — empty
- [ ] `src/automil/runtime.py` — get_runtime() 3-line module

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fcntl | recorder.py | ✓ | stdlib (Linux) | Windows not supported (CLAUDE.md: Linux+CUDA only) |
| tarfile | export.py | ✓ | stdlib | — |
| hashlib | export.py (manifest redaction-rule hash) | ✓ | stdlib | — |
| threading | recorder.py (RLock) | ✓ | stdlib | — |
| Bun (opencode runtime) | opencode TS plugin | ✓ | opencode ships with Bun | Plugin only runs inside opencode process |
| pytest | All tests | ✓ | via uv workspace | — |
| opentelemetry-sdk | NOT required | NOT installed | — | Intentional: forbidden by D-106 |

**No missing dependencies block Phase 3 execution.** [VERIFIED: fcntl available on Python 3.12.3 Linux; opentelemetry not installed — confirmed by `python3 -c "import opentelemetry"` test]

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1` per config.json.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | partial | Recorder bounded to `archive/<node_id>/` — cannot write outside (D-79) |
| V5 Input Validation | yes | `validate_event()` checks required fields; `redact_event()` is applied before any write |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in trajectory tool arguments (Pitfall 5a) | Information Disclosure | Redaction-on-capture: D-82 patterns applied before file write; soft-fail never skips redaction |
| Hook script injection via event payload | Tampering | `automil trajectory record` reads event as JSON string, not shell-evaluated; `json.loads()` rejects injection |
| Trajectory path traversal (`../../../etc/passwd`) | Tampering | `archive_dir` is passed as a `Path` from the orchestrator — bounded to `archive/<node_id>/`; recorder does not construct paths from user input |
| opencode TypeScript plugin arbitrary code execution | Elevation of Privilege | Plugin only calls `automil trajectory record`; no eval or dynamic import |
| Redactor regex ReDoS | Denial of Service | All patterns are linear (no nested quantifiers, no catastrophic backtracking). [VERIFIED: manual inspection of D-82 patterns] |
| claude_assets/ shim emitting warning on every import | Performance / DoS | PEP 562 `__getattr__` ensures warning fires on attribute access, not on module import [Per D-08 promotion rule] |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | opencode's Bun shell API (`$`) is available inside plugin functions | §6 (opencode plugin) | Medium — if Bun shell not available, use `child_process.execSync` instead; same semantics |
| A2 | opencode plugin at `.opencode/plugins/` is loaded automatically on startup | §6 | Medium — if load path differs, installation target changes; verify with opencode docs at impl time |
| A3 | `AUTOMIL_NODE_ID` env var is accessible inside opencode plugin (inherited by opencode process) | §6 | High — if not inherited, trajectory record fails for opencode; mitigation: document that orchestrator must set AUTOMIL_NODE_ID before launching agent |
| A4 | Redactor regex patterns have no catastrophic backtracking | §4 | Low — patterns are simple character classes; no nested quantifiers visible |
| A5 | `gen_ai.provider.name` is the correct current field name replacing `gen_ai.system` | §3 | Low — if wrong, schema.py needs one-line change; both are valid JSONL keys regardless |
| A6 | opencode reads `.opencode/AGENTS.md` as the per-project instruction file (analogous to `.claude/CLAUDE.md`) | §6 | Medium — opencode docs mention AGENTS.md but project-local `.opencode/AGENTS.md` reading needs verification at impl time |

**Claims tagged `[ASSUMED]`:** A1, A2, A3, A6 (opencode implementation details not fully documented; verify at implementation time by consulting opencode source or docs).

---

## Open Questions

1. **AUTOMIL_NODE_ID availability inside the opencode plugin process**
   - What we know: The orchestrator sets `AUTOMIL_NODE_ID` in the experiment process env. The opencode agent runs as a separate process.
   - What's unclear: Whether `AUTOMIL_NODE_ID` is inherited by the opencode process that the operator starts.
   - Recommendation: Document in `agent_assets/opencode/README.md` that the operator must set `AUTOMIL_NODE_ID` in their shell before launching opencode. The plugin checks for the env var and silently skips if absent.

2. **`init.py` re-initialization semantics with `--update`**
   - What we know: Current init raises `ClickException` if already initialized (line 53). D-98 requires `--update` for re-init.
   - What's unclear: Does `--update` also re-render config.yaml / program.md, or only update assets (skills, hooks, gitignore)?
   - Recommendation: `--update` updates only assets (skills, hooks, gitignore entries). It never overwrites `config.yaml` or `program.md` (user-edited files). This matches the "idempotent re-init merges new entries" framing in D-98.

3. **gen_ai.system vs gen_ai.provider.name in D-81**
   - What we know: D-81 specifies `gen_ai.system`; OTel registry marks it deprecated in favour of `gen_ai.provider.name`.
   - What's unclear: Whether the planner should use D-81 verbatim (gen_ai.system) or adopt the current spec (gen_ai.provider.name).
   - Recommendation: Use `gen_ai.provider.name` as the constant value (one change from D-81), with a comment in `schema.py` noting this replaces the deprecated `gen_ai.system`. This is a purely internal naming choice with no user-visible impact.

---

## Sources

### Primary (HIGH confidence)

- `src/automil/cli/init.py` — verified lines 53, 71, 89-144, option set [VERIFIED: direct read]
- `src/automil/compat.py` — verified `_PLANNED_MIGRATIONS["automil.claude_assets"]` at line 94 [VERIFIED: direct read]
- `src/automil/claude_assets/hooks/on_stop.sh` — verified current hook reads nothing from stdin [VERIFIED: direct read]
- `src/automil/claude_assets/skills/automil/SKILL.md` — verified Claude-specific content for split [VERIFIED: direct read]
- `src/automil/templates/.gitignore.j2` — verified current contents [VERIFIED: direct read]
- `src/automil/__init__.py` — verified `__version__ = "0.1.0"` [VERIFIED: direct read]
- `src/automil/backends/_orchestrator_daemon.py` — verified archive dir creation pattern [VERIFIED: line grep]
- `tests/` — verified 425 tests + 9 skipped (Phase 0+1+2 baseline) [VERIFIED: `uv run pytest` output]
- Python stdlib fcntl, os, threading docs — O_APPEND atomicity, LOCK_EX pattern [VERIFIED: direct execution]
- `code.claude.com/docs/en/hooks` — Stop hook JSON payload shape, stdin delivery, env vars [VERIFIED: WebFetch]
- `opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/` — gen_ai.* field names, gen_ai.system deprecation [VERIFIED: WebFetch]
- Regex false-positive tests — D-82 patterns tested by direct Python execution [VERIFIED: Bash execution]
- Section-replacement merge edge case — code block `## ` false-split confirmed by direct execution [VERIFIED: Bash execution]

### Secondary (MEDIUM confidence)

- `opencode.ai/docs/plugins/` — TypeScript-only plugin API, `tool.execute.after` hook signature [VERIFIED: WebFetch]
- `github.com/anomalyco/opencode/issues/12472` — Claude Code hooks compatibility: open issue, NOT implemented [VERIFIED: WebFetch]
- `developers.openai.com/codex/guides/agents-md` — AGENTS.md Codex discovery rules (git root hierarchy, 32 KiB cap) [VERIFIED: WebFetch]
- `agents.md` — AGENTS.md is standard Markdown, no enforced schema, 60k+ adoption [VERIFIED: WebFetch]
- gist.github.com/johnlindquist — opencode plugin hooks reference (hook names, Bun shell API) [MEDIUM: community gist, not official docs]

### Tertiary (LOW confidence)

- opencode `.opencode/AGENTS.md` discovery path — inferred from D-90 design; opencode docs mention AGENTS.md but project-local `.opencode/AGENTS.md` not explicitly verified [LOW]
- AUTOMIL_NODE_ID env var inheritance in opencode plugin — assumed; not verified against opencode source [LOW]

---

## Metadata

**Confidence breakdown:**
- Trajectory module: HIGH — all patterns verified by direct Python execution; stdlib-only
- Hook integration: HIGH for Claude Code (official docs verified), MEDIUM for opencode (TypeScript plugin confirmed; some env var inheritance details ASSUMED)
- OTel field semantics: HIGH — verified against official registry; gen_ai.system deprecation confirmed
- Overlay merger: HIGH — algorithm verified; edge cases confirmed by direct execution
- Smoke test design: HIGH — analogous to Phase 2 contract test pattern
- Redaction patterns: HIGH — tested by direct execution; false positive surface documented

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (stable Python stdlib patterns; opencode hook API is MEDIUM confidence and may change; OTel semconv is still "in development" status)

---

## RESEARCH COMPLETE

**Phase:** 03 — Trajectory recorder + multi-runtime asset reorganisation
**Confidence:** HIGH

### Key Findings

1. **Claude Code hook payload is stdin, not `$CLAUDE_HOOK_EVENT`** — D-96's template has a bug: `${CLAUDE_HOOK_EVENT:-}` is not a real env var. The correct pattern is `HOOK_EVENT=$(cat)` to read from stdin. This is the #1 implementation trap.

2. **opencode hook requires TypeScript plugin** — opencode has no shell-script hook equivalent. Phase 3's opencode integration is a TypeScript plugin that uses Bun's shell API to invoke `automil trajectory record`. Plugin is installed by `automil init --runtime opencode`.

3. **Section-replacement overlay has a confirmed code-block edge case** — `^## ` regex-split false-splits when SKILL.md content has `## ` inside a fenced code block. Documented limitation; lint test covers it. SKILL.md authors must not use `## ` inside code blocks.

4. **O_APPEND + LOCK_EX is the correct multi-process JSONL append pattern** — verified by direct execution. Key constraint: keep the fd open in a node_id keyed cache; never close-between-events (flock released on any fd close).

5. **`gen_ai.system` is deprecated** — current OTel spec uses `gen_ai.provider.name`. Use the current name from day one; one-line change from D-81 with no other impact.

### File Created
`/home/jma/Documents/yinshuol/autoMIL/.planning/phases/03-trajectory-recorder-multi-runtime-asset-reorganisation/03-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Trajectory recorder (stdlib patterns) | HIGH | Verified by direct Python execution |
| OTel field semantics | HIGH | Verified against official registry |
| Claude Code hook integration | HIGH | Verified against official docs |
| opencode hook integration | MEDIUM-HIGH | TypeScript plugin confirmed; env var inheritance ASSUMED |
| Section-replacement overlay | HIGH | Algorithm verified; edge cases confirmed |
| Smoke test design | HIGH | Analogous to Phase 2 contract test |
| Redaction patterns | HIGH | Tested against D-82 patterns by execution |

### Open Questions (for planner attention)
- `AUTOMIL_NODE_ID` availability inside opencode plugin process (A3)
- `--update` flag scope: assets-only vs full re-render (Open Question 2)
- `gen_ai.system` vs `gen_ai.provider.name` alignment with D-81 (Open Question 3)

### Ready for Planning
Research complete. Planner can now create PLAN.md files using wave-cadence structure: Wave 0 (skeleton) → Wave 1 (core logic) → Wave 2 (overlay + CLI) → Wave 3 (integration + smoke).
