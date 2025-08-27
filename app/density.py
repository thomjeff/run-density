# app/density.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field


# -----------------------------
# Pydantic models (request/response)
# -----------------------------

class StartTimes(BaseModel):
    """Start offsets in minutes after race clock 0."""
    Full: Optional[int] = None
    Half: Optional[int] = None
    tenK: Optional[int] = Field(default=None, alias="10K")  # Accept "10K" in JSON

    def get(self, event: str) -> int:
        if event == "Full" and self.Full is not None:
            return self.Full
        if event == "Half" and self.Half is not None:
            return self.Half
        if event == "10K" and self.tenK is not None:
            return self.tenK
        # If missing, default to 0 (better: provide them in requests)
        return 0


class AdHocSegment(BaseModel):
    """For manual single/pairwise requests (legacy handy path)."""
    eventA: str
    eventB: str
    from_: float = Field(..., alias="from")
    to: float
    direction: str = Field(..., pattern="^(uni|bi)$")
    width_m: float


class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None  # preferred for full run
    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: float = 60.0
    # Legacy/manual fallback: if provided, we’ll compute only these segments
    segments: Optional[List[AdHocSegment]] = None


# -----------------------------
# Internal data models
# -----------------------------

@dataclass
class OverlapSeg:
    seg_id: str
    segment_label: str
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: str  # "uni" | "bi"
    width_m: float


# -----------------------------
# Utilities
# -----------------------------

def _http_get_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch: {url} ({e})")


