"""Issue #947: Execute layers, plan import with participants, paired legs, legend."""

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
    apply_plan_overrides,
    import_published_plan,
    sha256_bytes,
)
from app.execute_app import app

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "tests" / "fixtures" / "issue911_participant_list.csv"


def _package(
    *,
    name: str = "Day plan 2027-05-09",
    calendar_date: str = "2027-05-09",
    weekday_code: str = "sun",
) -> bytes:
    locations = {
        "locations": [
            {"loc_id": 16, "loc_label": "10K Water Stop", "loc_type": "water"}
        ],
        "resources_available": [],
    }
    course = {"type": "FeatureCollection", "features": []}
    loc_bytes = json.dumps(locations).encode("utf-8")
    course_bytes = json.dumps(course).encode("utf-8")
    manifest = {
        "schema_version": 1,
        "plan_id": str(uuid4()),
        "revision": 1,
        "published_at": "2026-10-31T12:00:00+00:00",
        "calendar_date": calendar_date,
        "weekday_code": weekday_code,
        "name": name,
        "timezone": "America/Halifax",
        "source_run_id": "src947",
        "races": [
            {"id": "elite", "name": "5K Elite", "course": "courses/elite.geojson"}
        ],
        "files": [
            {"path": "locations.json", "sha256": sha256_bytes(loc_bytes)},
            {"path": "courses/elite.geojson", "sha256": sha256_bytes(course_bytes)},
        ],
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("locations.json", loc_bytes)
        zf.writestr("courses/elite.geojson", course_bytes)
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        "app.core.execute.published_plan.get_runflow_root",
        lambda: tmp_path,
    )
    return TestClient(app)


def _import(client: TestClient, archive: bytes, **form):
    files = {"package": ("plan.zip", archive, "application/zip")}
    if form.pop("with_roster", False):
        files["participants"] = ("roster.csv", FIXTURE.read_bytes(), "text/csv")
    return client.post("/api/execute/plans/import", files=files, data=form)


def _plan_row(client: TestClient, plan_id: str) -> dict:
    rows = client.get("/api/execute/plans").json()["plans"]
    return next(row for row in rows if row["plan_id"] == plan_id)


# --- Item 1: Execute layers -------------------------------------------------


def test_execute_layers_match_plan_location_types():
    html = (REPO / "frontend" / "templates" / "pages" / "execute.html").read_text(
        encoding="utf-8"
    )
    order = [
        'data-layer="aid" checked> Aid',
        'data-layer="course" checked> Course',
        'data-layer="extract" checked> Extract',
        'data-layer="official" checked> Official',
        'data-layer="resources" checked> Resources',
        'data-layer="sos" checked> SOS',
        'data-layer="traffic" checked> Traffic',
        'data-layer="water" checked> Water',
        'data-layer="all" checked> All Layers',
    ]
    positions = [html.index(item) for item in order]
    assert positions == sorted(positions)
    for gone in ("Reopen set", "Turn-arounds", "All locations", "Water / aid"):
        assert gone not in html


def test_execute_layer_logic_by_type():
    js = (REPO / "frontend" / "static" / "js" / "execute_board.js").read_text(
        encoding="utf-8"
    )
    assert "function locTypeLayer" in js
    assert "function allLayersOn" in js
    assert "reopen:" not in js and "turnarounds:" not in js
    visible = js[js.index("function locationVisible") :]
    visible = visible[: visible.index("function statusTitle")]
    assert 'key === "traffic"' in visible
    assert 'focusedCol === "reopen_next"' in visible
    assert "if (key) return !!layers[key];" in visible
    type_map = js[js.index("function locTypeLayer") :]
    type_map = type_map[: type_map.index("function serviceLayerOn")]
    for loc_type in ("aid", "course", "extract", "official", "traffic", "water"):
        assert f'type === "{loc_type}"' in type_map
    assert 'pin.source === "course"' in js
    assert 'key === "all"' in js
    assert "all.indeterminate" in js


# --- Items 2-3: import with participants ------------------------------------


