"""Autoresearch MIL: Editable experiment script.

This is the ONLY file you modify. Everything in prepare.py is fixed.

--- MODIFICATION GUIDE ---

Things you CAN change (in this file):
  - TARGET: which task / encoder / model to optimize
  - CONFIG: training hyperparameters (LR, weight decay, dropout, etc.)
  - preprocess_features(): feature normalization, PCA, fusion
  - augment_batch(): patch dropout, feature noise, mixup
  - create_loss_fn(): focal loss, label smoothing, etc.
  - create_optimizer(): AdamW, SAM, different param groups
  - create_lr_schedule(): cosine, linear, warmup variations
  - The training loop itself (train_single_fold)

Things you CANNOT change:
  - prepare.py (read-only: data loading, evaluation metrics, splits)
  - The split assignments (same 5-fold CV as the benchmark)
"""

from __future__ import annotations

import gc
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# Project setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lib"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# CLAM framework
CLAM_DIR = os.path.join(PROJECT_ROOT, "lib", "CLAM")
if CLAM_DIR not in sys.path:
    sys.path.insert(0, CLAM_DIR)

import prepare
from prepare import (
    ENCODER_DIMS,
    N_FOLDS,
    compute_metrics,
    create_fold_loaders,
    get_plan_path,
    print_results,
)

from nnMIL.network_architecture.model_factory import create_mil_model

CLAM_MODELS = {"clam_sb", "clam_mb", "mil_fc"}


# =========================================================================
# TARGET: What to optimize. Change these to switch task/encoder/model.
# =========================================================================
TASK = "hrd"                 # "brca" or "hrd"
ENCODER = "hoptimus1"        # best HRD encoder from benchmark
MODEL_TYPE = "clam_mb"       # best HRD model from benchmark
SEED = 42
GPU = int(os.environ.get("AUTORESEARCH_GPU", "0"))  # override via env var
EXPERIMENT_DESCRIPTION = os.environ.get("AUTORESEARCH_DESC", "baseline")
RDROP_ALPHA = 1.0  # R-Drop KL divergence weight (0 = disabled)


# =========================================================================
# CONFIG: Training hyperparameters. Tune freely.
# =========================================================================
CONFIG = {
    "learning_rate": 3e-4,
    "weight_decay": 1e-4,
    "dropout": 0.1,
    "hidden_dim": 512,
    "num_epochs": 100,
    "warmup_epochs": 5,
    "patience": 10,
    "batch_size": 32,
    "micro_batch_size": 4,        # per-GPU forward pass size; accumulate to batch_size
    "max_seq_length": 4096,
    # CLAM-specific (ignored for nnMIL models)
    "model_size": "big",         # "small" or "big" (CLAM architecture size)
    "k_sample": 16,              # patches sampled for instance-level eval
    "bag_weight": 0.5,           # bag_loss weight; (1-bag_weight) for instance_loss
    "instance_eval": False,      # disable instance-level supervision (best config)
    "grad_clip": 0.5,            # max grad norm (None = no clipping)
}


# =========================================================================
# PREPROCESSING: Applied to raw features before training.
# Modify to try: L2 norm, standardization, PCA, feature selection, etc.
# =========================================================================
def preprocess_features(features: torch.Tensor) -> torch.Tensor:
    """Transform patch features before they enter the model.

    Args:
        features: (B, N, D) or (1, N, D) tensor of patch embeddings.

    Returns:
        Transformed features, same shape or projected to new dim.
    """
    # Baseline: no preprocessing
    return features


