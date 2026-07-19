"""
Org-level leg library outside config packages (Issue #780).

Legs live under ``{runflow}/org/legs/`` with the same manifest + GPX layout as a
package ``segment_library/``. Packages import copies with freshly allocated ids.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.core.config_package.legs import allocate_next_leg_id, leg_row_from_entry
from app.core.config_package.segment_recipes import (
    load_package_segment_manifest,
    package_segment_library_dir,
    save_package_segment_manifest,
)
from app.core.config_package.storage import resolve_config_package_path, validate_config_id
from app.core.course.segment_library import (
    manifest_legs,
    parse_leg_gpx,
    set_manifest_legs,
)
from app.utils.run_id import get_runflow_root

logger = logging.getLogger(__name__)

ORG_LEGS_DIRNAME = "legs"
MANIFEST_YAML = "manifest.yaml"

# Org leg fields whose edits must be reflected in each package's course.json
# (locations/labels re-merge leg placements; metadata re-syncs segments).
_PACKAGE_SYNC_FIELDS = (
    "locations",
    "start_label",
    "end_label",
    "leg_label",
    "seg_label",
    "description",
    "width_m",
    "schema",
    "direction",
    "flow_type",
    "flow_notes",
    "paired_with",
)


def get_org_legs_dir() -> Path:
    return get_runflow_root() / "org" / ORG_LEGS_DIRNAME


def _manifest_path() -> Path:
    return get_org_legs_dir() / MANIFEST_YAML


def save_org_leg_manifest(manifest: Dict[str, Any]) -> Path:
    """Persist org leg library manifest."""
    import yaml

    org_dir = get_org_legs_dir()
    org_dir.mkdir(parents=True, exist_ok=True)
    path = _manifest_path()
    manifest.setdefault("version", 2)
    manifest.setdefault("label", "Org leg library")
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(manifest, fh, sort_keys=False, allow_unicode=True)
    return path


def load_org_leg_manifest() -> Dict[str, Any]:
    path = _manifest_path()
    if not path.is_file():
        return {"version": 2, "label": "Org leg library", "legs": [], "recipes": {}}
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("Invalid org leg manifest")
    data.setdefault("legs", [])
    return data


def _leg_id_sort_key(leg_id: str) -> tuple:
    text = str(leg_id or "").strip()
    if text.isdigit():
        return (0, int(text))
    return (1, text.lower())


def list_org_legs() -> List[Dict[str, Any]]:
    """Summarize org library legs for picker UI."""
    manifest = load_org_leg_manifest()
    lib_dir = get_org_legs_dir()
    rows: List[Dict[str, Any]] = []
    for entry in manifest_legs(manifest) or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if not leg_id:
            continue
        loaded: Dict[str, Any] = {}
        file_name = entry.get("file")
        if file_name:
            gpx_path = lib_dir / str(file_name)
            if gpx_path.is_file():
                try:
                    loaded = parse_leg_gpx(gpx_path)
                    loaded["file"] = gpx_path.name
                except ValueError:
                    pass
        row = leg_row_from_entry(entry, loaded)
        row["org_leg_id"] = leg_id
        rows.append(row)
    rows.sort(key=lambda r: _leg_id_sort_key(str(r.get("id", ""))))
    return rows


def import_org_leg_to_package(config_id: str, org_leg_id: str) -> Dict[str, Any]:
    """
    Copy one org-library leg (GPX + metadata) into a config package.

    The package receives a new system-assigned leg id when the org id is taken.
    """
    from app.core.config_package.segment_recipes import get_package_segment_library_state

    cid = validate_config_id(config_id)
    org_leg_id = str(org_leg_id).strip()
    if not org_leg_id:
        raise ValueError("org_leg_id is required")

    org_manifest = load_org_leg_manifest()
    org_dir = get_org_legs_dir()
    source = None
    for entry in manifest_legs(org_manifest) or []:
        if isinstance(entry, dict) and str(entry.get("id", "")).strip() == org_leg_id:
            source = dict(entry)
            break
    if not source:
        raise ValueError(f"Org leg not found: {org_leg_id}")

    file_name = str(source.get("file") or "").strip()
    if not file_name:
        raise ValueError(f"Org leg {org_leg_id} has no GPX file")
    src_gpx = org_dir / file_name
    if not src_gpx.is_file():
        raise FileNotFoundError(f"Org GPX not found: {file_name}")

    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    lib_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_package_segment_manifest(cid)
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))

    new_id = allocate_next_leg_id(legs)
    label = str(source.get("seg_label") or org_leg_id).strip() or org_leg_id
    dest_name = f"{new_id}_{file_name.split('_', 1)[-1] if '_' in file_name else file_name}"
    if not dest_name.lower().endswith(".gpx"):
        dest_name = f"{new_id}.gpx"
    shutil.copy2(src_gpx, lib_dir / dest_name)

    entry = {
        "id": new_id,
        "file": dest_name,
        "seg_label": label,
        "start_label": str(source.get("start_label") or "").strip(),
        "end_label": str(source.get("end_label") or "").strip(),
        "width_m": source.get("width_m", 3),
        "schema": source.get("schema", "on_course_open"),
        "direction": source.get("direction", "uni"),
        "description": str(source.get("description") or "").strip(),
        "flow_type": source.get("flow_type"),
        "flow_notes": source.get("flow_notes"),
        "locations": source.get("locations") or [],
    }
    entry = {k: v for k, v in entry.items() if v not in (None, "")}
    legs.append(entry)
    set_manifest_legs(manifest, legs)
    save_package_segment_manifest(cid, manifest)
    state = get_package_segment_library_state(cid)
    state["imported_org_leg_id"] = org_leg_id
    state["imported_package_leg_id"] = new_id
    return state


def publish_package_leg_to_org_library(config_id: str, leg_id: str) -> Dict[str, Any]:
    """
    Copy a package leg (GPX + metadata + locations) into the org leg library.

    Returns summary with ``org_leg_id`` assigned in the org manifest.
    """
    from app.core.config_package.legs import _find_leg_index

    cid = validate_config_id(config_id)
    leg_id = str(leg_id).strip()
    if not leg_id:
        raise ValueError("leg_id is required")

    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    idx = _find_leg_index(legs, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    source = dict(legs[idx])
    file_name = str(source.get("file") or "").strip()
    if not file_name:
        raise ValueError(f"Leg {leg_id} has no GPX file")
    src_gpx = lib_dir / file_name
    if not src_gpx.is_file():
        raise FileNotFoundError(f"GPX not found: {file_name}")

    org_manifest = load_org_leg_manifest()
    org_dir = get_org_legs_dir()
    org_dir.mkdir(parents=True, exist_ok=True)
    org_legs: List[Dict[str, Any]] = list(manifest_legs(org_manifest))
    org_id = allocate_next_leg_id(org_legs)

    stem = file_name
    if "_" in stem:
        stem = stem.split("_", 1)[-1]
    dest_name = f"{org_id}_{stem}" if stem.lower().endswith(".gpx") else f"{org_id}.gpx"
    shutil.copy2(src_gpx, org_dir / dest_name)

    entry = {
        "id": org_id,
        "file": dest_name,
        "seg_label": str(source.get("seg_label") or leg_id).strip() or leg_id,
        "start_label": str(source.get("start_label") or "").strip(),
        "end_label": str(source.get("end_label") or "").strip(),
        "width_m": source.get("width_m", 3),
        "schema": source.get("schema", "on_course_open"),
        "direction": source.get("direction", "uni"),
        "description": str(source.get("description") or "").strip(),
        "flow_type": source.get("flow_type"),
        "flow_notes": source.get("flow_notes"),
        "locations": source.get("locations") or [],
    }
    entry = {k: v for k, v in entry.items() if v not in (None, "")}
    org_legs.append(entry)
    set_manifest_legs(org_manifest, org_legs)
    save_org_leg_manifest(org_manifest)
    return {
        "org_leg_id": org_id,
        "package_leg_id": leg_id,
        "file": dest_name,
        "leg_label": entry.get("seg_label"),
        "location_count": len(entry.get("locations") or []),
    }


def create_org_leg(
    gpx_bytes: bytes,
    filename: str,
    *,
    leg_label: str = "",
    start_label: str = "",
    end_label: str = "",
    width_m: float = 3,
    schema: str = "on_course_open",
    direction: str = "uni",
    flow_type: str = "none",
    flow_notes: str = "",
    description: str = "",
    locations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a new leg in the org library from GPX."""
    from app.utils.constants import DEFAULT_FLOW_TYPE
    from app.core.config_package.legs import (
        _LEG_ID_RE,
        _default_endpoint_labels,
        _find_leg_index,
        _normalize_flow_notes,
        _normalize_flow_type,
        _normalize_leg_description,
        _normalize_locations,
        _normalize_segment_direction,
        _normalize_segment_schema,
        _slugify,
        _validate_leg_entry,
    )

    org_dir = get_org_legs_dir()
    org_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    new_id = allocate_next_leg_id(legs)
    if not _LEG_ID_RE.match(new_id):
        raise ValueError("leg_id must be two or three digits (e.g. 01, 12)")
    if _find_leg_index(legs, new_id) >= 0:
        raise ValueError(f"Leg id already exists: {new_id}")

    label = (leg_label or Path(filename).stem.replace("_", " ")).strip() or f"Leg {new_id}"
    safe_name = f"{new_id}_{_slugify(label)}.gpx"
    dest = org_dir / safe_name
    dest.write_bytes(gpx_bytes)
    parsed = parse_leg_gpx(dest)

    s_label = start_label.strip() or _default_endpoint_labels(label, parsed)[0]
    e_label = end_label.strip() or _default_endpoint_labels(label, parsed)[1]
    entry = {
        "id": new_id,
        "file": safe_name,
        "seg_label": label,
        "start_label": s_label,
        "end_label": e_label,
        "width_m": width_m,
        "schema": _normalize_segment_schema(schema),
        "direction": _normalize_segment_direction(direction),
        "flow_type": _normalize_flow_type(flow_type or DEFAULT_FLOW_TYPE),
        "flow_notes": _normalize_flow_notes(flow_notes),
        "description": _normalize_leg_description(
            (description or "").strip() or _normalize_flow_notes(flow_notes)
        ),
        "locations": _normalize_locations(locations),
    }
    _validate_leg_entry(entry)
    legs.append(entry)
    set_manifest_legs(manifest, legs)
    save_org_leg_manifest(manifest)
    return get_org_leg_library_state()


