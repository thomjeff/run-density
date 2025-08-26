from __future__ import annotations
import csv
import io
import math
import statistics
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator


# ---------------------------
# Input models (Pydantic v2)
# ---------------------------

class LegacySegment(BaseModel):
    # legacy inline segment (only used if overlapsCsv not provided)
    eventA: str
    eventB: str
    from_: float = Field(..., alias="from")
    to: float
    direction: str = Field("uni", pattern="^(uni|bi)$")
    width_m: float = 3.0

    @property
    def seg_id(self) -> str:
        return "LEGACY"

    @property
    def segment_label(self) -> str:
        return f"{self.eventA}–{self.eventB} {self.from_:.2f}-{self.to:.2f}km"


class DensityPayload(BaseModel):
    paceCsv: HttpUrl
    overlapsCsv: Optional[HttpUrl] = None  # preferred path
    # start times in minutes from day start (e.g., 420 == 07:00)
    startTimes: Dict[str, int]
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds
    # legacy support
    segments: Optional[List[LegacySegment]] = None

    @field_validator("stepKm")
    @classmethod
    def _step_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("stepKm must be > 0")
        return v

    @field_validator("timeWindow")
    @classmethod
    def _tw_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeWindow must be > 0")
        return v


# ---------------------------
# Internal structures
# ---------------------------

@dataclass
class PaceRow:
    event: str
    runner_id: str
    pace_min_per_km: float  # minutes per km
    distance_km: float


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
    direction: str  # "uni" | "bi"
    width_m: float


# ---------------------------
# Helpers
# ---------------------------

def _fetch_text(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=502, detail=f"fetch failed: {url} ({resp.status})")
            data = resp.read()
            # handle potential large files but keep memory reasonable
            return data.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"fetch error for {url}: {e}")

def _load_pace_csv(url: str) -> List[PaceRow]:
    text = _fetch_text(url)
    rdr = csv.DictReader(io.StringIO(text))
    required = {"event", "runner_id", "pace", "distance"}
    if set(rdr.fieldnames or []) & required != required:
        raise HTTPException(status_code=422, detail="paceCsv missing required columns: event, runner_id, pace, distance")
    rows: List[PaceRow] = []
    for r in rdr:
        try:
            rows.append(
                PaceRow(
                    event=r["event"],
                    runner_id=str(r["runner_id"]),
                    pace_min_per_km=float(r["pace"]),
                    distance_km=float(r["distance"]),
                )
            )
        except Exception:
            # skip bad rows
            continue
    if not rows:
        raise HTTPException(status_code=422, detail="paceCsv parsed but no valid rows")
    return rows

def _load_overlaps_csv(url: str) -> List[OverlapRow]:
    text = _fetch_text(url)
    rdr = csv.DictReader(io.StringIO(text))
    required = {
        "seg_id","segment_label",
        "eventA","eventB",
        "from_km_A","to_km_A","from_km_B","to_km_B",
        "direction","width_m",
    }
    if set(rdr.fieldnames or []) & required != required:
        raise HTTPException(status_code=422, detail="overlapsCsv missing required columns (use seg_id, not segment_id)")
    out: List[OverlapRow] = []
    for r in rdr:
        try:
            out.append(
                OverlapRow(
                    seg_id=r["seg_id"].strip(),
                    segment_label=r["segment_label"].strip(),
                    eventA=r["eventA"].strip(),
                    eventB=r["eventB"].strip(),
                    from_km_A=float(r["from_km_A"]),
                    to_km_A=float(r["to_km_A"]),
                    from_km_B=float(r["from_km_B"]),
                    to_km_B=float(r["to_km_B"]),
                    direction=(r["direction"].strip() or "uni"),
                    width_m=float(r["width_m"]),
                )
            )
        except Exception:
            # tolerate note columns or partial bad lines
            continue
    if not out:
        raise HTTPException(status_code=422, detail="overlapsCsv parsed but no valid rows")
    return out

def _legacy_as_overlaps(legacy: List[LegacySegment]) -> List[OverlapRow]:
    out: List[OverlapRow] = []
    for i, s in enumerate(legacy, start=1):
        out.append(
            OverlapRow(
                seg_id=f"LEG-{i}",
                segment_label=s.segment_label,
                eventA=s.eventA,
                eventB=s.eventB,
                from_km_A=s.from_,
                to_km_A=s.to,
                from_km_B=s.from_,
                to_km_B=s.to,
                direction=s.direction,
                width_m=s.width_m,
            )
        )
    return out

def _arrival_min(start_min: int, pace_min_per_km: float, km: float) -> float:
    # minutes to reach km (simple linear model)
    return start_min + pace_min_per_km * km

