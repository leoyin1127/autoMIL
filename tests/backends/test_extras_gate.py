"""Phase 6 D-153 extras-gate tests — `import automil` must never fail when extras absent."""
from __future__ import annotations

import importlib
import sys


def test_import_automil_backends_no_extras():
    """No-extras install: `import automil.backends` succeeds; SLURM/Ray backends absent from BACKENDS."""
    # If submitit/ray aren't installed, BACKENDS should not contain them.
    # If they ARE installed in the dev env, this is permissive — we only assert NO ImportError.
    importlib.import_module("automil.backends")
    from automil.backends import BACKENDS
    if "submitit" not in sys.modules and "ray" not in sys.modules:
        # Pure no-extras case — neither registered.
        assert "slurm" not in BACKENDS
        assert "ray" not in BACKENDS


def test_three_phase6_errors_in_public_namespace():
    """`from automil.backends import BackendNotInstalledError, ...` works."""
    from automil.backends import (
        BackendNotInstalledError,
        SlurmDirectivesIncompleteError,
        RayClusterUnreachableError,
    )
    assert BackendNotInstalledError.__name__ == "BackendNotInstalledError"
    assert SlurmDirectivesIncompleteError.__name__ == "SlurmDirectivesIncompleteError"
    assert RayClusterUnreachableError.__name__ == "RayClusterUnreachableError"
