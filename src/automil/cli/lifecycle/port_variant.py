"""port-variant command: convert a node's overlay to a registered variant module (Plan 01-11)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("port-variant")
@click.argument("node_id")
@click.option(
    "--name",
    default=None,
    help="Override auto-name (default: <parent>_v<node_short>).",
)
@click.option(
    "--kind",
    default=None,
    type=click.Choice(["model", "loss", "policy"]),
    help="Override auto-detected kind (model | loss | policy).",
)
def port_variant(node_id: str, name: str | None, kind: str | None):
    """Convert a node's overlay to a registered variant module + manifest.

    Workflow: after an experiment produced a good composite, run
    `automil port-variant <node_id>` to convert its dirty diff into a
    committed variant module under automil/variants/<kind_dir>/<name>.py
    plus a sibling <name>.json manifest. Auto-names as <parent>_v<short>
    unless --name is passed; auto-detects kind from the overlay paths
    unless --kind is passed.

    Idempotent: re-porting a node with matching node_id is a no-op.
    Mismatched-node-id same-name is a hard-fail (don't silently overwrite).

    Plan 01-11 will implement this; Phase 1 stub raises ClickException.
    """
    raise click.ClickException(
        f"`automil port-variant {node_id}` not yet implemented "
        f"(Plan 01-11 will ship it)."
    )
