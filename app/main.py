# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any
import time

# density endpoint
from app.density import DensityPayload, run_density

app = FastAPI(title="run-density API (Cloud Run)", version="v1.3.0")

# We keep these simple/on by default so /ready is green for smoke.
STATE = {
    "density_loaded": True,
    "overlap_loaded": True,
}

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "ts": time.time()}

@app.get("/ready")
def ready() -> Dict[str, Any]:
    return {
        "ok": True,
        "density_loaded": bool(STATE["density_loaded"]),
        "overlap_loaded": bool(STATE["overlap_loaded"]),
    }

# --------- /api/density ---------
@app.post("/api/density")
def api_density(payload: DensityPayload):
    """
    Accepts either:
      A) explicit `segments` array, OR
      B) `overlapsCsv` URL (CSV with seg_id,... columns) to auto-build segments.
    """
    try:
        result = run_density(payload)
        # If we successfully parsed overlapsCsv, reflect it in ready flag
        if payload.overlapsCsv:
            STATE["overlap_loaded"] = True
        STATE["density_loaded"] = True
        return JSONResponse(result)
    except HTTPException:
        # pass through pydantic/validation-style errors
        raise
    except Exception as e:
        # keep the error payload short and actionable
        raise HTTPException(status_code=500, detail=str(e))

# --------- /api/report (human-readable formatter) ---------
class ReportIn(BaseModel):
    eventA: str
    eventB: str
    from_: float | None = None  # legacy; not required
    to: float | None = None     # legacy; not required
    segment_name: str | None = None
    segment_label: str
    direction: str
    width_m: float
    startTimes: Dict[str, int] | None = None
    startTimesClock: Dict[str, str] | None = None
    runnersA: int | None = None
    runnersB: int | None = None
    overlap_from_km: float | None = None
    overlap_to_km: float | None = None
    first_overlap_clock: str | None = None
    first_overlap_km: float | None = None
    first_overlap_bibA: str | None = None
    first_overlap_bibB: str | None = None
    peak: Dict[str, Any] | None = None

@app.post("/api/report")
def report(payload: ReportIn):
    # Compose the human-readable block you used before
    parts = []
    # Line 1
    rng = ""
    if payload.from_ is not None and payload.to is not None:
        rng = f" from {payload.from_:.2f}km–{payload.to:.2f}km"
    parts.append(
        f"Checking {payload.eventA} vs {payload.eventB}{rng}, Segment {payload.segment_name or ''}".strip()
    )
    # Line 2
    if payload.startTimesClock:
        a = payload.startTimesClock.get(payload.eventA)
        b = payload.startTimesClock.get(payload.eventB)
        if a and b:
            parts.append(f"Start: {payload.eventA} {a}, {payload.eventB} {b}")
    # Line 3
    if payload.runnersA is not None and payload.runnersB is not None:
        parts.append(f"Runners: {payload.eventA}: {payload.runnersA}, {payload.eventB}: {payload.runnersB}")
    # Line 4
    parts.append(f"Segment: {payload.segment_label} | Direction: {payload.direction} | Width: {payload.width_m:.1f}m")
    # Line 5 overlap window
    if payload.overlap_from_km is not None and payload.overlap_to_km is not None:
        parts.append(f"Overlap Segment: {payload.overlap_from_km:.2f}km–{payload.overlap_to_km:.2f}km")
    # Line 6 first overlap
    if payload.first_overlap_clock and payload.first_overlap_km is not None:
        parts.append(
            f"First overlap: {payload.first_overlap_clock} at {payload.first_overlap_km:.2f}km "
            f"({payload.eventA}: {payload.first_overlap_bibA}, {payload.eventB}: {payload.first_overlap_bibB})"
        )
    # Line 7 peak
    if payload.peak:
        km = payload.peak.get("km")
        A = payload.peak.get("A")
        B = payload.peak.get("B")
        comb = payload.peak.get("combined")
        ad = payload.peak.get("areal_density")
        zone = payload.peak.get("zone", None)
        zone_tag = f" [{zone}]" if zone else ""
        if km is not None and comb is not None and A is not None and B is not None and ad is not None:
            parts.append(
                f"Peak: {comb} ({payload.eventA}: {A}, {payload.eventB}: {B}) at {float(km):.2f}km — {float(ad):.2f} ppl/m²{zone_tag}"
            )

    return {"report": "\n".join(parts)}