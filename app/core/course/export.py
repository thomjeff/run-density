"""
Course Mapping export: generate segments.csv, flow.csv, locations.csv, and GPX from course.json.

Issue #732: Pipeline-compatible CSV/GPX for the current course.
"""

import csv
import io
import zipfile
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

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


def build_segments_csv(course: Dict[str, Any]) -> str:
    """Build segments.csv content from course.segments and course.events."""
    segments = course.get("segments") or []
    events = course.get("events") or []
    event_ids = [_event_id(e) for e in events]
    if not event_ids:
        event_ids = ["full", "half", "10k", "elite", "open"]
    coords = (course.get("geometry") or {}).get("coordinates") or []
    coords_len = len(coords)

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

    for seg in segments:
        seg_id = seg.get("seg_id", "")
        seg_label = seg.get("seg_label", "")
        start_idx = seg.get("start_index", 0)
        end_idx = seg.get("end_index", coords_len - 1 if coords_len else 0)
        pin_start = _pin_label(course, start_idx, coords_len, "start")
        pin_end = _pin_label(course, end_idx, coords_len, "end")
        width_m = seg.get("width_m", 0)
        schema = seg.get("schema", "on_course_open")
        direction = seg.get("direction", "uni")
        from_km = seg.get("from_km", 0)
        to_km = seg.get("to_km", 0)
        seg_events = seg.get("events") or event_ids
        # y/n per event
        yn = ["y" if eid in seg_events else "n" for eid in event_ids]
        # from_km/to_km only for events in segment; 0 for others
        event_km = []
        for eid in event_ids:
            if eid in seg_events:
                event_km.extend([from_km, to_km])
            else:
                event_km.extend([0, 0])
        lengths = [to_km - from_km if eid in seg_events else 0 for eid in event_ids]
        description = seg.get("description", "")
        row = [seg_id, seg_label, pin_start, pin_end, width_m, schema, direction] + yn + event_km + lengths + [description]
        w.writerow(row)
    return out.getvalue()


def build_flow_csv(course: Dict[str, Any]) -> str:
    """Build minimal flow.csv from course.segments (one row per segment with default flow_type)."""
    segments = course.get("segments") or []
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["seg_id", "seg_label", "event_a", "event_b", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "flow_type", "direction", "notes"])
    for seg in segments:
        seg_id = seg.get("seg_id", "")
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
    w.writerow(["loc_id", "loc_label", "loc_type", "lat", "lon"])
    for i, loc in enumerate(locations):
        loc_id = loc.get("id", i + 1)
        loc_label = loc.get("loc_label", "")
        loc_type = loc.get("loc_type", "course")
        lat = loc.get("lat", "")
        lon = loc.get("lon", "")
        w.writerow([loc_id, loc_label, loc_type, lat, lon])
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


def export_course_zip(course: Dict[str, Any], course_id: str, course_name: str = "") -> bytes:
    """Build a zip with segments.csv, flow.csv, locations.csv, and course.gpx."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("segments.csv", build_segments_csv(course))
        zf.writestr("flow.csv", build_flow_csv(course))
        zf.writestr("locations.csv", build_locations_csv(course))
        zf.writestr("course.gpx", build_gpx(course, course_name))
    return buf.getvalue()
