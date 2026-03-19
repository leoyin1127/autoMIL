"""SMMILe hyperparameter configuration for SMMILe_SINGLE (binary)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SMMILeConfig:
    """Hyperparameters for SMMILe_SINGLE binary classification."""

    # Model
    model_size: str = "small"
    dropout: bool = True
    drop_rate: float = 0.25
    n_refs: int = 3

    # Stage 1 (base)
    stage1_epochs: int = 40
    lr: float = 2e-5
    weight_decay: float = 1e-5
    bag_loss: str = "bce"
    early_stopping: bool = True
    patience: int = 20
    stop_epoch: int = 30
    weighted_sample: bool = True

    # SMMILe modules (Stage 1)
    drop_with_score: bool = True
    D: int = 1
    superpixel: bool = True
    G: int = 4
    sp_smooth: bool = True
    consistency: bool = False

    # Stage 2 (refinement)
    stage2_epochs: int = 20
    inst_refinement: bool = True
    inst_rate: float = 0.01
    mrf: bool = True
    tau: float = 0.1

    # Data
    patch_size: int = 256
    n_segments_per_sp: int = 16
    compactness: int = 50
