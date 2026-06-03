"""
Config package segment library + event recipes (#755 / #769).

GPX legs live under runflow/config/{config_id}/segment_library/.
Manifest (legs metadata + recipes) is segment_library/manifest.json.
Apply recipes rebuilds course.json segments[] for export.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from app.core.config_package.storage import (
    export_config_package_segments,
    load_config_course,
    load_config_manifest,
    package_readiness,
    resolve_config_package_path,
    save_config_course,
    validate_config_id,
)
from app.core.course.segment_library import (
    build_course_segments_from_library,
    build_event_gpx_content,
    build_flow_csv_from_segments,
    concat_recipe_coordinates,
    export_library_to_course,
    load_leg_library,
    load_manifest,
    manifest_legs,
    normalize_library_manifest,
    parse_leg_gpx,
    set_manifest_legs,
    validate_recipe_stitch,
)
from app.utils.constants import COURSE_EVENT_IDS

logger = logging.getLogger(__name__)

SEGMENT_LIBRARY_DIRNAME = "segment_library"
MANIFEST_YAML = "manifest.yaml"
MANIFEST_JSON = "manifest.json"

# Legacy default when package has no package_events (pre-#769 packages only)
_LEGACY_RECIPE_EVENT_IDS = ("full", "half", "10k")


def package_recipe_event_ids(config_id: str) -> List[str]:
    """
    Event ids for recipe grid and export — from package manifest, not hardcoded.

    Falls back to keys already in segment_library recipes, then legacy FM trio.
    """
    cid = validate_config_id(config_id)
    try:
        manifest = load_config_manifest(cid)
        raw = manifest.get("package_events")
        if isinstance(raw, list) and raw:
            return [str(e).strip().lower() for e in raw if str(e).strip()]
    except FileNotFoundError:
        pass
    package_path = resolve_config_package_path(cid)
    path = _manifest_path(package_path)
    if path.is_file():
        data = _read_manifest_file(path)
        recipes = data.get("recipes") or {}
        if isinstance(recipes, dict) and recipes:
            return sorted(str(k).strip().lower() for k in recipes.keys() if str(k).strip())
    return list(_LEGACY_RECIPE_EVENT_IDS)

def _repo_root() -> Path:
    """Project root (/app in Docker, repo root on host)."""
    return Path(__file__).resolve().parents[3]


def _reference_library_dir() -> Path:
    """Built-in PlotARoute reference legs (image or repo cursor/plotaroute)."""
    candidates = [
        _repo_root() / "cursor" / "plotaroute",
        Path("/app/cursor/plotaroute"),
    ]
    for path in candidates:
        if (path / MANIFEST_YAML).is_file() or (path / MANIFEST_JSON).is_file():
            return path
    return candidates[0]


REFERENCE_LIBRARY_DIR = _reference_library_dir()


def package_segment_library_dir(package_path: Path) -> Path:
    return package_path / SEGMENT_LIBRARY_DIRNAME


def _manifest_path(package_path: Path) -> Path:
    """Resolved manifest file in package (yaml preferred, matches reference library)."""
    lib_dir = package_segment_library_dir(package_path)
    for name in (MANIFEST_YAML, MANIFEST_JSON):
        path = lib_dir / name
        if path.is_file():
            return path
    return lib_dir / MANIFEST_YAML


def _read_manifest_file(path: Path) -> Dict[str, Any]:
    if path.suffix.lower() in (".yaml", ".yml"):
        return load_manifest(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid manifest: {path}")
    return data


def _write_manifest_file(path: Path, manifest: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in (".yaml", ".yml"):
        path.write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    else:
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _default_manifest(event_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    eids = list(event_ids) if event_ids else []
    return {
        "version": 1,
        "label": "",
        "legs": [],
        "recipes": {eid: [] for eid in eids},
        "flow_overrides": [],
    }


def _ensure_recipe_keys(manifest: Dict[str, Any], event_ids: Sequence[str]) -> None:
    recipes = manifest.setdefault("recipes", {})
    if not isinstance(recipes, dict):
        recipes = {}
        manifest["recipes"] = recipes
    for eid in event_ids:
        key = str(eid).strip().lower()
        if key and key not in recipes:
            recipes[key] = []


def load_package_segment_manifest(config_id: str) -> Dict[str, Any]:
    """Load segment_library manifest or empty defaults."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    path = _manifest_path(package_path)
    if not path.is_file():
        return _default_manifest(package_recipe_event_ids(cid))
    data = _read_manifest_file(path)
    if not isinstance(data, dict):
        raise ValueError("segment library manifest must be an object")
    data = normalize_library_manifest(data)
    event_ids = package_recipe_event_ids(cid)
    _ensure_recipe_keys(data, event_ids)
    return data


