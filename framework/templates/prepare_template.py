"""autoMIL Data Preparation Template.

This is the READ-ONLY file that defines data loading, evaluation metrics,
and cross-validation splits. The agent CANNOT modify this file.

Copy it, rename to prepare.py, and fill in the TODO sections.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import yaml

# ============================================================
# LOAD CONFIG
# ============================================================
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
with open(CONFIG_PATH) as f:
    PROJECT_CONFIG = yaml.safe_load(f)

FEATURES_DIR = PROJECT_CONFIG["paths"]["features_dir"]
N_FOLDS = PROJECT_CONFIG["dataset"]["cv_folds"]

# ============================================================
# DEVICE SETUP
# ============================================================
import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ============================================================
# DATA LOADING -- customize for your dataset
# ============================================================
def load_dataset():
    """Load the full dataset (features, labels, metadata).

    TODO: Implement for your dataset format.
    Should return a list/dict of samples, each with:
      - features: tensor or path to H5 file
      - label: int class label
      - metadata: any additional info (patient_id, slide_id, etc.)
    """
    raise NotImplementedError("Implement dataset loading")


def create_fold_loaders(fold_idx, batch_size=32):
    """Create train/val/test data loaders for a given fold.

    TODO: Implement cross-validation splitting.
    Should return (train_loader, val_loader, test_loader).
    """
    raise NotImplementedError("Implement fold splitting and data loading")


# ============================================================
# EVALUATION -- customize metrics for your task
# ============================================================
def compute_metrics(y_true, y_pred, y_prob):
    """Compute evaluation metrics.

    TODO: Implement for your task. Common metrics:
      - AUC-ROC (binary or multi-class)
      - Balanced accuracy
      - F1 score
      - Sensitivity / Specificity

    Returns:
        dict with metric names as keys, values as floats.
        Example: {"auc_roc": 0.85, "bacc": 0.78, "f1": 0.80}
    """
    raise NotImplementedError("Implement evaluation metrics")


# ============================================================
# UTILITIES
# ============================================================
def print_results(val_results, test_results, elapsed, peak_vram_mb):
    """Print parseable results summary.

    Format must match what config.yaml's extract_command expects.
    """
    val_auc = np.mean([m["auc_roc"] for m in val_results])
    val_bacc = np.mean([m["bacc"] for m in val_results])
    test_auc = np.mean([m["auc_roc"] for m in test_results])
    test_bacc = np.mean([m["bacc"] for m in test_results])

    print("---")
    print(f"val_auc_roc: {val_auc:.6f}")
    print(f"val_bacc: {val_bacc:.6f}")
    print(f"test_auc_roc: {test_auc:.6f}")
    print(f"test_bacc: {test_bacc:.6f}")
    print(f"elapsed_seconds: {elapsed:.1f}")
    print(f"peak_vram_mb: {peak_vram_mb:.1f}")
    print("---")
