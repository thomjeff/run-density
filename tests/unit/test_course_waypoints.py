"""Unit tests for waypoint segment resolver (Issue #767)."""

import pytest

from app.core.course.waypoints import (
    find_vertex_occurrence,
    migrate_breaks_to_waypoints,
    normalize_course_waypoints,
    resolve_segments_from_definitions,
)


def _line_course(coords):
    return {
        "geometry": {"type": "LineString", "coordinates": coords},
        "segment_breaks": [],
        "segment_break_labels": {},
        "segments": [],
    }


def test_find_vertex_occurrence_second_visit():
    # Out-and-back: pass (0,0) twice
    coords = [
        [-66.0, 45.0],
        [-66.1, 45.1],
        [-66.2, 45.2],
        [-66.1, 45.1],
        [-66.0, 45.0],
    ]
    assert find_vertex_occurrence(45.0, -66.0, coords, occurrence=1) == 0
    assert find_vertex_occurrence(45.0, -66.0, coords, occurrence=2) == 4


def test_migrate_breaks_to_waypoints():
    course = _line_course(
        [
            [-66.64, 45.95],
            [-66.63, 45.96],
            [-66.62, 45.97],
        ]
    )
    course["segment_breaks"] = [1]
    course["segment_break_labels"] = {1: "Friel"}
    course["segments"] = [
        {
            "seg_id": "1",
            "seg_label": "Start to Friel",
            "start_index": 0,
            "end_index": 1,
            "events": ["full", "half"],
            "from_km": 0,
            "to_km": 0.5,
        },
        {
            "seg_id": "2",
            "seg_label": "Friel to Finish",
            "start_index": 1,
            "end_index": 2,
            "events": ["full"],
            "from_km": 0.5,
            "to_km": 1.0,
        },
    ]
    migrate_breaks_to_waypoints(course)
    assert len(course["waypoints"]) == 3
    assert course["waypoints"][0]["id"] == "wp-start"
    assert course["waypoints"][1]["label"] == "Friel"
    assert len(course["segment_defs"]) == 2
    assert course["segment_defs"][0]["from_waypoint_id"] == "wp-start"
    assert course["segment_defs"][0]["to_waypoint_id"] == "wp-pin-1"


def test_resolve_segment_definitions():
    coords = [
        [-66.64, 45.95],
        [-66.63, 45.96],
        [-66.62, 45.97],
        [-66.61, 45.98],
    ]
    course = _line_course(coords)
    course["waypoints"] = [
        {"id": "wp-start", "label": "Start", "lat": 45.95, "lon": -66.64},
        {"id": "wp-mid", "label": "Mid", "lat": 45.97, "lon": -66.62},
        {"id": "wp-finish", "label": "Finish", "lat": 45.98, "lon": -66.61},
    ]
    course["segment_defs"] = [
        {
            "id": "sd-1",
            "from_waypoint_id": "wp-start",
            "to_waypoint_id": "wp-mid",
            "events": ["full"],
            "seg_label": "Start to Mid",
        },
        {
            "id": "sd-2",
            "from_waypoint_id": "wp-mid",
            "to_waypoint_id": "wp-finish",
            "events": ["full", "10k"],
            "seg_label": "Mid to Finish",
        },
    ]
    resolve_segments_from_definitions(course, event_ids=["full", "half", "10k"])
    assert len(course["segments"]) == 2
    assert course["segments"][0]["start_index"] == 0
    assert course["segments"][0]["end_index"] == 2
    assert course["segments"][0]["events"] == ["full"]
    assert course["segments"][1]["events"] == ["full", "10k"]
    assert 2 in course["segment_breaks"]


def test_resolve_rejects_to_before_from():
    course = _line_course(
        [
            [-66.64, 45.95],
            [-66.63, 45.96],
            [-66.62, 45.97],
        ]
    )
    course["waypoints"] = [
        {"id": "wp-a", "label": "A", "lat": 45.97, "lon": -66.62},
        {"id": "wp-b", "label": "B", "lat": 45.95, "lon": -66.64},
    ]
    course["segment_defs"] = [
        {
            "id": "sd-1",
            "from_waypoint_id": "wp-a",
            "to_waypoint_id": "wp-b",
            "events": ["full"],
        }
    ]
    with pytest.raises(ValueError, match="before"):
        resolve_segments_from_definitions(course)


def test_normalize_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    from app.core.config_package.storage import (
        create_config_package,
        load_config_course,
        save_config_course,
    )

    result = create_config_package("WP test", "")
    config_id = result["config_id"]
    course = load_config_course(config_id)
    course["geometry"] = {
        "type": "LineString",
        "coordinates": [[-66.64, 45.95], [-66.63, 45.96], [-66.62, 45.97]],
    }
    course["segment_breaks"] = [1]
    course["segment_break_labels"] = {"1": "Turn"}
    course["segments"] = [
        {
            "seg_id": "1",
            "seg_label": "Leg 1",
            "start_index": 0,
            "end_index": 1,
            "events": ["full"],
            "from_km": 0,
            "to_km": 0.1,
        },
        {
            "seg_id": "2",
            "seg_label": "Leg 2",
            "start_index": 1,
            "end_index": 2,
            "events": ["10k"],
            "from_km": 0.1,
            "to_km": 0.2,
        },
    ]
    save_config_course(config_id, course)
    reloaded = load_config_course(config_id)
    assert reloaded.get("waypoints")
    assert reloaded.get("segment_defs")
    assert len(reloaded["segments"]) == 2
