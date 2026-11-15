"""Tests for Race Roster results → runner CSV conversion (Issues #957)."""

from io import BytesIO

import pandas as pd
import pytest

from app.core.baseline.raceroster_runners import (
    build_event_runners_from_results_df,
    convert_raceroster_workbook,
    filter_sheet_events,
    parse_time_to_seconds,
    suggest_event_for_sheet,
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
    out, skipped = build_event_runners_from_results_df(df, "10k", 10.0)
    assert skipped == 1
    assert len(out) == 2
    assert list(out.columns) == ["event", "runner_id", "pace", "distance", "start_offset"]
    assert out["event"].tolist() == ["10k", "10k"]
    assert out["runner_id"].tolist() == ["101", "102"]
    assert out["distance"].tolist() == [10, 10]
    assert out.iloc[0]["start_offset"] == 2


def test_anonymize_replaces_bibs():
    df = pd.DataFrame(
        {
            "No.": [101, 102],
            "Gun Time": ["35:20", "36:00"],
            "Chip Time": ["35:18", "35:58"],
        }
    )
    used = {"already"}
    out, skipped = build_event_runners_from_results_df(
        df, "5k", 5.0, anonymize=True, used_runner_ids=used
    )
    assert skipped == 0
    assert out["runner_id"].tolist() != ["101", "102"]
    assert "101" not in out["runner_id"].tolist()
    assert len(out["runner_id"].unique()) == 2
    assert "already" in used
    assert used.issuperset(set(out["runner_id"].tolist()))
    for rid in out["runner_id"]:
        assert len(str(rid)) == 7
        assert str(rid).isalnum()


def test_suggest_event_for_sheet_active_catalog():
    assert suggest_event_for_sheet("5K Open") == "5k"
    assert suggest_event_for_sheet("5K Elite") == "5k"
    assert suggest_event_for_sheet("10K") == "10k"
    assert suggest_event_for_sheet("Half Marathon") == "half"
    assert suggest_event_for_sheet("Full Marathon") == "full"
    assert suggest_event_for_sheet("Mystery") is None


def test_filter_sheet_events():
    selected = filter_sheet_events(["10k", "full"])
    assert [row[1] for row in selected] == ["10k", "full"]
    with pytest.raises(ValueError, match="No matching events"):
        filter_sheet_events(["ultra"])


def _xlsx_bytes_from_frames(sheets: dict) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def test_convert_raceroster_workbook_preview_and_anonymize():
    sheets = {
        "5K Open": pd.DataFrame(
            {
                "No.": [1, 2, 3],
                "Gun Time": ["20:00", "21:00", "22:00"],
                "Chip Time": ["19:50", "20:50", None],
            }
        ),
        "10K": pd.DataFrame(
            {
                "No.": [10, 11],
                "Gun Time": ["45:00", "46:00"],
                "Chip Time": ["44:50", "45:55"],
            }
        ),
    }
    data = _xlsx_bytes_from_frames(sheets)
    result = convert_raceroster_workbook(
        data,
        {"5K Open": "5k", "10K": "10k"},
        anonymize=True,
        source_filenames=["FM Results.xlsx"],
    )
    assert set(result["events"]) == {"5k", "10k"}
    assert result["preview"]["5k"]["participants"] == 2
    assert result["preview"]["5k"]["skipped_no_chip"] == 1
    assert result["preview"]["10k"]["participants"] == 2
    assert result["provenance"]["anonymized"] is True
    assert result["provenance"]["source_filenames"] == ["FM Results.xlsx"]
    fivek = result["frames"]["5k"]
    assert "1" not in fivek["runner_id"].astype(str).tolist()
    assert list(fivek.columns) == [
        "event",
        "runner_id",
        "pace",
        "distance",
        "start_offset",
    ]
