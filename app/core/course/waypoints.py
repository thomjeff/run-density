"""
Waypoint-based segment definitions for draw-first course workspace (Issue #767).

Waypoints are named places on the course (lat/lon). Segment definitions describe
logical legs (from_waypoint → to_waypoint + events). A resolver projects them onto
geometry.coordinates as start_index / end_index for export and map display.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

COORD_EPS = 1e-9
MAX_SNAP_METERS = 80.0


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _coord_near(
    c: Sequence[float], lat: float, lon: float, eps: float = COORD_EPS
) -> bool:
    if not c or len(c) < 2:
        return False
    return abs(c[0] - lon) < eps and abs(c[1] - lat) < eps


def _nearest_vertex_index(lat: float, lon: float, coords: Sequence[Sequence[float]]) -> int:
    if not coords:
        return 0
    best_i = 0
    best_d = float("inf")
    for i, c in enumerate(coords):
        d = _haversine_m(lon, lat, c[0], c[1])
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _cumulative_km(coords: Sequence[Sequence[float]]) -> List[float]:
    if not coords:
        return [0.0]
    cum = [0.0]
    for i in range(1, len(coords)):
        c0, c1 = coords[i - 1], coords[i]
        cum.append(
            cum[-1] + _haversine_m(c0[0], c0[1], c1[0], c1[1]) / 1000.0
        )
    return cum


def find_vertex_occurrence(
    lat: float,
    lon: float,
    coords: Sequence[Sequence[float]],
    *,
    occurrence: int = 1,
    min_index: int = 0,
) -> int:
    """
    Return vertex index of the occurrence-th match at or after min_index.

    Matches coordinates within COORD_EPS, then falls back to the nearest
    vertex at or after min_index.
    """
    if not coords:
        return 0
    occ = max(1, int(occurrence))
    start = max(0, min_index)

    exact: List[int] = []
    for i in range(start, len(coords)):
        if _coord_near(coords[i], lat, lon):
            exact.append(i)
    if len(exact) >= occ:
        return exact[occ - 1]

    best_i = start
    best_d = float("inf")
    for i in range(start, len(coords)):
        c = coords[i]
        d = _haversine_m(lon, lat, c[0], c[1])
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _resolve_waypoint_index(
    wp: Dict[str, Any],
    coords: Sequence[Sequence[float]],
    *,
    min_index: int,
    role: str,
) -> int:
    """Project waypoint onto course polyline forward from min_index."""
    if not coords:
        return 0
    last = len(coords) - 1
    kind = (wp.get("kind") or "").strip().lower()
    if role == "from" and kind == "start":
        return 0
    if role == "to" and kind == "finish":
        return last

    lat, lon = _waypoint_lat_lon(wp)
    occ = _waypoint_occurrence(wp)
    return find_vertex_occurrence(lat, lon, coords, occurrence=occ, min_index=min_index)


def _waypoint_lat_lon(wp: Dict[str, Any]) -> Tuple[float, float]:
    lat = float(wp.get("lat", 0))
    lon = float(wp.get("lon", 0))
    return lat, lon


def _waypoint_occurrence(wp: Dict[str, Any]) -> int:
    raw = wp.get("path_occurrence", 1)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def migrate_breaks_to_waypoints(course: Dict[str, Any]) -> Dict[str, Any]:
    """
    Populate waypoints and segment_defs from legacy segment_breaks + segments.

    No-op if waypoints already present.
    """
    if course.get("waypoints"):
        return course

    geometry = course.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        course["waypoints"] = []
        course["segment_defs"] = []
        return course

    labels = course.get("segment_break_labels") or {}
    breaks = sorted(
        int(b)
        for b in (course.get("segment_breaks") or [])
        if isinstance(b, (int, float)) and 0 < int(b) < len(coords)
    )

    waypoints: List[Dict[str, Any]] = []
    c0 = coords[0]
    waypoints.append(
        {
            "id": "wp-start",
            "label": "Start",
            "lat": c0[1],
            "lon": c0[0],
            "kind": "start",
            "path_occurrence": 1,
        }
    )
    for bi in breaks:
        c = coords[bi]
        lbl = (labels.get(bi) or labels.get(str(bi)) or "").strip() or f"Pin {bi}"
        waypoints.append(
            {
                "id": f"wp-pin-{bi}",
                "label": lbl,
                "lat": c[1],
                "lon": c[0],
                "kind": "pin",
                "path_occurrence": 1,
                "vertex_index": bi,
            }
        )
    c_last = coords[-1]
    waypoints.append(
        {
            "id": "wp-finish",
            "label": "Finish",
            "lat": c_last[1],
            "lon": c_last[0],
            "kind": "finish",
            "path_occurrence": 1,
        }
    )

    wp_by_vertex: Dict[int, str] = {}
    for wp in waypoints:
        vi = wp.get("vertex_index")
        if vi is not None:
            wp_by_vertex[int(vi)] = wp["id"]
    wp_by_vertex[0] = "wp-start"
    wp_by_vertex[len(coords) - 1] = "wp-finish"

    segment_defs: List[Dict[str, Any]] = []
    existing = course.get("segments") or []
    if existing:
        for i, seg in enumerate(existing):
            if not isinstance(seg, dict):
                continue
            start_idx = int(seg.get("start_index", 0))
            end_idx = int(seg.get("end_index", len(coords) - 1))
            from_id = wp_by_vertex.get(start_idx)
            to_id = wp_by_vertex.get(end_idx)
            if not from_id:
                from_id = "wp-start"
            if not to_id:
                to_id = "wp-finish"
            segment_defs.append(
                {
                    "id": f"sd-{seg.get('seg_id', i + 1)}",
                    "from_waypoint_id": from_id,
                    "to_waypoint_id": to_id,
                    "events": list(seg.get("events") or []),
                    "seg_label": (seg.get("seg_label") or "").strip()
                    or f"Segment {i + 1}",
                    "width_m": seg.get("width_m", 3),
                    "schema": seg.get("schema", "on_course_open"),
                    "direction": seg.get("direction", "uni"),
                    "description": (seg.get("description") or "").strip(),
                }
            )
    else:
        boundaries = [0] + breaks + [len(coords) - 1]
        for i in range(len(boundaries) - 1):
            start_idx, end_idx = boundaries[i], boundaries[i + 1]
            if end_idx <= start_idx:
                continue
            from_id = wp_by_vertex.get(start_idx, "wp-start")
            to_id = wp_by_vertex.get(end_idx, "wp-finish")
            segment_defs.append(
                {
                    "id": f"sd-{i + 1}",
                    "from_waypoint_id": from_id,
                    "to_waypoint_id": to_id,
                    "events": [],
                    "seg_label": f"Segment {i + 1}",
                    "width_m": 3,
                    "schema": "on_course_open",
                    "direction": "uni",
                    "description": "",
                }
            )

    course["waypoints"] = waypoints
    course["segment_defs"] = segment_defs
    return course


def resolve_segments_from_definitions(
    course: Dict[str, Any],
    event_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Build course['segments'] from segment_defs + waypoints + geometry.

    Updates segment_breaks cache from resolved end indices (excluding finish).
    """
    geometry = course.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        course["segments"] = []
        return course

    segment_defs = course.get("segment_defs") or []
    if not segment_defs:
        return course

    waypoints = course.get("waypoints") or []
    wp_by_id: Dict[str, Dict[str, Any]] = {}
    for wp in waypoints:
        if isinstance(wp, dict) and wp.get("id"):
            wp_by_id[str(wp["id"])] = wp

    if not wp_by_id:
        raise ValueError("segment_defs require waypoints")

    cum = _cumulative_km(coords)
    existing = course.get("segments") or []
    default_events = list(event_ids or [])
    if not default_events and existing:
        default_events = list(existing[0].get("events") or [])

    resolved: List[Dict[str, Any]] = []
    search_from = -1

    for ordinal, sd in enumerate(segment_defs):
        if not isinstance(sd, dict):
            continue
        from_id = str(sd.get("from_waypoint_id", "")).strip()
        to_id = str(sd.get("to_waypoint_id", "")).strip()
        from_wp = wp_by_id.get(from_id)
        to_wp = wp_by_id.get(to_id)
        if not from_wp or not to_wp:
            raise ValueError(
                f"segment_defs[{ordinal}]: unknown waypoint "
                f"from={from_id!r} to={to_id!r}"
            )

        from_min = 0 if ordinal == 0 else max(0, search_from)
        start_idx = _resolve_waypoint_index(
            from_wp, coords, min_index=from_min, role="from"
        )
        if ordinal > 0 and start_idx < search_from:
            raise ValueError(
                f"segment_defs[{ordinal}]: from waypoint {from_id!r} is before "
                f"the previous segment end along the course"
            )
        to_min = min(start_idx + 1, len(coords) - 1)
        end_idx = _resolve_waypoint_index(
            to_wp, coords, min_index=to_min, role="to"
        )
        if end_idx <= start_idx:
            raise ValueError(
                f"segment_defs[{ordinal}]: to waypoint {to_id!r} is before "
                f"from waypoint {from_id!r} along the course"
            )

        prev = existing[ordinal] if ordinal < len(existing) else {}
        if not isinstance(prev, dict):
            prev = {}

        from_km = cum[start_idx]
        to_km = cum[end_idx]
        events = sd.get("events")
        if not events:
            events = prev.get("events") or default_events

        resolved.append(
            {
                "seg_id": str(sd.get("id", ordinal + 1)).replace("sd-", "") or str(ordinal + 1),
                "seg_label": (sd.get("seg_label") or prev.get("seg_label") or "").strip()
                or f"Segment {ordinal + 1}",
                "width_m": sd.get("width_m", prev.get("width_m", 3)),
                "direction": sd.get("direction", prev.get("direction", "uni")),
                "schema": sd.get("schema", prev.get("schema", "on_course_open")),
                "description": (sd.get("description") or prev.get("description") or "").strip(),
                "events": list(events),
                "from_km": round(from_km, 2),
                "to_km": round(to_km, 2),
                "start_index": start_idx,
                "end_index": end_idx,
                "info_icon_lat": prev.get("info_icon_lat"),
                "info_icon_lon": prev.get("info_icon_lon"),
            }
        )
        search_from = end_idx

    _apply_flow_control(course, resolved, coords)
    course["segments"] = resolved
    _sync_segment_breaks_cache(course, resolved, coords)
    return course


