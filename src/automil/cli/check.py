"""check command: validate project setup before running experiments."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import click
import yaml

from automil.cli import main
from automil.cli._helpers import _find_automil_dir, _find_git_root


@main.command()
def check():
    """Validate project setup before running experiments."""
    git_root = _find_git_root()
    adir = _find_automil_dir()
    issues = []
    warnings = []

    # Check config.yaml
    config_path = adir / "config.yaml"
    config: dict = {}
    if not config_path.exists():
        issues.append("automil/config.yaml not found. Run 'automil init' first.")
    else:
        config = yaml.safe_load(config_path.read_text()) or {}

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

    # CLN-05: report the resolved nvidia-smi path so operators can see whether
    # path pinning is in effect (D-18). The constant is set at orchestrator.py
    # module import via shutil.which('nvidia-smi') — see Plan 03.
    from automil.orchestrator import NVIDIA_SMI_PATH

    if NVIDIA_SMI_PATH != "nvidia-smi":
        click.echo(f"nvidia-smi: {NVIDIA_SMI_PATH}")
    else:
        click.echo("nvidia-smi: bare PATH lookup (path detection failed)")

    # CLN-02 / D-04 / D-06: surface the subprocess env whitelist so the operator
    # knows exactly what experiment processes will receive. Hardcoded system
    # whitelist comes from the orchestrator module; per-project passthrough is
    # read fresh from the config we already loaded above.
    from automil.orchestrator import (
        _SYSTEM_ENV_WHITELIST_LITERAL,
        _SYSTEM_ENV_WHITELIST_PREFIX,
    )

    literal_list = ", ".join(sorted(_SYSTEM_ENV_WHITELIST_LITERAL))
    prefix_list = ", ".join(f"{p}*" for p in _SYSTEM_ENV_WHITELIST_PREFIX)
    click.echo(f"env whitelist (system, literal): {literal_list}")
    click.echo(f"env whitelist (system, prefix-glob): {prefix_list}")

    passthrough: list[str] = []
    env_section = (config or {}).get("env") or {}
    raw_pt = env_section.get("passthrough", []) or []
    if isinstance(raw_pt, list):
        passthrough = [str(k) for k in raw_pt]
    else:
        warnings.append(
            f"config.yaml: env.passthrough must be a list of var names; "
            f"got {type(raw_pt).__name__} — ignoring."
        )
    if passthrough:
        click.echo("env.passthrough:")
        for key in passthrough:
            present = "OK" if key in os.environ else "MISSING"
            click.echo(f"  {key}: passthrough {present}")
    else:
        click.echo("env.passthrough: (none declared)")

    # --- Phase 1 registry checks (REG-04 / REG-05 / D-46) ---
    from automil.registry.config import load_registry_config
    from automil.registry.scanner import scan_variants
    from automil.registry._state import _clear_registry
    from automil.registry.manifest import Manifest

    reg_cfg = load_registry_config(adir)

    # Protected-files dirty check (REG-05 / D-34): both staged and unstaged dirty fail.
    if reg_cfg.protected:
        try:
            git_status = subprocess.run(
                ["git", "status", "--porcelain", "--"] + list(reg_cfg.protected),
                cwd=git_root, capture_output=True, text=True, timeout=10,
            )
            dirty_lines = [ln for ln in git_status.stdout.splitlines() if ln.strip()]
            if dirty_lines:
                issues.append(
                    "registry.protected paths dirty in working tree:\n      "
                    + "\n      ".join(dirty_lines[:20])
                    + (
                        f"\n      ... ({len(dirty_lines) - 20} more)"
                        if len(dirty_lines) > 20 else ""
                    )
                    + "\n      Run `automil revert-baseline` to reset, or "
                    "commit the changes to a variant module via "
                    "`automil port-variant <node_id>`."
                )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            warnings.append(
                "Could not run `git status` for protected files — "
                "git may not be on PATH."
            )

    # Registry consistency (D-46).
    variants_root = adir / "variants"
    if variants_root.exists():
        _clear_registry()  # avoid pollution from prior CLI calls in same process
        scan_result = scan_variants(variants_root)
        for path, exc_str in scan_result.failed:
            issues.append(f"Variant module {path} failed import: {exc_str}")
        for var_path in scan_result.imported:
            manifest_path = var_path.with_suffix(".json")
            if not manifest_path.exists():
                warnings.append(
                    f"Variant module {var_path} has no sibling manifest "
                    f"({manifest_path.name}). Run `automil port-variant <node_id>` "
                    f"to regenerate, or remove the variant module."
                )
                continue
            try:
                manifest = Manifest.read(manifest_path)
            except (ValueError, FileNotFoundError) as e:
                issues.append(f"Manifest {manifest_path} invalid: {e}")
                continue
            ok, reason = manifest.cross_check_with_module(var_path)
            if not ok:
                issues.append(
                    f"Manifest {manifest_path.name} mismatches docstring of "
                    f"{var_path.name}: {reason}"
                )

    # Repro manifest (D-40 / D-46): warn-not-fail if missing or stale.
    repro_path = adir / "repro_manifest.yaml"
    if not repro_path.exists():
        warnings.append(
            "automil/repro_manifest.yaml not found. Run "
            "`automil verify-repro <node_id>` after porting variants to "
            "generate the reproduction-sanity report."
        )
    else:
        if variants_root.exists():
            max_var_mtime = 0.0
            for p in variants_root.rglob("*.py"):
                try:
                    mt = p.stat().st_mtime
                    if mt > max_var_mtime:
                        max_var_mtime = mt
                except OSError:
                    continue
            try:
                repro_mtime = repro_path.stat().st_mtime
                if max_var_mtime > repro_mtime:
                    warnings.append(
                        "automil/repro_manifest.yaml is older than the newest "
                        "variant module. Run `automil verify-repro <node_id>` "
                        "to refresh."
                    )
            except OSError:
                pass

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