def create_org_leg_from_coordinates(
    coordinates: Sequence[Sequence[float]],
    *,
    leg_label: str = "",
    start_label: str = "",
    end_label: str = "",
    width_m: float = 3,
    schema: str = "on_course_open",
    direction: str = "uni",
    flow_type: str = "none",
    flow_notes: str = "",
    description: str = "",
) -> Dict[str, Any]:
    """
    Create an org library leg from drawn [lon, lat] vertices (Issue #789 Create Leg).

    Builds a GPX track from the coordinates and reuses create_org_leg so the
    drawn leg is indistinguishable from an imported one.
    """
    from app.core.config_package.legs import _normalize_line_coordinates, _slugify
    from app.core.course.export import build_gpx_line_coordinates

    coords = _normalize_line_coordinates(coordinates)
    label = (leg_label or "").strip() or "Drawn leg"
    gpx_content = build_gpx_line_coordinates(coords, track_name=label)
    filename = f"{_slugify(label) or 'drawn-leg'}.gpx"
    return create_org_leg(
        gpx_content.encode("utf-8"),
        filename,
        leg_label=label,
        start_label=start_label,
        end_label=end_label,
        width_m=width_m,
        schema=schema,
        direction=direction,
        flow_type=flow_type,
        flow_notes=flow_notes,
        description=description,
    )


