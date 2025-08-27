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
# Pydantic models (request/response)
# -----------------------------

class StartTimes(BaseModel):
    # minutes after "race clock 0"
    full: Optional[int] = Field(default=None, alias="Full")
    half: Optional[int] = Field(default=None, alias="Half")
    tenk: Optional[int] = Field(default=None, alias="10K")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    def get(self, event: str) -> int:
        if event == "Full" and self.full is not None:
            return self.full
        if event == "Half" and self.half is not None:
            return self.half
        if event == "10K" and self.tenk is not None:
            return self.tenk
        return 0

class SegmentIn(BaseModel):
    eventA: str
    eventB: str
    # inline/simple segments (ad-hoc)
    from_: Optional[float] = Field(default=None, alias="from")
    to: Optional[float] = None
    # per-event km (used when loaded from overlapsCsv)
    from_km_A: Optional[float] = None
    to_km_A: Optional[float] = None
    from_km_B: Optional[float] = None
    to_km_B: Optional[float] = None
    direction: Optional[str] = "uni"
    width_m: Optional[float] = None

    # IDs/labels (present when loaded from overlapsCsv; optional for ad-hoc)
    seg_id: Optional[str] = None
    segment_label: Optional[str] = None


class PeakOut(BaseModel):
    km: float
    A: int
    B: int
    combined: int
    areal_density: Optional[float] = None
    zone: Optional[str] = None


class SegmentOut(BaseModel):
    seg_id: Optional[str] = None
    segment_label: Optional[str] = None
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: Optional[str] = None
    width_m: Optional[float] = None
    peak: Optional[PeakOut] = None
    first_overlap: Optional[dict] = None  # placeholder for future enrichment


class DensityPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    segments: Optional[List[SegmentIn]] = None
    startTimes: StartTimes
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds


class DensityResponse(BaseModel):
    engine: str = "density"
    segments: List[SegmentOut]


# -----------------------------
# Internal data structures
# -----------------------------

@dataclass
class Runner:
    pace_sec_per_km: float
    distance_km: float

# event -> list of Runner
PaceIndex = Dict[str, List[Runner]]


# -----------------------------
# Utilities
# -----------------------------

def _fetch_csv(url: str) -> pd.DataFrame:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to load CSV from {url}: {e}")


def _load_pace_index(pace_csv_url: str) -> PaceIndex:
    df = _fetch_csv(pace_csv_url)
    needed = {"event", "runner_id", "pace", "distance"}
    missing = needed - set(df.columns.astype(str))
    if missing:
        raise HTTPException(status_code=422, detail=f"paceCsv missing columns: {sorted(missing)}")

    # pace is minutes/km -> convert to seconds/km
    runners_by_event: PaceIndex = {}
    for event, g in df.groupby("event"):
        lst: List[Runner] = []
        for _, row in g.iterrows():
            try:
                pace_min_per_km = float(row["pace"])
                pace_sec_per_km = pace_min_per_km * 60.0
                dist_km = float(row["distance"])
            except Exception:
                continue
            lst.append(Runner(pace_sec_per_km=pace_sec_per_km, distance_km=dist_km))
        # Sort by pace (fast first) purely to make window scans cache-friendly
        lst.sort(key=lambda r: r.pace_sec_per_km)
        runners_by_event[event] = lst
    return runners_by_event


def _zone_from_density(ppl_per_m2: float) -> str:
    if ppl_per_m2 >= 2.0:
        return "dark-red"
    if ppl_per_m2 >= 1.5:
        return "red"
    if ppl_per_m2 >= 1.0:
        return "amber"
    return "green"


