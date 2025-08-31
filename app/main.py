from __future__ import annotations

import csv
import io
import os
import datetime
from fastapi import FastAPI, Query, HTTPException, Request
from starlette.responses import JSONResponse, StreamingResponse
from app.density import DensityPayload, run_density, preview_segments

try:
    from app.density import export_peaks_csv
except ImportError:  # pragma: no cover
    export_peaks_csv = None

app = FastAPI(title="run-density", version="v1.3.7-dev")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/version")
def version():
    return {
        "app": "run-density",
        "version": APP_VERSION or app.version,
        "git_sha": GIT_SHA,
        "built_at": BUILD_AT,
    }

@app.get("/ready")
def ready():
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}

@app.post("/api/density")
async def api_density(
    request: Request,  # <-- required Request (no Optional/None)
    payload: DensityPayload,
    seg_id: str | None = Query(default=None, description="Filter to a single seg_id"),
    debug: bool = Query(default=False, description="Include trace & write peaks.csv"),
):
    """
    Density API

    Body: DensityPayload
    Query:
      - seg_id      (optional)
      - debug       (optional)
      - zoneMetric  (optional, parity with /api/peaks.csv)
    """
    # accept ?zoneMetric=...
    zm = request.query_params.get("zoneMetric")
    if zm:
        payload.zoneMetric = zm

    try:
        result = run_density(payload, seg_id_filter=seg_id, debug=debug)

        if debug and export_peaks_csv is not None and result.get("segments"):
            try:
                export_peaks_csv(result["segments"])
            except Exception:
                pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/density.summary")
async def api_density_summary(payload: DensityPayload, request: Request):
    """
    Returns a compact summary per segment for the selected metric
    (areal by default, or crowd if requested).
    """
    try:
        # Allow query to override payload.zoneMetric, just like /api/density
        qm = request.query_params.get("zoneMetric")
        metric_name = (qm or getattr(payload, "zoneMetric", "areal")).strip().lower()
        if metric_name not in {"areal", "crowd"}:
            metric_name = "areal"

        seg_id = request.query_params.get("seg_id")
        result = run_density(payload, seg_id_filter=seg_id, debug=False)

        # Build compact summary: {seg_id, segment_label, value, zone, areal_density, crowd_density}
        compact = []
        for s in result.get("segments", []):
            peak = s.get("peak", {})
            value = peak.get("areal_density") if metric_name == "areal" else peak.get("crowd_density")
            compact.append({
                "seg_id": s.get("seg_id"),
                "segment_label": s.get("segment_label"),   # NEW
                "value": round(value, 2) if value is not None else None,
                "zone": peak.get("zone"),
                "areal_density": round(peak.get("areal_density"), 2) if peak.get("areal_density") is not None else None,
                "crowd_density": round(peak.get("crowd_density"), 2) if peak.get("crowd_density") is not None else None,
            })

        return {
            "engine": "density",
            "zone_by": metric_name,   # "areal" | "crowd"
            "segments": compact
        }
    except HTTPException:
        # Propagate 4xx (e.g., 422 validation) untouched
        raise
    except Exception as e:
        # Match /api/density behavior on unexpected errors
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/segments")
def api_segments(payload: DensityPayload):
    try:
        return {"segments": preview_segments(payload)}
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/segments.csv")
def api_segments_csv(payload: DensityPayload):
    try:
        rows = preview_segments(payload)

        buf = io.StringIO()
        fieldnames = [
            "seg_id",
            "segment_label",
            "direction",
            "width_m",
            "eventA",
            "from_km_A",
            "to_km_A",
            "eventB",
            "from_km_B",
            "to_km_B",
            "length_km",
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

        return StreamingResponse(io.StringIO(buf.getvalue()), media_type="text/csv")
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/peaks.csv")
async def peaks_csv(request: Request):
    """
    Returns a CSV of segment peaks. Adds two comment lines at the top:
    # zone_by: areal|crowd
    # zone_cuts: [7.5, 15.0, 30.0, 50.0]  (or custom crowd cuts if zoneMetric=crowd)
    """
    try:
        payload = DensityPayload(**(await request.json()))
    except Exception:
        # Fallback: read body manually (Starlette Request in sync route)
        import json
        body = request.body()
        try:
            payload = DensityPayload(**json.loads(body.decode('utf-8')))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid JSON body: {e}")

    # Allow query override for zoneMetric (matches how /api/density works)
    q = request.query_params
    zone_override = q.get("zoneMetric")
    if zone_override:
        payload.zoneMetric = zone_override

    result = run_density(payload, seg_id_filter=q.get("seg_id"), debug=False)
    segs = result.get("segments", [])

    # Figure out which metric is active and which cuts to print
    metric_name = (payload.zoneMetric or "areal").strip().lower()
    if metric_name == "crowd":
        cuts = (payload.zones.crowd if (payload.zones and payload.zones.crowd) else None) or [1.0, 2.0, 4.0, 8.0]
    else:
        cuts = (payload.zones.areal if (payload.zones and payload.zones.areal) else None) or [7.5, 15.0, 30.0, 50.0]

    # Build CSV in-memory
    buf = io.StringIO()
    buf.write(f"# zone_by: {metric_name}\n")
    buf.write(f"# zone_cuts: {cuts}\n")

    # Columns: keep your existing export shape (audit-safe)
    fieldnames = [
        "seg_id", "segment_label", "direction", "width_m",
        "eventA", "from_km_A", "to_km_A",
        "eventB", "from_km_B", "to_km_B",
        "length_km",
        "peak_km", "peak_A", "peak_B", "peak_combined",
        "areal_density", "crowd_density", "zone"
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    for s in segs:
        peak = s.get("peak", {}) or {}
        row = {
            "seg_id": s.get("seg_id"),
            "segment_label": s.get("segment_label"),
            "direction": s.get("direction"),
            "width_m": s.get("width_m"),
            "eventA": s.get("eventA") or "",
            "from_km_A": s.get("from_km_A") if s.get("from_km_A") is not None else "",
            "to_km_A": s.get("to_km_A") if s.get("to_km_A") is not None else "",
            "eventB": s.get("eventB") or "",
            "from_km_B": s.get("from_km_B") if s.get("from_km_B") is not None else "",
            "to_km_B": s.get("to_km_B") if s.get("to_km_B") is not None else "",
            "length_km": s.get("length_km") if s.get("length_km") is not None else "",
            "peak_km": peak.get("km"),
            "peak_A": peak.get("A"),
            "peak_B": peak.get("B"),
            "peak_combined": peak.get("combined"),
            "areal_density": round(peak.get("areal_density"), 2) if peak.get("areal_density") is not None else None,
            "crowd_density": round(peak.get("crowd_density"), 2) if peak.get("crowd_density") is not None else None,
            "zone": peak.get("zone"),
        }
        writer.writerow(row)

    buf.seek(0)
    try:
        csv_content = buf.getvalue().encode("utf-8")
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="peaks.csv"'},
        )
    except UnicodeEncodeError as e:
        raise HTTPException(status_code=500, detail=f"CSV encoding error: {e}")
