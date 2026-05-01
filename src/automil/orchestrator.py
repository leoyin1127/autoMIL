"""autoMIL Experiment Orchestrator.

Background daemon that watches a queue directory for experiment specs,
schedules them across GPUs using best-fit bin packing with priority,
manages process lifecycles via git worktree isolation, and archives results.

Usage:
    automil start    # Start daemon
    automil status   # Show status
    automil stop     # Graceful stop
    automil submit spec.json  # Submit experiment
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values

from automil.runner import Runner

# ---------------------------------------------------------------------------
# Defaults (overridden by config.yaml orchestrator section)
# ---------------------------------------------------------------------------
POLL_INTERVAL_SEC = 5
SAFETY_MARGIN_GB = 2.0
DEFAULT_TIMEOUT_MIN = 150
# Saturate GPUs by default: the orchestrator's job is to pack experiments
# until VRAM runs out, not to run them serially. Projects whose workloads
# are heavier should override via config.yaml → orchestrator.max_concurrent_per_gpu.
MAX_CONCURRENT_PER_GPU = 8
DEFAULT_VRAM_ESTIMATE_GB = 1.0

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# nvidia-smi path pinning (CLN-05)
# ---------------------------------------------------------------------------
# Resolve nvidia-smi's absolute path once at module import. On a shared host a
# PATH-shim could otherwise return spoofed VRAM numbers and trick the
# bin-packer (CONCERNS.md §"nvidia-smi invocation has no path pinning"). If
# detection fails we fall back to bare PATH lookup with a WARN — never silent
# (D-18). Resolution happens here (module-level), not on every query_gpus
# call, so the cost is paid once and tests can re-resolve via importlib.reload.
_resolved_nvidia_smi = shutil.which("nvidia-smi")
NVIDIA_SMI_PATH = _resolved_nvidia_smi or "nvidia-smi"
if _resolved_nvidia_smi:
    logger.info("nvidia-smi resolved to %s", NVIDIA_SMI_PATH)
else:
    logger.warning(
        "nvidia-smi not found via shutil.which; falling back to bare PATH lookup. "
        "GPU state may be unreliable on hosts with shimmed PATH."
    )


def _find_automil_dir() -> Path:
    """Walk up from cwd to find automil/config.yaml. Returns the automil/ dir."""
    p = Path.cwd()
    while p != p.parent:
        if (p / "automil" / "config.yaml").exists():
            return p / "automil"
        p = p.parent
    raise RuntimeError(
        "No automil/config.yaml found. Run 'automil init' in your project root."
    )


def _find_git_root(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) to find the git repo root."""
    p = (start or Path.cwd()).resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    raise RuntimeError("Not inside a git repository.")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class GPUInfo:
    index: int
    total_mb: int
    free_mb: int
    utilization: int

    @property
    def free_gb(self) -> float:
        return self.free_mb / 1024


@dataclass
class RunningExperiment:
    id: str
    spec: dict
    gpu: int
    process: subprocess.Popen
    log_file: object  # file handle
    log_path: Path
    started_at: float
    timeout_at: float
    estimated_vram_gb: float


