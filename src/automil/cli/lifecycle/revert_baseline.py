"""revert-baseline command: reset registry-protected paths to base_commit state (Plan 01-10)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("revert-baseline")
def revert_baseline():
    """Reset registry-protected paths to their base_commit state.

    Workflow: when the agent has accumulated edits to shared library files
    that should NOT have been touched (registry.protected violation), run
    `automil revert-baseline` to git-checkout those paths back to clean.
    STASHES uncommitted changes first (Leo's "never blind-checkout" memory)
    — the stash name is printed to stdout so you can recover if needed.

    Idempotent: running on a clean tree is a no-op.

    Plan 01-10 will implement this; Phase 1 stub raises ClickException.
    """
    raise click.ClickException(
        "`automil revert-baseline` not yet implemented "
        "(Plan 01-10 will ship it)."
    )
