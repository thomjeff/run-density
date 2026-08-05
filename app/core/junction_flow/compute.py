"""
Junction Flow compute (Issue #818).

Constant-pace presence at junction nodes with dwell co-presence gating.
Merge partners are full/half on To streams only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.core.junction_flow.descriptions import (
    format_interaction_description,
    role_headline_labels,
)

NODE_DWELL_SEC = 30.0
MERGE_PARTNER_EVENTS = ("full", "half")


def _enrich_interaction_result(
    result: "InteractionResult",
    ix: Dict[str, Any],
    nearby_by_id: Dict[str, Dict[str, Any]],
) -> "InteractionResult":
    authored = str(ix.get("description") or "").strip()
    result.description = authored or format_interaction_description(ix, nearby_by_id)
    result.headline_labels = role_headline_labels(
        ix, nearby_by_id, result.unique_by_role_event
    )
    return result


@dataclass
class StreamPresence:
    role: str  # crossing | crossed | joining | through
    seg_id: str
    event: str
    runner_ids: np.ndarray
    node_times_sec: np.ndarray  # instant at junction node
    paces: np.ndarray
    quintiles: np.ndarray  # 1=lead (fast) .. 5=rear (slow) within event


@dataclass
class InteractionResult:
    interaction_id: str
    type: str
    side: str
    label: str
    events: List[str]
    window_start_hhmm: str
    window_end_hhmm: str
    window_minutes: float
    unique_by_role_event: Dict[str, Dict[str, int]]
    peak_concurrent: Dict[str, int]
    field_crosstab: List[Dict[str, Any]]
    minute_rows: List[Dict[str, Any]]
    notes: List[str] = field(default_factory=list)
    description: str = ""
    headline_labels: Dict[str, Any] = field(default_factory=dict)
    mix_breakdown: Dict[str, Any] = field(default_factory=dict)


def _hhmm(seconds: float) -> str:
    minutes = int(max(0, seconds) // 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _load_runners(package_dir: Path, event: str) -> pd.DataFrame:
    path = package_dir / f"{event}_runners.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["event"] = event
    df["pace"] = pd.to_numeric(df["pace"], errors="coerce")
    df["start_offset"] = pd.to_numeric(df["start_offset"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["pace", "runner_id"])
    df = df[df["pace"] > 0].copy()
    # Q1 = lead (fastest / lowest pace), Q5 = rear
    try:
        df["quintile"] = pd.qcut(
            df["pace"], 5, labels=[1, 2, 3, 4, 5], duplicates="drop"
        )
        df["quintile"] = df["quintile"].astype(int)
    except ValueError:
        # Too few distinct paces — rank into up to 5 bins
        ranks = df["pace"].rank(method="first")
        df["quintile"] = pd.qcut(ranks, min(5, len(df)), labels=False) + 1
        df["quintile"] = df["quintile"].astype(int)
    return df


def _node_km_for_segment(
    nearby_by_id: Dict[str, Dict[str, Any]],
    seg_id: str,
    event: str,
) -> Optional[float]:
    """Km along the event course at the junction endpoint of this segment."""
    row = nearby_by_id.get(seg_id) or {}
    ek = (row.get("event_kms") or {}).get(event) or {}
    near = str(row.get("near_endpoint") or "")
    if near in ("end", "both") and ek.get("to_km") is not None:
        return float(ek["to_km"])
    if near in ("start", "both") and ek.get("from_km") is not None:
        return float(ek["from_km"])
    # Fallback: prefer to_km then from_km
    if ek.get("to_km") is not None:
        return float(ek["to_km"])
    if ek.get("from_km") is not None:
        return float(ek["from_km"])
    return None


def _presence_at_node(
    runners: pd.DataFrame,
    gun_min: float,
    node_km: float,
    role: str,
    seg_id: str,
    event: str,
) -> StreamPresence:
    pace_sec = runners["pace"].to_numpy(dtype=float) * 60.0
    offset = runners["start_offset"].to_numpy(dtype=float)
    t0 = float(gun_min) * 60.0
    node_times = t0 + offset + pace_sec * float(node_km)
    return StreamPresence(
        role=role,
        seg_id=seg_id,
        event=event,
        runner_ids=runners["runner_id"].astype(str).to_numpy(),
        node_times_sec=node_times,
        paces=runners["pace"].to_numpy(dtype=float),
        quintiles=runners["quintile"].to_numpy(dtype=int),
    )


def _minute_metrics(
    node_times: np.ndarray,
    start_sec: float,
    end_sec: float,
    dwell_sec: float = NODE_DWELL_SEC,
) -> Tuple[List[float], List[Dict[str, int]]]:
    """
    Treat each runner as present for dwell_sec centered on node transit.
    Entries = arrivals in minute; exits = departures; concurrent ≈ present.
    """
    if node_times.size == 0:
        return [], []
    entry = node_times - dwell_sec / 2.0
    exit_ = node_times + dwell_sec / 2.0
    entry_sorted = np.sort(entry)
    exit_sorted = np.sort(exit_)
    start_floor = int(math.floor(start_sec / 60.0) * 60)
    end_ceil = int(math.ceil(end_sec / 60.0) * 60)
    if end_ceil <= start_floor:
        return [], []
    minute_starts = list(range(start_floor, end_ceil, 60))
    out: List[Dict[str, int]] = []
    for ms in minute_starts:
        me = ms + 60
        entries = int(
            np.searchsorted(entry_sorted, me, side="left")
            - np.searchsorted(entry_sorted, ms, side="left")
        )
        exits = int(
            np.searchsorted(exit_sorted, me, side="left")
            - np.searchsorted(exit_sorted, ms, side="left")
        )
        concurrent = int(
            np.searchsorted(entry_sorted, me, side="left")
            - np.searchsorted(exit_sorted, ms, side="left")
        )
        out.append({"concurrent": concurrent, "entries": entries, "exits": exits})
    return [float(s) for s in minute_starts], out


def _combine_presences(parts: Sequence[StreamPresence]) -> StreamPresence:
    if not parts:
        raise ValueError("no stream parts to combine")
    return StreamPresence(
        role=parts[0].role,
        seg_id=",".join(sorted({p.seg_id for p in parts})),
        event=",".join(sorted({p.event for p in parts})),
        runner_ids=np.concatenate([p.runner_ids for p in parts]),
        node_times_sec=np.concatenate([p.node_times_sec for p in parts]),
        paces=np.concatenate([p.paces for p in parts]),
        quintiles=np.concatenate([p.quintiles for p in parts]),
    )


def _unique_in_window(p: StreamPresence, start_sec: float, end_sec: float) -> int:
    mask = (p.node_times_sec >= start_sec) & (p.node_times_sec <= end_sec)
    return int(np.unique(p.runner_ids[mask]).size)


def _nearest_partner_dt(
    t: float,
    partner_times_sorted: np.ndarray,
) -> Optional[float]:
    if partner_times_sorted.size == 0:
        return None
    idx = int(np.searchsorted(partner_times_sorted, t, side="left"))
    best_dt: Optional[float] = None
    for j in (idx - 1, idx):
        if 0 <= j < partner_times_sorted.size:
            dt = abs(float(partner_times_sorted[j] - t))
            if best_dt is None or dt < best_dt:
                best_dt = dt
    return best_dt


def _copresent_runner_ids(
    primary: StreamPresence,
    partner: StreamPresence,
    start_sec: float,
    end_sec: float,
    dwell_sec: float = NODE_DWELL_SEC,
) -> Tuple[set, set]:
    """Return (ids with a partner within dwell, ids in window without a partner)."""
    p_mask = (primary.node_times_sec >= start_sec) & (primary.node_times_sec <= end_sec)
    partner_mask = (partner.node_times_sec >= start_sec - dwell_sec) & (
        partner.node_times_sec <= end_sec + dwell_sec
    )
    p_t = primary.node_times_sec[p_mask]
    p_id = primary.runner_ids[p_mask].astype(str)
    partner_t = np.sort(partner.node_times_sec[partner_mask])
    with_ids: set = set()
    without_ids: set = set()
    for i in range(p_t.size):
        rid = str(p_id[i])
        if rid in with_ids:
            continue
        dt = _nearest_partner_dt(float(p_t[i]), partner_t)
        if dt is not None and dt <= dwell_sec:
            with_ids.add(rid)
            without_ids.discard(rid)
        elif rid not in with_ids:
            without_ids.add(rid)
    return with_ids, without_ids - with_ids


def _unique_with_copresence(
    primary: StreamPresence,
    partner: StreamPresence,
    start_sec: float,
    end_sec: float,
    dwell_sec: float = NODE_DWELL_SEC,
) -> Dict[str, int]:
    """
    Per-runner co-presence at the node.

    A primary runner counts as "with_partner" only if some partner runner's
    node transit is within dwell_sec of theirs (not merely in the same window).
    """
    with_ids, without_ids = _copresent_runner_ids(
        primary, partner, start_sec, end_sec, dwell_sec=dwell_sec
    )
    return {
        "in_window": len(with_ids | without_ids),
        "with_partner": len(with_ids),
        "without_partner": len(without_ids),
    }


def _event_mix_rows(
    primary_by_event: Dict[str, StreamPresence],
    partner_by_event: Dict[str, StreamPresence],
    start_sec: float,
    end_sec: float,
) -> Dict[str, Any]:
    """Unique primary runners who met each partner event within dwell (union ≠ sum)."""
    out: Dict[str, Any] = {}
    for event, primary in primary_by_event.items():
        vs: Dict[str, int] = {}
        id_sets: Dict[str, set] = {}
        for other, partner in partner_by_event.items():
            ids, _ = _copresent_runner_ids(primary, partner, start_sec, end_sec)
            vs[other] = len(ids)
            id_sets[other] = ids
        union: set = set()
        for ids in id_sets.values():
            union |= ids
        in_two = sum(
            1 for rid in union if sum(1 for ids in id_sets.values() if rid in ids) >= 2
        )
        out[event] = {
            "vs": vs,
            "unique": len(union),
            "in_two_or_more": in_two,
        }
    return out


def _filter_presence_events(
    parts: Sequence[StreamPresence], events: Sequence[str]
) -> List[StreamPresence]:
    wanted = {str(e).lower() for e in events}
    return [p for p in parts if str(p.event).lower() in wanted]


def _by_event_combined(
    parts: Sequence[StreamPresence],
) -> Dict[str, StreamPresence]:
    buckets: Dict[str, List[StreamPresence]] = {}
    for p in parts:
        buckets.setdefault(str(p.event).lower(), []).append(p)
    return {
        event: parts_e[0] if len(parts_e) == 1 else _combine_presences(parts_e)
        for event, parts_e in buckets.items()
    }


def _crosstab(
    a: StreamPresence,
    b: StreamPresence,
    start_sec: float,
    end_sec: float,
    dwell_sec: float = NODE_DWELL_SEC,
) -> List[Dict[str, Any]]:
    """
    Concurrent-participation crosstab by quintile:
    count unique A runners whose node time overlaps (±dwell/2) with some B runner,
    bucketed by (A quintile, B quintile of a concurrent partner).
    Simplified: for each A in window, find if any B within dwell of A's time;
    use nearest B's quintile.
    """
    a_mask = (a.node_times_sec >= start_sec) & (a.node_times_sec <= end_sec)
    b_mask = (b.node_times_sec >= start_sec - dwell_sec) & (
        b.node_times_sec <= end_sec + dwell_sec
    )
    a_t = a.node_times_sec[a_mask]
    a_q = a.quintiles[a_mask]
    a_id = a.runner_ids[a_mask]
    b_t = b.node_times_sec[b_mask]
    b_q = b.quintiles[b_mask]
    if a_t.size == 0 or b_t.size == 0:
        return []
    order = np.argsort(b_t)
    b_t_s = b_t[order]
    b_q_s = b_q[order]
    counts: Dict[Tuple[int, int], set] = {}
    seen_a: set = set()
    for i in range(a_t.size):
        rid = str(a_id[i])
        if rid in seen_a:
            continue
        idx = int(np.searchsorted(b_t_s, a_t[i], side="left"))
        candidates = []
        if idx < b_t_s.size:
            candidates.append(idx)
        if idx > 0:
            candidates.append(idx - 1)
        best = None
        best_dt = None
        for j in candidates:
            dt = abs(float(b_t_s[j] - a_t[i]))
            if best_dt is None or dt < best_dt:
                best_dt = dt
                best = j
        if best is None or best_dt is None or best_dt > dwell_sec:
            continue
        seen_a.add(rid)
        key = (int(a_q[i]), int(b_q_s[best]))
        counts.setdefault(key, set()).add(rid)
    rows = []
    for (qa, qb), ids in sorted(counts.items()):
        rows.append(
            {
                "crossing_or_joining_quintile": qa,
                "crossed_or_through_quintile": qb,
                "unique_crossing_or_joining_runners": len(ids),
            }
        )
    return rows


def _analyze_pair(
    *,
    ix: Dict[str, Any],
    primary: StreamPresence,
    secondary: StreamPresence,
    primary_label: str,
    secondary_label: str,
    notes: List[str],
) -> InteractionResult:
    if primary.node_times_sec.size == 0 or secondary.node_times_sec.size == 0:
        return InteractionResult(
            interaction_id=str(ix.get("id") or ""),
            type=str(ix.get("type") or ""),
            side=str(ix.get("side") or ""),
            label=f"{primary_label} vs {secondary_label}",
            events=list(ix.get("events") or []),
            window_start_hhmm="—",
            window_end_hhmm="—",
            window_minutes=0.0,
            unique_by_role_event={},
            peak_concurrent={},
            field_crosstab=[],
            minute_rows=[],
            notes=notes + ["No runners on one or both streams for scoped events."],
        )

    t0 = float(min(primary.node_times_sec.min(), secondary.node_times_sec.min()))
    t1 = float(max(primary.node_times_sec.max(), secondary.node_times_sec.max()))
    m_pri, met_pri = _minute_metrics(primary.node_times_sec, t0, t1)
    m_sec, met_sec = _minute_metrics(secondary.node_times_sec, t0, t1)
    # Align on primary minutes (same grid)
    concurrent_both = []
    minute_rows = []
    for i, ms in enumerate(m_pri):
        ca = met_pri[i]["concurrent"]
        cb = met_sec[i]["concurrent"] if i < len(met_sec) else 0
        concurrent_both.append(ca > 0 and cb > 0)
        minute_rows.append(
            {
                "minute_start": _hhmm(ms),
                "minute_end": _hhmm(ms + 60),
                f"{primary_label}_count": ca,
                f"{primary_label}_entries": met_pri[i]["entries"],
                f"{primary_label}_exits": met_pri[i]["exits"],
                f"{secondary_label}_count": cb,
                f"{secondary_label}_entries": met_sec[i]["entries"] if i < len(met_sec) else 0,
                f"{secondary_label}_exits": met_sec[i]["exits"] if i < len(met_sec) else 0,
                "both_present": bool(ca > 0 and cb > 0),
            }
        )

    if any(concurrent_both):
        idxs = [i for i, v in enumerate(concurrent_both) if v]
        w0 = m_pri[idxs[0]]
        w1 = m_pri[idxs[-1]] + 60
    else:
        w0, w1 = t0, t1
        notes.append("No minute with both streams concurrent; window falls back to full span.")

    # Unique by role × event
    unique: Dict[str, Dict[str, int]] = {primary_label: {}, secondary_label: {}}
    for p, label in ((primary, primary_label), (secondary, secondary_label)):
        # split combined events if needed
        mask = (p.node_times_sec >= w0) & (p.node_times_sec <= w1)
        # event field may be comma-joined when combined; regroup via runner list sizes per building
        unique[label]["all"] = int(np.unique(p.runner_ids[mask]).size)

    # Per-event unique: recompute from parts stored in notes? Simpler: parse from building below in caller.
    peak = {
        primary_label: max(
            (r[f"{primary_label}_count"] for r in minute_rows if r["both_present"]),
            default=0,
        ),
        secondary_label: max(
            (r[f"{secondary_label}_count"] for r in minute_rows if r["both_present"]),
            default=0,
        ),
    }

    return InteractionResult(
        interaction_id=str(ix.get("id") or ""),
        type=str(ix.get("type") or ""),
        side=str(ix.get("side") or ""),
        label=f"{primary_label} vs {secondary_label}",
        events=list(ix.get("events") or []),
        window_start_hhmm=_hhmm(w0),
        window_end_hhmm=_hhmm(w1),
        window_minutes=max(0.0, (w1 - w0) / 60.0),
        unique_by_role_event=unique,
        peak_concurrent=peak,
        field_crosstab=_crosstab(primary, secondary, w0, w1),
        minute_rows=minute_rows,
        notes=notes,
    )


def build_stream_parts(
    *,
    seg_id: str,
    role: str,
    events: Sequence[str],
    nearby_by_id: Dict[str, Dict[str, Any]],
    runners_by_event: Dict[str, pd.DataFrame],
    gun_by_event: Dict[str, float],
) -> Tuple[List[StreamPresence], List[str]]:
    parts: List[StreamPresence] = []
    notes: List[str] = []
    for event in events:
        if event not in runners_by_event:
            notes.append(f"No runners file for event={event}")
            continue
        node_km = _node_km_for_segment(nearby_by_id, seg_id, event)
        if node_km is None:
            notes.append(f"No node km for {seg_id}/{event}")
            continue
        # Only include runners whose event uses this segment (event_kms present)
        row = nearby_by_id.get(seg_id) or {}
        if event not in (row.get("event_kms") or {}):
            notes.append(f"{seg_id} not on event={event}; skipped")
            continue
        parts.append(
            _presence_at_node(
                runners_by_event[event],
                gun_by_event[event],
                node_km,
                role,
                seg_id,
                event,
            )
        )
    return parts, notes


def analyze_interaction(
    ix: Dict[str, Any],
    nearby_by_id: Dict[str, Dict[str, Any]],
    runners_by_event: Dict[str, pd.DataFrame],
    gun_by_event: Dict[str, float],
) -> InteractionResult:
    events = [str(e).lower() for e in (ix.get("events") or [])]
    itype = str(ix.get("type") or "").lower()
    notes: List[str] = []

    if itype == "cross":
        from_seg = str(ix.get("from_seg_id") or "")
        to_seg = (ix.get("to_seg_ids") or [None])[0]
        conflicts = str(ix.get("conflicts_with_seg_id") or "")
        # Crossing stream: runners who use From (at node). Path To is used to
        # identify the turning stream events (intersection with To's events).
        crossing_events = []
        for e in events:
            from_km = _node_km_for_segment(nearby_by_id, from_seg, e)
            to_km = _node_km_for_segment(nearby_by_id, str(to_seg), e)
            if from_km is not None and to_km is not None:
                crossing_events.append(e)
        if not crossing_events:
            crossing_events = events
            notes.append("Could not refine crossing events via From∩To; using interaction events.")

        crossed_events = []
        for e in events:
            if _node_km_for_segment(nearby_by_id, conflicts, e) is not None:
                crossed_events.append(e)
        if not crossed_events:
            crossed_events = events
            notes.append("Conflicts stream missing for some events; using interaction events.")

        pri_parts, n1 = build_stream_parts(
            seg_id=from_seg,
            role="crossing",
            events=crossing_events,
            nearby_by_id=nearby_by_id,
            runners_by_event=runners_by_event,
            gun_by_event=gun_by_event,
        )
        sec_parts, n2 = build_stream_parts(
            seg_id=conflicts,
            role="crossed",
            events=crossed_events,
            nearby_by_id=nearby_by_id,
            runners_by_event=runners_by_event,
            gun_by_event=gun_by_event,
        )
        notes.extend(n1 + n2)
        # Annotate To for mapping
        notes.append(f"Cross path {from_seg}→{to_seg} conflicts {conflicts}; side={ix.get('side')}")
        for e in crossing_events:
            notes.append(
                f"map crossing {e}: {from_seg}@{_node_km_for_segment(nearby_by_id, from_seg, e)}km "
                f"→ {to_seg}@{_node_km_for_segment(nearby_by_id, str(to_seg), e)}km"
            )
        for e in crossed_events:
            notes.append(
                f"map crossed {e}: {conflicts}@{_node_km_for_segment(nearby_by_id, conflicts, e)}km"
            )

        if not pri_parts or not sec_parts:
            return _enrich_interaction_result(
                InteractionResult(
                    interaction_id=str(ix.get("id") or ""),
                    type="cross",
                    side=str(ix.get("side") or ""),
                    label=f"{from_seg}→{to_seg} vs {conflicts}",
                    events=events,
                    window_start_hhmm="—",
                    window_end_hhmm="—",
                    window_minutes=0.0,
                    unique_by_role_event={},
                    peak_concurrent={},
                    field_crosstab=[],
                    minute_rows=[],
                    notes=notes,
                ),
                ix,
                nearby_by_id,
            )

        primary = _combine_presences(pri_parts)
        secondary = _combine_presences(sec_parts)
        # Concurrent minutes + peaks use full streams; unique counts require
        # per-runner dwell co-presence (same gate as merge).
        result = _analyze_pair(
            ix=ix,
            primary=primary,
            secondary=secondary,
            primary_label="crossing",
            secondary_label="crossed",
            notes=notes,
        )

        def _parse_hhmm(s: str) -> float:
            if not s or s == "—":
                return 0.0
            hh, mm = s.split(":")
            return int(hh) * 3600 + int(mm) * 60

        w0 = _parse_hhmm(result.window_start_hhmm)
        w1 = _parse_hhmm(result.window_end_hhmm)
        crossing_cp = _unique_with_copresence(primary, secondary, w0, w1)
        crossed_cp = _unique_with_copresence(secondary, primary, w0, w1)
        notes.append(
            "Cross uniques gated by dwell co-presence at node "
            f"(±{int(NODE_DWELL_SEC) // 2}s); window-only counts kept for comparison."
        )
        result.notes = notes
        result.unique_by_role_event = {
            "crossing_in_window": {
                event: _unique_in_window(p, w0, w1)
                for event, p in _by_event_combined(pri_parts).items()
            },
            "crossed_in_window": {
                event: _unique_in_window(p, w0, w1)
                for event, p in _by_event_combined(sec_parts).items()
            },
            "crossing_with_copresence": {
                "all": crossing_cp["with_partner"],
                **{
                    event: _unique_with_copresence(p, secondary, w0, w1)["with_partner"]
                    for event, p in _by_event_combined(pri_parts).items()
                },
            },
            "crossing_without_copresence": {"all": crossing_cp["without_partner"]},
            "crossed_with_copresence": {
                "all": crossed_cp["with_partner"],
                **{
                    event: _unique_with_copresence(p, primary, w0, w1)["with_partner"]
                    for event, p in _by_event_combined(sec_parts).items()
                },
            },
            "crossed_without_copresence": {"all": crossed_cp["without_partner"]},
        }
        result.field_crosstab = _crosstab(primary, secondary, w0, w1)
        pri_by_event = _by_event_combined(pri_parts)
        sec_by_event = _by_event_combined(sec_parts)
        result.mix_breakdown = {
            "meeting": _event_mix_rows(pri_by_event, sec_by_event, w0, w1),
            "met_by": _event_mix_rows(sec_by_event, pri_by_event, w0, w1),
            "primary_events": list(pri_by_event.keys()),
            "secondary_events": list(sec_by_event.keys()),
        }
        result.label = f"{from_seg}→{to_seg} vs {conflicts}"
        return _enrich_interaction_result(result, ix, nearby_by_id)

    # merge
    from_seg = str(ix.get("from_seg_id") or "")
    to_segs = [str(s) for s in (ix.get("to_seg_ids") or [])]
    join_parts, n1 = build_stream_parts(
        seg_id=from_seg,
        role="joining",
        events=events,
        nearby_by_id=nearby_by_id,
        runners_by_event=runners_by_event,
        gun_by_event=gun_by_event,
    )
    through_parts: List[StreamPresence] = []
    notes.extend(n1)
    notes.append(
        "Merge is junction-level: through stream unions all To segments; "
        "each To keeps event km/time for map/context."
    )
    # A merge "counts" only when a full/half runner is at the node with the
    # joining runner — not merely because full/half use S9/S22 sometime.
    merge_partner_events = MERGE_PARTNER_EVENTS
    notes.append(
        "Merge co-presence partners = full/half at To node within dwell; "
        "same-event through (e.g. 10k already on trail) does not count."
    )
    for to_seg in to_segs:
        parts, n = build_stream_parts(
            seg_id=to_seg,
            role="through",
            events=events,
            nearby_by_id=nearby_by_id,
            runners_by_event=runners_by_event,
            gun_by_event=gun_by_event,
        )
        notes.extend(n)
        through_parts.extend(parts)
        for e in events:
            km = _node_km_for_segment(nearby_by_id, to_seg, e)
            if km is not None:
                notes.append(f"map through {to_seg}/{e} @ {km} km")

    partner_parts = _filter_presence_events(through_parts, merge_partner_events)
    if not join_parts or not partner_parts:
        return _enrich_interaction_result(
            InteractionResult(
                interaction_id=str(ix.get("id") or ""),
                type="merge",
                side=str(ix.get("side") or ""),
                label=f"{from_seg}→{','.join(to_segs)}",
                events=events,
                window_start_hhmm="—",
                window_end_hhmm="—",
                window_minutes=0.0,
                unique_by_role_event={},
                peak_concurrent={},
                field_crosstab=[],
                minute_rows=[],
                notes=notes
                + (
                    ["No full/half through presence at To streams."]
                    if join_parts and not partner_parts
                    else []
                ),
            ),
            ix,
            nearby_by_id,
        )

    primary = _combine_presences(join_parts)
    # Minute concurrency / involvement window vs full+half partners only
    secondary = _combine_presences(partner_parts)
    result = _analyze_pair(
        ix=ix,
        primary=primary,
        secondary=secondary,
        primary_label="joining",
        secondary_label="through_full_half",
        notes=notes,
    )

    def _parse_hhmm(s: str) -> float:
        if not s or s == "—":
            return 0.0
        hh, mm = s.split(":")
        return int(hh) * 3600 + int(mm) * 60

    w0 = _parse_hhmm(result.window_start_hhmm)
    w1 = _parse_hhmm(result.window_end_hhmm)
    joining_cp = _unique_with_copresence(primary, secondary, w0, w1)
    partner_cp = _unique_with_copresence(secondary, primary, w0, w1)

    # Through uniques (window) for context — all To events, deduped
    through_ids = set()
    through_by_event: Dict[str, set] = {}
    for p in through_parts:
        mask = (p.node_times_sec >= w0) & (p.node_times_sec <= w1)
        ids = set(p.runner_ids[mask].astype(str))
        through_ids |= ids
        through_by_event.setdefault(p.event, set()).update(ids)

    result.unique_by_role_event = {
        "joining_in_window": {
            event: _unique_in_window(p, w0, w1)
            for event, p in _by_event_combined(join_parts).items()
        },
        "joining_with_full_half_copresence": {
            "all": joining_cp["with_partner"],
            **{
                event: _unique_with_copresence(p, secondary, w0, w1)["with_partner"]
                for event, p in _by_event_combined(join_parts).items()
            },
        },
        "joining_without_full_half": {"all": joining_cp["without_partner"]},
        "through_full_half_with_joining_copresence": {
            "all": partner_cp["with_partner"],
            **{
                event: _unique_with_copresence(p, primary, w0, w1)["with_partner"]
                for event, p in _by_event_combined(partner_parts).items()
            },
        },
        "through_in_window": {e: len(ids) for e, ids in through_by_event.items()},
        "through_all_deduped_in_window": {"all": len(through_ids)},
    }
    result.field_crosstab = _crosstab(primary, secondary, w0, w1)
    join_by_event = _by_event_combined(join_parts)
    partner_by_event = _by_event_combined(partner_parts)
    result.mix_breakdown = {
        "meeting": _event_mix_rows(join_by_event, partner_by_event, w0, w1),
        "met_by": _event_mix_rows(partner_by_event, join_by_event, w0, w1),
        "primary_events": list(join_by_event.keys()),
        "secondary_events": list(partner_by_event.keys()),
    }
    result.label = f"{from_seg}→{','.join(to_segs)}"
    return _enrich_interaction_result(result, ix, nearby_by_id)


def prepare_runners_by_event(runners_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Split runners DataFrame by event and attach pace quintiles (Q1 lead … Q5 rear)."""
    if runners_df is None or runners_df.empty:
        return {}
    out: Dict[str, pd.DataFrame] = {}
    df = runners_df.copy()
    df["event"] = df["event"].astype(str).str.lower()
    df["pace"] = pd.to_numeric(df["pace"], errors="coerce")
    df["start_offset"] = pd.to_numeric(df["start_offset"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["pace", "runner_id"])
    df = df[df["pace"] > 0]
    for event, part in df.groupby("event"):
        part = part.copy()
        try:
            part["quintile"] = pd.qcut(
                part["pace"], 5, labels=[1, 2, 3, 4, 5], duplicates="drop"
            )
            part["quintile"] = part["quintile"].astype(int)
        except ValueError:
            ranks = part["pace"].rank(method="first")
            part["quintile"] = pd.qcut(ranks, min(5, len(part)), labels=False) + 1
            part["quintile"] = part["quintile"].astype(int)
        out[str(event)] = part
    return out


def interaction_to_dict(result: InteractionResult) -> Dict[str, Any]:
    return {
        "id": result.interaction_id,
        "type": result.type,
        "side": result.side,
        "label": result.label,
        "description": getattr(result, "description", "") or "",
        "events": result.events,
        "window_start": result.window_start_hhmm,
        "window_end": result.window_end_hhmm,
        "window_minutes": round(result.window_minutes, 2),
        "unique_by_role_event": result.unique_by_role_event,
        "peak_concurrent": result.peak_concurrent,
        "field_crosstab": result.field_crosstab,
        "minute_rows": result.minute_rows,
        "headline_labels": getattr(result, "headline_labels", None) or {},
        "mix_breakdown": getattr(result, "mix_breakdown", None) or {},
        "notes": result.notes,
    }


def analyze_junction(
    junction: Dict[str, Any],
    runners_by_event: Dict[str, pd.DataFrame],
    gun_by_event: Dict[str, float],
) -> Dict[str, Any]:
    """Analyze all interactions for one authored junction."""
    nearby_by_id = {
        str(s["seg_id"]): s
        for s in (junction.get("nearby_segments") or [])
        if s.get("seg_id")
    }
    interactions = []
    for ix in junction.get("interactions") or []:
        result = analyze_interaction(ix, nearby_by_id, runners_by_event, gun_by_event)
        interactions.append(interaction_to_dict(result))
    return {
        "junction_id": junction.get("id"),
        "junction_label": junction.get("label"),
        "lat": junction.get("lat"),
        "lon": junction.get("lon"),
        "interactions": interactions,
    }


def analyze_junctions_doc(
    junctions_doc: Dict[str, Any],
    runners_by_event: Dict[str, pd.DataFrame],
    gun_by_event: Dict[str, float],
) -> Dict[str, Any]:
    """Analyze all junctions in a package junctions.json document."""
    junctions = []
    for junction in junctions_doc.get("junctions") or []:
        junctions.append(analyze_junction(junction, runners_by_event, gun_by_event))
    return {
        "ok": True,
        "method": {
            "participation": "dwell_copresence_at_node",
            "field_bands": "event_relative_pace_quintiles_Q1_lead_Q5_rear",
            "timing_model": "gun + start_offset + pace*node_km (Flow-overlap equivalent)",
            "node_dwell_sec": NODE_DWELL_SEC,
            "merge_partner_events": list(MERGE_PARTNER_EVENTS),
            "unique_count_rule": (
                "unique runners who met the other stream within "
                "node_dwell_sec; Full or Half is sufficient (union, not both required)"
            ),
        },
        "junctions": junctions,
    }


def result_to_ui_payload(day_result: Dict[str, Any]) -> Dict[str, Any]:
    """Slim UI metrics payload (omit verbose notes by default; keep minute series)."""
    junctions = []
    for j in day_result.get("junctions") or []:
        interactions = []
        for ix in j.get("interactions") or []:
            interactions.append(
                {
                    "id": ix.get("id"),
                    "type": ix.get("type"),
                    "side": ix.get("side"),
                    "label": ix.get("label"),
                    "description": ix.get("description"),
                    "events": ix.get("events"),
                    "window_start": ix.get("window_start"),
                    "window_end": ix.get("window_end"),
                    "window_minutes": ix.get("window_minutes"),
                    "unique_by_role_event": ix.get("unique_by_role_event"),
                    "peak_concurrent": ix.get("peak_concurrent"),
                    "field_crosstab": ix.get("field_crosstab"),
                    "minute_rows": ix.get("minute_rows"),
                    "headline_labels": ix.get("headline_labels") or {},
                    "mix_breakdown": ix.get("mix_breakdown") or {},
                }
            )
        junctions.append(
            {
                "junction_id": j.get("junction_id"),
                "junction_label": j.get("junction_label"),
                "lat": j.get("lat"),
                "lon": j.get("lon"),
                "interactions": interactions,
            }
        )
    return {
        "ok": bool(day_result.get("ok", True)),
        "method": day_result.get("method") or {},
        "junctions": junctions,
    }
