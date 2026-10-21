"""Incident store for Execute Health & Safety (Issues #911 / #912)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.core.execute.times import wall_now
from app.core.locations.report_json import (
    locations_report_relpath,
    parse_optional_id,
)

SCHEMA_VERSION = 2
INCIDENTS_FILENAME = "incidents.json"
NOTE_KINDS = frozenset({"system", "user", "transfer"})

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
    ("first_aid", "Care given"),
    ("fluids", "Fluids"),
    ("ice", "Ice"),
    ("sja", "SJA attended"),
    ("other", "Other"),
)
AGENCIES = (
    ("sja", "SJA"),
    ("ski", "SKI"),
    ("yssr", "YSSR"),
    ("ffd", "FFD"),
    ("anb", "ANB"),
    ("fpf", "FPF"),
)
REPORTER_AGENCIES = tuple(
    sorted(
        (
            ("anb", "ANB"),
            ("awp", "AWP"),
            ("ffd", "FFD"),
            ("fpf", "FPF"),
            ("participant", "Participant"),
            ("race_crew", "Race Crew"),
            ("sja", "SJA"),
            ("ski", "Ski"),
            ("spectator", "Spectator"),
            ("volunteer", "Volunteer"),
        ),
        key=lambda item: item[1].casefold(),
    )
)
TRANSFERRED_TO = AGENCIES
OUTCOMES = (
    ("returned_to_course", "Returned to race course"),
    ("left_with_friend_family", "Left with friend / family"),
    ("anb_to_hospital", "Transported to hospital by ANB"),
    ("fm_crew_to_race_site", "Transported to race site by race crew"),
    ("declined_further", "Declined further care"),
    ("dnf", "Did not finish (DNF)"),
    ("other", "Other"),
)
ALLOWED_STATUS = frozenset({"active", "closed"})
ALLOWED_OUTCOMES = frozenset(key for key, _label in OUTCOMES)
ALLOWED_AGENCIES = frozenset(key for key, _label in AGENCIES)
ALLOWED_REPORTERS = frozenset(key for key, _label in REPORTER_AGENCIES)
CATALOG_KEYS = {
    "fm_event": frozenset(key for key, _label in FM_EVENTS),
    "incident_types": frozenset(key for key, _label in INCIDENT_TYPES),
    "care_types": frozenset(key for key, _label in CARE_TYPES),
    "transferred_to": ALLOWED_AGENCIES,
}


class IncidentNotFoundError(KeyError):
    pass


def is_closed(incident: Mapping[str, Any]) -> bool:
    return str(incident.get("incident_status") or "") == "closed"


def require_open(incident: Mapping[str, Any]) -> None:
    if is_closed(incident):
        raise ValueError("Closed incidents are read-only.")


def incidents_relpath(day: str) -> str:
    return f"{day}/execution/{INCIDENTS_FILENAME}"


def catalog() -> Dict[str, List[Dict[str, str]]]:
    def _pairs(items: Sequence[tuple[str, str]]) -> List[Dict[str, str]]:
        return [{"id": key, "label": label} for key, label in items]

    return {
        "fm_event": _pairs(FM_EVENTS),
        "incident_types": _pairs(INCIDENT_TYPES),
        "care_types": _pairs(CARE_TYPES),
        "agencies": _pairs(AGENCIES),
        "reporter_agencies": _pairs(REPORTER_AGENCIES),
        "transferred_to": _pairs(AGENCIES),
        "outcomes": _pairs(OUTCOMES),
    }


def wall_stamp() -> Dict[str, str]:
    now = wall_now()
    return {
        "saved_at": now.isoformat(timespec="seconds"),
        "saved_at_label": now.strftime("%a %H:%M"),
    }


def stamp_label(iso: Any) -> str:
    text = str(iso or "").strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text).strftime("%a %H:%M")
    except ValueError:
        return ""


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


def _clean_agency(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    return key if key in ALLOWED_AGENCIES else ""


def _clean_reporter(raw: Any) -> str:
    key = str(raw or "").strip().lower().replace(" ", "_")
    return key if key in ALLOWED_REPORTERS else ""


def _clean_loc_id(raw: Any) -> str:
    parsed = parse_optional_id(raw)
    return str(parsed) if parsed is not None else ""


def _outcome_label(outcome_id: str) -> str:
    wanted = str(outcome_id or "").strip()
    for key, label in OUTCOMES:
        if key == wanted:
            return label
    return wanted


def agency_label(agency_id: str) -> str:
    wanted = str(agency_id or "").strip().lower()
    if not wanted:
        return "Unassigned"
    for key, label in AGENCIES:
        if key == wanted:
            return label
    return wanted


def reporter_label(agency_id: str) -> str:
    wanted = str(agency_id or "").strip().lower().replace(" ", "_")
    for key, label in REPORTER_AGENCIES:
        if key == wanted:
            return label
    return wanted


def reporter_note_text(name: str, agency_id: str) -> str:
    who = str(name or "").strip()
    agency = _clean_reporter(agency_id)
    if not who or not agency:
        return ""
    return "Reported by " + who + " · " + reporter_label(agency) + "."


def _catalog_diff(
    old_keys: Sequence[Any],
    new_keys: Sequence[Any],
    pairs: Sequence[tuple[str, str]],
) -> tuple[List[str], List[str]]:
    old = {str(item) for item in (old_keys or []) if str(item)}
    new = {str(item) for item in (new_keys or []) if str(item)}
    added = [label for key, label in pairs if key in new - old]
    removed = [label for key, label in pairs if key in old - new]
    return added, removed


def type_care_change_note(
    old_types: Sequence[Any],
    new_types: Sequence[Any],
    old_care: Sequence[Any],
    new_care: Sequence[Any],
    *,
    old_other: str = "",
    new_other: str = "",
) -> str:
    parts: List[str] = []
    type_added, type_removed = _catalog_diff(old_types, new_types, INCIDENT_TYPES)
    care_added, care_removed = _catalog_diff(old_care, new_care, CARE_TYPES)
    if type_added:
        parts.append("Type added: " + ", ".join(type_added) + ".")
    if type_removed:
        parts.append("Type removed: " + ", ".join(type_removed) + ".")
    other_text = str(new_other or "").strip()
    if other_text and other_text != str(old_other or "").strip():
        parts.append("Type other: " + other_text + ".")
    if care_added:
        parts.append("Care added: " + ", ".join(care_added) + ".")
    if care_removed:
        parts.append("Care removed: " + ", ".join(care_removed) + ".")
    return " ".join(parts)


def _touch(incident: Dict[str, Any], stamp: Optional[Mapping[str, str]] = None) -> None:
    used = dict(stamp or wall_stamp())
    incident["updated_at"] = used["saved_at"]
    incident["updated_at_label"] = used["saved_at_label"]


def empty_incident(*, reg_id: str) -> Dict[str, Any]:
    stamp = wall_stamp()
    incident: Dict[str, Any] = {
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
        "location_loc_id": "",
        "description": "",
        "incident_types": [],
        "incident_type_note": "",
        "incident_type_other": "",
        "care_types": [],
        "care_note": "",
        "care_transferred": "",
        "care_transferred_at": "",
        "transferred_to": [],
        "reported_by_name": "",
        "reported_by_agency": "",
        "assigned_to": "",
        "called_911": "",
        "called_911_at": "",
        "outcome": "",
        "completed_by_name": "",
        "completed_by_agency": "",
        "notes": [],
        "opened_at": stamp["saved_at"],
        "opened_at_label": stamp["saved_at_label"],
        "updated_at": stamp["saved_at"],
        "updated_at_label": stamp["saved_at_label"],
        "closed_at": None,
        "closed_at_label": None,
    }
    append_note(incident, "Opened.", kind="system")
    return incident


def normalize_incident(incident: Dict[str, Any]) -> Dict[str, Any]:
    """Fill v2 fields on read. Old type notes become description; old transfer flags stay hidden."""
    defaults = {
        "description": "",
        "reported_by_name": "",
        "reported_by_agency": "",
        "assigned_to": "",
        "location_loc_id": "",
        "incident_type_other": "",
        "updated_at_label": "",
    }
    for key, value in defaults.items():
        if incident.get(key) is None:
            incident[key] = value
    desc = str(incident.get("description") or "").strip()
    old_note = str(incident.get("incident_type_note") or "").strip()
    if not desc and old_note:
        incident["description"] = old_note
    incident["assigned_to"] = _clean_agency(incident.get("assigned_to"))
    incident["location_loc_id"] = _clean_loc_id(incident.get("location_loc_id"))
    if not str(incident.get("updated_at_label") or "").strip():
        incident["updated_at_label"] = (
            stamp_label(incident.get("updated_at"))
            or str(incident.get("opened_at_label") or "").strip()
        )
    notes = incident.get("notes")
    if isinstance(notes, list):
        for note in notes:
            if not isinstance(note, dict):
                continue
            kind = str(note.get("kind") or "user").strip().lower()
            note["kind"] = kind if kind in NOTE_KINDS else "user"
    return incident


def apply_fields(
    incident: Dict[str, Any],
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    require_open(incident)
    old_desc = str(incident.get("description") or "").strip()
    old_911 = _clean_yes_no(incident.get("called_911"))
    old_assigned = _clean_agency(incident.get("assigned_to"))
    old_reporter_name = str(incident.get("reported_by_name") or "").strip()
    old_reporter_agency = _clean_reporter(incident.get("reported_by_agency"))
    old_types = list(incident.get("incident_types") or [])
    old_care = list(incident.get("care_types") or [])
    old_other = str(incident.get("incident_type_other") or "").strip()
    changed = False
    text_fields = (
        "bib",
        "given_name",
        "family_name",
        "age",
        "sex",
        "sub_event",
        "location_text",
        "description",
        "incident_type_note",
        "incident_type_other",
        "care_note",
        "care_transferred_at",
        "called_911_at",
        "completed_by_name",
        "reported_by_name",
    )
    for field in text_fields:
        if field in payload and payload.get(field) is not None:
            new_val = str(payload.get(field) or "").strip()
            if str(incident.get(field) or "").strip() != new_val:
                incident[field] = new_val
                changed = True
    if "location_loc_id" in payload:
        new_loc = _clean_loc_id(payload.get("location_loc_id"))
        if incident.get("location_loc_id") != new_loc:
            incident["location_loc_id"] = new_loc
            changed = True
    if "reported_by_agency" in payload:
        new_reporter = _clean_reporter(payload.get("reported_by_agency"))
        if incident.get("reported_by_agency") != new_reporter:
            incident["reported_by_agency"] = new_reporter
            changed = True
    if "completed_by_agency" in payload and payload.get("completed_by_agency") is not None:
        new_completed = _clean_reporter(payload.get("completed_by_agency"))
        if str(incident.get("completed_by_agency") or "") != new_completed:
            incident["completed_by_agency"] = new_completed
            changed = True
    if "assigned_to" in payload:
        new_assigned = _clean_agency(payload.get("assigned_to"))
        if new_assigned != old_assigned:
            changed = True
            if old_assigned and new_assigned:
                transfer_care(incident, new_assigned)
            elif old_assigned and not new_assigned:
                incident["assigned_to"] = ""
                append_note(
                    incident,
                    "Transferred " + agency_label(old_assigned) + " → Unassigned.",
                    kind="transfer",
                )
            else:
                incident["assigned_to"] = new_assigned
    list_fields = (
        ("fm_event", CATALOG_KEYS["fm_event"]),
        ("incident_types", CATALOG_KEYS["incident_types"]),
        ("care_types", CATALOG_KEYS["care_types"]),
        ("transferred_to", CATALOG_KEYS["transferred_to"]),
    )
    for field, allowed in list_fields:
        if field in payload:
            cleaned = _clean_list(payload.get(field), allowed)
            if list(incident.get(field) or []) != cleaned:
                incident[field] = cleaned
                changed = True
    if "care_transferred" in payload:
        new_xfer = _clean_yes_no(payload.get("care_transferred"))
        if incident.get("care_transferred") != new_xfer:
            incident["care_transferred"] = new_xfer
            changed = True
    if "called_911" in payload:
        new_911 = _clean_yes_no(payload.get("called_911"))
        if incident.get("called_911") != new_911:
            incident["called_911"] = new_911
            changed = True
    if "outcome" in payload and payload.get("outcome") is not None:
        outcome = str(payload.get("outcome") or "").strip()
        outcome = outcome if outcome in ALLOWED_OUTCOMES else ""
        if incident.get("outcome") != outcome:
            incident["outcome"] = outcome
            changed = True
    if not changed:
        return incident
    _touch(incident)
    new_desc = str(incident.get("description") or "").strip()
    if new_desc and not old_desc:
        append_note(incident, new_desc, kind="user")
    if incident.get("called_911") == "yes" and old_911 != "yes":
        append_note(incident, "911 called.", kind="system")
    new_reporter_name = str(incident.get("reported_by_name") or "").strip()
    new_reporter_agency = _clean_reporter(incident.get("reported_by_agency"))
    reported = reporter_note_text(new_reporter_name, new_reporter_agency)
    if reported and (
        new_reporter_name != old_reporter_name
        or new_reporter_agency != old_reporter_agency
    ):
        append_note(incident, reported, kind="system")
    care_note = type_care_change_note(
        old_types,
        incident.get("incident_types") or [],
        old_care,
        incident.get("care_types") or [],
        old_other=old_other,
        new_other=str(incident.get("incident_type_other") or "").strip(),
    )
    if care_note:
        append_note(incident, care_note, kind="system")
    return incident


def append_note(
    incident: Dict[str, Any],
    text: str,
    *,
    kind: str = "user",
) -> Dict[str, Any]:
    body = str(text or "").strip()
    if not body:
        raise ValueError("Note text is required.")
    stamp = wall_stamp()
    kind_key = str(kind or "user").strip().lower()
    if kind_key not in NOTE_KINDS:
        kind_key = "user"
    notes = list(incident.get("notes") or [])
    notes.append(
        {
            "text": body,
            "kind": kind_key,
            "saved_at": stamp["saved_at"],
            "saved_at_label": stamp["saved_at_label"],
        }
    )
    incident["notes"] = notes
    _touch(incident, stamp)
    return incident


def transfer_care(
    incident: Dict[str, Any],
    to_agency: str,
    text: str = "",
) -> Dict[str, Any]:
    require_open(incident)
    to_key = _clean_agency(to_agency)
    if not to_key:
        raise ValueError("Unknown care agency.")
    from_key = _clean_agency(incident.get("assigned_to"))
    if from_key == to_key:
        raise ValueError("Already assigned to that care agency.")
    extra = str(text or "").strip()
    note = (
        "Transferred "
        + agency_label(from_key)
        + " → "
        + agency_label(to_key)
        + "."
    )
    if extra:
        note = note + " " + extra
    incident["assigned_to"] = to_key
    append_note(incident, note, kind="transfer")
    return incident


def close_incident(incident: Dict[str, Any]) -> Dict[str, Any]:
    stamp = wall_stamp()
    incident["incident_status"] = "closed"
    incident["closed_at"] = stamp["saved_at"]
    incident["closed_at_label"] = stamp["saved_at_label"]
    _touch(incident, stamp)
    outcome = _outcome_label(str(incident.get("outcome") or ""))
    text = "Closed · " + outcome + "." if outcome else "Closed."
    append_note(incident, text, kind="system")
    return incident


def location_catalog(storage: Any, day: str) -> List[Dict[str, Any]]:
    path = locations_report_relpath(day)
    if not storage.exists(path):
        return []
    try:
        payload = storage.read_json(path)
    except Exception:
        return []
    rows = payload.get("locations") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    seen: set[Any] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        loc_id = parse_optional_id(row.get("loc_id"))
        label = str(row.get("loc_label") or "").strip()
        if not label:
            continue
        key = loc_id if loc_id is not None else label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "loc_id": loc_id,
                "loc_label": label,
                "zone": str(row.get("zone") or "").strip(),
            }
        )
    return out


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
        normalize_incident(dict(item))
        for item in items
        if isinstance(item, Mapping)
    ]
    if raw.get("run_id"):
        store["run_id"] = str(raw.get("run_id"))
    return store


def persist_store(storage: Any, day: str, store: Mapping[str, Any]) -> str:
    payload = dict(store)
    payload["schema_version"] = SCHEMA_VERSION
    return storage.write_json(incidents_relpath(day), payload)


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
