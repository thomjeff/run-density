"""Issue #904: Build owns location edits; package inspect-only; Plan owns start times."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "frontend" / "templates"
JS = REPO_ROOT / "frontend" / "static" / "js"


def test_edit_locations_button_is_on_legs_not_package_card():
    workspace = (TEMPLATES / "partials" / "course_mapping_workspace.html").read_text(
        encoding="utf-8"
    )
    legs_card, rest = workspace.split('id="leg-locations-browser-card"', 1)
    package_locs = rest.split('id="locations-card"', 1)[1]
    assert 'id="btn-edit-locations-grid"' in rest.split('id="locations-card"', 1)[0]
    assert ">Edit Locations<" in rest.split('id="locations-card"', 1)[0]
    assert 'id="btn-edit-locations-grid"' not in package_locs.split("</section>", 1)[0]
    assert "Edit operations" not in package_locs.split("</section>", 1)[0]
    assert 'id="btn-manage-resources"' not in package_locs.split("</section>", 1)[0]
    assert 'id="btn-manage-resources-legs"' in workspace
    assert legs_card  # legs panel precedes the browser card


def test_location_grid_persists_via_org_legs():
    recipes = (JS / "map" / "segment_recipes.js").read_text(encoding="utf-8")
    grid = (JS / "map" / "location_grid_editor.js").read_text(encoding="utf-8")
    assert "initLegLocationGridEditor" in recipes
    assert "persistLegLocationsFromGrid" in recipes
    assert "collectFilteredLegLocationsForGrid" in recipes
    assert "Edit Locations · " in grid
    mapping = (JS / "map" / "course_mapping.js").read_text(encoding="utf-8")
    assert "locationGridEditor.init" not in mapping
    assert "if (isConfigPackageMode()) return false" in mapping or (
        "isConfigPackageMode()) return false" in mapping
    )


def test_edit_locations_modals_reparent_to_body_on_legs_hub():
    """Package workspace is display:none on Build → Legs; hub modals must leave it."""
    race_js = (JS / "race_configuration.js").read_text(encoding="utf-8")
    grid = (JS / "map" / "location_grid_editor.js").read_text(encoding="utf-8")
    assert "location-grid-modal" in race_js
    assert "location-grid-bulk-modal" in race_js
    assert "location-grid-unsaved-modal" in race_js
    assert "document.body.appendChild(modal)" in grid


def test_package_combined_course_is_inspect_only():
    mapping = (JS / "map" / "course_mapping.js").read_text(encoding="utf-8")
    recipes = (JS / "map" / "segment_recipes.js").read_text(encoding="utf-8")
    assert "zoomToSegmentOnPreview" in mapping
    assert "focusCoursePreviewLocation" in recipes
    assert "legacyWrap.style.display = 'none'" in recipes


def test_plan_overview_owns_run_analysis():
    overview = (TEMPLATES / "pages" / "overview.html").read_text(encoding="utf-8")
    race = (TEMPLATES / "pages" / "race_configuration.html").read_text(encoding="utf-8")
    plan_js = (JS / "plan_run_analysis.js").read_text(encoding="utf-8")
    assert 'id="rf-plan-new-analysis"' in overview
    assert 'id="rf-plan-package-select"' in overview
    assert 'id="rf-plan-run-analysis"' in overview
    assert "plan_run_analysis.js" in overview
    assert "run_analysis_modal.html" in overview
    assert 'id="btn-run-package-analysis"' not in race
    assert "/run-analysis" in plan_js
    assert "/analyze-setup" in plan_js
    saved = (JS / "map" / "saved_courses.js").read_text(encoding="utf-8")
    assert "function openRunAnalysisModal" not in saved
    assert "function runPackageAnalysis" not in saved


def test_org_leg_location_puts_do_not_fan_out_to_packages():
    src = (
        REPO_ROOT / "app" / "core" / "config_package" / "org_leg_library.py"
    ).read_text(encoding="utf-8")
    start = src.index("_PACKAGE_SYNC_FIELDS = (")
    end = src.index(")", start)
    block = src[start:end]
    assert '"locations"' not in block
    assert "'locations'" not in block
