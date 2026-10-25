"""Issue #928 Milestone 2: session name, SOS attention, action audit."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.execute.attention import (
    acknowledge_sos,
    attention_map,
    clear_sos_attention,
    latch_new_sos,
    list_audit,
    record_audit,
)
from app.core.execute.operator import OPERATOR_COOKIE, clean_operator
from app.core.execute.published_plan import (
    import_published_plan,
    save_registry,
)
from tests.unit.test_issue928_execute_operations import _package


def _file_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.core.execute.db.using_postgres",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    save_registry({"active_plan_id": None, "plans": {}}, root=tmp_path)


def test_clean_operator_trims_and_limits():
    assert clean_operator("  JT  ") == "JT"
    assert len(clean_operator("x" * 80)) == 40


def test_acknowledge_and_clear_keep_who_and_history(
    tmp_path, monkeypatch
):
    _file_store(tmp_path, monkeypatch)
    sun = str(uuid4())
    import_published_plan(
        _package(
            calendar_date="2026-05-10",
            weekday_code="sun",
            plan_id=sun,
        ),
        root=tmp_path,
    )
    latch_new_sos(sun, "imei-4421", root=tmp_path)
    acked = acknowledge_sos(sun, "imei-4421", "JT", root=tmp_path)
    assert acked["status"] == "acknowledged"
    assert acked["acknowledged_by"] == "JT"
    assert acked["acknowledged_at"]
    cleared = clear_sos_attention(sun, "imei-4421", "JT", root=tmp_path)
    assert cleared["status"] == "cleared"
    assert cleared["cleared_by"] == "JT"
    rows = attention_map(sun, root=tmp_path)
    assert rows["imei-4421"]["status"] == "cleared"
    audit = list_audit(sun, root=tmp_path)
    actions = [row["action"] for row in audit]
    assert "sos_acknowledge" in actions
    assert "sos_clear" in actions
    assert all(row["actor"] == "JT" for row in audit)


def test_clear_does_not_use_resolved(tmp_path, monkeypatch):
    _file_store(tmp_path, monkeypatch)
    sun = str(uuid4())
    import_published_plan(
        _package(
            calendar_date="2026-05-10",
            weekday_code="sun",
            plan_id=sun,
        ),
        root=tmp_path,
    )
    latch_new_sos(sun, "imei-4421", root=tmp_path)
    clear_sos_attention(sun, "imei-4421", "JT", root=tmp_path)
    row = attention_map(sun, root=tmp_path)["imei-4421"]
    assert row["status"] == "cleared"
    assert "resolved" not in row["status"]


def test_audit_records_reopen_and_assignment(tmp_path, monkeypatch):
    _file_store(tmp_path, monkeypatch)
    sun = str(uuid4())
    import_published_plan(
        _package(
            calendar_date="2026-05-10",
            weekday_code="sun",
            plan_id=sun,
        ),
        root=tmp_path,
    )
    record_audit(sun, action="reopen", actor="JT", loc_id=2, root=tmp_path)
    record_audit(
        sun,
        action="assignment_upsert",
        actor="JT",
        device_id="imei-1180",
        detail={"resource_name": "Sweep Bike"},
        root=tmp_path,
    )
    rows = list_audit(sun, root=tmp_path)
    assert rows[0]["action"] == "assignment_upsert"
    assert rows[1]["action"] == "reopen"
    assert rows[1]["loc_id"] == 2


def test_assignment_write_requires_session_name(tmp_path, monkeypatch):
    _file_store(tmp_path, monkeypatch)
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
    missing = client.put(
        f"/api/execute/plans/{sun}/assignments",
        json={"device_id": "imei-1", "resource_name": "Lead"},
    )
    assert missing.status_code == 400
    client.cookies.set(OPERATOR_COOKIE, "JT")
    saved = client.put(
        f"/api/execute/plans/{sun}/assignments",
        json={"device_id": "imei-1", "resource_name": "Lead"},
    )
    assert saved.status_code == 200
    audit = list_audit(sun, root=tmp_path)
    assert audit[0]["action"] == "assignment_upsert"
    assert audit[0]["actor"] == "JT"


def test_session_cookie_round_trip():
    from app.execute_app import app as execute_app

    client = TestClient(execute_app)
    saved = client.put(
        "/api/execute/ops/session",
        json={"operator": "  JT  "},
    )
    assert saved.status_code == 200
    assert saved.json()["operator"] == "JT"
    again = client.get("/api/execute/ops/session")
    assert again.json()["operator"] == "JT"


def test_overlay_omits_cleared_sos(monkeypatch):
    from datetime import datetime, timezone

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
                "lat": 45.96,
                "lon": -66.64,
                "fix_time": now,
                "received_at": now,
                "alarm": "",
                "speed": 0.0,
                "heading": None,
            }
        ],
    )
    monkeypatch.setattr(
        "app.core.execute.gps.list_sos",
        lambda pid: [
            {
                "device_id": "imei-4421",
                "lat": 45.96,
                "lon": -66.64,
                "fix_time": now,
                "received_at": now,
                "alarm": "sos",
            }
        ],
    )
    monkeypatch.setattr(
        "app.core.execute.assignments.list_assignments",
        lambda pid, root=None: [],
    )
    monkeypatch.setattr(
        "app.core.execute.attention.attention_map",
        lambda pid, root=None: {
            "imei-4421": {"status": "cleared", "cleared_by": "JT"}
        },
    )
    body = overlay(now=now)
    assert body["sos"] == []
    assert body["positions"][0]["sos"] is False


def test_operations_copy_has_acknowledge_and_no_resolved():
    root = Path(__file__).resolve().parents[2]
    html = (
        root / "frontend" / "templates" / "pages" / "execute.html"
    ).read_text(encoding="utf-8")
    js = (
        root / "frontend" / "static" / "js" / "execute_board.js"
    ).read_text(encoding="utf-8")
    password = (
        root / "frontend" / "templates" / "pages" / "password.html"
    ).read_text(encoding="utf-8")
    assert 'id="rf-execute-operator"' in html
    assert 'id="rf-execute-audit"' in html
    assert html.index('id="rf-execute-audit"') < html.index(
        'class="rf-ex-attention-rail"'
    )
    assert "Acknowledge" in js
    assert "Acknowledged" in js
    assert "data-sos-clear" in js
    assert "/api/execute/ops/sos/ack" in js
    assert "/api/execute/ops/sos/clear" in js
    assert "Resolved" not in js
    assert "Display name or initials" in password
