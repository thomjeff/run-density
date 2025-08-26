# FastAPI density engine: optional segments[], or overlapsCsv → segments
from __future__ import annotations

from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from fastapi import HTTPException
import io
import math

import pandas as pd
import numpy as np


Direction = Literal["uni", "contra"]


class SegmentIn(BaseModel):
    # Incoming shape when caller sends segments[] directly
    eventA: str
    eventB: str
    from_km: float = Field(alias="from")
    to_km: float = Field(alias="to")
    direction: Direction
    width_m: float = Field(alias="width_m", default=3.0)

    # optional, if caller included them
    seg_id: Optional[str] = None
    segment_label: Optional[str] = None

    @field_validator("to_km")
    @classmethod
    def _range_ok(cls, v, info):
        # pydantic v2: validator sees field only; ensure alias-from is already mapped
        # Will check using model fields at runtime if needed.
        return v

    def ensure_order(self) -> "SegmentIn":
        if self.from_km <= self.to_km:
            return self
        # Normalize if caller flipped them
        return self.model_copy(update={"from_km": self.to_km, "to_km": self.from_km})


class StartTimes(BaseModel):
    # Map: event -> minutes after midnight (int)
    __root__: Dict[str, int]

    def minutes(self, ev: str) -> int:
        try:
            return int(self.__root__[ev])
        except KeyError:
            raise HTTPException(status_code=422, detail=f"Missing start time for event '{ev}'")


