"""Issue #920: race-day Execute Plans, Operations, and active-day context."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.execute.published_plan import (
    PublishedPlanError,
    activate_published_plan,
    active_day_context,
    archive_published_plan,
    deactivate_published_plan,
    import_published_plan,
    listed_plans,
    operational_state_path,
    operations_board,
    record_operations_reopen,
    restore_published_plan,
)
from app.execute_app import app


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
    source_run_id: str = "srcRun920",
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
        "plan_id": plan_id,
        "revision": 1,
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


def test_import_does_not_activate(tmp_path: Path):
    archive = _package(calendar_date="2026-10-24", weekday_code="sat")
    result = import_published_plan(archive, root=tmp_path)
    assert result["activated"] is False
    listing = listed_plans(root=tmp_path)
    assert listing["active_plan_id"] is None
    assert listing["plans"][0]["status"] == "inactive"
    board = operations_board(root=tmp_path)
    assert board["empty"] is True


def test_archive_restore_and_activate_rules(tmp_path: Path):
    archive = _package(calendar_date="2026-10-25", weekday_code="sun")
    plan_id = import_published_plan(archive, root=tmp_path)[
        "plan_id"
    ]
    activate_published_plan(plan_id, root=tmp_path)
    row = archive_published_plan(plan_id, root=tmp_path)
    assert row["archived"] is True
    listing = listed_plans(root=tmp_path)
    assert listing["active_plan_id"] is None
    assert listing["plans"][0]["status"] == "archived"
    with pytest.raises(PublishedPlanError, match="Restore"):
        activate_published_plan(plan_id, root=tmp_path)
    restored = restore_published_plan(plan_id, root=tmp_path)
    assert restored["archived"] is False
    listing = listed_plans(root=tmp_path)
    assert listing["active_plan_id"] is None
    assert listing["plans"][0]["status"] == "inactive"


def test_reopen_writes_execute_owned_state(tmp_path: Path):
    archive = _package(
        calendar_date="2026-10-24",
        weekday_code="sat",
        source_run_id="srcRun920",
    )
    plan_id = import_published_plan(archive, root=tmp_path)[
        "plan_id"
    ]
    activate_published_plan(plan_id, root=tmp_path)
    board = record_operations_reopen(2, root=tmp_path)
    reopened = board["columns"]["reopened"]
    assert reopened and int(reopened[0]["loc_id"]) == 2
    state_path = operational_state_path(plan_id, root=tmp_path)
    assert state_path.is_file()
    leaked = tmp_path / "srcRun920" / "sat" / "execution" / "state.json"
    assert not leaked.exists()


def test_switching_plans_isolates_reopen_state(tmp_path: Path):
    sat = _package(calendar_date="2026-10-24", weekday_code="sat")
    sun = _package(calendar_date="2026-10-25", weekday_code="sun")
    sat_id = import_published_plan(sat, root=tmp_path)["plan_id"]
    sun_id = import_published_plan(sun, root=tmp_path)["plan_id"]
    activate_published_plan(sat_id, root=tmp_path)
    record_operations_reopen(2, root=tmp_path)
    activate_published_plan(sun_id, root=tmp_path)
    sun_board = operations_board(root=tmp_path)
    assert sun_board["plan_id"] == sun_id
    assert sun_board["columns"]["reopened"] == []
    activate_published_plan(sat_id, root=tmp_path)
    sat_board = operations_board(root=tmp_path)
    assert sat_board["columns"]["reopened"]
    assert int(sat_board["columns"]["reopened"][0]["loc_id"]) == 2


def test_active_day_context_uses_source_run(tmp_path: Path):
    archive = _package(
        calendar_date="2026-10-25",
        weekday_code="sun",
        source_run_id="srcSun920",
    )
    plan_id = import_published_plan(archive, root=tmp_path)[
        "plan_id"
    ]
    assert active_day_context(root=tmp_path)["active"] is False
    activate_published_plan(plan_id, root=tmp_path)
    ctx = active_day_context(root=tmp_path)
    assert ctx["active"] is True
    assert ctx["plan_id"] == plan_id
    assert ctx["source_run_id"] == "srcSun920"
    assert "run_id" not in ctx
    assert ctx["weekday_code"] == "sun"
    deactivate_published_plan(root=tmp_path)
    assert active_day_context(root=tmp_path)["active"] is False


def test_ops_http_uses_active_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    client = TestClient(app)
    empty = client.get("/api/execute/ops/board")
    assert empty.status_code == 200
    assert empty.json()["empty"] is True
    archive = _package(calendar_date="2026-10-24", weekday_code="sat")
    imported = client.post(
        "/api/execute/plans/import",
        files={"package": ("sat.zip", archive, "application/zip")},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["activated"] is False
    plan_id = body["plan_id"]
    listed = client.get("/api/execute/plans")
    assert listed.json()["active_plan_id"] is None
    client.post(
        "/api/execute/plans/activate",
        json={"plan_id": plan_id},
    )
    board = client.get("/api/execute/ops/board")
    assert board.status_code == 200
    assert board.json()["empty"] is False
    ctx = client.get("/api/execute/active-context")
    assert ctx.json()["active"] is True
    page = client.get("/execute/plans", follow_redirects=False)
    assert page.status_code in (200, 302, 303)


def test_execute_nav_and_plans_copy():
    root = Path(__file__).resolve().parents[2]
    base = (root / "frontend" / "templates" / "base.html").read_text(
        encoding="utf-8"
    )
    plans_html = (
        root / "frontend" / "templates" / "pages" / "execute_plans.html"
    ).read_text(encoding="utf-8")
    plans_js = (
        root / "frontend" / "static" / "js" / "execute_plans.js"
    ).read_text(encoding="utf-8")
    ops_js = (
        root / "frontend" / "static" / "js" / "execute_board.js"
    ).read_text(encoding="utf-8")
    assert 'data-rf-execute-view="plans">Plans</a>' in base
    assert 'data-rf-execute-view="operations">Operations</a>' in base
    assert "Import does not activate" in plans_html
    assert "table_actions.js" in plans_html
    assert "Activate this Day Plan" in plans_js
    assert 'createIconButton(kind, title, function (ev)' in plans_js
    assert '"activate"' in plans_js
    assert '"archive"' in plans_js
    assert "Records are kept" in plans_js
    assert "/api/execute/ops/board" in ops_js
    assert "/api/execute/ops/reopen" in ops_js
    participants = (
        root / "frontend" / "templates" / "pages" / "execute_participants.html"
    ).read_text(encoding="utf-8")
    incidents = (
        root / "frontend" / "templates" / "pages" / "execute_incidents.html"
    ).read_text(encoding="utf-8")
    assert "No Day Plan is active" in participants
    assert "No Day Plan is active" in incidents
    assert "execute_context.js" in participants
    assert "execute_context.js" in incidents
