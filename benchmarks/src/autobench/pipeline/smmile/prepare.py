"""Convert H5 features to SMMILe NIC format and generate superpixel maps.

SMMILe expects two .npy files per slide:
  1. Feature file: dict with 'feature' (C, H, W), 'index' (N, 2), 'inst_label', 'mask' (H, W)
  2. Superpixel file: dict with 'm_slic' (H, W), 'm_adj' (n_sp, n_sp)

Our H5 files have: 'features' (N, embed_dim) and 'coords' (N, 2) with 256px spacing.
"""

from __future__ import annotations

import os

import h5py
import numpy as np
from skimage import segmentation
from tqdm import tqdm


def _build_nic_grid(
    features: np.ndarray,
    coords: np.ndarray,
    patch_size: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Arrange flat features into a spatial grid (Neural Image Coordinates).

    Args:
        features: (N, embed_dim) patch embeddings.
        coords: (N, 2) pixel coordinates (x, y).
        patch_size: Step size between patches in pixels.

    Returns:
        feature_nic: (embed_dim, H, W) spatial feature grid (NaN filled then zeroed).
        mask: (H, W) binary mask (1 = valid patch, 0 = empty).
        index: (N, 2) original coordinates.
    """
    x, y = coords[:, 0], coords[:, 1]
    x_min, x_max = x.min(), x.max()
    y_min, y_max = y.min(), y.max()
    grid_h = (x_max - x_min) // patch_size + 1
    grid_w = (y_max - y_min) // patch_size + 1

    embed_dim = features.shape[1]
    feature_nic = np.full((embed_dim, grid_h, grid_w), np.nan, dtype=np.float32)
    mask = np.zeros((grid_h, grid_w), dtype=np.float64)

    for feat, cx, cy in zip(features, x, y):
        gi = (cx - x_min) // patch_size
        gj = (cy - y_min) // patch_size
        feature_nic[:, gi, gj] = feat
        mask[gi, gj] = 1.0

    # Zero-fill NaN positions (SMMILe convention)
    feature_nic = np.nan_to_num(feature_nic, nan=0.0)

    return feature_nic, mask, coords.copy()


def convert_h5_to_nic(
    h5_path: str,
    output_dir: str,
    patch_size: int = 256,
) -> str:
    """Convert a single H5 feature file to SMMILe NIC .npy format.

    Returns the output path.
    """
    os.makedirs(output_dir, exist_ok=True)
    slide_id = os.path.splitext(os.path.basename(h5_path))[0]
    out_name = f"{slide_id}_0_{patch_size}.npy"
    out_path = os.path.join(output_dir, out_name)

    with h5py.File(h5_path, "r") as f:
        features = f["features"][:]
        coords = f["coords"][:]

    feature_nic, mask, index = _build_nic_grid(features, coords, patch_size)

    record = {
        "feature": feature_nic,
        "index": index,
        "inst_label": [-1] * len(coords),
        "mask": mask,
    }
    np.save(out_path, record)
    return out_path


def convert_all_h5_to_nic(
    h5_dir: str,
    output_dir: str,
    patch_size: int = 256,
) -> list[str]:
    """Batch convert all H5 files in a directory to NIC .npy format."""
    os.makedirs(output_dir, exist_ok=True)
    h5_files = sorted(f for f in os.listdir(h5_dir) if f.endswith(".h5"))

    results = []
    for h5_name in tqdm(h5_files, desc=f"H5->NIC ({os.path.basename(h5_dir)})"):
        h5_path = os.path.join(h5_dir, h5_name)
        results.append(convert_h5_to_nic(h5_path, output_dir, patch_size))
    return results


def _generate_adjacency_matrix(sp_map: np.ndarray) -> np.ndarray:
    """Build adjacency matrix from a superpixel label map."""
    n_sp = int(sp_map.max()) + 1
    adj = np.zeros((n_sp, n_sp), dtype=np.int32)
    rows, cols = sp_map.shape

    for i in range(rows):
        for j in range(cols):
            cur = sp_map[i, j]
            if cur == 0:
                continue
            if i > 0 and sp_map[i - 1, j] != cur:
                nb = sp_map[i - 1, j]
                adj[cur, nb] = 1
                adj[nb, cur] = 1
            if j > 0 and sp_map[i, j - 1] != cur:
                nb = sp_map[i, j - 1]
                adj[cur, nb] = 1
                adj[nb, cur] = 1
    return adj


def generate_superpixels(
    npy_path: str,
    output_dir: str,
    n_segments_per_sp: int = 16,
    compactness: int = 50,
) -> str:
    """Generate superpixel segmentation for a single NIC .npy file.

    Uses SLIC on the feature grid (normalized to 0-255 for SLIC).
    Does NOT transpose m_slic; the dataset class handles transposing
    to match SMMILe's convention.

    Returns the output path.
    """
    os.makedirs(output_dir, exist_ok=True)
    basename = os.path.basename(npy_path)
    out_path = os.path.join(output_dir, basename)

    record = np.load(npy_path, allow_pickle=True)[()]
    feature_nic = record["feature"]  # (C, H, W)
    mask = record["mask"]            # (H, W) - use stored mask

    n_patches = int(mask.sum())
    if n_patches < 2:
        sp_map = np.zeros(mask.shape, dtype=np.int32)
        adj = np.zeros((1, 1), dtype=np.int32)
        np.save(out_path, {"m_slic": sp_map, "m_adj": adj})
        return out_path

    # Normalize features to 0-255 for SLIC
    fmin, fmax = feature_nic.min(), feature_nic.max()
    denom = fmax - fmin if fmax != fmin else 1.0
    feat_norm = (feature_nic - fmin) / denom * 255.0

    # Transpose to (H, W, C) for skimage SLIC
    data = feat_norm.transpose(1, 2, 0)

    n_segments = max(2, n_patches // n_segments_per_sp)
    sp_map = segmentation.slic(
        data,
        n_segments=n_segments,
        mask=mask.astype(bool),
        compactness=compactness,
        start_label=1,
    )
    # Store as (H, W) - NOT transposed. Dataset class transposes later.

    adj = _generate_adjacency_matrix(sp_map)
    np.save(out_path, {"m_slic": sp_map, "m_adj": adj})
    return out_path


def generate_all_superpixels(
    npy_dir: str,
    output_dir: str,
    n_segments_per_sp: int = 16,
    compactness: int = 50,
) -> list[str]:
    """Batch generate superpixel maps for all NIC .npy files."""
    os.makedirs(output_dir, exist_ok=True)
    npy_files = sorted(f for f in os.listdir(npy_dir) if f.endswith(".npy"))

    results = []
    for npy_name in tqdm(npy_files, desc=f"Superpixels ({os.path.basename(npy_dir)})"):
        npy_path = os.path.join(npy_dir, npy_name)
        results.append(
            generate_superpixels(npy_path, output_dir, n_segments_per_sp, compactness)
        )
    return results


def prepare_smmile_data(
    features_base_dir: str,
    smmile_dir: str,
    encoder_keys: list[str],
    patch_size: int = 256,
    n_segments_per_sp: int = 16,
    compactness: int = 50,
) -> None:
    """Full preparation pipeline: convert H5 -> NIC and generate superpixels.

    Idempotent: skips already-converted files.

    Args:
        features_base_dir: Directory containing features_{encoder}/ subdirs with H5 files.
        smmile_dir: Output base directory for SMMILe data.
        encoder_keys: List of encoder names to process.
        patch_size: Patch step size in pixels.
        n_segments_per_sp: Patches per superpixel segment (default 16).
        compactness: SLIC compactness parameter (default 50).
    """
    for enc in encoder_keys:
        h5_dir = os.path.join(features_base_dir, f"features_{enc}")
        if not os.path.isdir(h5_dir):
            print(f"[SKIP] No H5 directory for encoder '{enc}': {h5_dir}")
            continue

        npy_dir = os.path.join(smmile_dir, "features_npy", enc)
        sp_dir = os.path.join(smmile_dir, "superpixels", enc)

        # Step 1: H5 -> NIC (skip existing)
        existing_npy = set(
            f for f in os.listdir(npy_dir) if f.endswith(".npy")
        ) if os.path.isdir(npy_dir) else set()
        h5_files = [f for f in os.listdir(h5_dir) if f.endswith(".h5")]
        needed = [
            f for f in h5_files
            if f.replace(".h5", f"_0_{patch_size}.npy") not in existing_npy
        ]
        if needed:
            print(f"\n[{enc}] Converting {len(needed)}/{len(h5_files)} H5 -> NIC")
            os.makedirs(npy_dir, exist_ok=True)
            for h5_name in tqdm(needed, desc=f"H5->NIC ({enc})"):
                convert_h5_to_nic(os.path.join(h5_dir, h5_name), npy_dir, patch_size)
        else:
            print(f"[{enc}] NIC conversion already done ({len(existing_npy)} files)")

        # Step 2: Superpixels (skip existing)
        sp_existing = set(
            f for f in os.listdir(sp_dir) if f.endswith(".npy")
        ) if os.path.isdir(sp_dir) else set()
        npy_files = [f for f in os.listdir(npy_dir) if f.endswith(".npy")]
        sp_needed = [f for f in npy_files if f not in sp_existing]
        if sp_needed:
            print(f"[{enc}] Generating {len(sp_needed)}/{len(npy_files)} superpixel maps")
            os.makedirs(sp_dir, exist_ok=True)
            for npy_name in tqdm(sp_needed, desc=f"Superpixels ({enc})"):
                generate_superpixels(
                    os.path.join(npy_dir, npy_name), sp_dir,
                    n_segments_per_sp, compactness,
                )
        else:
            print(f"[{enc}] Superpixels already done ({len(sp_existing)} files)")
