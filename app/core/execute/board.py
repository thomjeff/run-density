"""Merge Plan locations + execution state into the three-column board."""

from __future__ import annotations

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

from app.core.execute.times import (
    REOPEN_NEXT_WINDOW_MINUTES,
    SKIP_RESOURCE_CODES,
    display_loc_end_minutes,
    display_now_hhmmss,
    estimate_passed,
    gun_deltas_minutes,
    minutes_to_hhmm,
    parse_hhmm,
)
from app.core.locations.report_json import parse_optional_id
from app.utils.constants import DISPLAY_TIMEZONE


def resource_assignments(
    row: Mapping[str, Any],
    available: Sequence[str],
) -> List[Dict[str, Any]]:
    allowed = {
        str(code).strip().lower()
        for code in available
        if str(code).strip().lower() not in SKIP_RESOURCE_CODES
    }
    out: List[Dict[str, Any]] = []
    for key, raw in row.items():
        name = str(key)
        if not name.endswith("_count"):
            continue
        code = name[:-6].strip().lower()
        if allowed and code not in allowed:
            continue
        if code in SKIP_RESOURCE_CODES:
            continue
        try:
            count = int(float(raw or 0))
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        out.append({"code": code.upper(), "count": count})
    out.sort(key=lambda item: item["code"])
    return out


