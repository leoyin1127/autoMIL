#!/usr/bin/env python3
"""sklearn-iris: minimal autoMIL contract demo (DEC-02 / D-203).

Honors the DEC-06 contract: reads automil/config.yaml for data.seed,
accepts CUDA_VISIBLE_DEVICES and AUTOMIL_GPU (no-op on CPU), installs
a SIGTERM handler before compute, and writes result.json conforming to
automil/schemas/result.schema.json. No automil.* imports (consumer-decoupled).
"""
from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path
from typing import Any

import yaml
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

RESULTS_DIR = Path(".")  # write to cwd (= worktree when launched by orchestrator)
_state: dict[str, Any] = {"completed": False, "accuracy": 0.0, "f1": 0.0}


def _write_result(*, status: str, partial: bool) -> None:
    """Write result.json conforming to automil/schemas/result.schema.json."""
    payload = {
        "status": status,
        "composite": float(_state["accuracy"]),
        "metrics": {
            "accuracy": float(_state["accuracy"]),
            "f1": float(_state["f1"]),
        },
        "partial": partial,
    }
    (RESULTS_DIR / "result.json").write_text(json.dumps(payload, indent=2))


def _sigterm_handler(signum: int, frame: object) -> None:
    """SIGTERM clean exit. Idempotent: late SIGTERM after completion writes status=completed."""
    if _state["completed"]:
        _write_result(status="completed", partial=False)
    else:
        _write_result(status="budget_killed", partial=True)
    sys.exit(0)  # NOT sys.exit(130); 0 signals graceful flush to daemon.


def main() -> None:
    """Train LogisticRegression on iris; write result.json."""
    signal.signal(signal.SIGTERM, _sigterm_handler)  # install before any compute

    # Honor CUDA_VISIBLE_DEVICES + AUTOMIL_GPU (no-op on CPU, D-204 items 2-3).
    _ = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    _ = os.environ.get("AUTOMIL_GPU", "")

    config_path = Path("automil/config.yaml")  # D-204 contract item 1
    seed = 42
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text()) or {}
        seed = int((config.get("data") or {}).get("seed", 42))

    X, y = load_iris(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=seed
    )
    clf = LogisticRegression(max_iter=200, random_state=seed).fit(X_train, y_train)
    y_pred = clf.predict(X_test)

    _state["accuracy"] = float(accuracy_score(y_test, y_pred))
    _state["f1"] = float(f1_score(y_test, y_pred, average="macro"))
    _state["completed"] = True

    _write_result(status="completed", partial=False)


if __name__ == "__main__":
    main()
