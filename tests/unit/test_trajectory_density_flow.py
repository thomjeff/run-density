"""Unit tests for Density/Flow trajectory substrate (#862)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.density.compute import DensityAnalyzer, DensityConfig
from app.core.density.models import SegmentMeta
from app.core.flow.flow import build_segment_flow_cache
from app.core.motion.persist import build_and_persist_motion_for_day
from app.core.trajectory.layer import snapshot_to_runners_df, try_load_day_layer
from app.core.trajectory.presence import TrajectoryPresence, datetime_midnight_sec
from app.core.v2.models import Day, Event


def test_datetime_midnight_sec():
    assert datetime_midnight_sec(datetime(2025, 1, 1, 7, 20, 0)) == 7 * 3600 + 20 * 60


def test_presence_counts_unique_runners_in_km_window():
    samples = pd.DataFrame(
        {
            "t": [25200, 25200, 25205, 25205],
            "elapsed_km": [1.0, 5.0, 1.01, 1.02],
            "event": ["10k", "full", "10k", "10k"],
            "runner_id": ["a", "b", "a", "c"],
        }
    )
    presence = TrajectoryPresence.from_samples(samples)
    n = presence.count_unique(25200, 25210, ["10k"], [(0.0, 2.0)])
    assert n == 2


def test_positions_in_window_one_row_per_runner():
    samples = pd.DataFrame(
        {
            "t": [25200, 25205, 25200],
            "elapsed_km": [1.0, 1.2, 1.5],
            "event": ["10k", "10k", "10k"],
            "runner_id": ["a", "a", "b"],
        }
    )
    snap = pd.DataFrame({"runner_id": ["a", "b"], "pace": [6.0, 6.0]})
    presence = TrajectoryPresence.from_samples(samples, snap)
    pos, speed = presence.positions_in_window(25203, 0.0, 2.0, "10k")
    assert len(pos) == 2
    assert np.all(speed > 0)


def test_density_union_uses_samples_when_present():
    samples = pd.DataFrame(
        {
            "t": [25200, 25200],
            "elapsed_km": [0.5, 0.6],
            "event": ["10k", "10k"],
            "runner_id": ["1", "2"],
        }
    )
    analyzer = DensityAnalyzer(DensityConfig(bin_seconds=30), None, samples_df=samples)
    segment = SegmentMeta(
        segment_id="S1",
        from_km=0.0,
        to_km=1.0,
        width_m=4.0,
        direction="uni",
        events=("10k",),
    )
    t0 = datetime(2025, 1, 1, 7, 0, 0)
    n = analyzer.calculate_concurrent_runners_union(
        segment,
        pd.DataFrame({"event": ["10k"], "runner_id": ["1"], "pace": [6.0], "start_offset": [0]}),
        {"10k": t0},
        t0,
        {"10k_from_km": 0.0, "10k_to_km": 1.0},
    )
    assert n == 2


def test_flow_cache_from_snapshot_matches_csv_arrays(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
    runners = pd.DataFrame(
        {
            "runner_id": ["1", "2"],
            "event": ["10k", "10k"],
            "pace": [5.0, 6.0],
            "start_offset": [0, 10],
            "distance": [10.0, 10.0],
        }
    )
    cache_csv = build_segment_flow_cache(
        runners,
        runners,
        "10k",
        "10k",
        {"10k": 460.0},
        0.0,
        1.0,
        0.0,
        1.0,
    )
    snap = snapshot_to_runners_df(
        type("L", (), {"snapshot": runners, "samples": pd.DataFrame(), "metadata": {}, "day_path": tmp_path})()
    )
    cache_snap = build_segment_flow_cache(
        snap,
        snap,
        "10k",
        "10k",
        {"10k": 460.0},
        0.0,
        1.0,
        0.0,
        1.0,
    )
    assert cache_csv is not None and cache_snap is not None
    np.testing.assert_array_equal(cache_csv.pace_a, cache_snap.pace_a)
    np.testing.assert_array_equal(cache_csv.offset_a, cache_snap.offset_a)


def _tiny_gpx(path: Path, *, n: int = 21) -> None:
    lines = [
        '<?xml version="1.0"?>',
        '<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">',
        "<trk><name>test</name><trkseg>",
    ]
    for i in range(n):
        lines.append(f'<trkpt lat="{45.0 + i * 0.0009}" lon="-66.0"></trkpt>')
    lines.append("</trkseg></trk></gpx>")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_snapshot_includes_distance(tmp_path):
    gpx = tmp_path / "10k.gpx"
    _tiny_gpx(gpx)
    segments = pd.DataFrame(
        [
            {
                "seg_id": "S1",
                "seg_label": "Start",
                "schema": "on_course_open",
                "width_m": 4.0,
                "direction": "uni",
                "10k": "y",
                "10k_from_km": 0.0,
                "10k_to_km": 1.0,
            }
        ]
    )
    runners = pd.DataFrame(
        {
            "runner_id": ["1"],
            "event": ["10k"],
            "pace": [6.0],
            "start_offset": [0],
            "distance": [10.0],
        }
    )
    event = Event(
        name="10k",
        day=Day.SUN,
        start_time=460,
        gpx_file="10k.gpx",
        runners_file="10k_runners.csv",
    )
    csv_path = tmp_path / "10k_runners.csv"
    runners.to_csv(csv_path, index=False)
    day_path = tmp_path / "sun"
    day_path.mkdir()
    build_and_persist_motion_for_day(
        day_path=day_path,
        day_code="sun",
        day_events=[event],
        runners_df=runners,
        segments_df=segments,
        gpx_paths={"10k": str(gpx)},
        runner_csv_paths={"10k": str(csv_path)},
        package_id="pkg",
    )
    layer = try_load_day_layer(day_path)
    assert layer is not None
    assert "distance" in layer.snapshot.columns
    assert float(layer.snapshot.iloc[0]["distance"]) == 10.0
