"""
SSOT for config-package location records and locations.csv export columns.

Issue #765: Package resource registry (FPF, YSSR, AWP, VOL + user-defined orgs).
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence

from app.utils.constants import COURSE_EVENT_IDS

# Stable 2027 defaults; packages may add more via config.json "resources".
DEFAULT_PACKAGE_RESOURCES: List[Dict[str, str]] = [
    {"code": "fpf", "label": "FPF"},
    {"code": "yssr", "label": "YSSR"},
    {"code": "awp", "label": "AWP"},
    {"code": "vol", "label": "VOL"},
]

_RESOURCE_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,15}$")

LOCATIONS_CSV_PREFIX_COLUMNS: List[str] = [
    "loc_id",
    "loc_label",
    "loc_type",
    "lat",
    "lon",
    "proxy_loc_id",
    "seg_id",
    "day",
    "zone",
    "full",
    "half",
    "10k",
    "elite",
    "open",
    "buffer",
    "interval",
]

LOCATIONS_CSV_SUFFIX_COLUMNS: List[str] = [
    "onepage",
    "equipment",
    "contact",
    "notes",
]

EVENT_FLAG_COLUMNS: List[str] = list(COURSE_EVENT_IDS)


def count_column(resource_code: str) -> str:
    return f"{resource_code.strip().lower()}_count"


def normalize_resource_code(code: str) -> str:
    normalized = (code or "").strip().lower()
    if not normalized or not _RESOURCE_CODE_RE.match(normalized):
        raise ValueError(
            f"Invalid resource code '{code}': use lowercase letters, digits, underscore; "
            "must start with a letter."
        )
    return normalized


def normalize_resource_registry(
    resources: Optional[Sequence[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    """Return validated resource registry; default to FPF/YSSR/AWP/VOL when empty."""
    if not resources:
        return deepcopy(DEFAULT_PACKAGE_RESOURCES)

    seen: set[str] = set()
    out: List[Dict[str, str]] = []
    for item in resources:
        if not isinstance(item, dict):
            continue
        code = normalize_resource_code(str(item.get("code", "")))
        if code in seen:
            raise ValueError(f"Duplicate resource code: {code}")
        seen.add(code)
        label = (item.get("label") or code).strip() or code.upper()
        out.append({"code": code, "label": label})
    if not out:
        return deepcopy(DEFAULT_PACKAGE_RESOURCES)
    return out


def ensure_manifest_resources(manifest: Dict[str, Any]) -> List[Dict[str, str]]:
    """Ensure config.json manifest has a resources list; return normalized registry."""
    registry = normalize_resource_registry(manifest.get("resources"))
    manifest["resources"] = registry
    return registry


def locations_csv_columns(resource_codes: Sequence[str]) -> List[str]:
    codes = [normalize_resource_code(c) for c in resource_codes]
    count_cols = [count_column(c) for c in codes]
    return (
        list(LOCATIONS_CSV_PREFIX_COLUMNS)
        + count_cols
        + list(LOCATIONS_CSV_SUFFIX_COLUMNS)
    )


def _yn(value: Any, default: str = "n") -> str:
    if value is None or value == "":
        return default
    s = str(value).strip().lower()
    if s in ("y", "yes", "true", "1"):
        return "y"
    if s in ("n", "no", "false", "0"):
        return "n"
    return default


def _default_location_fields() -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "loc_label": "",
        "loc_type": "course",
        "lat": "",
        "lon": "",
        "proxy_loc_id": "",
        "seg_id": "",
        "day": "",
        "zone": "",
        "buffer": 10,
        "interval": 5,
        "onepage": "n",
        "equipment": "",
        "contact": "",
        "notes": "",
    }
    for ev in EVENT_FLAG_COLUMNS:
        fields[ev] = "n"
    return fields


def _sync_resources_dict(
    loc: Dict[str, Any], resource_codes: Sequence[str]
) -> Dict[str, int]:
    """Merge flat *_count columns and nested resources into resources dict."""
    resources = loc.get("resources")
    if not isinstance(resources, dict):
        resources = {}
    for code in resource_codes:
        col = count_column(code)
        if col in loc and loc[col] not in (None, ""):
            try:
                resources[code] = int(float(loc[col]))
            except (TypeError, ValueError):
                resources[code] = 0
        elif code not in resources:
            resources[code] = 0
        else:
            try:
                resources[code] = int(resources[code])
            except (TypeError, ValueError):
                resources[code] = 0
        loc[count_column(code)] = resources[code]
    loc["resources"] = resources
    return resources


def normalize_location_record(
    loc: Dict[str, Any],
    resource_codes: Sequence[str],
    *,
    index: int = 0,
) -> Dict[str, Any]:
    """Normalize a course.json location object for editor + export."""
    if not isinstance(loc, dict):
        raise ValueError("location must be an object")

    defaults = _default_location_fields()
    out: Dict[str, Any] = dict(defaults)
    out.update(loc)

    loc_id = out.get("id", out.get("loc_id", index + 1))
    try:
        out["id"] = int(loc_id)
    except (TypeError, ValueError):
        out["id"] = index + 1

    if out.get("loc_description") and not out.get("notes"):
        out["notes"] = str(out.pop("loc_description")).strip()
    out.pop("loc_description", None)
    out.pop("loc_direction", None)

    for ev in EVENT_FLAG_COLUMNS:
        out[ev] = _yn(out.get(ev), "n")

    out["onepage"] = _yn(out.get("onepage"), "n")
    for key in ("buffer", "interval"):
        try:
            out[key] = int(float(out[key])) if out[key] not in (None, "") else defaults[key]
        except (TypeError, ValueError):
            out[key] = defaults[key]

    for key in ("proxy_loc_id", "seg_id", "day", "zone", "equipment", "contact", "notes", "loc_label"):
        if out.get(key) is None:
            out[key] = ""
        else:
            out[key] = str(out[key]).strip() if key != "loc_label" else str(out[key])

    if not out.get("loc_type"):
        out["loc_type"] = "course"

    _sync_resources_dict(out, resource_codes)
    return out


def location_to_csv_row(
    loc: Dict[str, Any], resource_codes: Sequence[str]
) -> Dict[str, Any]:
    """Build a dict keyed by locations.csv column names."""
    normalized = normalize_location_record(loc, resource_codes)
    row: Dict[str, Any] = {
        "loc_id": normalized["id"],
        "loc_label": normalized.get("loc_label", ""),
        "loc_type": normalized.get("loc_type", "course"),
        "lat": normalized.get("lat", ""),
        "lon": normalized.get("lon", ""),
        "proxy_loc_id": normalized.get("proxy_loc_id", ""),
        "seg_id": normalized.get("seg_id", ""),
        "day": normalized.get("day", ""),
        "zone": normalized.get("zone", ""),
        "buffer": normalized.get("buffer", 10),
        "interval": normalized.get("interval", 5),
        "onepage": normalized.get("onepage", "n"),
        "equipment": normalized.get("equipment", ""),
        "contact": normalized.get("contact", ""),
        "notes": normalized.get("notes", ""),
    }
    for ev in EVENT_FLAG_COLUMNS:
        row[ev] = normalized.get(ev, "n")
    resources = normalized.get("resources") or {}
    for code in resource_codes:
        row[count_column(code)] = resources.get(code, 0)
    return row
