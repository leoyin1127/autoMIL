"""apply command: copy a node's variant selection into the active config (CLI-01 / D-41)."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

import click
import yaml

from automil.cli import main
from automil.cli._helpers import _find_automil_dir
from automil.cli.lifecycle._shared import (
    _atomic_write_text,
    _get_node_or_die,
)

logger = logging.getLogger(__name__)


def _derive_variant_selection(node: dict) -> dict[str, dict[str, Optional[str]]]:
    """From a graph node, derive {model, loss, policy} variant selection.

    Honours two formats:
      - ``recipe``: a list of ``{kind, name, parent?}`` dicts for multi-kind nodes.
      - ``variant_spec``: a single ``{kind, name, parent?}`` dict.

    Both formats are honoured; if a node has both, the ``variant_spec`` value
    takes precedence (it was written last by ``port-variant``).

    Returns a dict with keys ``"model"``, ``"loss"``, ``"policy"`` and
    optional string values:
        {
            "model": {"variant": "clam_mb_v0176", "parent": "clam_mb"},
            "loss":  {"variant": "ce_smooth008"},
            "policy":{"variant": "sam_lookahead"},
        }
    All values default to ``None`` when the node does not specify that kind.
    """
    sel: dict[str, dict[str, Optional[str]]] = {
        "model": {"variant": None, "parent": None},
        "loss": {"variant": None},
        "policy": {"variant": None},
    }

    # Recipe path: list of {kind, name, parent?} dicts.
    recipe = node.get("recipe")
    if isinstance(recipe, list):
        for entry in recipe:
            if not isinstance(entry, dict):
                continue
            kind = entry.get("kind")
            if kind in sel:
                sel[kind]["variant"] = entry.get("name")
                if kind == "model":
                    sel["model"]["parent"] = entry.get("parent")

    # variant_spec path: single {kind, name, parent?}.
    spec = node.get("variant_spec")
    if isinstance(spec, dict):
        kind = spec.get("kind")
        if kind in sel:
            sel[kind]["variant"] = spec.get("name")
            if kind == "model":
                sel["model"]["parent"] = spec.get("parent")

    return sel


@main.command("apply")
@click.argument("node_id")
def apply(node_id: str):
    """Apply a node's variant selection to automil/config.yaml.

    Workflow: after running an experiment that produced a good composite,
    use `automil apply <node_id>` to set that node's variant choices
    (model.variant, loss.variant, policy.variant) as the active config
    for the next submit. Edits config.yaml only — never modifies the
    codebase (registry-first invariant: variant code is committed).

    Backup: writes a single rolling automil/config.yaml.bak before mutation.
    Atomic write via tempfile+rename. Idempotent.

    Hard-fails if:
      - node_id is not in graph.json (lists available nodes).
      - the node has no recorded variant_spec or recipe (run port-variant first).
      - automil/config.yaml does not exist (run automil init first).
    """
    adir = _find_automil_dir()
    config_path = adir / "config.yaml"
    backup_path = adir / "config.yaml.bak"

    if not config_path.exists():
        raise click.ClickException(
            f"automil/config.yaml not found at {config_path}. "
            f"Run `automil init` first."
        )

    node = _get_node_or_die(adir, node_id)
    selection = _derive_variant_selection(node)

    # Hard-fail if the node has no variant selection recorded at all.
    if (
        selection["model"]["variant"] is None
        and selection["loss"]["variant"] is None
        and selection["policy"]["variant"] is None
    ):
        raise click.ClickException(
            f"Node {node_id} has no recorded variant_spec or recipe. "
            f"Run `automil port-variant {node_id}` first to register the "
            f"variant, then `automil apply {node_id}` again."
        )

    raw_yaml = yaml.safe_load(config_path.read_text()) or {}

    # Patch the three sections.
    for kind in ("model", "loss", "policy"):
        section = raw_yaml.setdefault(kind, {})
        if not isinstance(section, dict):
            raise click.ClickException(
                f"automil/config.yaml: `{kind}:` is not a mapping. "
                f"Fix the file or restore from a recent commit."
            )
        v = selection[kind].get("variant")
        if v is not None:
            section["variant"] = v
        if kind == "model":
            p = selection["model"].get("parent")
            if p is not None:
                section["parent"] = p

    # Roll backup THEN atomic write.
    shutil.copy2(config_path, backup_path)
    new_text = yaml.safe_dump(raw_yaml, sort_keys=False, default_flow_style=False)
    _atomic_write_text(config_path, new_text)

    click.echo(
        f"Applied node {node_id}: "
        f"model.variant={selection['model'].get('variant')}, "
        f"loss.variant={selection['loss'].get('variant')}, "
        f"policy.variant={selection['policy'].get('variant')}"
    )
    click.echo(f"Backup: {backup_path}")
