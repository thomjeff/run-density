from __future__ import annotations

import io
import math
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import HTTPException
from pydantic import BaseModel, Field


# -----------------------------
# Pydantic models (request/response)
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


class SegmentDef(BaseModel):
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
    notes: Optional[str] = None


class SegmentPeak(BaseModel):
    km: float
    A: int
    B: int
    combined: int
    areal_density: float
    zone: str


class SegmentResult(BaseModel):
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
    peak: SegmentPeak
    first_overlap: Optional[float] = None
    trace: Optional[dict] = None


class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    startTimes: StartTimes
    segments: Optional[List[SegmentDef]] = None
    stepKm: float = 0.05
    timeWindow: int = 60
    debug: Optional[bool] = False
    seg_id: Optional[str] = None


# -----------------------------
# Utility
# -----------------------------

def load_csv(url: str) -> pd.DataFrame:
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch {url}: {e}")
    return pd.read_csv(io.StringIO(resp.text))


def classify_zone(density: float) -> str:
    if density < 1.0:
        return "green"
    elif density < 1.5:
        return "amber"
    elif density < 2.0:
        return "red"
    else:
        return "dark-red"


# -----------------------------
# Density math
# -----------------------------

def run_density(payload: DensityPayload) -> Dict:
    df = load_csv(payload.paceCsv)

    if payload.overlapsCsv:
        overlaps_df = load_csv(payload.overlapsCsv)
        segments: List[SegmentDef] = [
            SegmentDef(**row._asdict())
            for row in overlaps_df.itertuples(index=False)
        ]
    else:
        if not payload.segments:
            raise HTTPException(status_code=422, detail="Either overlapsCsv or segments[] required")
        segments = payload.segments

    results: List[SegmentResult] = []

    for seg in segments:
        # If debug mode and seg_id filter, skip others
        if payload.debug and payload.seg_id and seg.seg_id != payload.seg_id:
            continue

        L = min(seg.to_km_A - seg.from_km_A, seg.to_km_B - seg.from_km_B)
        if L <= 0:
            continue

        grid = [seg.from_km_A + s for s in
                [i * payload.stepKm for i in range(int(L / payload.stepKm) + 1)]]

        peak_comb = 0
        peak_at = seg.from_km_A
        peak_A = peak_B = 0
        peak_density = 0.0

        trace_data = {"s_km": [], "window_counts": []} if payload.debug else None

        for s in grid:
            dA = seg.from_km_A + (s - seg.from_km_A)
            dB = seg.from_km_B + (s - seg.from_km_A)

            tA = []
            for r in df[df["event"] == seg.eventA].itertuples():
                if r.distance >= dA:
                    tA.append(payload.startTimes.get(seg.eventA) * 60 + r.pace * 60 * dA)

            tB = []
            for r in df[df["event"] == seg.eventB].itertuples():
                if r.distance >= dB:
                    tB.append(payload.startTimes.get(seg.eventB) * 60 + r.pace * 60 * dB)

            # Rolling window counts – approximate: just count at mean times
            times = sorted(tA + tB)
            max_here = 0
            if times:
                left = 0
                for right, t in enumerate(times):
                    while t - times[left] > payload.timeWindow:
                        left += 1
                    max_here = max(max_here, right - left + 1)

            if max_here > peak_comb:
                peak_comb = max_here
                peak_at = s
                peak_A = len(tA)
                peak_B = len(tB)

            if payload.debug:
                trace_data["s_km"].append(s)
                trace_data["window_counts"].append(max_here)

        # Density calc
        vA = df[df["event"] == seg.eventA]["pace"].mean()
        vB = df[df["event"] == seg.eventB]["pace"].mean()
        vA_ms = 1000 / (vA * 60) if pd.notna(vA) else 3.0
        vB_ms = 1000 / (vB * 60) if pd.notna(vB) else 3.0
        avg_speed = (vA_ms + vB_ms) / 2
        length_m = max(1.0, avg_speed * payload.timeWindow)
        area = seg.width_m * length_m
        peak_density = peak_comb / area
        zone = classify_zone(peak_density)

        res = SegmentResult(
            seg_id=seg.seg_id,
            segment_label=seg.segment_label,
            eventA=seg.eventA,
            eventB=seg.eventB,
            from_km_A=seg.from_km_A,
            to_km_A=seg.to_km_A,
            from_km_B=seg.from_km_B,
            to_km_B=seg.to_km_B,
            direction=seg.direction,
            width_m=seg.width_m,
            peak=SegmentPeak(
                km=peak_at,
                A=peak_A,
                B=peak_B,
                combined=peak_comb,
                areal_density=peak_density,
                zone=zone,
            ),
            trace={
                "s_km": trace_data["s_km"][:5],
                "window_counts": trace_data["window_counts"][:5],
            } if payload.debug and trace_data else None
        )

        results.append(res)

    return {"engine": "density", "segments": [r.dict() for r in results]}