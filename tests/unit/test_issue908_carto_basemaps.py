"""Issue #908: CARTO raster basemaps require CARTO_BASEMAP_KEY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.utils import carto_basemaps as carto


REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def carto_key(monkeypatch):
    monkeypatch.setenv("CARTO_BASEMAP_KEY", "test-key-issue-908")
    return "test-key-issue-908"


def test_missing_key_fails_fast(monkeypatch):
    monkeypatch.delenv("CARTO_BASEMAP_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CARTO_BASEMAP_KEY"):
        carto.get_carto_basemap_key()


def test_tile_urls_append_key_query(carto_key):
    voyager = carto.carto_voyager_tile_url()
    light = carto.carto_light_tile_url()
    dark = carto.carto_dark_tile_url()
    assert voyager.endswith("?key=test-key-issue-908")
    assert light.endswith("?key=test-key-issue-908")
    assert dark.endswith("?key=test-key-issue-908")
    assert "{s}" in voyager and "{z}" in voyager
    assert "rastertiles/voyager" in voyager
    assert "light_all" in light
    assert "dark_all" in dark


def test_frontend_config_json_roundtrip(carto_key):
    cfg = carto.frontend_tile_config()
    dumped = json.loads(carto.map_tiles_json_or_null())
    assert dumped["voyagerUrl"] == cfg["voyagerUrl"]
    assert dumped["attribution"]
    assert "OpenStreetMap" in dumped["attribution"]
    assert "carto.com/attributions" in dumped["attribution"]
    assert dumped["maxZoom"] == 20
    assert dumped["subdomains"] == "abcd"


def test_map_tiles_json_null_without_key(monkeypatch):
    monkeypatch.delenv("CARTO_BASEMAP_KEY", raising=False)
    assert carto.map_tiles_json_or_null() == "null"


def test_base_html_injects_map_tiles(carto_key):
    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "frontend" / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["runflow_map_tiles_json"] = carto.map_tiles_json_or_null

    class _Url:
        path = "/overview"

    class _Request:
        url = _Url()
        query_params = {}

    template = env.from_string(
        '{% extends "base.html" %}\n'
        "{% block content %}<p>ok</p>{% endblock %}"
    )
    html = template.render(request=_Request(), cloud_mode=False)
    assert "window.RUNFLOW_MAP_TILES" in html
    assert "test-key-issue-908" in html
    assert "basemaps.cartocdn.com" in html


def test_frontend_js_does_not_hardcode_carto_tile_urls():
    js_root = REPO_ROOT / "frontend" / "static" / "js"
    offenders = []
    for path in js_root.rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        if "basemaps.cartocdn.com" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
