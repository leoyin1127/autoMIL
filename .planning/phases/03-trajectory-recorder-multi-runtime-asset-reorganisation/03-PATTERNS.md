# Phase 3: Trajectory Recorder + Multi-Runtime Asset Reorganisation — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 31 new/modified files + 3 git-mv targets
**Analogs found:** 29 / 31 (2 novel: opencode TS plugin, runtime.py stub)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Existing Analog | Match Quality |
|-------------------|------|-----------|-------------------------|---------------|
| `src/automil/trajectory/__init__.py` | package public surface | request-response | `src/automil/backends/__init__.py` | exact |
| `src/automil/trajectory/schema.py` | constants + validator | request-response | `src/automil/backends/base.py` (JobState Enum + dataclasses) | role-match |
| `src/automil/trajectory/recorder.py` | service, file-I/O | file-I/O | `src/automil/backends/_orchestrator_daemon.py` (long-lived file writer) | role-match |
| `src/automil/trajectory/redactor.py` | utility, transform | transform | `src/automil/registry/validators/purity.py` (AST walker, compiled patterns) | role-match |
| `src/automil/trajectory/rotation.py` | service, file-I/O | file-I/O | `src/automil/cli/lifecycle/_shared.py` `_atomic_write_text` | partial |
| `src/automil/trajectory/export.py` | utility, batch | batch | `src/automil/registry/validators/` (read+validate+produce output) | partial |
| `src/automil/runtime.py` | utility | request-response | **Novel** — 3-line module; no existing analog; stdlib-only `os.environ.get` | none |
| `src/automil/agent_assets/_overlay.py` | utility, transform | transform | `src/automil/registry/validators/purity.py` (stateless pure function, regex-based) | role-match |
| `src/automil/agent_assets/_shared/SKILL.md` | asset (git mv) | — | `src/automil/claude_assets/skills/automil/SKILL.md` | exact (git mv) |
| `src/automil/agent_assets/_shared/AGENTS.md` | asset (new) | — | `src/automil/claude_assets/skills/automil/SKILL.md` (content source) | partial |
| `src/automil/agent_assets/claude/hooks/on_stop.sh` | hook script (git mv + extend) | event-driven | `src/automil/claude_assets/hooks/on_stop.sh` | exact (git mv + additive) |
| `src/automil/agent_assets/opencode/plugins/automil-trajectory.ts` | plugin (TypeScript/Bun) | event-driven | **Novel** — no TypeScript in the codebase; use RESEARCH.md §6 | none |
| `src/automil/cli/show_skill.py` | CLI command | request-response | `src/automil/cli/reconcile.py` (read-only CLI command, no side-effects) | exact |
| `src/automil/cli/trajectory.py` | CLI group + 2 subcommands | request-response | `src/automil/cli/orchestrator.py` (Click group with subcommands) | exact |
| `src/automil/cli/init.py` (modified) | CLI command, extended | request-response | `src/automil/cli/init.py` current (self) | exact (extend) |
| `src/automil/cli/submit.py` (modified) | CLI command, extended | request-response | `src/automil/cli/submit.py` lines 269-293 (D-76 backend pattern) | exact |
| `src/automil/compat.py` (modified) | re-export shim, promotion | — | `src/automil/orchestrator.py` PEP 562 shim + `compat.py` current | exact |
| `src/automil/templates/.gitignore.j2` (modified) | config template | — | `src/automil/templates/.gitignore.j2` current (self) | exact (extend) |
| `tests/trajectory/__init__.py` | test package | — | `tests/backends/__init__.py` | exact |
| `tests/trajectory/test_recorder.py` | unit test, file-I/O | file-I/O | `tests/test_runner.py` (file-system tests) | role-match |
| `tests/trajectory/test_schema.py` | unit test | request-response | `tests/test_registry_spec.py` (schema/dataclass contract tests) | role-match |
| `tests/trajectory/test_redactor.py` | unit test | transform | `tests/test_registry_validator_purity.py` (pattern-matching tests) | exact |
| `tests/trajectory/test_rotation.py` | unit test, file-I/O | file-I/O | `tests/test_runner.py` | role-match |
| `tests/agent_assets/__init__.py` | test package | — | `tests/backends/__init__.py` | exact |
| `tests/agent_assets/test_overlay.py` | unit test | transform | `tests/test_registry_validator_purity.py` (text transform + edge-case tests) | role-match |
| `tests/agent_assets/test_show_skill.py` | CLI integration test | request-response | `tests/test_cli.py` (CliRunner + tmp_path + monkeypatch.chdir) | exact |
| `tests/agent_assets/test_init_runtime.py` | CLI integration test | request-response | `tests/test_cli.py` TestInit class | exact |
| `tests/agent_assets/test_smoke_two_runtimes.py` | integration smoke test | event-driven | `tests/test_submit_writes_metadata_backend.py` (submit lifecycle + spec assertions) | role-match |

