"""Wave 0 stubs for D-172 SLURM-directive validation (BCK-05).

These tests assert that automil check refuses to run when backend.slurm.directives
is incomplete or contains the literal 'TODO_FILL_IN' sentinel. The validator
helper _validate_slurm_directives is created in plan 06-03.
"""
from __future__ import annotations

import pytest


def test_check_rejects_todo():
    """D-172: any TODO_FILL_IN sentinel in required directives raises SlurmDirectivesIncompleteError."""
    from automil.backends.errors import SlurmDirectivesIncompleteError
    from automil.cli.check import _validate_slurm_directives

    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "walltime_seconds": 21600,
                "directives": {
                    "partition": "TODO_FILL_IN",
                    "account": "mylab",
                    "cpus_per_task": 8,
                    "mem_gb": 48,
                },
            },
        },
    }
    with pytest.raises(SlurmDirectivesIncompleteError) as exc_info:
        _validate_slurm_directives(config)
    assert "partition" in exc_info.value.missing_keys


def test_check_accepts_complete():
    """D-172: validator returns None when all required keys present and no TODO sentinels."""
    from automil.cli.check import _validate_slurm_directives

    config = {
        "backend": {
            "name": "slurm",
            "slurm": {
                "walltime_seconds": 21600,
                "directives": {
                    "partition": "compute",
                    "account": "mylab",
                    "cpus_per_task": 8,
                    "mem_gb": 48,
                },
            },
        },
    }
    # Should NOT raise
    _validate_slurm_directives(config)


def test_walltime_seconds_to_timeout_min():
    """RESEARCH.md OQ-1: walltime_seconds -> timeout_min = max(1, walltime_seconds // 60)."""
    from automil.backends.slurm import _walltime_to_timeout_min

    assert _walltime_to_timeout_min(0) == 1          # min floor
    assert _walltime_to_timeout_min(30) == 1         # < 60s rounds up to 1
    assert _walltime_to_timeout_min(60) == 1
    assert _walltime_to_timeout_min(120) == 2
    assert _walltime_to_timeout_min(21600) == 360    # 6h
