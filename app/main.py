# app/main.py
from __future__ import annotations
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.responses import JSONResponse, PlainTextResponse
from app.density import DensityPayload, run_density
import io, csv

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

@app.post("/api/segments")
def api_segments(payload: DensityPayload):
    try:
        from app.density import preview_segments
        return {"segments": preview_segments(payload)}
    except HTTPException as he:
        # propagate 422s from validators
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/segments.csv")
def api_segments_csv(payload: DensityPayload):
    try:
        from app.density import preview_segments
        rows = preview_segments(payload)
        # build CSV
        import csv, io
        buf = io.StringIO()
        fieldnames = [
            "seg_id","segment_label","direction","width_m",
            "eventA","from_km_A","to_km_A",
            "eventB","from_km_B","to_km_B",
            "length_km",
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        return PlainTextResponse(buf.getvalue(), media_type="text/csv")
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/peaks.csv")
def api_peaks_csv(payload: DensityPayload, request: Request):
    """
    Compute density then stream a CSV with per-segment peaks.
    Columns: seg_id,segment_label,direction,width_m,first_clock,first_km,
             peak_km,A,B,combined,areal_density,crowd_density,zone
    """
    # Optional query overrides
    seg_id = request.query_params.get("seg_id")
    zone_metric_qp = request.query_params.get("zoneMetric")
    if zone_metric_qp:
        payload.zoneMetric = zone_metric_qp  # override if present

    # Compute
    result = run_density(payload, seg_id_filter=seg_id, debug=False)
    segments = result.get("segments", [])

    # Build CSV in-memory
    import io, csv
    buf = io.StringIO()
    fieldnames = [
        "seg_id", "segment_label", "direction", "width_m",
        "first_clock", "first_km",
        "peak_km", "A", "B", "combined",
        "areal_density", "crowd_density", "zone",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    for seg in segments:
        peak = seg.get("peak", {}) or {}
        first = seg.get("first_overlap") or {"clock": None, "km": None}
        writer.writerow({
            "seg_id": seg.get("seg_id"),
            "segment_label": seg.get("segment_label"),
            "direction": seg.get("direction"),
            "width_m": seg.get("width_m"),
            "first_clock": first.get("clock"),
            "first_km": first.get("km"),
            "peak_km": peak.get("km"),
            "A": peak.get("A"),
            "B": peak.get("B"),
            "combined": peak.get("combined"),
            "areal_density": peak.get("areal_density"),
            "crowd_density": peak.get("crowd_density"),
            "zone": peak.get("zone"),
        })

    # Stream it back
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv") 