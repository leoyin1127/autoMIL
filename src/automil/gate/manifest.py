"""Gate manifest persistence (D-137 / D-138 / GTE-01, GTE-02).

Pattern composes:
- cells/state.py:write_cell — atomic write via tempfile.mkstemp + os.replace
- cli/lifecycle/promote_variant.py — git subprocess pattern (Task 2 only)

Rollback on git failure uses path.unlink() — NEVER git checkout
(Leo memory: feedback_never_blind_checkout).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "gate-v1"
BOOTSTRAP_REPS_FLOOR = 100


@dataclass(frozen=True)
class GateManifest:
    """Immutable snapshot of a pre-registered gate manifest (D-137).

    Frozen — instances cannot be mutated. Schema mutations go through
    retire_manifest (write new file) + write_manifest_committed (new instance).
    Hashable + JSON-serialisable via dataclasses.asdict(manifest).
    """

    parent_id: str
    created_at: str              # ISO-8601 UTC
    git_committed_at_sha: str    # "PENDING" until commit resolves; second commit backfills
    held_out_cells: tuple[tuple[str, str, str, str], ...]  # (cell_id, dataset, encoder, task)
    K: int                       # minimum cells that must pass
    p_threshold: float           # pre-Bonferroni alpha (default 0.05)
    bootstrap_reps: int          # default 1000
    win_definition: str          # human-readable string for paper citation
    schema_version: str          # "gate-v1"


def validate_manifest_dict(d: dict) -> None:
    """Schema validator — raises ValueError on violation.

    Called by write_* before persistence. All fields required; validated in order.
    """
    if not isinstance(d.get("K"), int) or d["K"] < 1:
        raise ValueError(f"K must be >= 1; got {d.get('K')!r}")
    held = d.get("held_out_cells", [])
    if not held:
        raise ValueError("held_out_cells must be non-empty")
    if d["K"] > len(held):
        raise ValueError(
            f"K={d['K']} exceeds held_out_cells count={len(held)}"
        )
    p = d.get("p_threshold")
    if not isinstance(p, (int, float)) or not (0 < p <= 1):
        raise ValueError(f"p_threshold must be in (0, 1]; got {p!r}")
    reps = d.get("bootstrap_reps")
    if not isinstance(reps, int) or reps < BOOTSTRAP_REPS_FLOOR:
        raise ValueError(
            f"bootstrap_reps must be >= {BOOTSTRAP_REPS_FLOOR}; got {reps!r}"
        )
    sv = d.get("schema_version")
    if sv != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {SCHEMA_VERSION!r}; got {sv!r}"
        )


def write_manifest(manifest: GateManifest, manifests_dir: Path) -> Path:
    """Atomic write — does NOT commit to git. Returns the written path.

    Uses tempfile.mkstemp(dir=str(manifests_dir)) to keep the temp file on the
    same filesystem as the destination so os.replace is an atomic POSIX rename
    (cross-filesystem renames are NOT atomic — Pitfall 2 defence).

    On failure the temp file is cleaned up and the exception re-raised.
    """
    manifests_dir.mkdir(parents=True, exist_ok=True)
    path = manifests_dir / f"{manifest.parent_id}.gate_manifest.json"
    validate_manifest_dict(dataclasses.asdict(manifest))
    payload = json.dumps(dataclasses.asdict(manifest), indent=2)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(manifests_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return path


def read_manifest(path: Path) -> GateManifest:
    """Deserialise from disk. Raises FileNotFoundError, json.JSONDecodeError on bad input."""
    d = json.loads(path.read_text())
    validate_manifest_dict(d)
    # tuple-of-tuples reconstruction for held_out_cells
    held = tuple(tuple(item) for item in d["held_out_cells"])
    return GateManifest(
        parent_id=d["parent_id"],
        created_at=d["created_at"],
        git_committed_at_sha=d["git_committed_at_sha"],
        held_out_cells=held,
        K=d["K"],
        p_threshold=d["p_threshold"],
        bootstrap_reps=d["bootstrap_reps"],
        win_definition=d["win_definition"],
        schema_version=d["schema_version"],
    )


def load_manifest(parent_id: str, manifests_dir: Path) -> GateManifest:
    """Convenience: read by parent_id. Raises FileNotFoundError if absent."""
    path = manifests_dir / f"{parent_id}.gate_manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No manifest for parent_id={parent_id!r} in {manifests_dir}"
        )
    return read_manifest(path)


def retire_manifest(
    parent_id: str,
    reason: str,
    manifests_dir: Path,
    git_root: Path,
) -> str:
    """Rename active manifest to .retired.gate_manifest.json with reason + commit.

    Returns the retire commit SHA.

    Rollback discipline: if git commit fails, the active manifest is RESTORED from
    the in-memory cached payload and the retired file is removed. NEVER git checkout
    (Leo memory: feedback_never_blind_checkout — checkout silently destroys
    uncommitted work).
    """
    active = manifests_dir / f"{parent_id}.gate_manifest.json"
    retired = manifests_dir / f"{parent_id}.retired.gate_manifest.json"
    if not active.exists():
        raise FileNotFoundError(f"No active manifest at {active}")
    if retired.exists():
        raise FileExistsError(
            f"Retired manifest already exists at {retired}; "
            f"a parent_id can only be retired once"
        )

    # Read active payload and add retirement annotations
    d = json.loads(active.read_text())
    d["retired_reason"] = reason
    d["retired_at"] = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(d, indent=2)

    # Write retired file atomically
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(manifests_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as fh:
            fh.write(payload)
        os.replace(tmp_path, str(retired))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Cache the active manifest's payload BEFORE we unlink — needed for rollback
    # if the subsequent git commit fails (state-consistency: never leave working
    # tree in active-gone-retired-uncommitted half-state).
    active_payload_for_rollback = active.read_text()
    active.unlink()  # working-tree only — NEVER git rm

    # Commit the rename via git
    msg = f"gate: retire manifest for {parent_id} ({reason!r})"
    try:
        subprocess.run(
            ["git", "add", str(active), str(retired)],
            cwd=git_root, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=git_root, check=True, capture_output=True, text=True,
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_root, check=True, capture_output=True, text=True,
        ).stdout.strip()
        return sha
    except subprocess.CalledProcessError as exc:
        # Roll back to pre-retire state: restore active from cached payload,
        # remove retired. Per Leo memory feedback_never_blind_checkout: NO `git
        # checkout` — we restore from the in-memory cached payload to avoid
        # silently destroying any uncommitted operator work.
        try:
            active.write_text(active_payload_for_rollback)
            retired.unlink(missing_ok=True)
        except OSError:
            pass  # best-effort; raise the original error below
        raise RuntimeError(
            f"git commit failed during retire: {exc.stderr}; "
            f"working tree restored to pre-retire state"
        ) from exc


def write_manifest_committed(
    manifest: GateManifest,
    manifests_dir: Path,
    git_root: Path,
) -> str:
    """Atomic write + git stage + git commit, in one operation.

    Returns the resulting commit SHA. On git failure, the manifest file is
    REMOVED from the working tree via path.unlink() — NEVER `git checkout`
    (Leo memory: feedback_never_blind_checkout — checkout silently destroys
    uncommitted work).

    Refuses to overwrite an existing manifest (D-138 #5). To re-register,
    operator must run retire_manifest() first.
    """
    manifests_dir.mkdir(parents=True, exist_ok=True)
    path = manifests_dir / f"{manifest.parent_id}.gate_manifest.json"

    if path.exists():
        raise FileExistsError(
            f"Manifest already exists: {path}. Run "
            f"`automil gate retire-manifest {manifest.parent_id} --reason '...'` first."
        )

    # 1. Atomic write (write_manifest already validates the dict)
    write_manifest(manifest, manifests_dir)

    # 2. git add + git commit; rollback via path.unlink() on failure
    try:
        subprocess.run(
            ["git", "add", str(path)],
            cwd=git_root, check=True, capture_output=True, text=True,
        )
        msg = (
            f"gate: register manifest for {manifest.parent_id} "
            f"(held_out: {len(manifest.held_out_cells)} cells, "
            f"K={manifest.K}, p<{manifest.p_threshold})"
        )
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=git_root, check=True, capture_output=True, text=True,
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_root, check=True, capture_output=True, text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        # Rollback: remove the working-tree file. NEVER git checkout
        # (Leo memory: feedback_never_blind_checkout silently destroys
        # uncommitted work).
        try:
            path.unlink()
        except OSError:
            pass
        raise RuntimeError(
            f"git commit failed; manifest file removed: {exc.stderr}"
        ) from exc

    # 3. D-138 #4: backfill git_committed_at_sha via SECOND commit (no amend —
    # preserving the pre-registration timestamp in git history)
    if manifest.git_committed_at_sha == "PENDING":
        updated = dataclasses.replace(manifest, git_committed_at_sha=sha)
        payload = json.dumps(dataclasses.asdict(updated), indent=2)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(manifests_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as fh:
                fh.write(payload)
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        try:
            subprocess.run(
                ["git", "add", str(path)],
                cwd=git_root, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "commit", "-m",
                 f"gate: backfill commit SHA for {manifest.parent_id}"],
                cwd=git_root, check=True, capture_output=True, text=True,
            )
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=git_root, check=True, capture_output=True, text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "SHA backfill commit failed for %s: %s; manifest stays with PENDING. "
                "Recover via `automil gate register-manifest %s --force-recover` "
                "(future enhancement).",
                manifest.parent_id, exc.stderr, manifest.parent_id,
            )

    return sha
