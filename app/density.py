# app/density.py
from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional, Tuple

import requests
import pandas as pd
from fastapi import HTTPException
from pydantic import BaseModel, Field, HttpUrl


# ---------- Pydantic models ----------

class SegmentIn(BaseModel):
    # We allow "from" and "to" in JSON via aliases to Python identifiers
    seg_id: Optional[str] = None
    segment_label: Optional[str] = None
    eventA: str
    eventB: str
    direction: str = "uni"                 # "uni" or "bi" (used only as a label)
    width_m: float = Field(3.0, alias="width")  # accept "width" in payload; store as width_m
    from_km: float = Field(..., alias="from")
    to_km: float = Field(..., alias="to")

    class Config:
        populate_by_name = True  # allow using "from"/"to" from JSON


class DensityPayload(BaseModel):
    paceCsv: HttpUrl
    overlapsCsv: Optional[HttpUrl] = None
    startTimes: Dict[str, int]  # e.g. {"Full": 420, "10K": 440}
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds; interpreted as a +/- window when matching flows
    segments: Optional[List[SegmentIn]] = None  # if None, we generate from overlapsCsv


# ---------- Helpers ----------

def _http_get_text(url: str, timeout: float = 10.0) -> str:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        # GitHub raw may set text/plain; we want decoded text as-is
        return r.text
    except requests.RequestException as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {url} ({e})")


def _load_pace_csv(url: str) -> pd.DataFrame:
    """
    Expects columns: event, runner_id, pace, distance
    - pace: minutes per km (float)
    """
    txt = _http_get_text(url)
    try:
        df = pd.read_csv(io.StringIO(txt))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse paceCsv: {e}")

    required = {"event", "runner_id", "pace", "distance"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"paceCsv missing columns: {sorted(missing)}")

    # Normalize types
    try:
        df["event"] = df["event"].astype(str)
        df["runner_id"] = df["runner_id"].astype(str)
        df["pace"] = pd.to_numeric(df["pace"], errors="raise")  # minutes/km
        df["distance"] = pd.to_numeric(df["distance"], errors="raise")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"paceCsv type normalization failed: {e}")

    return df


def _normalize_overlaps_csv(url: str) -> List[SegmentIn]:
    """
    Accept headers with either:
      seg_id OR segment_id
      segment_label, eventA, eventB,
      from_km_A, to_km_A, from_km_B, to_km_B,
      direction, width_m

    We synthesize a single [from_km, to_km] for the shared path by taking the
    intersection of [from_km_A, to_km_A] and [from_km_B, to_km_B].
    Rows with empty intersection are skipped.
    """
    txt = _http_get_text(url)
    try:
        rows = list(csv.DictReader(io.StringIO(txt)))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse overlapsCsv: {e}")

    if not rows:
        raise HTTPException(status_code=422, detail="overlapsCsv has no data rows.")

    out: List[SegmentIn] = []
    auto_idx = 1

    for raw in rows:
        # IDs/labels
        seg_id = (raw.get("seg_id") or raw.get("segment_id") or "").strip()
        label = (raw.get("segment_label") or seg_id or "").strip()

        # Events
        a = (raw.get("eventA") or "").strip()
        b = (raw.get("eventB") or "").strip()
        if not a or not b:
            # Skip invalid rows quietly; they won't help the run
            continue

        # Bounds
        def _num(s: Optional[str]) -> Optional[float]:
            if s is None:
                return None
            s = s.strip()
            if s == "":
                return None
            try:
                return float(s)
            except ValueError:
                return None

        a_from = _num(raw.get("from_km_A"))
        a_to = _num(raw.get("to_km_A"))
        b_from = _num(raw.get("from_km_B"))
        b_to = _num(raw.get("to_km_B"))

        if None in (a_from, a_to, b_from, b_to):
            # Invalid bounds — skip
            continue

        # Intersection of A and B spans
        from_km = max(a_from, b_from)
        to_km = min(a_to, b_to)
        if from_km >= to_km:
            # No actual overlap
            continue

        direction = (raw.get("direction") or "uni").strip()
        width_m = _num(raw.get("width_m")) or 3.0

        # Synthesize id/label if missing
        if not seg_id:
            seg_id = f"S{auto_idx}"
            auto_idx += 1
        if not label:
            label = seg_id

        out.append(
            SegmentIn(
                seg_id=seg_id,
                segment_label=label,
                eventA=a,
                eventB=b,
                direction=direction,
                width_m=width_m,
                **{"from": from_km, "to": to_km},  # via alias
            )
        )

    if not out:
        raise HTTPException(
            status_code=422,
            detail="No valid overlaps produced from overlapsCsv (check headers/values).",
        )
    return out