def _segments_from_overlaps_csv(url: str) -> List[SegmentIn]:
    df = _fetch_csv(url)
    # Expect EXACT names you’re using in your repo:
    required = [
        "seg_id", "segment_label",
        "eventA", "eventB",
        "from_km_A", "to_km_A",
        "from_km_B", "to_km_B",
        "direction", "width_m",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"overlapsCsv missing columns: {missing}")

    segs: List[SegmentIn] = []
    for _, row in df.iterrows():
        segs.append(SegmentIn(
            seg_id=str(row["seg_id"]),
            segment_label=str(row["segment_label"]),
            eventA=str(row["eventA"]),
            eventB=str(row["eventB"]),
            from_km_A=float(row["from_km_A"]),
            to_km_A=float(row["to_km_A"]),
            from_km_B=float(row["from_km_B"]),
            to_km_B=float(row["to_km_B"]),
            direction=(str(row["direction"]) if not pd.isna(row["direction"]) else "uni"),
            width_m=(float(row["width_m"]) if not pd.isna(row["width_m"]) else None),
        ))
    return segs


def _materialize_inline_segments(inline: List[SegmentIn]) -> List[SegmentIn]:
    out: List[SegmentIn] = []
    for i, s in enumerate(inline, 1):
        # For ad-hoc segments, use from/to for BOTH events unless explicitly provided
        if s.from_km_A is None and s.from_ is not None:
            s.from_km_A = s.from_
        if s.to_km_A is None and s.to is not None:
            s.to_km_A = s.to
        if s.from_km_B is None:
            s.from_km_B = s.from_km_A
        if s.to_km_B is None:
            s.to_km_B = s.to_km_A

        if s.seg_id is None:
            s.seg_id = f"adhoc-{i}"
        if s.segment_label is None:
            s.segment_label = f"{s.eventA}/{s.eventB} {s.from_km_A:.2f}-{s.to_km_A:.2f} km"

        out.append(s)
    return out


# --- core math ---

def _arrival_times_for_event(
    runners: List[Runner],
    start_min: int,
    km: float
) -> List[float]:
    """Arrival times (seconds since t0) at distance 'km' for all runners able to reach km."""
    if km is None:
        return []
    t0 = start_min * 60.0
    # only runners whose total distance covers this km
    return [t0 + r.pace_sec_per_km * km for r in runners if r.distance_km + 1e-9 >= km]


def _best_window_counts(
    timesA: List[float],
    timesB: List[float],
    window_s: float
) -> Tuple[int, int, float]:
    """
    Given two sorted arrays of times (sec), find T that maximizes
    countA(T) + countB(T) within [T - w/2, T + w/2]. Return (A, B, T_best).
    """
    if not timesA and not timesB:
        return (0, 0, 0.0)
    arrA = sorted(timesA)
    arrB = sorted(timesB)
    half = window_s / 2.0

    # Evaluate candidate centers at every arrival time from A∪B.
    candidates = arrA + arrB
    candidates.sort()

    import bisect

    bestA = bestB = 0
    bestT = 0.0

    for T in candidates:
        loA = bisect.bisect_left(arrA, T - half)
        hiA = bisect.bisect_right(arrA, T + half)
        cntA = hiA - loA

        loB = bisect.bisect_left(arrB, T - half)
        hiB = bisect.bisect_right(arrB, T + half)
        cntB = hiB - loB

        if cntA + cntB > bestA + bestB:
            bestA, bestB, bestT = cntA, cntB, T

    return (bestA, bestB, bestT)


