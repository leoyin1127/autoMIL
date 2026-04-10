"""Experiment graph: directed tree tracking for multi-branch exploration.

Provides atomic read/write to graph.json. The agent is the sole writer.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
import tokenize
from datetime import datetime
from pathlib import Path


class ExperimentGraph:
    DEFAULT_TECHNIQUE_MAP: dict[str, str] = {
        "no_inst": "no_inst_eval", "focal": "focal_g1", "gamma1": "focal_g1",
        "gc05": "grad_clip", "gc0.5": "grad_clip", "rdrop": "rdrop",
        "step_lr": "step_lr", "coord_pe": "coord_pe", "noise001": "noise_aug",
        "d0.1": "dropout_01", "big": "big_model", "bw0.5": "bag_weight_05",
        "trans_mil": "trans_mil", "dtfd": "dtfd_mil", "ilra": "ilra_mil",
        "vit": "vision_transformer", "ab_mil": "ab_mil", "clam_sb": "clam_sb",
        "uni_v2": "uni_v2", "hibou_l": "hibou_l", "psemix": "psemix",
        "aem": "aem", "variance_pool": "variance_pool", "topk": "topk_attn",
        "maxsoft": "maxsoft", "supcon": "supcon", "attn_temp": "attn_temp",
        "poly1": "poly_loss", "bilevel_lr": "bilevel_lr",
    }

    def __init__(self, path: str | Path, technique_map: dict[str, list[str]] | None = None, data: dict | None = None):
        self.path = Path(path)
        self._technique_map = technique_map if technique_map is not None else self.DEFAULT_TECHNIQUE_MAP
        if data is not None:
            self._data = data
        elif self.path.exists():
            self._data = json.loads(self.path.read_text())
        else:
            self._data = {
                "schema_version": 1,
                "meta": {
                    "best_composite": 0.0,
                    "best_node_id": None,
                    "total_executed": 0,
                    "total_proposed": 0,
                    "next_id": 1,
                    "baseline_composite": 0.0,
                    "scoring": {
                        "exploration_weight": 0.005,
                        "novelty_weight": 0.003,
                    },
                },
                "nodes": {},
                "technique_stats": {},
            }

    @staticmethod
    def load(path: str | Path) -> ExperimentGraph:
        return ExperimentGraph(path=path)

    @property
    def meta(self) -> dict:
        return self._data["meta"]

    @property
    def nodes(self) -> dict:
        return self._data["nodes"]

    @property
    def technique_stats_data(self) -> dict:
        return self._data["technique_stats"]

    # --- ID generation ---
    def next_id(self) -> str:
        nid = self.meta["next_id"]
        self.meta["next_id"] = nid + 1
        return f"node_{nid:04d}"

    # --- Reading ---
    def get_node(self, node_id: str) -> dict | None:
        return self.nodes.get(node_id)

    def best_node(self) -> dict | None:
        best_id = self.meta.get("best_node_id")
        return self.nodes.get(best_id) if best_id else None

    def children(self, node_id: str) -> list[dict]:
        return [n for n in self.nodes.values() if n.get("parent_id") == node_id]

    def lineage(self, node_id: str) -> list[dict]:
        path = []
        current = node_id
        while current:
            node = self.get_node(current)
            if node is None:
                break
            path.append(node)
            current = node.get("parent_id")
        path.reverse()
        return path

    def technique_stats(self, technique: str) -> dict:
        return self.technique_stats_data.get(technique, {
            "times_tried": 0, "best_parent_delta": 0.0, "avg_parent_delta": 0.0,
        })

    # --- Writing ---
    def add_executed(self, parent_id: str | None, description: str,
                     techniques: list[str], metrics: dict,
                     status: str = "discard", commit: str | None = None,
                     config_hash: str | None = None,
                     bootstrapped: bool = False) -> str:
        nid = self.next_id()
        parent = self.get_node(parent_id) if parent_id else None
        parent_composite = parent.get("composite", 0.0) if parent else 0.0
        composite = metrics.get("composite", 0.0)

        node = {
            "id": nid,
            "parent_id": parent_id,
            "type": "executed",
            "status": status,
            "description": description,
            "techniques": techniques,
            "composite": composite,
            "global_delta": metrics.get("global_delta", metrics.get("delta", 0.0)),
            "parent_delta": composite - parent_composite,
            "test_auc": metrics.get("test_auc", 0.0),
            "test_bacc": metrics.get("test_bacc", 0.0),
            "val_auc": metrics.get("val_auc", 0.0),
            "val_bacc": metrics.get("val_bacc", 0.0),
            "vram_gb": metrics.get("vram_gb", 0.0),
            "elapsed_min": metrics.get("elapsed_min", 0.0),
            "gpu": metrics.get("gpu", -1),
            "commit": commit,
            "archive_id": nid,
            "config_hash": config_hash,
            "potential": 0.0,
            "child_count": 0,
            "created_at": datetime.now().isoformat(),
        }
        if bootstrapped:
            node["bootstrapped"] = True

        self.nodes[nid] = node
        self.meta["total_executed"] += 1

        if composite > self.meta["best_composite"]:
            self.meta["best_composite"] = composite
            self.meta["best_node_id"] = nid

        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id]["child_count"] = len(self.children(parent_id))

        self._update_technique_stats(techniques, composite - parent_composite)
        return nid

    def add_proposed(self, parent_id: str, description: str,
                     techniques: list[str], rationale: str = "",
                     reference: str | None = None,
                     expected_gain: str = "low", effort: str = "low",
                     tier: int = 2) -> str:
        nid = self.next_id()
        node = {
            "id": nid,
            "parent_id": parent_id,
            "type": "proposed",
            "status": "pending",
            "description": description,
            "techniques": techniques,
            "tier": tier,
            "rationale": rationale,
            "reference": reference,
            "expected_gain": expected_gain,
            "effort": effort,
            "potential": 0.0,
            "created_at": datetime.now().isoformat(),
        }
        self.nodes[nid] = node
        self.meta["total_proposed"] += 1
        return nid

    def mark_running(self, node_id: str):
        node = self.nodes[node_id]
        assert node["type"] == "proposed" and node["status"] == "pending", \
            f"Cannot mark {node_id} running: type={node['type']}, status={node['status']}"
        node["status"] = "running"

    def promote(self, node_id: str, metrics: dict):
        node = self.nodes[node_id]
        parent = self.get_node(node.get("parent_id")) if node.get("parent_id") else None
        parent_composite = parent.get("composite", 0.0) if parent else 0.0
        composite = metrics.get("composite", 0.0)
        status = metrics.get("status", "discard")

        node["type"] = "executed"
        node["status"] = status
        node["composite"] = composite
        node["global_delta"] = metrics.get("global_delta", metrics.get("delta", 0.0))
        node["parent_delta"] = composite - parent_composite
        node["test_auc"] = metrics.get("test_auc", 0.0)
        node["test_bacc"] = metrics.get("test_bacc", 0.0)
        node["val_auc"] = metrics.get("val_auc", 0.0)
        node["val_bacc"] = metrics.get("val_bacc", 0.0)
        node["vram_gb"] = metrics.get("vram_gb", 0.0)
        node["elapsed_min"] = metrics.get("elapsed_min", 0.0)
        node["gpu"] = metrics.get("gpu", -1)
        node["commit"] = metrics.get("commit")
        node["archive_id"] = node_id
        node["config_hash"] = metrics.get("config_hash")
        node["child_count"] = 0

        self.meta["total_executed"] += 1
        self.meta["total_proposed"] = max(0, self.meta["total_proposed"] - 1)

        if composite > self.meta["best_composite"]:
            self.meta["best_composite"] = composite
            self.meta["best_node_id"] = node_id

        pid = node.get("parent_id")
        if pid and pid in self.nodes:
            self.nodes[pid]["child_count"] = len([
                n for n in self.nodes.values()
                if n.get("parent_id") == pid and n["type"] == "executed"
            ])

        self._update_technique_stats(node.get("techniques", []),
                                     composite - parent_composite)

    def mark_failed(self, node_id: str, status: str, error: str = "",
                    config_hash: str | None = None):
        node = self.nodes[node_id]
        node["type"] = "executed"
        node["status"] = status
        node["composite"] = 0.0
        node["parent_delta"] = 0.0
        node["global_delta"] = 0.0
        node["error"] = error
        node["child_count"] = 0
        node["archive_id"] = node_id
        if config_hash:
            node["config_hash"] = config_hash
        self.meta["total_executed"] += 1
        self.meta["total_proposed"] = max(0, self.meta["total_proposed"] - 1)

    def cancel(self, node_id: str):
        node = self.nodes[node_id]
        node["status"] = "cancelled"
        self.meta["total_proposed"] = max(0, self.meta["total_proposed"] - 1)

    # --- Technique stats ---
    def _update_technique_stats(self, techniques: list[str], parent_delta: float):
        for tech in techniques:
            if tech not in self.technique_stats_data:
                self.technique_stats_data[tech] = {
                    "times_tried": 0,
                    "best_parent_delta": float("-inf"),
                    "avg_parent_delta": 0.0,
                    "_total_delta": 0.0,
                }
            stats = self.technique_stats_data[tech]
            stats["times_tried"] += 1
            stats["_total_delta"] = stats.get("_total_delta", 0.0) + parent_delta
            stats["avg_parent_delta"] = stats["_total_delta"] / stats["times_tried"]
            if parent_delta > stats["best_parent_delta"]:
                stats["best_parent_delta"] = parent_delta

    # --- Scoring ---
    def recalculate_scores(self):
        total = max(1, self.meta["total_executed"])
        w_e = self.meta["scoring"]["exploration_weight"]
        w_n = self.meta["scoring"]["novelty_weight"]

        for node in self.nodes.values():
            if node["type"] == "executed":
                child_count = len([
                    n for n in self.nodes.values()
                    if n.get("parent_id") == node["id"] and n["type"] == "executed"
                ])
                node["child_count"] = child_count
                node["potential"] = round(
                    node.get("composite", 0) +
                    w_e * math.sqrt(math.log(total) / (1 + child_count)),
                    6,
                )
            elif node["type"] == "proposed" and node["status"] != "cancelled":
                parent = self.get_node(node.get("parent_id"))
                parent_composite = parent.get("composite", 0.0) if parent else 0.0
                siblings_tried = len([
                    n for n in self.nodes.values()
                    if n.get("parent_id") == node.get("parent_id")
                    and n["type"] == "executed"
                ])
                tech_novelty = 0.0
                for tech in node.get("techniques", []):
                    stats = self.technique_stats_data.get(tech, {})
                    tech_novelty += 1.0 / (1 + stats.get("times_tried", 0))
                if node.get("techniques"):
                    tech_novelty /= len(node["techniques"])

                node["potential"] = round(
                    parent_composite +
                    w_e * math.sqrt(math.log(total) / (1 + siblings_tried)) +
                    w_n * tech_novelty,
                    6,
                )

    def rank_proposals(self, n: int = 6, max_per_branch: int = 2) -> list[dict]:
        proposals = [
            nd for nd in self.nodes.values()
            if nd["type"] == "proposed" and nd["status"] == "pending"
        ]
        proposals.sort(key=lambda x: x.get("potential", 0), reverse=True)

        result = []
        branch_counts: dict[str, int] = {}
        for p in proposals:
            pid = p.get("parent_id", "")
            if branch_counts.get(pid, 0) >= max_per_branch:
                continue
            result.append(p)
            branch_counts[pid] = branch_counts.get(pid, 0) + 1
            if len(result) >= n:
                break
        return result

    # --- Deduplication ---
    @staticmethod
    def compute_config_hash(content: str | dict[str, str], base_commit: str = "") -> str:
        """Hash experiment config. Single script or {path: content} dict."""
        if isinstance(content, dict):
            parts = []
            for path in sorted(content.keys()):
                file_hash = hashlib.sha256(content[path].encode()).hexdigest()
                parts.append(f"{path}:{file_hash}")
            combined = base_commit + "\n" + "\n".join(parts)
            return hashlib.sha256(combined.encode()).hexdigest()[:16]
        else:
            # Keep existing tokenizer-based hash logic for single file
            try:
                tokens = tokenize.generate_tokens(io.StringIO(content).readline)
                code_tokens = [
                    tok.string for tok in tokens
                    if tok.type not in (tokenize.COMMENT, tokenize.NL,
                                        tokenize.NEWLINE, tokenize.INDENT,
                                        tokenize.DEDENT, tokenize.ENCODING)
                ]
                normalized = " ".join(code_tokens)
            except tokenize.TokenError:
                normalized = content
            return hashlib.sha256(normalized.encode()).hexdigest()

    def has_config(self, config_hash: str) -> bool:
        return any(
            n.get("config_hash") == config_hash
            for n in self.nodes.values()
            if n.get("config_hash")
        )

    # --- Technique extraction ---
    def _extract_techniques(self, description: str) -> list[str]:
        """Extract technique tags from a description string."""
        techniques = []
        desc_lower = description.lower()
        for pattern, tag in self._technique_map.items():
            if pattern in desc_lower and tag not in techniques:
                techniques.append(tag)
        return techniques

    # --- Reconciliation ---
    def reconcile(self, queue_dir: str, running_dir: str,
                  completed_dir: str, archive_dir: str):
        queue_path = Path(queue_dir)
        running_path = Path(running_dir)
        completed_path = Path(completed_dir)
        archive_path = Path(archive_dir)

        orch_ids = set()
        for d in (queue_path, running_path):
            if d.exists():
                for f in d.glob("*.json"):
                    try:
                        spec = json.loads(f.read_text())
                        orch_ids.add(spec.get("id", f.stem))
                    except (json.JSONDecodeError, Exception):
                        orch_ids.add(f.stem)

        if completed_path.exists():
            for f in completed_path.glob("*.json"):
                try:
                    completion = json.loads(f.read_text())
                except (json.JSONDecodeError, Exception):
                    continue
                node_id = completion.get("id", f.stem)
                orch_ids.add(node_id)

                node = self.get_node(node_id)
                if node and node["type"] == "executed":
                    continue

                orch_status = completion.get("status", "")
                if orch_status in ("oom", "crash", "timeout"):
                    graph_status = orch_status
                elif orch_status == "completed":
                    composite = completion.get("composite", 0.0)
                    comp_metrics = completion.get("metrics", {})
                    gm = completion.get("graph_metadata", {})
                    if not gm:
                        spec_file = archive_path / node_id / "spec.json"
                        if spec_file.exists():
                            try:
                                gm = json.loads(spec_file.read_text()).get("graph_metadata", {})
                            except Exception:
                                pass
                    parent_id_check = gm.get("parent_id")
                    # Fall back to existing node's parent if metadata is missing
                    if not parent_id_check and node:
                        parent_id_check = node.get("parent_id")
                    parent_node = self.get_node(parent_id_check) if parent_id_check else None
                    if parent_node:
                        p_auc = parent_node.get("test_auc", 0)
                        p_bacc = parent_node.get("test_bacc", 0)
                        p_comp = parent_node.get("composite", 0)
                        keep = (comp_metrics.get("test_auc", 0) >= p_auc and
                                comp_metrics.get("test_bacc", 0) >= p_bacc and
                                composite > p_comp)
                        graph_status = "keep" if keep else "discard"
                    else:
                        graph_status = "keep" if composite > 0 else "discard"
                else:
                    graph_status = "discard"

                comp_metrics = completion.get("metrics", {})
                metrics = {
                    "composite": completion.get("composite", 0.0),
                    "test_auc": comp_metrics.get("test_auc", 0.0),
                    "test_bacc": comp_metrics.get("test_bacc", 0.0),
                    "val_auc": comp_metrics.get("val_auc", 0.0),
                    "val_bacc": comp_metrics.get("val_bacc", 0.0),
                    "vram_gb": completion.get("peak_vram_mb", 0) / 1024,
                    "elapsed_min": completion.get("elapsed_seconds", 0) / 60,
                    "gpu": completion.get("gpu", -1),
                    "status": graph_status,
                    "global_delta": completion.get("composite", 0) - self.meta.get("best_composite", 0),
                }

                config_hash = completion.get("config_hash")
                if not config_hash:
                    spec_file = archive_path / node_id / "spec.json"
                    if spec_file.exists():
                        try:
                            spec_data = json.loads(spec_file.read_text())
                            config_hash = spec_data.get("graph_metadata", {}).get("config_hash")
                        except (json.JSONDecodeError, Exception):
                            pass
                metrics["config_hash"] = config_hash

                if node:
                    if graph_status in ("keep", "discard"):
                        self.promote(node_id, metrics)
                    else:
                        self.mark_failed(node_id, graph_status,
                                         completion.get("error", ""),
                                         config_hash=config_hash)
                else:
                    parent_id = None
                    techniques = []
                    spec_file = archive_path / node_id / "spec.json"
                    if spec_file.exists():
                        try:
                            spec = json.loads(spec_file.read_text())
                            gm = spec.get("graph_metadata", {})
                            parent_id = gm.get("parent_id")
                            techniques = gm.get("techniques", [])
                            if not config_hash:
                                config_hash = gm.get("config_hash")
                                metrics["config_hash"] = config_hash
                        except (json.JSONDecodeError, Exception):
                            pass

                    self.nodes[node_id] = {
                        "id": node_id,
                        "parent_id": parent_id,
                        "type": "executed",
                        "status": graph_status,
                        "description": completion.get("description", "recovered"),
                        "techniques": techniques,
                        "composite": metrics["composite"],
                        "global_delta": metrics["global_delta"],
                        "parent_delta": 0.0,
                        "test_auc": metrics["test_auc"],
                        "test_bacc": metrics["test_bacc"],
                        "val_auc": metrics["val_auc"],
                        "val_bacc": metrics["val_bacc"],
                        "vram_gb": metrics["vram_gb"],
                        "elapsed_min": metrics["elapsed_min"],
                        "gpu": metrics["gpu"],
                        "commit": None,
                        "archive_id": node_id,
                        "config_hash": metrics.get("config_hash"),
                        "potential": 0.0,
                        "child_count": 0,
                        "created_at": datetime.now().isoformat(),
                        "recovered": True,
                    }
                    if parent_id and parent_id in self.nodes:
                        parent_comp = self.nodes[parent_id].get("composite", 0)
                        self.nodes[node_id]["parent_delta"] = metrics["composite"] - parent_comp
                    self.meta["total_executed"] += 1
                    if metrics["composite"] > self.meta["best_composite"]:
                        self.meta["best_composite"] = metrics["composite"]
                        self.meta["best_node_id"] = node_id

                    self._update_technique_stats(
                        techniques, self.nodes[node_id]["parent_delta"])

                    if node_id.startswith("node_"):
                        try:
                            recovered_num = int(node_id.split("_")[1])
                            if recovered_num >= self.meta["next_id"]:
                                self.meta["next_id"] = recovered_num + 1
                        except (ValueError, IndexError):
                            pass

        # Archive-based recovery: scan for result.json in archive dirs
        if archive_path.exists():
            for node_dir in archive_path.iterdir():
                if not node_dir.is_dir():
                    continue
                node_id_r = node_dir.name
                result_file = node_dir / "result.json"
                if node_id_r not in self.nodes and result_file.exists():
                    try:
                        result = json.loads(result_file.read_text())
                        spec_file = node_dir / "spec.json"
                        spec = json.loads(spec_file.read_text()) if spec_file.exists() else {}
                        gm = spec.get("graph_metadata", {})
                        r_metrics = result.get("metrics", {})
                        composite = result.get("composite", 0.0)
                        num = int(node_id_r.split("_")[1])
                        if num >= self.meta["next_id"]:
                            self.meta["next_id"] = num + 1

                        parent_id = gm.get("parent_id")
                        parent = self.get_node(parent_id) if parent_id else None
                        parent_composite = parent.get("composite", 0.0) if parent else 0.0
                        raw_status = result.get("status", "completed")
                        if raw_status == "completed":
                            if parent:
                                p_auc = parent.get("test_auc", 0)
                                p_bacc = parent.get("test_bacc", 0)
                                keep = (r_metrics.get("test_auc", 0) >= p_auc and
                                        r_metrics.get("test_bacc", 0) >= p_bacc and
                                        composite > parent_composite)
                                status = "keep" if keep else "discard"
                            else:
                                status = "keep" if composite > 0 else "discard"
                        else:
                            status = raw_status

                        techniques = gm.get("techniques", [])
                        self.nodes[node_id_r] = {
                            "id": node_id_r, "parent_id": parent_id,
                            "type": "executed", "status": status,
                            "description": spec.get("description", f"recovered {node_id_r}"),
                            "techniques": techniques, "composite": composite,
                            "global_delta": composite - self.meta.get("best_composite", 0),
                            "parent_delta": composite - parent_composite,
                            "test_auc": r_metrics.get("test_auc", 0),
                            "test_bacc": r_metrics.get("test_bacc", 0),
                            "val_auc": r_metrics.get("val_auc", 0),
                            "val_bacc": r_metrics.get("val_bacc", 0),
                            "vram_gb": result.get("peak_vram_mb", 0) / 1024,
                            "elapsed_min": result.get("elapsed_seconds", 0) / 60,
                            "gpu": -1,
                            "config_hash": gm.get("config_hash"),
                            "archive_id": node_id_r, "recovered": True,
                            "created_at": datetime.now().isoformat(),
                        }
                        self.meta["total_executed"] += 1
                        if composite > self.meta.get("best_composite", 0):
                            self.meta["best_composite"] = composite
                            self.meta["best_node_id"] = node_id_r
                        parent_delta = composite - parent_composite
                        self._update_technique_stats(techniques, parent_delta)
                    except (json.JSONDecodeError, Exception):
                        continue

        for node in list(self.nodes.values()):
            if node["type"] == "proposed" and node["status"] == "running":
                if node["id"] not in orch_ids:
                    node["status"] = "pending"

        self.recalculate_scores()

    # --- Migration ---
    @staticmethod
    def import_from_tsv(tsv_path: str, strategies_path: str | None = None,
                        graph_path: str | Path = "graph.json") -> ExperimentGraph:
        g = ExperimentGraph(path=graph_path)

        with open(tsv_path) as f:
            lines = f.readlines()

        if not lines or len(lines) < 2:
            return g

        rows = lines[1:]
        current_best_id = None

        for row in rows:
            parts = row.strip().split("\t")
            if len(parts) < 11:
                continue

            commit, val_auc, val_bacc = parts[0], float(parts[1]), float(parts[2])
            test_auc, test_bacc = float(parts[3]), float(parts[4])
            composite, delta = float(parts[5]), float(parts[6].replace("+", ""))
            vram_gb, elapsed_min = float(parts[7]), float(parts[8])
            status, description = parts[9], parts[10]

            techniques = []
            desc_lower = description.lower()
            for pattern, tag in ExperimentGraph.DEFAULT_TECHNIQUE_MAP.items():
                if pattern in desc_lower and tag not in techniques:
                    techniques.append(tag)

            nid = g.add_executed(
                parent_id=current_best_id,
                description=description,
                techniques=techniques,
                metrics={
                    "composite": composite,
                    "delta": delta,
                    "test_auc": test_auc, "test_bacc": test_bacc,
                    "val_auc": val_auc, "val_bacc": val_bacc,
                    "vram_gb": vram_gb, "elapsed_min": elapsed_min, "gpu": -1,
                },
                status=status,
                commit=commit,
                bootstrapped=True,
            )

            if status == "keep":
                current_best_id = nid

        if strategies_path and os.path.exists(strategies_path):
            with open(strategies_path) as f:
                strat_data = json.loads(f.read())
            best_id = g.meta.get("best_node_id")
            for strat in strat_data.get("strategies", []):
                if strat.get("status") == "not_started" and best_id:
                    g.add_proposed(
                        parent_id=best_id,
                        description=strat.get("description", strat.get("name", "")),
                        techniques=[strat["id"]],
                        rationale=strat.get("description", ""),
                        reference=strat.get("reference"),
                        expected_gain=strat.get("expected_gain", "low"),
                        effort=strat.get("effort", "low"),
                        tier=strat.get("tier", 2),
                    )

        g.recalculate_scores()
        return g

    # --- Persistence ---
    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(self._data, f, indent=2)
                f.write("\n")
            os.rename(tmp_path, str(self.path))
            os.utime(str(self.path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def to_dict(self) -> dict:
        return self._data
