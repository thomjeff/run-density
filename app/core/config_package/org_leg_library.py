"""
Org-level leg library outside config packages (Issue #780).

Legs live under ``{runflow}/org/legs/`` with the same manifest + GPX layout as a
package ``segment_library/``. Packages import copies with freshly allocated ids.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

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

ORG_LEGS_DIRNAME = "legs"
MANIFEST_YAML = "manifest.yaml"


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
