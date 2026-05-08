# Phase 7: Hardware Autodetect + /automil-setup Skill — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 8 new/modified files
**Analogs found:** 8 / 8

---

## Pattern Map

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/automil/backends/base.py` | ABC definition | request-response | `src/automil/backends/base.py` (JobSpec/JobHandle) | exact — extend same file |
| `src/automil/backends/local.py` | Backend impl | request-response | `src/automil/backends/local.py` (submit/poll/cancel) | exact — add method to same class |
| `src/automil/cli/init.py` | CLI command | request-response | `src/automil/cli/init.py` (existing init command) | exact — extend same command |
| `src/automil/cli/check.py` | CLI command | request-response | `src/automil/cli/check.py` (nvidia-smi subprocess block) | exact — reuse subprocess pattern |
| `src/automil/agent_assets/_shared/skills/automil-setup/SKILL.md` | skill content | N/A | `src/automil/agent_assets/_shared/skills/automil/SKILL.md` | role-match — same skill format |
| `src/automil/agent_assets/_overlay.py` | content merger | transform | `src/automil/agent_assets/_overlay.py` (merge_skill) | exact — existing mechanism |
| `tests/backends/test_healthcheck.py` (new) | test | N/A | `tests/test_orchestrator_nvidia_smi.py` | role-match — subprocess mock pattern |
| `tests/backends/test_contract.py` (extend) | test | N/A | `tests/backends/test_contract.py` (S-01..S-12 pattern) | exact — extend same parameterised suite |

---

## Pattern Assignments

### `src/automil/backends/base.py` — HealthReport dataclass + `healthcheck()` ABC method (D-189)

**Analog:** `src/automil/backends/base.py` lines 36-56 (JobHandle and JobSpec frozen dataclass pattern) and lines 113-167 (Backend ABC abstract method pattern).

**Frozen dataclass pattern** (base.py lines 36-55):
```python
@dataclass(frozen=True)
class JobHandle:
    """Immutable reference to a submitted job (D-52).

    Carries no live process objects — backends look up rich state via
    `opaque_id`.  Frozen and hashable; safe to use as a dict key or set
    member.  JSON-serialisable via ``dataclasses.asdict(handle)``.
    """
    node_id: str
    backend: str
    opaque_id: str
    submitted_at: float
```

HealthReport follows the same `@dataclass(frozen=True)` shape. Tuple fields (not list) for hashability — same convention as `overlay_files: tuple[str, ...]` in JobSpec (base.py line 73) and `env: tuple[tuple[str, str], ...]` (line 83).

**Abstract method declaration pattern** (base.py lines 122-130):
```python
@abstractmethod
def submit(self, spec: JobSpec) -> JobHandle:
    """Submit a job and return a handle immediately (D-55).

    Eventually-consistent: the handle may reflect ``pending`` for several
    poll cycles after submission.  Backends do NOT block on actual job start.
    Caller responsibility: poll until terminal state.
    """
```

Copy this docstring structure for `healthcheck()`: one-line summary, then bullet semantics, then caller contract. The method must be `@abstractmethod` — NOT `@abstractmethod` with a default body (no "optional" fallback; D-189 says backwards-incompatibility is acceptable).

**Imports to add** (base.py lines 8-16 for reference — add these):
```python
from datetime import datetime
from typing import Literal
```
`Literal` is already importable from `typing` (Python 3.8+); `datetime` is stdlib. Both are import-clean.

---

### `src/automil/backends/local.py` — `LocalBackend.healthcheck()` implementation (D-190)

**Analog:** `src/automil/backends/_orchestrator_daemon.py` lines 242-272 (`query_gpus()` function — the definitive nvidia-smi subprocess block).

**CUDA probe pattern** (_orchestrator_daemon.py lines 248-272):
```python
result = subprocess.run(
    [
        NVIDIA_SMI_PATH,
        "--query-gpu=index,memory.total,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits",
    ],
    capture_output=True,
    text=True,
    timeout=10,
)
gpus = []
for line in result.stdout.strip().splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 4:
        gpus.append(GPUInfo(
            index=int(parts[0]),
            total_mb=int(parts[1]),
            ...
        ))