class DensityPayload(BaseModel):
    paceCsv: HttpUrl
    # Either provide segments[] OR an overlapsCsv we will parse into segments.
    segments: Optional[List[SegmentIn]] = None
    overlapsCsv: Optional[HttpUrl] = None

    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds

    @field_validator("stepKm")
    @classmethod
    def _positive_step(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("stepKm must be > 0")
        return v

    @field_validator("timeWindow")
    @classmethod
    def _positive_window(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeWindow must be > 0")
        return v


# -------------------------
# CSV helpers
# -------------------------

def _read_csv_url(url: str) -> pd.DataFrame:
    try:
        # Let pandas fetch directly; no extra deps
        return pd.read_csv(url)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch CSV: {url} ({e})")


def _load_pace_csv(url: str) -> pd.DataFrame:
    df = _read_csv_url(url)
    required = {"event", "runner_id", "pace", "distance"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=422, detail=f"paceCsv missing columns: {', '.join(sorted(missing))}")

    # Coerce numeric
    for col in ("pace", "distance"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["pace", "distance"])
    # Keep just what we need
    return df[["event", "runner_id", "pace", "distance"]].copy()


def _overlaps_csv_to_segments(url: str) -> List[SegmentIn]:
    """
    Accept headers exactly as your current repo uses:
      seg_id, segment_label, eventA, eventB,
      from_km_A, to_km_A, from_km_B, to_km_B,
      direction, width_m, notes
    We will materialize segments using the A-side distances for [from, to].
    """
    df = _read_csv_url(url)

    required = [
        "seg_id", "segment_label", "eventA", "eventB",
        "from_km_A", "to_km_A", "from_km_B", "to_km_B",
        "direction", "width_m"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"overlapsCsv missing columns: {', '.join(missing)}")

    # Coerce numeric columns
    for c in ["from_km_A", "to_km_A", "from_km_B", "to_km_B", "width_m"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["from_km_A", "to_km_A", "width_m"])

    segments: List[SegmentIn] = []
    for _, r in df.iterrows():
        seg = SegmentIn(
            eventA=str(r["eventA"]).strip(),
            eventB=str(r["eventB"]).strip(),
            **{
                "from": float(r["from_km_A"]),
                "to": float(r["to_km_A"]),
                "width_m": float(r["width_m"])
            },
            direction=str(r["direction"]).strip() if str(r["direction"]).strip() in ("uni", "contra") else "uni",
            seg_id=str(r["seg_id"]).strip() or None,
            segment_label=str(r["segment_label"]).strip() or None,
        ).ensure_order()
        segments.append(seg)

    if not segments:
        raise HTTPException(status_code=422, detail="No valid rows parsed from overlapsCsv.")
    return segments


# -------------------------
# Density math
# -------------------------

def _peak_in_window(times_sec: np.ndarray, window_sec: float) -> int:
    """
    Given sorted times in seconds, return the maximum count within any
    contiguous window of length window_sec. Two-pointer sweep (O(n)).
    """
    if times_sec.size == 0:
        return 0
    i = 0
    best = 1
    for j in range(times_sec.size):
        # expand right to j; shrink left while window too wide
        while times_sec[j] - times_sec[i] > window_sec:
            i += 1
        count = j - i + 1
        if count > best:
            best = count
    return int(best)


def _event_peak_at_x(
    pace_df: pd.DataFrame,
    event: str,
    x_km: float,
    start_minutes: int,
    window_sec: float
) -> int:
    ev = pace_df[pace_df["event"] == event]
    if ev.empty:
        return 0

    # pace is minutes per km → seconds per km
    pace_sec_per_km = ev["pace"].to_numpy(dtype=float) * 60.0
    t0 = float(start_minutes) * 60.0
    # Pass time at position x: t = start + pace_sec_per_km * x
    times = t0 + pace_sec_per_km * x_km
    # Sort for sliding window
    times_sorted = np.sort(times)
    return _peak_in_window(times_sorted, window_sec)


def _scan_segment_peak(
    pace_df: pd.DataFrame,
    seg: SegmentIn,
    start_times: StartTimes,
    step_km: float,
    window_sec: int
) -> Dict[str, Any]:
    """
    Return the peak across the segment for combined flow and per-event breakdown.
    """
    x0, x1 = float(seg.from_km), float(seg.to_km)
    if not math.isfinite(x0) or not math.isfinite(x1):
        raise HTTPException(status_code=422, detail=f"Non-finite distances in segment {seg.seg_id or seg.segment_label or '(unnamed)'}")

    xs = np.arange(min(x0, x1), max(x0, x1) + 1e-9, step_km, dtype=float)

    startA = start_times.minutes(seg.eventA)
    startB = start_times.minutes(seg.eventB)

    best = {
        "km": float(xs[0]) if xs.size else float(x0),
        "A": 0,
        "B": 0,
        "combined": 0,
        "areal_density": 0.0,
    }

    # Precompute constant per segment
    width = max(0.1, float(seg.width_m))  # guard against zero
    for x in xs:
        a = _event_peak_at_x(pace_df, seg.eventA, x, startA, window_sec)
        b = _event_peak_at_x(pace_df, seg.eventB, x, startB, window_sec)
        combined = a + b
        # Simple areal density estimate (people per square meter) across ~1m along-track slice
        areal = float(combined) / max(0.1, width)

        if combined > best["combined"]:
            best.update({"km": float(x), "A": int(a), "B": int(b), "combined": int(combined), "areal_density": areal})

    return best


# -------------------------
# Public entry point
# -------------------------

def run_density(payload: DensityPayload) -> Dict[str, Any]:
    """
    Main engine invoked by app.main. Returns:
      {
        "engine": "density",
        "segments": [
            {
              "seg_id": "...", "segment_label": "...",
              "pair": "10K-Half", "direction": "uni", "width_m": 3.0,
              "from_km": 0.0, "to_km": 2.7,
              "peak": { "km": 1.8, "A": 260, "B": 140, "combined": 400, "areal_density": 2.2 }
            }, ...
        ]
      }
    """
    # Materialize segments from overlapsCsv if caller didn’t pass them
    segments: List[SegmentIn]
    if payload.segments and len(payload.segments) > 0:
        segments = [s.ensure_order() for s in payload.segments]
    elif payload.overlapsCsv:
        segments = _overlaps_csv_to_segments(str(payload.overlapsCsv))
    else:
        raise HTTPException(
            status_code=422,
            detail="Either provide 'segments' or 'overlapsCsv'."
        )

    # Load pace data once
    pace_df = _load_pace_csv(str(payload.paceCsv))

    out_segments: List[Dict[str, Any]] = []
    for seg in segments:
        peak = _scan_segment_peak(
            pace_df=pace_df,
            seg=seg,
            start_times=payload.startTimes,
            step_km=payload.stepKm,
            window_sec=payload.timeWindow
        )
        out_segments.append({
            "seg_id": seg.seg_id,
            "segment_label": seg.segment_label or seg.seg_id,
            "pair": f"{seg.eventA}-{seg.eventB}",
            "direction": seg.direction,
            "width_m": seg.width_m,
            "from_km": seg.from_km,
            "to_km": seg.to_km,
            "peak": peak
        })

    return {
        "engine": "density",
        "segments": out_segments
    }