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
import pandas as pd
from datetime import datetime

from app.storage_service import get_storage_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage service
storage = get_storage_service()


def format_time_for_display(iso_string: str) -> str:
    """
    Convert ISO timestamp to HH:MM format for display.
    
    Args:
        iso_string: ISO timestamp string (e.g., "2025-10-23T07:00:00Z")
        
    Returns:
        str: Formatted time string (e.g., "07:00")
    """
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%H:%M')
    except Exception as e:
        logger.warning(f"Failed to format time '{iso_string}': {e}")
        return iso_string


def load_bins_data() -> List[Dict[str, Any]]:
    """
    Load bin-level data from bins.parquet via StorageService.
    
    Returns:
        List of bin records with formatted data for frontend display
        
    Raises:
        HTTPException: If data cannot be loaded
    """
    try:
        # Get the latest run ID and construct the path
        run_id = storage.get_latest_run_id()
        bins_path = f"reports/{run_id}/bins.parquet"
        
        # Load bins.parquet from storage service
        bins_df = storage.read_parquet(bins_path)
        
        if bins_df is None or bins_df.empty:
            logger.warning("bins.parquet is empty or not found")
            return []
        
        # Convert to list of dictionaries with formatted data
        bins_data = []
        for _, row in bins_df.iterrows():
            bin_record = {
                "segment_id": str(row.get("segment_id", "")),
                "start_km": float(row.get("start_km", 0.0)),
                "end_km": float(row.get("end_km", 0.0)),
                "t_start": format_time_for_display(str(row.get("t_start", ""))),
                "t_end": format_time_for_display(str(row.get("t_end", ""))),
                "density": float(row.get("density", 0.0)),
                "rate": float(row.get("rate", 0.0)),
                "los_class": str(row.get("los_class", "Unknown"))
            }
            bins_data.append(bin_record)
        
        logger.info(f"Loaded {len(bins_data)} bin records from bins.parquet")
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
    limit: int = Query(1000, description="Maximum number of records to return", ge=1, le=50000)
):
    """
    Get bin-level density and flow data.
    
    Args:
        segment_id: Optional filter by segment ID
        los_class: Optional filter by LOS class (A, B, C, D, E, F)
        limit: Maximum number of records to return (default: 1000, max: 50000)
        
    Returns:
        JSON response with bin data and metadata
    """
    try:
        # Load all bin data
        bins_data = load_bins_data()
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_bins_data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/api/bins/summary")
async def get_bins_summary():
    """
    Get summary statistics for bin-level data.
    
    Returns:
        JSON response with summary statistics
    """
    try:
        bins_data = load_bins_data()
        
        if not bins_data:
            return JSONResponse({
                "total_bins": 0,
                "segments": [],
                "los_distribution": {},
                "message": "No bin data available"
            })
        
        # Calculate summary statistics
        total_bins = len(bins_data)
        
        # Get unique segments
        segments = list(set(bin_record["segment_id"] for bin_record in bins_data))
        segments.sort()
        
        # Calculate LOS distribution
        los_distribution = {}
        for bin_record in bins_data:
            los = bin_record["los_class"]
            los_distribution[los] = los_distribution.get(los, 0) + 1
        
        # Calculate density and rate statistics
        densities = [bin_record["density"] for bin_record in bins_data]
        rates = [bin_record["rate"] for bin_record in bins_data]
        
        summary = {
            "total_bins": total_bins,
            "segments": segments,
            "los_distribution": los_distribution,
            "density_stats": {
                "min": min(densities) if densities else 0,
                "max": max(densities) if densities else 0,
                "avg": sum(densities) / len(densities) if densities else 0
            },
            "rate_stats": {
                "min": min(rates) if rates else 0,
                "max": max(rates) if rates else 0,
                "avg": sum(rates) / len(rates) if rates else 0
            }
        }
        
        logger.info(f"Generated summary for {total_bins} bins across {len(segments)} segments")
        return JSONResponse(summary)
        
    except Exception as e:
        logger.error(f"Failed to generate bins summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )
