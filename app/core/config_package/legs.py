"""
Config package course legs: create, edit, delete GPX legs and leg-scoped locations.

Issue #769 — in-runflow leg authoring (PlotARoute reference is optional bootstrap only).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.config_package.location_ids import (
    allocate_location_id,
    assign_unique_location_ids,
    parse_location_id,
)
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
from app.core.course.export import build_gpx_line_coordinates
from app.core.course.segment_library import parse_chunk_gpx
from app.core.config_package.segment_recipes import package_recipe_event_ids
from app.utils.constants import (
    LEG_MAP_NO_SNAP_LOCATION_TYPES,
    COURSE_EVENT_IDS,
    LOCATION_PLACEMENT_CHOICES,
    LOCATION_TYPE_CHOICES,
    ON_COURSE_LOCATION_TYPES,
    SEGMENT_DIRECTION_CHOICES,
    SEGMENT_DIRECTION_VALUES,
    SEGMENT_SCHEMA_CHOICES,
    SEGMENT_SCHEMA_VALUES,
)

_LEG_LOC_PRESERVE_FIELDS = (
    "loc_label",
    "loc_type",
    "lat",
    "lon",
    "placement",
    "notes",
    "buffer",
    "interval",
    "zone",
    "equipment",
    "contact",
    "proxy_loc_id",
    "day",
    "onepage",
    "resources",
)

_LEG_ID_RE = re.compile(r"^\d{2,3}$")
LEG_EXPORT_VERSION = 1


def _normalize_segment_schema(schema: Any) -> str:
    value = str(schema or "on_course_open").strip()
    if value not in SEGMENT_SCHEMA_VALUES:
        raise ValueError(f"schema must be one of: {', '.join(SEGMENT_SCHEMA_VALUES)}")
    return value


def _normalize_segment_direction(direction: Any) -> str:
    value = str(direction or "uni").strip()
    if value not in SEGMENT_DIRECTION_VALUES:
        raise ValueError(f"direction must be one of: {', '.join(SEGMENT_DIRECTION_VALUES)}")
    return value


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
        if loc_type in LEG_MAP_NO_SNAP_LOCATION_TYPES:
            placement = "off"
        else:
            placement = str(item.get("placement") or "along").strip().lower()
            if placement not in LOCATION_PLACEMENT_CHOICES:
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
    schema = _normalize_segment_schema(schema)
    direction = _normalize_segment_direction(direction)

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
    for key in ("width_m", "description"):
        if key in fields:
            entry[key] = fields[key]
    if "schema" in fields:
        entry["schema"] = _normalize_segment_schema(fields["schema"])
    if "direction" in fields:
        entry["direction"] = _normalize_segment_direction(fields["direction"])
    if "locations" in fields:
        entry["locations"] = _normalize_locations(fields.get("locations"))

    if gpx_bytes:
        if gpx_filename:
            file_name = Path(str(gpx_filename)).name
        else:
            file_name = entry.get("file") or f"{leg_id}_{_slugify(entry.get('seg_label', ''))}.gpx"
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
    if "locations" in fields:
        try:
            merge_leg_locations_into_course(cid)
        except FileNotFoundError:
            pass
    elif any(
        key in fields
        for key in ("start_label", "end_label", "leg_label", "seg_label")
    ):
        try:
            sync_leg_locations_if_applied(cid)
        except FileNotFoundError:
            pass
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


def parse_leg_export_json_bytes(data: bytes) -> Optional[Dict[str, Any]]:
    """Parse a runflow leg export JSON file; return the ``leg`` object or None."""
    try:
        payload = json.loads(data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("export_kind") != "runflow_leg":
        return None
    leg = payload.get("leg")
    return leg if isinstance(leg, dict) else None


def leg_id_from_export_filename(filename: str) -> Optional[str]:
    """Derive leg id from export sidecar name (e.g. 01.json -> 01)."""
    stem = Path(filename).stem
    if _LEG_ID_RE.match(stem):
        return stem
    return None


def merge_leg_export_into_chunk(
    entry: Dict[str, Any],
    leg_export: Dict[str, Any],
) -> None:
    """Apply exported leg metadata and locations onto a manifest chunk entry."""
    label = str(leg_export.get("leg_label") or leg_export.get("seg_label") or "").strip()
    if label:
        entry["seg_label"] = label
    for key in ("start_label", "end_label", "description"):
        if key in leg_export and leg_export[key] is not None:
            entry[key] = str(leg_export[key] or "").strip()
    if "width_m" in leg_export and leg_export["width_m"] is not None:
        try:
            entry["width_m"] = float(leg_export["width_m"])
        except (TypeError, ValueError):
            pass
    if "schema" in leg_export and leg_export["schema"]:
        try:
            entry["schema"] = _normalize_segment_schema(leg_export["schema"])
        except ValueError:
            pass
    if "direction" in leg_export and leg_export["direction"]:
        try:
            entry["direction"] = _normalize_segment_direction(leg_export["direction"])
        except ValueError:
            pass
    if "locations" in leg_export:
        entry["locations"] = _normalize_locations(leg_export.get("locations"))


def apply_leg_exports_to_manifest(
    manifest: Dict[str, Any],
    exports_by_leg_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge runflow leg export JSON payloads into manifest chunks by leg id."""
    if not exports_by_leg_id:
        return manifest
    chunks = manifest.get("chunks") or []
    for entry in chunks:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        leg_export = exports_by_leg_id.get(leg_id)
        if leg_export:
            merge_leg_export_into_chunk(entry, leg_export)
    manifest["chunks"] = chunks
    return manifest


