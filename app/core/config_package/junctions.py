"""
Junction Flow authoring (Issue #817).

Package-root ``junctions.json`` — independent of Locations / Segments schemas.
Nearby discovery: segment leg start/end within JUNCTION_SEGMENT_PROXIMITY_M.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config_package.leg_library_resolver import resolve_leg_library
from app.core.config_package.storage import (
    load_config_course,
    resolve_config_package_path,
    validate_config_id,
)
from app.core.course.segment_library import manifest_legs, parse_leg_gpx
from app.core.gpx.processor import haversine_m
from app.utils.constants import JUNCTION_SEGMENT_PROXIMITY_M
from app.utils.run_id import generate_run_id

logger = logging.getLogger(__name__)

JUNCTIONS_NAME = "junctions.json"
JUNCTIONS_DOC_VERSION = 1

_INTERACTION_TYPES = frozenset({"cross", "merge"})
_SIDES = frozenset({"left", "right", ""})


def junctions_path(config_id: str) -> Path:
    return resolve_config_package_path(config_id) / JUNCTIONS_NAME


def empty_junctions_doc() -> Dict[str, Any]:
    return {"version": JUNCTIONS_DOC_VERSION, "junctions": [], "updated": None}


def load_config_junctions(config_id: str) -> Dict[str, Any]:
    """Load junctions.json or return an empty document if missing."""
    cid = validate_config_id(config_id)
    path = junctions_path(cid)
    if not path.is_file():
        return empty_junctions_doc()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {JUNCTIONS_NAME} in package {cid}")
    return validate_junctions_doc(data)


def save_config_junctions(config_id: str, data: Dict[str, Any]) -> Path:
    """Validate and write junctions.json for a config package."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    doc = validate_junctions_doc(data)
    doc["updated"] = datetime.now(timezone.utc).isoformat()
    path = package_path / JUNCTIONS_NAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def _as_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} must be a number") from e


