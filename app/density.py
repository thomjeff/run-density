from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field


# -----------------------------
# Config
# -----------------------------

ZONE_THRESHOLDS = {
    "green": 0.0,     # < 1.0
    "amber": 1.0,     # 1.0–1.5
    "red":   1.5,     # 1.5–2.0
    "dark-red": 2.0,  # ≥ 2.0
}

EPS = 1e-9


# -----------------------------
# Pydantic models (request/response)
# -----------------------------

class SegmentIn(BaseModel):
    eventA: str
    eventB: str
    from_: float = Field(..., alias="from")  # A’s km-from
    to: float                                 # A’s km-to
    direction: str
    width_m: float

class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    startTimes: Dict[str, int]  # minutes offsets; keys: "Full","Half","10K"
    segments: Optional[List[SegmentIn]] = None
    stepKm: float = 0.03
    timeWindow: int = 60


# -----------------------------
# Internal structures
# -----------------------------

@dataclass
class OverlapRow:
    seg_id: str
    segment_label: str
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: str
    width_m: float

@dataclass
class SegResult:
    seg_id: str
    segment_label: str
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: str
    width_m: float
    peak: dict
    first_overlap: Optional[dict]
    trace: Optional[List[dict]]


# -----------------------------
# Helpers
# -----------------------------

def _download_csv(url: str) -> pd.DataFrame:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch CSV: {url} ({e})")
    try:
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse CSV: {url} ({e})")

def _zone_for(density: float) -> str:
    if density < ZONE_THRESHOLDS["amber"]:
        return "green"
    if density < ZONE_THRESHOLDS["red"]:
        return "amber"
    if density < ZONE_THRESHOLDS["dark-red"]:
        return "red"
    return "dark-red"

def _km_samples(a: float, b: float, step: float) -> List[float]:
    if step <= 0:  # guard
        return [a, b]
    # Ensure inclusive of the end
    n = max(1, int(math.floor((b - a) / step)) + 1)
    xs = [a + i * step for i in range(n)]
    if xs[-1] + EPS < b:
        xs.append(b)
    xs[0] = a
    xs[-1] = b
    return xs

def _count_in_window(arrivals: pd.Series, t0: float, window: float) -> int:
    if arrivals is None or len(arrivals) == 0:
        return 0
    arr = arrivals.values
    return int(((arr >= t0) & (arr <= t0 + window)).sum())

def _arrival_times_for_event(df_event: pd.DataFrame, start_offset_min: int, km: float) -> pd.Series:
    """
    arrival_time_seconds = start_offset_seconds + pace_min_per_km * 60 * km
    Only count runners whose total distance >= km (to avoid counting 10K runners beyond 10 km, etc.)
    """
    if df_event.empty:
        return pd.Series(dtype=float)
    eligible = df_event[df_event["distance"] + EPS >= km]
    if eligible.empty:
        return pd.Series(dtype=float)
    return (start_offset_min * 60.0) + eligible["pace"] * 60.0 * km

def _weighted_speed(df_event: pd.DataFrame) -> float:
    """
    Return a conservative longitudinal speed estimate in m/s for a cohort,
    using the *fastest* typical runner (lower pace) among those present.
    pace (min/km) -> speed = 1000 / (pace*60) m/s
    """
    if df_event.empty:
        return 0.0
    p_min = float(eligible_min := df_event["pace"].min())
    if p_min <= 0:
        return 0.0
    return 1000.0 / (p_min * 60.0)

def _build_overlap_rows_from_csv(df: pd.DataFrame) -> List[OverlapRow]:
    # Required headers (per your final overlaps.csv)
    needed = [
        "seg_id","segment_label","eventA","eventB",
        "from_km_A","to_km_A","from_km_B","to_km_B",
        "direction","width_m"
    ]
    for c in needed:
        if c not in df.columns:
            raise HTTPException(status_code=422, detail=f"overlapsCsv missing column: {c}")

    rows: List[OverlapRow] = []
    for _, r in df.iterrows():
        rows.append(OverlapRow(
            seg_id=str(r["seg_id"]),
            segment_label=str(r["segment_label"]),
            eventA=str(r["eventA"]),
            eventB=str(r["eventB"]),
            from_km_A=float(r["from_km_A"]),
            to_km_A=float(r["to_km_A"]),
            from_km_B=float(r["from_km_B"]),
            to_km_B=float(r["to_km_B"]),
            direction=str(r["direction"]).strip().lower(),
            width_m=float(r["width_m"]),
        ))
    return rows

