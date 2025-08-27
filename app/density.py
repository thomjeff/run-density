# app/density.py
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field

# -------------------------------------------------
# Pydantic request models (same external contract)
# -------------------------------------------------

class StartTimes(BaseModel):
    # Minutes after race "clock 0"
    Full: Optional[int] = None
    Half: Optional[int] = None
    TenK: Optional[int] = Field(default=None, alias="10K")

    model_config = {"populate_by_name": True}

    def get(self, event: str) -> int:
        if event == "Full" and self.Full is not None:
            return self.Full
        if event == "Half" and self.Half is not None:
            return self.Half
        if event == "10K" and self.TenK is not None:
            return self.TenK
        return 0  # safe default; better to supply in payload


class InlineSegment(BaseModel):
    eventA: str
    eventB: str
    from_: float = Field(alias="from")
    to: float
    direction: str  # "uni" or "bi"
    width_m: float


class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    segments: Optional[List[InlineSegment]] = None
    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds


# -------------------------------------------------
# Internal structures
# -------------------------------------------------

@dataclass
class SegmentSpec:
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


# -------------------------------------------------
# Helpers — CSV loaders
# -------------------------------------------------

def _fetch_csv(url: str) -> pd.DataFrame:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch CSV: {e}")
    try:
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV parse error: {e}")


def _load_pace_df(pace_url: str) -> pd.DataFrame:
    df = _fetch_csv(pace_url)
    # required base columns
    for c in ["event", "runner_id", "pace", "distance"]:
        if c not in df.columns:
            raise HTTPException(status_code=400, detail=f"paceCsv missing required column: {c}")
    # optional start_offset (seconds)
    if "start_offset" not in df.columns:
        df["start_offset"] = 0
    # Normalize event names
    df["event"] = df["event"].astype(str)
    return df


def _load_overlaps(overlaps_url: Optional[str], inline: Optional[List[InlineSegment]]) -> List[SegmentSpec]:
    if overlaps_url:
        df = _fetch_csv(overlaps_url)
        required = [
            "seg_id","segment_label","eventA","eventB",
            "from_km_A","to_km_A","from_km_B","to_km_B",
            "direction","width_m"
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"overlapsCsv missing columns: {missing}")

        rows: List[SegmentSpec] = []
        for _, r in df.iterrows():
            rows.append(
                SegmentSpec(
                    seg_id=str(r["seg_id"]).strip(),
                    segment_label=str(r["segment_label"]).strip(),
                    eventA=str(r["eventA"]).strip(),
                    eventB=str(r["eventB"]).strip(),
                    from_km_A=float(r["from_km_A"]),
                    to_km_A=float(r["to_km_A"]),
                    from_km_B=float(r["from_km_B"]),
                    to_km_B=float(r["to_km_B"]),
                    direction=str(r["direction"]).strip(),
                    width_m=float(r["width_m"]),
                )
            )
        return rows

    # Fallback: inline ad-hoc segment(s)
    segs: List[SegmentSpec] = []
    if inline:
        for i, s in enumerate(inline, start=1):
            segs.append(
                SegmentSpec(
                    seg_id=f"inline-{i}",
                    segment_label=f"Inline {i}",
                    eventA=s.eventA,
                    eventB=s.eventB,
                    from_km_A=float(s.from_),
                    to_km_A=float(s.to),
                    from_km_B=float(s.from_),  # assume same corridor
                    to_km_B=float(s.to),
                    direction=s.direction,
                    width_m=float(s.width_m),
                )
            )
    return segs


# -------------------------------------------------
# Core density computation (kept simple & stable)
# -------------------------------------------------

_A_START_SEG_IDS = {"A1", "A2", "A3"}  # ONLY here do we honor per-runner start_offset

def _zones(areal: float) -> str:
    # Your thresholds (unchanged)
    if areal < 1.0:
        return "green"
    if areal < 1.5:
        return "amber"
    if areal < 2.0:
        return "red"
    return "dark-red"


