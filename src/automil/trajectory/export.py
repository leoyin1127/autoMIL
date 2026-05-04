"""Trajectory export bundle producer (TRJ-05 / D-94).

Full implementation wired in Plan 03-09 (cli/trajectory.py export subcommand).
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_bundle(node_id: str, archive_dir: Path, out_path: Path | None = None) -> Path:
    """Produce a redacted, schema-validated trajectory bundle.

    Bundle: <node_id>.trajectory.tar.gz containing trajectory.jsonl +
    rotated siblings + manifest.json.
    Full implementation provided in Plan 03-09.
    """
    raise NotImplementedError(
        "export_bundle full implementation in Plan 03-09 (cli/trajectory.py)"
    )
