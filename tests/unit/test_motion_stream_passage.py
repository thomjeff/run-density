"""Unit tests for Motion Stream Passage (#855)."""

from __future__ import annotations

import pandas as pd

from app.core.motion.occupancy import PinPlace
from app.core.motion.stream_passage import (
    build_stream_passage_table,
    build_visit_summary,
    pair_visit_episodes,
    planar_crossing_events,
)
from app.utils.constants import MOTION_STREAM_WINDOW_SEC, MOTION_VISIT_KM_GAP


def _pin() -> PinPlace:
    return PinPlace(lat=45.0, lon=-66.0, radius_m=30.0, place_id="44", label="Cliffe")


def test_stream_passage_bins_enters_by_event_with_km_context():
    # ~0.00005 deg ≈ 5.5 m (inside); 0.001 ≈ 111 m (outside)
    samples = pd.DataFrame(
        [
            # r1 10k enters at t=27005 (07:30:05) → bin 07:30
            {"runner_id": "r1", "event": "10k", "t": 27000, "lat": 45.001, "lon": -66.0, "elapsed_km": 3.10},
            {"runner_id": "r1", "event": "10k", "t": 27005, "lat": 45.00005, "lon": -66.0, "elapsed_km": 3.21},
            {"runner_id": "r1", "event": "10k", "t": 27015, "lat": 45.001, "lon": -66.0, "elapsed_km": 3.30},
            # r2 half enters same 5-min bin
            {"runner_id": "r2", "event": "half", "t": 27000, "lat": 45.001, "lon": -66.0, "elapsed_km": 3.00},
            {"runner_id": "r2", "event": "half", "t": 27100, "lat": 45.00005, "lon": -66.0, "elapsed_km": 3.22},
            # r3 full enters next bin 07:35
            {"runner_id": "r3", "event": "full", "t": 27295, "lat": 45.001, "lon": -66.0, "elapsed_km": 17.40},
            {"runner_id": "r3", "event": "full", "t": 27305, "lat": 45.00005, "lon": -66.0, "elapsed_km": 17.54},
        ]
    )
    out = build_stream_passage_table(
        samples,
        _pin(),
        window_sec=MOTION_STREAM_WINDOW_SEC,
    )
    assert out["mode"] == "stream_passage"
    assert out["events"] == ["10k", "full", "half"]
    assert out["legend"] == "10k / full / half"
    assert len(out["rows"]) == 2

    first = out["rows"][0]
    assert first["t0"] == 27000
    assert first["label"].startswith("07:30")
    assert first["enters_by_event"]["10k"] == 1
    assert first["enters_by_event"]["half"] == 1
    assert first["enters_by_event"]["full"] == 0
    assert first["enter_elapsed_km_by_event"]["10k"] == 3.21
    assert "10k 3.21:1" in first["context"]
    assert "half 3.22:1" in first["context"]
    assert first["enters_by_visit"]

    second = out["rows"][1]
    assert second["t0"] == 27300
    assert second["enters_by_event"]["full"] == 1
    assert second["enter_elapsed_km_by_event"]["full"] == 17.54

    assert out["totals"]["enters_by_event"]["10k"] == 1
    assert out["totals"]["enters_by_event"]["full"] == 1
    assert out["totals"]["passages_by_event"]["10k"] == 1
    assert out["visit_km_gap"] == MOTION_VISIT_KM_GAP
    # Incomplete exits still yield visit rows from paired episodes only —
    # r1 has enter+exit; r2/r3 enter without exit in fixture → not in summary
    assert any(v["event"] == "10k" for v in out["visit_summary"])


def test_planar_crossing_respects_span():
    samples = pd.DataFrame(
        [
            {"runner_id": "r1", "event": "10k", "t": 100, "lat": 45.001, "lon": -66.0, "elapsed_km": 1.0},
            {"runner_id": "r1", "event": "10k", "t": 105, "lat": 45.00005, "lon": -66.0, "elapsed_km": 1.1},
            {"runner_id": "r1", "event": "10k", "t": 200, "lat": 45.001, "lon": -66.0, "elapsed_km": 1.2},
            {"runner_id": "r1", "event": "10k", "t": 205, "lat": 45.00005, "lon": -66.0, "elapsed_km": 1.3},
        ]
    )
    crosses = planar_crossing_events(samples, _pin(), t0=150, t1=300)
    enters = crosses[crosses.kind == "enter"]
    assert len(enters) == 1
    assert int(enters.iloc[0]["t"]) == 205


