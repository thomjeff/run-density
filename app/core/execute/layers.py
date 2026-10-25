"""Operations map layers from the imported Day Plan (Issue #928)."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

TURNAROUND_RE = re.compile(r"turn[\s-]?around", re.I)
TURN_WORD_RE = re.compile(r"\bturn\b", re.I)


def is_turnaround(row: Mapping[str, Any]) -> bool:
    loc_type = str(row.get("loc_type") or "").strip().lower()
    if loc_type in {"turnaround", "turn-around", "turn_around"}:
        return True
    if loc_type == "water":
        return False
    label = str(row.get("loc_label") or "")
    if TURNAROUND_RE.search(label):
        return True
    if not TURN_WORD_RE.search(label):
        return False
    return loc_type in {"official", "course", ""}


def is_water_or_service(row: Mapping[str, Any]) -> bool:
    loc_type = str(row.get("loc_type") or "").strip().lower()
    return loc_type in {"water", "aid", "official"}


def _coord(row: Mapping[str, Any]) -> Optional[Dict[str, float]]:
    try:
        lat = float(row.get("lat"))
        lon = float(row.get("lon"))
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return {"lat": lat, "lon": lon}


def turnaround_pins(
    locations: Iterable[Mapping[str, Any]],
    courses: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Turn-around points from Plan Locations, plus course indices."""
    pins: List[Dict[str, Any]] = []
    seen = set()
    for row in locations:
        if not isinstance(row, Mapping) or not is_turnaround(row):
            continue
        coord = _coord(row)
        if coord is None:
            continue
        loc_id = row.get("loc_id")
        key = ("loc", str(loc_id))
        if key in seen:
            continue
        seen.add(key)
        pins.append(
            {
                "source": "location",
                "loc_id": loc_id,
                "label": row.get("loc_label") or "Turn-around",
                "lat": coord["lat"],
                "lon": coord["lon"],
            }
        )
    for race_id, geo in (courses or {}).items():
        if not isinstance(geo, Mapping):
            continue
        pins.extend(
            _course_turnarounds(str(race_id), geo, seen)
        )
    return pins


def _course_turnarounds(
    race_id: str,
    geo: Mapping[str, Any],
    seen: set,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    features = geo.get("features")
    items = features if isinstance(features, list) else [geo]
    for index, feature in enumerate(items):
        if not isinstance(feature, Mapping):
            continue
        props = feature.get("properties") or {}
        if not isinstance(props, Mapping):
            props = {}
        indices = props.get("turnaround_indices")
        if not isinstance(indices, list):
            indices = geo.get("turnaround_indices")
        if not isinstance(indices, list):
            continue
        coords = _line_coords(feature.get("geometry") or geo.get("geometry"))
        if not coords:
            continue
        for raw in indices:
            try:
                point_i = int(raw)
            except (TypeError, ValueError):
                continue
            if point_i < 0 or point_i >= len(coords):
                continue
            lon, lat = coords[point_i][0], coords[point_i][1]
            key = ("course", race_id, point_i)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "source": "course",
                    "race_id": race_id,
                    "index": point_i,
                    "label": f"{race_id} turn-around",
                    "lat": lat,
                    "lon": lon,
                    "feature_index": index,
                }
            )
    return out


def _line_coords(geometry: Any) -> List[List[float]]:
    if not isinstance(geometry, Mapping):
        return []
    coords = geometry.get("coordinates")
    gtype = str(geometry.get("type") or "")
    if gtype == "LineString" and isinstance(coords, list):
        return [c for c in coords if isinstance(c, list) and len(c) >= 2]
    if gtype == "MultiLineString" and isinstance(coords, list):
        flat: List[List[float]] = []
        for part in coords:
            if not isinstance(part, list):
                continue
            flat.extend(
                c for c in part if isinstance(c, list) and len(c) >= 2
            )
        return flat
    return []