---

## Pattern Catalog

### 1. Package `__init__.py` as public re-export surface

**Analog:** `src/automil/backends/__init__.py:1-89`

**Imports pattern** (lines 1-21):
```python
"""Trajectory capture subpackage (TRJ-01..06 / D-78..D-87)."""
from __future__ import annotations

import logging

from automil.trajectory.schema import (
    TrajectorySchemaError,
    REQUIRED_FIELDS,
    validate_event,
)
from automil.trajectory.recorder import record_event, read_metadata
from automil.trajectory.rotation import RotationManager

logger = logging.getLogger(__name__)

__all__ = [
    "TrajectorySchemaError",
    "REQUIRED_FIELDS",
    "validate_event",
    "record_event",
    "read_metadata",
    "RotationManager",
]
```

**Rules carried forward from Phase 2:**
- `__init__.py` imports only from sibling submodules — never the reverse.
- `__all__` explicitly lists every exported name.
- `logger = logging.getLogger(__name__)` is the first non-import line.
- Phase / decision annotations as comments per the existing convention.
- Do NOT auto-import test-only utilities at package level.

---

### 2. Schema constants module (string constants + custom exception + validator)

**Analog:** `src/automil/backends/base.py:1-60`

**Pattern** (from lines 1-34 of base.py):
```python
"""Backend ABC + JobHandle + JobSpec + JobState (BCK-01 / D-51..D-58)."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    """Terminal / non-terminal job lifecycle states (D-53).

    String-valued so `json.dumps(JobState.RUNNING)` returns '"running"'
    without a custom encoder.
    """
    PENDING = "pending"
    RUNNING = "running"
    ...
```

**Apply to `schema.py`:** Use module-level string constants (NOT an Enum — field names are plain strings per D-78/D-81). Custom `TrajectorySchemaError(ValueError)` follows the same pattern as `BackendError(Exception)` in `src/automil/backends/errors.py`. The `validate_event(d: dict) -> None` function raises on missing required fields and passes silently on unknown fields (forward-compat per D-80). Module docstring cites D-78, D-80, D-81.

**Concrete excerpt from `errors.py:1-10`:**
```python
"""Backend-specific exceptions (BCK-01 / D-51)."""
from __future__ import annotations


class BackendError(Exception):
    """Raised by backend implementations for unrecoverable errors."""
```

For Phase 3 apply to `trajectory/schema.py`:
```python
class TrajectorySchemaError(ValueError):
    """Raised when a trajectory event or file fails schema validation (D-80, D-81)."""
```

---

### 3. Module-level compiled patterns (redactor) — regex at import time

**Analog:** `src/automil/registry/validators/purity.py` (AST walker with pre-built visitor state)

**Pattern reference from purity.py (structure, not AST):** The purity validator pre-computes its check set at class definition time and applies it per node during the walk. For `redactor.py` the same "compile-once, apply-many" discipline applies to the compiled regex list.

**D-82 `_PATTERNS` list (from RESEARCH.md §4 — verified by direct execution):**
```python
import re

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),        "sk-[REDACTED]"),
    (re.compile(r"hf_[A-Za-z0-9]{20,}"),            "hf_[REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"),           "ghp_[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"),           "AKIA[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_API_KEY)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_TOKEN)\s*[:=]\s*\S+"),   r"\1=[REDACTED]"),
    (re.compile(r"([A-Z][A-Z0-9_]{1,40}_KEY)\s*[:=]\s*\S+"),     r"\1=[REDACTED]"),
]

_SIZE_CAP_BYTES = 8192  # D-83: 8 KB per-event cap

logger = logging.getLogger(__name__)
```

**Soft-fail discipline (D-85 from RESEARCH.md §5):** Every public function in `redactor.py` is wrapped so exceptions are caught and logged at WARNING, returning a safe fallback (empty dict or the sentinel truncation event), never raising. The experiment process MUST NOT crash due to redactor failures.

**`redact_event` recursive walk pattern:** Walk dict → recurse values; list/tuple → recurse elements; str → apply `_PATTERNS`; int/float/bool/None → pass through unchanged. Returns a NEW dict — original is not mutated.

---

### 4. Long-lived file descriptor cache + `O_APPEND` + `flock` (recorder)

**Analog:** `src/automil/backends/_orchestrator_daemon.py` (long-lived daemon that keeps file handles for log writing) — role-match.

**Direct pattern (from RESEARCH.md §5 — verified by execution):**
```python
import fcntl
import os
import json
import threading

# Process-level fd cache — keyed by node_id, value is open fd (int)
_FD_CACHE: dict[str, int] = {}
_NODE_LOCKS: dict[str, threading.RLock] = {}
_DICT_LOCK = threading.Lock()   # protects _FD_CACHE + _NODE_LOCKS dicts


def _get_node_lock(node_id: str) -> threading.RLock:
    with _DICT_LOCK:
        if node_id not in _NODE_LOCKS:
            _NODE_LOCKS[node_id] = threading.RLock()
        return _NODE_LOCKS[node_id]


def _append_line(fd: int, data: dict) -> None:
    """Atomically append one JSON line. fd MUST be opened with O_APPEND."""
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        line = json.dumps(data, ensure_ascii=False) + "\n"
        os.write(fd, line.encode("utf-8"))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
```

