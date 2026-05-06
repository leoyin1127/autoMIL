"""Nominate operation — mutate keep -> candidate (D-136, D-142, GTE-05).

Pattern mirrors cells/registry.py: in-place mutation; caller controls
graph.save() — same discipline.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from automil.graph import ExperimentGraph

logger = logging.getLogger(__name__)


def nominate(
    node_id: str,
    graph: "ExperimentGraph",
    agent_initiated: bool = False,
) -> None:
    """Mutate graph node status keep -> candidate (idempotent).

    Raises ValueError if node not found, or status is not 'keep' / 'candidate'.

    Side effects:
        - node["status"] = "candidate"
        - node["history"].append({"event": "nominated", "timestamp": ...,
          "agent_initiated": agent_initiated})

    Caller must call graph.save() to persist (D-142 discipline; matches
    cells/registry.py: write_cell happens at the caller boundary).
    """
    node = graph.nodes.get(node_id)
    if node is None:
        raise ValueError(
            f"Cannot nominate: node {node_id!r} not found in graph"
        )
    current = node.get("status")
    if current == "candidate":
        logger.info("nominate: %s already candidate; no-op (idempotent)", node_id)
        return
    if current != "keep":
        raise ValueError(
            f"Cannot nominate {node_id!r}: status={current!r}; "
            f"only nodes with status='keep' can be nominated "
            f"(D-136 status flow: keep -> candidate -> registered)"
        )

    node["status"] = "candidate"
    node.setdefault("history", []).append({
        "event": "nominated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_initiated": bool(agent_initiated),
    })
    logger.info(
        "nominate: %s status=keep -> candidate (agent_initiated=%s)",
        node_id, agent_initiated,
    )
