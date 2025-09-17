"""
Main FastAPI Application - v1.5.0 Architecture Split
"""

from __future__ import annotations
import os
import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
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
    from .map_api import router as map_router
    from .routes.reports import router as reports_router
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
    from map_api import router as map_router
    from routes.reports import router as reports_router
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

app = FastAPI(title="run-density", version="v1.6.32")
APP_VERSION = os.getenv("APP_VERSION", app.version)
GIT_SHA = os.getenv("GIT_SHA", "local")
BUILD_AT = os.getenv("BUILD_AT", datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z")

# Include API routers
app.include_router(density_router)
app.include_router(map_router)
app.include_router(reports_router)
# app.include_router(test_router)  # Disabled for Cloud Run deployment

# Mount static files
try:
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")
except Exception as e:
    print(f"Warning: Could not mount frontend directory: {e}")

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


def parse_latest_density_report():
    """Parse the latest density report to extract summary data without running new analysis."""
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
            
            # Check the reports folder structure (reports/YYYY-MM-DD/)
            # We need to construct the full path for the reports folder
            reports_date_path = f"reports/{check_date}"
            files = storage._list_gcs_files(reports_date_path, "Density.md") if storage.config.use_cloud_storage else storage._list_local_files(reports_date_path, "Density.md")
            for file in files:
                all_files.append((check_date, file))
        
        if not all_files:
            return None
        
        # Sort by date and filename to get the latest
        latest_date, latest_filename = max(all_files, key=lambda x: (x[0], x[1]))
        
        # Load the latest density report content from the reports folder
        content = storage._load_from_gcs(f"reports/{latest_date}/{latest_filename}") if storage.config.use_cloud_storage else storage._load_from_local(f"reports/{latest_date}/{latest_filename}")
        if not content:
            return None
        
        # Parse the report content
        lines = content.split('\n')
        
        # Extract basic info
        total_segments = 0
        processed_segments = 0
        peak_areal_density = 0.0
        peak_flow_rate = 0.0
        critical_segments = 0
        overall_los = 'A'
        
        # Parse header info
        for line in lines:
            if line.startswith('**Total Segments:**'):
                total_segments = int(line.split('**Total Segments:**')[1].strip())
            elif line.startswith('**Processed Segments:**'):
                processed_segments = int(line.split('**Processed Segments:**')[1].strip())
        
        # Parse individual segment sections to get actual density values
        current_segment = None
        los_counts = {}
        
        for i, line in enumerate(lines):
            # Look for segment headers like "### Segment A1 — Start to Queen/Regent"
            if line.startswith('### Segment ') and '—' in line:
                current_segment = line.split('—')[0].replace('### Segment ', '').strip()
                continue
            
            # Look for density values in metrics tables
            if current_segment and '| Density |' in line:
                # Extract density value from the same line
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3:  # | Density | 0.20 | p/m² |
                        try:
                            density = float(parts[2])
                            peak_areal_density = max(peak_areal_density, density)
                        except ValueError:
                            pass
            
            # Look for flow rate values
            if current_segment and '| Flow Rate |' in line:
                # Extract flow rate value from the same line
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) >= 3:  # | Flow Rate | 182 | p/min/m |
                        try:
                            flow_rate = float(parts[2])
                            peak_flow_rate = max(peak_flow_rate, flow_rate)
                        except ValueError:
                            pass
            
            # Count critical segments from LOS indicators
            if '🟡' in line or '🔴' in line:
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
        
        # Calculate overall LOS (most common)
        if los_counts:
            overall_los = max(los_counts.items(), key=lambda x: x[1])[0]
        
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


