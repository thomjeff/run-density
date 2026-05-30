"""
Config package storage: runflow/config/{config_id}/ with config.json manifest.

Issue #756: Race Configuration hub — UUID packages + legacy slug directories.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.course.export import (
    build_locations_csv,
    build_segments_csv,
    enrich_segments_event_distances,
)
from app.io.loader import load_segments
from app.utils.constants import COURSE_EVENT_IDS
from app.utils.run_id import generate_run_id, get_runflow_root

logger = logging.getLogger(__name__)

# Top-level keys allowed in config package course.json (Issue #757)
_COURSE_LIST_FIELDS = (
    "segments",
    "locations",
    "segment_breaks",
    "turnaround_indices",
    "flow_control_points",
)
_COURSE_DICT_FIELDS = (
    "segment_break_labels",
    "segment_break_descriptions",
    "segment_break_ids",
    "turnaround_descriptions",
)

CONFIG_MANIFEST_NAME = "config.json"
COURSE_WORKSPACE_NAME = "course.json"
INDEX_NAME = "index.json"

PACKAGE_SIGNAL_FILES = (
    "segments.csv",
    "flow.csv",
    "locations.csv",
    COURSE_WORKSPACE_NAME,
    CONFIG_MANIFEST_NAME,
)
PACKAGE_SIGNAL_GLOBS = ("*_runners.csv", "*.gpx")


def get_config_root() -> Path:
    """Return runflow/config root directory."""
    return get_runflow_root() / "config"


def validate_config_id(config_id: str) -> str:
    """
    Validate config_id is a single safe path segment (UUID or legacy slug).

    Raises:
        ValueError: If invalid
    """
    if not config_id or not isinstance(config_id, str):
        raise ValueError("config_id is required")
    normalized = config_id.strip()
    if not normalized:
        raise ValueError("config_id must not be empty")
    if normalized in (".", ".."):
        raise ValueError(f"Invalid config_id: {config_id}")
    if Path(normalized).name != normalized or "/" in normalized or "\\" in normalized:
        raise ValueError(f"Invalid config_id: {config_id}")
    if not normalized.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Invalid config_id: {config_id}")
    return normalized


def resolve_config_package_path(config_id: str) -> Path:
    """Resolve and verify config package directory exists."""
    cid = validate_config_id(config_id)
    root = get_config_root()
    if not root.is_dir():
        raise FileNotFoundError(f"Config root not found: {root}")
    package_path = root / cid
    if not package_path.exists() or not package_path.is_dir():
        raise FileNotFoundError(f"Config package not found: {cid}")
    return package_path


def _package_has_signal_files(package_path: Path) -> bool:
    for name in PACKAGE_SIGNAL_FILES:
        if (package_path / name).is_file():
            return True
    for pattern in PACKAGE_SIGNAL_GLOBS:
        if any(package_path.glob(pattern)):
            return True
    return False


def package_readiness(package_path: Path) -> Dict[str, Any]:
    """Summarize which standard inputs exist in the package folder."""
    files = sorted(
        p.name
        for p in package_path.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )
    missing = []
    for required in ("segments.csv", "flow.csv", "locations.csv"):
        if not (package_path / required).is_file():
            missing.append(required)
    has_runners = any(package_path.glob("*_runners.csv"))
    has_gpx = any(package_path.glob("*.gpx"))
    analyze_ready = (
        (package_path / "segments.csv").is_file()
        and (package_path / "flow.csv").is_file()
        and has_runners
        and has_gpx
    )
    return {
        "files": files,
        "has_runners": has_runners,
        "has_gpx": has_gpx,
        "analyze_ready": analyze_ready,
        "missing": missing,
    }


def validate_config_course_data(course_data: Any, config_id: str) -> Dict[str, Any]:
    """
    Validate course workspace payload before save.

    Raises:
        ValueError: Invalid structure or id mismatch
    """
    cid = validate_config_id(config_id)
    if not isinstance(course_data, dict):
        raise ValueError("course must be a JSON object")

    course_id = course_data.get("id") or course_data.get("config_id")
    if course_id is not None and str(course_id) != cid:
        raise ValueError(f"course id must equal config_id: {cid}")

    for key in _COURSE_LIST_FIELDS:
        value = course_data.get(key)
        if value is not None and not isinstance(value, list):
            raise ValueError(f"course.{key} must be a list")

    for key in _COURSE_DICT_FIELDS:
        value = course_data.get(key)
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"course.{key} must be an object")

    geometry = course_data.get("geometry")
    if geometry is not None:
        if not isinstance(geometry, dict):
            raise ValueError("course.geometry must be an object or null")
        if geometry.get("type") != "LineString":
            raise ValueError("course.geometry.type must be LineString")
        coords = geometry.get("coordinates")
        if coords is not None and not isinstance(coords, list):
            raise ValueError("course.geometry.coordinates must be a list")

    for key in ("name", "description", "start_description", "end_description"):
        value = course_data.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"course.{key} must be a string")

    return course_data


def _normalize_course_locations(course_data: Dict[str, Any]) -> None:
    """Migrate deprecated loc_description to notes; drop loc_direction if present."""
    locations = course_data.get("locations")
    if not isinstance(locations, list):
        return
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if loc.get("loc_description") and not loc.get("notes"):
            loc["notes"] = str(loc.pop("loc_description")).strip()
        elif "loc_description" in loc:
            loc.pop("loc_description", None)
        loc.pop("loc_direction", None)


def load_config_course(config_id: str) -> Dict[str, Any]:
    """
    Load course.json from runflow/config/{config_id}/.

    Raises:
        FileNotFoundError: Package or course.json missing
        ValueError: Invalid config_id
    """
    package_path = resolve_config_package_path(config_id)
    course_path = package_path / COURSE_WORKSPACE_NAME
    if not course_path.is_file():
        raise FileNotFoundError(
            f"{COURSE_WORKSPACE_NAME} not found in package {config_id}"
        )
    with open(course_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid {COURSE_WORKSPACE_NAME} in package {config_id}")
    data.pop("events", None)
    _normalize_course_locations(data)
    return data


def save_config_course(config_id: str, course_data: Dict[str, Any]) -> Path:
    """
    Save course workspace to runflow/config/{config_id}/course.json.

    Raises:
        FileNotFoundError: Package not found
        ValueError: Invalid config_id or course payload
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    data = validate_config_course_data(course_data, cid)
    _normalize_course_locations(data)

    data = dict(data)
    data["id"] = cid
    data["config_id"] = cid
    data["updated"] = datetime.now(timezone.utc).isoformat()
    data.pop("events", None)
    data.pop("data_dir", None)

    segments = data.get("segments") or []
    if segments:
        enrich_segments_event_distances(segments, COURSE_EVENT_IDS)

    course_path = package_path / COURSE_WORKSPACE_NAME
    with open(course_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved config package course: %s", course_path)
    return course_path


def default_course_json(config_id: str) -> Dict[str, Any]:
    """Minimal draw-first course workspace for a new package."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": config_id,
        "config_id": config_id,
        "name": "",
        "description": "",
        "created": now,
        "updated": now,
        "segments": [],
        "locations": [],
        "geometry": None,
        "segment_breaks": [],
        "segment_break_labels": {},
        "segment_break_descriptions": {},
        "segment_break_ids": {},
        "turnaround_indices": [],
        "start_description": "",
        "end_description": "",
        "turnaround_descriptions": {},
        "flow_control_points": [],
    }


def _read_manifest(package_path: Path) -> Optional[Dict[str, Any]]:
    manifest_path = package_path / CONFIG_MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config_manifest(config_id: str) -> Dict[str, Any]:
    """Load config.json for a package."""
    package_path = resolve_config_package_path(config_id)
    manifest = _read_manifest(package_path)
    if manifest is None:
        raise FileNotFoundError(
            f"{CONFIG_MANIFEST_NAME} not found in package {config_id}"
        )
    return manifest


def save_config_manifest(package_path: Path, manifest: Dict[str, Any]) -> None:
    """Write config.json and touch updated timestamp."""
    manifest["updated"] = datetime.now(timezone.utc).isoformat()
    path = package_path / CONFIG_MANIFEST_NAME
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _load_index(root: Path) -> Dict[str, Any]:
    index_path = root / INDEX_NAME
    if not index_path.is_file():
        return {"packages": []}
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"packages": []}
    packages = data.get("packages")
    if not isinstance(packages, list):
        return {"packages": []}
    return data


def _save_index(root: Path, data: Dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    index_path = root / INDEX_NAME
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def append_package_index(entry: Dict[str, Any]) -> None:
    """Append or update a package entry in config/index.json."""
    root = get_config_root()
    root.mkdir(parents=True, exist_ok=True)
    data = _load_index(root)
    packages: List[Dict[str, Any]] = data["packages"]
    cid = entry.get("config_id")
    packages = [p for p in packages if p.get("config_id") != cid]
    packages.append(entry)
    packages.sort(key=lambda p: (p.get("label") or p.get("config_id") or "").lower())
    data["packages"] = packages
    _save_index(root, data)


def _entry_from_package_dir(package_path: Path) -> Optional[Dict[str, Any]]:
    if not package_path.is_dir():
        return None
    if not _package_has_signal_files(package_path):
        return None

    config_id = package_path.name
    manifest = _read_manifest(package_path)
    if manifest:
        label = (manifest.get("label") or config_id).strip()
        description = (manifest.get("description") or "").strip()
        created = manifest.get("created")
        updated = manifest.get("updated")
        legacy = bool(manifest.get("legacy", False))
    else:
        label = config_id
        description = ""
        created = None
        updated = None
        legacy = True

    readiness = package_readiness(package_path)
    return {
        "config_id": config_id,
        "label": label,
        "description": description,
        "created": created,
        "updated": updated,
        "legacy": legacy,
        "path": str(package_path),
        "readiness": readiness,
    }


def list_config_packages() -> List[Dict[str, Any]]:
    """List all config packages (manifest + legacy slug folders)."""
    root = get_config_root()
    if not root.is_dir():
        return []

    entries: Dict[str, Dict[str, Any]] = {}
    for package_path in root.iterdir():
        if not package_path.is_dir():
            continue
        try:
            validate_config_id(package_path.name)
        except ValueError:
            continue
        entry = _entry_from_package_dir(package_path)
        if entry:
            entries[package_path.name] = entry

    index = _load_index(root)
    for item in index.get("packages", []):
        cid = item.get("config_id")
        if not cid or cid in entries:
            continue
        try:
            package_path = resolve_config_package_path(cid)
            entry = _entry_from_package_dir(package_path)
            if entry:
                entries[cid] = entry
        except FileNotFoundError:
            continue

    result = list(entries.values())
    result.sort(key=lambda p: (p.get("label") or "").lower())
    return result


def create_config_package(label: str, description: str = "") -> Dict[str, Any]:
    """
    Create a new config package with UUID config_id.

    Args:
        label: Human-readable package name
        description: Optional package description

    Returns:
        Dict with config_id, label, path, manifest
    """
    clean_label = (label or "").strip()
    if not clean_label:
        raise ValueError("label is required")
    clean_description = (description or "").strip()
    if len(clean_description) > 255:
        raise ValueError("description must be at most 255 characters")

    config_id = generate_run_id()
    root = get_config_root()
    root.mkdir(parents=True, exist_ok=True)
    package_path = root / config_id
    if package_path.exists():
        raise FileExistsError(f"Config package path already exists: {config_id}")

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "config_id": config_id,
        "label": clean_label,
        "description": clean_description,
        "created": now,
        "updated": now,
        "legacy": False,
    }
    package_path.mkdir(parents=True, exist_ok=False)
    save_config_manifest(package_path, manifest)

    course_path = package_path / COURSE_WORKSPACE_NAME
    course_data = default_course_json(config_id)
    course_data["name"] = clean_label
    course_data["description"] = clean_description
    with open(course_path, "w", encoding="utf-8") as f:
        json.dump(course_data, f, indent=2)

    append_package_index(
        {
            "config_id": config_id,
            "label": clean_label,
            "description": clean_description,
            "created": now,
            "updated": now,
            "legacy": False,
        }
    )

    logger.info("Created config package %s (%s)", config_id, clean_label)
    return {
        "config_id": config_id,
        "label": clean_label,
        "description": clean_description,
        "path": str(package_path),
        "manifest": manifest,
        "readiness": package_readiness(package_path),
    }


def update_config_package_metadata(
    config_id: str,
    label: str,
    description: str = "",
) -> Dict[str, Any]:
    """
    Update package name and description in config.json (and course.json when present).

    Raises:
        FileNotFoundError: Package or config.json missing
        ValueError: Invalid label/description
    """
    cid = validate_config_id(config_id)
    clean_label = (label or "").strip()
    if not clean_label:
        raise ValueError("label is required")
    clean_description = (description or "").strip()
    if len(clean_description) > 255:
        raise ValueError("description must be at most 255 characters")

    package_path = resolve_config_package_path(cid)
    manifest_path = package_path / CONFIG_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"{CONFIG_MANIFEST_NAME} not found in package {cid}; cannot edit metadata"
        )

    manifest = _read_manifest(package_path) or {}
    manifest["config_id"] = cid
    manifest["label"] = clean_label
    manifest["description"] = clean_description
    save_config_manifest(package_path, manifest)

    course_path = package_path / COURSE_WORKSPACE_NAME
    if course_path.is_file():
        with open(course_path, "r", encoding="utf-8") as f:
            course_data = json.load(f)
        course_data["name"] = clean_label
        course_data["description"] = clean_description
        course_data["updated"] = manifest["updated"]
        with open(course_path, "w", encoding="utf-8") as f:
            json.dump(course_data, f, indent=2)

    append_package_index(
        {
            "config_id": cid,
            "label": clean_label,
            "description": clean_description,
            "created": manifest.get("created"),
            "updated": manifest["updated"],
            "legacy": bool(manifest.get("legacy", False)),
        }
    )

    logger.info("Updated config package metadata %s (%s)", cid, clean_label)
    return {
        "config_id": cid,
        "label": clean_label,
        "description": clean_description,
        "path": str(package_path),
        "manifest": manifest,
        "readiness": package_readiness(package_path),
    }


def import_runner_files_from_package(
    target_config_id: str,
    source_config_id: str,
) -> List[str]:
    """
    Copy all *_runners.csv files from source package into target package.

    Raises:
        ValueError: Same package or no runner files in source
        FileNotFoundError: Package not found
    """
    target_id = validate_config_id(target_config_id)
    source_id = validate_config_id(source_config_id)
    if target_id == source_id:
        raise ValueError("Source and target package must be different")

    target_path = resolve_config_package_path(target_id)
    source_path = resolve_config_package_path(source_id)

    copied: List[str] = []
    for src in sorted(source_path.glob("*_runners.csv")):
        if not src.is_file():
            continue
        dest = target_path / src.name
        shutil.copy2(src, dest)
        copied.append(src.name)

    if not copied:
        raise ValueError(
            f"No *_runners.csv files found in source package '{source_id}'"
        )

    logger.info(
        "Copied %s runner file(s) from %s into %s",
        len(copied),
        source_id,
        target_id,
    )
    return copied


def _validate_exported_segments_file(segments_path: Path) -> None:
    """Fail-fast checks so exported segments.csv is loadable by the pipeline."""
    if not segments_path.is_file():
        raise FileNotFoundError(f"segments.csv not written: {segments_path}")
    df = load_segments(str(segments_path))
    if df.empty:
        raise ValueError("segments.csv must contain at least one row")
    if "seg_id" not in df.columns:
        raise ValueError("segments.csv missing seg_id column")
    if df["seg_id"].duplicated().any():
        dupes = df[df.duplicated(subset=["seg_id"], keep=False)]["seg_id"].tolist()
        raise ValueError(f"Duplicate seg_id values: {dupes}")
    for col in ("width_m", "schema", "direction"):
        if col not in df.columns:
            raise ValueError(f"segments.csv missing required column: {col}")
    for eid in COURSE_EVENT_IDS:
        if eid not in df.columns:
            raise ValueError(f"segments.csv missing event column: {eid}")
        from_col = f"{eid}_from_km"
        to_col = f"{eid}_to_km"
        if from_col not in df.columns or to_col not in df.columns:
            raise ValueError(f"segments.csv missing km columns for {eid}")


def export_config_package_segments(config_id: str) -> Dict[str, Any]:
    """
    Export segments.csv from package course.json into runflow/config/{config_id}/.

    Backs up existing segments.csv to segments.csv.bak.{timestamp} when present.

    Raises:
        FileNotFoundError: Package or course.json missing
        ValueError: No segments or validation failed
    """
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    course = load_config_course(cid)
    segments = course.get("segments") or []
    if not segments:
        raise ValueError("Course has no segments; add segment pins before export")

    enrich_segments_event_distances(segments, COURSE_EVENT_IDS)
    csv_content = build_segments_csv(course, fmt="pipeline")

    target = package_path / "segments.csv"
    backup_path: Optional[Path] = None
    if target.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = package_path / f"segments.csv.bak.{stamp}"
        shutil.copy2(target, backup_path)

    target.write_text(csv_content, encoding="utf-8")
    _validate_exported_segments_file(target)

    locations_target = package_path / "locations.csv"
    locations_backup_path: Optional[Path] = None
    locations = course.get("locations") or []
    locations_csv = build_locations_csv(course)
    if locations_target.is_file():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        locations_backup_path = package_path / f"locations.csv.bak.{stamp}"
        shutil.copy2(locations_target, locations_backup_path)
    locations_target.write_text(locations_csv, encoding="utf-8")

    logger.info(
        "Exported segments.csv (%s rows) and locations.csv (%s rows) for config package %s",
        len(segments),
        len(locations),
        cid,
    )
    return {
        "config_id": cid,
        "path": str(target),
        "backup_path": str(backup_path) if backup_path else None,
        "segments_backup_path": str(backup_path) if backup_path else None,
        "segment_count": len(segments),
        "locations_path": str(locations_target),
        "locations_backup_path": str(locations_backup_path) if locations_backup_path else None,
        "location_count": len(locations),
        "readiness": package_readiness(package_path),
    }
