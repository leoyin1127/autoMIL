# Phase 3: Trajectory recorder + multi-runtime asset reorganisation - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Engineering decisions locked per production best practice (Leo's directive 2026-05-02 — "decide engineering questions yourself; ask only user/feature questions"). Every decision below is a technical implementation choice; there are no open user/feature questions for Phase 3.

<domain>
## Phase Boundary

Land **per-submit trajectory capture** (bounded, redacted, schema-versioned JSONL) and **multi-runtime agent-asset reorganisation** so the framework runs end-to-end on ≥2 runtimes — defending Pitfall 3 ("multi-runtime untested-but-claimed") and Pitfall 5 ("trajectory leaks/bloats/fossilises") simultaneously. Phase 3 is the only Phase in the milestone that addresses the F2 reviewer's "this is a Claude paper" attack head-on.

After Phase 3:

1. **`src/automil/trajectory/`** — append-only JSONL recorder per `archive/<node_id>/trajectory.jsonl`. First line is metadata `{schema_version, runtime, runtime_version, tool_schema_version, automil_version, automil_runtime_env}`. Subsequent lines use **OpenTelemetry `gen_ai.*` semantic-convention field names** with **no `opentelemetry-sdk` runtime dependency** (we use the field-name strings directly, not the SDK). Redaction-on-capture covers `sk-…`, `hf_…`, `ghp_…`, AWS access keys, `*_API_KEY=…`, `*_TOKEN=…`. Per-event 8 KB cap. Per-file 5 MB soft / 50 MB hard rotation to `trajectory.<n>.jsonl` siblings.
2. **`src/automil/agent_assets/`** replaces `src/automil/claude_assets/`. `_shared/SKILL.md` is the canonical content. `_shared/AGENTS.md` is the universal instruction file. Per-runtime subdirectories (`claude/`, `opencode/`, `codex/`) contain ONLY diverging sections — section-replacement merge against `_shared/`. `deepseek/README.md` documents that DeepSeek is a *model* routed via opencode/Codex/etc., not a runtime. `git mv` preserves blame.
3. **`automil init --runtime <claude|codex|opencode|deepseek-via-X|all>`** with auto-detection from existing `.claude/`, `.codex/`, `.opencode/`. `AGENTS.md` is generated at the project root by `init`; per-runtime native files (`.claude/CLAUDE.md`, `.codex/CODEX.md`, `~/.config/opencode/AGENTS.md`) reference it.
4. **`automil show-skill --runtime <name>`** renders the merged per-runtime SKILL.md to stdout for inspection.
5. **`automil trajectory record <event-json>`** is the runtime-agnostic CLI fallback (covers runtimes without native hook support). **`automil trajectory export <node_id>`** produces a re-redacted, schema-validated bundle for sharing. Trajectories are gitignored by default.
6. **End-to-end smoke test** (`tests/agent_assets/test_smoke_two_runtimes.py`) drives a real submit→run→complete→archive cycle on ≥2 runtimes — Claude Code AND opencode — with each runtime's hook script firing `automil trajectory record` and producing a valid trajectory with correct runtime metadata. **The Phase is NOT done until this test is green.** This is the Pitfall-3 anti-acceptance gate.

**Hard floors:**

- Phase 0+1+2 baseline (425 tests + 9 skipped) stays green — no behavioural regressions in existing imports.
- `archive/<node_id>/trajectory.jsonl` produced by either runtime contains zero substring matches for `sk-` (followed by a token), `hf_`, `ghp_`, AWS access key prefix, or `_(API_)?KEY=` / `_TOKEN=` with non-redacted right-hand side. Verified by a positive-case test per leak class.
- `python -c "import opentelemetry"` raises `ModuleNotFoundError` after `pip install -e .` — we have NO runtime dep on the OTel SDK.
- `grep -r "claude_assets" src/automil/` returns matches only in `compat.py` (re-export shim).
- The smoke test in 03-11 produces a valid `result.json` AND a valid trajectory for **both** runtimes in a single CI run.
- `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/` returns zero matches — trajectory + agent_assets are framework-only.

