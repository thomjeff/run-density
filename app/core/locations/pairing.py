"""
Paired reverse-leg pass helpers (Issue #810 / 2027 identity).

Multiple pass rows sharing a ``pass_key`` are passes at the same Location.
Outbound = earlier ``first_runner``; return = later ``first_runner``.

Terminology:
- ``loc_id`` — human Location number (shared by paired passes)
- ``pass_id`` — timed instance
- ``pass_key`` — opaque unifier (system join; not volunteer-facing)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple

from app.core.locations.identity import effective_pass_key

logger = logging.getLogger(__name__)


def _merge_by_event_from_passes(passes: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Issue #828: Location-level by_event = merge of pass-level maps."""
    from app.location_report import merge_by_event_timings

    return merge_by_event_timings([p.get("by_event") for p in passes])


def effective_location_key(row: MutableMapping[str, Any]) -> str:
    """Alias for effective_pass_key (legacy name)."""
    return effective_pass_key(row)


def time_to_seconds(value: Any) -> Optional[int]:
    """Parse HH:MM[:SS] (or pandas-ish) into seconds since midnight."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.upper() in ("NA", "NAN", "NONE", "NULL"):
        return None
    parts = text.split(":")
    try:
        if len(parts) == 2:
            h, m = int(parts[0]), int(parts[1])
            return h * 3600 + m * 60
        if len(parts) >= 3:
            h, m, s = int(parts[0]), int(parts[1]), int(float(parts[2]))
            return h * 3600 + m * 60 + s
    except (TypeError, ValueError):
        return None
    return None


def min_time_str(values: Iterable[Any]) -> Optional[str]:
    """Earliest HH:MM:SS among values; preserve original string of the winner."""
    best: Optional[Tuple[int, str]] = None
    for value in values:
        sec = time_to_seconds(value)
        if sec is None:
            continue
        text = str(value).strip()
        if best is None or sec < best[0]:
            best = (sec, text)
    return best[1] if best else None


def max_time_str(values: Iterable[Any]) -> Optional[str]:
    """Latest HH:MM:SS among values; preserve original string of the winner."""
    best: Optional[Tuple[int, str]] = None
    for value in values:
        sec = time_to_seconds(value)
        if sec is None:
            continue
        text = str(value).strip()
        if best is None or sec > best[0]:
            best = (sec, text)
    return best[1] if best else None


def _row_pass_id(row: MutableMapping[str, Any]) -> Any:
    for field in ("pass_id", "id"):
        raw = row.get(field)
        if raw is None or raw == "":
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return raw
    # Legacy report rows used loc_id as the instance id
    raw = row.get("loc_id")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return raw


def annotate_location_passes(rows: Sequence[MutableMapping[str, Any]]) -> None:
    """
    Mutate report rows in place: set ``pass`` and ``same_pass_as``.

    Also mirrors ``same_location_as`` for older importers during cutover.
    """
    by_key: Dict[str, List[MutableMapping[str, Any]]] = {}
    for row in rows:
        key = effective_pass_key(row)
        if key:
            row["pass_key"] = key
            row.setdefault("location_key", key)
        row["pass"] = ""
        row["same_pass_as"] = ""
        row["same_location_as"] = ""
        if not key:
            continue
        by_key.setdefault(key, []).append(row)

    for key, group in by_key.items():
        if len(group) < 2:
            continue
        if len(group) > 2:
            logger.warning(
                "pass_key=%s has %s rows (expected 2); "
                "assigning passes by first_runner order",
                key,
                len(group),
            )

        def sort_key(r: MutableMapping[str, Any]) -> Tuple[int, int]:
            fr = time_to_seconds(r.get("first_runner"))
            try:
                pid = int(_row_pass_id(r) or 10**9)
            except (TypeError, ValueError):
                pid = 10**9
            return (fr if fr is not None else 10**9, pid)

        ordered = sorted(group, key=sort_key)
        outbound = ordered[0]
        outbound_id = _row_pass_id(outbound)

        for i, row in enumerate(ordered):
            role = "outbound" if i == 0 else "return"
            row["pass"] = role
            if role == "outbound":
                peer = ordered[1] if len(ordered) > 1 else None
                peer_id = _row_pass_id(peer) if peer else ""
                row["same_pass_as"] = peer_id if peer_id is not None else ""
            else:
                row["same_pass_as"] = outbound_id if outbound_id is not None else ""
            row["same_location_as"] = row["same_pass_as"]


def group_rows_by_location_key(
    rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Collapse flat pass rows into Location-centric groups for UI / sheets.

    Each group dict includes ``loc_id`` (human), ``pass_key``, ``pass_ids``,
    ``passes``, and combined earliest/latest timing windows.
    """
    working = [dict(r) for r in rows]
    annotate_location_passes(working)

    singles: List[Dict[str, Any]] = []
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for row in working:
        key = effective_pass_key(row)
        if not key:
            singles.append(_singleton_group(row))
            continue
        by_key.setdefault(key, []).append(row)

    groups: List[Dict[str, Any]] = list(singles)
    for key, group in by_key.items():
        if len(group) == 1:
            groups.append(_singleton_group(group[0], pass_key=key))
            continue
        groups.append(_paired_group(key, group))

    def sort_loc(g: Dict[str, Any]) -> int:
        try:
            return int(g.get("loc_id") or g.get("primary_loc_id") or 0)
        except (TypeError, ValueError):
            return 0

    groups.sort(key=sort_loc)
    return groups


