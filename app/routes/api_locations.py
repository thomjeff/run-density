"""
API Routes for Locations Report (Issue #277)

Provides endpoints for location report generation and retrieval.

Author: Cursor AI Assistant
Epic: Issue #277
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any, Optional
import logging
import os
from pathlib import Path

from app.location_report import generate_location_report
from app.utils.constants import DEFAULT_START_TIMES
from app.utils.run_id import get_latest_run_id
from app.storage import create_runflow_storage

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/api/locations")
async def get_locations_report(
    run_id: Optional[str] = Query(None, description="Run ID for runflow structure"),
    generate: bool = Query(False, description="Generate new report if not exists")
) -> JSONResponse:
    """
    Get locations report data.
    
    Issue #277: Returns location report as JSON.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        generate: Whether to generate report if not found
        
    Returns:
        JSON response with location report data
    """
    try:
        # Get run_id (use latest if not provided)
        if not run_id:
            run_id = get_latest_run_id()
        
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id parameter."
            )
        
        storage = create_runflow_storage(run_id)
        
        # Try to load existing report
        report_path = f"reports/Locations.csv"
        
        # Check if CSV exists
        if storage.exists(report_path):
            # Read CSV and convert to JSON
            import pandas as pd
            import io
            import numpy as np
            csv_data = storage.read_text(report_path)
            df = pd.read_csv(io.StringIO(csv_data))
            # Replace NaN/Inf values with None for JSON serialization
            df = df.replace([np.nan, np.inf, -np.inf], None)
            report_data = df.to_dict('records')
        elif generate:
            # Generate new report
            logger.info(f"Generating locations report for run_id={run_id}")
            result = generate_location_report(
                locations_csv="data/locations.csv",
                runners_csv="data/runners.csv",
                segments_csv="data/segments.csv",
                start_times=DEFAULT_START_TIMES,
                run_id=run_id
            )
            
            if not result.get("ok"):
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate report: {result.get('error', 'Unknown error')}"
                )
            
            # Read the generated CSV
            if storage.exists(report_path):
                import pandas as pd
                import io
                csv_data = storage.read_text(report_path)
                df = pd.read_csv(io.StringIO(csv_data))
                report_data = df.to_dict('records')
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Report generated but file not found"
                )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Locations report not found for run_id={run_id}. Use ?generate=true to create it."
            )
        
        return JSONResponse(content={
            "ok": True,
            "run_id": run_id,
            "locations": report_data,
            "count": len(report_data) if report_data else 0
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving locations report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/api/locations/generate")
async def generate_locations_report(
    run_id: Optional[str] = Query(None, description="Run ID for runflow structure")
) -> JSONResponse:
    """
    Generate locations report.
    
    Issue #277: Forces generation of a new locations report.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        
    Returns:
        JSON response with generation result
    """
    try:
        # Get run_id (use latest if not provided)
        if not run_id:
            run_id = get_latest_run_id()
        
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id parameter."
            )
        
        logger.info(f"Generating locations report for run_id={run_id}")
        
        result = generate_location_report(
            locations_csv="data/locations.csv",
            runners_csv="data/runners.csv",
            segments_csv="data/segments.csv",
            start_times=DEFAULT_START_TIMES,
            run_id=run_id
        )
        
        if not result.get("ok"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate report: {result.get('error', 'Unknown error')}"
            )
        
        return JSONResponse(content={
            "ok": True,
            "run_id": run_id,
            "file_path": result.get("file_path"),
            "locations_processed": result.get("locations_processed", 0),
            "message": "Locations report generated successfully"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating locations report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/api/locations/csv")
async def get_locations_csv(
    run_id: Optional[str] = Query(None, description="Run ID for runflow structure")
) -> FileResponse:
    """
    Download locations report as CSV.
    
    Issue #277: Serves the locations report CSV file.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        
    Returns:
        CSV file response
    """
    try:
        # Get run_id (use latest if not provided)
        if not run_id:
            run_id = get_latest_run_id()
        
        if not run_id:
            raise HTTPException(
                status_code=404,
                detail="No run ID available. Run analysis first or provide run_id parameter."
            )
        
        storage = create_runflow_storage(run_id)
        report_path = f"reports/Locations.csv"
        
        if not storage.exists(report_path):
            raise HTTPException(
                status_code=404,
                detail=f"Locations report not found for run_id={run_id}"
            )
        
        # Get full file path using internal method
        file_path = storage._full_local(report_path)
        
        return FileResponse(
            str(file_path),
            filename="Locations.csv",
            media_type="text/csv"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving locations CSV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

