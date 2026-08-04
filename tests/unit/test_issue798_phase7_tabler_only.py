"""Issue #798 Phase 7: Tabler is the sole admin chrome in base.html."""

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


def test_base_html_always_tabler_no_classic(base_source: str):
    assert 'class="rf-tabler"' in base_source
    assert "@tabler/core@1.4.0/dist/css/tabler.min.css" in base_source
    assert "@tabler/core@1.4.0/dist/js/tabler.min.js" in base_source
    assert "/static/css/common.css" in base_source
    assert "/static/css/tabler_spike.css" in base_source

    assert "Classic UI" not in base_source
    assert "rf-tabler-exit" not in base_source
    assert "tabler_ui" not in base_source
    assert "Race Density & Flow Intelligence</div>" not in base_source  # classic tagline
    assert "{% if not tabler_ui %}" not in base_source
    assert 'href="/overview?ui=tabler"' not in base_source
    assert 'params.set("ui", "tabler")' not in base_source
    assert "Opt-in via ?ui=tabler" not in base_source


def test_base_html_jinja_render_smoke():
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
        '{% block content %}<p id="rf-phase7-smoke">ok</p>{% endblock %}'
    )
    html = template.render(request=_Request(), cloud_mode=False)

    assert 'class="rf-tabler"' in html
    assert "@tabler/core@1.4.0/dist/css/tabler.min.css" in html
    assert "@tabler/core@1.4.0/dist/js/tabler.min.js" in html
    assert "Classic UI" not in html
    assert "rf-tabler-exit" not in html
    assert 'id="day-selector"' not in html  # Issue #841: day from run, no dropdown
    assert "initRunflowContext" in html
    assert 'id="rf-runs-dropdown"' in html
    assert 'id="rf-tabler-context-strip"' in html
    assert 'id="rf-tabler-context-day"' in html
    assert 'id="rf-phase7-smoke"' in html


def test_base_html_no_day_selector_markup(base_source: str):
    """Issue #841: multi-day day dropdown removed from product chrome."""
    assert 'id="day-selector"' not in base_source
    assert 'id="day-selector-wrap"' not in base_source
    assert "setDaySelectorVisible" not in base_source
    assert "initDaySelector" not in base_source
    assert "initRunflowContext" in base_source
    assert 'id="rf-tabler-context-day"' in base_source
    # Results nav is run_id-primary (day stripped from analysis links)
    assert 'setQueryParam(newHref, "day", null)' in base_source
    assert '"/overview?run_id=" + encodeURIComponent(runId)' in base_source
    assert "initWorkspaceControl" in base_source
