"""Issue #924: drop leftover Execute run_id and analysis-board coupling."""

from __future__ import annotations

import inspect
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.execute import incidents as hs_incidents
from app.core.execute.db import database_url, using_postgres
from app.core.execute.session_cookies import (
    COMBINED_AUTH,
    EXECUTE_AUTH,
    incoming_cookie_header,
    outgoing_set_cookie,
)
from app.core.execute.store_identity import with_plan_id
from app.main import app as combined_app


def _route_paths(routes) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
        nested = getattr(route, "routes", None)
        if nested:
            paths.update(_route_paths(nested))
        original = getattr(route, "original_router", None)
        if original is not None and hasattr(original, "routes"):
            paths.update(_route_paths(original.routes))
    return paths


def test_leftover_analysis_board_routes_are_unmounted():
    from app.execute_app import app as execute_app

    leftover = {
        "/api/execute/board",
        "/api/execute/clock",
        "/api/execute/state",
        "/api/execute/reopen",
        "/api/execute/reopen.csv",
    }
    combined = _route_paths(combined_app.routes)
    execute = _route_paths(execute_app.routes)
    assert leftover.isdisjoint(combined)
    assert leftover.isdisjoint(execute)
    assert "/api/execute/ops/board" in combined
    assert "/api/execute/ops/board" in execute
    client = TestClient(combined_app)
    assert client.get("/api/execute/board").status_code == 404
    assert client.get("/api/execute/ops/board").status_code in (200, 400)


def test_gps_ingest_and_overlay_remain_on_execute():
    from app.execute_app import app as execute_app

    paths = _route_paths(execute_app.routes)
    assert "/api/execute/gps/osmand" in paths
    assert "/api/execute/gps/overlay" in paths
    client = TestClient(execute_app)
    overlay = client.get("/api/execute/gps/overlay")
    assert overlay.status_code == 200
    body = overlay.json()
    assert body.get("ok") is True
    assert "positions" in body
    assert "sos" in body
    assert TestClient(combined_app).get(
        "/api/execute/gps/overlay"
    ).status_code == 404


def test_participants_and_incidents_drop_unused_query_params():
    from app.routes import api_execute_runtime as runtime

    for name in (
        "get_execute_participants",
        "post_execute_participants_import",
        "get_execute_incidents",
        "get_execute_incident_locations",
    ):
        params = inspect.signature(getattr(runtime, name)).parameters
        assert "run_id" not in params
        assert "day" not in params


def test_stores_write_plan_id_and_read_leftover_run_id():
    leftover = {
        "schema_version": 1,
        "run_id": "leftover-plan",
        "day": "sun",
        "rows": [],
    }
    normalized = with_plan_id(leftover, "active-plan")
    assert normalized["plan_id"] == "leftover-plan"
    assert "run_id" not in normalized
    fresh = with_plan_id({"day": "sun", "rows": []}, "active-plan")
    assert fresh["plan_id"] == "active-plan"
    assert "run_id" not in fresh


def test_location_catalog_is_unused_by_execute_routes():
    from app.routes.api_execute_runtime import get_execute_incident_locations

    src = inspect.getsource(get_execute_incident_locations)
    assert "location_catalog_from_rows" in src
    assert "hs_incidents.location_catalog" not in src
    assert hasattr(hs_incidents, "location_catalog")


def test_postgres_ignores_leftover_database_url(monkeypatch):
    monkeypatch.delenv("EXECUTE_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://other/db")
    assert database_url() == ""
    assert using_postgres() is False
    monkeypatch.setenv("EXECUTE_DATABASE_URL", "postgresql://execute/db")
    assert database_url() == "postgresql://execute/db"
    assert using_postgres() is True


def test_execute_session_cookies_are_isolated(monkeypatch):
    leftover = b"rf_auth=authenticated; rf_auth_ts=1"
    assert incoming_cookie_header(leftover) == b""
    execute = b"rf_auth_execute=authenticated; rf_auth_execute_ts=1"
    assert incoming_cookie_header(execute) == leftover
    assert outgoing_set_cookie(b"rf_auth=authenticated; Path=/") == (
        b"rf_auth_execute=authenticated; Path=/"
    )
    assert outgoing_set_cookie(b"rf_auth_ts=1; Path=/") == (
        b"rf_auth_execute_ts=1; Path=/"
    )

    from app.execute_app import app as execute_app

    monkeypatch.setenv("DASHBOARD_PASSWORD", "")
    client = TestClient(execute_app)
    login = client.post(
        "/login", data={"password": "x"}, follow_redirects=False
    )
    assert login.status_code == 303
    assert EXECUTE_AUTH in login.cookies
    assert COMBINED_AUTH not in login.cookies
    leftover_client = TestClient(execute_app)
    leftover_client.cookies.set(COMBINED_AUTH, "authenticated")
    leftover_client.cookies.set("rf_auth_ts", str(time.time()))
    check = leftover_client.get("/api/auth/check")
    assert check.json()["authenticated"] is False


def test_operator_js_does_not_call_leftover_board():
    root = Path(__file__).resolve().parents[2] / "frontend" / "static" / "js"
    text = ""
    for name in (
        "execute_board.js",
        "execute_plans.js",
        "execute_participants.js",
        "execute_incidents.js",
        "execute_map.js",
        "execute_context.js",
    ):
        text += (root / name).read_text(encoding="utf-8")
    assert "/api/execute/ops/board" in text
    stripped = (
        text.replace("/api/execute/ops/board", "")
        .replace("/api/execute/ops/clock", "")
        .replace("/api/execute/ops/reopen.csv", "")
        .replace("/api/execute/ops/reopen", "")
        .replace("/api/execute/ops/close", "")
    )
    assert "/api/execute/board" not in stripped
    assert "/api/execute/clock" not in stripped
    assert "/api/execute/state" not in stripped
    assert "/api/execute/reopen" not in stripped