**Critical flock gotcha (D-86 / RESEARCH.md §5):** Linux releases ALL locks when ANY fd to the file is closed. The recorder MUST keep an fd in `_FD_CACHE` and reuse it across events — never open-close per event. Cache is flushed on rotation and at `atexit`.

**`atexit` cleanup pattern:**
```python
import atexit

def _close_all_fds() -> None:
    for fd in list(_FD_CACHE.values()):
        try:
            os.close(fd)
        except OSError:
            pass
    _FD_CACHE.clear()

atexit.register(_close_all_fds)
```

---

### 5. Atomic rotation via `os.rename` (rotation manager)

**Analog:** `src/automil/graph.py:787-801` (ExperimentGraph.save — `tempfile.mkstemp` + `os.rename`)

**Existing code to copy from (`graph.py` lines 787-801):**
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

**Apply to `rotation.py`:**
- Soft rotation: `os.rename(traj_path, traj_path.with_suffix(f".{next_n}.jsonl"))` — same-filesystem rename is atomic (POSIX guarantee).
- `os.rename` not `os.replace` for rotation (source disappears; no overwrite needed).
- After rotation, open new `trajectory.jsonl` with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)` and write metadata header.
- Hard rotate returns `False` (soft-fail) + logs `CRITICAL`; never raises.
- `RotationManager` is a class (not a function) with `soft_bytes` and `hard_bytes` config fields, consistent with Phase 2's `@dataclass(frozen=True)` pattern.

---

### 6. Click group with subcommands

**Analog:** `src/automil/cli/orchestrator.py:1-44`

**Complete pattern (lines 1-44):**
```python
"""orchestrator subgroup: start, stop, status."""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir, _find_git_root


@main.group(name="orchestrator")
def orchestrator_group():
    """Manage the GPU scheduler daemon."""
    pass


@orchestrator_group.command("start")
def orch_start():
    """Start the orchestrator daemon."""
    from automil.orchestrator import ExperimentOrchestrator   # lazy import
    ...
```

**Apply to `cli/trajectory.py`:**
```python
"""trajectory subgroup: record and export trajectory events (TRJ-04..05 / D-94)."""
from __future__ import annotations

import click

from automil.cli import main


@main.group("trajectory")
def trajectory_group():
    """Trajectory capture commands."""
    pass


@trajectory_group.command("record")
@click.argument("event_json")
def record(event_json: str) -> None:
    """Record one trajectory event (runtime-agnostic CLI fallback)."""
    import json, os
    from automil.trajectory import record_event  # lazy import
    ...


@trajectory_group.command("export")
@click.argument("node_id")
@click.option("--out", default=None, help="Output path for the bundle tar.gz")
def export(node_id: str, out: str | None) -> None:
    """Produce a redacted, schema-validated trajectory bundle."""
    from automil.trajectory.export import export_bundle  # lazy import
    ...
```

**Registration in `cli/__init__.py`:** Add `from automil.cli import trajectory  # noqa: E402,F401` in alphabetical order (after `submit`, before `viz`).

---

### 7. Read-only CLI command (show-skill)

**Analog:** `src/automil/cli/reconcile.py:1-79` (read-only command with lazy import)

**Pattern to copy (reconcile.py lines 1-17):**
```python
"""reconcile command: sync experiment graph with orchestrator state."""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir


@main.command()
@click.option("--recompute-best", is_flag=True, default=False, help="...")
def reconcile(recompute_best: bool):
    """Sync experiment graph with orchestrator state."""
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph  # lazy import
    ...
    click.echo(...)
```

**Apply to `cli/show_skill.py`:**
```python
"""show-skill command: render merged per-runtime SKILL.md to stdout (D-93)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("show-skill")
@click.option("--runtime", required=True,
              type=click.Choice(["claude", "opencode", "codex",
                                 "deepseek-via-opencode", "deepseek-via-codex"]),
              help="Runtime to render the skill for")
@click.option("--asset", default="SKILL",
              type=click.Choice(["SKILL", "AGENTS"]),
              help="Which asset to render (default: SKILL)")
def show_skill(runtime: str, asset: str) -> None:
    """Render merged per-runtime skill file to stdout."""
    from automil.agent_assets._overlay import merge_skill  # lazy import
    from pathlib import Path
    package_dir = Path(__file__).parent.parent
    shared_path = package_dir / "agent_assets" / "_shared" / f"{asset}.md"
    overlay_path = package_dir / "agent_assets" / runtime / f"{asset}.md"
    result = merge_skill(runtime, shared_path, overlay_path if overlay_path.exists() else None)
    click.echo(result, nl=False)   # pipeable — no trailing newline added
```

