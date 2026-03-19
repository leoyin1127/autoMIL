"""Tests for SMMILe data preparation (H5 -> NIC .npy + superpixels)."""

import os

import h5py
import numpy as np
import pytest


@pytest.fixture
def tmp_dirs(tmp_path):
    """Create a minimal H5 feature file and return paths."""
    h5_dir = tmp_path / "features_test_enc"
    h5_dir.mkdir()
    npy_dir = tmp_path / "features_npy" / "test_enc"
    npy_dir.mkdir(parents=True)
    sp_dir = tmp_path / "superpixels" / "test_enc"
    sp_dir.mkdir(parents=True)

    # Create a fake H5 with 20 patches on a 5x4 grid, step=256
    n_patches = 20
    embed_dim = 768
    coords = np.array(
        [[r * 256, c * 256] for r in range(5) for c in range(4)],
        dtype=np.int64,
    )
    features = np.random.randn(n_patches, embed_dim).astype(np.float32)

    h5_path = h5_dir / "slide_test.h5"
    with h5py.File(h5_path, "w") as f:
        f.create_dataset("coords", data=coords)
        f.create_dataset("features", data=features)

    return {
        "h5_dir": str(h5_dir),
        "npy_dir": str(npy_dir),
        "sp_dir": str(sp_dir),
        "h5_path": str(h5_path),
        "n_patches": n_patches,
        "embed_dim": embed_dim,
    }


class TestH5ToNIC:
    def test_converts_single_slide(self, tmp_dirs):
        from autobench.pipeline.smmile.prepare import convert_h5_to_nic

        convert_h5_to_nic(
            h5_path=tmp_dirs["h5_path"],
            output_dir=tmp_dirs["npy_dir"],
            patch_size=256,
        )
        out_path = os.path.join(tmp_dirs["npy_dir"], "slide_test_0_256.npy")
        assert os.path.exists(out_path)

        record = np.load(out_path, allow_pickle=True)[()]
        assert "feature" in record
        assert "index" in record
        assert "inst_label" in record
        assert "mask" in record

        # feature should be (embed_dim, H, W)
        assert record["feature"].ndim == 3
        assert record["feature"].shape[0] == tmp_dirs["embed_dim"]

        # mask should be (H, W) with all 1s (full grid)
        assert record["mask"].shape == record["feature"].shape[1:]
        assert record["mask"].sum() == tmp_dirs["n_patches"]

    def test_nic_grid_shape_matches_coords(self, tmp_dirs):
        from autobench.pipeline.smmile.prepare import convert_h5_to_nic

        convert_h5_to_nic(
            h5_path=tmp_dirs["h5_path"],
            output_dir=tmp_dirs["npy_dir"],
            patch_size=256,
        )
        out_path = os.path.join(tmp_dirs["npy_dir"], "slide_test_0_256.npy")
        record = np.load(out_path, allow_pickle=True)[()]

        # 5 rows x 4 cols grid
        assert record["feature"].shape[1] == 5
        assert record["feature"].shape[2] == 4

    def test_batch_conversion(self, tmp_dirs):
        from autobench.pipeline.smmile.prepare import convert_all_h5_to_nic

        convert_all_h5_to_nic(
            h5_dir=tmp_dirs["h5_dir"],
            output_dir=tmp_dirs["npy_dir"],
            patch_size=256,
        )
        npy_files = [f for f in os.listdir(tmp_dirs["npy_dir"]) if f.endswith(".npy")]
        assert len(npy_files) == 1


class TestSuperpixelGeneration:
    def test_generates_superpixel_map(self, tmp_dirs):
        from autobench.pipeline.smmile.prepare import (
            convert_h5_to_nic,
            generate_superpixels,
        )

        convert_h5_to_nic(
            h5_path=tmp_dirs["h5_path"],
            output_dir=tmp_dirs["npy_dir"],
            patch_size=256,
        )
        npy_path = os.path.join(tmp_dirs["npy_dir"], "slide_test_0_256.npy")
        generate_superpixels(
            npy_path=npy_path,
            output_dir=tmp_dirs["sp_dir"],
            n_segments_per_sp=4,
            compactness=50,
        )
        sp_path = os.path.join(tmp_dirs["sp_dir"], "slide_test_0_256.npy")
        assert os.path.exists(sp_path)

        sp_record = np.load(sp_path, allow_pickle=True)[()]
        assert "m_slic" in sp_record
        assert "m_adj" in sp_record
        assert sp_record["m_slic"].ndim == 2
        assert sp_record["m_adj"].ndim == 2
        # adjacency matrix should be square
        assert sp_record["m_adj"].shape[0] == sp_record["m_adj"].shape[1]

    def test_superpixel_not_transposed(self, tmp_dirs):
        """m_slic should NOT be pre-transposed; dataset handles that."""
        from autobench.pipeline.smmile.prepare import (
            convert_h5_to_nic,
            generate_superpixels,
        )

        convert_h5_to_nic(
            h5_path=tmp_dirs["h5_path"],
            output_dir=tmp_dirs["npy_dir"],
            patch_size=256,
        )
        npy_path = os.path.join(tmp_dirs["npy_dir"], "slide_test_0_256.npy")
        record = np.load(npy_path, allow_pickle=True)[()]

        generate_superpixels(
            npy_path=npy_path,
            output_dir=tmp_dirs["sp_dir"],
            n_segments_per_sp=4,
            compactness=50,
        )
        sp_path = os.path.join(tmp_dirs["sp_dir"], "slide_test_0_256.npy")
        sp_record = np.load(sp_path, allow_pickle=True)[()]

        # SLIC output shape should match feature grid (H, W), not transposed
        assert sp_record["m_slic"].shape == record["feature"].shape[1:]
