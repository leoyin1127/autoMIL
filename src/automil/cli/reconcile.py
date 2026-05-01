"""reconcile command: sync experiment graph with orchestrator state.

Plan 01 (CLN-06) lifted the unflagged body verbatim from the original
``cli.py:510-524``. Plan 07 (CLI-07) adds ``--recompute-best`` (with
``--dry-run`` sibling) per locked decisions D-10..D-15. Existing
unflagged behaviour is byte-identical (D-14).
"""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir


@main.command()
@click.option(
    "--recompute-best",
    is_flag=True,
    default=False,
    help="Rebuild meta.best_node_id from executed/keep nodes (CLI-07).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="With --recompute-best: print summary, do not write graph.json.",
)
def reconcile(recompute_best: bool, dry_run: bool):
    """Sync experiment graph with orchestrator state.

    With ``--recompute-best``: walks ``executed/keep`` nodes, picks the
    max-composite node (lex tie-break on ``node_id``), updates
    ``meta.best_node_id`` and ``meta.best_composite``, and prints a
    one-line summary. ``--dry-run`` prints the same summary without
    writing.
    """
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph

    if recompute_best:
        # CLI-07 path: rebuild meta.best_node_id from executed/keep nodes.
        graph_path = adir / "graph.json"
        graph = ExperimentGraph.load(graph_path)
        old_id, old_c, new_id, new_c = graph.recompute_best()

        old_id_str = old_id if old_id is not None else "None"
        new_id_str = new_id if new_id is not None else "None"
        if old_id == new_id:
            # D-13 verbatim: unchanged-best line.
            click.echo(
                f"best_node_id unchanged: {new_id_str} (composite {new_c:.6f})"
            )
        else:
            # D-13 verbatim: changed-best line with literal Unicode → (U+2192).
            # ASCII fallback is forbidden — silently weakening the locked
            # decision is not allowed. stdout encoding is UTF-8 on Linux
            # (project is Linux-only per PROJECT.md).
            click.echo(
                f"best_node_id: {old_id_str} (composite {old_c:.6f}) "
                f"→ {new_id_str} (composite {new_c:.6f})"
            )

        if not dry_run:
            graph.save()
        return

    # Default path (D-14): orchestrator-state sync. Body byte-identical to
    # Plan 01's lift from the original cli.py:510-524.
    orch = adir / "orchestrator"
    graph = ExperimentGraph(path=str(adir / "graph.json"))
    graph.reconcile(
        queue_dir=str(orch / "queue"),
        running_dir=str(orch / "running"),
        completed_dir=str(orch / "completed"),
        archive_dir=str(orch / "archive"),
    )
    graph.save()
    click.echo("Graph reconciled with orchestrator state.")
