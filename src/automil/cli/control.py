"""control commands: start-loop, stop-loop.

Phase 0 ships ``start-loop`` + ``stop-loop`` only. Cancel/resubmit are Phase 2
(BCK / CLI-03 / CLI-04) and will land in this module then.
"""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir


@main.command("start-loop")
def start_loop():
    """Create .automil_active flag to prevent agent stopping."""
    adir = _find_automil_dir()
    (adir.parent / ".automil_active").touch()
    click.echo("Loop started. Agent will not stop until 'automil stop-loop' is run.")


@main.command("stop-loop")
def stop_loop():
    """Remove .automil_active flag to allow agent stopping."""
    adir = _find_automil_dir()
    flag = adir.parent / ".automil_active"
    if flag.exists():
        flag.unlink()
        click.echo("Loop stopped. Agent can now exit.")
    else:
        click.echo("Loop was not active.")


# Phase 2: cancel, resubmit will be added here.
