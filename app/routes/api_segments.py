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

from app.storage import create_storage_from_env
from app.common.config import load_reporting

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


def enrich_segment_features(segments_geojson: Dict[str, Any], 
                          segment_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            "active": segment_metrics_data.get("active_window", "Unknown")
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
        # Read segments.geojson
        if not storage.exists("segments.geojson"):
            logger.warning("segments.geojson not found in storage")
            return JSONResponse(
                content={"type": "FeatureCollection", "features": []},
                headers={"Cache-Control": "public, max-age=60"}
            )
        
        segments_geojson = storage.read_json("segments.geojson")
        
        # Read segment_metrics.json
        segment_metrics = {}
        if storage.exists("segment_metrics.json"):
            segment_metrics = storage.read_json("segment_metrics.json")
        else:
            logger.warning("segment_metrics.json not found in storage")
        
        # Enrich features
        enriched_features = enrich_segment_features(segments_geojson, segment_metrics)
        
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
        # Read segments.geojson
        if not storage.exists("segments.geojson"):
            return JSONResponse(content={"error": "segments.geojson not found"})
        
        segments_geojson = storage.read_json("segments.geojson")
        features = segments_geojson.get("features", [])
        
        # Read segment_metrics.json
        segment_metrics = {}
        if storage.exists("segment_metrics.json"):
            segment_metrics = storage.read_json("segment_metrics.json")
        
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
        if storage.exists("flags.json"):
            flags = storage.read_json("flags.json")
            flagged_count = len(flags.get("flagged_segments", []))
        
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
