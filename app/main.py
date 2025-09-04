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
from app.density import analyze_density_segments
from app.density_api import router as density_router
from app.temporal_flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
from app.report import generate_combined_report, generate_combined_narrative

# Pydantic models for request bodies
class AnalysisRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    stepKm: float = 0.03
    timeWindow: int = 300
    format: str = "json"

class TemporalFlowRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    minOverlapDuration: float = 5.0
    conflictLengthM: float = 100.0
    format: str = "json"

class ReportRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    stepKm: float = 0.03
    timeWindow: int = 300
    minOverlapDuration: float = 5.0
    includeDensity: bool = True
    includeOvertake: bool = True
    format: str = "json"

app = FastAPI(title="run-density", version="v1.6.0")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Include density API router
app.include_router(density_router)

# Mount static files
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
except Exception as e:
    print(f"Warning: Could not mount frontend directory: {e}")

@app.get("/")
async def root():
    return {
        "message": "run-density API v1.6.0",
        "version": APP_VERSION,
        "architecture": "split",
        "endpoints": ["/api/density", "/api/temporal-flow", "/api/report", "/health"]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": APP_VERSION}

@app.post("/api/density")
async def analyze_density(request: AnalysisRequest):
    try:
        results = analyze_density_segments(
            pace_csv=request.paceCsv, 
            segments_csv=request.segmentsCsv, 
            start_times=request.startTimes, 
            step_km=request.stepKm, 
            time_window_s=request.timeWindow
        )
        if request.format == "text":
            narrative = generate_density_narrative(results)
            return Response(content=narrative, media_type="text/plain")
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Density analysis failed: {str(e)}")

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

@app.post("/api/overlap")
async def legacy_overlap_endpoint(request: ReportRequest):
    return await generate_report(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