**Wave-cadence target:** 10–11 plans across 4 waves. Granularity `fine`. Dependency shape: trajectory skeleton ‖ agent_assets migration → redaction + rotation + overlay-merge → AGENTS.md/init/show-skill/record-CLI ‖ Claude+opencode hooks → gitignore + submit integration → end-to-end smoke (anti-acceptance).

</domain>

<decisions>
## Implementation Decisions

> **Numbering:** D-78 onward continues from Phase 2's D-51..D-77. Each decision is a locked engineering choice; downstream agents (researcher, planner, executor) honour these verbatim.

### Trajectory module layout (TRJ-01..06)

- **D-78:** New package `src/automil/trajectory/` with five modules:
  ```
  src/automil/trajectory/
    __init__.py              # public surface: record_event, read_metadata, RotationManager
    schema.py                # OTel gen_ai.* field constants + validation predicate
    recorder.py              # append-only JSONL writer (O_APPEND + LOCK_EX)
    redactor.py              # compiled regex set + per-event 8 KB truncation
    rotation.py              # 5 MB soft / 50 MB hard rotation manager
    export.py                # `automil trajectory export` bundle producer
  ```
  Stdlib-only. No `opentelemetry-sdk`, no `pydantic` (autoMIL is stdlib-first per Phase 0 conventions). Module is **framework-internal** — no autobench imports, no consumer-specific paths.

- **D-79:** **Trajectory canonical path** is `archive/<node_id>/trajectory.jsonl`. The orchestrator already owns the archive directory (Phase 2 D-58); trajectory writes piggyback on that ownership. The recorder NEVER opens files outside the node's archive subdirectory — bounded by construction.

- **D-80:** **First-line metadata schema** is exactly:
  ```json
  {
    "schema_version": "trajectory-v1",
    "runtime": "claude-code",
    "runtime_version": "claude-opus-4-7@2026-04-30",
    "tool_schema_version": "claude-2026-04",
    "automil_version": "0.X.Y",
    "automil_runtime_env": {"AUTOMIL_RUNTIME": "claude-code", "AUTOMIL_GPU": "0"}
  }
  ```
  `schema_version` follows semver-style: `trajectory-v1.<minor>` for backwards-compatible additions, `trajectory-v2` for breaking changes. Phase 3 ships `trajectory-v1`. Readers MUST tolerate unknown fields in v1.* (forward-compat) and MUST refuse to interpret v2 (defends Pitfall 5c — fossilisation).

