from __future__ import annotations

import csv
import io
from fastapi import FastAPI, Query, HTTPException, Request
from starlette.responses import JSONResponse, StreamingResponse

from app.density import DensityPayload, run_density, preview_segments

try:
    from app.density import export_peaks_csv  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    export_peaks_csv = None

app = FastAPI(title="run-density", version="v1.3.4-dev")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/ready")
def ready():
    return {"ok": True, "density_loaded": True, "overlap_loaded": True}


@app.post("/api/density")
def api_density(
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

        if debug and export_peaks_csv and result.get("segments"):
            try:
                export_peaks_csv(result["segments"])  # type: ignore[arg-type]
            except Exception:
                pass

        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/segments")
def api_segments(payload: DensityPayload):
    try:
        return {"segments": preview_segments(payload)}
    except HTTPException as he:
        raise he
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
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/peaks.csv")
def api_peaks_csv(payload: DensityPayload, request: Request):
    """
    Stream per-segment peaks as CSV.
    Columns: seg_id,segment_label,direction,width_m,first_clock,first_km,
             peak_km,A,B,combined,areal_density,crowd_density,zone
    """
    seg_id = request.query_params.get("seg_id")
    zm = request.query_params.get("zoneMetric")
    if zm:
        payload.zoneMetric = zm

    try:
        result = run_density(payload, seg_id_filter=seg_id, debug=False)
        segments = result.get("segments", []) or []

        buf = io.StringIO()
        fieldnames = [
            "seg_id",
            "segment_label",
            "direction",
            "width_m",
            "first_clock",
            "first_km",
            "peak_km",
            "A",
            "B",
            "combined",
            "areal_density",
            "crowd_density",
            "zone",
        ]
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()

        for seg in segments:
            peak = seg.get("peak", {}) or {}
            first = seg.get("first_overlap") or {"clock": None, "km": None}
            writer.writerow(
                {
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
                }
            )

        return StreamingResponse(io.StringIO(buf.getvalue()), media_type="text/csv")
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})@app.post("/api/segments.csv")
def api_segments_csv(payload: DensityPayload):
    from app.density import _load_overlaps
    import io, csv
    overlaps = _load_overlaps(payload.overlapsCsv, payload.segments)
    csv_io = io.StringIO()
    w = csv.writer(csv_io)
    w.writerow(["seg_id","segment_label","eventA","eventB","from_km_A","to_km_A","from_km_B","to_km_B","direction","width_m"])
    for s in overlaps:
        w.writerow([s.seg_id, s.segment_label, s.eventA, s.eventB,
                    s.from_km_A, s.to_km_A, s.from_km_B, s.to_km_B,
                    s.direction, s.width_m])
    return Response(content=csv_io.getvalue(), media_type="text/csv")
