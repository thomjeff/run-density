"""
API Routes for Segments Data (RF-FE-002)

Provides enriched GeoJSON endpoints for the segments page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 5
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging

# Issue #466 Step 2: Storage consolidated to app.storage
from app.utils.run_id import get_latest_run_id, resolve_selected_day
from app.storage import create_runflow_storage
from app.utils.env import env_bool
from app.utils.auth import is_session_valid

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage singleton (not needed)

# Issue #477: Coordinate system conversion (Web Mercator → WGS84)
from pyproj import Transformer

# Create transformer (Web Mercator → WGS84)
# segments.geojson contains Web Mercator coordinates (EPSG:3857)
# but GeoJSON standard requires WGS84 (EPSG:4326)
webmerc_to_wgs84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)


def convert_geometry_to_wgs84(geometry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert geometry coordinates from Web Mercator to WGS84.
    
    Issue #477: segments.geojson contains Web Mercator coordinates but GeoJSON standard
    requires WGS84. This function converts before serving to frontend.
    
    Args:
        geometry: GeoJSON geometry object (LineString or MultiLineString)
        
    Returns:
        Geometry with coordinates converted to WGS84 [lon, lat]
    """
    if not geometry or not isinstance(geometry, dict):
        return geometry
    
    geom_type = geometry.get("type")
    if geom_type == "LineString":
        coords = geometry.get("coordinates", [])
        if coords:
            geometry["coordinates"] = [
                list(webmerc_to_wgs84.transform(x, y)) for x, y in coords
            ]
    elif geom_type == "MultiLineString":
        coords = geometry.get("coordinates", [])
        if coords:
            geometry["coordinates"] = [
                [list(webmerc_to_wgs84.transform(x, y)) for x, y in line]
                for line in coords
            ]
    # Other geometry types (Point, Polygon, etc.) not expected for segments
    # but handle gracefully if encountered
    return geometry


def enrich_segment_features(segments_geojson: Dict[str, Any], 
                          segment_metrics: Dict[str, Any],
                          flagged_seg_ids: set) -> List[Dict[str, Any]]:
    """
    Enrich segment features with metrics data.
    
    Args:
        segments_geojson: GeoJSON FeatureCollection from segments.geojson
        segment_metrics: Metrics data from segment_metrics.json
        
    Returns:
        List of enriched feature dictionaries
    """
    # Build metrics lookup: {seg_id: {worst_los, peak_density, peak_rate, active_window}}
    metrics_lookup = {}
    for seg_id, metrics in segment_metrics.items():
        if isinstance(metrics, dict):
            metrics_lookup[seg_id] = {
                "worst_los": metrics.get("worst_los", "Unknown"),
                "peak_density": metrics.get("peak_density", 0.0),
                "peak_rate": metrics.get("peak_rate", 0.0),
                "active_window": metrics.get("active_window", "Unknown")
            }
    
    # Enrich each feature
    enriched_features = []
    for feature in segments_geojson.get("features", []):
        properties = feature.get("properties", {})
        seg_id = properties.get("seg_id", "")
        
        # Get metrics for this segment
        segment_metrics_data = metrics_lookup.get(seg_id, {})
        
        # Create enriched properties
        enriched_properties = {
            # Original properties
            "seg_id": seg_id,
            "label": properties.get("label", ""),
            "length_km": properties.get("length_km", 0.0),
            "width_m": properties.get("width_m", 0.0),
            "direction": properties.get("direction", ""),
            "events": properties.get("events", []),
            
            # Enriched metrics
            "worst_los": segment_metrics_data.get("worst_los", "Unknown"),
            "peak_density": segment_metrics_data.get("peak_density", 0.0),
            "peak_rate": segment_metrics_data.get("peak_rate", 0.0),
            "active": segment_metrics_data.get("active_window", "Unknown"),
            "is_flagged": seg_id in flagged_seg_ids,  # Mark if segment is flagged
            
            # Issue #373: Add description from source GeoJSON
            "description": properties.get("description", "No description available")
        }
        
        # Create enriched feature
        enriched_feature = {
            "type": "Feature",
            "geometry": feature.get("geometry"),
            "properties": enriched_properties
        }
        
        enriched_features.append(enriched_feature)
    
    return enriched_features