- **D-81:** **OTel `gen_ai.*` field set** (subset of [GenAI semantic-conventions v1.30](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — we use field-name strings only, no SDK):
  ```
  gen_ai.system                  # "claude-code" | "opencode" | "codex"
  gen_ai.request.model           # e.g. "claude-opus-4-7"
  gen_ai.event.name              # "prompt" | "tool_call" | "tool_result" | "response"
  gen_ai.event.timestamp         # ISO 8601, microsecond precision
  gen_ai.tool.name               # "Read" | "Edit" | "Bash" | ...
  gen_ai.tool.arguments          # JSON-encoded subset (after redaction + 8KB cap)
  gen_ai.tool.result             # JSON-encoded subset (after redaction + 8KB cap)
  gen_ai.usage.input_tokens      # int (when known; absent OK)
  gen_ai.usage.output_tokens     # int (when known; absent OK)
  ```
  `schema.py` defines these as module-level string constants and a `REQUIRED_FIELDS = {"gen_ai.system", "gen_ai.event.name", "gen_ai.event.timestamp"}` set. `validate_event(d: dict) -> None` raises `TrajectorySchemaError` if a required field is missing; unknown fields pass silently (forward-compat).

### Redaction-on-capture (TRJ-03)

- **D-82:** **Compiled regex set** at module-import time (one-time cost), applied to every string field recursively before append:
  ```python
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
  `redact(s: str) -> str` runs all patterns in order. `redact_event(d: dict) -> dict` walks the event recursively (dict, list, tuple, str leaves) and returns a new redacted dict — original is not mutated. **Redaction is mandatory** (no opt-out flag); Pitfall 5a is catastrophic if pushed to git.

- **D-83:** **Per-event size cap** is **8 KB** post-redaction. If `len(json.dumps(redacted_event).encode("utf-8")) > 8192`, the event's `gen_ai.tool.arguments` and `gen_ai.tool.result` fields are truncated to fit, with a marker `"…[truncated:<original_size>B]"` appended. If after-truncation the event is still > 8 KB (pathological metadata bloat), the event is replaced with `{"gen_ai.event.name": "truncated", "gen_ai.event.timestamp": ..., "_dropped_size": <bytes>}` and a WARNING is logged.

- **D-84:** **Rotation thresholds** are config-set with conservative defaults:
  ```yaml
  trajectory:
    soft_rotate_bytes: 5242880    # 5 MB — rotate to trajectory.<n>.jsonl
    hard_rotate_bytes: 52428800   # 50 MB — refuse new events; log critical
  ```
  Soft rotate: rename `trajectory.jsonl` → `trajectory.1.jsonl` (or next free integer), open new `trajectory.jsonl` with metadata header copied verbatim. Atomic via `os.rename`. Hard rotate: `record_event` returns `False` (soft-fail) and logs CRITICAL — never crashes the experiment.

### Recorder API + thread-safety (TRJ-01, TRJ-04)

- **D-85:** **Recorder public API** is one function:
  ```python
  def record_event(
      *,
      node_id: str,
      event: dict,
      archive_dir: Path,
      automil_version: str | None = None,
      runtime: str | None = None,
  ) -> bool:
      """Append one event to archive/<node_id>/trajectory.jsonl.

      Auto-creates the file with first-line metadata if absent.
      Returns False (and logs WARNING) on any I/O / redaction error
      — never raises. Thread-safe via per-node-id RLock + LOCK_EX.
      """
  ```
  **Soft-fail discipline:** disk full / permission denied / redactor crash → caught, logged at WARNING, returns `False`. The experiment process MUST NOT crash because of trajectory recorder failures. Pitfall 5b mitigation: an unknown bug in the recorder cannot kill an experiment.

- **D-86:** **Multi-process safety** via `O_APPEND` open mode + `fcntl.flock(fd, LOCK_EX)` around each line append. Single-line atomic appends at the kernel level. Per-process RLock prevents intra-process re-entry deadlock. `automil trajectory record <event-json>` (CLI fallback, D-91) uses the same lock primitive — Claude Code hook + a parallel manual `automil trajectory record` invocation cannot interleave broken lines.

- **D-87:** **Runtime declaration is explicit, NEVER inferred** (defends Pitfall 5c-edge: trajectory mis-tagged as Claude when it was actually Codex). The runtime contract:
  - `AUTOMIL_RUNTIME` environment variable declares the runtime: `"claude-code" | "opencode" | "codex" | "deepseek-via-opencode" | "deepseek-via-codex" | "unknown"`.
  - `src/automil/runtime.py` exposes `get_runtime() -> str` which reads `AUTOMIL_RUNTIME` (default `"unknown"`).
  - Each runtime's installed assets set `AUTOMIL_RUNTIME` in the experiment process env (via `JobSpec.env` passthrough — Phase 0's env whitelist already contains the prefix).
  - `automil/config.yaml: env.passthrough` is extended to include `AUTOMIL_RUNTIME` by default in `automil init`.

### Multi-runtime asset reorg (MRT-01..06)

- **D-88:** **Migration is `git mv`** (preserves blame). Concretely:
  1. `git mv src/automil/claude_assets/skills/automil src/automil/agent_assets/_shared/skills/automil`
  2. `git mv src/automil/claude_assets/skills/automil-setup src/automil/agent_assets/_shared/skills/automil-setup`
  3. `git mv src/automil/claude_assets/hooks src/automil/agent_assets/claude/hooks`
  4. Create empty `src/automil/agent_assets/{claude,opencode,codex,deepseek}/` overlay dirs.
  5. Create `src/automil/agent_assets/_shared/AGENTS.md` (canonical instruction file — extract from current `claude_assets/skills/automil/SKILL.md` what is universal).
  6. Update `src/automil/cli/init.py` to read from `agent_assets/` (D-92).
  7. Update `compat.py` `_PLANNED_MIGRATIONS["automil.claude_assets"]` (already declared at line 94 — promote to `_DEPRECATED_PATHS` with one-shot `__getattr__` shim emitting a `DeprecationWarning`).

- **D-89:** **Section-replacement merge** is the overlay algorithm:
  - Sections are delimited by markdown H2 headers (`^## `).
  - Render order: (1) read `_shared/<asset>.md`; (2) read `<runtime>/<asset>.md` if present; (3) for each H2 section in the runtime overlay, replace the matching section in `_shared` (matched by exact header text, case-sensitive); (4) sections in the runtime overlay with no `_shared` match are appended at the end; (5) sections in `_shared` with no override pass through.
  - The H1 `# Title` is taken from `_shared`; runtime files MUST NOT override it (lint-checked in tests).
  - Implementation lives at `src/automil/agent_assets/_overlay.py` (`merge_skill(runtime: str, shared_path: Path, overlay_path: Path | None) -> str`).

- **D-90:** **`AGENTS.md` lives at the project root** (per the [AGENTS.md spec](https://github.com/openai/agents.md) — Linux Foundation, OpenAI, opencode all support it). Per-runtime native files reference or extend it:
  - `<project_root>/AGENTS.md` — canonical (rendered from `agent_assets/_shared/AGENTS.md` + per-runtime overlay)
  - `<project_root>/.claude/CLAUDE.md` — runtime-specific; first line `@AGENTS.md` to import the universal content (Claude Code natively supports `@<file>` imports — verified in current `.claude/` setup).
  - `<project_root>/.opencode/AGENTS.md` — opencode reads this natively (no extra import needed).
  - `<project_root>/.codex/instructions.md` — Codex's documented file (CLI-fallback path; auto-detect surface only).
  - `automil init` writes whichever exist for detected/explicit runtimes.

- **D-91:** **Auto-detection** in `automil init` (no `--runtime` flag):
  - Probe `(.claude / .opencode / .codex)` directory existence in the **project root** at `automil init` time.
  - If exactly one is found → install only that runtime's overlay.
  - If multiple are found → install all matched.
  - If none → install Claude Code by default (current behaviour) AND print a banner: `"No runtime config detected — installing Claude Code overlay. Use --runtime to override or --runtime all for full multi-runtime support."`
  - `--runtime all` installs all four runtime overlays unconditionally.
  - `--runtime claude` (etc.) is the explicit single-runtime path; ignores auto-detection.
  - Detection is **lenient**: an empty `.claude/` directory is treated as "Claude Code is in use here." Don't try to be clever about contents.

### CLI surfaces (CLI new)

- **D-92:** **`automil init` rewrite** for runtime selection (Phase 1's init code is preserved; we extend, not replace):
  - Add `--runtime` Click option with choices `[claude, opencode, codex, deepseek-via-opencode, deepseek-via-codex, all]` (default: auto-detect).
  - Replace the hard-coded `claude_src = package_dir / "claude_assets"` (init.py:90) with a loop over selected runtimes; for each runtime, render skills via the overlay merger (D-89) and write to the runtime's native location.
  - Render the project-root `AGENTS.md` once per `init` invocation.
  - Update the "Next steps" footer to show only the selected runtime(s).

- **D-93:** **`automil show-skill --runtime <name> [--asset SKILL|AGENTS]`** lives at `src/automil/cli/show_skill.py`:
  - Reads the same overlay merger (D-89), prints rendered output to stdout.
  - `--asset` defaults to `SKILL`; `AGENTS` renders the merged AGENTS.md.
  - Pipeable: `automil show-skill --runtime claude > /tmp/preview.md`.
  - No write side-effects.

- **D-94:** **`automil trajectory` Click group** lives at `src/automil/cli/trajectory.py` with two subcommands:
  - `automil trajectory record <event-json>` — the runtime-agnostic fallback (covers runtimes without hook support, like Codex). Reads `<event-json>` (string or `@filepath`), parses, calls `record_event(node_id=os.environ["AUTOMIL_NODE_ID"], event=parsed, archive_dir=...)`. Exits 0 on success, 0 on soft-fail (with stderr WARNING). Hard-fails only on JSON parse error or missing `AUTOMIL_NODE_ID` env.
  - `automil trajectory export <node_id> [--out <path>]` — produces a redacted, schema-validated bundle. Re-runs the redactor (defends against rule additions since capture). Bundle is `<node_id>.trajectory.tar.gz` containing `trajectory.jsonl` + any rotated siblings + a `manifest.json` listing schema version + line counts + redaction-rule-set hash.

### Hook integration (TRJ-04)

- **D-95:** **Hook integration matrix** for Phase 3:
  | Runtime | Hook mechanism | Integration |
  |---|---|---|
  | Claude Code | `Stop` hook + post-tool-use (already in `claude_assets/hooks/on_stop.sh`; **EXTEND** in 03-09) | Hook script invokes `automil trajectory record "$(claude_event_json)"` after each tool call |
  | opencode | `~/.config/opencode/hooks/on_tool_call.sh` (opencode supports hooks per [opencode docs](https://github.com/opencode-ai/opencode)) | New hook script in `agent_assets/opencode/hooks/`, installed by `automil init --runtime opencode` |
  | Codex | **CLI-fallback only** (Codex hook surface unstable as of 2026-05) | User documentation + `agent_assets/codex/README.md` showing how to invoke `automil trajectory record` from a manual hook script if desired |
  | DeepSeek | Routed via opencode/Codex; uses host runtime's hook | Documented in `agent_assets/deepseek/README.md` (MRT-06) |

- **D-96:** **The `claude_assets/hooks/on_stop.sh` extension** is additive: it currently fires nothing trajectory-related. Phase 3 extends it to:
  ```bash
  if [[ -n "${AUTOMIL_NODE_ID:-}" && -n "${AUTOMIL_RUNTIME:-}" ]]; then
      # CLAUDE_HOOK_EVENT is the JSON event payload Claude Code provides
      automil trajectory record "${CLAUDE_HOOK_EVENT:-}" 2>>"${AUTOMIL_DIR:-/tmp}/trajectory.err.log" || true
  fi
  ```
  Soft-fail (`|| true`) — a recorder error never breaks Claude Code's hook chain. The opencode hook is structurally identical (different env-var name for the event payload).

### Submit pathway integration (TRJ-05, MRT)

- **D-97:** **`cli/submit.py` extension** writes `metadata.runtime = os.environ.get("AUTOMIL_RUNTIME", "unknown")` into the queue spec. Symmetric to Phase 2's D-76 (`metadata.backend`). Tells the orchestrator which runtime is requesting the run; passed to the experiment process via `JobSpec.env`. ~3 lines.

- **D-98:** **`automil/.gitignore` template** (rendered by `automil init`) gains:
  ```
  # Trajectories — gitignored by default; use `automil trajectory export` to share
  archive/*/trajectory.jsonl
  archive/*/trajectory.*.jsonl
  archive/*/trajectory.err.log
  ```
  Existing `.gitignore.j2` template is extended in 03-10. Pre-existing projects using autoMIL pre-Phase-3 get the new entries by re-running `automil init --update` (idempotent re-init merges new entries).

### Acceptance gate (TRJ-06, MRT-05) — Pitfall-3 anti-acceptance

- **D-99:** **Phase 3 acceptance** is the conjunction of:
  1. `pytest tests/trajectory/` is fully green: `test_recorder.py` (append, redaction, rotation, soft-fail), `test_schema.py` (schema-version mismatch tolerance), `test_redactor.py` (positive case for each leak class above).
  2. `pytest tests/agent_assets/` is fully green: `test_overlay.py` (section-replacement merge), `test_show_skill.py`, `test_init_runtime.py`.
  3. **The two-runtime smoke test `tests/agent_assets/test_smoke_two_runtimes.py` is green**: Claude Code AND opencode each execute one full submit→run→complete→archive cycle (against `LocalBackend` with a stub training script that exits 0) with each runtime's hook script firing `automil trajectory record` and producing a non-empty trajectory.jsonl with the correct runtime metadata in line 1.
  4. `python -c "import opentelemetry"` raises `ModuleNotFoundError` after a fresh `pip install -e .`.
  5. Existing Phase 0+1+2 baseline (425 + 9 skipped) stays green — no regressions.
  6. `grep -r "claude_assets" src/automil/` returns matches only in `compat.py`.
  7. `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/` returns zero.

  This conjunction is the Pitfall-3 anti-acceptance defence: "an experiment loop runs end-to-end on ≥2 runtimes" is operationally testable, not just claim-able.

### Out of scope (Phase 3)

- **D-100:** **Codex native hook integration** — CLI-fallback only in Phase 3. Codex hook API is unstable as of 2026-05; revisit in Phase 4 or after Codex stabilises. The `agent_assets/codex/README.md` documents the manual fallback.
- **D-101:** **Trajectory replay / "as-protocol reproducibility"** — paper-time work, NOT framework. Phase 3 captures forensically; replay is explicitly downstream.
- **D-102:** **`automil trajectory diff <node_id_a> <node_id_b>`** and other trajectory-analysis commands — v2.
- **D-103:** **Per-runtime training-script trampoline** — out of scope. Each runtime declares itself via `AUTOMIL_RUNTIME`; the training script is runtime-agnostic.
- **D-104:** **Concurrent multi-runtime orchestration** (running Claude + opencode in parallel against the same graph) — v2 / paper-time grid.
- **D-105:** **Cross-runtime trajectory comparison tooling** — v2.
- **D-106:** **OTel SDK runtime dependency** — explicitly forbidden in Phase 3 (we use field-name strings only). If a future phase needs SDK features (sampling, batching, OTLP export), it ships behind an extra: `pip install -e '.[otel]'`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` § Phase 3 (success criteria 1–5)
- `.planning/REQUIREMENTS.md` TRJ-01..06, MRT-01..06
- `.planning/PROJECT.md` § Key decisions (multi-runtime is v1, not paper-time)

### Existing framework code (Phase 3 extends these)
- `src/automil/cli/init.py` (150 lines) — current `claude_assets` install path; extension target for D-92
- `src/automil/claude_assets/skills/automil/SKILL.md` (156 lines) — content extracted into `_shared/SKILL.md`
- `src/automil/claude_assets/skills/automil-setup/SKILL.md` (122 lines) — likewise
- `src/automil/claude_assets/hooks/on_stop.sh` — extension target for D-96
- `src/automil/compat.py` lines 94–96 — `_PLANNED_MIGRATIONS["automil.claude_assets"]` declared in Phase 0; promoted in 03-02

### Phase 0 patterns (continue them)
- `.planning/phases/00-…/00-PATTERNS.md` § "Atomic write via tempfile + os.rename"
- `.planning/phases/00-…/00-PATTERNS.md` § "Click subcommand file structure"

### Phase 1 patterns (continue them)
- `.planning/phases/01-…/01-PATTERNS.md` § 1 "CLI command file organization"
- `.planning/phases/01-…/01-PATTERNS.md` § 7 "ClickException error format"

### Phase 2 patterns (continue them)
- `.planning/phases/02-…/02-PATTERNS.md` § "Frozen dataclass with tuple types"
- `.planning/phases/02-…/02-PATTERNS.md` § "Lazy backend imports inside command body"
- `src/automil/backends/_orchestrator_daemon.py` — orchestrator owns `archive/<node_id>/` lifecycle; trajectory writes piggyback on this

### Anti-pattern reference
- `.planning/research/PITFALLS.md` § Pitfall 3 — multi-runtime untested-but-claimed (Phase 3's primary defence)
- `.planning/research/PITFALLS.md` § Pitfall 5 — trajectory leaks/bloats/fossilises (three failure modes; Phase 3 addresses all)

### External specs
- [OpenTelemetry GenAI semantic conventions v1.30](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — field-name source for `gen_ai.*` keys (D-81)
- [AGENTS.md spec](https://agents.md) — Linux Foundation / OpenAI / opencode shared format (D-90)

</canonical_refs>

<specifics>
## Specific Ideas

- **Renaming `claude_assets/` → `agent_assets/` is `git mv`** so blame is preserved across all skill/hook content. Phase 0+2 precedent: `git mv` for cli.py and orchestrator.py renames.
- **`_shared/SKILL.md` content** comes from the current `claude_assets/skills/automil/SKILL.md` minus any Claude-Code-specific paragraphs (e.g., `.claude/skills/` install path). The Claude-specific paragraphs live in `claude/SKILL.md` as overlay. Same pattern for `automil-setup/SKILL.md`.
- **`AGENTS.md` (project root)** content draft (locked in 03-06):
  ```markdown
  # AGENTS

  This project uses autoMIL — an autonomous experiment framework for ML.

  ## How to work in this repo
  - Read `automil/program.md` for the experiment goals.
  - Read `automil/learnings.md` before submitting (avoid repeating dead-ends).
  - Submit experiments via `automil submit`. Never run training scripts directly.

  ## Constraints
  - Cap: 6h per cell (framework-enforced, Phase 4).
  - Trajectories captured automatically (gitignored by default).

  ## Runtime
  - Set `AUTOMIL_RUNTIME` to declare your runtime.
  ```
  Per-runtime overlays add native specifics (e.g., Claude's skill-invocation conventions).
- **Two-runtime smoke test** (`tests/agent_assets/test_smoke_two_runtimes.py`) uses **`LocalBackend` with a stub training script** (exits 0, writes a trivial `result.json`). The "runtime" half is exercised by setting `AUTOMIL_RUNTIME={claude-code|opencode}` + invoking the runtime's installed hook script (which fires `automil trajectory record` against a synthetic event payload). The test asserts: (a) `result.json` valid; (b) `trajectory.jsonl` first line metadata has correct `runtime`; (c) `trajectory.jsonl` has ≥1 event line; (d) no leaked-secret substring in the file.
- **`automil trajectory record` exit codes:** `0` for both success and soft-fail (recorder soft-fails are NOT user errors). `1` for hard errors (JSON parse, missing env). This makes the CLI safe to invoke from `|| true` hook tails.
- **Section-replacement merge** is implemented as a regex-based H2 splitter — NOT a markdown-AST parser. ~40 lines. Splitting on `^## ` in MULTILINE mode; canonical/overlay are dicts keyed by header text; output is `[h1] + ordered union of sections`.

</specifics>

<deferred>
## Deferred Ideas

- **Real Codex hook integration** — Phase 4 / post-Codex-stabilisation; CLI-fallback only in Phase 3.
- **`automil trajectory replay`** (re-execute a trajectory against the same runtime+version) — paper-time, possibly v2.
- **`automil trajectory diff`, `automil trajectory analyse`** — v2.
- **Concurrent multi-runtime orchestration** (running Claude + opencode in parallel against the same graph) — v2 / `CMR-*` requirement category.
- **Per-runtime training-script trampoline** — out of scope; runtime is declared, not dispatched.
- **OTel SDK runtime dependency** — explicitly forbidden in Phase 3; gated behind a future `[otel]` extra if ever needed.
- **Per-event redaction-rule customisation in `automil/config.yaml`** — out of scope; redaction rules are framework-locked in Phase 3 (defends against accidental disable).

</deferred>

---

*Phase: 03-trajectory-recorder-multi-runtime-asset-reorganisation*
*Context bootstrapped autonomously 2026-05-03 per Leo's "decide engineering, ask features" directive. No open questions for Leo at planning time.*
