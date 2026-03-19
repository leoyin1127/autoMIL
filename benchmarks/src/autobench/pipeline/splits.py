"""Strategy-aware split generation for benchmarking.

Generates split CSVs in the same format as ``prepare.create_stratified_splits``
(columns: train, val, test with slide_ids, padded with NA) so that CLAM's
``return_splits`` and the nnMIL plan builder can consume them identically.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

from autobench.pipeline.config import StrategyConfig


def create_strategy_splits(
    task_csv: str,
    splits_dir: str,
    strategy_cfg: StrategyConfig | None = None,
    n_splits: int = 5,
    seed: int = 42,
) -> list[str]:
    """Create split CSVs using standard k-fold CV.

    Each fold: ~60 % train, ~20 % val, ~20 % test.

    The task CSV must have columns ``slide_id`` and ``label``.
    The output CSV format is identical to the existing CLAM
    format: columns ``[train, val, test]`` with slide_ids, padded with
    ``pd.NA``.

    Splits are stratified by label.

    Parameters
    ----------
    strategy_cfg:
        Reserved for future use.  Currently ignored — all strategies
        use standard stratified k-fold.

    Returns a list of paths to the generated split CSVs.
    """
    df = pd.read_csv(task_csv)
    os.makedirs(splits_dir, exist_ok=True)

    return _splits_standard_cv(df, splits_dir, n_splits, seed)


def _splits_standard_cv(
    df: pd.DataFrame,
    splits_dir: str,
    n_splits: int,
    seed: int,
) -> list[str]:
    """Standard k-fold: test from CV, val carved from train remainder."""
    slide_ids = df["slide_id"].values
    labels = df["label"].values

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    split_paths: list[str] = []

    for fold_idx, (train_val_idx, test_idx) in enumerate(skf.split(slide_ids, labels)):
        test_ids = slide_ids[test_idx]

        tv_slides = slide_ids[train_val_idx]
        tv_labels = labels[train_val_idx]
        inner_skf = StratifiedKFold(n_splits=4, shuffle=True, random_state=seed + fold_idx)
        train_sub_idx, val_sub_idx = next(inner_skf.split(tv_slides, tv_labels))

        train_ids = tv_slides[train_sub_idx]
        val_ids = tv_slides[val_sub_idx]

        path = _write_split_csv(splits_dir, fold_idx, train_ids, val_ids, test_ids)
        split_paths.append(path)

    print(f"  Splits: {splits_dir}  ({n_splits} folds, standard CV)")
    return split_paths


def _write_split_csv(
    splits_dir: str,
    fold_idx: int,
    train_ids: np.ndarray,
    val_ids: np.ndarray,
    test_ids: np.ndarray,
) -> str:
    """Write a single split CSV with columns [train, val, test], padded with NA."""
    max_len = max(len(train_ids), len(val_ids), len(test_ids))

    def _pad(arr: np.ndarray) -> list:
        return list(arr) + [pd.NA] * (max_len - len(arr))

    split_df = pd.DataFrame({
        "train": _pad(train_ids),
        "val": _pad(val_ids),
        "test": _pad(test_ids),
    })
    path = os.path.join(splits_dir, f"splits_{fold_idx}.csv")
    split_df.to_csv(path, index=False)
    return path
