"""Smoke tests for finish-area operational PDF (Issue #743 extension)."""

from pathlib import Path

import pandas as pd

from app.finish_area_pdf import (
    expected_runners_for_day,
    generate_finish_area_demand_pdf,
    _operational_tier,
)


def test_operational_tier_thresholds():
    assert _operational_tier(0, 100) == "—"
    assert _operational_tier(90, 100) == "Peak / surge"
    assert _operational_tier(50, 100) == "High"
    assert _operational_tier(15, 100) == "Moderate"
    assert _operational_tier(5, 100) == "Low"


def test_expected_runners_for_day():
    cfg = {
        "events": [
            {"day": "sat", "runners": 100},
            {"day": "sun", "runners": 200},
            {"day": "sun", "runners": 50},
        ]
    }
    assert expected_runners_for_day(cfg, "sat") == 100
    assert expected_runners_for_day(cfg, "sun") == 250
    assert expected_runners_for_day({}, "sat") is None


def test_generate_finish_area_demand_pdf_writes_file(tmp_path: Path):
    csv_path = tmp_path / "finish_times.csv"
    pdf_path = tmp_path / "finish_area_demand.pdf"
    df = pd.DataFrame(
        {
            "day": ["sat", "sat", "sat", "sat"],
            "time_window_start": ["08:00:00", "08:00:00", "08:20:00", "08:20:00"],
            "time_window_end": ["08:19:59", "08:19:59", "08:39:59", "08:39:59"],
            "event": ["full", "all", "full", "all"],
            "count": [10, 10, 5, 5],
        }
    )
    df.to_csv(csv_path, index=False)

    ok = generate_finish_area_demand_pdf(
        finish_times_csv=csv_path,
        output_pdf=pdf_path,
        day_display_name="Saturday",
        run_id="test-run",
        expected_runner_total=15,
    )
    assert ok is True
    assert pdf_path.is_file()
    assert pdf_path.stat().st_size > 500
