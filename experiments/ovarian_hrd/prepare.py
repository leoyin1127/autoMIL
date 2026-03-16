"""Fixed evaluation and data-loading utilities for MIL autoresearch.

DO NOT MODIFY THIS FILE. It is the ground truth for evaluation and data loading.
Only modify train.py.
"""

from __future__ import annotations

import os
import sys
from functools import partial

import h5py
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score
from torch.utils.data import DataLoader

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lib"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

BENCHMARK_DIR = "/mnt/pool/ovariancancer/ovarian2026/benchmark_full"
FEATURES_BASE_DIR = (
    "/mnt/pool/ovariancancer/ovarian2026/trident_output/20x_256px_0px_overlap"
)

ENCODER_DIMS: dict[str, int] = {
    "conch_v15": 768,
    "hibou_l": 1024,
    "uni_v2": 1536,
    "hoptimus1": 1536,
    "midnight12k": 1536,
    "virchow2": 2560,
    "h0_mini": 768,
}

# Benchmark baselines to beat (UHN 5-fold CV, best encoder+model per task)
# These are TEST AUC-ROC values from the benchmark aggregated results.
BASELINES = {
    "brca": {"encoder": "hibou_l", "model": "ilra_mil", "test_auc": 0.722},
    "hrd": {"encoder": "hoptimus1", "model": "clam_mb", "test_auc": 0.865},
}

N_FOLDS = 5


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def get_plan_path(task: str, encoder: str, strategy: str = "uhn_baseline") -> str:
    """Return path to existing dataset_plan.json from benchmark."""
    return os.path.join(
        BENCHMARK_DIR, "nnmil", strategy, f"{task}_{encoder}", "dataset_plan.json"
    )


def _collate_fn(batch):
    """Stack variable-length bags into (B, N, D) tensors."""
    features = torch.stack([b[0] for b in batch])
    coords = torch.stack([b[1] for b in batch])
    bag_sizes = torch.stack([b[2] for b in batch])
    labels = torch.stack([b[3] for b in batch])
    return features, coords, bag_sizes, labels


def _seed_worker(base_seed: int, worker_id: int) -> None:
    np.random.seed(base_seed + worker_id)


def create_fold_loaders(
    plan_path: str,
    fold: int,
    batch_size: int = 32,
    max_seq_length: int | None = 4096,
    num_workers: int = 0,
    seed: int = 42,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Create train/val/test DataLoaders from a plan file.

    Returns (train_loader, val_loader, test_loader).
    """
    from nnMIL.training.samplers.classification_sampler import BalancedBatchSampler
    from nnMIL.utilities.plan_loader import create_dataset_from_plan

    train_ds = create_dataset_from_plan(
        plan_path, split="train", fold=fold, max_seq_length=max_seq_length
    )
    val_ds = create_dataset_from_plan(
        plan_path, split="val", fold=fold, max_seq_length=max_seq_length
    )
    test_ds = create_dataset_from_plan(
        plan_path, split="test", fold=fold, max_seq_length=max_seq_length
    )

    worker_init = partial(_seed_worker, seed)

    train_sampler = BalancedBatchSampler(
        train_ds, batch_size, shuffle=True, seed=seed
    )
    train_loader = DataLoader(
        train_ds,
        batch_sampler=train_sampler,
        num_workers=num_workers,
        worker_init_fn=worker_init,
        collate_fn=_collate_fn,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=1,
        shuffle=False,
        num_workers=num_workers,
        worker_init_fn=worker_init,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=1,
        shuffle=False,
        num_workers=num_workers,
        worker_init_fn=worker_init,
    )

    return train_loader, val_loader, test_loader


def get_feature_dir(encoder: str) -> str:
    """Return path to H5 feature directory for an encoder."""
    return os.path.join(FEATURES_BASE_DIR, f"features_{encoder}")


def load_h5_features(encoder: str, slide_ids: list[str]) -> dict[str, np.ndarray]:
    """Load raw features from H5 files. For fusion experiments."""
    h5_dir = get_feature_dir(encoder)
    features: dict[str, np.ndarray] = {}
    for sid in slide_ids:
        path = os.path.join(h5_dir, f"{sid}.h5")
        if os.path.exists(path):
            with h5py.File(path, "r") as f:
                features[sid] = f["features"][:]
    return features


def get_splits(
    task: str, strategy: str = "uhn_baseline", n_folds: int = N_FOLDS
) -> list[tuple[list[str], list[str], list[str]]]:
    """Load split CSVs. Returns [(train_ids, val_ids, test_ids), ...] per fold."""
    splits_dir = os.path.join(BENCHMARK_DIR, "splits", strategy, task)
    folds = []
    for i in range(n_folds):
        df = pd.read_csv(os.path.join(splits_dir, f"splits_{i}.csv"))
        folds.append((
            df["train"].dropna().tolist(),
            df["val"].dropna().tolist(),
            df["test"].dropna().tolist(),
        ))
    return folds


# ---------------------------------------------------------------------------
# Evaluation (ground truth, do not modify)
# ---------------------------------------------------------------------------


def compute_metrics(
    labels: np.ndarray, probs: np.ndarray
) -> dict[str, float]:
    """Compute classification metrics from labels and probability predictions."""
    preds = np.argmax(probs, axis=1)
    auc = (
        roc_auc_score(labels, probs[:, 1])
        if len(np.unique(labels)) > 1
        else 0.0
    )
    bacc = balanced_accuracy_score(labels, preds)
    f1 = f1_score(labels, preds, average="weighted")
    return {"auc_roc": float(auc), "bacc": float(bacc), "f1": float(f1)}


def print_results(
    val_fold_metrics: list[dict[str, float]],
    test_fold_metrics: list[dict[str, float]],
    task: str,
    extra: dict | None = None,
) -> None:
    """Print results in autoresearch-parseable format."""
    print("---")

    # Validation metrics (primary optimization target)
    for key in val_fold_metrics[0]:
        vals = [m[key] for m in val_fold_metrics]
        mean, std = np.mean(vals), np.std(vals, ddof=1)
        print(f"val_{key}: {mean:.6f} (+/- {std:.4f})")

    # Test metrics (for reference only, do NOT optimize on these)
    for key in test_fold_metrics[0]:
        vals = [m[key] for m in test_fold_metrics]
        mean, std = np.mean(vals), np.std(vals, ddof=1)
        print(f"test_{key}: {mean:.6f} (+/- {std:.4f})")

    # Baseline comparison (against benchmark test AUC)
    baseline = BASELINES.get(task, {})
    if baseline:
        test_auc = np.mean([m["auc_roc"] for m in test_fold_metrics])
        delta = test_auc - baseline["test_auc"]
        sign = "+" if delta >= 0 else ""
        print(f"baseline_delta: {sign}{delta:.6f}")

    if extra:
        for k, v in extra.items():
            print(f"{k}: {v}")

    print("---")