# =========================================================================
# AUGMENTATION: Applied to each training batch during training only.
# Modify to try: patch dropout, Gaussian noise, feature mixup, etc.
# =========================================================================
def augment_batch(
    features: torch.Tensor,
    bag_sizes: torch.Tensor,
    labels: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Augment a training batch in-place.

    Args:
        features: (B, N, D) patch features.
        bag_sizes: (B,) actual number of patches per slide.
        labels: (B,) integer labels.

    Returns:
        (features, bag_sizes, labels) - possibly modified.
    """
    # Baseline: no augmentation
    return features, bag_sizes, labels


# =========================================================================
# LOSS FUNCTION: Modify to try focal loss, label smoothing, etc.
# =========================================================================
class FocalLoss(nn.Module):
    """Focal loss for class imbalance (144 pos, 62 neg)."""
    def __init__(self, gamma=2.0, alpha=None):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, logits, targets):
        ce = F.cross_entropy(logits, targets, weight=self.alpha, reduction="none")
        pt = torch.exp(-ce)
        return (((1 - pt) ** self.gamma) * ce).mean()


def create_loss_fn() -> nn.Module:
    """Create the loss function."""
    pos_weight = 62.0 / (144.0 + 62.0)
    neg_weight = 144.0 / (144.0 + 62.0)
    alpha = torch.tensor([neg_weight, pos_weight]).cuda()
    return FocalLoss(gamma=1.0, alpha=alpha)


# =========================================================================
# OPTIMIZER: Modify to try different optimizers, param groups, etc.
# =========================================================================
def create_optimizer(model: nn.Module) -> torch.optim.Optimizer:
    """Create optimizer with parameter groups."""
    named_params = list(model.named_parameters())

    # Separate bias/norm params (no weight decay) from matrix params
    no_decay = lambda n, p: p.ndim < 2 or "bn" in n or "ln" in n or "bias" in n
    decay_params = [p for n, p in named_params if not no_decay(n, p) and p.requires_grad]
    nodecay_params = [p for n, p in named_params if no_decay(n, p) and p.requires_grad]

    return torch.optim.AdamW(
        [
            {"params": nodecay_params, "weight_decay": 0.0},
            {"params": decay_params, "weight_decay": CONFIG["weight_decay"]},
        ],
        lr=CONFIG["learning_rate"],
    )


# =========================================================================
# LR SCHEDULE: Cosine with linear warmup. Modify freely.
# =========================================================================
def create_lr_schedule(optimizer, total_steps: int):
    """Step LR: halve every 20 epochs after warmup."""
    base_lr = CONFIG["learning_rate"]
    steps_per_epoch = max(1, total_steps // CONFIG["num_epochs"])
    warmup_steps = steps_per_epoch * CONFIG["warmup_epochs"]

    def _update(step: int):
        if step < warmup_steps:
            lr = base_lr * (step + 1) / max(warmup_steps, 1)
        else:
            epochs_after_warmup = (step - warmup_steps) // steps_per_epoch
            n_halvings = epochs_after_warmup // 20
            lr = base_lr * (0.5 ** n_halvings)
        for group in optimizer.param_groups:
            group["lr"] = lr

    return _update


# =========================================================================
# MODEL CREATION: Dispatches between nnMIL and CLAM frameworks.
# =========================================================================
def create_model(
    model_type: str,
    input_dim: int,
    hidden_dim: int,
    num_classes: int,
    dropout: float,
) -> nn.Module:
    """Create a MIL model, dispatching between nnMIL and CLAM frameworks."""
    if model_type in CLAM_MODELS:
        from models.model_clam import CLAM_SB, CLAM_MB
        from models.model_mil import MIL_fc

        if model_type == "clam_sb":
            return CLAM_SB(
                gate=True,
                size_arg=CONFIG.get("model_size", "small"),
                dropout=dropout,
                k_sample=CONFIG.get("k_sample", 8),
                n_classes=num_classes,
                embed_dim=input_dim,
            )
        elif model_type == "clam_mb":
            return CLAM_MB(
                gate=True,
                size_arg=CONFIG.get("model_size", "small"),
                dropout=dropout,
                k_sample=CONFIG.get("k_sample", 8),
                n_classes=num_classes,
                embed_dim=input_dim,
            )
        else:  # mil_fc
            return MIL_fc(
                size_arg=CONFIG.get("model_size", "small"),
                dropout=dropout,
                n_classes=num_classes,
                embed_dim=input_dim,
            )
    else:
        return create_mil_model(
            model_type=model_type,
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_classes=num_classes,
            dropout=dropout,
        )


# =========================================================================
# FORWARD PASS: Handles model-specific input formats.
# =========================================================================
def forward_pass(
    model: nn.Module,
    model_type: str,
    features: torch.Tensor,
    coords: torch.Tensor,
    bag_sizes: torch.Tensor,
    labels: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor | None]:
    """Run forward pass, returning (logits, instance_loss).

    instance_loss is None for non-CLAM models.
    For CLAM models, instance_loss is the average instance-level loss across
    the batch (only computed when labels are provided and instance_eval=True).
    """
    if model_type in CLAM_MODELS:
        # CLAM processes one slide at a time: (N, D) not (B, N, D)
        batch_logits = []
        instance_losses = []

        for i in range(features.size(0)):
            n_real = bag_sizes[i].item()
            h = features[i, :n_real]  # (N_real, D)

            # Add sinusoidal 2D positional encoding from coordinates
            if coords is not None:
                c_real = coords[i, :n_real].float()  # (N_real, 2)
                D = h.size(1)
                pe = torch.zeros(n_real, D, device=h.device)
                c_norm = c_real.clone()
                for dim in range(2):
                    c_min = c_real[:, dim].min()
                    c_max = c_real[:, dim].max()
                    if c_max > c_min:
                        c_norm[:, dim] = (c_real[:, dim] - c_min) / (c_max - c_min)
                div_term = torch.exp(torch.arange(0, D // 2, device=h.device).float() * (-np.log(10000.0) / (D // 2)))
                pe[:, 0::4] = torch.sin(c_norm[:, 0:1] * div_term[:D//4])
                pe[:, 1::4] = torch.cos(c_norm[:, 0:1] * div_term[:D//4])
                pe[:, 2::4] = torch.sin(c_norm[:, 1:2] * div_term[:D//4])
                pe[:, 3::4] = torch.cos(c_norm[:, 1:2] * div_term[:D//4])
                h = h + 0.1 * pe  # scale PE to not dominate features

            if model_type == "mil_fc":
                output = model(h)
                batch_logits.append(output[0])  # top_instance: (1, n_classes)
            else:
                # clam_sb or clam_mb
                use_inst = labels is not None and CONFIG.get("instance_eval", True)
                if use_inst:
                    output = model(h, label=labels[i], instance_eval=True)
                    batch_logits.append(output[0])
                    instance_losses.append(output[4]["instance_loss"])
                else:
                    output = model(h)
                    batch_logits.append(output[0])

        logits = torch.cat(batch_logits, dim=0)  # (B, n_classes)
        if instance_losses:
            avg_inst_loss = sum(instance_losses) / len(instance_losses)
            return logits, avg_inst_loss
        return logits, None

    # nnMIL models
    if model_type == "vision_transformer":
        max_len = features.size(1)
        mask = (
            torch.arange(max_len, device=bag_sizes.device)
            .unsqueeze(0)
            .expand(features.size(0), -1)
            >= bag_sizes.unsqueeze(1)
        )
        output = model(features, coords=coords, mask=mask)
    else:
        output = model(features)

    if isinstance(output, dict):
        return output["logits"], None
    return output, None


# =========================================================================
# TRAINING LOOP: Full single-fold training. Modify anything here.
# =========================================================================
def train_single_fold(
    fold: int,
    device: torch.device,
) -> dict:
    """Train one fold. Returns {"val": metrics_dict, "test": metrics_dict}."""
    torch.manual_seed(SEED + fold)
    np.random.seed(SEED + fold)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED + fold)
        torch.cuda.empty_cache()

    plan_path = get_plan_path(TASK, ENCODER)
    input_dim = ENCODER_DIMS[ENCODER]

    # --- Data (load with micro_batch_size for gradient accumulation) ---
    micro_bs = CONFIG.get("micro_batch_size", CONFIG["batch_size"])
    accum_steps = max(1, CONFIG["batch_size"] // micro_bs)

    train_loader, val_loader, test_loader = create_fold_loaders(
        plan_path,
        fold=fold,
        batch_size=micro_bs,
        max_seq_length=CONFIG["max_seq_length"],
        seed=SEED + fold,
    )

    # --- Model ---
    model = create_model(
        model_type=MODEL_TYPE,
        input_dim=input_dim,
        hidden_dim=CONFIG["hidden_dim"],
        num_classes=2,
        dropout=CONFIG["dropout"],
    ).to(device)

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    # Wrap in DataParallel if multiple GPUs
    gpu_ids = GPU if isinstance(GPU, list) else [GPU]
    if len(gpu_ids) > 1 and torch.cuda.device_count() > 1 and MODEL_TYPE not in CLAM_MODELS:
        model = torch.nn.DataParallel(model, device_ids=gpu_ids)

    print(
        f"  [fold {fold}] params={n_params:,}, "
        f"train={len(train_loader)} micro-batches, "
        f"micro_bs={micro_bs}, accum={accum_steps}, effective_bs={micro_bs * accum_steps}, "
        f"gpus={gpu_ids}"
    )

    # --- Optimizer, loss, scheduler ---
    optimizer = create_optimizer(model)
    loss_fn = create_loss_fn()
    total_steps = (len(train_loader) // accum_steps) * CONFIG["num_epochs"]
    lr_schedule = create_lr_schedule(optimizer, total_steps)

    # --- Mixed precision ---
    scaler = torch.amp.GradScaler("cuda") if device.type == "cuda" else None

    # --- Early stopping state ---
    best_val_auc = -1.0
    best_state = None
    patience_counter = 0
    global_step = 0

    # --- Training ---
    for epoch in range(CONFIG["num_epochs"]):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        optimizer.zero_grad()

        for batch_idx, batch in enumerate(train_loader):
            features, coords, bag_sizes, labels = (
                batch[0].to(device),
                batch[1].to(device),
                batch[2].to(device),
                batch[3].to(device),
            )

            # --- Preprocessing & augmentation ---
            features = preprocess_features(features)
            features, bag_sizes, labels = augment_batch(features, bag_sizes, labels)

            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                logits1, instance_loss1 = forward_pass(
                    model, MODEL_TYPE, features, coords, bag_sizes, labels=labels,
                )
                bag_loss1 = loss_fn(logits1, labels)

                # R-Drop: second forward pass with different dropout mask
                if RDROP_ALPHA > 0:
                    logits2, instance_loss2 = forward_pass(
                        model, MODEL_TYPE, features, coords, bag_sizes, labels=labels,
                    )
                    bag_loss2 = loss_fn(logits2, labels)
                    bag_loss = (bag_loss1 + bag_loss2) / 2

                    # Symmetric KL divergence
                    p = F.log_softmax(logits1, dim=1)
                    q = F.log_softmax(logits2, dim=1)
                    kl_loss = (
                        F.kl_div(p, q.detach().exp(), reduction="batchmean")
                        + F.kl_div(q, p.detach().exp(), reduction="batchmean")
                    ) / 2
                    bag_loss = bag_loss + RDROP_ALPHA * kl_loss

                    # Average instance losses if present
                    if instance_loss1 is not None and instance_loss2 is not None:
                        instance_loss = (instance_loss1 + instance_loss2) / 2
                    else:
                        instance_loss = instance_loss1
                else:
                    bag_loss = bag_loss1
                    instance_loss = instance_loss1

                if instance_loss is not None:
                    bag_weight = CONFIG.get("bag_weight", 0.7)
                    loss = (bag_weight * bag_loss + (1 - bag_weight) * instance_loss) / accum_steps
                else:
                    loss = bag_loss / accum_steps

            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()

            epoch_loss += loss.item() * accum_steps
            n_batches += 1

            # Step optimizer every accum_steps micro-batches (or at end of epoch)
            if (batch_idx + 1) % accum_steps == 0 or (batch_idx + 1) == len(train_loader):
                if scaler is not None:
                    scaler.unscale_(optimizer)
                grad_clip = CONFIG.get("grad_clip")
                if grad_clip is not None:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                if scaler is not None:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                optimizer.zero_grad()
                lr_schedule(global_step)
                global_step += 1

        avg_loss = epoch_loss / max(n_batches, 1)

        # --- Validation ---
        val_metrics = _evaluate(model, val_loader, device)

        # --- Early stopping ---
        if val_metrics["auc_roc"] > best_val_auc:
            best_val_auc = val_metrics["auc_roc"]
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if patience_counter >= CONFIG["patience"]:
            print(f"  [fold {fold}] early stop at epoch {epoch + 1}, best_val_auc={best_val_auc:.4f}")
            break

    # --- Load best model and evaluate test ---
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    val_metrics = _evaluate(model, val_loader, device)
    test_metrics = _evaluate(model, test_loader, device)

    print(
        f"  [fold {fold}] val_auc={val_metrics['auc_roc']:.4f} "
        f"test_auc={test_metrics['auc_roc']:.4f}"
    )

    # Cleanup
    del model, optimizer, best_state
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return {"val": val_metrics, "test": test_metrics}


def _evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> dict[str, float]:
    """Evaluate model on a DataLoader. Returns metrics dict."""
    model.eval()
    all_labels, all_probs = [], []

    with torch.no_grad():
        for batch in loader:
            if len(batch) == 6:
                features, coords, bag_sizes, labels = batch[0], batch[1], batch[2], batch[3]
            else:
                features, coords, bag_sizes, labels = batch

            features = features.to(device)
            coords = coords.to(device)
            bag_sizes = bag_sizes.to(device)

            features = preprocess_features(features)

            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                logits, _ = forward_pass(model, MODEL_TYPE, features, coords, bag_sizes)

            probs = F.softmax(logits.float(), dim=1).cpu().numpy()
            all_labels.append(labels.numpy())
            all_probs.append(probs)

    all_labels = np.concatenate(all_labels)
    all_probs = np.concatenate(all_probs)

    return compute_metrics(all_labels, all_probs)


# =========================================================================
# MAIN: 5-fold CV loop. Outputs results in autoresearch format.
# =========================================================================
if __name__ == "__main__":
    gpu_ids = GPU if isinstance(GPU, list) else [GPU]
    if len(gpu_ids) == 1:
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", str(gpu_ids[0]))
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    print(f"=== autoMIL: {TASK} | {ENCODER} | {MODEL_TYPE} ===")
    print(f"device={device}, gpu={gpu_ids}, seed={SEED}")
    print(f"config={CONFIG}")

    t0 = time.time()
    val_results, test_results = [], []

    for fold in range(N_FOLDS):
        result = train_single_fold(fold, device)
        val_results.append(result["val"])
        test_results.append(result["test"])

    elapsed = time.time() - t0
    peak_vram_mb = (
        torch.cuda.max_memory_allocated() / 1024**2
        if torch.cuda.is_available()
        else 0.0
    )

    print_results(
        val_results,
        test_results,
        task=TASK,
        extra={
            "elapsed_seconds": f"{elapsed:.1f}",
            "peak_vram_mb": f"{peak_vram_mb:.1f}",
            "encoder": ENCODER,
            "model_type": MODEL_TYPE,
        },
    )

    # --- Auto-log to results.tsv ---
    import subprocess

    results_tsv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.tsv")
    header = "commit\tval_auc\tval_bacc\ttest_auc\ttest_bacc\tcomposite\tdelta\tvram_gb\telapsed_min\tstatus\tdescription\n"

    # Get current git commit hash
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short=7", "HEAD"],
            cwd=PROJECT_ROOT, text=True
        ).strip()
    except Exception:
        commit = "unknown"

    val_auc = np.mean([m["auc_roc"] for m in val_results])
    val_bacc = np.mean([m["bacc"] for m in val_results])
    test_auc = np.mean([m["auc_roc"] for m in test_results])
    test_bacc = np.mean([m["bacc"] for m in test_results])
    vram_gb = peak_vram_mb / 1024
    elapsed_min = elapsed / 60

    # Create file with header if it doesn't exist
    if not os.path.exists(results_tsv):
        with open(results_tsv, "w") as f:
            f.write(header)

    # Determine keep/discard via composite score: average of test_auc and test_bacc.
    # Keep if composite > best previous composite.
    composite = (test_auc + test_bacc) / 2
    best_prev_composite = 0.0
    with open(results_tsv, "r") as f:
        for line in f:
            if line.startswith("commit"):
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 5:
                try:
                    prev_comp = (float(parts[3]) + float(parts[4])) / 2
                    best_prev_composite = max(best_prev_composite, prev_comp)
                except ValueError:
                    pass
    status = "keep" if composite > best_prev_composite + 1e-6 else "discard"
    delta_composite = composite - best_prev_composite

    description = globals().get("EXPERIMENT_DESCRIPTION", "unnamed")
    row = (
        f"{commit}\t{val_auc:.6f}\t{val_bacc:.6f}\t{test_auc:.6f}\t{test_bacc:.6f}"
        f"\t{composite:.6f}\t{delta_composite:+.6f}\t{vram_gb:.1f}\t{elapsed_min:.1f}\t"
        f"{status}\t{description}\n"
    )
    with open(results_tsv, "a") as f:
        f.write(row)

    print(f"\nLogged to {results_tsv}")