def _arrival_times_seconds(df_event: pd.DataFrame, start_sec: int, d_km: float) -> pd.Series:
    """
    Arrival time at distance d_km = start_sec + pace(min/km)*60 * d_km
    """
    return start_sec + (df_event["pace"].values * 60.0 * d_km)


def _peak_for_segment(
    df_pace: pd.DataFrame,
    start_times: Dict[str, int],
    seg: SegmentIn,
    step_km: float,
    time_window: int,
) -> Tuple[float, int, int, int]:
    """
    Sweep along the segment and compute the max combined occupancy.
    At each d_km we count runners in A and B whose arrival times are within a +/- (time_window/2) seconds band
    centered at the median of the two events' arrival times at that d_km. This captures temporal overlap.
    """
    a = seg.eventA
    b = seg.eventB
    if a not in start_times or b not in start_times:
        # If an event has no start time, treat as zero contribution
        return (seg.from_km, 0, 0, 0)

    dfA = df_pace[df_pace["event"] == a]
    dfB = df_pace[df_pace["event"] == b]

    if dfA.empty and dfB.empty:
        return (seg.from_km, 0, 0, 0)

    half = max(1, int(time_window // 2))
    peak_combined = -1
    peak_km = seg.from_km
    peak_A = 0
    peak_B = 0

    d = seg.from_km
    end = seg.to_km + 1e-9
    while d <= end:
        tA = _arrival_times_seconds(dfA, start_times[a], d) if not dfA.empty else None
        tB = _arrival_times_seconds(dfB, start_times[b], d) if not dfB.empty else None

        if tA is None and tB is None:
            d += step_km
            continue

        # Choose a reference time around which to consider co-occupancy.
        # If both present, use the mid of medians; else just that event's median.
        if tA is not None and tB is not None and len(tA) > 0 and len(tB) > 0:
            ref = (float(pd.Series(tA).median()) + float(pd.Series(tB).median())) / 2.0
        elif tA is not None and len(tA) > 0:
            ref = float(pd.Series(tA).median())
        elif tB is not None and len(tB) > 0:
            ref = float(pd.Series(tB).median())
        else:
            d += step_km
            continue

        lo = ref - half
        hi = ref + half

        cntA = int(((tA >= lo) & (tA <= hi)).sum()) if tA is not None else 0
        cntB = int(((tB >= lo) & (tB <= hi)).sum()) if tB is not None else 0
        combined = cntA + cntB

        if combined > peak_combined:
            peak_combined = combined
            peak_km = round(d, 3)
            peak_A = cntA
            peak_B = cntB

        d += step_km

    return (peak_km, peak_A, peak_B, max(0, peak_combined))


# ---------- Public entry point used by app.main ----------

def run_density(payload: DensityPayload) -> dict:
    """
    Compute density peaks for each requested segment (inline or from overlapsCsv).
    Returns:
    {
      "engine": "density",
      "segments": [
        {
          "seg_id": "...",
          "segment_label": "...",
          "pair": "10K vs Half",
          "direction": "uni",
          "width_m": 3.0,
          "from_km": 0.0,
          "to_km": 2.7,
          "peak": { "km": 1.8, "A": 260, "B": 140, "combined": 400 }
        },
        ...
      ]
    }
    """
    # Decide source of segments
    if payload.segments is not None and len(payload.segments) > 0:
        segments_in = payload.segments
    elif payload.overlapsCsv:
        segments_in = _normalize_overlaps_csv(str(payload.overlapsCsv))
    else:
        raise HTTPException(
            status_code=422,
            detail="Either provide non-empty 'segments' or a valid 'overlapsCsv'.",
        )

    # Load pace data
    df_pace = _load_pace_csv(str(payload.paceCsv))

    results = []
    for idx, seg in enumerate(segments_in, start=1):
        seg_id = seg.seg_id or f"S{idx}"
        label = seg.segment_label or seg_id

        pk_km, pkA, pkB, pkAll = _peak_for_segment(
            df_pace=df_pace,
            start_times=payload.startTimes,
            seg=seg,
            step_km=payload.stepKm,
            time_window=payload.timeWindow,
        )

        results.append(
            {
                "seg_id": seg_id,
                "segment_label": label,
                "pair": f"{seg.eventA} vs {seg.eventB}",
                "direction": seg.direction,
                "width_m": seg.width_m,
                "from_km": seg.from_km,
                "to_km": seg.to_km,
                "peak": {
                    "km": pk_km,
                    "A": pkA,
                    "B": pkB,
                    "combined": pkAll,
                },
            }
        )

    return {
        "engine": "density",
        "segments": results,
    }