"""Tests for OpenSlideWSI pickle support (__getstate__ / __setstate__)."""

import pickle
from unittest.mock import MagicMock, patch

import pytest

trident = pytest.importorskip("trident")

from trident.wsi_objects.OpenSlideWSI import OpenSlideWSI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wsi(**attrs):
    """Create an OpenSlideWSI without triggering __init__ / _lazy_initialize.

    Uses ``__new__`` to allocate the object, then sets ``__dict__`` directly
    so tests control exactly which attributes exist.
    """
    wsi = OpenSlideWSI.__new__(OpenSlideWSI)
    wsi.__dict__.update(attrs)
    return wsi


# ---------------------------------------------------------------------------
# __getstate__
# ---------------------------------------------------------------------------

class TestOpenSlideWSIGetState:
    def test_getstate_drops_img(self):
        wsi = _make_wsi(
            slide_path="/fake.svs",
            img=MagicMock(),
            name="test_slide",
        )
        state = wsi.__getstate__()
        assert "img" not in state

    def test_getstate_converts_properties_to_plain_dict(self):
        # Simulate openslide._PropertyMap: iterable over keys with
        # __getitem__ returning the corresponding value.
        backing = {"key_a": "val_a", "key_b": "val_b"}
        mock_props = MagicMock()
        mock_props.__iter__ = MagicMock(side_effect=lambda: iter(backing))
        mock_props.__getitem__ = MagicMock(side_effect=backing.__getitem__)
        mock_props.keys = MagicMock(return_value=backing.keys())

        wsi = _make_wsi(
            slide_path="/fake.svs",
            properties=mock_props,
        )
        state = wsi.__getstate__()

        assert isinstance(state["properties"], dict)
        assert state["properties"] == {"key_a": "val_a", "key_b": "val_b"}

    def test_getstate_preserves_metadata(self):
        wsi = _make_wsi(
            slide_path="/data/slides/sample.svs",
            name="sample",
            mpp=0.25,
            mag=40,
            width=100000,
            height=80000,
        )
        state = wsi.__getstate__()

        assert state["slide_path"] == "/data/slides/sample.svs"
        assert state["name"] == "sample"
        assert state["mpp"] == 0.25
        assert state["mag"] == 40
        assert state["width"] == 100000
        assert state["height"] == 80000

    def test_getstate_handles_none_properties(self):
        wsi = _make_wsi(
            slide_path="/fake.svs",
            properties=None,
        )
        state = wsi.__getstate__()

        assert "properties" in state
        assert state["properties"] is None

    def test_getstate_handles_missing_img(self):
        wsi = _make_wsi(slide_path="/fake.svs")
        # img is intentionally not set
        assert not hasattr(wsi, "img")

        state = wsi.__getstate__()
        assert "img" not in state

    def test_properties_decoupled_from_ctypes(self):
        backing = {"openslide.mpp-x": "0.25"}
        mock_props = MagicMock()
        mock_props.__iter__ = MagicMock(side_effect=lambda: iter(backing))
        mock_props.__getitem__ = MagicMock(side_effect=backing.__getitem__)
        mock_props.keys = MagicMock(return_value=backing.keys())

        wsi = _make_wsi(
            slide_path="/fake.svs",
            properties=mock_props,
        )
        state = wsi.__getstate__()

        # Mutate the backing data after snapshotting
        backing["openslide.mpp-x"] = "CHANGED"

        # The snapshotted dict must be independent of the mock
        assert state["properties"]["openslide.mpp-x"] == "0.25"


# ---------------------------------------------------------------------------
# __setstate__
# ---------------------------------------------------------------------------

