"""
API Routes for Heatmap Generation (Issue #365)

Provides heatmap generation endpoint for on-demand heatmap creation.

Author: Cursor AI Assistant (per Senior Architect guidance)
Issue: #365
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from app.heatmap_generator import generate_heatmaps_for_run
# Phase 3 cleanup: Removed unused import get_heatmap_files()
# Issue #466 Step 2: Storage consolidated to app.storage

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


class HeatmapGenerationRequest:
    """Request model for heatmap generation."""
    run_id: str
    force: bool = False
    
    class Config:
        extra = "forbid"


# Issue #466 Step 3: Dead GCS upload function removed (Phase 1 declouding)
# upload_binary_to_gcs() archived - no longer needed for local-only architecture


@router.post("/heatmaps")
async def generate_heatmaps(request: Dict[str, Any]):
    """
    Generate heatmaps for a specified run (local-only).
    
    Issue #466 Step 3: Removed GCS upload logic (Phase 1 declouding).
    
    Args:
        request: Dict with 'run_id' (required) and 'force' (optional)
        
    Returns:
        JSON with status, message, and heatmap_count
    """
    run_id = request.get("run_id")
    force = request.get("force", False)
    
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    
    logger.info(f"Received heatmap generation request for run_id: {run_id}, force: {force}")
    
    try:
        # Generate heatmaps
        heatmaps_generated, segments = generate_heatmaps_for_run(run_id)
        
        if heatmaps_generated == 0:
            raise HTTPException(
                status_code=500, 
                detail=f"No heatmaps were generated for run_id: {run_id}"
            )
        
        # Issue #464: Local-only after Phase 1 declouding
        logger.info("Local mode: Heatmaps written to local filesystem")
        uploaded_count = heatmaps_generated
        
        logger.info(f"Successfully generated {uploaded_count} heatmaps for {run_id}")
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Heatmaps generated successfully",  # Issue #466 Step 3: Removed "uploaded"
            "heatmap_count": uploaded_count,
            "segments": segments,
            "run_id": run_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating heatmaps for {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate heatmaps: {str(e)}"
        )

