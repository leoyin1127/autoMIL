"""automil CLI - command-line interface for autoMIL framework."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml


def _find_project_root() -> Path:
    """Walk up from cwd to find a directory containing automil/config.yaml."""
    p = Path.cwd()
    while p != p.parent:
        if (p / "automil" / "config.yaml").exists():
            return p
        p = p.parent
    raise click.ClickException(
        "No automil/config.yaml found. Run 'automil init' in your project root."
    )


def _automil_dir(root: Path) -> Path:
    return root / "automil"


@click.group()
def main():
    """autoMIL: Autonomous agent-driven MIL model improvement."""
    pass


@main.command()
@click.argument("path", default="automil")
@click.option("--task", default="binary", help="Task type: binary or multiclass")
@click.option("--encoder", default="hoptimus1", help="Primary encoder name")
def init(path: str, task: str, encoder: str):
    """Add autoMIL to an existing project."""
    from jinja2 import Environment, FileSystemLoader

    project_root = Path.cwd()
    automil_dir = project_root / path

    # Verify we're in a git repo
    if not (project_root / ".git").exists():
        raise click.ClickException(
            "Not a git repository. Run 'git init' first or cd into your project."
        )

    if automil_dir.exists() and (automil_dir / "config.yaml").exists():
        raise click.ClickException(f"autoMIL already initialized at {automil_dir}")

    # Create directory structure
    automil_dir.mkdir(parents=True, exist_ok=True)
    for subdir in [
        "orchestrator/queue",
        "orchestrator/running",
        "orchestrator/archive",
        "orchestrator/completed",
    ]:
        (automil_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Render templates
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    context = {
        "task_type": task,
        "encoder": encoder,
        "project_name": project_root.name,
    }

    for template_name, target_name in [
        ("config.yaml.j2", "config.yaml"),
        ("program.md.j2", "program.md"),
        ("learnings.md.j2", "learnings.md"),
        (".gitignore.j2", ".gitignore"),
    ]:
        template = env.get_template(template_name)
        (automil_dir / target_name).write_text(template.render(**context))

    click.echo(f"autoMIL initialized at {automil_dir}/")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {automil_dir}/config.yaml with your project settings")
    click.echo(f"  2. Run: automil orchestrator start")
    click.echo(f"  3. Start your coding agent")


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

    root = _find_project_root()
    adir = _automil_dir(root)

    # Determine files to snapshot
    if files:
        file_list = list(files)
        # Warn (but allow) if explicit --files includes readonly files
        config_path = adir / "config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text())
            readonly = set(config.get("files", {}).get("readonly", []))
            for f in file_list:
                if f in readonly:
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

        # Get all changed files from git
        tracked = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=root, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, text=True,
        ).stdout.strip().splitlines()
        all_changed = [f for f in tracked + untracked if f]

        if editable:
            # Only capture files that are both editable AND changed
            file_list = [f for f in all_changed if f in editable]
            skipped = [f for f in all_changed if f not in editable]
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
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Create archive directory and copy files
    archive = adir / "orchestrator" / "archive" / node
    archive.mkdir(parents=True, exist_ok=True)

    overlay_manifest = {}
    for f in file_list:
        # Reject absolute paths and directory traversal
        if os.path.isabs(f) or ".." in Path(f).parts:
            raise click.ClickException(f"Invalid path (must be relative, no ..): {f}")
        src = root / f
        if not src.exists():
            click.echo(f"Warning: {f} does not exist (deleted file? skipping)")
            continue
        # Verify resolved path is inside the project root
        try:
            src.resolve().relative_to(root.resolve())
        except ValueError:
            raise click.ClickException(f"Path escapes project root: {f}")
        dst = archive / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        content_hash = hashlib.sha256(src.read_bytes()).hexdigest()
        overlay_manifest[f] = f"sha256:{content_hash}"

    # Compute config_hash from manifest
    parts = [f"{p}:{h}" for p, h in sorted(overlay_manifest.items())]
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

    click.echo(f"Submitted {node}: {len(file_list)} file(s) snapshotted")
    click.echo(f"  base_commit: {base_commit[:8]}")
    click.echo(f"  config_hash: {config_hash}")


@main.command()
@click.option("--n", default=6, help="Number of proposals to return")
@click.option("--max-per-branch", default=2, help="Max proposals per branch")
def rank(n: int, max_per_branch: int):
    """Show top-ranked proposals from the experiment graph."""
    root = _find_project_root()
    graph_path = _automil_dir(root) / "graph.json"

    if not graph_path.exists():
        click.echo("No graph.json found. Run some experiments first.")
        return

    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(graph_path))
    proposals = graph.rank_proposals(n=n, max_per_branch=max_per_branch)

    if not proposals:
        click.echo("No proposals available. Time to brainstorm!")
        return

    click.echo(f"Top {len(proposals)} proposals:\n")
    for i, node in enumerate(proposals, 1):
        node_id = node["id"]
        parent = node.get("parent_id", "root")
        desc = node.get("description", "")
        score = node.get("potential", 0)
        click.echo(f"  {i}. [{node_id}] (parent: {parent}, score: {score:.4f})")
        click.echo(f"     {desc}")
        click.echo()


@main.command()
@click.option("--parent", required=True, help="Parent node ID")
@click.option("--desc", required=True, help="Proposal description")
@click.option("--techniques", multiple=True, help="Technique tags")
def propose(parent: str, desc: str, techniques: tuple):
    """Add a new experiment proposal to the graph."""
    root = _find_project_root()
    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(_automil_dir(root) / "graph.json"))
    node_id = graph.add_proposed(
        parent_id=parent,
        description=desc,
        techniques=list(techniques),
    )
    graph.save()
    click.echo(f"Added proposal {node_id}: {desc}")


@main.command()
def reconcile():
    """Sync experiment graph with orchestrator state."""
    root = _find_project_root()
    adir = _automil_dir(root)
    orch = adir / "orchestrator"
    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(adir / "graph.json"))
    graph.reconcile(
        queue_dir=str(orch / "queue"),
        running_dir=str(orch / "running"),
        completed_dir=str(orch / "completed"),
        archive_dir=str(orch / "archive"),
    )
    graph.save()
    click.echo("Graph reconciled with orchestrator state.")


@main.command()
def status():
    """Show experiment status summary."""
    root = _find_project_root()
    adir = _automil_dir(root)

    queue = list((adir / "orchestrator" / "queue").glob("*.json"))
    completed = list((adir / "orchestrator" / "completed").glob("*.json"))

    graph_path = adir / "graph.json"
    if graph_path.exists():
        from automil.graph import ExperimentGraph
        graph = ExperimentGraph(path=str(graph_path))
        executed = sum(1 for n in graph.nodes.values() if n.get("type") == "executed")
        proposed = sum(1 for n in graph.nodes.values() if n.get("type") == "proposed")
        best = graph.meta.get("best_composite", 0)
        click.echo(f"Executed: {executed}  Proposed: {proposed}  Best: {best:.4f}")
    else:
        click.echo("No graph.json found.")

    click.echo(f"Queue: {len(queue)}  Completed (pending read): {len(completed)}")


@main.command("start-loop")
def start_loop():
    """Create .automil_active flag to prevent agent stopping."""
    root = _find_project_root()
    (root / ".automil_active").touch()
    click.echo("Loop started. Agent will not stop until 'automil stop-loop' is run.")


@main.command("stop-loop")
def stop_loop():
    """Remove .automil_active flag to allow agent stopping."""
    root = _find_project_root()
    flag = root / ".automil_active"
    if flag.exists():
        flag.unlink()
        click.echo("Loop stopped. Agent can now exit.")
    else:
        click.echo("Loop was not active.")


# Orchestrator subgroup
@main.group()
def orchestrator():
    """Manage the GPU scheduler daemon."""
    pass


@orchestrator.command("start")
def orch_start():
    """Start the orchestrator daemon."""
    root = _find_project_root()
    from automil.orchestrator import ExperimentOrchestrator
    orch = ExperimentOrchestrator(project_root=root)
    orch.cmd_start()


@orchestrator.command("stop")
def orch_stop():
    """Stop the orchestrator daemon."""
    root = _find_project_root()
    from automil.orchestrator import ExperimentOrchestrator
    orch = ExperimentOrchestrator(project_root=root)
    orch.cmd_stop()


@orchestrator.command("status")
def orch_status():
    """Show orchestrator status."""
    root = _find_project_root()
    from automil.orchestrator import ExperimentOrchestrator
    orch = ExperimentOrchestrator(project_root=root)
    orch.cmd_status()


# Viz subgroup
@main.group()
def viz():
    """Manage the visualization dashboard."""
    pass


@viz.command("start")
@click.option("--port", default=8420, help="Server port")
def viz_start(port: int):
    """Start the 3D visualization dashboard."""
    root = _find_project_root()
    from automil.viz.server import cmd_start
    cmd_start(port=port, project_root=root)


@viz.command("stop")
def viz_stop():
    """Stop the visualization dashboard."""
    root = _find_project_root()
    from automil.viz.server import cmd_stop
    cmd_stop(project_root=root)


@viz.command("status")
def viz_status():
    """Show visualization server status."""
    root = _find_project_root()
    from automil.viz.server import cmd_status
    cmd_status(project_root=root)


if __name__ == "__main__":
    main()
