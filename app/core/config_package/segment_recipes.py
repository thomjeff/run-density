"""
Config package segment library + event recipes (#755 / #769).

GPX chunks live under runflow/config/{config_id}/segment_library/.
Manifest (chunks metadata + recipes) is segment_library/manifest.json.
Apply recipes rebuilds course.json segments[] for export.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import yaml

from app.core.config_package.storage import (
    export_config_package_segments,
    load_config_course,
    resolve_config_package_path,
    save_config_course,
    validate_config_id,
)
from app.core.course.segment_library import (
    build_course_segments_from_library,
    export_library_to_course,
    load_chunk_library,
    load_manifest,
    parse_chunk_gpx,
    validate_recipe_stitch,
)
from app.utils.constants import COURSE_EVENT_IDS

logger = logging.getLogger(__name__)

SEGMENT_LIBRARY_DIRNAME = "segment_library"
MANIFEST_YAML = "manifest.yaml"
MANIFEST_JSON = "manifest.json"

# Sun events for Phase 1 recipe UI
RECIPE_EVENT_IDS = ("full", "half", "10k")

def _repo_root() -> Path:
    """Project root (/app in Docker, repo root on host)."""
    return Path(__file__).resolve().parents[3]


def _reference_library_dir() -> Path:
    """Built-in PlotARoute reference chunks (image or repo cursor/plotaroute)."""
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


def _default_manifest() -> Dict[str, Any]:
    return {
        "version": 1,
        "label": "",
        "chunks": [],
        "recipes": {eid: [] for eid in RECIPE_EVENT_IDS},
        "flow_overrides": [],
    }


def load_package_segment_manifest(config_id: str) -> Dict[str, Any]:
    """Load segment_library manifest or empty defaults."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    path = _manifest_path(package_path)
    if not path.is_file():
        return _default_manifest()
    data = _read_manifest_file(path)
    if not isinstance(data, dict):
        raise ValueError("segment library manifest must be an object")
    if "recipes" not in data:
        data["recipes"] = {eid: [] for eid in RECIPE_EVENT_IDS}
    if "chunks" not in data:
        data["chunks"] = []
    return data


def save_package_segment_manifest(config_id: str, manifest: Dict[str, Any]) -> Path:
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    lib_dir.mkdir(parents=True, exist_ok=True)
    path = package_segment_library_dir(package_path) / MANIFEST_YAML
    out = dict(manifest)
    if "recipes" not in out:
        out["recipes"] = {eid: [] for eid in RECIPE_EVENT_IDS}
    if "chunks" not in out:
        out["chunks"] = []
    _write_manifest_file(path, out)
    logger.info("Saved segment library manifest: %s", path)
    return path


def _chunk_id_from_filename(filename: str) -> str:
    """Derive chunk id from PlotARoute-style names (e.g. 01_start_friel.gpx -> 01)."""
    stem = Path(filename).stem
    if stem.startswith("00_"):
        return ""
    prefix = stem.split("_", 1)[0]
    if prefix.isdigit():
        return prefix
    return stem[:24]


