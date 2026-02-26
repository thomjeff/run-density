"""
Course Mapping export: generate segments.csv, flow.csv, locations.csv, course.gpx, and course.json.

Issue #732: Pipeline-compatible CSV/GPX for the current course.
"""

import csv
import io
import json
import zipfile
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

from app.utils.constants import COURSE_EVENT_IDS

# GPX 1.1 namespace
GPX_NS = "http://www.topografix.com/GPX/1/1"


def _event_id(e: Any) -> str:
    if isinstance(e, dict):
        return str(e.get("id", e.get("name", "")))
    return str(e)


def _pin_label(course: Dict[str, Any], index: int, coords_len: int, role: str) -> str:
    """Label for segment boundary: 'Start' at index 0, 'Finish' at last index, else segment_break_labels."""
    if role == "start" and index <= 0:
        return "Start"
    if role == "end" and coords_len and index >= coords_len - 1:
        return "Finish"
    labels = course.get("segment_break_labels") or {}
    if not isinstance(labels, dict):
        return ""
    return (labels.get(index) or labels.get(str(index)) or "").strip()


def _segment_display_id(segment_index: int) -> str:
    """Return segment ID as sequential number (1, 2, 3, ...) for pipeline compatibility."""
    return str(segment_index + 1)


def _segment_events_set(seg: Dict[str, Any], event_ids: List[str]) -> set:
    """Normalize segment 'events' to a set of lowercase strings for reliable membership checks."""
    raw = seg.get("events")
    if raw is None:
        return set(event_ids)
    if isinstance(raw, (list, tuple)):
        return set(str(x).strip().lower() for x in raw if x)
    if isinstance(raw, str):
        return set(raw.strip().lower().split()) if raw.strip() else set(event_ids)
    return set(event_ids)


def _format_km(value: float) -> str:
    """Format a distance value to exactly 2 decimal places for CSV output."""
    return format(round(float(value), 2), ".2f")


def _event_cumulative_distances(segments: List[Dict], event_ids: List[str]) -> List[Dict[str, tuple]]:
    """
    For each event, compute per-segment from_km/to_km as cumulative distance along
    only the segments that include that event (so half skips segments 2/3, etc.).
    Returns list of dicts: result[i][eid] = (from_km, to_km) for segment i and event eid.
    Accumulated values are rounded to 2 decimal places to avoid float drift.
    """
    n = len(segments)
    result = [{} for _ in range(n)]
    event_ids_lower = [e.lower() for e in event_ids]
    for ei, eid in enumerate(event_ids_lower):
        accumulated = 0.0
        for i, seg in enumerate(segments):
            seg_events = _segment_events_set(seg, event_ids_lower)
            if eid not in seg_events:
                result[i][eid] = (0.0, 0.0)
                continue
            from_km = float(seg.get("from_km") or 0)
            to_km = float(seg.get("to_km") or 0)
            seg_len = round(to_km - from_km, 2)
            from_accum = round(accumulated, 2)
            to_accum = round(accumulated + seg_len, 2)
            result[i][eid] = (from_accum, to_accum)
            accumulated = to_accum
    return result


def build_segments_csv(course: Dict[str, Any]) -> str:
    """Build segments.csv content from course.segments and course.events.
    Uses sequential segment IDs (1, 2, 3, ...) for pipeline compatibility.
    Event-specific from_km/to_km are cumulative along only segments that use that event.
    """
    segments = course.get("segments") or []
    # Event list from constants (SSOT); course.json does not store events
    event_ids = COURSE_EVENT_IDS
    coords = (course.get("geometry") or {}).get("coordinates") or []
    coords_len = len(coords)

    # Per-segment, per-event (from_km, to_km) using event-cumulative distance
    event_distances = _event_cumulative_distances(segments, event_ids)

    out = io.StringIO()
    # Header: seg_id, seg_label, pin_start_label, pin_end_label, width_m, schema, direction, then y/n, then per-event from_km/to_km/length
    event_cols = []
    for eid in event_ids:
        event_cols.extend([f"{eid}_from_km", f"{eid}_to_km"])
    length_cols = [f"{eid}_length" for eid in event_ids]
    header = (
        ["seg_id", "seg_label", "pin_start_label", "pin_end_label", "width_m", "schema", "direction"]
        + event_ids
        + event_cols
        + length_cols
        + ["description"]
    )
    w = csv.writer(out)
    w.writerow(header)

    for i, seg in enumerate(segments):
        seg_id = _segment_display_id(i)
        seg_label = seg.get("seg_label", "")
        start_idx = seg.get("start_index", 0)
        end_idx = seg.get("end_index", coords_len - 1 if coords_len else 0)
        pin_start = _pin_label(course, start_idx, coords_len, "start")
        pin_end = _pin_label(course, end_idx, coords_len, "end")
        width_m = seg.get("width_m", 0)
        schema = seg.get("schema", "on_course_open")
        direction = seg.get("direction", "uni")
        from_km = float(seg.get("from_km") or 0)
        to_km = float(seg.get("to_km") or 0)
        seg_events = _segment_events_set(seg, event_ids)
        # y/n per event (use lowercase for lookup)
        yn = ["y" if eid.lower() in seg_events else "n" for eid in event_ids]
        # Event-specific from_km/to_km and lengths: all formatted to exactly 2 decimal places
        event_km = []
        for eid in event_ids:
            ev_from, ev_to = event_distances[i].get(eid.lower(), (0.0, 0.0))
            event_km.extend([_format_km(ev_from), _format_km(ev_to)])
        seg_len = round(to_km - from_km, 2)
        lengths = [_format_km(seg_len) if eid.lower() in seg_events else "0.00" for eid in event_ids]
        description = seg.get("description", "")
        row = [seg_id, seg_label, pin_start, pin_end, width_m, schema, direction] + yn + event_km + lengths + [description]
        w.writerow(row)
    return out.getvalue()


