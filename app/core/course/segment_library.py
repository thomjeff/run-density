"""
Segment library + event recipes (PlotARoute / 2027 planning).

A segment library is a set of reusable GPX legs. Event recipes list leg ids in order.
From that we build:
  - per-event combined GPX
  - multi-event segments.csv (one row per leg, 2026-style)
  - flow.csv rows for event pairs on shared legs (#759 baseline)
"""

from __future__ import annotations

import csv
import io
import math
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from app.core.course.export import build_segments_csv, enrich_segments_event_distances
from app.core.gpx.processor import parse_gpx_file
from app.utils.constants import COURSE_EVENT_IDS

GPX_NS = "http://www.topografix.com/GPX/1/1"
EARTH_R = 6371000.0
STITCH_TOLERANCE_M = 80.0


def normalize_library_manifest(data: Dict[str, Any]) -> Dict[str, Any]:
    """Accept legacy ``chunks`` key; normalize to ``legs``."""
    out = dict(data)
    if "legs" not in out and "chunks" in out:
        out["legs"] = out.pop("chunks")
    out.pop("chunks", None)
    out.setdefault("legs", [])
    return out


def manifest_legs(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Leg entries from a manifest (after normalization)."""
    m = normalize_library_manifest(manifest) if "chunks" in manifest else manifest
    return list(m.get("legs") or [])


def set_manifest_legs(manifest: Dict[str, Any], legs: List[Dict[str, Any]]) -> None:
    manifest["legs"] = legs
    manifest.pop("chunks", None)


def segment_leg_id(seg: Dict[str, Any]) -> str:
    """Stable leg id on a course segment row (legacy ``chunk_id`` accepted on read)."""
    return str(seg.get("leg_id") or seg.get("chunk_id") or "").strip()


def set_segment_leg_id(seg: Dict[str, Any], leg_id: str) -> None:
    if leg_id:
        seg["leg_id"] = leg_id
    seg.pop("chunk_id", None)


def _haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_manifest(path: Path) -> Dict[str, Any]:
    """Load YAML manifest with legs and recipes."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid manifest: {path}")
    if "recipes" not in data:
        raise ValueError("manifest must include recipes")
    if "legs" not in data and "chunks" not in data:
        raise ValueError("manifest must include legs and recipes")
    return normalize_library_manifest(data)


def parse_leg_gpx(path: Path) -> Dict[str, Any]:
    """Parse a PlotARoute leg GPX into coordinates and length."""
    course = parse_gpx_file(str(path))
    coords = [[p.lon, p.lat] for p in course.points]
    if len(coords) < 2:
        raise ValueError(f"Leg GPX needs at least 2 points: {path}")
    return {
        "name": course.name,
        "coordinates": coords,
        "length_km": round(course.total_distance_km, 2),
        "start": coords[0],
        "end": coords[-1],
        "point_count": len(coords),
    }


def validate_recipe_stitch(
    library_dir: Path,
    leg_ids: Sequence[str],
    legs_by_id: Dict[str, Dict[str, Any]],
    *,
    tolerance_m: float = STITCH_TOLERANCE_M,
) -> List[str]:
    """Return human-readable warnings for endpoint gaps between consecutive legs."""
    warnings: List[str] = []
    for i in range(len(leg_ids) - 1):
        a_id, b_id = leg_ids[i], leg_ids[i + 1]
        a = legs_by_id.get(a_id)
        b = legs_by_id.get(b_id)
        if not a or not b:
            warnings.append(f"Unknown leg in recipe: {a_id} or {b_id}")
            continue
        gap = _haversine_m(a["end"][0], a["end"][1], b["start"][0], b["start"][1])
        if gap > tolerance_m:
            warnings.append(
                f"Stitch gap {gap:.0f}m between {a_id} ({a.get('file', '')}) "
                f"and {b_id} ({b.get('file', '')})"
            )
    return warnings


