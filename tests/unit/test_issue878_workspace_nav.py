"""Issue #878: Build / Plan / Execute workspace chrome."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_HTML = REPO_ROOT / "frontend" / "templates" / "base.html"
OVERVIEW = REPO_ROOT / "frontend" / "templates" / "pages" / "overview.html"
EXECUTE = REPO_ROOT / "frontend" / "templates" / "pages" / "execute.html"
RACE_CONFIG = REPO_ROOT / "frontend" / "templates" / "pages" / "race_configuration.html"
TEMPLATES_DIR = REPO_ROOT / "frontend" / "templates"


@pytest.fixture(scope="module")
def base_source() -> str:
    return BASE_HTML.read_text(encoding="utf-8")


def test_workspace_picks_are_build_plan_execute(base_source: str):
    assert 'data-workspace="build"' in base_source
    assert 'data-workspace="plan"' in base_source
    assert 'data-workspace="execute"' in base_source
    assert 'data-workspace="results"' not in base_source
    assert "normalizeWorkspace" in base_source
    assert 'v === "plan" || v === "results"' in base_source


def test_build_nav_includes_runners_between_courses_and_packages(base_source: str):
    courses = base_source.find('data-rf-build-view="courses"')
    runners = base_source.find('data-rf-build-view="runners"')
    packages = base_source.find('data-rf-build-view="packages"')
    assert courses != -1 and runners != -1 and packages != -1
    assert courses < runners < packages


def test_plan_chrome_has_no_package_top_nav(base_source: str):
    assert 'id="rf-tabler-package-nav"' not in base_source
    assert 'id="rf-tabler-open-package"' not in base_source
    overview = OVERVIEW.read_text(encoding="utf-8")
    assert "attachPackageMeta" in overview
    assert "Package Name" in (
        REPO_ROOT / "frontend" / "static" / "js" / "run_overview.js"
    ).read_text(encoding="utf-8")


def test_execute_placeholder_has_no_locations_nav(base_source: str):
    assert 'href="/execute"' in base_source
    assert "rf-execute-chrome" in base_source
    assert 'data-rf-execute-view="1"' in base_source
    execute = EXECUTE.read_text(encoding="utf-8")
    assert "placeholder" in execute.lower() or "coming later" in execute.lower()
    assert "Plan → Locations" in execute
    # Execute landing must not add a second Locations object/UI
    assert 'href="/locations"' not in execute


def test_runners_hub_panel_exists():
    src = RACE_CONFIG.read_text(encoding="utf-8")
    assert 'id="race-config-hub-runners"' in src
    assert 'id="race-config-runners-tbody"' in src
    assert "Import actuals" in src
    assert 'id="package-runner-dataset-select"' in (
        REPO_ROOT / "frontend" / "templates" / "partials" / "runners_baseline_body.html"
    ).read_text(encoding="utf-8")
    assert 'id="race-config-new-runners-dataset"' in src
    js = (REPO_ROOT / "frontend" / "static" / "js" / "runner_datasets.js").read_text(
        encoding="utf-8"
    )
    assert "/api/org/runners" in js
    assert "compatible_datasets" in js or "runner-datasets" in js


def test_package_header_owns_readiness_and_run_analysis():
    header = RACE_CONFIG.read_text(encoding="utf-8")
    assign = (
        REPO_ROOT / "frontend" / "templates" / "partials" / "course_mapping_workspace.html"
    ).read_text(encoding="utf-8")
    header_card = header.split('id="config-package-details-card"', 1)[1]
    header_card = header_card.split('id="race-config-tab-workspace"', 1)[0]
    assert 'id="btn-run-package-analysis"' in header_card
    assert 'id="package-readiness-checklist"' in header_card
    assert "EVENT DAY" in header_card
    assert header_card.find("EVENT DAY") < header_card.find('id="package-readiness-checklist"')
    assert 'id="btn-run-package-analysis"' not in assign
    assert 'id="package-readiness-checklist"' not in assign
    assert 'id="btn-build-race-exports"' in assign


def test_package_courses_does_not_auto_open_event_recipes():
    js = (
        REPO_ROOT / "frontend" / "static" / "js" / "map" / "segment_recipes.js"
    ).read_text(encoding="utf-8")
    assert "syncCoursePanelUi({ autoOpen: true })" not in js
    shown = js.split("function onCourseTabShown()", 1)[1].split("function deleteLeg", 1)[0]
    assert "autoOpen: false" in shown
    assert "recipesModalDismissed = false" not in shown


def test_package_runners_tab_has_dataset_metrics():
    body = (
        REPO_ROOT / "frontend" / "templates" / "partials" / "runners_baseline_body.html"
    ).read_text(encoding="utf-8")
    assert 'id="package-runner-dataset-metrics"' in body
    js = (REPO_ROOT / "frontend" / "static" / "js" / "runner_datasets.js").read_text(
        encoding="utf-8"
    )
    assert "renderPackageDatasetMetrics" in js
    assert "P50 (Median)" in js


def test_base_html_renders_plan_execute_chrome():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    class _Url:
        path = "/overview"

    class _Request:
        url = _Url()
        query_params = {}

    template = env.from_string(
        '{% extends "base.html" %}\n'
        '{% block content %}<p id="rf-878-smoke">ok</p>{% endblock %}'
    )
    html = template.render(request=_Request(), cloud_mode=False)
    assert 'data-workspace="plan"' in html
    assert 'data-workspace="execute"' in html
    assert 'data-rf-build-view="runners"' in html
    assert 'id="rf-878-smoke"' in html
    assert 'id="rf-tabler-open-package"' not in html
