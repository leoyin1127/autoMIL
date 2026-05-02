"""verify-repro command: re-run a node's recipe + emit a repro_manifest.yaml (Plan 01-12)."""
from __future__ import annotations

import click

from automil.cli import main


@main.command("verify-repro")
@click.argument("node_id")
@click.option(
    "--tolerance",
    default=None,
    type=float,
    help="Override registry.repro_tolerance (default: 0.005 from config).",
)
def verify_repro(node_id: str, tolerance: float | None):
    """Reproduce a node's experiment via the registry path; write a manifest.

    Workflow: after porting a node's variant via `automil port-variant`,
    run `automil verify-repro <node_id>` to re-execute the experiment via
    the registry path on a clean worktree, compare the new composite
    against the recorded composite, and write
    automil/repro_manifest.yaml with {expected_composite, actual_composite,
    tolerance, status: pass | fail}. Phase 1 acceptance is the synthetic
    mini-consumer round-trip in tests/fixtures/.

    Plan 01-12 will implement this; Phase 1 stub raises ClickException.
    """
    raise click.ClickException(
        f"`automil verify-repro {node_id}` not yet implemented "
        f"(Plan 01-12 will ship it)."
    )
