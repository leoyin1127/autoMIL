"""Runtime helpers for training scripts using autoMIL.

Training scripts opt-in to cap-driven SIGTERM flush by calling
``register_sigterm_flush()`` at the top of their ``main()`` function,
before any DataLoader or multiprocessing setup.

D-121 / D-122: the orchestrator does NOT inject signal handlers automatically.
Opt-in is explicit to avoid invisible behavioural changes in user code.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

_SIGTERM_REGISTERED: bool = False


def get_fold_count() -> int:
    """Return the expected fold count for the current experiment.

    Read from ``AUTOMIL_FOLD_COUNT`` env var (set by the orchestrator from
    ``automil/config.yaml: training.fold_count``).  Falls back to 5 if unset
    (matches Leo's CCRCC / CLWD paper-campaign convention and is the framework
    default per D-120).
    """
    return int(os.environ.get("AUTOMIL_FOLD_COUNT", "5"))


def register_sigterm_flush(
    *,
    fold_count_env: str = "AUTOMIL_FOLD_COUNT",
) -> None:
    """Install a SIGTERM handler that flushes a partial ``result.json``.

    When the autoMIL orchestrator fires a budget-kill (CAP-02 / D-115), it
    sends SIGTERM to the training process group.  This handler:

    1. Collects whatever ``fold_*_result.json`` files exist in ``Path.cwd()``.
    2. Calls ``aggregate_folds()`` to compute a partial composite.
    3. Writes ``result.json`` to ``Path.cwd()`` with ``status: partial``
       (or ``completed`` if all folds are present).
    4. Exits with ``sys.exit(0)`` — NOT 130 — so the daemon's
       ``_handle_completion`` treats this as a *graceful flush* rather than a
       crash.  ``reconcile_budget_kill`` then upgrades the node to
       ``status: executed`` with ``metadata.budget_killed: True``.

    **Threading constraint (Pitfall 1):** ``signal.signal()`` can only be
    called from the main thread of the main interpreter.  Call this function
    at the very top of ``main()`` — before any ``DataLoader``,
    ``multiprocessing.Pool``, or ``threading.Thread`` construction.

    **Idempotency:** calling this function more than once in the same process
    is a no-op (guarded by the module-level ``_SIGTERM_REGISTERED`` flag).
    """
    global _SIGTERM_REGISTERED
    if _SIGTERM_REGISTERED:
        return

    def _handler(signum: int, frame: object) -> None:  # noqa: ANN001
        # Lazy import: aggregate_folds lives in cells.reconcile which lands
        # in Wave 2 (Plan 04-04). The lazy import means this module compiles
        # without cells/ existing; the handler only needs it resolvable at
        # CALL TIME (which is post-Wave-2 in any real run).
        try:
            from automil.cells.reconcile import aggregate_folds
        except ImportError:
            # cells package not yet deployed — write a minimal result.json
            # so the daemon does not see a crash
            import json
            (Path.cwd() / "result.json").write_text(
                json.dumps(
                    {
                        "status": "partial",
                        "composite": 0.0,
                        "partial_folds": 0,
                        "expected_folds": get_fold_count(),
                        "metrics": {},
                        "elapsed_seconds": 0,
                        "peak_vram_mb": 0,
                    },
                    indent=2,
                )
            )
            sys.exit(0)

        n = get_fold_count()
        payload = aggregate_folds(Path.cwd(), n)

        import json
        (Path.cwd() / "result.json").write_text(json.dumps(payload, indent=2))
        sys.exit(0)  # NOT sys.exit(130) — clean exit signals graceful flush

    signal.signal(signal.SIGTERM, _handler)
    _SIGTERM_REGISTERED = True
