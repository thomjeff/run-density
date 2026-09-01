"""Incident store for Execute Health & Safety (Issue #911)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.core.execute.times import wall_now

SCHEMA_VERSION = 1
INCIDENTS_FILENAME = "incidents.json"

FM_EVENTS = (
    ("5k_elite", "5K Elite"),
    ("5k_open", "5K Open"),
    ("youth_fun_run", "Youth Fun Run"),
    ("10k", "10K"),
    ("half", "Half"),
    ("full", "Full"),
)
INCIDENT_TYPES = (
    ("blister_skin", "Blister / skin"),
    ("heat_dehydration", "Heat / dehydration"),
    ("musculoskeletal", "Musculoskeletal"),
    ("respiratory", "Respiratory"),
    ("cardiac", "Cardiac"),
    ("other", "Other"),
)
CARE_TYPES = (
    ("first_aid", "First aid"),
    ("fluids", "Fluids"),
    ("ice", "Ice"),
    ("sja", "SJA"),
    ("other", "Other"),
)
TRANSFERRED_TO = (
    ("sja", "SJA"),
    ("ski", "SKI"),
    ("yssr", "YSSR"),
    ("ffd", "FFD"),
    ("anb", "ANB"),
    ("fpf", "FPF"),
)
OUTCOMES = (
    ("returned_to_course", "Returned to course"),
    ("left_with_friend_family", "Left with friend / family"),
    ("anb_to_hospital", "ANB to hospital"),
    ("fm_crew_to_race_site", "FM crew to race site"),
    ("declined_further", "Declined further"),
    ("dnf", "DNF"),
    ("other", "Other"),
)
ALLOWED_STATUS = frozenset({"active", "closed"})
ALLOWED_OUTCOMES = frozenset(key for key, _label in OUTCOMES)
CATALOG_KEYS = {
    "fm_event": frozenset(key for key, _label in FM_EVENTS),
    "incident_types": frozenset(key for key, _label in INCIDENT_TYPES),
    "care_types": frozenset(key for key, _label in CARE_TYPES),
    "transferred_to": frozenset(key for key, _label in TRANSFERRED_TO),
}


class IncidentNotFoundError(KeyError):
    pass


def incidents_relpath(day: str) -> str:
    return f"{day}/execution/{INCIDENTS_FILENAME}"


def catalog() -> Dict[str, List[Dict[str, str]]]:
    def _pairs(items: Sequence[tuple[str, str]]) -> List[Dict[str, str]]:
        return [{"id": key, "label": label} for key, label in items]

    return {
        "fm_event": _pairs(FM_EVENTS),
        "incident_types": _pairs(INCIDENT_TYPES),
        "care_types": _pairs(CARE_TYPES),
        "transferred_to": _pairs(TRANSFERRED_TO),
        "outcomes": _pairs(OUTCOMES),
    }


def wall_stamp() -> Dict[str, str]:
    now = wall_now()
    return {
        "saved_at": now.isoformat(timespec="seconds"),
        "saved_at_label": now.strftime("%a %H:%M"),
    }


def empty_store(*, run_id: str, day: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "day": (day or "").strip().lower(),
        "incidents": [],
    }


def new_incident_id() -> str:
    return "inc_" + uuid.uuid4().hex[:12]


def _clean_list(raw: Any, allowed: frozenset[str]) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    seen = set()
    for item in raw:
        key = str(item or "").strip()
        if not key or key not in allowed or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _clean_yes_no(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    if text in ("yes", "y", "true", "1"):
        return "yes"
    if text in ("no", "n", "false", "0"):
        return "no"
    return ""


def empty_incident(*, reg_id: str) -> Dict[str, Any]:
    stamp = wall_stamp()
    return {
        "incident_id": new_incident_id(),
        "reg_id": str(reg_id or "").strip(),
        "incident_status": "active",
        "bib": "",
        "given_name": "",
        "family_name": "",
        "age": "",
        "sex": "",
        "sub_event": "",
        "fm_event": [],
        "location_text": "",
        "incident_types": [],
        "incident_type_note": "",
        "care_types": [],
        "care_note": "",
        "care_transferred": "",
        "care_transferred_at": "",
        "transferred_to": [],
        "called_911": "",
        "called_911_at": "",
        "outcome": "",
        "completed_by_name": "",
        "completed_by_agency": "",
        "notes": [],
        "opened_at": stamp["saved_at"],
        "opened_at_label": stamp["saved_at_label"],
        "updated_at": stamp["saved_at"],
        "closed_at": None,
        "closed_at_label": None,
    }


def apply_fields(incident: Dict[str, Any], payload: Mapping[str, Any]) -> Dict[str, Any]:
    text_fields = (
        "bib",
        "given_name",
        "family_name",
        "age",
        "sex",
        "sub_event",
        "location_text",
        "incident_type_note",
        "care_note",
        "care_transferred_at",
        "called_911_at",
        "completed_by_name",
        "completed_by_agency",
    )
    for field in text_fields:
        if field in payload and payload.get(field) is not None:
            incident[field] = str(payload.get(field) or "").strip()
    if "fm_event" in payload:
        incident["fm_event"] = _clean_list(
            payload.get("fm_event"), CATALOG_KEYS["fm_event"]
        )
    if "incident_types" in payload:
        incident["incident_types"] = _clean_list(
            payload.get("incident_types"), CATALOG_KEYS["incident_types"]
        )
    if "care_types" in payload:
        incident["care_types"] = _clean_list(
            payload.get("care_types"), CATALOG_KEYS["care_types"]
        )
    if "transferred_to" in payload:
        incident["transferred_to"] = _clean_list(
            payload.get("transferred_to"), CATALOG_KEYS["transferred_to"]
        )
    if "care_transferred" in payload:
        incident["care_transferred"] = _clean_yes_no(payload.get("care_transferred"))
    if "called_911" in payload:
        incident["called_911"] = _clean_yes_no(payload.get("called_911"))
    if "outcome" in payload and payload.get("outcome") is not None:
        outcome = str(payload.get("outcome") or "").strip()
        incident["outcome"] = outcome if outcome in ALLOWED_OUTCOMES else ""
    stamp = wall_stamp()
    incident["updated_at"] = stamp["saved_at"]
    return incident


def append_note(incident: Dict[str, Any], text: str) -> Dict[str, Any]:
    body = str(text or "").strip()
    if not body:
        raise ValueError("Note text is required.")
    stamp = wall_stamp()
    notes = list(incident.get("notes") or [])
    notes.append(
        {
            "text": body,
            "saved_at": stamp["saved_at"],
            "saved_at_label": stamp["saved_at_label"],
        }
    )
    incident["notes"] = notes
    incident["updated_at"] = stamp["saved_at"]
    return incident


def close_incident(incident: Dict[str, Any]) -> Dict[str, Any]:
    stamp = wall_stamp()
    incident["incident_status"] = "closed"
    incident["closed_at"] = stamp["saved_at"]
    incident["closed_at_label"] = stamp["saved_at_label"]
    incident["updated_at"] = stamp["saved_at"]
    return incident


def load_store(storage: Any, *, run_id: str, day: str) -> Dict[str, Any]:
    path = incidents_relpath(day)
    raw = None
    if storage.exists(path):
        try:
            loaded = storage.read_json(path)
            if isinstance(loaded, Mapping):
                raw = loaded
        except Exception:
            raw = None
    store = empty_store(run_id=run_id, day=day)
    if not raw:
        return store
    items = raw.get("incidents") if isinstance(raw.get("incidents"), list) else []
    store["incidents"] = [
        dict(item) for item in items if isinstance(item, Mapping)
    ]
    if raw.get("run_id"):
        store["run_id"] = str(raw.get("run_id"))
    return store


def persist_store(storage: Any, day: str, store: Mapping[str, Any]) -> str:
    return storage.write_json(incidents_relpath(day), dict(store))


def find_incident(store: Mapping[str, Any], incident_id: str) -> Dict[str, Any]:
    wanted = str(incident_id or "").strip()
    for item in store.get("incidents") or []:
        if str(item.get("incident_id") or "") == wanted:
            return item
    raise IncidentNotFoundError(wanted)


def display_bib(incident: Mapping[str, Any], roster_row: Optional[Mapping[str, Any]]) -> str:
    if roster_row and str(roster_row.get("bib") or "").strip():
        return str(roster_row.get("bib") or "").strip()
    return str(incident.get("bib") or "").strip()
