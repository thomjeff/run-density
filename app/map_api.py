"""
Map API Module

This module provides API endpoints specifically for map visualization
as outlined in Issue #146 technical implementation strategy.

Endpoints:
- /api/segments.geojson - GeoJSON data for map segments
- /api/flow-bins - Bin-level flow data for visualization
- /api/export-bins - CSV/GeoJSON export functionality
"""

from __future__ import annotations
import json
import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

try:
    from .bin_analysis import get_all_segment_bins, analyze_segment_bins, get_cache_stats
    from .geo_utils import generate_segments_geojson, generate_bins_geojson
    from .constants import DISTANCE_BIN_SIZE_KM
except ImportError:
    from bin_analysis import get_all_segment_bins, analyze_segment_bins, get_cache_stats
    from geo_utils import generate_segments_geojson, generate_bins_geojson
    from constants import DISTANCE_BIN_SIZE_KM

logger = logging.getLogger(__name__)

# Create router for map-specific endpoints
router = APIRouter(prefix="/api", tags=["map"])

class MapRequest(BaseModel):
    """Request model for map API endpoints."""
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    binSizeKm: Optional[float] = None

class FlowBinsRequest(BaseModel):
    """Request model for flow bins endpoint."""
    paceCsv: str
    segmentsCsv: str
    startTimes: Dict[str, int]
    segmentId: Optional[str] = None
    binSizeKm: Optional[float] = None

@router.get("/segments.geojson")
async def get_segments_geojson(
    paceCsv: str = Query(..., description="Path to pace data CSV"),
    segmentsCsv: str = Query(..., description="Path to segments data CSV"),
    startTimes: str = Query(..., description="JSON string of start times"),
    binSizeKm: Optional[float] = Query(None, description="Bin size in kilometers")
):
    """
    Get GeoJSON data for map segments with bin-level information.
    
    This endpoint provides the GeoJSON data needed for map visualization,
    including segment geometry and bin-level density/flow data.
    """
    try:
        # Parse start times
        start_times = json.loads(startTimes)
        
        # Use default bin size if not provided
        if binSizeKm is None:
            binSizeKm = DISTANCE_BIN_SIZE_KM
        
        # Get all segment bin data
        all_bins = get_all_segment_bins(
            pace_csv=paceCsv,
            segments_csv=segmentsCsv,
            start_times=start_times,
            bin_size_km=binSizeKm
        )
        
        # Generate GeoJSON
        geojson = generate_segments_geojson(all_bins)
        
        return JSONResponse(content=geojson)
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid startTimes JSON: {e}")
    except Exception as e:
        logger.error(f"Error generating segments GeoJSON: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating segments GeoJSON: {e}")

@router.post("/flow-bins")
async def get_flow_bins(request: FlowBinsRequest):
    """
    Get bin-level flow data for visualization.
    
    This endpoint provides detailed bin-level data including:
    - Density metrics per bin
    - Overtake counts per bin
    - Co-presence data per bin
    - RSI scores and convergence points
    """
    try:
        if request.segmentId:
            # Get data for specific segment
            segment_bins = analyze_segment_bins(
                segment_id=request.segmentId,
                pace_csv=request.paceCsv,
                segments_csv=request.segmentsCsv,
                start_times=request.startTimes,
                bin_size_km=request.binSizeKm
            )
            
            # Convert to API response format
            bins_data = []
            for bin_data in segment_bins.bins:
                bins_data.append({
                    "bin_index": bin_data.bin_index,
                    "start_km": bin_data.start_km,
                    "end_km": bin_data.end_km,
                    "density": bin_data.density,
                    "density_level": bin_data.density_level,
                    "overtakes": bin_data.overtakes,
                    "co_presence": bin_data.co_presence,
                    "rsi_score": bin_data.rsi_score,
                    "convergence_point": bin_data.convergence_point,
                    "centroid_lat": bin_data.centroid_lat,
                    "centroid_lon": bin_data.centroid_lon
                })
            
            return JSONResponse(content={
                "ok": True,
                "segment_id": request.segmentId,
                "segment_label": segment_bins.segment_label,
                "bins": bins_data,
                "total_bins": segment_bins.total_bins,
                "bin_size_m": segment_bins.bin_size_m,
                "generated_at": segment_bins.generated_at.isoformat()
            })
        else:
            # Get data for all segments
            all_bins = get_all_segment_bins(
                pace_csv=request.paceCsv,
                segments_csv=request.segmentsCsv,
                start_times=request.startTimes,
                bin_size_km=request.binSizeKm
            )
            
            # Convert to API response format
            segments_data = {}
            for segment_id, segment_bins in all_bins.items():
                bins_data = []
                for bin_data in segment_bins.bins:
                    bins_data.append({
                        "bin_index": bin_data.bin_index,
                        "start_km": bin_data.start_km,
                        "end_km": bin_data.end_km,
                        "density": bin_data.density,
                        "density_level": bin_data.density_level,
                        "overtakes": bin_data.overtakes,
                        "co_presence": bin_data.co_presence,
                        "rsi_score": bin_data.rsi_score,
                        "convergence_point": bin_data.convergence_point,
                        "centroid_lat": bin_data.centroid_lat,
                        "centroid_lon": bin_data.centroid_lon
                    })
                
                segments_data[segment_id] = {
                    "segment_label": segment_bins.segment_label,
                    "bins": bins_data,
                    "total_bins": segment_bins.total_bins,
                    "bin_size_m": segment_bins.bin_size_m,
                    "generated_at": segment_bins.generated_at.isoformat()
                }
            
            return JSONResponse(content={
                "ok": True,
                "segments": segments_data,
                "total_segments": len(segments_data)
            })
            
    except Exception as e:
        logger.error(f"Error getting flow bins: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting flow bins: {e}")

