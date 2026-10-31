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
from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import UUID

from app.core.execute.board import assemble_board
from app.core.execute.layers import turnaround_pins
from app.core.execute.report import (
    build_reopen_rows,
    csv_columns,
    reopen_csv_text,
)
from app.core.execute.state import (
    apply_clock_update,
    normalize_state,
    record_close,
    record_reopen,
)
from app.core.execute.times import wall_hhmmss
from app.utils.constants import COURSE_EVENT_IDS, DISPLAY_TIMEZONE
from app.utils.path_mapper import resolve_runflow_root as get_runflow_root

SCHEMA_VERSION = 1
REGISTRY_NAME = "registry.json"
MANIFEST_NAME = "manifest.json"
LOCATIONS_NAME = "locations.json"
COURSES_DIR = "courses"
LOC_SHEETS_DIR = "loc_sheets"
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
        msg = "plan_id must be an RFC 4122 UUID."
        raise PublishedPlanError(msg) from exc


def race_display_name(race_id: str) -> str:
    key = str(race_id or "").strip().lower()
    return RACE_DISPLAY_NAMES.get(key, key)


def execute_store_root(root: Optional[Path] = None) -> Path:
    base = Path(root) if root else get_runflow_root()
    store = base / "execute" / "plans"
    leftover = base / "execute" / "published_plans"
    if not store.exists() and leftover.exists():
        leftover.rename(store)
    return store


def registry_path(root: Optional[Path] = None) -> Path:
    return execute_store_root(root) / REGISTRY_NAME


