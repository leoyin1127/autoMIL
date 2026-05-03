"""cancel command: terminate a running experiment via its backend (CLI-03 / D-66).

Workflow:
  1. Look up node_id in graph.json (hard-fail if unknown).
  2. Hard-fail if node is not in 'running' state.
  3. Read backend name from node.metadata.backend (default 'local' for legacy nodes, D-76).
  4. Read running/<node_id>.json to obtain opaque_id + submitted_at (W-03 fix: NOT
     from graph metadata — opaque_id is only known after the daemon launches the job).
  5. Resolve BackendClass via BACKENDS[backend_name]; instantiate.
  6. Reconstruct JobHandle; call backend.cancel(handle) — fire-and-forget.
  7. Poll up to --timeout seconds for JobState.CANCELLED.
  8. Atomically update graph node: status='cancelled', cancelled_at, cancel_reason='cli'.
  9. Move running/<id>.json to archive/<id>/.
 10. Echo "Cancelled {node_id}."
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir, _find_git_root
from automil.cli.lifecycle._shared import _get_node_or_die

logger = logging.getLogger(__name__)


@main.command("cancel")
@click.argument("node_id")
@click.option(
    "--timeout",
    default=30,
    type=int,
    show_default=True,
    help="Seconds to wait for the job to reach CANCELLED state before failing.",
)
def cancel(node_id: str, timeout: int) -> None:
    """Cancel a running experiment by node_id.

    Dispatches through the registered backend (BACKENDS[node.metadata.backend]).
    Reads the job's opaque_id from running/<node_id>.json (written by the daemon
    at launch time — not from graph metadata, which has no PID until launch).

    Polls up to --timeout seconds for the CANCELLED state transition, then
    updates graph.json atomically (status=cancelled, cancelled_at, cancel_reason=cli)
    and archives the running spec file.

    Hard-fails if:
      - node_id is not in graph.json.
      - node is not in 'running' state.
      - running/<node_id>.json does not exist or is missing 'opaque_id'.
      - backend name is not in the BACKENDS registry.
      - the cancel does not complete within --timeout seconds.
    """
    # Lazy imports inside function body to prevent circular imports at CLI load
    # (PATTERNS.md §8 / D-69).
    from automil.backends import BACKENDS, JobHandle, JobState  # noqa: PLC0415
    from automil.backends.local import LocalBackend  # noqa: F401,PLC0415

    adir = _find_automil_dir()

    # Step 1: look up node — hard-fail if unknown.
    node = _get_node_or_die(adir, node_id)

    # Step 2: hard-fail if node is not running.
    state = node.get("status", "")
    if state != "running":
        raise click.ClickException(
            f"Refusing to cancel: node {node_id!r} is in state {state!r}, not 'running'. "
            f"Only running experiments can be cancelled. "
            f"Use `automil status` to verify the current state."
        )

    # Step 3: resolve backend name — D-76 default fallback for legacy nodes.
    backend_name: str = node.get("metadata", {}).get("backend", "local")

    # Step 4 (W-03 fix): read opaque_id + submitted_at from running/<node_id>.json.
    orch_dir = adir / "orchestrator"
    running_path = orch_dir / "running" / f"{node_id}.json"
    if not running_path.exists():
        raise click.ClickException(
            f"Refusing to cancel: no running spec at {running_path}. "
            f"Node may have already finished — try `automil status`."
        )

    try:
        running_spec: dict = json.loads(running_path.read_text())
    except json.JSONDecodeError as exc:
        raise click.ClickException(
            f"Running spec at {running_path} is malformed JSON: {exc}. "
            f"Inspect the file and manage the process manually."
        ) from exc

    opaque_id: str = running_spec.get("opaque_id", "")
    if not opaque_id:
        raise click.ClickException(
            f"Running spec at {running_path} is missing 'opaque_id' — corrupted state. "
            f"Manage the process manually."
        )

    submitted_at: float = running_spec.get("submitted_at", 0.0)
    if isinstance(submitted_at, str):
        # ISO-8601 string → epoch float (some specs write ISO-8601).
        try:
            submitted_at = datetime.fromisoformat(submitted_at).replace(
                tzinfo=timezone.utc
            ).timestamp()
        except (ValueError, TypeError):
            submitted_at = 0.0

    # Step 5: resolve backend class.
    BackendClass = BACKENDS.get(backend_name)
    if BackendClass is None:
        raise click.ClickException(
            f"Unknown backend {backend_name!r}; available: {sorted(BACKENDS.keys())}. "
            f"Check automil/config.yaml or import the backend module first."
        )

    # Step 6: instantiate backend + reconstruct JobHandle.
    try:
        git_root = _find_git_root()
    except click.ClickException:
        git_root = adir.parent

    backend = BackendClass(project_root=git_root, automil_dir=adir)
    handle = JobHandle(
        node_id=node_id,
        backend=backend_name,
        opaque_id=opaque_id,
        submitted_at=submitted_at,
    )

    # Step 7: fire-and-forget cancel; poll for CANCELLED.
    backend.cancel(handle)
    logger.debug("cancel sent for %s via %s; polling for CANCELLED...", node_id, backend_name)

    deadline = time.monotonic() + timeout
    final_state: JobState | None = None
    while time.monotonic() < deadline:
        try:
            final_state = backend.poll(handle)
        except Exception as exc:  # noqa: BLE001
            logger.debug("poll error during cancel wait: %s", exc)
            final_state = None
        if final_state == JobState.CANCELLED:
            break
        time.sleep(1.0)

    if final_state != JobState.CANCELLED:
        current = final_state.value if final_state is not None else "unknown"
        raise click.ClickException(
            f"Cancel sent but state did not transition to 'cancelled' within "
            f"{timeout}s (current state: {current!r}). "
            f"Inspect the process manually and re-run `automil cancel {node_id}` "
            f"or use `automil status`."
        )

    # Step 8: atomically update graph node.
    graph_path = adir / "graph.json"
    try:
        graph_data: dict = json.loads(graph_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise click.ClickException(
            f"Could not read graph.json for update: {exc}."
        ) from exc

    nodes = graph_data.get("nodes", {})
    if node_id in nodes:
        target = nodes[node_id]
        target["status"] = "cancelled"
        target.setdefault("metadata", {})["cancelled_at"] = datetime.now().isoformat()
        target["metadata"]["cancel_reason"] = "cli"
    else:
        logger.warning("cancel: node %s disappeared from graph.json after state check", node_id)

    import os
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(graph_path.parent), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            json.dump(graph_data, fh, indent=2)
            fh.write("\n")
        os.replace(tmp_path, str(graph_path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Step 9: move running/<id>.json to archive/<id>/.
    archive_node_dir = orch_dir / "archive" / node_id
    archive_node_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_node_dir / f"{node_id}_running_spec.json"
    try:
        running_path.rename(dest)
    except OSError as exc:
        logger.warning(
            "cancel: could not move running spec %s → %s: %s",
            running_path, dest, exc,
        )

    # Step 10: confirm.
    click.echo(f"Cancelled {node_id}.")