---

### 8. `cli/init.py` extension — `--runtime` + `--update` flags

**Analog:** `src/automil/cli/init.py:34-54` (current guard + option pattern)

**Key existing code (lines 34-54 of init.py):**
```python
@main.command()
@click.argument("path", default="automil")
@click.option("--task", default="binary", help="Task type: binary or multiclass")
@click.option("--encoder", default="hoptimus1", help="Primary encoder name")
def init(path: str, task: str, encoder: str):
    """Add autoMIL to an existing project."""
    from jinja2 import Environment, FileSystemLoader

    project_root = Path.cwd()
    automil_dir = project_root / path
    ...
    if automil_dir.exists() and (automil_dir / "config.yaml").exists():
        raise click.ClickException(f"autoMIL already initialized at {automil_dir}")
```

**Phase 3 extension pattern:**
```python
@main.command()
@click.argument("path", default="automil")
@click.option("--task", default="binary", help="Task type: binary or multiclass")
@click.option("--encoder", default="hoptimus1", help="Primary encoder name")
@click.option(
    "--runtime",
    default=None,
    type=click.Choice(["claude", "opencode", "codex",
                       "deepseek-via-opencode", "deepseek-via-codex", "all"]),
    help="Runtime to install assets for (default: auto-detect)",
)
@click.option("--update", is_flag=True, default=False,
              help="Re-render skills/hooks/AGENTS.md for currently-installed runtimes without re-scaffolding")
def init(path: str, task: str, encoder: str, runtime: str | None, update: bool):
    ...
    # D-92: bypass the already-initialized guard when --update is set
    if automil_dir.exists() and (automil_dir / "config.yaml").exists():
        if not update:
            raise click.ClickException(f"autoMIL already initialized at {automil_dir}")
        # --update path: skip scaffold, go straight to asset re-install
    ...
    # Replace hard-coded claude_src block (init.py lines 88-144) with
    # runtime-aware loop using merge_skill() and the overlay merger.
    package_dir = Path(__file__).parent.parent
    from automil.agent_assets._overlay import merge_skill  # lazy import
    ...
```

**Settings.json hook registration pattern to reuse (init.py lines 120-144):**
```python
settings_path = project_claude / "settings.json"
hook_cmd = f"bash {project_root / '.claude' / 'hooks' / 'on_stop.sh'}"
if settings_path.exists():
    settings = json.loads(settings_path.read_text())
else:
    project_claude.mkdir(parents=True, exist_ok=True)
    settings = {}
hooks = settings.setdefault("hooks", {})
stop_hooks = hooks.setdefault("Stop", [])
already_registered = any(hook_cmd in str(entry) for entry in stop_hooks)
if not already_registered:
    stop_hooks.append({"hooks": [{"type": "command", "command": hook_cmd}]})
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
```

---

### 9. `submit.py` metadata.runtime — D-97 (3-line extension)

**Analog:** `src/automil/cli/submit.py:269-293` (D-76 metadata.backend pattern)

**Existing code to mirror (lines 269-293):**
```python
# D-76: read backend name from automil/config.yaml (default "local" if absent).
_automil_cfg = yaml.safe_load((adir / "config.yaml").read_text()) if (adir / "config.yaml").exists() else {}
_backend_name: str = _automil_cfg.get("backend", {}).get("name", "local")
...
spec.setdefault("metadata", {})["backend"] = _backend_name
```

**Phase 3 addition (D-97, ~3 lines directly after the backend line):**
```python
# D-97: write metadata.runtime so orchestrator + cancel.py know which
# runtime made this submission. AUTOMIL_RUNTIME is set by the agent runtime
# (never inferred — D-87). Falls back to "unknown" if unset.
import os as _os
spec.setdefault("metadata", {})["runtime"] = _os.environ.get("AUTOMIL_RUNTIME", "unknown")
```

---

### 10. `compat.py` — D-88 promotion of `automil.claude_assets`

**Analog:** `src/automil/orchestrator.py:1-64` (the Phase 2 PEP 562 re-export shim) + `src/automil/compat.py:80-112` (planned migration promotion rule)

**Orchestrator shim pattern (lines 47-64):**
```python
def __getattr__(name: str):
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    _warnings.warn(
        f"automil.orchestrator.{name} moved to automil.backends._orchestrator_daemon "
        f"in Phase 2 (D-60). Update imports by 2027-01.",
        DeprecationWarning,
        stacklevel=2,
    )
    from automil.backends import _orchestrator_daemon as _mod
    return getattr(_mod, name)
```

