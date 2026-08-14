"""Package location subjects for clearance authoring (Issue #832)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from app.core.config_package.storage import (
    COURSE_WORKSPACE_NAME,
    resolve_config_package_path,
    validate_config_id,
)


def _norm_loc_id(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or text.lower() in {"nan", "none", "na"}:
        return ""
    if text.isdigit():
        return str(int(text))
    return text


def _norm_zone(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or text.lower() in {"nan", "none", "na"}:
        return ""
    return text


def _add_location(
    seen: Dict[str, Dict[str, str]],
    loc_id: str,
    *,
    label: Any = None,
    zone: Any = None,
    loc_type: Any = None,
) -> None:
    if not loc_id:
        return
    label_text = str(label).strip() if label is not None else ""
    zone_text = _norm_zone(zone)
    type_text = str(loc_type).strip() if loc_type is not None else ""
    if loc_id not in seen:
        seen[loc_id] = {
            "kind": "location",
            "id": loc_id,
            "label": label_text,
            "zone": zone_text,
            "loc_type": type_text,
        }
        return
    row = seen[loc_id]
    if label_text and not row.get("label"):
        row["label"] = label_text
    if zone_text and not row.get("zone"):
        row["zone"] = zone_text
    if type_text and not row.get("loc_type"):
        row["loc_type"] = type_text


def _locations_from_csv(path: Path, seen: Dict[str, Dict[str, str]]) -> None:
    if not path.is_file():
        return
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            loc_id = _norm_loc_id(row.get("loc_id"))
            _add_location(
                seen,
                loc_id,
                label=row.get("loc_label"),
                zone=row.get("zone"),
                loc_type=row.get("loc_type"),
            )


def _locations_from_course(path: Path, seen: Dict[str, Dict[str, str]]) -> None:
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    for loc in payload.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        loc_id = _norm_loc_id(loc.get("loc_id"))
        _add_location(
            seen,
            loc_id,
            label=loc.get("loc_label"),
            zone=loc.get("zone"),
            loc_type=loc.get("loc_type"),
        )


def location_sort_key(loc: Dict[str, str]) -> Tuple[Any, ...]:
    zone = (loc.get("zone") or "").strip()
    loc_id = str(loc.get("id") or "")
    zone_key = (1, "") if not zone else (0, zone.lower() if not zone.isdigit() else f"{int(zone):06d}")
    id_key = (0, int(loc_id)) if loc_id.isdigit() else (1, loc_id)
    return (zone_key, id_key)


def list_package_location_ids(config_id: str) -> Set[str]:
    return {s["id"] for s in list_package_locations(config_id)}


def list_package_locations(config_id: str) -> List[Dict[str, str]]:
    cid = validate_config_id(config_id)
    package = resolve_config_package_path(cid)
    seen: Dict[str, Dict[str, str]] = {}
    _locations_from_csv(package / "locations.csv", seen)
    _locations_from_csv(package / "passes.csv", seen)
    _locations_from_course(package / COURSE_WORKSPACE_NAME, seen)
    return sorted(seen.values(), key=location_sort_key)


def list_package_clearance_subjects(config_id: str) -> Dict[str, Any]:
    """Locations available as clearance subjects (zone-ordered)."""
    cid = validate_config_id(config_id)
    locations = list_package_locations(cid)
    return {
        "config_id": cid,
        "locations": locations,
        "subjects": locations,
    }