def _copy_leg_label(label: str) -> str:
    """Default label for a duplicated leg."""
    base = (label or "Leg").strip()
    suffix = " (copy)"
    if base.endswith(suffix):
        return base
    return base + suffix


def _reverse_leg_label(label: str) -> str:
    """Default label for a leg duplicated with reversed start/finish."""
    base = (label or "Leg").strip()
    suffix = " (reverse)"
    if base.endswith(suffix):
        return base
    return base + suffix


def _clone_leg_locations(raw: Any) -> List[Dict[str, Any]]:
    """Deep-copy leg manifest locations for a new leg (fresh keys, same pins/metadata)."""
    import copy

    from app.core.config_package.legs import _normalize_locations

    if not isinstance(raw, list):
        return []
    clones: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = copy.deepcopy(item)
        row.pop("leg_loc_key", None)
        row.pop("id", None)
        row.pop("loc_id", None)
        clones.append(row)
    return _normalize_locations(clones)


def copy_org_leg(
    leg_id: str,
    *,
    leg_label: str = "",
    reverse: bool = False,
) -> Dict[str, Any]:
    """
    Duplicate an org library leg: new id + GPX file, copied metadata and locations.

    When ``reverse`` is true, the GPX track runs from the source finish to the source
    start and ``start_label`` / ``end_label`` are swapped on the new leg.

    Does not copy ``paired_with`` (the copy starts unpaired). Use Trim route on the
    copy to shorten geometry while keeping location pins.
    """
    from app.core.config_package.legs import _find_leg_index
    from app.core.course.export import build_gpx_line_coordinates
    from app.core.course.segment_library import parse_leg_gpx

    leg_id = str(leg_id).strip()
    org_dir = get_org_legs_dir()
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    idx = _find_leg_index(legs, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    source = legs[idx]
    file_name = source.get("file")
    if not file_name:
        raise ValueError(f"Leg {leg_id} has no GPX file")
    gpx_path = org_dir / str(file_name)
    if not gpx_path.is_file():
        raise FileNotFoundError(f"GPX not found: {file_name}")

    before_ids = {
        str(entry.get("id") or "").strip()
        for entry in legs
        if isinstance(entry, dict) and str(entry.get("id") or "").strip()
    }
    source_label = str(source.get("seg_label") or "").strip()
    source_start = str(source.get("start_label") or "")
    source_end = str(source.get("end_label") or "")
    if reverse:
        new_label = (leg_label or "").strip() or _reverse_leg_label(source_label)
        parsed = parse_leg_gpx(gpx_path)
        reversed_coords = list(reversed(parsed["coordinates"]))
        gpx_bytes = build_gpx_line_coordinates(
            reversed_coords,
            track_name=new_label,
        ).encode("utf-8")
        start_label = source_end
        end_label = source_start
    else:
        new_label = (leg_label or "").strip() or _copy_leg_label(source_label)
        gpx_bytes = gpx_path.read_bytes()
        start_label = source_start
        end_label = source_end
    source_description = str(source.get("description") or source.get("flow_notes") or "").strip()
    if not source_description:
        source_description = new_label

    state = create_org_leg(
        gpx_bytes,
        gpx_path.name,
        leg_label=new_label,
        start_label=start_label,
        end_label=end_label,
        width_m=float(source.get("width_m") or 3),
        schema=str(source.get("schema") or "on_course_open"),
        direction=str(source.get("direction") or "uni"),
        flow_type=str(source.get("flow_type") or "none"),
        flow_notes=str(source.get("flow_notes") or ""),
        description=source_description,
        locations=_clone_leg_locations(source.get("locations")),
    )

    copied_leg_id = ""
    for entry in state.get("legs") or []:
        if not isinstance(entry, dict):
            continue
        lid = str(entry.get("id") or "").strip()
        if lid and lid not in before_ids:
            copied_leg_id = lid
            break
    if not copied_leg_id:
        raise ValueError("Copy succeeded but new leg id could not be determined")

    return {
        **state,
        "copied_leg_id": copied_leg_id,
        "source_leg_id": leg_id,
        "reversed": bool(reverse),
    }


def copy_org_leg_locations(
    target_leg_id: str,
    source_leg_id: str,
    *,
    replace: bool = True,
) -> Dict[str, Any]:
    """
    Copy location pins from one org leg onto another.

    Uses the same clone/normalize path as ``copy_org_leg`` (fresh keys, same
    lat/lon and resource counts). Typical use: a reversed corridor pair where
    the reverse leg was created before locations were placed on the source leg.
    """
    from app.core.config_package.legs import _find_leg_index, _normalize_locations

    target_leg_id = str(target_leg_id).strip()
    source_leg_id = str(source_leg_id).strip()
    if not target_leg_id or not source_leg_id:
        raise ValueError("Source and target leg ids are required")
    if target_leg_id == source_leg_id:
        raise ValueError("Source and target leg must differ")

    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    target_idx = _find_leg_index(legs, target_leg_id)
    source_idx = _find_leg_index(legs, source_leg_id)
    if target_idx < 0:
        raise ValueError(f"Leg not found: {target_leg_id}")
    if source_idx < 0:
        raise ValueError(f"Leg not found: {source_leg_id}")

    cloned = _clone_leg_locations(legs[source_idx].get("locations"))
    if not cloned:
        raise ValueError(f"Leg {source_leg_id} has no locations to copy")

    entry = dict(legs[target_idx])
    if replace:
        entry["locations"] = cloned
    else:
        existing = entry.get("locations") or []
        entry["locations"] = _normalize_locations(list(existing) + cloned)

    legs[target_idx] = entry
    set_manifest_legs(manifest, legs)
    save_org_leg_manifest(manifest)
    sync_org_leg_changes_into_packages()

    return {
        **get_org_leg_library_state(),
        "target_leg_id": target_leg_id,
        "source_leg_id": source_leg_id,
        "location_count": len(cloned),
        "replaced": bool(replace),
    }


def get_org_leg_library_state() -> Dict[str, Any]:
    """API state for org leg library management UI."""
    legs = list_org_legs()
    return {
        "leg_source": "org",
        "library_dir": str(get_org_legs_dir()),
        "has_library": bool(legs),
        "legs": legs,
    }


def import_gpx_files_to_org_library(uploads: Sequence[tuple]) -> Dict[str, Any]:
    """Import GPX (+ optional leg export JSON) into the org leg library."""
    from app.core.config_package.legs import (
        apply_leg_exports_to_manifest,
        leg_id_from_export_filename,
        parse_leg_export_json_bytes,
    )
    from app.core.config_package.segment_recipes import sync_manifest_legs_from_gpx

    org_dir = get_org_legs_dir()
    org_dir.mkdir(parents=True, exist_ok=True)
    saved_gpx: List[str] = []
    exports_by_leg_id: Dict[str, Dict[str, Any]] = {}
    exports_by_gpx_file: Dict[str, Dict[str, Any]] = {}
    for name, data in uploads:
        safe = Path(name).name
        lower = safe.lower()
        if lower.endswith(".json"):
            leg_export = parse_leg_export_json_bytes(data)
            if not leg_export:
                continue
            leg_id = (
                str(leg_export.get("id") or "").strip()
                or leg_id_from_export_filename(safe)
                or ""
            )
            if leg_id:
                exports_by_leg_id[leg_id] = leg_export
            gpx_file = str(leg_export.get("gpx_file") or "").strip()
            if gpx_file:
                exports_by_gpx_file[gpx_file] = leg_export
            (org_dir / safe).write_bytes(data)
            continue
        if not lower.endswith(".gpx"):
            continue
        (org_dir / safe).write_bytes(data)
        saved_gpx.append(safe)
    if not saved_gpx:
        raise ValueError("No .gpx files uploaded")
    manifest = load_org_leg_manifest()
    manifest = sync_manifest_legs_from_gpx(org_dir, manifest)
    manifest = apply_leg_exports_to_manifest(
        manifest, exports_by_leg_id, exports_by_gpx_file=exports_by_gpx_file
    )
    save_org_leg_manifest(manifest)
    return get_org_leg_library_state()


def update_org_leg(
    leg_id: str,
    fields: Dict[str, Any],
    *,
    gpx_bytes: Optional[bytes] = None,
    gpx_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Update org leg metadata, locations, and optional GPX."""
    from app.core.config_package.legs import (
        _default_endpoint_labels,
        _find_leg_index,
        _normalize_flow_notes,
        _normalize_flow_type,
        _normalize_leg_description,
        _normalize_locations,
        _normalize_segment_direction,
        _normalize_segment_schema,
        _slugify,
        apply_leg_pairing,
    )

    leg_id = str(leg_id).strip()
    org_dir = get_org_legs_dir()
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    idx = _find_leg_index(legs, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")

    entry = dict(legs[idx])
    if "leg_label" in fields or "seg_label" in fields:
        entry["seg_label"] = str(
            fields.get("leg_label") or fields.get("seg_label") or entry.get("seg_label") or ""
        ).strip()
    for key in ("start_label", "end_label", "width_m"):
        if key in fields:
            entry[key] = fields[key]
    if "description" in fields:
        entry["description"] = _normalize_leg_description(fields.get("description"))
    if "schema" in fields:
        entry["schema"] = _normalize_segment_schema(fields["schema"])
    if "direction" in fields:
        entry["direction"] = _normalize_segment_direction(fields["direction"])
    if "flow_type" in fields:
        entry["flow_type"] = _normalize_flow_type(fields["flow_type"])
    if "flow_notes" in fields:
        entry["flow_notes"] = _normalize_flow_notes(fields.get("flow_notes"))
    if "locations" in fields:
        entry["locations"] = _normalize_locations(fields.get("locations"))

    if gpx_bytes:
        if gpx_filename:
            file_name = Path(str(gpx_filename)).name
        else:
            file_name = entry.get("file") or f"{leg_id}_{_slugify(entry.get('seg_label', ''))}.gpx"
        dest = org_dir / Path(file_name).name
        dest.write_bytes(gpx_bytes)
        entry["file"] = dest.name
        parsed = parse_leg_gpx(dest)
        if not entry.get("start_label"):
            entry["start_label"] = _default_endpoint_labels(entry.get("seg_label", ""), parsed)[0]
        if not entry.get("end_label"):
            entry["end_label"] = _default_endpoint_labels(entry.get("seg_label", ""), parsed)[1]

    legs[idx] = entry
    if "paired_with" in fields:
        apply_leg_pairing(legs, leg_id, fields.get("paired_with"))
    set_manifest_legs(manifest, legs)
    save_org_leg_manifest(manifest)
    if any(key in fields for key in _PACKAGE_SYNC_FIELDS):
        sync_org_leg_changes_into_packages()
    return get_org_leg_library_state()


def update_org_leg_geometry(
    leg_id: str,
    coordinates: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    """Replace org leg GPX track from edited [lon, lat] vertices (trim/reshape)."""
    from app.core.config_package.legs import _find_leg_index, _normalize_line_coordinates
    from app.core.course.export import build_gpx_line_coordinates

    coords = _normalize_line_coordinates(coordinates)
    leg_id = str(leg_id).strip()
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    idx = _find_leg_index(legs, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    entry = legs[idx]
    label = (entry.get("seg_label") or leg_id).strip() or leg_id
    gpx_content = build_gpx_line_coordinates(coords, track_name=label)
    return update_org_leg(
        leg_id,
        {},
        gpx_bytes=gpx_content.encode("utf-8"),
        gpx_filename=entry.get("file") or f"{leg_id}.gpx",
    )


def sync_org_leg_changes_into_packages() -> None:
    """
    Propagate org leg edits into course.json for org-sourced packages.

    The Legs tab saves to the org manifest only; without this, a moved
    location pin (or label/metadata change) stays stale in each package's
    combined course until the next recipe apply. Packages without applied
    recipes are skipped by ``sync_leg_locations_if_applied``.
    """
    from app.core.config_package.leg_library_resolver import (
        LEG_SOURCE_ORG,
        effective_leg_source,
    )
    from app.core.config_package.legs import sync_leg_locations_if_applied
    from app.core.config_package.storage import (
        COURSE_WORKSPACE_NAME,
        list_config_packages,
        resolve_config_package_path,
    )

    for pkg in list_config_packages():
        cid = str(pkg.get("config_id") or "").strip()
        if not cid:
            continue
        try:
            pkg_manifest = load_package_segment_manifest(cid)
        except (FileNotFoundError, ValueError):
            continue
        if effective_leg_source(pkg_manifest) != LEG_SOURCE_ORG:
            continue
        try:
            course_path = resolve_config_package_path(cid) / COURSE_WORKSPACE_NAME
        except ValueError:
            continue
        if not course_path.is_file():
            continue
        try:
            sync_leg_locations_if_applied(cid)
        except Exception:
            logger.warning(
                "Failed to sync org leg change into package %s", cid, exc_info=True
            )


def delete_org_leg(leg_id: str) -> Dict[str, Any]:
    """Remove one leg from the org library."""
    from app.core.config_package.legs import _find_leg_index

    leg_id = str(leg_id).strip()
    org_dir = get_org_legs_dir()
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    idx = _find_leg_index(legs, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    entry = legs.pop(idx)
    file_name = entry.get("file")
    if file_name:
        gpx_path = org_dir / str(file_name)
        if gpx_path.is_file():
            gpx_path.unlink()
    set_manifest_legs(manifest, legs)
    save_org_leg_manifest(manifest)
    return get_org_leg_library_state()


def _org_leg_line_geojson_from_entry(
    org_dir: Path,
    leg_id: str,
    entry: Dict[str, Any],
) -> Dict[str, Any]:
    """Build GeoJSON for one org leg from a manifest entry (no manifest reload)."""
    leg_id = str(leg_id).strip()
    file_name = entry.get("file")
    if not file_name:
        raise ValueError(f"Leg {leg_id} has no GPX file")
    gpx_path = org_dir / str(file_name)
    if not gpx_path.is_file():
        raise FileNotFoundError(f"GPX not found: {file_name}")
    parsed = parse_leg_gpx(gpx_path)
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


def get_all_org_leg_line_geojson() -> List[Dict[str, Any]]:
    """GeoJSON features for every org leg (single manifest read)."""
    org_dir = get_org_legs_dir()
    manifest = load_org_leg_manifest()
    features: List[Dict[str, Any]] = []
    for entry in manifest_legs(manifest):
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id") or "").strip()
        if not leg_id:
            continue
        try:
            features.append(_org_leg_line_geojson_from_entry(org_dir, leg_id, entry))
        except (FileNotFoundError, ValueError):
            continue
    return features


def get_org_leg_line_geojson(leg_id: str) -> Dict[str, Any]:
    """GeoJSON LineString for one org leg."""
    leg_id = str(leg_id).strip()
    org_dir = get_org_legs_dir()
    manifest = load_org_leg_manifest()
    legs: List[Dict[str, Any]] = list(manifest_legs(manifest))
    from app.core.config_package.legs import _find_leg_index

    idx = _find_leg_index(legs, leg_id)
    if idx < 0:
        raise ValueError(f"Leg not found: {leg_id}")
    return _org_leg_line_geojson_from_entry(org_dir, leg_id, legs[idx])
