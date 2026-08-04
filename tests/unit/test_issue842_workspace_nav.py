"""Issue #842: Results/Build workspace selector chrome."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_HTML = REPO_ROOT / "frontend" / "templates" / "base.html"
TEMPLATES_DIR = REPO_ROOT / "frontend" / "templates"


@pytest.fixture(scope="module")
def base_source() -> str:
    return BASE_HTML.read_text(encoding="utf-8")


def test_workspace_dropdown_markup(base_source: str):
    assert 'id="rf-workspace-dropdown"' in base_source
    assert 'id="rf-workspace-label"' in base_source
    assert 'data-workspace="results"' in base_source
    assert 'data-workspace="build"' in base_source
    assert "initWorkspaceControl" in base_source
    assert "switchWorkspace" in base_source


def test_build_hub_links_in_top_nav(base_source: str):
    assert 'data-rf-build-view="legs"' in base_source
    assert 'data-rf-build-view="courses"' in base_source
    assert 'data-rf-build-view="packages"' in base_source
    assert 'class="nav-item rf-build-chrome"' in base_source
    # Old single Build link removed from local chrome
    assert 'title="Legs, Courses, and Packages"' not in base_source


def test_build_page_has_no_in_page_hub_tabs():
    src = (REPO_ROOT / "frontend" / "templates" / "pages" / "race_configuration.html").read_text(
        encoding="utf-8"
    )
    assert "race-config-hub-tab" not in src
    assert 'id="race-config-page-title"' in src
    assert "Shared routes and locations" in src


def test_results_chrome_class_on_run_controls(base_source: str):
    assert "rf-results-chrome" in base_source
    assert 'id="rf-runs-dropdown"' in base_source
    assert "WS_LAST_RESULTS" in base_source
    assert "WS_LAST_BUILD" in base_source
    assert "rf_last_results_path" in base_source
    assert "rf_last_build_path" in base_source


def test_build_does_not_show_active_run_strip(base_source: str):
    assert "Build never shows Active-run strip" in base_source
    assert 'strip.hidden = onBuild' in base_source


def test_base_html_renders_workspace_control():
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
        '{% block content %}<p id="rf-842-smoke">ok</p>{% endblock %}'
    )
    html = template.render(request=_Request(), cloud_mode=False)
    assert 'id="rf-workspace-dropdown"' in html
    assert 'data-rf-build-view="courses"' in html
    assert 'id="rf-842-smoke"' in html
    assert 'id="day-selector"' not in html
