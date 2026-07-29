"""
Dynamic event flag / span discovery for analysis artifacts (#701).

Analysis-facing code should iterate events from analysis.json (or a provided
subset of COURSE_EVENT_IDS), not duplicated elite/open/10k/half/full literals.
Config-facing code continues to use COURSE_EVENT_IDS as the product vocabulary.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from app.utils.constants import COURSE_EVENT_IDS

# Stable GPX / length tie-break among product events (Saturday first, then Sunday).
GPX_EVENT_PRIORITY: List[str] = ["elite", "open", "10k", "half", "full"]


def normalize_event_name(name: str) -> str:
    return str(name or "").strip().lower()


def event_display_label(event: str) -> str:
    """UI/GeoJSON label: 10k → 10K, full → Full."""
    e = normalize_event_name(event)
    if e == "10k":
        return "10K"
    return e.capitalize() if e else ""


def _row_get_ci(row: Mapping[str, Any], key: str) -> Any:
    """Get a value from a mapping/Series with exact then case-insensitive key match."""
    if key in row:
        return row[key]
    key_l = key.lower()
    # pandas Series: prefer .index
    keys = list(getattr(row, "index", row.keys()))
    for k in keys:
        if str(k).lower() == key_l:
            return row[k]
    return None


def resolve_event_flag(row: Mapping[str, Any], event: str) -> str:
    """Return normalized flag string for an event column ('' if absent)."""
    event = normalize_event_name(event)
    val = _row_get_ci(row, event)
    if val is None and event == "10k":
        val = _row_get_ci(row, "10K")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip().lower()


def is_event_active(row: Mapping[str, Any], event: str) -> bool:
    return resolve_event_flag(row, event) == "y"


def active_events(
    row: Mapping[str, Any],
    event_names: Optional[Sequence[str]] = None,
) -> List[str]:
    """Event ids from ``event_names`` (default COURSE_EVENT_IDS) with flag ``y``."""
    names = [normalize_event_name(e) for e in (event_names or COURSE_EVENT_IDS) if e]
    return [e for e in names if is_event_active(row, e)]


def get_event_span(row: Mapping[str, Any], event: str) -> Tuple[Any, Any]:
    """Return (from_km, to_km) for an event, including legacy 10K_* columns."""
    event = normalize_event_name(event)
    from_km = _row_get_ci(row, f"{event}_from_km")
    to_km = _row_get_ci(row, f"{event}_to_km")
    if event == "10k":
        if from_km is None:
            from_km = _row_get_ci(row, "10K_from_km")
        if to_km is None:
            to_km = _row_get_ci(row, "10K_to_km")
    return from_km, to_km


def build_segment_event_payload(
    row: Mapping[str, Any],
    event_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Flags + span fields for ``generate_segment_coordinates``.

    Copies every listed event's flag and ``{event}_from_km`` / ``{event}_to_km``.
    """
    names = [normalize_event_name(e) for e in (event_names or COURSE_EVENT_IDS) if e]
    out: Dict[str, Any] = {}
    for event in names:
        flag = resolve_event_flag(row, event)
        out[event] = flag if flag in ("y", "n") else (flag or "n")
        from_km, to_km = get_event_span(row, event)
        out[f"{event}_from_km"] = from_km
        out[f"{event}_to_km"] = to_km
    return out


def pick_gpx_event(
    segment: Mapping[str, Any],
    available_events: Iterable[str],
    *,
    priority: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """
    Choose which event's GPX/spans to use for a segment.

    Walks ``priority`` (default GPX_EVENT_PRIORITY), then any other available
    events, picking the first with flag ``y``.
    """
    available = {normalize_event_name(e) for e in available_events if e}
    order = [normalize_event_name(e) for e in (priority or GPX_EVENT_PRIORITY)]
    for event in available:
        if event not in order:
            order.append(event)
    for event in order:
        if event in available and is_event_active(segment, event):
            return event
    return None


def length_km_from_event_fields(
    dims: Mapping[str, Any],
    event_names: Optional[Sequence[str]] = None,
) -> float:
    """Best-effort segment length from ``{event}_length`` or span columns."""
    names = [normalize_event_name(e) for e in (event_names or GPX_EVENT_PRIORITY) if e]
    for event in names:
        col = f"{event}_length"
        val = _row_get_ci(dims, col)
        if val is not None and pd.notna(val) and float(val) > 0:
            return float(val)
    for event in names:
        from_km, to_km = get_event_span(dims, event)
        if (
            from_km is not None
            and to_km is not None
            and pd.notna(from_km)
            and pd.notna(to_km)
        ):
            length = float(to_km) - float(from_km)
            if length > 0:
                return length
    return 0.0


def display_events_from_flags(
    row: Mapping[str, Any],
    event_names: Optional[Sequence[str]] = None,
) -> List[str]:
    """Active event display labels (Full, Half, 10K, Elite, Open, …)."""
    return [event_display_label(e) for e in active_events(row, event_names)]
