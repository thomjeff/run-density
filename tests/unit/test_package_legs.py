"""Tests for config package leg authoring (#769)."""

import pytest

from app.core.config_package.legs import (
    allocate_next_leg_id,
    leg_row_from_entry,
    _normalize_locations,
)


def test_allocate_next_leg_id():
    chunks = [{"id": "01"}, {"id": "02"}, {"id": "15"}]
    assert allocate_next_leg_id(chunks) == "16"
    assert allocate_next_leg_id([]) == "01"


def test_normalize_locations():
    locs = _normalize_locations([
        {"loc_label": "Water", "loc_type": "water", "lat": 45.96, "lon": -66.64, "placement": "start"},
        {"label": "bad", "lat": "x"},
    ])
    assert len(locs) == 1
    assert locs[0]["loc_type"] == "water"


def test_leg_row_from_entry_defaults():
    row = leg_row_from_entry(
        {"id": "01", "seg_label": "Start to Friel", "start_label": "", "end_label": ""},
        {"length_km": 2.7, "coordinates": [[-66.6, 45.9], [-66.5, 45.95]]},
    )
    assert row["id"] == "01"
    assert "Start" in row["start_label"]
    assert "Friel" in row["end_label"] or row["leg_label"]
