"""Issue #917: published day plan + Operations Map reopen parity."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.execute.board import assemble_board
from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    assert_date_matches_weekday,
    import_published_plan,
    map_snapshot,
    validate_manifest,
)
from app.core.execute.state import empty_state, record_reopen
from app.main import app


def _zip_from_files(files: dict) -> bytes:
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
    revision: int = 1,
    source_run_id: str = "",
    loc_end: str = "08:50:00",
) -> bytes:
    plan_id = plan_id or str(uuid4())
    locations = {
        "locations": [
            {
                "loc_id": 2,
                "loc_label": "Queen",
                "zone": 1,
                "lat": 45.96,
                "lon": -66.64,
                "loc_end": loc_end,
            }
        ],
        "resources_available": [],
    }
    course = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"events": ["elite"]},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-66.64, 45.96], [-66.63, 45.97]],
                },
            }
        ],
    }
    loc_bytes = json.dumps(locations).encode("utf-8")
    course_bytes = json.dumps(course).encode("utf-8")
    from app.core.execute.published_plan import sha256_bytes

    manifest = {
        "schema_version": 1,
        "published_plan_id": plan_id,
        "revision": revision,
        "published_at": "2026-10-22T12:00:00+00:00",
        "calendar_date": calendar_date,
        "weekday_code": weekday_code,
        "name": f"Test {calendar_date}",
        "timezone": "America/Halifax",
        "source_run_id": source_run_id,
        "races": [
            {
                "id": "elite",
                "name": "5K Elite",
                "start_time": 480,
                "course": "courses/elite.geojson",
            }
        ],
        "files": [
            {
                "path": "locations.json",
                "sha256": sha256_bytes(loc_bytes),
            },
            {
                "path": "courses/elite.geojson",
                "sha256": sha256_bytes(course_bytes),
            },
        ],
    }
    return _zip_from_files(
        {
            "manifest.json": manifest,
            "locations.json": loc_bytes,
            "courses/elite.geojson": course_bytes,
        }
    )


def test_calendar_date_required_and_uuid_identity():
    with pytest.raises(PublishedPlanError):
        validate_manifest(
            {
                "schema_version": 1,
                "published_plan_id": str(uuid4()),
                "revision": 1,
                "races": [{"id": "elite"}],
                "files": [{"path": "x", "sha256": "a"}],
            }
        )
    with pytest.raises(PublishedPlanError):
        validate_manifest(
            {
                "schema_version": 1,
                "published_plan_id": "sat",
                "revision": 1,
                "calendar_date": "2026-10-24",
                "races": [{"id": "elite"}],
                "files": [{"path": "x", "sha256": "a"}],
            }
        )


def test_date_must_match_weekday_slice():
    assert assert_date_matches_weekday("2026-10-24", "sat") == "sat"
    with pytest.raises(PublishedPlanError, match="not sat"):
        assert_date_matches_weekday("2026-10-25", "sat")


def test_import_is_idempotent(tmp_path: Path):
    archive = _package(calendar_date="2026-10-24", weekday_code="sat")
    first = import_published_plan(archive, root=tmp_path)
    second = import_published_plan(archive, root=tmp_path)
    assert first["imported"] is True
    assert second["idempotent"] is True
    assert first["published_plan_id"] == second["published_plan_id"]
    plans = list((tmp_path / "execute" / "published_plans").iterdir())
    assert len([p for p in plans if p.is_dir()]) == 1


def test_second_calendar_date_is_isolated(tmp_path: Path):
    sat = _package(calendar_date="2026-10-24", weekday_code="sat")
    sun = _package(calendar_date="2026-10-25", weekday_code="sun")
    sat_id = import_published_plan(sat, root=tmp_path)["published_plan_id"]
    sun_id = import_published_plan(sun, root=tmp_path)["published_plan_id"]
    assert sat_id != sun_id
    activate_published_plan(sat_id, root=tmp_path)
    snap = map_snapshot(root=tmp_path)
    assert snap["calendar_date"] == "2026-10-24"
    assert snap["published_plan_id"] == sat_id
    sun_dir = tmp_path / "execute" / "published_plans" / sun_id
    assert sun_dir.is_dir()


def test_map_empty_without_activate(tmp_path: Path):
    snap = map_snapshot(root=tmp_path)
    assert snap["empty"] is True
    assert snap["locations"] == []


def test_reopen_status_matches_board_not_planned_time(tmp_path: Path):
    archive = _package(
        calendar_date="2026-10-24",
        weekday_code="sat",
        loc_end="06:00:00",
    )
    plan_id = import_published_plan(archive, root=tmp_path)[
        "published_plan_id"
    ]
    activate_published_plan(plan_id, root=tmp_path)
    locations = [
        {
            "loc_id": 2,
            "loc_label": "Queen",
            "zone": 1,
            "lat": 45.96,
            "lon": -66.64,
            "loc_end": "06:00:00",
        }
    ]
    state = empty_state(run_id="unused", day="sat")
    overdue = map_snapshot(
        root=tmp_path,
        now_hhmmss="12:00:00",
        state=state,
    )
    assert overdue["locations"][0]["status"] != "reopened"
    board_before = assemble_board(
        locations=locations,
        state=state,
        resources_available=[],
        run_id="unused",
        day="sat",
        now_hhmmss="12:00:00",
    )
    before_status = (
        (board_before["columns"]["reopen_next"] or board_before["columns"]["closed"])[0][
            "status"
        ]
    )
    assert overdue["locations"][0]["status"] == before_status
    record_reopen(state, loc_id=2, linked_loc_ids=[])
    human = map_snapshot(
        root=tmp_path,
        now_hhmmss="12:00:00",
        state=state,
    )
    assert human["locations"][0]["status"] == "reopened"


def test_map_and_publish_routes_exist():
    client = TestClient(app)
    response = client.get("/execute/map", follow_redirects=False)
    assert response.status_code in (200, 303)
    listed = client.get("/api/execute/published-plans")
    assert listed.status_code == 200
    empty = client.get("/api/execute/map")
    assert empty.status_code == 200
    assert empty.json().get("empty") is True
