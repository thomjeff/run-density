"""Tests for config package segment recipes (#769 / #780)."""

import pytest

from app.core.config_package.segment_recipes import (
    _leg_id_from_filename,
    order_grid_from_recipes,
    recipes_from_order_grid,
    sync_manifest_legs_from_gpx,
)
from app.core.course.segment_library import manifest_legs

_GPX_MIN = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""


def test_recipes_from_order_grid():
    legs = [{"id": "01"}, {"id": "02"}, {"id": "05"}]
    grid = {
        "full": {"01": 1, "02": 2, "05": None},
        "half": {"01": 1, "05": 2, "02": None},
        "10k": {"01": 1, "02": 2},
    }
    recipes = recipes_from_order_grid(legs, grid, ["full", "half", "10k"])
    assert recipes["full"] == ["01", "02"]
    assert recipes["half"] == ["01", "05"]
    assert recipes["10k"] == ["01", "02"]


def test_leg_id_from_filename():
    assert _leg_id_from_filename("01_start_friel.gpx") == "01"
    assert _leg_id_from_filename("00_full.gpx") == ""


def test_sync_manifest_legs_distinct_ids_for_shared_prefix(tmp_path):
    """Regression: 03_A.gpx and 03_B.gpx must not both become leg id 03 (#780)."""
    lib = tmp_path
    (lib / "03_blake_out.gpx").write_text(_GPX_MIN, encoding="utf-8")
    (lib / "03_blake_back.gpx").write_text(_GPX_MIN, encoding="utf-8")
    manifest = sync_manifest_legs_from_gpx(lib)
    ids = [str(leg["id"]) for leg in manifest_legs(manifest)]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_sync_manifest_legs_preserves_id_by_filename(tmp_path):
    lib = tmp_path
    (lib / "16_return.gpx").write_text(_GPX_MIN, encoding="utf-8")
    import yaml

    manifest = {
        "legs": [
            {
                "id": "16",
                "file": "16_return.gpx",
                "seg_label": "Return",
            }
        ],
        "recipes": {},
    }
    (lib / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    out = sync_manifest_legs_from_gpx(lib, manifest)
    legs = manifest_legs(out)
    assert len(legs) == 1
    assert legs[0]["id"] == "16"
    assert legs[0]["file"] == "16_return.gpx"


def test_order_grid_roundtrip():
    legs = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    recipes = {"full": ["a", "c"], "half": ["b"], "10k": ["a", "b", "c"]}
    events = ["full", "half", "10k"]
    grid = order_grid_from_recipes(legs, recipes, events)
    assert grid["full"]["a"] == 1
    assert grid["full"]["c"] == 2
    assert grid["full"]["b"] is None
    assert grid["half"]["b"] == 1
    back = recipes_from_order_grid(legs, grid, events)
    assert back == recipes
