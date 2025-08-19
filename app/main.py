import time
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Lazy import: plug in your real engines here
try:
    from . import density as density_mod
except Exception:
    density_mod = None

try:
    from . import overlap as overlap_mod
except Exception:
    overlap_mod = None

app = FastAPI(title="run-congestion API (Cloud Run)", version="2025-08-19")

class SegmentObj(BaseModel):
    eventA: str
    eventB: Optional[str] = None
    from_: float = Field(..., alias="from")
    to: float
    width: float = 3.0
    direction: str = "uni"

class DensityPayload(BaseModel):
    paceCsv: str
    startTimes: Dict[str, float]
    # Accept either inline string "10K,Half,0.00,2.74,3.0,uni" or object form
    segments: List[Union[str, SegmentObj]]
    stepKm: float = 0.03
    timeWindow: float = 60.0

class OverlapPayload(BaseModel):
    paceCsv: str
    overlapsCsv: Optional[str] = None
    startTimes: Dict[str, float]
    stepKm: float = 0.03
    timeWindow: float = 60.0
    eventA: str
    eventB: Optional[str] = None
    from_: float = Field(..., alias="from")
    to: float

@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "run-congestion",
        "endpoints": ["/health", "/ready", "/api/density", "/api/overlap"],
    }

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "ts": time.time()}

@app.get("/ready")
def ready() -> Dict[str, Any]:
    return {
        "ok": True,
        "density_loaded": bool(density_mod and hasattr(density_mod, "run_density")),
        "overlap_loaded": bool(overlap_mod and hasattr(overlap_mod, "analyze_overlaps")),
    }

def _resp_with_timing(data: Any, t0: float, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    elapsed = time.perf_counter() - t0
    hdrs = dict(headers or {})
    hdrs["X-Compute-Seconds"] = f"{elapsed:.2f}"
    return JSONResponse(content=data, headers=hdrs)

def _parse_segments(segments: List[Union[str, dict, SegmentObj]]) -> List[dict]:
    parsed: List[dict] = []
    for s in segments:
        if isinstance(s, str):
            parts = [p.strip() for p in s.split(",")]
            if len(parts) != 6:
                raise HTTPException(status_code=400, detail=f"Bad segment string: {s}")
            eventA, eventB, from_km, to_km, width_m, direction = parts
            eventB = eventB or None
            parsed.append({
                "eventA": eventA,
                "eventB": eventB,
                "from": float(from_km),
                "to": float(to_km),
                "width": float(width_m),
                "direction": direction,
            })
        elif isinstance(s, SegmentObj):
            parsed.append({
                "eventA": s.eventA,
                "eventB": s.eventB,
                "from": s.from_,
                "to": s.to,
                "width": s.width,
                "direction": s.direction,
            })
        elif isinstance(s, dict):
            # tolerate dicts from clients not using pydantic on their side
            seg = SegmentObj(**s)
            parsed.append({
                "eventA": seg.eventA,
                "eventB": seg.eventB,
                "from": seg.from_,
                "to": seg.to,
                "width": seg.width,
                "direction": seg.direction,
            })
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported segment entry: {type(s)}")
    return parsed

@app.post("/api/density")
def api_density(payload: DensityPayload, request: Request) -> JSONResponse:
    t0 = time.perf_counter()
    if density_mod is None or not hasattr(density_mod, "run_density"):
        raise HTTPException(status_code=500, detail="density.run_density() missing. Put your implementation in app/density.py")
    try:
        segs = _parse_segments(payload.segments)
        out = density_mod.run_density(
            pace_csv=payload.paceCsv,
            start_times=payload.startTimes,
            segments=segs,
            step_km=payload.stepKm,
            time_window_s=payload.timeWindow,
        )
        return _resp_with_timing(out, t0)
    except HTTPException:
        raise
    except Exception as e:
        return _resp_with_timing({"error": str(e)}, t0, headers={"X-Error": "1"})

@app.post("/api/overlap")
def api_overlap(payload: OverlapPayload, request: Request) -> JSONResponse:
    t0 = time.perf_counter()
    if overlap_mod is None or not hasattr(overlap_mod, "analyze_overlaps"):
        raise HTTPException(status_code=500, detail="overlap.analyze_overlaps() missing. Put your implementation in app/overlap.py")
    try:
        out = overlap_mod.analyze_overlaps(
            pace_csv=payload.paceCsv,
            overlaps_csv=payload.overlapsCsv,
            start_times=payload.startTimes,
            step_km=payload.stepKm,
            time_window_s=payload.timeWindow,
            eventA=payload.eventA,
            eventB=payload.eventB,
            from_km=payload.from_,
            to_km=payload.to,
        )
        return _resp_with_timing(out, t0)
    except HTTPException:
        raise
    except Exception as e:
        return _resp_with_timing({"error": str(e)}, t0, headers={"X-Error": "1"})
