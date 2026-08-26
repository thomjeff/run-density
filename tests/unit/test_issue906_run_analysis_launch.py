"""Issue #906: New analysis button + package picker; launch from Build package."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "frontend" / "templates"
JS = REPO_ROOT / "frontend" / "static" / "js"


def test_overview_new_analysis_is_a_button_not_a_package_tile():
    overview = (TEMPLATES / "pages" / "overview.html").read_text(encoding="utf-8")
    assert 'id="rf-plan-new-analysis"' in overview
    assert ">New analysis<" in overview
    assert 'id="rf-plan-package-select"' not in overview
    assert 'id="rf-plan-run-analysis"' not in overview
    assert "run_analysis_modal.html" in overview


def test_package_picker_lists_name_and_id():
    modal = (TEMPLATES / "partials" / "run_analysis_modal.html").read_text(
        encoding="utf-8"
    )
    js = (JS / "plan_run_analysis.js").read_text(encoding="utf-8")
    assert 'id="package-picker-modal"' in modal
    assert 'id="package-picker-select"' in modal
    assert "name" in modal.lower() and "ID" in modal
    assert "openPackagePicker" in js
    assert "(pkg.label || pkg.config_id)" in js
    assert "pkg.config_id" in js
    assert "dataset.ready" in js
    assert "openRunAnalysisForPackage" in js


def test_build_package_run_analysis_skips_picker():
    race = (TEMPLATES / "pages" / "race_configuration.html").read_text(encoding="utf-8")
    js = (JS / "plan_run_analysis.js").read_text(encoding="utf-8")
    saved = (JS / "map" / "saved_courses.js").read_text(encoding="utf-8")
    header_card = race.split('id="config-package-details-card"', 1)[1]
    header_card = header_card.split('id="race-config-tab-workspace"', 1)[0]
    assert 'id="btn-run-package-analysis"' in header_card
    assert "run_analysis_modal.html" in race
    assert "openRunAnalysisForPackage" in js
    assert "btn-run-package-analysis" in js
    assert "function openRunAnalysisModal" not in saved
    assert "function runPackageAnalysis" not in saved
    assert "function openPackagePicker" not in saved
