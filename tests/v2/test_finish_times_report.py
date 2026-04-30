"""Issue #743: finish_times.csv aggregation (20-minute naive-clock buckets)."""

import pandas as pd
import pytest

from app.core.v2.models import Day, Event
from app.core.v2.timings import (
    build_runner_finish_times_df,
    finish_bucket_start_sec,
    write_finish_times_csv,
)


def test_finish_bucket_start_sec_boundary():
    # End of first 20-minute slot within 08:xx hour
    s_end = 8 * 3600 + 19 * 60 + 59
    assert finish_bucket_start_sec(s_end) == 8 * 3600

    # Exact start of second slot
    s_second = 8 * 3600 + 20 * 60
    assert finish_bucket_start_sec(s_second) == 8 * 3600 + 20 * 60

    # Third slot in hour
    s_third = 8 * 3600 + 45 * 60
    assert finish_bucket_start_sec(s_third) == 8 * 3600 + 40 * 60


def test_build_runner_finish_times_df_matches_formula():
    events = [
        Event(
            name="full",
            day=Day.SUN,
            start_time=420,
            gpx_file="f.gpx",
            runners_file="f.csv",
        ),
    ]
    analysis_config = {}
    runners_df = pd.DataFrame(
        [
            {"runner_id": "a", "event": "full", "pace": 10.0, "distance": 1.0, "start_offset": 0},
        ]
    )
    df = build_runner_finish_times_df(
        events=events, analysis_config=analysis_config, runners_df=runners_df
    )
    assert df is not None and len(df) == 1
    # 420 min gun -> 25200 s + pace 10 min/km * 1 km -> 600 s
    assert pytest.approx(df.iloc[0]["finish_time_sec"], rel=1e-9) == 25200 + 600


def test_write_finish_times_csv_nonzero_rows_and_all(tmp_path):
    finish_df = pd.DataFrame(
        {
            "runner_id": ["1", "2", "3"],
            "event": ["full", "full", "half"],
            "finish_time_sec": [
                8 * 3600 + 5 * 60,
                8 * 3600 + 10 * 60,
                8 * 3600 + 8 * 60,
            ],
        }
    )
    out = tmp_path / "finish_times.csv"
    assert write_finish_times_csv(out, "sun", finish_df) is True
    text = out.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    # header + 2 event rows + all row (same window)
    assert lines[0].startswith("day,time_window_start")
    body = lines[1:]
    assert len(body) == 3
    assert any(",full,2" in ln for ln in body)
    assert any(",half,1" in ln for ln in body)
    assert any(",all,3" in ln for ln in body)


def test_write_finish_times_csv_blank_line_between_hours(tmp_path):
    finish_df = pd.DataFrame(
        {
            "runner_id": ["1", "2"],
            "event": ["full", "full"],
            "finish_time_sec": [
                8 * 3600 + 15 * 60,
                9 * 3600 + 5 * 60,
            ],
        }
    )
    out = tmp_path / "finish_times.csv"
    assert write_finish_times_csv(out, "sun", finish_df) is True
    raw = out.read_text(encoding="utf-8")
    assert "\n\n" in raw
