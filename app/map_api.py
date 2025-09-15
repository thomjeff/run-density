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
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

try:
    from .bin_analysis import get_all_segment_bins, analyze_segment_bins, get_cache_stats
    from .geo_utils import generate_segments_geojson, generate_bins_geojson
    from .constants import DISTANCE_BIN_SIZE_KM
    from .cache_manager import get_global_cache_manager
    from .map_data_generator import find_latest_reports
except ImportError:
    from bin_analysis import get_all_segment_bins, analyze_segment_bins, get_cache_stats
    from geo_utils import generate_segments_geojson, generate_bins_geojson
    from constants import DISTANCE_BIN_SIZE_KM
    from cache_manager import get_global_cache_manager
    from map_data_generator import find_latest_reports

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


@router.get("/bins-data")
async def get_bins_data(
    forceRefresh: bool = Query(False, description="Force refresh by running new analysis")
):
    """
    Get bin-level visualization data for map display.
    
    This endpoint provides bin-level data for the map visualization:
    - Uses existing analysis data if available and forceRefresh=False
    - Runs new bin analysis if no data found or forceRefresh=True
    - Returns GeoJSON data for bin-level visualization
    """
    try:
        if forceRefresh:
            logger.info("Force refresh requested - running new bin analysis")
            # Use default data paths and start times
            pace_csv = "data/runners.csv"
            segments_csv = "data/segments.csv"
            start_times = {"Full": 420, "10K": 440, "Half": 460}
            
            # Run new bin analysis
            all_bins = get_all_segment_bins(
                pace_csv=pace_csv,
                segments_csv=segments_csv,
                start_times=start_times
            )
            
            # Generate GeoJSON
            geojson = generate_bins_geojson(all_bins)
            
            return JSONResponse(content={
                "ok": True,
                "source": "bin_analysis",
                "timestamp": datetime.now().isoformat(),
                "geojson": geojson,
                "metadata": {
                    "total_segments": len(all_bins),
                    "analysis_type": "bins",
                    "bin_size_km": DISTANCE_BIN_SIZE_KM
                }
            })
        else:
            # Try to load existing bin data from reports
            try:
                from .map_data_generator import find_latest_bin_dataset
                bin_data = find_latest_bin_dataset()
                
                if bin_data and bin_data.get('ok'):
                    logger.info("Using existing bin data from reports")
                    return JSONResponse(content=bin_data)
                else:
                    logger.info("No existing bin data found - returning empty data")
                    return JSONResponse(content={
                        "ok": True,
                        "source": "placeholder",
                        "timestamp": datetime.now().isoformat(),
                        "geojson": {
                            "type": "FeatureCollection",
                            "features": []
                        },
                        "metadata": {
                            "total_segments": 0,
                            "analysis_type": "bins",
                            "bin_size_km": DISTANCE_BIN_SIZE_KM,
                            "message": "No bin data available - run analysis first"
                        }
                    })
            except Exception as e:
                logger.warning(f"Error loading bin data: {e}")
                return JSONResponse(content={
                    "ok": True,
                    "source": "placeholder",
                    "timestamp": datetime.now().isoformat(),
                    "geojson": {
                        "type": "FeatureCollection",
                        "features": []
                    },
                    "metadata": {
                        "total_segments": 0,
                        "analysis_type": "bins",
                        "bin_size_km": DISTANCE_BIN_SIZE_KM,
                        "message": "Error loading bin data"
                    }
                })
        
    except Exception as e:
        logger.error(f"Error getting bins data: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting bins data: {e}")