def plan_revision_dir(
    plan_id: str,
    revision: int,
    root: Optional[Path] = None,
) -> Path:
    root_dir = execute_store_root(root)
    return root_dir / plan_id / f"r{int(revision)}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_registry(root: Optional[Path] = None) -> Dict[str, Any]:
    from app.core.execute.db import registry_from_db, using_postgres

    if using_postgres() and root is None:
        return registry_from_db()
    path = registry_path(root)
    if not path.is_file():
        return {"active_plan_id": None, "plans": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PublishedPlanError("registry.json is invalid.")
    normalized = _normalize_registry(data)
    if _registry_has_leftover(data):
        save_registry(normalized, root)
    return normalized


def save_registry(
    registry: Mapping[str, Any],
    root: Optional[Path] = None,
) -> None:
    from app.core.execute.db import save_registry_db, using_postgres

    if using_postgres() and root is None:
        save_registry_db(dict(registry))
        return
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(registry), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _registry_has_leftover(data: Mapping[str, Any]) -> bool:
    if "active_published_plan_id" in data:
        return True
    for meta in (data.get("plans") or {}).values():
        if isinstance(meta, Mapping) and "published_plan_id" in meta:
            return True
    return False


def _normalize_registry(data: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(data)
    leftover_active = out.pop("active_published_plan_id", None)
    if out.get("active_plan_id") in (None, "") and leftover_active:
        out["active_plan_id"] = leftover_active
    out.setdefault("active_plan_id", None)
    plans: Dict[str, Any] = {}
    for key, meta in (out.get("plans") or {}).items():
        if not isinstance(meta, Mapping):
            continue
        row = dict(meta)
        leftover_id = row.pop("published_plan_id", None)
        raw_id = row.get("plan_id") or leftover_id or key
        try:
            plan_id = assert_uuid(raw_id)
        except PublishedPlanError:
            continue
        row["plan_id"] = plan_id
        plans[plan_id] = row
    active = out.get("active_plan_id")
    if active:
        try:
            out["active_plan_id"] = assert_uuid(active)
        except PublishedPlanError:
            out["active_plan_id"] = None
    out["plans"] = plans
    return out


def validate_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise PublishedPlanError("manifest must be an object.")
    if int(manifest.get("schema_version") or 0) != SCHEMA_VERSION:
        raise PublishedPlanError("Unsupported published-plan schema_version.")
    if manifest.get("plan_id") in (None, ""):
        raise PublishedPlanError("plan_id is required.")
    plan_id = assert_uuid(manifest.get("plan_id"))
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
    out["plan_id"] = plan_id
    out.pop("published_plan_id", None)
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


def apply_plan_overrides(
    manifest: Mapping[str, Any],
    *,
    name: Optional[str] = None,
    calendar_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Operator edits from the import modal (#947). Date keeps the plan weekday."""
    out = dict(manifest)
    name_text = str(name or "").strip()
    if name_text:
        out["name"] = name_text
    date_text = str(calendar_date or "").strip()
    if date_text:
        parse_calendar_date(date_text)
        original = str(out.get("calendar_date") or "").strip()
        weekday = str(out.get("weekday_code") or "").strip().lower()
        if not weekday and original:
            weekday = weekday_code_for_date(original)
        if weekday and weekday_code_for_date(date_text) != weekday:
            day_name = parse_calendar_date(original).strftime("%A")
            raise PublishedPlanError(
                f"This Day Plan is for a {day_name}. Pick a {day_name} date."
            )
        out["calendar_date"] = date_text
        if weekday:
            out["weekday_code"] = weekday
    return out


def _read_package(archive: bytes) -> Tuple[Dict[str, bytes], Dict[str, Any]]:
    files = extract_package(archive)
    raw = files.get(MANIFEST_NAME)
    if raw is None:
        raise PublishedPlanError("Package is missing manifest.json.")
    return files, json.loads(raw.decode("utf-8"))


def preview_published_plan(
    archive: bytes,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Name, date, and import status for the import modal (#947)."""
    files, raw_manifest = _read_package(archive)
    manifest = validate_manifest(raw_manifest)
    _verify_checksums(manifest, files)
    plan_id = manifest["plan_id"]
    existing = (load_registry(root).get("plans") or {}).get(plan_id) or {}
    return {
        "plan_id": plan_id,
        "revision": int(manifest["revision"]),
        "name": manifest.get("name") or "",
        "calendar_date": manifest["calendar_date"],
        "weekday_code": manifest["weekday_code"],
        "already_imported": bool(existing),
        "archived": bool(existing.get("archived")),
    }


def _save_package_db(
    plan_id: str,
    manifest: Mapping[str, Any],
    dest: Path,
) -> None:
    from app.core.execute.db import save_plan_package

    locations_doc = json.loads((dest / LOCATIONS_NAME).read_text())
    courses: Dict[str, Any] = {}
    for race in manifest["races"]:
        rel = race.get("course") or f"{COURSES_DIR}/{race['id']}.geojson"
        course_path = dest / rel
        if course_path.is_file():
            courses[race["id"]] = json.loads(course_path.read_text(encoding="utf-8"))
    save_plan_package(
        plan_id,
        manifest=manifest,
        locations=locations_doc,
        courses=courses,
    )


def _store_plan_metadata(
    registry: Dict[str, Any],
    manifest: Mapping[str, Any],
    raw_manifest: Mapping[str, Any],
    dest: Path,
    root: Optional[Path],
) -> None:
    """Persist edited name/date on an already-imported revision."""
    from app.core.execute.db import using_postgres

    plan_id = manifest["plan_id"]
    plans = dict(registry.get("plans") or {})
    row = dict(plans.get(plan_id) or {})
    row["name"] = manifest.get("name") or ""
    row["calendar_date"] = manifest["calendar_date"]
    plans[plan_id] = row
    registry["plans"] = plans
    save_registry(registry, root)
    if dest.is_dir():
        (dest / MANIFEST_NAME).write_text(
            json.dumps(dict(raw_manifest), indent=2) + "\n", encoding="utf-8"
        )
        if using_postgres() and root is None:
            _save_package_db(plan_id, manifest, dest)


def import_published_plan(
    archive: bytes,
    root: Optional[Path] = None,
    *,
    name: Optional[str] = None,
    calendar_date: Optional[str] = None,
) -> Dict[str, Any]:
    files, published = _read_package(archive)
    raw_manifest = apply_plan_overrides(
        published, name=name, calendar_date=calendar_date
    )
    edited = raw_manifest != published
    manifest = validate_manifest(raw_manifest)
    _verify_checksums(manifest, files)
    plan_id = manifest["plan_id"]
    revision = int(manifest["revision"])
    dest = plan_revision_dir(plan_id, revision, root)
    registry = load_registry(root)
    existing = (registry.get("plans") or {}).get(plan_id)
    same_revision = int((existing or {}).get("revision") or 0) == revision
    from app.core.execute.db import using_postgres

    already = dest.is_dir()
    if using_postgres() and root is None and existing:
        already = True
    if existing and same_revision and already:
        changed = (existing.get("name") or "") != (manifest.get("name") or "") or (
            existing.get("calendar_date") != manifest["calendar_date"]
        )
        if edited and changed:
            _store_plan_metadata(registry, manifest, raw_manifest, dest, root)
        active_id = registry.get("active_plan_id")
        return {
            "imported": False,
            "idempotent": True,
            "plan_id": plan_id,
            "revision": revision,
            "name": manifest.get("name") or "",
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
    if edited:
        (dest / MANIFEST_NAME).write_text(
            json.dumps(raw_manifest, indent=2) + "\n", encoding="utf-8"
        )
    plans = dict(registry.get("plans") or {})
    plans[plan_id] = {
        "plan_id": plan_id,
        "revision": revision,
        "calendar_date": manifest["calendar_date"],
        "weekday_code": manifest["weekday_code"],
        "name": manifest.get("name") or "",
        "source_run_id": manifest.get("source_run_id") or "",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "archived": bool((existing or {}).get("archived")),
    }
    registry["plans"] = plans
    save_registry(registry, root)
    if using_postgres() and root is None:
        _save_package_db(plan_id, manifest, dest)
    return {
        "imported": True,
        "idempotent": False,
        "plan_id": plan_id,
        "revision": revision,
        "name": manifest.get("name") or "",
        "calendar_date": manifest["calendar_date"],
        "activated": False,
    }


def activate_published_plan(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = assert_uuid(plan_id)
    registry = load_registry(root)
    meta = (registry.get("plans") or {}).get(plan_id)
    if not meta:
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    if meta.get("archived"):
        raise PublishedPlanError("Restore this Day Plan before activating.")
    registry["active_plan_id"] = plan_id
    save_registry(registry, root)
    return load_imported_plan(plan_id, root)


def deactivate_published_plan(root: Optional[Path] = None) -> None:
    registry = load_registry(root)
    registry["active_plan_id"] = None
    save_registry(registry, root)


def archive_published_plan(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = assert_uuid(plan_id)
    registry = load_registry(root)
    plans = dict(registry.get("plans") or {})
    if plan_id not in plans:
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    plans[plan_id] = dict(plans[plan_id])
    plans[plan_id]["archived"] = True
    registry["plans"] = plans
    if registry.get("active_plan_id") == plan_id:
        registry["active_plan_id"] = None
    save_registry(registry, root)
    return plans[plan_id]


def restore_published_plan(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = assert_uuid(plan_id)
    registry = load_registry(root)
    plans = dict(registry.get("plans") or {})
    if plan_id not in plans:
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    plans[plan_id] = dict(plans[plan_id])
    plans[plan_id]["archived"] = False
    registry["plans"] = plans
    save_registry(registry, root)
    return plans[plan_id]


def listed_plans(root: Optional[Path] = None) -> Dict[str, Any]:
    registry = load_registry(root)
    active_id = registry.get("active_plan_id")
    rows = []
    for meta in (registry.get("plans") or {}).values():
        row = dict(meta)
        plan_id = row.get("plan_id")
        archived = bool(row.get("archived"))
        row["archived"] = archived
        row["active"] = (not archived) and plan_id == active_id
        if archived:
            row["status"] = "archived"
        elif row["active"]:
            row["status"] = "active"
        else:
            row["status"] = "inactive"
        rows.append(row)

    def _sort_key(item: Mapping[str, Any]) -> Tuple[int, str]:
        status = str(item.get("status") or "")
        rank = 0 if status == "active" else 1 if status == "inactive" else 2
        return (rank, str(item.get("calendar_date") or ""))

    rows.sort(key=_sort_key)
    return {
        "active_plan_id": active_id,
        "plans": rows,
    }


def operational_state_path(
    plan_id: str,
    root: Optional[Path] = None,
) -> Path:
    plan_id = assert_uuid(plan_id)
    return execute_store_root(root) / plan_id / "execution" / "state.json"


def _guns_from_manifest(manifest: Mapping[str, Any]) -> Dict[str, str]:
    guns: Dict[str, str] = {}
    for race in manifest.get("races") or []:
        race_id = str(race.get("id") or "").strip().lower()
        start = str(race.get("start_time") or "").strip()
        if race_id and start:
            guns[race_id] = start
    return guns


def load_operational_state(
    plan_id: str,
    *,
    day: str,
    manifest: Optional[Mapping[str, Any]] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    from app.core.execute.db import get_blob, using_postgres

    path = operational_state_path(plan_id, root)
    raw = None
    if using_postgres() and root is None:
        raw = get_blob(plan_id, "reopen_state", day)
    if raw is None and path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
    guns = _guns_from_manifest(manifest or {})
    return normalize_state(
        raw,
        run_id=plan_id,
        day=day,
        analysis_guns=guns,
    )


def save_operational_state(
    plan_id: str,
    state: Mapping[str, Any],
    root: Optional[Path] = None,
) -> None:
    from app.core.execute.db import put_blob, using_postgres

    payload = dict(state)
    if using_postgres() and root is None:
        put_blob(plan_id, "reopen_state", str(state.get("day") or ""), payload)
    path = operational_state_path(plan_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def operations_board(
    plan_id: Optional[str] = None,
    root: Optional[Path] = None,
    now_hhmmss: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    plan_id = plan_id or active_plan_id(root)
    if not plan_id:
        return {
            "ok": False,
            "empty": True,
            "detail": "Activate a Day Plan on Execute → Plans.",
            "columns": {
                "closed": [],
                "reopen_next": [],
                "reopened": [],
            },
            "counts": {
                "closed": 0,
                "reopen_next": 0,
                "reopened": 0,
            },
            "courses": {},
            "turnarounds": [],
        }
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    locations_doc = loaded["locations"]
    locations = list(locations_doc.get("locations") or [])
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    if state is None:
        state = load_operational_state(
            plan_id,
            day=day,
            manifest=manifest,
            root=root,
        )
    board = assemble_board(
        locations=locations,
        state=state,
        resources_available=locations_doc.get("resources_available") or [],
        run_id=plan_id,
        day=day,
        now_hhmmss=now_hhmmss,
    )
    board["ok"] = True
    board["empty"] = False
    board["plan_id"] = plan_id
    board["calendar_date"] = manifest.get("calendar_date")
    board["name"] = manifest.get("name") or ""
    board["courses"] = loaded.get("courses") or {}
    board["source_run_id"] = manifest.get("source_run_id") or ""
    board["weekday_code"] = day
    columns = board.get("columns") or {}
    board["counts"] = {
        "closed": len(columns.get("closed") or []),
        "reopen_next": len(columns.get("reopen_next") or []),
        "reopened": len(columns.get("reopened") or []),
    }
    board["turnarounds"] = turnaround_pins(
        locations,
        loaded.get("courses") or {},
    )
    return board


def record_operations_reopen(
    loc_id: int,
    linked_loc_ids: Optional[List[int]] = None,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = active_plan_id(root)
    if not plan_id:
        raise PublishedPlanError("Activate a Day Plan on Execute → Plans.")
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    state = load_operational_state(
        plan_id,
        day=day,
        manifest=manifest,
        root=root,
    )
    record_reopen(
        state,
        loc_id=int(loc_id),
        linked_loc_ids=linked_loc_ids or [],
    )
    save_operational_state(plan_id, state, root)
    return operations_board(plan_id, root=root, state=state)


def record_operations_close(
    loc_id: int,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = active_plan_id(root)
    if not plan_id:
        raise PublishedPlanError("Activate a Day Plan on Execute → Plans.")
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    state = load_operational_state(
        plan_id,
        day=day,
        manifest=manifest,
        root=root,
    )
    record_close(state, loc_id=int(loc_id))
    save_operational_state(plan_id, state, root)
    return operations_board(plan_id, root=root, state=state)


def update_operations_clock(
    payload: Mapping[str, Any],
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = active_plan_id(root)
    if not plan_id:
        raise PublishedPlanError("Activate a Day Plan on Execute → Plans.")
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    state = load_operational_state(
        plan_id,
        day=day,
        manifest=manifest,
        root=root,
    )
    apply_clock_update(state, payload, now_hhmmss=wall_hhmmss())
    save_operational_state(plan_id, state, root)
    return operations_board(plan_id, root=root, state=state)


def operations_reopen_csv(
    root: Optional[Path] = None,
) -> Tuple[str, str]:
    plan_id = active_plan_id(root)
    if not plan_id:
        raise PublishedPlanError("Activate a Day Plan on Execute → Plans.")
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    locations_doc = loaded["locations"]
    locations = list(locations_doc.get("locations") or [])
    available = locations_doc.get("resources_available") or []
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    state = load_operational_state(
        plan_id,
        day=day,
        manifest=manifest,
        root=root,
    )
    rows = build_reopen_rows(
        locations,
        state,
        resources_available=available,
    )
    fieldnames = csv_columns(locations, available)
    date = manifest.get("calendar_date") or "day"
    filename = "execute_reopen_" + str(date) + ".csv"
    return reopen_csv_text(rows, fieldnames), filename


def active_day_context(root: Optional[Path] = None) -> Dict[str, Any]:
    plan_id = active_plan_id(root)
    if not plan_id:
        return {"active": False}
    loaded = load_imported_plan(plan_id, root)
    manifest = loaded["manifest"]
    day = manifest.get("weekday_code") or weekday_code_for_date(
        manifest["calendar_date"]
    )
    return {
        "active": True,
        "plan_id": plan_id,
        "name": manifest.get("name") or "",
        "calendar_date": manifest.get("calendar_date"),
        "weekday_code": day,
        "source_run_id": manifest.get("source_run_id") or "",
    }


def load_imported_plan(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    plan_id = assert_uuid(plan_id)
    registry = load_registry(root)
    meta = (registry.get("plans") or {}).get(plan_id)
    if not meta:
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    dest = plan_revision_dir(plan_id, int(meta["revision"]), root)
    from app.core.execute.db import load_plan_package, using_postgres

    package = None
    if using_postgres() and root is None:
        package = load_plan_package(plan_id)
    if package and package.get("manifest"):
        manifest = validate_manifest(package["manifest"])
        locations_doc = package.get("locations") or {}
        courses = package.get("courses") or {}
    else:
        manifest = validate_manifest(
            json.loads((dest / MANIFEST_NAME).read_text(encoding="utf-8"))
        )
        loc_path = dest / LOCATIONS_NAME
        locations_doc = json.loads(loc_path.read_text(encoding="utf-8"))
        courses = {}
        for race in manifest["races"]:
            rel = race.get("course") or (f"{COURSES_DIR}/{race['id']}.geojson")
            course_path = dest / rel
            if course_path.is_file():
                raw = course_path.read_text(encoding="utf-8")
                courses[race["id"]] = json.loads(raw)
    return {
        "manifest": manifest,
        "locations": locations_doc,
        "courses": courses,
        "directory": str(dest),
        "active": registry.get("active_plan_id") == plan_id,
    }


def loc_sheet_token(loc_id: Any) -> str:
    text = str(loc_id or "").strip()
    if not text or not text.replace("-", "").replace("_", "").isalnum():
        raise PublishedPlanError("Location sheet not found.")
    return text


def loc_sheet_relpath(loc_id: Any) -> str:
    return f"{LOC_SHEETS_DIR}/{loc_sheet_token(loc_id)}.html"


def _location_id_tokens(locations_doc: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for row in locations_doc.get("locations") or []:
        if not isinstance(row, Mapping):
            continue
        raw = row.get("loc_id")
        if raw in (None, ""):
            continue
        tokens.add(str(raw).strip())
    return tokens


def resolve_public_loc_sheet(
    plan_id: str,
    loc_id: str,
    root: Optional[Path] = None,
) -> Path:
    """Path to a packaged volunteer HTML sheet, or raise if it must 404.

    Independent of ``active_plan_id``. Archived plans never expose sheets.
    """
    plan_id = assert_uuid(plan_id)
    token = loc_sheet_token(loc_id)
    registry = load_registry(root)
    meta = (registry.get("plans") or {}).get(plan_id)
    if not meta or meta.get("archived"):
        raise PublishedPlanError("Location sheet not found.")
    loaded = load_imported_plan(plan_id, root)
    if token not in _location_id_tokens(loaded.get("locations") or {}):
        raise PublishedPlanError("Location sheet not found.")
    dest = Path(loaded["directory"]).resolve()
    path = (dest / loc_sheet_relpath(token)).resolve()
    if dest not in path.parents:
        raise PublishedPlanError("Location sheet not found.")
    if not path.is_file():
        raise PublishedPlanError("Location sheet not found.")
    return path


def list_plan_loc_sheets(
    plan_id: str,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Operator index of copyable volunteer URLs for one imported plan."""
    plan_id = assert_uuid(plan_id)
    registry = load_registry(root)
    meta = (registry.get("plans") or {}).get(plan_id)
    if not meta:
        raise PublishedPlanError(f"Published plan {plan_id} is not imported.")
    archived = bool(meta.get("archived"))
    loaded = load_imported_plan(plan_id, root)
    dest = Path(loaded["directory"])
    sheets: List[Dict[str, Any]] = []
    if not archived:
        for row in loaded.get("locations", {}).get("locations") or []:
            if not isinstance(row, Mapping):
                continue
            raw = row.get("loc_id")
            if raw in (None, ""):
                continue
            try:
                token = loc_sheet_token(raw)
                html_path = dest / loc_sheet_relpath(token)
            except PublishedPlanError:
                continue
            if not html_path.is_file():
                continue
            sheets.append(
                {
                    "loc_id": token,
                    "loc_label": row.get("loc_label") or "",
                    "path": f"/locsheets/{plan_id}/{token}",
                }
            )
    return {
        "plan_id": plan_id,
        "archived": archived,
        "sheets": sheets,
    }


def active_plan_id(root: Optional[Path] = None) -> Optional[str]:
    return load_registry(root).get("active_plan_id")


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
    plan_id: Optional[str] = None,
    root: Optional[Path] = None,
    now_hhmmss: Optional[str] = None,
    state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    plan_id = plan_id or active_plan_id(root)
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
    if state is None:
        state = load_operational_state(
            plan_id,
            day=day,
            manifest=manifest,
            root=root,
        )
    available = locations_doc.get("resources_available") or []
    board = assemble_board(
        locations=locations,
        state=state,
        resources_available=available,
        run_id=plan_id,
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
        "plan_id": plan_id,
        "calendar_date": manifest["calendar_date"],
        "weekday_code": manifest.get("weekday_code"),
        "name": manifest.get("name") or "",
        "timezone": manifest.get("timezone") or DISPLAY_TIMEZONE,
        "races": manifest.get("races") or [],
        "courses": loaded["courses"],
        "locations": pins,
        "board": board,
    }
