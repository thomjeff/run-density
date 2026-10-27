"""Race Roster import and participant lookup (Issue #911)."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
PARTICIPANTS_FILENAME = "participants.json"
DROPPED_HEADERS = frozenset({"original sub-event", "event id"})
BUNDLE_JOINER = re.compile(r"\s+(?:and|&)\s+", re.IGNORECASE)

HEADER_FIELDS = (
    ("participant id", "reg_id"),
    ("bib numbers", "bib"),
    ("last name", "family_name"),
    ("first name", "given_name"),
    ("sex", "sex"),
    ("date of birth", "dob"),
    ("phone number", "phone"),
    ("email", "email"),
    ("city", "city"),
    ("state", "region"),
    ("address", "address"),
    ("zip/postal code", "postcode"),
    ("country", "country"),
    ("sub-event", "sub_event"),
    ("age", "age"),
    ("confirmation no.", "confirmation_no"),
    ("confirmation no", "confirmation_no"),
    ("emergency contact first and last name", "emerg_name"),
    ("emergency contact phone number", "emerg_phone"),
)


class DuplicateBibError(ValueError):
    """Two starts share the same non-empty bib."""

    def __init__(self, bib: str, reg_ids: Sequence[str]):
        self.bib = bib
        self.reg_ids = list(reg_ids)
        joined = ", ".join(self.reg_ids)
        super().__init__(f"Duplicate bib {bib} on starts {joined}.")


def participants_relpath(day: str) -> str:
    return f"{day}/execution/{PARTICIPANTS_FILENAME}"


def empty_store(*, run_id: str, day: str) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "day": (day or "").strip().lower(),
        "rows": [],
    }


def classify_row_kind(sub_event: str) -> str:
    """Bundle if sub_event joins two event labels; else start."""
    text = (sub_event or "").strip()
    if text and BUNDLE_JOINER.search(text):
        return "bundle"
    return "start"


def _norm_header(raw: Any) -> str:
    text = str(raw or "").replace("\ufeff", "").strip().lower()
    return " ".join(text.split())


def _map_headers(fieldnames: Optional[Sequence[str]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for raw in fieldnames or []:
        key = _norm_header(raw)
        if not key or key in DROPPED_HEADERS:
            continue
        for prefix, field in HEADER_FIELDS:
            if key == prefix:
                mapping[raw] = field
                break
        else:
            if key.startswith("do you have a medical condition"):
                mapping[raw] = "medical_disclosed"
            elif key.startswith("which of the following best describes"):
                mapping[raw] = "medical_conditions_raw"
            elif key.startswith("please provide any important details"):
                mapping[raw] = "medical_note"
            elif key.startswith("is there anything responders should avoid"):
                mapping[raw] = "medical_avoid"
    return mapping


def _cell(row: Mapping[str, Any], header: str) -> str:
    value = row.get(header)
    if value is None:
        return ""
    return str(value).strip()


def parse_disclosed(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text in ("yes", "y", "true", "1"):
        return "yes"
    if text in ("no", "n", "false", "0"):
        return "no"
    return ""


def split_conditions(raw: str) -> List[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if "||" in text:
        parts = text.split("||")
    else:
        parts = text.split("|")
    out: List[str] = []
    seen = set()
    for part in parts:
        token = part.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _row_from_csv(
    raw: Mapping[str, Any], mapping: Mapping[str, str]
) -> Optional[Dict[str, Any]]:
    values: Dict[str, str] = {}
    for header, field in mapping.items():
        values[field] = _cell(raw, header)
    reg_id = values.get("reg_id") or ""
    if not reg_id:
        return None
    bib = values.get("bib") or ""
    sub_event = values.get("sub_event") or ""
    disclosed = parse_disclosed(values.get("medical_disclosed") or "")
    return {
        "reg_id": reg_id,
        "row_kind": classify_row_kind(sub_event),
        "bib": bib,
        "given_name": values.get("given_name") or "",
        "family_name": values.get("family_name") or "",
        "sex": values.get("sex") or "",
        "dob": values.get("dob") or "",
        "age": values.get("age") or "",
        "phone": values.get("phone") or "",
        "email": values.get("email") or "",
        "address": values.get("address") or "",
        "city": values.get("city") or "",
        "region": values.get("region") or "",
        "postcode": values.get("postcode") or "",
        "country": values.get("country") or "",
        "sub_event": sub_event,
        "confirmation_no": values.get("confirmation_no") or "",
        "emerg_name": values.get("emerg_name") or "",
        "emerg_phone": values.get("emerg_phone") or "",
        "medical_disclosed": disclosed,
        "medical_conditions": split_conditions(
            values.get("medical_conditions_raw") or ""
        ),
        "medical_note": values.get("medical_note") or "",
        "medical_avoid": values.get("medical_avoid") or "",
    }


def parse_roster_csv(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    mapping = _map_headers(reader.fieldnames)
    if "reg_id" not in mapping.values():
        raise ValueError("CSV is missing Participant ID (reg_id).")
    rows: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    for raw in reader:
        row = _row_from_csv(raw, mapping)
        if row is None:
            continue
        reg_id = row["reg_id"]
        if reg_id in seen:
            rows[seen[reg_id]] = row
        else:
            seen[reg_id] = len(rows)
            rows.append(row)
    return rows


def assert_unique_start_bibs(rows: Iterable[Mapping[str, Any]]) -> None:
    owners: Dict[str, List[str]] = {}
    for row in rows:
        if str(row.get("row_kind") or "") != "start":
            continue
        bib = str(row.get("bib") or "").strip()
        if not bib:
            continue
        owners.setdefault(bib, []).append(str(row.get("reg_id") or ""))
    for bib, reg_ids in owners.items():
        if len(reg_ids) > 1:
            raise DuplicateBibError(bib, reg_ids)


def lookup_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(row) for row in rows if str(row.get("row_kind") or "") == "start"]


def query_matches(query: str, field: str, row: Mapping[str, Any]) -> bool:
    needle = (query or "").strip().lower()
    if not needle:
        return True
    field = (field or "bib").strip().lower()
    if field == "bib":
        hay = str(row.get("bib") or "")
    elif field == "name":
        hay = " ".join(
            [
                str(row.get("given_name") or ""),
                str(row.get("family_name") or ""),
            ]
        )
    elif field == "phone":
        hay = str(row.get("phone") or "")
    elif field == "email":
        hay = str(row.get("email") or "")
    elif field in ("sub_event", "event"):
        hay = str(row.get("sub_event") or "")
    else:
        hay = " ".join(
            str(row.get(key) or "")
            for key in (
                "bib",
                "given_name",
                "family_name",
                "phone",
                "email",
                "sub_event",
            )
        )
    return needle in hay.lower()


def condition_matches(row: Mapping[str, Any], condition: str) -> bool:
    wanted = (condition or "").strip().lower()
    if not wanted or wanted == "any":
        return True
    for token in row.get("medical_conditions") or []:
        if wanted in str(token).strip().lower():
            return True
    return False


def condition_matches_any(row: Mapping[str, Any], conditions: Sequence[str]) -> bool:
    wanted = [str(item).strip() for item in conditions if str(item).strip()]
    if not wanted:
        return True
    return any(condition_matches(row, item) for item in wanted)


def load_store(storage: Any, *, run_id: str, day: str) -> Dict[str, Any]:
    path = participants_relpath(day)
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
    rows = raw.get("rows") if isinstance(raw.get("rows"), list) else []
    store["rows"] = [dict(row) for row in rows if isinstance(row, Mapping)]
    if raw.get("run_id"):
        store["run_id"] = str(raw.get("run_id"))
    return store


def persist_store(storage: Any, day: str, store: Mapping[str, Any]) -> str:
    return storage.write_json(participants_relpath(day), dict(store))


def import_csv_text(
    storage: Any,
    *,
    run_id: str,
    day: str,
    text: str,
) -> Tuple[Dict[str, Any], Dict[str, int]]:
    rows = parse_roster_csv(text)
    assert_unique_start_bibs(rows)
    store = empty_store(run_id=run_id, day=day)
    store["rows"] = rows
    persist_store(storage, day, store)
    starts = lookup_rows(rows)
    stats = {
        "rows": len(rows),
        "starts": len(starts),
        "bundles": sum(1 for row in rows if row.get("row_kind") == "bundle"),
        "no_bib": sum(1 for row in starts if not str(row.get("bib") or "").strip()),
    }
    return store, stats