@router.get("/segments.geojson")
async def get_segments_geojson(
    paceCsv: str = Query(..., description="Path to pace data CSV"),
    segmentsCsv: str = Query(..., description="Path to segments data CSV"),
    startTimes: str = Query(..., description="JSON string of start times"),
    binSizeKm: Optional[float] = Query(None, description="Bin size in kilometers")
):
    """
    Get GeoJSON data for map segments with real GPS coordinates from GPX files.
    
    This endpoint provides segment geometry for map visualization using actual
    race course coordinates from GPX files.
    """
    try:
        # Parse start times
        start_times = json.loads(startTimes)
        
        # Load segments data
        from .io.loader import load_segments
        segments_data = load_segments(segmentsCsv)
        
        # Load GPX courses for real coordinates
        from .gpx_processor import load_all_courses, generate_segment_coordinates
        
        # Load all GPX courses
        courses = load_all_courses("data")
        
        # Convert segments to list of dicts for GPX processing
        # Use the same logic as the bin analysis to determine which event each segment belongs to
        segments_list = []
        for _, segment in segments_data.iterrows():
            segments_list.append({
                "seg_id": segment['seg_id'],
                "segment_label": segment.get('seg_label', segment['seg_id']),
                # Include all event flags and distance fields for proper event selection
                "10K": segment.get('10K', 'n'),
                "half": segment.get('half', 'n'),
                "full": segment.get('full', 'n'),
                "10K_from_km": segment.get('10K_from_km'),
                "10K_to_km": segment.get('10K_to_km'),
                "half_from_km": segment.get('half_from_km'),
                "half_to_km": segment.get('half_to_km'),
                "full_from_km": segment.get('full_from_km'),
                "full_to_km": segment.get('full_to_km')
            })
        
        # Generate real coordinates from GPX data
        segments_with_coords = generate_segment_coordinates(courses, segments_list)
        
        # Create GeoJSON features
        geojson = {
            "type": "FeatureCollection",
            "features": []
        }
        
        for segment_coords in segments_with_coords:
            # Use real coordinates if available, otherwise fallback
            if segment_coords.get('line_coords') and not segment_coords.get('coord_issue'):
                # Convert tuples to lists for GeoJSON format
                coordinates = [list(coord) for coord in segment_coords['line_coords']]
            else:
                # Fallback to placeholder coordinates
                coordinates = [
                    [-66.6, 45.9],  # Fredericton area
                    [-66.5, 45.9]
                ]
            
            feature = {
                "type": "Feature",
                "properties": {
                    "segment_id": segment_coords['seg_id'],
                    "seg_label": segment_coords['segment_label'],
                    "from_km": segment_coords['from_km'],
                    "to_km": segment_coords['to_km'],
                    "width_m": 5.0,  # Default width
                    "flow_type": "none",  # Default flow type
                    "zone": "green",  # Default zone
                    "coord_issue": segment_coords.get('coord_issue', False),
                    "course": segment_coords.get('course', 'Full')
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates
                }
            }
            geojson["features"].append(feature)
        
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

@router.post("/historical-trends")
async def get_historical_trends(request: MapRequest):
    """
    Get historical trends analysis for a segment.
    
    This endpoint provides historical analysis capabilities for understanding
    how bin-level data changes over time or across different scenarios.
    """
    try:
        from .bin_analysis import analyze_historical_trends
        
        # Get segment ID from request (assuming it's in the request body)
        segment_id = getattr(request, 'segmentId', None)
        if not segment_id:
            raise HTTPException(status_code=400, detail="segmentId is required")
        
        trends = analyze_historical_trends(
            segment_id=segment_id,
            pace_csv=request.paceCsv,
            segments_csv=request.segmentsCsv,
            start_times=request.startTimes,
            bin_size_km=request.binSizeKm
        )
        
        return JSONResponse(content=trends)
        
    except Exception as e:
        logger.error(f"Error getting historical trends: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting historical trends: {e}")

@router.post("/compare-segments")
async def compare_segments(request: dict):
    """
    Compare bin-level data across multiple segments.
    
    This endpoint provides comparative analysis capabilities for understanding
    how different segments perform relative to each other.
    """
    try:
        from .bin_analysis import compare_segments
        
        segment_ids = request.get('segmentIds', [])
        if len(segment_ids) < 2:
            raise HTTPException(status_code=400, detail="At least 2 segment IDs required")
        
        comparison = compare_segments(
            segment_ids=segment_ids,
            pace_csv=request.get('paceCsv', 'data/runners.csv'),
            segments_csv=request.get('segmentsCsv', 'data/segments.csv'),
            start_times=request.get('startTimes', {"Full": 420, "10K": 440, "Half": 460}),
            bin_size_km=request.get('binSizeKm')
        )
        
        return JSONResponse(content=comparison)
        
    except Exception as e:
        logger.error(f"Error comparing segments: {e}")
        raise HTTPException(status_code=500, detail=f"Error comparing segments: {e}")

