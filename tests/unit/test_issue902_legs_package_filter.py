"""Issue #902: Build → Legs package filter of org library."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "frontend" / "templates"
JS = REPO_ROOT / "frontend" / "static" / "js"


def test_legs_hub_has_package_filter_dropdown():
    workspace = (TEMPLATES / "partials" / "course_mapping_workspace.html").read_text(
        encoding="utf-8"
    )
    legs_card = workspace.split('id="course-legs-card"', 1)[1].split(
        'id="leg-locations-browser-card"', 1
    )[0]
    assert 'id="legs-hub-package-filter"' in legs_card
    assert "All packages" in legs_card
    assert 'id="course-legs-package-empty"' in legs_card


def test_package_filter_hooks_exist_and_move_dropdown_stays_full_library():
    recipes = (JS / "map" / "segment_recipes.js").read_text(encoding="utf-8")
    assert "function getPackageFilteredLegs" in recipes
    assert "function loadPackageFilterLegIds" in recipes
    assert "function collectRecipeLegIds" in recipes
    assert "legsTableBoundsFilter.setAllItems(getPackageFilteredLegs())" in recipes
    assert "packageFilterLegIds && (!legId || !packageFilterLegIds[String(legId)])" in recipes
    # Move-to-leg dropdown still iterates the full org library
    assert "(libraryState && libraryState.legs || []).forEach(function (leg)" in recipes
    assert "This package has no assigned courses yet" in (
        TEMPLATES / "partials" / "course_mapping_workspace.html"
    ).read_text(encoding="utf-8")
    assert "Showing " in recipes and " of " in recipes and " legs for " in recipes
    assert "return null;" in recipes.split("function collectRecipeLegIds", 1)[1][:800]
