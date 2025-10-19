"""
API Routes for Flow Data (RF-FE-002)

Provides temporal flow analysis endpoints for the flow page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import logging

from app.storage import create_storage_from_env

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


@router.get("/api/flow/segments")
async def get_flow_segments():
    """
    Get flow analysis data for all segments.
    
    Returns:
        Dictionary mapping seg_id to flow metrics:
        - overtaking_a/b: Sum of overtaking events
        - copresence_a/b: Sum of co-presence events
    """
    try:
        # Load flow.json
        flow_data = {}
        if storage.exists("flow.json"):
            flow_data = storage.read_json("flow.json")
        else:
            logger.warning("flow.json not found")
        
        # Load segment labels from geojson
        segment_labels = {}
        if storage.exists("segments.geojson"):
            segments_geojson = storage.read_json("segments.geojson")
            for feature in segments_geojson.get("features", []):
                props = feature.get("properties", {})
                seg_id = props.get("seg_id")
                if seg_id:
                    segment_labels[seg_id] = props.get("label", seg_id)
        
        # Build enriched flow data with labels
        enriched_flow = {}
        for seg_id, metrics in flow_data.items():
            enriched_flow[seg_id] = {
                "seg_id": seg_id,
                "name": segment_labels.get(seg_id, seg_id),
                "overtaking_a": metrics.get("overtaking_a", 0.0),
                "overtaking_b": metrics.get("overtaking_b", 0.0),
                "copresence_a": metrics.get("copresence_a", 0.0),
                "copresence_b": metrics.get("copresence_b", 0.0),
                "flow_type": "overtake"  # From CSV if needed
            }
        
        response = JSONResponse(content=enriched_flow)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error generating flow segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load flow data: {str(e)}")

