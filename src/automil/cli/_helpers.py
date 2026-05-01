"""Internal helpers shared across automil CLI subcommands.

Private to the cli/ package (D-02). If the registry or backends layer needs
git-root lookup in Phase 1+, lift to ``automil/paths.py`` at that point — not
now.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

import click


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
    raise click.ClickException("Not inside a git repository.")


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
