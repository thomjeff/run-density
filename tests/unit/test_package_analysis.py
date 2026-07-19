"""Tests for building v2 analyze payloads from config packages."""

import pytest
import yaml

from app.core.config_package.package_analysis import (
    build_package_analyze_payload,
    get_package_analyze_setup,
)
from app.core.config_package.saved_courses import (
    build_package_race_exports,
    save_org_course,
    set_package_course_assignments,
)
from app.core.config_package.segment_recipes import save_package_segment_manifest
from app.core.config_package.storage import create_config_package, resolve_config_package_path

_GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Org trail</name><trkseg>
    <trkpt lat="45.96" lon="-66.64"/>
    <trkpt lat="45.97" lon="-66.63"/>
  </trkseg></trk>
</gpx>"""


def _patch_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.config_package.storage.get_config_root",
        lambda: tmp_path / "config",
    )
    monkeypatch.setattr(
        "app.core.config_package.org_leg_library.get_runflow_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.utils.run_id.get_runflow_root",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "app.core.config_package.saved_courses.get_runflow_root",
        lambda: tmp_path,
    )


def _seed_org_legs(tmp_path, leg_ids=("05", "06")):
    org_dir = tmp_path / "org" / "legs"
    org_dir.mkdir(parents=True)
    manifest_legs = []
    for leg_id in leg_ids:
        gpx_name = f"{leg_id}_trail.gpx"
        (org_dir / gpx_name).write_text(_GPX, encoding="utf-8")
        manifest_legs.append(
            {
                "id": leg_id,
                "file": gpx_name,
                "seg_label": f"Leg {leg_id}",
                "start_label": "Start",
                "end_label": "End",
            }
        )
    (org_dir / "manifest.yaml").write_text(
        yaml.safe_dump({"legs": manifest_legs}),
        encoding="utf-8",
    )


def _build_ready_package(tmp_path, monkeypatch):
    _patch_roots(tmp_path, monkeypatch)
    _seed_org_legs(tmp_path)

    save_org_course(name="Full A", distance="full", recipe=["05", "06"], course_id="01")
    save_org_course(name="10K A", distance="10k", recipe=["05", "06"], course_id="02")

    created = create_config_package(
        "FM2027",
        "",
        event_day="sun",
        package_events=["full", "10k"],
    )
    config_id = created["config_id"]
    package_path = resolve_config_package_path(config_id)

    set_package_course_assignments(config_id, {"full": "01", "10k": "02"})
    save_package_segment_manifest(
        config_id,
        {
            "version": 1,
            "leg_source": "org",
            "legs": [],
            "recipes": {"full": [], "10k": []},
            "flow_overrides": [],
        },
    )
    build_package_race_exports(config_id)

    (package_path / "full_runners.csv").write_text("runner_id,event,pace\n1,full,5.0\n", encoding="utf-8")
    (package_path / "10k_runners.csv").write_text("runner_id,event,pace\n1,10k,5.0\n", encoding="utf-8")
    return config_id, package_path


def test_get_package_analyze_setup(tmp_path, monkeypatch):
    config_id, _package_path = _build_ready_package(tmp_path, monkeypatch)
    setup = get_package_analyze_setup(config_id)
    assert setup["event_day"] == "sun"
    assert len(setup["events"]) == 2
    assert setup["events"][0]["suggested_start_time"] is not None


def test_build_package_analyze_payload_requires_schedules(tmp_path, monkeypatch):
    config_id, package_path = _build_ready_package(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="events schedule is required"):
        build_package_analyze_payload(config_id, event_schedules=[])

    payload = build_package_analyze_payload(
        config_id,
        event_schedules=[
            {"name": "full", "start_time": 420, "event_duration_minutes": 390},
            {"name": "10k", "start_time": 460, "event_duration_minutes": 120},
        ],
    )
    assert payload["segments_file"] == "segments.csv"
    assert payload["data_dir"] == str(package_path.resolve())
    assert len(payload["events"]) == 2
    full = next(e for e in payload["events"] if e["name"] == "full")
    assert full["start_time"] == 420
    assert full["day"] == "sun"
    assert payload["event_group"]["sun-all"] == "full, 10k"
