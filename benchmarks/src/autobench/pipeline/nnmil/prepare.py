"""Generate nnMIL dataset artifacts (dataset.json, dataset.csv, dataset_plan.json).

We generate ``dataset_plan.json`` ourselves (not using nnMIL's ExperimentPlanner)
to control splits precisely -- ensuring they match the shared split CSVs used by
CLAM.  We DO use nnMIL's ``ClassificationTrainer`` for actual training.
"""

from __future__ import annotations

import json
import os

import h5py
import numpy as np
import pandas as pd


def prepare_nnmil_experiment(
    benchmark_dir: str,
    task_name: str,
    encoder_key: str,
    strategy: str,
    label_col: str,
    label_dict: dict[str, int],
    embed_dim: int,
    features_base_dir: str,
    dataset_name: str = "dataset",
    seed: int = 42,
    n_splits: int = 5,
) -> str:
    """Prepare nnMIL dataset artifacts for one (task, encoder, strategy) combo.

    Returns the path to the generated ``dataset_plan.json``.

    The generated plan embeds the SAME splits from the shared split CSVs
    into nnMIL's ``data_splits`` format so that CLAM and nnMIL use
    identical patient/slide assignments.
    """
    dataset_dir = os.path.join(
        benchmark_dir, "nnmil", strategy, f"{task_name}_{encoder_key}"
    )
    plan_path = os.path.join(dataset_dir, "dataset_plan.json")

    if os.path.exists(plan_path):
        return plan_path

    os.makedirs(dataset_dir, exist_ok=True)

    # Task CSV is always {task_name}.csv
    task_csv_path = os.path.join(benchmark_dir, "dataset_csv", f"{task_name}.csv")

    task_df = pd.read_csv(task_csv_path)
    h5_dir = os.path.join(features_base_dir, f"features_{encoder_key}")

    # Filter to slides that have H5 feature files
    has_h5 = task_df["slide_id"].apply(
        lambda sid: os.path.exists(os.path.join(h5_dir, f"{sid}.h5"))
    )
    n_missing = (~has_h5).sum()
    if n_missing > 0:
        print(f"  Skipping {n_missing} slides without H5 features for {encoder_key}")
        task_df = task_df[has_h5].reset_index(drop=True)

    # --- dataset.json ---
    # Invert label_dict: {"neg": 0, "pos": 1} -> {"0": "neg", "1": "pos"}
    labels_map = {str(v): k for k, v in label_dict.items()}
    dataset_json = {
        "name": f"{dataset_name}_{task_name}_{strategy}",
        "description": f"{dataset_name} {task_name.upper()} classification, strategy {strategy}",
        "task_type": "classification",
        "task_name": f"{task_name}_{strategy}_{encoder_key}",
        "evaluation_setting": "5fold",
        "feature_dir": h5_dir,
        "labels": labels_map,
        "metric": "bacc",
        "modality": {"0": "Histopathology"},
    }
    with open(os.path.join(dataset_dir, "dataset.json"), "w") as f:
        json.dump(dataset_json, f, indent=2)

    # --- dataset.csv ---
    # Map string labels to ints for nnMIL
    csv_df = pd.DataFrame({
        "slide_id": task_df["slide_id"],
        "patient_id": task_df["case_id"],
        "label": task_df["label"].map(label_dict),
    })
    csv_df.to_csv(os.path.join(dataset_dir, "dataset.csv"), index=False)

    # --- feature statistics (from a sample of H5 files) ---
    feature_stats = _analyze_features(h5_dir, task_df["slide_id"].tolist(), embed_dim)

    # --- data splits (from shared split CSVs) ---
    splits_dir = os.path.join(benchmark_dir, "splits", strategy, task_name)
    data_splits = _load_splits_as_nnmil_format(
        splits_dir, task_df, label_dict, n_splits
    )

    # --- dataset_plan.json ---
    plan = {
        **dataset_json,
        "feature_statistics": feature_stats,
        "data_splits": data_splits,
        "training_configuration": _generate_training_config(feature_stats, len(task_df), n_classes=len(label_dict)),
        "random_seed": seed,
    }
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)

    print(f"  nnMIL plan: {plan_path}")
    return plan_path


