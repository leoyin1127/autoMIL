"""CLAM-specific data preparation: H5 -> PT tensor conversion."""

from __future__ import annotations

import os

import h5py
import torch
from tqdm import tqdm


def convert_h5_to_pt(
    h5_dir: str,
    pt_dir: str,
    encoder_key: str,
    slide_ids: list[str],
) -> int:
    """Convert H5 feature files to PT tensors for CLAM consumption.

    Skips files that already exist (resumable).
    Returns the number of files actually converted.
    """
    pt_files_dir = os.path.join(pt_dir, "pt_files")
    os.makedirs(pt_files_dir, exist_ok=True)
    converted = 0
    skipped = 0

    pbar = tqdm(slide_ids, desc=f"  {encoder_key}", unit="slide")
    for slide_id in pbar:
        pt_path = os.path.join(pt_files_dir, f"{slide_id}.pt")
        if os.path.exists(pt_path):
            skipped += 1
            continue

        h5_path = os.path.join(h5_dir, f"{slide_id}.h5")
        if not os.path.exists(h5_path):
            continue

        try:
            with h5py.File(h5_path, "r") as f:
                features = f["features"][:]
        except (OSError, KeyError) as e:
            raise RuntimeError(
                f"Failed to read features from H5 file: {h5_path}\n"
                f"  Encoder: {encoder_key}\n"
                f"  Slide:   {slide_id}\n"
                f"  Cause:   {type(e).__name__}: {e}\n"
                f"  Likely corrupted/truncated. Re-extract this slide via "
                f"benchmarks/scripts/run_feature_extraction.py --models {encoder_key} --skip_seg"
            ) from e

        features = torch.from_numpy(features).float()
        torch.save(features, pt_path)
        converted += 1
        pbar.set_postfix(converted=converted, skipped=skipped)

    return converted