def _sec_to_clock(sec: float) -> str:
    sec = max(0.0, float(sec))
    hh = int(sec // 3600)
    mm = int((sec % 3600) // 60)
    ss = int(round(sec % 60))
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _zone_from_density(d: float) -> str:
    # thresholds you approved
    if d >= 2.0:
        return "dark-red"
    if d >= 1.5:
        return "red"
    if d >= 1.0:
        return "amber"
    return "green"


def _load_pace_csv(url: str) -> pd.DataFrame:
    """
    Expected columns:
      event, runner_id, pace, distance
    - pace is minutes per km (float)
    - distance is total race distance in km
    """
    text = _http_get_text(url)
    df = pd.read_csv(io.StringIO(text))
    needed = {"event", "runner_id", "pace", "distance"}
    missing = needed - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"paceCsv missing columns: {sorted(missing)}")
    return df


def _load_overlaps_csv(url: str) -> List[OverlapSeg]:
    """
    Expected columns (your current schema):
      seg_id,segment_label,eventA,eventB,
      from_km_A,to_km_A,from_km_B,to_km_B,
      direction,width_m,notes
    """
    text = _http_get_text(url)
    df = pd.read_csv(io.StringIO(text))
    required = [
        "seg_id", "segment_label", "eventA", "eventB",
        "from_km_A", "to_km_A", "from_km_B", "to_km_B",
        "direction", "width_m"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"overlapsCsv missing columns: {missing}")

    rows: List[OverlapSeg] = []
    for _, r in df.iterrows():
        rows.append(
            OverlapSeg(
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
            )
        )
    return rows


# -----------------------------
# Core per-sample math
# -----------------------------

def _arrival_secs_series(rows: pd.DataFrame, event: str, km_event: float, start_times_min: Dict[str, int]) -> pd.Series:
    if rows.empty:
        return pd.Series([], dtype=float)
    # arrival time to km_event from the event start gun, in seconds
    # t = start_offset*60 + km_event * pace_min_per_km * 60
    t = start_times_min.get(event, 0) * 60.0 + km_event * (rows["pace"] * 60.0)
    return t


def _window_load(rows: pd.DataFrame, time_window: float) -> float:
    """Flow-ish proxy: weight by 1/pace; scale by window seconds."""
    if rows.empty:
        return 0.0
    w = 1.0 / rows["pace"]  # 1/(min/km)
    W = w.sum()
    if W <= 0:
        return 0.0
    return time_window * float(W)


def _weighted_speed(rows: pd.DataFrame) -> float:
    """Weighted average speed (m/s) using 1/pace weights."""
    if rows.empty:
        return 0.0
    v = 1000.0 / (rows["pace"] * 60.0)  # m/s
    w = 1.0 / rows["pace"]
    vw = (v * w).sum() / w.sum()
    return float(vw)


def _sample_metrics_pair(
    p: float,  # 0..1 position along the physical segment
    seg: OverlapSeg,
    pace_df: pd.DataFrame,         # event, runner_id, pace(min/km), distance(km)
    start_times_min: Dict[str, int],
    time_window: float,
) -> dict:
    """
    Compute metrics at proportion p. We map p -> kmA, kmB per their own ranges.
    """
    kmA = seg.from_km_A + p * (seg.to_km_A - seg.from_km_A)
    kmB = seg.from_km_B + p * (seg.to_km_B - seg.from_km_B)

    # Runners who still have distance >= kmX for each event
    A_rows = pace_df[(pace_df["event"] == seg.eventA) & (pace_df["distance"] >= kmA)]
    B_rows = pace_df[(pace_df["event"] == seg.eventB) & (pace_df["distance"] >= kmB)]

    tA = _arrival_secs_series(A_rows, seg.eventA, kmA, start_times_min)
    tB = _arrival_secs_series(B_rows, seg.eventB, kmB, start_times_min)
    tA_min = float(tA.min()) if len(tA) else None
    tB_min = float(tB.min()) if len(tB) else None

    loadA = _window_load(A_rows, time_window)
    loadB = _window_load(B_rows, time_window)
    combined = int(round(loadA + loadB))

    # Effective width (bi halves the usable width)
    width_eff = seg.width_m if seg.direction == "uni" else max(0.1, seg.width_m / 2.0)

    # Longitudinal span in same window uses the faster cohort (conservative crowding)
    vA = _weighted_speed(A_rows)
    vB = _weighted_speed(B_rows)
    v_eff = max(vA, vB)
    if v_eff <= 0.0:
        return {
            "p": p,
            "kmA": kmA, "kmB": kmB,
            "A": 0, "B": 0, "combined": 0,
            "areal_density": 0.0,
            "tA_min": tA_min, "tB_min": tB_min
        }

    span_m = v_eff * time_window
    area_m2 = max(0.1, width_eff * span_m)
    areal_density = float(combined) / area_m2

    return {
        "p": p,
        "kmA": kmA, "kmB": kmB,
        "A": int(round(loadA)),
        "B": int(round(loadB)),
        "combined": combined,
        "areal_density": areal_density,
        "tA_min": tA_min, "tB_min": tB_min
    }


# -----------------------------
# Public entry point
# -----------------------------

def run_density(payload: DensityPayload, seg_id: Optional[str] = None, debug: bool = False) -> dict:
    """
    Computes density segments.

    If payload.overlapsCsv is provided:
      - Loads all overlap rows and computes all segments (optionally filter ?seg_id=).
    Else if payload.segments is provided:
      - Computes only the ad-hoc segment(s) from the body.
    """
    # 1) load inputs
    pace_df = _load_pace_csv(payload.paceCsv)
    start_times_min = {
        "Full": payload.startTimes.Full or 0,
        "Half": payload.startTimes.Half or 0,
        "10K":  payload.startTimes.tenK or 0,
    }
    stepKm = float(payload.stepKm)
    timeWindow = float(payload.timeWindow)

    # Build the overlap list
    overlaps: List[OverlapSeg] = []
    if payload.overlapsCsv:
        all_rows = _load_overlaps_csv(payload.overlapsCsv)
        if seg_id:
            overlaps = [r for r in all_rows if r.seg_id == seg_id]
            if not overlaps:
                raise HTTPException(status_code=404, detail=f"seg_id '{seg_id}' not found in overlapsCsv")
        else:
            overlaps = all_rows
    elif payload.segments:
        # Translate ad-hoc segments into OverlapSeg stubs
        for i, s in enumerate(payload.segments, start=1):
            overlaps.append(
                OverlapSeg(
                    seg_id=f"adhoc-{i}",
                    segment_label=f"AdHoc {i}",
                    eventA=s.eventA, eventB=s.eventB,
                    from_km_A=s.from_, to_km_A=s.to,
                    from_km_B=s.from_, to_km_B=s.to,
                    direction=s.direction, width_m=s.width_m
                )
            )
    else:
        raise HTTPException(status_code=422, detail="Provide either overlapsCsv or segments in request body")

    # 2) compute for each overlap
    out_segments: List[dict] = []

    for seg in overlaps:
        # Create a proportional grid along the segment
        # Use arc-length on A as baseline for resolution
        spanA = abs(seg.to_km_A - seg.from_km_A)
        if spanA <= 0:
            # zero-length guard
            samples = []
        else:
            nsteps = max(1, int(round(spanA / stepKm)))
            # nsteps points across [0,1]
            samples = []
            for j in range(nsteps + 1):
                p = j / nsteps
                m = _sample_metrics_pair(
                    p=p,
                    seg=seg,
                    pace_df=pace_df,
                    start_times_min=start_times_min,
                    time_window=timeWindow,
                )
                samples.append(m)

        # first_overlap: earliest time where both cohorts exist at the same proportional place
        first_k = None
        first_t = None
        for m in samples:
            if m["tA_min"] is not None and m["tB_min"] is not None:
                t_here = max(m["tA_min"], m["tB_min"])
                if first_t is None or t_here < first_t:
                    first_t = t_here
                    # pick a representative km; we’ll report A’s km for readability
                    first_k = m["kmA"]

        first_overlap = None
        if first_k is not None and first_t is not None:
            first_overlap = {
                "clock": _sec_to_clock(first_t),
                "km": round(first_k, 2)
            }

        # peak by areal density (break ties by combined desc, then smaller km)
        peak = None
        for m in samples:
            if peak is None:
                peak = m
            else:
                if (m["areal_density"] > peak["areal_density"]) or \
                   (m["areal_density"] == peak["areal_density"] and m["combined"] > peak["combined"]) or \
                   (m["areal_density"] == peak["areal_density"] and m["combined"] == peak["combined"] and m["kmA"] < peak["kmA"]):
                    peak = m

        if peak is None:
            # empty segment
            seg_out = {
                "seg_id": seg.seg_id,
                "segment_label": seg.segment_label,
                "eventA": seg.eventA,
                "eventB": seg.eventB,
                "from_km_A": seg.from_km_A,
                "to_km_A": seg.to_km_A,
                "from_km_B": seg.from_km_B,
                "to_km_B": seg.to_km_B,
                "direction": seg.direction,
                "width_m": seg.width_m,
                "peak": {
                    "km": round(seg.from_km_A, 2),
                    "A": 0, "B": 0, "combined": 0,
                    "areal_density": 0.0,
                    "zone": _zone_from_density(0.0)
                },
                "first_overlap": None,
                "trace": None if not debug else [],
            }
            out_segments.append(seg_out)
            continue

        peak_info = {
            "km": round(peak["kmA"], 2),  # report A km
            "A": peak["A"],
            "B": peak["B"],
            "combined": peak["combined"],
            "areal_density": peak["areal_density"],
            "zone": _zone_from_density(peak["areal_density"]),
        }

        trace_payload = None
        if debug:
            # keep reasonable size
            trace_payload = [
                {
                    "p": round(m["p"], 3),
                    "kmA": round(m["kmA"], 3),
                    "kmB": round(m["kmB"], 3),
                    "A": m["A"], "B": m["B"],
                    "combined": m["combined"],
                    "areal_density": m["areal_density"],
                    "tA_min": m["tA_min"],
                    "tB_min": m["tB_min"]
                }
                for m in samples[:300]
            ]

        seg_out = {
            "seg_id": seg.seg_id,
            "segment_label": seg.segment_label,
            "eventA": seg.eventA,
            "eventB": seg.eventB,
            "from_km_A": seg.from_km_A,
            "to_km_A": seg.to_km_A,
            "from_km_B": seg.from_km_B,
            "to_km_B": seg.to_km_B,
            "direction": seg.direction,
            "width_m": seg.width_m,
            "peak": peak_info,
            "first_overlap": first_overlap,
            "trace": trace_payload,
        }
        out_segments.append(seg_out)

    return {
        "engine": "density",
        "segments": out_segments
    }