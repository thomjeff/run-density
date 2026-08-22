"""Clock helpers for Execute (Issue #893)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

from app.utils.constants import DISPLAY_TIMEZONE

REOPEN_NEXT_WINDOW_MINUTES = 15
SKIP_RESOURCE_CODES = frozenset({"pass"})


def parse_hhmm(value: Any) -> Optional[int]:
    """Parse HH:MM or HH:MM:SS to minutes past midnight."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minutes = int(value)
        if minutes < 0:
            return None
        return minutes
    text = str(value).strip()
    if not text or text.upper() in ("NA", "NAN", "NONE", "NULL"):
        return None
    parts = text.split(":")
    try:
        hours = int(parts[0])
        mins = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError, IndexError):
        return None
    return hours * 60 + mins


def minutes_to_hhmm(
    minutes: Optional[int],
    with_seconds: bool = False,
) -> Optional[str]:
    if minutes is None:
        return None
    hours, mins = divmod(int(minutes), 60)
    if with_seconds:
        return f"{hours:02d}:{mins:02d}:00"
    return f"{hours:02d}:{mins:02d}"


def minutes_to_hhmmss(minutes: Optional[int]) -> Optional[str]:
    return minutes_to_hhmm(minutes, with_seconds=True)


def wall_now(timezone: str = DISPLAY_TIMEZONE) -> datetime:
    return datetime.now(ZoneInfo(timezone))


def wall_hhmm(timezone: str = DISPLAY_TIMEZONE) -> str:
    return wall_now(timezone).strftime("%H:%M")


def wall_hhmmss(timezone: str = DISPLAY_TIMEZONE) -> str:
    return wall_now(timezone).strftime("%H:%M:%S")


def display_now_hhmmss(
    clock: Mapping[str, Any],
    timezone: str = DISPLAY_TIMEZONE,
) -> str:
    if clock.get("paused") and clock.get("paused_at"):
        return str(clock["paused_at"])
    return wall_hhmmss(timezone)


def analysis_guns_hhmm(analysis: Mapping[str, Any]) -> dict[str, str]:
    """Event start times as HH:MM from analysis.json."""
    out: dict[str, str] = {}
    start_times = analysis.get("start_times") or {}
    if isinstance(start_times, Mapping):
        for key, raw in start_times.items():
            minutes = parse_hhmm(raw)
            label = minutes_to_hhmm(minutes)
            if label:
                out[str(key).strip().lower()] = label
    if out:
        return out
    for event in analysis.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        name = str(event.get("name") or "").strip().lower()
        label = minutes_to_hhmm(parse_hhmm(event.get("start_time")))
        if name and label:
            out[name] = label
    return out


def gun_deltas_minutes(
    analysis_guns: Mapping[str, str],
    operator_guns: Mapping[str, str],
) -> dict[str, int]:
    deltas: dict[str, int] = {}
    for event, planned in analysis_guns.items():
        actual = operator_guns.get(event, planned)
        planned_m = parse_hhmm(planned)
        actual_m = parse_hhmm(actual)
        if planned_m is None or actual_m is None:
            continue
        deltas[str(event)] = actual_m - planned_m
    return deltas


def controlling_event(row: Mapping[str, Any]) -> Optional[str]:
    """Event whose last_runner is latest (drives loc_end)."""
    by_event = row.get("by_event") or {}
    if not isinstance(by_event, Mapping):
        return None
    best_event = None
    best_time = None
    for name, payload in by_event.items():
        if not isinstance(payload, Mapping):
            continue
        last = parse_hhmm(payload.get("last_runner"))
        if last is None:
            continue
        if best_time is None or last >= best_time:
            best_time = last
            best_event = str(name).strip().lower()
    return best_event


def display_loc_end_minutes(
    row: Mapping[str, Any],
    deltas: Mapping[str, int],
) -> Optional[int]:
    """
    Planned loc_end plus gun-shift overlay.

    Shift uses the event that produced the latest last_runner.
    When guns are unchanged, this equals planned loc_end.
    """
    planned = parse_hhmm(row.get("loc_end"))
    if planned is None:
        return None
    if not deltas:
        return planned
    event = controlling_event(row)
    if event and event in deltas:
        return planned + int(deltas[event])
    unique = set(deltas.values())
    if len(unique) == 1:
        return planned + next(iter(unique))
    return planned


def estimate_passed(loc_end_minutes: Optional[int], now_hhmmss: str) -> bool:
    now_m = parse_hhmm(now_hhmmss)
    if loc_end_minutes is None or now_m is None:
        return False
    return now_m >= loc_end_minutes
