"""
API Routes for Segments Data (RF-FE-002)

Provides enriched GeoJSON endpoints for the segments page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 5
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import json
import logging

from app.storage_service import get_storage_service
from app.common.config import load_reporting

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage service
storage = get_storage_service()


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
async def get_segments_geojson():
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
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        from app.utils.metadata import get_latest_run_id
        from app.storage import create_runflow_storage
        
        run_id = get_latest_run_id()
        storage = create_runflow_storage(run_id)
        
        # Read segments.geojson from runflow UI artifacts
        segments_geojson = storage.read_geojson("ui/segments.geojson")
        if segments_geojson is None:
            logger.warning(f"segments.geojson not found in runflow/{run_id}/ui/")
            return JSONResponse(
                content={"type": "FeatureCollection", "features": []},
                headers={"Cache-Control": "public, max-age=60"}
            )
        
        # Read segment_metrics.json from runflow UI artifacts
        segment_metrics = storage.read_json("ui/segment_metrics.json")
        if segment_metrics is None:
            logger.warning(f"segment_metrics.json not found in runflow/{run_id}/ui/")
            segment_metrics = {}
        
        # Load flags to mark flagged segments
        flagged_seg_ids = set()
        flags = storage.read_json("ui/flags.json")
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
async def get_segments_summary():
    """
    Get segments summary for dashboard tiles.
    
    Returns:
        Summary statistics about segments and metrics
    """
    try:
        # Get latest run_id to locate UI artifacts
        run_id = storage.get_latest_run_id()
        artifacts_path = f"artifacts/{run_id}/ui"
        
        # Read segments.geojson from UI artifacts
        segments_geojson = storage.read_geojson(f"{artifacts_path}/segments.geojson")
        if segments_geojson is None:
            return JSONResponse(content={"error": "segments.geojson not found"})
        
        features = segments_geojson.get("features", [])
        
        # Read segment_metrics.json from UI artifacts
        segment_metrics = storage.read_json(f"{artifacts_path}/segment_metrics.json")
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
        
        # Count flagged segments (if flags exist)
        flagged_count = 0
        flags = storage.read_json(f"{artifacts_path}/flags.json")
        if flags:
            # Handle both dict and array formats
            if isinstance(flags, dict):
                flagged_count = len(flags.get("flagged_segments", []))
            elif isinstance(flags, list):
                flagged_count = len(flags)
            else:
                flagged_count = 0
        
        summary = {
            "total_segments": total_segments,
            "los_counts": los_counts,
            "flagged_segments": flagged_count,
            "has_metrics": len(segment_metrics) > 0
        }
        
        return JSONResponse(content=summary)
        
    except Exception as e:
        logger.error(f"Error generating segments summary: {e}")
        return JSONResponse(content={"error": str(e)})
