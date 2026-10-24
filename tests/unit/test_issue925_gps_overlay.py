"""Issue #925: GPS overlay never authorizes reopen; SOS survives later fixes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.execute.gps import (
    GpsError,
    ingest_osmand,
    is_sos,
    overlay,
    parse_osmand,
    require_ingest_token,
)


def test_device_id_is_not_the_ingest_token(monkeypatch):
    monkeypatch.setenv("EXECUTE_GPS_TOKEN", "server-token")
    require_ingest_token("server-token")
    with pytest.raises(GpsError, match="Unauthorized"):
        require_ingest_token("phone-device-1")


def test_traccar_v9_json_body_merges_osmand_fields():
    from app.core.execute.gps import merge_client_payload, parse_osmand

    merged = merge_client_payload(
        {},
        {
            "device_id": "phone-1",
            "location": {
                "timestamp": "2026-10-24T16:00:00.000Z",
                "coords": {
                    "latitude": 45.96,
                    "longitude": -66.64,
                    "accuracy": 8,
                    "speed": 0.2,
                    "heading": 70,
                },
                "battery": {"level": 0.8, "is_charging": False},
                "extras": {"alarm": "sos"},
                "_": "&id=phone-1&lat=45.96&lon=-66.64&timestamp=2026-10-24T16:00:00.000Z&",
            },
        },
    )
    parsed = parse_osmand(merged)
    assert parsed["device_id"] == "phone-1"
    assert parsed["lat"] == 45.96
    assert parsed["alarm"] == "sos"
    assert parsed["battery"] == 80.0


def test_parse_osmand_requires_id_and_fix():
    parsed = parse_osmand(
        {"id": "unit-1", "lat": "45.96", "lon": "-66.64", "timestamp": "1"}
    )
    assert parsed["device_id"] == "unit-1"
    assert parsed["lat"] == 45.96
    with pytest.raises(GpsError, match="lat and lon"):
        parse_osmand({"id": "unit-1"})


def test_sos_alarm_is_detected():
    assert is_sos("sos") is True
    assert is_sos("SOS") is True
    assert is_sos("") is False


def test_ingest_requires_active_plan_and_postgres(monkeypatch):
    monkeypatch.setenv("EXECUTE_GPS_TOKEN", "server-token")
    monkeypatch.setattr("app.core.execute.gps.using_postgres", lambda: False)
    with pytest.raises(GpsError, match="PostgreSQL"):
        ingest_osmand(
            {"id": "u1", "lat": "45.9", "lon": "-66.6"},
            token="server-token",
        )
    monkeypatch.setattr("app.core.execute.gps.using_postgres", lambda: True)
    monkeypatch.setattr("app.core.execute.gps.active_plan_id", lambda: None)
    with pytest.raises(GpsError, match="Activate a plan"):
        ingest_osmand(
            {"id": "u1", "lat": "45.9", "lon": "-66.6"},
            token="server-token",
        )


def test_sos_survives_later_position(monkeypatch):
    plan_id = str(uuid4())
    fixes = []
    sos = []
    monkeypatch.setenv("EXECUTE_GPS_TOKEN", "server-token")
    monkeypatch.setattr("app.core.execute.gps.using_postgres", lambda: True)
    monkeypatch.setattr(
        "app.core.execute.gps.active_plan_id", lambda: plan_id
    )
    monkeypatch.setattr(
        "app.core.execute.gps.insert_fix",
        lambda pid, fix, received: fixes.append((pid, dict(fix))),
    )
    monkeypatch.setattr(
        "app.core.execute.gps.insert_sos",
        lambda pid, fix, received: sos.append((pid, dict(fix))),
    )
    ingest_osmand(
        {"id": "u1", "lat": "45.9", "lon": "-66.6", "alarm": "sos"},
        token="server-token",
    )
    ingest_osmand(
        {"id": "u1", "lat": "45.91", "lon": "-66.61"},
        token="server-token",
    )
    assert len(fixes) == 2
    assert len(sos) == 1
    assert sos[0][1]["lat"] == 45.9


def test_stale_is_not_a_confirmed_stop(monkeypatch):
    plan_id = str(uuid4())
    now = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(seconds=181)
    monkeypatch.setattr("app.core.execute.gps.using_postgres", lambda: True)
    monkeypatch.setattr(
        "app.core.execute.gps.active_plan_id", lambda: plan_id
    )
    monkeypatch.setattr(
        "app.core.execute.gps.latest_fixes",
        lambda pid: [
            {
                "device_id": "u1",
                "lat": 45.9,
                "lon": -66.6,
                "fix_time": old,
                "received_at": old,
                "alarm": "",
            }
        ],
    )
    monkeypatch.setattr("app.core.execute.gps.list_sos", lambda pid: [])
    body = overlay(now=now)
    assert body["positions"][0]["stale"] is True
    assert body["positions"][0]["unknown"] is False


def test_gps_never_imports_reopen():
    from app.core.execute import gps as gps_mod
    from app.core.execute import published_plan

    assert not hasattr(gps_mod, "record_operations_reopen")
    assert "record_reopen" not in gps_mod.__dict__
    assert published_plan.record_operations_reopen is not gps_mod.overlay


def test_execute_app_has_gps_combined_does_not():
    from app.execute_app import app as execute_app
    from app.main import app as combined

    exec_client = TestClient(execute_app)
    combined_client = TestClient(combined)
    assert exec_client.get("/api/execute/gps/overlay").status_code == 200
    assert combined_client.get("/api/execute/gps/osmand").status_code == 404
    assert combined_client.get("/api/execute/gps/overlay").status_code == 404


def test_osmand_without_token_is_rejected(monkeypatch):
    monkeypatch.setenv("EXECUTE_GPS_TOKEN", "server-token")
    from app.execute_app import app as execute_app

    client = TestClient(execute_app)
    resp = client.get(
        "/api/execute/gps/osmand",
        params={"id": "u1", "lat": "45.9", "lon": "-66.6"},
    )
    assert resp.status_code == 401


def test_osmand_accepts_classic_get_and_json_post(monkeypatch):
    monkeypatch.setenv("EXECUTE_GPS_TOKEN", "server-token")
    ingested = []

    def _ingest(params, token=""):
        ingested.append((dict(params), token))
        return {"ok": True}

    monkeypatch.setattr("app.routes.api_execute_gps.ingest_osmand", _ingest)
    from app.execute_app import app as execute_app

    client = TestClient(execute_app)
    classic = client.get(
        "/api/execute/gps/osmand",
        params={
            "token": "server-token",
            "id": "phone-1",
            "lat": "45.96",
            "lon": "-66.64",
            "timestamp": "1",
            "speed": "2",
            "bearing": "90",
            "altitude": "12",
            "accuracy": "8",
            "batt": "80",
            "charge": "true",
        },
    )
    assert classic.status_code == 200
    assert classic.text == "OK"
    form = client.post(
        "/api/execute/gps/osmand?token=server-token",
        data={"id": "phone-1", "lat": "45.97", "lon": "-66.65"},
    )
    assert form.status_code == 200
    json_body = client.post(
        "/api/execute/gps/osmand?token=server-token",
        json={
            "device_id": "phone-1",
            "location": {
                "timestamp": "2026-10-24T16:00:00.000Z",
                "coords": {"latitude": 45.98, "longitude": -66.66},
                "extras": {"alarm": "sos"},
            },
        },
    )
    assert json_body.status_code == 200
    assert len(ingested) == 3
    assert ingested[0][0]["id"] == "phone-1"
    assert ingested[1][0]["lat"] == "45.97"
    assert ingested[2][0]["alarm"] == "sos"
