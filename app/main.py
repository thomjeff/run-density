from __future__ import annotations

import csv
import io
import os
import datetime
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, StreamingResponse, HTMLResponse
from app.density import DensityPayload, run_density, preview_segments

try:
    from app.density import export_peaks_csv
except ImportError:  # pragma: no cover
    export_peaks_csv = None

app = FastAPI(title="run-density", version="v1.3.7-dev")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Templates setup
templates = Jinja2Templates(directory="app/templates")

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


@app.get("/api/map")
async def api_map(request: Request):
    """
    Serves an interactive map showing segment density zones.
    Users can toggle between areal and crowd metrics.
    """
    return templates.TemplateResponse("map.html", {"request": request})


@app.get("/map")
async def map_page(request: Request):
    """
    Convenience route for the map page.
    """
    return templates.TemplateResponse("map.html", {"request": request})


@app.get("/api/segments.geojson")
async def api_segments_geojson():
    """
    Returns GeoJSON representation of all segments using real GPX coordinates.
    """
    try:
        from app.gpx_processor import (
            load_all_courses, 
            generate_segment_coordinates, 
            create_geojson_from_segments
        )
        
        # Load GPX courses
        courses = load_all_courses()
        if not courses:
            raise HTTPException(status_code=500, detail="No GPX courses loaded")
        
        # Define segments based on overlaps.csv
        segments = [
            {"seg_id": "A1a", "from_km": 0.0, "to_km": 0.9, "label": "Start to Queen/Regent", "event": "10K"},
            {"seg_id": "A1b", "from_km": 0.9, "to_km": 1.8, "label": "Queen/Regent to WSB mid-point", "event": "10K"},
            {"seg_id": "A1c", "from_km": 1.8, "to_km": 2.7, "label": "WSB mid-point to Friel", "event": "10K"},
            {"seg_id": "A2a", "from_km": 0.0, "to_km": 0.9, "label": "Start to Queen/Regent", "event": "10K"},
            {"seg_id": "A2b", "from_km": 0.9, "to_km": 1.8, "label": "Queen/Regent to WSB mid-point", "event": "10K"},
            {"seg_id": "A2c", "from_km": 1.8, "to_km": 2.7, "label": "WSB mid-point to Friel", "event": "10K"},
            {"seg_id": "A3a", "from_km": 0.0, "to_km": 0.9, "label": "Start to Queen/Regent", "event": "Half"},
            {"seg_id": "A3b", "from_km": 0.9, "to_km": 1.8, "label": "Queen/Regent to WSB mid-point", "event": "Half"},
            {"seg_id": "A3c", "from_km": 1.8, "to_km": 2.7, "label": "WSB mid-point to Friel", "event": "Half"},
            {"seg_id": "B1", "from_km": 2.7, "to_km": 4.25, "label": "Friel to 10K Turn (outbound)", "event": "10K"},
            {"seg_id": "B2", "from_km": 2.7, "to_km": 4.25, "label": "Friel to 10K Turn (out vs return)", "event": "10K"},
            {"seg_id": "C1", "from_km": 4.25, "to_km": 5.81, "label": "10K Turn to Friel (return) vs Full (early)", "event": "10K"},
            {"seg_id": "C2", "from_km": 4.25, "to_km": 5.81, "label": "10K Turn to Friel (return) vs Full (late)", "event": "10K"},
            {"seg_id": "D1", "from_km": 2.7, "to_km": 4.25, "label": "Friel to 10K Turn (Full only)", "event": "Full"},
            {"seg_id": "D2", "from_km": 4.25, "to_km": 14.8, "label": "10K Turn to 14.8km (Full only)", "event": "Full"},
            {"seg_id": "E1", "from_km": 2.7, "to_km": 4.25, "label": "Friel to 10K Turn (late overlaps)", "event": "Full"},
            {"seg_id": "F1", "from_km": 5.81, "to_km": 8.1, "label": "Friel to 10K Return (continuing)", "event": "10K"},
            {"seg_id": "F2", "from_km": 5.81, "to_km": 8.1, "label": "Friel to Station/Barker (shared path)", "event": "10K"},
            {"seg_id": "F3", "from_km": 5.81, "to_km": 8.1, "label": "Friel to Station/Barker (shared path)", "event": "10K"},
            {"seg_id": "F4", "from_km": 2.7, "to_km": 4.95, "label": "Friel to Station/Barker", "event": "Half"},
            {"seg_id": "G1", "from_km": 8.1, "to_km": 10.0, "label": "Station/Barker to Queen Square (10K to Finish)", "event": "10K"},
            {"seg_id": "G2", "from_km": 19.35, "to_km": 21.1, "label": "Station/Barker to Queen Square (Half to Finish)", "event": "Half"},
            {"seg_id": "G3", "from_km": 18.59, "to_km": 20.54, "label": "Station/Barker to Queen Square (Full loop inbound)", "event": "Full"},
            {"seg_id": "G4", "from_km": 40.5, "to_km": 42.2, "label": "Station/Barker to Queen Square (Full final finish)", "event": "Full"},
            {"seg_id": "G5", "from_km": 8.1, "to_km": 10.0, "label": "Station/Barker to Queen Square (10K & Half finishes)", "event": "10K"},
            {"seg_id": "G6", "from_km": 8.1, "to_km": 10.0, "label": "Station/Barker to Queen Square (10K & Full final finish)", "event": "10K"},
            {"seg_id": "G7", "from_km": 19.35, "to_km": 21.1, "label": "Station/Barker to Queen Square (Half & Full final finish)", "event": "Half"},
            {"seg_id": "G8", "from_km": 19.35, "to_km": 21.1, "label": "Station/Barker to Queen Square (Half finish & Full loop inbound)", "event": "Half"},
            {"seg_id": "G9", "from_km": 8.1, "to_km": 10.0, "label": "Station/Barker to Queen Square (10K finish & Full loop inbound)", "event": "10K"},
            {"seg_id": "H1", "from_km": 20.54, "to_km": 21.65, "label": "Queen Square Loop (Full only)", "event": "Full"},
            {"seg_id": "H2", "from_km": 21.65, "to_km": 23.26, "label": "Queen Square to Station/Barker (Full returning vs 10K finish)", "event": "Full"},
            {"seg_id": "H3", "from_km": 21.65, "to_km": 23.26, "label": "Queen Square to Station/Barker (Full returning vs Half finish)", "event": "Full"},
            {"seg_id": "I1", "from_km": 4.95, "to_km": 10.84, "label": "Station/Barker to Bridge/Mill (Half outbound)", "event": "Half"},
            {"seg_id": "I2", "from_km": 23.26, "to_km": 29.06, "label": "Station/Barker to Bridge/Mill (Full outbound)", "event": "Full"},
            {"seg_id": "I3", "from_km": 4.95, "to_km": 10.84, "label": "Station/Barker to Bridge/Mill (Half + Full co-direction)", "event": "Half"},
            {"seg_id": "J1", "from_km": 10.84, "to_km": 13.43, "label": "Bridge/Mill to Half Turn (Half outbound)", "event": "Half"},
            {"seg_id": "J2", "from_km": 29.06, "to_km": 31.64, "label": "Bridge/Mill to Half Turn (Full outbound)", "event": "Full"},
            {"seg_id": "J3", "from_km": 10.84, "to_km": 13.43, "label": "Bridge/Mill to Half Turn (Half + Full co-direction)", "event": "Half"},
            {"seg_id": "K1", "from_km": 31.64, "to_km": 33.11, "label": "Half Turn to Full Turn (Full outbound spur)", "event": "Full"},
            {"seg_id": "K2", "from_km": 33.11, "to_km": 34.34, "label": "Full Turn to Half Turn (Full returning spur)", "event": "Full"},
            {"seg_id": "L1", "from_km": 13.43, "to_km": 16.02, "label": "Half Turn to Bridge/Mill (Half returning)", "event": "Half"},
            {"seg_id": "L2", "from_km": 34.34, "to_km": 35.47, "label": "Half Turn to Bridge/Mill (Full returning)", "event": "Full"},
            {"seg_id": "L3", "from_km": 13.43, "to_km": 16.02, "label": "Half Turn to Bridge/Mill (Half + Full co-direction return)", "event": "Half"},
            {"seg_id": "L4", "from_km": 34.34, "to_km": 36.92, "label": "Bridge/Mill sector counter-flow (optional)", "event": "Full"},
            {"seg_id": "M1", "from_km": 36.92, "to_km": 40.5, "label": "Bridge/Mill to Station/Barker (Full returning vs Half outbound)", "event": "Full"},
            {"seg_id": "M2", "from_km": 36.92, "to_km": 40.5, "label": "Bridge/Mill to Station/Barker (Full returning vs Full outbound)", "event": "Full"},
        ]
        
        # Generate real coordinates from GPX data
        segments_with_coords = generate_segment_coordinates(courses, segments)
        
        # Convert to GeoJSON
        geojson = create_geojson_from_segments(segments_with_coords)
        
        return geojson
        
    except Exception as e:
        # Fallback to estimated coordinates if GPX processing fails
        print(f"GPX processing failed: {e}")
        return {
            "type": "FeatureCollection",
            "features": [],
            "error": f"GPX processing failed: {str(e)}"
        }
