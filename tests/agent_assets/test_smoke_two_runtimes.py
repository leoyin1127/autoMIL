"""Two-runtime smoke test — Phase 3 Pitfall-3 anti-acceptance gate (MRT-05 / D-99).

Exercises submit→run→complete→archive→trajectory for:
- claude-code (simulated via automil trajectory record CLI with AUTOMIL_RUNTIME=claude-code)
- opencode   (simulated via automil trajectory record CLI with AUTOMIL_RUNTIME=opencode)

Does NOT launch actual Claude Code or opencode processes — exercises the hook's downstream
effect directly. This is the operational definition of Pitfall-3 compliance: two runtimes
produce valid, correctly-tagged trajectories in a single CI run (D-99).

This test is the Phase 3 acceptance gate. Phase 3 is NOT done until both arms are green.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from automil.trajectory import record_event, read_metadata
from automil.trajectory.schema import TrajectorySchemaError


# --- Fixtures ---

@pytest.fixture
def automil_project(tmp_path: Path):
    """Minimal autoMIL project with archive/ directory."""
    automil_dir = tmp_path / "automil"
    archive_dir = automil_dir / "archive"
    archive_dir.mkdir(parents=True)
    (automil_dir / "config.yaml").write_text(
        "backend:\n  name: local\ntrajectory:\n  soft_rotate_bytes: 5242880\n"
    )
    return tmp_path, automil_dir, archive_dir


def _make_trajectory_event(runtime: str) -> dict:
    """Build a valid gen_ai.* trajectory event for the given runtime."""
    return {
        "gen_ai.provider.name":      runtime,
        "gen_ai.event.name":         "tool_call",
        "gen_ai.event.timestamp":    "2026-05-03T00:00:00.000000Z",
        "gen_ai.tool.name":          "Bash",
        "gen_ai.tool.call.arguments": '{"command": "echo hello"}',
        "gen_ai.tool.call.result":    "hello\n",
    }


# --- Claude Code arm: REAL hook script invocation (proves D-95/D-96 stdin contract) ---

def test_smoke_claude_hook_script(
    automil_project,
    tmp_path: Path,
) -> None:
    """Pitfall-3 / D-99 conjunct 3: invoke the REAL Claude Code hook script.

    Pipes a synthetic gen_ai.* event JSON to `bash agent_assets/claude/hooks/on_stop.sh`
    on stdin (matching how Claude Code delivers hook payloads per D-95/D-96 corrected).
    Asserts the trajectory.jsonl receives the event with correct runtime metadata.

    This test FAILS if the on_stop.sh `HOOK_EVENT="$(cat)"` contract regresses.
    """
    tmp_path_proj, automil_dir, archive_dir = automil_project
    runtime = "claude-code"
    node_id = "node_smoke_claude_hook"

    # Locate the real installed hook script (after 03-10 lands).
    repo_root = Path(__file__).resolve().parents[2]
    hook_script = repo_root / "src" / "automil" / "agent_assets" / "claude" / "hooks" / "on_stop.sh"
    assert hook_script.exists(), (
        f"Claude hook script not found at {hook_script} — 03-10 must land first"
    )

    event = _make_trajectory_event(runtime)
    event_json = json.dumps(event)

    env = {
        **os.environ,
        "AUTOMIL_NODE_ID":  node_id,
        "AUTOMIL_RUNTIME":  runtime,
        "AUTOMIL_DIR":      str(automil_dir),
    }

    # Invoke the REAL hook script with the event piped on stdin.
    # This is what Claude Code does in production.
    result = subprocess.run(
        ["bash", str(hook_script)],
        input=event_json,
        env=env,
        capture_output=True,
        text=True,
        cwd=str(tmp_path_proj),
    )

    assert result.returncode == 0, (
        f"on_stop.sh failed (exit {result.returncode})\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Assert trajectory.jsonl was written by the hook → CLI → recorder chain.
    traj_path = archive_dir / node_id / "trajectory.jsonl"
    assert traj_path.exists(), (
        f"trajectory.jsonl not created — on_stop.sh did not deliver event to recorder.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    lines = traj_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2, f"Expected >=2 lines, got {len(lines)}"

    metadata = json.loads(lines[0])
    assert metadata["runtime"] == runtime, (
        f"runtime mismatch: {metadata['runtime']!r} != {runtime!r}"
    )
    assert metadata["schema_version"].startswith("trajectory-v1")

    for event_line in lines[1:]:
        parsed = json.loads(event_line)
        assert "gen_ai.event.name" in parsed

    # No unredacted secret tokens (TRJ-06 / D-99).
    content = traj_path.read_text(encoding="utf-8")
    import re as _re
    for secret_prefix in ["sk-", "hf_", "ghp_"]:
        pat = _re.compile(rf"{_re.escape(secret_prefix)}[A-Za-z0-9_\-]{{20,}}")
        assert not pat.findall(content), (
            f"Unredacted {secret_prefix!r} token in trajectory: {pat.findall(content)}"
        )


# --- opencode arm: static-content check (Bun runtime not assumed in CI) ---

def test_smoke_opencode_plugin_static_content() -> None:
    """Pitfall-3 / D-99 conjunct 3 (opencode arm): static-content check on the plugin.

    Bun (the opencode plugin runtime) is not assumed available in CI. This test
    verifies the plugin file exists and contains the wiring that delivers events
    to `automil trajectory record` via Bun's `$` shell API. End-to-end Bun
    execution is a documented manual smoke step (Leo's workstation).
    """
    repo_root = Path(__file__).resolve().parents[2]
    plugin = repo_root / "src" / "automil" / "agent_assets" / "opencode" / "plugins" / "automil-trajectory.ts"
    assert plugin.exists(), (
        f"opencode plugin not found at {plugin} — 03-10 must land first"
    )

    content = plugin.read_text(encoding="utf-8")

    # tool.execute.after is the opencode hook anchor we care about (per D-95).
    assert "tool.execute.after" in content, (
        "opencode plugin missing `tool.execute.after` declaration — hook will never fire"
    )

    # Bun shell-API call to invoke `automil trajectory record` is the delivery path.
    # Match permissively: either `$\`automil trajectory record` (Bun's tagged-template form)
    # OR `Bun.$` / `await $\`automil` — any plausible Bun shell invocation.
    assert "automil trajectory record" in content, (
        "opencode plugin must invoke `automil trajectory record` to deliver events"
    )
    assert ("$`" in content) or ("Bun.$" in content) or ("await $" in content), (
        "opencode plugin must use Bun's $ shell API to invoke the CLI"
    )

    # AUTOMIL_RUNTIME=opencode must be set on the spawned process so the recorder
    # tags the trajectory correctly.
    assert "AUTOMIL_RUNTIME" in content, (
        "opencode plugin must set AUTOMIL_RUNTIME on the recorder subprocess"
    )


# --- Compatibility: keep the cheap CLI-only assertion for both runtimes too ---

@pytest.mark.parametrize("runtime", [
    pytest.param("claude-code", id="claude_cli"),
    pytest.param("opencode",    id="opencode_cli"),
])
def test_smoke_record_cli_for_runtime(
    runtime: str,
    automil_project,
    tmp_path: Path,
) -> None:
    """Cheap smoke: `automil trajectory record` exits 0 for both runtimes when
    AUTOMIL_RUNTIME is set. This complements the real hook script test above —
    it gates that the CLI path the hooks invoke works for each runtime tag.
    """
    tmp_path_proj, automil_dir, archive_dir = automil_project
    node_id = f"node_cli_{runtime.replace('-', '_')}"

    event = _make_trajectory_event(runtime)
    env = {
        **os.environ,
        "AUTOMIL_NODE_ID":  node_id,
        "AUTOMIL_RUNTIME":  runtime,
        "AUTOMIL_DIR":      str(automil_dir),
    }

    # Use the automil CLI binary co-located with the current Python interpreter.
    # `-m automil.cli` does not work because automil.cli is a package (no __main__.py).
    automil_bin = Path(sys.executable).parent / "automil"
    result = subprocess.run(
        [str(automil_bin), "trajectory", "record", json.dumps(event)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(tmp_path_proj),
    )

    assert result.returncode == 0, (
        f"trajectory record CLI failed for runtime={runtime!r}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    traj_path = archive_dir / node_id / "trajectory.jsonl"
    assert traj_path.exists()
    lines = traj_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 2

    metadata = json.loads(lines[0])
    assert metadata["runtime"] == runtime
    assert metadata["schema_version"].startswith("trajectory-v1")


@pytest.mark.parametrize("runtime", ["claude-code", "opencode"])
def test_trajectory_metadata_forward_compat(
    runtime: str,
    automil_project,
    tmp_path: Path,
) -> None:
    """read_metadata() does not raise on v1 trajectory produced by the smoke run."""
    tmp_path_proj, automil_dir, archive_dir = automil_project
    node_id = f"node_compat_{runtime.replace('-', '_')}"

    # Write trajectory directly via record_event (faster than subprocess)
    from automil.trajectory import record_event
    event = _make_trajectory_event(runtime)
    record_event(
        node_id=node_id,
        event=event,
        archive_dir=archive_dir,
        runtime=runtime,
    )

    traj_path = archive_dir / node_id / "trajectory.jsonl"
    # read_metadata must not raise (v1 forward-compat)
    meta = read_metadata(traj_path)
    assert meta["schema_version"].startswith("trajectory-v1")
    assert meta["runtime"] == runtime


# --- Hard floor verification (D-99 conjuncts 4-7) ---

def test_no_opentelemetry_sdk_installed() -> None:
    """python -c 'import opentelemetry' raises ModuleNotFoundError (D-99 conjunct 4)."""
    result = subprocess.run(
        [sys.executable, "-c", "import opentelemetry"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "opentelemetry is importable! It must NOT be a runtime dependency (D-106)"
    )
    assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr


def test_no_claude_assets_outside_compat() -> None:
    """grep -r 'claude_assets' src/automil/ returns matches only in compat.py (D-99 conjunct 6)."""
    src_dir = Path(__file__).parent.parent.parent / "src" / "automil"
    result = subprocess.run(
        ["grep", "-r", "claude_assets", str(src_dir), "--include=*.py", "-l"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:  # grep found matches
        files_with_match = [
            f for f in result.stdout.strip().splitlines()
            if not f.endswith("compat.py")
        ]
        assert not files_with_match, (
            f"claude_assets found outside compat.py: {files_with_match}\n"
            f"Hard floor D-99 conjunct 6 violated."
        )


def test_no_autobench_in_trajectory_or_agent_assets() -> None:
    """grep autobench/benchmarks in trajectory/ and agent_assets/ returns zero (D-99 conjunct 7)."""
    src_dir = Path(__file__).parent.parent.parent / "src" / "automil"
    for subdir in ["trajectory", "agent_assets"]:
        target = src_dir / subdir
        if not target.exists():
            continue
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "autobench\\|AUTOBENCH_\\|benchmarks/", str(target)],
            capture_output=True,
            text=True,
            shell=False,
        )
        # Also check plaintext files
        result2 = subprocess.run(
            ["grep", "-r", "--include=*.md", "--include=*.sh", "--include=*.ts",
             "autobench", str(target)],
            capture_output=True,
            text=True,
        )
        combined = (result.stdout + result2.stdout).strip()
        assert not combined, (
            f"autobench/benchmarks references found in {subdir}/:\n{combined}\n"
            f"Hard floor D-99 conjunct 7 violated."
        )
