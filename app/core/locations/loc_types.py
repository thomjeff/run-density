"""Location type and placement rules (Issue #948).

Traffic control can sit on the course (timed by its segment) or off it
(timed from a proxy location). The legacy ``course`` type is on-course
traffic.
"""

from __future__ import annotations

from typing import Any, Mapping, Tuple

from app.utils.constants import (
    LEG_MAP_NO_SNAP_LOCATION_TYPES,
    LOCATION_PLACEMENT_CHOICES,
    LOCATION_TYPE_CHOICES,
)

LEGACY_COURSE_TYPE = "course"
DEFAULT_LOCATION_TYPE = "traffic"
OFF_COURSE = "off"
ON_COURSE = "along"


def _placement_text(raw: Any) -> str:
    # YAML reads a bare ``off`` as boolean False.
    if raw is False:
        return OFF_COURSE
    return str(raw or "").strip().lower()


def normalize_type_and_placement(raw_type: Any, raw_placement: Any) -> Tuple[str, str]:
    """Return ``(loc_type, placement)`` with legacy ``course`` folded into traffic."""
    loc_type = str(raw_type or "").strip().lower()
    placement = _placement_text(raw_placement)
    if loc_type == LEGACY_COURSE_TYPE or loc_type not in LOCATION_TYPE_CHOICES:
        if placement not in LOCATION_PLACEMENT_CHOICES or placement == OFF_COURSE:
            placement = ON_COURSE
        return DEFAULT_LOCATION_TYPE, placement
    if loc_type in LEG_MAP_NO_SNAP_LOCATION_TYPES:
        return loc_type, OFF_COURSE
    if loc_type == "traffic" and placement not in LOCATION_PLACEMENT_CHOICES:
        return loc_type, OFF_COURSE
    if placement not in LOCATION_PLACEMENT_CHOICES:
        placement = ON_COURSE
    return loc_type, placement


def is_off_course(loc: Mapping[str, Any]) -> bool:
    """True when the location is timed from a proxy instead of its segment."""
    loc_type, placement = normalize_type_and_placement(
        loc.get("loc_type"), loc.get("placement")
    )
    if loc_type == "extract":
        return True
    return loc_type == "traffic" and placement == OFF_COURSE


def snaps_to_route(loc: Mapping[str, Any]) -> bool:
    """True when the leg map should snap the pin to the route."""
    _, placement = normalize_type_and_placement(
        loc.get("loc_type"), loc.get("placement")
    )
    return placement != OFF_COURSE
