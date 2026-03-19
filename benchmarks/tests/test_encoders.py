"""Tests for autobench.encoders.h0_mini module."""

from unittest.mock import MagicMock, patch

import pytest

torch = pytest.importorskip("torch")
trident = pytest.importorskip("trident")

from autobench.encoders.h0_mini import H0MiniInferenceEncoder
from trident.patch_encoder_models.load import BasePatchEncoder


class TestH0MiniClass:
    def test_inherits_base_patch_encoder(self):
        assert issubclass(H0MiniInferenceEncoder, BasePatchEncoder)

    def test_is_torch_module(self):
        assert issubclass(H0MiniInferenceEncoder, torch.nn.Module)


class TestH0MiniBuild:
    """Test _build() in isolation by mocking timm and weight loading."""

    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value=None)
    @patch("autobench.encoders.h0_mini.BasePatchEncoder.ensure_has_internet")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    def test_build_sets_enc_name(
        self, mock_create_transform, mock_resolve, mock_create_model, mock_internet, mock_weights
    ):
        mock_model = MagicMock()
        mock_model.pretrained_cfg = {}
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        mock_create_transform.return_value = MagicMock()

        encoder = H0MiniInferenceEncoder()
        assert encoder.enc_name == "h0_mini"

    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value=None)
    @patch("autobench.encoders.h0_mini.BasePatchEncoder.ensure_has_internet")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    def test_build_returns_float16_precision(
        self, mock_create_transform, mock_resolve, mock_create_model, mock_internet, mock_weights
    ):
        mock_model = MagicMock()
        mock_model.pretrained_cfg = {}
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        mock_create_transform.return_value = MagicMock()

        encoder = H0MiniInferenceEncoder()
        assert encoder.precision == torch.float16

    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value=None)
    @patch("autobench.encoders.h0_mini.BasePatchEncoder.ensure_has_internet")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    def test_build_creates_hf_hub_model(
        self, mock_create_transform, mock_resolve, mock_create_model, mock_internet, mock_weights
    ):
        mock_model = MagicMock()
        mock_model.pretrained_cfg = {}
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        mock_create_transform.return_value = MagicMock()

        H0MiniInferenceEncoder()
        mock_create_model.assert_called_once_with(
            "hf-hub:bioptimus/H0-mini",
            pretrained=True,
            mlp_layer=pytest.importorskip("timm").layers.SwiGLUPacked,
            act_layer=torch.nn.SiLU,
            num_classes=0,
            global_pool="token",
        )

    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value=None)
    @patch("autobench.encoders.h0_mini.BasePatchEncoder.ensure_has_internet")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    def test_build_sets_eval_transforms(
        self, mock_create_transform, mock_resolve, mock_create_model, mock_internet, mock_weights
    ):
        mock_model = MagicMock()
        mock_model.pretrained_cfg = {}
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        sentinel_transform = MagicMock()
        mock_create_transform.return_value = sentinel_transform

        encoder = H0MiniInferenceEncoder()
        assert encoder.eval_transforms is sentinel_transform

    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value=None)
    @patch("autobench.encoders.h0_mini.BasePatchEncoder.ensure_has_internet")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    def test_build_resolves_data_config_from_pretrained_cfg(
        self, mock_create_transform, mock_resolve, mock_create_model, mock_internet, mock_weights
    ):
        mock_model = MagicMock()
        sentinel_cfg = {"mean": (0.5, 0.5, 0.5), "std": (0.5, 0.5, 0.5)}
        mock_model.pretrained_cfg = sentinel_cfg
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        mock_create_transform.return_value = MagicMock()

        H0MiniInferenceEncoder()
        mock_resolve.assert_called_once_with(sentinel_cfg)

    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value="/fake/weights.pt")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    @patch("torch.load")
    def test_build_local_weights_path(
        self, mock_torch_load, mock_create_transform, mock_resolve, mock_create_model, mock_weights
    ):
        mock_model = MagicMock()
        mock_model.pretrained_cfg = {}
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        mock_create_transform.return_value = MagicMock()
        mock_torch_load.return_value = {}

        encoder = H0MiniInferenceEncoder()
        # Should use local model name, not hf-hub
        mock_create_model.assert_called_once_with(
            "vit_base_patch14_dinov2",
            pretrained=False,
            mlp_layer=pytest.importorskip("timm").layers.SwiGLUPacked,
            act_layer=torch.nn.SiLU,
            num_classes=0,
            global_pool="token",
        )
        mock_torch_load.assert_called_once_with("/fake/weights.pt", map_location="cpu")


class TestH0MiniForward:
    @patch("autobench.encoders.h0_mini.BasePatchEncoder._get_weights_path", return_value=None)
    @patch("autobench.encoders.h0_mini.BasePatchEncoder.ensure_has_internet")
    @patch("timm.create_model")
    @patch("timm.data.resolve_data_config")
    @patch("timm.data.transforms_factory.create_transform")
    def test_forward_delegates_to_model(
        self, mock_create_transform, mock_resolve, mock_create_model, mock_internet, mock_weights
    ):
        mock_model = MagicMock()
        mock_model.pretrained_cfg = {}
        expected_output = torch.randn(2, 768)
        mock_model.return_value = expected_output
        mock_create_model.return_value = mock_model
        mock_resolve.return_value = {"input_size": (3, 224, 224)}
        mock_create_transform.return_value = MagicMock()

        encoder = H0MiniInferenceEncoder()
        dummy_input = torch.randn(2, 3, 224, 224)
        result = encoder(dummy_input)

        # BasePatchEncoder.forward calls self.model(x)
        mock_model.assert_called_with(dummy_input)
        assert torch.equal(result, expected_output)
