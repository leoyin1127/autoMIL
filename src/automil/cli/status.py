"""status command: experiment status summary."""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir


@main.command()
def status():
    """Show experiment status summary."""
    adir = _find_automil_dir()

    queue = list((adir / "orchestrator" / "queue").glob("*.json"))
    completed = list((adir / "orchestrator" / "completed").glob("*.json"))

    graph_path = adir / "graph.json"
    if graph_path.exists():
        from automil.graph import ExperimentGraph
        graph = ExperimentGraph(path=str(graph_path))
        executed = sum(1 for n in graph.nodes.values() if n.get("type") == "executed")
        proposed = sum(1 for n in graph.nodes.values() if n.get("type") == "proposed")
        best = graph.meta.get("best_composite", 0)
        click.echo(f"Executed: {executed}  Proposed: {proposed}  Best: {best:.4f}")
    else:
        click.echo("No graph.json found.")

    click.echo(f"Queue: {len(queue)}  Completed (pending read): {len(completed)}")
