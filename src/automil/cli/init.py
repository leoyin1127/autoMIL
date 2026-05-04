"""init command: scaffold autoMIL into an existing project."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from automil.cli import main
from automil.cli._helpers import _find_git_root


def _scaffold_variants_skeleton(automil_dir: Path) -> None:
    """Create automil/variants/<_losses|_policies|_candidates>/ + .gitkeep files.

    Per D-25 + REG-04 + REG-08 (deferred portion): each kind subdirectory
    gets a .gitkeep so the empty directory commits cleanly. The per-parent
    <parent>/ subdirectory is created by `port-variant` on first use
    (Plan 01-11) — no parent name to assume at init time.

    Idempotent: re-running on an existing skeleton is a no-op (mkdir
    parents=True exist_ok=True; .gitkeep .touch is safe to repeat).
    """
    variants_root = automil_dir / "variants"
    variants_root.mkdir(parents=True, exist_ok=True)
    (variants_root / ".gitkeep").touch()
    for sub in ("_losses", "_policies", "_candidates"):
        sub_dir = variants_root / sub
        sub_dir.mkdir(parents=True, exist_ok=True)
        (sub_dir / ".gitkeep").touch()


def _register_claude_hooks(
    project_root: Path,
    project_claude: Path,
    package_dir: Path,
) -> None:
    """Register the stop hook in .claude/settings.json.

    Extracted from the original init.py block (lines 120–144) to allow
    reuse from _install_runtime_assets without duplication.
    """
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


def _install_runtime_assets(
    rt: str,
    project_root: Path,
    package_dir: Path,
    merge_skill,  # callable: (runtime, shared_path, overlay_path) -> str
) -> None:
    """Install per-runtime overlay assets (skill, hooks, native files).

    D-92: per-runtime overlay loop. Hook scripts are not installed here
    (that is Plan 03-10). This function installs:
    - Skill files into .claude/skills/ (for claude runtime)
    - Native runtime instruction files (CLAUDE.md, .opencode/AGENTS.md, etc.)
    - settings.json hook registration (claude only)
    """
    shared_dir = package_dir / "agent_assets" / "_shared"
    overlay_dir = package_dir / "agent_assets" / rt

    # Copy skill files from _shared/skills into runtime-appropriate location
    skills_src = shared_dir / "skills"

    if rt == "claude":
        project_claude = project_root / ".claude"
        project_claude.mkdir(parents=True, exist_ok=True)

        # Install skills into .claude/skills/ using merge_skill for overlay
        if skills_src.exists():
            for skill_dir in skills_src.iterdir():
                if skill_dir.is_dir():
                    dst_dir = project_claude / "skills" / skill_dir.name
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    shared_skill = skill_dir / "SKILL.md"
                    if shared_skill.exists():
                        overlay_skill_path = overlay_dir / "skills" / skill_dir.name / "SKILL.md"
                        overlay_arg = overlay_skill_path if overlay_skill_path.exists() else None
                        merged = merge_skill(rt, shared_skill, overlay_arg)
                        dst = dst_dir / "SKILL.md"
                        if not dst.exists():
                            dst.write_text(merged, encoding="utf-8")

        # Copy hook scripts from agent_assets/claude/hooks
        hooks_src = package_dir / "agent_assets" / "claude" / "hooks"
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

        # .claude/CLAUDE.md — first line @AGENTS.md (D-90)
        claude_md = project_claude / "CLAUDE.md"
        if not claude_md.exists():
            claude_md.write_text(
                "@AGENTS.md\n\n# Claude Code — autoMIL\n\nSee AGENTS.md above for universal instructions.\n",
                encoding="utf-8",
            )
            click.echo("  Created: .claude/CLAUDE.md")

        # Register stop hook in settings.json
        _register_claude_hooks(project_root, project_claude, package_dir)
        click.echo("  Runtime: claude — assets installed")

    elif rt == "opencode":
        opencode_dir = project_root / ".opencode"
        opencode_dir.mkdir(parents=True, exist_ok=True)
        # .opencode/AGENTS.md — same universal content as project-root AGENTS.md
        agents_src = shared_dir / "AGENTS.md"
        if agents_src.exists():
            dst = opencode_dir / "AGENTS.md"
            if not dst.exists():
                dst.write_text(agents_src.read_text(encoding="utf-8"), encoding="utf-8")
        # .opencode/plugins/automil-trajectory.ts (Bun TypeScript plugin)
        plugins_dir = opencode_dir / "plugins"
        plugins_dir.mkdir(exist_ok=True)
        ts_src = package_dir / "agent_assets" / "opencode" / "plugins" / "automil-trajectory.ts"
        if ts_src.exists():
            (plugins_dir / "automil-trajectory.ts").write_text(ts_src.read_text(encoding="utf-8"), encoding="utf-8")
            click.echo("  Plugin: .opencode/plugins/automil-trajectory.ts")
        click.echo("  Runtime: opencode — assets installed (.opencode/AGENTS.md + plugin)")

    elif rt == "codex":
        codex_dir = project_root / ".codex"
        codex_dir.mkdir(parents=True, exist_ok=True)
        # .codex/instructions.md
        instructions = codex_dir / "instructions.md"
        if not instructions.exists():
            agents_src = shared_dir / "AGENTS.md"
            content = (
                agents_src.read_text(encoding="utf-8")
                if agents_src.exists()
                else "# autoMIL\n\nSee AGENTS.md.\n"
            )
            instructions.write_text(content, encoding="utf-8")
        click.echo("  Runtime: codex — assets installed (.codex/instructions.md)")

    elif rt in ("deepseek-via-opencode", "deepseek-via-codex"):
        base_rt = "opencode" if "opencode" in rt else "codex"
        click.echo(f"  Runtime: {rt} — DeepSeek is a model; installing {base_rt} overlay")
        _install_runtime_assets(base_rt, project_root, package_dir, merge_skill)


@main.command()
@click.argument("path", default="automil")
@click.option("--task", default="binary", help="Task type: binary or multiclass")
@click.option("--encoder", default="hoptimus1", help="Primary encoder name")
@click.option(
    "--runtime",
    default=None,
    type=click.Choice(
        ["claude", "opencode", "codex", "deepseek-via-opencode", "deepseek-via-codex", "all"]
    ),
    help=(
        "Runtime to install assets for "
        "(default: auto-detect from existing .claude/.opencode/.codex dirs)"
    ),
)
@click.option(
    "--update",
    is_flag=True,
    default=False,
    help="Re-render skills/hooks/AGENTS.md for installed runtimes without re-scaffolding",
)
def init(path: str, task: str, encoder: str, runtime: str | None, update: bool) -> None:
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

    # D-92: --update bypasses the already-initialized guard
    if automil_dir.exists() and (automil_dir / "config.yaml").exists():
        if not update:
            raise click.ClickException(f"autoMIL already initialized at {automil_dir}")
        # --update: skip scaffold, proceed to asset re-install

    if not update:
        # Create directory structure
        automil_dir.mkdir(parents=True, exist_ok=True)
        for subdir in [
            "orchestrator/queue",
            "orchestrator/running",
            "orchestrator/archive",
            "orchestrator/completed",
        ]:
            (automil_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Scaffold the registry variants/ skeleton (D-25, REG-04).
        _scaffold_variants_skeleton(automil_dir)

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

    # D-91: auto-detect runtime from existing dirs if --runtime not specified
    if runtime is None:
        detected = []
        if (project_root / ".claude").exists():
            detected.append("claude")
        if (project_root / ".opencode").exists():
            detected.append("opencode")
        if (project_root / ".codex").exists():
            detected.append("codex")
        if detected:
            runtimes_to_install = detected
        else:
            runtimes_to_install = ["claude"]  # default: Claude Code
            click.echo(
                "No runtime config detected — installing Claude Code overlay. "
                "Use --runtime to override or --runtime all for full multi-runtime support."
            )
    elif runtime == "all":
        runtimes_to_install = ["claude", "opencode", "codex"]
    else:
        runtimes_to_install = [runtime]

    # D-92: lazy import of overlay merger inside command body
    from automil.agent_assets._overlay import merge_skill  # noqa: E402

    package_dir = Path(__file__).parent.parent

    # Render project-root AGENTS.md once per init invocation (D-90)
    agents_shared = package_dir / "agent_assets" / "_shared" / "AGENTS.md"
    if agents_shared.exists():
        agents_content = agents_shared.read_text(encoding="utf-8")
        (project_root / "AGENTS.md").write_text(agents_content, encoding="utf-8")
        click.echo("  Created: AGENTS.md")

    # Install per-runtime assets
    for rt in runtimes_to_install:
        _install_runtime_assets(rt, project_root, package_dir, merge_skill)

    click.echo(f"autoMIL initialized at {automil_dir}/")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {automil_dir}/config.yaml with your project settings")
    click.echo(f"  2. Run: automil orchestrator start")
    runtimes_display = ", ".join(runtimes_to_install)
    click.echo(f"  3. Start your coding agent ({runtimes_display} -> /automil-setup)")
