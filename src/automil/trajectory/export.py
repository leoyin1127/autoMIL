"""Trajectory export bundle producer (TRJ-05 / D-94)."""
from __future__ import annotations

import hashlib
import json
import logging
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from automil.trajectory.redactor import redact_event, _PATTERNS
from automil.trajectory.schema import validate_event, TrajectorySchemaError

logger = logging.getLogger(__name__)


def export_bundle(
    node_id: str,
    archive_dir: Path,
    out_path: Optional[Path] = None,
) -> Path:
    """Produce a redacted, schema-validated trajectory bundle (D-94).

    Bundle is a .tar.gz containing:
    - trajectory.jsonl (re-redacted)
    - trajectory.*.jsonl siblings (re-redacted)
    - manifest.json (schema version, line counts, redaction rule hash)

    Returns the path to the created .tar.gz file.
    Raises FileNotFoundError if the node archive or trajectory files do not exist.
    """
    node_archive = archive_dir / node_id
    if not node_archive.exists():
        raise FileNotFoundError(
            f"No archive found for node {node_id!r} at {node_archive}"
        )

    # Collect trajectory files (primary + rotated siblings)
    traj_files = sorted(node_archive.glob("trajectory*.jsonl"))
    if not traj_files:
        raise FileNotFoundError(
            f"No trajectory.jsonl files found for node {node_id!r}"
        )

    out_path = out_path or (Path.cwd() / f"{node_id}.trajectory.tar.gz")

    # Build redaction-rule hash for manifest (deterministic across runs)
    rule_hash = hashlib.sha256(
        "|".join(p.pattern for p, _ in _PATTERNS).encode()
    ).hexdigest()[:16]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest: dict = {
            "node_id": node_id,
            "schema_version": "trajectory-v1",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "redaction_rule_hash": rule_hash,
            "files": [],
        }

        for traj_file in traj_files:
            lines = traj_file.read_text(encoding="utf-8").splitlines()
            redacted_lines: list[str] = []
            line_count = 0
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    redacted = redact_event(event)
                    # Validate all lines except the first (metadata header)
                    if i > 0:
                        try:
                            validate_event(redacted)
                        except TrajectorySchemaError as exc:
                            logger.warning("Schema validation failed on export: %s", exc)
                    redacted_lines.append(json.dumps(redacted, ensure_ascii=False))
                    line_count += 1
                except json.JSONDecodeError as exc:
                    logger.warning("Skipping malformed line %d in %s: %s", i, traj_file.name, exc)

            out_file = tmp / traj_file.name
            out_file.write_text("\n".join(redacted_lines) + "\n", encoding="utf-8")
            manifest["files"].append({
                "name": traj_file.name,
                "line_count": line_count,
            })

        (tmp / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        # Build tarball
        with tarfile.open(str(out_path), "w:gz") as tar:
            for f in tmp.iterdir():
                tar.add(str(f), arcname=f.name)

    logger.info("Exported trajectory bundle for %s to %s", node_id, out_path)
    return out_path
