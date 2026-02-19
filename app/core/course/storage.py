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

# Issue #732: Fixed event list until Issue 701. Lowercase per quick-reference.
COURSE_EVENT_IDS = ["full", "half", "10k", "elite", "open"]


def _default_course_json(course_id: str, data_dir: str) -> Dict[str, Any]:
    """Minimal course state for a new course."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": course_id,
        "data_dir": data_dir,
        "created": now,
        "updated": now,
        "events": [{"id": eid, "name": eid, "distance_label": eid} for eid in COURSE_EVENT_IDS],
        "segments": [],
        "locations": [],
        "geometry": None,  # GeoJSON LineString: { type: "LineString", coordinates: [[lon, lat], ...] }
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
    List courses under data_dir/courses/. Each entry has id, path, updated (from course.json).

    Args:
        data_dir: Resolved data directory path.

    Returns:
        List of {"id": str, "path": str, "updated": str} (updated from course.json if present).

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
            result.append({"id": path.name, "path": str(path), "updated": None})
            continue
        try:
            with open(course_file, "r") as f:
                data = json.load(f)
            result.append({
                "id": data.get("id", path.name),
                "path": str(path),
                "updated": data.get("updated"),
            })
        except (json.JSONDecodeError, IOError):
            result.append({"id": path.name, "path": str(path), "updated": None})
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
        return json.load(f)


def save_course(data_dir: Path, course_id: str, course_data: Dict[str, Any]) -> Path:
    """
    Save course state to data_dir/courses/{course_id}/course.json.
    Updates the "updated" timestamp.

    Args:
        data_dir: Resolved data directory path.
        course_id: Course directory name.
        course_data: Full course dict (must include id, events; segments, locations optional).

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
    course_path = course_dir / "course.json"
    with open(course_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved course: {course_path}")
    return course_path
