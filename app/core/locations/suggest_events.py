"""
Suggest location event flags (full/half/10k/elite/open) from segment membership.

Issue #765
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.utils.constants import COURSE_EVENT_IDS


def _parse_seg_ids(seg_id: Any) -> List[str]:
    if seg_id is None or seg_id == "":
        return []
    text = str(seg_id).strip().strip('"').strip("'")
    if not text:
        return []
    return [s.strip().strip('"').strip("'") for s in text.split(",") if s.strip()]


def suggest_location_events(
    location: Dict[str, Any],
    segments: List[Dict[str, Any]],
    event_ids: List[str] | None = None,
) -> Tuple[Dict[str, str], str]:
    """
    Suggest y/n event flags for a location from course segments and seg_id.

    Returns:
        (flags dict, human-readable rationale)
    """
    events = event_ids or list(COURSE_EVENT_IDS)
    seg_ids = _parse_seg_ids(location.get("seg_id"))
    if not seg_ids:
        return (
            {e: "n" for e in events},
            "Set seg_id first, then suggest events from segment membership.",
        )

    matched: List[Dict[str, Any]] = []
    for seg in segments or []:
        sid = str(seg.get("seg_id", "")).strip()
        if sid and sid in seg_ids:
            matched.append(seg)

    if not matched:
        return (
            {e: "n" for e in events},
            f"No course segments found for seg_id '{','.join(seg_ids)}'.",
        )

    union: set[str] = set()
    labels: List[str] = []
    for seg in matched:
        labels.append(str(seg.get("seg_label") or seg.get("seg_id", "")))
        for ev in seg.get("events") or []:
            union.add(str(ev).strip().lower())

    flags = {e: ("y" if e in union else "n") for e in events}
    label_part = ", ".join(labels) if labels else ",".join(seg_ids)
    active = [e for e in events if flags[e] == "y"]
    rationale = (
        f"Segment(s) {label_part}: events "
        f"{', '.join(active) if active else '(none)'}."
    )
    return flags, rationale
