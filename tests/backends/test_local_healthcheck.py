"""Unit tests for D-198 clause 1: LocalBackend.healthcheck (STP-01 / D-189 / D-190).

Six tests, one per bullet in D-198 clause 1:
  1.1 cuda-3-gpu happy path
  1.2 cuda-no-gpus falls through to CPU (when CUDA_VISIBLE_DEVICES unset)
  1.3 rocm fallback (CUDA fails, ROCm succeeds)
  1.4 cpu terminal fallback (all probes fail, no GPU env signal)
  1.5 partial detection (1-of-2 GPUs unparseable)
  1.6 full failure prompts override (CUDA_VISIBLE_DEVICES set, all probes fail)

All probes are subprocess.run-mocked. No real nvidia-smi / rocm-smi invoked.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from automil.backends.base import HealthReport
from automil.backends.local import LocalBackend


def _mock_run(stdout: str = "", returncode: int = 0, raise_exc: BaseException | None = None):
    """Build a side_effect callable for subprocess.run that returns the given fields.

    If raise_exc is provided, raises that exception instead of returning a result.
    The callable inspects argv[0] / argv to dispatch CUDA vs ROCm vs MIG-mode probes.
    """
    def _side_effect(argv, **kwargs):
        if raise_exc is not None:
            raise raise_exc
        return MagicMock(stdout=stdout, returncode=returncode, stderr="", args=argv)
    return _side_effect


def test_healthcheck_cuda_3_gpu_happy_path(monkeypatch):
    """D-198 clause 1.1: 3 CUDA GPUs detected; status='ok', accelerator='cuda'."""
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def _side_effect(argv, **kwargs):
        if "mig.mode.current" in str(argv):
            return MagicMock(stdout="Disabled\nDisabled\nDisabled\n", returncode=0, stderr="")
        # CUDA query-gpu=index,memory.total
        return MagicMock(stdout="0, 49140\n1, 49140\n2, 49140\n", returncode=0, stderr="")

    with patch("subprocess.run", side_effect=_side_effect):
        report = LocalBackend().healthcheck()

    assert isinstance(report, HealthReport)
    assert report.gpu_count == 3
    assert report.accelerator == "cuda"
    assert report.detection_status == "ok"
    assert all(47.0 <= v <= 48.5 for v in report.gpu_vram_gb), report.gpu_vram_gb
    assert report.detection_warnings == ()


def test_healthcheck_cuda_no_gpus_falls_through_to_cpu(monkeypatch):
    """D-198 clause 1.2: CUDA stdout empty -> ROCm tried -> ROCm absent -> CPU; status='ok'.

    Without CUDA_VISIBLE_DEVICES, no-GPU is a legitimate environment, so status='ok'.
    """
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def _side_effect(argv, **kwargs):
        # Both probes return empty stdout (no GPUs detected on either path).
        if "rocm-smi" in str(argv[0]):
            raise FileNotFoundError("rocm-smi not present")
        return MagicMock(stdout="", returncode=1, stderr="")

    with patch("subprocess.run", side_effect=_side_effect):
        report = LocalBackend().healthcheck()

    assert report.gpu_count == 0
    assert report.gpu_vram_gb == ()
    assert report.accelerator == "cpu"
    assert report.detection_status == "ok"
    assert report.detection_warnings == ()


def test_healthcheck_rocm_fallback(monkeypatch):
    """D-198 clause 1.3: CUDA absent, ROCm present -> accelerator='rocm', status='ok'."""
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def _side_effect(argv, **kwargs):
        argv_str = str(argv[0])
        if "rocm-smi" in argv_str:
            # rocm-smi --csv: columns vary; pick a 2-GPU shape with VRAM in bytes.
            return MagicMock(
                stdout="device,Total VRAM (B)\ncard0,68719476736\ncard1,68719476736\n",
                returncode=0,
                stderr="",
            )
        # CUDA path: nvidia-smi missing.
        raise FileNotFoundError("nvidia-smi not on PATH")

    with patch("subprocess.run", side_effect=_side_effect):
        report = LocalBackend().healthcheck()

    assert report.accelerator == "rocm"
    assert report.detection_status == "ok"
    assert report.gpu_count == 2
    assert all(60.0 <= v <= 70.0 for v in report.gpu_vram_gb), report.gpu_vram_gb


def test_healthcheck_cpu_only(monkeypatch):
    """D-198 clause 1.4: all probes absent, no GPU env signal -> CPU 'ok'."""
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    with patch("subprocess.run", side_effect=FileNotFoundError("no probes available")):
        report = LocalBackend().healthcheck()

    assert report.accelerator == "cpu"
    assert report.gpu_count == 0
    assert report.detection_status == "ok"
    assert report.detection_warnings == ()


def test_healthcheck_partial_detection(monkeypatch):
    """D-198 clause 1.5: 1-of-2 GPUs unparseable -> status='partial', warning recorded."""
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)

    def _side_effect(argv, **kwargs):
        if "mig.mode.current" in str(argv):
            return MagicMock(stdout="Disabled\nDisabled\n", returncode=0, stderr="")
        return MagicMock(
            stdout="0, 49140\n1, [Not Supported]\n",
            returncode=0,
            stderr="",
        )

    with patch("subprocess.run", side_effect=_side_effect):
        report = LocalBackend().healthcheck()

    assert report.accelerator == "cuda"
    assert report.gpu_count == 2
    assert len(report.gpu_vram_gb) == 1, report.gpu_vram_gb
    assert report.detection_status == "partial"
    assert any("[Not Supported]" in w for w in report.detection_warnings), report.detection_warnings


def test_healthcheck_full_failure_prompts_override(monkeypatch):
    """D-198 clause 1.6: all probes fail AND CUDA_VISIBLE_DEVICES set -> status='failed'.

    STP-03: never silently default to CPU when user clearly expected a GPU.
    """
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,1,2")

    with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi missing")):
        report = LocalBackend().healthcheck()

    assert report.detection_status == "failed"
    assert report.accelerator == "cpu"  # CPU is the structural fallback; status surfaces failure
    assert any("CUDA_VISIBLE_DEVICES" in w for w in report.detection_warnings), report.detection_warnings
