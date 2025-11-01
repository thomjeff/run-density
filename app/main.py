"""
Main FastAPI Application - v1.5.0 Architecture Split
"""

from __future__ import annotations
import os
import datetime
from typing import Dict, Any, Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
from pydantic import BaseModel

# Import modules using v1.7 absolute import pattern
from app.core.density.compute import analyze_density_segments
from app.api.density import router as density_router
from app.density_report import generate_density_report, generate_simple_density_report
from app.core.flow.flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
from app.flow_report import generate_temporal_flow_report, generate_simple_temporal_flow_report
from app.api.report import generate_combined_report, generate_combined_narrative
from app.api.map import router as map_router
from app.routes.reports import router as reports_router
from app.routes.ui import router as ui_router
from app.routes.api_segments import router as api_segments_router
from app.routes.api_dashboard import router as api_dashboard_router
from app.routes.api_health import router as api_health_router
from app.routes.api_density import router as api_density_router
from app.routes.api_flow import router as api_flow_router
from app.routes.api_reports import router as api_reports_router
from app.routes.api_bins import router as api_bins_router
from app.routes.api_e2e import router as api_e2e_router
from app.routes.api_heatmaps import router as api_heatmaps_router
from app.utils.constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS

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

class SingleSegmentFlowRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    segId: str
    eventA: Optional[str] = None
    eventB: Optional[str] = None
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
    enable_bin_dataset: bool = True  # Issue #319: Enable by default (resource constraints resolved)

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

app = FastAPI(title="run-density", version="v1.6.50")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Boot environment logging for bin dataset debugging
import logging
import pathlib
from app.utils.env import env_bool, env_str

BOOT_ENV = {
    "cwd": str(pathlib.Path.cwd()),
    "enable_bin_dataset": True,  # TEMPORARY FIX: Force enable bin dataset generation
    "output_dir": env_str("OUTPUT_DIR", "reports"),
    "bin_max_features": env_str("BIN_MAX_FEATURES"),
    "bin_dt_s": env_str("DEFAULT_BIN_TIME_WINDOW_SECONDS"),
    "raw_enable_bin_dataset": os.getenv("ENABLE_BIN_DATASET"),
    "all_env_vars_with_BIN": {k: v for k, v in os.environ.items() if "BIN" in k},
    "all_env_vars_with_ENABLE": {k: v for k, v in os.environ.items() if "ENABLE" in k}
}
logging.getLogger().info("BOOT_ENV %s", BOOT_ENV)

# Include API routers
# app.include_router(density_router)  # Disabled - conflicts with api_density_router
app.include_router(map_router)
app.include_router(reports_router)
app.include_router(ui_router)
app.include_router(api_segments_router)
app.include_router(api_dashboard_router)
app.include_router(api_health_router)
app.include_router(api_density_router)
app.include_router(api_flow_router)
app.include_router(api_reports_router)
app.include_router(api_bins_router)
app.include_router(api_e2e_router)
app.include_router(api_heatmaps_router, prefix="/api/generate", tags=["heatmaps"])

# CSV Data Endpoints for Reports Page
@app.get("/data/runners.csv")
async def get_runners_csv():
    """Serve runners.csv file for download."""
    file_path = "data/runners.csv"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Runners CSV file not found")
    return FileResponse(file_path, filename="runners.csv", media_type="text/csv")

@app.get("/data/segments.csv") 
async def get_segments_csv():
    """Serve segments.csv file for download."""
    file_path = "data/segments.csv"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Segments CSV file not found")
    return FileResponse(file_path, filename="segments.csv", media_type="text/csv")

@app.get("/data/flow_expected_results.csv")
async def get_expected_results_csv():
    """Serve flow_expected_results.csv file for download.""" 
    file_path = "data/flow_expected_results.csv"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Expected results CSV file not found")
    return FileResponse(file_path, filename="flow_expected_results.csv", media_type="text/csv")
# app.include_router(test_router)  # Disabled for Cloud Run deployment

# Mount static files
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
except Exception as e:
    print(f"Warning: Could not mount frontend directory: {e}")

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"Warning: Could not mount static directory: {e}")

# Mount artifacts directory for local development only
# In Cloud Run, heatmaps are served via signed URLs from GCS
if os.path.exists("artifacts"):
    try:
        app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
    except Exception as e:
        print(f"Warning: Could not mount artifacts directory: {e}")
else:
    print("Info: Artifacts directory not found - using GCS storage mode")

