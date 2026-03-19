"""Tests for scripts/run_feature_extraction.py."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

torch = pytest.importorskip("torch")

# We need to import the functions from the script.
# Add scripts/ to path so we can import run_feature_extraction as a module.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import run_feature_extraction

from _helpers import make_test_ds


class TestParseArgs:
    def test_defaults(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian"])
        args = run_feature_extraction.parse_args()
        assert args.gpu == 0
        assert args.all_gpus is False
        assert args.models is None
        assert args.batch_size is None  # now defaults to None (from dataset config)
        assert args.skip_seg is False
        assert args.dataset == "ovarian"

    def test_gpu_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian", "--gpu", "2"])
        args = run_feature_extraction.parse_args()
        assert args.gpu == 2

    def test_models_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian", "--models", "hibou_l", "uni_v2"])
        args = run_feature_extraction.parse_args()
        assert args.models == ["hibou_l", "uni_v2"]

    def test_batch_size_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian", "--batch_size", "128"])
        args = run_feature_extraction.parse_args()
        assert args.batch_size == 128

    def test_skip_seg_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian", "--skip_seg"])
        args = run_feature_extraction.parse_args()
        assert args.skip_seg is True

    def test_all_gpus_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian", "--all_gpus"])
        args = run_feature_extraction.parse_args()
        assert args.all_gpus is True

    def test_single_model(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--dataset", "ovarian", "--models", "virchow2"])
        args = run_feature_extraction.parse_args()
        assert args.models == ["virchow2"]

    def test_dataset_required(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog"])
        with pytest.raises(SystemExit):
            run_feature_extraction.parse_args()


class TestLoadEncoder:
    @patch("trident.patch_encoder_models.encoder_factory")
    def test_native_encoder_uses_factory(self, mock_factory):
        sentinel = MagicMock()
        mock_factory.return_value = sentinel
        result = run_feature_extraction.load_encoder("hibou_l")
        mock_factory.assert_called_once_with("hibou_l")
        assert result is sentinel

    @patch("autobench.encoders.h0_mini.H0MiniInferenceEncoder")
    def test_h0_mini_uses_custom_class(self, mock_cls):
        sentinel = MagicMock()
        mock_cls.return_value = sentinel
        result = run_feature_extraction.load_encoder("h0_mini")
        mock_cls.assert_called_once()
        assert result is sentinel

    @patch("trident.patch_encoder_models.encoder_factory")
    def test_each_native_encoder_key(self, mock_factory):
        """Verify all native encoder keys go through encoder_factory."""
        native_keys = ["hibou_l", "conch_v15", "virchow2", "midnight12k", "uni_v2", "hoptimus1"]
        for key in native_keys:
            mock_factory.reset_mock()
            run_feature_extraction.load_encoder(key)
            mock_factory.assert_called_once_with(key)


class TestMainModelFiltering:
    """Test the model selection logic using DatasetConfig."""

    def test_all_models_from_dataset_config(self):
        ds = make_test_ds()
        all_keys = list(ds.encoder_models.values())
        assert len(all_keys) == 7

    def test_valid_subset_filtering(self):
        ds = make_test_ds()
        all_keys = list(ds.encoder_models.values())
        requested = ["hibou_l", "uni_v2", "fake_model"]
        valid = [k for k in requested if k in all_keys]
        invalid = [k for k in requested if k not in all_keys]
        assert valid == ["hibou_l", "uni_v2"]
        assert invalid == ["fake_model"]

    def test_all_invalid_gives_empty(self):
        ds = make_test_ds()
        all_keys = list(ds.encoder_models.values())
        requested = ["fake1", "fake2"]
        valid = [k for k in requested if k in all_keys]
        assert valid == []


class TestSkipSegCoordsDir:
    """Test that --skip_seg constructs the expected coords_dir path."""

    def test_coords_dir_format(self):
        ds = make_test_ds()
        expected = os.path.join(ds.output_dir, f"{ds.magnification}x_{ds.patch_size}px_0px_overlap")
        assert expected.endswith("20x_256px_0px_overlap")
