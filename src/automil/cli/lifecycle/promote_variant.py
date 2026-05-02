"""promote-variant command: move candidate to canonical variants/ + stage (CLI-06 / D-45)."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir, _find_git_root

logger = logging.getLogger(__name__)


@main.command("promote-variant")
@click.argument("node_id")
def promote_variant(node_id: str):
    """Move a gate-passing candidate to the canonical variants/<parent>/.

    Workflow: when a candidate variant in automil/variants/_candidates/
    passes the generalization gate (Phase 5 GTE), run
    `automil promote-variant <node_id>` to move its module + manifest
    into the canonical per-parent directory and stage them for commit.
    Phase 1 ships the command + the _candidates/ directory; the gate-
    passing pipeline lands in Phase 5.

    The command:
      1. Finds the candidate variant by manifest.source_node == node_id.
      2. `git mv` the .py + .json to the canonical kind directory.
      3. Regenerates affected __init__.py files.
      4. STAGES the move (`git add`) but does NOT commit (D-45).
    """
    from automil.registry.manifest import Manifest
    from automil.registry.scanner import regenerate_init_py

    adir = _find_automil_dir()
    git_root = _find_git_root()
    candidates_dir = adir / "variants" / "_candidates"

    if not candidates_dir.exists():
        raise click.ClickException(
            f"automil/variants/_candidates/ not found. Run `automil init` first."
        )

    # 1. Find the candidate manifest with matching source_node.
    candidate_manifest_path: Path | None = None
    for json_path in candidates_dir.glob("*.json"):
        try:
            m = Manifest.read(json_path)
        except Exception:
            continue
        if m.source_node == node_id:
            candidate_manifest_path = json_path
            break

    if candidate_manifest_path is None:
        available = sorted(p.stem for p in candidates_dir.glob("*.json"))
        raise click.ClickException(
            f"No candidate variant found for node_id={node_id!r} in "
            f"{candidates_dir}. available: {available}. "
            f"Run `automil port-variant {node_id}` first to create a candidate, "
            f"or check the node_id."
        )

    candidate_module_path = candidate_manifest_path.with_suffix(".py")
    if not candidate_module_path.exists():
        raise click.ClickException(
            f"Candidate manifest {candidate_manifest_path} exists but the "
            f"sibling .py module is missing. Inspect _candidates/ and clean up."
        )

    manifest = Manifest.read(candidate_manifest_path)
    spec = manifest.spec

    # 2. Compute canonical destination dir.
    if spec.kind == "model":
        if not spec.parent:
            raise click.ClickException(
                f"Cannot promote model variant {spec.name!r}: manifest has no "
                f"parent. Re-port via `automil port-variant {node_id} "
                f"--kind model --parent <name>`."
            )
        dest_dir = adir / "variants" / spec.parent
    elif spec.kind == "loss":
        dest_dir = adir / "variants" / "_losses"
    else:
        dest_dir = adir / "variants" / "_policies"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_module = dest_dir / candidate_module_path.name
    dest_manifest = dest_dir / candidate_manifest_path.name

    # Idempotence: if already at destination with matching node_id, no-op.
    if dest_module.exists() and dest_manifest.exists():
        try:
            existing = Manifest.read(dest_manifest)
        except Exception:
            existing = None
        if existing is not None and existing.source_node == node_id:
            click.echo(f"promote-variant: already promoted; no-op.")
            return

    # 3. git mv .py and .json.
    for src, dst in [(candidate_module_path, dest_module),
                     (candidate_manifest_path, dest_manifest)]:
        result = subprocess.run(
            ["git", "mv", str(src), str(dst)],
            cwd=git_root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise click.ClickException(
                f"`git mv {src} {dst}` failed: {result.stderr.strip()}. "
                f"Inspect with `git status` and resolve manually."
            )

    # 4. Regenerate __init__.py for both source and destination dirs.
    regenerate_init_py(candidates_dir)
    regenerate_init_py(dest_dir)
    # Stage the regenerated init files too.
    for init_path in (candidates_dir / "__init__.py", dest_dir / "__init__.py"):
        if init_path.exists():
            subprocess.run(
                ["git", "add", str(init_path)],
                cwd=git_root, capture_output=True, check=True,
            )

    click.echo(f"Promoted {node_id} -> {dest_module.relative_to(git_root)}")
    click.echo(f"Manifest: {dest_manifest.relative_to(git_root)}")
    click.echo(
        "Files staged. Commit with your own message (e.g., "
        "`git commit -m 'promote: {name} after gate'`).".format(name=spec.name)
    )