```

Phase 7 adapts this pattern: change `--query-gpu=index,memory.total,...` to `--query-gpu=index,memory.total` (only two columns needed), divide MB by 1024.0 for GB, and build `gpu_vram_gb: tuple[float, ...]` from the parsed values. Use `NVIDIA_SMI_PATH` from `automil.backends._orchestrator_daemon` (the CLN-05 path-pinned constant) — do NOT re-resolve via `shutil.which` inside `healthcheck()`.

**Import pattern** (local.py lines 22-34):
```python
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from automil.backends.base import Backend, JobHandle, JobSpec, JobState
from automil.backends.errors import BackendError
from automil.backends import register
```

Add `import subprocess` and `import sys` to this block. Import `HealthReport` from `automil.backends.base` (the same import line as `Backend, JobHandle, ...`).

**ROCm fallback structure** — no existing analog in this repo. Model on the CUDA block above: wrap `subprocess.run(["rocm-smi", ...])` in a try/except `FileNotFoundError` and check `returncode`. Parse `--showmeminfo vram --csv` output to extract VRAM MB per device.

**CPU terminal fallback:**
```python
return HealthReport(
    gpu_count=0,
    gpu_vram_gb=(),
    accelerator="cpu",
    python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    automil_version=importlib.metadata.version("automil"),
    detection_status="ok",
    detection_warnings=(),
    detected_at=datetime.utcnow(),
)
```

---

### `src/automil/cli/check.py` — GPU probe subprocess pattern (D-190, CLN-05 reuse)

**Analog:** `src/automil/cli/check.py` lines 147-158 (existing nvidia-smi block in `check()`) and lines 187-194 (`NVIDIA_SMI_PATH` import + report).

**Existing check() GPU block** (check.py lines 147-158):
```python
try:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        warnings.append("nvidia-smi failed. GPU scheduling may not work correctly.")
    else:
        n_gpus = len(result.stdout.strip().splitlines())
        click.echo(f"GPUs detected: {n_gpus}")
except (FileNotFoundError, subprocess.TimeoutExpired):
    warnings.append("nvidia-smi not found. GPU scheduling will use fallback.")
```

**Key delta for Phase 7:** `LocalBackend.healthcheck()` uses `NVIDIA_SMI_PATH` (the CLN-05 path-pinned constant), NOT the bare `"nvidia-smi"` string that check.py currently uses. The check.py block above is the OLD pattern — `healthcheck()` is the correct new form. Do NOT copy the bare string.

**NVIDIA_SMI_PATH import pattern** (check.py lines 190-193):
```python
from automil.orchestrator import NVIDIA_SMI_PATH

if NVIDIA_SMI_PATH != "nvidia-smi":
    click.echo(f"nvidia-smi: {NVIDIA_SMI_PATH}")
else:
    click.echo("nvidia-smi: bare PATH lookup (path detection failed)")
```

Phase 7 extends `check()` with a `--healthcheck` flag that calls `LocalBackend().healthcheck()` and pretty-prints the `HealthReport`. The existing issues/warnings accumulator pattern (check.py lines 103-337) is the correct shape: branch on `report.detection_status == "failed"` to `issues.append(...)`, on `"partial"` to `warnings.append(...)`.

---

### `src/automil/cli/init.py` — `--no-healthcheck` flag + healthcheck call insertion (D-191)

**Analog:** `src/automil/cli/init.py` lines 174-213 (command decorator + `--update` guard block).

**Option decorator pattern** (init.py lines 174-194):
```python
@main.command()
@click.argument("path", default="automil")
@click.option("--task", default="binary", help="Task type: binary or multiclass")
@click.option("--encoder", default="hoptimus1", help="Primary encoder name")
@click.option(
    "--runtime",
    default=None,
    type=click.Choice([...]),
    help="Runtime to install assets for ..."
)
@click.option(
    "--update",
    is_flag=True,
    default=False,
    help="Re-render skills/hooks/AGENTS.md for installed runtimes without re-scaffolding",
)
def init(path: str, task: str, encoder: str, runtime: str | None, update: bool) -> None:
```

Add `--no-healthcheck` as an `is_flag=True` option in this decorator block (same pattern as `--update`). Wire it as a `no_healthcheck: bool` parameter.

**Insertion point** (init.py lines 211-215 — the `--update` guard):
```python
if automil_dir.exists() and (automil_dir / "config.yaml").exists():
    if not update:
        raise click.ClickException(f"autoMIL already initialized at {automil_dir}")
    # --update: skip scaffold, proceed to asset re-install
```

Insert the healthcheck call AFTER this block, BEFORE the scaffold/template rendering block (line 216). Pattern:
```python
if not no_healthcheck:
    from automil.backends.local import LocalBackend  # noqa: PLC0415
    report = LocalBackend().healthcheck()
    _print_health_report(report)
    if report.detection_status == "failed":
        if not click.confirm("Detection failed; use conservative defaults? [y/N]", default=False):
            raise click.ClickException(
                "Healthcheck failed and operator declined conservative defaults. "
                "Run `automil init --no-healthcheck` to skip, or fix GPU drivers."
            )
