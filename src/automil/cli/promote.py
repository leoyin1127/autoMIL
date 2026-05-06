"""Top-level promote command — runs Stage B held-out gate (GTE-04 / D-141 / D-145).

Distinct from `automil promote-variant` (Phase 1, lifecycle/promote_variant.py)
which moves a registered variant into the canonical variants/ directory.
`automil promote` (this command) runs the gate decision; `promote-variant`
is the post-gate move. They form a pipeline: nominate -> promote -> promote-variant.

BCK-04 clean: no os.kill / os.killpg / Popen / .pid references.
Framework purity: generic framework code only — D-148 verified.
"""
from __future__ import annotations

import click

from automil.cli import main


@main.command("promote")
@click.argument("candidate_id")
@click.option(
    "--calibrate",
    is_flag=True,
    default=False,
    help="D-151 dry-run: evaluate but do not change status. Used by calibration pilot.",
)
@click.option(
    "--backend",
    default="local",
    help="Backend name (currently 'local' is the only supported value).",
)
def promote_cmd(candidate_id: str, calibrate: bool, backend: str) -> None:
    """Run Stage B gate on a nominated candidate (status='candidate' required).

    Spawns held-out evaluations via Backend.submit, applies paired Wilcoxon +
    bootstrap CI + Bonferroni correction, mutates status to 'registered' (pass),
    'keep' (fail), or stays 'candidate' (inconclusive when too many cells skipped
    due to per-cell cap exhaustion — D-150).
    """
    from automil.cli._helpers import _find_automil_dir
    from automil.gate import promote
    from automil.graph import ExperimentGraph

    adir = _find_automil_dir()
    graph_path = adir / "graph.json"
    if not graph_path.exists():
        raise click.ClickException(f"No graph.json at {graph_path}")
    graph = ExperimentGraph(path=str(graph_path))

    backend_instance = _resolve_backend(backend, adir)

    manifests_dir = adir / "gate"
    archive_dir = adir / "archive"

    try:
        result = promote(
            candidate_id,
            backend_instance,
            graph,
            manifests_dir,
            archive_dir,
            calibrate=calibrate,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise click.ClickException(str(exc))

    node = graph.nodes.get(candidate_id, {})
    status = node.get("status", "?")
    if calibrate:
        click.echo(
            f"[calibrate] {candidate_id}: would-{'PASS' if result else 'FAIL'} "
            f"(status unchanged: {status})"
        )
    else:
        click.echo(f"{candidate_id}: status -> {status}")


def _resolve_backend(name: str, adir):
    """Construct a Backend instance from CLI args. Single-source pattern.

    Mirrors the LocalBackend constructor used across other CLI commands:
    LocalBackend(automil_dir=adir) — automil_dir is the automil/ overlay
    directory found by _find_automil_dir(). project_root=None triggers
    auto-detection by ExperimentOrchestrator (same as daemon default, D-61).
    """
    if name != "local":
        raise click.ClickException(
            f"Unsupported backend {name!r}; only 'local' is implemented in v1"
        )
    from automil.backends.local import LocalBackend
    return LocalBackend(automil_dir=adir)