@router.post("/export-advanced")
async def export_advanced_data(request: dict):
    """
    Export bin-level data with advanced filtering and formatting.
    
    This endpoint provides enhanced export capabilities for bin-level data
    with filtering, sorting, and multiple format options.
    """
    try:
        from .bin_analysis import export_bin_data
        
        segment_ids = request.get('segmentIds', [])
        export_format = request.get('format', 'csv')
        
        export_data = export_bin_data(
            segment_ids=segment_ids,
            pace_csv=request.get('paceCsv', 'data/runners.csv'),
            segments_csv=request.get('segmentsCsv', 'data/segments.csv'),
            start_times=request.get('startTimes', {"Full": 420, "10K": 440, "Half": 460}),
            format=export_format,
            bin_size_km=request.get('binSizeKm')
        )
        
        return JSONResponse(content=export_data)
        
    except Exception as e:
        logger.error(f"Error exporting advanced data: {e}")
        raise HTTPException(status_code=500, detail=f"Error exporting advanced data: {e}")

@router.get("/cache-management")
async def get_cache_management():
    """
    Get detailed cache management information.
    
    This endpoint provides comprehensive cache statistics and management
    capabilities for the map system.
    """
    try:
        from .bin_analysis import get_cache_stats, clear_bin_cache
        
        cache_stats = get_cache_stats()
        
        return JSONResponse(content={
            "ok": True,
            "cache_stats": cache_stats,
            "management_actions": [
                "clear_cache",
                "get_stats",
                "invalidate_segment"
            ],
            "cache_info": {
                "description": "Bin-level analysis cache for map visualization",
                "purpose": "Improve performance by caching computed bin data",
                "invalidation": "Automatic on dataset changes"
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting cache management info: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting cache management info: {e}")

@router.post("/invalidate-segment")
async def invalidate_segment_cache(request: dict):
    """
    Invalidate cache for a specific segment.
    
    This endpoint allows selective cache invalidation for specific segments
    without clearing the entire cache.
    """
    try:
        from .bin_analysis import _bin_cache, calculate_dataset_hash
        
        segment_id = request.get('segmentId')
        if not segment_id:
            raise HTTPException(status_code=400, detail="segmentId is required")
        
        # Calculate dataset hash for invalidation
        dataset_hash = calculate_dataset_hash(
            request.get('paceCsv', 'data/runners.csv'),
            request.get('segmentsCsv', 'data/segments.csv'),
            request.get('startTimes', {"Full": 420, "10K": 440, "Half": 460})
        )
        
        # Invalidate cache for this segment
        _bin_cache.invalidate(dataset_hash)
        
        return JSONResponse(content={
            "ok": True,
            "message": f"Cache invalidated for segment {segment_id}",
            "segment_id": segment_id,
            "dataset_hash": dataset_hash
        })
        
    except Exception as e:
        logger.error(f"Error invalidating segment cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error invalidating segment cache: {e}")

@router.get("/cache-status")
async def get_cache_status(
    analysisType: str = Query(..., description="Type of analysis: density, flow, or bins"),
    paceCsv: str = Query("data/runners.csv", description="Path to pace data CSV"),
    segmentsCsv: str = Query("data/segments.csv", description="Path to segments data CSV"),
    startTimes: str = Query('{"Full": 420, "10K": 440, "Half": 460}', description="JSON string of start times")
):
    """
    Get cache status for analysis results.
    
    This endpoint provides information about cached analysis results
    including timestamps and age of the data.
    """
    try:
        # Parse start times
        start_times = json.loads(startTimes)
        
        # Calculate dataset hash
        from .bin_analysis import calculate_dataset_hash
        dataset_hash = calculate_dataset_hash(paceCsv, segmentsCsv, start_times)
        
        # Get cache manager
        cache_manager = get_global_cache_manager()
        
        # Get cache status
        status = cache_manager.get_cache_status(analysisType, dataset_hash)
        
        return JSONResponse(content={
            "ok": True,
            "cache_status": status,
            "analysis_type": analysisType,
            "dataset_hash": dataset_hash
        })
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid startTimes JSON: {e}")
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting cache status: {e}")

# REMOVED: /api/force-refresh endpoint - causes Cloud Run timeouts
# Maps are now visualization-only and read from existing reports

@router.get("/cached-analysis")
async def get_cached_analysis(
    analysisType: str = Query(..., description="Type of analysis: density, flow, or bins"),
    paceCsv: str = Query("data/runners.csv", description="Path to pace data CSV"),
    segmentsCsv: str = Query("data/segments.csv", description="Path to segments data CSV"),
    startTimes: str = Query('{"Full": 420, "10K": 440, "Half": 460}', description="JSON string of start times")
):
    """
    Get cached analysis results.
    
    This endpoint returns cached analysis results if available,
    or indicates if no cached data exists.
    """
    try:
        # Parse start times
        start_times = json.loads(startTimes)
        
        # Calculate dataset hash
        from .bin_analysis import calculate_dataset_hash
        dataset_hash = calculate_dataset_hash(paceCsv, segmentsCsv, start_times)
        
        # Get cache manager
        cache_manager = get_global_cache_manager()
        
        # Get cached analysis
        entry = cache_manager.get_analysis(analysisType, dataset_hash)
        
        if entry is None:
            return JSONResponse(content={
                "ok": False,
                "message": f"No cached {analysisType} analysis found",
                "analysis_type": analysisType,
                "dataset_hash": dataset_hash
            })
        
        # Handle timezone-aware vs timezone-naive datetime comparison
        now = datetime.now()
        if entry.timestamp.tzinfo is not None:
            # If entry.timestamp is timezone-aware, make now timezone-aware too
            now = now.replace(tzinfo=entry.timestamp.tzinfo)
        elif now.tzinfo is not None:
            # If now is timezone-aware but entry.timestamp is not, make entry.timestamp timezone-aware
            entry.timestamp = entry.timestamp.replace(tzinfo=now.tzinfo)
        
        return JSONResponse(content={
            "ok": True,
            "analysis_type": analysisType,
            "dataset_hash": dataset_hash,
            "timestamp": entry.timestamp.isoformat(),
            "age_hours": (now - entry.timestamp).total_seconds() / 3600,
            "data": entry.data,
            "metadata": entry.metadata
        })
        
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid startTimes JSON: {e}")
    except Exception as e:
        logger.error(f"Error getting cached analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting cached analysis: {e}")

@router.get("/map-data")
async def get_map_data(date: str = Query(default=None, description="YYYY-MM-DD")):
    """
    Get map data for the frontend (read-only from existing reports).
    
    This endpoint reads map_data.json from the reports directory.
    Maps are visualization-only and do not run analysis.
    """
    import pathlib
    import json
    
    try:
        REPORTS_DIR = pathlib.Path("reports")
        
        def latest_report_dir():
            dirs = sorted([p for p in REPORTS_DIR.glob("20*--") if p.is_dir()], reverse=True)
            return dirs[0] if dirs else None
        
        report_dir = (REPORTS_DIR / date) if date else latest_report_dir()
        
        if not report_dir:
            raise HTTPException(status_code=404, detail={"error": "No reports found."})
        
        map_file = report_dir / "map_data.json"
        if not map_file.exists():
            raise HTTPException(status_code=404, detail={"error": "No map data available. Please generate reports first."})
        
        try:
            return json.loads(map_file.read_text())
        except Exception:
            raise HTTPException(status_code=500, detail={"error": "Corrupt map_data.json"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting map data: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting map data: {e}")

@router.post("/cleanup-cache")
async def cleanup_cache(
    maxAgeHours: int = Query(24, description="Maximum age of cache entries in hours")
):
    """
    Clean up old cache entries.
    
    This endpoint removes cache entries older than the specified age.
    """
    try:
        # Get cache manager
        cache_manager = get_global_cache_manager()
        
        # Clean up old entries
        cleaned_count = cache_manager.cleanup_old_entries(maxAgeHours)
        
        return JSONResponse(content={
            "ok": True,
            "message": f"Cleaned up {cleaned_count} old cache entries",
            "max_age_hours": maxAgeHours,
            "cleaned_count": cleaned_count
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning up cache: {e}")
