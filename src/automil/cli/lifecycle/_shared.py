"""Shared helpers across lifecycle commands.

Private to the lifecycle/ package. Three utilities:
  - _atomic_write_text(path, content): tempfile + rename (PATTERNS.md §3)
  - _load_registry_or_die(adir): load registry config with friendly error
  - _get_node_or_die(adir, node_id): look up a node dict with "available:" listing
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

import click

logger = logging.getLogger(__name__)


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomic tempfile + rename write (PATTERNS.md §3).

    Creates intermediate parent directories as needed. No leftover .tmp files
    on success. On failure, the .tmp is cleaned up and the exception re-raised.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_registry_or_die(adir: Path):
    """Load registry config; raise click.ClickException with a fix suggestion if invalid.

    Parameters
    ----------
    adir:
        The ``automil/`` directory (output of ``_find_automil_dir()``).

    Returns
    -------
    The loaded registry config object.
    """
    from automil.registry.config import load_registry_config

    try:
        return load_registry_config(adir)
    except (ValueError, TypeError) as e:
        raise click.ClickException(
            f"Invalid automil/config.yaml: {e}. Fix the config and retry."
        ) from e


def _get_node_or_die(adir: Path, node_id: str) -> dict:
    """Read graph.json and return the node dict; hard-fail with an ``available:``
    listing if the node is missing.

    Operator-friendly error format:
        "Node {node_id!r} not found in graph.json.
         available: [...]. Run `automil status` to inspect."

    Truncates the available list to 10 entries for readability.
    """
    graph_path = adir / "graph.json"
    if not graph_path.exists():
        raise click.ClickException(
            "automil/graph.json not found. Run `automil init` and submit at "
            "least one experiment first."
        )
    try:
        graph = json.loads(graph_path.read_text())
    except json.JSONDecodeError as e:
        raise click.ClickException(
            f"automil/graph.json is malformed: {e}. Inspect or restore from "
            "a recent commit."
        ) from e

    nodes = graph.get("nodes", {})
    if node_id not in nodes:
        available = sorted(nodes.keys())
        sample = available[:10]
        more = f" ... ({len(available) - 10} more)" if len(available) > 10 else ""
        raise click.ClickException(
            f"Node {node_id!r} not found in graph.json. "
            f"available: {sample}{more}. "
            f"Run `automil status` for the full graph state."
        )
    return nodes[node_id]