def build_flow_csv(course: Dict[str, Any]) -> str:
    """Build minimal flow.csv from course.segments (one row per segment with default flow_type).
    Uses sequential segment IDs (1, 2, 3, ...) for pipeline compatibility.
    """
    segments = course.get("segments") or []
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["seg_id", "seg_label", "event_a", "event_b", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "flow_type", "direction", "notes"])
    for i, seg in enumerate(segments):
        seg_id = _segment_display_id(i)
        seg_label = seg.get("seg_label", "")
        from_km = seg.get("from_km", 0)
        to_km = seg.get("to_km", 0)
        events = seg.get("events") or ["full"]
        event_a = events[0] if events else "full"
        event_b = event_a
        w.writerow([seg_id, seg_label, event_a, event_b, from_km, to_km, from_km, to_km, "overtake", seg.get("direction", "uni"), ""])
    return out.getvalue()


def build_locations_csv(course: Dict[str, Any]) -> str:
    """Build locations.csv from course.locations (minimal columns)."""
    locations = course.get("locations") or []
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["loc_id", "loc_label", "loc_type", "loc_description", "lat", "lon"])
    for i, loc in enumerate(locations):
        loc_id = loc.get("id", i + 1)
        loc_label = loc.get("loc_label", "")
        loc_type = loc.get("loc_type", "course")
        loc_description = loc.get("loc_description", "")
        lat = loc.get("lat", "")
        lon = loc.get("lon", "")
        w.writerow([loc_id, loc_label, loc_type, loc_description, lat, lon])
    return out.getvalue()


def _gpx_tag(name: str) -> str:
    return f"{{{GPX_NS}}}{name}"


def build_gpx(course: Dict[str, Any], course_name: str = "") -> str:
    """Build GPX 1.1 with one track from course.geometry (LineString)."""
    root = ET.Element(_gpx_tag("gpx"), version="1.1", creator="Run-Density Course Mapping")
    root.set("xmlns", GPX_NS)

    geometry = course.get("geometry")
    if not geometry or geometry.get("type") != "LineString":
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    trk = ET.SubElement(root, _gpx_tag("trk"))
    name_el = ET.SubElement(trk, _gpx_tag("name"))
    name_el.text = course_name or course.get("name") or course.get("id", "course")
    trkseg = ET.SubElement(trk, _gpx_tag("trkseg"))
    for lon, lat in coords:
        ET.SubElement(trkseg, _gpx_tag("trkpt"), lat=str(lat), lon=str(lon))
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def build_course_json(course: Dict[str, Any]) -> str:
    """Serialize course dict to JSON string for export."""
    return json.dumps(course, indent=2, ensure_ascii=False)


def export_course_zip(course: Dict[str, Any], course_id: str, course_name: str = "") -> bytes:
    """Build a zip with segments.csv, flow.csv, locations.csv, course.gpx, and course.json."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("segments.csv", build_segments_csv(course))
        zf.writestr("flow.csv", build_flow_csv(course))
        zf.writestr("locations.csv", build_locations_csv(course))
        zf.writestr("course.gpx", build_gpx(course, course_name))
        zf.writestr("course.json", build_course_json(course))
    return buf.getvalue()
