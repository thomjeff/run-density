"""Tests for org-level leg library (Issue #780)."""

import yaml

from app.core.config_package.org_leg_library import (
    import_org_leg_to_package,
    list_org_legs,
    move_org_leg_location,
    publish_package_leg_to_org_library,
    update_org_leg,
    update_org_leg_geometry,
)
from app.core.config_package.segment_recipes import save_package_segment_manifest
from app.core.config_package.storage import create_config_package

_GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Org trail</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""


def test_list_and_import_org_leg(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )

    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "05_org_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "05",
                        "file": "05_org_trail.gpx",
                        "seg_label": "Org trail",
                        "start_label": "Start",
                        "end_label": "End",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = list_org_legs()
    assert len(rows) == 1
    assert rows[0]["org_leg_id"] == "05"
    assert rows[0]["leg_label"] == "Org trail"

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    state = import_org_leg_to_package(config_id, "05")
    assert state["imported_org_leg_id"] == "05"
    assert state["imported_package_leg_id"] == "01"
    assert len(state["legs"]) == 1
    assert state["legs"][0]["leg_label"] == "Org trail"


def test_publish_package_leg_to_org_library(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )

    result = create_config_package("Pkg", "", event_day="sun", package_events=["full"])
    config_id = result["config_id"]
    package_path = tmp_path / "config" / config_id
    lib_dir = package_path / "segment_library"
    lib_dir.mkdir(parents=True, exist_ok=True)
    (lib_dir / "01_trail.gpx").write_text(_GPX, encoding="utf-8")
    (lib_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "file": "01_trail.gpx",
                        "seg_label": "Package trail",
                        "locations": [
                            {
                                "loc_label": "Water",
                                "loc_type": "water",
                                "lat": 45.961,
                                "lon": -66.642,
                                "placement": "along",
                            }
                        ],
                    }
                ],
                "recipes": {},
            }
        ),
        encoding="utf-8",
    )

    published = publish_package_leg_to_org_library(config_id, "01")
    assert published["org_leg_id"] == "01"
    assert published["package_leg_id"] == "01"

    rows = list_org_legs()
    assert len(rows) == 1
    assert rows[0]["leg_label"] == "Package trail"
    assert rows[0]["location_count"] == 1


def test_create_org_leg_from_coordinates(tmp_path, monkeypatch):
    """Issue #789: drawn coordinates become a normal org library leg."""
    import pytest

    from app.core.config_package.org_leg_library import (
        create_org_leg_from_coordinates,
        get_org_legs_dir,
    )

    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )

    coords = [[-66.64, 45.96], [-66.635, 45.965], [-66.63, 45.97]]
    state = create_org_leg_from_coordinates(
        coords,
        leg_label="Drawn Trail",
        start_label="A",
        end_label="B",
        width_m=4.5,
        direction="bi",
        description="Drawn on the map",
    )
    assert state["leg_source"] == "org"
    legs = state["legs"]
    assert len(legs) == 1
    leg = legs[0]
    assert leg["leg_label"] == "Drawn Trail"
    assert leg["start_label"] == "A"
    assert leg["end_label"] == "B"
    assert leg["width_m"] == 4.5
    assert leg["direction"] == "bi"
    assert leg["length_km"] > 0

    gpx_files = list(get_org_legs_dir().glob("*.gpx"))
    assert len(gpx_files) == 1
    content = gpx_files[0].read_text(encoding="utf-8")
    assert 'lat="45.96"' in content
    assert 'lon="-66.63"' in content

    with pytest.raises(ValueError):
        create_org_leg_from_coordinates([[-66.64, 45.96]], leg_label="Too short")