def _build_overlap_rows_from_segments(segments: List[SegmentIn]) -> List[OverlapRow]:
    rows: List[OverlapRow] = []
    for i, s in enumerate(segments, start=1):
        rows.append(OverlapRow(
            seg_id=f"S{i}",
            segment_label=f"Ad-hoc {i}",
            eventA=s.eventA, eventB=s.eventB,
            from_km_A=float(s.from_), to_km_A=float(s.to),
            from_km_B=float(s.from_), to_km_B=float(s.to),
            direction=s.direction.strip().lower(),
            width_m=float(s.width_m),
        ))
    return rows

def _first_overlap_clock(tA_min: Optional[float], tB_min: Optional[float]) -> Optional[str]:
    if tA_min is None or tB_min is None:
        return None
    secs = min(tA_min, tB_min)
    hh = int(secs // 3600); mm = int((secs % 3600) // 60); ss = int(secs % 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}"

def _format_first_overlap(km: Optional[float], clock: Optional[str]) -> Optional[dict]:
    if km is None or clock is None:
        return None
    return {"clock": clock, "km": km}


# -----------------------------
# Core density computation
# -----------------------------

def _segment_density(
    seg: OverlapRow,
    df_pace: pd.DataFrame,
    startTimes: Dict[str, int],
    stepKm: float,
    timeWindow: int,
    debug: bool
) -> SegResult:
    """
    For each sample along the segment, compute:
      - arrivals of A and B in [t0, t0+timeWindow], where t0 is earliest presence at that sample
      - combined count, areal density (uni uses width, bi uses width/2)
      - track the peak over samples; compute first_overlap as earliest sample both present
    """

    # filter by event
    dfA = df_pace[df_pace["event"] == seg.eventA]
    dfB = df_pace[df_pace["event"] == seg.eventB]

    stA = int(startTimes.get(seg.eventA, 0))
    stB = int(startTimes.get(seg.eventB, 0))

    # sample grids
    kmAs = _km_samples(seg.from_km_A, seg.to_km_A, stepKm)
    kmBs = _km_samples(seg.from_km_B, seg.to_km_B, stepKm)
    # ensure same length by pairing by index proportionally
    # (assume same physical stretch; pair samples by relative index)
    n = max(len(kmAs), len(kmBs))
    if len(kmAs) != n:
        kmAs = _km_samples(seg.from_km_A, seg.to_km_A, (seg.to_km_A - seg.from_km_A) / max(1, n - 1))
    if len(kmBs) != n:
        kmBs = _km_samples(seg.from_km_B, seg.to_km_B, (seg.to_km_B - seg.from_km_B) / max(1, n - 1))

    # precompute effective width and longitudinal speed estimate
    width_eff = seg.width_m if seg.direction == "uni" else max(0.1, seg.width_m / 2.0)
    vA = _weighted_speed(dfA)  # m/s
    vB = _weighted_speed(dfB)
    v_eff = max(vA, vB)
    # if v_eff == 0 we’ll guard when used

    peak = {
        "km": kmAs[0],
        "A": 0, "B": 0, "combined": 0,
        "areal_density": 0.0,
        "zone": "green",
    }
    first_overlap_km: Optional[float] = None
    first_overlap_clock_str: Optional[str] = None

    trace_rows: List[dict] = []

    for kA, kB in zip(kmAs, kmBs):
        tA_arr = _arrival_times_for_event(dfA, stA, kA)
        tB_arr = _arrival_times_for_event(dfB, stB, kB)
        tA_min = float(tA_arr.min()) if len(tA_arr) else None
        tB_min = float(tB_arr.min()) if len(tB_arr) else None

        if tA_min is None and tB_min is None:
            if debug:
                trace_rows.append({
                    "kmA": kA, "kmB": kB,
                    "A": 0, "B": 0, "combined": 0,
                    "areal_density": 0.0,
                    "note": "no presence"
                })
            continue

        t0 = min([t for t in [tA_min, tB_min] if t is not None])

        A_cnt = _count_in_window(tA_arr, t0, timeWindow) if tA_min is not None else 0
        B_cnt = _count_in_window(tB_arr, t0, timeWindow) if tB_min is not None else 0
        combined = A_cnt + B_cnt

        if v_eff > 0:
            span_m = v_eff * timeWindow
            area_m2 = max(0.1, width_eff * span_m)
            areal = float(combined) / area_m2
        else:
            areal = 0.0

        zone = _zone_for(areal)

        if debug:
            trace_rows.append({
                "kmA": kA, "kmB": kB,
                "t0": t0,
                "A": A_cnt, "B": B_cnt, "combined": combined,
                "width_eff": width_eff, "v_eff": v_eff,
                "areal_density": areal, "zone": zone
            })

        # set first overlap (first sample where both have presence)
        if first_overlap_km is None and (tA_min is not None) and (tB_min is not None):
            first_overlap_km = (kA + kB) / 2.0
            first_overlap_clock_str = _first_overlap_clock(tA_min, tB_min)

        # track peak by areal density; if tie, prefer higher combined
        better = (areal > peak["areal_density"] + EPS) or (
            abs(areal - peak["areal_density"]) <= EPS and combined > peak["combined"]
        )
        if better:
            peak = {
                "km": float((kA + kB) / 2.0),
                "A": int(A_cnt),
                "B": int(B_cnt),
                "combined": int(combined),
                "areal_density": float(areal),
                "zone": zone,
            }

    return SegResult(
        seg_id=seg.seg_id,
        segment_label=seg.segment_label,
        eventA=seg.eventA, eventB=seg.eventB,
        from_km_A=seg.from_km_A, to_km_A=seg.to_km_A,
        from_km_B=seg.from_km_B, to_km_B=seg.to_km_B,
        direction=seg.direction, width_m=seg.width_m,
        peak=peak,
        first_overlap=_format_first_overlap(first_overlap_km, first_overlap_clock_str),
        trace=(trace_rows if debug else None)
    )


# -----------------------------
# Public entrypoint
# -----------------------------

def run_density(payload: DensityPayload, seg_id: Optional[str] = None, debug: bool = False) -> dict:
    # Load pace data
    df = _download_csv(payload.paceCsv)
    # enforce required cols: event, runner_id, pace, distance
    need = ["event", "runner_id", "pace", "distance"]
    for c in need:
        if c not in df.columns:
            raise HTTPException(status_code=422, detail=f"paceCsv missing column: {c}")
    # Types
    df["event"] = df["event"].astype(str)
    df["runner_id"] = df["runner_id"]
    df["pace"] = pd.to_numeric(df["pace"], errors="coerce")
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    df = df.dropna(subset=["pace", "distance"])

    # Build overlap rows
    overlaps: List[OverlapRow]
    if payload.overlapsCsv:
        df_over = _download_csv(payload.overlapsCsv)
        overlaps = _build_overlap_rows_from_csv(df_over)
    elif payload.segments:
        overlaps = _build_overlap_rows_from_segments(payload.segments)
    else:
        raise HTTPException(status_code=422, detail="Provide either overlapsCsv or segments[]")

    # Optional filter by seg_id
    if seg_id:
        overlaps = [o for o in overlaps if o.seg_id == seg_id]
        if not overlaps:
            raise HTTPException(status_code=422, detail=f"seg_id not found: {seg_id}")

    results: List[SegResult] = []
    for o in overlaps:
        results.append(
            _segment_density(
                o, df, payload.startTimes, payload.stepKm, payload.timeWindow, debug
            )
        )

    # Shape the response
    out = {
        "engine": "density",
        "segments": [
            {
                "seg_id": r.seg_id,
                "segment_label": r.segment_label,
                "eventA": r.eventA,
                "eventB": r.eventB,
                "from_km_A": r.from_km_A,
                "to_km_A": r.to_km_A,
                "from_km_B": r.from_km_B,
                "to_km_B": r.to_km_B,
                "direction": r.direction,
                "width_m": r.width_m,
                "peak": r.peak,
                "first_overlap": r.first_overlap,
                "trace": r.trace if debug else None,
            }
            for r in results
        ],
    }
    return out