def _analyze_features(
    h5_dir: str,
    slide_ids: list[str],
    expected_dim: int,
    sample_size: int = 100,
) -> dict:
    """Analyze H5 feature files to get statistics for nnMIL config."""
    patch_counts: list[int] = []
    feat_dim = expected_dim

    sample = slide_ids[:sample_size] if len(slide_ids) > sample_size else slide_ids
    for sid in sample:
        h5_path = os.path.join(h5_dir, f"{sid}.h5")
        if not os.path.exists(h5_path):
            continue
        with h5py.File(h5_path, "r") as f:
            shape = f["features"].shape
            feat_dim = shape[1]
            patch_counts.append(shape[0])

    if not patch_counts:
        patch_counts = [256]  # fallback

    arr = np.array(patch_counts)
    median = float(np.median(arr))
    return {
        "feature_dimension": feat_dim,
        "num_patches_per_slide": {
            "min": int(arr.min()),
            "max": int(arr.max()),
            "mean": float(arr.mean()),
            "median": median,
            "percentile_25": float(np.percentile(arr, 25)),
            "percentile_75": float(np.percentile(arr, 75)),
            "percentile_95": float(np.percentile(arr, 95)),
        },
        "recommended_max_seq_length": min(int(median * 0.5), 4096),
    }


def _load_splits_as_nnmil_format(
    splits_dir: str,
    task_df: pd.DataFrame,
    label_dict: dict[str, int],
    n_splits: int,
) -> dict:
    """Convert shared split CSVs to nnMIL's data_splits format.

    Each fold in the output has::

        {
            "train": {"slide_ids": [...], "slide_info": [...]},
            "val":   {"slide_ids": [...], "slide_info": [...]},
            "test":  {"slide_ids": [...], "slide_info": [...]},
        }

    where each ``slide_info`` entry is::

        {"slide_id": "...", "patient_id": "...", "label": 0}
    """
    # Build lookup: slide_id -> (case_id, label_int)
    lookup: dict[str, tuple[str, int]] = {}
    for _, row in task_df.iterrows():
        label_int = label_dict.get(row["label"], row["label"])
        if isinstance(label_int, str):
            label_int = int(label_int)
        lookup[row["slide_id"]] = (row["case_id"], int(label_int))

    data_splits: dict[str, dict] = {}

    for fold_idx in range(n_splits):
        split_path = os.path.join(splits_dir, f"splits_{fold_idx}.csv")
        if not os.path.exists(split_path):
            break

        split_df = pd.read_csv(split_path)
        fold_data: dict[str, dict] = {}

        for split_name in ("train", "val", "test"):
            if split_name not in split_df.columns:
                continue
            sids = split_df[split_name].dropna().tolist()
            slide_info = []
            for sid in sids:
                if sid in lookup:
                    case_id, label_int = lookup[sid]
                    slide_info.append({
                        "slide_id": sid,
                        "patient_id": case_id,
                        "label": label_int,
                    })
            fold_data[split_name] = {
                "slide_ids": [si["slide_id"] for si in slide_info],
                "slide_info": slide_info,
            }

        data_splits[f"fold_{fold_idx}"] = fold_data

    return data_splits


def _generate_training_config(feature_stats: dict, n_samples: int, n_classes: int = 2) -> dict:
    """Generate nnMIL training configuration from feature statistics."""
    feat_dim = feature_stats["feature_dimension"]
    hidden_dim = max(256, feat_dim // 4)
    median_patches = feature_stats["num_patches_per_slide"]["median"]

    # Cap max_seq_length at 4096 (standard in MIL literature: AB-MIL, TransMIL, DSMIL).
    # Training uses random subsampling per epoch so capping acts as data augmentation.
    # Val/test always use ALL patches (dataset overrides max_seq_length=None).
    MAX_SEQ_LENGTH_CAP = 4096
    max_seq_length = min(int(median_patches * 0.5), MAX_SEQ_LENGTH_CAP)

    # VRAM-aware batch_size: each experiment must fit in ~5 GB.
    # Conservative estimate: 20 bytes per element (bf16 fwd + fp32 bwd + overhead).
    VRAM_BUDGET_BYTES = 5 * 1024**3
    MODEL_OVERHEAD_BYTES = int(0.5 * 1024**3)
    per_sample_bytes = max_seq_length * feat_dim * 20
    vram_batch = max(8, (VRAM_BUDGET_BYTES - MODEL_OVERHEAD_BYTES) // per_sample_bytes)

    # Data-driven batch minimum: larger for smaller datasets to ensure minority class visibility
    if n_samples < 100:
        data_batch = 16
    elif n_samples < 500:
        data_batch = 32
    else:
        data_batch = 48

    batch_size = min(data_batch, vram_batch)

    return {
        "feature_dimension": feat_dim,
        "hidden_dim": hidden_dim,
        "max_seq_length": max_seq_length,
        "use_original_length": False,
        "batch_size": batch_size,
        "learning_rate": 3e-4,
        "batch_sampler": "balanced",
        "num_epochs": 100,
        "warmup_epochs": 10 if n_samples < 200 else 5,
        "weight_decay": 0.01 if hidden_dim >= 512 else 1e-4,
        "dropout": 0.25,
        "patience": 10,
        "num_classes": n_classes,
    }