def _clock_from_minutes(mins: float) -> str:
    # race clock 0 at 00:00:00
    total = int(round(mins * 60))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _runner_time_to_reach_km(start_min: float, pace_min_per_km: float, km: float) -> float:
    # when (minutes after race clock 0) does runner hit distance = km?
    return start_min + pace_min_per_km * km


def _segment_trace(
    seg: SegmentSpec,
    pace_df: pd.DataFrame,
    start_times: StartTimes,
    stepKm: float,
    timeWindow: int,
) -> Tuple[List[dict], dict, dict]:
    """
    Produce a simple time-sliced count along the segment corridor.
    We look at discrete km marks and count how many runners are within
    +/- timeWindow/2 seconds of the time that the *median* runner hits that km.
    """
    # Prepare per-event runners and *effective* per-runner start minute.
    # ONLY for A1/A2/A3 do we add `start_offset` (seconds) to personal start.
    def effective_start_minutes(event: str, seg_id: str) -> pd.Series:
        base_min = start_times.get(event)
        sub = pace_df[pace_df["event"] == event].copy()
        if seg_id in _A_START_SEG_IDS:
            # per-runner start = base + (start_offset seconds)/60
            sub["start_min"] = base_min + (sub["start_offset"].fillna(0).astype(float) / 60.0)
        else:
            sub["start_min"] = float(base_min)
        return sub.set_index("runner_id")["start_min"]

    # Build views per event, attach effective starts
    a_df = pace_df[pace_df["event"] == seg.eventA].copy()
    b_df = pace_df[pace_df["event"] == seg.eventB].copy()

    if a_df.empty and b_df.empty:
        return [], {"clock": None, "km": None}, {"km": None, "A": 0, "B": 0, "combined": 0, "areal_density": 0.0, "zone": "green"}

    a_starts = effective_start_minutes(seg.eventA, seg.seg_id)
    b_starts = effective_start_minutes(seg.eventB, seg.seg_id)

    # Attach per-runner start_min to frames (some runners may not have offsets; defaulted to 0)
    if not a_df.empty:
        a_df = a_df.set_index("runner_id")
        a_df["start_min"] = a_starts.reindex(a_df.index).fillna(start_times.get(seg.eventA))
        a_df = a_df.reset_index()
    if not b_df.empty:
        b_df = b_df.set_index("runner_id")
        b_df["start_min"] = b_starts.reindex(b_df.index).fillna(start_times.get(seg.eventB))
        b_df = b_df.reset_index()

    # Build km samples in each event’s coordinate
    # For reporting, we put both on "A" coordinate (first number) just to anchor,
    # but counts are independent per event track.
    kms_A = _km_span(seg.from_km_A, seg.to_km_A, stepKm)
    kms_B = _km_span(seg.from_km_B, seg.to_km_B, stepKm)

    # Given we don’t have an absolute wall time to compare, we estimate crowd
    # at each km mark by counting runners whose arrival time at that km
    # falls within a small “arrival window” around the segment’s median arrival time.
    # Window = timeWindow seconds (symmetric).
    half_window_min = (timeWindow / 2.0) / 60.0
    def _arrivals(df: pd.DataFrame, km: float) -> Optional[pd.Series]:
        if df.empty:
            return None
        return df["start_min"].astype(float) + df["pace"].astype(float) * km
    
    trace: List[dict] = []

    # Helper to count arrivals near the *median* arrival among that event’s runners
    def _count_near_km(df: pd.DataFrame, km: float) -> int:
        if df.empty:
            return 0
        arrivals = df["start_min"].astype(float) + df["pace"].astype(float) * km
        med = arrivals.median()
        return int(((arrivals >= med - half_window_min) & (arrivals <= med + half_window_min)).sum())

    # We’ll sweep along the *A* coordinate and pair with a close km in B track by proportion.
    steps = len(kms_A)
    for i, kA in enumerate(kms_A):
        kB = kms_B[min(i, len(kms_B) - 1)] if kms_B else None

        a_arr = _arrivals(a_df, kA) if not a_df.empty else None
        b_arr = _arrivals(b_df, kB) if (kB is not None and not b_df.empty) else None

        # choose one common time center for this km
        med_a = a_arr.median() if a_arr is not None and len(a_arr) else None
        med_b = b_arr.median() if b_arr is not None and len(b_arr) else None

        if med_a is None and med_b is None:
            cntA = cntB = 0
        else:
            # common center (earliest of the two medians)
            if med_a is None:      t0 = med_b
            elif med_b is None:    t0 = med_a
            else:                  t0 = min(med_a, med_b)

            lo, hi = t0 - half_window_min, t0 + half_window_min
            cntA = int(((a_arr >= lo) & (a_arr <= hi)).sum()) if a_arr is not None else 0
            cntB = int(((b_arr >= lo) & (b_arr <= hi)).sum()) if b_arr is not None else 0

        combined = cntA + cntB
        width = seg.width_m
        areal = (combined / width) if width > 0 else 0.0

        trace.append({
            "km": round(float(kA), 3),
            "A": int(cntA),
            "B": int(cntB),
            "combined": int(combined),
        })

    # Peak selection
    if trace:
        peak_idx = max(range(len(trace)), key=lambda idx: trace[idx]["combined"])
        peak = trace[peak_idx]
        peak_out = {
            "km": float(peak["km"]),
            "A": int(peak["A"]),
            "B": int(peak["B"]),
            "combined": int(peak["combined"]),
            "areal_density": float(peak["combined"]) / max(1.0, seg.width_m),
            "zone": _zones(float(peak["combined"]) / max(1.0, seg.width_m)),
        }
    else:
        peak_out = {"km": None, "A": 0, "B": 0, "combined": 0, "areal_density": 0.0, "zone": "green"}

    # First overlap heuristic = first non-zero combined
    first = next((t for t in trace if t["combined"] > 0), None)
    if first:
        # Approximate the *clock* as the earlier of the two median arrivals at that km
        clock_min = None
        if not a_df.empty:
            a_arrivals = a_df["start_min"].astype(float) + a_df["pace"].astype(float) * first["km"]
            clock_min = a_arrivals.median()
        if not b_df.empty:
            b_arrivals = b_df["start_min"].astype(float) + b_df["pace"].astype(float) * (first["km"])
            clock_min = min(clock_min, b_arrivals.median()) if clock_min is not None else b_arrivals.median()

        first_overlap = {"clock": _clock_from_minutes(clock_min) if clock_min is not None else None,
                         "km": float(first["km"])}
    else:
        first_overlap = {"clock": None, "km": None}

    return trace, first_overlap, peak_out