def load_leg_library(library_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Load all legs from manifest into memory."""
    out: Dict[str, Dict[str, Any]] = {}
    for entry in manifest_legs(manifest):
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("id", "")).strip()
        file_name = entry.get("file")
        if not cid or not file_name:
            continue
        gpx_path = library_dir / str(file_name)
        parsed = parse_leg_gpx(gpx_path)
        out[cid] = {**entry, **parsed, "file": str(file_name)}
    return out


def concat_recipe_coordinates(
    leg_ids: Sequence[str],
    legs_by_id: Dict[str, Dict[str, Any]],
) -> List[List[float]]:
    """Concatenate leg LineStrings; drop duplicate join vertex."""
    coords: List[List[float]] = []
    for cid in leg_ids:
        leg = legs_by_id.get(cid)
        if not leg:
            raise ValueError(f"Unknown leg id: {cid}")
        part = leg["coordinates"]
        if not coords:
            coords.extend(part)
        else:
            coords.extend(part[1:])
    return coords


def build_event_gpx_content(
    event_id: str,
    manifest: Dict[str, Any],
    legs_by_id: Dict[str, Dict[str, Any]],
    *,
    course_name: str = "",
) -> str:
    """Build GPX 1.1 XML for one event recipe."""
    import xml.etree.ElementTree as ET

    recipes = manifest.get("recipes") or {}
    leg_ids = recipes.get(event_id) or recipes.get(event_id.lower())
    if not leg_ids:
        raise ValueError(f"No recipe for event: {event_id}")

    coords = concat_recipe_coordinates(leg_ids, legs_by_id)
    root = ET.Element("gpx", version="1.1", creator="run-density segment_library")
    root.set("xmlns", GPX_NS)
    trk = ET.SubElement(root, "trk")
    name_el = ET.SubElement(trk, "name")
    name_el.text = course_name or f"{event_id} course"
    trkseg = ET.SubElement(trk, "trkseg")
    for lon, lat in coords:
        ET.SubElement(trkseg, "trkpt", lat=str(lat), lon=str(lon))
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _events_for_leg(
    leg_id: str,
    recipes: Dict[str, Any],
    event_ids: Sequence[str],
) -> List[str]:
    out: List[str] = []
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        if leg_id in seq:
            out.append(eid.lower())
    return out


def build_course_segments_from_library(
    manifest: Dict[str, Any],
    legs_by_id: Dict[str, Dict[str, Any]],
    event_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Build course['segments'] list: one dict per library leg (multi-event row).

    Each segment has geometry length (leg length) and per-event from/to km from
    cumulative distance along each event's recipe (2026 segments.csv model).
    """
    event_ids = list(event_ids or COURSE_EVENT_IDS)
    recipes = manifest.get("recipes") or {}

    # Per-event cumulative at each leg end (only legs in that recipe)
    event_cum_at_leg: Dict[str, Dict[str, float]] = {e: {} for e in event_ids}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        cum = 0.0
        for cid in seq:
            ch = legs_by_id.get(cid)
            if not ch:
                continue
            cum += float(ch["length_km"])
            event_cum_at_leg[eid.lower()][cid] = round(cum, 2)

    segments: List[Dict[str, Any]] = []
    leg_order = manifest_legs(manifest)
    segment_index = 0
    for entry in leg_order:
        if not isinstance(entry, dict):
            continue
        cid = str(entry.get("id", "")).strip()
        ch = legs_by_id.get(cid)
        if not ch:
            continue
        segment_index += 1
        length_km = float(ch["length_km"])
        events = _events_for_leg(cid, recipes, event_ids)
        seg: Dict[str, Any] = {
            "seg_id": f"S{segment_index}",
            "seg_label": (entry.get("seg_label") or ch.get("name") or cid).strip(),
            "from_label": (entry.get("start_label") or "").strip(),
            "to_label": (entry.get("end_label") or "").strip(),
            "width_m": entry.get("width_m", 3),
            "schema": entry.get("schema", "on_course_open"),
            "direction": entry.get("direction", "uni"),
            "description": (entry.get("description") or "").strip(),
            "events": events,
            "leg_id": cid,
            "length_km": length_km,
            "from_km": 0.0,
            "to_km": length_km,
        }
        for eid in event_ids:
            el = eid.lower()
            if el not in events:
                seg[f"{el}_from_km"] = 0.0
                seg[f"{el}_to_km"] = 0.0
                continue
            to_km = event_cum_at_leg[el].get(cid, 0.0)
            from_km = round(to_km - length_km, 2)
            seg[f"{el}_from_km"] = max(0.0, from_km)
            seg[f"{el}_to_km"] = to_km
        segments.append(seg)

    enrich_segments_event_distances(segments, event_ids)
    return segments


def build_flow_csv_from_segments(
    segments: Sequence[Dict[str, Any]],
    event_ids: Optional[Sequence[str]] = None,
    *,
    overrides: Optional[Sequence[Dict[str, Any]]] = None,
    include_same_event_pairs: bool = True,
) -> str:
    """
    Generate 2026-style flow.csv from multi-event segment rows.

    For each segment used by 2+ events, emit one row per event pair (A,B) with
    from_km_a/to_km_a and from_km_b/to_km_b from segment per-event columns.
    """
    event_ids = [e.lower() for e in (event_ids or COURSE_EVENT_IDS)]
    override_index = {
        (str(o.get("seg_id", "")), str(o.get("event_a", "")), str(o.get("event_b", ""))): o
        for o in (overrides or [])
        if isinstance(o, dict)
    }

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            "seg_id",
            "seg_label",
            "event_a",
            "event_b",
            "from_km_a",
            "to_km_a",
            "from_km_b",
            "to_km_b",
            "flow_type",
            "direction",
            "notes",
        ]
    )

    for seg in segments:
        seg_id = str(seg.get("seg_id", "")).strip()
        seg_label = str(seg.get("seg_label", "")).strip()
        direction = seg.get("direction", "uni")
        active = []
        for eid in event_ids:
            if eid in (seg.get("events") or []):
                active.append(eid)
            elif str(seg.get(eid, "n")).lower() == "y":
                active.append(eid)
        if len(active) < 2 and not include_same_event_pairs:
            continue
        pairs: List[Tuple[str, str]] = []
        if include_same_event_pairs:
            pairs = [(a, b) for a, b in combinations(active, 2)]
            for e in active:
                pairs.append((e, e))
        else:
            pairs = [(a, b) for a, b in combinations(active, 2)]
        for event_a, event_b in pairs:
            from_a = float(seg.get(f"{event_a}_from_km") or 0)
            to_a = float(seg.get(f"{event_a}_to_km") or 0)
            from_b = float(seg.get(f"{event_b}_from_km") or 0)
            to_b = float(seg.get(f"{event_b}_to_km") or 0)
            if to_a <= from_a and to_b <= from_b:
                continue
            key = (seg_id, event_a, event_b)
            ov = override_index.get(key, {})
            flow_type = ov.get("flow_type") or seg.get("flow_type") or "overtake"
            notes = ov.get("notes") or seg.get("flow_notes") or ""
            w.writerow(
                [
                    seg_id,
                    seg_label,
                    event_a,
                    event_b,
                    from_a,
                    to_a,
                    from_b,
                    to_b,
                    flow_type,
                    direction,
                    notes,
                ]
            )
    return out.getvalue()