def _apply_flow_control(
    course: Dict[str, Any],
    segments: List[Dict[str, Any]],
    coords: Sequence[Sequence[float]],
) -> None:
    """Apply flow_control_points event overrides to resolved segments."""
    fcp = course.get("flow_control_points") or []
    for fc in fcp:
        if not isinstance(fc, dict):
            continue
        v = fc.get("vertex_index")
        branches = fc.get("branches") or []
        for br in branches:
            if not isinstance(br, dict):
                continue
            end_v = br.get("end_vertex_index")
            evts = br.get("events") or []
            for seg in segments:
                if seg.get("start_index") == v and seg.get("end_index") == end_v:
                    seg["events"] = list(evts)
                    break


def _sync_segment_breaks_cache(
    course: Dict[str, Any],
    segments: List[Dict[str, Any]],
    coords: Sequence[Sequence[float]],
) -> None:
    """Keep segment_breaks aligned with segment end indices (excluding finish)."""
    last = len(coords) - 1
    breaks = sorted(
        {
            int(seg["end_index"])
            for seg in segments
            if isinstance(seg, dict)
            and seg.get("end_index") is not None
            and 0 < int(seg["end_index"]) < last
        }
    )
    course["segment_breaks"] = breaks

    labels = dict(course.get("segment_break_labels") or {})
    ids = dict(course.get("segment_break_ids") or {})
    wp_by_id = {
        str(wp["id"]): wp
        for wp in (course.get("waypoints") or [])
        if isinstance(wp, dict) and wp.get("id")
    }
    for seg in segments:
        end_idx = seg.get("end_index")
        if end_idx is None or end_idx <= 0 or end_idx >= last:
            continue
        for sd in course.get("segment_defs") or []:
            if not isinstance(sd, dict):
                continue
            to_wp = wp_by_id.get(str(sd.get("to_waypoint_id", "")))
            if to_wp and find_vertex_occurrence(
                to_wp["lat"],
                to_wp["lon"],
                coords,
                occurrence=int(
                    sd.get("to_path_occurrence") or _waypoint_occurrence(to_wp)
                ),
                min_index=0,
            ) == int(end_idx):
                lbl = (sd.get("seg_label") or to_wp.get("label") or "").strip()
                if lbl:
                    labels[end_idx] = lbl
                    labels[str(end_idx)] = lbl
                break
    course["segment_break_labels"] = labels
    course["segment_break_ids"] = ids


def normalize_course_waypoints(course: Dict[str, Any]) -> Dict[str, Any]:
    """
    Migrate legacy breaks if needed, then resolve segments from definitions.
    """
    data = deepcopy(course)
    geometry = data.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return data

    migrate_breaks_to_waypoints(data)
    if data.get("segment_defs"):
        resolve_segments_from_definitions(data)
    return data
