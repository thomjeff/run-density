"""Incident store for Execute Health & Safety (Issues #911 / #912 / #914).

Reported-problem and care catalogs have not been reviewed by first-aid
agencies (#914). They are reports of what the EOC was told, not diagnoses
or treatment orders.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.core.execute.times import wall_now
from app.core.locations.report_json import (
    locations_report_relpath,
    parse_optional_id,
)

SCHEMA_VERSION = 3
INCIDENTS_FILENAME = "incidents.json"
NOTE_KINDS = frozenset({"system", "user", "transfer"})
NOT_YET_KNOWN = "not_yet_known"
EXCLUSIVE_CARE = frozenset(
    {"no_care_as_reported", "care_details_not_known"}
)
SHARED_CARE = (
    "assessed_by_agency",
    "observation",
    "other_care",
    "no_care_as_reported",
    "care_details_not_known",
)

FM_EVENTS = (
    ("5k_elite", "5K Elite"),
    ("5k_open", "5K Open"),
    ("youth_fun_run", "Youth Fun Run"),
    ("10k", "10K"),
    ("half", "Half"),
    ("full", "Full"),
)
INCIDENT_TYPES = (
    ("fall_collision_injury", "Fall / collision / injury"),
    ("blister_chafing_skin", "Blister / chafing / skin problem"),
    ("muscle_joint_cramp", "Muscle / joint pain or cramp"),
    ("dizziness_fainting_collapse", "Dizziness / fainting / collapse"),
    ("exhaustion", "Exhaustion / unable to continue"),
    ("heat_concern", "Feeling overheated / heat concern"),
    ("cold_exposure", "Feeling cold / cold exposure"),
    ("breathing_difficulty", "Breathing difficulty"),
    ("chest_pain_heart", "Chest pain / heart-related concern"),
    ("nausea_stomach", "Nausea / vomiting / stomach complaint"),
    ("confusion_altered", "Confusion / altered responsiveness"),
    ("other", "Other"),
    (NOT_YET_KNOWN, "Not yet known"),
)
CARE_TYPES = (
    ("wound_cleaned", "Wound cleaned"),
    ("dressing_bandage", "Dressing / bandage applied"),
    ("bleeding_control", "Bleeding control"),
    ("injury_support", "Injury support / immobilization"),
    ("blister_skin_care", "Blister / skin care"),
    ("dressing_covering", "Dressing / protective covering applied"),
    ("rest_recovery", "Rest / recovery support"),
    ("ice_cold_pack", "Ice / cold pack applied"),
    ("assisted_to_rest", "Assisted to rest"),
    ("observation", "Observation / monitoring"),
    ("assessed_by_agency", "Assessed by care agency"),
    ("fluids_provided", "Fluids provided"),
    ("moved_shade", "Moved to shade / cooler area"),
    ("cooling_measures", "Cooling measures"),
    ("moved_shelter", "Moved to shelter"),
    ("blanket_warming", "Blanket / warming measures"),
    ("oxygen_reported", "Oxygen reported"),
    ("cpr_reported", "CPR reported"),
    ("aed_use_reported", "AED use reported"),
    ("other_care", "Other care reported"),
    ("no_care_as_reported", "No care provided — as reported"),
    ("care_details_not_known", "Care details not known"),
)
CARE_SUGGESTIONS = {
    "fall_collision_injury": (
        "wound_cleaned",
        "dressing_bandage",
        "bleeding_control",
        "injury_support",
    ),
    "blister_chafing_skin": (
        "blister_skin_care",
        "dressing_covering",
    ),
    "muscle_joint_cramp": (
        "rest_recovery",
        "ice_cold_pack",
        "injury_support",
    ),
    "dizziness_fainting_collapse": (
        "assisted_to_rest",
        "observation",
        "assessed_by_agency",
    ),
    "exhaustion": (
        "rest_recovery",
        "fluids_provided",
        "observation",
    ),
    "heat_concern": (
        "moved_shade",
        "cooling_measures",
        "fluids_provided",
        "observation",
    ),
    "cold_exposure": (
        "moved_shelter",
        "blanket_warming",
        "observation",
    ),
    "breathing_difficulty": (
        "assessed_by_agency",
        "observation",
        "oxygen_reported",
    ),
    "chest_pain_heart": (
        "assessed_by_agency",
        "observation",
        "cpr_reported",
        "aed_use_reported",
        "oxygen_reported",
    ),
    "nausea_stomach": (
        "rest_recovery",
        "assessed_by_agency",
        "observation",
    ),
    "confusion_altered": (
        "assessed_by_agency",
        "observation",
        "assisted_to_rest",
    ),
}
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


def catalog() -> Dict[str, Any]:
    def _pairs(items: Sequence[tuple[str, str]]) -> List[Dict[str, str]]:
        return [{"id": key, "label": label} for key, label in items]

    return {
        "fm_event": _pairs(FM_EVENTS),
        "incident_types": _pairs(INCIDENT_TYPES),
        "care_types": _pairs(CARE_TYPES),
        "care_suggestions": {
            key: list(ids) for key, ids in CARE_SUGGESTIONS.items()
        },
        "shared_care_types": list(SHARED_CARE),
        "exclusive_incident_types": [NOT_YET_KNOWN],
        "exclusive_care_types": sorted(EXCLUSIVE_CARE),
        "agencies": _pairs(AGENCIES),
        "reporter_agencies": _pairs(REPORTER_AGENCIES),
        "transferred_to": _pairs(AGENCIES),
        "outcomes": _pairs(OUTCOMES),
        "catalog_review": (
            "Reported-problem and care catalogs have not been reviewed "
            "by first-aid agencies."
        ),
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


def clean_incident_types(raw: Any) -> List[str]:
    cleaned = _clean_list(raw, CATALOG_KEYS["incident_types"])
    has_specific = any(key != NOT_YET_KNOWN for key in cleaned)
    if NOT_YET_KNOWN in cleaned and has_specific:
        return [key for key in cleaned if key != NOT_YET_KNOWN]
    return cleaned


def clean_care_types(raw: Any) -> List[str]:
    cleaned = _clean_list(raw, CATALOG_KEYS["care_types"])
    exclusive = [key for key in cleaned if key in EXCLUSIVE_CARE]
    actual = [key for key in cleaned if key not in EXCLUSIVE_CARE]
    if actual:
        return actual
    if len(exclusive) > 1:
        return [exclusive[-1]]
    return exclusive


def suggested_care_ids(problem_ids: Sequence[Any]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for problem in problem_ids or []:
        for care_id in CARE_SUGGESTIONS.get(str(problem), ()):
            if care_id in seen:
                continue
            seen.add(care_id)
            out.append(care_id)
    return out


def lifecycle(incident: Mapping[str, Any]) -> Dict[str, str]:
    if is_closed(incident):
        return {"id": "closed", "label": "Closed", "display": "Closed"}
    agency = _clean_agency(incident.get("assigned_to"))
    if agency:
        label = agency_label(agency)
        return {
            "id": "assigned",
            "label": "Assigned",
            "agency": agency,
            "agency_label": label,
            "display": "Assigned · " + label,
        }
    return {"id": "open", "label": "Open", "display": "Open"}


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
    old_care_note: str = "",
    new_care_note: str = "",
) -> str:
    parts: List[str] = []
    type_added, type_removed = _catalog_diff(old_types, new_types, INCIDENT_TYPES)
    care_added, care_removed = _catalog_diff(old_care, new_care, CARE_TYPES)
    if type_added:
        parts.append("Problem added: " + ", ".join(type_added) + ".")
    if type_removed:
        parts.append("Problem removed: " + ", ".join(type_removed) + ".")
    other_text = str(new_other or "").strip()
    if other_text and other_text != str(old_other or "").strip():
        parts.append("Other reported problem: " + other_text + ".")
    if care_added:
        parts.append("Care added: " + ", ".join(care_added) + ".")
    if care_removed:
        parts.append("Care removed: " + ", ".join(care_removed) + ".")
    care_other = str(new_care_note or "").strip()
    if care_other and care_other != str(old_care_note or "").strip():
        parts.append("Other care reported: " + care_other + ".")
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
    old_care_note = str(incident.get("care_note") or "").strip()
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
            extra = str(
                payload.get("assigned_note")
                or payload.get("transfer_note")
                or ""
            ).strip()
            if old_assigned and new_assigned:
                transfer_care(incident, new_assigned, extra)
            elif old_assigned and not new_assigned:
                incident["assigned_to"] = ""
                append_note(
                    incident,
                    "Transferred " + agency_label(old_assigned) + " → Unassigned.",
                    kind="transfer",
                    detail=extra,
                )
            else:
                assign_care(incident, new_assigned, extra)
    if "fm_event" in payload:
        cleaned_events = _clean_list(
            payload.get("fm_event"), CATALOG_KEYS["fm_event"]
        )
        if list(incident.get("fm_event") or []) != cleaned_events:
            incident["fm_event"] = cleaned_events
            changed = True
    if "incident_types" in payload:
        cleaned_types = clean_incident_types(payload.get("incident_types"))
        if list(incident.get("incident_types") or []) != cleaned_types:
            incident["incident_types"] = cleaned_types
            changed = True
    if "care_types" in payload:
        cleaned_care = clean_care_types(payload.get("care_types"))
        if list(incident.get("care_types") or []) != cleaned_care:
            incident["care_types"] = cleaned_care
            changed = True
    if "transferred_to" in payload:
        cleaned_xfer = _clean_list(
            payload.get("transferred_to"), CATALOG_KEYS["transferred_to"]
        )
        if list(incident.get("transferred_to") or []) != cleaned_xfer:
            incident["transferred_to"] = cleaned_xfer
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
        old_care_note=old_care_note,
        new_care_note=str(incident.get("care_note") or "").strip(),
    )
    if care_note:
        append_note(incident, care_note, kind="system")
    return incident


def append_note(
    incident: Dict[str, Any],
    text: str,
    *,
    kind: str = "user",
    detail: str = "",
) -> Dict[str, Any]:
    body = str(text or "").strip()
    if not body:
        raise ValueError("Note text is required.")
    stamp = wall_stamp()
    kind_key = str(kind or "user").strip().lower()
    if kind_key not in NOTE_KINDS:
        kind_key = "user"
    entry: Dict[str, Any] = {
        "text": body,
        "kind": kind_key,
        "saved_at": stamp["saved_at"],
        "saved_at_label": stamp["saved_at_label"],
    }
    extra = str(detail or "").strip()
    if extra:
        entry["detail"] = extra
    notes = list(incident.get("notes") or [])
    notes.append(entry)
    incident["notes"] = notes
    _touch(incident, stamp)
    return incident


def assign_care(
    incident: Dict[str, Any],
    to_agency: str,
    text: str = "",
) -> Dict[str, Any]:
    require_open(incident)
    to_key = _clean_agency(to_agency)
    if not to_key:
        raise ValueError("Unknown care agency.")
    if _clean_agency(incident.get("assigned_to")):
        return transfer_care(incident, to_agency, text)
    extra = str(text or "").strip()
    incident["assigned_to"] = to_key
    append_note(
        incident,
        "Assigned " + agency_label(to_key) + ".",
        kind="transfer",
        detail=extra,
    )
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
    incident["assigned_to"] = to_key
    append_note(incident, note, kind="transfer", detail=extra)
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


def location_catalog_from_rows(
    rows: Optional[Sequence[Any]],
) -> List[Dict[str, Any]]:
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


def location_catalog(storage: Any, day: str) -> List[Dict[str, Any]]:
    path = locations_report_relpath(day)
    if not storage.exists(path):
        return []
    try:
        payload = storage.read_json(path)
    except Exception:
        return []
    rows = payload.get("locations") if isinstance(payload, Mapping) else None
    return location_catalog_from_rows(rows)


def load_store(storage: Any, *, run_id: str, day: str) -> Dict[str, Any]:
    from app.core.execute.db import get_blob, using_postgres

    if using_postgres():
        raw = get_blob(str(run_id), "incidents", day)
        if raw:
            store = empty_store(run_id=run_id, day=day)
            items = (
                raw.get("incidents")
                if isinstance(raw.get("incidents"), list)
                else []
            )
            store["incidents"] = [
                normalize_incident(dict(item))
                for item in items
                if isinstance(item, Mapping)
            ]
            return store
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
    from app.core.execute.db import put_blob, using_postgres

    payload = dict(store)
    payload["schema_version"] = SCHEMA_VERSION
    if using_postgres():
        put_blob(str(store.get("run_id") or ""), "incidents", day, payload)
    try:
        return storage.write_json(incidents_relpath(day), payload)
    except Exception:
        if using_postgres():
            return ""
        raise


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
