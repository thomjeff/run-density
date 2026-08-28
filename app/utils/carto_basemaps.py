"""
CARTO raster basemap URLs (Issue #908).

Raster PNG tiles require CARTO_BASEMAP_KEY. The key is never committed;
it is read from the environment at call time.
"""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib.parse import quote

from fastapi.templating import Jinja2Templates

from app.utils.env import env_str

CARTO_VOYAGER_TILE_TEMPLATE = (
    "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
)
CARTO_LIGHT_TILE_TEMPLATE = (
    "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
)
CARTO_DARK_TILE_TEMPLATE = (
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
)
CARTO_TILE_SUBDOMAINS = ["a", "b", "c", "d"]
CARTO_MAX_ZOOM = 20
CARTO_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, '
    '&copy; <a href="https://carto.com/attributions">CARTO</a>'
)

_MISSING_KEY = (
    "CARTO_BASEMAP_KEY is required for CARTO raster basemaps (Issue #908). "
    "Set it in dev.env or cloud.env; do not commit the key."
)


def get_carto_basemap_key() -> str:
    key = env_str("CARTO_BASEMAP_KEY", "").strip()
    if not key:
        raise RuntimeError(_MISSING_KEY)
    return key


def _with_key(url_template: str) -> str:
    key = get_carto_basemap_key()
    joiner = "&" if "?" in url_template else "?"
    return f"{url_template}{joiner}key={quote(key, safe='')}"


def carto_voyager_tile_url() -> str:
    return _with_key(CARTO_VOYAGER_TILE_TEMPLATE)


def carto_light_tile_url() -> str:
    return _with_key(CARTO_LIGHT_TILE_TEMPLATE)


def carto_dark_tile_url() -> str:
    return _with_key(CARTO_DARK_TILE_TEMPLATE)


def frontend_tile_config() -> Dict[str, Any]:
    return {
        "voyagerUrl": carto_voyager_tile_url(),
        "lightUrl": carto_light_tile_url(),
        "darkUrl": carto_dark_tile_url(),
        "attribution": CARTO_ATTRIBUTION,
        "subdomains": "".join(CARTO_TILE_SUBDOMAINS),
        "maxZoom": CARTO_MAX_ZOOM,
    }


def map_tiles_json_or_null() -> str:
    try:
        return json.dumps(frontend_tile_config())
    except RuntimeError:
        return "null"


def register_jinja_map_tiles(templates: Jinja2Templates) -> None:
    templates.env.globals["runflow_map_tiles_json"] = map_tiles_json_or_null
