"""Issue #841: one-day analysis product chrome — day from run, no day dropdown."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_HTML = REPO_ROOT / "frontend" / "templates" / "base.html"
RUN_CONTEXT = REPO_ROOT / "frontend" / "templates" / "partials" / "run_context.html"
TEMPLATES_DIR = REPO_ROOT / "frontend" / "templates"


@pytest.fixture(scope="module")
def base_source() -> str:
    return BASE_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def run_context_source() -> str:
    return RUN_CONTEXT.read_text(encoding="utf-8")


def test_day_dropdown_removed(base_source: str):
    assert 'id="day-selector"' not in base_source
    assert "day-selector-wrap" not in base_source


def test_runflow_context_strips_day_from_results_url(base_source: str):
    assert "initRunflowContext" in base_source
    assert "Do not pass URL day" in base_source or "stale ?day=" in base_source
    assert 'p.delete("day")' in base_source
    assert 'setQueryParam(newHref, "day", null)' in base_source


def test_pick_run_navigates_without_day_query(base_source: str):
    assert '"/overview?run_id=" + encodeURIComponent(runId)' in base_source
    assert "rememberWorkspaceRoute(\"results\", dest)" in base_source or \
        'rememberWorkspaceRoute("results", dest)' in base_source


def test_active_run_strip_always_shows_day_when_known(base_source: str):
    assert "Issue #841: always show day as read-only run metadata when known" in base_source
    assert 'dayEl.textContent = "· " + String(day).toUpperCase()' in base_source
    # Old multi-day-only visibility gate removed
    assert "window.runflowDay.available.length > 1" not in base_source

def test_run_context_banner_shows_day_read_only(run_context_source: str):
    assert "always show day as read-only when known" in run_context_source
    assert "multiDay && day" not in run_context_source
    # Subnav is run_id-primary
    assert "day=' + encodeURIComponent(day)" not in run_context_source


def test_base_html_renders_without_day_selector():
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
        '{% block content %}<p id="rf-841-smoke">ok</p>{% endblock %}'
    )
    html = template.render(request=_Request(), cloud_mode=False)
    assert 'id="day-selector"' not in html
    assert 'id="rf-tabler-context-day"' in html
    assert 'id="rf-841-smoke"' in html
