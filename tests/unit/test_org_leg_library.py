"""Tests for org-level leg library (Issue #780)."""

import yaml

from app.core.config_package.org_leg_library import import_org_leg_to_package, list_org_legs
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
