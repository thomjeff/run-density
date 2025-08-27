# app/density.py
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field


# -----------------------------
# Pydantic models (request/response)
# -----------------------------

class StartTimes(BaseModel):
    # Minutes offset after race clock zero
    Full: Optional[int] = None
    Half: Optional[int] = None
    TenK: Optional[int] = Field(default=None, alias="10K")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    def get(self, event: str) -> int:
        if event == "Full" and self.Full is not None:
            return self.Full
        if event == "Half" and self.Half is not None:
            return self.Half
        if event == "10K" and self.TenK is not None:
            return self.TenK
        return 0  # default to 0 if missing to avoid crashes


class SegmentIn(BaseModel):
    eventA: str
    eventB: str
    from_: float = Field(alias="from")  # retained for optional ad-hoc POST bodies
    to: float
    direction: str  # 'uni' | 'bi'
    width_m: float


class DensityPayload(BaseModel):
    paceCsv: Optional[str] = None
    overlapsCsv: Optional[str] = None
    startTimes: StartTimes
    segments: Optional[List[SegmentIn]] = None
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }


# -----------------------------
# Internal helpers
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


def _fetch_csv(url: str) -> pd.DataFrame:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch CSV: {url} ({e})")


def _load_overlaps(overlaps_csv_url: Optional[str], segments_from_body: Optional[List[SegmentIn]]) -> List[OverlapRow]:
    rows: List[OverlapRow] = []
    if overlaps_csv_url:
        df = _fetch_csv(overlaps_csv_url)
        required = [
            "seg_id","segment_label","eventA","eventB",
            "from_km_A","to_km_A","from_km_B","to_km_B","direction","width_m"
        ]
        for col in required:
            if col not in df.columns:
                raise HTTPException(status_code=422, detail=f"overlaps.csv missing column: {col}")

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
                direction=str(r["direction"]),
                width_m=float(r["width_m"]),
            ))
        return rows

    # fallback: segments array (legacy/manual post)
    if segments_from_body:
        # fabricate seg_id/label so the response shape is consistent
        out: List[OverlapRow] = []
        for i, s in enumerate(segments_from_body, start=1):
            out.append(OverlapRow(
                seg_id=f"S{i}",
                segment_label=f"Ad-hoc {i}",
                eventA=s.eventA, eventB=s.eventB,
                from_km_A=s.from_, to_km_A=s.to,
                from_km_B=s.from_, to_km_B=s.to,
                direction=s.direction,
                width_m=s.width_m,
            ))
        return out

    raise HTTPException(status_code=422, detail="Provide overlapsCsv or segments")


@dataclass
class EventPace:
    # Pre-sorted by pace (ascending), so arrival time order stays consistent for any km
    pace_s_per_km: np.ndarray  # shape (N,)
    distance_km: np.ndarray     # shape (N,) total distance for runner (not used in arrival, but kept)
    start_offset_min: int       # start offset (minutes)


def _load_paces(pace_csv_url: str, start_times: StartTimes) -> Dict[str, EventPace]:
    df = _fetch_csv(pace_csv_url)
    need = ["event", "runner_id", "pace", "distance"]
    for c in need:
        if c not in df.columns:
            raise HTTPException(status_code=422, detail=f"paceCsv missing column: {c}")

    events = {}
    for name in ["Full", "Half", "10K"]:
        sub = df[df["event"] == name].copy()
        if sub.empty:
            continue
        # pace is minutes/km in file; convert to seconds/km
        sub["pace_s_per_km"] = sub["pace"].astype(float) * 60.0
        # sort by pace (fastest first) ONCE; order remains for linear transforms
        sub = sub.sort_values("pace_s_per_km", ascending=True)
        events[name] = EventPace(
            pace_s_per_km=sub["pace_s_per_km"].to_numpy(),
            distance_km=sub["distance"].to_numpy(),
            start_offset_min=start_times.get(name),
        )
    if not events:
        raise HTTPException(status_code=422, detail="paceCsv has no known events (Full/Half/10K)")
    return events


def _km_linspace(a0: float, a1: float, step_km: float) -> np.ndarray:
    if a1 < a0:
        a0, a1 = a1, a0
    if step_km <= 0:
        step_km = 0.03
    n = max(1, int(math.floor((a1 - a0) / step_km)) + 1)
    xs = a0 + np.arange(n) * step_km
    if xs[-1] < a1 - 1e-9:
        xs = np.append(xs, a1)
    return xs


