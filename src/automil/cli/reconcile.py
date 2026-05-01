"""reconcile command: sync experiment graph with orchestrator state.

Phase 0 ships UNFLAGGED reconcile (no ``--recompute-best``). Plan 07 (CLI-07)
adds the flag.
"""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir


@main.command()
def reconcile():
    """Sync experiment graph with orchestrator state."""
    adir = _find_automil_dir()
    orch = adir / "orchestrator"
    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(adir / "graph.json"))
    graph.reconcile(
        queue_dir=str(orch / "queue"),
        running_dir=str(orch / "running"),
        completed_dir=str(orch / "completed"),
        archive_dir=str(orch / "archive"),
    )
    graph.save()
    click.echo("Graph reconciled with orchestrator state.")
