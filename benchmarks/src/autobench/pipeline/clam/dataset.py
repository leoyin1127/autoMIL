"""Dataset helpers that wrap CLAM's Generic_MIL_Dataset."""

from __future__ import annotations

import os

from autobench.pipeline.clam._imports import Generic_MIL_Dataset, Generic_Split
from autobench.pipeline.config import ExperimentConfig


def create_dataset(
    exp_cfg: ExperimentConfig,
    benchmark_dir: str,
    task_csv_name: str | None = None,
) -> Generic_MIL_Dataset:
    """Instantiate a CLAM Generic_MIL_Dataset for the given experiment.

    *task_csv_name* overrides the default task CSV filename (without .csv
    extension).  For multi-cohort strategies, pass e.g. ``"brca_all"``.
    """
    if task_csv_name is None:
        task_csv_name = exp_cfg.task.name
    csv_path = os.path.join(benchmark_dir, "dataset_csv", f"{task_csv_name}.csv")
    data_dir = os.path.join(benchmark_dir, "features", exp_cfg.encoder_key)

    dataset = Generic_MIL_Dataset(
        data_dir=data_dir,
        csv_path=csv_path,
        shuffle=False,
        seed=exp_cfg.train.seed,
        print_info=False,
        label_dict=exp_cfg.task.label_dict,
        label_col="label",
        patient_strat=False,
        ignore=[],
    )

    # Filter out slides missing .pt feature files (e.g. corrupted WSIs
    # that were silently skipped during feature extraction).
    pt_dir = os.path.join(data_dir, "pt_files")
    mask = dataset.slide_data["slide_id"].apply(
        lambda sid: os.path.exists(os.path.join(pt_dir, f"{sid}.pt"))
    )
    n_missing = (~mask).sum()
    if n_missing > 0:
        missing = dataset.slide_data.loc[~mask, "slide_id"].tolist()
        print(f"[WARNING] Dropping {n_missing} slides missing .pt features: {missing}")
        dataset.slide_data = dataset.slide_data[mask].reset_index(drop=True)
        dataset.cls_ids_prep()

    return dataset


def load_fold_splits(
    dataset: Generic_MIL_Dataset,
    benchmark_dir: str,
    splits_subdir: str,
    fold: int,
) -> tuple[Generic_Split, Generic_Split, Generic_Split]:
    """Load pre-generated split CSV and return (train, val, test) splits.

    *splits_subdir* is the relative path under ``benchmark_dir/splits/``,
    e.g. ``"brca"`` (legacy) or ``"a/brca"`` (strategy-based).
    """
    split_csv = os.path.join(benchmark_dir, "splits", splits_subdir, f"splits_{fold}.csv")
    train_split, val_split, test_split = dataset.return_splits(
        from_id=False, csv_path=split_csv
    )
    return train_split, val_split, test_split
