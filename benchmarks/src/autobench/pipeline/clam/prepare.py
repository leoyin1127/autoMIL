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

        with h5py.File(h5_path, "r") as f:
            features = f["features"][:]

        features = torch.from_numpy(features).float()
        torch.save(features, pt_path)
        converted += 1
        pbar.set_postfix(converted=converted, skipped=skipped)

    return converted