**`_DEPRECATION_MESSAGE_FORMAT` from compat.py line 80:**
```python
_DEPRECATION_MESSAGE_FORMAT = (
    "{old_path} moved to {new_path} in Phase {phase}; old import retained "
    "for backwards-compat. Update by {date}."
)
```

**Phase 3 promotion in `compat.py`:**
1. Remove `"automil.claude_assets"` entry from `_PLANNED_MIGRATIONS`.
2. Add a PEP 562 `__getattr__` in the Active aliases section that:
   - Short-circuits `__dunder__` probes (copy the `name.startswith("__")` guard from orchestrator.py line 55-57).
   - Emits `DeprecationWarning` with `_DEPRECATION_MESSAGE_FORMAT.format(old_path="automil.claude_assets", new_path="automil.agent_assets._shared + automil.agent_assets.claude", phase=3, date="2027-06")`.
   - Dynamically imports from the new location.
3. The `tests/test_compat.py:34` assertion `assert "automil.claude_assets" in compat._PLANNED_MIGRATIONS` will BREAK — that test must be updated to assert the entry is NOT in `_PLANNED_MIGRATIONS` (promoted) AND that accessing `automil.claude_assets` emits a `DeprecationWarning`. See the existing test pattern at `test_compat.py:7-16` for how to assert DeprecationWarning on USE.

---

### 11. `.gitignore.j2` extension — idempotent append

**Analog:** `src/automil/templates/.gitignore.j2` current (8 lines) + init.py's idempotent settings.json registration (lines 133-136)

**Current `.gitignore.j2` (complete, lines 1-9):**
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

**D-98 entries to append:**
```
# Trajectories — gitignored by default; use `automil trajectory export` to share
archive/*/trajectory.jsonl
archive/*/trajectory.*.jsonl
archive/*/trajectory.err.log
```

**Idempotent update pattern (for `--update` path):** Copy the `already_registered` check from init.py lines 133-136; apply it per-line to avoid duplicating gitignore entries. Simple `if line not in existing_content` check (string membership, not regex).

---

### 12. Section-replacement overlay merger (`_overlay.py`)

**Role:** Pure utility function (~40 lines). No analog exists for section-replacement markdown merge. The closest structural analog is `src/automil/registry/validators/purity.py` (stateless utility, regex-based, pure function, no I/O).

**Pattern from purity.py (structure to follow):**
```python
"""Purity validator: static AST checks for variant modules (REG-02 / D-28)."""
from __future__ import annotations
import re  # (purity uses ast; overlay uses re)
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def stateless_function(path: Path) -> None:
    """One-sentence docstring. Returns None or raises named exception."""
    ...
```

