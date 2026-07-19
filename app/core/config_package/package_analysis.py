"""
Build v2 analyze payloads from Race Configuration packages.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.core.config_package.storage import (
    load_config_manifest,
    package_readiness,
    resolve_config_package_path,
    validate_config_id,
)

# UI-only suggestions when opening the run-analysis dialog (not applied server-side).
SUGGESTED_EVENT_SCHEDULE: Dict[str, Dict[str, int]] = {
    "full": {"start_time": 420, "event_duration_minutes": 390},
    "half": {"start_time": 440, "event_duration_minutes": 180},
    "10k": {"start_time": 460, "event_duration_minutes": 120},
    "elite": {"start_time": 480, "event_duration_minutes": 45},
    "open": {"start_time": 510, "event_duration_minutes": 75},
}


def _format_start_time(minutes: int) -> str:
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    return f"{hours:02d}:{mins:02d}"


def _package_event_ids(manifest: Dict[str, Any]) -> List[str]:
    package_events = manifest.get("package_events") or []
    if not package_events:
        package_events = sorted(
            {
                str(k).strip().lower()
                for k in (manifest.get("assigned_courses") or {}).keys()
                if str(k).strip()
            }
        )
    return [str(ev).strip().lower() for ev in package_events if str(ev).strip()]


def get_package_analyze_setup(config_id: str) -> Dict[str, Any]:
    """Event list and UI suggestions for the run-analysis dialog."""
    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    manifest = load_config_manifest(cid)
    event_day = str(manifest.get("event_day") or "sun").strip().lower() or "sun"
    readiness = package_readiness(package_path)

    events: List[Dict[str, Any]] = []
    for event_id in _package_event_ids(manifest):
        runners_file = f"{event_id}_runners.csv"
        gpx_file = f"{event_id}.gpx"
        suggested = SUGGESTED_EVENT_SCHEDULE.get(event_id, {})
        events.append(
            {
                "name": event_id,
                "day": event_day,
                "runners_file": runners_file,
                "gpx_file": gpx_file,
                "runners_present": (package_path / runners_file).is_file(),
                "gpx_present": (package_path / gpx_file).is_file(),
                "suggested_start_time": suggested.get("start_time"),
                "suggested_start_time_label": (
                    _format_start_time(int(suggested["start_time"]))
                    if suggested.get("start_time") is not None
                    else ""
                ),
                "suggested_event_duration_minutes": suggested.get("event_duration_minutes"),
            }
        )

    return {
        "config_id": cid,
        "event_day": event_day,
        "events": events,
        "readiness": readiness,
        "description": str(manifest.get("label") or cid).strip()[:254],
    }


def build_package_analyze_payload(
    config_id: str,
    *,
    event_schedules: Sequence[Dict[str, Any]],
    description: Optional[str] = None,
    enable_audit: str = "n",
) -> Dict[str, Any]:
    """
    Construct a POST /runflow/v2/analyze payload from a config package folder.

    ``event_schedules`` must include every package event with explicit
    ``start_time`` (minutes after midnight) and ``event_duration_minutes``.
    """
    if not event_schedules:
        raise ValueError("events schedule is required")

    cid = validate_config_id(config_id)
    package_path = resolve_config_package_path(cid)
    readiness = package_readiness(package_path)
    if not readiness.get("analyze_ready"):
        missing = readiness.get("missing") or []
        extras: List[str] = []
        if not readiness.get("has_runners"):
            extras.append("*_runners.csv")
        if not readiness.get("has_gpx"):
            extras.append("*.gpx")
        detail = ", ".join(missing + extras) or "required inputs"
        raise ValueError(f"Package is not analysis-ready (missing: {detail})")

    manifest = load_config_manifest(cid)
    default_day = str(manifest.get("event_day") or "sun").strip().lower() or "sun"
    expected_ids = set(_package_event_ids(manifest))
    if not expected_ids:
        raise ValueError("Package has no events configured (package_events)")

    schedule_by_name: Dict[str, Dict[str, Any]] = {}
    for raw in event_schedules:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip().lower()
        if not name:
            raise ValueError("Each event schedule must include name")
        if name in schedule_by_name:
            raise ValueError(f"Duplicate event in schedule: {name}")
        start_time = raw.get("start_time")
        duration = raw.get("event_duration_minutes")
        if start_time is None or duration is None:
            raise ValueError(f"Event '{name}' requires start_time and event_duration_minutes")
        start_time = int(start_time)
        duration = int(duration)
        if start_time < 300 or start_time > 1200:
            raise ValueError(f"Event '{name}' start_time must be between 300 and 1200 minutes")
        if duration < 1 or duration > 500:
            raise ValueError(
                f"Event '{name}' event_duration_minutes must be between 1 and 500"
            )
        schedule_by_name[name] = {
            "name": name,
            "day": str(raw.get("day") or default_day).strip().lower() or default_day,
            "start_time": start_time,
            "event_duration_minutes": duration,
        }

    missing_events = sorted(expected_ids - set(schedule_by_name.keys()))
    extra_events = sorted(set(schedule_by_name.keys()) - expected_ids)
    if missing_events:
        raise ValueError(f"Missing start-time schedule for: {', '.join(missing_events)}")
    if extra_events:
        raise ValueError(f"Unknown events in schedule: {', '.join(extra_events)}")

    events: List[Dict[str, Any]] = []
    for event_id in _package_event_ids(manifest):
        sched = schedule_by_name[event_id]
        runners_file = f"{event_id}_runners.csv"
        gpx_file = f"{event_id}.gpx"
        if not (package_path / runners_file).is_file():
            raise ValueError(f"Missing runner file: {runners_file}")
        if not (package_path / gpx_file).is_file():
            raise ValueError(f"Missing GPX file: {gpx_file}")
        events.append(
            {
                "name": event_id,
                "day": sched["day"],
                "start_time": sched["start_time"],
                "event_duration_minutes": sched["event_duration_minutes"],
                "runners_file": runners_file,
                "gpx_file": gpx_file,
            }
        )

    by_day: Dict[str, List[str]] = {}
    for event in events:
        by_day.setdefault(str(event["day"]), []).append(str(event["name"]))
    event_group = {
        f"{day}-all": ", ".join(names) for day, names in sorted(by_day.items())
    }

    locations_file = "locations.csv"
    if not (package_path / locations_file).is_file():
        raise ValueError("Missing locations.csv in package root")

    desc = str(description or manifest.get("label") or cid).strip()[:254]

    return {
        "description": desc,
        "data_dir": str(package_path.resolve()),
        "segments_file": "segments.csv",
        "flow_file": "flow.csv",
        "locations_file": locations_file,
        "events": events,
        "event_group": event_group,
        "enableAudit": "y" if str(enable_audit or "n").lower() == "y" else "n",
    }
