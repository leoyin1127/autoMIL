"""Tests for autobench.data module."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

openslide = pytest.importorskip("openslide")
from openslide import OpenSlideError

from autobench.data import generate_wsi_list_csv, load_all_slides, validate_slides
from _helpers import make_test_ds

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ROWS = [
    {"new_name": "slide_001.svs", "status": "mapped_unique_case_id", "primary_hospital": "UHN"},
    {"new_name": "slide_002.svs", "status": "mapped_unique_case_id", "primary_hospital": "UHN"},
    {"new_name": "slide_003.svs", "status": "mapped_unique_case_id", "primary_hospital": "Kingston"},
    {"new_name": "slide_004.svs", "status": "unreferenced", "primary_hospital": "UHN"},
    {"new_name": "slide_005.svs", "status": "mapped_multiple_case_ids", "primary_hospital": "UHN"},
    {"new_name": "slide_006.svs", "status": "mapped_unique_case_id", "primary_hospital": "uhn"},  # lowercase
    {"new_name": "slide_007.svs", "status": "mapped_unique_case_id", "primary_hospital": "Stanford"},
]


@pytest.fixture
def ds():
    return make_test_ds()


@pytest.fixture
def sample_csv(tmp_path):
    csv_path = tmp_path / "mapping.csv"
    pd.DataFrame(SAMPLE_ROWS).to_csv(csv_path, index=False)
    return str(csv_path)


# ---------------------------------------------------------------------------
# load_all_slides
# ---------------------------------------------------------------------------

class TestLoadAllSlides:
    def test_returns_dataframe(self, sample_csv, ds):
        result = load_all_slides(sample_csv, ds)
        assert isinstance(result, pd.DataFrame)

    def test_filters_by_status(self, sample_csv, ds):
        result = load_all_slides(sample_csv, ds)
        # Should match all rows with mapped_unique_case_id (rows 0,1,2,5,6)
        assert len(result) == 5

    def test_only_mapped_unique_status(self, sample_csv, ds):
        result = load_all_slides(sample_csv, ds)
        assert (result["status"] == "mapped_unique_case_id").all()

    def test_excludes_wrong_status(self, sample_csv, ds):
        result = load_all_slides(sample_csv, ds)
        names = result["new_name"].tolist()
        assert "slide_004.svs" not in names  # unreferenced
        assert "slide_005.svs" not in names  # mapped_multiple

    def test_includes_all_hospitals(self, sample_csv, ds):
        result = load_all_slides(sample_csv, ds)
        names = result["new_name"].tolist()
        assert "slide_003.svs" in names  # Kingston
        assert "slide_007.svs" in names  # Stanford

    def test_reset_index(self, sample_csv, ds):
        result = load_all_slides(sample_csv, ds)
        assert list(result.index) == list(range(len(result)))

    def test_no_status_filter_when_null(self, sample_csv):
        ds_no_status = make_test_ds(status_column=None, status_value=None)
        result = load_all_slides(sample_csv, ds_no_status)
        assert len(result) == 7  # all rows returned


# ---------------------------------------------------------------------------
# generate_wsi_list_csv
# ---------------------------------------------------------------------------

class TestGenerateWsiListCsv:
    def test_creates_csv_file(self, tmp_path, ds):
        df = pd.DataFrame({"new_name": ["slide_001.svs", "slide_002.svs"]})
        output = str(tmp_path / "output" / "wsi_list.csv")
        result = generate_wsi_list_csv(df, output, ds)
        assert os.path.isfile(result)

    def test_returns_output_path(self, tmp_path, ds):
        df = pd.DataFrame({"new_name": ["slide_001.svs"]})
        output = str(tmp_path / "wsi_list.csv")
        result = generate_wsi_list_csv(df, output, ds)
        assert result == output

    def test_csv_has_wsi_column(self, tmp_path, ds):
        df = pd.DataFrame({"new_name": ["slide_001.svs", "slide_002.svs"]})
        output = str(tmp_path / "wsi_list.csv")
        generate_wsi_list_csv(df, output, ds)
        written = pd.read_csv(output)
        assert "wsi" in written.columns

    def test_csv_contains_correct_filenames(self, tmp_path, ds):
        names = ["slide_001.svs", "slide_002.svs", "slide_003.svs"]
        df = pd.DataFrame({"new_name": names})
        output = str(tmp_path / "wsi_list.csv")
        generate_wsi_list_csv(df, output, ds)
        written = pd.read_csv(output)
        assert written["wsi"].tolist() == names

    def test_csv_row_count(self, tmp_path, ds):
        df = pd.DataFrame({"new_name": [f"slide_{i:03d}.svs" for i in range(10)]})
        output = str(tmp_path / "wsi_list.csv")
        generate_wsi_list_csv(df, output, ds)
        written = pd.read_csv(output)
        assert len(written) == 10

    def test_creates_parent_directories(self, tmp_path, ds):
        df = pd.DataFrame({"new_name": ["slide_001.svs"]})
        output = str(tmp_path / "a" / "b" / "c" / "wsi_list.csv")
        generate_wsi_list_csv(df, output, ds)
        assert os.path.isfile(output)

    def test_no_index_column(self, tmp_path, ds):
        df = pd.DataFrame({"new_name": ["slide_001.svs"]})
        output = str(tmp_path / "wsi_list.csv")
        generate_wsi_list_csv(df, output, ds)
        written = pd.read_csv(output)
        assert list(written.columns) == ["wsi"]


# ---------------------------------------------------------------------------
# validate_slides
# ---------------------------------------------------------------------------

class TestValidateSlides:
    """Tests for validate_slides().

    The function opens each slide twice per level: once to get level_count,
    then once per level to read a region.  Mocks must account for multiple
    OpenSlide() calls per slide.

    Note: openslide is now lazy-imported inside validate_slides, so the mock
    path is ``autobench.data.OpenSlide``.
    """

    def _make_df(self, names):
        return pd.DataFrame({"new_name": names, "status": "mapped_unique_case_id"})

    def _make_good_slide(self, num_levels=4):
        """Return a MagicMock that behaves like a healthy OpenSlide handle."""
        slide = MagicMock()
        slide.level_count = num_levels
        slide.level_dimensions = [(1000, 1000)] * num_levels
        return slide

    @patch("openslide.OpenSlide")
    def test_valid_slides_kept(self, mock_cls, tmp_path, ds):
        mock_cls.return_value = self._make_good_slide()

        df = self._make_df(["a.svs", "b.svs"])
        valid_df, failed = validate_slides(df, str(tmp_path), ds)

        assert len(valid_df) == 2
        assert failed == []

    @patch("openslide.OpenSlide")
    def test_corrupted_slide_excluded(self, mock_cls, tmp_path, ds):
        mock_cls.side_effect = OpenSlideError("corrupt JPEG data")

        df = self._make_df(["bad.svs"])
        valid_df, failed = validate_slides(df, str(tmp_path), ds)

        assert len(valid_df) == 0
        assert failed == ["bad.svs"]

    @patch("openslide.OpenSlide")
    def test_missing_file_excluded(self, mock_cls, tmp_path, ds):
        mock_cls.side_effect = FileNotFoundError("No such file")

        df = self._make_df(["missing.svs"])
        valid_df, failed = validate_slides(df, str(tmp_path), ds)

        assert len(valid_df) == 0
        assert failed == ["missing.svs"]

    @patch("openslide.OpenSlide")
    def test_mix_of_valid_and_invalid(self, mock_cls, tmp_path, ds):
        good_slide = self._make_good_slide()

        def side_effect(path):
            if "bad" in path:
                raise OpenSlideError("corrupt")
            return good_slide

        mock_cls.side_effect = side_effect

        df = self._make_df(["good1.svs", "bad.svs", "good2.svs"])
        valid_df, failed = validate_slides(df, str(tmp_path), ds)

        assert valid_df["new_name"].tolist() == ["good1.svs", "good2.svs"]
        assert failed == ["bad.svs"]

    @patch("openslide.OpenSlide")
    def test_original_df_not_mutated(self, mock_cls, tmp_path, ds):
        mock_cls.side_effect = OpenSlideError("corrupt")

        df = self._make_df(["bad.svs", "also_bad.svs"])
        original_len = len(df)
        validate_slides(df, str(tmp_path), ds)

        assert len(df) == original_len

    @patch("openslide.OpenSlide")
    def test_skipped_slides_file_written(self, mock_cls, tmp_path, ds):
        wsi_dir = tmp_path / "wsi"
        wsi_dir.mkdir()
        mock_cls.side_effect = OpenSlideError("corrupt")

        df = self._make_df(["bad1.svs", "bad2.svs"])
        validate_slides(df, str(wsi_dir), ds)

        skipped_path = tmp_path / "skipped_slides.txt"
        assert skipped_path.exists()
        content = skipped_path.read_text()
        assert "bad1.svs" in content
        assert "bad2.svs" in content

    @patch("openslide.OpenSlide")
    def test_no_skipped_file_when_all_valid(self, mock_cls, tmp_path, ds):
        wsi_dir = tmp_path / "wsi"
        wsi_dir.mkdir()
        mock_cls.return_value = self._make_good_slide()

        df = self._make_df(["good.svs"])
        validate_slides(df, str(wsi_dir), ds)

        skipped_path = tmp_path / "skipped_slides.txt"
        assert not skipped_path.exists()

    @patch("openslide.OpenSlide")
    def test_read_region_failure_caught(self, mock_cls, tmp_path, ds):
        mock_slide = self._make_good_slide()
        mock_slide.read_region.side_effect = OpenSlideError("bad tile")
        mock_cls.return_value = mock_slide

        df = self._make_df(["tile_error.svs"])
        valid_df, failed = validate_slides(df, str(tmp_path), ds)

        assert len(valid_df) == 0
        assert failed == ["tile_error.svs"]

    @patch("openslide.OpenSlide")
    def test_level1_corruption_caught(self, mock_cls, tmp_path, ds):
        """Corruption at level 1 only (level 0 is fine) -- the real-world failure mode."""
        call_count = [0]

        def side_effect(path):
            call_count[0] += 1
            # First call: get level_count (returns healthy handle)
            if call_count[0] == 1:
                s = MagicMock()
                s.level_count = 4
                return s
            # Second call: level 0 read (OK)
            if call_count[0] == 2:
                s = MagicMock()
                s.level_dimensions = [(1000, 1000)] * 4
                return s
            # Third call: level 1 read (corrupt)
            if call_count[0] == 3:
                s = MagicMock()
                s.level_dimensions = [(1000, 1000)] * 4
                s.read_region.side_effect = OpenSlideError(
                    "Not a JPEG file: starts with 0xff 0x10"
                )
                return s
            return MagicMock()

        mock_cls.side_effect = side_effect

        df = self._make_df(["level1_bad.svs"])
        valid_df, failed = validate_slides(df, str(tmp_path), ds)

        assert len(valid_df) == 0
        assert failed == ["level1_bad.svs"]
