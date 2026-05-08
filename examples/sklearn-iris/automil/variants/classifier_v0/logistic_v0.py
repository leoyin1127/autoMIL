"""Logistic Regression baseline for iris (DEC-02 starter variant)."""
from __future__ import annotations

from sklearn.linear_model import LogisticRegression


def make_classifier(seed: int = 42) -> LogisticRegression:
    """Construct the v0 classifier.

    Hyperparameters are baseline defaults; agents tune them across variants.
    """
    return LogisticRegression(max_iter=200, random_state=seed)
