"""Unit tests for Motion movement drill-down (#856)."""

from __future__ import annotations

import json

import pandas as pd

from app.core.motion.movement_drilldown import (
    build_concurrent_pairs,
    build_movement_spans,
    load_authored_movements,
    match_authored_movement,
    nearest_partner_quintile_matrix,
)
from app.core.motion.occupancy import PinPlace
from app.core.motion.stream_passage import build_stream_passage_table


def _pin() -> PinPlace:
    return PinPlace(lat=45.0, lon=-66.0, radius_m=30.0, place_id="38", label="George")


def test_concurrent_pairs_and_authored_cross_parallel():
    visits = [
        {"event": "10k", "visit_km": 6.28, "enters": 26},
        {"event": "full", "visit_km": 20.61, "enters": 49},
        {"event": "full", "visit_km": 22.70, "enters": 19},
    ]
    authored = [
        {
            "name": "10K crosses Full",
            "type": "cross",
            "stream_a": {"event": "10k", "visit_km": 6.28},
            "stream_b": {"event": "full", "visit_km": 22.70},
        },
        {
            "name": "10K parallel Full",
            "type": "parallel",
            "stream_a": {"event": "10k", "visit_km": 6.28},
            "stream_b": {"event": "full", "visit_km": 20.61},
        },
    ]
    pairs = build_concurrent_pairs(visits, authored_movements=authored)
    assert len(pairs) == 3
    by_type = {p["movement_type"]: p for p in pairs if p["movement_type"]}
    assert by_type["cross"]["volume_a"] == 26
    assert by_type["cross"]["volume_b"] == 19
    assert by_type["parallel"]["volume_b"] == 49
    # Full×Full remains unlabeled concurrent
    unlabeled = [p for p in pairs if p["movement_type"] is None]
    assert len(unlabeled) == 1
    assert unlabeled[0]["label"] == "concurrent_streams"


def test_match_authored_tolerates_cluster_median_drift():
    matched = match_authored_movement(
        {"event": "10k", "visit_km": 6.27},
        {"event": "full", "visit_km": 22.69},
        [
            {
                "type": "cross",
                "stream_a": {"event": "10k", "visit_km": 6.28},
                "stream_b": {"event": "full", "visit_km": 22.70},
            }
        ],
    )
    assert matched is not None
    assert matched["type"] == "cross"


def test_movement_spans_first_peak_last():
    rows = [
        {
            "t0": 30000,
            "enters_by_visit": [
                {"event": "10k", "visit_km": 6.28, "enters": 10},
                {"event": "full", "visit_km": 22.70, "enters": 2},
            ],
        },
        {
            "t0": 30300,
            "enters_by_visit": [
                {"event": "10k", "visit_km": 6.28, "enters": 40},
                {"event": "full", "visit_km": 22.70, "enters": 20},
            ],
        },
        {
            "t0": 30600,
            "enters_by_visit": [
                {"event": "10k", "visit_km": 6.28, "enters": 5},
                {"event": "full", "visit_km": 22.70, "enters": 3},
            ],
        },
    ]
    spans = build_movement_spans(
        rows,
        window_sec=300,
        authored_movements=[
            {
                "type": "cross",
                "stream_a": {"event": "10k", "visit_km": 6.28},
                "stream_b": {"event": "full", "visit_km": 22.70},
            }
        ],
    )
    assert len(spans) == 1
    s = spans[0]
    assert s["movement_type"] == "cross"
    assert s["first_t0"] == 30000
    assert s["peak_t0"] == 30300
    assert s["last_t0"] == 30600
    assert s["peak_volume_a"] == 40
    assert s["peak_volume_b"] == 20


def test_nearest_partner_quintile_matrix():
    matrix = nearest_partner_quintile_matrix(
        [
            {"runner_id": "a1", "t": 100, "quintile": 1},
            {"runner_id": "a2", "t": 110, "quintile": 2},
            {"runner_id": "a3", "t": 200, "quintile": 5},
        ],
        [
            {"runner_id": "b1", "t": 101, "quintile": 3},
            {"runner_id": "b2", "t": 112, "quintile": 4},
        ],
        dwell_sec=30,
    )
    assert matrix["matched_a"] == 2
    assert matrix["stream_a_with_q"] == 3
    cells = {(c["qa"], c["qb"]): c["n"] for c in matrix["cells"]}
    assert cells[(1, 3)] == 1
    assert cells[(2, 4)] == 1
    assert (5, 3) not in cells and (5, 4) not in cells