def export_package_leg_zip(config_id: str, leg_id: str) -> Tuple[bytes, str]:
    """
    Build a zip with the leg GPX track and JSON metadata (label, schema, locations, …).

    Returns (zip_bytes, suggested_download_filename).
    """
    cid = validate_config_id(config_id)
    leg_id = str(leg_id).strip()
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    idx = _find_chunk_index(chunks, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    entry = chunks[idx]
    file_name = entry.get("file")
    if not file_name:
        raise ValueError(f"Leg {leg_id} has no GPX file")
    gpx_path = lib_dir / str(file_name)
    if not gpx_path.is_file():
        raise FileNotFoundError(f"GPX not found: {file_name}")
    parsed = parse_chunk_gpx(gpx_path)
    row = leg_row_from_entry(entry, parsed)
    payload: Dict[str, Any] = {
        "export_version": LEG_EXPORT_VERSION,
        "export_kind": "runflow_leg",
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "config_id": cid,
        "leg": {
            "id": row["id"],
            "leg_label": row["leg_label"],
            "start_label": row["start_label"],
            "end_label": row["end_label"],
            "width_m": row["width_m"],
            "schema": row["schema"],
            "direction": row["direction"],
            "description": row["description"],
            "length_km": row["length_km"],
            "gpx_file": str(file_name),
            "locations": row["locations"],
        },
    }
    gpx_arcname = f"{leg_id}.gpx"
    json_arcname = f"{leg_id}.json"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(gpx_arcname, gpx_path.read_bytes())
        zf.writestr(
            json_arcname,
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        )
        zf.writestr(
            "README.txt",
            (
                f"Runflow leg export (v{LEG_EXPORT_VERSION})\n"
                f"config_id: {cid}\n"
                f"leg_id: {leg_id}\n\n"
                f"  {gpx_arcname} — route polyline (GPX 1.1 track)\n"
                f"  {json_arcname} — leg metadata and map locations\n"
            ),
        )
    download_name = f"{cid}_leg_{leg_id}.zip"
    return buf.getvalue(), download_name


def _normalize_line_coordinates(raw: Any) -> List[List[float]]:
    if not isinstance(raw, list) or len(raw) < 2:
        raise ValueError("coordinates must be a list of at least two [lon, lat] points")
    out: List[List[float]] = []
    for pt in raw:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            raise ValueError("each coordinate must be [lon, lat]")
        try:
            lon = round(float(pt[0]), 6)
            lat = round(float(pt[1]), 6)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid coordinate") from exc
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            raise ValueError("coordinate out of range")
        out.append([lon, lat])
    return out


def update_package_leg_geometry(
    config_id: str,
    leg_id: str,
    coordinates: List[List[float]],
) -> Dict[str, Any]:
    """Replace leg GPX track from edited [lon, lat] vertices (reshape route)."""
    coords = _normalize_line_coordinates(coordinates)
    cid = validate_config_id(config_id)
    leg_id = str(leg_id).strip()
    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    idx = _find_chunk_index(chunks, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    entry = chunks[idx]
    label = (entry.get("seg_label") or leg_id).strip() or leg_id
    gpx_content = build_gpx_line_coordinates(coords, track_name=label)
    return update_package_leg(
        config_id,
        leg_id,
        {},
        gpx_bytes=gpx_content.encode("utf-8"),
        gpx_filename=entry.get("file") or f"{leg_id}.gpx",
    )


def get_leg_line_geojson(config_id: str, leg_id: str) -> Dict[str, Any]:
    """GeoJSON LineString for map display of one leg."""
    cid = validate_config_id(config_id)
    leg_id = str(leg_id).strip()
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    idx = _find_chunk_index(chunks, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    entry = chunks[idx]
    file_name = entry.get("file")
    if not file_name:
        raise ValueError(f"Leg {leg_id} has no GPX file")
    gpx_path = lib_dir / str(file_name)
    if not gpx_path.is_file():
        raise FileNotFoundError(f"GPX not found: {file_name}")
    parsed = parse_chunk_gpx(gpx_path)
    coords = parsed.get("coordinates") or []
    if len(coords) < 2:
        raise ValueError(f"Leg {leg_id} GPX has insufficient points")
    return {
        "type": "Feature",
        "properties": {
            "leg_id": leg_id,
            "leg_label": (entry.get("seg_label") or "").strip(),
            "start_label": (entry.get("start_label") or "").strip(),
            "end_label": (entry.get("end_label") or "").strip(),
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def leg_loc_key(leg_id: str, index: int) -> str:
    return f"{leg_id}:{index}"


def _segment_for_leg(
    segments: Sequence[Dict[str, Any]], leg_id: str
) -> Optional[Dict[str, Any]]:
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if str(seg.get("chunk_id", "")).strip() == leg_id:
            return seg
    return None


def _event_flags_for_segment(
    seg: Optional[Dict[str, Any]], event_ids: Sequence[str]
) -> Dict[str, str]:
    on_seg = set()
    if seg:
        on_seg = {
            str(e).strip().lower()
            for e in (seg.get("events") or [])
            if str(e).strip()
        }
    flags: Dict[str, str] = {}
    for eid in event_ids:
        el = str(eid).strip().lower()
        flags[el] = "y" if el in on_seg else "n"
    return flags


def merge_leg_locations_into_course(config_id: str) -> None:
    """
    Copy leg-scoped placements from the segment library into course.json.

    Replaces prior ``source=leg`` rows. Preserves Course-tab edits (resources,
  notes, etc.) matched by ``leg_loc_key``. Sets ``seg_id`` from the combined
    segment whose ``chunk_id`` matches the leg.
    """
    cid = validate_config_id(config_id)
    manifest = load_package_segment_manifest(cid)
    course = load_config_course(cid)
    segments = [
        s for s in (course.get("segments") or []) if isinstance(s, dict)
    ]
    try:
        package_events = list(package_recipe_event_ids(cid))
    except (FileNotFoundError, ValueError):
        package_events = list(COURSE_EVENT_IDS)
    event_ids = package_events or list(COURSE_EVENT_IDS)

    existing_leg: Dict[str, Dict[str, Any]] = {}
    for loc in course.get("locations") or []:
        if not isinstance(loc, dict) or loc.get("source") != "leg":
            continue
        key = str(loc.get("leg_loc_key") or "").strip()
        if key:
            existing_leg[key] = loc

    locations: List[Dict[str, Any]] = [
        loc
        for loc in (course.get("locations") or [])
        if isinstance(loc, dict) and loc.get("source") != "leg"
    ]
    used_ids: set[int] = set()
    for loc in locations:
        parsed = parse_location_id(loc.get("id", loc.get("loc_id")))
        if parsed is not None and parsed > 0:
            used_ids.add(parsed)

    for entry in manifest.get("chunks") or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if not leg_id:
            continue
        seg = _segment_for_leg(segments, leg_id)
        seg_id = str(seg.get("seg_id", "")).strip() if seg else ""
        event_flags = _event_flags_for_segment(seg, event_ids)

        for i, loc in enumerate(_normalize_locations(entry.get("locations"))):
            key = leg_loc_key(leg_id, i)
            prev = existing_leg.get(key)
            on_course = loc["loc_type"] in ON_COURSE_LOCATION_TYPES
            row: Dict[str, Any] = {
                "loc_label": loc["loc_label"],
                "loc_type": loc["loc_type"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "leg_id": leg_id,
                "leg_loc_key": key,
                "placement": loc.get("placement", "along"),
                "source": "leg",
                "seg_id": seg_id if on_course else "",
            }
            for ev, flag in event_flags.items():
                row[ev] = flag
            for ev in COURSE_EVENT_IDS:
                row.setdefault(ev, "n")

            if prev:
                prev_id = parse_location_id(prev.get("id", prev.get("loc_id")))
                if prev_id is not None and prev_id > 0 and prev_id not in used_ids:
                    row["id"] = prev_id
                    used_ids.add(prev_id)
                else:
                    row["id"] = allocate_location_id(used_ids)
                if (prev.get("seg_id") or "").strip():
                    row["seg_id"] = str(prev["seg_id"]).strip()
                for field in _LEG_LOC_PRESERVE_FIELDS:
                    if field not in prev:
                        continue
                    val = prev[field]
                    if field == "resources":
                        if isinstance(val, dict):
                            row[field] = val
                        continue
                    if val not in (None, ""):
                        row[field] = val
            else:
                row["id"] = allocate_location_id(used_ids)
            locations.append(row)

    assign_unique_location_ids(locations)
    course["locations"] = locations
    save_config_course(cid, course)


def _manifest_chunk_order(manifest: Dict[str, Any]) -> List[str]:
    order: List[str] = []
    for entry in manifest.get("chunks") or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if leg_id:
            order.append(leg_id)
    return order


def _leg_id_for_segment(seg: Dict[str, Any], chunk_order: Sequence[str]) -> str:
    leg_id = str(seg.get("chunk_id", "")).strip()
    if leg_id:
        return leg_id
    match = re.match(r"^S(\d+)$", str(seg.get("seg_id", "")).strip(), re.IGNORECASE)
    if match:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(chunk_order):
            return chunk_order[idx]
    return ""


def sync_leg_segment_labels_into_course(config_id: str) -> bool:
    """
    Refresh segment from/to/label fields from leg library metadata.

    Called after leg renames without re-running full recipe export.
    """
    cid = validate_config_id(config_id)
    course = load_config_course(cid)
    if not course.get("segment_library_applied"):
        return False
    manifest = load_package_segment_manifest(cid)
    chunk_order = _manifest_chunk_order(manifest)
    chunk_by_id: Dict[str, Dict[str, Any]] = {}
    for entry in manifest.get("chunks") or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if leg_id:
            chunk_by_id[leg_id] = entry

    updated = False
    for seg in course.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        leg_id = _leg_id_for_segment(seg, chunk_order)
        entry = chunk_by_id.get(leg_id) if leg_id else None
        if not entry:
            continue
        if leg_id and str(seg.get("chunk_id", "")).strip() != leg_id:
            seg["chunk_id"] = leg_id
            updated = True
        row = leg_row_from_entry(entry)
        start = row["start_label"]
        end = row["end_label"]
        label = row["leg_label"]
        if start != str(seg.get("from_label") or "").strip():
            seg["from_label"] = start
            updated = True
        if end != str(seg.get("to_label") or "").strip():
            seg["to_label"] = end
            updated = True
        if label != str(seg.get("seg_label") or "").strip():
            seg["seg_label"] = label
            updated = True

    if updated:
        save_config_course(cid, course)
    return updated


def sync_leg_location_metadata_from_course(config_id: str) -> bool:
    """
    Push leg-sourced label/placement edits from course.json into the segment library.

    Course tab is master for loc_label and related fields edited there; the manifest
    is updated so Legs tab and subsequent merges stay consistent.
    """
    cid = validate_config_id(config_id)
    course = load_config_course(cid)
    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    chunk_index: Dict[str, int] = {}
    for i, entry in enumerate(chunks):
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if leg_id:
            chunk_index[leg_id] = i

    changed = False
    for loc in course.get("locations") or []:
        if not isinstance(loc, dict) or loc.get("source") != "leg":
            continue
        key = str(loc.get("leg_loc_key") or "").strip()
        if ":" not in key:
            continue
        leg_id, _, idx_s = key.partition(":")
        leg_id = leg_id.strip()
        try:
            idx = int(idx_s)
        except ValueError:
            continue
        chunk_idx = chunk_index.get(leg_id)
        if chunk_idx is None:
            continue
        entry = dict(chunks[chunk_idx])
        locs = _normalize_locations(entry.get("locations"))
        if idx < 0 or idx >= len(locs):
            continue
        leg_payload: Dict[str, Any] = {
            "loc_label": loc.get("loc_label"),
            "loc_type": loc.get("loc_type"),
            "lat": loc.get("lat"),
            "lon": loc.get("lon"),
            "placement": loc.get("placement"),
        }
        for field in _LEG_LOC_PRESERVE_FIELDS:
            if field in leg_payload:
                continue
            if field not in loc:
                continue
            val = loc[field]
            if field == "resources":
                if isinstance(val, dict):
                    leg_payload[field] = val
                continue
            if val not in (None, ""):
                leg_payload[field] = val
        updated = _normalize_locations([leg_payload])
        if not updated:
            continue
        if locs[idx] != updated[0]:
            locs[idx] = updated[0]
            entry["locations"] = locs
            chunks[chunk_idx] = entry
            changed = True

    if changed:
        manifest["chunks"] = chunks
        save_package_segment_manifest(cid, manifest)
    return changed


def reconcile_leg_locations_to_course(config_id: str) -> bool:
    """Rebuild leg-sourced rows in course.json from the segment library manifest."""
    cid = validate_config_id(config_id)
    try:
        manifest = load_package_segment_manifest(cid)
    except FileNotFoundError:
        return False
    if not manifest.get("chunks"):
        return False
    merge_leg_locations_into_course(cid)
    return True


def sync_leg_locations_if_applied(config_id: str) -> bool:
    """Merge leg placements and labels into course.json when recipes have been applied."""
    course = load_config_course(config_id)
    if not course.get("segment_library_applied"):
        return False
    merge_leg_locations_into_course(config_id)
    sync_leg_segment_labels_into_course(config_id)
    return True


def remove_leg_location_from_manifest(config_id: str, leg_loc_key: str) -> bool:
    """
    Remove one leg placement from the library (e.g. after delete on the Course tab).

    Returns True when a manifest row was removed. False when the key is stale
    (already absent from the manifest); callers should reconcile course.json.
    """
    cid = validate_config_id(config_id)
    key = str(leg_loc_key or "").strip()
    if ":" not in key:
        raise ValueError("Invalid leg_loc_key")
    leg_id, _, idx_s = key.partition(":")
    leg_id = leg_id.strip()
    try:
        idx = int(idx_s)
    except ValueError as exc:
        raise ValueError("Invalid leg_loc_key index") from exc

    manifest = load_package_segment_manifest(cid)
    chunks: List[Dict[str, Any]] = list(manifest.get("chunks") or [])
    chunk_idx = _find_chunk_index(chunks, leg_id)
    if chunk_idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")

    entry = dict(chunks[chunk_idx])
    locs = _normalize_locations(entry.get("locations"))
    if idx < 0 or idx >= len(locs):
        return False
    locs.pop(idx)
    entry["locations"] = locs
    chunks[chunk_idx] = entry
    manifest["chunks"] = chunks
    save_package_segment_manifest(cid, manifest)
    return True
