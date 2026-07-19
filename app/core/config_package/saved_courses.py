"""
Global named courses (org library) and package course assignment.

Courses live under ``runflow/org/courses/{course_id}/`` with snapshotted legs
and frozen analysis exports. Packages assign one course per distance and can
build a multi-distance race export at the package root for v2 analyze.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from app.core.config_package.location_ids import allocate_location_id, assign_unique_location_ids
from app.core.config_package.location_keys import ensure_location_key
from app.core.config_package.legs import (
    _event_flags_for_leg,
    _normalize_locations,
    _seg_ids_for_leg,
    leg_loc_key,
    merge_leg_locations_into_course,
    refresh_course_location_seg_ids,
)
from app.core.config_package.org_leg_library import get_org_legs_dir, load_org_leg_manifest
from app.core.config_package.storage import (
    list_config_packages,
    load_config_course,
    load_config_manifest,
    package_readiness,
    resolve_config_package_path,
    save_config_course,
    save_config_manifest,
    validate_config_id,
)
from app.utils.run_id import get_runflow_root
from app.core.course.export import build_locations_csv
from app.core.course.flow_csv import validate_flow_csv_text
from app.core.course.segment_library import (
    build_event_gpx_content,
    export_library_to_course,
    load_leg_library,
    load_manifest,
    manifest_legs,
)
from app.utils.constants import COURSE_EVENT_IDS, ON_COURSE_LOCATION_TYPES

logger = logging.getLogger(__name__)

ORG_COURSES_DIRNAME = "courses"
SAVED_COURSE_META = "saved_course.json"
ORG_COURSES_INDEX = "manifest.yaml"
_COURSE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
DEFAULT_RESOURCE_CODES = ("fpf", "yssr", "awp", "vol")


def get_org_courses_dir() -> Path:
    return get_runflow_root() / "org" / ORG_COURSES_DIRNAME


def allocate_next_course_id() -> str:
    """Next numeric course id (01, 02, …), like org leg ids."""
    max_n = 0
    index = _load_index()
    for raw in index.get("courses") or []:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("id") or "").strip()
        if cid.isdigit():
            max_n = max(max_n, int(cid))
    org_dir = get_org_courses_dir()
    if org_dir.is_dir():
        for child in org_dir.iterdir():
            if child.is_dir() and child.name.isdigit():
                max_n = max(max_n, int(child.name))
    return f"{max_n + 1:02d}"


def _course_id_sort_key(row: Dict[str, Any]) -> tuple:
    cid = str(row.get("id") or "").strip()
    if cid.isdigit():
        return (0, int(cid))
    return (1, cid.lower())


def normalize_course_id(raw: str, *, distance: str = "", name: str = "") -> str:
    """Normalize explicit slug, numeric id, or derive from distance + name."""
    text = str(raw or "").strip().lower()
    if text.isdigit():
        return f"{int(text):02d}"
    text = re.sub(r"[^a-z0-9-]+", "-", text).strip("-")
    if text and _COURSE_ID_RE.match(text):
        return text
    dist = str(distance or "").strip().lower()
    name_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") if name else ""
    if dist and name_slug.startswith(f"{dist}-"):
        derived = name_slug
    elif dist and name_slug:
        derived = f"{dist}-{name_slug}"
    else:
        derived = dist or name_slug
    derived = re.sub(r"-+", "-", derived).strip("-")
    if not derived or not _COURSE_ID_RE.match(derived):
        raise ValueError("course_id must be lowercase letters, digits, and hyphens")
    return derived[:63]


def _course_dir(course_id: str) -> Path:
    return get_org_courses_dir() / course_id


def _index_path() -> Path:
    return get_org_courses_dir() / ORG_COURSES_INDEX


def _load_index() -> Dict[str, Any]:
    path = _index_path()
    if not path.is_file():
        return {"version": 1, "courses": []}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        return {"version": 1, "courses": []}
    data.setdefault("version", 1)
    data.setdefault("courses", [])
    return data


def _save_index(data: Dict[str, Any]) -> None:
    org_dir = get_org_courses_dir()
    org_dir.mkdir(parents=True, exist_ok=True)
    with open(_index_path(), "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def _course_row_from_disk(course_id: str, index_entry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    row = dict(index_entry or {})
    row["id"] = course_id
    course_path = _course_dir(course_id)
    row["exists"] = course_path.is_dir()
    row["analysis_data_dir"] = f"runflow/org/courses/{course_id}"
    distance = str(row.get("distance") or "").strip().lower()
    meta_path = course_path / SAVED_COURSE_META
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for key in ("name", "distance", "recipe", "saved_at", "length_km", "stitch_warnings"):
                if meta.get(key) is not None and row.get(key) is None:
                    row[key] = meta.get(key)
            distance = str(row.get("distance") or distance).strip().lower()
        except (json.JSONDecodeError, OSError):
            pass
    row["distance"] = distance
    row["analyze_ready"] = bool(
        course_path.is_dir()
        and (course_path / "segments.csv").is_file()
        and (course_path / "flow.csv").is_file()
        and distance
        and (course_path / f"{distance}.gpx").is_file()
    )
    return row


def list_org_courses(*, distance: Optional[str] = None) -> List[Dict[str, Any]]:
    """List global org courses."""
    index = _load_index()
    want = str(distance or "").strip().lower()
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for raw in index.get("courses") or []:
        if not isinstance(raw, dict):
            continue
        course_id = str(raw.get("id") or "").strip()
        if not course_id or course_id in seen:
            continue
        seen.add(course_id)
        row = _course_row_from_disk(course_id, raw)
        if want and str(row.get("distance") or "").lower() != want:
            continue
        out.append(row)
    # Also discover folders not yet in index
    org_dir = get_org_courses_dir()
    if org_dir.is_dir():
        for child in sorted(org_dir.iterdir()):
            if not child.is_dir() or child.name in seen:
                continue
            if not (child / SAVED_COURSE_META).is_file():
                continue
            row = _course_row_from_disk(child.name)
            if want and str(row.get("distance") or "").lower() != want:
                continue
            out.append(row)
    out.sort(
        key=lambda r: (
            _course_id_sort_key(r),
            str(r.get("distance") or ""),
            str(r.get("name") or r.get("id") or ""),
        )
    )
    return out


def get_org_course(course_id: str) -> Dict[str, Any]:
    slug = normalize_course_id(course_id)
    course_path = _course_dir(slug)
    if not course_path.is_dir():
        raise FileNotFoundError(f"Course not found: {slug}")
    index = _load_index()
    entry = next(
        (
            x
            for x in (index.get("courses") or [])
            if isinstance(x, dict) and str(x.get("id", "")).strip() == slug
        ),
        None,
    )
    return _course_row_from_disk(slug, entry)


def get_org_course_route_preview(course_id: str) -> Dict[str, Any]:
    """Stitched route coordinates for a saved org course (map preview)."""
    from app.core.course.segment_library import concat_recipe_coordinates

    slug = normalize_course_id(course_id)
    course_dir = _course_dir(slug)
    if not course_dir.is_dir():
        raise FileNotFoundError(f"Course not found: {slug}")

    meta_path = course_dir / SAVED_COURSE_META
    if not meta_path.is_file():
        raise ValueError(f"Course metadata missing for {slug}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    recipe = [str(x).strip() for x in (meta.get("recipe") or []) if str(x).strip()]
    if not recipe:
        raise ValueError(f"Course {slug} has an empty recipe")

    distance = str(meta.get("distance") or "").strip().lower()
    lib_dir = course_dir / "leg_library"
    manifest_path = lib_dir / "manifest.yaml"
    if not manifest_path.is_file():
        raise ValueError(f"Course {slug} has no leg snapshot")
    manifest = load_manifest(manifest_path)
    legs_by_id = load_leg_library(lib_dir, manifest)
    coords = concat_recipe_coordinates(recipe, legs_by_id)
    if len(coords) < 2:
        raise ValueError(f"Course {slug} recipe has insufficient route points")

    length_km = meta.get("length_km")
    if length_km is None:
        length_km = round(
            sum(float(legs_by_id[c]["length_km"]) for c in recipe if c in legs_by_id),
            2,
        )

    recipe_legs: List[Dict[str, Any]] = []
    for order, leg_id in enumerate(recipe, start=1):
        leg = legs_by_id.get(leg_id) or {}
        recipe_legs.append(
            {
                "order": order,
                "id": leg_id,
                "leg_label": str(leg.get("seg_label") or leg.get("leg_label") or "").strip(),
                "length_km": leg.get("length_km"),
                "start_label": str(leg.get("start_label") or "").strip(),
                "end_label": str(leg.get("end_label") or "").strip(),
            }
        )

    locations: List[Dict[str, Any]] = []
    course_json_path = course_dir / "course.json"
    if course_json_path.is_file():
        try:
            course_data = json.loads(course_json_path.read_text(encoding="utf-8"))
            for loc in course_data.get("locations") or []:
                if not isinstance(loc, dict):
                    continue
                lat = loc.get("lat")
                lon = loc.get("lon")
                if lat is None or lon is None:
                    continue
                locations.append(
                    {
                        "loc_id": loc.get("loc_id"),
                        "loc_label": str(loc.get("loc_label") or "").strip(),
                        "loc_type": str(loc.get("loc_type") or "course").strip(),
                        "lat": float(lat),
                        "lon": float(lon),
                        "zone": loc.get("zone"),
                        "resources": loc.get("resources") if isinstance(loc.get("resources"), dict) else {},
                    }
                )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    return {
        "course_id": slug,
        "name": meta.get("name") or slug,
        "distance": distance,
        "recipe": recipe,
        "recipe_legs": recipe_legs,
        "locations": locations,
        "coordinates": coords,
        "length_km": length_km,
        "leg_count": len(recipe),
    }


def _expand_recipe_legs_with_pairs(
    org_manifest: Dict[str, Any],
    leg_ids: Sequence[str],
) -> set[str]:
    """Recipe legs plus corridor partners (for metadata and pairing validation)."""
    by_id: Dict[str, Dict[str, Any]] = {
        str(entry.get("id", "")).strip(): entry
        for entry in (manifest_legs(org_manifest) or [])
        if isinstance(entry, dict) and str(entry.get("id", "")).strip()
    }
    wanted = {str(x).strip() for x in leg_ids if str(x).strip()}
    pending = list(wanted)
    while pending:
        leg_id = pending.pop()
        entry = by_id.get(leg_id)
        if not entry:
            continue
        mate_id = str(entry.get("paired_with") or "").strip()
        if mate_id and mate_id in by_id and mate_id not in wanted:
            wanted.add(mate_id)
            pending.append(mate_id)
    return wanted


def _copy_org_legs_snapshot(
    target_lib_dir: Path,
    leg_ids: Sequence[str],
) -> Dict[str, Any]:
    """Copy org legs referenced in recipe (and paired partners) into leg_library/."""
    org_dir = get_org_legs_dir()
    org_manifest = load_org_leg_manifest()
    wanted = _expand_recipe_legs_with_pairs(org_manifest, leg_ids)
    if not wanted:
        raise ValueError("Recipe must include at least one leg")

    copied: List[Dict[str, Any]] = []
    missing: List[str] = []
    for entry in manifest_legs(org_manifest) or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if leg_id not in wanted:
            continue
        file_name = str(entry.get("file") or "").strip()
        if not file_name:
            missing.append(leg_id)
            continue
        src_gpx = org_dir / file_name
        if not src_gpx.is_file():
            missing.append(leg_id)
            continue
        dest_name = (
            f"{leg_id}_{Path(file_name).name}"
            if not file_name.startswith(f"{leg_id}")
            else file_name
        )
        target_lib_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_gpx, target_lib_dir / dest_name)
        snap = dict(entry)
        snap["file"] = dest_name
        copied.append(snap)
        wanted.discard(leg_id)

    if missing or wanted:
        unknown = sorted(set(missing) | wanted)
        raise ValueError(f"Org legs not found or missing GPX: {', '.join(unknown)}")

    manifest: Dict[str, Any] = {
        "version": 2,
        "label": "Saved course leg snapshot",
        "legs": copied,
        "recipes": {},
    }
    with open(target_lib_dir / "manifest.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(manifest, fh, sort_keys=False, allow_unicode=True)
    return manifest


def _build_snapshot_locations(
    segments: Sequence[Dict[str, Any]],
    manifest: Dict[str, Any],
    distance: str,
) -> List[Dict[str, Any]]:
    """Build location rows from snapshotted leg placements for one event distance."""
    distance = distance.strip().lower()
    event_ids = [distance]
    locations: List[Dict[str, Any]] = []
    used_ids: set[int] = set()
    used_loc_keys: set[str] = set()

    for entry in manifest_legs(manifest) or []:
        if not isinstance(entry, dict):
            continue
        leg_id = str(entry.get("id", "")).strip()
        if not leg_id:
            continue
        seg_id = _seg_ids_for_leg(segments, leg_id)
        event_flags = _event_flags_for_leg(segments, leg_id, event_ids)
        for i, loc in enumerate(
            _normalize_locations(entry.get("locations"), used_location_keys=used_loc_keys)
        ):
            key = leg_loc_key(leg_id, i)
            on_course = loc["loc_type"] in ON_COURSE_LOCATION_TYPES
            row: Dict[str, Any] = {
                "id": allocate_location_id(used_ids),
                "loc_label": loc["loc_label"],
                "loc_type": loc["loc_type"],
                "lat": loc["lat"],
                "lon": loc["lon"],
                "leg_id": leg_id,
                "leg_loc_key": key,
                "placement": loc.get("placement", "along"),
                "source": "leg",
                "seg_id": seg_id if on_course else "",
                "buffer": loc.get("buffer", 0),
                "interval": loc.get("interval", 5),
                "zone": loc.get("zone", ""),
                "equipment": loc.get("equipment", ""),
                "contact": loc.get("contact", ""),
                "notes": loc.get("notes", ""),
                "day": loc.get("day", ""),
                "onepage": loc.get("onepage", ""),
            }
            if isinstance(loc.get("resources"), dict):
                row["resources"] = loc["resources"]
            ensure_location_key(row, used_loc_keys)
            for ev in COURSE_EVENT_IDS:
                row[ev] = event_flags.get(ev, "n") if ev == distance else "n"
            locations.append(row)

    assign_unique_location_ids(locations)
    return locations


def save_org_course(
    *,
    name: str,
    distance: str,
    recipe: Sequence[str],
    course_id: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Snapshot org legs for ``recipe``, build exports for ``distance``, save under
    ``runflow/org/courses/{course_id}/``.
    """
    name = str(name or "").strip()
    if not name:
        raise ValueError("name is required")
    distance = str(distance or "").strip().lower()
    if not distance:
        raise ValueError("distance is required")
    if distance not in COURSE_EVENT_IDS:
        raise ValueError(f"Unsupported distance: {distance}")

    recipe_list = [str(x).strip() for x in recipe if str(x).strip()]
    if len(recipe_list) < 1:
        raise ValueError("Recipe must include at least one leg")

    if course_id:
        slug = normalize_course_id(course_id, distance=distance, name=name)
    else:
        slug = allocate_next_course_id()
    course_dir = _course_dir(slug)
    if course_dir.exists() and not overwrite:
        raise ValueError(
            f"Course '{slug}' already exists; pass overwrite=true to replace"
        )
    if course_dir.exists():
        shutil.rmtree(course_dir)
    course_dir.mkdir(parents=True, exist_ok=True)

    leg_lib_dir = course_dir / "leg_library"
    snapshot_manifest = _copy_org_legs_snapshot(leg_lib_dir, recipe_list)
    apply_manifest = dict(snapshot_manifest)
    apply_manifest["recipes"] = {distance: recipe_list}
    apply_manifest["label"] = name

    bundle = export_library_to_course(
        leg_lib_dir, manifest=apply_manifest, event_ids=[distance]
    )
    segments = bundle["segments"]
    if not segments:
        shutil.rmtree(course_dir, ignore_errors=True)
        raise ValueError("Recipe produced no segments; check leg GPX and order")

    flow_csv = bundle["flow_csv"]
    flow_validation = validate_flow_csv_text(flow_csv)
    if not flow_validation.ok:
        shutil.rmtree(course_dir, ignore_errors=True)
        raise ValueError(
            "flow.csv validation failed: " + "; ".join(flow_validation.errors)
        )

    resource_codes = list(DEFAULT_RESOURCE_CODES)
    course: Dict[str, Any] = {
        "name": name,
        "saved_course_id": slug,
        "distance": distance,
        "segments": segments,
        "segment_library_applied": True,
    }
    course["locations"] = _build_snapshot_locations(segments, apply_manifest, distance)

    legs_by_id = load_leg_library(leg_lib_dir, apply_manifest)
    gpx_content = build_event_gpx_content(
        distance,
        apply_manifest,
        legs_by_id,
        course_name=name,
    )

    (course_dir / "course.json").write_text(
        json.dumps(course, indent=2) + "\n", encoding="utf-8"
    )
    (course_dir / "segments.csv").write_text(bundle["segments_csv"], encoding="utf-8")
    (course_dir / "flow.csv").write_text(flow_csv, encoding="utf-8")
    (course_dir / "locations.csv").write_text(
        build_locations_csv(course, resource_codes=resource_codes),
        encoding="utf-8",
    )
    (course_dir / f"{distance}.gpx").write_text(gpx_content, encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "id": slug,
        "name": name,
        "distance": distance,
        "recipe": recipe_list,
        "saved_at": now,
        "leg_snapshot": True,
        "analysis_data_dir": f"runflow/org/courses/{slug}",
        "stitch_warnings": bundle.get("stitch_warnings") or [],
        "length_km": (bundle.get("recipe_lengths_km") or {}).get(distance),
    }
    (course_dir / SAVED_COURSE_META).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    index = _load_index()
    courses = [
        x
        for x in (index.get("courses") or [])
        if not (isinstance(x, dict) and str(x.get("id", "")).strip() == slug)
    ]
    courses.append(
        {
            "id": slug,
            "name": name,
            "distance": distance,
            "recipe": recipe_list,
            "saved_at": now,
            "length_km": meta.get("length_km"),
        }
    )
    index["courses"] = courses
    _save_index(index)

    return {
        "ok": True,
        "saved_course": meta,
        "courses": list_org_courses(),
        "stitch_warnings": meta["stitch_warnings"],
    }


