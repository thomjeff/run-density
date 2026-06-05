"""Tests for config package leg authoring (#769)."""

import json
import zipfile
from io import BytesIO

import pytest

from app.core.config_package.legs import (
    allocate_next_leg_id,
    export_package_leg_zip,
    leg_row_from_entry,
    merge_leg_locations_into_course,
    parse_leg_export_json_bytes,
    reconcile_leg_locations_to_course,
    remove_leg_location_from_manifest,
    sync_leg_location_metadata_from_course,
    sync_leg_metadata_into_course,
    sync_leg_segment_labels_into_course,
    update_package_leg,
    update_package_leg_geometry,
    _normalize_flow_notes,
    _normalize_flow_type,
    _normalize_locations,
)
from app.core.course.segment_library import (
    build_course_segments_from_library,
    build_flow_csv_from_segments,
    load_leg_library,
)
from app.core.config_package.segment_recipes import import_gpx_files_to_library, parse_leg_gpx
from app.core.config_package.location_ids import assign_unique_location_ids
from app.core.config_package.storage import create_config_package, load_config_course


def test_allocate_next_leg_id():
    legs = [{"id": "01"}, {"id": "02"}, {"id": "15"}]
    assert allocate_next_leg_id(legs) == "16"
    assert allocate_next_leg_id([]) == "01"


def test_normalize_locations():
    locs = _normalize_locations([
        {"loc_label": "Water", "loc_type": "water", "lat": 45.96, "lon": -66.64, "placement": "start"},
        {"label": "bad", "lat": "x"},
    ])
    assert len(locs) == 1
    assert locs[0]["loc_type"] == "water"