def test_george_shaped_table_keeps_full_visits_distinct(tmp_path):
    samples = pd.DataFrame(
        [
            # 10k @ 6.28
            {"runner_id": "a", "event": "10k", "t": 30100, "lat": 45.001, "lon": -66.0, "elapsed_km": 6.20},
            {"runner_id": "a", "event": "10k", "t": 30105, "lat": 45.00005, "lon": -66.0, "elapsed_km": 6.28},
            {"runner_id": "a", "event": "10k", "t": 30120, "lat": 45.001, "lon": -66.0, "elapsed_km": 6.34},
            # full @ 20.61
            {"runner_id": "b", "event": "full", "t": 30100, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.50},
            {"runner_id": "b", "event": "full", "t": 30110, "lat": 45.00005, "lon": -66.0, "elapsed_km": 20.61},
            {"runner_id": "b", "event": "full", "t": 30125, "lat": 45.001, "lon": -66.0, "elapsed_km": 20.68},
            # full @ 22.70
            {"runner_id": "c", "event": "full", "t": 30150, "lat": 45.001, "lon": -66.0, "elapsed_km": 22.60},
            {"runner_id": "c", "event": "full", "t": 30155, "lat": 45.00005, "lon": -66.0, "elapsed_km": 22.70},
            {"runner_id": "c", "event": "full", "t": 30170, "lat": 45.001, "lon": -66.0, "elapsed_km": 22.76},
            # full @ 41.17 (later window)
            {"runner_id": "c", "event": "full", "t": 37000, "lat": 45.001, "lon": -66.0, "elapsed_km": 41.10},
            {"runner_id": "c", "event": "full", "t": 37005, "lat": 45.00005, "lon": -66.0, "elapsed_km": 41.17},
            {"runner_id": "c", "event": "full", "t": 37020, "lat": 45.001, "lon": -66.0, "elapsed_km": 41.24},
        ]
    )
    authored = [
        {
            "type": "cross",
            "stream_a": {"event": "10k", "visit_km": 6.28},
            "stream_b": {"event": "full", "visit_km": 22.70},
        },
        {
            "type": "parallel",
            "stream_a": {"event": "10k", "visit_km": 6.28},
            "stream_b": {"event": "full", "visit_km": 20.61},
        },
    ]
    runners = pd.DataFrame(
        [
            {"runner_id": "a", "event": "10k", "pace": 4.5, "start_offset": 0},
            {"runner_id": "b", "event": "full", "pace": 5.0, "start_offset": 0},
            {"runner_id": "c", "event": "full", "pace": 5.5, "start_offset": 0},
        ]
    )
    out = build_stream_passage_table(
        samples,
        _pin(),
        window_sec=300,
        authored_movements=authored,
        runners_df=runners,
    )
    full_visits = sorted(
        v["visit_km"] for v in out["visit_summary"] if v["event"] == "full"
    )
    assert full_visits == [20.61, 22.70, 41.17]
    assert out["count_semantics"] == "same_window_concurrent_stream_volume"
    assert out["matrix_semantics_note"]

    first = out["rows"][0]
    types = {p["movement_type"] for p in first["concurrent_pairs"] if p["movement_type"]}
    assert "cross" in types
    assert "parallel" in types
    # Unrelated full@41 must not appear in the early window pairs
    for p in first["concurrent_pairs"]:
        for side in (p["stream_a"], p["stream_b"]):
            assert float(side["visit_km"]) != 41.17
        assert "quintile_matrix" in p
        assert "cells" in p["quintile_matrix"]

    parallel = next(p for p in first["concurrent_pairs"] if p["movement_type"] == "parallel")
    assert parallel["quintile_matrix"]["matched_a"] >= 1
    assert parallel["quintile_matrix"]["cells"]

    assert first["quintile_profiles"]
    assert any(s["movement_type"] == "cross" for s in out["movement_spans"])


def test_load_authored_movements(tmp_path):
    path = tmp_path / "motion_movements.json"
    path.write_text(
        json.dumps(
            {
                "locations": {
                    "38": {
                        "movements": [
                            {
                                "type": "cross",
                                "name": "Cross",
                                "stream_a": {"event": "10k", "visit_km": 6.28},
                                "stream_b": {"event": "full", "visit_km": 22.7},
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    loaded = load_authored_movements(tmp_path, "38")
    assert len(loaded) == 1
    assert loaded[0]["type"] == "cross"
