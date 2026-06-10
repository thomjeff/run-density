"""Tests for org-level leg library (Issue #780)."""

import yaml

from app.core.config_package.org_leg_library import (
    import_org_leg_to_package,
    list_org_legs,
    publish_package_leg_to_org_library,
)
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