def test_course_loc_label_preserved_after_reconcile(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Label edit", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "file": "01.gpx",
                        "locations": [
                            {
                                "loc_label": "Original label",
                                "loc_type": "course",
                                "lat": 45.96,
                                "lon": -66.64,
                                "placement": "along",
                            }
                        ],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Leg one</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    course_path = package_path / "course.json"
    course = load_config_course(config_id)
    course["segment_library_applied"] = True
    course["segments"] = [
        {"seg_id": "S1", "leg_id": "01", "events": ["full"]},
    ]
    merge_leg_locations_into_course(config_id)
    course = load_config_course(config_id)
    course["locations"][0]["loc_label"] = "Edited on Course tab"
    course_path.write_text(json.dumps(course, indent=2))

    sync_leg_location_metadata_from_course(config_id)
    reconcile_leg_locations_to_course(config_id)
    merged = load_config_course(config_id)
    assert merged["locations"][0]["loc_label"] == "Edited on Course tab"

    manifest = yaml.safe_load((lib_dir / "manifest.yaml").read_text())
    assert manifest["legs"][0]["locations"][0]["loc_label"] == "Edited on Course tab"


def test_normalize_locations_off_course_placement():
    locs = _normalize_locations([
        {
            "loc_label": "Regent at McLeod",
            "loc_type": "traffic",
            "lat": 45.954,
            "lon": -66.641,
            "placement": "off",
        },
    ])
    assert len(locs) == 1
    assert locs[0]["placement"] == "off"


def test_merge_traffic_location_has_empty_seg_id(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Traffic off course", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "file": "01.gpx",
                        "locations": [
                            {
                                "loc_label": "Regent at McLeod",
                                "loc_type": "traffic",
                                "lat": 45.954492,
                                "lon": -66.6414,
                                "placement": "off",
                            }
                        ],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    course_path = package_path / "course.json"
    course = load_config_course(config_id)
    course["segment_library_applied"] = True
    course["segments"] = [
        {
            "seg_id": "S1",
            "leg_id": "01",
            "events": ["full"],
            "from_km": 0,
            "to_km": 2.7,
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))

    merge_leg_locations_into_course(config_id)
    merged = load_config_course(config_id)
    traffic = merged["locations"][0]
    assert traffic["loc_type"] == "traffic"
    assert traffic.get("seg_id") in ("", None)
    assert traffic.get("placement") == "off"


def test_merge_water_location_gets_seg_id(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Water on course", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "file": "01.gpx",
                        "locations": [
                            {
                                "loc_label": "Water Stop",
                                "loc_type": "water",
                                "lat": 45.96,
                                "lon": -66.64,
                                "placement": "along",
                            }
                        ],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    course_path = package_path / "course.json"
    course = load_config_course(config_id)
    course["segment_library_applied"] = True
    course["segments"] = [
        {"seg_id": "S1", "leg_id": "01", "events": ["full"]},
    ]
    course_path.write_text(json.dumps(course, indent=2))

    merge_leg_locations_into_course(config_id)
    merged = load_config_course(config_id)
    water = merged["locations"][0]
    assert water["loc_type"] == "water"
    assert water.get("seg_id") == "S1"


def test_assign_unique_location_ids_repairs_duplicates():
    locations = [
        {"id": 1, "loc_label": "A"},
        {"id": 1, "loc_label": "B"},
        {"loc_label": "C"},
    ]
    assign_unique_location_ids(locations)
    ids = [loc["id"] for loc in locations]
    assert ids == [1, 2, 3]


def test_merge_leg_locations_sets_seg_id_from_leg(tmp_path, monkeypatch):
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
        "legs": [
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
            "leg_id": "01",
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
        "legs": [
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
        {"seg_id": "S1", "leg_id": "01", "events": ["full"]},
        {"seg_id": "S2", "leg_id": "02", "events": ["full"]},
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
    assert _leg_id_for_segment({"seg_id": "S2", "leg_id": "99"}, order) == "99"


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
                "legs": [
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
            "leg_id": "01",
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


def test_sync_leg_flow_type_to_segment(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Flow sync", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Start to Friel",
                        "file": "01.gpx",
                        "flow_type": "merge",
                        "flow_notes": "Keep right",
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
            "leg_id": "01",
            "seg_label": "Start to Friel",
            "flow_type": "overtake",
            "flow_notes": "",
            "events": ["full"],
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))

    assert sync_leg_metadata_into_course(config_id) is True
    merged = load_config_course(config_id)
    seg = merged["segments"][0]
    assert seg["flow_type"] == "merge"
    assert seg["description"] == "Keep right"


def test_sync_leg_description_with_chunk_id_without_applied_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Chunk sync", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Start to Friel",
                        "start_label": "Start",
                        "end_label": "Friel",
                        "description": "From manifest legs",
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
    course["segments"] = [
        {
            "seg_id": "S1",
            "chunk_id": "01",
            "seg_label": "01_start_friel",
            "description": "",
            "events": ["full"],
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))

    assert sync_leg_metadata_into_course(config_id) is True
    merged = load_config_course(config_id)
    assert merged["segments"][0]["description"] == "From manifest legs"
    assert merged["segments"][0].get("leg_id") == "01"
    assert "chunk_id" not in merged["segments"][0]


def test_sync_leg_description_to_segment(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Desc sync", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Start to Friel",
                        "file": "01.gpx",
                        "description": "Shared start corridor",
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
            "leg_id": "01",
            "seg_label": "Start to Friel",
            "description": "",
            "events": ["full"],
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))

    assert sync_leg_metadata_into_course(config_id) is True
    merged = load_config_course(config_id)
    assert merged["segments"][0]["description"] == "Shared start corridor"


def test_prune_segments_not_in_recipes_on_sync(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Prune sync", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {"id": "01", "seg_label": "Used", "file": "01.gpx"},
                    {"id": "09", "seg_label": "Unused", "file": "09.gpx"},
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
        {"seg_id": "S1", "leg_id": "01", "events": ["full"]},
        {"seg_id": "S9", "leg_id": "09", "events": []},
    ]
    course_path.write_text(json.dumps(course, indent=2))

    assert sync_leg_metadata_into_course(config_id) is True
    merged = load_config_course(config_id)
    assert [s["leg_id"] for s in merged["segments"]] == ["01"]


def test_update_package_leg_syncs_flow_type_without_recipe_apply(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Flow update", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "start_label": "Start",
                        "end_label": "End",
                        "description": "Leg one segment",
                        "file": "01.gpx",
                        "flow_type": "none",
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
            "leg_id": "01",
            "flow_type": "overtake",
            "events": ["full"],
        }
    ]
    course_path.write_text(json.dumps(course, indent=2))
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )

    update_package_leg(
        config_id,
        "01",
        {"flow_type": "counterflow", "description": "Bi traffic"},
    )
    merged = load_config_course(config_id)
    assert merged["segments"][0]["flow_type"] == "counterflow"
    assert merged["segments"][0]["description"] == "Bi traffic"


def test_update_package_leg_merges_locations_before_recipes_applied(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Early locs", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "file": "01.gpx",
                        "locations": [],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Leg one</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    course = load_config_course(config_id)
    assert course.get("segment_library_applied") is not True

    update_package_leg(
        config_id,
        "01",
        {
            "locations": [
                {
                    "loc_label": "Traffic control",
                    "loc_type": "traffic",
                    "lat": 45.96,
                    "lon": -66.64,
                    "placement": "along",
                }
            ]
        },
    )
    merged = load_config_course(config_id)
    assert len(merged["locations"]) == 1
    assert merged["locations"][0]["loc_type"] == "traffic"
    assert merged["locations"][0]["source"] == "leg"


def test_remove_stale_leg_loc_key_reconciles_course(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Stale key", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "file": "01.gpx",
                        "locations": [
                            {
                                "loc_label": "Only one",
                                "loc_type": "course",
                                "lat": 45.96,
                                "lon": -66.64,
                                "placement": "along",
                            }
                        ],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Leg one</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    course_path = package_path / "course.json"
    course = load_config_course(config_id)
    course["locations"] = [
        {
            "id": 1,
            "loc_label": "Only one",
            "loc_type": "course",
            "lat": 45.96,
            "lon": -66.64,
            "source": "leg",
            "leg_id": "01",
            "leg_loc_key": "01:0",
        },
        {
            "id": 2,
            "loc_label": "Orphan",
            "loc_type": "course",
            "lat": 45.965,
            "lon": -66.635,
            "source": "leg",
            "leg_id": "01",
            "leg_loc_key": "01:1",
        },
    ]
    course_path.write_text(json.dumps(course, indent=2))

    assert remove_leg_location_from_manifest(config_id, "01:1") is False
    reconcile_leg_locations_to_course(config_id)
    merged = load_config_course(config_id)
    assert len(merged["locations"]) == 1
    assert merged["locations"][0]["loc_label"] == "Only one"


def test_remove_leg_location_from_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Remove loc", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "file": "01.gpx",
                        "locations": [
                            {
                                "loc_label": "First",
                                "loc_type": "course",
                                "lat": 45.96,
                                "lon": -66.64,
                                "placement": "along",
                            },
                            {
                                "loc_label": "Duplicate",
                                "loc_type": "course",
                                "lat": 45.961,
                                "lon": -66.639,
                                "placement": "along",
                            },
                        ],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Leg one</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    merge_leg_locations_into_course(config_id)
    assert remove_leg_location_from_manifest(config_id, "01:1") is True
    reconcile_leg_locations_to_course(config_id)
    merged = load_config_course(config_id)
    assert len(merged["locations"]) == 1
    assert merged["locations"][0]["loc_label"] == "First"


def test_leg_row_from_entry_defaults():
    row = leg_row_from_entry(
        {"id": "01", "seg_label": "Start to Friel", "start_label": "", "end_label": ""},
        {"length_km": 2.7, "coordinates": [[-66.6, 45.9], [-66.5, 45.95]]},
    )
    assert row["id"] == "01"
    assert "Start" in row["start_label"]
    assert "Friel" in row["end_label"] or row["leg_label"]


def test_export_package_leg_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Export test", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "River trail",
                        "file": "01_river.gpx",
                        "start_label": "Start A",
                        "end_label": "End B",
                        "width_m": 4,
                        "schema": "on_course_narrow",
                        "direction": "bi",
                        "description": "Test leg",
                        "locations": [
                            {
                                "loc_label": "Water stop",
                                "loc_type": "water",
                                "lat": 45.961,
                                "lon": -66.642,
                                "placement": "along",
                            }
                        ],
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    gpx_body = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>River trail</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""
    (lib_dir / "01_river.gpx").write_text(gpx_body, encoding="utf-8")

    zip_bytes, filename = export_package_leg_zip(config_id, "01")
    assert filename == f"{config_id}_leg_01.zip"
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        assert "01.gpx" in names
        assert "01.json" in names
        assert zf.read("01.gpx").decode("utf-8") == gpx_body
        meta = json.loads(zf.read("01.json").decode("utf-8"))
    assert meta["export_kind"] == "runflow_leg"
    assert meta["config_id"] == config_id
    leg = meta["leg"]
    assert leg["leg_label"] == "River trail"
    assert leg["schema"] == "on_course_narrow"
    assert leg["direction"] == "bi"
    assert leg["width_m"] == 4
    assert len(leg["locations"]) == 1
    assert leg["locations"][0]["loc_label"] == "Water stop"


def test_import_gpx_with_leg_export_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package("Import JSON", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    gpx_body = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Trail</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""
    export_json = {
        "export_version": 1,
        "export_kind": "runflow_leg",
        "config_id": "other",
        "leg": {
            "id": "01",
            "leg_label": "Imported label",
            "start_label": "Start X",
            "end_label": "End Y",
            "width_m": 5,
            "schema": "on_course_narrow",
            "direction": "bi",
            "description": "From export",
            "gpx_file": "01.gpx",
            "locations": [
                {
                    "loc_label": "Aid tent",
                    "loc_type": "aid",
                    "lat": 45.965,
                    "lon": -66.635,
                    "placement": "along",
                }
            ],
        },
    }
    state = import_gpx_files_to_library(
        config_id,
        [
            ("01.gpx", gpx_body.encode("utf-8")),
            ("01.json", json.dumps(export_json).encode("utf-8")),
        ],
    )
    leg = state["legs"][0]
    assert leg["id"] == "01"
    assert leg["leg_label"] == "Imported label"
    assert leg["start_label"] == "Start X"
    assert leg["schema"] == "on_course_narrow"
    assert leg["direction"] == "bi"
    assert len(leg["locations"]) == 1
    assert leg["locations"][0]["loc_label"] == "Aid tent"


def test_parse_leg_export_json_bytes():
    leg = parse_leg_export_json_bytes(
        json.dumps({"export_kind": "runflow_leg", "leg": {"id": "02", "leg_label": "X"}}).encode()
    )
    assert leg["id"] == "02"
    assert parse_leg_export_json_bytes(b"{}") is None


def test_update_package_leg_geometry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package("Geom", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg",
                        "file": "01_leg.gpx",
                        "locations": [],
                    }
                ],
                "recipes": {},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01_leg.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.965" lon="-66.635"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    new_coords = [
        [-66.64, 45.96],
        [-66.638, 45.962],
        [-66.63, 45.97],
    ]
    state = update_package_leg_geometry(config_id, "01", new_coords)
    leg = state["legs"][0]
    assert leg["length_km"] > 0
    parsed = parse_leg_gpx(lib_dir / "01_leg.gpx")
    assert len(parsed["coordinates"]) == 3
    assert parsed["coordinates"][1][0] == -66.638


def test_refresh_location_seg_ids_updates_stale_leg_seg_id():
    from app.core.config_package.legs import refresh_location_seg_ids_from_segments

    segments = [
        {"seg_id": "S1", "leg_id": "01"},
        {"seg_id": "S2", "leg_id": "02"},
    ]
    locations = [
        {
            "id": 1,
            "loc_label": "Aid",
            "loc_type": "course",
            "leg_id": "01",
            "seg_id": "S2",
            "source": "leg",
        }
    ]
    updated = refresh_location_seg_ids_from_segments(locations, segments)
    assert updated == 1
    assert locations[0]["seg_id"] == "S1"


def test_refresh_location_seg_ids_clears_traffic_seg_id():
    from app.core.config_package.legs import refresh_location_seg_ids_from_segments

    segments = [{"seg_id": "S1", "leg_id": "01"}]
    locations = [
        {
            "id": 2,
            "loc_label": "Barricade",
            "loc_type": "traffic",
            "seg_id": "S1",
            "proxy_loc_id": 1,
        }
    ]
    updated = refresh_location_seg_ids_from_segments(locations, segments)
    assert updated == 1
    assert locations[0]["seg_id"] == ""


def test_validate_locations_for_export_rejects_stale_seg_id():
    from app.core.config_package.legs import validate_locations_for_export

    course = {
        "segments": [{"seg_id": "S1", "leg_id": "01"}],
        "locations": [
            {
                "id": 1,
                "loc_label": "Stale",
                "loc_type": "course",
                "seg_id": "S99",
            }
        ],
    }
    errors = validate_locations_for_export(course)
    assert any("S99" in e for e in errors)


def test_validate_locations_for_export_rejects_missing_proxy():
    from app.core.config_package.legs import validate_locations_for_export

    course = {
        "segments": [{"seg_id": "S1", "leg_id": "01"}],
        "locations": [
            {
                "id": 5,
                "loc_label": "Traffic",
                "loc_type": "traffic",
                "seg_id": "",
                "proxy_loc_id": 99,
            }
        ],
    }
    errors = validate_locations_for_export(course)
    assert any("proxy_loc_id 99" in e for e in errors)


def test_export_config_package_segments_fails_on_invalid_proxy(
    tmp_path, monkeypatch
):
    from app.core.config_package.storage import (
        export_config_package_segments,
        save_config_course,
    )

    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Export guard", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    course = load_config_course(config_id)
    course["segments"] = [
        {
            "seg_id": "S1",
            "seg_label": "Only",
            "width_m": 3,
            "schema": "on_course_open",
            "direction": "uni",
            "full": "y",
            "full_from_km": 0,
            "full_to_km": 1,
        }
    ]
    course["locations"] = [
        {
            "id": 1,
            "loc_label": "Aid",
            "loc_type": "course",
            "lat": 45.96,
            "lon": -66.64,
            "seg_id": "S1",
            "full": "y",
        },
        {
            "id": 2,
            "loc_label": "Traffic",
            "loc_type": "traffic",
            "lat": 45.97,
            "lon": -66.63,
            "seg_id": "",
            "proxy_loc_id": 42,
            "full": "y",
        },
    ]
    save_config_course(config_id, course)
    with pytest.raises(ValueError, match="Cannot export locations.csv"):
        export_config_package_segments(config_id)


def test_update_package_leg_requires_description(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Desc required", "", event_day="sun", package_events=["full"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Leg one",
                        "start_label": "Start",
                        "end_label": "End",
                        "description": "Initial",
                        "file": "01.gpx",
                    }
                ],
                "recipes": {"full": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="description is required"):
        update_package_leg(config_id, "01", {"description": "   "})


def test_normalize_flow_type_rejects_invalid():
    assert _normalize_flow_type("merge") == "merge"
    assert _normalize_flow_notes("  note  ") == "note"
    with pytest.raises(ValueError, match="flow_type"):
        _normalize_flow_type("diverge")


def test_leg_flow_type_persisted_and_exported(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    result = create_config_package(
        "Flow meta", "", event_day="sun", package_events=["full", "half"]
    )
    config_id = result["config_id"]
    package_path = tmp_path / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "seg_label": "Shared start",
                        "start_label": "Start",
                        "end_label": "End",
                        "description": "Initial note",
                        "file": "01.gpx",
                        "schema": "on_course_open",
                        "direction": "uni",
                        "flow_type": "overtake",
                    }
                ],
                "recipes": {"full": ["01"], "half": ["01"]},
            }
        ),
        encoding="utf-8",
    )
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Shared start</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )

    update_package_leg(
        config_id,
        "01",
        {"flow_type": "merge", "description": "Keep right critical"},
    )
    manifest = yaml.safe_load((lib_dir / "manifest.yaml").read_text())
    assert manifest["legs"][0]["flow_type"] == "merge"
    assert manifest["legs"][0]["description"] == "Keep right critical"

    row = leg_row_from_entry(manifest["legs"][0], parse_leg_gpx(lib_dir / "01.gpx"))
    assert row["flow_type"] == "merge"
    assert row["description"] == "Keep right critical"

    zip_bytes, _ = export_package_leg_zip(config_id, "01")
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        payload = json.loads(zf.read("01.json"))
    assert payload["leg"]["flow_type"] == "merge"
    assert payload["leg"]["description"] == "Keep right critical"


def test_flow_type_propagates_to_segments_and_flow_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    lib_dir = tmp_path / "pkg" / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    manifest = {
        "legs": [
            {
                "id": "01",
                "seg_label": "Leg A",
                "file": "01.gpx",
                "flow_type": "counterflow",
                "flow_notes": "Shared trail",
            }
        ],
        "recipes": {"full": ["01"], "10k": ["01"]},
    }
    (lib_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    (lib_dir / "01.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    legs_by_id = load_leg_library(lib_dir, manifest)
    segments = build_course_segments_from_library(
        manifest, legs_by_id, event_ids=["full", "10k"]
    )
    assert segments[0]["flow_type"] == "counterflow"
    assert segments[0]["description"] == "Shared trail"
    csv_text = build_flow_csv_from_segments(segments, ["full", "10k"])
    assert ",counterflow," in csv_text
    assert "Shared trail" in csv_text