def _compute_peak_for_segment(
    seg: SegmentIn,
    pace_index: PaceIndex,
    starts: StartTimes,
    step_km: float,
) -> Optional[PeakOut]:
    """
    Scan the segment along its physical extent (normalized 0..1) and
    find the distance that maximizes simultaneous counts within timeWindow at that location.
    """
    eventA, eventB = seg.eventA, seg.eventB
    runnersA = pace_index.get(eventA, [])
    runnersB = pace_index.get(eventB, [])

    if not runnersA and not runnersB:
        return None

    # per-event km extents
    a0, a1 = float(seg.from_km_A), float(seg.to_km_A)
    b0, b1 = float(seg.from_km_B), float(seg.to_km_B)

    # normalize along the shared physical segment by u in [0,1]
    # distance in event-space at u:
    lenA = abs(a1 - a0)
    lenB = abs(b1 - b0)
    # If a segment has zero length (bad data), bail out gracefully.
    if lenA < 1e-9 and lenB < 1e-9:
        return None

    # Choose normalized step by mapping step_km onto the longer of the two spans
    phys_len = max(lenA, lenB, step_km)
    # number of slices (at least 1)
    n = max(1, int(math.ceil(phys_len / step_km)))

    # time window is provided at the top (seconds); we pass by argument
    # areal window length (meters) uses 2*stepKm, matching prior behavior
    # (e.g., for stepKm=0.03 → 60m)
    areal_length_m = 2.0 * step_km * 1000.0
    width_m = seg.width_m if (seg.width_m and seg.width_m > 0) else (3.0 if (seg.direction or "uni").lower().startswith("uni") else 1.5)

    best_combined = -1
    best_A = best_B = 0
    best_kmA = a0

    startA = starts.get(eventA)
    startB = starts.get(eventB)

    for i in range(n + 1):
        u = i / n
        kmA = a0 + (a1 - a0) * u
        kmB = b0 + (b1 - b0) * u

        timesA = _arrival_times_for_event(runnersA, startA, kmA)
        timesB = _arrival_times_for_event(runnersB, startB, kmB)

        A, B, _T = _best_window_counts(timesA, timesB, window_s=payload_timeWindow)  # see wrapper below
        if A + B > best_combined:
            best_combined = A + B
            best_A, best_B = A, B
            best_kmA = kmA

    if best_combined <= 0:
        return None

    ppl_per_m2 = best_combined / max(1e-9, (width_m * areal_length_m))
    return PeakOut(
        km=round(best_kmA, 2),
        A=int(best_A),
        B=int(best_B),
        combined=int(best_combined),
        areal_density=round(ppl_per_m2, 2),
        zone=_zone_from_density(ppl_per_m2),
    )


# This global is set inside run_density() before we start scanning
payload_timeWindow: int = 60


# -----------------------------
# Public entrypoint used by FastAPI
# -----------------------------

def run_density(payload: DensityPayload) -> DensityResponse:
    """
    Main engine: builds the list of segments either from overlapsCsv or inline segments,
    runs peak computation, and returns SegmentOuts.
    """
    global payload_timeWindow
    payload_timeWindow = int(payload.timeWindow)

    # 1) Load pace index
    pace_index = _load_pace_index(payload.paceCsv)

    # 2) Build segments list
    segs_in: List[SegmentIn] = []
    if payload.overlapsCsv:
        segs_in.extend(_segments_from_overlaps_csv(payload.overlapsCsv))

    if payload.segments:
        segs_in.extend(_materialize_inline_segments(payload.segments))

    if not segs_in:
        # No segments provided anywhere
        return DensityResponse(segments=[])

    # 3) Compute peaks
    out: List[SegmentOut] = []
    for s in segs_in:
        # fill width default if needed (uni → 3.0; bi → 1.5)
        if not s.width_m or s.width_m <= 0:
            s.width_m = 3.0 if (s.direction or "uni").lower().startswith("uni") else 1.5

        peak = _compute_peak_for_segment(
            seg=s,
            pace_index=pace_index,
            starts=payload.startTimes,
            step_km=payload.stepKm,
        )

        out.append(SegmentOut(
            seg_id=s.seg_id,
            segment_label=s.segment_label,
            eventA=s.eventA,
            eventB=s.eventB,
            from_km_A=float(s.from_km_A),
            to_km_A=float(s.to_km_A),
            from_km_B=float(s.from_km_B),
            to_km_B=float(s.to_km_B),
            direction=s.direction,
            width_m=s.width_m,
            peak=peak
        ))

    return DensityResponse(segments=out)