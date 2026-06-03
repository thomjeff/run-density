"""Tests for config package segment recipes (#769)."""

import pytest

from app.core.config_package.segment_recipes import (
    _leg_id_from_filename,
    order_grid_from_recipes,
    recipes_from_order_grid,
    sync_manifest_legs_from_gpx,
)


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
