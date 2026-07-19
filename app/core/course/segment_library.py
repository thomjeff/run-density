"""
Segment library + event recipes (reusable GPX legs and per-event recipes).

A segment library is a set of reusable GPX legs. Event recipes list leg ids in order.
From that we build:
  - per-event combined GPX
  - multi-event segments.csv (one row per recipe occurrence, 2026-style)
  - flow.csv rows for event pairs on shared legs (#759 baseline)
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml

from app.core.course.export import build_segments_csv
from app.core.course.flow_csv import build_flow_csv_from_segments
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
    """Parse a leg GPX file into coordinates and length."""
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


def validate_corridor_pairings(
    legs_by_id: Dict[str, Dict[str, Any]],
    recipes: Dict[str, Any],
    *,
    tolerance_m: float = STITCH_TOLERANCE_M,
) -> List[str]:
    """
    Warnings for corridor pairings (Issue #785): dangling or asymmetric
    ``paired_with`` references, pairs whose legs don't look like reverses of
    each other, and pairs inert because a leg is unused in every recipe.
    """
    warnings: List[str] = []
    used_legs: set = set()
    for seq in (recipes or {}).values():
        if isinstance(seq, list):
            used_legs.update(str(x).strip() for x in seq if str(x or "").strip())

    checked: set = set()
    for leg_id, leg in legs_by_id.items():
        mate_id = str(leg.get("paired_with") or "").strip()
        if not mate_id:
            continue
        mate = legs_by_id.get(mate_id)
        if mate is None:
            warnings.append(
                f"Leg {leg_id} is paired with unknown leg {mate_id}"
            )
            continue
        mate_pair = str(mate.get("paired_with") or "").strip()
        if mate_pair != leg_id:
            warnings.append(
                f"Asymmetric pairing: leg {leg_id} pairs with {mate_id}, "
                f"but {mate_id} pairs with {mate_pair or 'nothing'}"
            )
        key = tuple(sorted([leg_id, mate_id]))
        if key in checked:
            continue
        checked.add(key)
        if leg_id not in used_legs and mate_id not in used_legs:
            warnings.append(
                f"Corridor pairing {key[0]}/{key[1]} is unused: "
                f"neither leg appears in any event recipe"
            )
        # Paired legs should be approximate reverses: A start ≈ B end, A end ≈ B start.
        try:
            gap_se = _haversine_m(
                leg["start"][0], leg["start"][1], mate["end"][0], mate["end"][1]
            )
            gap_es = _haversine_m(
                leg["end"][0], leg["end"][1], mate["start"][0], mate["start"][1]
            )
        except (KeyError, IndexError, TypeError):
            continue
        if gap_se > tolerance_m or gap_es > tolerance_m:
            warnings.append(
                f"Corridor pairing {key[0]}/{key[1]}: leg endpoints are not "
                f"reverses of each other "
                f"(start↔end gaps {gap_se:.0f}m / {gap_es:.0f}m)"
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


LegOccurrence = Tuple[str, int]


def _events_for_leg(
    leg_id: str,
    recipes: Dict[str, Any],
    event_ids: Sequence[str],
) -> List[str]:
    """Events whose recipe includes leg_id at least once (first occurrence)."""
    return _events_for_leg_occurrence(leg_id, 1, recipes, event_ids)


def _events_for_leg_occurrence(
    leg_id: str,
    occurrence: int,
    recipes: Dict[str, Any],
    event_ids: Sequence[str],
) -> List[str]:
    """Events whose recipe includes leg_id at least ``occurrence`` times."""
    out: List[str] = []
    leg_id = str(leg_id).strip()
    if not leg_id or occurrence < 1:
        return out
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        count = sum(1 for raw in seq if str(raw).strip() == leg_id)
        if count >= occurrence:
            out.append(eid.lower())
    return out


def _build_event_occurrence_km(
    recipes: Dict[str, Any],
    legs_by_id: Dict[str, Dict[str, Any]],
    event_ids: Sequence[str],
) -> Dict[str, Dict[LegOccurrence, Tuple[float, float]]]:
    """Per-event km window for each (leg_id, 1-based occurrence) in that recipe."""
    result: Dict[str, Dict[LegOccurrence, Tuple[float, float]]] = {}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        occ_counts: Dict[str, int] = {}
        cum = 0.0
        event_map: Dict[LegOccurrence, Tuple[float, float]] = {}
        for raw_id in seq:
            cid = str(raw_id).strip()
            ch = legs_by_id.get(cid)
            if not ch:
                continue
            length = float(ch["length_km"])
            occ_counts[cid] = occ_counts.get(cid, 0) + 1
            occ = occ_counts[cid]
            cum += length
            event_map[(cid, occ)] = (round(cum - length, 2), round(cum, 2))
        result[eid.lower()] = event_map
    return result


def _recipe_occurrence_order(
    legs_by_id: Dict[str, Dict[str, Any]],
    event_ids: Sequence[str],
    recipes: Dict[str, Any],
) -> List[LegOccurrence]:
    """(leg_id, occurrence) pairs in recipe traversal order (first-seen wins)."""
    ordered: List[LegOccurrence] = []
    seen: set[LegOccurrence] = set()
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        occ_in_pass: Dict[str, int] = {}
        for raw_id in recipes.get(key) or []:
            cid = str(raw_id).strip()
            if not cid or cid not in legs_by_id:
                continue
            occ_in_pass[cid] = occ_in_pass.get(cid, 0) + 1
            occ = occ_in_pass[cid]
            token = (cid, occ)
            if token in seen:
                continue
            events = _events_for_leg_occurrence(cid, occ, recipes, event_ids)
            if not events:
                continue
            seen.add(token)
            ordered.append(token)
    return ordered


def _recipe_leg_order(
    manifest: Dict[str, Any],
    legs_by_id: Dict[str, Dict[str, Any]],
    event_ids: Sequence[str],
    recipes: Dict[str, Any],
) -> List[str]:
    """Leg ids in recipe traversal order (union across events, first-seen wins)."""
    del manifest  # kept for call-site compatibility
    return [cid for cid, _occ in _recipe_occurrence_order(legs_by_id, event_ids, recipes)]


def build_course_segments_from_library(
    manifest: Dict[str, Any],
    legs_by_id: Dict[str, Dict[str, Any]],
    event_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Build course['segments'] list: one row per recipe occurrence of a leg.

    The same library leg may appear multiple times in one event's recipe (e.g.
    out-and-back). Each passage becomes its own segment row with distinct
    per-event km windows. Leg metadata is shared; ``leg_occurrence`` marks the
    nth use of ``leg_id`` in the combined ordering.
    """
    event_ids = list(event_ids or COURSE_EVENT_IDS)
    recipes = manifest.get("recipes") or {}
    event_km = _build_event_occurrence_km(recipes, legs_by_id, event_ids)

    entries_by_id: Dict[str, Dict[str, Any]] = {
        str(entry.get("id", "")).strip(): entry
        for entry in manifest_legs(manifest)
        if isinstance(entry, dict) and entry.get("id")
    }

    segments: List[Dict[str, Any]] = []
    for segment_index, (cid, occ) in enumerate(
        _recipe_occurrence_order(legs_by_id, event_ids, recipes), start=1
    ):
        entry = entries_by_id.get(cid) or {}
        ch = legs_by_id.get(cid)
        if not ch:
            continue
        events = _events_for_leg_occurrence(cid, occ, recipes, event_ids)
        if not events:
            continue
        length_km = float(ch["length_km"])
        leg_description = (
            str(entry.get("description") or entry.get("flow_notes") or "").strip()
        )
        seg_label = (entry.get("seg_label") or ch.get("name") or cid).strip()
        if occ > 1:
            seg_label = f"{seg_label} ({occ})"
        seg: Dict[str, Any] = {
            "seg_id": f"S{segment_index}",
            "seg_label": seg_label,
            "from_label": (entry.get("start_label") or "").strip(),
            "to_label": (entry.get("end_label") or "").strip(),
            "width_m": entry.get("width_m", 3),
            "schema": entry.get("schema", "on_course_open"),
            "direction": entry.get("direction", "uni"),
            "flow_type": (entry.get("flow_type") or "none").strip().lower(),
            "paired_with": str(entry.get("paired_with") or "").strip(),
            "flow_notes": leg_description,
            "description": leg_description,
            "events": events,
            "leg_id": cid,
            "leg_occurrence": occ,
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
            from_km, to_km = event_km.get(el, {}).get((cid, occ), (0.0, 0.0))
            seg[f"{el}_from_km"] = max(0.0, from_km)
            seg[f"{el}_to_km"] = to_km
        segments.append(seg)

    return segments


def export_library_to_course(
    library_dir: Path,
    manifest_path: Optional[Path] = None,
    *,
    manifest: Optional[Dict[str, Any]] = None,
    event_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Load library + manifest and return export bundle (segments, flow csv, validation).
    """
    if manifest is None:
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
    stitch_warnings.extend(validate_corridor_pairings(legs_by_id, recipes))

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