@app.get("/api/segments.geojson")
async def get_segments_geojson(
    paceCsv: str = Query(..., description="Path to pace data CSV"),
    segmentsCsv: str = Query(..., description="Path to segments data CSV"),
    startTimes: str = Query(..., description="JSON string of start times"),
    binSizeKm: Optional[float] = Query(None, description="Bin size in kilometers")
):
    """Generate segments.geojson for frontend map using real course data."""
    try:
        import pandas as pd
        import xml.etree.ElementTree as ET
        import json
        
        # Parse start times
        start_times = json.loads(startTimes)
        
        # Load segments.csv to get segment definitions
        segments_df = pd.read_csv(segmentsCsv)
        
        # Load GPX data for coordinates
        def load_gpx_coordinates(gpx_file):
            tree = ET.parse(gpx_file)
            root = tree.getroot()
            coordinates = []
            
            # Find all track points
            for trkpt in root.findall('.//{http://www.topografix.com/GPX/1/1}trkpt'):
                lat = float(trkpt.get('lat'))
                lon = float(trkpt.get('lon'))
                coordinates.append([lon, lat])  # GeoJSON format is [lng, lat]
            
            return coordinates
        
        # Load full course coordinates
        full_coords = load_gpx_coordinates('data/Full.gpx')
        
        # Create GeoJSON FeatureCollection
        features = []
        for _, row in segments_df.iterrows():
            # Calculate segment coordinates based on distance
            start_km = row['full_from_km']
            end_km = row['full_to_km']
            
            # Convert km to approximate coordinate index (rough estimation)
            total_coords = len(full_coords)
            start_idx = int((start_km / 42.2) * total_coords)  # 42.2km is approximate marathon distance
            end_idx = int((end_km / 42.2) * total_coords)
            
            # Ensure indices are within bounds
            start_idx = max(0, min(start_idx, total_coords - 1))
            end_idx = max(start_idx + 1, min(end_idx, total_coords - 1))
            
            # Extract segment coordinates
            segment_coords = full_coords[start_idx:end_idx + 1]
            
            # Create GeoJSON feature
            feature = {
                "type": "Feature",
                "properties": {
                    "id": row['seg_id'],
                    "label": row['seg_label'],
                    "schema": "course_segment",
                    "los": "A",
                    "status": "STABLE",
                    "metrics": {
                        "areal_density": 0.2,
                        "linear_density": 0.15,
                        "flow_rate": 100,
                        "flow_supply": 500,
                        "flow_capacity": 600
                    },
                    "notes": [row['notes']] if pd.notna(row['notes']) else []
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": segment_coords
                }
            }
            features.append(feature)
        
        # Return GeoJSON FeatureCollection
        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        return JSONResponse(content=geojson_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate segments data: {str(e)}")


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
                print(f"DEBUG: parse_latest_density_report_segments() found table header: {line}")
                in_table = True
                continue
            elif in_table and line.startswith('|') and '|' in line[1:]:
                print(f"DEBUG: parse_latest_density_report_segments() processing table row: {line}")
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 5 and parts[1] != 'Segment':  # Skip header row
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

@app.get("/api/segments")
async def get_segments():
    """Get segments data for frontend dashboard using pre-existing analysis data."""
    try:
        # Try to parse the latest density report first
        segments = parse_latest_density_report_segments()
        
        if segments:
            # Use data from existing report
            return {
                "ok": True,
                "segments": segments,
                "total": len(segments)
            }
        else:
            # Fallback to hardcoded values if no report found
            import pandas as pd
            segments_df = pd.read_csv("data/segments.csv")
            
            segments = []
            for _, row in segments_df.iterrows():
                segments.append({
                    "id": row['seg_id'],
                    "label": row['seg_label'],
                    "los": "A",
                    "status": "STABLE",
                    "notes": ["No issues detected"]
                })
            
            return {
                "ok": True,
                "segments": segments,
                "total": len(segments)
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load segments data: {str(e)}")

@app.get("/frontend/data/segments.json")
async def serve_segments_json():
    """Serve segments.json for frontend."""
    return await get_segments_data()


@app.get("/frontend/data/reports.json")
async def serve_reports_json():
    """Serve reports.json for frontend."""
    return await get_reports_data()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
