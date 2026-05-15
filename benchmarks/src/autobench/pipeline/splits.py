"""Strategy-aware split generation for benchmarking.

Generates split CSVs in the same format as ``prepare.create_stratified_splits``
(columns: train, val, test with slide_ids, padded with NA) so that CLAM's
``return_splits`` and the nnMIL plan builder can consume them identically.

Splits are **patient-level**: all slides from the same ``case_id`` go to the
same fold. This matches CLAM upstream's ``patient_strat=True`` and nnMIL
upstream's patient-keyed stratification, and avoids same-patient leakage
across train/val/test.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from autobench.pipeline.config import StrategyConfig


def create_strategy_splits(
    task_csv: str,
    splits_dir: str,
    strategy_cfg: StrategyConfig | None = None,
    n_splits: int = 5,
    seed: int = 42,
) -> list[str]:
    """Create split CSVs using patient-stratified k-fold CV.

    Each fold: ~80 % (train+val) / ~20 % test, with val carved as ~12.5 %
    of (train+val) to match nnMIL upstream's ``val_frac=0.125``.

    The task CSV must have columns ``case_id``, ``slide_id``, and ``label``.
    All slides from the same ``case_id`` are forced into the same partition
    (train, val, or test) to prevent patient-level leakage.

    Output CSV format: columns ``[train, val, test]`` with slide_ids,
    padded with ``pd.NA`` — identical to CLAM's expected format.

    Parameters
    ----------
    strategy_cfg:
        Reserved for future use.  Currently ignored — all strategies
        use patient-stratified k-fold.

    Returns a list of paths to the generated split CSVs.
    """
    df = pd.read_csv(task_csv)
    if "case_id" not in df.columns:
        raise ValueError(
            f"Task CSV {task_csv} is missing required 'case_id' column. "
            "Patient-level stratification cannot proceed."
        )
    os.makedirs(splits_dir, exist_ok=True)

    return _splits_standard_cv(df, splits_dir, n_splits, seed)


def _splits_standard_cv(
    df: pd.DataFrame,
    splits_dir: str,
    n_splits: int,
    seed: int,
) -> list[str]:
    """Patient-stratified k-fold: test from outer CV, val carved from train+val."""
    slide_ids = df["slide_id"].values
    case_ids = df["case_id"].values
    labels = df["label"].values

    outer = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    split_paths: list[str] = []

    for fold_idx, (train_val_idx, test_idx) in enumerate(outer.split(slide_ids, labels, groups=case_ids)):
        test_ids = slide_ids[test_idx]

        tv_slides = slide_ids[train_val_idx]
        tv_cases = case_ids[train_val_idx]
        tv_labels = labels[train_val_idx]

        # Inner val carve: ~12.5% val (1/8 split) to match nnMIL upstream val_frac=0.125
        inner = StratifiedGroupKFold(n_splits=8, shuffle=True, random_state=seed + fold_idx)
        train_sub_idx, val_sub_idx = next(inner.split(tv_slides, tv_labels, groups=tv_cases))

        train_ids = tv_slides[train_sub_idx]
        val_ids = tv_slides[val_sub_idx]

        _assert_no_patient_leakage(
            train_cases=tv_cases[train_sub_idx],
            val_cases=tv_cases[val_sub_idx],
            test_cases=case_ids[test_idx],
            fold_idx=fold_idx,
        )

        path = _write_split_csv(splits_dir, fold_idx, train_ids, val_ids, test_ids)
        split_paths.append(path)

    print(f"  Splits: {splits_dir}  ({n_splits} folds, patient-stratified CV)")
    return split_paths


def _assert_no_patient_leakage(
    train_cases: np.ndarray,
    val_cases: np.ndarray,
    test_cases: np.ndarray,
    fold_idx: int,
) -> None:
    """Hard fail if any case_id crosses train/val/test boundaries."""
    train_set = set(train_cases.tolist())
    val_set = set(val_cases.tolist())
    test_set = set(test_cases.tolist())
    train_val = train_set & val_set
    train_test = train_set & test_set
    val_test = val_set & test_set
    if train_val or train_test or val_test:
        raise AssertionError(
            f"Patient leakage in fold {fold_idx}: "
            f"train∩val={train_val}, train∩test={train_test}, val∩test={val_test}"
        )


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