def test_get_all_org_leg_line_geojson_single_manifest_read(tmp_path, monkeypatch):
    """Bulk leg geometries load manifest once, not per leg."""
    import yaml

    from app.core.config_package.org_leg_library import (
        get_all_org_leg_line_geojson,
        get_org_leg_line_geojson,
    )

    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "01_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "file": "01_trail.gpx",
                        "seg_label": "Org trail",
                        "start_label": "Start",
                        "end_label": "End",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    features = get_all_org_leg_line_geojson()
    assert len(features) == 1
    assert features[0]["geometry"]["type"] == "LineString"
    assert len(features[0]["geometry"]["coordinates"]) == 2
    assert features[0]["properties"]["leg_id"] == "01"

    single = get_org_leg_line_geojson("01")
    assert single["properties"]["leg_id"] == "01"
    assert single["geometry"]["coordinates"] == features[0]["geometry"]["coordinates"]


def test_copy_org_leg_duplicates_gpx_metadata_and_locations(tmp_path, monkeypatch):
    """Copy creates a new leg id with the same route, locations, and no pairing."""
    import yaml

    from app.core.config_package.org_leg_library import copy_org_leg, get_org_legs_dir

    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "16_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "16",
                        "file": "16_trail.gpx",
                        "seg_label": "Station At Barker To Trail At Aberdeen",
                        "start_label": "Barker",
                        "end_label": "Aberdeen",
                        "width_m": 3,
                        "schema": "on_course_open",
                        "direction": "uni",
                        "flow_type": "none",
                        "paired_with": "04",
                        "locations": [
                            {
                                "loc_label": "Water 1",
                                "loc_type": "water",
                                "lat": 45.96,
                                "lon": -66.64,
                                "placement": "along",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    state = copy_org_leg("16")
    assert state["copied_leg_id"] == "17"
    assert state["source_leg_id"] == "16"
    legs = state["legs"]
    assert len(legs) == 2
    original = next(l for l in legs if l["id"] == "16")
    copied = next(l for l in legs if l["id"] == "17")
    assert copied["leg_label"].endswith("(copy)")
    assert copied["start_label"] == "Barker"
    assert copied["end_label"] == "Aberdeen"
    assert copied.get("paired_with") in (None, "")
    assert len(copied.get("locations") or []) == 1
    assert copied["locations"][0]["loc_label"] == "Water 1"
    assert original["paired_with"] == "04"

    gpx_files = sorted(get_org_legs_dir().glob("*.gpx"))
    assert len(gpx_files) == 2
    assert gpx_files[0].read_bytes() == gpx_files[1].read_bytes()


def test_copy_org_leg_reversed_swaps_geometry_and_endpoint_labels(tmp_path, monkeypatch):
    """Reverse copy runs from source finish to source start with swapped labels."""
    from app.core.config_package.org_leg_library import copy_org_leg, get_org_legs_dir
    from app.core.course.segment_library import parse_leg_gpx

    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "23_trail.gpx").write_text(
        """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Bridge To Station</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.965" lon="-66.635"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>""",
        encoding="utf-8",
    )
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "23",
                        "file": "23_trail.gpx",
                        "seg_label": "Walking Bridge To Barker Station",
                        "start_label": "Walking Bridge",
                        "end_label": "Barker Station",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    source_parsed = parse_leg_gpx(org_dir / "23_trail.gpx")
    state = copy_org_leg("23", reverse=True)
    assert state["reversed"] is True
    assert state["copied_leg_id"] == "24"
    copied = next(l for l in state["legs"] if l["id"] == "24")
    assert copied["leg_label"].endswith("(reverse)")
    assert copied["start_label"] == "Barker Station"
    assert copied["end_label"] == "Walking Bridge"

    copied_gpx = org_dir / copied["file"]
    copied_parsed = parse_leg_gpx(copied_gpx)
    assert copied_parsed["coordinates"] == list(reversed(source_parsed["coordinates"]))
    assert copied_parsed["start"] == source_parsed["end"]
    assert copied_parsed["end"] == source_parsed["start"]
    assert len(list(get_org_legs_dir().glob("*.gpx"))) == 2


def test_copy_org_leg_locations_from_paired_leg(tmp_path, monkeypatch):
    """Copy locations onto an existing leg without duplicating the route."""
    import yaml

    from app.core.config_package.org_leg_library import copy_org_leg_locations, get_org_legs_dir

    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "36_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "37_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "36",
                        "file": "36_trail.gpx",
                        "seg_label": "George to Aberdeen via Trail",
                        "locations": [
                            {
                                "loc_label": "Trail at Charlotte",
                                "loc_type": "traffic",
                                "lat": 45.96,
                                "lon": -66.64,
                                "resources": {"yssr": 2},
                            }
                        ],
                        "paired_with": "37",
                    },
                    {
                        "id": "37",
                        "file": "37_trail.gpx",
                        "seg_label": "George to Aberdeen via Trail (reverse)",
                        "locations": [],
                        "paired_with": "36",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    state = copy_org_leg_locations("37", "36")
    assert state["target_leg_id"] == "37"
    assert state["source_leg_id"] == "36"
    assert state["location_count"] == 1
    copied = next(l for l in state["legs"] if l["id"] == "37")
    assert len(copied.get("locations") or []) == 1
    assert copied["locations"][0]["loc_label"] == "Trail at Charlotte"
    assert copied["locations"][0]["resources"]["yssr"] == 2
    assert len(list(get_org_legs_dir().glob("*.gpx"))) == 2


def test_move_org_leg_location_happy_path(tmp_path, monkeypatch):
    """Move one pin from source leg onto target; preserve location_key."""
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "05_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "12_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "05",
                        "file": "05_trail.gpx",
                        "seg_label": "Source corridor",
                        "locations": [
                            {
                                "loc_label": "Keep on source",
                                "loc_type": "course",
                                "lat": 45.961,
                                "lon": -66.641,
                                "location_key": "KEEP1",
                            },
                            {
                                "loc_label": "St John at Aberdeen",
                                "loc_type": "traffic",
                                "lat": 45.96,
                                "lon": -66.64,
                                "zone": "A",
                                "resources": {"yssr": 1},
                                "location_key": "ABCDE",
                            },
                        ],
                    },
                    {
                        "id": "12",
                        "file": "12_trail.gpx",
                        "seg_label": "Target corridor",
                        "locations": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    state = move_org_leg_location("05", 1, "12")
    assert state["source_leg_id"] == "05"
    assert state["target_leg_id"] == "12"
    assert state["new_loc_index"] == 0
    source = next(l for l in state["legs"] if l["id"] == "05")
    target = next(l for l in state["legs"] if l["id"] == "12")
    assert len(source.get("locations") or []) == 1
    assert source["locations"][0]["loc_label"] == "Keep on source"
    assert len(target.get("locations") or []) == 1
    moved = target["locations"][0]
    assert moved["loc_label"] == "St John at Aberdeen"
    assert moved["location_key"] == "ABCDE"
    assert moved["zone"] == "A"
    assert moved["resources"]["yssr"] == 1


def test_move_org_leg_location_blocks_duplicate_key(tmp_path, monkeypatch):
    """Refuse move when target already has the same location_key."""
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "05_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "12_trail.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "05",
                        "file": "05_trail.gpx",
                        "seg_label": "Source",
                        "locations": [
                            {
                                "loc_label": "Shared pin",
                                "loc_type": "traffic",
                                "lat": 45.96,
                                "lon": -66.64,
                                "location_key": "SAME2",
                            }
                        ],
                    },
                    {
                        "id": "12",
                        "file": "12_trail.gpx",
                        "seg_label": "Target",
                        "locations": [
                            {
                                "loc_label": "Already here",
                                "loc_type": "traffic",
                                "lat": 45.961,
                                "lon": -66.641,
                                "location_key": "SAME2",
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        move_org_leg_location("05", 0, "12")
        assert False, "expected ValueError for duplicate location_key"
    except ValueError as exc:
        assert "SAME2" in str(exc)


def test_update_org_leg_geometry(tmp_path, monkeypatch):
    """Trim/reshape saves edited coordinates back to org leg GPX."""
    from app.core.config_package.legs import parse_leg_gpx

    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "01_trail.gpx").write_text(
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
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "01",
                        "file": "01_trail.gpx",
                        "seg_label": "Org trail",
                        "start_label": "Start",
                        "end_label": "End",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    new_coords = [
        [-66.64, 45.96],
        [-66.638, 45.962],
        [-66.63, 45.97],
    ]
    state = update_org_leg_geometry("01", new_coords)
    leg = next(l for l in state["legs"] if l["id"] == "01")
    assert leg["length_km"] > 0
    parsed = parse_leg_gpx(org_dir / "01_trail.gpx")
    assert len(parsed["coordinates"]) == 3
    assert parsed["coordinates"][1][0] == -66.638


def test_update_org_leg_locations_skips_packages_without_course_json(
    tmp_path, monkeypatch
):
    """Org leg saves must not fail when legacy packages lack course.json."""
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )

    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "33_university.gpx").write_text(_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "33",
                        "file": "33_university.gpx",
                        "seg_label": "Forest Hill to George",
                        "locations": [
                            {
                                "loc_label": "University at George",
                                "loc_type": "traffic",
                                "lat": 45.955372,
                                "lon": -66.634182,
                                "placement": "off",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    legacy = create_config_package(
        "Legacy runners", "", event_day="sun", package_events=["10k"]
    )
    legacy_id = legacy["config_id"]
    save_package_segment_manifest(
        legacy_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {},
        },
    )
    (tmp_path / "config" / legacy_id / "course.json").unlink()

    state = update_org_leg(
        "33",
        {
            "locations": [
                {
                    "loc_label": "University at George",
                    "loc_type": "course",
                    "lat": 45.955372,
                    "lon": -66.634182,
                    "placement": "along",
                }
            ]
        },
    )
    leg = next(l for l in state["legs"] if l["id"] == "33")
    assert leg["locations"][0]["loc_type"] == "course"


_SPLIT_GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Split trail</name><trkseg>
    <trkpt lat="45.960000" lon="-66.640000"/>
    <trkpt lat="45.965000" lon="-66.635000"/>
    <trkpt lat="45.970000" lon="-66.630000"/>
  </trkseg></trk>
</gpx>"""


def _write_split_source(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    (org_dir / "12_trail.gpx").write_text(_SPLIT_GPX, encoding="utf-8")
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "legs": [
                    {
                        "id": "12",
                        "file": "12_trail.gpx",
                        "seg_label": "Walking Bridge To George",
                        "start_label": "Bridge",
                        "end_label": "George",
                        "width_m": 3,
                        "schema": "on_course_open",
                        "direction": "uni",
                        "flow_type": "none",
                        "paired_with": "04",
                        "locations": [
                            {
                                "loc_label": "Start water",
                                "loc_type": "water",
                                "lat": 45.960000,
                                "lon": -66.640000,
                                "placement": "along",
                            },
                            {
                                "loc_label": "Split water",
                                "loc_type": "water",
                                "lat": 45.965000,
                                "lon": -66.635000,
                                "placement": "along",
                            },
                            {
                                "loc_label": "End water",
                                "loc_type": "water",
                                "lat": 45.970000,
                                "lon": -66.630000,
                                "placement": "along",
                            },
                            {
                                "loc_label": "Traffic near end",
                                "loc_type": "traffic",
                                "lat": 45.970200,
                                "lon": -66.630100,
                                "placement": "off",
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return org_dir


def test_copy_split_org_leg_creates_two_legs_and_keeps_source(tmp_path, monkeypatch):
    from app.core.config_package.org_leg_library import copy_split_org_leg, get_org_legs_dir
    from app.core.course.segment_library import parse_leg_gpx

    _write_split_source(tmp_path, monkeypatch)
    state = copy_split_org_leg("12", split_lat=45.965000, split_lon=-66.635000)
    assert state["source_leg_id"] == "12"
    assert state["split_leg_ids"] == ["13", "14"]
    legs = {row["id"]: row for row in state["legs"]}
    source = legs["12"]
    first = legs["13"]
    second = legs["14"]
    assert source["leg_label"] == "Walking Bridge To George"
    assert source["paired_with"] == "04"
    assert len(source["locations"]) == 4
    assert first["leg_label"].endswith("(split 1)")
    assert second["leg_label"].endswith("(split 2)")
    assert first["start_label"] == "Bridge"
    assert first["end_label"] == "Split"
    assert second["start_label"] == "Split"
    assert second["end_label"] == "George"
    assert first.get("paired_with") in (None, "")
    assert second.get("paired_with") in (None, "")
    first_labels = {loc["loc_label"] for loc in first["locations"]}
    second_labels = {loc["loc_label"] for loc in second["locations"]}
    assert first_labels == {"Start water", "Split water"}
    assert second_labels == {"Split water", "End water", "Traffic near end"}

    org_dir = get_org_legs_dir()
    source_parsed = parse_leg_gpx(org_dir / "12_trail.gpx")
    first_parsed = parse_leg_gpx(org_dir / first["file"])
    second_parsed = parse_leg_gpx(org_dir / second["file"])
    assert len(source_parsed["coordinates"]) == 3
    def round6(pt):
        return [round(float(pt[0]), 6), round(float(pt[1]), 6)]

    assert round6(first_parsed["coordinates"][-1]) == round6(second_parsed["coordinates"][0])
    assert round6(first_parsed["coordinates"][0]) == round6(source_parsed["coordinates"][0])
    assert round6(second_parsed["coordinates"][-1]) == round6(source_parsed["coordinates"][-1])


def test_copy_split_org_leg_rejects_endpoint_and_offline_points(tmp_path, monkeypatch):
    from app.core.config_package.org_leg_library import copy_split_org_leg

    _write_split_source(tmp_path, monkeypatch)
    try:
        copy_split_org_leg("12", split_lat=45.960000, split_lon=-66.640000)
        raise AssertionError("expected start-point split to fail")
    except ValueError as exc:
        assert "start or finish" in str(exc)
    try:
        copy_split_org_leg("12", split_lat=46.5, split_lon=-67.5)
        raise AssertionError("expected off-line split to fail")
    except ValueError as exc:
        assert "too far" in str(exc)


def test_copy_split_org_leg_rolls_back_if_second_create_fails(tmp_path, monkeypatch):
    import app.core.config_package.org_leg_library as org_lib

    _write_split_source(tmp_path, monkeypatch)
    real_create = org_lib.create_org_leg_from_coordinates
    calls = {"n": 0}

    def flaky_create(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(org_lib, "create_org_leg_from_coordinates", flaky_create)
    try:
        org_lib.copy_split_org_leg("12", split_lat=45.965000, split_lon=-66.635000)
        raise AssertionError("expected second create failure")
    except RuntimeError:
        pass
    remaining = {row["id"] for row in org_lib.get_org_leg_library_state()["legs"]}
    assert remaining == {"12"}
    assert {path.name for path in (tmp_path / "org" / "legs").glob("*.gpx")} == {"12_trail.gpx"}


def test_copy_split_api_and_ui_markers_exist():
    from pathlib import Path

    from app.main import app

    routes = {route.path for route in app.routes}
    assert "/api/org/legs/{leg_id}/copy-split" in routes
    recipes = Path("frontend/static/js/map/segment_recipes.js").read_text(encoding="utf-8")
    actions = Path("frontend/static/js/table_actions.js").read_text(encoding="utf-8")
    assert "startLegCopySplit" in recipes
    assert "confirmLegCopySplit" in recipes
    assert "'split'" in actions or '"split"' in actions
    assert "kind === 'split'" in actions