class TestOpenSlideWSISetState:
    @patch("trident.wsi_objects.OpenSlideWSI.openslide.OpenSlide")
    def test_setstate_restores_attributes(self, mock_openslide_cls):
        mock_openslide_cls.return_value = MagicMock()

        state = {
            "slide_path": "/restored.svs",
            "name": "restored",
            "mpp": 0.5,
            "mag": 20,
            "width": 50000,
            "height": 40000,
            "properties": {"openslide.mpp-x": "0.5"},
        }

        wsi = OpenSlideWSI.__new__(OpenSlideWSI)
        wsi.__setstate__(state)

        assert wsi.slide_path == "/restored.svs"
        assert wsi.name == "restored"
        assert wsi.mpp == 0.5
        assert wsi.mag == 20
        assert wsi.width == 50000
        assert wsi.height == 40000
        assert wsi.properties == {"openslide.mpp-x": "0.5"}

    @patch("trident.wsi_objects.OpenSlideWSI.openslide.OpenSlide")
    def test_setstate_reopens_openslide_handle(self, mock_openslide_cls):
        fake_handle = MagicMock(name="reopened_handle")
        mock_openslide_cls.return_value = fake_handle

        state = {"slide_path": "/fake.svs"}

        wsi = OpenSlideWSI.__new__(OpenSlideWSI)
        wsi.__setstate__(state)

        mock_openslide_cls.assert_called_once_with("/fake.svs")
        assert wsi.img is fake_handle


# ---------------------------------------------------------------------------
# Pickle round-trip
# ---------------------------------------------------------------------------

class TestOpenSlideWSIPickleRoundTrip:
    @patch("trident.wsi_objects.OpenSlideWSI.openslide.OpenSlide")
    def test_pickle_roundtrip_preserves_metadata(self, mock_openslide_cls):
        mock_openslide_cls.return_value = MagicMock()

        original = _make_wsi(
            slide_path="/round/trip.svs",
            name="trip",
            mpp=0.25,
            mag=40,
            width=100000,
            height=80000,
            img=MagicMock(),
            properties={"openslide.mpp-x": "0.25"},
        )

        state = original.__getstate__()
        restored = OpenSlideWSI.__new__(OpenSlideWSI)
        restored.__setstate__(state)

        assert restored.slide_path == "/round/trip.svs"
        assert restored.name == "trip"
        assert restored.mpp == 0.25
        assert restored.mag == 40
        assert restored.width == 100000
        assert restored.height == 80000
        assert restored.properties == {"openslide.mpp-x": "0.25"}

    @patch("trident.wsi_objects.OpenSlideWSI.openslide.OpenSlide")
    def test_full_pickle_dumps_loads(self, mock_openslide_cls):
        mock_openslide_cls.return_value = MagicMock()

        original = _make_wsi(
            slide_path="/pickle/test.svs",
            name="pickle_test",
            mpp=0.5,
            mag=20,
            img=MagicMock(),
            properties={"aperio.MPP": "0.5"},
        )

        data = pickle.dumps(original)
        restored = pickle.loads(data)

        assert restored.slide_path == "/pickle/test.svs"
        assert restored.name == "pickle_test"
        assert restored.mpp == 0.5
        assert restored.mag == 20
        assert restored.properties == {"aperio.MPP": "0.5"}
        # img should have been re-opened by __setstate__
        mock_openslide_cls.assert_called_with("/pickle/test.svs")
        assert restored.img is mock_openslide_cls.return_value

    @patch("trident.wsi_objects.OpenSlideWSI.openslide.OpenSlide")
    def test_pickle_with_real_properties_dict(self, mock_openslide_cls):
        mock_openslide_cls.return_value = MagicMock()

        real_props = {
            "openslide.mpp-x": "0.2528",
            "openslide.mpp-y": "0.2528",
            "openslide.objective-power": "40",
            "openslide.vendor": "aperio",
            "aperio.AppMag": "40",
            "tiff.ImageDescription": "Aperio SVS",
        }

        original = _make_wsi(
            slide_path="/props/test.svs",
            name="props_test",
            img=MagicMock(),
            properties=real_props,
        )

        data = pickle.dumps(original)
        restored = pickle.loads(data)

        assert restored.properties == real_props
        assert restored.properties["openslide.mpp-x"] == "0.2528"
        assert restored.properties["openslide.vendor"] == "aperio"
