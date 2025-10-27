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

from app.heatmap_generator import generate_heatmaps_for_run, get_heatmap_files
from app.storage_service import get_storage_service

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


def upload_binary_to_gcs(local_file_path: Path, gcs_dest_path: str) -> bool:
    """
    Upload binary file (PNG) to GCS.
    
    Args:
        local_file_path: Path to local file
        gcs_dest_path: GCS destination path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        storage_service = get_storage_service()
        
        # Read binary file
        with open(local_file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload using StorageService client
        bucket = storage_service._client.bucket(storage_service.config.bucket_name)
        blob = bucket.blob(gcs_dest_path)
        blob.upload_from_string(file_content, content_type='image/png')
        
        logger.info(f"Uploaded {local_file_path.name} to GCS: {gcs_dest_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to upload {local_file_path.name} to GCS: {e}")
        return False


@router.post("/heatmaps")
async def generate_heatmaps(request: Dict[str, Any]):
    """
    Generate heatmaps for a specified run and upload to GCS.
    
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
        
        # Upload to GCS (only if using cloud storage)
        storage = get_storage_service()
        uploaded_count = 0
        
        if storage.config.use_cloud_storage:
            logger.info("Cloud mode: Uploading heatmaps to GCS")
            png_files = get_heatmap_files(run_id)
            
            for png_file in png_files:
                gcs_dest = f"artifacts/{run_id}/ui/heatmaps/{png_file.name}"
                if upload_binary_to_gcs(png_file, gcs_dest):
                    uploaded_count += 1
        else:
            logger.info("Local mode: Heatmaps written to local filesystem")
            uploaded_count = heatmaps_generated
        
        logger.info(f"Successfully generated and uploaded {uploaded_count} heatmaps for {run_id}")
        
        return JSONResponse(content={
            "status": "success",
            "message": f"Heatmaps generated and uploaded successfully",
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

