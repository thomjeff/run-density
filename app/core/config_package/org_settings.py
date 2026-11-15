"""
Org-level Settings catalog (Issue #966).

Single source of truth for Build/Plan resource types and related org catalogs.
Persists under ``runflow/org/settings.json``. Seed defaults come from
``schema.DEFAULT_PACKAGE_RESOURCES`` and ``constants`` when the file is absent.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from app.core.locations.schema import (
    DEFAULT_PACKAGE_RESOURCES,
    normalize_resource_registry,
)
from app.utils.constants import (
    COURSE_DISTANCES,
    DAY_SHORT_CODES,
    DISPLAY_TIMEZONE,
    FLOW_TYPE_CHOICES,
    LOCATION_TYPE_CHOICES,
    RACE_EVENTS,
    SEGMENT_DIRECTION_CHOICES,
    SEGMENT_SCHEMA_CHOICES,
)
from app.utils.run_id import get_runflow_root

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "settings.json"
SCHEMA_VERSION = 1


def get_org_settings_path() -> Path:
    return get_runflow_root() / "org" / SETTINGS_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _choice_dicts(values: Sequence[Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in values:
        if isinstance(item, Mapping):
            value = str(
                item.get("value") or item.get("id") or item.get("code") or ""
            ).strip()
            label = str(item.get("label") or value).strip() or value
            if value:
                out.append({"value": value, "label": label})
            continue
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            value = str(item[0]).strip()
            label = str(item[1]).strip() or value
            if value:
                out.append({"value": value, "label": label})
            continue
        value = str(item).strip()
        if value:
            out.append({"value": value, "label": value})
    return out


def default_org_settings() -> Dict[str, Any]:
    """In-code seed used when settings.json is missing."""
    return {
        "schema_version": SCHEMA_VERSION,
        "updated": None,
        "display_timezone": DISPLAY_TIMEZONE,
        "resources": deepcopy(DEFAULT_PACKAGE_RESOURCES),
        "location_types": [
            {"value": t, "label": str(t).capitalize()} for t in LOCATION_TYPE_CHOICES
        ],
        "event_choices": [
            {"value": e["id"], "label": e.get("label") or e["id"]} for e in RACE_EVENTS
        ],
        "distance_choices": [
            {"value": d["id"], "label": d.get("label") or d["id"]}
            for d in COURSE_DISTANCES
        ],
        "day_short_codes": list(DAY_SHORT_CODES),
        "segment_schema_choices": _choice_dicts(SEGMENT_SCHEMA_CHOICES),
        "segment_direction_choices": _choice_dicts(SEGMENT_DIRECTION_CHOICES),
        "flow_type_choices": _choice_dicts(FLOW_TYPE_CHOICES),
    }


def _merge_settings(raw: Mapping[str, Any]) -> Dict[str, Any]:
    base = default_org_settings()
    if not isinstance(raw, Mapping):
        return base
    out = dict(base)
    out["schema_version"] = int(raw.get("schema_version") or SCHEMA_VERSION)
    out["updated"] = raw.get("updated")
    out["display_timezone"] = (
        str(raw.get("display_timezone") or DISPLAY_TIMEZONE).strip() or DISPLAY_TIMEZONE
    )
    out["resources"] = normalize_resource_registry(raw.get("resources"))
    for key in (
        "location_types",
        "event_choices",
        "distance_choices",
        "segment_schema_choices",
        "segment_direction_choices",
        "flow_type_choices",
    ):
        if isinstance(raw.get(key), list) and raw.get(key):
            out[key] = _choice_dicts(raw[key])
    if isinstance(raw.get("day_short_codes"), list) and raw.get("day_short_codes"):
        out["day_short_codes"] = [
            str(x).strip().lower() for x in raw["day_short_codes"] if str(x).strip()
        ]
    return out


def load_org_settings() -> Dict[str, Any]:
    path = get_org_settings_path()
    if not path.is_file():
        return default_org_settings()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read org settings %s: %s", path, exc)
        return default_org_settings()
    return _merge_settings(raw if isinstance(raw, dict) else {})


def save_org_settings(patch: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge ``patch`` into current settings and write settings.json."""
    current = load_org_settings()
    merged = dict(current)
    if "resources" in patch:
        merged["resources"] = normalize_resource_registry(patch.get("resources"))
    if "display_timezone" in patch and patch.get("display_timezone") is not None:
        tz = str(patch.get("display_timezone") or "").strip()
        if tz:
            merged["display_timezone"] = tz
    for key in (
        "location_types",
        "event_choices",
        "distance_choices",
        "segment_schema_choices",
        "segment_direction_choices",
        "flow_type_choices",
    ):
        if key in patch and isinstance(patch.get(key), list):
            merged[key] = _choice_dicts(patch[key])
    if "day_short_codes" in patch and isinstance(patch.get("day_short_codes"), list):
        merged["day_short_codes"] = [
            str(x).strip().lower() for x in patch["day_short_codes"] if str(x).strip()
        ]
    merged["schema_version"] = SCHEMA_VERSION
    merged["updated"] = _now_iso()

    path = get_org_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
        fh.write("\n")
    tmp.replace(path)
    logger.info("Saved org settings (%s resource types)", len(merged["resources"]))
    return merged


def org_resource_registry() -> List[Dict[str, str]]:
    return list(load_org_settings().get("resources") or DEFAULT_PACKAGE_RESOURCES)


def org_resource_codes() -> List[str]:
    return [str(r["code"]) for r in org_resource_registry()]
