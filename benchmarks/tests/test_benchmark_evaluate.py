"""Tests for autobench.pipeline.evaluate module."""

import numpy as np
import pytest

from autobench.pipeline.evaluate import (
    compute_confidence_intervals,
    compute_extended_metrics,
)


class TestComputeExtendedMetrics:
    def test_perfect_binary_classification(self):
        y_true = np.array([0, 0, 1, 1, 0])
        y_probs = np.array([[1, 0], [1, 0], [0, 1], [0, 1], [1, 0]], dtype=float)
        y_pred = np.array([0, 0, 1, 1, 0])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        assert m["auc_roc"] == 1.0
        assert m["accuracy"] == 1.0
        assert m["balanced_accuracy"] == 1.0
        assert m["f1"] == 1.0
        assert m["sensitivity"] == 1.0
        assert m["specificity"] == 1.0

    def test_all_wrong_predictions(self):
        y_true = np.array([0, 0, 1, 1])
        y_probs = np.array([[0, 1], [0, 1], [1, 0], [1, 0]], dtype=float)
        y_pred = np.array([1, 1, 0, 0])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        assert m["auc_roc"] == 0.0
        assert m["accuracy"] == 0.0
        assert m["sensitivity"] == 0.0
        assert m["specificity"] == 0.0

    def test_all_predicted_positive(self):
        y_true = np.array([0, 0, 1, 1])
        y_probs = np.array([[0.3, 0.7]] * 4)
        y_pred = np.array([1, 1, 1, 1])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        assert m["sensitivity"] == 1.0
        assert m["specificity"] == 0.0

    def test_all_predicted_negative(self):
        y_true = np.array([0, 0, 1, 1])
        y_probs = np.array([[0.7, 0.3]] * 4)
        y_pred = np.array([0, 0, 0, 0])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        assert m["sensitivity"] == 0.0
        assert m["specificity"] == 1.0

    def test_returns_all_expected_keys(self):
        y_true = np.array([0, 1])
        y_probs = np.array([[0.6, 0.4], [0.3, 0.7]])
        y_pred = np.array([0, 1])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        expected_keys = {"auc_roc", "accuracy", "balanced_accuracy", "f1",
                         "sensitivity", "specificity"}
        assert set(m.keys()) == expected_keys

    def test_all_values_are_floats(self):
        y_true = np.array([0, 1, 0, 1])
        y_probs = np.random.rand(4, 2)
        y_pred = np.array([0, 1, 1, 0])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        for v in m.values():
            assert isinstance(v, float)

    def test_single_class_in_true_labels(self):
        """AUC is nan when only one class present."""
        y_true = np.array([0, 0, 0])
        y_probs = np.array([[0.8, 0.2], [0.6, 0.4], [0.9, 0.1]])
        y_pred = np.array([0, 0, 0])
        m = compute_extended_metrics(y_true, y_probs, y_pred, 2)
        assert np.isnan(m["auc_roc"])


class TestComputeConfidenceIntervals:
    def test_basic_ci(self):
        fold_metrics = [
            {"auc_roc": 0.8, "accuracy": 0.7},
            {"auc_roc": 0.9, "accuracy": 0.8},
            {"auc_roc": 0.85, "accuracy": 0.75},
        ]
        ci = compute_confidence_intervals(fold_metrics)
        assert "auc_roc" in ci
        assert "accuracy" in ci
        assert ci["auc_roc"]["mean"] == pytest.approx(0.85, abs=1e-6)

    def test_ci_keys(self):
        fold_metrics = [{"auc_roc": 0.8}, {"auc_roc": 0.9}]
        ci = compute_confidence_intervals(fold_metrics)
        assert set(ci["auc_roc"].keys()) == {"mean", "std", "ci_low", "ci_high"}

    def test_ci_ordering(self):
        fold_metrics = [{"auc_roc": v} for v in [0.7, 0.8, 0.9, 0.85, 0.75]]
        ci = compute_confidence_intervals(fold_metrics)
        assert ci["auc_roc"]["ci_low"] < ci["auc_roc"]["mean"]
        assert ci["auc_roc"]["ci_high"] > ci["auc_roc"]["mean"]

    def test_identical_values_zero_ci_width(self):
        fold_metrics = [{"auc_roc": 0.8}] * 5
        ci = compute_confidence_intervals(fold_metrics)
        assert ci["auc_roc"]["std"] == 0.0
        assert ci["auc_roc"]["ci_low"] == ci["auc_roc"]["ci_high"]

    def test_handles_nan_values(self):
        fold_metrics = [
            {"auc_roc": float("nan")},
            {"auc_roc": 0.8},
        ]
        ci = compute_confidence_intervals(fold_metrics)
        # Should not crash; single valid value
        assert not np.isnan(ci["auc_roc"]["mean"])

    def test_single_fold(self):
        fold_metrics = [{"auc_roc": 0.85}]
        ci = compute_confidence_intervals(fold_metrics)
        assert ci["auc_roc"]["mean"] == 0.85
        assert ci["auc_roc"]["ci_low"] == ci["auc_roc"]["ci_high"]