def _arrival_times_seconds(ev: EventPace, km: float) -> np.ndarray:
    """
    Arrival time (seconds) at km for every runner of the event:
      T = start_offset_min*60 + pace_s_per_km * km
    Order is preserved because pace_s_per_km is sorted asc.
    """
    return ev.start_offset_min * 60.0 + ev.pace_s_per_km * km


def _peak_window_two_lists(
    times_a: np.ndarray,
    times_b: np.ndarray,
    window_s: float,
) -> Tuple[int, int, int, float]:
    """
    Two-pointer sliding window over merged times.
    Returns:
      (combined_max, best_a, best_b, best_window_start_seconds)
    """
    # Merge with labels (0 for A, 1 for B) without sorting each time:
    # times are individually sorted if pace arrays were sorted.
    i = j = 0
    merged_t: List[float] = []
    merged_lbl: List[int] = []
    na, nb = len(times_a), len(times_b)
    while i < na or j < nb:
        if j >= nb or (i < na and times_a[i] <= times_b[j]):
            merged_t.append(times_a[i]); merged_lbl.append(0); i += 1
        else:
            merged_t.append(times_b[j]); merged_lbl.append(1); j += 1

    L = len(merged_t)
    left = 0
    countA = countB = 0
    best_total = 0
    best_a = 0
    best_b = 0
    best_start = 0.0

    for right in range(L):
        if merged_lbl[right] == 0:
            countA += 1
        else:
            countB += 1

        # shrink window
        while merged_t[right] - merged_t[left] > window_s and left <= right:
            if merged_lbl[left] == 0:
                countA -= 1
            else:
                countB -= 1
            left += 1

        total = countA + countB
        if total > best_total:
            best_total = total
            best_a = countA
            best_b = countB
            best_start = merged_t[right] - min(window_s, merged_t[right] - merged_t[left] if right >= left else 0)

    return best_total, best_a, best_b, best_start


def _first_overlap_two_lists(
    times_a: np.ndarray,
    times_b: np.ndarray,
    window_s: float,
) -> Optional[float]:
    """
    Earliest window start time (seconds) such that window contains >=1 from A and >=1 from B.
    Return None if no overlap.
    """
    i = j = 0
    merged_t: List[float] = []
    merged_lbl: List[int] = []
    na, nb = len(times_a), len(times_b)
    while i < na or j < nb:
        if j >= nb or (i < na and times_a[i] <= times_b[j]):
            merged_t.append(times_a[i]); merged_lbl.append(0); i += 1
        else:
            merged_t.append(times_b[j]); merged_lbl.append(1); j += 1

    L = len(merged_t)
    left = 0
    countA = countB = 0
    for right in range(L):
        if merged_lbl[right] == 0:
            countA += 1
        else:
            countB += 1

        while merged_t[right] - merged_t[left] > window_s and left <= right:
            if merged_lbl[left] == 0:
                countA -= 1
            else:
                countB -= 1
            left += 1

        if countA > 0 and countB > 0:
            # earliest time within this window is merged_t[left]
            return merged_t[left]
    return None


def _fmt_clock(sec: float) -> str:
    if sec is None or math.isnan(sec):
        return "00:00:00"
    sec = max(0, int(round(sec)))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# -----------------------------
# Main entry
# -----------------------------

