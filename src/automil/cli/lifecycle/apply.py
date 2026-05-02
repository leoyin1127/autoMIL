"""apply command: copy a node's variant selection into the active config (Plan 01-09)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("apply")
@click.argument("node_id")
def apply(node_id: str):
    """Apply a node's variant selection to automil/config.yaml.

    Workflow: after running an experiment that produced a good composite,
    use `automil apply <node_id>` to set that node's variant choices
    (model.variant, loss.variant, policy.variant) as the active config for
    the next submit. Edits config.yaml only — never modifies the codebase
    (registry-first invariant: variant code is committed).

    Idempotent: running on the same node twice produces the same config.

    Plan 01-09 will implement this; Phase 1 stub raises ClickException.
    """
    raise click.ClickException(
        f"`automil apply {node_id}` not yet implemented "
        f"(Plan 01-09 will ship it)."
    )
