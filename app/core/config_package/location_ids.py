"""Unique numeric IDs for course.json location records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _parse_location_id(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def assign_unique_location_ids(locations: List[Dict[str, Any]]) -> None:
    """Ensure each location has a distinct positive integer ``id``."""
    used: set[int] = set()
    next_candidate = 1
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        parsed = _parse_location_id(loc.get("id", loc.get("loc_id")))
        if parsed is not None and parsed > 0 and parsed not in used:
            loc["id"] = parsed
            used.add(parsed)
            next_candidate = max(next_candidate, parsed + 1)
            continue
        while next_candidate in used:
            next_candidate += 1
        loc["id"] = next_candidate
        used.add(next_candidate)
        next_candidate += 1


def allocate_location_id(used: set[int]) -> int:
    next_id = 1
    while next_id in used:
        next_id += 1
    used.add(next_id)
    return next_id


def parse_location_id(raw: Any) -> Optional[int]:
    return _parse_location_id(raw)
