"""
API Routes for Density Data (RF-FE-002)

Provides density analysis endpoints for the density page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging

from app.storage import create_storage_from_env

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


@router.get("/api/density/segments")
async def get_density_segments():
    """
    Get density analysis data for all segments.
    
    Returns:
        Array of segment density records with:
        - seg_id, name, schema, active, peak_density, worst_los, peak_rate
        - utilization, flagged, worst_bin, watch, mitigation
    """
    try:
        # Load segment metrics
        segment_metrics = {}
        if storage.exists("segment_metrics.json"):
            segment_metrics = storage.read_json("segment_metrics.json")
        else:
            logger.warning("segment_metrics.json not found")
        
        # Load segments geojson for labels
        segments_geojson = {}
        if storage.exists("segments.geojson"):
            segments_geojson = storage.read_json("segments.geojson")
        else:
            logger.warning("segments.geojson not found")
        
        # Build label lookup from geojson
        label_lookup = {}
        for feature in segments_geojson.get("features", []):
            props = feature.get("properties", {})
            seg_id = props.get("seg_id")
            if seg_id:
                label_lookup[seg_id] = {
                    "label": props.get("label", seg_id),
                    "length_km": props.get("length_km", 0.0),
                    "width_m": props.get("width_m", 0.0),
                    "direction": props.get("direction", ""),
                    "events": props.get("events", [])
                }
        
        # Load flags
        flagged_seg_ids = set()
        if storage.exists("flags.json"):
            try:
                flags = storage.read_json("flags.json")
                if isinstance(flags, list):
                    flagged_seg_ids = {f.get("seg_id") for f in flags if f.get("seg_id")}
                elif isinstance(flags, dict):
                    flagged_seg_ids = {f.get("seg_id") for f in flags.get("flagged_segments", []) if f.get("seg_id")}
            except Exception as e:
                logger.warning(f"Could not read flags: {e}")
        
        # Build segments list
        segments_list = []
        for seg_id, metrics in segment_metrics.items():
            label_info = label_lookup.get(seg_id, {})
            
            # Build schema string (e.g., "0.9 km × 5.0 m")
            length = label_info.get("length_km", 0.0)
            width = label_info.get("width_m", 0.0)
            schema = f"{length:.1f} km × {width:.1f} m" if length > 0 else "N/A"
            
            # Events list
            events = label_info.get("events", [])
            events_str = ", ".join(events) if events else "N/A"
            
            segment_record = {
                "seg_id": seg_id,
                "name": label_info.get("label", seg_id),
                "schema": schema,
                "active": metrics.get("active_window", "N/A"),
                "peak_density": metrics.get("peak_density", 0.0),
                "worst_los": metrics.get("worst_los", "Unknown"),
                "peak_rate": metrics.get("peak_rate", 0.0),
                "utilization": 0.0,  # To be computed if needed
                "flagged": seg_id in flagged_seg_ids,
                "worst_bin": "N/A",  # From bin-level data if available
                "watch": metrics.get("worst_los") in ["D", "E", "F"],
                "mitigation": "Monitor" if seg_id in flagged_seg_ids else "None",
                "events": events_str,
                "bin_detail": "absent"  # Will update if heatmaps exist
            }
            
            segments_list.append(segment_record)
        
        # Sort by seg_id
        segments_list.sort(key=lambda x: x["seg_id"])
        
        response = JSONResponse(content=segments_list)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error generating density segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load density data: {str(e)}")


@router.get("/api/density/segment/{seg_id}")
async def get_density_segment_detail(seg_id: str):
    """
    Get detailed density analysis for a specific segment.
    
    Args:
        seg_id: Segment identifier
        
    Returns:
        Detailed segment record with heatmap availability
    """
    try:
        # Load segment metrics
        segment_metrics = {}
        if storage.exists("segment_metrics.json"):
            segment_metrics = storage.read_json("segment_metrics.json")
        
        if seg_id not in segment_metrics:
            raise HTTPException(status_code=404, detail=f"Segment {seg_id} not found")
        
        metrics = segment_metrics[seg_id]
        
        # Load segments geojson for label
        label = seg_id
        length_km = 0.0
        width_m = 0.0
        direction = ""
        events = []
        
        if storage.exists("segments.geojson"):
            segments_geojson = storage.read_json("segments.geojson")
            for feature in segments_geojson.get("features", []):
                props = feature.get("properties", {})
                if props.get("seg_id") == seg_id:
                    label = props.get("label", seg_id)
                    length_km = props.get("length_km", 0.0)
                    width_m = props.get("width_m", 0.0)
                    direction = props.get("direction", "")
                    events = props.get("events", [])
                    break
        
        # Check if flagged
        is_flagged = False
        if storage.exists("flags.json"):
            flags = storage.read_json("flags.json")
            if isinstance(flags, list):
                is_flagged = any(f.get("seg_id") == seg_id for f in flags)
            elif isinstance(flags, dict):
                is_flagged = any(f.get("seg_id") == seg_id for f in flags.get("flagged_segments", []))
        
        # Check for heatmap (if we add heatmap export later)
        heatmap_url = None
        # Future: check if artifacts/<run_id>/ui/heatmaps/<seg_id>.png exists
        
        detail = {
            "seg_id": seg_id,
            "name": label,
            "schema": f"{length_km:.1f} km × {width_m:.1f} m" if length_km > 0 else "N/A",
            "active": metrics.get("active_window", "N/A"),
            "peak_density": metrics.get("peak_density", 0.0),
            "worst_los": metrics.get("worst_los", "Unknown"),
            "peak_rate": metrics.get("peak_rate", 0.0),
            "flagged": is_flagged,
            "events": ", ".join(events) if events else "N/A",
            "direction": direction,
            "length_km": length_km,
            "width_m": width_m,
            "heatmap_url": heatmap_url,
            "bin_detail": "absent" if not heatmap_url else "available"
        }
        
        return JSONResponse(content=detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting segment detail for {seg_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load segment detail: {str(e)}")