def consolidate_location_rows(
    pass_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build Locations.csv rows (one per loc_id) from Passes.csv-style rows.

    Combined window = earliest first_runner / loc_start and latest last_runner / loc_end.
    """
    groups = group_rows_by_location_key(pass_rows)
    out: List[Dict[str, Any]] = []
    for g in groups:
        passes = g.get("passes") or []
        pass_ids = []
        for p in passes:
            pid = _row_pass_id(p)
            if pid is not None and pid != "":
                pass_ids.append(pid)
        row = {
            "loc_id": g.get("loc_id") if g.get("loc_id") is not None else g.get("primary_loc_id"),
            "pass_key": g.get("pass_key") or g.get("location_key") or "",
            "pass_ids": ",".join(str(p) for p in pass_ids),
            "pass_count": len(passes),
            "loc_label": g.get("loc_label"),
            "day": next((p.get("day") for p in passes if p.get("day")), ""),
            "loc_type": g.get("loc_type"),
            "lat": g.get("lat"),
            "lon": g.get("lon"),
            "zone": g.get("zone"),
            "first_runner": g.get("first_runner"),
            "last_runner": g.get("last_runner"),
            "loc_start": g.get("loc_start"),
            "loc_end": g.get("loc_end"),
            "peak_start": g.get("peak_start"),
            "peak_end": g.get("peak_end"),
            "by_event": g.get("by_event") or _merge_by_event_from_passes(passes),
            "flag": g.get("flag"),
            "onepage": g.get("onepage"),
            "notes": g.get("notes"),
        }
        for k, v in g.items():
            if k.endswith("_count") or k.endswith("_mins"):
                row[k] = v
        out.append(row)
    return out


def _human_loc_id(row: Dict[str, Any]) -> Any:
    raw = row.get("loc_id")
    # If this is a legacy pass-only row, loc_id may actually be pass_id;
    # prefer explicit human field when pass_id is also present and differs.
    pass_id = row.get("pass_id")
    if pass_id is not None and raw is not None:
        try:
            if int(raw) != int(pass_id):
                return int(raw)
            return int(raw)  # may still be human if already stamped
        except (TypeError, ValueError):
            return raw
    try:
        return int(raw)
    except (TypeError, ValueError):
        return raw


def _singleton_group(
    row: Dict[str, Any], *, pass_key: Optional[str] = None
) -> Dict[str, Any]:
    key = pass_key if pass_key is not None else effective_pass_key(row)
    loc_id = _human_loc_id(row)
    pass_id = _row_pass_id(row)
    return {
        "pass_key": key,
        "location_key": key,
        "loc_id": loc_id,
        "loc_label": row.get("loc_label"),
        "loc_type": row.get("loc_type"),
        "zone": row.get("zone"),
        "lat": row.get("lat"),
        "lon": row.get("lon"),
        "primary_loc_id": loc_id,
        "loc_ids": [loc_id],
        "pass_ids": [pass_id],
        "passes": [row],
        "paired": False,
        "first_runner": row.get("first_runner"),
        "last_runner": row.get("last_runner"),
        "loc_start": row.get("loc_start"),
        "loc_end": row.get("loc_end"),
        "peak_start": row.get("peak_start"),
        "peak_end": row.get("peak_end"),
        "by_event": _merge_by_event_from_passes([row]),
        "flag": row.get("flag"),
        "onepage": row.get("onepage"),
        "notes": row.get("notes"),
        **{k: row[k] for k in row if k.endswith("_count") or k.endswith("_mins")},
    }


def _paired_group(key: str, group: List[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(
        group,
        key=lambda r: (
            0 if str(r.get("pass") or "") == "outbound" else 1,
            time_to_seconds(r.get("first_runner")) or 10**9,
        ),
    )
    primary = ordered[0]
    loc_id = _human_loc_id(primary)
    # Prefer shared human loc_id from any row that differs from its pass_id
    for r in ordered:
        candidate = _human_loc_id(r)
        pid = _row_pass_id(r)
        try:
            if candidate is not None and int(candidate) != int(pid):
                loc_id = int(candidate)
                break
        except (TypeError, ValueError):
            pass

    pass_ids = [_row_pass_id(r) for r in ordered]

    merged_counts: Dict[str, Any] = {}
    for r in ordered:
        for k, v in r.items():
            if k.endswith("_count") or k.endswith("_mins"):
                try:
                    num = float(v) if v is not None and str(v) not in ("", "nan") else 0
                except (TypeError, ValueError):
                    num = 0
                prev = merged_counts.get(k, 0) or 0
                try:
                    merged_counts[k] = max(float(prev), num)
                except (TypeError, ValueError):
                    merged_counts[k] = num

    return {
        "pass_key": key,
        "location_key": key,
        "loc_id": loc_id,
        "loc_label": primary.get("loc_label"),
        "loc_type": primary.get("loc_type"),
        "zone": primary.get("zone"),
        "lat": primary.get("lat"),
        "lon": primary.get("lon"),
        "primary_loc_id": loc_id,
        "loc_ids": [loc_id],
        "pass_ids": pass_ids,
        "passes": ordered,
        "paired": True,
        "first_runner": min_time_str(r.get("first_runner") for r in ordered),
        "last_runner": max_time_str(r.get("last_runner") for r in ordered),
        "loc_start": min_time_str(r.get("loc_start") for r in ordered),
        "loc_end": max_time_str(r.get("loc_end") for r in ordered),
        "peak_start": min_time_str(r.get("peak_start") for r in ordered),
        "peak_end": max_time_str(r.get("peak_end") for r in ordered),
        "by_event": _merge_by_event_from_passes(ordered),
        "flag": any(
            r.get("flag") in (True, "true", "True", "Y", "y", 1, "1") for r in ordered
        ),
        "onepage": "y"
        if any(str(r.get("onepage", "")).strip().lower() == "y" for r in ordered)
        else primary.get("onepage"),
        "notes": primary.get("notes")
        or next((r.get("notes") for r in ordered if r.get("notes")), ""),
        **merged_counts,
    }