@app.get("/")
async def root():
    return {
        "message": "run-density API v1.6.25",
        "version": APP_VERSION,
        "architecture": "split",
        "endpoints": [
            "/api/density", "/api/temporal-flow", "/api/report", 
            "/api/density-report", "/api/temporal-flow-report", "/api/flow-audit",
            "/api/segments.geojson", "/api/flow-bins", "/api/export-bins", "/api/map-status",
            "/api/historical-trends", "/api/compare-segments", "/api/export-advanced",
            "/api/cache-management", "/api/invalidate-segment", "/api/clear-cache",
            "/health", "/ready"
        ]
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

@app.get("/api/debug/env")
async def debug_env():
    """Debug endpoint to verify environment variables for bin dataset generation."""
    # Check canonical segments availability
    canonical_status = {"available": False, "error": "Not checked"}
    try:
        from .canonical_segments import is_canonical_segments_available, get_canonical_segments_metadata
        canonical_available = is_canonical_segments_available()
        canonical_status = {
            "available": canonical_available,
            "metadata": get_canonical_segments_metadata() if canonical_available else None
        }
    except Exception as e:
        canonical_status = {"available": False, "error": str(e)}
    
    return {
        "enable_bin_dataset": env_bool("ENABLE_BIN_DATASET", False),
        "segments_from_bins": env_bool("SEGMENTS_FROM_BINS", True),
        "output_dir": env_str("OUTPUT_DIR", "reports"),
        "bin_max_features": env_str("BIN_MAX_FEATURES"),
        "bin_dt_s": env_str("DEFAULT_BIN_TIME_WINDOW_SECONDS"),
        "canonical_segments": canonical_status,
        "boot_env": BOOT_ENV
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
        
        # Handle JSON serialization for pandas data types
        import json
        import math
        
        def convert_nan(obj):
            if isinstance(obj, dict):
                return {k: convert_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_nan(item) for item in obj]
            elif isinstance(obj, float) and math.isnan(obj):
                return None
            elif hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            else:
                return obj
        
        # Convert the results to ensure JSON serialization
        results_clean = convert_nan(results)
        return JSONResponse(content=results_clean)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Temporal flow analysis failed: {str(e)}")

@app.post("/api/temporal-flow-single")
async def analyze_single_segment_flow(request: SingleSegmentFlowRequest):
    """Analyze temporal flow for a single segment with optional event filtering."""
    try:
        # Create a new flags instance with single segment mode
        from .config_algo_consistency import AlgoConsistencyFlags
        import app.config_algo_consistency as config_module
        
        # Store original flags
        original_flags = config_module.FLAGS
        
        # Create new flags with single segment mode
        new_flags = AlgoConsistencyFlags(
            ENABLE_STRICT_FIRST_PUBLISH=original_flags.ENABLE_STRICT_FIRST_PUBLISH,
            ENABLE_BIN_SELECTOR_UNIFICATION=original_flags.ENABLE_BIN_SELECTOR_UNIFICATION,
            ENABLE_INPUT_NORMALIZATION=original_flags.ENABLE_INPUT_NORMALIZATION,
            ENABLE_TELEMETRY_MIN=original_flags.ENABLE_TELEMETRY_MIN,
            FORCE_BIN_PATH_FOR_SEGMENTS=original_flags.FORCE_BIN_PATH_FOR_SEGMENTS,
            SINGLE_SEGMENT_MODE=request.segId
        )
        
        # Temporarily replace the global flags
        config_module.FLAGS = new_flags
        
        try:
            results = analyze_temporal_flow_segments(
                pace_csv=request.paceCsv, 
                segments_csv=request.segmentsCsv, 
                start_times=request.startTimes, 
                min_overlap_duration=request.minOverlapDuration,
                conflict_length_m=request.conflictLengthM
            )
            
            # Filter by specific events if provided
            if request.eventA and request.eventB:
                filtered_segments = []
                for segment in results.get("segments", []):
                    if (segment.get("event_a") == request.eventA and 
                        segment.get("event_b") == request.eventB):
                        filtered_segments.append(segment)
                results["segments"] = filtered_segments
                results["total_segments"] = len(filtered_segments)
            
            if request.format == "text":
                narrative = generate_temporal_flow_narrative(results)
                return Response(content=narrative, media_type="text/plain")
            return JSONResponse(content=results)
        finally:
            # Restore original flags
            config_module.FLAGS = original_flags
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Single segment flow analysis failed: {str(e)}")

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
            output_dir=request.outputDir,
            enable_bin_dataset=request.enable_bin_dataset
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
        
        # Add markdown content for Cloud Run E2E testing
        if cleaned_results.get("ok") and cleaned_results.get("report_path"):
            try:
                with open(cleaned_results["report_path"], 'r', encoding='utf-8') as f:
                    cleaned_results["markdown_content"] = f.read()
            except Exception as e:
                cleaned_results["markdown_content"] = f"Error reading report: {e}"
        
        return JSONResponse(content=cleaned_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Density report generation failed: {str(e)}")

def detect_environment() -> str:
    """Detect the current environment (local, cloud-run, etc.)"""
    import os
    if os.getenv("K_SERVICE"):  # Cloud Run sets this environment variable
        return "cloud-run"
    elif os.getenv("GAE_SERVICE"):  # App Engine sets this
        return "app-engine"
    elif os.getenv("VERCEL"):  # Vercel sets this
        return "vercel"
    else:
        return "local"

@app.post("/api/temporal-flow-report")
async def generate_temporal_flow_report_endpoint(request: TemporalFlowReportRequest):
    """Generate comprehensive temporal flow analysis report with convergence analysis."""
    try:
        environment = detect_environment()
        results = generate_temporal_flow_report(
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            min_overlap_duration=request.minOverlapDuration,
            conflict_length_m=request.conflictLengthM,
            output_dir=request.outputDir,
            environment=environment
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
            elif hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            else:
                return obj
        
        cleaned_results = convert_nan(results)
        
        # Add markdown and CSV content for Cloud Run E2E testing
        if cleaned_results.get("ok") and cleaned_results.get("report_path"):
            try:
                with open(cleaned_results["report_path"], 'r', encoding='utf-8') as f:
                    cleaned_results["markdown_content"] = f.read()
            except Exception as e:
                cleaned_results["markdown_content"] = f"Error reading report: {e}"
        
        # Also add CSV content if available
        if cleaned_results.get("ok") and cleaned_results.get("csv_path"):
            try:
                with open(cleaned_results["csv_path"], 'r', encoding='utf-8') as f:
                    cleaned_results["csv_content"] = f.read()
            except Exception as e:
                cleaned_results["csv_content"] = f"Error reading CSV: {e}"
        
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
            elif hasattr(obj, 'item'):  # numpy scalar
                return obj.item()
            else:
                return obj
        
        cleaned_results = convert_nan(results)
        return JSONResponse(content=cleaned_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flow audit generation failed: {str(e)}")

@app.post("/api/overlap")
async def legacy_overlap_endpoint(request: ReportRequest):
    return await generate_report(request)

@app.post("/api/flow-density-correlation")
async def generate_flow_density_correlation_endpoint(request: ReportRequest):
    """Generate Flow↔Density correlation analysis report."""
    try:
        from .flow_density_correlation import analyze_flow_density_correlation, export_correlation_report
        from .density import analyze_density_segments, load_density_cfg
        from .flow import analyze_temporal_flow_segments
        
        # Run both Flow and Density analysis
        flow_results = analyze_temporal_flow_segments(
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            min_overlap_duration=request.minOverlapDuration,
            conflict_length_m=100.0  # Default conflict length
        )
        
        # Load data for density analysis
        from .io.loader import load_runners, load_segments
        from .density import DensityConfig, StaticWidthProvider
        
        pace_data = load_runners(request.paceCsv)
        segments_df = load_segments(request.segmentsCsv)
        
        # Convert start times to datetime objects
        from datetime import datetime, timedelta
        start_datetimes = {}
        for event, minutes in request.startTimes.items():
            start_datetimes[event] = datetime(2025, 1, 1) + timedelta(minutes=minutes)
        
        # Create density config
        density_config = DensityConfig(
            step_km=request.stepKm,
            bin_seconds=request.timeWindow
        )
        
        # Create width provider
        width_provider = StaticWidthProvider(segments_df)
        
        # Run density analysis
        density_results = analyze_density_segments(
            pace_data=pace_data,
            start_times=start_datetimes,
            config=density_config,
            density_csv_path=request.segmentsCsv
        )
        
        # Load segments configuration
        segments_config = load_density_cfg(request.segmentsCsv)
        
        # Run correlation analysis
        correlation_results = analyze_flow_density_correlation(
            flow_results, density_results, segments_config
        )
        
        if not correlation_results.get("ok", False):
            raise HTTPException(status_code=500, detail="Flow↔Density correlation analysis failed")
        
        # Export reports
        report_paths = export_correlation_report(correlation_results, "reports")
        
        # Add report content for Cloud Run E2E testing
        cleaned_results = {
            "ok": True,
            "engine": "flow_density_correlation",
            "timestamp": correlation_results.get("timestamp"),
            "flow_summary": correlation_results.get("flow_summary", {}),
            "density_summary": correlation_results.get("density_summary", {}),
            "correlations": correlation_results.get("correlations", []),
            "summary_insights": correlation_results.get("summary_insights", []),
            "total_correlations": correlation_results.get("total_correlations", 0),
            "report_paths": report_paths
        }
        
        # Add markdown content for Cloud Run E2E testing
        if report_paths.get("markdown_path"):
            try:
                with open(report_paths["markdown_path"], 'r', encoding='utf-8') as f:
                    cleaned_results["markdown_content"] = f.read()
            except Exception as e:
                cleaned_results["markdown_content"] = f"Error reading report: {e}"
        
        # Add CSV content for Cloud Run E2E testing
        if report_paths.get("csv_path"):
            try:
                with open(report_paths["csv_path"], 'r', encoding='utf-8') as f:
                    cleaned_results["csv_content"] = f.read()
            except Exception as e:
                cleaned_results["csv_content"] = f"Error reading CSV: {e}"
        
        return JSONResponse(content=cleaned_results)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flow↔Density correlation analysis failed: {str(e)}")


# PDF Generation Endpoints
class PDFReportRequest(BaseModel):
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    layout: str = "brief"  # "brief" or "detailed"
    reportType: str = "density"  # "density" or "flow"


@app.post("/api/pdf-report")
async def generate_pdf_report_endpoint(request: PDFReportRequest):
    """Generate PDF report from analysis data."""
    try:
        from .pdf_generator import generate_pdf_report, validate_pandoc_installation
        
        # Check if Pandoc is available
        if not validate_pandoc_installation():
            raise HTTPException(
                status_code=503, 
                detail="PDF generation not available: Pandoc is not installed"
            )
        
        # Generate report data based on type
        if request.reportType == "density":
            from .density import analyze_density_segments
            from datetime import datetime
            
            # Convert start times to datetime objects
            start_datetimes = {}
            for event, minutes in request.startTimes.items():
                start_datetimes[event] = datetime(2025, 1, 1) + datetime.timedelta(minutes=minutes)
            
            # Run density analysis
            results = analyze_density_segments(
                pace_csv=request.paceCsv,
                segments_csv=request.segmentsCsv,
                start_times=start_datetimes
            )
            
            # Add start times to results for PDF generation
            results['start_times'] = request.startTimes
            
        elif request.reportType == "flow":
            from .flow import analyze_temporal_flow_segments
            
            # Run flow analysis
            results = analyze_temporal_flow_segments(
                pace_csv=request.paceCsv,
                segments_csv=request.segmentsCsv,
                start_times=request.startTimes
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid reportType. Must be 'density' or 'flow'")
        
        # Generate PDF
        pdf_path = generate_pdf_report(results, layout=request.layout)
        
        if pdf_path and os.path.exists(pdf_path):
            return JSONResponse(content={
                "success": True,
                "pdf_path": pdf_path,
                "message": f"PDF report generated successfully: {pdf_path}"
            })
        else:
            raise HTTPException(status_code=500, detail="PDF generation failed")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@app.get("/api/pdf-templates")
async def list_pdf_templates():
    """List available PDF templates."""
    try:
        from .pdf_generator import setup_pdf_templates
        
        templates = setup_pdf_templates()
        
        return JSONResponse(content={
            "templates": list(templates.keys()),
            "template_paths": templates
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@app.get("/api/pdf-status")
async def check_pdf_status():
    """Check PDF generation system status."""
    try:
        from .pdf_generator import validate_pandoc_installation
        
        pandoc_available = validate_pandoc_installation()
        
        return JSONResponse(content={
            "pandoc_available": pandoc_available,
            "pdf_generation_ready": pandoc_available,
            "message": "PDF generation ready" if pandoc_available else "Pandoc not installed"
        })
        
    except Exception as e:
        return JSONResponse(content={
            "pandoc_available": False,
            "pdf_generation_ready": False,
            "message": f"Error checking status: {str(e)}"
        })


def _find_latest_density_report_file(storage) -> Optional[Tuple[str, str]]:
    """Find the latest density report file from the last 7 days."""
    from datetime import timedelta
    from app.storage_service import get_storage_service
    
    all_files = []
    
    # Try to list files from the last few days to find the latest report
    for days_back in range(7):  # Check last 7 days
        check_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        
        # Check the reports folder structure (reports/YYYY-MM-DD/)
        reports_date_path = f"reports/{check_date}"
        files = storage._list_gcs_files(reports_date_path, "Density.md") if storage.config.use_cloud_storage else storage._list_local_files(reports_date_path, "Density.md")
        for file in files:
            all_files.append((check_date, file))
    
    if not all_files:
        return None
    
    # Sort by date and filename to get the latest
    return max(all_files, key=lambda x: (x[0], x[1]))


def _load_density_report_content(storage, latest_date: str, latest_filename: str) -> Optional[str]:
    """Load the latest density report content from storage."""
    content = storage._load_from_gcs(f"reports/{latest_date}/{latest_filename}") if storage.config.use_cloud_storage else storage._load_from_local(f"reports/{latest_date}/{latest_filename}")
    return content


def _parse_report_header(lines: List[str]) -> Tuple[int, int]:
    """Parse header info to extract total_segments and processed_segments."""
    total_segments = 0
    processed_segments = 0
    
    for line in lines:
        if line.startswith('**Total Segments:**'):
            total_segments = int(line.split('**Total Segments:**')[1].strip())
        elif line.startswith('**Processed Segments:**'):
            processed_segments = int(line.split('**Processed Segments:**')[1].strip())
    
    return total_segments, processed_segments


def _parse_segment_metrics_from_line(
    line: str,
    current_segment: Optional[str],
    peak_areal_density: float,
    peak_flow_rate: float
) -> Tuple[float, float]:
    """Extract density and flow rate values from a line if present."""
    if not current_segment or '|' not in line:
        return peak_areal_density, peak_flow_rate
    
    parts = [p.strip() for p in line.split('|')]
    if len(parts) < 3:
        return peak_areal_density, peak_flow_rate
    
    # Look for density values in metrics tables
    if '| Density |' in line:
        try:
            density = float(parts[2])
            peak_areal_density = max(peak_areal_density, density)
        except ValueError:
            pass
    
    # Look for flow rate values
    if '| Flow Rate |' in line:
        try:
            flow_rate = float(parts[2])
            peak_flow_rate = max(peak_flow_rate, flow_rate)
        except ValueError:
            pass
    
    return peak_areal_density, peak_flow_rate


def _update_los_counts_and_critical(
    line: str,
    los_counts: Dict[str, int],
    critical_segments: int
) -> Tuple[Dict[str, int], int]:
    """Update LOS counts and critical segment count based on line content."""
    # Count critical segments from LOS indicators
    if '🟡' in line:
        los_counts['C'] = los_counts.get('C', 0) + 1
        los_counts['D'] = los_counts.get('D', 0) + 1
    
    if '🔴' in line:
        los_counts['E'] = los_counts.get('E', 0) + 1
        los_counts['F'] = los_counts.get('F', 0) + 1
        critical_segments += 1
    
    # Count supply > capacity warnings
    if 'Supply > Capacity' in line or 'risk of congestion' in line:
        critical_segments += 1
    
    return los_counts, critical_segments


def _calculate_overall_los(los_counts: Dict[str, int]) -> str:
    """Calculate overall LOS (most common) from LOS counts."""
    if los_counts:
        return max(los_counts.items(), key=lambda x: x[1])[0]
    return 'A'


def _extract_current_segment(line: str) -> Optional[str]:
    """Extract current segment ID from segment header line."""
    if line.startswith('### Segment ') and '—' in line:
        return line.split('—')[0].replace('### Segment ', '').strip()
    return None


def parse_latest_density_report():
    """Parse the latest density report to extract summary data without running new analysis."""
    from app.storage_service import get_storage_service
    
    # Use unified storage service that works in both local and Cloud Run
    storage = get_storage_service()
    
    try:
        # Find the latest density report file
        latest_file_info = _find_latest_density_report_file(storage)
        if not latest_file_info:
            return None
        
        latest_date, latest_filename = latest_file_info
        
        # Load the latest density report content
        content = _load_density_report_content(storage, latest_date, latest_filename)
        if not content:
            return None
        
        # Parse the report content
        lines = content.split('\n')
        
        # Parse header info
        total_segments, processed_segments = _parse_report_header(lines)
        
        # Parse individual segment sections to get actual density values
        current_segment = None
        los_counts = {}
        peak_areal_density = 0.0
        peak_flow_rate = 0.0
        critical_segments = 0
        
        for line in lines:
            # Look for segment headers like "### Segment A1 — Start to Queen/Regent"
            segment_id = _extract_current_segment(line)
            if segment_id:
                current_segment = segment_id
                continue
            
            # Extract density and flow rate from metrics tables
            peak_areal_density, peak_flow_rate = _parse_segment_metrics_from_line(
                line, current_segment, peak_areal_density, peak_flow_rate
            )
            
            # Update LOS counts and critical segment count
            los_counts, critical_segments = _update_los_counts_and_critical(
                line, los_counts, critical_segments
            )
        
        # Calculate overall LOS (most common)
        overall_los = _calculate_overall_los(los_counts)
        
        return {
            "total_segments": total_segments,
            "processed_segments": processed_segments,
            "peak_areal_density": peak_areal_density,
            "peak_flow_rate": peak_flow_rate,
            "critical_segments": critical_segments,
            "overall_los": overall_los
        }
        
    except Exception as e:
        print(f"Error parsing density report: {e}")
        return None

@app.get("/api/summary")
async def get_summary_data():
    """Generate summary.json for frontend dashboard using pre-existing analysis data."""
    try:
        # Try to parse the latest density report first
        report_data = parse_latest_density_report()
        
        # Debug: Log what we found
        print(f"DEBUG: parse_latest_density_report() returned: {report_data}")
        
        if report_data:
            # Use data from existing report
            summary_data = {
                "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
                "time_bin_s": 30,
                "totals": {
                    "segments": report_data["total_segments"],
                    "processed": report_data["processed_segments"],
                    "skipped": 0
                },
                "metrics": {
                    "peak_areal_density": round(report_data["peak_areal_density"], 2),
                    "peak_flow_rate": round(report_data["peak_flow_rate"], 1),
                    "critical_segments": report_data["critical_segments"],
                    "overall_los": report_data["overall_los"]
                }
            }
        else:
            # Fallback to hardcoded values if no report found
            summary_data = {
                "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
                "time_bin_s": 30,
                "totals": {
                    "segments": 22,
                    "processed": 22,
                    "skipped": 0
                },
                "metrics": {
                    "peak_areal_density": 0.85,
                    "peak_flow_rate": 12.4,
                    "critical_segments": 1,
                    "overall_los": "A"
                }
            }
        
        return JSONResponse(content=summary_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate summary data: {str(e)}")




@app.get("/api/reports")
async def get_reports_data():
    """Generate reports.json for frontend reports page."""
    try:
        # For now, return empty reports list
        # This will be implemented in Phase 3/4 with Cloud Storage integration
        reports_data = {
            "files": []
        }
        
        return JSONResponse(content=reports_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate reports data: {str(e)}")


@app.get("/frontend/data/summary.json")
async def serve_summary_json():
    """Serve summary.json for frontend."""
    return await get_summary_data()


def _load_tooltips_json():
    """Load operational intelligence from tooltips.json (Issue #237)."""
    try:
        from pathlib import Path
        import json
        
        # Try to find tooltips.json in latest report directory
        reports_dir = Path("reports")
        if not reports_dir.exists():
            return None
        
        # Check date directories (newest first)
        date_dirs = sorted([d for d in reports_dir.iterdir() if d.is_dir() and d.name.startswith("2025-")], reverse=True)
        
        for date_dir in date_dirs:
            tooltips_file = date_dir / "tooltips.json"
            if tooltips_file.exists():
                with open(tooltips_file, 'r') as f:
                    data = json.load(f)
                print(f"📊 Loaded operational intelligence from {tooltips_file}")
                return data
        
        print("⚠️ No tooltips.json found - operational intelligence not available")
        return None
        
    except Exception as e:
        print(f"⚠️ Error loading tooltips.json: {e}")
        return None


def _build_operational_intelligence_lookup(tooltips_data):
    """Build segment-level operational intelligence lookup from tooltips (Issue #237)."""
    if not tooltips_data or 'tooltips' not in tooltips_data:
        return {}
    
    tooltips = tooltips_data['tooltips']
    oi_by_segment = {}
    
    # Aggregate bin-level data to segment-level
    for tooltip in tooltips:
        seg_id = tooltip.get('segment_id')
        if not seg_id:
            continue
        
        if seg_id not in oi_by_segment:
            oi_by_segment[seg_id] = {
                'los': tooltip.get('los'),
                'los_description': tooltip.get('los_description'),
                'los_color': tooltip.get('los_color'),
                'severity': tooltip.get('severity', 'NONE'),
                'flag_reason': tooltip.get('flag_reason', 'NONE'),
                'flagged_bins_count': 0,
                'max_density': tooltip.get('density_peak', 0)
            }
        
        # Count flagged bins and track worst severity
        if tooltip.get('severity') and tooltip['severity'] != 'NONE':
            oi_by_segment[seg_id]['flagged_bins_count'] += 1
            
            # Track worst severity (CRITICAL > CAUTION > WATCH)
            current_severity = oi_by_segment[seg_id]['severity']
            new_severity = tooltip['severity']
            if new_severity == 'CRITICAL' or (new_severity == 'CAUTION' and current_severity == 'WATCH'):
                oi_by_segment[seg_id]['severity'] = new_severity
        
        # Track maximum density
        bin_density = tooltip.get('density_peak', 0)
        if bin_density > oi_by_segment[seg_id]['max_density']:
            oi_by_segment[seg_id]['max_density'] = bin_density
            oi_by_segment[seg_id]['los'] = tooltip.get('los')
            oi_by_segment[seg_id]['los_description'] = tooltip.get('los_description')
            oi_by_segment[seg_id]['los_color'] = tooltip.get('los_color')
    
    return oi_by_segment


def _get_los_color(los: str) -> str:
    """Get color for LOS level (Issue #237)."""
    colors = {
        'A': '#4CAF50',  # Green
        'B': '#8BC34A',  # Light green
        'C': '#FFC107',  # Amber
        'D': '#FF9800',  # Orange
        'E': '#FF5722',  # Red-orange
        'F': '#F44336'   # Red
    }
    return colors.get(los, '#9E9E9E')  # Grey for unknown


def parse_latest_density_report_segments():
    """Parse the latest density report to extract segment data without running new analysis."""
    import os
    import re
    from pathlib import Path
    from datetime import datetime
    from app.storage_service import get_storage_service
    
    # Use unified storage service that works in both local and Cloud Run
    storage = get_storage_service()
    
    # Find the latest density report
    try:
        # Get all available dates by listing files and extracting dates
        all_files = []
        
        # Try to list files from the last few days to find the latest report
        from datetime import timedelta
        for days_back in range(7):  # Check last 7 days
            check_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            
            # Files are saved directly in YYYY-MM-DD/ not reports/YYYY-MM-DD/
            files = storage._list_gcs_files(check_date, "Density.md") if storage.config.use_cloud_storage else storage._list_local_files(check_date, "Density.md")
            for file in files:
                all_files.append((check_date, file))
        
        if not all_files:
            return []
        
        # Sort by date and filename to get the latest
        latest_date, latest_filename = max(all_files, key=lambda x: (x[0], x[1]))
        
        # Load the latest density report content
        content = storage._load_from_gcs(f"{latest_date}/{latest_filename}") if storage.config.use_cloud_storage else storage._load_from_local(f"{latest_date}/{latest_filename}")
        if not content:
            return []
        
        # Parse the report content
        lines = content.split('\n')
        
        segments = []
        in_table = False
        
        for line in lines:
            if '| Segment | Label | Key Takeaway | LOS |' in line:
                in_table = True
                continue
            elif in_table and line.startswith('|') and '|' in line[1:]:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 5 and parts[1] != 'Segment' and not parts[1].startswith('-'):  # Skip header and separator rows
                    segment_id = parts[1]
                    segment_label = parts[2]
                    takeaway = parts[3]
                    los = parts[4].replace('🟢', '').replace('🟡', '').replace('🔴', '').strip()
                    
                    # Determine status based on LOS
                    if los in ['D', 'E', 'F']:
                        status = 'OVERLOAD'
                    elif los in ['B', 'C']:
                        status = 'MODERATE'
                    else:
                        status = 'STABLE'
                    
                    segments.append({
                        "id": segment_id,
                        "label": segment_label,
                        "los": los,
                        "status": status,
                        "notes": [takeaway]
                    })
            elif in_table and not line.startswith('|'):
                break
        
        return segments
        
    except Exception as e:
        print(f"Error parsing density report segments: {e}")
        return []

def _determine_los_from_density(peak_areal_density: float) -> str:
    """Determine LOS from peak areal density value."""
    if peak_areal_density < 0.5:
        return "A"
    elif peak_areal_density < 1.0:
        return "B"
    elif peak_areal_density < 1.5:
        return "C"
    elif peak_areal_density < 2.0:
        return "D"
    elif peak_areal_density < 3.0:
        return "E"
    else:
        return "F"


def _determine_status_from_los_and_severity(los: str, severity: str) -> str:
    """Determine status from LOS and severity."""
    if severity == 'CRITICAL':
        return "CRITICAL"
    elif severity in ['CAUTION', 'WATCH']:
        return "FLAGGED"
    elif los in ['E', 'F']:
        return "OVERLOAD"
    elif los in ['C', 'D']:
        return "MODERATE"
    else:
        return "STABLE"


def _load_segments_csv_dict() -> Dict[str, Dict[str, str]]:
    """Load segments CSV and return dictionary mapping seg_id to seg_label."""
    try:
        import pandas as pd
        segments_df = pd.read_csv("data/segments.csv")
        segments_dict = {}
        for _, row in segments_df.iterrows():
            segments_dict[row['seg_id']] = {
                'seg_label': row.get('seg_label', row['seg_id'])
            }
        return segments_dict
    except Exception as e:
        print(f"⚠️ Could not load segments CSV: {e}, using defaults")
        return {}


def _build_segment_from_canonical_data(
    segment_id: str,
    peak_data: Dict[str, Any],
    segment_info: Dict[str, str],
    oi: Dict[str, Any]
) -> Dict[str, Any]:
    """Build segment entry from canonical data with operational intelligence."""
    peak_areal_density = peak_data["peak_areal_density"]
    
    # Use LOS from operational intelligence if available, otherwise calculate
    los = oi.get('los') if oi.get('los') else _determine_los_from_density(peak_areal_density)
    
    # Determine status from LOS and severity
    severity = oi.get('severity', 'NONE')
    status = _determine_status_from_los_and_severity(los, severity)
    
    return {
        "id": segment_id,
        "label": segment_info.get('seg_label', segment_id),
        "los": los,
        "los_description": oi.get('los_description', ''),
        "los_color": oi.get('los_color', _get_los_color(los)),
        "status": status,
        "severity": severity,
        "flag_reason": oi.get('flag_reason', 'NONE'),
        "flagged_bins_count": oi.get('flagged_bins_count', 0),
        "notes": [f"Canonical segments: {peak_data['total_windows']} windows"],
        "peak_areal_density": peak_areal_density,
        "peak_mean_density": peak_data["peak_mean_density"],
        "source": "canonical_segments"
    }


def _load_canonical_segments_with_oi(tooltips_data) -> Optional[Dict[str, Any]]:
    """Load canonical segments with operational intelligence."""
    try:
        from .canonical_segments import (
            is_canonical_segments_available, get_segment_peak_densities,
            get_canonical_segments_metadata
        )
        
        if not is_canonical_segments_available():
            return None
        
        print("🎯 Issue #231: /api/segments using canonical segments as source of truth")
        
        # Get canonical segments data
        segment_peaks = get_segment_peak_densities()
        metadata = get_canonical_segments_metadata()
        
        # Load segments CSV for labels
        segments_dict = _load_segments_csv_dict()
        
        # Build operational intelligence lookup from tooltips
        oi_by_segment = _build_operational_intelligence_lookup(tooltips_data)
        
        # Build segments list from canonical data with operational intelligence
        segments = []
        for segment_id, peak_data in segment_peaks.items():
            segment_info = segments_dict.get(segment_id, {})
            oi = oi_by_segment.get(segment_id, {})
            segment = _build_segment_from_canonical_data(segment_id, peak_data, segment_info, oi)
            segments.append(segment)
        
        return {
            "ok": True,
            "segments": segments,
            "total": len(segments),
            "metadata": {
                "source": "canonical_segments",
                "methodology": "bottom_up_aggregation",
                "total_windows": metadata.get("total_windows", 0),
                "has_operational_intelligence": tooltips_data is not None
            }
        }
        
    except ImportError:
        print("⚠️ Canonical segments module not available, using legacy approach")
        return None
    except Exception as e:
        print(f"⚠️ Error using canonical segments: {e}, falling back to legacy approach")
        return None


def _load_fallback_segments_from_csv() -> Dict[str, Any]:
    """Load fallback segments from CSV when no analysis data available."""
    print("⚠️ No density report found, using segments CSV fallback")
    import pandas as pd
    segments_df = pd.read_csv("data/segments.csv")
    
    segments = []
    for _, row in segments_df.iterrows():
        segments.append({
            "id": row['seg_id'],
            "label": row['seg_label'],
            "los": "A",
            "status": "STABLE",
            "notes": ["No density analysis available"],
            "source": "segments_csv"
        })
    
    return {
        "ok": True,
        "segments": segments,
        "total": len(segments),
        "metadata": {"source": "segments_csv"}
    }


@app.get("/api/segments")
async def get_segments():
    """Get segments data for frontend dashboard with operational intelligence (Issue #237)."""
    try:
        # Issue #237: Load operational intelligence from tooltips.json
        tooltips_data = _load_tooltips_json()
        
        # Issue #231: Try canonical segments first (ChatGPT's roadmap)
        canonical_result = _load_canonical_segments_with_oi(tooltips_data)
        if canonical_result:
            return canonical_result
        
        # Legacy fallback: Try to parse the latest density report first
        print("📊 /api/segments using legacy density report parsing")
        segments = parse_latest_density_report_segments()
        
        if segments:
            # Use data from existing report
            return {
                "ok": True,
                "segments": segments,
                "total": len(segments),
                "metadata": {"source": "density_report"}
            }
        else:
            # Final fallback to hardcoded values if no report found
            return _load_fallback_segments_from_csv()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load segments data: {str(e)}")

@app.get("/frontend/data/segments.json")
async def serve_segments_json():
    """Serve segments.json for frontend."""
    return await get_segments()


@app.get("/api/tooltips")
async def get_tooltips():
    """Get operational intelligence tooltips for map integration (Issue #237)."""
    try:
        tooltips_data = _load_tooltips_json()
        
        if tooltips_data:
            return {
                "ok": True,
                "tooltips": tooltips_data.get('tooltips', []),
                "metadata": {
                    "generated": tooltips_data.get('generated'),
                    "schema_version": tooltips_data.get('schema_version'),
                    "density_method": tooltips_data.get('density_method'),
                    "total_bins": len(tooltips_data.get('tooltips', []))
                }
            }
        else:
            return {
                "ok": False,
                "error": "No operational intelligence data available",
                "tooltips": [],
                "metadata": {}
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load tooltips: {str(e)}")


@app.get("/frontend/data/reports.json")
async def serve_reports_json():
    """Serve reports.json for frontend."""
    return await get_reports_data()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
# Service account configuration update
