"""Locations report includes stable location_key in Locations.csv."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import app.location_report as location_report


def test_generate_location_report_includes_location_key(tmp_path, monkeypatch):
    locations = pd.DataFrame(
        [
            {
                "loc_id": 151,
                "location_key": "D3UF4",
                "loc_label": "Trail at George",
                "loc_type": "course",
                "lat": 45.95,
                "lon": -66.63,
                "seg_id": "S11",
                "full": "y",
                "half": "n",
                "10k": "n",
                "buffer": 10,
                "interval": 5,
                "zone": "",
                "notes": "",
            },
            {
                "loc_id": 148,
                "leg_loc_key": "D3UF4",  # fallback when location_key absent
                "loc_label": "Trail at George",
                "loc_type": "course",
                "lat": 45.95,
                "lon": -66.63,
                "seg_id": "S9",
                "full": "y",
                "half": "y",
                "10k": "y",
                "buffer": 10,
                "interval": 5,
                "zone": "",
                "notes": "",
            },
        ]
    )
    runners = pd.DataFrame(
        columns=["runner_id", "event", "pace", "start_offset"]
    )
    segments = pd.DataFrame(
        [
            {
                "seg_id": "S11",
                "seg_label": "rev",
                "full": "y",
                "half": "n",
                "10k": "n",
                "full_from_km": 0.0,
                "full_to_km": 0.3,
                "direction": "uni",
                "width_m": 4.0,
            }
        ]
    )

    monkeypatch.setattr(location_report, "load_locations", lambda p: locations.copy())
    monkeypatch.setattr(location_report, "load_runners", lambda p: runners.copy())
    monkeypatch.setattr(location_report, "load_segments", lambda p: segments.copy())
    monkeypatch.setattr(location_report, "load_all_courses", lambda gpx: {})
    monkeypatch.setattr(
        location_report,
        "calculate_arrival_times_for_location",
        lambda *a, **k: [],
    )
    monkeypatch.setattr(location_report, "load_flagged_segments", lambda **k: {})

    out_dir = tmp_path / "reports"
    out_dir.mkdir()
    result = location_report.generate_location_report(
        locations_csv=str(tmp_path / "locations.csv"),
        runners_csv=str(tmp_path / "runners.csv"),
        segments_csv=str(tmp_path / "segments.csv"),
        start_times={"full": 420, "half": 440, "10k": 460},
        output_dir=str(out_dir),
        day="sun",
        gpx_paths={"full": "full.gpx"},
    )
    assert result.get("ok") is True
    report_path = Path(result["file_path"])
    assert report_path.exists()
    df = pd.read_csv(report_path)
    assert "location_key" in df.columns
    assert list(df.columns[:4]) == ["loc_id", "location_key", "loc_label", "day"]
    by_id = df.set_index("loc_id")["location_key"].to_dict()
    assert by_id[151] == "D3UF4"
    assert by_id[148] == "D3UF4"
