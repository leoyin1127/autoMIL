"""propose + rank commands: paired by lifecycle (D-01)."""
from __future__ import annotations

import logging

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir

logger = logging.getLogger(__name__)


@main.command()
@click.option("--n", default=6, help="Number of proposals to return")
@click.option("--max-per-branch", default=2, help="Max proposals per branch")
@click.option(
    "--include-held-out",
    is_flag=True,
    default=False,
    help=(
        "Include held-out gate-eval nodes (D-139; logs WARNING; "
        "do NOT use during the agent search loop)."
    ),
)
def rank(n: int, max_per_branch: int, include_held_out: bool):
    """Show top-ranked proposals from the experiment graph."""
    adir = _find_automil_dir()
    graph_path = adir / "graph.json"

    if not graph_path.exists():
        click.echo("No graph.json found. Run some experiments first.")
        return

    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(graph_path))

    # D-139: held-out isolation — filter unless operator explicitly opts in.
    if include_held_out:
        logger.warning(
            "rank --include-held-out: held-out cell composites now visible; "
            "this MUST NOT be used during the agent search loop (D-139)."
        )
    else:
        graph._data["nodes"] = {
            k: v
            for k, v in graph.nodes.items()
            if not (
                isinstance(v, dict)
                and v.get("metadata", {}).get("held_out", False)
            )
        }

    graph.recalculate_scores()
    proposals = graph.rank_proposals(n=n, max_per_branch=max_per_branch)

    if not proposals:
        click.echo("No proposals available. Time to brainstorm!")
        return

    click.echo(f"Top {len(proposals)} proposals:\n")
    for i, node in enumerate(proposals, 1):
        node_id = node["id"]
        parent = node.get("parent_id", "root")
        desc = node.get("description", "")
        score = node.get("potential", 0)
        click.echo(f"  {i}. [{node_id}] (parent: {parent}, score: {score:.4f})")
        click.echo(f"     {desc}")
        click.echo()


@main.command()
@click.option("--parent", required=True, help="Parent node ID")
@click.option("--desc", required=True, help="Proposal description")
@click.option("--techniques", multiple=True, help="Technique tags")
def propose(parent: str, desc: str, techniques: tuple):
    """Add a new experiment proposal to the graph."""
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(adir / "graph.json"))

    # Duplicate guard: refuse exact-description sibling proposals under the
    # same parent that are still pending or running. Prevents waste from
    # accidental double-proposes (the 0063="dup of 0057" case). Exact-match
    # only — fine-grained hyperparameter sweeps with different descriptions
    # are unaffected.
    desc_norm = desc.strip()
    for n in graph.nodes.values():
        if (n.get("parent_id") == parent
                and n.get("type") == "proposed"
                and n.get("status") in ("pending", "running")
                and (n.get("description", "") or "").strip() == desc_norm):
            raise click.ClickException(
                f"Refusing to propose: {n['id']} already exists under "
                f"--parent {parent} with the same description "
                f"'{desc_norm[:60]}'. Use a different description, pick a "
                f"different parent, or wait for {n['id']} to complete."
            )

    node_id = graph.add_proposed(
        parent_id=parent,
        description=desc,
        techniques=list(techniques),
    )
    graph.recalculate_scores()
    graph.save()
    click.echo(f"Added proposal {node_id}: {desc}")