```

**click.confirm pattern** — already used in the codebase (grep confirms `click.confirm` appears in CLI files). The `default=False` makes Enter mean "abort", matching D-191's `[y/N]` contract.

**Jinja2 context stamping** (init.py lines 232-247):
```python
context = {
    "task_type": task,
    "encoder": encoder,
    "project_name": project_root.name,
}

for template_name, target_name in [
    ("config.yaml.j2", "config.yaml"),
    ...
]:
    template = env.get_template(template_name)
    (automil_dir / target_name).write_text(template.render(**context))
```

Extend `context` with `healthcheck_gpu_count`, `healthcheck_vram_gb`, `healthcheck_accelerator` keys derived from the `HealthReport`. These keys are consumed by `config.yaml.j2` to stamp concrete default values (not comments).

---

### `src/automil/cli/lifecycle/port_variant.py` — Idempotency 3-way diff pattern (D-194)

**Analog:** `src/automil/cli/lifecycle/port_variant.py` lines 254-269 (idempotency check block).

**Idempotency check pattern** (port_variant.py lines 254-269):
```python
# 7. Idempotence check: if module exists with matching node_id, no-op.
if module_path.exists() and manifest_path.exists():
    try:
        existing = Manifest.read(manifest_path)
    except Exception:
        existing = None
    if existing is not None and existing.spec.node_id == node_id:
        click.echo(f"port-variant: {final_name} already ported (node_id match); no-op.")
        return
    if existing is not None and existing.spec.node_id != node_id:
        raise click.ClickException(
            f"Refusing to port: {module_path} already exists with "
            f"node_id={existing.spec.node_id!r}, but you're porting "
            f"node_id={node_id!r}. Names collide. Use `--name <other_name>` "
            f"to disambiguate."
        )
```

The skill 3-way diff in D-194 is a more elaborate version of this pattern:
1. Detect existing file (analogous to `module_path.exists()`)
2. Compute drafted version (analogous to `spec` object)
3. Diff existing vs drafted (new step — `difflib.unified_diff`)
4. For each changed section: prompt `overwrite | keep | merge` (analogous to the `click.ClickException` hard-fail, but interactive)

The key idempotency invariant to copy: **same inputs produce zero diff, and zero diff is a silent no-op**. Only non-trivial diffs (excluding whitespace/comment-only changes) surface a prompt.

**Atomic write pattern** (port_variant.py line 155 via `_shared.py`):
```python
_atomic_write_text(target_path, body)
```
All skill file writes in Phase 7 must use the same `_atomic_write_text` helper from `src/automil/cli/lifecycle/_shared.py`. Never use `path.write_text()` directly for skill artifact writes.

---

### `src/automil/agent_assets/_overlay.py` — Per-runtime overlay rebuild (D-196)

**Analog:** `src/automil/agent_assets/_overlay.py` lines 42-95 (`merge_skill` function, full file).

**Section-replacement merge pattern** (_overlay.py lines 26-39):
```python
_H2_SPLIT = re.compile(r"^(## .+)$", re.MULTILINE)

def _parse_sections(text: str) -> tuple[str, dict[str, str]]:
    """Split markdown text into (preamble, {h2_header: body})."""
    parts = _H2_SPLIT.split(text)
    preamble = parts[0]
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections[header] = body
    return preamble, sections
