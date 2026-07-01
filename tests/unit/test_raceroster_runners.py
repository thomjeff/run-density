"""Tests for Race Roster results → runner CSV conversion."""

import pandas as pd
import pytest

from app.core.baseline.raceroster_runners import (
    build_event_runners_from_results_df,
    filter_sheet_events,
    parse_time_to_seconds,
)


def test_parse_time_to_seconds():
    assert parse_time_to_seconds("14:00") == 840
    assert parse_time_to_seconds("1:11:16") == 4276
    assert parse_time_to_seconds("") is None
    assert parse_time_to_seconds(None) is None


def test_build_event_runners_chip_only():
    df = pd.DataFrame(
        {
            "No.": [101, 102, 103],
            "Gun Time": ["35:20", "36:00", "2:13:55"],
            "Chip Time": ["35:18", "35:58", None],
        }
    )
    out = build_event_runners_from_results_df(df, "10k", 10.0)
    assert len(out) == 2
    assert list(out.columns) == ["event", "runner_id", "pace", "distance", "start_offset"]
    assert out["event"].tolist() == ["10k", "10k"]
    assert out["runner_id"].tolist() == ["101", "102"]
    assert out["distance"].tolist() == [10, 10]
    assert out.iloc[0]["start_offset"] == 2


def test_filter_sheet_events():
    selected = filter_sheet_events(["10k", "full"])
    assert [row[1] for row in selected] == ["10k", "full"]
    with pytest.raises(ValueError, match="No matching events"):
        filter_sheet_events(["ultra"])
