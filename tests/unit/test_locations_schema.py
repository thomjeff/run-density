"""Unit tests for location schema and suggest-events (Issue #765)."""

import csv
import io

import pytest

from app.core.course.export import build_locations_csv
from app.core.locations.schema import (
    DEFAULT_PACKAGE_RESOURCES,
    locations_csv_columns,
    normalize_location_record,
    normalize_resource_registry,
)
from app.core.locations.suggest_events import suggest_location_events


def test_default_resource_registry():
    reg = normalize_resource_registry(None)
    codes = [r["code"] for r in reg]
    assert codes == ["fpf", "yssr", "awp", "vol"]


def test_locations_csv_columns_include_resource_counts():
    cols = locations_csv_columns(["fpf", "vol"])
    assert "fpf_count" in cols
    assert "vol_count" in cols
    assert "loc_direction" not in cols
    assert cols.index("notes") == len(cols) - 1


def test_normalize_location_migrates_description_and_resources():
    loc = {
        "id": 3,
        "loc_label": "Aid",
        "loc_type": "aid",
        "loc_description": "Old text",
        "fpf_count": 2,
        "resources": {"vol": 1},
    }
    out = normalize_location_record(loc, ["fpf", "vol"], index=2)
    assert out["notes"] == "Old text"
    assert "loc_description" not in out
    assert out["resources"]["fpf"] == 2
    assert out["resources"]["vol"] == 1


def test_build_locations_csv_full_schema():
    course = {
        "locations": [
            {
                "id": 1,
                "loc_label": "Post A",
                "loc_type": "course",
                "lat": 45.95,
                "lon": -66.64,
                "seg_id": "A1",
                "full": "y",
                "half": "y",
                "notes": "Watch crossing",
                "resources": {"yssr": 2, "fpf": 0},
            }
        ]
    }
    csv_content = build_locations_csv(course, resource_codes=["fpf", "yssr", "awp", "vol"])
    reader = csv.DictReader(io.StringIO(csv_content))
    row = next(reader)
    assert row["loc_id"] == "1"
    assert row["notes"] == "Watch crossing"
    assert row["yssr_count"] == "2"
    assert row["fpf_count"] == "0"
    assert row["full"] == "y"


def test_suggest_location_events_from_segments():
    location = {"seg_id": "A1"}
    segments = [
        {"seg_id": "A1", "seg_label": "Start leg", "events": ["full", "half", "10k"]},
        {"seg_id": "B1", "seg_label": "10k only", "events": ["10k"]},
    ]
    flags, rationale = suggest_location_events(location, segments)
    assert flags["full"] == "y"
    assert flags["half"] == "y"
    assert flags["10k"] == "y"
    assert flags["elite"] == "n"
    assert "Start leg" in rationale


def test_suggest_events_requires_seg_id():
    flags, rationale = suggest_location_events({}, [])
    assert all(v == "n" for v in flags.values())
    assert "seg_id" in rationale


def test_reject_invalid_resource_code():
    with pytest.raises(ValueError, match="Invalid resource"):
        normalize_resource_registry([{"code": "BAD CODE", "label": "X"}])
