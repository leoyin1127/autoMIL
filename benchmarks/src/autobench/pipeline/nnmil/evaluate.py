"""Normalize nnMIL metrics to shared benchmark format.

Methods-note on AUC formula provenance
--------------------------------------
The CLAM and nnMIL paths in this wrapper compute multi-class AUC differently,
and the difference is intentional — each path matches its own upstream.

- CLAM path:  ``pipeline/evaluate.py::compute_extended_metrics`` recomputes
  AUC from predictions using upstream CLAM's per-class ``roc_curve`` +
  ``nanmean`` formula (``lib/CLAM/utils/core_utils.py:514-527``).
- nnMIL path: the AUC value passed in via ``raw_metrics["{split}/auroc"]``
  is produced by nnMIL's trainer using
  ``sklearn.metrics.roc_auc_score(multi_class='ovr', average='macro')``
  (``lib/nnMIL/utilities/utils.py:130-141``). We map it through without
  recomputation.

For binary tasks the two formulas agree. For multi-class tasks (e.g. CLWD
``subtype_7class``) the numbers will differ. This is faithful to each
framework's published methodology; cross-framework multi-class AUC
comparison should note the asymmetry.
"""

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

    The ``auc_roc`` value here is the OvR-macro AUC produced by nnMIL's
    trainer; see the module docstring for the provenance asymmetry vs. the
    CLAM path.
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
