"""Coverage for subprocess env whitelist + config passthrough (CLN-02 / D-04).

Replaces the `env = {**os.environ, ...}` leak at orchestrator._launch with an
explicit whitelist + config-driven passthrough. Operator secrets like
OPENAI_API_KEY / WANDB_API_KEY / GITHUB_TOKEN / AWS_SECRET_ACCESS_KEY MUST NOT
flow into experiment subprocesses unless the consumer config explicitly opts
each one in via env.passthrough.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from automil.orchestrator import ExperimentOrchestrator


@pytest.fixture
def orch(tmp_path, monkeypatch):
    """Build an orchestrator with a minimal automil/ skeleton + isolated env baseline."""
    automil_dir = tmp_path / "automil"
    automil_dir.mkdir()
    (automil_dir / "config.yaml").write_text(
        "orchestrator: {}\n"
        "env:\n"
        "  passthrough: [MY_CUSTOM_VAR, OPTIONAL_MISSING_VAR]\n"
    )
    (tmp_path / ".git").mkdir()

    # Hard-set fake secrets so we can detect leaks deterministically.
    for k in ("OPENAI_API_KEY", "WANDB_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "SECRET-NEVER-LEAK")
    monkeypatch.setenv("MY_CUSTOM_VAR", "passthrough-value")
    monkeypatch.delenv("OPTIONAL_MISSING_VAR", raising=False)

    return ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)


def _call_build(orch, **overrides):
    """Helper to invoke _build_subprocess_env with sensible defaults."""
    defaults = dict(
        gpu_id=0,
        node_id="node_0001",
        archive=Path("/tmp/archive_test"),
        spec={"description": "test", "env": {}},
        pythonpath="/tmp/wt/benchmarks/src",
        worktree_benchmarks=Path("/tmp/wt/benchmarks"),
    )
    defaults.update(overrides)
    return orch._build_subprocess_env(**defaults)


def test_system_literals_pass(orch, monkeypatch):
    """System-minimal literal whitelist (PATH, HOME, USER, ...) flows through."""
    for var in ("PATH", "HOME", "USER", "SHELL", "LANG", "TZ", "TMPDIR", "LD_LIBRARY_PATH"):
        monkeypatch.setenv(var, f"value-of-{var}")
    env = _call_build(orch)
    for var in ("PATH", "HOME", "USER", "SHELL", "LANG", "TZ", "TMPDIR", "LD_LIBRARY_PATH"):
        assert env.get(var) == f"value-of-{var}", f"system literal {var} missing or wrong"


def test_system_prefix_globs_pass(orch, monkeypatch):
    """LC_*, CUDA_*, NVIDIA_*, AUTOMIL_* prefix-globs flow through."""
    cases = {
        "LC_ALL": "en_US.UTF-8",
        "LC_CTYPE": "en_US",
        "CUDA_HOME": "/usr/local/cuda",
        "CUDA_PATH": "/usr/local/cuda",
        "NVIDIA_VISIBLE_DEVICES": "all",
        "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
        "AUTOMIL_FOO": "bar",
    }
    for k, v in cases.items():
        monkeypatch.setenv(k, v)
    env = _call_build(orch)
    for k, v in cases.items():
        assert env.get(k) == v, f"prefix-glob {k} missing"


def test_secrets_do_not_leak(orch):
    """Operator secrets must NOT inherit into subprocess env (the CLN-02 fix)."""
    env = _call_build(orch)
    for k in ("OPENAI_API_KEY", "WANDB_API_KEY", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"):
        assert k not in env, f"secret {k} leaked into subprocess env"


def test_passthrough_present_passes(orch):
    """Config-declared passthrough vars present in os.environ flow through."""
    env = _call_build(orch)
    assert env.get("MY_CUSTOM_VAR") == "passthrough-value"


def test_passthrough_missing_does_not_block(orch):
    """Missing passthrough vars are simply absent — they do NOT block scheduling."""
    env = _call_build(orch)
    assert "OPTIONAL_MISSING_VAR" not in env
    # The present sibling DID make it through, proving the loop didn't abort.
    assert "MY_CUSTOM_VAR" in env


def test_passthrough_missing_warns_at_construction(tmp_path, monkeypatch, caplog):
    """Missing passthrough vars log WARN at orchestrator construction (D-04)."""
    automil_dir = tmp_path / "automil"
    automil_dir.mkdir()
    (automil_dir / "config.yaml").write_text(
        "orchestrator: {}\n"
        "env:\n"
        "  passthrough: [SOME_DEFINITELY_MISSING_VAR]\n"
    )
    (tmp_path / ".git").mkdir()
    monkeypatch.delenv("SOME_DEFINITELY_MISSING_VAR", raising=False)

    with caplog.at_level(logging.WARNING, logger="automil.orchestrator"):
        ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)

    assert any(
        "SOME_DEFINITELY_MISSING_VAR" in rec.getMessage() for rec in caplog.records
    ), "expected WARN for missing passthrough key"


def test_orchestrator_injected_vars_always_set(orch):
    """Orchestrator-injected fixed keys are always set."""
    env = _call_build(orch, gpu_id=3)
    assert env["CUDA_VISIBLE_DEVICES"] == "3"
    assert env["AUTOMIL_GPU"] == "0"
    assert env["AUTOMIL_NODE_ID"] == "node_0001"
    assert "AUTOMIL_RESULTS_DIR" in env
    assert "AUTOMIL_DESC" in env


def test_autobench_root_still_injected_phase0(orch):
    """D-05: AUTOBENCH_ROOT injection stays in Phase 0; Phase 8 owns removal."""
    env = _call_build(orch, worktree_benchmarks=Path("/tmp/wt/benchmarks"))
    assert env.get("AUTOBENCH_ROOT") == "/tmp/wt/benchmarks"


def test_spec_env_overrides(orch):
    """Per-spec env values override whitelist matches (last-write-wins)."""
    env = _call_build(orch, spec={"description": "x", "env": {"MY_CUSTOM_VAR": "spec-wins"}})
    assert env["MY_CUSTOM_VAR"] == "spec-wins"


def test_spec_env_cannot_override_blocked_keys(orch):
    """spec.env CANNOT override AUTOMIL_GPU / CUDA_VISIBLE_DEVICES (T-00-09 mitigation)."""
    env = _call_build(
        orch,
        gpu_id=2,
        spec={"description": "x", "env": {"AUTOMIL_GPU": "99", "CUDA_VISIBLE_DEVICES": "99"}},
    )
    assert env["AUTOMIL_GPU"] == "0"
    assert env["CUDA_VISIBLE_DEVICES"] == "2"


def test_config_without_env_section(tmp_path, monkeypatch):
    """If config.yaml has no env: section, orchestrator constructs cleanly with empty passthrough."""
    automil_dir = tmp_path / "automil"
    automil_dir.mkdir()
    (automil_dir / "config.yaml").write_text("orchestrator: {}\n")
    (tmp_path / ".git").mkdir()
    o = ExperimentOrchestrator(project_root=tmp_path, automil_dir=automil_dir)
    assert o._env_passthrough == []


def test_pythonpath_overrides_whitelist_value(orch, monkeypatch):
    """The orchestrator-injected PYTHONPATH wins over the whitelisted os.environ['PYTHONPATH']."""
    monkeypatch.setenv("PYTHONPATH", "/some/parent/path")
    env = _call_build(orch, pythonpath="/tmp/wt/benchmarks/src")
    assert env["PYTHONPATH"] == "/tmp/wt/benchmarks/src"
