"""Issue #864: Plan Progression map — spatial race clock, Front/Tail v1."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.motion.persist import build_and_persist_motion_for_day
from app.core.progression.payload import (
    PROGRESSION_MODEL_LABEL,
    ProgressionNotFound,
    build_progression_field,
    build_progression_setup,
    course_active_windows,
    downsample_polyline,
    order_progression_events,
    select_midpack,
)
from app.core.trajectory.crossing import arrival_at_km, elapsed_km_at
from app.core.v2.models import Day, Event
from app.utils.constants import DISPLAY_TIMEZONE, PROGRESSION_POLYLINE_MAX_POINTS

REPO_ROOT = Path(__file__).resolve().parents[2]


def _tiny_gpx(path: Path, *, n: int = 21) -> None:
    lines = [
        '<?xml version="1.0"?>',
        '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">',
        "<trk><name>test</name><trkseg>",
    ]
    for i in range(n):
        lat = 45.0 + i * 0.0009
        lon = -66.0
        lines.append(f'<trkpt lat="{lat}" lon="{lon}"></trkpt>')
    lines.append("</trkseg></trk></gpx>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_analysis(run_dir: Path, data_dir: Path, *, gun_minutes: int = 435) -> None:
    payload = {
        "data_dir": str(data_dir),
        "start_times": {"10k": gun_minutes},
        "data_files": {
            "gpx": {"10k": str(data_dir / "10k.gpx")},
            "segments": str(data_dir / "segments.csv"),
        },
        "events": [
            {
                "name": "10k",
                "day": "sun",
                "start_time": gun_minutes,
                "gpx_file": str(data_dir / "10k.gpx"),
            }
        ],
    }
    (run_dir / "analysis.json").write_text(json.dumps(payload), encoding="utf-8")


def _make_run(tmp_path: Path, *, gpx_points: int = 21) -> tuple[str, Path, Path]:
    data_dir = tmp_path / "pkg"
    data_dir.mkdir()
    gpx = data_dir / "10k.gpx"
    _tiny_gpx(gpx, n=gpx_points)
    runners_path = data_dir / "10k_runners.csv"
    runners_path.write_text(
        "event,runner_id,pace,distance,start_offset\n"
        "10k,r1,5.0,2.0,0\n"
        "10k,r2,6.0,2.0,5\n",
        encoding="utf-8",
    )
    segments = pd.DataFrame(
        [
            {
                "seg_id": "S1",
                "10k": "y",
                "10k_from_km": 0.0,
                "10k_to_km": 1.0,
                "full": "n",
                "half": "n",
            },
            {
                "seg_id": "S2",
                "10k": "y",
                "10k_from_km": 1.0,
                "10k_to_km": 2.0,
                "full": "n",
                "half": "n",
            },
        ]
    )
    segments.to_csv(data_dir / "segments.csv", index=False)
    runners = pd.read_csv(runners_path)
    event = Event(
        name="10k",
        day=Day.SUN,
        start_time=7 * 60 + 15,
        gpx_file=str(gpx),
        runners_file=str(runners_path),
    )
    run_id = "progTestRun01"
    run_dir = tmp_path / "analysis" / run_id
    run_dir.mkdir(parents=True)
    day_path = run_dir / "sun"
    build_and_persist_motion_for_day(
        day_path=day_path,
        day_code="sun",
        day_events=[event],
        runners_df=runners,
        segments_df=segments,
        gpx_paths={"10k": str(gpx)},
        runner_csv_paths={"10k": str(runners_path)},
        package_id="pkg-test",
        course_json_path=None,
    )
    _write_analysis(run_dir, data_dir)
    return run_id, run_dir, day_path


def test_elapsed_km_at_is_inverse_of_arrival():
    gun = 7 * 3600 + 15 * 60
    km = 1.25
    t = arrival_at_km(
        gun_sec=gun,
        start_offset_sec=5.0,
        pace_min_per_km=5.0,
        km=km,
    )
    status, got = elapsed_km_at(
        t_sec=t,
        gun_sec=gun,
        start_offset_sec=5.0,
        pace_min_per_km=5.0,
        finish_km=2.0,
    )
    assert status == "on_course"
    assert got == pytest.approx(km)

    status, got = elapsed_km_at(
        t_sec=gun,
        gun_sec=gun,
        start_offset_sec=10.0,
        pace_min_per_km=5.0,
        finish_km=2.0,
    )
    assert status == "not_started"
    assert got == 0.0

    finish_t = arrival_at_km(
        gun_sec=gun,
        start_offset_sec=0.0,
        pace_min_per_km=5.0,
        km=2.0,
    )
    status, got = elapsed_km_at(
        t_sec=finish_t + 1,
        gun_sec=gun,
        start_offset_sec=0.0,
        pace_min_per_km=5.0,
        finish_km=2.0,
    )
    assert status == "finished"
    assert got == pytest.approx(2.0)


def test_downsample_keeps_endpoints_and_cap():
    n = 800
    points = [(45.0 + i * 0.0001, -66.0) for i in range(n)]
    cum = [i * 0.01 for i in range(n)]
    out = downsample_polyline(points, cum, max_points=400, finish_km=10.0)
    assert 2 <= len(out) <= 400
    assert out[0][0] == pytest.approx(points[0][0])
    assert out[-1][2] >= 10.0 or out[-1][2] == pytest.approx(cum[-1])
    assert all(len(row) == 3 for row in out)


def test_setup_and_field_from_snapshot(tmp_path: Path):
    _run_id, run_dir, _day_path = _make_run(tmp_path)
    setup = build_progression_setup(run_dir, "sun")
    field = build_progression_field(run_dir, "sun")

    assert setup["ok"] is True
    assert setup["timezone"] == DISPLAY_TIMEZONE
    assert setup["model"]["label"] == PROGRESSION_MODEL_LABEL
    assert setup["model"]["time_source"] == "modeled_constant_pace"
    gun = (7 * 60 + 15) * 60
    assert setup["t0_sec"] == gun
    assert setup["t1_sec"] > setup["t0_sec"]
    assert len(setup["events"]) == 1
    ev = setup["events"][0]
    assert ev["id"] == "10k"
    assert ev["gun_sec"] == gun
    assert ev["finish_km"] == pytest.approx(2.0)
    assert ev["color"].startswith("#")
    assert ev["active_start_sec"] == gun
    assert ev["active_end_sec"] == setup["t1_sec"]
    assert ev["active_end_sec"] > ev["active_start_sec"]
    assert ev["midpack_id"] == "r1"
    assert ev["midpack_finish_sec"] == gun + 600
    assert 2 <= len(ev["polyline"]) <= PROGRESSION_POLYLINE_MAX_POINTS
    assert ev["polyline"][0][0] == pytest.approx(45.0, abs=1e-6)

    ids = {r["id"] for r in field["runners"]}
    assert ids == {"r1", "r2"}
    assert all("start_offset_sec" in r and "pace_min_per_km" in r for r in field["runners"])
    # Whole field — not a Front/Tail id list.
    assert "front" not in field
    assert "tail" not in field


def test_missing_snapshot_is_not_found(tmp_path: Path):
    run_dir = tmp_path / "analysis" / "emptyRun0001"
    run_dir.mkdir(parents=True)
    (run_dir / "sun").mkdir()
    (run_dir / "analysis.json").write_text(
        json.dumps({"data_dir": str(tmp_path), "start_times": {"10k": 420}}),
        encoding="utf-8",
    )
    with pytest.raises(ProgressionNotFound):
        build_progression_setup(run_dir, "sun")


def test_front_tail_from_field_at_clock(tmp_path: Path):
    _run_id, run_dir, _ = _make_run(tmp_path)
    setup = build_progression_setup(run_dir, "sun")
    field = build_progression_field(run_dir, "sun")
    ev = setup["events"][0]
    t = ev["gun_sec"] + 300  # 5 minutes after gun
    on_course = []
    for r in field["runners"]:
        status, km = elapsed_km_at(
            t_sec=t,
            gun_sec=ev["gun_sec"],
            start_offset_sec=r["start_offset_sec"],
            pace_min_per_km=r["pace_min_per_km"],
            finish_km=ev["finish_km"],
        )
        if status == "on_course":
            on_course.append((r["id"], km))
    assert {row[0] for row in on_course} == {"r1", "r2"}
    front = max(on_course, key=lambda row: row[1])
    tail = min(on_course, key=lambda row: row[1])
    assert front[0] == "r1"
    assert tail[0] == "r2"
    assert front[1] == pytest.approx(1.0)  # 5 min at 5 min/km


def test_api_setup_and_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_id, run_dir, _ = _make_run(tmp_path, gpx_points=50)

    def _run_day(rid, day):
        return run_id, "sun", ["sun"], run_dir

    monkeypatch.setattr("app.api.progression._run_day", _run_day)
    app = FastAPI()
    from app.api.progression import router

    app.include_router(router)
    client = TestClient(app)
    setup = client.get(f"/api/runs/{run_id}/progression/setup")
    assert setup.status_code == 200, setup.text
    body = setup.json()
    assert body["run_id"] == run_id
    assert body["events"][0]["polyline"]
    field = client.get(f"/api/runs/{run_id}/progression/field")
    assert field.status_code == 200
    assert len(field.json()["runners"]) == 2


def test_api_404_without_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_dir = tmp_path / "analysis" / "noSnapRun001"
    run_dir.mkdir(parents=True)
    (run_dir / "sun").mkdir()
    (run_dir / "analysis.json").write_text(
        json.dumps({"data_dir": str(tmp_path), "start_times": {"10k": 420}}),
        encoding="utf-8",
    )

    def _run_day(rid, day):
        return "noSnapRun001", "sun", ["sun"], run_dir

    monkeypatch.setattr("app.api.progression._run_day", _run_day)
    app = FastAPI()
    from app.api.progression import router

    app.include_router(router)
    client = TestClient(app)
    res = client.get("/api/runs/noSnapRun001/progression/setup")
    assert res.status_code == 404


def test_page_and_js_are_lead_last_only():
    page = (REPO_ROOT / "frontend" / "templates" / "pages" / "progression.html").read_text(
        encoding="utf-8"
    )
    js = (REPO_ROOT / "frontend" / "static" / "js" / "map" / "progression.js").read_text(
        encoding="utf-8"
    )
    assert "Modeled runner progression on the analysis clock" in page
    assert "not GPS" not in page
    assert "provenance" not in page
    assert page.find('id="progression-map"') < page.find('id="progression-legend"')
    assert page.find('id="progression-legend"') < page.find('id="progression-clock"')
    assert page.find('id="progression-scrub"') < page.find('id="progression-wallboard"')
    assert "quintile" not in js.lower()
    assert "lead pack" not in js.lower()
    assert "full-field" not in js.lower() and "full field" not in js.lower()
    assert "frontTailByEvent" in js
    assert "frontGone" in js
    assert "computeMainOffsetCaps" in js
    assert "elapsedKmAt" in js
    assert '"setup"' in js and '"field"' in js
    assert "/progression/" in js
    assert "progression.js?v=885d" in page
    assert "Lead" in js and "Last" in js
    assert "Mid-pack" in js
    assert "glyphForRoles" in js
    assert "midpack_id" in js
    assert "halfFillIcon" in js
    assert "progression-wallboard-midpack" not in js
    assert "diamondIcon" not in js
    assert "eventLabel" in js
    assert 'id="progression-playpause"' in page
    assert 'id="progression-reset"' in page
    assert 'id="progression-pause"' not in page
    assert 'id="progression-stop"' not in page
    assert page.count('class="course-map-action-btn"') == 2
    assert "renderWallboard" in js
    assert "progression-wallboard-seek" in js
    assert "progression-wallboard-tick-mark" in js
    assert "First modeled start" in js
    assert "Last modeled finish" in js
    assert "active_start_sec" in js


def test_course_active_window_includes_late_finishers():
    gun = 7 * 3600 + 20 * 60
    finish_km = 21.1
    runners = [
        {
            "event": "half",
            "start_offset_sec": 0.0,
            "pace_min_per_km": 4.5,
        },
        {
            "event": "half",
            "start_offset_sec": 3347.0,
            "pace_min_per_km": 6.0,
        },
    ]
    windows = course_active_windows(
        runners,
        {"half": gun},
        {"half": finish_km},
    )
    start, end = windows["half"]
    assert start == gun
    late_finish = arrival_at_km(
        gun_sec=gun,
        start_offset_sec=3347.0,
        pace_min_per_km=6.0,
        km=finish_km,
    )
    early_finish = arrival_at_km(
        gun_sec=gun,
        start_offset_sec=0.0,
        pace_min_per_km=4.5,
        km=finish_km,
    )
    assert end == int(late_finish)
    assert end > int(early_finish)


def test_midpack_is_p50_of_all_finishers_not_main_wave():
    gun = 7 * 3600 + 20 * 60
    finish_km = 10.0
    runners = [
        {"id": "a", "event": "half", "start_offset_sec": 0.0, "pace_min_per_km": 4.0},
        {"id": "b", "event": "half", "start_offset_sec": 0.0, "pace_min_per_km": 5.0},
        {"id": "c", "event": "half", "start_offset_sec": 0.0, "pace_min_per_km": 6.0},
        {"id": "late", "event": "half", "start_offset_sec": 3000.0, "pace_min_per_km": 8.0},
    ]
    # n=4 → floor(0.50 * 3) = 1 → second-fastest finish = b (5 min/km).
    mid = select_midpack(runners, gun_sec=gun, finish_km=finish_km)
    assert mid["id"] == "b"
    assert mid["finish_sec"] == int(
        arrival_at_km(
            gun_sec=gun,
            start_offset_sec=0.0,
            pace_min_per_km=5.0,
            km=finish_km,
        )
    )
    even_two = select_midpack(runners[:2], gun_sec=gun, finish_km=finish_km)
    assert even_two["id"] == "a"


def test_progression_events_ordered_by_earliest_modeled_start():
    windows = {
        "10k": (27600, 36000),
        "full": (25200, 46500),
        "half": (26400, 40800),
    }
    analysis = {
        "events": [
            {"name": "10k"},
            {"name": "half"},
            {"name": "full"},
        ]
    }
    assert order_progression_events(
        ["10k", "full", "half"], windows, analysis
    ) == ["full", "half", "10k"]


def test_progression_event_order_tie_breaks_on_package_order_not_distance():
    windows = {
        "10k": (25200, 30000),
        "full": (25200, 40000),
        "half": (25200, 35000),
    }
    analysis = {
        "events": [
            {"name": "10k"},
            {"name": "half"},
            {"name": "full"},
        ]
    }
    assert order_progression_events(
        ["full", "half", "10k"], windows, analysis
    ) == ["10k", "half", "full"]
