from __future__ import annotations

import csv
import io
import os
import datetime
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import Response

from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, StreamingResponse, HTMLResponse
from app.density import DensityPayload, run_density, preview_segments
from app.overlap import generate_overlap_narrative, generate_overlap_trace
import pandas as pd

try:
    from app.density import export_peaks_csv
except ImportError:  # pragma: no cover
    export_peaks_csv = None

app = FastAPI(title="run-density", version="v1.3.9-dev")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Static files setup for frontend
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount static files from frontend directory (with error handling)
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
except Exception as e:
    print(f"Warning: Could not mount frontend directory: {e}")
    print("Frontend static files will not be available")

def _load_csv_smart(path_or_url: str) -> pd.DataFrame:
    """Load CSV from either a local file path or a URL."""
    try:
        # Check if it's a URL (starts with http:// or https://)
        if path_or_url.startswith(('http://', 'https://')):
            import requests
            r = requests.get(path_or_url, timeout=15)
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text))
        else:
            # Local file path
            return pd.read_csv(path_or_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load CSV: {path_or_url} ({e})")

def load_segments_from_overlaps_csv(overlaps_csv_path: str) -> list:
    """
    Load segments from overlaps.csv file.
    Returns a list of segment dictionaries compatible with the map endpoint.
    """
    try:
        df = _load_csv_smart(overlaps_csv_path)
        segments = []
        
        for _, row in df.iterrows():
            # Create segment dict with required fields for map endpoint
            segment = {
                "seg_id": row["seg_id"],
                "from_km": row["from_km_A"],  # Use from_km_A as the primary from_km
                "to_km": row["to_km_A"],      # Use to_km_A as the primary to_km
                "label": row.get("segment_label", f"{row['eventA']} vs {row['eventB']}"),
                "event": row["eventA"],  # Primary event for display
                # Additional fields from overlaps.csv
                "eventA": row["eventA"],
                "eventB": row["eventB"],
                "from_km_A": row["from_km_A"],
                "to_km_A": row["to_km_A"],
                "from_km_B": row["from_km_B"],
                "to_km_B": row["to_km_B"],
                "direction": row.get("direction", "uni"),
                "width_m": row.get("width_m", 3.0)
            }
            segments.append(segment)
        
        return segments
    except Exception as e:
        print(f"Error loading segments from {overlaps_csv_path}: {e}")
        # Fallback to hardcoded segments if CSV loading fails
        return [
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
async def api_map():
    """
    API endpoint for map data (deprecated - use /frontend/pages/map.html directly)
    """
    return {"message": "Use /frontend/pages/map.html for the interactive map"}


@app.get("/map")
async def map_page():
    """
    Serves the interactive map page from the new frontend structure.
    """
    try:
        return FileResponse("frontend/pages/map.html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Map page not found. Frontend files may not be available.")


@app.get("/")
async def index_page():
    """
    Serves the main landing page from the new frontend structure.
    """
    try:
        return FileResponse("frontend/pages/index.html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Index page not found. Frontend files may not be available.")


@app.get("/density")
async def density_page():
    """
    Serves the density analysis form page from the new frontend structure.
    """
    try:
        return FileResponse("frontend/pages/density-form.html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Density form page not found. Frontend files may not be available.")


@app.get("/overlap")
async def overlap_page():
    """
    Serves the overlap analysis form page from the new frontend structure.
    """
    try:
        return FileResponse("frontend/pages/overlap-form.html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Overlap form page not found. Frontend files may not be available.")


@app.get("/api/segments.geojson")
async def api_segments_geojson():
    """
    Returns GeoJSON representation of all segments using real GPX coordinates.
    Now dynamically loads segments from overlaps.csv instead of hardcoded list.
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
        
        # Load segments dynamically from overlaps.csv
        overlaps_csv_path = "data/overlaps.csv"
        segments = load_segments_from_overlaps_csv(overlaps_csv_path)
        
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


@app.post("/api/overlap.narrative")
async def api_overlap_narrative(
    request: Request,
    payload: DensityPayload,
    seg_id: str | None = Query(default=None, description="Filter to a single seg_id"),
    sample_bibs: int = Query(default=5, ge=0, le=20, description="Number of bibs to include per side at first overlap"),
    include_trace: bool = Query(default=False, description="Include bounded trace array for debugging"),
    zoneMetric: str = Query(default="areal", description="Zone coloring metric: areal or crowd"),
    as_format: str = Query(default="json", alias="as", description="Response format: json or tsv")
):
    """
    Overlap Narrative API
    
    Returns per-segment narrative including:
    - Totals per event on the segment
    - First overlap snapshot (time, km, counts, sample bibs, densities)
    - Peak counts and zones
    - Optional bounded trace for debugging
    
    Query parameters:
    - seg_id: Filter to single segment
    - sample_bibs: Number of bibs to include (0-20, default 5)
    - include_trace: Include trace data (default false)
    - zoneMetric: Zone coloring (areal or crowd, default areal)
    - as: Response format (json or tsv, default json)
    """
    try:
        # Override payload zoneMetric if specified in query
        if zoneMetric:
            payload.zoneMetric = zoneMetric
            
        # Always enable debug for trace access (needed for first overlap search)
        result = run_density(payload, seg_id_filter=seg_id, debug=True)
        
        # Build narrative response
        narrative_segments = []
        for segment in result.get("segments", []):
            narrative_seg = build_narrative_segment(segment, payload, sample_bibs, include_trace)
            if narrative_seg:
                narrative_segments.append(narrative_seg)
        
        # Determine zone_by from the result
        zone_by = result.get("zone_by", "areal")
        
        response = {
            "engine": "density",
            "zone_by": zone_by,
            "segments": narrative_segments
        }
        
        # Return TSV if requested
        if as_format.lower() == "tsv":
            return StreamingResponse(
                generate_tsv_response(response),
                media_type="text/tab-separated-values",
                headers={"Content-Disposition": "attachment; filename=overlap_narrative.tsv"}
            )
        
        # Default JSON response
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


def build_narrative_segment(segment: dict, payload: DensityPayload, sample_bibs: int, include_trace: bool) -> dict:
    """Build narrative segment from density segment result."""
    from app.density import compute_segment_totals, first_overlap_snapshot
    
    # Basic segment info
    narrative = {
        "seg_id": segment.get("seg_id"),
        "segment_label": segment.get("segment_label"),
        "direction": segment.get("direction"),
        "width_m": segment.get("width_m"),
        "eventA": segment.get("eventA"),
        "eventB": segment.get("eventB"),
        "from_km_A": segment.get("from_km_A"),
        "to_km_A": segment.get("to_km_A"),
        "from_km_B": segment.get("from_km_B"),
        "to_km_B": segment.get("to_km_B"),
        "length_km": segment.get("length_km"),
        "peak": segment.get("peak", {})
    }
    
    # Compute segment totals (unique runners per event)
    try:
        totals = compute_segment_totals(segment, payload)
        narrative["totals"] = totals
    except Exception as e:
        print(f"Warning: Could not compute totals for {segment.get('seg_id')}: {e}")
        narrative["totals"] = {"A": 0, "B": 0}
    
    # Get first overlap snapshot
    try:
        first_overlap = first_overlap_snapshot(segment, payload, sample_bibs)
        if first_overlap:
            narrative["first_overlap"] = first_overlap
            narrative["no_overlap"] = False
        else:
            narrative["no_overlap"] = True
    except Exception as e:
        print(f"Warning: Could not compute first overlap for {segment.get('seg_id')}: {e}")
        narrative["no_overlap"] = True
    
    # Include trace if requested
    if include_trace and segment.get("trace"):
        # Limit to first 50 rows for performance
        trace = segment["trace"][:50]
        narrative["trace"] = trace
    else:
        narrative["trace"] = None
    
    return narrative


def generate_tsv_response(response: dict) -> str:
    """Generate TSV response for overlap narrative."""
    import io
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t')
    
    # Write header
    header = [
        "seg_id", "segment_label", "first_clock", "first_km", 
        "A_count", "B_count", "A_bibs", "B_bibs", 
        "areal", "crowd", "zone", 
        "totA", "totB", "peak_km", "peak_A", "peak_B", "peak_combined"
    ]
    writer.writerow(header)
    
    # Write data rows
    for segment in response.get("segments", []):
        first_overlap = segment.get("first_overlap", {})
        peak = segment.get("peak", {})
        totals = segment.get("totals", {})
        
        row = [
            segment.get("seg_id", ""),
            segment.get("segment_label", ""),
            first_overlap.get("clock", "—"),
            first_overlap.get("km", "—"),
            first_overlap.get("A_count", 0),
            first_overlap.get("B_count", 0),
            ",".join(map(str, first_overlap.get("A_bibs", []))),
            ",".join(map(str, first_overlap.get("B_bibs", []))),
            first_overlap.get("areal_density", "—"),
            first_overlap.get("crowd_density", "—"),
            first_overlap.get("zone", "—"),
            totals.get("A", 0),
            totals.get("B", 0),
            peak.get("km", "—"),
            peak.get("A", 0),
            peak.get("B", 0),
            peak.get("combined", 0)
        ]
        writer.writerow(row)
    
    return output.getvalue()

@app.post("/api/overlap.narrative.text")
async def api_overlap_narrative_text(
    request: Request,
    payload: DensityPayload,
    seg_id: str | None = Query(default=None, description="Filter to a single segment"),
    tolerance_sec: float = Query(default=0.0, ge=0.0, le=300.0, description="Time tolerance for overlap detection in seconds"),
    as_format: str = Query(default="text", alias="as", description="Response format: text or json")
):
    """
    Overlap Narrative Text API (v1.3.9)
    Returns human-readable narrative text describing overlaps:
    - First catch location and time
    - Runner counts from each event
    - Peak overlap details
    - Clear, readable format
    """
    try:
        # Load pace CSV
        import pandas as pd
        df = _load_csv_smart(payload.paceCsv)
        if "start_offset" not in df.columns:
            df["start_offset"] = 0
        df["start_offset"] = df["start_offset"].fillna(0).astype(int)
        
        # Load overlaps CSV
        overlaps_df = _load_csv_smart(payload.overlapsCsv)
        
        # Filter by segment if specified
        if seg_id:
            overlaps_df = overlaps_df[overlaps_df["seg_id"] == seg_id]
        
        # Generate narrative data for each segment
        narrative_data = []
        summary_stats = {
            "total_segments": len(overlaps_df),
            "segments_with_overlaps": 0,
            "top_segments": []
        }
        
        for _, row in overlaps_df.iterrows():
            seg_id = row["seg_id"]
            eventA = row["eventA"]
            eventB = row["eventB"]
            from_km_A = row["from_km_A"]
            to_km_A = row["to_km_A"]
            from_km_B = row["from_km_B"]
            to_km_B = row["to_km_B"]
            
            # Generate narrative using overlap module
            narrative = generate_overlap_narrative(
                df=df,
                seg_id=seg_id,
                eventA=eventA,
                eventB=eventB,
                from_km_A=from_km_A,
                to_km_A=to_km_A,
                from_km_B=from_km_B,
                to_km_B=to_km_B,
                start_times={
                    "Full": payload.startTimes.Full,
                    "Half": payload.startTimes.Half,
                    "10K": payload.startTimes.TenK
                },
                step_km=payload.stepKm,
                tolerance_sec=tolerance_sec,
                sample_bibs=5
            )
            
            # Add direction and segment_label from the CSV row
            narrative["direction"] = row.get("direction", "unknown")
            narrative["segment_label"] = row.get("segment_label", "")
            
            # Track summary statistics
            first = narrative["first_overlap"]
            peak = narrative["peak_overlap"]
            
            if first and first["km"] is not None:
                summary_stats["segments_with_overlaps"] += 1
                
                # Track peak counts for top segments
                if peak and peak["km"] is not None:
                    peak_combined = peak.get("combined", 0)
                    summary_stats["top_segments"].append({
                        "seg_id": seg_id,
                        "segment_label": narrative["segment_label"],
                        "from_km": from_km_A,
                        "to_km": to_km_A,
                        "peak_count": peak_combined
                    })
            
            # Convert to human-readable text
            text = _generate_narrative_text(narrative)
            narrative_data.append({
                "narrative": narrative,
                "text": text
            })
        
        # Sort top segments by peak count and take top 3
        summary_stats["top_segments"].sort(key=lambda x: x["peak_count"], reverse=True)
        summary_stats["top_segments"] = summary_stats["top_segments"][:3]
        
        # Generate summary text
        summary_text = _generate_summary_text(summary_stats)
        
        # Combine summary and narrative texts
        narrative_texts = [summary_text] + [data["text"] for data in narrative_data]
        
        if as_format.lower() == "json":
            return {
                "engine": "overlap",
                "version": "v1.3.9",
                "type": "narrative_text",
                "segments": narrative_texts
            }
        else:
            # Return as plain text
            full_text = "\n\n".join(narrative_texts)
            return Response(content=full_text, media_type="text/plain")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating narrative text: {str(e)}")

def _generate_narrative_text(narrative: dict) -> str:
    """Generate human-readable narrative text from overlap data."""
    seg_id = narrative["seg_id"]
    eventA = narrative["eventA"]
    eventB = narrative["eventB"]
    totals = narrative["segment_totals"]
    first = narrative["first_overlap"]
    peak = narrative["peak_overlap"]
    
    # Build the narrative text
    lines = []
    
    # Segment info
    lines.append(f"🏷️ Segment: {seg_id}")
    if "segment_label" in narrative and narrative["segment_label"]:
        lines.append(f"📝 Label: {narrative['segment_label']}")
    
    # Header with km range on separate line
    lines.append(f"🔍 Checking {eventA} vs {eventB}")
    lines.append(f"📍 Range: {narrative['analysis_params']['from_km_A']:.1f}km to {narrative['analysis_params']['to_km_A']:.1f}km")
    
    # Direction
    direction = narrative.get("direction", "unknown")
    if direction == "uni":
        lines.append("➡️ Direction: Unidirectional")
    elif direction == "bi":
        lines.append("➡️ Direction: Bidirectional")
    else:
        lines.append("➡️ Direction: Unknown")
    
    # Check for same event segments
    if eventA == eventB:
        # Special handling for same event segments
        lines.append(f"👥 Total in '{eventA}': {totals['A']} runners")
        
        # For unidirectional same-event segments, no overlaps are possible
        if direction == "uni":
            lines.append("✅ No overlap possible")
            lines.append("📈 No peak overlap data")
        else:
            # Bidirectional same-event segments can have overlaps (like B2)
            if first and first["km"] is not None:
                lines.append(f"⚠️ First overlap: {first['km']:.2f}km {eventA}: {first['count_A']} {eventB}: {first['count_B']}")
                
                if first["sample_runner_ids_A"] and first["sample_runner_ids_B"]:
                    sample_A = ", ".join(first["sample_runner_ids_A"][:3])
                    sample_B = ", ".join(first["sample_runner_ids_B"][:3])
                    lines.append(f"🏃‍♂️ Runners - {eventA}: {sample_A} (Fastest), {eventB}: {sample_B} (Slowest)")
            else:
                lines.append("❌ No overlaps detected in this segment")
            
            if peak and peak["km"] is not None:
                lines.append(f"📈 Peak: {peak['km']:.2f}km {eventA}: {peak['A']} {eventB}: {peak['B']} (Combined: {peak['combined']})")
            else:
                lines.append("📈 No peak overlap data")
    else:
        # Different events - normal handling
        lines.append(f"👥 Total in '{eventA}': {totals['A']} runners")
        lines.append(f"👥 Total in '{eventB}': {totals['B']} runners")
        
        # First overlap
        if first and first["km"] is not None:
            lines.append(f"⚠️ First overlap: {first['km']:.2f}km {eventA}: {first['count_A']} {eventB}: {first['count_B']}")
            
            if first["sample_runner_ids_A"] and first["sample_runner_ids_B"]:
                sample_A = ", ".join(first["sample_runner_ids_A"][:3])
                sample_B = ", ".join(first["sample_runner_ids_B"][:3])
                lines.append(f"🏃‍♂️ Runners - {eventA}: {sample_A} (Fastest), {eventB}: {sample_B} (Slowest)")
        else:
            lines.append("❌ No overlaps detected in this segment")
        
        # Peak overlap
        if peak and peak["km"] is not None:
            lines.append(f"📈 Peak: {peak['km']:.2f}km {eventA}: {peak['A']} {eventB}: {peak['B']} (Combined: {peak['combined']})")
        else:
            lines.append("📈 No peak overlap data")
    
    # Analysis parameters
    params = narrative["analysis_params"]
    lines.append(f"⚙️ Analysis: {params['step_km']:.3f}km steps, {params['tolerance_sec']:.1f}s tolerance")
    
    return "\n".join(lines)

def _generate_summary_text(summary_stats: dict) -> str:
    """Generate summary text from overlap statistics."""
    lines = []
    
    lines.append("📊 OVERLAP ANALYSIS SUMMARY")
    lines.append("=" * 50)
    lines.append(f"📈 Total segments evaluated: {summary_stats['total_segments']}")
    lines.append(f"⚠️ Segments with overlaps: {summary_stats['segments_with_overlaps']}")
    lines.append(f"📊 Overlap rate: {(summary_stats['segments_with_overlaps'] / summary_stats['total_segments'] * 100):.1f}%")
    
    if summary_stats["top_segments"]:
        lines.append("")
        lines.append("🏆 TOP 3 SEGMENTS BY PEAK RUNNER COUNT:")
        for i, segment in enumerate(summary_stats["top_segments"], 1):
            lines.append(f"{i}. {segment['seg_id']} - {segment['segment_label']}")
            lines.append(f"   📍 Range: {segment['from_km']:.1f}km to {segment['to_km']:.1f}km")
            lines.append(f"   👥 Peak count: {segment['peak_count']} runners")
    
    lines.append("")
    lines.append("=" * 50)
    lines.append("")
    
    return "\n".join(lines)

@app.post("/api/overlap.trace")
async def api_overlap_trace(
    request: Request,
    payload: DensityPayload,
    seg_id: str | None = Query(default=None, description="Filter to a single segment"),
    tolerance_sec: float = Query(default=0.0, ge=0.0, le=300.0, description="Time tolerance for overlap detection in seconds"),
    as_format: str = Query(default="json", alias="as", description="Response format: json or tsv")
):
    """
    Overlap Trace API (v1.3.9)
    Returns comprehensive overlap trace showing overlaps at every km step:
    - Segment totals per event
    - First overlap snapshot
    - Peak overlap
    - Complete trace array with overlaps at each km step
    - Analysis parameters
    """
    try:
        # Load pace CSV
        import pandas as pd
        df = _load_csv_smart(payload.paceCsv)
        if "start_offset" not in df.columns:
            df["start_offset"] = 0
        df["start_offset"] = df["start_offset"].fillna(0).astype(int)
        
        # Load overlaps CSV
        overlaps_df = _load_csv_smart(payload.overlapsCsv)
        
        # Filter by segment if specified
        if seg_id:
            overlaps_df = overlaps_df[overlaps_df["seg_id"] == seg_id]
        
        # Build trace response
        trace_segments = []
        for _, segment in overlaps_df.iterrows():
            trace = generate_overlap_trace(
                df=df,
                seg_id=segment["seg_id"],
                eventA=segment["eventA"],
                eventB=segment["eventB"],
                from_km_A=segment["from_km_A"],
                to_km_A=segment["to_km_A"],
                from_km_B=segment["from_km_B"],
                to_km_B=segment["to_km_B"],
                start_times={
                    "Full": payload.startTimes.Full,
                    "Half": payload.startTimes.Half,
                    "10K": payload.startTimes.TenK
                },
                step_km=payload.stepKm,
                tolerance_sec=tolerance_sec,
                sample_bibs=5
            )
            trace_segments.append(trace)
        
        response = {
            "engine": "overlap",
            "version": "v1.3.9",
            "type": "trace",
            "segments": trace_segments
        }
        
        # Return TSV if requested
        if as_format.lower() == "tsv":
            return StreamingResponse(
                generate_trace_tsv_response(response),
                media_type="text/tab-separated-values",
                headers={"Content-Disposition": "attachment; filename=overlap_trace.tsv"}
            )
        
        # Default JSON response
        return response
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

def generate_trace_tsv_response(response: dict) -> str:
    """Generate TSV response for overlap trace."""
    import io
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t')
    
    # Write header
    header = [
        "seg_id", "km", "A_count", "B_count", "combined", 
        "A_runner_ids", "B_runner_ids"
    ]
    writer.writerow(header)
    
    # Write data rows - one row per km step per segment
    for segment in response.get("segments", []):
        seg_id = segment.get("seg_id", "")
        trace = segment.get("trace", [])
        
        for step in trace:
            row = [
                seg_id,
                step.get("km", ""),
                step.get("A", 0),
                step.get("B", 0),
                step.get("combined", 0),
                ",".join(map(str, step.get("A_runner_ids", []))),
                ",".join(map(str, step.get("B_runner_ids", [])))
            ]
            writer.writerow(row)
    
    return output.getvalue()

@app.post("/api/overlap.narrative.csv")
async def api_overlap_narrative_csv(
    request: Request,
    payload: DensityPayload,
    seg_id: str | None = Query(default=None, description="Filter to a single segment"),
    tolerance_sec: float = Query(default=0.0, ge=0.0, le=300.0, description="Time tolerance for overlap detection in seconds")
):
    """
    Overlap Narrative CSV Export API (v1.3.9)
    Exports overlap narrative data as CSV to /reports directory with DTM prefix.
    """
    try:
        import os
        import datetime
        import csv
        
        # Load pace CSV
        import pandas as pd
        df = _load_csv_smart(payload.paceCsv)
        if "start_offset" not in df.columns:
            df["start_offset"] = 0
        df["start_offset"] = df["start_offset"].fillna(0).astype(int)
        
        # Load overlaps CSV
        overlaps_df = _load_csv_smart(payload.overlapsCsv)
        
        # Filter by segment if specified
        if seg_id:
            overlaps_df = overlaps_df[overlaps_df["seg_id"] == seg_id]
        
        # Generate narrative data for each segment
        narrative_data = []
        summary_stats = {
            "total_segments": len(overlaps_df),
            "segments_with_overlaps": 0,
            "top_segments": []
        }
        
        for _, row in overlaps_df.iterrows():
            seg_id = row["seg_id"]
            eventA = row["eventA"]
            eventB = row["eventB"]
            from_km_A = row["from_km_A"]
            to_km_A = row["to_km_A"]
            from_km_B = row["from_km_B"]
            to_km_B = row["to_km_B"]
            direction = row.get("direction", "unknown")
            segment_label = row.get("segment_label", "")
            
            # Generate narrative using overlap module
            narrative = generate_overlap_narrative(
                df=df,
                seg_id=seg_id,
                eventA=eventA,
                eventB=eventB,
                from_km_A=from_km_A,
                to_km_A=to_km_A,
                from_km_B=from_km_B,
                to_km_B=to_km_B,
                start_times={
                    "Full": payload.startTimes.Full,
                    "Half": payload.startTimes.Half,
                    "10K": payload.startTimes.TenK
                },
                step_km=payload.stepKm,
                tolerance_sec=tolerance_sec,
                sample_bibs=5
            )
            
            # Add direction and segment_label from the CSV row
            narrative["direction"] = direction
            narrative["segment_label"] = segment_label
            
            # Extract data for CSV
            totals = narrative["segment_totals"]
            first = narrative["first_overlap"]
            peak = narrative["peak_overlap"]
            
            # Track summary statistics
            if first and first["km"] is not None:
                summary_stats["segments_with_overlaps"] += 1
                
                # Track peak counts for top segments
                if peak and peak["km"] is not None:
                    peak_combined = peak.get("combined", 0)
                    summary_stats["top_segments"].append({
                        "seg_id": seg_id,
                        "segment_label": segment_label,
                        "from_km": from_km_A,
                        "to_km": to_km_A,
                        "peak_count": peak_combined
                    })
            
            # Determine overlap status
            if eventA == eventB and direction == "uni":
                overlap_status = "No overlap possible"
                first_km = None
                first_A_count = None
                first_B_count = None
                first_A_runners = None
                first_B_runners = None
                peak_km = None
                peak_A = None
                peak_B = None
                peak_combined = None
            elif first and first["km"] is not None:
                overlap_status = "Overlap detected"
                first_km = first["km"]
                first_A_count = first["count_A"]
                first_B_count = first["count_B"]
                first_A_runners = ", ".join(first["sample_runner_ids_A"][:3]) if first["sample_runner_ids_A"] else ""
                first_B_runners = ", ".join(first["sample_runner_ids_B"][:3]) if first["sample_runner_ids_B"] else ""
                peak_km = peak["km"] if peak and peak["km"] is not None else None
                peak_A = peak["A"] if peak and peak["km"] is not None else None
                peak_B = peak["B"] if peak and peak["km"] is not None else None
                peak_combined = peak["combined"] if peak and peak["km"] is not None else None
            else:
                overlap_status = "No overlaps detected"
                first_km = None
                first_A_count = None
                first_B_count = None
                first_A_runners = None
                first_B_runners = None
                peak_km = None
                peak_A = None
                peak_B = None
                peak_combined = None
            
            narrative_data.append({
                "seg_id": seg_id,
                "segment_label": segment_label,
                "eventA": eventA,
                "eventB": eventB,
                "from_km_A": from_km_A,
                "to_km_A": to_km_A,
                "from_km_B": from_km_B,
                "to_km_B": to_km_B,
                "direction": direction,
                "total_A": totals["A"],
                "total_B": totals["B"],
                "overlap_status": overlap_status,
                "first_km": first_km,
                "first_A_count": first_A_count,
                "first_B_count": first_B_count,
                "first_A_runners": first_A_runners,
                "first_B_runners": first_B_runners,
                "peak_km": peak_km,
                "peak_A": peak_A,
                "peak_B": peak_B,
                "peak_combined": peak_combined,
                "step_km": payload.stepKm,
                "tolerance_sec": tolerance_sec
            })
        
        # Sort top segments by peak count and take top 3
        summary_stats["top_segments"].sort(key=lambda x: x["peak_count"], reverse=True)
        summary_stats["top_segments"] = summary_stats["top_segments"][:3]
        
        # Create reports directory if it doesn't exist
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate filename with DTM prefix
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"{timestamp}_overlaps.csv"
        filepath = os.path.join(reports_dir, filename)
        
        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                "seg_id", "segment_label", "eventA", "eventB", 
                "from_km_A", "to_km_A", "from_km_B", "to_km_B", "direction",
                "total_A", "total_B", "overlap_status",
                "first_km", "first_A_count", "first_B_count", 
                "first_A_runners", "first_B_runners",
                "peak_km", "peak_A", "peak_B", "peak_combined",
                "step_km", "tolerance_sec"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write summary rows
            writer.writerow({
                "seg_id": "SUMMARY",
                "segment_label": f"Total segments: {summary_stats['total_segments']}",
                "eventA": f"With overlaps: {summary_stats['segments_with_overlaps']}",
                "eventB": f"Overlap rate: {(summary_stats['segments_with_overlaps'] / summary_stats['total_segments'] * 100):.1f}%",
                "from_km_A": "", "to_km_A": "", "from_km_B": "", "to_km_B": "",
                "direction": "", "total_A": "", "total_B": "", "overlap_status": "",
                "first_km": "", "first_A_count": "", "first_B_count": "",
                "first_A_runners": "", "first_B_runners": "",
                "peak_km": "", "peak_A": "", "peak_B": "", "peak_combined": "",
                "step_km": "", "tolerance_sec": ""
            })
            
            # Write top segments
            for i, segment in enumerate(summary_stats["top_segments"], 1):
                writer.writerow({
                    "seg_id": f"TOP_{i}",
                    "segment_label": f"{segment['seg_id']} - {segment['segment_label']}",
                    "eventA": f"Range: {segment['from_km']:.1f}km to {segment['to_km']:.1f}km",
                    "eventB": f"Peak count: {segment['peak_count']} runners",
                    "from_km_A": "", "to_km_A": "", "from_km_B": "", "to_km_B": "",
                    "direction": "", "total_A": "", "total_B": "", "overlap_status": "",
                    "first_km": "", "first_A_count": "", "first_B_count": "",
                    "first_A_runners": "", "first_B_runners": "",
                    "peak_km": "", "peak_A": "", "peak_B": "", "peak_combined": "",
                    "step_km": "", "tolerance_sec": ""
                })
            
            # Write empty row as separator
            writer.writerow({
                "seg_id": "", "segment_label": "", "eventA": "", "eventB": "",
                "from_km_A": "", "to_km_A": "", "from_km_B": "", "to_km_B": "",
                "direction": "", "total_A": "", "total_B": "", "overlap_status": "",
                "first_km": "", "first_A_count": "", "first_B_count": "",
                "first_A_runners": "", "first_B_runners": "",
                "peak_km": "", "peak_A": "", "peak_B": "", "peak_combined": "",
                "step_km": "", "tolerance_sec": ""
            })
            
            # Write segment data
            writer.writerows(narrative_data)
        
        return {
            "engine": "overlap",
            "version": "v1.3.9",
            "type": "narrative_csv",
            "filename": filename,
            "filepath": filepath,
            "segments_processed": len(narrative_data),
            "message": f"CSV exported to {filepath}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating narrative CSV: {str(e)}")
