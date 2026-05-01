"""viz subgroup: start, stop, status."""
from __future__ import annotations

import click

from automil.cli import main
from automil.cli._helpers import _find_automil_dir


@main.group(name="viz")
def viz_group():
    """Manage the visualization dashboard."""
    pass


@viz_group.command("start")
@click.option("--port", default=8420, help="Server port")
def viz_start(port: int):
    """Start the 3D visualization dashboard."""
    adir = _find_automil_dir()
    from automil.viz.server import cmd_start
    cmd_start(port=port, project_root=adir.parent)


@viz_group.command("stop")
def viz_stop():
    """Stop the visualization dashboard."""
    adir = _find_automil_dir()
    from automil.viz.server import cmd_stop
    cmd_stop(project_root=adir.parent)


@viz_group.command("status")
def viz_status():
    """Show visualization server status."""
    adir = _find_automil_dir()
    from automil.viz.server import cmd_status
    cmd_status(project_root=adir.parent)