def test_pair_visit_episodes_and_multi_km_clusters():
    """George-shaped: one full runner, three distinct passages at the pin."""
    samples = pd.DataFrame(
        [
            # visit ~20.61
            {"runner_id": "f1", "event": "full", "t": 30000, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.50},
            {"runner_id": "f1", "event": "full", "t": 30005, "lat": 45.00005, "lon": -66.0, "elapsed_km": 20.61},
            {"runner_id": "f1", "event": "full", "t": 30025, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.68},
            # visit ~22.70
            {"runner_id": "f1", "event": "full", "t": 30700, "lat": 45.001, "lon": -66.0, "elapsed_km": 22.60},
            {"runner_id": "f1", "event": "full", "t": 30705, "lat": 45.00005, "lon": -66.0, "elapsed_km": 22.70},
            {"runner_id": "f1", "event": "full", "t": 30725, "lat": 45.001, "lon": -66.0, "elapsed_km": 22.76},
            # visit ~41.17
            {"runner_id": "f1", "event": "full", "t": 37000, "lat": 45.001, "lon": -66.0, "elapsed_km": 41.10},
            {"runner_id": "f1", "event": "full", "t": 37005, "lat": 45.00005, "lon": -66.0, "elapsed_km": 41.17},
            {"runner_id": "f1", "event": "full", "t": 37025, "lat": 45.001, "lon": -66.0, "elapsed_km": 41.24},
            # half single visit
            {"runner_id": "h1", "event": "half", "t": 31000, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.60},
            {"runner_id": "h1", "event": "half", "t": 31005, "lat": 45.00005, "lon": -66.0, "elapsed_km": 20.67},
            {"runner_id": "h1", "event": "half", "t": 31025, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.73},
        ]
    )
    crosses = planar_crossing_events(samples, _pin())
    episodes = pair_visit_episodes(crosses)
    paired = episodes[episodes["orphan"].isna()]
    assert len(paired) == 4  # 3 full + 1 half
    assert int((paired["event"] == "full").sum()) == 3

    summary = build_visit_summary(episodes, window_sec=300, gap_km=MOTION_VISIT_KM_GAP)
    full_rows = [r for r in summary if r["event"] == "full"]
    assert len(full_rows) == 3
    assert [r["visit_km"] for r in full_rows] == [20.61, 22.70, 41.17]
    for r in full_rows:
        assert r["passages"] == 1
        assert r["unique_runners"] == 1

    half_rows = [r for r in summary if r["event"] == "half"]
    assert len(half_rows) == 1
    assert half_rows[0]["visit_km"] == 20.67
    assert half_rows[0]["passages"] == 1

    out = build_stream_passage_table(samples, _pin())
    assert out["totals"]["passages_by_event"]["full"] == 3
    assert out["totals"]["enters_by_event"]["full"] == 1  # unique
    assert out["totals"]["passages_total"] == 4
    assert out["totals"]["unique_runners_total"] == 2
    assert len(out["visit_summary"]) == 4


def test_window_context_lists_co_present_visit_clusters():
    """Same window can hold parallel and cross streams — show each visit count."""
    samples = pd.DataFrame(
        [
            # 10k @ 6.28
            {"runner_id": "a", "event": "10k", "t": 30000, "lat": 45.001, "lon": -66.0, "elapsed_km": 6.20},
            {"runner_id": "a", "event": "10k", "t": 30005, "lat": 45.00005, "lon": -66.0, "elapsed_km": 6.28},
            {"runner_id": "a", "event": "10k", "t": 30020, "lat": 45.001, "lon": -66.0, "elapsed_km": 6.34},
            # full @ 20.61 (parallel with 10k 6.28)
            {"runner_id": "b", "event": "full", "t": 30000, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.50},
            {"runner_id": "b", "event": "full", "t": 30010, "lat": 45.00005, "lon": -66.0, "elapsed_km": 20.61},
            {"runner_id": "b", "event": "full", "t": 30025, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.68},
            # full @ 22.70 (cross with 10k 6.28)
            {"runner_id": "c", "event": "full", "t": 30100, "lat": 45.001, "lon": -66.0, "elapsed_km": 22.60},
            {"runner_id": "c", "event": "full", "t": 30105, "lat": 45.00005, "lon": -66.0, "elapsed_km": 22.70},
            {"runner_id": "c", "event": "full", "t": 30120, "lat": 45.001, "lon": -66.0, "elapsed_km": 22.76},
        ]
    )
    out = build_stream_passage_table(samples, _pin(), window_sec=300)
    row = out["rows"][0]
    ctx = row["context"]
    assert "10k 6.28:1" in ctx
    assert "full 20.61:1" in ctx
    assert "full 22.70:1" in ctx
    visits = {(v["event"], v["visit_km"]): v["enters"] for v in row["enters_by_visit"]}
    assert visits[("10k", 6.28)] == 1
    assert visits[("full", 20.61)] == 1
    assert visits[("full", 22.70)] == 1


def test_visit_summary_passages_can_exceed_unique_in_same_cluster():
    """Two passages at nearly the same km → same cluster, passages > unique."""
    episodes = pd.DataFrame(
        [
            {
                "runner_id": "r1",
                "event": "10k",
                "enter_t": 1000,
                "exit_t": 1020,
                "enter_km": 6.28,
                "exit_km": 6.34,
                "orphan": None,
            },
            {
                "runner_id": "r1",
                "event": "10k",
                "enter_t": 2000,
                "exit_t": 2020,
                "enter_km": 6.30,
                "exit_km": 6.36,
                "orphan": None,
            },
        ]
    )
    summary = build_visit_summary(episodes, gap_km=MOTION_VISIT_KM_GAP)
    assert len(summary) == 1
    assert summary[0]["passages"] == 2
    assert summary[0]["unique_runners"] == 1