def test_preview_returns_name_and_date(client: TestClient):
    resp = client.post(
        "/api/execute/plans/preview",
        files={"package": ("plan.zip", _package(), "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Day plan 2027-05-09"
    assert body["calendar_date"] == "2027-05-09"
    assert body["weekday_code"] == "sun"
    assert body["already_imported"] is False


def test_import_with_roster_edits_and_activates(client: TestClient):
    resp = _import(
        client,
        _package(),
        with_roster=True,
        name="FM 2027 Sunday",
        calendar_date="2027-05-16",
        activate="true",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["activated"] is True
    assert body["participants"]["starts"] > 0
    row = _plan_row(client, body["plan_id"])
    assert row["name"] == "FM 2027 Sunday"
    assert row["calendar_date"] == "2027-05-16"
    assert row["active"] is True
    assert row["participant_count"] == body["participants"]["starts"]
    ctx = client.get("/api/execute/active-context").json()
    assert ctx["name"] == "FM 2027 Sunday"
    assert ctx["calendar_date"] == "2027-05-16"


def test_import_rejects_wrong_weekday_before_writing(client: TestClient):
    resp = _import(
        client,
        _package(),
        with_roster=True,
        calendar_date="2027-05-10",
        activate="true",
    )
    assert resp.status_code == 400
    assert "Sunday" in resp.json()["detail"]
    assert client.get("/api/execute/plans").json()["plans"] == []


def test_import_rejects_bad_roster_before_writing(client: TestClient):
    resp = client.post(
        "/api/execute/plans/import",
        files={
            "package": ("plan.zip", _package(), "application/zip"),
            "participants": ("bad.csv", b"name,email\nA,a@x\n", "text/csv"),
        },
        data={"activate": "true"},
    )
    assert resp.status_code == 400
    assert client.get("/api/execute/plans").json()["plans"] == []


def test_activate_requires_participants(client: TestClient):
    imported = _import(client, _package())
    assert imported.status_code == 200
    plan_id = imported.json()["plan_id"]
    assert _plan_row(client, plan_id)["participant_count"] == 0
    blocked = client.post("/api/execute/plans/activate", json={"plan_id": plan_id})
    assert blocked.status_code == 400
    assert "participant list" in blocked.json()["detail"]
    no_roster = _import(client, _package(), activate="true")
    assert no_roster.status_code == 400

    loaded = client.post(
        f"/api/execute/plans/{plan_id}/participants",
        files={"file": ("roster.csv", FIXTURE.read_bytes(), "text/csv")},
    )
    assert loaded.status_code == 200, loaded.text
    assert _plan_row(client, plan_id)["participant_count"] > 0
    ok = client.post("/api/execute/plans/activate", json={"plan_id": plan_id})
    assert ok.status_code == 200


def test_new_plan_starts_without_other_plans_cases(client: TestClient):
    first = _import(client, _package(), with_roster=True, activate="true").json()
    created = client.post("/api/execute/incidents", json={"reg_id": "1"})
    assert created.status_code == 200, created.text
    assert client.get("/api/execute/incidents").json()["counts"]["active"] == 1

    second = _import(
        client, _package(name="Second plan"), with_roster=True, activate="true"
    ).json()
    assert second["plan_id"] != first["plan_id"]
    assert client.get("/api/execute/active-context").json()["name"] == "Second plan"
    assert client.get("/api/execute/incidents").json()["counts"] == {
        "active": 0,
        "closed": 0,
    }


def test_reimport_updates_name_and_date(tmp_path: Path):
    archive = _package()
    first = import_published_plan(archive, root=tmp_path)
    again = import_published_plan(
        archive, root=tmp_path, name="Renamed", calendar_date="2027-05-16"
    )
    assert again["idempotent"] is True
    assert again["plan_id"] == first["plan_id"]
    assert again["name"] == "Renamed"
    assert again["calendar_date"] == "2027-05-16"
    registry = json.loads(
        (tmp_path / "execute" / "plans" / "registry.json").read_text("utf-8")
    )
    row = registry["plans"][first["plan_id"]]
    assert row["name"] == "Renamed"
    assert row["calendar_date"] == "2027-05-16"


def test_overrides_keep_weekday():
    manifest = {"calendar_date": "2027-05-09", "weekday_code": "sun", "name": "A"}
    out = apply_plan_overrides(manifest, name="  B ", calendar_date="2027-05-16")
    assert out["name"] == "B"
    assert out["calendar_date"] == "2027-05-16"
    assert apply_plan_overrides(manifest, name="", calendar_date="") == manifest
    with pytest.raises(PublishedPlanError, match="Sunday"):
        apply_plan_overrides(manifest, calendar_date="2027-05-15")


def test_plans_page_import_modal_markup():
    html = (REPO / "frontend" / "templates" / "pages" / "execute_plans.html").read_text(
        encoding="utf-8"
    )
    js = (REPO / "frontend" / "static" / "js" / "execute_plans.js").read_text(
        encoding="utf-8"
    )
    for needle in (
        'id="rf-plans-import-modal"',
        'id="rf-plans-import-package"',
        'id="rf-plans-import-name"',
        'type="date" id="rf-plans-import-date"',
        'id="rf-plans-import-roster"',
        "Import and activate",
        "<th>Participants</th>",
    ):
        assert needle in html
    assert "/api/execute/plans/preview" in js
    assert 'body.append("activate", "true")' in js
    assert "Add participants before activating" in js
    assert '"/participants"' in js
    assert "'participants'" in (
        REPO / "frontend" / "static" / "js" / "table_actions.js"
    ).read_text(encoding="utf-8")


def test_plans_show_short_plan_id():
    static = REPO / "frontend" / "static" / "js"
    html = (REPO / "frontend" / "templates" / "pages" / "execute_plans.html").read_text(
        encoding="utf-8"
    )
    js = (static / "execute_plans.js").read_text(encoding="utf-8")
    context = (static / "execute_context.js").read_text(encoding="utf-8")
    assert "<th>Name</th>\n                        <th>ID</th>" in html
    assert 'id="rf-plans-import-id"' in html
    assert 'colspan="6"' not in html and 'colspan="6"' not in js
    assert "shortPlanId(row.plan_id)" in js
    assert "importPlanId(data.plan_id)" in js
    assert "String(ctx.plan_id).slice(0, 8)" in context


# --- Item 4: paired legs ----------------------------------------------------


def test_build_prompts_to_apply_changes_to_paired_leg():
    js = (REPO / "frontend" / "static" / "js" / "map" / "segment_recipes.js").read_text(
        encoding="utf-8"
    )
    save = js[js.index("function saveLegLocations") :]
    save = save[: save.index("function libraryLeg")]
    assert "queuePairedLocationsPrompt(legId)" in save
    assert "skipPairPrompt" in save
    assert "function offerPairedLocationsCopy" in js
    assert "edited.indexOf(String(paired.id)) !== -1" in js
    fields = js[js.index("var PAIRED_LEG_FIELDS") :]
    fields = fields[: fields.index("];")]
    for key in ("width_m", "schema", "flow_type", "description"):
        assert f"key: '{key}'" in fields
    assert "key: 'start_label', label: 'start place', pairedKey: 'end_label'" in fields
    assert "key: 'end_label', label: 'end place', pairedKey: 'start_label'" in fields
    assert "direction" not in fields
    editor = js[js.index("function saveLegEditor") :]
    editor = editor[: editor.index("function replaceLegGpx")]
    assert "offerPairedLegFieldsCopy(editedLegId, before, fields)" in editor
    assert "{ skipPairPrompt: true }" in js


# --- Item 5: Progression legend ---------------------------------------------


def test_progression_legend_matches_subtitle_size():
    page = (REPO / "frontend" / "templates" / "pages" / "progression.html").read_text(
        encoding="utf-8"
    )
    legend = page[page.index(".progression-legend {") :]
    legend = legend[: legend.index("}")]
    assert "font-size: 0.875rem;" in legend