def run_density(payload: DensityPayload, seg_id_filter: Optional[str] = None, debug: bool = False):
    # 1) Load overlaps (CSV or segments array)
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)

    # Optional filter by seg_id (query param)
    if seg_id_filter:
        overlaps = [o for o in overlaps if o.seg_id == seg_id_filter]
        if not overlaps:
            # keep shape stable
            return {"engine": "density", "segments": []}

    # 2) Load pace data & prep per-event arrays
    events = _load_paces(payload.paceCsv, payload.startTimes)
    window_s = float(payload.timeWindow)

    # Prepare small cache to avoid recomputing per-km arrivals too often
    # (event_name, km) -> (times seconds ndarray)
    arr_cache: Dict[Tuple[str, float], np.ndarray] = {}

    def arrival(ev_name: str, km: float) -> np.ndarray:
        key = (ev_name, round(km, 5))
        if key in arr_cache:
            return arr_cache[key]
        ev = events.get(ev_name)
        if ev is None:
            arr_cache[key] = np.array([], dtype=float)
        else:
            arr_cache[key] = _arrival_times_seconds(ev, km)
        return arr_cache[key]

    # Helper for areal density: estimate window length (meters)
    # We approximate mean pace (sec/km) of runners actually within the peak window.
    def window_length_m(best_a: int, best_b: int, times_median_pace_s_per_km: float) -> float:
        if times_median_pace_s_per_km <= 0:
            return 0.0
        mps = 1000.0 / times_median_pace_s_per_km
        return mps * window_s

    segments_out: List[dict] = []

    for ov in overlaps:
        # sample along segment using linear mapping for A/B km
        steps = _km_linspace(0.0, 1.0, max(1e-6, payload.stepKm / max(1e-6, abs(ov.to_km_A - ov.from_km_A))))
        best = {
            "combined": 0,
            "A": 0, "B": 0,
            "km": float(ov.from_km_A),  # report along A's scale by convention
            "areal_density": 0.0,
            "zone": "green",
            "clock_s": None,
            "clock": "00:00:00",
        }

        first_overlap_clock_s: Optional[float] = None
        first_overlap_km: Optional[float] = None

        trace: List[dict] = []

        # precompute per-event median pace (sec/km) to convert time window -> length
        med_pace_A = float(np.median(events.get(ov.eventA, EventPace(np.array([]), np.array([]), 0)).pace_s_per_km)) if ov.eventA in events else math.nan
        med_pace_B = float(np.median(events.get(ov.eventB, EventPace(np.array([]), np.array([]), 0)).pace_s_per_km)) if ov.eventB in events else math.nan
        # combine medians (if one missing, use the other)
        if math.isnan(med_pace_A) and math.isnan(med_pace_B):
            median_pace = 360.0  # 6:00 min/km fallback
        elif math.isnan(med_pace_A):
            median_pace = med_pace_B
        elif math.isnan(med_pace_B):
            median_pace = med_pace_A
        else:
            median_pace = 0.5 * (med_pace_A + med_pace_B)

        for t in steps:
            kmA = ov.from_km_A + t * (ov.to_km_A - ov.from_km_A)
            kmB = ov.from_km_B + t * (ov.to_km_B - ov.from_km_B)

            timesA = arrival(ov.eventA, kmA)
            timesB = arrival(ov.eventB, kmB)

            total, cntA, cntB, start_s = _peak_window_two_lists(timesA, timesB, window_s)

            # areal density
            length_m = window_length_m(cntA, cntB, median_pace)
            area_m2 = max(ov.width_m, 0.1) * max(length_m, 0.1)
            areal = (total / area_m2) if area_m2 > 0 else 0.0

            if total > best["combined"]:
                best.update({
                    "combined": int(total),
                    "A": int(cntA),
                    "B": int(cntB),
                    "km": float(kmA),  # report in A-scale
                    "areal_density": float(areal),
                    "clock_s": float(start_s + window_s / 2.0),
                    "clock": _fmt_clock(start_s + window_s / 2.0),
                    "zone": ("dark-red" if areal >= 2.0 else "red" if areal >= 1.5 else "amber" if areal >= 1.0 else "green"),
                })

            # first overlap (earliest time with >=1 from each)
            if first_overlap_clock_s is None:
                s = _first_overlap_two_lists(timesA, timesB, window_s)
                if s is not None:
                    first_overlap_clock_s = s
                    first_overlap_km = kmA

            if debug and len(trace) < 10:
                trace.append({
                    "km": round(kmA, 3),
                    "peak": {"A": int(cntA), "B": int(cntB), "combined": int(total)},
                    "clock": _fmt_clock(start_s + window_s / 2.0),
                    "areal_density": float(areal),
                })

        seg_out = {
            "seg_id": ov.seg_id,
            "segment_label": ov.segment_label,
            "eventA": ov.eventA,
            "eventB": ov.eventB,
            "direction": ov.direction,
            "width_m": ov.width_m,
            "peak": {
                "km": round(best["km"], 3),
                "A": best["A"],
                "B": best["B"],
                "combined": best["combined"],
                "areal_density": best["areal_density"],
                "zone": best["zone"],
            },
            "first_overlap": (None if first_overlap_clock_s is None else {
                "clock": _fmt_clock(first_overlap_clock_s),
                "km": round(first_overlap_km if first_overlap_km is not None else 0.0, 3),
            }),
        }
        if debug:
            seg_out["trace"] = trace

        segments_out.append(seg_out)

    return {"engine": "density", "segments": segments_out}