def save_package_segment_manifest(config_id: str, manifest: Dict[str, Any]) -> Path:
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    lib_dir.mkdir(parents=True, exist_ok=True)
    path = package_segment_library_dir(package_path) / MANIFEST_YAML
    out = normalize_library_manifest(dict(manifest))
    _ensure_recipe_keys(out, package_recipe_event_ids(cid))
    _write_manifest_file(path, out)
    logger.info("Saved segment library manifest: %s", path)
    return path


def _leg_id_from_filename(filename: str) -> str:
    """Derive leg id from PlotARoute-style names (e.g. 01_start_friel.gpx -> 01)."""
    stem = Path(filename).stem
    if stem.startswith("00_"):
        return ""
    prefix = stem.split("_", 1)[0]
    if prefix.isdigit():
        return prefix
    return stem[:24]


def sync_manifest_legs_from_gpx(
    lib_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ensure manifest lists every leg GPX in lib_dir (except 00_* combined routes).

    New files get default metadata; existing entries keep seg_id, width, recipes, etc.
    """
    manifest = normalize_library_manifest(dict(manifest or _default_manifest()))
    existing_by_file = {
        str(c.get("file", "")): c
        for c in manifest_legs(manifest)
        if isinstance(c, dict) and c.get("file")
    }
    legs: List[Dict[str, Any]] = []
    for gpx_path in sorted(lib_dir.glob("*.gpx")):
        name = gpx_path.name
        if name.startswith("00_"):
            continue
        cid = _leg_id_from_filename(name)
        if not cid:
            continue
        prior = existing_by_file.get(name) or {}
        if prior.get("id"):
            cid = str(prior["id"])
        try:
            parsed = parse_leg_gpx(gpx_path)
        except ValueError:
            continue
        label = (
            (prior.get("seg_label") or "").strip()
            or (parsed.get("name") or "").strip()
            or gpx_path.stem.replace("_", " ").title()
        )
        legs.append(
            {
                "id": cid,
                "file": name,
                "seg_label": label,
                "start_label": (prior.get("start_label") or "").strip(),
                "end_label": (prior.get("end_label") or "").strip(),
                "width_m": prior.get("width_m", 3),
                "schema": prior.get("schema", "on_course_open"),
                "direction": prior.get("direction", "uni"),
                "description": (prior.get("description") or "").strip(),
                "locations": prior.get("locations") or [],
            }
        )
    set_manifest_legs(manifest, legs)
    return manifest


def seed_reference_segment_library(config_id: str) -> Dict[str, Any]:
    """Copy cursor/plotaroute reference library into the config package."""
    ref_dir = _reference_library_dir()
    if not ref_dir.is_dir():
        raise FileNotFoundError(
            f"Reference library not found at {ref_dir}. "
            "Rebuild the dev container or mount cursor/plotaroute."
        )
    ref_manifest = ref_dir / MANIFEST_YAML
    if not ref_manifest.is_file():
        ref_manifest = ref_dir / MANIFEST_JSON
    if not ref_manifest.is_file():
        raise FileNotFoundError(f"Reference manifest missing under {ref_dir}")

    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
    shutil.copytree(
        ref_dir,
        lib_dir,
        ignore=shutil.ignore_patterns("generated_segments.csv", "README.md"),
    )
    manifest = _read_manifest_file(_manifest_path(package_path))
    manifest["label"] = manifest.get("label") or "Reference (PlotARoute)"
    save_package_segment_manifest(cid, manifest)
    return get_package_segment_library_state(cid)


def recipes_from_order_grid(
    legs: Sequence[Dict[str, Any]],
    order_by_event: Dict[str, Dict[str, Optional[int]]],
    event_ids: Optional[Sequence[str]] = None,
) -> Dict[str, List[str]]:
    """
    Convert UI order grid to recipe lists.

    order_by_event[event][leg_id] = 1-based order or None if unused.
    """
    recipes: Dict[str, List[str]] = {}
    leg_ids = [str(c.get("id", "")).strip() for c in legs if c.get("id")]
    eids = list(event_ids) if event_ids is not None else []
    for eid in eids:
        key = eid if eid in order_by_event else eid.lower()
        orders = order_by_event.get(key) or order_by_event.get(eid) or {}
        pairs: List[tuple] = []
        for cid in leg_ids:
            raw = orders.get(cid)
            if raw is None or raw == "":
                continue
            try:
                n = int(raw)
            except (TypeError, ValueError):
                continue
            if n > 0:
                pairs.append((n, cid))
        pairs.sort(key=lambda x: x[0])
        recipes[eid] = [cid for _, cid in pairs]
    return recipes


def order_grid_from_recipes(
    legs: Sequence[Dict[str, Any]],
    recipes: Dict[str, Any],
    event_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Dict[str, Optional[int]]]:
    """Inverse of recipes_from_order_grid for UI."""
    leg_ids = [str(c.get("id", "")).strip() for c in legs if c.get("id")]
    grid: Dict[str, Dict[str, Optional[int]]] = {}
    eids = list(event_ids) if event_ids is not None else []
    for eid in eids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        row: Dict[str, Optional[int]] = {cid: None for cid in leg_ids}
        for i, cid in enumerate(seq, start=1):
            if cid in row:
                row[cid] = i
        grid[eid] = row
    return grid


def get_package_segment_library_state(config_id: str) -> Dict[str, Any]:
    """Full library state for API: legs, recipes, lengths, warnings."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    legs_meta = manifest_legs(manifest)
    event_ids = package_recipe_event_ids(cid)

    if not lib_dir.is_dir() or not legs_meta:
        return {
            "config_id": cid,
            "library_dir": str(lib_dir),
            "has_library": False,
            "package_events": event_ids,
            "manifest": manifest,
            "legs": [],
            "recipes": manifest.get("recipes") or {},
            "order_grid": order_grid_from_recipes(
                [], manifest.get("recipes") or {}, event_ids
            ),
            "recipe_lengths_km": {eid: 0.0 for eid in event_ids},
            "stitch_warnings": [],
        }

    manifest_path = _manifest_path(package_path)
    legs_by_id = load_leg_library(lib_dir, manifest)
    from app.core.config_package.legs import leg_row_from_entry

    leg_rows: List[Dict[str, Any]] = []
    for entry in legs_meta:
        if not isinstance(entry, dict):
            continue
        leg_id_key = str(entry.get("id", "")).strip()
        loaded = legs_by_id.get(leg_id_key) or {}
        leg_rows.append(leg_row_from_entry(entry, loaded))

    recipes = manifest.get("recipes") or {}
    stitch_warnings: List[str] = []
    recipe_lengths: Dict[str, float] = {}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        stitch_warnings.extend(validate_recipe_stitch(lib_dir, seq, legs_by_id))
        recipe_lengths[eid] = round(
            sum(float(legs_by_id[c]["length_km"]) for c in seq if c in legs_by_id),
            2,
        )

    return {
        "config_id": cid,
        "library_dir": str(lib_dir),
        "has_library": bool(leg_rows),
        "package_events": event_ids,
        "manifest": manifest,
        "legs": leg_rows,
        "recipes": recipes,
        "order_grid": order_grid_from_recipes(leg_rows, recipes, event_ids),
        "recipe_lengths_km": recipe_lengths,
        "stitch_warnings": stitch_warnings,
    }


def _backup_export_file(target: Path) -> Optional[Path]:
    if not target.is_file():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = target.parent / f"{target.name}.bak.{stamp}"
    shutil.copy2(target, backup)
    return backup


def export_package_flow_and_gpx_files(config_id: str) -> Dict[str, Any]:
    """
    Write flow.csv and per-event GPX files into the config package folder.

    Uses segment library recipes when manifest exists; otherwise builds flow.csv
    from course.json segments only (no GPX).
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest_path = _manifest_path(package_path)
    event_ids = package_recipe_event_ids(cid)
    course = load_config_course(cid)
    segments = course.get("segments") or []

    flow_backup: Optional[Path] = None
    flow_path = package_path / "flow.csv"
    gpx_exports: List[Dict[str, str]] = []

    if manifest_path.is_file():
        bundle = export_library_to_course(lib_dir, manifest_path, event_ids=event_ids)
        flow_backup = _backup_export_file(flow_path)
        flow_path.write_text(bundle["flow_csv"], encoding="utf-8")

        manifest = bundle["manifest"]
        legs_by_id = load_leg_library(lib_dir, manifest)
        recipes = manifest.get("recipes") or {}
        for eid in event_ids:
            key = eid if eid in recipes else eid.lower()
            if not (recipes.get(key) or recipes.get(eid)):
                continue
            try:
                gpx_content = build_event_gpx_content(
                    eid,
                    manifest,
                    legs_by_id,
                    course_name=str(course.get("name") or course.get("label") or cid),
                )
            except ValueError:
                continue
            gpx_path = package_path / f"{eid.lower()}.gpx"
            _backup_export_file(gpx_path)
            gpx_path.write_text(gpx_content, encoding="utf-8")
            gpx_exports.append({"event_id": eid.lower(), "path": str(gpx_path)})
    elif segments:
        manifest_data = {}
        flow_overrides = manifest_data.get("flow_overrides")
        flow_csv = build_flow_csv_from_segments(
            segments,
            event_ids,
            overrides=flow_overrides,
        )
        flow_backup = _backup_export_file(flow_path)
        flow_path.write_text(flow_csv, encoding="utf-8")
    else:
        return {
            "flow_exported": False,
            "flow_path": None,
            "flow_backup_path": None,
            "gpx_files": [],
        }

    logger.info(
        "Exported flow.csv and %s event GPX file(s) for config package %s",
        len(gpx_exports),
        cid,
    )
    return {
        "flow_exported": True,
        "flow_path": str(flow_path),
        "flow_backup_path": str(flow_backup) if flow_backup else None,
        "gpx_files": gpx_exports,
        "readiness": package_readiness(package_path),
    }


def get_event_route_preview(config_id: str, event_id: str) -> Dict[str, Any]:
    """Stitched route coordinates for one event recipe (map preview)."""
    cid = validate_config_id(config_id)
    eid = str(event_id or "").strip().lower()
    if not eid:
        raise ValueError("event_id is required")

    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest_path = _manifest_path(package_path)
    if not manifest_path.is_file():
        raise ValueError("No segment library; import legs and save recipes first")

    manifest = load_manifest(manifest_path)
    legs_by_id = load_leg_library(lib_dir, manifest)
    recipes = manifest.get("recipes") or {}
    leg_ids = recipes.get(eid) or recipes.get(event_id)
    if not leg_ids:
        raise ValueError(f"No recipe for event: {eid}")

    coords = concat_recipe_coordinates(leg_ids, legs_by_id)
    if len(coords) < 2:
        raise ValueError(f"Recipe for {eid} has insufficient route points")

    length_km = round(
        sum(float(legs_by_id[c]["length_km"]) for c in leg_ids if c in legs_by_id),
        2,
    )
    return {
        "config_id": cid,
        "event_id": eid,
        "coordinates": coords,
        "length_km": length_km,
        "leg_count": len(leg_ids),
    }


def save_package_recipes(
    config_id: str,
    recipes: Dict[str, List[str]],
    *,
    order_by_event: Optional[Dict[str, Dict[str, Optional[int]]]] = None,
) -> Dict[str, Any]:
    """Persist recipe lists to package manifest."""
    manifest = load_package_segment_manifest(config_id)
    event_ids = package_recipe_event_ids(config_id)
    if order_by_event is not None:
        recipes = recipes_from_order_grid(
            manifest_legs(manifest), order_by_event, event_ids
        )
    normalized: Dict[str, List[str]] = {}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        normalized[eid] = [str(x).strip() for x in seq if str(x).strip()]
    manifest["recipes"] = normalized
    save_package_segment_manifest(config_id, manifest)
    return get_package_segment_library_state(config_id)


def apply_package_recipes(
    config_id: str,
    *,
    export_csv: bool = True,
) -> Dict[str, Any]:
    """
    Rebuild course.json segments from package segment library recipes.

    Optionally writes segments.csv via export_config_package_segments.
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest_path = _manifest_path(package_path)
    if not manifest_path.is_file():
        raise ValueError("No segment library; import or seed GPX legs first")

    event_ids = package_recipe_event_ids(cid)
    bundle = export_library_to_course(lib_dir, manifest_path, event_ids=event_ids)
    segments = bundle["segments"]
    if not segments:
        raise ValueError("Recipes produced no segments; check leg GPX and recipe order")

    course = load_config_course(cid)
    course["segments"] = segments
    course["segment_library_applied"] = True
    save_config_course(cid, course)

    from app.core.config_package.legs import (
        merge_leg_locations_into_course,
        refresh_course_location_seg_ids,
    )

    merge_leg_locations_into_course(cid)
    seg_refresh = refresh_course_location_seg_ids(cid)

    export_result: Optional[Dict[str, Any]] = None
    flow_gpx_result: Optional[Dict[str, Any]] = None
    if export_csv:
        export_result = export_config_package_segments(cid)
        flow_gpx_result = export_result.get("flow_gpx") if export_result else None

    state = get_package_segment_library_state(cid)
    return {
        "config_id": cid,
        "segment_count": len(segments),
        "recipe_lengths_km": bundle["recipe_lengths_km"],
        "stitch_warnings": bundle["stitch_warnings"],
        "seg_id_refresh_count": seg_refresh.get("seg_id_refresh_count", 0),
        "seg_id_unmapped": seg_refresh.get("seg_id_unmapped") or [],
        "segments_csv_path": export_result.get("path") if export_result else None,
        "flow_csv_path": (flow_gpx_result or {}).get("flow_path"),
        "gpx_files": (flow_gpx_result or {}).get("gpx_files") or [],
        "readiness": (export_result or {}).get("readiness") or package_readiness(package_path),
        "library": state,
    }


def import_gpx_files_to_library(
    config_id: str,
    uploads: Sequence[tuple],
) -> Dict[str, Any]:
    """
    Save uploaded GPX and optional runflow leg export JSON into segment_library/.

    uploads: sequence of (filename, bytes).
    Pair ``{leg_id}.gpx`` with ``{leg_id}.json`` from a leg export zip (same import).
    Filenames should match manifest leg file names when updating an existing library.
    """
    from app.core.config_package.legs import (
        apply_leg_exports_to_manifest,
        leg_id_from_export_filename,
        parse_leg_export_json_bytes,
    )

    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    lib_dir.mkdir(parents=True, exist_ok=True)
    saved_gpx: List[str] = []
    exports_by_leg_id: Dict[str, Dict[str, Any]] = {}
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
            dest = lib_dir / safe
            dest.write_bytes(data)
            continue
        if not lower.endswith(".gpx"):
            continue
        dest = lib_dir / safe
        dest.write_bytes(data)
        saved_gpx.append(safe)
    if not saved_gpx:
        raise ValueError("No .gpx files uploaded")
    manifest = load_package_segment_manifest(config_id)
    manifest = sync_manifest_legs_from_gpx(lib_dir, manifest)
    manifest = apply_leg_exports_to_manifest(manifest, exports_by_leg_id)
    save_package_segment_manifest(config_id, manifest)
    return get_package_segment_library_state(config_id)