def _window_count_at_km(
    km: float,
    event: str,
    runners: List[PaceRow],
    startTimes: Dict[str, int],
    center_min: float,
    window_sec: int,
) -> Tuple[int, float]:
    """Return (count, avg_speed_mps) for runners of `event` within the time window at position `km`."""
    if event not in startTimes:
        return 0, 0.0
    start_min = startTimes[event]
    half_win_min = window_sec / 120.0  # seconds -> minutes, half-window
    count = 0
    speeds: List[float] = []  # m/s
    for r in runners:
        if r.event != event:
            continue
        if km > r.distance_km + 1e-9:
            continue  # runner never reaches this km
        t_min = _arrival_min(start_min, r.pace_min_per_km, km)
        if abs(t_min - center_min) <= half_win_min:
            count += 1
            # speed from pace: (km per min) -> m/s
            if r.pace_min_per_km > 0:
                mps = (1000.0) / (r.pace_min_per_km * 60.0)
                speeds.append(mps)
    avg_speed = statistics.fmean(speeds) if speeds else 0.0
    return count, avg_speed

def _areal_density(combined: int, avg_speed_mps: float, window_sec: int, width_m: float) -> float:
    """
    people / m^2 ~= combined / (width * (distance advanced in window))
    distance advanced ~ avg_speed * window_sec
    Clamp to avoid div-by-zero and keep values reasonable.
    """
    travel_m = max(avg_speed_mps * window_sec, 0.5)  # minimum small slab
    area_m2 = max(width_m * travel_m, 0.5)
    return combined / area_m2


# ---------------------------
# Engine
# ---------------------------

def run_density(payload: DensityPayload) -> dict:
    # 1) load paces
    paces = _load_pace_csv(str(payload.paceCsv))

    # 2) load overlaps (preferred) or legacy
    if payload.overlapsCsv:
        overlaps = _load_overlaps_csv(str(payload.overlapsCsv))
    elif payload.segments:
        overlaps = _legacy_as_overlaps(payload.segments)
    else:
        raise HTTPException(status_code=422, detail="Provide overlapsCsv or legacy segments[]")

    # 3) compute per-overlap summary with stepping
    segments_out = []
    for seg in overlaps:
        # map both events onto a shared path length for stepping
        lengthA = abs(seg.to_km_A - seg.from_km_A)
        lengthB = abs(seg.to_km_B - seg.from_km_B)
        # use min length so step grid stays inside both
        length = min(lengthA, lengthB)
        if length <= 0:
            continue

        steps = max(1, math.ceil(length / payload.stepKm))
        # build a representative time center: mean of median arrivals from both events at midpoint
        midA = seg.from_km_A + (lengthA * 0.5 if lengthA > 0 else 0.0)
        midB = seg.from_km_B + (lengthB * 0.5 if lengthB > 0 else 0.0)

        centers_min: List[float] = []
        for ev, midkm in ((seg.eventA, midA), (seg.eventB, midB)):
            if ev in payload.startTimes:
                # use median runner pace for ev
                p = [r.pace_min_per_km for r in paces if r.event == ev]
                if p:
                    med_pace = statistics.median(p)
                    centers_min.append(_arrival_min(payload.startTimes[ev], med_pace, midkm))
        center_min = statistics.fmean(centers_min) if centers_min else 0.0

        peak = {
            "km": None,
            "A": 0,
            "B": 0,
            "combined": 0,
            "areal_density": 0.0,
            "zone": "green",
        }

        # walk the segment in steps; for A/B we map step i to its own km on each course
        for i in range(steps + 1):
            frac = i / steps
            kmA = seg.from_km_A + frac * (seg.to_km_A - seg.from_km_A)
            kmB = seg.from_km_B + frac * (seg.to_km_B - seg.from_km_B)

            countA, speedA = _window_count_at_km(kmA, seg.eventA, paces, payload.startTimes, center_min, payload.timeWindow)
            countB, speedB = _window_count_at_km(kmB, seg.eventB, paces, payload.startTimes, center_min, payload.timeWindow)
            combined = countA + countB
            avg_speed = (speedA + speedB) / ( (1 if speedA>0 else 0) + (1 if speedB>0 else 0) or 1 )
            dens = _areal_density(combined, avg_speed, payload.timeWindow, seg.width_m)

            if combined > peak["combined"]:
                peak.update({
                    "km": round((kmA + kmB) / 2.0, 2),
                    "A": countA,
                    "B": countB,
                    "combined": combined,
                    "areal_density": round(dens, 2),
                    "zone": _zone(dens),
                })

        segments_out.append({
            "seg_id": seg.seg_id,
            "segment_label": seg.segment_label,
            "eventA": seg.eventA,
            "eventB": seg.eventB,
            "direction": seg.direction,
            "width_m": seg.width_m,
            "peak": peak,
        })

    return {
        "engine": "density",
        "segments": segments_out,
    }


def _zone(d: float) -> str:
    # thresholds per your defaults
    if d < 1.0:
        return "green"
    if d < 1.5:
        return "amber"
    if d < 2.0:
        return "red"
    return "dark-red"