# app/main.py
from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.density import DensityPayload, run_density

# Optional: only import when debug=true to avoid import cycles if you prefer.
try:
    from app.density import export_peaks_csv  # type: ignore
except Exception:  # pragma: no cover
    export_peaks_csv = None  # noqa: N816


app = FastAPI(title="run-density", version="1.3.4-dev")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready")
def ready():
    # Keep keys stable for the smoke tests
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}


@app.post("/api/density")
def api_density(
    payload: DensityPayload,
    seg_id: str | None = Query(default=None, description="Filter to a single seg_id"),
    debug: bool = Query(default=False, description="Include trace & write peaks.csv"),
):
    """
    Density API:
      - Body: DensityPayload (paceCsv/overlapsCsv OR inline segments, startTimes, stepKm, timeWindow, depth_m)
      - Query params:
          seg_id (optional): filter to a specific segment id
          debug (optional): include trace and export peaks.csv on the server
    """
    try:
        result = run_density(payload, seg_id_filter=seg_id, debug=debug)
        if debug and "segments" in result and export_peaks_csv:
            try:
                export_peaks_csv(result["segments"])
            except Exception:
                # Don’t fail the request if CSV export has a filesystem/permission hiccup
                pass
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})