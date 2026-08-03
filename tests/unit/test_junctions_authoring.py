"""Unit tests for Junction Flow authoring (Issue #817)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config_package.junctions import (
    find_nearby_segments,
    load_config_junctions,
    save_config_junctions,
    validate_junctions_doc,
)
from app.core.config_package.storage import create_config_package, save_config_course
from app.utils.constants import JUNCTION_SEGMENT_PROXIMITY_M


def test_junction_proximity_constant():
    assert JUNCTION_SEGMENT_PROXIMITY_M == 20.0


def test_validate_junctions_cross_and_merge():
    doc = validate_junctions_doc(
        {
            "version": 1,
            "junctions": [
                {
                    "id": "j1",
                    "label": "George",
                    "lat": 45.95,
                    "lon": -66.63,
                    "nearby_seg_ids": ["S8", "S9", "S11", "S25", "S26", "S22"],
                    "interactions": [
                        {
                            "type": "cross",
                            "side": "left",
                            "from_seg_id": "S8",
                            "to_seg_ids": ["S25"],
                            "conflicts_with_seg_id": "S11",
                            "events": ["10k", "full", "half"],
                        },
                        {
                            "type": "merge",
                            "from_seg_id": "S26",
                            "to_seg_ids": ["S9", "S22"],
                            "events": ["10k", "full"],
                        },
                    ],
                }
            ],
        }
    )
    j = doc["junctions"][0]
    assert j["interactions"][0]["type"] == "cross"
    assert j["interactions"][0]["to_seg_ids"] == ["S25"]
    assert j["interactions"][1]["to_seg_ids"] == ["S9", "S22"]
    assert j["interactions"][1]["conflicts_with_seg_id"] == ""
    stream_ids = {s["seg_id"] for s in j["streams"]}
    assert {"S8", "S9", "S11", "S25", "S26", "S22"} <= stream_ids


def test_validate_rejects_cross_without_conflicts():
    with pytest.raises(ValueError, match="conflicts_with_seg_id"):
        validate_junctions_doc(
            {
                "junctions": [
                    {
                        "id": "j1",
                        "label": "x",
                        "lat": 1,
                        "lon": 2,
                        "interactions": [
                            {
                                "type": "cross",
                                "from_seg_id": "S8",
                                "to_seg_ids": ["S25"],
                            }
                        ],
                    }
                ]
            }
        )


def test_validate_rejects_cross_multi_to():
    with pytest.raises(ValueError, match="exactly one"):
        validate_junctions_doc(
            {
                "junctions": [
                    {
                        "id": "j1",
                        "label": "x",
                        "lat": 1,
                        "lon": 2,
                        "interactions": [
                            {
                                "type": "cross",
                                "from_seg_id": "S8",
                                "to_seg_ids": ["S25", "S9"],
                                "conflicts_with_seg_id": "S11",
                            }
                        ],
                    }
                ]
            }
        )


def test_load_save_junctions_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.core.config_package.junctions.resolve_config_package_path",
        lambda config_id: tmp_path / config_id,
    )
    pkg = create_config_package(
        "Junc Test",
        "",
        event_day="sun",
        package_events=["full", "10k"],
    )
    cid = pkg["config_id"]
    empty = load_config_junctions(cid)
    assert empty["junctions"] == []

    save_config_junctions(
        cid,
        {
            "version": 1,
            "junctions": [
                {
                    "id": "j1",
                    "label": "Test",
                    "lat": 45.0,
                    "lon": -66.0,
                    "nearby_seg_ids": ["S1"],
                    "interactions": [],
                }
            ],
        },
    )
    loaded = load_config_junctions(cid)
    assert len(loaded["junctions"]) == 1
    assert loaded["junctions"][0]["label"] == "Test"
    assert (tmp_path / cid / "junctions.json").is_file()


def _write_two_point_gpx(path: Path, lon0: float, lat0: float, lon1: float, lat1: float) -> None:
    path.write_text(
        f"""<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><trkseg>
    <trkpt lat="{lat0}" lon="{lon0}"/>
    <trkpt lat="{lat1}" lon="{lon1}"/>
  </trkseg></trk>
</gpx>
""",
        encoding="utf-8",
    )


def test_find_nearby_segments_uses_endpoints(tmp_path, monkeypatch):
    """Synthetic course + GPX: only endpoint-near segments are returned."""
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.core.config_package.junctions.resolve_leg_library",
        lambda config_id: (
            tmp_path / config_id / "legs",
            {
                "legs": [
                    {"id": "01", "file": "01.gpx", "seg_label": "Near"},
                    {"id": "02", "file": "02.gpx", "seg_label": "Far"},
                ]
            },
            "package",
            {"recipes": {}},
        ),
    )

    pkg = create_config_package(
        "Nearby",
        "",
        event_day="sun",
        package_events=["full"],
    )
    cid = pkg["config_id"]
    legs_dir = tmp_path / cid / "legs"
    legs_dir.mkdir(parents=True, exist_ok=True)

    # Pin at (0,0); near leg ends at origin; far leg is ~1km away
    _write_two_point_gpx(legs_dir / "01.gpx", -0.00005, 0.0, 0.0, 0.0)
    _write_two_point_gpx(legs_dir / "02.gpx", 0.01, 0.01, 0.011, 0.011)

    course = {
        "segments": [
            {
                "seg_id": "S1",
                "seg_label": "Near",
                "leg_id": "01",
                "events": ["full"],
                "full_from_km": 0.0,
                "full_to_km": 0.1,
                "length_km": 0.1,
            },
            {
                "seg_id": "S2",
                "seg_label": "Far",
                "leg_id": "02",
                "events": ["full"],
                "full_from_km": 1.0,
                "full_to_km": 1.2,
                "length_km": 0.2,
            },
        ]
    }
    save_config_course(cid, course)

    nearby = find_nearby_segments(cid, 0.0, 0.0, radius_m=10.0)
    ids = [r["seg_id"] for r in nearby]
    assert ids == ["S1"]
    assert nearby[0]["near_endpoint"] in ("start", "end", "both")
