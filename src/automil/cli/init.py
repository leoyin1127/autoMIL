"""init command: scaffold autoMIL into an existing project."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from automil.cli import main
from automil.cli._helpers import _find_git_root


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

    # Render templates. Templates live alongside the package (not the cli/
    # subpackage), so resolve relative to ``automil/`` rather than ``cli/``.
    templates_dir = Path(__file__).parent.parent / "templates"
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
    package_dir = Path(__file__).parent.parent
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
