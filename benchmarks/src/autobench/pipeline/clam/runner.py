"""Single-experiment runner: all folds for one (task, encoder, model) combo."""

from __future__ import annotations

import json
import os

import torch

from autobench.pipeline.config import ExperimentConfig
from autobench.pipeline.clam.dataset import create_dataset, load_fold_splits
from autobench.pipeline.evaluate import compute_confidence_intervals
from autobench.pipeline.clam.train import train_fold


def run_experiment(
    exp_cfg: ExperimentConfig,
    benchmark_dir: str,
    device: torch.device,
    wandb_project: str | None = None,
    results_dir: str | None = None,
) -> dict:
    """Run all folds for a single CLAM experiment and return aggregated results."""
    if results_dir is None:
        results_dir = os.path.join(benchmark_dir, "results", exp_cfg.results_subdir)
    os.makedirs(results_dir, exist_ok=True)

    exp_cfg.save(os.path.join(results_dir, "config.json"))

    task_csv_name = exp_cfg.task.name

    dataset = create_dataset(exp_cfg, benchmark_dir, task_csv_name=task_csv_name)

    # Splits directory: splits/{strategy}/{task}/
    splits_subdir = os.path.join(exp_cfg.strategy, exp_cfg.task.name)

    fold_results: list[dict] = []
    for fold in range(exp_cfg.n_folds):
        train_split, val_split, test_split = load_fold_splits(
            dataset, benchmark_dir, splits_subdir, fold,
        )
        result = train_fold(
            exp_cfg, train_split, val_split, test_split,
            fold, results_dir, device, wandb_project=wandb_project,
        )
        fold_results.append(result)

    test_fold_metrics = [fr["test_metrics"] for fr in fold_results]
    val_fold_metrics = [fr["val_metrics"] for fr in fold_results]

    exp_summary = {
        "experiment_id": exp_cfg.experiment_id,
        "task": exp_cfg.task.name,
        "encoder": exp_cfg.encoder_key,
        "embed_dim": exp_cfg.embed_dim,
        "model_type": exp_cfg.model.model_type,
        "framework": exp_cfg.framework.value,
        "strategy": exp_cfg.strategy,
        "n_folds": exp_cfg.n_folds,
        "seed": exp_cfg.train.seed,
        "test": compute_confidence_intervals(test_fold_metrics),
        "val": compute_confidence_intervals(val_fold_metrics),
        "per_fold_test": test_fold_metrics,
        "per_fold_val": val_fold_metrics,
    }

    summary_path = os.path.join(results_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(exp_summary, f, indent=2)

    return exp_summary