@router.get("/api/segments/geojson")
async def get_segments_geojson(
    request: Request,
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get enriched segments GeoJSON with metrics data.
    
    Returns:
        GeoJSON FeatureCollection with enriched properties:
        - Original: seg_id, label, length_km, width_m, direction, events
        - Enriched: worst_los, peak_density, peak_rate, active
        
    Errors:
        - Returns empty FeatureCollection if files missing
        - Logs warnings for missing data
    """
    try:
        if env_bool("CLOUD_MODE") and not is_session_valid(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Read segments.geojson from runflow UI artifacts (Issue #580: Updated path to geospatial/ subdirectory)
        segments_geojson = storage.read_json(f"{selected_day}/ui/geospatial/segments.geojson")
        if segments_geojson is None:
            logger.warning(f"segments.geojson not found in runflow/analysis/{run_id}/{selected_day}/ui/geospatial/")
            return JSONResponse(
                content={
                    "selected_day": selected_day,
                    "available_days": available_days,
                    "type": "FeatureCollection",
                    "features": []
                },
                headers={"Cache-Control": "public, max-age=60"}
            )
        
        # Issue #477: Convert geometry coordinates from UTM Zone 19N to WGS84
        # GeoJSON standard requires WGS84, and frontend expects WGS84
        for feature in segments_geojson.get("features", []):
            if "geometry" in feature:
                feature["geometry"] = convert_geometry_to_wgs84(feature["geometry"])
        
        # Read segment_metrics.json from runflow UI artifacts (Issue #580: Updated path to metrics/ subdirectory)
        segment_metrics = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json")
        if segment_metrics is None:
            logger.warning(f"segment_metrics.json not found in runflow/analysis/{run_id}/{selected_day}/ui/")
            segment_metrics = {}
        
        # Load flags to mark flagged segments (Issue #580: Updated path to metrics/ subdirectory)
        flagged_seg_ids = set()
        flags = storage.read_json(f"{selected_day}/ui/metrics/flags.json")
        if flags:
            try:
                # Handle both dict and array formats
                if isinstance(flags, list):
                    flagged_seg_ids = {f.get("seg_id") for f in flags if f.get("seg_id")}
                elif isinstance(flags, dict):
                    flagged_seg_ids = {f.get("seg_id") for f in flags.get("flagged_segments", []) if f.get("seg_id")}
            except Exception as e:
                logger.warning(f"Could not read flags: {e}")
        
        # Enrich features
        enriched_features = enrich_segment_features(segments_geojson, segment_metrics, flagged_seg_ids)
        
        # Build response
        response_data = {
            "selected_day": selected_day,
            "available_days": available_days,
            "type": "FeatureCollection",
            "features": enriched_features
        }
        
        logger.info(f"Returning {len(enriched_features)} enriched segment features")
        
        return JSONResponse(
            content=response_data,
            headers={"Cache-Control": "public, max-age=60"}
        )
        
    except Exception as e:
        logger.error(f"Error generating segments GeoJSON: {e}")
        return JSONResponse(
            content={"type": "FeatureCollection", "features": []},
            headers={"Cache-Control": "public, max-age=60"}
        )


@router.get("/api/segments/summary")
async def get_segments_summary(
    request: Request,
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get segments summary for dashboard tiles.
    
    Returns:
        Summary statistics about segments and metrics
    """
    try:
        if env_bool("CLOUD_MODE") and not is_session_valid(request):
            raise HTTPException(status_code=401, detail="Unauthorized")
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Read segments.geojson from runflow UI artifacts (Issue #580: Updated path to geospatial/ subdirectory)
        segments_geojson = storage.read_json(f"{selected_day}/ui/geospatial/segments.geojson")
        if segments_geojson is None:
            return JSONResponse(content={
                "error": "segments.geojson not found",
                "selected_day": selected_day,
                "available_days": available_days
            })
        
        features = segments_geojson.get("features", [])
        
        # Read segment_metrics.json from UI artifacts (Issue #580: Updated path to metrics/ subdirectory)
        segment_metrics = storage.read_json(f"{selected_day}/ui/metrics/segment_metrics.json")
        if segment_metrics is None:
            segment_metrics = {}
        
        # Calculate summary stats
        total_segments = len(features)
        
        # Count by LOS
        los_counts = {}
        for feature in features:
            properties = feature.get("properties", {})
            seg_id = properties.get("seg_id", "")
            metrics = segment_metrics.get(seg_id, {})
            worst_los = metrics.get("worst_los", "Unknown")
            los_counts[worst_los] = los_counts.get(worst_los, 0) + 1
        
        # Count flagged segments (if flags exist) (Issue #580: Updated path to metrics/ subdirectory)
        flagged_count = 0
        flags = storage.read_json(f"{selected_day}/ui/metrics/flags.json")
        if flags:
            # Handle both dict and array formats
            if isinstance(flags, dict):
                flagged_count = len(flags.get("flagged_segments", []))
            elif isinstance(flags, list):
                flagged_count = len(flags)
            else:
                flagged_count = 0
        
        summary = {
            "selected_day": selected_day,
            "available_days": available_days,
            "total_segments": total_segments,
            "los_counts": los_counts,
            "flagged_segments": flagged_count,
            "has_metrics": len(segment_metrics) > 0
        }
        
        return JSONResponse(content=summary)
        
    except Exception as e:
        logger.error(f"Error generating segments summary: {e}")
        return JSONResponse(content={"error": str(e)})
