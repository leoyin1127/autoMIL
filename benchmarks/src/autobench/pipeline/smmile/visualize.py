"""SMMILe tumor ROI heatmap visualization.

Generates slide-level heatmap overlays from per-patch detection scores,
enabling pathologist review of predicted tumor regions.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

try:
    import openslide
except ImportError:
    openslide = None

try:
    from scipy.ndimage import gaussian_filter
except ImportError:
    gaussian_filter = None


def generate_slide_heatmap(
    npz_path: str,
    svs_path: str,
    output_path: str,
    patch_size: int = 256,
    thumbnail_max_dim: int = 2048,
    cmap: str = "RdYlBu_r",
    alpha: float = 0.5,
    score_threshold: float = 0.0,
    sigma: float | None = 2.0,
    title: str | None = None,
) -> str:
    """Generate a heatmap overlay for one slide.

    Args:
        npz_path: Path to .npz with 'coords' (N,2) and 'det_scores' (N,).
        svs_path: Path to .svs whole-slide image.
        output_path: Where to save the output PNG.
        patch_size: Patch size in pixels at full resolution.
        thumbnail_max_dim: Maximum dimension of the output image.
        cmap: Matplotlib colormap name.
        alpha: Heatmap overlay opacity (0=transparent, 1=opaque).
        score_threshold: Only show patches with score >= threshold.
        sigma: Gaussian smoothing sigma in grid units. None = no smoothing.
        title: Optional title text on the image.

    Returns:
        Path to the saved PNG.
    """
    if openslide is None:
        raise ImportError("openslide-python is required for heatmap generation")

    # Load patch scores
    data = np.load(npz_path)
    coords = data["coords"]  # (N, 2) - (x, y) pixel positions at level 0
    det_scores = data["det_scores"]  # (N,) float32 in [0, 1]

    # Convert pixel coords to grid indices
    grid_cols = coords[:, 0] // patch_size
    grid_rows = coords[:, 1] // patch_size

    # Build 2D score grid (offset to 0-based)
    col_offset, row_offset = grid_cols.min(), grid_rows.min()
    grid_cols -= col_offset
    grid_rows -= row_offset
    grid_h = grid_rows.max() + 1
    grid_w = grid_cols.max() + 1

    score_grid = np.full((grid_h, grid_w), np.nan, dtype=np.float32)
    score_grid[grid_rows, grid_cols] = det_scores

    # Apply score threshold
    if score_threshold > 0:
        score_grid[score_grid < score_threshold] = np.nan

    # Gaussian smoothing with normalized convolution.
    # Spreads scores into nearby empty cells to produce a continuous heatmap
    # instead of a dotted grid. Cells far from any patch stay transparent.
    if sigma is not None and sigma > 0 and gaussian_filter is not None:
        valid_mask = (~np.isnan(score_grid)).astype(np.float32)
        scores_filled = np.where(valid_mask, score_grid, 0.0)
        smoothed_scores = gaussian_filter(scores_filled, sigma=sigma)
        smoothed_mask = gaussian_filter(valid_mask, sigma=sigma)
        # Show smoothed values wherever the smoothed mask has enough support,
        # i.e. within ~2*sigma cells of any real patch.
        coverage = smoothed_mask > 0.01
        smoothed_mask = np.maximum(smoothed_mask, 1e-8)
        score_grid = np.where(coverage, smoothed_scores / smoothed_mask, np.nan)

    # Get slide thumbnail via OpenSlide
    slide = openslide.OpenSlide(svs_path)
    slide_w, slide_h = slide.dimensions
    thumb = slide.get_thumbnail((thumbnail_max_dim, thumbnail_max_dim))
    thumb_w, thumb_h = thumb.size
    slide.close()

    # Compute where the score grid sits on the thumbnail
    scale_x = thumb_w / slide_w
    scale_y = thumb_h / slide_h
    grid_origin_x = col_offset * patch_size * scale_x
    grid_origin_y = row_offset * patch_size * scale_y
    grid_extent_w = grid_w * patch_size * scale_x
    grid_extent_h = grid_h * patch_size * scale_y

    # Map scores to RGBA using colormap
    colormap = cm.get_cmap(cmap)
    nan_mask = np.isnan(score_grid)
    scores_safe = np.where(nan_mask, 0, score_grid)
    rgba = colormap(scores_safe)  # (H, W, 4) float in [0, 1]
    rgba[nan_mask, 3] = 0.0  # transparent where no data
    rgba[~nan_mask, 3] = alpha

    # Resize heatmap to match its footprint on the thumbnail
    heatmap_img = Image.fromarray((rgba * 255).astype(np.uint8), mode="RGBA")
    heatmap_resized = heatmap_img.resize(
        (int(round(grid_extent_w)), int(round(grid_extent_h))),
        Image.BILINEAR,
    )

    # Composite onto thumbnail
    thumb_rgba = thumb.convert("RGBA")
    overlay = Image.new("RGBA", thumb_rgba.size, (0, 0, 0, 0))
    paste_x = int(round(grid_origin_x))
    paste_y = int(round(grid_origin_y))
    overlay.paste(heatmap_resized, (paste_x, paste_y))
    composite = Image.alpha_composite(thumb_rgba, overlay)

    # Add colorbar
    composite = _add_colorbar(composite, cmap, vmin=0.0, vmax=1.0)

    # Add title
    if title:
        composite = _add_title(composite, title)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    composite.save(output_path, "PNG")
    return output_path


def _add_colorbar(
    img: Image.Image, cmap: str, vmin: float = 0.0, vmax: float = 1.0,
) -> Image.Image:
    """Render a colorbar and paste it onto the right edge of the image."""
    fig, ax = plt.subplots(figsize=(0.6, 3), dpi=100)
    norm = matplotlib.colors.Normalize(vmin=vmin, vmax=vmax)
    cb = matplotlib.colorbar.ColorbarBase(
        ax, cmap=cm.get_cmap(cmap), norm=norm, orientation="vertical",
    )
    cb.set_label("Detection Score", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.subplots_adjust(left=0.05, right=0.55, top=0.95, bottom=0.05)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    cbar_img = Image.open(buf).convert("RGBA")

    # Scale colorbar height to 40% of image height
    target_h = int(img.height * 0.4)
    ratio = target_h / cbar_img.height
    cbar_resized = cbar_img.resize(
        (int(cbar_img.width * ratio), target_h), Image.LANCZOS,
    )

    # Paste on right side with margin
    result = img.copy()
    margin = 10
    paste_x = result.width - cbar_resized.width - margin
    paste_y = result.height - cbar_resized.height - margin
    result.paste(cbar_resized, (paste_x, paste_y), cbar_resized)
    return result


def _add_title(img: Image.Image, title: str) -> Image.Image:
    """Add title text to the top of the image using matplotlib."""
    fig, ax = plt.subplots(figsize=(6, 0.4), dpi=100)
    ax.text(0.5, 0.5, title, ha="center", va="center", fontsize=10, fontweight="bold")
    ax.axis("off")
    fig.tight_layout(pad=0)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    title_img = Image.open(buf).convert("RGBA")

    # Scale to image width
    ratio = img.width / title_img.width
    title_resized = title_img.resize(
        (img.width, int(title_img.height * ratio)), Image.LANCZOS,
    )

    result = img.copy()
    result.paste(title_resized, (0, 5), title_resized)
    return result


def generate_fold_heatmaps(
    patch_scores_dir: str,
    wsi_dir: str,
    output_dir: str,
    wsi_extension: str = ".svs",
    **kwargs,
) -> list[str]:
    """Generate heatmaps for all .npz files in a fold's patch_scores/ directory.

    Returns:
        List of generated PNG paths.
    """
    npz_files = sorted(Path(patch_scores_dir).glob("*.npz"))
    if not npz_files:
        print(f"  No .npz files found in {patch_scores_dir}")
        return []

    os.makedirs(output_dir, exist_ok=True)
    generated = []

    for i, npz_path in enumerate(npz_files):
        slide_id = npz_path.stem
        wsi_path = os.path.join(wsi_dir, f"{slide_id}{wsi_extension}")
        if not os.path.exists(wsi_path):
            print(f"  [{i+1}/{len(npz_files)}] SKIP {slide_id} (no {wsi_extension})")
            continue

        out_path = os.path.join(output_dir, f"{slide_id}.png")
        if os.path.exists(out_path):
            generated.append(out_path)
            continue

        generate_slide_heatmap(
            str(npz_path), wsi_path, out_path,
            title=slide_id, **kwargs,
        )
        generated.append(out_path)
        print(f"  [{i+1}/{len(npz_files)}] {slide_id}")

    print(f"  Generated {len(generated)}/{len(npz_files)} heatmaps -> {output_dir}")
    return generated


def generate_experiment_heatmaps(
    results_dir: str,
    wsi_dir: str,
    output_base_dir: str | None = None,
    folds: list[int] | None = None,
    **kwargs,
) -> list[str]:
    """Generate heatmaps for all folds in a SMMILe experiment run.

    Args:
        results_dir: e.g., {smmile_dir}/results/{task}/{encoder}/{run_name}/
        wsi_dir: Directory containing .svs files.
        output_base_dir: If None, saves to {fold_dir}/heatmaps/.
        folds: Specific folds to process. None = all found.

    Returns:
        List of all generated PNG paths.
    """
    all_generated = []

    fold_dirs = sorted(Path(results_dir).glob("fold_*"))
    for fold_dir in fold_dirs:
        fold_num = int(fold_dir.name.split("_")[1])
        if folds is not None and fold_num not in folds:
            continue

        ps_dir = fold_dir / "patch_scores"
        if not ps_dir.exists():
            print(f"Fold {fold_num}: no patch_scores/ directory, skipping")
            continue

        if output_base_dir:
            out_dir = os.path.join(output_base_dir, fold_dir.name, "heatmaps")
        else:
            out_dir = str(fold_dir / "heatmaps")

        print(f"Fold {fold_num}: generating heatmaps...")
        generated = generate_fold_heatmaps(str(ps_dir), wsi_dir, out_dir, **kwargs)
        all_generated.extend(generated)

    return all_generated
