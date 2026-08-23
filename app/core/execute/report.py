"""On-demand Execute reopen variance CSV (Issue #898)."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Mapping, Optional, Sequence

from app.core.execute.times import (
    SKIP_RESOURCE_CODES,
    display_loc_end_minutes,
    gun_deltas_minutes,
    minutes_to_hhmm,
    parse_hhmm,
)
from app.core.locations.report_json import parse_optional_id

FIXED_PREFIX = ("loc_id", "loc_label")
FIXED_SUFFIX = (
    "loc_start",
    "first_runner",
    "last_runner",
    "loc_end",
    "actual_reopen",
    "difference_min",
)


def count_codes(
    locations: Sequence[Mapping[str, Any]],
    available: Optional[Sequence[str]] = None,
) -> List[str]:
    """Package resource codes as `{code}_count` columns, Locations.csv order."""
    codes: List[str] = []
    if available:
        codes = [
            str(code).strip().lower()
            for code in available
            if str(code).strip()
        ]
    else:
        seen = set()
        for row in locations:
            if not isinstance(row, Mapping):
                continue
            for key in row:
                name = str(key)
                if not name.endswith("_count"):
                    continue
                seen.add(name[:-6].strip().lower())
        codes = list(seen)
    return sorted(
        code for code in codes if code and code not in SKIP_RESOURCE_CODES
    )


def csv_columns(
    locations: Sequence[Mapping[str, Any]],
    available: Optional[Sequence[str]] = None,
) -> List[str]:
    counts = [f"{code}_count" for code in count_codes(locations, available)]
    return [*FIXED_PREFIX, *counts, *FIXED_SUFFIX]


def _clock_deltas(state: Mapping[str, Any]) -> Dict[str, int]:
    clock = state.get("clock") or {}
    if not isinstance(clock, Mapping):
        return {}
    if not clock.get("guns_accepted"):
        return {}
    analysis_guns = clock.get("analysis_guns") or {}
    operator_guns = clock.get("guns") or analysis_guns
    if not isinstance(analysis_guns, Mapping):
        return {}
    if not isinstance(operator_guns, Mapping):
        operator_guns = analysis_guns
    return gun_deltas_minutes(analysis_guns, operator_guns)


def _plan_time(row: Mapping[str, Any], key: str) -> str:
    raw = row.get(key)
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text or text.upper() in ("NA", "NAN", "NONE", "NULL"):
        return ""
    return text


def _count_value(row: Mapping[str, Any], code: str) -> int:
    raw = row.get(f"{code}_count")
    try:
        return int(float(raw or 0))
    except (TypeError, ValueError):
        return 0


def build_reopen_rows(
    locations: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
    resources_available: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    deltas = _clock_deltas(state)
    reopened = state.get("reopened") or {}
    if not isinstance(reopened, Mapping):
        reopened = {}
    codes = count_codes(locations, resources_available)
    rows: List[Dict[str, Any]] = []
    for row in locations:
        if not isinstance(row, Mapping):
            continue
        loc_id = parse_optional_id(row.get("loc_id"))
        if loc_id is None:
            continue
        est_m = display_loc_end_minutes(row, deltas)
        entry = reopened.get(str(loc_id))
        actual = ""
        if isinstance(entry, Mapping):
            actual = str(entry.get("reopened_at") or "").strip()
        actual_m = parse_hhmm(actual) if actual else None
        diff: Optional[int] = None
        if est_m is not None and actual_m is not None:
            diff = actual_m - est_m
        item: Dict[str, Any] = {
            "loc_id": loc_id,
            "loc_label": row.get("loc_label") or "",
            "loc_start": _plan_time(row, "loc_start"),
            "first_runner": _plan_time(row, "first_runner"),
            "last_runner": _plan_time(row, "last_runner"),
            "loc_end": minutes_to_hhmm(est_m) or "",
            "actual_reopen": actual,
            "difference_min": "" if diff is None else diff,
        }
        for code in codes:
            item[f"{code}_count"] = _count_value(row, code)
        rows.append(item)
    rows.sort(key=lambda item: int(item["loc_id"]))
    return rows


def reopen_csv_text(
    rows: Sequence[Mapping[str, Any]],
    fieldnames: Optional[Sequence[str]] = None,
) -> str:
    columns = list(fieldnames or csv_columns(rows))
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=columns,
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in columns})
    return buf.getvalue()