def update_org_course(
    course_id: str,
    *,
    recipe: Sequence[str],
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """Replace a saved course recipe and rebuild frozen exports (same course id)."""
    slug = normalize_course_id(course_id)
    existing = get_org_course(slug)
    meta_path = _course_dir(slug) / SAVED_COURSE_META
    meta: Dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}
    use_name = str(name or existing.get("name") or meta.get("name") or slug).strip()
    if not use_name:
        raise ValueError("name is required")
    distance = str(existing.get("distance") or meta.get("distance") or "").strip().lower()
    if not distance:
        raise ValueError(f"Course {slug} has no distance")
    return save_org_course(
        name=use_name,
        distance=distance,
        recipe=recipe,
        course_id=slug,
        overwrite=True,
    )


def delete_org_course(course_id: str) -> Dict[str, Any]:
    """Remove a global course directory and index entry."""
    slug = normalize_course_id(course_id)
    course_dir = _course_dir(slug)
    if course_dir.is_dir():
        shutil.rmtree(course_dir)

    index = _load_index()
    index["courses"] = [
        x
        for x in (index.get("courses") or [])
        if not (isinstance(x, dict) and str(x.get("id", "")).strip() == slug)
    ]
    _save_index(index)
    return {"ok": True, "deleted": slug, "courses": list_org_courses()}


