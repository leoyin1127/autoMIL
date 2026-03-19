"""Normalize nnMIL metrics to shared benchmark format."""

from __future__ import annotations

# nnMIL's evaluate(split='test') returns keys like "test_test/bacc", "test_test/auroc", etc.
# We map these to our unified metric names used by compute_confidence_intervals().

_NNMIL_TO_SHARED: dict[str, str] = {
    "acc": "accuracy",
    "bacc": "balanced_accuracy",
    "auroc": "auc_roc",
    "weighted_f1": "f1",
    "kappa": "kappa",
}


def normalize_nnmil_metrics(raw_metrics: dict, split: str = "test") -> dict[str, float]:
    """Map nnMIL metric keys to the shared benchmark schema.

    nnMIL returns keys like ``{split}_{split}/bacc`` (e.g. ``test_test/bacc``).
    We extract the metric suffix and map to our standard names.

    Returns a dict compatible with ``compute_extended_metrics`` output
    (keys: auc_roc, accuracy, balanced_accuracy, f1, sensitivity, specificity).
    """
    result: dict[str, float] = {}

    for raw_key, value in raw_metrics.items():
        # Extract the metric suffix after the last "/"
        if "/" not in raw_key:
            continue
        suffix = raw_key.rsplit("/", 1)[1]
        if suffix in _NNMIL_TO_SHARED:
            result[_NNMIL_TO_SHARED[suffix]] = float(value)

    # nnMIL doesn't compute sensitivity/specificity; set to NaN
    result.setdefault("sensitivity", float("nan"))
    result.setdefault("specificity", float("nan"))

    return result
