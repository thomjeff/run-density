"""
Course Mapping storage: create/list/load/save under {data_dir}/courses/{id}.

Issue #732: Same approach as baseline — data_dir from request, same as /analysis, /config, /baseline.
"""

from pathlib import Path
from typing import Dict, Any, List
import json
import logging
from datetime import datetime, timezone

from app.utils.run_id import generate_run_id

logger = logging.getLogger(__name__)


def _haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Distance in km between two WGS84 points."""
    import math
    R = 6371000  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)) / 1000


def _course_distance_km(course_data: Dict[str, Any]) -> float:
    """Total distance from geometry coordinates, in km."""
    geom = course_data.get("geometry")
    if not geom or geom.get("type") != "LineString":
        return 0.0
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(coords)):
        c0, c1 = coords[i - 1], coords[i]
        total += _haversine_km(c0[0], c0[1], c1[0], c1[1])
    return round(total, 2)


def _default_course_json(course_id: str, data_dir: str) -> Dict[str, Any]:
    """Minimal course state for a new course."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": course_id,
        "name": "",
        "description": "",
        "data_dir": data_dir,
        "created": now,
        "updated": now,
        "segments": [],
        "locations": [],
        "geometry": None,  # GeoJSON LineString: { type: "LineString", coordinates: [[lon, lat], ...] }
        "segment_breaks": [],  # Indices into geometry.coordinates where segment ends (segment i = breaks[i-1]..breaks[i], breaks[0]=0 implied)
        "segment_break_labels": {},  # Optional labels for segment boundaries: { "index": "label" }
        "segment_break_descriptions": {},  # Optional descriptions for segment boundaries: { "index": "description" }
        "segment_break_ids": {},  # Optional stable IDs: { "index": id } (sequential int, e.g. 1, 2, 3)
    }


def create_course_directory(data_dir: Path) -> Path:
    """
    Create a new course directory under data_dir/courses/{id}.

    Args:
        data_dir: Resolved data directory path (same as used for analysis/baseline).

    Returns:
        Path to the new course directory (data_dir/courses/{run_id}/).

    Issue #732: Course storage.
    """
    course_id = generate_run_id()
    courses_root = data_dir / "courses"
    course_dir = courses_root / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    course_json = _default_course_json(course_id, str(data_dir))
    course_path = course_dir / "course.json"
    with open(course_path, "w") as f:
        json.dump(course_json, f, indent=2)
    logger.info(f"Created course directory: {course_dir}")
    return course_dir


def list_courses(data_dir: Path) -> List[Dict[str, Any]]:
    """
    List courses under data_dir/courses/. Each entry has id, name, description, path, updated,
    distance_km, segments_count, locations_count (from course.json).

    Issue #732: Course storage.
    """
    courses_root = data_dir / "courses"
    if not courses_root.exists() or not courses_root.is_dir():
        return []
    result = []
    for path in sorted(courses_root.iterdir(), key=lambda p: p.name):
        if not path.is_dir():
            continue
        course_file = path / "course.json"
        if not course_file.exists():
            result.append({
                "id": path.name, "name": "", "description": "", "path": str(path),
                "updated": None, "distance_km": 0, "segments_count": 0, "locations_count": 0,
            })
            continue
        try:
            with open(course_file, "r") as f:
                data = json.load(f)
            segments = data.get("segments") or []
            locations = data.get("locations") or []
            result.append({
                "id": data.get("id", path.name),
                "name": (data.get("name") or "")[:255],
                "description": (data.get("description") or "")[:255],
                "path": str(path),
                "updated": data.get("updated"),
                "distance_km": _course_distance_km(data),
                "segments_count": len(segments),
                "locations_count": len(locations),
            })
        except (json.JSONDecodeError, IOError):
            result.append({
                "id": path.name, "name": "", "description": "", "path": str(path),
                "updated": None, "distance_km": 0, "segments_count": 0, "locations_count": 0,
            })
    return result


def load_course(data_dir: Path, course_id: str) -> Dict[str, Any]:
    """
    Load course.json from data_dir/courses/{course_id}/.

    Args:
        data_dir: Resolved data directory path.
        course_id: Course directory name (id).

    Returns:
        Course JSON dict.

    Raises:
        FileNotFoundError: If course directory or course.json does not exist.
        ValueError: If course_id contains path segments (security).

    Issue #732: Course storage.
    """
    if "/" in course_id or "\\" in course_id or course_id in ("", ".", ".."):
        raise ValueError(f"Invalid course_id: {course_id}")
    course_dir = data_dir / "courses" / course_id
    course_file = course_dir / "course.json"
    if not course_file.exists():
        raise FileNotFoundError(f"Course not found: {course_dir}")
    with open(course_file, "r") as f:
        data = json.load(f)
    # Events come from constants (SSOT); strip if present in stored file
    data.pop("events", None)
    return data


def delete_course(data_dir: Path, course_id: str) -> None:
    """
    Delete a course directory and all contents. Cannot be undone.

    Raises:
        ValueError: If course_id invalid.
        FileNotFoundError: If course directory does not exist.

    Issue #732.
    """
    import shutil
    if "/" in course_id or "\\" in course_id or course_id in ("", ".", ".."):
        raise ValueError(f"Invalid course_id: {course_id}")
    course_dir = data_dir / "courses" / course_id
    if not course_dir.exists() or not course_dir.is_dir():
        raise FileNotFoundError(f"Course not found: {course_dir}")
    shutil.rmtree(course_dir)
    logger.info(f"Deleted course: {course_dir}")


def save_course(data_dir: Path, course_id: str, course_data: Dict[str, Any]) -> Path:
    """
    Save course state to data_dir/courses/{course_id}/course.json.
    Updates the "updated" timestamp.

    Args:
        data_dir: Resolved data directory path.
        course_id: Course directory name.
        course_data: Full course dict (must include id; segments, locations optional). events is stripped before save (SSOT: constants.COURSE_EVENT_IDS).

    Returns:
        Path to course.json.

    Raises:
        ValueError: If course_id invalid or course_data["id"] != course_id.

    Issue #732: Course storage.
    """
    if "/" in course_id or "\\" in course_id or course_id in ("", ".", ".."):
        raise ValueError(f"Invalid course_id: {course_id}")
    if course_data.get("id") != course_id:
        raise ValueError(f"course_data.id must equal course_id: {course_id}")
    course_dir = data_dir / "courses" / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    data = dict(course_data)
    data["updated"] = datetime.now(timezone.utc).isoformat()
    data["data_dir"] = str(data_dir)
    # Events come from constants (COURSE_EVENT_IDS); do not persist to course.json
    data.pop("events", None)
    course_path = course_dir / "course.json"
    with open(course_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved course: {course_path}")
    return course_path
