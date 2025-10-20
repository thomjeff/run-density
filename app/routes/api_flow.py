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
from pathlib import Path

from app.storage import create_storage_from_env
from app.storage_service import StorageService

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()
storage_service = StorageService()


@router.get("/api/flow/segments")
async def get_flow_segments():
    """
    Get flow analysis data for all segments from Flow CSV.
    
    Returns:
        Array of flow records with event pairs (29 rows total).
        Each row represents a segment-event_a-event_b combination.
    """
    try:
        # Load flow data from UI artifacts using storage service
        flow_data = storage_service.load_ui_artifact("flow.json")
        
        if not flow_data:
            logger.warning("flow.json not found in storage service")
            return JSONResponse(content=[])
        
        logger.info(f"Loaded {len(flow_data)} flow records from storage service")
        
        # Convert to the format expected by the frontend
        flow_records = []
        for item in flow_data:
            # Skip empty items
            if not item.get('seg_id'):
                continue
                
            flow_record = {
                "id": str(item['seg_id']),
                "name": str(item.get('segment_label', item['seg_id'])),
                "event_a": str(item.get('event_a', '')),
                "event_b": str(item.get('event_b', '')),
                "flow_type": str(item.get('flow_type', '')),
                "overtaking_a": float(item.get('overtaking_a', 0.0)),
                "pct_a": float(item.get('pct_a', 0.0)),
                "overtaking_b": float(item.get('overtaking_b', 0.0)),
                "pct_b": float(item.get('pct_b', 0.0)),
                "copresence_a": float(item.get('copresence_a', 0.0)),
                "copresence_b": float(item.get('copresence_b', 0.0))
            }
            flow_records.append(flow_record)
        
        logger.info(f"Loaded {len(flow_records)} flow records from storage service")
        
        response = JSONResponse(content=flow_records)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error generating flow segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load flow data: {str(e)}")

