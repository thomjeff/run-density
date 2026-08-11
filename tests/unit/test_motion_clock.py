"""Unit tests for Runflow motion clock (#850 Child A)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.core.motion.build import (
    aligned_ticks,
    build_motion_samples,
    resolve_motion_package_id,
)
from app.core.motion.course_map import EventSpan, locate_on_course
from app.core.motion.persist import build_and_persist_motion_for_day
from app.core.v2.models import Day, Event
from app.utils.constants import MOTION_SAMPLE_INTERVAL_SEC


def test_aligned_ticks_from_midnight():
    ticks = aligned_ticks(7 * 3600 + 1, 7 * 3600 + 16, 5)
    assert list(ticks) == [7 * 3600 + 5, 7 * 3600 + 10, 7 * 3600 + 15]


def test_resolve_motion_package_id_from_config_json_and_basename(tmp_path: Path):
    pkg = tmp_path / "hhiJEA4MuN588jYh7rZfLt"
    pkg.mkdir()
    (pkg / "config.json").write_text(
        json.dumps({"config_id": "hhiJEA4MuN588jYh7rZfLt", "label": "FM2027"}),
        encoding="utf-8",
    )
    assert resolve_motion_package_id(data_dir=pkg) == "hhiJEA4MuN588jYh7rZfLt"

    # Basename fallback when manifest is absent / incomplete
    bare = tmp_path / "barePkgId"
    bare.mkdir()
    assert resolve_motion_package_id(data_dir=bare) == "barePkgId"

    # Explicit analysis_config wins
    assert (
        resolve_motion_package_id(
            analysis_config={"config_id": "explicit-id"},
            data_dir=pkg,
        )
        == "explicit-id"
    )


def test_locate_boundary_belongs_to_downstream_except_finish():
    spans = [
        EventSpan(0.0, 1.0, "S1"),
        EventSpan(1.0, 2.5, "S2"),
    ]
    assert locate_on_course(1.0, spans, 2.5) == ("S2", 0.0)
    assert locate_on_course(0.0, spans, 2.5) == ("S1", 0.0)
    assert locate_on_course(2.5, spans, 2.5) == ("S2", 1.5)
    assert locate_on_course(0.5, spans, 2.5) == ("S1", 0.5)


def _tiny_gpx(path: Path, *, n: int = 11, step_km: float = 0.1) -> None:
    # ~0.0009 deg lat ≈ 100 m; include GPX 1.1 xmlns so parse_gpx_file finds trkpt nodes.
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


def test_build_and_persist_motion_deterministic(tmp_path: Path):
    gpx = tmp_path / "10k.gpx"
    _tiny_gpx(gpx, n=21, step_km=0.1)
    runners_path = tmp_path / "10k_runners.csv"
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
    runners = pd.read_csv(runners_path)
    event = Event(
        name="10k",
        day=Day.SUN,
        start_time=7 * 60 + 15,
        gpx_file=str(gpx),
        runners_file=str(runners_path),
    )
    day_path = tmp_path / "sun"

    first = build_and_persist_motion_for_day(
        day_path=day_path,
        day_code="sun",
        day_events=[event],
        runners_df=runners,
        segments_df=segments,
        gpx_paths={"10k": str(gpx)},
        runner_csv_paths={"10k": str(runners_path)},
        package_id="pkg-test",
        course_json_path=None,
        interval_sec=MOTION_SAMPLE_INTERVAL_SEC,
    )
    samples1 = pd.read_parquet(first["samples_path"])
    meta1 = json.loads(Path(first["metadata_path"]).read_text(encoding="utf-8"))

    # Boundary kinds present; unique key
    assert set(samples1["sample_kind"].unique()) >= {"start", "finish", "tick"}
    assert samples1.duplicated(subset=["runner_id", "t"]).sum() == 0
    assert meta1["row_count"] == len(samples1)
    assert meta1["event_counts"]["10k"] == len(samples1)
    assert meta1["compiled_course_lengths_km"]["10k"] == pytest.approx(2.0)
    assert meta1["sample_interval_sec"] == MOTION_SAMPLE_INTERVAL_SEC
    assert meta1["min_t"] <= meta1["max_t"]

    # Start on global grid for r1 (offset 0, gun 07:15:00)
    gun = (7 * 60 + 15) * 60
    r1_start = samples1[(samples1.runner_id == "r1") & (samples1.sample_kind == "start")]
    assert len(r1_start) == 1
    assert int(r1_start.iloc[0]["t"]) == gun

    # Deterministic rewrite
    second = build_and_persist_motion_for_day(
        day_path=day_path,
        day_code="sun",
        day_events=[event],
        runners_df=runners,
        segments_df=segments,
        gpx_paths={"10k": str(gpx)},
        runner_csv_paths={"10k": str(runners_path)},
        package_id="pkg-test",
        course_json_path=None,
        interval_sec=MOTION_SAMPLE_INTERVAL_SEC,
    )
    samples2 = pd.read_parquet(second["samples_path"])
    pd.testing.assert_frame_equal(samples1, samples2)


def test_compiled_finish_clamps_beyond_csv_distance(tmp_path: Path):
    gpx = tmp_path / "half.gpx"
    _tiny_gpx(gpx, n=31)
    runners = pd.DataFrame(
        [
            {
                "event": "half",
                "runner_id": "h1",
                "pace": 5.0,
                "distance": 21.1,  # nominal; compiled is 2.0
                "start_offset": 0,
            }
        ]
    )
    segments = pd.DataFrame(
        [
            {
                "seg_id": "S1",
                "half": "y",
                "half_from_km": 0.0,
                "half_to_km": 2.0,
                "full": "n",
                "10k": "n",
            }
        ]
    )
    event = Event(
        name="half",
        day=Day.SUN,
        start_time=450,
        gpx_file=str(gpx),
        runners_file="half_runners.csv",
    )
    frame, diag = build_motion_samples(
        runners_df=runners,
        day_events=[event],
        segments_df=segments,
        gpx_paths={"half": str(gpx)},
        interval_sec=5,
    )
    assert frame["elapsed_km"].max() == pytest.approx(2.0)
    assert diag["csv_distance_mismatches"]
    assert diag["csv_distance_mismatches"][0]["delta_km"] == pytest.approx(19.1)