def linked_for(
    locations: Sequence[Mapping[str, Any]],
    loc_id: Any,
    reopened: Mapping[str, Any],
    available: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    target = parse_optional_id(loc_id)
    if target is None:
        return []
    linked: List[Dict[str, Any]] = []
    for row in locations:
        if parse_optional_id(row.get("proxy_loc_id")) != target:
            continue
        lid = parse_optional_id(row.get("loc_id"))
        if lid is None:
            continue
        already = str(lid) in reopened
        linked.append(
            {
                "loc_id": lid,
                "loc_label": row.get("loc_label") or "",
                "loc_type": row.get("loc_type") or "",
                "reopened": already,
                "resources": resource_assignments(
                    row, available or _row_resource_codes(row)
                ),
            }
        )
    linked.sort(key=lambda item: item["loc_id"])
    return [item for item in linked if not item["reopened"]]


def _row_resource_codes(row: Mapping[str, Any]) -> List[str]:
    codes: List[str] = []
    for key, raw in row.items():
        name = str(key)
        if not name.endswith("_count"):
            continue
        try:
            if float(raw or 0) > 0:
                codes.append(name[:-6])
        except (TypeError, ValueError):
            continue
    return codes


def _sort_active(rows: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    def key(row: Mapping[str, Any]) -> Tuple[int, int, int]:
        minutes = parse_hhmm(row.get("loc_end"))
        timed = 0 if minutes is not None else 1
        stamp = minutes if minutes is not None else 0
        return (timed, stamp, int(row["loc_id"]))

    return sorted((dict(r) for r in rows), key=key)


def _sort_reopened(
    rows: Iterable[Mapping[str, Any]],
    activity: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Most recently reopened first (activity order, not HH:MM lexicographic)."""
    recency: Dict[int, int] = {}
    for index, item in enumerate(activity or []):
        if not isinstance(item, Mapping):
            continue
        loc_id = parse_optional_id(item.get("loc_id"))
        if loc_id is not None:
            recency[loc_id] = index
        for linked in item.get("linked_loc_ids") or []:
            linked_id = parse_optional_id(linked)
            if linked_id is not None:
                recency[linked_id] = index

    def key(row: Mapping[str, Any]) -> Tuple[int, int, int]:
        loc_id = int(row["loc_id"])
        seq = recency.get(loc_id, -1)
        stamp = parse_hhmm(row.get("reopened_at"))
        return (seq, stamp if stamp is not None else -1, loc_id)

    return sorted((dict(r) for r in rows), key=key, reverse=True)


def reopen_next_ids(
    closed: Sequence[Mapping[str, Any]],
    now_hhmmss: Optional[str] = None,
) -> set[int]:
    """
    Work queue for remaining closed locations.

    Before the first loc_end, preview that earliest 15-minute cluster.
    Once the clock reaches it, the window is now + 15 minutes, so
    overdue locations leave Closed. Time never auto-reopens.
    """
    timed = []
    for row in closed:
        minutes = parse_hhmm(row.get("loc_end"))
        if minutes is None:
            continue
        timed.append((int(row["loc_id"]), minutes))
    if not timed:
        return set()
    earliest = min(item[1] for item in timed)
    now_m = parse_hhmm(now_hhmmss)
    anchor = earliest if now_m is None else max(now_m, earliest)
    end = anchor + REOPEN_NEXT_WINDOW_MINUTES
    return {lid for lid, minutes in timed if minutes <= end}


def zone_code(raw: Any) -> Optional[str]:
    """Display zone as Z3; empty or invalid becomes None."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return f"Z{raw}"
    if isinstance(raw, float):
        if raw != raw:  # NaN
            return None
        return f"Z{int(raw)}"
    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none", "null", "na"):
        return None
    if text[0] in ("z", "Z"):
        rest = text[1:].lstrip()
        return f"Z{rest}" if rest else None
    try:
        return f"Z{int(float(text))}"
    except (TypeError, ValueError):
        return f"Z{text}"


def build_strip(
    row: Mapping[str, Any],
    *,
    loc_end_minutes: Optional[int],
    now_hhmmss: str,
    status: str,
    reopened_entry: Optional[Mapping[str, Any]],
    linked: Sequence[Mapping[str, Any]],
    available: Sequence[str],
    run_id: str,
) -> Dict[str, Any]:
    loc_id = parse_optional_id(row.get("loc_id"))
    return {
        "loc_id": loc_id,
        "loc_label": row.get("loc_label") or "",
        "loc_type": row.get("loc_type") or "",
        "zone": zone_code(row.get("zone")),
        "loc_end": minutes_to_hhmm(loc_end_minutes),
        "loc_end_planned": row.get("loc_end"),
        "estimate_passed": estimate_passed(loc_end_minutes, now_hhmmss),
        "resources": resource_assignments(row, available),
        "status": status,
        "reopened_at": (reopened_entry or {}).get("reopened_at"),
        "operator": None,
        "linked": list(linked),
        "map_href": (
            f"/locations?run_id={run_id}&loc_id={loc_id}"
        ),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
    }


def assemble_board(
    *,
    locations: Sequence[Mapping[str, Any]],
    state: Mapping[str, Any],
    resources_available: Sequence[str],
    run_id: str,
    day: str,
    now_hhmmss: Optional[str] = None,
) -> Dict[str, Any]:
    clock = state.get("clock") or {}
    now = now_hhmmss or display_now_hhmmss(clock)
    accepted = bool(clock.get("guns_accepted"))
    analysis_guns = clock.get("analysis_guns") or {}
    operator_guns = clock.get("guns") or analysis_guns
    if accepted:
        deltas = gun_deltas_minutes(analysis_guns, operator_guns)
    else:
        deltas = {}
    reopened_map = state.get("reopened") or {}
    if not isinstance(reopened_map, Mapping):
        reopened_map = {}

    prepared: List[Dict[str, Any]] = []
    for row in locations:
        if not isinstance(row, Mapping):
            continue
        loc_id = parse_optional_id(row.get("loc_id"))
        if loc_id is None:
            continue
        minutes = display_loc_end_minutes(row, deltas)
        prepared.append(
            {
                "row": row,
                "loc_id": loc_id,
                "loc_end_minutes": minutes,
                "loc_end": minutes_to_hhmm(minutes),
                "reopened_entry": reopened_map.get(str(loc_id)),
            }
        )

    closed_src = [p for p in prepared if not p["reopened_entry"]]
    closed_for_window = [
        {"loc_id": p["loc_id"], "loc_end": p["loc_end"]} for p in closed_src
    ]
    next_ids = reopen_next_ids(closed_for_window, now)

    closed: List[Dict[str, Any]] = []
    reopen_next: List[Dict[str, Any]] = []
    reopened: List[Dict[str, Any]] = []
    for item in prepared:
        row = item["row"]
        loc_id = item["loc_id"]
        entry = item["reopened_entry"]
        if entry:
            status = "reopened"
        elif loc_id in next_ids:
            status = "reopen_next"
        else:
            status = "closed"
        strip = build_strip(
            row,
            loc_end_minutes=item["loc_end_minutes"],
            now_hhmmss=now,
            status=status,
            reopened_entry=entry,
            linked=linked_for(
                locations, loc_id, reopened_map, resources_available
            ),
            available=resources_available,
            run_id=run_id,
        )
        if status == "reopened":
            reopened.append(strip)
        elif status == "reopen_next":
            reopen_next.append(strip)
        else:
            closed.append(strip)

    return {
        "ok": True,
        "run_id": run_id,
        "day": day,
        "timezone": DISPLAY_TIMEZONE,
        "now": now,
        "clock": dict(clock),
        "columns": {
            "closed": _sort_active(closed),
            "reopen_next": _sort_active(reopen_next),
            "reopened": _sort_reopened(
                reopened, state.get("activity") or []
            ),
        },
        "counts": {
            "closed": len(closed),
            "reopen_next": len(reopen_next),
            "reopened": len(reopened),
            "total": len(prepared),
        },
        "activity": list(state.get("activity") or []),
        "resource_codes": [
            c for c in resources_available if c not in SKIP_RESOURCE_CODES
        ],
    }
