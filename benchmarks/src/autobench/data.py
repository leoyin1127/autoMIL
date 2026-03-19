"""Data loading and filtering utilities.

All functions accept a ``DatasetConfig`` to determine column names and
filtering rules -- no dataset-specific constants are hardcoded.
"""

from __future__ import annotations

import os

import pandas as pd

from autobench.config import DatasetConfig


def load_all_slides(
    mapping_csv: str,
    ds: DatasetConfig,
) -> pd.DataFrame:
    """Load all slides from a mapping CSV (for datasets without cohort/status filtering)."""
    df = pd.read_csv(mapping_csv)
    if ds.status_column and ds.status_value:
        df = df[df[ds.status_column] == ds.status_value].reset_index(drop=True)
    return df


def validate_slides(
    filtered_df: pd.DataFrame,
    wsi_dir: str,
    ds: DatasetConfig,
) -> tuple[pd.DataFrame, list[str]]:
    """Open each WSI file and read a small region at every pyramid level.

    Returns (valid_df, failed_slides).
    """
    from openslide import OpenSlide, OpenSlideError

    slide_col = ds.slide_id_column
    failed: list[str] = []

    for raw_id in filtered_df[slide_col]:
        filename = ds.get_wsi_filename(raw_id)
        path = os.path.join(wsi_dir, filename)
        try:
            slide = OpenSlide(path)
            num_levels = slide.level_count
            slide.close()

            for level in range(num_levels):
                s = OpenSlide(path)
                lw, lh = s.level_dimensions[level]
                s.read_region((0, 0), level, (min(lw, 256), min(lh, 256)))
                s.close()
        except (OpenSlideError, FileNotFoundError) as exc:
            print(f"Skipping {raw_id}: {exc}")
            failed.append(raw_id)

    valid_df = filtered_df[~filtered_df[slide_col].isin(failed)].reset_index(drop=True)

    if failed:
        skipped_path = os.path.join(os.path.dirname(wsi_dir.rstrip("/")), "skipped_slides.txt")
        with open(skipped_path, "w") as f:
            f.write("\n".join(failed) + "\n")

    return valid_df, failed


def generate_wsi_list_csv(
    filtered_df: pd.DataFrame,
    output_path: str,
    ds: DatasetConfig,
) -> str:
    """Write a CSV with a 'wsi' column of slide filenames for TRIDENT."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wsi_df = pd.DataFrame({"wsi": filtered_df[ds.slide_id_column].apply(ds.get_wsi_filename)})
    wsi_df.to_csv(output_path, index=False)
    return output_path
