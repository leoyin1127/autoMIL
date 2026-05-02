"""refresh-registry command: scan variants/ and regenerate __init__.py manifests (Plan 01-09)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("refresh-registry")
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Hard-fail on any failed-import; default warns and continues.",
)
def refresh_registry(strict: bool):
    """Scan automil/variants/ and regenerate per-kind __init__.py files.

    Workflow: after adding, renaming, or removing a variant module, run
    `automil refresh-registry` to keep the auto-generated __init__.py
    manifests in sync with the directory contents. The command imports
    every variant module (triggering @register decorators), then writes
    deterministic, alphabetic, imports-only __init__.py files atomically.

    Idempotent: regenerating produces byte-identical bodies if nothing on
    disk changed (timestamp comment is on a separate line). Use --strict to
    hard-fail on any failed-import rather than warn-and-continue.

    Plan 01-09 will implement this; Phase 1 stub raises ClickException.
    """
    raise click.ClickException(
        "`automil refresh-registry` not yet implemented "
        "(Plan 01-09 will ship it)."
    )
