"""Tests for config package leg authoring (#769)."""

import json

import pytest

from app.core.config_package.legs import (
    allocate_next_leg_id,
    leg_row_from_entry,
    merge_leg_locations_into_course,
    sync_leg_segment_labels_into_course,
    _normalize_locations,
)
from app.core.config_package.location_ids import assign_unique_location_ids
from app.core.config_package.storage import create_config_package, load_config_course


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


def test_assign_unique_location_ids_repairs_duplicates():
    locations = [
        {"id": 1, "loc_label": "A"},
        {"id": 1, "loc_label": "B"},
        {"loc_label": "C"},
    ]
    assign_unique_location_ids(locations)
    ids = [loc["id"] for loc in locations]
    assert ids == [1, 2, 3]


def test_merge_leg_locations_sets_seg_id_from_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Loc merge", "", event_day="sun", package_events=["full", "half"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "chunks": [
            {
                "id": "01",
                "seg_label": "Leg one",
                "file": "01.gpx",
                "locations": [
                    {
                        "loc_label": "YSSR",
                        "loc_type": "course",
                        "lat": 45.96,
                        "lon": -66.64,
                        "placement": "along",
                    }
                ],
            }
        ],
        "recipes": {"full": ["01"], "half": []},
    }
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest), encoding="utf-8"
    )
    course_path = package_path / "course.json"
    course = json.loads(course_path.read_text())
    course["segment_library_applied"] = True
    course["segments"] = [
        {
            "seg_id": "S1",
            "chunk_id": "01",
            "events": ["full"],
            "from_km": 0,
            "to_km": 2.7,
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))

    merge_leg_locations_into_course(config_id)
    merged = load_config_course(config_id)
    leg_locs = [loc for loc in merged["locations"] if loc.get("source") == "leg"]
    assert len(leg_locs) == 1
    assert leg_locs[0]["seg_id"] == "S1"
    assert leg_locs[0]["leg_loc_key"] == "01:0"
    assert leg_locs[0]["full"] == "y"
    assert leg_locs[0]["half"] == "n"


def test_merge_leg_locations_assigns_unique_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Unique ids", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    manifest = {
        "chunks": [
            {
                "id": "01",
                "seg_label": "Leg one",
                "file": "01.gpx",
                "locations": [
                    {
                        "loc_label": "A",
                        "loc_type": "course",
                        "lat": 45.96,
                        "lon": -66.64,
                    }
                ],
            },
            {
                "id": "02",
                "seg_label": "Leg two",
                "file": "02.gpx",
                "locations": [
                    {
                        "loc_label": "B",
                        "loc_type": "course",
                        "lat": 45.97,
                        "lon": -66.65,
                    }
                ],
            },
        ],
        "recipes": {"full": ["01", "02"]},
    }
    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest), encoding="utf-8"
    )
    course_path = package_path / "course.json"
    course = json.loads(course_path.read_text())
    course["segment_library_applied"] = True
    course["segments"] = [
        {"seg_id": "S1", "chunk_id": "01", "events": ["full"]},
        {"seg_id": "S2", "chunk_id": "02", "events": ["full"]},
    ]
    course_path.write_text(json.dumps(course, indent=2))

    merge_leg_locations_into_course(config_id)
    merged = load_config_course(config_id)
    ids = [loc["id"] for loc in merged["locations"]]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == [1, 2]


def test_leg_id_for_segment_falls_back_to_s_index():
    from app.core.config_package.legs import _leg_id_for_segment

    order = ["01", "02", "03"]
    assert _leg_id_for_segment({"seg_id": "S2"}, order) == "02"
    assert _leg_id_for_segment({"seg_id": "S2", "chunk_id": "99"}, order) == "99"


def test_sync_leg_segment_labels_from_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Labels", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "chunks": [
                    {
                        "id": "01",
                        "seg_label": "Start to Friel",
                        "start_label": "Start",
                        "end_label": "Trail at Friel",
                        "file": "01.gpx",
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    course_path = package_path / "course.json"
    course = json.loads(course_path.read_text())
    course["segment_library_applied"] = True
    course["segments"] = [
        {
            "seg_id": "S1",
            "chunk_id": "01",
            "from_label": "Old start",
            "to_label": "Old end",
            "seg_label": "old_label",
            "events": ["full"],
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))

    assert sync_leg_segment_labels_into_course(config_id) is True
    merged = load_config_course(config_id)
    seg = merged["segments"][0]
    assert seg["from_label"] == "Start"
    assert seg["to_label"] == "Trail at Friel"
    assert seg["seg_label"] == "Start to Friel"


def test_leg_row_from_entry_defaults():
    row = leg_row_from_entry(
        {"id": "01", "seg_label": "Start to Friel", "start_label": "", "end_label": ""},
        {"length_km": 2.7, "coordinates": [[-66.6, 45.9], [-66.5, 45.95]]},
    )
    assert row["id"] == "01"
    assert "Start" in row["start_label"]
    assert "Friel" in row["end_label"] or row["leg_label"]
