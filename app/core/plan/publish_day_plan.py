"""Publish one planning-scenario day as an immutable package (#917)."""

from __future__ import annotations

import copy
import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, List, Mapping, Optional
from uuid import uuid4

from app.core.execute.published_plan import (
    COURSES_DIR,
    LOCATIONS_NAME,
    MANIFEST_NAME,
    SCHEMA_VERSION,
    PublishedPlanError,
    assert_date_matches_weekday,
    parse_calendar_date,
    race_display_name,
    sha256_bytes,
    weekday_code_for_date,
)
from app.core.locations.report_json import locations_report_relpath
from app.routes.api_segments import convert_geometry_to_wgs84
from app.storage import create_runflow_storage
from app.utils.constants import COURSE_EVENT_IDS, DISPLAY_TIMEZONE
from app.utils.run_id import get_run_directory


def _read_analysis(run_id: str) -> Dict[str, Any]:
    path = get_run_directory(run_id) / "analysis.json"
    if not path.exists():
        raise PublishedPlanError(
            f"Planning scenario {run_id} has no analysis.json."
        )
    from app.config.loader import load_analysis_config_readonly

    return dict(load_analysis_config_readonly(get_run_directory(run_id)))


def _events_for_day(
    analysis: Mapping[str, Any],
    day: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for event in analysis.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        if str(event.get("day") or "").strip().lower() != day:
            continue
        race_id = str(event.get("name") or "").strip().lower()
        if race_id not in COURSE_EVENT_IDS:
            continue
        out.append(dict(event))
    return out


def _load_locations(run_id: str, day: str) -> Dict[str, Any]:
    storage = create_runflow_storage(run_id)
    rel = locations_report_relpath(day)
    if not storage.exists(rel):
        raise PublishedPlanError(
            f"No locations_report.json for day={day}."
        )
    payload = storage.read_json(rel)
    locations = payload.get("locations") or []
    if not isinstance(locations, list):
        raise PublishedPlanError("locations_report.json is invalid.")
    return payload


def _looks_like_wgs84(geometry: Mapping[str, Any]) -> bool:
    coords = geometry.get("coordinates")
    sample = coords
    while isinstance(sample, list) and sample and isinstance(sample[0], list):
        sample = sample[0]
    if not (isinstance(sample, list) and len(sample) >= 2):
        return False
    try:
        x, y = float(sample[0]), float(sample[1])
    except (TypeError, ValueError):
        return False
    return abs(x) <= 180.0 and abs(y) <= 90.0


def _wgs84_feature_collection(raw: Mapping[str, Any]) -> Dict[str, Any]:
    doc = copy.deepcopy(dict(raw))
    features = []
    for feature in doc.get("features") or []:
        if not isinstance(feature, Mapping):
            continue
        item = copy.deepcopy(dict(feature))
        geom = item.get("geometry")
        if isinstance(geom, dict) and not _looks_like_wgs84(geom):
            item["geometry"] = convert_geometry_to_wgs84(
                copy.deepcopy(geom)
            )
        features.append(item)
    return {"type": "FeatureCollection", "features": features}


def _course_from_segments(
    run_id: str,
    day: str,
    race_id: str,
) -> Dict[str, Any]:
    storage = create_runflow_storage(run_id)
    rel = f"{day}/ui/geospatial/segments.geojson"
    if not storage.exists(rel):
        return {"type": "FeatureCollection", "features": []}
    raw = storage.read_json(rel)
    if not isinstance(raw, dict):
        return {"type": "FeatureCollection", "features": []}
    filtered = {
        "type": "FeatureCollection",
        "features": [],
    }
    for feature in raw.get("features") or []:
        if not isinstance(feature, Mapping):
            continue
        props = feature.get("properties") or {}
        events = props.get("events") or props.get("event") or []
        if isinstance(events, str):
            events = [events]
        names = {str(item).strip().lower() for item in events}
        if names and race_id not in names:
            continue
        filtered["features"].append(dict(feature))
    return _wgs84_feature_collection(filtered)


def _location_export_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "loc_id": row.get("loc_id"),
        "loc_label": row.get("loc_label") or "",
        "loc_type": row.get("loc_type") or "",
        "zone": row.get("zone"),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "loc_start": row.get("loc_start"),
        "loc_end": row.get("loc_end"),
        "proxy_loc_id": row.get("proxy_loc_id"),
        "proxy_pass_id": row.get("proxy_pass_id"),
        **{
            key: row.get(key)
            for key in row
            if str(key).endswith("_count")
        },
        "by_event": row.get("by_event") or {},
    }


def build_published_plan_files(
    *,
    run_id: str,
    day: str,
    calendar_date: str,
    name: Optional[str] = None,
    event_series: Optional[str] = None,
    event_edition: Optional[str] = None,
    published_plan_id: Optional[str] = None,
    revision: int = 1,
) -> Dict[str, bytes]:
    parse_calendar_date(calendar_date)
    weekday = assert_date_matches_weekday(calendar_date, day)
    analysis = _read_analysis(run_id)
    events = _events_for_day(analysis, weekday)
    if not events:
        raise PublishedPlanError(
            f"No Build-catalog races on {weekday} in this scenario."
        )
    report = _load_locations(run_id, weekday)
    locations_doc = {
        "locations": [
            _location_export_row(row)
            for row in report.get("locations") or []
            if isinstance(row, Mapping)
        ],
        "resources_available": report.get("resources_available") or [],
    }
    files: Dict[str, bytes] = {}
    races = []
    for event in events:
        race_id = str(event.get("name")).strip().lower()
        course = _course_from_segments(run_id, weekday, race_id)
        rel = f"{COURSES_DIR}/{race_id}.geojson"
        files[rel] = json.dumps(course).encode("utf-8")
        races.append(
            {
                "id": race_id,
                "name": race_display_name(race_id),
                "start_time": event.get("start_time"),
                "duration_minutes": event.get(
                    "event_duration_minutes"
                ),
                "course": rel,
            }
        )
    files[LOCATIONS_NAME] = json.dumps(locations_doc).encode("utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "published_plan_id": published_plan_id or str(uuid4()),
        "revision": int(revision),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "calendar_date": calendar_date,
        "weekday_code": weekday,
        "name": name
        or f"{event_edition or 'Day plan'} {calendar_date}",
        "event_series": event_series or "",
        "event_edition": event_edition or "",
        "timezone": DISPLAY_TIMEZONE,
        "source_run_id": run_id,
        "source_config_id": analysis.get("config_id")
        or analysis.get("package_id")
        or "",
        "races": races,
        "files": [],
    }
    manifest["files"] = [
        {"path": path, "sha256": sha256_bytes(payload)}
        for path, payload in sorted(files.items())
    ]
    files[MANIFEST_NAME] = json.dumps(
        manifest, indent=2, sort_keys=True
    ).encode("utf-8")
    return files


def publish_day_plan_zip(**kwargs: Any) -> bytes:
    files = build_published_plan_files(**kwargs)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in files.items():
            zf.writestr(name, payload)
    return buffer.getvalue()