# ---------------------------------------------------------------------------
# GPU monitoring
# ---------------------------------------------------------------------------
def query_gpus() -> list[GPUInfo]:
    """Query nvidia-smi for GPU state.

    Uses the path resolved at module import (NVIDIA_SMI_PATH) to defend
    against PATH-shim spoofing on shared hosts (CLN-05).
    """
    try:
        result = subprocess.run(
            [
                NVIDIA_SMI_PATH,
                "--query-gpu=index,memory.total,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpus.append(GPUInfo(
                    index=int(parts[0]),
                    total_mb=int(parts[1]),
                    free_mb=int(parts[2]),
                    utilization=int(parts[3]),
                ))
        return gpus
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.warning(f"nvidia-smi failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class ExperimentOrchestrator:
    """Schedules and manages experiment lifecycle across GPUs."""

    def __init__(self, project_root: Path | None = None,
                 automil_dir: Path | None = None):
        self.automil_dir = automil_dir or _find_automil_dir()
        self.project_root = project_root or _find_git_root()
        self.orch_dir = self.automil_dir / "orchestrator"
        self.queue_dir = self.orch_dir / "queue"
        self.running_dir = self.orch_dir / "running"
        self.archive_dir = self.orch_dir / "archive"
        self.completed_dir = self.orch_dir / "completed"
        self.results_tsv = self.automil_dir / "results.tsv"
        self.pid_file = self.orch_dir / "orchestrator.pid"
        self.log_file = self.orch_dir / "orchestrator.log"
        self.gpu_state_file = self.orch_dir / "gpu_state.json"

        self.runner = Runner(self.project_root)

        # Load config
        config_path = self.automil_dir / "config.yaml"
        if config_path.exists():
            try:
                import yaml
                self.config = yaml.safe_load(config_path.read_text())
            except ImportError:
                self.config = self._parse_yaml_fallback(config_path)
        else:
            self.config = {}

        # Run script config
        run_config = self.config.get("run", {}) if self.config else {}
        self.run_script = run_config.get("script", "train.py")
        self.run_command = run_config.get("command")

        orch_cfg = self.config.get("orchestrator", {}) if self.config else {}
        self.poll_interval = orch_cfg.get("poll_interval_sec", POLL_INTERVAL_SEC)
        self.safety_margin_gb = orch_cfg.get("safety_margin_gb", SAFETY_MARGIN_GB)
        self.default_timeout = orch_cfg.get("default_timeout_min", DEFAULT_TIMEOUT_MIN)
        self.max_per_gpu = orch_cfg.get("max_concurrent_per_gpu", MAX_CONCURRENT_PER_GPU)
        self.default_vram = orch_cfg.get("default_vram_estimate_gb", DEFAULT_VRAM_ESTIMATE_GB)

        # Runtime state
        self.running: dict[str, RunningExperiment] = {}
        self.gpu_allocations: dict[int, list[str]] = {}
        self.counter = 0
        self.draining = False
        self._shutdown = False
        self._timed_out: dict[str, bool] = {}

        # Detect GPUs
        gpus = query_gpus()
        for g in gpus:
            self.gpu_allocations[g.index] = []
        if not self.gpu_allocations:
            logger.warning("No GPUs detected, using GPU 0 as fallback")
            self.gpu_allocations[0] = []

        # Load .env from project root so worktree processes inherit env vars
        # (worktrees don't contain .env since it's typically gitignored)
        self._load_dotenv()

        # Ensure directories
        for d in (self.queue_dir, self.running_dir, self.archive_dir, self.completed_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Load persisted state (don't recover orphans until run() is called)
        self._load_state(recover=False)

    @staticmethod
    def _parse_yaml_fallback(config_path: Path) -> dict:
        """Minimal YAML parsing when PyYAML is not installed."""
        lines = config_path.read_text().splitlines()
        orch: dict = {}
        in_orch = False
        for line in lines:
            if line.strip() == "orchestrator:":
                in_orch = True
                continue
            if in_orch:
                if line and not line[0].isspace():
                    break
                parts = line.strip().split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    try:
                        orch[key] = float(val) if "." in val else int(val)
                    except ValueError:
                        orch[key] = val
        return {"orchestrator": orch}

    def _load_dotenv(self) -> None:
        """Load .env files from the project root into os.environ.

        Worktrees are detached git checkouts and don't contain .env
        (which is typically gitignored). Loading here ensures the
        orchestrator's child processes inherit the variables.

        Uses python-dotenv so quoted values, the ``export`` prefix, and
        inline ``# comments`` after unquoted values are handled
        correctly (CLN-03; see CONCERNS.md §"Naive .env parser").
        Pre-existing entries in ``os.environ`` are preserved
        (``setdefault`` semantic) — the shell wins over the file.
        """
        candidates = [
            self.project_root / ".env",
            self.project_root / "benchmarks" / ".env",
        ]
        for env_file in candidates:
            if not env_file.is_file():
                continue
            parsed = dotenv_values(env_file)
            for key, value in parsed.items():
                if value is None:
                    continue
                # Don't override existing env vars (preserves prior semantic).
                if key not in os.environ:
                    os.environ[key] = value
                    logger.debug("Loaded env var %s from %s", key, env_file)

    # --- State persistence ---

    def _load_state(self, recover: bool = True):
        """Load counter from persisted state. Only recover orphans if requested."""
        if self.gpu_state_file.exists():
            try:
                state = json.loads(self.gpu_state_file.read_text())
                self.counter = state.get("counter", 0)
            except (json.JSONDecodeError, KeyError):
                pass

        if recover:
            self._recover_orphans()

    def _save_state(self):
        """Persist GPU state and counters to disk."""
        gpus = query_gpus()
        gpu_data = {}
        for g in gpus:
            running_on = self.gpu_allocations.get(g.index, [])
            alloc_vram = sum(
                self.running[eid].estimated_vram_gb
                for eid in running_on
                if eid in self.running
            )
            gpu_data[str(g.index)] = {
                "total_mb": g.total_mb,
                "free_mb": g.free_mb,
                "schedulable_free_gb": round(g.free_gb - self.safety_margin_gb - alloc_vram, 1),
                "running": running_on,
                "utilization_pct": g.utilization,
            }

        state = {
            "counter": self.counter,
            "last_updated": datetime.now().isoformat(),
            "gpus": gpu_data,
            "queue_depth": len(list(self.queue_dir.glob("*.json"))),
            "total_running": len(self.running),
            "total_completed": len(list(self.completed_dir.glob("*.json"))),
        }
        self.gpu_state_file.write_text(json.dumps(state, indent=2) + "\n")

    def _recover_orphans(self):
        """Mark orphaned running experiments as crashed and clean up worktrees."""
        if not self.running_dir.exists():
            return
        for f in self.running_dir.glob("*.json"):
            try:
                spec = json.loads(f.read_text())
                node_id = spec.get("id", f.stem)
                logger.info(f"Orphaned experiment {node_id} found, marking as crashed")

                archive = self.archive_dir / node_id
                archive.mkdir(parents=True, exist_ok=True)
                result = {"status": "crash", "error": "Orchestrator restarted while running"}
                (archive / "result.json").write_text(json.dumps(result, indent=2))
                (self.completed_dir / f"{node_id}.json").write_text(json.dumps({
                    "id": node_id,
                    "status": "crash",
                    "completed_at": datetime.now().isoformat(),
                }, indent=2))

                f.unlink()

                wt = self.runner.worktree_path(node_id)
                if wt.exists():
                    self.runner.cleanup_worktree(wt)
            except Exception:
                continue

    # --- Scheduling ---

    def _get_pending(self) -> list[dict]:
        """Read and sort pending experiments from queue."""
        pending = []
        for f in sorted(self.queue_dir.glob("*.json")):
            try:
                spec = json.loads(f.read_text())
                spec["_file"] = f
                pending.append(spec)
            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"Bad spec {f}: {e}")
        # Sort by priority ASC, then submitted_at ASC
        pending.sort(key=lambda s: (s.get("priority", 2), s.get("submitted_at", "")))
        return pending

    def _find_best_gpu(self, needed_gb: float) -> int | None:
        """Best-fit bin packing: find GPU with least free VRAM that still fits."""
        gpus = query_gpus()
        candidates = []

        for g in gpus:
            running_on = self.gpu_allocations.get(g.index, [])
            if len(running_on) >= self.max_per_gpu:
                continue
            alloc_vram = sum(
                self.running[eid].estimated_vram_gb
                for eid in running_on
                if eid in self.running
            )
            schedulable = g.free_gb - self.safety_margin_gb - alloc_vram
            if schedulable >= needed_gb:
                candidates.append((g.index, schedulable))

        if not candidates:
            return None

        # Best-fit: pick GPU with LEAST schedulable free (tightest fit)
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def _pre_launch_check(self, gpu_id: int, needed_gb: float) -> bool:
        """Final VRAM check right before launch."""
        gpus = query_gpus()
        for g in gpus:
            if g.index == gpu_id:
                return g.free_gb >= needed_gb + self.safety_margin_gb
        return False

    # --- Experiment lifecycle ---

    def _launch(self, spec: dict, gpu_id: int):
        """Launch an experiment in an isolated git worktree."""
        node_id = spec["id"]
        archive = self.archive_dir / node_id
        archive.mkdir(parents=True, exist_ok=True)

        # Save spec (without internal keys)
        spec_clean = {k: v for k, v in spec.items() if k not in ("_file",)}
        (archive / "spec.json").write_text(json.dumps(spec_clean, indent=2))

        # Remove from queue before attempting launch (prevents infinite retry)
        src_file = spec.get("_file")
        if src_file and Path(src_file).exists():
            Path(src_file).unlink()

        base_commit = spec.get("base_commit", "HEAD")
        try:
            wt_path = self.runner.create_worktree(base_commit, node_id)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create worktree for {node_id}: {e}")
            self._mark_crashed(node_id, spec, f"Worktree creation failed: {e}")
            return

        overlay_dir = spec.get("overlay_dir")
        deletions = spec.get("deletions")
        if overlay_dir:
            self.runner.apply_overlay(
                wt_path, self.orch_dir / overlay_dir, deletions=deletions
            )

        # CUDA_VISIBLE_DEVICES masks physical GPU; logical device is always 0
        # AUTOMIL_RESULTS_DIR points to this experiment's archive dir so that
        # training scripts write per-fold checkpoints/metrics there (not /tmp,
        # not the shared benchmark_dir which would cache across experiments).
        #
        # AUTOBENCH_ROOT + PYTHONPATH force the `autobench` package (and its
        # LIB_ROOT) to resolve inside the worktree. Without this the editable
        # `pip install -e .` pointer in the parent env wins and overlays under
        # benchmarks/src/autobench/ or benchmarks/lib/ are silently ignored.
        worktree_benchmarks = wt_path / "benchmarks"
        worktree_src = worktree_benchmarks / "src"
        existing_pp = os.environ.get("PYTHONPATH", "")
        pythonpath = (
            f"{worktree_src}{os.pathsep}{existing_pp}" if existing_pp else str(worktree_src)
        )
        env = {
            **os.environ,
            "CUDA_VISIBLE_DEVICES": str(gpu_id),
            "AUTOMIL_GPU": "0",
            "AUTOMIL_DESC": spec.get("description", ""),
            "AUTOMIL_NODE_ID": node_id,
            "AUTOMIL_RESULTS_DIR": str(archive.resolve()),
            "AUTOBENCH_ROOT": str(worktree_benchmarks.resolve()),
            "PYTHONPATH": pythonpath,
        }
        for k, v in spec.get("env", {}).items():
            if k not in ("AUTOMIL_GPU", "CUDA_VISIBLE_DEVICES"):
                env[k] = str(v)

        log_path = archive / "run.log"
        log_fh = open(log_path, "w")
        try:
            if self.run_command:
                cmd = shlex.split(self.run_command)
            else:
                cmd = [sys.executable, self.run_script]
            process = subprocess.Popen(
                cmd,
                cwd=str(wt_path),
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
        except Exception as e:
            log_fh.close()
            logger.error(f"Failed to launch {node_id}: {e}")
            self._mark_crashed(node_id, spec, str(e))
            self.runner.cleanup_worktree(wt_path)
            return

        timeout_min = spec.get("timeout_min", self.default_timeout)
        estimated_vram = spec.get("estimated_vram_gb", self.default_vram)

        self.running[node_id] = RunningExperiment(
            id=node_id,
            spec=spec,
            gpu=gpu_id,
            process=process,
            log_file=log_fh,
            log_path=log_path,
            started_at=time.time(),
            timeout_at=time.time() + timeout_min * 60,
            estimated_vram_gb=estimated_vram,
        )
        self.gpu_allocations.setdefault(gpu_id, []).append(node_id)

        # Copy spec to running dir for orphan recovery
        import shutil
        running_spec = self.running_dir / f"{node_id}.json"
        shutil.copy2(archive / "spec.json", running_spec)

        logger.info(
            f"Launched {node_id} on GPU {gpu_id} "
            f"(PID {process.pid}, est. {estimated_vram}GB, timeout {timeout_min}min)"
        )

    def _check_running(self):
        """Poll running experiments for completion or timeout."""
        for exp_id, exp in list(self.running.items()):
            retcode = exp.process.poll()
            if retcode is not None:
                self._handle_completion(exp_id, retcode)
            elif time.time() > exp.timeout_at:
                self._handle_timeout(exp_id)

    def _handle_completion(self, node_id: str, returncode: int):
        """Process a completed experiment: collect results, write TSV, clean up."""
        exp = self.running.pop(node_id)
        if exp.gpu in self.gpu_allocations:
            try:
                self.gpu_allocations[exp.gpu].remove(node_id)
            except ValueError:
                pass

        exp.log_file.close()
        elapsed_s = time.time() - exp.started_at
        archive = self.archive_dir / node_id
        wt_path = self.runner.worktree_path(node_id)
        gpu_id = exp.gpu
        spec = exp.spec

        # Try to collect result.json from worktree
        result = self.runner.collect_result(wt_path, archive)

        if result is None:
            log_text = (archive / "run.log").read_text() if (archive / "run.log").exists() else ""
            if "CUDA out of memory" in log_text or "OutOfMemoryError" in log_text:
                status = "oom"
            elif self._timed_out.get(node_id):
                status = "timeout"
            elif returncode != 0:
                status = "crash"
            else:
                status = "completed"

            error_tail = log_text[-2000:] if status != "completed" else ""
            result = {"status": status}
            if error_tail:
                result["error"] = error_tail
            (archive / "result.json").write_text(json.dumps(result, indent=2))

        if "status" not in result:
            result["status"] = "completed" if returncode == 0 else "crash"

        # Write completion notification with all fields reconcile needs
        completion = {
            "id": node_id,
            "status": result.get("status", "completed"),
            "composite": result.get("composite", 0),
            "metrics": result.get("metrics", {}),
            "elapsed_seconds": result.get("elapsed_seconds", elapsed_s),
            "peak_vram_mb": result.get("peak_vram_mb", 0),
            "gpu": gpu_id,
            "completed_at": datetime.now().isoformat(),
            "graph_metadata": result.get("graph_metadata") or spec.get("graph_metadata") or {},
        }

        # Include error details in completion for better agent visibility
        status = result.get("status", "completed")
        if status in ("crash", "oom", "timeout"):
            log_path = archive / "run.log"
            error_tail = ""
            if log_path.exists():
                lines = log_path.read_text().splitlines()
                error_tail = "\n".join(lines[-20:])
            completion["error"] = error_tail
            completion["log_location"] = str(log_path)

        (self.completed_dir / f"{node_id}.json").write_text(
            json.dumps(completion, indent=2) + "\n"
        )

        # Append to results.tsv (sole writer)
        self._append_results_tsv(node_id, result, description=spec.get("description", ""))

        # Clean running spec
        running_spec = self.running_dir / f"{node_id}.json"
        if running_spec.exists():
            running_spec.unlink()

        # Cleanup worktree
        if wt_path.exists():
            self.runner.cleanup_worktree(wt_path)

        # Clear timeout flag
        self._timed_out.pop(node_id, None)

        status_str = result.get("status", "unknown")
        composite = result.get("composite", 0)
        logger.info(
            f"Completed {node_id}: status={status_str}, "
            f"composite={composite:.4f}, elapsed={elapsed_s / 60:.1f}min, GPU {gpu_id}"
        )

    def _handle_timeout(self, exp_id: str):
        """Terminate a timed-out experiment and its full process group.

        Children launched via start_new_session=True live in their own
        process group, so killing the parent alone leaks DataLoader
        workers and CUDA contexts (they reparent to PID 1 and keep VRAM).
        Signal the whole group instead.
        """
        exp = self.running[exp_id]
        pid = exp.process.pid
        logger.warning(f"Timeout for {exp_id}, killing PID {pid} and process group")
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(5)
        if exp.process.poll() is None:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._timed_out[exp_id] = True
        self._handle_completion(exp_id, returncode=-9)

    def _mark_crashed(self, node_id: str, spec: dict, error: str):
        """Mark an experiment as crashed without a running process."""
        archive = self.archive_dir / node_id
        archive.mkdir(parents=True, exist_ok=True)

        result = {
            "id": node_id,
            "description": spec.get("description", ""),
            "status": "crash",
            "error": error,
            "completed_at": datetime.now().isoformat(),
        }
        if "graph_metadata" in spec:
            result["graph_metadata"] = spec["graph_metadata"]

        (archive / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        spec_clean = {k: v for k, v in spec.items() if k not in ("_file",)}
        (archive / "spec.json").write_text(json.dumps(spec_clean, indent=2) + "\n")
        (self.completed_dir / f"{node_id}.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )

    def _append_results_tsv(self, node_id: str, result: dict, description: str = ""):
        """Append a row to results.tsv (sole writer, no locking needed)."""
        metrics = result.get("metrics", {})
        composite = result.get("composite", 0.0)
        status = result.get("status", "completed")
        elapsed_s = result.get("elapsed_seconds", 0)
        vram_mb = result.get("peak_vram_mb", 0)

        header = "node_id\tval_auc\tval_bacc\ttest_auc\ttest_bacc\tcomposite\tvram_gb\telapsed_min\tstatus\tdescription\n"
        if not self.results_tsv.exists() or self.results_tsv.stat().st_size == 0:
            self.results_tsv.write_text(header)

        row = "\t".join([
            node_id,
            f"{metrics.get('val_auc', 0):.4f}",
            f"{metrics.get('val_bacc', 0):.4f}",
            f"{metrics.get('test_auc', 0):.4f}",
            f"{metrics.get('test_bacc', 0):.4f}",
            f"{composite:.6f}",
            f"{vram_mb / 1024:.1f}",
            f"{elapsed_s / 60:.1f}",
            status,
            description or node_id,
        ])
        with open(self.results_tsv, "a") as f:
            f.write(row + "\n")

    # --- Main loop ---

    def _reload_orchestrator_config(self) -> None:
        """Hot-reload the orchestrator section of config.yaml each tick.

        Lets an operator raise/lower concurrency and VRAM estimates live
        without restarting the daemon (which would orphan running jobs).
        Only the orchestrator.* section is reloaded; other sections are
        not used after construction.
        """
        config_path = self.automil_dir / "config.yaml"
        if not config_path.exists():
            return
        try:
            import yaml
            cfg = yaml.safe_load(config_path.read_text()) or {}
        except Exception as e:
            logger.warning(
                f"Config reload skipped: {config_path.name} parse failed ({e}); "
                f"keeping previous values (max_per_gpu={self.max_per_gpu}, "
                f"default_vram={self.default_vram}, safety_margin={self.safety_margin_gb})"
            )
            return
        orch_cfg = (cfg.get("orchestrator") or {}) if isinstance(cfg, dict) else {}
        new_max = orch_cfg.get("max_concurrent_per_gpu", self.max_per_gpu)
        new_vram = orch_cfg.get("default_vram_estimate_gb", self.default_vram)
        new_safety = orch_cfg.get("safety_margin_gb", self.safety_margin_gb)
        if new_max != self.max_per_gpu:
            logger.info(
                f"Config reload: max_concurrent_per_gpu {self.max_per_gpu} -> {new_max}"
            )
            self.max_per_gpu = new_max
        if new_vram != self.default_vram:
            logger.info(
                f"Config reload: default_vram_estimate_gb {self.default_vram} -> {new_vram}"
            )
            self.default_vram = new_vram
        if new_safety != self.safety_margin_gb:
            logger.info(
                f"Config reload: safety_margin_gb {self.safety_margin_gb} -> {new_safety}"
            )
            self.safety_margin_gb = new_safety

    def tick(self):
        """Single scheduling cycle."""
        # 0. Hot-reload config so concurrency bumps take effect live
        self._reload_orchestrator_config()

        # 1. Check running experiments
        self._check_running()

        # 2. Schedule pending experiments (skip if draining)
        if not self.draining:
            pending = self._get_pending()
            for spec in pending:
                if not spec.get("id"):
                    self.counter += 1
                    spec["id"] = f"{self.counter:04d}"

                needed_gb = spec.get("estimated_vram_gb", self.default_vram)
                gpu = self._find_best_gpu(needed_gb)

                if gpu is not None and self._pre_launch_check(gpu, needed_gb):
                    self._launch(spec, gpu)

        # 3. Save state
        self._save_state()

    def run(self):
        """Main daemon loop."""
        self.runner.prune_stale_worktrees()
        self._recover_orphans()

        logger.info(
            f"Orchestrator started. GPUs: {list(self.gpu_allocations.keys())}, "
            f"poll={self.poll_interval}s, safety={self.safety_margin_gb}GB"
        )

        # Signal handlers
        def handle_signal(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"Received {sig_name}, shutting down gracefully...")
            self._shutdown = True

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        # Write PID file
        self.pid_file.write_text(str(os.getpid()) + "\n")

        try:
            while not self._shutdown:
                try:
                    self.tick()
                except Exception as e:
                    logger.error(f"Tick error: {e}", exc_info=True)
                time.sleep(self.poll_interval)

            # Graceful shutdown: wait for running experiments
            if self.running:
                logger.info(f"Waiting for {len(self.running)} running experiments...")
                self.draining = True
                while self.running:
                    self._check_running()
                    time.sleep(5)
                logger.info("All experiments completed, exiting.")
        finally:
            if self.pid_file.exists():
                self.pid_file.unlink()
            self._save_state()
            logger.info("Orchestrator stopped.")

    # --- CLI commands (instance methods) ---

    def cmd_start(self):
        """Start the orchestrator daemon."""
        if self.pid_file.exists():
            pid = int(self.pid_file.read_text().strip())
            try:
                os.kill(pid, 0)
                print(f"Orchestrator already running (PID {pid})")
                return
            except OSError:
                self.pid_file.unlink()

        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(),
            ],
        )

        self.run()

    def cmd_status(self):
        """Print orchestrator status."""
        if self.pid_file.exists():
            pid = int(self.pid_file.read_text().strip())
            try:
                os.kill(pid, 0)
                print(f"Orchestrator: RUNNING (PID {pid})")
            except OSError:
                print("Orchestrator: DEAD (stale PID file)")
        else:
            print("Orchestrator: NOT RUNNING")

        # GPU state
        if self.gpu_state_file.exists():
            state = json.loads(self.gpu_state_file.read_text())
            print(f"\nLast updated: {state.get('last_updated', 'unknown')}")
            print(f"Queue depth: {state.get('queue_depth', 0)}")
            print(f"Running: {state.get('total_running', 0)}")
            print(f"Completed: {state.get('total_completed', 0)}")
            print(f"Counter: {state.get('counter', 0)}")
            print("\nGPUs:")
            for idx, gpu in sorted(state.get("gpus", {}).items()):
                running_ids = gpu.get("running", [])
                sched = gpu.get("schedulable_free_gb", 0)
                util = gpu.get("utilization_pct", 0)
                print(f"  GPU {idx}: {sched:.1f}GB schedulable, {util}% util, running={running_ids}")
        else:
            gpus = query_gpus()
            print("\nGPUs (live):")
            for g in gpus:
                print(f"  GPU {g.index}: {g.free_gb:.1f}GB free, {g.utilization}% util")

        # Queue
        pending = list(self.queue_dir.glob("*.json"))
        if pending:
            print(f"\nPending ({len(pending)}):")
            for f in sorted(pending):
                try:
                    spec = json.loads(f.read_text())
                    print(f"  {f.name}: {spec.get('description', '?')[:60]} (P{spec.get('priority', '?')})")
                except Exception:
                    print(f"  {f.name}: (unreadable)")

    def cmd_stop(self):
        """Stop the orchestrator gracefully."""
        if not self.pid_file.exists():
            print("Orchestrator not running")
            return
        pid = int(self.pid_file.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to PID {pid}")
        except OSError as e:
            print(f"Failed to stop: {e}")
            self.pid_file.unlink()

    def cmd_submit(self, spec_path: str):
        """Submit an experiment spec to the queue."""
        src = Path(spec_path)
        if not src.exists():
            print(f"File not found: {spec_path}")
            sys.exit(1)

        spec = json.loads(src.read_text())
        if not spec.get("id"):
            # Auto-assign ID from counter
            counter = 0
            if self.gpu_state_file.exists():
                try:
                    counter = json.loads(self.gpu_state_file.read_text()).get("counter", 0)
                except Exception:
                    pass
            counter += 1
            spec["id"] = f"{counter:04d}"

        if not spec.get("submitted_at"):
            spec["submitted_at"] = datetime.now().isoformat()

        dst = self.queue_dir / f"{spec['id']}.json"
        dst.write_text(json.dumps(spec, indent=2) + "\n")
        print(f"Submitted experiment {spec['id']}: {spec.get('description', '?')}")


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    # For status/stop/submit, we just need path resolution, not GPU init.
    # Construct orchestrator instance.
    orch = ExperimentOrchestrator()

    if cmd == "start":
        orch.cmd_start()
    elif cmd == "status":
        orch.cmd_status()
    elif cmd == "stop":
        orch.cmd_stop()
    elif cmd == "submit":
        if len(sys.argv) < 3:
            print("Usage: automil submit <spec.json>")
            sys.exit(1)
        orch.cmd_submit(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
