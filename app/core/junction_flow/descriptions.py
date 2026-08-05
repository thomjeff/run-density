"""
Plain-language Junction Flow interaction descriptions (Issue #819 §4).

Derived from From / To / Conflicts + segment labels + per-stream events.
Not stored in junctions.json — computed for Build UI and analysis artifacts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def format_event_list(events: Sequence[str]) -> str:
    """Human event list: Full, Half, 10k → 'Full+Half' / '10k' / 'Full+Half+10k'."""
    order = ["full", "half", "10k", "elite", "open"]
    labels = {
        "full": "Full",
        "half": "Half",
        "10k": "10k",
        "elite": "Elite",
        "open": "Open",
    }
    seen = []
    lower = {str(e).lower() for e in events if e}
    for key in order:
        if key in lower:
            seen.append(labels[key])
    for e in sorted(lower):
        if e not in order:
            seen.append(e.title())
    if not seen:
        return "runners"
    return "+".join(seen)


def _seg_meta(
    nearby_by_id: Dict[str, Dict[str, Any]], seg_id: str
) -> Dict[str, Any]:
    return nearby_by_id.get(str(seg_id) or "") or {}


def _seg_label(nearby_by_id: Dict[str, Dict[str, Any]], seg_id: str) -> str:
    row = _seg_meta(nearby_by_id, seg_id)
    label = str(row.get("seg_label") or row.get("name") or "").strip()
    return label or str(seg_id)


def _seg_events(
    nearby_by_id: Dict[str, Dict[str, Any]], seg_id: str
) -> List[str]:
    row = _seg_meta(nearby_by_id, seg_id)
    events = row.get("events")
    if isinstance(events, list) and events:
        return [str(e).lower() for e in events if e]
    ek = row.get("event_kms") or {}
    if isinstance(ek, dict):
        return [str(e).lower() for e in ek.keys()]
    return []


def _named(seg_id: str, nearby_by_id: Dict[str, Dict[str, Any]]) -> str:
    label = _seg_label(nearby_by_id, seg_id)
    sid = str(seg_id)
    if not label or label == sid:
        return f"({sid})"
    return f"{label} ({sid})"


def _side_phrase(side: str) -> str:
    s = str(side or "").strip().lower()
    if s == "left":
        return "left"
    if s == "right":
        return "right"
    return ""


def cross_role_events(
    ix: Dict[str, Any], nearby_by_id: Dict[str, Dict[str, Any]]
) -> Dict[str, List[str]]:
    """Crossing = From∩To events; crossed = Conflicts events (scoped to ix.events if set)."""
    scoped = {str(e).lower() for e in (ix.get("events") or []) if e}
    from_seg = str(ix.get("from_seg_id") or "")
    to_segs = [str(s) for s in (ix.get("to_seg_ids") or []) if s]
    conflicts = str(ix.get("conflicts_with_seg_id") or "")
    from_ev = set(_seg_events(nearby_by_id, from_seg))
    to_ev: set = set()
    for t in to_segs:
        to_ev |= set(_seg_events(nearby_by_id, t))
    crossing = sorted(from_ev & to_ev) if to_ev else sorted(from_ev)
    crossed = sorted(_seg_events(nearby_by_id, conflicts))
    if scoped:
        crossing = [e for e in crossing if e in scoped] or crossing
        crossed = [e for e in crossed if e in scoped] or crossed
    return {"crossing": crossing, "crossed": crossed}


def merge_role_events(
    ix: Dict[str, Any], nearby_by_id: Dict[str, Dict[str, Any]]
) -> Dict[str, List[str]]:
    """Joining = From events; through partners = full/half on To (analysis rule)."""
    scoped = {str(e).lower() for e in (ix.get("events") or []) if e}
    from_seg = str(ix.get("from_seg_id") or "")
    to_segs = [str(s) for s in (ix.get("to_seg_ids") or []) if s]
    joining = sorted(_seg_events(nearby_by_id, from_seg))
    through: set = set()
    for t in to_segs:
        through |= set(_seg_events(nearby_by_id, t))
    through = {e for e in through if e in ("full", "half")}
    if scoped:
        joining = [e for e in joining if e in scoped] or joining
        through_list = [e for e in sorted(through) if e in scoped] or sorted(through)
    else:
        through_list = sorted(through)
    return {"joining": joining, "through": through_list}


def format_interaction_description(
    ix: Dict[str, Any],
    nearby_by_id: Dict[str, Dict[str, Any]],
) -> str:
    """
    Build a race-director description for one interaction.

    Cross example:
      10k runners from Walking Bridge South to George (S8) crossing Full runners
      from George to Aberdeen via Trail (reverse) (S11) left to
      George to Forest Hill (via University) (S25)
    """
    itype = str(ix.get("type") or "").lower()
    from_seg = str(ix.get("from_seg_id") or "").strip()
    to_segs = [str(s).strip() for s in (ix.get("to_seg_ids") or []) if str(s).strip()]
    if not from_seg or not to_segs:
        return ""

    if itype == "cross":
        roles = cross_role_events(ix, nearby_by_id)
        conflicts = str(ix.get("conflicts_with_seg_id") or "").strip()
        side = _side_phrase(str(ix.get("side") or ""))
        crossing = format_event_list(roles["crossing"])
        crossed = format_event_list(roles["crossed"])
        to_part = _named(to_segs[0], nearby_by_id)
        mid = f" {side} to " if side else " to "
        conflict_part = (
            _named(conflicts, nearby_by_id) if conflicts else "the conflict stream"
        )
        return (
            f"{crossing} runners from {_named(from_seg, nearby_by_id)} "
            f"crossing {crossed} runners from {conflict_part}"
            f"{mid}{to_part}"
        )

    # merge
    roles = merge_role_events(ix, nearby_by_id)
    joining = format_event_list(roles["joining"])
    through = format_event_list(roles["through"])
    if len(to_segs) == 1:
        to_part = _named(to_segs[0], nearby_by_id)
    else:
        to_part = ", ".join(_named(s, nearby_by_id) for s in to_segs)
    through_bit = f"{through} traffic" if through != "runners" else "through traffic"
    return (
        f"{joining} runners from {_named(from_seg, nearby_by_id)} "
        f"merging into {through_bit} on {to_part}"
    )


def role_headline_labels(
    ix: Dict[str, Any],
    nearby_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    unique_by_role_event: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Labels for analysis headlines (Issue #819 §5).

    Returns primary_label / secondary_label with events, e.g.
    'Unique 10k who met Full within 30s'.
    """
    nearby_by_id = nearby_by_id or {}
    itype = str(ix.get("type") or "").lower()
    u = unique_by_role_event or {}

    def events_from_bucket(bucket: Dict[str, Any]) -> List[str]:
        return sorted(
            str(k).lower()
            for k, v in (bucket or {}).items()
            if k != "all" and v is not None
        )

    if itype == "merge":
        joining = events_from_bucket(u.get("joining_with_full_half_copresence") or {})
        through = events_from_bucket(
            u.get("through_full_half_with_joining_copresence") or {}
        )
        if not joining or not through:
            roles = merge_role_events(ix, nearby_by_id)
            joining = joining or roles["joining"]
            through = through or roles["through"]
        return {
            "primary_label": (
                f"Unique {format_event_list(joining)} who met "
                f"{format_event_list(through)} within 30s"
            ),
            "secondary_label": (
                f"Unique {format_event_list(through)} who met "
                f"{format_event_list(joining)} within 30s"
            ),
            "primary_role": "joining",
            "secondary_role": "through",
            "primary_events": joining,
            "secondary_events": through,
        }

    crossing = events_from_bucket(u.get("crossing_with_copresence") or {})
    crossed = events_from_bucket(u.get("crossed_with_copresence") or {})
    if not crossing or not crossed:
        roles = cross_role_events(ix, nearby_by_id)
        crossing = crossing or roles["crossing"]
        crossed = crossed or roles["crossed"]
    return {
        "primary_label": (
            f"Unique {format_event_list(crossing)} who met "
            f"{format_event_list(crossed)} within 30s"
        ),
        "secondary_label": (
            f"Unique {format_event_list(crossed)} who met "
            f"{format_event_list(crossing)} within 30s"
        ),
        "primary_role": "crossing",
        "secondary_role": "crossed",
        "primary_events": crossing,
        "secondary_events": crossed,
    }
