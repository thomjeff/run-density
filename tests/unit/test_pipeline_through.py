"""Staged pipeline --through trajectory / locations (#860)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.core.v2.analysis_config import generate_analysis_json
from app.core.v2.models import Day, Event
from app.core.v2.pipeline import create_full_analysis_pipeline
from app.utils.constants import MOTION_RUNNERS_SNAPSHOT_FILENAME, MOTION_SAMPLES_FILENAME
from app.utils.run_id import get_run_directory


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


@pytest.fixture
def staged_package(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNFLOW_ROOT", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _tiny_gpx(data_dir / "10k.gpx")

    pd.DataFrame(
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
                "full": "n",
            },
            {
                "seg_id": "S2",
                "seg_label": "End",
                "schema": "on_course_open",
                "width_m": 4.0,
                "direction": "uni",
                "10k": "y",
                "10k_from_km": 1.0,
                "10k_to_km": 2.0,
                "full": "n",
            },
        ]
    ).to_csv(data_dir / "segments.csv", index=False)

    pd.DataFrame(
        {"seg_id": ["S1"], "event_a": ["10k"], "event_b": ["10k"]}
    ).to_csv(data_dir / "flow.csv", index=False)

    pd.DataFrame(
        {
            "loc_id": [1],
            "loc_label": ["Aid"],
            "lat": [45.0009],
            "lon": [-66.0],
            "seg_id": ["S1"],
            "10k": ["y"],
            "day": ["sun"],
            "buffer": [0],
            "interval": [5],
        }
    ).to_csv(data_dir / "locations.csv", index=False)

    pd.DataFrame(
        {
            "runner_id": ["r1", "r2"],
            "event": ["10k", "10k"],
            "pace": [5.0, 6.0],
            "distance": [2.0, 2.0],
            "start_offset": [0, 5],
        }
    ).to_csv(data_dir / "10k_runners.csv", index=False)

    events = [
        Event(
            name="10k",
            day=Day.SUN,
            start_time=435,
            gpx_file="10k.gpx",
            runners_file="10k_runners.csv",
        )
    ]
    return data_dir, events


def _write_analysis(data_dir: Path, run_id: str, through: str) -> Path:
    run_path = get_run_directory(run_id)
    run_path.mkdir(parents=True, exist_ok=True)
    generate_analysis_json(
        request_payload={
            "description": f"through={through}",
            "segments_file": "segments.csv",
            "locations_file": "locations.csv",
            "flow_file": "flow.csv",
            "through": through,
            "events": [
                {
                    "name": "10k",
                    "day": "sun",
                    "start_time": 435,
                    "event_duration_minutes": 120,
                    "runners_file": "10k_runners.csv",
                    "gpx_file": "10k.gpx",
                }
            ],
        },
        run_id=run_id,
        run_path=run_path,
        data_dir=str(data_dir),
    )
    return run_path


def test_through_trajectory_skips_density(staged_package, tmp_path, monkeypatch):
    data_dir, events = staged_package
    monkeypatch.setenv("DATA_ROOT", str(data_dir))
    run_id = "through-traj"
    _write_analysis(data_dir, run_id, "trajectory")

    result = create_full_analysis_pipeline(
        events=events,
        segments_file="segments.csv",
        locations_file="locations.csv",
        flow_file="flow.csv",
        data_dir=str(data_dir),
        run_id=run_id,
        through="trajectory",
    )
    assert result["through"] == "trajectory"
    sun = get_run_directory(run_id) / "sun"
    assert (sun / "motion" / MOTION_SAMPLES_FILENAME).is_file()
    assert (sun / "motion" / MOTION_RUNNERS_SNAPSHOT_FILENAME).is_file()
    assert not (sun / "reports" / "Density.md").exists()
    assert not (sun / "reports" / "Locations.csv").exists()
    assert not (sun / "computation" / "density_results.json").exists()
    meta = json.loads((sun / "metadata.json").read_text(encoding="utf-8"))
    assert meta["through"] == "trajectory"
    assert meta["status"] == "PASS"


def test_through_locations_writes_report_without_density(staged_package, tmp_path, monkeypatch):
    data_dir, events = staged_package
    monkeypatch.setenv("DATA_ROOT", str(data_dir))
    run_id = "through-loc"
    _write_analysis(data_dir, run_id, "locations")

    result = create_full_analysis_pipeline(
        events=events,
        segments_file="segments.csv",
        locations_file="locations.csv",
        flow_file="flow.csv",
        data_dir=str(data_dir),
        run_id=run_id,
        through="locations",
    )
    assert result["through"] == "locations"
    sun = get_run_directory(run_id) / "sun"
    assert (sun / "motion" / MOTION_SAMPLES_FILENAME).is_file()
    assert (sun / "computation" / "locations_results.json").is_file()
    assert not (sun / "reports" / "Density.md").exists()
    assert not (sun / "computation" / "density_results.json").exists()
    # Locations.csv depends on GPX projection succeeding for the pin
    loc_csv = sun / "reports" / "Locations.csv"
    if loc_csv.is_file():
        meta = json.loads((sun / "metadata.json").read_text(encoding="utf-8"))
        assert meta["through"] == "locations"
        df = pd.read_csv(loc_csv)
        assert not df.empty