def _km_span(a: float, b: float, step: float) -> List[float]:
    if step <= 0:
        step = 0.03
    lo, hi = (a, b) if a <= b else (b, a)
    out = []
    x = lo
    # include hi
    while x <= hi + 1e-9:
        out.append(round(x, 3))
        x += step
    if out and out[-1] != round(hi, 3):
        out.append(round(hi, 3))
    # preserve original direction for reporting
    return out if a <= b else list(reversed(out))


# -------------------------------------------------
# Public entry point
# -------------------------------------------------

def run_density(payload: DensityPayload, seg_id_filter: Optional[str] = None, debug: bool = False):
    # 1) Load inputs
    pace_df = _load_pace_df(payload.paceCsv)
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)

    # 2) Optional filter by seg-id (query param handled in app.main)
    if seg_id_filter:
        overlaps = [o for o in overlaps if o.seg_id == seg_id_filter]

    results = []
    for seg in overlaps:
        trace, first_overlap, peak = _segment_trace(
            seg=seg,
            pace_df=pace_df,
            start_times=payload.startTimes,
            stepKm=payload.stepKm,
            timeWindow=payload.timeWindow,
        )

        item = {
            "seg_id": seg.seg_id,
            "segment_label": seg.segment_label,
            "direction": seg.direction,
            "width_m": seg.width_m,
            "first_overlap": first_overlap,
            "peak": peak,
        }
        if debug:
            item["trace"] = trace
        results.append(item)

    return {"engine": "density", "segments": results}