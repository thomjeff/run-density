"""Issue #891: Overview ZIP exports and retired Reports page."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
from io import BytesIO

from app.routes.api_reports import (
    build_export_zip_bytes,
    export_entries_for_kind,
    is_human_report_name,
)
from app.routes.ui import reports as reports_page


def test_human_report_allow_list_matches_former_reports_page():
    assert is_human_report_name("Density.md")
    assert is_human_report_name("Flow.csv")
    assert is_human_report_name("Locations.csv")
    assert is_human_report_name("Passes.csv")
    assert is_human_report_name("finish_times.csv")
    assert is_human_report_name("finish_area_demand.pdf")
    assert not is_human_report_name("bins.parquet")
    assert not is_human_report_name("map_data_sun.json")
    assert not is_human_report_name("segment_windows_sun.csv")
    assert not is_human_report_name("runners.csv")


def test_export_entries_split_reports_and_data_files():
    entries = [
        {"name": "Density.md", "type": "report"},
        {"name": "bins.parquet", "type": "report"},
        {"name": "runners.csv", "type": "data_file"},
        {"name": "Flow.csv", "type": "report"},
    ]
    reports = export_entries_for_kind(entries, "reports")
    data_files = export_entries_for_kind(entries, "data_files")
    assert [e["name"] for e in reports] == ["Density.md", "Flow.csv"]
    assert [e["name"] for e in data_files] == ["runners.csv"]


def test_build_export_zip_uses_day_prefix_and_bytes(tmp_path):
    sun = tmp_path / "sun_Density.md"
    sun.write_text("density", encoding="utf-8")
    data = tmp_path / "runners.csv"
    data.write_text("id\n1\n", encoding="utf-8")
    zip_bytes = build_export_zip_bytes(
        [
            {"name": "Density.md", "day": "sun", "local_path": str(sun), "type": "report"},
        ],
        "reports",
    )
    with ZipFile(BytesIO(zip_bytes)) as zf:
        assert zf.namelist() == ["sun/Density.md"]
        assert zf.read("sun/Density.md") == b"density"


def test_reports_page_redirects_to_overview():
    source = Path("app/routes/ui.py").read_text(encoding="utf-8")
    assert "Issue #891" in source
    assert reports_page.__name__ == "reports"
    assert "_redirect_preserving_query" in source
    assert 'return _redirect_preserving_query(request, "/overview")' in source


def test_overview_has_export_buttons_and_nav_drops_reports():
    overview = Path("frontend/templates/pages/overview.html").read_text(encoding="utf-8")
    assert "rf-overview-exports" in overview
    assert "Reports (.zip)" in overview
    assert "Data Files (.zip)" in overview
    assert "Download Reports" not in overview
    assert "Download Data Files" not in overview
    assert "kind=reports" in overview
    assert "kind=data_files" in overview
    base = Path("frontend/templates/base.html").read_text(encoding="utf-8")
    assert 'href="/reports"' not in base
    chrome = Path("frontend/templates/partials/run_context.html").read_text(encoding="utf-8")
    assert 'data-results-path="/reports"' not in chrome
    assert 'id="run-context-open-reports"' in chrome
    assert "#rf-overview-exports" in chrome