**D-89 implementation spec (from RESEARCH.md §9 — 40-line implementation):**
```python
"""Section-replacement overlay merger for agent_assets (MRT-01, MRT-02 / D-89).

WARNING: The `^## ` H2 split treats any line beginning with `## ` as a section
header — including lines inside fenced code blocks. Skill authors MUST NOT use
`## ` at the start of a line inside a fenced code block. Violation causes a
false section split. See tests/agent_assets/test_overlay.py for the documented
known limitation.
"""
from __future__ import annotations
import re
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_H2_SPLIT = re.compile(r"^(## .+)$", re.MULTILINE)


def _parse_sections(text: str) -> tuple[str, dict[str, str]]:
    parts = _H2_SPLIT.split(text)
    preamble = parts[0]
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections[header] = body
    return preamble, sections


def merge_skill(runtime: str, shared_path: Path, overlay_path: Path | None) -> str:
    """Merge _shared/<asset>.md with <runtime>/<asset>.md via H2 section-replacement.

    Section matching is case-sensitive and whitespace-exact (D-89).
    H1 title is always taken from _shared. Overlay MUST NOT contain H1.
    Returns the merged text as a string. No writes — purely functional.
    """
    shared_text = shared_path.read_text(encoding="utf-8")
    preamble, shared_sections = _parse_sections(shared_text)

    if overlay_path is None or not overlay_path.exists():
        return shared_text

    overlay_text = overlay_path.read_text(encoding="utf-8")
    _, overlay_sections = _parse_sections(overlay_text)

    merged = dict(shared_sections)
    for header, body in overlay_sections.items():
        merged[header] = body

    result = preamble
    for header in shared_sections:
        result += header + merged[header]
    for header in overlay_sections:
        if header not in shared_sections:
            result += header + overlay_sections[header]

    return result
```

---

### 13. `runtime.py` (novel — no analog)

**Pattern:** 3-line stdlib module. Follow the logger convention even at this small scale.

```python
"""Runtime declaration — reads AUTOMIL_RUNTIME env var (D-87)."""
from __future__ import annotations
import os
import logging

logger = logging.getLogger(__name__)


def get_runtime() -> str:
    """Return the declared runtime identifier.

    Reads AUTOMIL_RUNTIME env var. Returns "unknown" if unset.
    Never raises. Explicit declaration is required — never inferred (D-87).
    """
    return os.environ.get("AUTOMIL_RUNTIME", "unknown")
```

---

### 14. Claude Code hook script extension (`on_stop.sh`)

**Analog:** `src/automil/claude_assets/hooks/on_stop.sh:1-20` (git mv target, then additive extension)

**Current on_stop.sh (complete, lines 1-20):**
```bash
#!/usr/bin/env bash
# Hook: prevent agent from stopping while autoMIL loop is active.
# Exit 1 = prevent stop. Exit 0 = allow stop.

# Find project root by walking up
DIR="$PWD"
while [ "$DIR" != "/" ]; do
    if [ -f "$DIR/.automil_active" ]; then
        echo "autoMIL loop is active. Run 'automil stop-loop' to allow stopping."
        echo ""
        echo "Resume instructions:"
        echo "  1. Read config.yaml, graph.json, learnings.md, program.md"
        echo "  2. Run: automil reconcile"
        echo "  3. Continue the experiment loop"
        exit 1
    fi
    DIR="$(dirname "$DIR")"
done

exit 0
```

**D-96 additive extension (from RESEARCH.md §6 — CORRECTED: stdin, not env var):**
```bash
#!/usr/bin/env bash
# Hook payload arrives on stdin (Claude Code hook delivery mechanism — D-95/D-96)
HOOK_EVENT="$(cat)"

# Find project root by walking up
DIR="$PWD"
while [ "$DIR" != "/" ]; do
    if [ -f "$DIR/.automil_active" ]; then
        echo "autoMIL loop is active. Run 'automil stop-loop' to allow stopping."
        ...
        exit 1
    fi
    DIR="$(dirname "$DIR")"
done

# Trajectory recording — only fires if AUTOMIL_NODE_ID and AUTOMIL_RUNTIME are set
# (these are set by the orchestrator before starting the agent session, not by Claude Code)
if [[ -n "${AUTOMIL_NODE_ID:-}" && -n "${AUTOMIL_RUNTIME:-}" && -n "$HOOK_EVENT" ]]; then
    automil trajectory record "$HOOK_EVENT" \
        2>>"${AUTOMIL_DIR:-/tmp}/trajectory.err.log" || true
fi

exit 0
```

**CRITICAL:** `HOOK_EVENT=$(cat)` not `${CLAUDE_HOOK_EVENT:-}` — Claude Code sends payload on stdin, NOT via env var. The D-96 template in CONTEXT.md has the correct form; the RESEARCH.md §6 corrects the earlier hypothesis.

---

### 15. opencode TypeScript plugin (`automil-trajectory.ts`)

**Novel — no TypeScript in the codebase.** Use RESEARCH.md §6 spec verbatim. Planner must specify this file carefully.

**From RESEARCH.md §6 (verified against opencode docs):**
```typescript
// .opencode/plugins/automil-trajectory.ts
// Installed by `automil init --runtime opencode`
// Requires: opencode running on Bun (ships Bun runtime; $ is Bun shell API)
import { $ } from "bun"

export default function() {
    return {
        "tool.execute.after": async (
            input: { tool: string, args: Record<string, unknown>, sessionID: string },
            output: { title: string, output: string, metadata?: unknown }
        ) => {
            const nodeId = process.env.AUTOMIL_NODE_ID
            const runtime = process.env.AUTOMIL_RUNTIME ?? "opencode"
            if (!nodeId) return  // soft-fail if not in an autoMIL session
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

**Installation path:** `<project_root>/.opencode/plugins/automil-trajectory.ts` (project-level per opencode docs). Written by `automil init --runtime opencode`. No Python analog — planner must write the spec in full.

---

### 16. Test file structure (trajectory tests)

**Analog:** `tests/test_registry_validator_purity.py` (pattern-match tests) + `tests/test_submit_writes_metadata_backend.py` (lifecycle + spec assertion)

**Fixture pattern for trajectory tests (from `test_submit_writes_metadata_backend.py:21-33`):**
```python
@pytest.fixture
def cli_runner():
    return CliRunner()


def _init_git_repo(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True)
    (path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)
```

**Trajectory-specific test fixture pattern (pure file-system, no git needed):**
```python
@pytest.fixture
def archive_dir(tmp_path):
    node_id = "node_0001"
    d = tmp_path / "archive" / node_id
    d.mkdir(parents=True)
    return d, node_id
```

**Positive-case redactor test pattern (from `test_registry_validator_purity.py` style):**
```python
@pytest.mark.parametrize("secret,expected_redacted", [
    ("sk-abcdefghijklmnopqrstu",        "sk-[REDACTED]"),
    ("hf_abcdefghijklmnopqrstu1234",    "hf_[REDACTED]"),
    ("ghp_abcdefghijklmnopqrstuvwxyz1234", "ghp_[REDACTED]"),
    ("AKIAIOSFODNN7EXAMPLE",            "AKIA[REDACTED]"),
    ("OPENAI_API_KEY=sk-abc123",        "OPENAI_API_KEY=[REDACTED]"),
    ("MY_TOKEN=verysecretvalue",        "MY_TOKEN=[REDACTED]"),
])
def test_redact_positive(secret, expected_redacted):
    from automil.trajectory.redactor import redact
    assert redact(secret) == expected_redacted
```

---

### 17. Two-runtime smoke test

**Analog:** `tests/test_submit_writes_metadata_backend.py` (submit lifecycle test) + `tests/backends/test_contract.py` (parametrize with `id=` labels)

**Parametrize pattern (from test_contract.py):**
```python
@pytest.mark.parametrize("runtime", [
    pytest.param("claude-code", id="claude"),
    pytest.param("opencode",    id="opencode"),
])
def test_smoke_runtime(runtime, tmp_path, monkeypatch):
    """Full submit → hook simulation → trajectory assertion."""
    ...
```

**Hook simulation pattern (D-99 / RESEARCH.md §11):**
```python
import subprocess
event = {
    "gen_ai.provider.name": runtime,
    "gen_ai.event.name": "tool_call",
    "gen_ai.event.timestamp": "2026-05-03T00:00:00.000000Z",
    "gen_ai.tool.name": "Bash",
    "gen_ai.tool.call.arguments": "{}",
    "gen_ai.tool.call.result": "done",
}
env = {**os.environ, "AUTOMIL_NODE_ID": node_id, "AUTOMIL_RUNTIME": runtime}
result = subprocess.run(
    ["automil", "trajectory", "record", json.dumps(event)],
    env=env,
    capture_output=True,
    text=True,
)
assert result.returncode == 0   # both success and soft-fail return 0 (D-94)
```

**Trajectory assertions pattern:**
```python
traj_path = archive_dir / "trajectory.jsonl"
assert traj_path.exists()
lines = traj_path.read_text().splitlines()
assert len(lines) >= 2          # line 0 = metadata, line 1+ = events
metadata = json.loads(lines[0])
assert metadata["runtime"] == runtime
assert metadata["schema_version"].startswith("trajectory-v1")
content = traj_path.read_text()
for secret_pattern in ["sk-", "hf_", "ghp_", "AKIA"]:
    assert secret_pattern not in content or "[REDACTED]" in content
```

---

## Shared Patterns

### Module logger
**Source:** `src/automil/backends/base.py:17`, `src/automil/backends/__init__.py:21`
**Apply to:** All new `trajectory/*.py` files, `agent_assets/_overlay.py`, `runtime.py`
```python
logger = logging.getLogger(__name__)
```
First non-import line in every module.

### Soft-fail discipline (trajectory-specific)
**Source:** D-85 locked decision (no existing codebase analog — trajectory introduces this pattern)
**Apply to:** `trajectory/recorder.py`, `trajectory/redactor.py`, `trajectory/rotation.py`
Every public function wraps its body in `try/except Exception` → log `WARNING` → return `False` (or safe fallback). NEVER raises from the recorder. Exceptions are caught, logged, and swallowed. This is intentional and mandatory — experiment processes MUST NOT die from trajectory failures.

### ClickException hard-fail format
**Source:** `src/automil/cli/submit.py:62-67`, `src/automil/cli/cancel.py:73-77`
**Apply to:** `cli/trajectory.py` (hard-fail on JSON parse error or missing `AUTOMIL_NODE_ID`), `cli/show_skill.py`, `cli/init.py` (runtime not recognised)
```python
raise click.ClickException(
    f"Refusing to record: JSON parse error: {exc}. "
    f"Event must be a valid JSON object. "
    f"Check the output from your hook script."
)
```

### Lazy imports inside CLI command bodies
**Source:** `src/automil/cli/reconcile.py:39`, `src/automil/cli/cancel.py:62-63`
**Apply to:** All three new CLI files (`trajectory.py`, `show_skill.py`, `init.py` extension)
```python
# Inside the Click command function:
from automil.trajectory import record_event   # lazy — prevents circular import
from automil.agent_assets._overlay import merge_skill   # lazy
```

### Atomic file write (tempfile + os.rename)
**Source:** `src/automil/graph.py:787-801`, `src/automil/cli/cancel.py:184-195`
**Apply to:** `trajectory/rotation.py` (atomic rotation rename), any state file writes in `trajectory/recorder.py`
The cancel.py version (lines 184-195) is the most direct copy-paste template since it uses `os.replace` and is in a CLI context. The graph.py version uses `os.rename` (for same-filesystem guarantee).

### `from __future__ import annotations` + module docstring
**Source:** Every file in `src/automil/cli/`, `src/automil/backends/`
**Apply to:** All new Python files without exception. Line 1 is always `"""<verb> / purpose (D-XX / REQ-YY)."""`, line 2 is blank, line 3 is `from __future__ import annotations`.

### Test `_init_git_repo` helper
**Source:** `tests/test_cli.py:19-37`, duplicated in `tests/test_submit_writes_metadata_backend.py:26-33`
**Apply to:** `tests/agent_assets/test_init_runtime.py`, `tests/agent_assets/test_smoke_two_runtimes.py`
Copy verbatim — do not re-implement. All CLI integration tests that call `automil init` need this helper.

### `cli/__init__.py` registration (alphabetical order)
**Source:** `src/automil/cli/__init__.py:20-31`
**Apply to:** New entries for `show_skill` and `trajectory` commands
```python
# Insert between `submit` and `viz` alphabetically:
from automil.cli import show_skill   # noqa: E402,F401
from automil.cli import trajectory   # noqa: E402,F401
```

---

## Novel Items (no codebase analog)

| File | Role | Reason | Instruction |
|------|------|--------|-------------|
| `src/automil/agent_assets/opencode/plugins/automil-trajectory.ts` | TypeScript/Bun plugin | No TypeScript in codebase; opencode plugin API is runtime-specific | Use RESEARCH.md §6 spec verbatim. Bun `$` shell API, `tool.execute.after` hook, soft-fail via `.nothrow()`. Planner must include the full TypeScript content in the plan. |
| `src/automil/runtime.py` | 3-line stdlib module | No existing single-function module with env-var read | Follow logger convention above; 3 lines + docstring; no external deps. |

---

## Anti-Patterns to Avoid (Phase 3 specific)

1. **`import opentelemetry` anywhere** — D-106 hard floor. Use field-name strings directly. `python -c "import opentelemetry"` must raise `ModuleNotFoundError` after `pip install -e .`. CI will catch this.

2. **Inferring runtime** — D-87: `AUTOMIL_RUNTIME` is explicit, never guessed. Do NOT try to detect runtime from `sys.argv[0]`, installed packages, or any heuristic. `get_runtime()` reads the env var and returns `"unknown"` as default.

3. **Open-close per event in recorder** — D-86: flock releases on ANY fd close. Keep the fd in `_FD_CACHE`, reuse across calls, close only on rotation or `atexit`. A per-event open/close causes silent lock release and loses multi-process safety.

4. **`## ` inside code blocks in SKILL.md content** — `_overlay.py`'s regex splitter treats any `^## ` line as a section boundary, including inside fenced code blocks. Skill content must avoid `## ` at line start inside fenced blocks. This known limitation is documented in the module docstring.

5. **`automil.claude_assets` references anywhere except `compat.py`** — D-88 hard floor: `grep -r "claude_assets" src/automil/` must return matches ONLY in `compat.py`. Any new file importing from `claude_assets` is a defect.

6. **`benchmarks/` or `AUTOBENCH_` references in trajectory/ or agent_assets/** — D-99 hard floor. These packages are framework-only. CI will catch via `grep -r "autobench\|AUTOBENCH_\|benchmarks/" src/automil/trajectory/ src/automil/agent_assets/`.

7. **`print()` in CLI commands** — existing convention: all CLI output uses `click.echo()`. The only exception is the orchestrator daemon's interactive status output.

8. **`_PLANNED_MIGRATIONS["automil.claude_assets"]` still present after Phase 3 compat.py edit** — D-08 promotion rule: the entry is REMOVED from `_PLANNED_MIGRATIONS` in the same commit that adds the live shim. `test_compat.py` must be updated simultaneously.

9. **Hard-failing in `trajectory record` on soft recorder errors** — D-94: exit code 0 for both success AND soft-fail; exit code 1 only for JSON parse error or missing `AUTOMIL_NODE_ID`. Hook scripts use `|| true` and a soft-fail exit-1 would be caught and ignored — but semantically wrong.

10. **Modifying `_shared/SKILL.md` content to be runtime-specific** — `_shared/` content is universal. Runtime-specific paragraphs go in the runtime overlay (`claude/SKILL.md`, `opencode/SKILL.md`). The `_shared` H1 title is always preserved; runtime overlays MUST NOT contain H1.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/automil/agent_assets/opencode/plugins/automil-trajectory.ts` | plugin | event-driven | No TypeScript/Bun code exists; opencode plugin API is unique to this ecosystem |
| `src/automil/runtime.py` | utility stub | request-response | Closest is a 1-line `os.environ.get` call — no module of this shape exists; it is too small to have a meaningful analog |

---

## Metadata

**Analog search scope:** `src/automil/backends/`, `src/automil/cli/`, `src/automil/graph.py`, `src/automil/orchestrator.py`, `src/automil/compat.py`, `src/automil/claude_assets/`, `src/automil/templates/`, `tests/`
**Files scanned:** 28 source files + 14 test files
**Pattern extraction date:** 2026-05-03

---

## PATTERN MAPPING COMPLETE
