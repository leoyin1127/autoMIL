"""Git worktree overlay runner for experiment isolation."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class Runner:
    """Manages git worktree lifecycle for experiment execution."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self._worktree_base = self.project_root / ".automil_worktrees"
        self._worktree_base.mkdir(exist_ok=True)

    def worktree_path(self, node_id: str) -> Path:
        """Public accessor for a node's worktree path."""
        return self._worktree_base / node_id

    def create_worktree(self, base_commit: str, node_id: str) -> Path:
        """Create a detached worktree at the given commit."""
        wt_path = self._worktree_base / node_id
        if wt_path.exists():
            shutil.rmtree(wt_path)

        subprocess.run(
            ["git", "worktree", "add", "--detach", str(wt_path), base_commit],
            cwd=self.project_root,
            capture_output=True,
            check=True,
        )
        return wt_path

    def apply_overlay(self, worktree_path: Path, overlay_dir: Path,
                      deletions: list[str] | None = None) -> None:
        """Copy modified files from overlay_dir on top of worktree.

        Also removes files listed in `deletions` from the worktree to support
        experiments that delete or rename files.
        """
        metadata_files = {Path("spec.json"), Path("run.log"), Path("result.json")}
        for src_file in overlay_dir.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(overlay_dir)
            if rel in metadata_files:
                continue
            dst = worktree_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst)

        # Apply deletions
        if deletions:
            for rel_path in deletions:
                target = worktree_path / rel_path
                if target.exists():
                    target.unlink()

    def collect_result(self, worktree_path: Path, archive_dir: Path) -> dict | None:
        """Copy result.json from worktree to archive. Returns parsed result or None."""
        result_file = worktree_path / "result.json"
        if not result_file.exists():
            return None

        archive_dir.mkdir(parents=True, exist_ok=True)
        dst = archive_dir / "result.json"
        shutil.copy2(result_file, dst)

        return json.loads(result_file.read_text())

    def cleanup_worktree(self, worktree_path: Path) -> None:
        """Remove a git worktree."""
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=self.project_root,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            if worktree_path.exists():
                shutil.rmtree(worktree_path)
            self.prune_stale_worktrees()

    def prune_stale_worktrees(self) -> None:
        """Remove references to deleted worktrees."""
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=self.project_root,
            capture_output=True,
        )
