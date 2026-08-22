"""Issues #894 / #895: computed locations JSON + proxy ids for Plan Locations API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.locations.pairing import consolidate_location_rows
from app.core.locations.report_json import (
    attach_resolved_proxies,
    build_locations_report_document,
    json_ready,
    locations_proxied_to,
    locations_report_relpath,
    parse_optional_id,
    resolve_proxy_ids,
    write_locations_report_json,
)
from app.main import app
from app.routes.api_locations import _normalize_location_api_row


def test_resolve_proxy_pass_id_to_human_loc_id():
    pass_to_loc = {83: 2, 81: 50}
    assert resolve_proxy_ids(83, pass_to_loc) == (83, 2)
    assert resolve_proxy_ids(None, pass_to_loc) == (None, None)
    assert resolve_proxy_ids(99, pass_to_loc) == (99, None)


def test_resolve_proxy_when_authored_as_human_loc_id():
    pass_to_loc = {83: 2}
    assert resolve_proxy_ids(2, pass_to_loc) == (83, 2)


def test_attach_resolved_proxies_on_pass_rows():
    rows = [
        {"pass_id": 83, "loc_id": 2, "loc_label": "St John at Queen"},
        {
            "pass_id": 87,
            "loc_id": 8,
            "loc_label": "Queen at Waterloo",
            "proxy_pass_id": 83,
        },
        {"pass_id": 1, "loc_id": 1, "loc_label": "On course"},
    ]
    attach_resolved_proxies(rows)
    by_loc = {r["loc_id"]: r for r in rows}
    assert by_loc[8]["proxy_pass_id"] == 83
    assert by_loc[8]["proxy_loc_id"] == 2
    assert by_loc[2]["proxy_pass_id"] is None
    assert by_loc[1]["proxy_loc_id"] is None


def test_consolidate_copies_proxy_onto_location_row():
    rows = [
        {
            "pass_id": 83,
            "loc_id": 2,
            "pass_key": "AAAAA",
            "loc_label": "St John at Queen",
            "loc_type": "course",
            "first_runner": "07:02:40",
            "last_runner": "08:40:15",
            "loc_end": "08:55:00",
        },
        {
            "pass_id": 87,
            "loc_id": 8,
            "pass_key": "BBBBB",
            "loc_label": "Queen at Waterloo",
            "loc_type": "traffic",
            "proxy_pass_id": 83,
            "loc_end": "08:55:00",
        },
    ]
    attach_resolved_proxies(rows)
    consolidated = consolidate_location_rows(rows)
    by_loc = {int(r["loc_id"]): r for r in consolidated}
    assert by_loc[8]["proxy_pass_id"] == 83
    assert by_loc[8]["proxy_loc_id"] == 2
    assert by_loc[2]["proxy_pass_id"] is None
    linked = locations_proxied_to(consolidated, 2)
    assert [int(r["loc_id"]) for r in linked] == [8]


def test_json_ready_strips_nan():
    payload = json_ready({"loc_end": float("nan"), "ok": 1.0})
    assert payload["loc_end"] is None
    assert payload["ok"] == 1.0
    json.dumps(payload, allow_nan=False)


def _patch_run_dir(monkeypatch, tmp_path: Path, run_id: str) -> Path:
    run_dir = tmp_path / "analysis" / run_id
    monkeypatch.setattr(
        "app.utils.run_id.get_run_directory", lambda rid: tmp_path / "analysis" / rid
    )
    return run_dir


def test_write_and_api_reads_json_not_csv(tmp_path, monkeypatch):
    run_id = "locjson894895aaaaaaaaaa"
    run_dir = _patch_run_dir(monkeypatch, tmp_path, run_id)
    day_dir = run_dir / "sun"
    comp = day_dir / "computation"
    reports = day_dir / "reports"
    comp.mkdir(parents=True)
    reports.mkdir(parents=True)
    (reports / "Locations.csv").write_text(
        "loc_id,loc_label\n999,SHOULD NOT BE READ\n", encoding="utf-8"
    )
    document = build_locations_report_document(
        run_id=run_id,
        day="sun",
        locations=[
            {
                "loc_id": 2,
                "loc_label": "St John at Queen",
                "loc_type": "course",
                "loc_end": "08:55:00",
                "yssr_count": 2,
                "flag": True,
                "by_event": {"half": {"last_runner": "08:40:15"}},
            },
            {
                "loc_id": 8,
                "loc_label": "Queen at Waterloo",
                "loc_type": "traffic",
                "loc_end": "08:55:00",
                "yssr_count": 1,
                "proxy_pass_id": 83,
                "proxy_loc_id": 2,
                "flag": False,
            },
        ],
    )
    write_locations_report_json(comp / "locations_report.json", document)
    (comp / "locations_results.json").write_text(
        json.dumps(
            {
                "resources_available": ["yssr"],
                "locations": [{"loc_id": 2, "day": "sun", "onepage": "y"}],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(app)
    response = client.get(f"/api/locations?run_id={run_id}&day=sun")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["count"] == 2
    labels = {row["loc_label"] for row in body["locations"]}
    assert "SHOULD NOT BE READ" not in labels
    by_id = {int(row["loc_id"]): row for row in body["locations"]}
    assert by_id[8]["proxy_loc_id"] == 2
    assert by_id[8]["proxy_pass_id"] == 83
    assert by_id[2]["onepage"] == "y"
    assert by_id[2]["flag"] is True
    assert by_id[2]["by_event"]["half"]["last_runner"] == "08:40:15"


def test_api_404_when_json_missing(tmp_path, monkeypatch):
    run_id = "locjsonmissingaaaaaaaaa"
    run_dir = _patch_run_dir(monkeypatch, tmp_path, run_id)
    day_dir = run_dir / "sun"
    (day_dir / "reports").mkdir(parents=True)
    (day_dir / "reports" / "Locations.csv").write_text(
        "loc_id,loc_label\n1,CSV only\n", encoding="utf-8"
    )
    client = TestClient(app)
    response = client.get(f"/api/locations?run_id={run_id}&day=sun")
    assert response.status_code == 404
    assert "locations_report.json" in response.json()["detail"]


def test_normalize_row_parses_by_event_string():
    row = _normalize_location_api_row(
        {"flag": "Y", "by_event": '{"full": {"last_runner": "09:00:00"}}'}
    )
    assert row["flag"] is True
    assert row["by_event"]["full"]["last_runner"] == "09:00:00"


def test_write_computed_json_helper(tmp_path, monkeypatch):
    from app.location_report import _write_computed_locations_json

    run_id = "locjsonhelperaaaaaaaaaa"
    monkeypatch.setattr(
        "app.utils.run_id.get_run_directory", lambda rid: tmp_path / "analysis" / rid
    )
    path = _write_computed_locations_json(
        [{"loc_id": 1, "loc_label": "A", "loc_end": "08:00:00", "fpf_count": 1}],
        run_id=run_id,
        day="sun",
        output_dir=str(tmp_path / "reports"),
    )
    assert path is not None
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["count"] == 1
    assert data["locations"][0]["loc_id"] == 1
    assert "fpf" in data["resources_available"]


def test_relpath_and_parse_optional_id():
    assert locations_report_relpath("sun") == "sun/computation/locations_report.json"
    assert parse_optional_id("83") == 83
    assert parse_optional_id("") is None
    assert parse_optional_id(float("nan")) is None
