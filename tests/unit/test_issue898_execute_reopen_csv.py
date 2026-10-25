"""Issue #898: Execute reopen variance CSV."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.execute.report import (
    build_reopen_rows,
    csv_columns,
    reopen_csv_text,
)
from app.core.execute.state import empty_state, record_reopen
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


def test_leftover_reopen_csv_route_is_gone():
    client = TestClient(app)
    assert client.get("/api/execute/reopen.csv").status_code == 404
    assert client.get("/api/execute/reopen").status_code == 404


def test_execute_ops_reopen_csv_route_stays():
    routes = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "routes"
        / "api_published_plans.py"
    ).read_text(encoding="utf-8")
    assert '/api/execute/ops/reopen.csv' in routes
