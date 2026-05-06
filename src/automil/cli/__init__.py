"""automil CLI - Click main group and command registration.

The package re-exports ``main`` so ``from automil.cli import main`` keeps
working for tests and the pyproject ``[project.scripts]`` entry.
"""
from __future__ import annotations

import click


@click.group()
def main():
    """autoMIL: Autonomous agent-driven MIL model improvement."""
    pass


# Command modules register themselves on `main` at import time.
# Order is alphabetic for readability — Click registration is idempotent on
# repeated import so cycles are not a concern.
from automil.cli import cancel  # noqa: E402,F401
from automil.cli import cell    # noqa: E402,F401  (CAP-06 / D-125)
from automil.cli import check  # noqa: E402,F401
from automil.cli import control  # noqa: E402,F401
from automil.cli import gate    # noqa: E402,F401  (GTE-01..06 / D-145)
from automil.cli import init  # noqa: E402,F401
from automil.cli import lifecycle  # noqa: E402,F401
from automil.cli import orchestrator  # noqa: E402,F401
from automil.cli import propose  # noqa: E402,F401
from automil.cli import reconcile  # noqa: E402,F401
from automil.cli import resubmit  # noqa: E402,F401
from automil.cli import show_skill  # noqa: E402,F401  (MRT-04 / D-93)
from automil.cli import status  # noqa: E402,F401
from automil.cli import submit  # noqa: E402,F401
from automil.cli import trajectory  # noqa: E402,F401  (TRJ-04, TRJ-05 / D-94)
from automil.cli import viz  # noqa: E402,F401

__all__ = ["main"]