```

**Merge invocation pattern** (init.py lines 271-273):
```python
from automil.agent_assets._overlay import merge_skill  # noqa: E402
...
merged = merge_skill(rt, shared_skill, overlay_arg)
dst.write_text(merged, encoding="utf-8")
```

Phase 7 workflow: (1) edit `_shared/skills/automil-setup/SKILL.md` with full D-189..D-196 narrative; (2) run `automil init --update` on the project to trigger `_install_runtime_assets` which calls `merge_skill` for each runtime. The per-runtime overlay SKILL.md files in `claude/skills/automil-setup/`, `codex/`, etc. only exist if they have runtime-specific frontmatter overrides. If a runtime has no overlay file, `merge_skill` returns the shared content unchanged (see _overlay.py lines 63-69). No manual editing of per-runtime files is needed.

**Warning — code-block H2 limitation** (_overlay.py lines 9-13):
```
WARNING: The `^## ` H2 split treats ANY line beginning with `## ` as a section header,
INCLUDING lines inside fenced code blocks (e.g., bash comments like `## usage`).
Skill authors MUST NOT use `## ` at the start of a line inside a fenced code block.
```
All new content added to `_shared/automil-setup/SKILL.md` must honor this constraint.

---

### `tests/backends/test_healthcheck.py` (new) — subprocess mock test pattern (D-197, D-198)

**Analog:** `tests/test_orchestrator_nvidia_smi.py` lines 22-68 (subprocess mock + module reload pattern).

**subprocess.run mock pattern** (test_orchestrator_nvidia_smi.py lines 56-69):
```python
def test_subprocess_uses_pinned_path(monkeypatch):
    mod = _reload_with_which(monkeypatch, "/opt/nvidia/nvidia-smi")
    captured_argv: dict[str, str] = {}

    def fake_run(argv, **kwargs):
        captured_argv["argv0"] = argv[0]
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    mod.query_gpus()
    assert captured_argv["argv0"] == "/opt/nvidia/nvidia-smi"
```

Phase 7 test file uses the same `monkeypatch.setattr(subprocess, "run", fake_run)` pattern. The six test cases from D-198 map to distinct `fake_run` return values:

| Test case | `fake_run` stdout | `fake_run` returncode | Expected HealthReport fields |
|---|---|---|---|
| cuda-3-gpu happy | `"0, 49140\n1, 49140\n2, 49140\n"` | 0 | `gpu_count=3`, `accelerator="cuda"`, `status="ok"` |
| cuda-no-gpus | `""` | 0 | falls through to ROCm probe |
| rocm-fallback | CUDA fails, ROCm stdout non-empty | 0 | `accelerator="rocm"`, `status="ok"` |
| cpu-fallback | both CUDA + ROCm fail | non-zero | `gpu_count=0`, `accelerator="cpu"`, `status="ok"` |
| partial detection | `"0, 49140\n1, NOTANUMBER\n"` | 0 | `gpu_count=1`, `status="partial"`, warning in `detection_warnings` |
| full-failure | CUDA fails, `CUDA_VISIBLE_DEVICES` set | non-zero | `status="failed"`, non-empty `detection_warnings` |

**CliRunner pattern for init integration test** (test_orchestrator_nvidia_smi.py lines 72-102):
```python
from click.testing import CliRunner
runner = CliRunner()
result = runner.invoke(main, ["check"])
assert "nvidia-smi:" in result.output
```

`tests/backends/test_healthcheck.py` uses `CliRunner` to test `automil init` integration (D-198 criterion 2): invoke `main, ["init", "--no-healthcheck"]` with a tmp_path project root and assert the rendered `config.yaml` contains expected default values.

**Contract test extension pattern** (tests/backends/test_contract.py lines 46-60):
```python
# S-12  restart recovery -- fresh instance sees completed job as not running
```
Extend this file with `test_healthcheck_returns_health_report(backend)` parameterised across all backends. For `LocalBackend`: assert `isinstance(report, HealthReport)`. For MockSLURMBackend/SLURMBackend/RayBackend: assert `raises NotImplementedError` (per D-189's deferred contract).

---

## Shared Patterns

### Frozen dataclass with detection-status payload
**Source:** `src/automil/backends/base.py` lines 36-110 (JobHandle + JobSpec)
**Apply to:** `HealthReport` definition in `base.py`
- `@dataclass(frozen=True)` — mandatory
- All sequence fields use `tuple[T, ...]` NOT `list[T]` — preserves hashability
- All fields have type annotations; no bare `Any`
- Class docstring references the decision ID (D-189)

### Subprocess-with-stdout-CSV-parse
**Source:** `src/automil/backends/_orchestrator_daemon.py` lines 248-272 (`query_gpus`)
**Apply to:** `LocalBackend.healthcheck()` CUDA probe
- Use `NVIDIA_SMI_PATH` constant (never bare `"nvidia-smi"`)
- `capture_output=True, text=True, timeout=10`
- Parse with `line.split(",")` + `[p.strip() for p in parts]`
- Guard `len(parts) >= N` before indexing
- Catch `(subprocess.TimeoutExpired, FileNotFoundError, Exception)` — same broad catch as query_gpus

### Click command with optional flag for CI bypass
**Source:** `src/automil/cli/init.py` lines 188-194 (`--update` flag pattern)
**Apply to:** `--no-healthcheck` flag in `init()`
- `is_flag=True, default=False`
- Flag name follows `--no-X` negation convention

### Idempotent write with conflict detection
**Source:** `src/automil/cli/lifecycle/port_variant.py` lines 254-269
**Apply to:** skill 3-way diff in `/automil-setup` implementation
- Check existing file first; if missing, write directly (no diff needed)
- If existing matches drafted exactly: silent no-op, echo one-liner
- If conflict: interactive prompt, never silent overwrite

### H2-section overlay merge
**Source:** `src/automil/agent_assets/_overlay.py` lines 42-95
**Apply to:** per-runtime SKILL.md propagation
- Edit `_shared/` only; let `merge_skill` propagate
- Section matching is case-sensitive, exact-whitespace
- No `## ` at start of line inside fenced code blocks