def export_library_to_course(
    library_dir: Path,
    manifest_path: Optional[Path] = None,
    *,
    event_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Load library + manifest and return export bundle (segments, flow csv, validation).
    """
    manifest_path = manifest_path or (library_dir / "manifest.yaml")
    manifest = load_manifest(manifest_path)
    legs_by_id = load_leg_library(library_dir, manifest)
    event_ids = list(event_ids or COURSE_EVENT_IDS)

    stitch_warnings: List[str] = []
    recipes = manifest.get("recipes") or {}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        stitch_warnings.extend(
            validate_recipe_stitch(library_dir, seq, legs_by_id)
        )

    segments = build_course_segments_from_library(manifest, legs_by_id, event_ids)
    course = {"segments": segments, "name": manifest.get("label", "")}
    segments_csv = build_segments_csv(course, fmt="pipeline")
    flow_csv = build_flow_csv_from_segments(
        segments,
        event_ids,
        overrides=manifest.get("flow_overrides"),
    )

    recipe_lengths: Dict[str, float] = {}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        recipe_lengths[eid] = round(
            sum(float(legs_by_id[c]["length_km"]) for c in seq if c in legs_by_id),
            2,
        )

    return {
        "manifest": manifest,
        "segments": segments,
        "segments_csv": segments_csv,
        "flow_csv": flow_csv,
        "stitch_warnings": stitch_warnings,
        "recipe_lengths_km": recipe_lengths,
    }


def write_package_exports(
    package_dir: Path,
    library_dir: Path,
    manifest_path: Optional[Path] = None,
    *,
    write_event_gpx: bool = True,
) -> Dict[str, Any]:
    """Write segments.csv, flow.csv, and optional per-event GPX into a config package."""
    bundle = export_library_to_course(library_dir, manifest_path)
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "segments.csv").write_text(bundle["segments_csv"], encoding="utf-8")
    (package_dir / "flow.csv").write_text(bundle["flow_csv"], encoding="utf-8")

    manifest = bundle["manifest"]
    legs_by_id = load_leg_library(
        library_dir, manifest
    )
    if write_event_gpx:
        for eid in (manifest.get("recipes") or {}).keys():
            gpx = build_event_gpx_content(eid, manifest, legs_by_id)
            (package_dir / f"{eid.lower()}.gpx").write_text(gpx, encoding="utf-8")

    return bundle
