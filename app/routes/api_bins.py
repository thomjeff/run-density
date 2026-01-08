"""
API Routes for Bin-Level Data (RF-FE-002)

Provides bin-level density and flow metrics from bins.parquet.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #318 | Step: 3
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging
# Phase 3 cleanup: Removed unused datetime import (only used by removed format_time_for_display)
# Phase 3 cleanup: Removed unused pandas import (not used in this file)

# Issue #466 Step 2: Storage consolidated to app.storage

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage singleton (not needed)


# Phase 3 cleanup: Removed unused function format_time_for_display() - never called

def load_bins_data(run_id: Optional[str] = None, day: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load bin-level data from bin_summary.json artifact.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped paths
    
    Returns:
        List of flagged bin records with formatted data for frontend display
        
    Raises:
        HTTPException: If data cannot be loaded
    """
    try:
        import json
        
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        if not run_id:
            run_id = get_latest_run_id()
        
        storage = create_runflow_storage(run_id)
        
        # Resolve day for day-scoped paths
        if day:
            selected_day, _ = resolve_selected_day(run_id, day)
            bin_summary_path = f"{selected_day}/bins/bin_summary.json"
        else:
            bin_summary_path = "bins/bin_summary.json"
        
        # Load bin_summary.json from day-scoped path
        bin_summary_data = storage.read_json(bin_summary_path)
        
        if not bin_summary_data or "segments" not in bin_summary_data:
            logger.warning("bin_summary.json is empty or not found")
            return []
        
        # Extract all flagged bins from all segments
        bins_data = []
        for segment_id, segment_data in bin_summary_data["segments"].items():
            for bin_data in segment_data.get("bins", []):
                bin_record = {
                    "segment_id": segment_id,
                    "start_km": float(bin_data.get("start_km", 0.0)),
                    "end_km": float(bin_data.get("end_km", 0.0)),
                    "t_start": bin_data.get("start_time", ""),
                    "t_end": bin_data.get("end_time", ""),
                    "density": float(bin_data.get("density", 0.0)),
                    "rate": float(bin_data.get("rate", 0.0)),
                    "los_class": str(bin_data.get("los_class", "Unknown")),
                    "flag": bin_data.get("flag", "flagged")
                }
                bins_data.append(bin_record)
        
        logger.info(f"Loaded {len(bins_data)} flagged bin records from bin_summary.json")
        return bins_data
        
    except Exception as e:
        logger.error(f"Failed to load bins data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load bin-level data: {str(e)}"
        )


@router.get("/api/bins")
async def get_bins_data(
    segment_id: Optional[str] = Query(None, description="Filter by segment ID"),
    los_class: Optional[str] = Query(None, description="Filter by LOS class"),
    limit: int = Query(1000, description="Maximum number of records to return", ge=1, le=50000),
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get bin-level density and flow data.
    
    Args:
        segment_id: Optional filter by segment ID
        los_class: Optional filter by LOS class (A, B, C, D, E, F)
        limit: Maximum number of records to return (default: 1000, max: 50000)
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped data
        
    Returns:
        JSON response with bin data and metadata
    """
    try:
        # Load all bin data (day-scoped)
        bins_data = load_bins_data(run_id, day)
        
        if not bins_data:
            return JSONResponse({
                "bins": [],
                "total_count": 0,
                "filtered_count": 0,
                "message": "No bin data available"
            })
        
        # Apply filters
        filtered_data = bins_data
        
        if segment_id:
            filtered_data = [bin_record for bin_record in filtered_data 
                           if segment_id.lower() in bin_record["segment_id"].lower()]
        
        if los_class:
            filtered_data = [bin_record for bin_record in filtered_data 
                           if bin_record["los_class"] == los_class.upper()]
        
        # Apply limit
        if len(filtered_data) > limit:
            filtered_data = filtered_data[:limit]
        
        # Prepare response
        response_data = {
            "bins": filtered_data,
            "total_count": len(bins_data),
            "filtered_count": len(filtered_data),
            "filters": {
                "segment_id": segment_id,
                "los_class": los_class,
                "limit": limit
            }
        }
        
        logger.info(f"Returning {len(filtered_data)} bin records (filtered from {len(bins_data)} total)")
        return JSONResponse(response_data)
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_bins_data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Phase 3 cleanup: Removed unused GET /api/bins/summary endpoint (~60 lines)
# - Not called by frontend (frontend/templates/pages/density.html only uses /api/bins)
# - Not called by E2E tests
# - Summary statistics can be calculated client-side from /api/bins response if needed
