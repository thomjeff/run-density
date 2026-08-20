"""Issue #888: Density absorbs Segments map/metadata and assessment layout."""

from __future__ import annotations

from pathlib import Path

from app.common.config import los_reference_rows
from app.routes.api_density import _format_field_window
from app.routes.ui import segments as segments_page


def test_segments_page_redirects_to_density():
    source = Path("app/routes/ui.py").read_text(encoding="utf-8")
    assert "Issue #888" in source
    assert segments_page.__name__ == "segments"
    assert 'return _redirect_preserving_query(request, "/density")' in source


def test_nav_and_density_html_drop_standalone_segments_workspace():
    base = Path("frontend/templates/base.html").read_text(encoding="utf-8")
    chrome = Path("frontend/templates/partials/run_context.html").read_text(encoding="utf-8")
    density = Path("frontend/templates/pages/density.html").read_text(encoding="utf-8")
    assert 'href="/segments"' not in base
    assert 'data-results-path="/segments"' not in chrome
    assert 'id="segments-map"' in density
    assert "<th>Peak Window</th>" in density
    assert "<th>Width</th>" in density
    assert "<th>Schema</th>" not in density
    assert "Peak Density" in density  # assessment, not master table
    assert "Field Window" in density
    assert "Density through space &amp; time" in density
    assert 'id="rf-view-flagged-bins"' in density
    assert 'id="rf-bin-modal"' in density
    assert "Bin-Level Details" not in density
    assert "los_reference.html" in density
    assert "rf-density-los-ref" in density
    assert "rf-density-analysis-scroll" in density
    assert "<details>" not in density
    assert "onDensitySegmentSelect" in density
    assert "emphasizeSegmentOnMap" in density


def test_segments_js_density_mode_avoids_aggressive_filter():
    source = Path("frontend/static/js/map/segments.js").read_text(encoding="utf-8")
    assert "isDensityWorkspace" in source
    assert "emphasizeSegmentOnMap" in source
    assert "hoverSegmentOnMap" in source
    assert "elapsed_km" in source
    assert "formatElapsedKm" in source


def test_field_window_formats_occupancy_first_last():
    assert _format_field_window("07:00", "08:54") == "07:00–08:54"
    assert _format_field_window(None, "08:54") == "N/A"


def test_los_reference_rows_use_rulebook_not_a_second_table():
    rows = los_reference_rows()
    by_grade = {row["grade"]: row for row in rows}
    assert by_grade["A"]["range"] == "0.00 – 0.36"
    assert by_grade["F"]["range"] == "1.63+"
    assert "Free" in by_grade["A"]["label"] or "free" in by_grade["A"]["label"].lower()
