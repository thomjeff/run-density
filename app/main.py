"""
Main FastAPI Application - v1.5.0 Architecture Split
"""

from __future__ import annotations
import os
import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

# Import new modules
from app.density import analyze_density_segments, generate_density_narrative
from app.overtake import analyze_overtake_segments, generate_overtake_narrative
from app.report import generate_combined_report, generate_combined_narrative

app = FastAPI(title="run-density", version="v1.5.0")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Mount static files
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
except Exception as e:
    print(f"Warning: Could not mount frontend directory: {e}")

@app.get("/")
async def root():
    return {
        "message": "run-density API v1.5.0",
        "version": APP_VERSION,
        "architecture": "split",
        "endpoints": ["/api/density", "/api/overtake", "/api/report", "/health"]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": APP_VERSION}

@app.post("/api/density")
async def analyze_density(paceCsv: str, segmentsCsv: str, startTimes: dict, stepKm: float = 0.03, timeWindow: int = 300, format: str = "json"):
    try:
        results = analyze_density_segments(pace_csv=paceCsv, segments_csv=segmentsCsv, start_times=startTimes, step_km=stepKm, time_window_s=timeWindow)
        if format == "text":
            narrative = generate_density_narrative(results)
            return Response(content=narrative, media_type="text/plain")
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Density analysis failed: {str(e)}")

@app.post("/api/overtake")
async def analyze_overtake(paceCsv: str, segmentsCsv: str, startTimes: dict, minOverlapDuration: float = 5.0, format: str = "json"):
    try:
        results = analyze_overtake_segments(pace_csv=paceCsv, segments_csv=segmentsCsv, start_times=startTimes, min_overlap_duration=minOverlapDuration)
        if format == "text":
            narrative = generate_overtake_narrative(results)
            return Response(content=narrative, media_type="text/plain")
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Overtake analysis failed: {str(e)}")

@app.post("/api/report")
async def generate_report(paceCsv: str, segmentsCsv: str, startTimes: dict, stepKm: float = 0.03, timeWindow: int = 300, minOverlapDuration: float = 5.0, includeDensity: bool = True, includeOvertake: bool = True, format: str = "json"):
    try:
        results = generate_combined_report(pace_csv=paceCsv, segments_csv=segmentsCsv, start_times=startTimes, step_km=stepKm, time_window_s=timeWindow, min_overlap_duration=minOverlapDuration, include_density=includeDensity, include_overtake=includeOvertake)
        if format == "text":
            narrative = generate_combined_narrative(results)
            return Response(content=narrative, media_type="text/plain")
        return JSONResponse(content=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Combined report generation failed: {str(e)}")

@app.post("/api/overlap")
async def legacy_overlap_endpoint(paceCsv: str, segmentsCsv: str, startTimes: dict, stepKm: float = 0.03, timeWindow: int = 300, minOverlapDuration: float = 5.0, format: str = "json"):
    return await generate_report(paceCsv=paceCsv, segmentsCsv=segmentsCsv, startTimes=startTimes, stepKm=stepKm, timeWindow=timeWindow, minOverlapDuration=minOverlapDuration, includeDensity=True, includeOvertake=True, format=format)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
