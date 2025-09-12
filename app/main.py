"""
Main FastAPI Application - v1.5.0 Architecture Split
"""

from __future__ import annotations
import os
import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from pydantic import BaseModel

# Import new modules
try:
    # Try relative imports first (for local development)
    from .density import analyze_density_segments
    from .density_api import router as density_router
    from .density_report import generate_density_report, generate_simple_density_report
    from .flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
    from .flow_report import generate_temporal_flow_report, generate_simple_temporal_flow_report
    from .report import generate_combined_report, generate_combined_narrative
    # from .test_api import test_router  # Disabled for Cloud Run deployment
    from .constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS
except ImportError:
    # Fall back to absolute imports (for Cloud Run)
    from density import analyze_density_segments
    from density_api import router as density_router
    from density_report import generate_density_report, generate_simple_density_report
    from flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
    from flow_report import generate_temporal_flow_report, generate_simple_temporal_flow_report
    from report import generate_combined_report, generate_combined_narrative
    # from test_api import test_router  # Disabled for Cloud Run deployment
    from constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS

# Pydantic models for request bodies
class AnalysisRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    stepKm: float = DEFAULT_STEP_KM
    timeWindow: int = DEFAULT_TIME_WINDOW_SECONDS
    format: str = "json"

class TemporalFlowRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    minOverlapDuration: float = DEFAULT_MIN_OVERLAP_DURATION
    conflictLengthM: float = DEFAULT_CONFLICT_LENGTH_METERS
    format: str = "json"

class ReportRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    stepKm: float = DEFAULT_STEP_KM
    timeWindow: int = DEFAULT_TIME_WINDOW_SECONDS
    minOverlapDuration: float = 5.0
    includeDensity: bool = True
    includeOvertake: bool = True
    format: str = "json"

class DensityReportRequest(BaseModel):
    paceCsv: str
    densityCsv: str
    startTimes: Dict[str, int]
    stepKm: float = DEFAULT_STEP_KM
    timeWindow: int = DEFAULT_TIME_WINDOW_SECONDS
    includePerEvent: bool = True
    outputDir: str = "reports"

class TemporalFlowReportRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    minOverlapDuration: float = DEFAULT_MIN_OVERLAP_DURATION
    conflictLengthM: float = DEFAULT_CONFLICT_LENGTH_METERS
    outputDir: str = "reports"

class FlowAuditRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    segId: str
    eventA: str
    eventB: str
    minOverlapDuration: float = DEFAULT_MIN_OVERLAP_DURATION
    conflictLengthM: float = DEFAULT_CONFLICT_LENGTH_METERS
    outputDir: str = "reports"

app = FastAPI(title="run-density", version="v1.6.20")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Include density API router
app.include_router(density_router)
# app.include_router(test_router)  # Disabled for Cloud Run deployment

# Mount static files
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
except Exception as e:
    print(f"Warning: Could not mount frontend directory: {e}")

@app.get("/")
async def root():
    return {
        "message": "run-density API v1.6.7",
        "version": APP_VERSION,
        "architecture": "split",
        "endpoints": ["/api/density", "/api/temporal-flow", "/api/report", "/api/density-report", "/api/temporal-flow-report", "/api/flow-audit", "/health", "/ready"]
    }

@app.get("/health")
async def health_check():
    return {"ok": True, "status": "healthy", "version": APP_VERSION}

@app.get("/ready")
async def readiness_check():
    """Check if the service is ready to handle requests."""
    return {
        "ok": True,
        "density_loaded": True,
        "overlap_loaded": True,
        "version": APP_VERSION
    }

# Density analysis is now handled by the density API router
# @app.post("/api/density") - moved to density_api.py

@app.post("/api/temporal-flow")
async def analyze_temporal_flow(request: TemporalFlowRequest):
    try:
        results = analyze_temporal_flow_segments(
            pace_csv=request.paceCsv, 
            segments_csv=request.segmentsCsv, 
            start_times=request.startTimes, 
            min_overlap_duration=request.minOverlapDuration,
            conflict_length_m=request.conflictLengthM
        )
        if request.format == "text":
            narrative = generate_temporal_flow_narrative(results)
            return Response(content=narrative, media_type="text/plain")
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal flow analysis failed: {str(e)}")

@app.post("/api/report")
async def generate_report(request: ReportRequest):
    try:
        results = generate_combined_report(
            pace_csv=request.paceCsv, 
            segments_csv=request.segmentsCsv, 
            start_times=request.startTimes, 
            step_km=request.stepKm, 
            time_window_s=request.timeWindow, 
            min_overlap_duration=request.minOverlapDuration, 
            include_density=request.includeDensity, 
            include_overtake=request.includeOvertake
        )
        if request.format == "text":
            narrative = generate_combined_narrative(results)
            return Response(content=narrative, media_type="text/plain")
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Combined report generation failed: {str(e)}")

@app.post("/api/overtake")
async def legacy_overtake_endpoint(request: TemporalFlowRequest):
    """Legacy endpoint for backward compatibility - redirects to temporal-flow"""
    return await analyze_temporal_flow(request)

@app.post("/api/density-report")
async def generate_density_report_endpoint(request: DensityReportRequest):
    """Generate comprehensive density analysis report with per-event views."""
    try:
        results = generate_density_report(
            pace_csv=request.paceCsv,
            density_csv=request.densityCsv,
            start_times=request.startTimes,
            step_km=request.stepKm,
            time_window_s=request.timeWindow,
            include_per_event=request.includePerEvent,
            output_dir=request.outputDir
        )
        # Handle NaN values and dataclass objects for JSON serialization
        import json
        import math
        
        def convert_for_json(obj):
            if isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_for_json(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return None
            elif hasattr(obj, '__dict__'):
                return convert_for_json(obj.__dict__)
            else:
                return obj
        
        cleaned_results = convert_for_json(results)
        return JSONResponse(content=cleaned_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Density report generation failed: {str(e)}")

@app.post("/api/temporal-flow-report")
async def generate_temporal_flow_report_endpoint(request: TemporalFlowReportRequest):
    """Generate comprehensive temporal flow analysis report with convergence analysis."""
    try:
        results = generate_temporal_flow_report(
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            min_overlap_duration=request.minOverlapDuration,
            conflict_length_m=request.conflictLengthM,
            output_dir=request.outputDir
        )
        # Handle NaN values for JSON serialization
        import json
        import math
        
        def convert_nan(obj):
            if isinstance(obj, dict):
                return {k: convert_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_nan(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return None
            else:
                return obj
        
        cleaned_results = convert_nan(results)
        return JSONResponse(content=cleaned_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal flow report generation failed: {str(e)}")

@app.post("/api/flow-audit")
async def generate_flow_audit_endpoint(request: FlowAuditRequest):
    """Generate Flow Audit for a specific segment and event pair."""
    try:
        # Import the flow audit function (we'll create this)
        from .flow import generate_flow_audit_for_segment
        
        results = generate_flow_audit_for_segment(
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            seg_id=request.segId,
            event_a=request.eventA,
            event_b=request.eventB,
            min_overlap_duration=request.minOverlapDuration,
            conflict_length_m=request.conflictLengthM,
            output_dir=request.outputDir
        )
        
        # Handle NaN values for JSON serialization
        import json
        import math
        
        def convert_nan(obj):
            if isinstance(obj, dict):
                return {k: convert_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_nan(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return None
            else:
                return obj
        
        cleaned_results = convert_nan(results)
        return JSONResponse(content=cleaned_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flow audit generation failed: {str(e)}")

@app.post("/api/overlap")
async def legacy_overlap_endpoint(request: ReportRequest):
    return await generate_report(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
