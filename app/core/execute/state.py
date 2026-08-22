"""Execution JSON store (Issue #893). Mutations never touch Plan loc_end."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from app.core.locations.report_json import parse_optional_id
from app.core.execute.times import analysis_guns_hhmm, wall_hhmm
from app.utils.constants import DISPLAY_TIMEZONE

SCHEMA_VERSION = 1
STATE_FILENAME = "state.json"


def execution_state_relpath(day: str) -> str:
    return f"{day}/execution/{STATE_FILENAME}"


def empty_clock(
    analysis_guns: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    guns = dict(analysis_guns or {})
    return {
        "guns_accepted": False,
        "guns_source": "analysis",
        "analysis_guns": guns,
        "guns": dict(guns),
        "paused": False,
        "paused_at": None,
    }


def empty_state(
    *,
    run_id: str,
    day: str,
    analysis_guns: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "day": (day or "").strip().lower(),
        "timezone": DISPLAY_TIMEZONE,
        "clock": empty_clock(analysis_guns),
        "reopened": {},
        "activity": [],
    }


def normalize_state(
    raw: Optional[Mapping[str, Any]],
    *,
    run_id: str,
    day: str,
    analysis_guns: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    base = empty_state(
        run_id=run_id,
        day=day,
        analysis_guns=analysis_guns,
    )
    if not raw:
        return base
    raw_clock = raw.get("clock")
    clock_in = raw_clock if isinstance(raw_clock, Mapping) else {}
    clock = base["clock"]
    if isinstance(clock_in, Mapping):
        if "guns_accepted" in clock_in:
            clock["guns_accepted"] = bool(clock_in.get("guns_accepted"))
        if clock_in.get("guns_source") in ("analysis", "override"):
            clock["guns_source"] = clock_in.get("guns_source")
        if isinstance(clock_in.get("analysis_guns"), Mapping):
            clock["analysis_guns"] = {
                str(k).lower(): str(v)
                for k, v in clock_in["analysis_guns"].items()
                if v
            }
        elif analysis_guns:
            clock["analysis_guns"] = dict(analysis_guns)
        if isinstance(clock_in.get("guns"), Mapping):
            clock["guns"] = {
                str(k).lower(): str(v)
                for k, v in clock_in["guns"].items()
                if v
            }
        clock["paused"] = bool(clock_in.get("paused"))
        paused_at = clock_in.get("paused_at")
        clock["paused_at"] = str(paused_at) if paused_at else None
    raw_reopened = raw.get("reopened")
    reopened_in = raw_reopened if isinstance(raw_reopened, Mapping) else {}
    reopened: Dict[str, Any] = {}
    if isinstance(reopened_in, Mapping):
        for key, entry in reopened_in.items():
            loc_id = parse_optional_id(key)
            if loc_id is None or not isinstance(entry, Mapping):
                continue
            reopened[str(loc_id)] = {
                "loc_id": loc_id,
                "reopened_at": entry.get("reopened_at"),
                "operator": None,
                "primary_loc_id": parse_optional_id(
                    entry.get("primary_loc_id")
                ),
                "linked_from": parse_optional_id(entry.get("linked_from")),
            }
    raw_activity = raw.get("activity")
    activity_in = raw_activity if isinstance(raw_activity, list) else []
    activity: List[Dict[str, Any]] = []
    for item in activity_in:
        if isinstance(item, Mapping):
            activity.append(dict(item))
    base["clock"] = clock
    base["reopened"] = reopened
    base["activity"] = activity
    if raw.get("run_id"):
        base["run_id"] = str(raw.get("run_id"))
    return base


def load_or_create_state(
    storage: Any,
    *,
    run_id: str,
    day: str,
    analysis: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    guns = analysis_guns_hhmm(analysis or {})
    path = execution_state_relpath(day)
    raw = None
    if storage.exists(path):
        try:
            loaded = storage.read_json(path)
            if isinstance(loaded, Mapping):
                raw = loaded
        except Exception:
            raw = None
    state = normalize_state(raw, run_id=run_id, day=day, analysis_guns=guns)
    if not state["clock"].get("analysis_guns") and guns:
        state["clock"]["analysis_guns"] = dict(guns)
        if not state["clock"].get("guns"):
            state["clock"]["guns"] = dict(guns)
    return state


def persist_state(storage: Any, day: str, state: Mapping[str, Any]) -> str:
    return storage.write_json(execution_state_relpath(day), dict(state))


def apply_clock_update(
    state: MutableMapping[str, Any],
    payload: Mapping[str, Any],
    *,
    now_hhmmss: str,
) -> Dict[str, Any]:
    clock = state.setdefault("clock", empty_clock())
    if "guns_accepted" in payload:
        clock["guns_accepted"] = bool(payload.get("guns_accepted"))
    guns = payload.get("guns")
    if isinstance(guns, Mapping) and guns:
        cleaned = {str(k).lower(): str(v) for k, v in guns.items() if v}
        clock["guns"] = cleaned
        analysis = clock.get("analysis_guns") or {}
        clock["guns_source"] = (
            "override" if cleaned != dict(analysis) else "analysis"
        )
        clock["guns_accepted"] = True
    if payload.get("jump_to_now"):
        clock["paused"] = False
        clock["paused_at"] = None
    elif "paused" in payload:
        paused = bool(payload.get("paused"))
        clock["paused"] = paused
        clock["paused_at"] = now_hhmmss if paused else None
    state["clock"] = clock
    return state


def record_reopen(
    state: MutableMapping[str, Any],
    *,
    loc_id: int,
    linked_loc_ids: Sequence[int],
    at_hhmm: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persist reopen for the primary location and selected linked ids.

    Already-reopened ids are left unchanged. Operator is always null.
    """
    stamp = at_hhmm or wall_hhmm()
    reopened = state.setdefault("reopened", {})
    activity = state.setdefault("activity", [])
    applied: List[int] = []

    def _stamp(target: int, linked_from: Optional[int]) -> bool:
        key = str(target)
        if key in reopened:
            return False
        reopened[key] = {
            "loc_id": target,
            "reopened_at": stamp,
            "operator": None,
            "primary_loc_id": loc_id,
            "linked_from": linked_from,
        }
        applied.append(target)
        return True

    primary_new = _stamp(loc_id, None)
    linked_applied: List[int] = []
    for linked in linked_loc_ids:
        lid = parse_optional_id(linked)
        if lid is None or lid == loc_id:
            continue
        if _stamp(lid, loc_id):
            linked_applied.append(lid)
    if primary_new or linked_applied:
        activity.append(
            {
                "at": stamp,
                "action": "reopen",
                "loc_id": loc_id,
                "linked_loc_ids": linked_applied,
                "operator": None,
            }
        )
    state["reopened"] = reopened
    state["activity"] = activity
    return {
        "applied": applied,
        "already_reopened": not primary_new,
        "reopened_at": stamp,
    }
