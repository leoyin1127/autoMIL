"""SMMILe evaluation: run inference and compute metrics matching benchmark schema.

Also extracts per-patch detection scores for tumor ROI visualization.
"""

from __future__ import annotations

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)


def evaluate_smmile_model(
    model,
    loader,
    device: torch.device,
    superpixel: bool = True,
    sp_smooth: bool = True,
    G: int = 4,
    inst_refinement: bool = False,
    extract_patch_scores: bool = False,
) -> dict:
    """Run inference and return predictions + metrics dict.

    Args:
        extract_patch_scores: If True, also collect per-patch detection scores
            and coordinates for tumor ROI visualization.
    """
    model.eval()
    all_probs = []
    all_labels = []
    all_preds = []
    slide_ids = []
    patch_scores_per_slide = {}

    with torch.no_grad():
        for batch_idx, (data, label, cors, inst_label) in enumerate(loader):
            data = data.to(device)
            label_val = label.to(device).float()

            mask = cors[1]
            sp = cors[2]
            adj = cors[3]
            coords_nd = cors[4]

            score, Y_prob, Y_hat, ref_score, results_dict = model(
                data, mask, sp, adj,
                label=label_val,
                superpixels=superpixel,
                sp_smooth=sp_smooth,
                group_numbers=G,
                instance_eval=inst_refinement,
            )

            prob = Y_prob[0].cpu().item()
            pred = int(prob > 0.5)

            all_probs.append(prob)
            all_labels.append(label.item())
            all_preds.append(pred)

            sid = None
            if hasattr(loader.dataset, "slide_data"):
                sid = loader.dataset.slide_data["slide_id"].iloc[batch_idx]
                slide_ids.append(sid)

            # Extract per-patch scores for tumor ROI
            # SMMILe returns patch-level detection scores as the first return
            # value (score), not inside results_dict.  score shape: (N, 1).
            # When instance refinement is on, ref_score[:,1] gives per-patch
            # tumor-class confidence from the reference network.
            if extract_patch_scores and sid is not None:
                if inst_refinement and ref_score is not None:
                    raw = ref_score[:, 1].detach().cpu().numpy()
                else:
                    raw = score[:, 0].detach().cpu().numpy()
                # Min-max normalise to [0, 1]
                rmin, rmax = raw.min(), raw.max()
                det = (raw - rmin) / (rmax - rmin + 1e-8)
                patch_scores_per_slide[sid] = {
                    "coords": coords_nd.cpu().numpy() if isinstance(coords_nd, torch.Tensor) else np.array(coords_nd),
                    "det_scores": det,
                }

    all_probs_np = np.array(all_probs)
    all_labels_np = np.array(all_labels, dtype=int)
    all_preds_np = np.array(all_preds, dtype=int)

    metrics = _compute_binary_metrics(all_labels_np, all_probs_np, all_preds_np)

    result = {
        "slide_ids": slide_ids,
        "y_true": all_labels_np,
        "y_prob": all_probs_np,
        "y_hat": all_preds_np,
        "metrics": metrics,
    }

    if extract_patch_scores:
        result["patch_scores"] = patch_scores_per_slide

    return result


def _compute_binary_metrics(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    y_pred: np.ndarray,
) -> dict:
    """Compute metrics matching our benchmark evaluate.py schema."""
    metrics = {}

    try:
        metrics["auc_roc"] = float(roc_auc_score(y_true, y_prob))
    except ValueError:
        metrics["auc_roc"] = float("nan")

    metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
    metrics["balanced_accuracy"] = float(balanced_accuracy_score(y_true, y_pred))
    metrics["f1"] = float(f1_score(y_true, y_pred, pos_label=1, zero_division=0))

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    metrics["sensitivity"] = tp / max(tp + fn, 1)
    metrics["specificity"] = tn / max(tn + fp, 1)

    return metrics
