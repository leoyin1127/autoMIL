"""submit command: snapshot changed files and queue an experiment."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import click
import yaml

from automil.cli import main
from automil.cli._helpers import _find_automil_dir, _find_git_root, _matches_scope


@main.command()
@click.option("--node", required=True, help="Node ID (e.g., node_0042)")
@click.option("--desc", required=True, help="Experiment description")
@click.option("--files", multiple=True, help="Files to snapshot (auto-detect if omitted)")
@click.option("--priority", default=1, help="Priority (lower = higher)")
@click.option("--vram", default=0.5, help="Estimated VRAM in GB")
@click.option("--timeout", default=150, help="Timeout in minutes")
@click.option("--parent", default=None, help="Parent node ID")
@click.option("--techniques", multiple=True, help="Technique tags")
def submit(node: str, desc: str, files: tuple, priority: int, vram: float,
           timeout: int, parent: str | None, techniques: tuple):
    """Snapshot changed files and queue an experiment."""
    import hashlib

    git_root = _find_git_root()
    adir = _find_automil_dir()

    # Guard against overwriting an already-executed node. Submitting against
    # an id that already has recorded results would cause the orchestrator to
    # re-run it and clobber its archive/result.json — destroying prior data
    # and corrupting graph state. The only valid targets for submit are:
    #   (a) an unused id (new node), or
    #   (b) an existing proposal that has not yet been executed.
    graph_path_preflight = adir / "graph.json"
    graph_json: dict = {"nodes": {}}
    if graph_path_preflight.exists():
        try:
            graph_json = json.loads(graph_path_preflight.read_text())
        except (json.JSONDecodeError, OSError):
            graph_json = {"nodes": {}}
        existing = graph_json.get("nodes", {}).get(node)
        if existing is not None:
            ntype = existing.get("type")
            nstatus = existing.get("status")
            if ntype == "executed" or nstatus in {
                "keep", "discard", "crash", "completed", "running",
            }:
                raise click.ClickException(
                    f"Refusing to submit: {node} is already {ntype}/{nstatus}. "
                    f"Submitting would overwrite its archive and destroy prior "
                    f"results. Use 'automil propose' to create a new proposal, "
                    f"then submit against that new node id."
                )
    # Also refuse if a spec for this node is already in queue/ or running/.
    for subdir in ("queue", "running"):
        conflict = adir / "orchestrator" / subdir / f"{node}.json"
        if conflict.exists():
            raise click.ClickException(
                f"Refusing to submit: {node} is already present in "
                f"orchestrator/{subdir}/. Wait for it to finish or remove "
                f"the stale spec file before resubmitting."
            )

    # Guard against submitting a child before its parent has completed.
    # If the parent is still a pending/running proposal, the Pareto-dominance
    # keep/discard computed at reconcile time has no basis (parent.composite
    # is 0). This was the root cause of orphan subtrees like 0051-0055→0048
    # where the child was submitted before 0048 had ever run. Failed parents
    # (crash/oom/timeout) are allowed but warned: the child's comparison will
    # be against composite=0, which the agent should know.
    if parent:
        parent_node = graph_json.get("nodes", {}).get(parent)
        if parent_node is None:
            raise click.ClickException(
                f"Refusing to submit: --parent {parent} does not exist in "
                f"graph.json. Either propose the parent first or omit --parent "
                f"for a root-level submission."
            )
        p_type = parent_node.get("type")
        p_status = parent_node.get("status")
        if p_type == "proposed":
            raise click.ClickException(
                f"Refusing to submit: --parent {parent} has type=proposed "
                f"(status={p_status}) and has not been executed yet. "
                f"Submitting a child now means the keep/discard Pareto check "
                f"will compare against composite=0. Wait for {parent} to "
                f"finish, or pick a different --parent."
            )
        if p_type == "executed" and p_status == "running":
            raise click.ClickException(
                f"Refusing to submit: --parent {parent} is still running. "
                f"Wait for it to finish before submitting a child."
            )
        if p_type == "executed" and p_status in ("crash", "oom", "timeout"):
            click.echo(
                f"Warning: --parent {parent} has status={p_status}; the "
                f"child's keep/discard will compare against composite=0 "
                f"for the parent."
            )

    # Compute automil dir prefix relative to git root for exclusion filtering
    try:
        automil_rel = adir.resolve().relative_to(git_root.resolve()).as_posix() + "/"
    except ValueError:
        automil_rel = "automil/"

    # Determine files to snapshot
    if files:
        file_list = list(files)
        # Warn (but allow) if explicit --files includes readonly files
        config_path = adir / "config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            readonly = set(config.get("files", {}).get("readonly", []))
            for f in file_list:
                if _matches_scope(f, readonly):
                    click.echo(f"Warning: {f} is marked readonly in config.yaml (submitting anyway)")
    else:
        # Auto-detect: use files.editable from config as the default scope,
        # intersected with actually changed files. This prevents capturing
        # unrelated changes in a dirty repo.
        config_path = adir / "config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            editable = set(config.get("files", {}).get("editable", []))
        else:
            editable = set()

        # Get all changed files from git (paths relative to git root)
        tracked = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=git_root, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=git_root, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        # Exclude automil and .claude directories from auto-detect
        all_changed = [
            f for f in tracked + untracked
            if f and not f.startswith(automil_rel) and not f.startswith(".claude/")
        ]

        if editable:
            # Only capture files that are both editable AND changed
            file_list = [f for f in all_changed if _matches_scope(f, editable)]
            skipped = [f for f in all_changed if not _matches_scope(f, editable)]
            if skipped:
                click.echo(f"Skipping {len(skipped)} non-editable changed file(s). "
                           f"Use --files to override.")
        else:
            # No editable list configured, fall back to all changed
            file_list = all_changed

    if not file_list:
        raise click.ClickException("No changed files to snapshot")

    # Get base commit
    base_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_root, capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Create archive directory and copy files
    archive = adir / "orchestrator" / "archive" / node
    archive.mkdir(parents=True, exist_ok=True)

    overlay_manifest = {}
    deletions = []
    for f in file_list:
        # Reject absolute paths and directory traversal
        if os.path.isabs(f) or ".." in Path(f).parts:
            raise click.ClickException(f"Invalid path (must be relative, no ..): {f}")
        src = git_root / f
        if not src.exists():
            # File was deleted - record as deletion
            deletions.append(f)
            click.echo(f"  {f}: deleted (will be removed in worktree)")
            continue
        # Verify resolved path is inside the git root
        try:
            src.resolve().relative_to(git_root.resolve())
        except ValueError:
            raise click.ClickException(f"Path escapes repository root: {f}")
        dst = archive / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        content_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        overlay_manifest[f] = f"sha256:{content_hash}"

    if not overlay_manifest and not deletions:
        raise click.ClickException("No files to snapshot or delete")

    # Compute config_hash from manifest + deletions
    parts = [f"{p}:{h}" for p, h in sorted(overlay_manifest.items())]
    parts.extend(f"DELETE:{d}" for d in sorted(deletions))
    config_hash = hashlib.sha256(
        (base_commit + "\n" + "\n".join(parts)).encode()
    ).hexdigest()[:16]

    # Write spec to queue
    spec = {
        "id": node,
        "description": desc,
        "base_commit": base_commit,
        "overlay_dir": f"archive/{node}",
        "overlay_manifest": overlay_manifest,
        "deletions": deletions,
        "priority": priority,
        "estimated_vram_gb": vram,
        "timeout_min": timeout,
        "graph_metadata": {
            "parent_id": parent,
            "techniques": list(techniques),
            "config_hash": config_hash,
        },
        "submitted_at": datetime.now().isoformat(),
    }

    queue_file = adir / "orchestrator" / "queue" / f"{node}.json"
    queue_file.write_text(json.dumps(spec, indent=2))

    # Register the node in the graph so that next_id is bumped and proposals
    # don't collide with submitted experiment IDs.
    graph_path = adir / "graph.json"
    if graph_path.exists():
        from automil.graph import ExperimentGraph
        graph = ExperimentGraph(path=str(graph_path))
        if not graph.get_node(node):
            graph.nodes[node] = {
                "id": node,
                "parent_id": parent,
                "type": "proposed",
                "status": "running",
                "description": desc,
                "techniques": list(techniques),
                "config_hash": config_hash,
                "potential": 0.0,
                "created_at": datetime.now().isoformat(),
            }
            # Bump next_id so proposals don't collide
            if node.startswith("node_"):
                try:
                    num = int(node.split("_")[1])
                    if num >= graph.meta["next_id"]:
                        graph.meta["next_id"] = num + 1
                except (ValueError, IndexError):
                    pass
            graph.save()

    n_snap = len(overlay_manifest)
    n_del = len(deletions)
    parts_msg = []
    if n_snap:
        parts_msg.append(f"{n_snap} file(s) snapshotted")
    if n_del:
        parts_msg.append(f"{n_del} file(s) deleted")
    click.echo(f"Submitted {node}: {', '.join(parts_msg)}")
    click.echo(f"  base_commit: {base_commit[:8]}")
    click.echo(f"  config_hash: {config_hash}")
