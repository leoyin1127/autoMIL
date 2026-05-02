"""promote-variant command: move a candidate to canonical variants/ (Plan 01-11)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("promote-variant")
@click.argument("node_id")
def promote_variant(node_id: str):
    """Move a gate-passing candidate to the canonical variants/<parent>/.

    Workflow: when a candidate variant in automil/variants/_candidates/
    passes the generalization gate (Phase 5 GTE), run
    `automil promote-variant <node_id>` to move its module + manifest into
    the canonical per-parent directory and stage them for commit. Phase 1
    ships the command + the _candidates/ directory (.gitkeep); the
    gate-passing pipeline lands in Phase 5.

    Plan 01-11 will implement this; Phase 1 stub raises ClickException.
    """
    raise click.ClickException(
        f"`automil promote-variant {node_id}` not yet implemented "
        f"(Plan 01-11 will ship it)."
    )
