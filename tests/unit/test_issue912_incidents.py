"""Issue #912: Execute Incidents two-pane case management."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.execute.incidents import (
    SCHEMA_VERSION,
    catalog,
    location_catalog,
    normalize_incident,
    transfer_care,
    type_care_change_note,
)
from app.main import app
from app.storage import Storage

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "issue911_participant_list.csv"


def _patch_run(monkeypatch, tmp_path: Path, run_id: str) -> Path:
    monkeypatch.setattr(
        "app.utils.run_id.get_run_directory",
        lambda rid: tmp_path / "analysis" / rid,
    )
    run_dir = tmp_path / "analysis" / run_id
    (run_dir / "sun").mkdir(parents=True)
    (run_dir / "analysis.json").write_text("{}", encoding="utf-8")
    return run_dir


def _import_roster(client: TestClient, run_id: str) -> None:
    resp = client.post(
        f"/api/execute/participants/import?run_id={run_id}&day=sun",
        files={"file": ("roster.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert resp.status_code == 200, resp.text


def test_normalize_copies_type_notes_into_description():
    incident = normalize_incident(
        {
            "incident_id": "inc_old",
            "incident_type_note": "Heat after km 8.",
            "notes": [{"text": "Opened.", "kind": "system"}],
            "opened_at_label": "Tue 17:21",
            "updated_at": "2026-10-20T17:21:00",
        }
    )
    assert incident["description"] == "Heat after km 8."
    assert incident["assigned_to"] == ""
    assert incident["location_loc_id"] == ""
    assert incident["updated_at_label"] == datetime.fromisoformat(
        "2026-10-20T17:21:00"
    ).strftime("%a %H:%M")
    assert incident["notes"][0]["kind"] == "system"


def test_catalog_uses_plain_language_care_and_outcomes():
    care = {item["id"]: item["label"] for item in catalog()["care_types"]}
    outcomes = {item["id"]: item["label"] for item in catalog()["outcomes"]}
    assert care["first_aid"] == "Care given"
    assert care["sja"] == "SJA attended"
    assert "First aid" not in care.values()
    assert outcomes["dnf"] == "Did not finish (DNF)"
    assert outcomes["returned_to_course"] == "Returned to race course"
    assert outcomes["anb_to_hospital"] == "Transported to hospital by ANB"


def test_reporter_agencies_are_alphabetical():
    labels = [item["label"] for item in catalog()["reporter_agencies"]]
    assert labels == [
        "ANB",
        "AWP",
        "FFD",
        "FPF",
        "Participant",
        "Race Crew",
        "SJA",
        "Ski",
        "Spectator",
        "Volunteer",
    ]


def test_type_care_change_note_names_additions_and_removals():
    note = type_care_change_note(
        ["blister_skin"],
        ["heat_dehydration", "other"],
        ["first_aid"],
        ["fluids", "ice"],
        old_other="",
        new_other="Bee sting",
    )
    assert note == (
        "Type added: Heat / dehydration, Other. "
        "Type removed: Blister / skin. "
        "Type other: Bee sting. "
        "Care added: Fluids, Ice. "
        "Care removed: Care given."
    )
    assert type_care_change_note(
        ["heat_dehydration"],
        ["heat_dehydration"],
        ["fluids"],
        ["fluids"],
    ) == ""


def test_transfer_care_appends_handoff_note():
    incident = {
        "assigned_to": "ski",
        "notes": [],
    }
    transfer_care(incident, "sja", "walking, alert")
    assert incident["assigned_to"] == "sja"
    assert incident["notes"][-1]["kind"] == "transfer"
    assert incident["notes"][-1]["text"] == "Transferred SKI → SJA. walking, alert"


def test_api_timestamps_transfer_locations_and_quiet_save(tmp_path, monkeypatch):
    run_id = "exec912incidentaaaaaaaaaa"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    report_dir = run_dir / "sun" / "computation"
    report_dir.mkdir(parents=True)
    (report_dir / "locations_report.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "day": "sun",
                "locations": [
                    {
                        "loc_id": 16,
                        "loc_label": "10K Water Stop",
                        "zone": "Z3",
                    },
                    {
                        "loc_id": 22,
                        "loc_label": "Trail at McKeen",
                        "zone": "Z2",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(app)
    _import_roster(client, run_id)

    created = client.post(
        f"/api/execute/incidents?run_id={run_id}&day=sun",
        json={"reg_id": "1"},
    )
    assert created.status_code == 200, created.text
    incident = created.json()["incident"]
    iid = incident["incident_id"]
    assert incident["updated_at_label"]
    assert incident["description"] == ""
    assert incident["assigned_to"] == ""

    listed = client.get(f"/api/execute/incidents?run_id={run_id}&day=sun")
    assert listed.status_code == 200
    active = listed.json()["active"]
    assert active[0]["updated_at_label"] == incident["updated_at_label"]
    assert "agencies" in listed.json()["catalog"]
    assert [item["label"] for item in listed.json()["catalog"]["reporter_agencies"]][
        0
    ] == "ANB"

    locs = client.get(f"/api/execute/locations?run_id={run_id}&day=sun")
    assert locs.status_code == 200
    labels = {row["loc_label"] for row in locs.json()["locations"]}
    assert labels == {"10K Water Stop", "Trail at McKeen"}
    water = next(
        row for row in locs.json()["locations"] if row["loc_label"] == "10K Water Stop"
    )
    assert water["loc_id"] == 16
    assert water["zone"] == "Z3"

    picked = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={
            "location_text": "10K Water Stop",
            "location_loc_id": "16",
            "description": "Runner down after the water stop.",
            "reported_by_name": "Jeff",
            "reported_by_agency": "race_crew",
            "assigned_to": "ski",
            "called_911": "yes",
        },
    )
    assert picked.status_code == 200, picked.text
    body = picked.json()["incident"]
    assert body["location_text"] == "10K Water Stop"
    assert body["location_loc_id"] == "16"
    assert body["description"] == "Runner down after the water stop."
    assert body["reported_by_name"] == "Jeff"
    assert body["reported_by_agency"] == "race_crew"
    assert body["assigned_to"] == "ski"
    texts = [item["text"] for item in body["notes"]]
    kinds = [item["kind"] for item in body["notes"]]
    assert "Opened." in texts
    assert "Runner down after the water stop." in texts
    assert "911 called." in texts
    assert "Reported by Jeff · Race Crew." in texts
    assert "Updated location" not in " ".join(texts)
    assert not any(text.startswith("Transferred ") for text in texts)
    assert kinds.count("user") == 1
    assert kinds.count("system") == 3

    again_report = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={
            "reported_by_name": "Jeff",
            "reported_by_agency": "race_crew",
        },
    )
    again_report_texts = [
        item["text"] for item in again_report.json()["incident"]["notes"]
    ]
    assert again_report_texts.count("Reported by Jeff · Race Crew.") == 1

    renamed = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={
            "reported_by_name": "Jeffrey",
            "reported_by_agency": "race_crew",
        },
    )
    renamed_inc = renamed.json()["incident"]
    assert renamed_inc["reported_by_name"] == "Jeffrey"
    assert renamed_inc["notes"][-1]["text"] == "Reported by Jeffrey · Race Crew."

    other = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={
            "incident_types": ["other"],
            "incident_type_other": "Bee sting, swelling",
        },
    )
    assert other.json()["incident"]["incident_types"] == ["other"]
    assert other.json()["incident"]["incident_type_other"] == "Bee sting, swelling"
    assert other.json()["incident"]["notes"][-1]["text"] == (
        "Type added: Other. Type other: Bee sting, swelling."
    )

    noop_stamp = other.json()["incident"]["updated_at"]
    noop = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={
            "incident_types": ["other"],
            "incident_type_other": "Bee sting, swelling",
        },
    )
    assert noop.json()["incident"]["updated_at"] == noop_stamp
    assert noop.json()["incident"]["notes"][-1]["text"] == (
        "Type added: Other. Type other: Bee sting, swelling."
    )

    care = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={"care_types": ["fluids", "ice"]},
    )
    assert care.json()["incident"]["notes"][-1]["text"] == "Care added: Fluids, Ice."
    care_removed = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={"care_types": ["ice"]},
    )
    assert care_removed.json()["incident"]["notes"][-1]["text"] == "Care removed: Fluids."

    changed = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={"assigned_to": "sja"},
    )
    assert changed.status_code == 200
    changed_inc = changed.json()["incident"]
    assert changed_inc["assigned_to"] == "sja"
    assert changed_inc["notes"][-1]["kind"] == "transfer"
    assert changed_inc["notes"][-1]["text"] == "Transferred SKI → SJA."

    again_911 = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={"called_911": "yes", "outcome": "dnf"},
    )
    again_texts = [item["text"] for item in again_911.json()["incident"]["notes"]]
    assert again_texts.count("911 called.") == 1
    assert not any(text.startswith("Updated ") for text in again_texts)

    free = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={
            "location_text": "Between Water Stop and Brookside",
            "location_loc_id": "",
        },
    )
    assert free.json()["incident"]["location_text"] == "Between Water Stop and Brookside"
    assert free.json()["incident"]["location_loc_id"] == ""

    xfer = client.post(
        f"/api/execute/incidents/{iid}/transfer?run_id={run_id}&day=sun",
        json={"to_agency": "anb", "text": "walking, alert"},
    )
    assert xfer.status_code == 200, xfer.text
    xfer_inc = xfer.json()["incident"]
    assert xfer_inc["assigned_to"] == "anb"
    assert xfer_inc["notes"][-1]["kind"] == "transfer"
    assert xfer_inc["notes"][-1]["text"] == "Transferred SJA → ANB. walking, alert"

    stored = json.loads(
        (run_dir / "sun" / "execution" / "incidents.json").read_text(encoding="utf-8")
    )
    assert stored["schema_version"] == SCHEMA_VERSION

    closed = client.post(
        f"/api/execute/incidents/{iid}/close?run_id={run_id}&day=sun"
    )
    assert closed.status_code == 200
    blocked = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={"description": "should not write"},
    )
    assert blocked.status_code == 400
    assert "read-only" in blocked.json()["detail"]
    blocked_note = client.post(
        f"/api/execute/incidents/{iid}/notes?run_id={run_id}&day=sun",
        json={"text": "should not write"},
    )
    assert blocked_note.status_code == 400

    storage = Storage(root=str(run_dir))
    catalog = location_catalog(storage, "sun")
    assert catalog[0]["loc_label"] == "10K Water Stop"


def test_v1_record_opens_with_v2_fields(tmp_path, monkeypatch):
    run_id = "exec912legacyaaaaaaaaaaaa"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    exec_dir = run_dir / "sun" / "execution"
    exec_dir.mkdir(parents=True)
    (exec_dir / "incidents.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": run_id,
                "day": "sun",
                "incidents": [
                    {
                        "incident_id": "inc_legacy",
                        "reg_id": "1",
                        "incident_status": "active",
                        "bib": "21100",
                        "given_name": "Debbie",
                        "family_name": "Perkins",
                        "location_text": "Med tent",
                        "incident_type_note": "Blister, still wants to continue.",
                        "care_transferred": "yes",
                        "transferred_to": ["ski"],
                        "notes": [
                            {
                                "text": "Opened.",
                                "kind": "system",
                                "saved_at": "2026-10-20T17:00:00",
                                "saved_at_label": "Tue 17:00",
                            }
                        ],
                        "opened_at": "2026-10-20T17:00:00",
                        "opened_at_label": "Tue 17:00",
                        "updated_at": "2026-10-20T17:00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _import_roster(TestClient(app), run_id)
    client = TestClient(app)
    got = client.get(
        f"/api/execute/incidents/inc_legacy?run_id={run_id}&day=sun"
    )
    assert got.status_code == 200, got.text
    incident = got.json()["incident"]
    assert incident["description"] == "Blister, still wants to continue."
    assert incident["reported_by_name"] == ""
    assert incident["assigned_to"] == ""
    assert incident["location_loc_id"] == ""
    assert incident["updated_at_label"] == datetime.fromisoformat(
        "2026-10-20T17:00:00"
    ).strftime("%a %H:%M")
    assert incident["care_transferred"] == "yes"
    assert incident["transferred_to"] == ["ski"]


def test_pages_have_two_pane_case_shell():
    html = (
        REPO / "frontend" / "templates" / "pages" / "execute_incidents.html"
    ).read_text(encoding="utf-8")
    js = (REPO / "frontend" / "static" / "js" / "execute_incidents.js").read_text(
        encoding="utf-8"
    )
    assert 'id="rf-hs-queue"' in html
    assert 'id="rf-hs-case"' in html
    assert "Back to lists" not in js
    assert 'id="hs-type-note"' not in js
    assert 'id="hs-desc"' in js
    assert 'id="hs-assigned"' in js
    assert 'id="hs-report-agency"' in js
    assert "Incident report" in js
    assert "Reported issue & care provided" in js
    assert "Care provided" in js
    assert "911 called" in js
    assert 'id="hs-type-other"' in js
    assert 'id="hs-xfer-to"' in js
    assert "Agency taking over care" in js
    assert "Record care handoff" in js
    assert "function recordTransfer" in js
    assert "function openCase" in js
    assert "function hasPendingWork" in js
    assert "Note not added" in js
    assert "Unsaved changes" in js
    assert "Save case changes &amp; switch" in html
    assert "Discard changes" in html
    assert js.index("Incident report") < js.index(">Case log<")
    assert js.index("Reported issue & care provided") < js.index("Close case")
    assert "Find bib or name" in js
    assert "Location not recorded" in js
    assert "Care agency not recorded" in js
    assert "Save case" in js
    assert "Review &amp; close case" in js
    assert "Save changes & add note" not in js
    assert "function missingSaveFields" in js
    assert "function missingCloseFields" in js
    assert "function canCloseCase" in js
    save_fields = js[
        js.index("function missingSaveFields") : js.index("function missingCloseFields")
    ]
    assert "Closed by" not in save_fields
    assert "Start a case" in js
    assert "Add to case log" in js
    assert "Closed by (required)" in js
    assert "organisation" not in js
    assert "first-aid" not in js.lower().replace("first_aid", "")
    assert "function dirtyFieldLabels" in js
    assert "Unsaved: " in js
    assert "Required to save" in js
    assert "DNF is an incident" not in js
    assert "Record the update received by the EOC" not in js
    assert "catalog.reporter_agencies" in js
    assert 'id="hs-by-agency"' in js
    assert "data-loc-label" in js
    assert "reverse()" in js
    assert "is-closed" in js
    assert "function isClosed" in js
    assert "function persistForm" in js
    assert js.index("function persistForm") < js.index("function saveNote")
    save_note = js[js.index("function saveNote") : js.index("function assignCare")]
    assert "/notes" in save_note
    assert "saveWithStatus" not in save_note
    assert "persistForm" in save_note
    open_case = js[js.index("function openCase") : js.index("function performClose")]
    assert "hasPendingWork()" in open_case
    assert "persistForm().then" not in open_case
    close_fn = js[js.index("function closeIncident") : js.index("function navStay")]
    assert "saveForm" in close_fn
    assert 'showNavModal("close")' in close_fn
    assert "beforeunload" in js
