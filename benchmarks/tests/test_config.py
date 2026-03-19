"""Tests for autobench.config module (DatasetConfig-based)."""

from _helpers import make_test_ds


class TestPaths:
    def test_data_root_is_absolute(self):
        ds = make_test_ds()
        assert ds.data_root.startswith("/")

    def test_wsi_dir_under_data_root(self):
        ds = make_test_ds()
        assert ds.wsi_dir.startswith(ds.data_root)

    def test_mapping_csv_under_data_root(self):
        ds = make_test_ds()
        assert ds.mapping_csv.startswith(ds.data_root)
        assert ds.mapping_csv.endswith(".csv")

    def test_output_dir_is_absolute(self):
        ds = make_test_ds()
        assert ds.output_dir.startswith("/")


class TestEncoderModels:
    def test_model_count(self):
        ds = make_test_ds()
        assert len(ds.encoder_models) == 7

    def test_all_expected_models_present(self):
        ds = make_test_ds()
        expected_keys = {
            "histai/hibou-L",
            "MahmoodLab/conchv1_5",
            "paige-ai/Virchow2",
            "kaiko-ai/midnight",
            "MahmoodLab/UNI2-h",
            "bioptimus/H-optimus-1",
            "bioptimus/H0-mini",
        }
        assert set(ds.encoder_models.keys()) == expected_keys

    def test_all_expected_encoder_keys_present(self):
        ds = make_test_ds()
        expected_values = {
            "hibou_l",
            "conch_v15",
            "virchow2",
            "midnight12k",
            "uni_v2",
            "hoptimus1",
            "h0_mini",
        }
        assert set(ds.encoder_models.values()) == expected_values

    def test_encoder_keys_are_unique(self):
        ds = make_test_ds()
        values = list(ds.encoder_models.values())
        assert len(values) == len(set(values))


class TestExtractionParams:
    def test_magnification(self):
        ds = make_test_ds()
        assert ds.magnification == 20

    def test_patch_size(self):
        ds = make_test_ds()
        assert ds.patch_size == 256

    def test_batch_size(self):
        ds = make_test_ds()
        assert ds.batch_size == 64

    def test_params_are_positive_ints(self):
        ds = make_test_ds()
        for val in (ds.magnification, ds.patch_size, ds.batch_size):
            assert isinstance(val, int)
            assert val > 0


class TestDatasetConfig:
    def test_slide_id_transform_strip_svs(self):
        ds = make_test_ds()
        assert ds.get_slide_id("slide_001.svs") == "slide_001"

    def test_slide_id_transform_none(self):
        ds = make_test_ds(slide_id_transform=None)
        assert ds.get_slide_id("slide_001.svs") == "slide_001.svs"

    def test_tasks_dict(self):
        ds = make_test_ds()
        assert "brca" in ds.tasks
        assert "hrd" in ds.tasks
        assert ds.tasks["brca"].label_col == "BRCA_predict_label"
        assert ds.tasks["brca"].n_classes == 2

    def test_split_strategies(self):
        ds = make_test_ds()
        assert "standard" in ds.split_strategies

    def test_encoder_dims(self):
        ds = make_test_ds()
        assert ds.encoder_dims["conch_v15"] == 768
        assert ds.encoder_dims["hibou_l"] == 1024
        assert ds.encoder_dims["virchow2"] == 2560
        assert ds.encoder_dims["h0_mini"] == 768
