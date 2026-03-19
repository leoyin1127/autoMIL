"""Extended evaluation metrics and cross-fold confidence intervals."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)


def compute_extended_metrics(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    y_pred: np.ndarray,
    n_classes: int,
) -> dict[str, float]:
    """Compute comprehensive classification metrics for one evaluation split."""
    metrics: dict[str, float] = {}

    # AUC-ROC
    if n_classes == 2:
        try:
            metrics["auc_roc"] = float(roc_auc_score(y_true, y_probs[:, 1]))
        except ValueError:
            metrics["auc_roc"] = float("nan")
    else:
        try:
            metrics["auc_roc"] = float(
                roc_auc_score(y_true, y_probs, multi_class="ovr")
            )
        except ValueError:
            metrics["auc_roc"] = float("nan")

    metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
    metrics["balanced_accuracy"] = float(balanced_accuracy_score(y_true, y_pred))
    if n_classes == 2:
        metrics["f1"] = float(f1_score(y_true, y_pred, pos_label=1, zero_division=0))
    else:
        metrics["f1"] = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    if n_classes == 2:
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()
        metrics["sensitivity"] = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        metrics["specificity"] = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    else:
        metrics["sensitivity"] = float("nan")
        metrics["specificity"] = float("nan")

    return metrics


def compute_confidence_intervals(
    fold_metrics: list[dict[str, float]],
    confidence: float = 0.95,
) -> dict[str, dict[str, float]]:
    """Compute mean and 95 % CI across folds via the t-distribution."""
    from scipy import stats

    metric_names = list(fold_metrics[0].keys())
    n = len(fold_metrics)
    alpha = 1 - confidence
    t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1) if n > 1 else 0.0

    results: dict[str, dict[str, float]] = {}
    for name in metric_names:
        values = np.array([fm[name] for fm in fold_metrics])
        valid = values[~np.isnan(values)]

        if len(valid) < 2:
            mean_val = float(np.nanmean(values))
            results[name] = {
                "mean": mean_val,
                "std": 0.0,
                "ci_low": mean_val,
                "ci_high": mean_val,
            }
            continue

        mean = float(np.mean(valid))
        std = float(np.std(valid, ddof=1))
        se = std / np.sqrt(len(valid))
        results[name] = {
            "mean": mean,
            "std": std,
            "ci_low": float(mean - t_crit * se),
            "ci_high": float(mean + t_crit * se),
        }

    return results
