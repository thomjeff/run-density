"""Issue #933: Execute Operations, Participants, and Incidents polish."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.execute.incidents import apply_fields, empty_incident
from app.core.execute.layers import is_water_or_service
from app.core.execute.published_plan import (
    activate_published_plan,
    import_published_plan,
    sha256_bytes,
)
from app.execute_app import app

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "issue911_participant_list.csv"


def _package() -> bytes:
    plan_id = str(uuid4())
    locations = {
        "locations": [{"loc_id": 16, "loc_label": "10K Water Stop", "zone": "Z3"}],
        "resources_available": [],
    }
    course = {"type": "FeatureCollection", "features": []}
    loc_bytes = json.dumps(locations).encode("utf-8")
    course_bytes = json.dumps(course).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "plan_id": plan_id,
        "revision": 1,
        "published_at": "2026-10-23T12:00:00+00:00",
        "calendar_date": "2026-10-25",
        "weekday_code": "sun",
        "name": "Test Sunday",
        "timezone": "America/Halifax",
        "source_run_id": "should-not-be-operator-key",
        "races": [
            {"id": "elite", "name": "5K Elite", "course": "courses/elite.geojson"}
        ],
        "files": [
            {"path": "locations.json", "sha256": sha256_bytes(loc_bytes)},
            {
                "path": "courses/elite.geojson",
                "sha256": sha256_bytes(course_bytes),
            },
        ],
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("locations.json", loc_bytes)
        zf.writestr("courses/elite.geojson", course_bytes)
    return buffer.getvalue()


def test_water_or_service_includes_aid_and_extract():
    assert is_water_or_service({"loc_type": "water"})
    assert is_water_or_service({"loc_type": "aid"})
    assert is_water_or_service({"loc_type": "extract"})
    assert is_water_or_service({"loc_type": "official"})
    assert not is_water_or_service({"loc_type": "course"})
    assert not is_water_or_service({"loc_type": "traffic"})


def test_operations_helper_text_removed_and_rows_are_two_line():
    js = (REPO / "frontend" / "static" / "js" / "execute_board.js").read_text(
        encoding="utf-8"
    )
    html = (REPO / "frontend" / "templates" / "pages" / "execute.html").read_text(
        encoding="utf-8"
    )
    assert "Select Closed, Reopen next, or Reopened." not in js
    assert "rf-ex-strip-sub" in js
    assert "water: true" in js
    assert 'type === "extract"' in js
    assert 'data-layer="water" checked> Water</label>' in html
    dockerfile = (REPO / "Dockerfile.execute").read_text(encoding="utf-8")
    assert "execute_help.html" in dockerfile


def test_help_is_execute_only_before_logout():
    base = (REPO / "frontend" / "templates" / "base.html").read_text(encoding="utf-8")
    help_at = base.index('href="/execute/help">Help</a>')
    logout_at = base.index('href="/logout">Logout</a>')
    assert help_at < logout_at
    assert "execute_runtime|default(false)" in base[help_at - 120 : help_at]
    page = (REPO / "frontend" / "templates" / "pages" / "execute_help.html").read_text(
        encoding="utf-8"
    )
    assert "Cases" in page
    assert "Aid, Extract, Official, Traffic, Water" in page
    assert "Off-course traffic shows as a ring" in page


def test_participants_sample_sentence_uses_issue_attachment():
    html = (
        REPO / "frontend" / "templates" / "pages" / "execute_participants.html"
    ).read_text(encoding="utf-8")
    assert (
        "List of all registered participants for the events associated with this"
        in html
    )
    assert "github.com/user-attachments/files/34037192" in html
    assert ">sample</a>" in html


def test_incidents_identity_and_form_copy():
    js = (REPO / "frontend" / "static" / "js" / "execute_incidents.js").read_text(
        encoding="utf-8"
    )
    assert "Emergency Contact" in js
    assert "medical_avoid" in js
    assert "Call 911" in js
    assert "Mark Urgent" in js
    assert "hs-911-toggle" in js
    assert "toggleIncidentFlag" in js
    assert "Record care agency" not in js
    assert "called911Control" not in js
    assert "rf-hs-problem-block" in js
    render = js[js.index("function renderCase") : js.index("function formPayload")]
    assert render.index("locationFieldHtml") < render.index("Reported problem")
    assert js.index("function locationFieldHtml") < js.index("function renderCase")
    assert 'id="hs-loc"' in js
    assert render.index("Reported problem") < render.index('id="hs-desc"')
    assert render.index('id="hs-desc"') < render.index("Category")
    assert render.index("Category") < render.index("Care provided")
    assert 'id="hs-care-options"' in js
    assert 'id="hs-outcome"' in js
    assert 'id === "hs-assigned"' in js
    assert "Add update" in js
    assert "first_aid" not in js


def test_urgent_and_911_persist(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    plan_id = import_published_plan(_package(), root=tmp_path)["plan_id"]
    activate_published_plan(plan_id, root=tmp_path)
    client = TestClient(app)
    imported = client.post(
        "/api/execute/participants/import",
        files={"file": ("roster.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert imported.status_code == 200, imported.text
    created = client.post(
        "/api/execute/incidents",
        json={"reg_id": "1"},
    )
    assert created.status_code == 200, created.text
    body = created.json()["incident"]
    assert body["emerg_name"] == "Alain Browne"
    assert body["emerg_phone"] == "15065551212"
    assert body["medical_conditions"]
    iid = body["incident_id"]
    updated = client.put(
        f"/api/execute/incidents/{iid}",
        json={"urgent": "yes", "called_911": "yes"},
    )
    assert updated.status_code == 200, updated.text
    row = updated.json()["incident"]
    assert row["urgent"] == "yes"
    assert row["called_911"] == "yes"
    notes = " ".join(note["text"] for note in row["notes"])
    assert "911 called." in notes
    assert "Marked urgent." in notes


def test_apply_fields_clears_urgent():
    incident = empty_incident(reg_id="1")
    apply_fields(incident, {"urgent": "yes"})
    assert incident["urgent"] == "yes"
    apply_fields(incident, {"urgent": "no"})
    assert incident["urgent"] == "no"
    notes = " ".join(note["text"] for note in incident["notes"])
    assert "Urgent cleared." in notes


def test_apply_fields_clears_911_and_logs_location():
    incident = empty_incident(reg_id="1")
    apply_fields(incident, {"called_911": "yes"})
    assert incident["called_911"] == "yes"
    apply_fields(incident, {"called_911": "no"})
    assert incident["called_911"] == "no"
    apply_fields(incident, {"location_text": "Trail at Neill · Zone 4"})
    apply_fields(incident, {"description": "Fell near the water stop."})
    apply_fields(incident, {"description": "Fell near the water stop; ice applied."})
    texts = [note["text"] for note in incident["notes"]]
    assert "911 called." in texts
    assert "911 cleared." in texts
    assert "Location: Trail at Neill · Zone 4." in texts
    assert "Fell near the water stop." in texts
    assert "Fell near the water stop; ice applied." in texts
