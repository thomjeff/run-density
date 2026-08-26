"""Issue #903: Locations.csv / Passes.csv export cleanup."""

from pathlib import Path

import pandas as pd

from app.core.v2 import reports as reports_mod
from app.location_report import order_locations_csv_columns, order_passes_csv_columns


def test_locations_csv_column_order_and_single_pass_count():
    cols = [
        "loc_id",
        "pass_key",
        "pass_ids",
        "pass_count",
        "loc_label",
        "day",
        "loc_type",
        "lat",
        "lon",
        "zone",
        "first_runner",
        "last_runner",
        "loc_start",
        "loc_end",
        "peak_start",
        "peak_end",
        "by_event",
        "flag",
        "onepage",
        "notes",
        "proxy_pass_id",
        "proxy_loc_id",
        "awp_count",
        "awp_mins",
        "ofc_count",
        "ofc_mins",
        "yssr_count",
        "yssr_mins",
    ]
    ordered = order_locations_csv_columns(cols)
    assert ordered.count("pass_count") == 1
    assert ordered[:7] == [
        "loc_id",
        "loc_label",
        "day",
        "loc_type",
        "lat",
        "lon",
        "zone",
    ]
    assert ordered[7:13] == [
        "loc_start",
        "loc_end",
        "first_runner",
        "last_runner",
        "peak_start",
        "peak_end",
    ]
    yssr = ordered.index("yssr_mins")
    assert ordered[yssr : yssr + 6] == [
        "yssr_mins",
        "flag",
        "onepage",
        "pass_key",
        "pass_ids",
        "pass_count",
    ]


def test_passes_csv_timing_order():
    cols = [
        "pass_id",
        "loc_id",
        "pass_key",
        "loc_label",
        "first_runner",
        "peak_start",
        "peak_end",
        "last_runner",
        "loc_start",
        "loc_end",
        "duration",
        "yssr_count",
        "yssr_mins",
        "notes",
        "flag",
        "onepage",
    ]
    ordered = order_passes_csv_columns(cols)
    start = ordered.index("loc_start")
    assert ordered[start : start + 6] == [
        "loc_start",
        "loc_end",
        "duration",
        "first_runner",
        "last_runner",
        "peak_start",
    ]


def test_reports_module_does_not_write_run_root_combined_csvs():
    src = Path(reports_mod.__file__).read_text(encoding="utf-8")
    assert "write_combined_locations_csv" not in src
    assert "write_combined_passes_csv" not in src
    assert "run_dir / filename" not in src


def test_generate_location_report_fills_onepage_and_unique_pass_count(
    tmp_path, monkeypatch
):
    import app.location_report as location_report
    from app.io.loader import normalize_passes_input_dataframe

    locations = normalize_passes_input_dataframe(
        pd.DataFrame(
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
                    "onepage": "y",
                }
            ]
        )
    )
    runners = pd.DataFrame(columns=["runner_id", "event", "pace", "start_offset"])
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
        lambda *a, **k: {},
    )
    monkeypatch.setattr(location_report, "load_flagged_segments", lambda **k: {})

    out_dir = tmp_path / "sun" / "reports"
    out_dir.mkdir(parents=True)
    result = location_report.generate_location_report(
        locations_csv=str(tmp_path / "locations.csv"),
        runners_csv=str(tmp_path / "runners.csv"),
        segments_csv=str(tmp_path / "segments.csv"),
        start_times={"full": 420},
        output_dir=str(out_dir),
        day="sun",
        gpx_paths={"full": "full.gpx"},
    )
    assert result.get("ok") is True
    locs = pd.read_csv(result["file_path"])
    assert list(locs.columns).count("pass_count") == 1
    assert str(locs.iloc[0]["onepage"]).strip().lower() == "y"
    assert list(locs.columns[:7]) == [
        "loc_id",
        "loc_label",
        "day",
        "loc_type",
        "lat",
        "lon",
        "zone",
    ]
    run_root = tmp_path / "Locations.csv"
    assert not run_root.exists()
    passes = pd.read_csv(result["passes_path"])
    start = list(passes.columns).index("loc_start")
    assert list(passes.columns[start : start + 4])[:2] == ["loc_start", "loc_end"]
