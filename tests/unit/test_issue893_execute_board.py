"""Issue #893: Execute board columns, gun overlay, and execution JSON."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.execute.board import assemble_board, reopen_next_ids, zone_code
from app.core.execute.state import (
    empty_state,
    record_reopen,
    apply_clock_update,
    persist_state,
    execution_state_relpath,
)
from app.core.execute.times import (
    display_loc_end_minutes,
    estimate_passed,
    gun_deltas_minutes,
    parse_hhmm,
)
from app.core.locations.report_json import build_locations_report_document
from app.main import app
from app.storage import Storage


def _locations():
    return [
        {
            "loc_id": 2,
            "loc_label": "St John at Queen",
            "loc_type": "course",
            "loc_end": "08:50:00",
            "zone": 1,
            "yssr_count": 2,
            "awp_count": 0,
            "by_event": {"10k": {"last_runner": "08:40:00"}},
        },
        {
            "loc_id": 8,
            "loc_label": "Queen at Waterloo",
            "loc_type": "traffic",
            "loc_end": "08:50:00",
            "yssr_count": 1,
            "proxy_loc_id": 2,
            "proxy_pass_id": 83,
        },
        {
            "loc_id": 9,
            "loc_label": "Maple at Ring Road",
            "loc_type": "traffic",
            "loc_end": "09:00:00",
            "fpf_count": 1,
            "proxy_loc_id": 95,
        },
        {
            "loc_id": 3,
            "loc_label": "Water Stop (Full Loop)",
            "loc_type": "water",
            "loc_end": "10:15:00",
            "vol_count": 4,
        },
        {
            "loc_id": 99,
            "loc_label": "Untimed pin",
            "loc_type": "official",
            "loc_end": None,
            "ofc_count": 1,
        },
    ]


def test_reopen_next_is_earliest_fifteen_minute_queue():
    closed = [
        {"loc_id": 1, "loc_end": "08:50"},
        {"loc_id": 2, "loc_end": "08:50"},
        {"loc_id": 3, "loc_end": "08:55"},
        {"loc_id": 4, "loc_end": "09:00"},
        {"loc_id": 5, "loc_end": "09:05"},
        {"loc_id": 6, "loc_end": None},
    ]
    expected = {1, 2, 3, 4, 5}
    assert reopen_next_ids(closed, "08:00:00") == expected
    assert 6 not in reopen_next_ids(closed, "08:00:00")


def test_reopen_next_follows_clock_once_estimates_pass():
    closed = [
        {"loc_id": 1, "loc_end": "08:50"},
        {"loc_id": 2, "loc_end": "09:05"},
        {"loc_id": 3, "loc_end": "10:15"},
        {"loc_id": 4, "loc_end": None},
    ]
    assert reopen_next_ids(closed, "08:00:00") == {1, 2}
    assert reopen_next_ids(closed, "14:29:00") == {1, 2, 3}
    assert 4 not in reopen_next_ids(closed, "14:29:00")


def test_zone_code_formats_z_prefix():
    assert zone_code(3) == "Z3"
    assert zone_code(3.0) == "Z3"
    assert zone_code("1") == "Z1"
    assert zone_code("Z2") == "Z2"
    assert zone_code(None) is None
    assert zone_code("") is None


def test_missing_loc_end_stays_closed_after_timed():
    state = empty_state(run_id="r", day="sun")
    state["clock"]["guns_accepted"] = True
    board = assemble_board(
        locations=_locations(),
        state=state,
        resources_available=["yssr", "awp", "fpf", "vol", "ofc", "pass"],
        run_id="r",
        day="sun",
        now_hhmmss="08:48:00",
    )
    next_ids = [row["loc_id"] for row in board["columns"]["reopen_next"]]
    closed_ids = [row["loc_id"] for row in board["columns"]["closed"]]
    assert 2 in next_ids
    queen = next(
        row for row in board["columns"]["reopen_next"] if row["loc_id"] == 2
    )
    assert queen["zone"] == "Z1"
    assert 8 in next_ids
    assert 9 in next_ids
    assert 3 in closed_ids
    assert 99 in closed_ids
    assert closed_ids[-1] == 99
    assert board["counts"]["reopened"] == 0


def test_reopened_column_is_activity_order_not_clock_string():
    """HH:MM reverse-sort would put 15:01 above a later 11:25 reopen."""
    state = empty_state(run_id="r", day="sun")
    state["clock"]["guns_accepted"] = True
    record_reopen(state, loc_id=3, linked_loc_ids=[], at_hhmm="15:01")
    record_reopen(state, loc_id=99, linked_loc_ids=[], at_hhmm="08:46")
    record_reopen(state, loc_id=2, linked_loc_ids=[8], at_hhmm="11:25")
    board = assemble_board(
        locations=_locations(),
        state=state,
        resources_available=["yssr", "fpf", "vol", "ofc"],
        run_id="r",
        day="sun",
        now_hhmmss="11:26:00",
    )
    ids = [row["loc_id"] for row in board["columns"]["reopened"]]
    assert set(ids[:2]) == {2, 8}
    assert ids[2:] == [99, 3]
    assert board["columns"]["reopened"][0]["reopened_at"] == "11:25"


def test_elapsed_time_never_auto_reopens():
    state = empty_state(run_id="r", day="sun")
    state["clock"]["guns_accepted"] = True
    board = assemble_board(
        locations=_locations(),
        state=state,
        resources_available=["yssr", "fpf", "vol"],
        run_id="r",
        day="sun",
        now_hhmmss="12:00:00",
    )
    assert board["counts"]["reopened"] == 0
    next_ids = {row["loc_id"] for row in board["columns"]["reopen_next"]}
    closed_ids = {row["loc_id"] for row in board["columns"]["closed"]}
    assert next_ids == {2, 8, 9, 3}
    assert 99 in closed_ids
    next_row = board["columns"]["reopen_next"][0]
    assert next_row["estimate_passed"] is True
    assert next_row["status"] == "reopen_next"


def test_resource_codes_only_nonzero_and_skip_pass():
    state = empty_state(run_id="r", day="sun")
    board = assemble_board(
        locations=_locations(),
        state=state,
        resources_available=["yssr", "pass", "vol"],
        run_id="r",
        day="sun",
        now_hhmmss="08:50:00",
    )
    queen = next(
        row
        for row in board["columns"]["reopen_next"]
        if row["loc_id"] == 2
    )
    assert queen["resources"] == [{"code": "YSSR", "count": 2}]
    assert "pass" not in board["resource_codes"]
    assert queen["map_href"] == "/locations?run_id=r&loc_id=2"


def test_linked_locations_are_proxy_reverse_index():
    state = empty_state(run_id="r", day="sun")
    board = assemble_board(
        locations=_locations(),
        state=state,
        resources_available=["yssr"],
        run_id="r",
        day="sun",
        now_hhmmss="08:50:00",
    )
    queen = next(
        row
        for row in board["columns"]["reopen_next"]
        if row["loc_id"] == 2
    )
    assert [row["loc_id"] for row in queen["linked"]] == [8]


def test_gun_shift_uses_controlling_event():
    row = {
        "loc_end": "08:55:00",
        "by_event": {
            "10k": {"last_runner": "08:10:00"},
            "full": {"last_runner": "08:40:00"},
        },
    }
    deltas = gun_deltas_minutes(
        {"10k": "07:15", "full": "07:00"},
        {"10k": "07:20", "full": "07:00"},
    )
    assert deltas["10k"] == 5
    assert deltas["full"] == 0
    # latest last_runner is full → no shift
    assert display_loc_end_minutes(row, deltas) == parse_hhmm("08:55")
    deltas_full = gun_deltas_minutes(
        {"10k": "07:15", "full": "07:00"},
        {"10k": "07:15", "full": "07:10"},
    )
    assert display_loc_end_minutes(row, deltas_full) == parse_hhmm("09:05")


def test_record_reopen_writes_null_operator_and_skips_already_open():
    state = empty_state(run_id="r", day="sun")
    first = record_reopen(
        state, loc_id=2, linked_loc_ids=[8], at_hhmm="12:49"
    )
    assert first["applied"] == [2, 8]
    assert state["reopened"]["2"]["operator"] is None
    assert state["reopened"]["2"]["reopened_at"] == "12:49"
    assert state["reopened"]["8"]["linked_from"] == 2
    second = record_reopen(
        state, loc_id=2, linked_loc_ids=[8], at_hhmm="12:50"
    )
    assert second["already_reopened"] is True
    assert second["applied"] == []
    assert state["reopened"]["2"]["reopened_at"] == "12:49"
    assert len(state["activity"]) == 1


def test_pause_freezes_display_now_without_reopening():
    state = empty_state(run_id="r", day="sun")
    apply_clock_update(state, {"paused": True}, now_hhmmss="08:12:00")
    assert state["clock"]["paused"] is True
    assert state["clock"]["paused_at"] == "08:12:00"
    apply_clock_update(
        state, {"jump_to_now": True, "paused": False}, now_hhmmss="08:20:00"
    )
    assert state["clock"]["paused"] is False
    assert state["clock"]["paused_at"] is None


def test_estimate_passed_helper():
    assert estimate_passed(parse_hhmm("08:50"), "08:50:00") is True
    assert estimate_passed(parse_hhmm("08:50"), "08:49:59") is False
    assert estimate_passed(None, "08:50:00") is False


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
        resources_available=["yssr", "fpf", "vol", "ofc"],
    )
    (comp / "locations_report.json").write_text(
        json.dumps(doc), encoding="utf-8"
    )
    (run_dir / "analysis.json").write_text(
        json.dumps(
            {
                "start_times": {"full": 420, "half": 460, "10k": 435},
                "events": [
                    {"name": "full", "start_time": 420},
                    {"name": "10k", "start_time": 435},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_api_requires_run_id():
    client = TestClient(app)
    resp = client.get("/api/execute/board")
    assert resp.status_code == 400


def test_api_board_and_reopen_persist_json(tmp_path, monkeypatch):
    run_id = "exec893boardaaaaaaaaaaa"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    _seed_run(run_dir, run_id)
    client = TestClient(app)
    board = client.get(f"/api/execute/board?run_id={run_id}&day=sun")
    assert board.status_code == 200, board.text
    body = board.json()
    assert body["ok"] is True
    assert body["counts"]["reopened"] == 0
    next_ids = {row["loc_id"] for row in body["columns"]["reopen_next"]}
    assert 2 in next_ids

    reopen = client.post(
        f"/api/execute/reopen?run_id={run_id}&day=sun",
        json={"loc_id": 2, "linked_loc_ids": [8]},
    )
    assert reopen.status_code == 200, reopen.text
    after = reopen.json()
    reopened_ids = {row["loc_id"] for row in after["columns"]["reopened"]}
    assert reopened_ids == {2, 8}
    assert all(row["operator"] is None for row in after["columns"]["reopened"])

    stored = json.loads(
        (run_dir / "sun" / "execution" / "state.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored["reopened"]["2"]["reopened_at"]
    assert stored["reopened"]["2"]["operator"] is None

    dup = client.post(
        f"/api/execute/reopen?run_id={run_id}&day=sun",
        json={"loc_id": 2, "linked_loc_ids": []},
    )
    assert dup.status_code == 409


def test_api_rejects_unlinked_proxy(tmp_path, monkeypatch):
    run_id = "exec893unlinkaaaaaaaaaa"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    _seed_run(run_dir, run_id)
    client = TestClient(app)
    resp = client.post(
        f"/api/execute/reopen?run_id={run_id}&day=sun",
        json={"loc_id": 2, "linked_loc_ids": [9]},
    )
    assert resp.status_code == 400


def test_clock_accept_persists_guns(tmp_path, monkeypatch):
    run_id = "exec893clockaaaaaaaaaaa"
    run_dir = _patch_run(monkeypatch, tmp_path, run_id)
    _seed_run(run_dir, run_id)
    client = TestClient(app)
    resp = client.put(
        f"/api/execute/clock?run_id={run_id}&day=sun",
        json={
            "guns_accepted": True,
            "guns": {"10k": "07:20", "full": "07:00"},
        },
    )
    assert resp.status_code == 200, resp.text
    clock = resp.json()["clock"]
    assert clock["guns_accepted"] is True
    assert clock["guns"]["10k"] == "07:20"
    storage = Storage(root=str(run_dir))
    assert storage.exists(execution_state_relpath("sun"))


def test_persist_state_helper(tmp_path):
    storage = Storage(root=str(tmp_path))
    state = empty_state(run_id="r", day="sun")
    persist_state(storage, "sun", state)
    loaded = storage.read_json(execution_state_relpath("sun"))
    assert loaded["schema_version"] == 1
    assert loaded["reopened"] == {}
