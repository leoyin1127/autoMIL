"""Budget-killed reconciliation and fold aggregation (CAP-03, CAP-04 / D-119, D-123).

aggregate_folds() — pure function that walks archive/<node>/fold_*_result.json
and returns a result.json payload. Called by:
  - automil.runtime_helpers._handler (SIGTERM flush, D-121)
  - reconcile_budget_kill() (post-cancel reconciliation, D-123)

reconcile_budget_kill() — called by the daemon when a node transitions from
RUNNING → CANCELLED with metadata.cancel_reason == "cap" (D-123).
Implemented in Plan 04-07 (Wave 3). Stub here for Wave 1 importability.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def aggregate_folds(node_archive: Path, expected_fold_count: int) -> dict:
    """Walk fold_*_result.json files in node_archive, return result.json payload.

    Pure function — no I/O side effects beyond reading existing files.

    Args:
        node_archive: Directory containing fold_*_result.json files.
                      For SIGTERM handler: Path.cwd() (D-121).
                      For post-cancel reconcile: archive/<node_id>/ (D-123).
        expected_fold_count: Total fold count (from AUTOMIL_FOLD_COUNT env, D-120).

    Returns:
        dict matching result.json schema:
        {
            "status":           "completed" | "partial" | "crashed",
            "metrics":          {<key>: <mean across completed folds>},
            "composite":        <float — mean of per-fold composite>,
            "partial_folds":    <int — number of completed fold files found>,
            "expected_folds":   <int — expected_fold_count>,
            "elapsed_seconds":  <float — sum across completed folds>,
            "peak_vram_mb":     <float — max across completed folds>,
            "metadata":         {"budget_killed": False},  # caller sets True for cap kills
        }

    Spec (D-119):
        - All K folds present → status: "completed", partial_folds == expected_fold_count
        - 1 ≤ folds < K → status: "partial", partial_folds: <n>
        - 0 folds → status: "crashed", composite: 0.0
    """
    fold_files = sorted(node_archive.glob("fold_*_result.json"))
    completed: list[dict] = []
    for fold_file in fold_files:
        try:
            data = json.loads(fold_file.read_text())
            completed.append(data)
        except Exception as exc:
            logger.warning("aggregate_folds: skipping malformed fold file %s: %s", fold_file, exc)

    n = len(completed)

    if n == 0:
        return {
            "status": "crashed",
            "metrics": {},
            "composite": 0.0,
            "partial_folds": 0,
            "expected_folds": expected_fold_count,
            "elapsed_seconds": 0.0,
            "peak_vram_mb": 0.0,
            "metadata": {"budget_killed": False},
        }

    # Aggregate metrics: mean per-key across completed folds
    all_metric_keys: set[str] = set()
    for fold in completed:
        all_metric_keys.update(fold.get("metrics", {}).keys())

    metrics: dict[str, float] = {}
    for key in all_metric_keys:
        values = [fold["metrics"][key] for fold in completed if key in fold.get("metrics", {})]
        metrics[key] = sum(values) / len(values) if values else 0.0

    composite = sum(f.get("composite", 0.0) for f in completed) / n
    elapsed_seconds = sum(f.get("elapsed_seconds", 0.0) for f in completed)
    peak_vram_mb = max((f.get("peak_vram_mb", 0.0) for f in completed), default=0.0)
    status = "completed" if n == expected_fold_count else "partial"

    return {
        "status": status,
        "metrics": metrics,
        "composite": composite,
        "partial_folds": n,
        "expected_folds": expected_fold_count,
        "elapsed_seconds": elapsed_seconds,
        "peak_vram_mb": peak_vram_mb,
        "metadata": {"budget_killed": False},
    }