def sync_manifest_chunks_from_gpx(
    lib_dir: Path,
    manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Ensure manifest lists every chunk GPX in lib_dir (except 00_* combined routes).

    New files get default metadata; existing entries keep seg_id, width, recipes, etc.
    """
    manifest = dict(manifest or _default_manifest())
    existing_by_file = {
        str(c.get("file", "")): c
        for c in (manifest.get("chunks") or [])
        if isinstance(c, dict) and c.get("file")
    }
    chunks: List[Dict[str, Any]] = []
    for gpx_path in sorted(lib_dir.glob("*.gpx")):
        name = gpx_path.name
        if name.startswith("00_"):
            continue
        cid = _chunk_id_from_filename(name)
        if not cid:
            continue
        prior = existing_by_file.get(name) or {}
        if prior.get("id"):
            cid = str(prior["id"])
        try:
            parsed = parse_chunk_gpx(gpx_path)
        except ValueError:
            continue
        label = (
            (prior.get("seg_label") or "").strip()
            or (parsed.get("name") or "").strip()
            or gpx_path.stem.replace("_", " ").title()
        )
        chunks.append(
            {
                "id": cid,
                "file": name,
                "seg_id": (prior.get("seg_id") or cid).strip(),
                "seg_label": label,
                "width_m": prior.get("width_m", 3),
                "schema": prior.get("schema", "on_course_open"),
                "direction": prior.get("direction", "uni"),
                "description": (prior.get("description") or "").strip(),
            }
        )
    manifest["chunks"] = chunks
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
    chunks: Sequence[Dict[str, Any]],
    order_by_event: Dict[str, Dict[str, Optional[int]]],
    event_ids: Sequence[str] = RECIPE_EVENT_IDS,
) -> Dict[str, List[str]]:
    """
    Convert UI order grid to recipe lists.

    order_by_event[event][chunk_id] = 1-based order or None if unused.
    """
    recipes: Dict[str, List[str]] = {}
    chunk_ids = [str(c.get("id", "")).strip() for c in chunks if c.get("id")]
    for eid in event_ids:
        key = eid if eid in order_by_event else eid.lower()
        orders = order_by_event.get(key) or order_by_event.get(eid) or {}
        pairs: List[tuple] = []
        for cid in chunk_ids:
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
    chunks: Sequence[Dict[str, Any]],
    recipes: Dict[str, Any],
    event_ids: Sequence[str] = RECIPE_EVENT_IDS,
) -> Dict[str, Dict[str, Optional[int]]]:
    """Inverse of recipes_from_order_grid for UI."""
    chunk_ids = [str(c.get("id", "")).strip() for c in chunks if c.get("id")]
    grid: Dict[str, Dict[str, Optional[int]]] = {}
    for eid in event_ids:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        row: Dict[str, Optional[int]] = {cid: None for cid in chunk_ids}
        for i, cid in enumerate(seq, start=1):
            if cid in row:
                row[cid] = i
        grid[eid] = row
    return grid


def get_package_segment_library_state(config_id: str) -> Dict[str, Any]:
    """Full library state for API: chunks, recipes, lengths, warnings."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    manifest = load_package_segment_manifest(cid)
    chunks_meta = manifest.get("chunks") or []

    if not lib_dir.is_dir() or not chunks_meta:
        return {
            "config_id": cid,
            "library_dir": str(lib_dir),
            "has_library": False,
            "manifest": manifest,
            "chunks": [],
            "recipes": manifest.get("recipes") or {},
            "order_grid": order_grid_from_recipes([], manifest.get("recipes") or {}),
            "recipe_lengths_km": {eid: 0.0 for eid in RECIPE_EVENT_IDS},
            "stitch_warnings": [],
        }

    manifest_path = _manifest_path(package_path)
    chunks_by_id = load_chunk_library(lib_dir, manifest)
    chunk_rows: List[Dict[str, Any]] = []
    for entry in chunks_meta:
        if not isinstance(entry, dict):
            continue
        cid_chunk = str(entry.get("id", "")).strip()
        loaded = chunks_by_id.get(cid_chunk) or {}
        chunk_rows.append(
            {
                "id": cid_chunk,
                "file": entry.get("file") or loaded.get("file"),
                "seg_id": entry.get("seg_id") or cid_chunk,
                "seg_label": entry.get("seg_label") or loaded.get("name") or cid_chunk,
                "length_km": loaded.get("length_km", 0),
                "width_m": entry.get("width_m", 3),
                "schema": entry.get("schema", "on_course_open"),
                "direction": entry.get("direction", "uni"),
                "description": (entry.get("description") or "").strip(),
            }
        )

    recipes = manifest.get("recipes") or {}
    stitch_warnings: List[str] = []
    recipe_lengths: Dict[str, float] = {}
    for eid in RECIPE_EVENT_IDS:
        key = eid if eid in recipes else eid.lower()
        seq = recipes.get(key) or []
        stitch_warnings.extend(validate_recipe_stitch(lib_dir, seq, chunks_by_id))
        recipe_lengths[eid] = round(
            sum(float(chunks_by_id[c]["length_km"]) for c in seq if c in chunks_by_id),
            2,
        )

    return {
        "config_id": cid,
        "library_dir": str(lib_dir),
        "has_library": bool(chunk_rows),
        "manifest": manifest,
        "chunks": chunk_rows,
        "recipes": recipes,
        "order_grid": order_grid_from_recipes(chunk_rows, recipes),
        "recipe_lengths_km": recipe_lengths,
        "stitch_warnings": stitch_warnings,
    }


def save_package_recipes(
    config_id: str,
    recipes: Dict[str, List[str]],
    *,
    order_by_event: Optional[Dict[str, Dict[str, Optional[int]]]] = None,
) -> Dict[str, Any]:
    """Persist recipe lists to package manifest."""
    manifest = load_package_segment_manifest(config_id)
    if order_by_event is not None:
        recipes = recipes_from_order_grid(manifest.get("chunks") or [], order_by_event)
    normalized: Dict[str, List[str]] = {}
    for eid in RECIPE_EVENT_IDS:
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
        raise ValueError("No segment library; import or seed GPX chunks first")

    bundle = export_library_to_course(lib_dir, manifest_path, event_ids=RECIPE_EVENT_IDS)
    segments = bundle["segments"]
    if not segments:
        raise ValueError("Recipes produced no segments; check chunk GPX and recipe order")

    course = load_config_course(cid)
    course["segments"] = segments
    course["segment_library_applied"] = True
    save_config_course(cid, course)

    export_result: Optional[Dict[str, Any]] = None
    if export_csv:
        export_result = export_config_package_segments(cid)

    state = get_package_segment_library_state(cid)
    return {
        "config_id": cid,
        "segment_count": len(segments),
        "recipe_lengths_km": bundle["recipe_lengths_km"],
        "stitch_warnings": bundle["stitch_warnings"],
        "segments_csv_path": export_result.get("path") if export_result else None,
        "library": state,
    }


def import_gpx_files_to_library(
    config_id: str,
    uploads: Sequence[tuple],
) -> Dict[str, Any]:
    """
    Save uploaded GPX files into segment_library/.

    uploads: sequence of (filename, bytes).
    Filenames should match manifest chunk file names when updating an existing library.
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    lib_dir = package_segment_library_dir(package_path)
    lib_dir.mkdir(parents=True, exist_ok=True)
    saved: List[str] = []
    for name, data in uploads:
        safe = Path(name).name
        if not safe.lower().endswith(".gpx"):
            continue
        dest = lib_dir / safe
        dest.write_bytes(data)
        saved.append(safe)
    if not saved:
        raise ValueError("No .gpx files uploaded")
    manifest = load_package_segment_manifest(config_id)
    manifest = sync_manifest_chunks_from_gpx(lib_dir, manifest)
    save_package_segment_manifest(config_id, manifest)
    return get_package_segment_library_state(config_id)
