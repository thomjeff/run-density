"""Issue #898: Execute reopen variance CSV."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.execute.report import (
    build_reopen_rows,
    csv_columns,
    reopen_csv_text,
)
from app.core.execute.state import empty_state, record_reopen
from app.core.locations.report_json import build_locations_report_document
from app.main import app


def _locations():
    return [
        {
            "loc_id": 2,
            "loc_label": "St John at Queen",
            "loc_type": "course",
            "loc_start": "06:30:00",
            "loc_end": "08:50:00",
            "first_runner": "07:20:10",
            "last_runner": "08:40:00",
            "yssr_count": 2,
            "awp_count": 1,
            "pass_count": 3,
            "by_event": {"10k": {"last_runner": "08:40:00"}},
        },
        {
            "loc_id": 3,
            "loc_label": "Water Stop (Full Loop)",
            "loc_type": "water",
            "loc_start": "07:00:00",
            "loc_end": "10:15:00",
            "first_runner": "07:45:00",
            "last_runner": "10:00:00",
            "vol_count": 4,
        },
    ]


def test_reopen_rows_blank_until_actual():
    state = empty_state(run_id="r", day="sun")
    rows = {row["loc_id"]: row for row in build_reopen_rows(_locations(), state)}
    assert rows[2]["awp_count"] == 1
    assert rows[2]["yssr_count"] == 2
    assert rows[2]["vol_count"] == 0
    assert rows[3]["vol_count"] == 4
    assert rows[3]["yssr_count"] == 0
    assert "pass_count" not in rows[2]
    assert rows[2]["loc_start"] == "06:30:00"
    assert rows[2]["first_runner"] == "07:20:10"
    assert rows[2]["last_runner"] == "08:40:00"
    assert rows[2]["loc_end"] == "08:50"
    assert rows[2]["actual_reopen"] == ""
    assert rows[2]["difference_min"] == ""
    assert rows[3]["loc_end"] == "10:15"


def test_difference_min_is_actual_minus_estimate():
    state = empty_state(run_id="r", day="sun")
    record_reopen(state, loc_id=2, linked_loc_ids=[], at_hhmm="09:05")
    rows = {row["loc_id"]: row for row in build_reopen_rows(_locations(), state)}
    assert rows[2]["actual_reopen"] == "09:05"
    assert rows[2]["difference_min"] == 15
    assert rows[3]["actual_reopen"] == ""
    assert rows[3]["difference_min"] == ""


def test_csv_uses_display_loc_end_after_gun_shift():
    state = empty_state(run_id="r", day="sun")
    state["clock"]["guns_accepted"] = True
    state["clock"]["analysis_guns"] = {"10k": "07:15"}
    state["clock"]["guns"] = {"10k": "07:20"}
    record_reopen(state, loc_id=2, linked_loc_ids=[], at_hhmm="09:00")
    rows = {row["loc_id"]: row for row in build_reopen_rows(_locations(), state)}
    assert rows[2]["loc_end"] == "08:55"
    assert rows[2]["difference_min"] == 5


def test_csv_text_has_count_columns_after_label():
    state = empty_state(run_id="r", day="sun")
    locations = _locations()
    columns = csv_columns(locations)
    assert columns[:5] == [
        "loc_id",
        "loc_label",
        "awp_count",
        "vol_count",
        "yssr_count",
    ]
    assert "pass_count" not in columns
    text = reopen_csv_text(build_reopen_rows(locations, state), columns)
    header = text.split("\n", 1)[0]
    assert header == ",".join(columns)


def _patch_run(monkeypatch, tmp_path: Path, run_id: str) -> Path:
    monkeypatch.setattr(
        "app.utils.run_id.get_run_directory",
        lambda rid: tmp_path / "analysis" / rid,
    )
    return tmp_path / "analysis" / run_id


def _seed_run(run_dir: Path, run_id: str) -> None:
    day = run_dir / "sun"
    comp = day / "computation"
    comp.mkdir(parents=True)
    doc = build_locations_report_document(
        run_id=run_id,
        day="sun",
        locations=_locations(),
        resources_available=["yssr", "awp", "vol"],
    )
    (comp / "locations_report.json").write_text(
        json.dumps(doc), encoding="utf-8"
    )
    (run_dir / "analysis.json").write_text(
        json.dumps({"start_times": {"10k": 435}}),
        encoding="utf-8",
    )


def test_api_reopen_csv_requires_run_id():
    client = TestClient(app)
    resp = client.get("/api/execute/reopen.csv")
    assert resp.status_code == 400


def test_api_reopen_csv_download(tmp_path, monkeypatch):
    run_id = "exec898csvbbbbbbbbbbbb"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    _seed_run(run_dir, run_id)
    client = TestClient(app)
    client.post(
        f"/api/execute/reopen?run_id={run_id}&day=sun",
        json={"loc_id": 2, "linked_loc_ids": []},
    )
    resp = client.get(f"/api/execute/reopen.csv?run_id={run_id}&day=sun")
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    assert "execute_reopen_" in resp.headers["content-disposition"]
    lines = resp.text.strip().split("\n")
    assert lines[0] == (
        "loc_id,loc_label,awp_count,vol_count,yssr_count,"
        "loc_start,first_runner,last_runner,loc_end,"
        "actual_reopen,difference_min"
    )
    queen = [line for line in lines if line.startswith("2,")][0]
    assert queen.startswith("2,St John at Queen,1,0,2,")
    assert "06:30:00" in queen
    assert "07:20:10" in queen
    assert "08:40:00" in queen
    water = [line for line in lines if line.startswith("3,")][0]
    assert water.endswith(",")


def test_execute_js_points_at_reopen_csv():
    js = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "static"
        / "js"
        / "execute_board.js"
    ).read_text(encoding="utf-8")
    assert "/api/execute/reopen.csv" in js
    assert "syncExportLink" in js
