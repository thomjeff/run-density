"""Tests for config package segment recipes (#769)."""

import pytest

from app.core.config_package.segment_recipes import (
    order_grid_from_recipes,
    recipes_from_order_grid,
)


def test_recipes_from_order_grid():
    chunks = [{"id": "01"}, {"id": "02"}, {"id": "05"}]
    grid = {
        "full": {"01": 1, "02": 2, "05": None},
        "half": {"01": 1, "05": 2, "02": None},
        "10k": {"01": 1, "02": 2},
    }
    recipes = recipes_from_order_grid(chunks, grid)
    assert recipes["full"] == ["01", "02"]
    assert recipes["half"] == ["01", "05"]
    assert recipes["10k"] == ["01", "02"]


def test_order_grid_roundtrip():
    chunks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    recipes = {"full": ["a", "c"], "half": ["b"], "10k": ["a", "b", "c"]}
    grid = order_grid_from_recipes(chunks, recipes)
    assert grid["full"]["a"] == 1
    assert grid["full"]["c"] == 2
    assert grid["full"]["b"] is None
    assert grid["half"]["b"] == 1
    back = recipes_from_order_grid(chunks, grid)
    assert back == recipes