### Atomic file write
**Source:** `src/automil/cli/lifecycle/_shared.py` (`_atomic_write_text`)
**Apply to:** all Phase 7 file writes (skill artifacts, config.yaml stamps)
- Use `_atomic_write_text(path, content)` — tempfile + `os.replace`
- Never `path.write_text()` for files that could be corrupted by concurrent writes

---

## Caveats / Anti-patterns to Avoid

1. **DO NOT execute user code during skill repo inspection (D-193).** The skill uses AST-walk (`ast.parse` + `ast.walk`) to find `nn.Module` subclasses, not `importlib.import_module` or `exec`. Executing arbitrary training scripts during setup would (a) consume GPU time, (b) trigger side effects, and (c) violate the boundary between inspection and execution. Any detection that cannot be done via `ast.parse` + regex grep falls back to "ask the user."

2. **DO NOT silently fall back on detection failure (STP-03, D-190).** The pattern in `check.py` lines 153-158 uses `warnings.append(...)` for a missing nvidia-smi — that is the OLD behaviour. `HealthReport.detection_status == "failed"` must surface as a blocking prompt in `automil init` (`click.confirm`), not a silent fallback to defaults. The `cpu` fallback is only reached when all probes are genuinely absent (no `CUDA_VISIBLE_DEVICES` set, no nvidia-smi, no rocm-smi); it is not a silent recovery path for a *failing* GPU environment.

3. **DO NOT mutate per-runtime overlay frontmatter inline.** The four per-runtime SKILL.md files (`claude/skills/automil-setup/SKILL.md`, `codex/`, `opencode/`, `deepseek/`) are managed exclusively by `_overlay.py`'s `merge_skill`. Phase 7 edits `_shared/automil-setup/SKILL.md` only. If runtime-specific frontmatter (e.g., Claude's `tools:` allowlist) needs updating, edit the per-runtime overlay file and let `merge_skill` reconstruct the merged output at install time. Inline edits to merged destination files are destroyed on the next `automil init --update`.

4. **DO NOT add `healthcheck()` as optional/default-implemented on the ABC.** D-189 explicitly accepts backwards-incompatibility. Adding a default `raise NotImplementedError` as a non-abstract method would silently pass contract tests for backends that never implement it. It must be `@abstractmethod` so that subclasses that fail to implement it raise `TypeError` at instantiation time, not at call time.

5. **DO NOT use bare `"nvidia-smi"` string in `LocalBackend.healthcheck()`.** Always import and use `NVIDIA_SMI_PATH` from `automil.backends._orchestrator_daemon`. The existing `check.py` lines 148-158 is an acknowledged technical debt (it predates CLN-05); the new `healthcheck()` implementation is the correct reference.

6. **DO NOT skip the setup-done gate submit (D-195, STP-06).** The gate calls `automil submit` with a real training script to validate the `result.json` write path, composite scoring, and reconcile flow. A `--dry-run` flag on the training script does NOT satisfy this requirement — only a terminal-state experiment with `status: completed` and a valid composite score counts.

---

## Files with No Analog (Planner uses RESEARCH.md patterns)

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `src/automil/backends/base.py::HealthReport` | dataclass | N/A | New dataclass; analog is JobSpec/JobHandle in same file (exact) |
| `tests/skills/test_setup_idempotency.py` | test | N/A | No existing skill idempotency tests; closest analog is test_lifecycle_port_variant.py |
| `tests/skills/test_setup_dry_run_gate.py` | test | N/A | No existing gate-validation tests; closest analog is test_integration.py end-to-end flows |

---

## Metadata

**Analog search scope:** `src/automil/backends/`, `src/automil/cli/`, `src/automil/agent_assets/`, `tests/backends/`, `tests/`
**Files scanned:** 14 source files, 3 test files
**Pattern extraction date:** 2026-05-07
