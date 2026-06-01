"""
Config package course legs: create, edit, delete GPX legs and leg-scoped locations.

Issue #769 — in-runflow leg authoring (PlotARoute reference is optional bootstrap only).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.core.config_package.segment_recipes import (
    load_package_segment_manifest,
    package_segment_library_dir,
    save_package_segment_manifest,
)
from app.core.config_package.storage import (
    load_config_course,
    resolve_config_package_path,
    save_config_course,
    validate_config_id,
)
from app.core.course.segment_library import parse_chunk_gpx
from app.utils.constants import LOCATION_TYPE_CHOICES

_LEG_ID_RE = re.compile(r"^\d{2,3}$")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug[:48] or "leg"


def _normalize_locations(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    allowed_types = set(LOCATION_TYPE_CHOICES)
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("loc_label") or item.get("label") or "").strip()
        if not label:
            continue
        loc_type = str(item.get("loc_type") or item.get("type") or "course").strip().lower()
        if loc_type not in allowed_types:
            loc_type = "course"
        try:
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
        except (TypeError, ValueError):
            continue
        placement = str(item.get("placement") or "along").strip().lower()
        if placement not in ("start", "end", "along"):
            placement = "along"
        out.append(
            {
                "loc_label": label,
                "loc_type": loc_type,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "placement": placement,
            }
        )
    return out


def _default_endpoint_labels(leg_label: str, parsed: Dict[str, Any]) -> tuple[str, str]:
    name = (parsed.get("name") or leg_label or "Leg").strip()
    return f"Start — {name}", f"End — {name}"


def allocate_next_leg_id(chunks: Sequence[Dict[str, Any]]) -> str:
    """Next numeric leg id (01, 02, …)."""
    max_n = 0
    for entry in chunks:
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("id", "")).strip()
        if raw.isdigit():
            max_n = max(max_n, int(raw))
    return f"{max_n + 1:02d}"


def _find_chunk_index(chunks: List[Dict[str, Any]], leg_id: str) -> int:
    for i, entry in enumerate(chunks):
        if isinstance(entry, dict) and str(entry.get("id", "")).strip() == leg_id:
            return i
    return -1


def _remove_leg_from_recipes(manifest: Dict[str, Any], leg_id: str) -> None:
    recipes = manifest.get("recipes") or {}
    for key in list(recipes.keys()):
        seq = recipes.get(key) or []
        if isinstance(seq, list):
            recipes[key] = [x for x in seq if str(x) != leg_id]


def leg_row_from_entry(
    entry: Dict[str, Any],
    loaded: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    loaded = loaded or {}
    coords = loaded.get("coordinates") or []
    start_lat = start_lon = end_lat = end_lon = None
    if coords:
        start_lon, start_lat = coords[0][0], coords[0][1]
        end_lon, end_lat = coords[-1][0], coords[-1][1]
    locations = _normalize_locations(entry.get("locations"))
    leg_label = (entry.get("seg_label") or loaded.get("name") or entry.get("id") or "").strip()
    start_label = (entry.get("start_label") or "").strip()
    end_label = (entry.get("end_label") or "").strip()
    if not start_label and leg_label:
        start_label = f"Start — {leg_label}"
    if not end_label and leg_label:
        end_label = f"End — {leg_label}"
    return {
        "id": str(entry.get("id", "")).strip(),
        "file": entry.get("file") or loaded.get("file"),
        "leg_label": leg_label,
        "start_label": start_label,
        "end_label": end_label,
        "length_km": loaded.get("length_km", 0),
        "width_m": entry.get("width_m", 3),
        "schema": entry.get("schema", "on_course_open"),
        "direction": entry.get("direction", "uni"),
        "description": (entry.get("description") or "").strip(),
        "locations": locations,
        "location_count": len(locations),
        "start_lat": start_lat,
        "start_lon": start_lon,
        "end_lat": end_lat,
        "end_lon": end_lon,
    }


def create_package_leg(
    config_id: str,
    gpx_bytes: bytes,
    filename: str,
    *,
    leg_label: str = "",
    start_label: str = "",
    end_label: str = "",
    width_m: float = 3,
    schema: str = "on_course_open",
    direction: str = "uni",
    description: str = "",
    locations: Optional[List[Dict[str, Any]]] = None,
    leg_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a new leg with GPX to the package segment library."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    lib_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    new_id = (leg_id or "").strip() or allocate_next_leg_id(chunks)
    if not _LEG_ID_RE.match(new_id):
        raise ValueError("leg_id must be two or three digits (e.g. 01, 12)")
    if _find_chunk_index(chunks, new_id) >= 0:
        raise ValueError(f"Leg id already exists: {new_id}")

    label = (leg_label or Path(filename).stem.replace("_", " ")).strip() or f"Leg {new_id}"
    safe_name = f"{new_id}_{_slugify(label)}.gpx"
    dest = lib_dir / safe_name
    dest.write_bytes(gpx_bytes)
    parsed = parse_chunk_gpx(dest)

    s_label = start_label.strip() or _default_endpoint_labels(label, parsed)[0]
    e_label = end_label.strip() or _default_endpoint_labels(label, parsed)[1]

    entry = {
        "id": new_id,
        "file": safe_name,
        "seg_label": label,
        "start_label": s_label,
        "end_label": e_label,
        "width_m": width_m,
        "schema": schema,
        "direction": direction,
        "description": (description or "").strip(),
        "locations": _normalize_locations(locations),
    }
    chunks.append(entry)
    manifest["chunks"] = chunks
    save_package_segment_manifest(cid, manifest)
    from app.core.config_package.segment_recipes import get_package_segment_library_state

    return get_package_segment_library_state(cid)


def update_package_leg(
    config_id: str,
    leg_id: str,
    fields: Dict[str, Any],
    *,
    gpx_bytes: Optional[bytes] = None,
    gpx_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Update leg metadata and optionally replace GPX."""
    cid = validate_config_id(config_id)
    leg_id = str(leg_id).strip()
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    idx = _find_chunk_index(chunks, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")

    entry = dict(chunks[idx])
    if "leg_label" in fields or "seg_label" in fields:
        entry["seg_label"] = str(
            fields.get("leg_label") or fields.get("seg_label") or entry.get("seg_label") or ""
        ).strip()
    if "start_label" in fields:
        entry["start_label"] = str(fields.get("start_label") or "").strip()
    if "end_label" in fields:
        entry["end_label"] = str(fields.get("end_label") or "").strip()
    for key in ("width_m", "schema", "direction", "description"):
        if key in fields:
            entry[key] = fields[key]
    if "locations" in fields:
        entry["locations"] = _normalize_locations(fields.get("locations"))

    if gpx_bytes:
        file_name = entry.get("file") or f"{leg_id}_{_slugify(entry.get('seg_label', ''))}.gpx"
        if gpx_filename:
            file_name = f"{leg_id}_{_slugify(Path(gpx_filename).stem)}.gpx"
        dest = lib_dir / Path(file_name).name
        dest.write_bytes(gpx_bytes)
        entry["file"] = dest.name
        parsed = parse_chunk_gpx(dest)
        if not entry.get("start_label"):
            entry["start_label"] = _default_endpoint_labels(entry.get("seg_label", ""), parsed)[0]
        if not entry.get("end_label"):
            entry["end_label"] = _default_endpoint_labels(entry.get("seg_label", ""), parsed)[1]

    chunks[idx] = entry
    manifest["chunks"] = chunks
    save_package_segment_manifest(cid, manifest)
    from app.core.config_package.segment_recipes import get_package_segment_library_state

    return get_package_segment_library_state(cid)


def delete_package_leg(config_id: str, leg_id: str) -> Dict[str, Any]:
    """Remove a leg, its GPX file, and recipe references."""
    cid = validate_config_id(config_id)
    leg_id = str(leg_id).strip()
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    idx = _find_chunk_index(chunks, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")

    entry = chunks.pop(idx)
    file_name = entry.get("file")
    if file_name:
        gpx_path = lib_dir / str(file_name)
        if gpx_path.is_file():
            gpx_path.unlink()
    _remove_leg_from_recipes(manifest, leg_id)
    manifest["chunks"] = chunks
    save_package_segment_manifest(cid, manifest)
    from app.core.config_package.segment_recipes import get_package_segment_library_state

    return get_package_segment_library_state(cid)


def merge_leg_locations_into_course(config_id: str) -> None:
    """Copy leg-scoped locations into course.json (replaces prior leg-sourced rows)."""
    cid = validate_config_id(config_id)
    manifest = load_package_segment_manifest(cid)
    course = load_config_course(cid)
    locations: List[Dict[str, Any]] = [
        loc
        for loc in (course.get("locations") or [])
        if isinstance(loc, dict) and loc.get("source") != "leg"
    ]
    for entry in manifest.get("chunks") or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        for i, loc in enumerate(_normalize_locations(entry.get("locations"))):
            locations.append(
                {
                    "loc_id": f"L{leg_id}-{i + 1}",
                    "loc_label": loc["loc_label"],
                    "loc_type": loc["loc_type"],
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "leg_id": leg_id,
                    "placement": loc.get("placement", "along"),
                    "source": "leg",
                    "full": "n",
                    "half": "n",
                    "10k": "n",
                    "elite": "n",
                    "open": "n",
                }
            )
    course["locations"] = locations
    save_config_course(cid, course)
