"""Tests for dynamic event discovery helpers (#701)."""

import pandas as pd
import pytest

from app.core.event_discovery import (
    active_events,
    build_segment_event_payload,
    display_events_from_flags,
    length_km_from_event_fields,
    pick_gpx_event,
)
from app.core.gpx.processor import generate_segment_coordinates
from app.core.gpx.processor import GPXCourse, GPXPoint


def test_active_events_subset_and_elite_open():
    row = {
        "elite": "y",
        "open": "Y",
        "full": "n",
        "half": "",
        "10k": "n",
    }
    assert active_events(row, ["elite", "open", "full"]) == ["elite", "open"]
    assert display_events_from_flags(row) == ["Elite", "Open"]


def test_build_segment_event_payload_includes_spans():
    row = pd.Series(
        {
            "elite": "y",
            "open": "n",
            "elite_from_km": 0.0,
            "elite_to_km": 1.2,
            "open_from_km": 0.0,
            "open_to_km": 0.0,
        }
    )
    payload = build_segment_event_payload(row, ["elite", "open"])
    assert payload["elite"] == "y"
    assert payload["elite_from_km"] == 0.0
    assert payload["elite_to_km"] == 1.2
    assert payload["open"] == "n"


def test_pick_gpx_event_prefers_priority_among_available():
    segment = {"elite": "n", "open": "y", "10k": "y", "half": "n", "full": "n"}
    assert pick_gpx_event(segment, ["10k", "open", "full"]) == "open"
    assert pick_gpx_event(segment, ["10k"]) == "10k"
    assert pick_gpx_event(segment, ["full"]) is None


def test_length_km_from_event_fields():
    dims = {"elite_length": 0, "open_from_km": 1.0, "open_to_km": 2.5, "open": "y"}
    assert length_km_from_event_fields(dims, ["elite", "open"]) == pytest.approx(1.5)


def test_generate_segment_coordinates_elite_only_subset():
    """Elite+open analysis subset: segment flagged elite must resolve without full/half/10k."""
    points = [
        GPXPoint(lat=45.96, lon=-66.64, distance_km=0.0),
        GPXPoint(lat=45.961, lon=-66.639, distance_km=0.15),
        GPXPoint(lat=45.962, lon=-66.638, distance_km=0.30),
    ]
    course = GPXCourse(name="elite", points=points, total_distance_km=0.3)
    courses = {"elite": course}
    to_km = min(0.25, course.cum_km[-1] if course.cum_km else 0.25)
    segments = [
        {
            "seg_id": "S1",
            "segment_label": "Start",
            "elite": "y",
            "elite_from_km": 0.0,
            "elite_to_km": to_km,
            "full": "n",
            "half": "n",
            "10k": "n",
            "direction": "uni",
            "width_m": 3.0,
        }
    ]
    out = generate_segment_coordinates(courses, segments)
    assert len(out) == 1
    assert out[0]["seg_id"] == "S1"
    assert len(out[0]["line_coords"]) >= 2
