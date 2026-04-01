"""Tests for Loc Sheets index builder."""

from __future__ import annotations

import json
from pathlib import Path

from app.utils.loc_sheets_list import build_loc_sheet_entries


def test_onepage_y_includes_location(tmp_path: Path) -> None:
    day = "sun"
    comp = tmp_path / day / "computation"
    comp.mkdir(parents=True)
    (comp / "locations_results.json").write_text(
        json.dumps(
            {
                "locations": [
                    {"loc_id": "L1", "loc_label": "A", "day": "sun", "onepage": "y"},
                    {"loc_id": "L2", "loc_label": "B", "day": "sun", "onepage": "n"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = build_loc_sheet_entries(tmp_path, day)
    assert len(out) == 1
    assert out[0]["loc_id"] == "L1"


def test_day_must_match_selected_day(tmp_path: Path) -> None:
    day = "sat"
    comp = tmp_path / day / "computation"
    comp.mkdir(parents=True)
    (comp / "locations_results.json").write_text(
        json.dumps(
            {
                "locations": [
                    {
                        "loc_id": 9,
                        "loc_label": "Nine",
                        "day": "sat",
                        "onepage": "y",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    out = build_loc_sheet_entries(tmp_path, day)
    assert len(out) == 1
    assert out[0]["loc_id"] == 9


def test_wrong_day_excluded(tmp_path: Path) -> None:
    day = "sat"
    comp = tmp_path / day / "computation"
    comp.mkdir(parents=True)
    (comp / "locations_results.json").write_text(
        json.dumps(
            {
                "locations": [
                    {
                        "loc_id": 1,
                        "loc_label": "Wrong day row",
                        "day": "sun",
                        "onepage": "y",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    out = build_loc_sheet_entries(tmp_path, day)
    assert len(out) == 0


def test_fallback_html_on_disk(tmp_path: Path) -> None:
    day = "sun"
    comp = tmp_path / day / "computation"
    html_dir = tmp_path / day / "reports" / "loc_sheets" / "html"
    comp.mkdir(parents=True)
    html_dir.mkdir(parents=True)
    (comp / "locations_results.json").write_text(
        json.dumps(
            {
                "locations": [
                    {"loc_id": "L9", "loc_label": "Nine", "day": "sun", "onepage": ""},
                ]
            }
        ),
        encoding="utf-8",
    )
    (html_dir / "L9.html").write_text("<html/>", encoding="utf-8")

    out = build_loc_sheet_entries(tmp_path, day)
    assert len(out) == 1
    assert out[0]["loc_id"] == "L9"
