"""
Location / pass identity (2027 terminology).

- ``loc_id``: short human integer for a Location (phone / UI / one-pager)
- ``pass_id``: timed instance (course.json ``id``; package/analysis pass rows)
- ``pass_key``: opaque Crockford unifier for passes at the same Location (system join)

``leg_loc_key`` remains the leg-library pin identity (``{leg_id}:{index}``).
"""

from __future__ import annotations

from typing import Any, Dict, List, MutableMapping, Optional, Sequence, Set

from app.core.config_package.location_ids import (
    allocate_location_id,
    assign_unique_location_ids,
    parse_location_id,
)
from app.core.config_package.location_keys import (
    ensure_location_key,
    is_valid_location_key,
)


def effective_pass_key(row: MutableMapping[str, Any]) -> str:
    """Return trimmed pass_key (legacy location_key / leg_loc_key fallback)."""
    for field in ("pass_key", "location_key", "leg_loc_key"):
        raw = row.get(field)
        if raw is None:
            continue
        text = str(raw).strip()
        if text and text.lower() not in ("nan", "none", "null"):
            return text
    return ""


def get_pass_id(row: MutableMapping[str, Any]) -> Optional[int]:
    """Pass instance id from ``pass_id`` or course ``id`` (not human ``loc_id``)."""
    for field in ("pass_id", "id"):
        parsed = parse_location_id(row.get(field))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def get_loc_id(row: MutableMapping[str, Any]) -> Optional[int]:
    """Human Location id when present as ``loc_id``."""
    parsed = parse_location_id(row.get("loc_id"))
    if parsed is not None and parsed > 0:
        return parsed
    return None


def migrate_pass_key_fields(loc: MutableMapping[str, Any]) -> None:
    """Normalize ``pass_key`` from legacy ``location_key`` on a course/pass row."""
    pk = str(loc.get("pass_key") or "").strip()
    if not pk or pk.lower() in ("nan", "none", "null"):
        legacy = str(loc.get("location_key") or "").strip()
        if legacy and legacy.lower() not in ("nan", "none", "null"):
            loc["pass_key"] = legacy
    if loc.get("pass_key"):
        # Keep legacy field in sync for older UI/readers during cutover.
        loc["location_key"] = loc["pass_key"]


def migrate_proxy_pass_fields(loc: MutableMapping[str, Any]) -> None:
    """Normalize ``proxy_pass_id`` from legacy ``proxy_loc_id``."""
    if loc.get("proxy_pass_id") not in (None, ""):
        return
    legacy = loc.get("proxy_loc_id")
    if legacy not in (None, ""):
        loc["proxy_pass_id"] = legacy


def ensure_pass_key(loc: Dict[str, Any], used: Optional[Set[str]] = None) -> str:
    """Ensure a valid Crockford ``pass_key`` (shared keys allowed for paired passes)."""
    migrate_pass_key_fields(loc)
    # Promote a Crockford-shaped leg_loc_key when pass_key is still empty
    if not is_valid_location_key(loc.get("pass_key") or loc.get("location_key")):
        leg = str(loc.get("leg_loc_key") or "").strip()
        if is_valid_location_key(leg):
            loc["pass_key"] = leg
            loc["location_key"] = leg
    if loc.get("pass_key") and not loc.get("location_key"):
        loc["location_key"] = loc["pass_key"]
    key = ensure_location_key(loc, used)
    loc["pass_key"] = key
    loc["location_key"] = key
    return key


def stamp_pass_identity(locations: Sequence[Dict[str, Any]]) -> None:
    """
    Stamp pass_id / pass_key / loc_id on course location rows in place.

    - ``id`` and ``pass_id`` are unique per timed pass
    - ``pass_key`` groups passes at the same Location
    - ``loc_id`` is a stable short int shared by all rows with the same pass_key
    """
    locs: List[Dict[str, Any]] = [loc for loc in locations if isinstance(loc, dict)]
    if not locs:
        return

    used_keys: Set[str] = set()
    for loc in locs:
        migrate_pass_key_fields(loc)
        migrate_proxy_pass_fields(loc)
        # Prefer existing valid pass_key when collecting used set for allocation
        existing = str(loc.get("pass_key") or loc.get("location_key") or "").strip()
        if is_valid_location_key(existing):
            used_keys.add(existing)

    for loc in locs:
        ensure_pass_key(loc, used_keys)

    assign_unique_location_ids(locs)
    for loc in locs:
        pid = parse_location_id(loc.get("id"))
        if pid is not None:
            loc["pass_id"] = pid
            loc["id"] = pid
        # proxy: prefer proxy_pass_id; keep proxy_loc_id alias for older editors
        migrate_proxy_pass_fields(loc)
        if loc.get("proxy_pass_id") not in (None, ""):
            loc["proxy_loc_id"] = loc["proxy_pass_id"]

    _assign_human_loc_ids(locs)


def _assign_human_loc_ids(locs: Sequence[Dict[str, Any]]) -> None:
    """Assign human ``loc_id`` per distinct ``pass_key`` (preserve existing when consistent)."""
    key_groups: Dict[str, List[Dict[str, Any]]] = {}
    singles: List[Dict[str, Any]] = []
    for loc in locs:
        key = effective_pass_key(loc)
        if key:
            key_groups.setdefault(key, []).append(loc)
        else:
            singles.append(loc)

    key_to_loc_id: Dict[str, int] = {}
    used_loc_ids: Set[int] = set()

    for key, group in key_groups.items():
        loc_ids = [get_loc_id(r) for r in group]
        unique = {i for i in loc_ids if i is not None}
        if len(group) >= 2 and len(unique) == 1:
            # Paired passes already share a human loc_id
            shared = next(iter(unique))
            if shared not in used_loc_ids:
                key_to_loc_id[key] = shared
                used_loc_ids.add(shared)
            continue
        if len(group) == 1 and loc_ids[0] is not None:
            lid = loc_ids[0]
            pid = get_pass_id(group[0])
            # Legacy CSV: loc_id was the pass instance — treat as unset
            # Also skip if another pass_key already claimed this human id (#838).
            if lid != pid and lid not in used_loc_ids:
                key_to_loc_id[key] = lid
                used_loc_ids.add(lid)

    for key in sorted(key_groups.keys()):
        if key not in key_to_loc_id:
            key_to_loc_id[key] = allocate_location_id(used_loc_ids)

    for loc in locs:
        key = effective_pass_key(loc)
        if key:
            loc["loc_id"] = key_to_loc_id[key]
            continue
        # No pass_key: 1:1 loc_id per pass (allocate if missing / legacy)
        lid = get_loc_id(loc)
        pid = get_pass_id(loc)
        if lid is not None and lid != pid and lid not in used_loc_ids:
            used_loc_ids.add(lid)
            continue
        loc["loc_id"] = allocate_location_id(used_loc_ids)
