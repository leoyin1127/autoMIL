"""refresh-registry command: scan variants/ and regenerate __init__.py manifests (CLI-08 / D-29)."""
from __future__ import annotations

import logging

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir

logger = logging.getLogger(__name__)


@main.command("refresh-registry")
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Hard-fail on any failed import; default warns and continues.",
)
def refresh_registry(strict: bool):
    """Scan automil/variants/ and regenerate per-kind __init__.py files.

    Workflow: after adding, renaming, or removing a variant module, run
    `automil refresh-registry` to keep the auto-generated __init__.py
    manifests in sync with the directory contents. Imports each variant
    module (triggering @register decorators) and writes deterministic,
    alphabetic, imports-only __init__.py files atomically.

    Idempotent: byte-identical bodies on no-change (timestamp on separate
    line). Reports imported / failed / skipped counts.
    """
    from automil.registry._state import _clear_registry
    from automil.registry.scanner import regenerate_init_py, scan_variants

    adir = _find_automil_dir()
    variants_root = adir / "variants"
    if not variants_root.exists():
        raise click.ClickException(
            f"automil/variants/ not found at {variants_root}. "
            f"Run `automil init` first."
        )

    # Clear the in-process registry so the scan starts from a known empty state.
    _clear_registry()
    result = scan_variants(variants_root)

    # Regenerate __init__.py for every kind subdirectory present on disk.
    kind_dirs = sorted(
        d for d in variants_root.iterdir()
        if d.is_dir() and d.name != "__pycache__"
    )
    for kind_dir in kind_dirs:
        regenerate_init_py(kind_dir)

    # Report.
    n_imp = len(result.imported)
    n_fail = len(result.failed)
    n_skip = len(result.skipped)
    click.echo(f"refresh-registry: imported={n_imp} failed={n_fail} skipped={n_skip}")
    if result.failed:
        click.echo("Failed imports:")
        for path, exc_str in result.failed:
            click.echo(f"  {path}: {exc_str}")

    if strict and result.failed:
        raise click.ClickException(
            f"refresh-registry --strict: {n_fail} module(s) failed to import. "
            f"Inspect the messages above and fix the offending file(s)."
        )
