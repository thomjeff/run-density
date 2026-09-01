"""Issue #911: Execute Participants import, lookup, and incidents."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.execute.participants import (
    DuplicateBibError,
    assert_unique_start_bibs,
    classify_row_kind,
    lookup_rows,
    parse_roster_csv,
)
from app.main import app

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "issue911_participant_list.csv"


def test_bundle_vs_start_from_sub_event():
    assert classify_row_kind("5 KM (Run Only) and 10 KM") == "bundle"
    assert classify_row_kind("5 KM (Run Only) & 21.1 KM") == "bundle"
    assert classify_row_kind("10 KM Run/Walk") == "start"
    assert classify_row_kind("5 KM (Run Only)") == "start"


def test_parse_fixture_hides_bundles_and_keeps_no_bib_start():
    rows = parse_roster_csv(FIXTURE.read_text(encoding="utf-8"))
    starts = lookup_rows(rows)
    bundles = [row for row in rows if row["row_kind"] == "bundle"]
    assert len(rows) == 12
    assert len(bundles) == 2
    assert len(starts) == 10
    assert {row["reg_id"] for row in bundles} == {"5", "8"}
    debbie = next(row for row in starts if row["bib"] == "21100")
    assert debbie["given_name"] == "Debbie"
    assert debbie["medical_disclosed"] == "yes"
    assert debbie["medical_conditions"] == [
        "Asthma or other breathing condition",
        "Diabetes or blood sugar condition",
        "Other medical condition",
    ]
    assert debbie["medical_note"] == "Hypothyroidism"
    alex = next(row for row in starts if row["reg_id"] == "12")
    assert alex["bib"] == ""
    assert alex["family_name"] == "Chen"


def test_duplicate_start_bibs_fail():
    rows = parse_roster_csv(FIXTURE.read_text(encoding="utf-8"))
    for row in rows:
        if row["reg_id"] == "11":
            row["bib"] = "10100"
    try:
        assert_unique_start_bibs(rows)
        raise AssertionError("expected DuplicateBibError")
    except DuplicateBibError as exc:
        assert exc.bib == "10100"


def _patch_run(monkeypatch, tmp_path: Path, run_id: str) -> Path:
    monkeypatch.setattr(
        "app.utils.run_id.get_run_directory",
        lambda rid: tmp_path / "analysis" / rid,
    )
    run_dir = tmp_path / "analysis" / run_id
    (run_dir / "sun").mkdir(parents=True)
    (run_dir / "analysis.json").write_text("{}", encoding="utf-8")
    return run_dir


def test_api_import_lookup_incident_and_reimport(tmp_path, monkeypatch):
    run_id = "exec911participantaaaaaaa"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    client = TestClient(app)
    empty = client.get(
        f"/api/execute/participants?run_id={run_id}&day=sun"
    )
    assert empty.status_code == 200, empty.text
    assert empty.json()["participants"] == []
    assert empty.json()["starts"] == 0

    imported = client.post(
        f"/api/execute/participants/import?run_id={run_id}&day=sun",
        files={
            "file": (
                "roster.csv",
                FIXTURE.read_bytes(),
                "text/csv",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    stats = imported.json()["stats"]
    assert stats["starts"] == 10
    assert stats["bundles"] == 2
    assert stats["no_bib"] == 1
    stored = json.loads(
        (run_dir / "sun" / "execution" / "participants.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(stored["rows"]) == 12

    listed = client.get(
        f"/api/execute/participants?run_id={run_id}&day=sun"
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 10
    assert listed.json()["starts"] == 10

    hit = client.get(
        f"/api/execute/participants?run_id={run_id}&day=sun&q=21100&field=bib"
    )
    assert hit.status_code == 200
    people = hit.json()["participants"]
    assert len(people) == 1
    assert people[0]["given_name"] == "Debbie"
    asthma = client.get(
        f"/api/execute/participants?run_id={run_id}&day=sun"
        "&condition=Asthma"
    )
    names = {row["given_name"] for row in asthma.json()["participants"]}
    assert "Debbie" in names

    hidden = client.get(
        f"/api/execute/participants?run_id={run_id}&day=sun&q=Jesome&field=name"
    )
    sally = hidden.json()["participants"]
    assert len(sally) == 2
    assert {row["bib"] for row in sally} == {"5013", "10100"}

    nobib = client.get(
        f"/api/execute/participants?run_id={run_id}&day=sun&q=Chen&field=name"
    )
    assert nobib.json()["participants"][0]["bib"] == ""

    bundle_reg = client.post(
        f"/api/execute/incidents?run_id={run_id}&day=sun",
        json={"reg_id": "5"},
    )
    assert bundle_reg.status_code == 400

    created = client.post(
        f"/api/execute/incidents?run_id={run_id}&day=sun",
        json={"reg_id": "1"},
    )
    assert created.status_code == 200, created.text
    incident = created.json()["incident"]
    iid = incident["incident_id"]
    assert incident["bib"] == "21100"
    assert incident["incident_status"] == "active"

    note1 = client.post(
        f"/api/execute/incidents/{iid}/notes?run_id={run_id}&day=sun",
        json={"text": "Arrived walking."},
    )
    assert note1.status_code == 200
    note2 = client.post(
        f"/api/execute/incidents/{iid}/notes?run_id={run_id}&day=sun",
        json={"text": "Elects not to continue."},
    )
    assert len(note2.json()["incident"]["notes"]) == 2

    saved = client.put(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun",
        json={"outcome": "dnf", "location_text": "Med tent, km 16"},
    )
    assert saved.json()["incident"]["outcome"] == "dnf"
    closed = client.post(
        f"/api/execute/incidents/{iid}/close?run_id={run_id}&day=sun"
    )
    assert closed.json()["incident"]["incident_status"] == "closed"
    lists = client.get(
        f"/api/execute/incidents?run_id={run_id}&day=sun"
    )
    assert lists.json()["counts"]["closed"] == 1
    assert lists.json()["closed"][0]["display_bib"] == "21100"

    rewritten = FIXTURE.read_text(encoding="utf-8").replace(
        "1,21100,Perkins,Debbie",
        "1,29999,Perkins,Debbie",
    )
    again = client.post(
        f"/api/execute/participants/import?run_id={run_id}&day=sun",
        files={"file": ("roster.csv", rewritten.encode("utf-8"), "text/csv")},
    )
    assert again.status_code == 200, again.text
    shown = client.get(
        f"/api/execute/incidents/{iid}?run_id={run_id}&day=sun"
    )
    assert shown.json()["incident"]["display_bib"] == "29999"
    assert shown.json()["incident"]["incident_status"] == "closed"


def test_api_rejects_duplicate_start_bibs(tmp_path, monkeypatch):
    run_id = "exec911dupbibaaaaaaaaaaaa"
    _patch_run(monkeypatch, tmp_path, run_id)
    client = TestClient(app)
    colliding = FIXTURE.read_text(encoding="utf-8").replace(
        "11,10102,Smith,James",
        "11,10100,Smith,James",
    )
    resp = client.post(
        f"/api/execute/participants/import?run_id={run_id}&day=sun",
        files={"file": ("roster.csv", colliding.encode("utf-8"), "text/csv")},
    )
    assert resp.status_code == 409
    assert "10100" in resp.json()["detail"]


def test_pages_have_search_and_lists():
    people = (
        REPO / "frontend" / "templates" / "pages" / "execute_participants.html"
    ).read_text(encoding="utf-8")
    incidents = (
        REPO / "frontend" / "templates" / "pages" / "execute_incidents.html"
    ).read_text(encoding="utf-8")
    assert "Participants" in people
    assert 'id="rf-hs-import"' in people
    assert 'placeholder="Search bib or name"' in people
    assert 'id="rf-hs-cond-btn"' in people
    assert 'id="rf-hs-nobib"' in people
    assert 'id="rf-hs-q-clear"' in people
    assert 'id="rf-hs-clear"' in people
    assert "Incidents" in incidents
    assert 'id="rf-hs-lists"' in incidents
    form_js = (REPO / "frontend" / "static" / "js" / "execute_incidents.js").read_text(
        encoding="utf-8"
    )
    assert "rf-hs-idbar" in form_js
    assert 'id="hs-bib"' not in form_js