def _update_package_course_id_references(old_id: str, new_id: str) -> int:
    """Rewrite assigned_courses entries that still point at ``old_id``."""
    updated = 0
    for pkg in list_config_packages():
        config_id = str(pkg.get("config_id") or "").strip()
        if not config_id:
            continue
        try:
            package_path = resolve_config_package_path(config_id)
            manifest = load_config_manifest(config_id)
        except (FileNotFoundError, ValueError):
            continue
        assigned = manifest.get("assigned_courses") or {}
        if not isinstance(assigned, dict):
            continue
        changed = False
        for distance, course_id in list(assigned.items()):
            if str(course_id or "").strip() == old_id:
                assigned[distance] = new_id
                changed = True
        if changed:
            manifest["assigned_courses"] = assigned
            save_config_manifest(package_path, manifest)
            updated += 1
    return updated


def rename_org_course(old_id: str, new_id: str) -> Dict[str, Any]:
    """Rename a course directory, metadata, index entry, and package assignments."""
    old_slug = normalize_course_id(old_id)
    new_slug = normalize_course_id(new_id)
    if old_slug == new_slug:
        return {
            "ok": True,
            "old_id": old_slug,
            "new_id": new_slug,
            "courses": list_org_courses(),
        }

    old_dir = _course_dir(old_slug)
    new_dir = _course_dir(new_slug)
    if not old_dir.is_dir():
        raise FileNotFoundError(f"Course not found: {old_slug}")
    if new_dir.exists():
        raise ValueError(f"Course id already in use: {new_slug}")

    meta_path = old_dir / SAVED_COURSE_META
    meta: Dict[str, Any] = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}

    old_dir.rename(new_dir)

    meta["id"] = new_slug
    meta["analysis_data_dir"] = f"runflow/org/courses/{new_slug}"
    (new_dir / SAVED_COURSE_META).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    course_json_path = new_dir / "course.json"
    if course_json_path.is_file():
        try:
            course = json.loads(course_json_path.read_text(encoding="utf-8"))
            if isinstance(course, dict):
                course["saved_course_id"] = new_slug
                course_json_path.write_text(
                    json.dumps(course, indent=2) + "\n", encoding="utf-8"
                )
        except (json.JSONDecodeError, OSError):
            pass

    index = _load_index()
    for entry in index.get("courses") or []:
        if isinstance(entry, dict) and str(entry.get("id", "")).strip() == old_slug:
            entry["id"] = new_slug
    _save_index(index)

    packages_updated = _update_package_course_id_references(old_slug, new_slug)

    return {
        "ok": True,
        "old_id": old_slug,
        "new_id": new_slug,
        "packages_updated": packages_updated,
        "courses": list_org_courses(),
    }


