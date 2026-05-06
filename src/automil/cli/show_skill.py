"""show-skill command: render merged per-runtime SKILL.md or AGENTS.md to stdout (MRT-04 / D-93)."""
from __future__ import annotations

from pathlib import Path

import click

from automil.cli import main


@main.command("show-skill")
@click.option(
    "--runtime",
    required=True,
    type=click.Choice(
        ["claude", "opencode", "codex", "deepseek-via-opencode", "deepseek-via-codex"]
    ),
    help="Runtime to render the skill file for",
)
@click.option(
    "--asset",
    default="SKILL",
    type=click.Choice(["SKILL", "AGENTS"]),
    show_default=True,
    help="Which asset to render: SKILL (default) or AGENTS",
)
def show_skill(runtime: str, asset: str) -> None:
    """Render merged per-runtime skill file to stdout.

    Pipeable: automil show-skill --runtime claude > /tmp/preview.md

    No write side-effects — read-only inspection command.
    """
    from automil.agent_assets._overlay import merge_skill  # lazy import — D-93

    package_dir = Path(__file__).parent.parent
    asset_filename = f"{asset}.md"

    if asset == "SKILL":
        shared_path = (
            package_dir / "agent_assets" / "_shared" / "skills" / "automil" / "SKILL.md"
        )
    else:  # AGENTS
        shared_path = package_dir / "agent_assets" / "_shared" / "AGENTS.md"

    if not shared_path.exists():
        raise click.ClickException(
            f"Shared asset not found at {shared_path}. "
            f"Ensure agent_assets/_shared/ is present (run `automil init` first)."
        )

    # Resolve overlay path — handle deepseek-via-X routing
    if runtime.startswith("deepseek-via-"):
        base_runtime = runtime.split("-via-", 1)[1]  # "opencode" or "codex"
        overlay_path = package_dir / "agent_assets" / base_runtime / asset_filename
    else:
        overlay_path = package_dir / "agent_assets" / runtime / asset_filename

    result = merge_skill(runtime, shared_path, overlay_path if overlay_path.exists() else None)
    click.echo(result, nl=False)  # pipeable — no trailing newline added
