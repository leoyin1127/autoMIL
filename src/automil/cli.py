"""automil CLI - command-line interface for autoMIL framework."""

from __future__ import annotations

import fnmatch
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml


def _find_automil_dir() -> Path:
    """Walk up from cwd to find a directory containing automil/config.yaml.

    Returns the ``automil/`` directory itself.
    """
    p = Path.cwd()
    while p != p.parent:
        candidate = p / "automil" / "config.yaml"
        if candidate.exists():
            return p / "automil"
        p = p.parent
    raise click.ClickException(
        "No automil/config.yaml found. Run 'automil init' in your project root."
    )


def _find_git_root(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) to find the git repo root."""
    p = (start or Path.cwd()).resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    raise click.ClickException(
        "Not inside a git repository."
    )



def _matches_scope(path: str, patterns: list[str] | set[str]) -> bool:
    """Return whether a relative path matches any configured scope pattern.

    Supports exact file paths, directory prefixes ending in ``/``, and glob
    patterns such as ``data/*.py``.
    """
    rel_path = Path(path).as_posix()
    for raw_pattern in patterns:
        pattern = str(raw_pattern).strip().replace("\\", "/")
        if not pattern:
            continue
        if pattern.endswith("/"):
            if rel_path.startswith(pattern):
                return True
            continue
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


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

    # Verify we're inside a git repo (can be a subdirectory)
    try:
        _find_git_root(project_root)
    except click.ClickException:
        raise click.ClickException(
            "Not inside a git repository. Run 'git init' or cd into your project."
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

    # Install Claude Code skills and hooks into the project
    package_dir = Path(__file__).parent
    claude_src = package_dir / "claude_assets"
    project_claude = project_root / ".claude"

    if claude_src.exists():
        # Copy skills (each skill is a subdirectory with SKILL.md)
        skills_src = claude_src / "skills"
        if skills_src.exists():
            for skill_dir in skills_src.iterdir():
                if skill_dir.is_dir():
                    dst_dir = project_claude / "skills" / skill_dir.name
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        dst = dst_dir / "SKILL.md"
                        if not dst.exists():
                            shutil.copy2(skill_file, dst)

        # Copy hook script
        hooks_src = claude_src / "hooks"
        if hooks_src.exists():
            hooks_dst = project_claude / "hooks"
            hooks_dst.mkdir(parents=True, exist_ok=True)
            for f in hooks_src.iterdir():
                if f.is_file():
                    dst = hooks_dst / f.name
                    if not dst.exists():
                        shutil.copy2(f, dst)
                        if f.suffix == ".sh":
                            dst.chmod(dst.stat().st_mode | 0o111)

        # Register the stop hook in settings.json
        settings_path = project_claude / "settings.json"
        hook_cmd = f"bash {project_root / '.claude' / 'hooks' / 'on_stop.sh'}"

        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
        else:
            project_claude.mkdir(parents=True, exist_ok=True)
            settings = {}

        # Add Stop hook if not already registered
        hooks = settings.setdefault("hooks", {})
        stop_hooks = hooks.setdefault("Stop", [])
        already_registered = any(
            hook_cmd in str(entry)
            for entry in stop_hooks
        )
        if not already_registered:
            stop_hooks.append({
                "hooks": [{
                    "type": "command",
                    "command": hook_cmd,
                }]
            })
            settings_path.write_text(json.dumps(settings, indent=2) + "\n")

    click.echo(f"autoMIL initialized at {automil_dir}/")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {automil_dir}/config.yaml with your project settings")
    click.echo(f"  2. Run: automil orchestrator start")
    click.echo(f"  3. Start your coding agent (claude -> /automil-setup)")


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


@main.command()
@click.option("--n", default=6, help="Number of proposals to return")
@click.option("--max-per-branch", default=2, help="Max proposals per branch")
def rank(n: int, max_per_branch: int):
    """Show top-ranked proposals from the experiment graph."""
    adir = _find_automil_dir()
    graph_path = adir / "graph.json"

    if not graph_path.exists():
        click.echo("No graph.json found. Run some experiments first.")
        return

    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(graph_path))
    graph.recalculate_scores()
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
    adir = _find_automil_dir()
    from automil.graph import ExperimentGraph
    graph = ExperimentGraph(path=str(adir / "graph.json"))

    # Duplicate guard: refuse exact-description sibling proposals under the
    # same parent that are still pending or running. Prevents waste from
    # accidental double-proposes (the 0063="dup of 0057" case). Exact-match
    # only — fine-grained hyperparameter sweeps with different descriptions
    # are unaffected.
    desc_norm = desc.strip()
    for n in graph.nodes.values():
        if (n.get("parent_id") == parent
                and n.get("type") == "proposed"
                and n.get("status") in ("pending", "running")
                and (n.get("description", "") or "").strip() == desc_norm):
            raise click.ClickException(
                f"Refusing to propose: {n['id']} already exists under "
                f"--parent {parent} with the same description "
                f"'{desc_norm[:60]}'. Use a different description, pick a "
                f"different parent, or wait for {n['id']} to complete."
            )

    node_id = graph.add_proposed(
        parent_id=parent,
        description=desc,
        techniques=list(techniques),
    )
    graph.recalculate_scores()
    graph.save()
    click.echo(f"Added proposal {node_id}: {desc}")


@main.command()
def reconcile():
    """Sync experiment graph with orchestrator state."""
    adir = _find_automil_dir()
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
    adir = _find_automil_dir()

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
    adir = _find_automil_dir()
    (adir.parent / ".automil_active").touch()
    click.echo("Loop started. Agent will not stop until 'automil stop-loop' is run.")


@main.command("stop-loop")
def stop_loop():
    """Remove .automil_active flag to allow agent stopping."""
    adir = _find_automil_dir()
    flag = adir.parent / ".automil_active"
    if flag.exists():
        flag.unlink()
        click.echo("Loop stopped. Agent can now exit.")
    else:
        click.echo("Loop was not active.")


@main.command()
def check():
    """Validate project setup before running experiments."""
    git_root = _find_git_root()
    adir = _find_automil_dir()
    issues = []
    warnings = []

    # Check config.yaml
    config_path = adir / "config.yaml"
    if not config_path.exists():
        issues.append("automil/config.yaml not found. Run 'automil init' first.")
    else:
        config = yaml.safe_load(config_path.read_text())

        # Check run script (skip if run.command is set — script may not exist)
        run_command = config.get("run", {}).get("command")
        run_script = config.get("run", {}).get("script") or "train.py"
        if not run_command:
            if not (git_root / run_script).exists():
                issues.append(f"Training script '{run_script}' not found at {git_root / run_script}")
            else:
                script_content = (git_root / run_script).read_text()
                if "result.json" not in script_content:
                    warnings.append(f"Training script '{run_script}' may not write result.json")

        # Check data paths
        for key in ["features_dir", "splits_dir", "mapping_csv"]:
            path = config.get("data", {}).get(key, "")
            if path and path.startswith("/path/to"):
                issues.append(f"data.{key} is still a placeholder: {path}")
            elif path and "${" not in path:
                resolved = Path(path)
                if not resolved.is_absolute():
                    resolved = git_root / resolved
                if not resolved.exists():
                    warnings.append(f"data.{key} path does not exist: {path}")

        # Check files.editable
        editable = config.get("files", {}).get("editable", [])
        if not editable:
            warnings.append("files.editable is empty. Auto-detect will capture ALL changed files.")

        # Check baseline
        baseline_comp = config.get("baseline", {}).get("composite", 0)
        if baseline_comp == 0:
            warnings.append("baseline.composite is 0. Set this after running your first experiment.")

    # Check GPU
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            warnings.append("nvidia-smi failed. GPU scheduling may not work correctly.")
        else:
            n_gpus = len(result.stdout.strip().splitlines())
            click.echo(f"GPUs detected: {n_gpus}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warnings.append("nvidia-smi not found. GPU scheduling will use fallback.")

    # Check orchestrator directories
    for d in ["queue", "running", "archive", "completed"]:
        if not (adir / "orchestrator" / d).exists():
            issues.append(f"automil/orchestrator/{d}/ missing. Run 'automil init'.")

    # Report
    if issues:
        click.echo("\nISSUES (must fix):")
        for i, issue in enumerate(issues, 1):
            click.echo(f"  {i}. {issue}")

    if warnings:
        click.echo("\nWARNINGS:")
        for i, w in enumerate(warnings, 1):
            click.echo(f"  {i}. {w}")

    if not issues and not warnings:
        click.echo("All checks passed. Ready to run experiments.")
    elif not issues:
        click.echo(f"\n{len(warnings)} warning(s), no blocking issues.")
    else:
        click.echo(f"\n{len(issues)} issue(s) must be fixed before running.")


# Orchestrator subgroup
@main.group()
def orchestrator():
    """Manage the GPU scheduler daemon."""
    pass


@orchestrator.command("start")
def orch_start():
    """Start the orchestrator daemon."""
    from automil.orchestrator import ExperimentOrchestrator
    orch = ExperimentOrchestrator(
        project_root=_find_git_root(), automil_dir=_find_automil_dir(),
    )
    orch.cmd_start()


@orchestrator.command("stop")
def orch_stop():
    """Stop the orchestrator daemon."""
    from automil.orchestrator import ExperimentOrchestrator
    orch = ExperimentOrchestrator(
        project_root=_find_git_root(), automil_dir=_find_automil_dir(),
    )
    orch.cmd_stop()


@orchestrator.command("status")
def orch_status():
    """Show orchestrator status."""
    from automil.orchestrator import ExperimentOrchestrator
    orch = ExperimentOrchestrator(
        project_root=_find_git_root(), automil_dir=_find_automil_dir(),
    )
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
    adir = _find_automil_dir()
    from automil.viz.server import cmd_start
    cmd_start(port=port, project_root=adir.parent)


@viz.command("stop")
def viz_stop():
    """Stop the visualization dashboard."""
    adir = _find_automil_dir()
    from automil.viz.server import cmd_stop
    cmd_stop(project_root=adir.parent)


@viz.command("status")
def viz_status():
    """Show visualization server status."""
    adir = _find_automil_dir()
    from automil.viz.server import cmd_status
    cmd_status(project_root=adir.parent)


if __name__ == "__main__":
    main()
