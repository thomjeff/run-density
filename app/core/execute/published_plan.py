"""Published day-plan registry for Execute (Issue #917).

Identity is UUID + calendar_date. Weekday codes are display only.
Imported packages live under runflow/execute/, not Plan analysis trees.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from uuid import UUID

from app.core.execute.board import assemble_board
from app.core.execute.state import load_or_create_state
from app.storage import create_runflow_storage
from app.utils.constants import COURSE_EVENT_IDS, DISPLAY_TIMEZONE
from app.utils.run_id import get_runflow_root

SCHEMA_VERSION = 1
REGISTRY_NAME = "registry.json"
MANIFEST_NAME = "manifest.json"
LOCATIONS_NAME = "locations.json"
COURSES_DIR = "courses"
RACE_DISPLAY_NAMES = {
    "elite": "5K Elite",
    "open": "5K Open",
    "10k": "10K",
    "half": "Half",
    "full": "Full",
}
_ISO_WEEKDAY_TO_CODE = {
    1: "mon",
    2: "tue",
    3: "wed",
    4: "thu",
    5: "fri",
    6: "sat",
    7: "sun",
}


class PublishedPlanError(ValueError):
    """Fail-fast published-plan validation error."""


def weekday_code_for_date(calendar_date: str) -> str:
    parsed = parse_calendar_date(calendar_date)
    return _ISO_WEEKDAY_TO_CODE[parsed.isoweekday()]


def parse_calendar_date(value: str) -> date:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise PublishedPlanError("calendar_date must be YYYY-MM-DD.") from exc


def assert_date_matches_weekday(
    calendar_date: str,
    weekday_code: str,
) -> str:
    derived = weekday_code_for_date(calendar_date)
    wanted = str(weekday_code or "").strip().lower()
    if wanted not in _ISO_WEEKDAY_TO_CODE.values():
        raise PublishedPlanError(f"Unknown weekday_code {weekday_code!r}.")
    if derived != wanted:
        raise PublishedPlanError(
            f"calendar_date {calendar_date} is {derived}, " f"not {wanted}."
        )
    return derived


def assert_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        msg = "published_plan_id must be an RFC 4122 UUID."
        raise PublishedPlanError(msg) from exc


def race_display_name(race_id: str) -> str:
    key = str(race_id or "").strip().lower()
    return RACE_DISPLAY_NAMES.get(key, key)


def execute_store_root(root: Optional[Path] = None) -> Path:
    base = Path(root) if root else get_runflow_root()
    return base / "execute" / "published_plans"


def registry_path(root: Optional[Path] = None) -> Path:
    return execute_store_root(root) / REGISTRY_NAME


def plan_revision_dir(
    published_plan_id: str,
    revision: int,
    root: Optional[Path] = None,
) -> Path:
    root_dir = execute_store_root(root)
    return root_dir / published_plan_id / f"r{int(revision)}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_registry(root: Optional[Path] = None) -> Dict[str, Any]:
    path = registry_path(root)
    if not path.is_file():
        return {"active_published_plan_id": None, "plans": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PublishedPlanError("registry.json is invalid.")
    data.setdefault("active_published_plan_id", None)
    data.setdefault("plans", {})
    return data


def save_registry(
    registry: Mapping[str, Any],
    root: Optional[Path] = None,
) -> None:
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(registry), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise PublishedPlanError("manifest must be an object.")
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise PublishedPlanError("Unsupported published-plan schema_version.")
    plan_id = assert_uuid(manifest.get("published_plan_id"))
    calendar_date = str(manifest.get("calendar_date") or "").strip()
    if not calendar_date:
        raise PublishedPlanError("calendar_date is required.")
    parse_calendar_date(calendar_date)
    weekday = str(manifest.get("weekday_code") or "").strip().lower()
    if weekday:
        assert_date_matches_weekday(calendar_date, weekday)
    else:
        weekday = weekday_code_for_date(calendar_date)
    try:
        revision = int(manifest.get("revision"))
    except (TypeError, ValueError) as exc:
        raise PublishedPlanError("revision must be an integer.") from exc
    if revision < 1:
        raise PublishedPlanError("revision must be >= 1.")
    races = manifest.get("races")
    if not isinstance(races, list) or not races:
        raise PublishedPlanError("races must be a non-empty array.")
    normalized_races: List[Dict[str, Any]] = []
    for race in races:
        if not isinstance(race, Mapping):
            raise PublishedPlanError("Each race must be an object.")
        race_id = str(race.get("id") or "").strip().lower()
        if race_id not in COURSE_EVENT_IDS:
            msg = f"Race id {race_id!r} is not a Build catalog id."
            raise PublishedPlanError(msg)
        course = str(race.get("course") or "").strip()
        if not course:
            course = f"{COURSES_DIR}/{race_id}.geojson"
        normalized_races.append(
            {
                "id": race_id,
                "name": race.get("name") or race_display_name(race_id),
                "start_time": race.get("start_time"),
                "duration_minutes": race.get("duration_minutes"),
                "course": course,
            }
        )
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise PublishedPlanError("files + checksums are required.")
    out = dict(manifest)
    out["published_plan_id"] = plan_id
    out["calendar_date"] = calendar_date
    out["weekday_code"] = weekday
    out["revision"] = revision
    out["timezone"] = out.get("timezone") or DISPLAY_TIMEZONE
    out["races"] = normalized_races
    return out


def _verify_checksums(
    manifest: Mapping[str, Any],
    files: Mapping[str, bytes],
) -> None:
    listed = manifest.get("files") or []
    for item in listed:
        path = str(item.get("path") or "")
        expected = str(item.get("sha256") or "")
        if path not in files:
            raise PublishedPlanError(f"Missing package file {path}.")
        actual = sha256_bytes(files[path])
        if actual != expected:
            raise PublishedPlanError(f"Checksum mismatch for {path}.")


def extract_package(archive: bytes) -> Dict[str, bytes]:
    try:
        with zipfile.ZipFile(BytesIO(archive), "r") as zf:
            files = {}
            for name in zf.namelist():
                if not name.endswith("/"):
                    files[name] = zf.read(name)
            return files
    except zipfile.BadZipFile as exc:
        raise PublishedPlanError("Package is not a valid ZIP.") from exc


def import_published_plan(
    archive: bytes,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    files = extract_package(archive)
    raw = files.get(MANIFEST_NAME)
    if raw is None:
        raise PublishedPlanError("Package is missing manifest.json.")
    manifest = validate_manifest(json.loads(raw.decode("utf-8")))
    _verify_checksums(manifest, files)
    plan_id = manifest["published_plan_id"]
    revision = int(manifest["revision"])
    dest = plan_revision_dir(plan_id, revision, root)
    registry = load_registry(root)
    existing = (registry.get("plans") or {}).get(plan_id)
    same_revision = int((existing or {}).get("revision") or 0) == revision
    if existing and same_revision and dest.is_dir():
        active_id = registry.get("active_published_plan_id")
        return {
            "imported": False,
            "idempotent": True,
            "published_plan_id": plan_id,
            "revision": revision,
            "calendar_date": manifest["calendar_date"],
            "activated": active_id == plan_id,
        }
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    plans = dict(registry.get("plans") or {})
    plans[plan_id] = {
        "published_plan_id": plan_id,
        "revision": revision,
        "calendar_date": manifest["calendar_date"],
        "weekday_code": manifest["weekday_code"],
        "name": manifest.get("name") or "",
        "source_run_id": manifest.get("source_run_id") or "",
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    registry["plans"] = plans
    save_registry(registry, root)
    return {
        "imported": True,
        "idempotent": False,
        "published_plan_id": plan_id,
        "revision": revision,
        "calendar_date": manifest["calendar_date"],
        "activated": False,
    }


def activate_published_plan(
    published_plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = assert_uuid(published_plan_id)
    registry = load_registry(root)
    if plan_id not in (registry.get("plans") or {}):
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    registry["active_published_plan_id"] = plan_id
    save_registry(registry, root)
    return load_imported_plan(plan_id, root)


def load_imported_plan(
    published_plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = assert_uuid(published_plan_id)
    registry = load_registry(root)
    meta = (registry.get("plans") or {}).get(plan_id)
    if not meta:
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    dest = plan_revision_dir(plan_id, int(meta["revision"]), root)
    manifest = validate_manifest(
        json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))
    )
    loc_path = dest / LOCATIONS_NAME
    locations_doc = json.loads(loc_path.read_text(encoding="utf-8"))
    courses: Dict[str, Any] = {}
    for race in manifest["races"]:
        rel = race.get("course") or f"{COURSES_DIR}/{race['id']}.geojson"
        course_path = dest / rel
        if course_path.is_file():
            raw = course_path.read_text(encoding="utf-8")
            courses[race["id"]] = json.loads(raw)
    return {
        "manifest": manifest,
        "locations": locations_doc,
        "courses": courses,
        "directory": str(dest),
        "active": registry.get("active_published_plan_id") == plan_id,
    }


def active_published_plan_id(root: Optional[Path] = None) -> Optional[str]:
    return load_registry(root).get("active_published_plan_id")


def classify_locations(
    locations: List[Mapping[str, Any]],
    state: Mapping[str, Any],
    *,
    run_id: str,
    day: str,
    resources_available: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return assemble_board(
        locations=locations,
        state=state,
        resources_available=resources_available or [],
        run_id=run_id,
        day=day,
    )


def map_snapshot(
    published_plan_id: Optional[str] = None,
    root: Optional[Path] = None,
    now_hhmmss: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    plan_id = published_plan_id or active_published_plan_id(root)
    if not plan_id:
        return {
            "ok": False,
            "empty": True,
            "detail": "Import and activate a published plan.",
            "locations": [],
            "courses": {},
        }
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    locations_doc = loaded["locations"]
    locations = list(locations_doc.get("locations") or [])
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    source_run_id = str(manifest.get("source_run_id") or "").strip()
    if state is None:
        state = {"reopened": {}, "clock": {}, "activity": []}
        if source_run_id:
            try:
                storage = create_runflow_storage(source_run_id)
                state = load_or_create_state(
                    storage,
                    run_id=source_run_id,
                    day=day,
                    analysis={},
                )
            except Exception:
                state = {"reopened": {}, "clock": {}, "activity": []}
    available = locations_doc.get("resources_available") or []
    board = assemble_board(
        locations=locations,
        state=state,
        resources_available=available,
        run_id=source_run_id or plan_id,
        day=day,
        now_hhmmss=now_hhmmss,
    )
    by_id = {}
    for column in board["columns"].values():
        for row in column:
            by_id[str(row.get("loc_id"))] = row
    pins = []
    for row in locations:
        loc_id = row.get("loc_id")
        classified = by_id.get(str(loc_id)) or {}
        pins.append(
            {
                "loc_id": loc_id,
                "loc_label": row.get("loc_label") or "",
                "zone": classified.get("zone") or row.get("zone"),
                "loc_end": row.get("loc_end"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "status": classified.get("status") or "closed",
            }
        )
    return {
        "ok": True,
        "empty": False,
        "published_plan_id": plan_id,
        "calendar_date": manifest["calendar_date"],
        "weekday_code": manifest.get("weekday_code"),
        "name": manifest.get("name") or "",
        "timezone": manifest.get("timezone") or DISPLAY_TIMEZONE,
        "races": manifest.get("races") or [],
        "courses": loaded["courses"],
        "locations": pins,
        "board": board,
    }