def renumber_org_courses_to_numeric() -> Dict[str, Any]:
    """
    Assign numeric ids (01, 02, …) to legacy slug course folders.

    Already-numeric courses are left unchanged. Legacy courses are renumbered in
    ``saved_at`` order (then name) so creation order is preserved.
    """
    courses = list_org_courses()
    legacy = [c for c in courses if not str(c.get("id") or "").strip().isdigit()]
    if not legacy:
        return {"ok": True, "renamed": [], "courses": courses}

    legacy.sort(
        key=lambda r: (
            str(r.get("saved_at") or ""),
            str(r.get("distance") or ""),
            str(r.get("name") or r.get("id") or ""),
        )
    )

    max_n = 0
    for course in courses:
        cid = str(course.get("id") or "").strip()
        if cid.isdigit():
            max_n = max(max_n, int(cid))

    next_n = max_n + 1 if max_n else 1
    renamed: List[Dict[str, str]] = []
    for course in legacy:
        new_id = f"{next_n:02d}"
        next_n += 1
        result = rename_org_course(str(course["id"]), new_id)
        renamed.append({"old_id": result["old_id"], "new_id": result["new_id"]})

    return {"ok": True, "renamed": renamed, "courses": list_org_courses()}


# --- Package assignment (race day) ---


def get_package_course_assignments(config_id: str) -> Dict[str, Any]:
    """Return assigned_courses map and resolved course summaries."""
    cid = validate_config_id(config_id)
    manifest = load_config_manifest(cid)
    assigned = manifest.get("assigned_courses") or {}
    if not isinstance(assigned, dict):
        assigned = {}
    clean = {
        str(k).strip().lower(): str(v).strip()
        for k, v in assigned.items()
        if str(k).strip() and str(v).strip()
    }
    resolved: Dict[str, Any] = {}
    for distance, course_id in clean.items():
        try:
            resolved[distance] = get_org_course(course_id)
        except (FileNotFoundError, ValueError) as exc:
            resolved[distance] = {
                "id": course_id,
                "distance": distance,
                "missing": True,
                "detail": str(exc),
            }
    events = manifest.get("package_events") or []
    return {
        "config_id": cid,
        "package_events": events,
        "assigned_courses": clean,
        "resolved": resolved,
    }