def _normalize_events(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
        return parts
    if not isinstance(raw, list):
        raise ValueError("events must be a list of event ids")
    out: List[str] = []
    for item in raw:
        eid = str(item or "").strip().lower()
        if eid and eid not in out:
            out.append(eid)
    return out


def _normalize_interaction(raw: Any, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"interactions[{index}] must be an object")
    itype = str(raw.get("type") or "").strip().lower()
    if itype not in _INTERACTION_TYPES:
        raise ValueError(
            f"interactions[{index}].type must be one of "
            f"{sorted(_INTERACTION_TYPES)}"
        )
    side = str(raw.get("side") or "").strip().lower()
    if side not in _SIDES:
        raise ValueError(
            f"interactions[{index}].side must be left, right, or empty"
        )
    from_seg = str(raw.get("from_seg_id") or "").strip()
    if not from_seg:
        raise ValueError(f"interactions[{index}].from_seg_id is required")

    to_raw = raw.get("to_seg_ids")
    if to_raw is None and raw.get("to_seg_id"):
        to_raw = [raw.get("to_seg_id")]
    if not isinstance(to_raw, list) or not to_raw:
        raise ValueError(
            f"interactions[{index}].to_seg_ids must be a non-empty list"
        )
    to_segs: List[str] = []
    for t in to_raw:
        sid = str(t or "").strip()
        if sid and sid not in to_segs:
            to_segs.append(sid)
    if not to_segs:
        raise ValueError(
            f"interactions[{index}].to_seg_ids must include a segment id"
        )
    if itype == "cross" and len(to_segs) != 1:
        raise ValueError(
            f"interactions[{index}]: cross allows exactly one to_seg_id"
        )

    conflicts = str(raw.get("conflicts_with_seg_id") or "").strip()
    if itype == "cross" and not conflicts:
        raise ValueError(
            f"interactions[{index}]: cross requires conflicts_with_seg_id"
        )
    if itype == "merge":
        conflicts = ""

    iid = str(raw.get("id") or "").strip() or f"ix_{index + 1}"
    return {
        "id": iid,
        "type": itype,
        "side": side,
        "from_seg_id": from_seg,
        "to_seg_ids": to_segs,
        "conflicts_with_seg_id": conflicts,
        "events": _normalize_events(raw.get("events")),
    }


def _derive_streams(junction: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build stream list from nearby segments + interaction segment refs."""
    ordered: List[str] = []
    for sid in junction.get("nearby_seg_ids") or []:
        s = str(sid or "").strip()
        if s and s not in ordered:
            ordered.append(s)
    for ix in junction.get("interactions") or []:
        if not isinstance(ix, dict):
            continue
        for key in ("from_seg_id", "conflicts_with_seg_id"):
            s = str(ix.get(key) or "").strip()
            if s and s not in ordered:
                ordered.append(s)
        for s in ix.get("to_seg_ids") or []:
            sid = str(s or "").strip()
            if sid and sid not in ordered:
                ordered.append(sid)
    endpoint_by_seg = {
        str(r.get("seg_id")): str(r.get("near_endpoint") or "")
        for r in (junction.get("nearby_segments") or [])
        if isinstance(r, dict) and r.get("seg_id")
    }
    streams: List[Dict[str, Any]] = []
    for sid in ordered:
        near = endpoint_by_seg.get(sid) or ""
        # At pin: start nearby → leave via end; end nearby → arrive from start
        if near == "start":
            direction = "from_start"
        elif near == "end":
            direction = "to_end"
        elif near == "both":
            direction = "both_ends"
        else:
            direction = "unspecified"
        streams.append(
            {
                "stream_id": sid,
                "seg_id": sid,
                "direction": direction,
                "near_endpoint": near or None,
            }
        )
    return streams


def _normalize_junction(raw: Any, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"junctions[{index}] must be an object")
    jid = str(raw.get("id") or "").strip() or generate_run_id()
    label = str(raw.get("label") or "").strip() or f"Junction {index + 1}"
    lat = _as_float(raw.get("lat"), f"junctions[{index}].lat")
    lon = _as_float(raw.get("lon"), f"junctions[{index}].lon")
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise ValueError(f"junctions[{index}] lat/lon out of range")

    nearby_ids: List[str] = []
    for sid in raw.get("nearby_seg_ids") or []:
        s = str(sid or "").strip()
        if s and s not in nearby_ids:
            nearby_ids.append(s)

    interactions = [
        _normalize_interaction(ix, i)
        for i, ix in enumerate(raw.get("interactions") or [])
    ]

    junction: Dict[str, Any] = {
        "id": jid,
        "label": label,
        "lat": lat,
        "lon": lon,
        "nearby_seg_ids": nearby_ids,
        "interactions": interactions,
    }
    # Optional cache of last discovery rows (UI convenience; not required)
    nearby_segments = raw.get("nearby_segments")
    if isinstance(nearby_segments, list):
        junction["nearby_segments"] = nearby_segments
    junction["streams"] = _derive_streams(junction)
    return junction


def validate_junctions_doc(data: Dict[str, Any]) -> Dict[str, Any]:
    version = int(data.get("version") or JUNCTIONS_DOC_VERSION)
    junctions_raw = data.get("junctions") or []
    if not isinstance(junctions_raw, list):
        raise ValueError("junctions must be a list")
    junctions = [
        _normalize_junction(j, i) for i, j in enumerate(junctions_raw)
    ]
    seen: Set[str] = set()
    for j in junctions:
        if j["id"] in seen:
            raise ValueError(f"Duplicate junction id: {j['id']}")
        seen.add(j["id"])
    return {
        "version": version,
        "junctions": junctions,
        "updated": data.get("updated"),
    }


def new_junction_id() -> str:
    return generate_run_id()


def _leg_gpx_path(
    lib_dir: Path, leg_manifest: Dict[str, Any], leg_id: str
) -> Optional[Path]:
    lid = str(leg_id or "").strip()
    if not lid:
        return None
    for entry in manifest_legs(leg_manifest):
        if str(entry.get("id") or "").strip() != lid:
            continue
        file_name = entry.get("file") or f"{lid}.gpx"
        path = lib_dir / str(file_name)
        if path.is_file():
            return path
        # Org legs sometimes use slug filenames; try id.gpx
        alt = lib_dir / f"{lid}.gpx"
        if alt.is_file():
            return alt
        return path if path.is_file() else None
    # Fallback: id.gpx without manifest row
    alt = lib_dir / f"{lid}.gpx"
    return alt if alt.is_file() else None


_leg_endpoint_cache: Dict[
    Tuple[str, str], Optional[Tuple[Tuple[float, float], Tuple[float, float]]]
] = {}


def clear_leg_endpoint_cache() -> None:
    _leg_endpoint_cache.clear()


def _leg_endpoints(
    config_id: str, leg_id: str
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Return ((start_lon, start_lat), (end_lon, end_lat)) for a leg GPX."""
    key = (config_id, str(leg_id))
    if key in _leg_endpoint_cache:
        return _leg_endpoint_cache[key]
    try:
        lib_dir, leg_manifest, _source, _pkg = resolve_leg_library(config_id)
    except Exception:
        _leg_endpoint_cache[key] = None
        return None
    path = _leg_gpx_path(lib_dir, leg_manifest, leg_id)
    if path is None or not path.is_file():
        _leg_endpoint_cache[key] = None
        return None
    try:
        parsed = parse_leg_gpx(path)
    except Exception as e:
        logger.warning("Failed to parse leg GPX %s: %s", path, e)
        _leg_endpoint_cache[key] = None
        return None
    coords = parsed.get("coordinates") or []
    if len(coords) < 2:
        _leg_endpoint_cache[key] = None
        return None
    start = (float(coords[0][0]), float(coords[0][1]))
    end = (float(coords[-1][0]), float(coords[-1][1]))
    _leg_endpoint_cache[key] = (start, end)
    return start, end


def _segment_event_kms(seg: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Per-event from/to km for hover tiles."""
    events = seg.get("events") or []
    if isinstance(events, str):
        events = [e.strip() for e in events.split(",") if e.strip()]
    out: Dict[str, Dict[str, float]] = {}
    for eid in events:
        el = str(eid).strip().lower()
        if not el:
            continue
        fk = seg.get(f"{el}_from_km")
        tk = seg.get(f"{el}_to_km")
        if fk is None and tk is None:
            continue
        try:
            out[el] = {
                "from_km": float(fk) if fk is not None else None,
                "to_km": float(tk) if tk is not None else None,
            }
        except (TypeError, ValueError):
            continue
    return out


def find_nearby_segments(
    config_id: str,
    lat: float,
    lon: float,
    *,
    radius_m: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Return course segments whose leg start/end is within radius_m of the pin.

    Each row includes distance_m, near_endpoint (start|end|both), events, and
    per-event km for UI hover tiles.
    """
    cid = validate_config_id(config_id)
    # Keep endpoint cache across nearby lookups; tests clear via
    # clear_leg_endpoint_cache().
    radius = float(
        radius_m if radius_m is not None else JUNCTION_SEGMENT_PROXIMITY_M
    )
    if radius <= 0:
        raise ValueError("radius_m must be positive")

    course = load_config_course(cid)
    segments = course.get("segments") or []
    results: List[Dict[str, Any]] = []

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_id = str(seg.get("seg_id") or "").strip()
        if not seg_id:
            continue
        leg_id = str(seg.get("leg_id") or "").strip()
        endpoints = _leg_endpoints(cid, leg_id) if leg_id else None
        if not endpoints:
            continue
        (start_lon, start_lat), (end_lon, end_lat) = endpoints
        d_start = haversine_m(lat, lon, start_lat, start_lon)
        d_end = haversine_m(lat, lon, end_lat, end_lon)
        near_start = d_start <= radius
        near_end = d_end <= radius
        if not near_start and not near_end:
            continue
        if near_start and near_end:
            near_endpoint = "both"
            distance_m = min(d_start, d_end)
        elif near_start:
            near_endpoint = "start"
            distance_m = d_start
        else:
            near_endpoint = "end"
            distance_m = d_end

        events = seg.get("events") or []
        if isinstance(events, str):
            events = [e.strip() for e in events.split(",") if e.strip()]
        else:
            events = [str(e).strip() for e in events if str(e).strip()]

        results.append(
            {
                "seg_id": seg_id,
                "seg_label": (
                    seg.get("seg_label") or seg.get("description") or seg_id
                ),
                "leg_id": leg_id,
                "length_km": seg.get("length_km"),
                "width_m": seg.get("width_m"),
                "direction": seg.get("direction"),
                "events": events,
                "event_kms": _segment_event_kms(seg),
                "near_endpoint": near_endpoint,
                "distance_m": round(distance_m, 2),
                "start_lat": start_lat,
                "start_lon": start_lon,
                "end_lat": end_lat,
                "end_lon": end_lon,
            }
        )

    results.sort(key=lambda r: (r["distance_m"], r["seg_id"]))
    return results


def course_segment_line_features(config_id: str) -> List[Dict[str, Any]]:
    """GeoJSON features for each course segment leg (map rendering)."""
    cid = validate_config_id(config_id)
    course = load_config_course(cid)
    try:
        lib_dir, leg_manifest, _source, _pkg = resolve_leg_library(cid)
    except Exception:
        return []

    features: List[Dict[str, Any]] = []
    seen_legs: Set[str] = set()
    for seg in course.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        seg_id = str(seg.get("seg_id") or "").strip()
        leg_id = str(seg.get("leg_id") or "").strip()
        if not seg_id or not leg_id:
            continue
        path = _leg_gpx_path(lib_dir, leg_manifest, leg_id)
        if path is None or not path.is_file():
            continue
        try:
            parsed = parse_leg_gpx(path)
        except Exception:
            continue
        coords = parsed.get("coordinates") or []
        if len(coords) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "seg_id": seg_id,
                    "seg_label": seg.get("seg_label") or seg_id,
                    "leg_id": leg_id,
                    "events": seg.get("events") or [],
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
        seen_legs.add(leg_id)
    return features