@router.post("/export-bins")
async def export_bins(
    request: MapRequest,
    format: str = Query("csv", description="Export format: csv or geojson")
):
    """
    Export bin-level data in CSV or GeoJSON format.
    
    This endpoint provides export functionality for bin-level data
    as specified in Issue #146 acceptance criteria.
    """
    try:
        # Get all segment bin data
        all_bins = get_all_segment_bins(
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            bin_size_km=request.binSizeKm
        )
        
        if format.lower() == "geojson":
            # Generate GeoJSON export
            geojson = generate_bins_geojson(all_bins)
            return JSONResponse(content=geojson)
        else:
            # Generate CSV export
            csv_data = []
            for segment_id, segment_bins in all_bins.items():
                for bin_data in segment_bins.bins:
                    # Flatten overtakes and co-presence data
                    overtakes_str = "; ".join([f"{k}:{v}" for k, v in bin_data.overtakes.items()])
                    co_presence_str = "; ".join([f"{k}:{v}" for k, v in bin_data.co_presence.items()])
                    
                    csv_data.append({
                        "segment_id": segment_id,
                        "bin_index": bin_data.bin_index,
                        "start_f": bin_data.start_km,
                        "end_f": bin_data.end_km,
                        "density": bin_data.density,
                        "overtakes": overtakes_str,
                        "co_presence": co_presence_str,
                        "rsi": bin_data.rsi_score,
                        "convergence_point": bin_data.convergence_point
                    })
            
            return JSONResponse(content={
                "ok": True,
                "format": "csv",
                "data": csv_data,
                "total_records": len(csv_data)
            })
            
    except Exception as e:
        logger.error(f"Error exporting bins: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting bins: {e}")

@router.get("/map-status")
async def get_map_status():
    """
    Get map system status and cache information.
    
    This endpoint provides status information for the map system,
    including cache statistics and system health.
    """
    try:
        cache_stats = get_cache_stats()
        
        return JSONResponse(content={
            "ok": True,
            "status": "healthy",
            "cache_stats": cache_stats,
            "bin_size_km": DISTANCE_BIN_SIZE_KM,
            "endpoints": [
                "/api/segments.geojson",
                "/api/flow-bins", 
                "/api/export-bins",
                "/api/map-status"
            ]
        })
        
    except Exception as e:
        logger.error(f"Error getting map status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map status: {e}")

@router.post("/clear-cache")
async def clear_map_cache():
    """
    Clear the map data cache.
    
    This endpoint clears all cached bin-level data to force
    fresh computation on next request.
    """
    try:
        from .bin_analysis import clear_bin_cache
        clear_bin_cache()
        
        return JSONResponse(content={
            "ok": True,
            "message": "Map cache cleared successfully"
        })
        
    except Exception as e:
        logger.error(f"Error clearing map cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing map cache: {e}")
