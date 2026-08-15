"""HTML location one-pagers without in-run PDFs (#871)."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.one_pager import generate_location_onepagers
from app.utils.loc_sheets_list import zip_loc_sheet_html


def test_generate_writes_html_not_pdf(tmp_path: Path) -> None:
    loc = {
        "loc_id": 12,
        "pass_id": 12,
        "day": "sun",
        "onepage": "y",
        "loc_label": "Churchill",
        "loc_type": "traffic",
        "lat": 45.27,
        "lon": -66.06,
        "notes": "Stay visible",
        "equipment": "Radio",
        "contact": "HQ",
        "vol_count": 2,
    }
    (tmp_path / "locations_results.json").write_text(
        json.dumps({"locations": [loc]}), encoding="utf-8"
    )
    pd.DataFrame(
        [
            {
                "loc_id": 12,
                "first_runner": "07:10:00",
                "last_runner": "08:00:00",
                "loc_start": "06:25:00",
                "loc_end": "08:30:00",
                "duration": 125,
                "peak_start": "07:20:00",
                "peak_end": "07:50:00",
            }
        ]
    ).to_csv(tmp_path / "Locations.csv", index=False)

    out = tmp_path / "loc_sheets"
    n = generate_location_onepagers(
        run_id="testrun",
        day="sun",
        locations_results_json_path=tmp_path / "locations_results.json",
        locations_report_csv_path=tmp_path / "Locations.csv",
        output_dir=out,
    )
    assert n == 1
    html_path = out / "html" / "12.html"
    assert html_path.is_file()
    assert not (out / "pdf").exists()
    text = html_path.read_text(encoding="utf-8")
    assert "Churchill" in text
    assert "leaflet" in text.lower()
    assert "data:image/png" not in text


def test_zip_loc_sheet_html_uses_existing_files(tmp_path: Path) -> None:
    html_dir = tmp_path / "sun" / "reports" / "loc_sheets" / "html"
    html_dir.mkdir(parents=True)
    (html_dir / "1.html").write_text("<html>one</html>", encoding="utf-8")
    (html_dir / "2.html").write_text("<html>two</html>", encoding="utf-8")
    payload = zip_loc_sheet_html(tmp_path, "sun")
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        names = set(zf.namelist())
    assert names == {"1.html", "2.html"}
