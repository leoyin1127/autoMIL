import torch
from trident.patch_encoder_models.load import BasePatchEncoder


class H0MiniInferenceEncoder(BasePatchEncoder):
    """Custom encoder for bioptimus/H0-mini (ViT-B/14, DINOv2 distilled from H-optimus-0)."""

    def __init__(self, **build_kwargs):
        super().__init__(**build_kwargs)

    def _build(self):
        import timm
        from timm.data import resolve_data_config
        from timm.data.transforms_factory import create_transform

        self.enc_name = "h0_mini"

        weights_path = self._get_weights_path()

        timm_kwargs = {
            "mlp_layer": timm.layers.SwiGLUPacked,
            "act_layer": torch.nn.SiLU,
            "num_classes": 0,
            "global_pool": "token",
        }

        if weights_path:
            model = timm.create_model(
                "vit_base_patch14_dinov2",
                pretrained=False,
                **timm_kwargs,
            )
            model.load_state_dict(torch.load(weights_path, map_location="cpu"), strict=True)
        else:
            self.ensure_has_internet(self.enc_name)
            model = timm.create_model(
                "hf-hub:bioptimus/H0-mini",
                pretrained=True,
                **timm_kwargs,
            )

        data_config = resolve_data_config(model.pretrained_cfg)
        eval_transform = create_transform(**data_config, is_training=False)
        precision = torch.float16

        return model, eval_transform, precision
