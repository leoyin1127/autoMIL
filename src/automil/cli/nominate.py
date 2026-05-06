"""Top-level nominate command (GTE-05 / D-142 / D-145).

Shortcut at `automil nominate <node_id>` — sibling of `automil submit` —
because operators use it more often than `automil gate nominate` would imply.
The gate subgroup (cli/gate.py) remains intact; this is an ADDITIVE top-level
alias per D-145 design decision.

BCK-04 clean: no os.kill / os.killpg / Popen / .pid references.
Framework purity: generic framework code only — D-148 verified.
"""
from __future__ import annotations

import click

from automil.cli import main


@main.command("nominate")
@click.argument("node_id")
@click.option(
    "--agent",
    is_flag=True,
    default=False,
    hidden=True,
    help="Mark as agent-initiated (auto_nominate path; audit log only).",
)
def nominate_cmd(node_id: str, agent: bool) -> None:
    """Nominate a keep-status node as a gate candidate (D-142).

    Mutates status keep -> candidate. Idempotent. Run `automil promote <node_id>`
    afterwards to evaluate against the parent's pre-registered held-out cells.
    """
    from automil.cli._helpers import _find_automil_dir
    from automil.gate import nominate
    from automil.graph import ExperimentGraph

    adir = _find_automil_dir()
    graph_path = adir / "graph.json"
    if not graph_path.exists():
        raise click.ClickException(f"No graph.json at {graph_path}")
    graph = ExperimentGraph(path=str(graph_path))
    try:
        nominate(node_id, graph, agent_initiated=agent)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    graph.save()
    status = graph.nodes[node_id].get("status")
    click.echo(f"Nominated {node_id}: status -> {status}")
