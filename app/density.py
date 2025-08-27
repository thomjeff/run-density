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
# Pydantic models
# -----------------------------

class StartTimes(BaseModel):
    Full: Optional[int] = None
    Half: Optional[int] = None
    TenK: Optional[int] = Field(default=None, alias="10K")

    def get(self, event: str) -> int:
        if event == "Full" and self.Full is not None:
            return self.Full
        if event == "Half" and self.Half is not None:
            return self.Half
        if event == "10K" and self.TenK is not None:
            return self.TenK
        return 0

class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: int = 60
    segments: Optional[List[Dict]] = None

# -----------------------------
# Data structures
# -----------------------------

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

# -----------------------------
# Helpers
# -----------------------------

ZONE_THRESHOLDS = [
    ("green",    0.0, 1.0),
    ("amber",    1.0, 1.5),
    ("red",      1.5, 2.0),
    ("dark-red", 2.0, float("inf")),
]

def zone_for(value: float) -> str:
    for name, lo, hi in ZONE_THRESHOLDS:
        if lo <= value < hi:
            return name
    return "dark-red"

def hms_from_seconds(secs: float) -> str:
    secs = max(0, int(round(secs)))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def _get(url: str) -> str:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch {url}: {e}")

def _load_pace(pace_csv_url: str) -> pd.DataFrame:
    text = _get(pace_csv_url)
    df = pd.read_csv(io.StringIO(text))
    required = {"event", "runner_id", "pace", "distance"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"paceCsv missing required columns: {sorted(missing)}")
    df["pace_s_per_km"] = df["pace"].astype(float) * 60.0
    df["distance"] = df["distance"].astype(float)
    return df

def _load_overlaps(overlaps_csv_url: Optional[str], inline_segments: Optional[List[Dict]]) -> List[SegmentSpec]:
    rows: List[Dict] = []
    if overlaps_csv_url:
        text = _get(overlaps_csv_url)
        odf = pd.read_csv(io.StringIO(text))
        req = [
            "seg_id","segment_label","eventA","eventB",
            "from_km_A","to_km_A","from_km_B","to_km_B",
            "direction","width_m",
        ]
        missing = [c for c in req if c not in odf.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"overlapsCsv missing required columns: {missing}")
        rows = odf.to_dict(orient="records")
    elif inline_segments:
        rows = []
        for i, raw in enumerate(inline_segments, start=1):
            seg = {
                "seg_id": f"S{i}",
                "segment_label": f"Inline S{i}",
                "eventA": raw.get("eventA"),
                "eventB": raw.get("eventB"),
                "from_km_A": float(raw.get("from")),
                "to_km_A": float(raw.get("to")),
                "from_km_B": float(raw.get("from")),
                "to_km_B": float(raw.get("to")),
                "direction": raw.get("direction", "uni"),
                "width_m": float(raw.get("width_m") or raw.get("width") or 3.0),
            }
            rows.append(seg)
    else:
        raise HTTPException(status_code=400, detail="Provide overlapsCsv or segments")

    return [
        SegmentSpec(
            seg_id=str(raw["seg_id"]).strip(),
            segment_label=str(raw["segment_label"]).strip(),
            eventA=str(raw["eventA"]).strip(),
            eventB=str(raw["eventB"]).strip(),
            from_km_A=float(raw["from_km_A"]),
            to_km_A=float(raw["to_km_A"]),
            from_km_B=float(raw["from_km_B"]),
            to_km_B=float(raw["to_km_B"]),
            direction=str(raw["direction"]).strip().lower(),
            width_m=float(raw["width_m"]),
        )
        for raw in rows
    ]

# -----------------------------
# Core math
# -----------------------------

def _compute_segment(seg: SegmentSpec, df: pd.DataFrame, start_times: StartTimes,
                     step_km: float, time_window_s: int, want_trace: bool=False) -> Dict:
    # filter runners
    dfA = df[df["event"] == seg.eventA].copy()
    dfB = df[df["event"] == seg.eventB].copy()

    # start offsets
    dfA["start_s"] = start_times.get(seg.eventA) * 60
    dfB["start_s"] = start_times.get(seg.eventB) * 60

    # speeds
    dfA["speed_mps"] = 1000.0 / dfA["pace_s_per_km"]
    dfB["speed_mps"] = 1000.0 / dfB["pace_s_per_km"]

    seg_len = max(seg.to_km_A - seg.from_km_A, seg.to_km_B - seg.from_km_B)
    n_steps = max(1, int(seg_len / step_km))

    peak = {"km": None, "A": 0, "B": 0, "combined": 0, "areal_density": 0.0, "zone": "green"}
    first_overlap = None
    trace = []

    for i in range(n_steps+1):
        kmA = seg.from_km_A + (seg.to_km_A - seg.from_km_A) * i/n_steps
        kmB = seg.from_km_B + (seg.to_km_B - seg.from_km_B) * i/n_steps

        tA = dfA["start_s"] + kmA * dfA["pace_s_per_km"]
        tB = dfB["start_s"] + kmB * dfB["pace_s_per_km"]

        tmin = max(tA.min(), tB.min())
        tmax = min(tA.max(), tB.max())

        window = (tmin, tmin+time_window_s)
        a_here = ((tA >= window[0]) & (tA <= window[1])).sum()
        b_here = ((tB >= window[0]) & (tB <= window[1])).sum()

        combined = a_here + b_here
        if combined > peak["combined"]:
            peak = {
                "km": round(kmA,2),
                "A": int(a_here),
                "B": int(b_here),
                "combined": int(combined),
                "areal_density": combined / (seg.width_m/2.0 if seg.direction=="bi" else seg.width_m),
                "zone": zone_for(combined / (seg.width_m/2.0 if seg.direction=="bi" else seg.width_m))
            }
        if first_overlap is None and combined > 0:
            first_overlap = {"km": round(kmA,2), "clock": hms_from_seconds(window[0])}
        if want_trace:
            trace.append({"km": round(kmA,2), "A": int(a_here), "B": int(b_here), "combined": int(combined)})

    return {
        "seg_id": seg.seg_id,
        "segment_label": seg.segment_label,
        "eventA": seg.eventA,
        "eventB": seg.eventB,
        "direction": seg.direction,
        "width_m": seg.width_m,
        "first_overlap": first_overlap,
        "peak": peak,
        "trace": trace if want_trace else None
    }

# -----------------------------
# Public API
# -----------------------------

def run_density(payload: DensityPayload, seg_id_filter: Optional[str]=None, debug: bool=False):
    pace_df = _load_pace(payload.paceCsv)
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)
    if seg_id_filter:
        overlaps = [o for o in overlaps if o.seg_id == seg_id_filter]

    results = []
    for seg in overlaps:
        results.append(_compute_segment(seg, pace_df, payload.startTimes,
                                        payload.stepKm, payload.timeWindow, debug))
    return {"engine": "density", "segments": results}