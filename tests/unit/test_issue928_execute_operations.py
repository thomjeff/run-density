"""Issue #928 Milestone 1: command surface, assignments, SOS latch."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.execute.assignments import (
    AssignmentError,
    delete_assignment,
    list_assignments,
    upsert_assignment,
)
from app.core.execute.layers import is_turnaround, turnaround_pins
from app.core.execute.published_plan import (
    activate_published_plan,
    import_published_plan,
    operations_board,
    record_operations_close,
    record_operations_reopen,
    save_registry,
)


def _zip_from_files(files: dict) -> bytes:
    import zipfile
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, payload in files.items():
            if isinstance(payload, dict):
                payload = json.dumps(payload).encode("utf-8")
            zf.writestr(name, payload)
    return buffer.getvalue()


def _package(
    *,
    calendar_date: str,
    weekday_code: str,
    plan_id: str | None = None,
    loc_label: str = "Queen",
    loc_end: str = "08:50:00",
) -> bytes:
    plan_id = plan_id or str(uuid4())
    locations = {
        "locations": [
            {
                "loc_id": 2,
                "loc_label": loc_label,
                "loc_type": "traffic",
                "zone": 1,
                "lat": 45.96,
                "lon": -66.64,
                "loc_end": loc_end,
            },
            {
                "loc_id": 9,
                "loc_label": "Nashwaaksis Turn-around",
                "loc_type": "course",
                "zone": 2,
                "lat": 45.99,
                "lon": -66.65,
                "loc_end": "09:10:00",
            },
        ],
        "resources_available": [],
    }
    course = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"events": ["10k"]},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-66.64, 45.96], [-66.63, 45.97]],
                },
            }
        ],
    }
    from app.core.execute.published_plan import sha256_bytes

    loc_bytes = json.dumps(locations).encode("utf-8")
    course_bytes = json.dumps(course).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "plan_id": plan_id,
        "revision": 1,
        "published_at": "2026-10-25T12:00:00+00:00",
        "calendar_date": calendar_date,
        "weekday_code": weekday_code,
        "name": f"{weekday_code} plan",
        "timezone": "America/Halifax",
        "races": [
            {
                "id": "10k",
                "name": "10K",
                "start_time": "08:00",
                "duration_minutes": 90,
                "course": "courses/10k.geojson",
            }
        ],
        "files": [
            {
                "path": "locations.json",
                "sha256": sha256_bytes(loc_bytes),
            },
            {
                "path": "courses/10k.geojson",
                "sha256": sha256_bytes(course_bytes),
            },
        ],
    }
    return _zip_from_files(
        {
            "manifest.json": manifest,
            "locations.json": loc_bytes,
            "courses/10k.geojson": course_bytes,
        }
    )


def _import_two_days(tmp_path: Path) -> tuple[str, str]:
    sat = str(uuid4())
    sun = str(uuid4())
    import_published_plan(
        _package(
            calendar_date="2026-05-09",
            weekday_code="sat",
            plan_id=sat,
        ),
        root=tmp_path,
    )
    import_published_plan(
        _package(
            calendar_date="2026-05-10",
            weekday_code="sun",
            plan_id=sun,
        ),
        root=tmp_path,
    )
    return sat, sun


def test_assignments_are_day_plan_specific(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    sat, sun = _import_two_days(tmp_path)
    upsert_assignment(
        sat,
        {
            "device_id": "imei-1180",
            "resource_name": "Half Lead",
            "person_name": "Pat Nguyen",
            "phone": "+1 (506) 555-0144",
            "agency": "Race Crew",
        },
        root=tmp_path,
    )
    upsert_assignment(
        sun,
        {
            "device_id": "imei-1180",
            "resource_name": "10K Lead",
            "person_name": "Pat Nguyen",
            "phone": "+1 (506) 555-0144",
            "agency": "Race Crew",
        },
        root=tmp_path,
    )
    sat_rows = list_assignments(sat, root=tmp_path)
    sun_rows = list_assignments(sun, root=tmp_path)
    assert sat_rows[0]["resource_name"] == "Half Lead"
    assert sun_rows[0]["resource_name"] == "10K Lead"
    delete_assignment(sun, "imei-1180", root=tmp_path)
    assert list_assignments(sun, root=tmp_path) == []
    assert list_assignments(sat, root=tmp_path)[0]["resource_name"] == (
        "Half Lead"
    )


def test_assignment_requires_resource_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    sun = _import_two_days(tmp_path)[1]
    with pytest.raises(AssignmentError, match="resource_name"):
        upsert_assignment(
            sun,
            {"device_id": "imei-1", "resource_name": ""},
            root=tmp_path,
        )


def test_turnaround_layer_uses_plan_locations():
    pins = turnaround_pins(
        [
            {
                "loc_id": 9,
                "loc_label": "Nashwaaksis Turn-around",
                "lat": 45.99,
                "lon": -66.65,
            },
            {
                "loc_id": 2,
                "loc_label": "Queen",
                "lat": 45.96,
                "lon": -66.64,
            },
        ]
    )
    assert len(pins) == 1
    assert pins[0]["loc_id"] == 9
    assert is_turnaround({"loc_label": "Bridge turnaround"})
    assert is_turnaround(
        {"loc_label": "10K Turn (WSB)", "loc_type": "course"}
    )
    assert not is_turnaround(
        {"loc_label": "Water (Half Turn)", "loc_type": "water"}
    )


def test_overlay_joins_assignment_and_keeps_unnamed(monkeypatch):
    from app.core.execute.gps import overlay

    plan_id = str(uuid4())
    now = datetime(2026, 10, 25, 15, 30, tzinfo=timezone.utc)
    monkeypatch.setattr("app.core.execute.gps.using_postgres", lambda: True)
    monkeypatch.setattr(
        "app.core.execute.gps.active_plan_id", lambda: plan_id
    )
    monkeypatch.setattr(
        "app.core.execute.gps.latest_fixes",
        lambda pid: [
            {
                "device_id": "imei-4421",
                "lat": 45.96233,
                "lon": -66.65033,
                "fix_time": now,
                "received_at": now,
                "alarm": "",
                "speed": 0.0,
                "heading": 90.0,
            },
            {
                "device_id": "imei-9",
                "lat": 45.96,
                "lon": -66.64,
                "fix_time": now,
                "received_at": now,
                "alarm": "",
                "speed": 2.4,
                "heading": None,
            },
        ],
    )
    monkeypatch.setattr(
        "app.core.execute.gps.list_sos",
        lambda pid: [
            {
                "device_id": "imei-4421",
                "lat": 45.96233,
                "lon": -66.65033,
                "fix_time": now,
                "received_at": now,
                "alarm": "sos",
            }
        ],
    )
    monkeypatch.setattr(
        "app.core.execute.assignments.list_assignments",
        lambda pid, root=None: [
            {
                "device_id": "imei-4421",
                "resource_name": "SJA Medic 1",
                "person_name": "James Smith",
                "phone": "+1 (212) 555-1212",
                "agency": "SJA · First Aid",
            }
        ],
    )
    body = overlay(now=now)
    medic = [
        row
        for row in body["positions"]
        if row["device_id"] == "imei-4421"
    ][0]
    unnamed = [
        row for row in body["positions"] if row["device_id"] == "imei-9"
    ][0]
    assert medic["display_name"] == "SJA Medic 1"
    assert medic["phone"] == "+1 (212) 555-1212"
    assert medic["unnamed"] is False
    assert medic["status_label"] == "live"
    assert medic["sos"] is True
    assert unnamed["sos"] is False
    assert unnamed["unnamed"] is True
    assert unnamed["display_name"] == "imei-9"
    assert body["sos"][0]["attention"] == "new"
    assert body["sos"][0]["display_name"] == "SJA Medic 1"


def test_stale_status_label_is_last_seen(monkeypatch):
    from app.core.execute.gps import overlay

    plan_id = str(uuid4())
    now = datetime(2026, 10, 25, 15, 30, tzinfo=timezone.utc)
    old = now - timedelta(seconds=181)
    monkeypatch.setattr("app.core.execute.gps.using_postgres", lambda: True)
    monkeypatch.setattr(
        "app.core.execute.gps.active_plan_id", lambda: plan_id
    )
    monkeypatch.setattr(
        "app.core.execute.gps.latest_fixes",
        lambda pid: [
            {
                "device_id": "sweep",
                "lat": 45.96,
                "lon": -66.64,
                "fix_time": old,
                "received_at": old,
                "alarm": "",
                "speed": 0.0,
                "heading": None,
            }
        ],
    )
    monkeypatch.setattr("app.core.execute.gps.list_sos", lambda pid: [])
    monkeypatch.setattr(
        "app.core.execute.assignments.list_assignments",
        lambda pid, root=None: [],
    )
    row = overlay(now=now)["positions"][0]
    assert row["stale"] is True
    assert row["status_label"] == "last seen"


def test_board_counts_and_turnarounds(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    sun = _import_two_days(tmp_path)[1]
    activate_published_plan(sun, root=tmp_path)
    board = operations_board(sun, root=tmp_path, now_hhmmss="08:40:00")
    assert "counts" in board
    assert board["counts"]["closed"] + board["counts"]["reopen_next"] >= 1
    labels = [pin["label"] for pin in board["turnarounds"]]
    assert any("Turn-around" in label for label in labels)


def test_sos_and_gps_do_not_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    from app.core.execute import gps as gps_mod

    sun = _import_two_days(tmp_path)[1]
    activate_published_plan(sun, root=tmp_path)
    before = operations_board(sun, root=tmp_path, now_hhmmss="08:40:00")
    overlay = gps_mod.overlay
    assert overlay is not record_operations_reopen
    after = operations_board(sun, root=tmp_path, now_hhmmss="08:40:00")
    assert before["counts"] == after["counts"]


def test_mark_closed_undoes_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    sun = _import_two_days(tmp_path)[1]
    activate_published_plan(sun, root=tmp_path)
    opened = record_operations_reopen(2, root=tmp_path)
    opened_ids = [
        row["loc_id"] for row in opened["columns"]["reopened"]
    ]
    assert 2 in opened_ids
    closed = record_operations_close(2, root=tmp_path)
    closed_ids = [
        row["loc_id"] for row in closed["columns"]["reopened"]
    ]
    assert 2 not in closed_ids


def test_assignment_routes_on_execute_app(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    save_registry({"active_plan_id": None, "plans": {}}, root=tmp_path)
    sun = str(uuid4())
    import_published_plan(
        _package(
            calendar_date="2026-05-10",
            weekday_code="sun",
            plan_id=sun,
        ),
        root=tmp_path,
    )
    from app.execute_app import app as execute_app

    client = TestClient(execute_app)
    client.cookies.set("rf_auth_execute_name", "JT")
    listed = client.get(f"/api/execute/plans/{sun}/assignments")
    assert listed.status_code == 200
    saved = client.put(
        f"/api/execute/plans/{sun}/assignments",
        json={
            "device_id": "imei-4421",
            "resource_name": "SJA Medic 1",
            "person_name": "James Smith",
            "phone": "+1 (212) 555-1212",
            "agency": "SJA · First Aid",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["assignment"]["resource_name"] == "SJA Medic 1"
    again = client.get(f"/api/execute/plans/{sun}/assignments")
    payload = again.json()
    names = [row["resource_name"] for row in payload["assignments"]]
    assert "SJA Medic 1" in names
    assert payload["unassigned"] == []


def test_command_surface_copy_and_no_gun_override():
    root = Path(__file__).resolve().parents[2]
    html = (
        root / "frontend" / "templates" / "pages" / "execute.html"
    ).read_text(encoding="utf-8")
    js = (
        root / "frontend" / "static" / "js" / "execute_board.js"
    ).read_text(encoding="utf-8")
    assert "rf-execute-command" in html
    assert "rf-execute-guns" not in html
    assert "Use planned start times for this run" not in html
    assert "Use planned start times for this run" not in js
    assert "rf-ex-sos-icon" in js
    assert "last seen" in js
    assert "A clear-looking course is not clearance." not in js
    assert "Confirm reopen after sweep reports on TMR" not in js
    assert "data-close-location" in js
    assert "data-close-resource" in js
    assert "closeSelectedLocation" in js
    assert "closeSelectedResource" in js
    assert "rf-ex-tile-close" in js
    assert "Mark closed" in js
    assert "/api/execute/ops/close" in js
    assert "if (zoneFilter && group.getLayers().length)" in js
    assert "stripInMapView" in js
    assert "bindMapViewSync" in js
    assert 'map.on("moveend"' in js
    assert "None in the current map view." in js
    assert "Open cases" not in html
    assert "Open cases" not in js
    assert "/api/execute/incidents" not in js
    assert "data-rf-execute-view" not in html
    assert "Resources" in html
    assert "Devices" in html
    assert "Locations" in html
    assert "Device assignments" in html
    assert "Export CSV" not in html
    assert 'id="rf-execute-assign-open"' in html
    assert 'id="rf-execute-assign-unassigned"' in html
    assert 'id="rf-execute-assign-new"' in html
    assert "Existing assignments" in html
    assert "Unassigned devices" in html
    assert "Save assignment" in html
    assert "Remove assignment" in html
    assert "setAssignFormMode" in js
    assert "data-unassigned-device" in js
    assert "mergeUnassigned" in js
    css = (
        root / "frontend" / "static" / "css" / "execute_board.css"
    ).read_text(encoding="utf-8")
    assert "overscroll-behavior: contain" in css
    assert "rf-ex-section-title" in css
    assert "rf-ex-theme-light" in css
    assert "applyPanelTheme" in js
    assert 'key === "satellite"' in js
    assert "/api/execute/ops/session" in js
    assert "Acknowledge" in js
    assert "Resolved" not in js
    assert "tel:" in js
    assert "sms:" in js
    assert "rf-ex-phone-icon" in js
    assert 'id="rf-execute-layers-open"' in html
    assert 'id="rf-execute-layers-chip"' in html
    assert "On the map" in html
    assert "How to read marks" in html
    assert "updateLayersChip" in js
    assert "--rf-ex-chip" in css
    assert "dockMapChrome" in js
    assert "leaflet-bottom.leaflet-right" in css
