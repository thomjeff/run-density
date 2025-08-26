# app/density.py
# FastAPI handler for density endpoint with overlapsCsv ingestion & header normalization.
from __future__ import annotations

import csv
import io
import math
from typing import Dict, List, Optional

import requests
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

# ---------- Pydantic models ----------

class SegmentSpec(BaseModel):
    # Accept both `seg_id` and `segment_id` via preprocess; we store in `seg_id`
    seg_id: str
    segment_label: str
    pair: str  # e.g. "10K+Half"
    eventA: str
    eventB: str
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    direction: str  # "uni" | "bi"
    width_m: float

class DensityRequest(BaseModel):
    paceCsv: HttpUrl
    overlapsCsv: Optional[HttpUrl] = None
    # Now optional: if omitted, we will load from overlapsCsv
    segments: Optional[List[SegmentSpec]] = None
    startTimes: Dict[str, int]  # e.g. {"Full":420,"10K":440,"Half":460} (minutes offset from 07:00 or race zerotime)
    stepKm: float = 0.03
    timeWindow: int = 60  # seconds

class PeakOut(BaseModel):
    km: float
    A: int
    B: int
    combined: int
    areal_density: float
    zone: str

class SegmentOut(BaseModel):
    seg_id: str
    segment_label: str
    pair: str
    eventA: str
    eventB: str
    direction: str
    width_m: float
    # For convenience in CLI/UI:
    from_km: float
    to_km: float
    # Raw per-event spans preserved too:
    from_km_A: float
    to_km_A: float
    from_km_B: float
    to_km_B: float
    # Computed results:
    peak: PeakOut

class DensityResponse(BaseModel):
    engine: str = "density"
    segments: List[SegmentOut]

# ---------- CSV normalization ----------

def _normalize_overlaps_csv(url: str) -> List[SegmentSpec]:
    """
    Load overlaps CSV and accept either `segment_id` or `seg_id`.
    Expected columns (either spelling for seg id is OK):
      segment_id|seg_id, segment_label, eventA, eventB,
      from_km_A, to_km_A, from_km_B, to_km_B,
      direction, width_m
    Extra columns (e.g., notes) are ignored.
    """
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch overlapsCsv: {e}")

    reader = csv.DictReader(io.StringIO(r.text))
    out: List[SegmentSpec] = []

    for raw in reader:
        seg_id = (raw.get("seg_id") or raw.get("segment_id") or "").strip()
        if not seg_id:
            # skip malformed lines
            continue

        segment_label = (raw.get("segment_label") or seg_id).strip()
        eventA = (raw.get("eventA") or "").strip()
        eventB = (raw.get("eventB") or "").strip()

        # Required floats
        def ffloat(key: str) -> float:
            v = raw.get(key)
            if v is None or str(v).strip() == "":
                raise ValueError(f"Missing {key}")
            return float(str(v).strip())

        try:
            from_km_A = ffloat("from_km_A")
            to_km_A   = ffloat("to_km_A")
            from_km_B = ffloat("from_km_B")
            to_km_B   = ffloat("to_km_B")
            direction = (raw.get("direction") or "").strip().lower()  # uni|bi
            width_m   = float(str(raw.get("width_m") or "0").strip())
        except Exception:
            # skip poorly-typed rows
            continue

        # A consistent "pair" string for outputs
        pair = f"{eventA}+{eventB}"

        out.append(
            SegmentSpec(
                seg_id=seg_id,
                segment_label=segment_label,
                pair=pair,
                eventA=eventA,
                eventB=eventB,
                from_km_A=from_km_A,
                to_km_A=to_km_A,
                from_km_B=from_km_B,
                to_km_B=to_km_B,
                direction=direction,
                width_m=width_m,
            )
        )

    if not out:
        raise HTTPException(
            status_code=422,
            detail="No valid rows parsed from overlapsCsv (check headers/values).",
        )
    return out

# ---------- Pace loading (unchanged; available for engine math) ----------

class Runner(BaseModel):
    event: str
    runner_id: str
    pace_min_per_km: float
    distance_km: float

def _load_pace_csv(url: str) -> List[Runner]:
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch paceCsv: {e}")

    reader = csv.DictReader(io.StringIO(r.text))
    out: List[Runner] = []
    for raw in reader:
        try:
            out.append(
                Runner(
                    event=(raw.get("event") or "").strip(),
                    runner_id=(raw.get("runner_id") or "").strip(),
                    pace_min_per_km=float(str(raw.get("pace") or "0").strip()),
                    distance_km=float(str(raw.get("distance") or "0").strip()),
                )
            )
        except Exception:
            # ignore bad rows
            continue
    if not out:
        raise HTTPException(status_code=422, detail="paceCsv contained no valid rows.")
    return out

# ---------- “Engine” placeholder / skeleton ----------

def _zone_from_density(areal: float) -> str:
    # Keep your threshold defaults
    if areal < 1.0:
        return "green"
    if areal < 1.5:
        return "amber"
    if areal < 2.0:
        return "red"
    return "dark-red"

def _compute_segment_peak_stub(seg: SegmentSpec) -> PeakOut:
    """
    Placeholder: returns neutral values but valid shape.
    Wire your real time-window density math back in here.
    """
    # Use the A span as representative for a single from/to in the outward payload
    km_mid = (seg.from_km_A + seg.to_km_A) / 2.0
    areal = 0.0  # TODO: compute real areal density (runners/m^2)
    return PeakOut(
        km=round(km_mid, 2),
        A=0,
        B=0,
        combined=0,
        areal_density=areal,
        zone=_zone_from_density(areal),
    )

# ---------- FastAPI wiring ----------

router = APIRouter()

@router.get("/health")
def health():
    return {"ok": True, "ts": __import__("time").time()}

@router.get("/ready")
def ready():
    # we don't pre-load here to keep it fast; simply report handler is live
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}

@router.post("/api/density", response_model=DensityResponse)
def density(req: DensityRequest):
    # resolve segments
    if req.segments is not None:
        segments_in = req.segments
    else:
        if not req.overlapsCsv:
            raise HTTPException(
                status_code=422,
                detail="Either segments[] or overlapsCsv must be provided."
            )
        segments_in = _normalize_overlaps_csv(str(req.overlapsCsv))

    # load pace (even if the stub doesn’t use it; ensures inputs are valid)
    _ = _load_pace_csv(str(req.paceCsv))

    # Produce outputs
    outputs: List[SegmentOut] = []
    for seg in segments_in:
        peak = _compute_segment_peak_stub(seg)
        outputs.append(
            SegmentOut(
                seg_id=seg.seg_id,
                segment_label=seg.segment_label,
                pair=seg.pair,
                eventA=seg.eventA,
                eventB=seg.eventB,
                direction=seg.direction,
                width_m=seg.width_m,
                from_km=seg.from_km_A,  # outward single span; clients can also read _A/_B
                to_km=seg.to_km_A,
                from_km_A=seg.from_km_A,
                to_km_A=seg.to_km_A,
                from_km_B=seg.from_km_B,
                to_km_B=seg.to_km_B,
                peak=peak,
            )
        )

    return DensityResponse(engine="density", segments=outputs)

# Create the app instance if this file is mounted directly by the ASGI server
app = FastAPI()
app.include_router(router)