def set_package_course_assignments(
    config_id: str,
    assigned_courses: Dict[str, str],
) -> Dict[str, Any]:
    """Persist assigned_courses on package config.json."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    manifest = load_config_manifest(cid)
    events = [
        str(e).strip().lower()
        for e in (manifest.get("package_events") or [])
        if str(e).strip()
    ]
    clean: Dict[str, str] = {}
    for distance, course_id in (assigned_courses or {}).items():
        dist = str(distance or "").strip().lower()
        cid_course = str(course_id or "").strip()
        if not dist or not cid_course:
            continue
        if events and dist not in events:
            raise ValueError(f"Distance {dist} is not in this package's events")
        course = get_org_course(cid_course)
        course_dist = str(course.get("distance") or "").strip().lower()
        if course_dist and course_dist != dist:
            raise ValueError(
                f"Course {cid_course} is distance {course_dist}, not {dist}"
            )
        clean[dist] = normalize_course_id(cid_course)

    manifest["assigned_courses"] = clean
    save_config_manifest(package_path, manifest)
    return get_package_course_assignments(cid)


def _merge_course_leg_libraries(
    course_ids: Sequence[str],
    target_lib_dir: Path,
) -> Dict[str, Any]:
    """Merge snapshotted leg libraries from assigned courses (first wins on conflict)."""
    if target_lib_dir.exists():
        shutil.rmtree(target_lib_dir)
    target_lib_dir.mkdir(parents=True, exist_ok=True)
    merged_legs: Dict[str, Dict[str, Any]] = {}
    for course_id in course_ids:
        slug = normalize_course_id(course_id)
        src_lib = _course_dir(slug) / "leg_library"
        if not src_lib.is_dir():
            raise ValueError(f"Course {slug} has no leg snapshot")
        src_manifest = load_manifest(src_lib / "manifest.yaml")
        for entry in manifest_legs(src_manifest) or []:
            if not isinstance(entry, dict):
                continue
            leg_id = str(entry.get("id", "")).strip()
            if not leg_id or leg_id in merged_legs:
                continue
            file_name = str(entry.get("file") or "").strip()
            if not file_name:
                continue
            src_gpx = src_lib / file_name
            if not src_gpx.is_file():
                continue
            dest_name = file_name
            shutil.copy2(src_gpx, target_lib_dir / dest_name)
            snap = dict(entry)
            snap["file"] = dest_name
            merged_legs[leg_id] = snap
    if not merged_legs:
        raise ValueError("No legs found in assigned course snapshots")
    manifest = {
        "version": 2,
        "label": "Race day merged leg snapshots",
        "legs": list(merged_legs.values()),
        "recipes": {},
    }
    with open(target_lib_dir / "manifest.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(manifest, fh, sort_keys=False, allow_unicode=True)
    return manifest


def build_package_race_exports(config_id: str) -> Dict[str, Any]:
    """
    Build multi-distance package-root exports from assigned global courses.

    Merges leg snapshots + recipes from each assigned course, writes
    segments.csv / flow.csv / locations.csv / {event}.gpx at the package root.
    """
    from app.core.config_package.storage import export_config_package_segments

    cid = validate_config_id(config_id)
    assignment = get_package_course_assignments(cid)
    assigned = assignment["assigned_courses"]
    events = [str(e).strip().lower() for e in (assignment["package_events"] or []) if str(e).strip()]
    if not events:
        events = sorted(assigned.keys())
    missing = [e for e in events if e not in assigned]
    if missing:
        raise ValueError(
            "Assign a course for every package event before building: "
            + ", ".join(missing)
        )

    recipes: Dict[str, List[str]] = {}
    course_ids: List[str] = []
    for distance in events:
        course_id = assigned[distance]
        course = get_org_course(course_id)
        recipe = course.get("recipe") or []
        if not recipe:
            meta_path = _course_dir(normalize_course_id(course_id)) / SAVED_COURSE_META
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            recipe = meta.get("recipe") or []
        recipes[distance] = [str(x).strip() for x in recipe if str(x).strip()]
        if not recipes[distance]:
            raise ValueError(f"Course {course_id} has an empty recipe")
        course_ids.append(course_id)

    package_path = resolve_config_package_path(cid)
    merge_lib = package_path / "race_leg_library"
    merged_manifest = _merge_course_leg_libraries(course_ids, merge_lib)
    apply_manifest = dict(merged_manifest)
    apply_manifest["recipes"] = recipes
    apply_manifest["label"] = str(load_config_manifest(cid).get("label") or cid)

    bundle = export_library_to_course(
        merge_lib, manifest=apply_manifest, event_ids=events
    )
    segments = bundle["segments"]
    if not segments:
        raise ValueError("Assigned courses produced no segments")

    course = load_config_course(cid)
    course["segments"] = segments
    course["segment_library_applied"] = True
    save_config_course(cid, course)

    # Persist recipes before export so sync_leg_metadata keeps recipe segments
    from app.core.config_package.segment_recipes import (
        load_package_segment_manifest,
        save_package_segment_manifest,
    )

    pkg_seg = load_package_segment_manifest(cid)
    pkg_seg["recipes"] = recipes
    pkg_seg["leg_source"] = "org"
    save_package_segment_manifest(cid, pkg_seg)

    # Merge locations from assigned-course snapshots (not live org legs). Package
    # course.json may still have stale traffic types; do not preserve those over
    # the saved course leg snapshot.
    try:
        from app.core.config_package.legs import (
            _RACE_EXPORT_PRESERVE_FIELDS,
            merge_leg_locations_into_course,
            refresh_course_location_seg_ids,
        )

        merge_leg_locations_into_course(
            cid,
            leg_manifest=merged_manifest,
            preserve_from_course=_RACE_EXPORT_PRESERVE_FIELDS,
        )
        refresh_course_location_seg_ids(cid)
    except Exception:
        logger.warning("Location merge after race build failed for %s", cid, exc_info=True)

    export_result = export_config_package_segments(cid)

    # Prefer GPX built from assigned course recipes (export_config uses package recipes)
    legs_by_id = load_leg_library(merge_lib, apply_manifest)
    gpx_files: List[Dict[str, str]] = []
    for distance in events:
        try:
            gpx_content = build_event_gpx_content(
                distance,
                apply_manifest,
                legs_by_id,
                course_name=f"{apply_manifest.get('label')} {distance}",
            )
            gpx_path = package_path / f"{distance}.gpx"
            gpx_path.write_text(gpx_content, encoding="utf-8")
            gpx_files.append({"event_id": distance, "path": str(gpx_path)})
        except ValueError:
            continue

    return {
        "ok": True,
        "config_id": cid,
        "assigned_courses": assigned,
        "recipes": recipes,
        "segment_count": len(segments),
        "stitch_warnings": bundle.get("stitch_warnings") or [],
        "recipe_lengths_km": bundle.get("recipe_lengths_km") or {},
        "export": export_result,
        "gpx_files": gpx_files,
        "readiness": package_readiness(package_path),
        "analysis_data_dir": f"runflow/config/{cid}",
    }


# Back-compat aliases used by earlier package-scoped API / tests
def list_saved_courses(config_id: str) -> List[Dict[str, Any]]:
    """Deprecated: list global org courses (config_id ignored)."""
    del config_id
    return list_org_courses()


def save_named_course(
    config_id: str,
    *,
    name: str,
    distance: str,
    recipe: Sequence[str],
    course_id: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Deprecated wrapper — saves to org courses (config_id unused)."""
    del config_id
    result = save_org_course(
        name=name,
        distance=distance,
        recipe=recipe,
        course_id=course_id,
        overwrite=overwrite,
    )
    result["saved_courses"] = result.get("courses") or []
    return result


def delete_saved_course(config_id: str, course_id: str) -> Dict[str, Any]:
    """Deprecated wrapper — deletes org course."""
    del config_id
    result = delete_org_course(course_id)
    result["saved_courses"] = result.get("courses") or []
    return result
