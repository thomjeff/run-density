"""Race-day Execute clock snapshot (Issue #830 v1).

Plan-vs-clock from analysis outputs. Not live GPS. Clearance times are
last runner at the location point (#832), not Stream Passage windows.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.core.locations.pairing import time_to_seconds
from app.core.v2.timings import _format_seconds_to_hhmmss


def parse_clock_sec(value: Any) -> Optional[int]:
    """Parse HH:MM[:SS] or seconds-since-midnight into int seconds."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0, int(value))
    return time_to_seconds(value)


def classify_reopen_status(
    reopen_at_sec: Optional[int], now_sec: Optional[int]
) -> str:
    """closed | open | unknown relative to race-day clock."""
    if reopen_at_sec is None or now_sec is None:
        return "unknown"
    return "open" if int(now_sec) >= int(reopen_at_sec) else "closed"


def guns_for_day(
    analysis: Mapping[str, Any],
    day: Optional[str],
) -> List[Dict[str, Any]]:
    """Event guns (start_time minutes → seconds) for the selected day."""
    want = (day or "").strip().lower()
    guns: List[Dict[str, Any]] = []
    events = analysis.get("events") or []
    if not isinstance(events, list):
        events = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        ev_day = str(event.get("day") or "").strip().lower()
        if want and ev_day and ev_day != want:
            continue
        name = str(event.get("name") or "").strip()
        raw_start = event.get("start_time")
        try:
            start_min = int(raw_start)
        except (TypeError, ValueError):
            continue
        start_sec = start_min * 60
        guns.append(
            {
                "event": name,
                "day": ev_day,
                "start_time_min": start_min,
                "start_sec": start_sec,
                "start_hhmmss": _format_seconds_to_hhmmss(start_sec),
            }
        )
    guns.sort(key=lambda g: (g["start_sec"], g["event"]))
    return guns


def attach_clock_status(
    entries: Iterable[Mapping[str, Any]],
    now_sec: Optional[int],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for raw in entries:
        entry = dict(raw)
        reopen_sec = entry.get("reopen_at_sec")
        try:
            reopen_i = int(reopen_sec) if reopen_sec is not None else None
        except (TypeError, ValueError):
            reopen_i = None
        status = classify_reopen_status(reopen_i, now_sec)
        entry["status"] = status
        if reopen_i is None or now_sec is None:
            entry["seconds_until_reopen"] = None
        else:
            entry["seconds_until_reopen"] = max(0, reopen_i - int(now_sec))
        out.append(entry)
    return out


def day_window(
    guns: List[Mapping[str, Any]],
    entries: List[Mapping[str, Any]],
) -> Dict[str, Any]:
    starts = [int(g["start_sec"]) for g in guns if g.get("start_sec") is not None]
    reopens = [
        int(e["reopen_at_sec"])
        for e in entries
        if e.get("reopen_at_sec") is not None
    ]
    begin = min(starts) if starts else None
    end = max(reopens) if reopens else (max(starts) if starts else None)
    return {
        "start_sec": begin,
        "end_sec": end,
        "start_hhmmss": _format_seconds_to_hhmmss(begin) if begin is not None else None,
        "end_hhmmss": _format_seconds_to_hhmmss(end) if end is not None else None,
    }


def build_execute_snapshot(
    *,
    playbook: Mapping[str, Any],
    analysis: Optional[Mapping[str, Any]] = None,
    day: Optional[str] = None,
    now_sec: Optional[int] = None,
) -> Dict[str, Any]:
    """Compose guns + playbook rows with optional clock status (v1)."""
    guns = guns_for_day(analysis or {}, day)
    entries = attach_clock_status(playbook.get("entries") or [], now_sec)
    window = day_window(guns, entries)
    next_closed = next((e for e in entries if e.get("status") == "closed"), None)
    return {
        "ok": True,
        "v1": True,
        "clear_when": playbook.get("clear_when") or "last_runner",
        "run_id": playbook.get("run_id"),
        "config_id": playbook.get("config_id"),
        "day": day or playbook.get("day"),
        "now_sec": now_sec,
        "now_hhmmss": _format_seconds_to_hhmmss(now_sec) if now_sec is not None else None,
        "guns": guns,
        "window": window,
        "entries": entries,
        "count": len(entries),
        "next": {
            "rule_id": next_closed.get("rule_id") if next_closed else None,
            "blocked": next_closed.get("blocked") if next_closed else None,
            "reopen_at": next_closed.get("reopen_at") if next_closed else None,
        },
    }
