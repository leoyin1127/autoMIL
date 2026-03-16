"""autoMIL Training Script Template.

This is the file the agent modifies. Copy it, rename to train.py,
and fill in the TODO sections for your dataset and model.

--- MODIFICATION GUIDE ---

Things the agent CAN change (in this file):
  - CONFIG: training hyperparameters (LR, weight decay, dropout, etc.)
  - preprocess_features(): feature normalization, PCA, fusion
  - augment_batch(): patch dropout, feature noise, mixup
  - create_loss_fn(): focal loss, label smoothing, etc.
  - create_optimizer(): AdamW, SAM, different param groups
  - create_lr_schedule(): cosine, linear, warmup variations
  - The training loop itself (train_single_fold)
  - The model architecture (create_model)

Things the agent CANNOT change:
  - prepare.py (read-only: data loading, evaluation metrics, splits)
  - The split assignments (same K-fold CV as the baseline)
"""

from __future__ import annotations

import gc
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# TODO: Import from your prepare.py
# from prepare import create_fold_loaders, compute_metrics, DEVICE, N_FOLDS

# ============================================================
# EXPERIMENT DESCRIPTION (agent updates this each experiment)
# ============================================================
EXPERIMENT_DESCRIPTION = "baseline"

# ============================================================
# CONFIG -- agent tunes these
# ============================================================
CONFIG = {
    "learning_rate": 3e-4,
    "weight_decay": 1e-4,
    "dropout": 0.25,
    "num_epochs": 100,
    "warmup_epochs": 5,
    "patience": 10,
    "batch_size": 32,
}

# GPU selection: int for single GPU, list for DataParallel
GPU = 0


# ============================================================
# PREPROCESSING -- agent can modify
# ============================================================
def preprocess_features(features, coords=None):
    """Preprocess raw features before model input.

    Options: L2 normalization, standardization, PCA,
    feature selection, multi-encoder fusion, positional encoding.
    """
    return features


# ============================================================
# AUGMENTATION -- agent can modify
# ============================================================
def augment_batch(features, labels, training=True):
    """Apply data augmentation during training.

    Options: patch dropout, Gaussian noise, feature-space mixup,
    random patch masking, pseudo-bag augmentation.
    """
    return features, labels


# ============================================================
# LOSS FUNCTION -- agent can modify
# ============================================================
def create_loss_fn():
    """Create the loss function.

    Options: CrossEntropyLoss, FocalLoss, label smoothing,
    class-weighted CE, supervised contrastive, R-Drop KL.
    """
    return nn.CrossEntropyLoss()


# ============================================================
# OPTIMIZER -- agent can modify
# ============================================================
def create_optimizer(model):
    """Create the optimizer.

    Options: AdamW, SAM, SGD, separate LR per parameter group,
    bi-level learning rates.
    """
    return torch.optim.AdamW(
        model.parameters(),
        lr=CONFIG["learning_rate"],
        weight_decay=CONFIG["weight_decay"],
    )


# ============================================================
# LR SCHEDULE -- agent can modify
# ============================================================
def create_lr_schedule(optimizer, num_epochs):
    """Create the learning rate schedule.

    Options: cosine annealing, step LR, linear warmup/decay,
    warm restarts, plateau-based.
    """
    return torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=num_epochs
    )


# ============================================================
# MODEL -- agent can modify or replace entirely
# ============================================================
def create_model(input_dim, n_classes):
    """Create the model.

    The agent can modify this to use any architecture:
    custom attention, different pooling, multi-head, etc.
    """
    # TODO: Replace with your model creation logic
    raise NotImplementedError("Define your model here")


# ============================================================
# TRAINING LOOP -- agent can modify
# ============================================================
def train_single_fold(fold_idx, train_loader, val_loader, test_loader):
    """Train one fold and return val/test metrics.

    The agent can modify: gradient clipping, accumulation,
    early stopping logic, test-time augmentation, etc.
    """
    # TODO: Implement training loop
    # Should return (val_metrics_dict, test_metrics_dict)
    raise NotImplementedError("Implement training loop")


# ============================================================
# MAIN
# ============================================================
def main():
    start_time = time.time()

    # TODO: Set up device, load data, run folds
    # Example structure:
    #
    # val_results = []
    # test_results = []
    # for fold in range(N_FOLDS):
    #     train_loader, val_loader, test_loader = create_fold_loaders(fold)
    #     val_metrics, test_metrics = train_single_fold(
    #         fold, train_loader, val_loader, test_loader
    #     )
    #     val_results.append(val_metrics)
    #     test_results.append(test_metrics)

    elapsed = time.time() - start_time
    peak_vram_mb = (
        torch.cuda.max_memory_allocated() / 1024 / 1024
        if torch.cuda.is_available()
        else 0.0
    )

    # --- Print parseable summary ---
    # TODO: Compute means from val_results and test_results
    # print("---")
    # print(f"val_auc_roc: {val_auc_mean:.6f} (+/- {val_auc_std:.4f})")
    # print(f"val_bacc: {val_bacc_mean:.6f} (+/- {val_bacc_std:.4f})")
    # print(f"test_auc_roc: {test_auc_mean:.6f} (+/- {test_auc_std:.4f})")
    # print(f"test_bacc: {test_bacc_mean:.6f} (+/- {test_bacc_std:.4f})")
    # print(f"elapsed_seconds: {elapsed:.1f}")
    # print(f"peak_vram_mb: {peak_vram_mb:.1f}")
    # print("---")

    # --- Auto-log to results.tsv ---
    # TODO: Implement results logging (see ovarian_hrd example)
    pass


if __name__ == "__main__":
    main()
