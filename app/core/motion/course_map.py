"""Compiled-course mapping: elapsed_km → seg_id / seg_km (#850)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import pandas as pd

from app.core.v2.res import calculate_event_total_distance


@dataclass(frozen=True)
class EventSpan:
    """One segment participation for an event on the compiled course."""

    from_km: float
    to_km: float
    seg_id: str

    @property
    def length_km(self) -> float:
        return max(0.0, float(self.to_km) - float(self.from_km))


def compiled_course_length_km(segments_df: pd.DataFrame, event: str) -> float:
    """Authoritative finish distance for motion (segments.csv spans)."""
    return float(calculate_event_total_distance(segments_df, event))


def event_spans(segments_df: pd.DataFrame, event: str) -> List[EventSpan]:
    """Ordered (from_km ascending) spans for ``event`` on the compiled course."""
    event_l = str(event or "").strip().lower()
    if event_l not in segments_df.columns:
        return []
    flag = segments_df[event_l].astype(str).str.lower().isin(["y", "yes", "true", "1"])
    from_col = f"{event_l}_from_km"
    to_col = f"{event_l}_to_km"
    if from_col not in segments_df.columns or to_col not in segments_df.columns:
        return []
    rows: List[EventSpan] = []
    for _, row in segments_df.loc[flag].iterrows():
        seg_id = str(row.get("seg_id") or "").strip()
        if not seg_id:
            continue
        try:
            from_km = float(row[from_col])
            to_km = float(row[to_col])
        except (TypeError, ValueError):
            continue
        if to_km < from_km:
            continue
        rows.append(EventSpan(from_km=from_km, to_km=to_km, seg_id=seg_id))
    rows.sort(key=lambda s: (s.from_km, s.to_km, s.seg_id))
    return rows


def locate_on_course(
    elapsed_km: float,
    spans: Sequence[EventSpan],
    finish_km: float,
) -> Tuple[str, float]:
    """
    Map elapsed race km to (seg_id, seg_km).

    Boundary rule (#850): a sample exactly at a segment join belongs to the
    **downstream / starting** segment; the final course endpoint belongs to the
    **final** segment.
    """
    if not spans:
        raise ValueError("No compiled spans for event")
    finish = max(0.0, float(finish_km))
    dist = min(max(float(elapsed_km), 0.0), finish)
    eps = 1e-9

    if dist >= finish - eps:
        last = spans[-1]
        return last.seg_id, last.length_km

    for span in spans:
        # Half-open [from, to): exact ``to`` falls through to the next span.
        if dist < span.to_km - eps:
            return span.seg_id, max(0.0, dist - span.from_km)

    last = spans[-1]
    return last.seg_id, last.length_km
