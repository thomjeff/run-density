"""Execute clock snapshot (Issue #830 v1)."""

from app.core.execute.clock import (
    attach_clock_status,
    build_execute_snapshot,
    classify_reopen_status,
    guns_for_day,
    parse_clock_sec,
)


def test_parse_clock_sec():
    assert parse_clock_sec("08:20:15") == 8 * 3600 + 20 * 60 + 15
    assert parse_clock_sec("07:15") == 7 * 3600 + 15 * 60
    assert parse_clock_sec(100) == 100
    assert parse_clock_sec(None) is None


def test_classify_reopen_status():
    assert classify_reopen_status(10, 9) == "closed"
    assert classify_reopen_status(10, 10) == "open"
    assert classify_reopen_status(10, 11) == "open"
    assert classify_reopen_status(None, 10) == "unknown"
    assert classify_reopen_status(10, None) == "unknown"


def test_guns_for_day_filters_and_sorts():
    analysis = {
        "events": [
            {"name": "10k", "day": "sun", "start_time": 435},
            {"name": "full", "day": "sun", "start_time": 420},
            {"name": "half", "day": "sat", "start_time": 400},
        ]
    }
    guns = guns_for_day(analysis, "sun")
    assert [g["event"] for g in guns] == ["full", "10k"]
    assert guns[0]["start_hhmmss"] == "07:00:00"


def test_snapshot_marks_closed_and_next():
    playbook = {
        "clear_when": "last_runner",
        "run_id": "abc",
        "entries": [
            {
                "rule_id": "early",
                "blocked": {"kind": "location", "id": "1", "label": "A"},
                "reopen_at": "08:00:00",
                "reopen_at_sec": 8 * 3600,
            },
            {
                "rule_id": "late",
                "blocked": {"kind": "location", "id": "2", "label": "B"},
                "reopen_at": "09:00:00",
                "reopen_at_sec": 9 * 3600,
            },
        ],
    }
    snap = build_execute_snapshot(
        playbook=playbook,
        analysis={"events": [{"name": "10k", "day": "sun", "start_time": 420}]},
        day="sun",
        now_sec=8 * 3600 + 30 * 60,
    )
    by_id = {e["rule_id"]: e for e in snap["entries"]}
    assert by_id["early"]["status"] == "open"
    assert by_id["late"]["status"] == "closed"
    assert snap["next"]["rule_id"] == "late"
    assert snap["guns"][0]["event"] == "10k"
    assert snap["window"]["start_hhmmss"] == "07:00:00"
