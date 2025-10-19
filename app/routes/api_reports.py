"""
API Routes for Reports (RF-FE-002)

Provides report listing and download endpoints.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from typing import List, Dict, Any
from pathlib import Path
import logging

from app.storage import create_storage_from_env, load_latest_run_id, list_reports

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


@router.get("/api/reports/list")
async def get_reports_list():
    """
    Get list of available report files for the latest run.
    
    Returns:
        Array of file objects with name, path, mtime, size
    """
    try:
        # Get latest run_id
        run_id = load_latest_run_id(storage)
        if not run_id:
            logger.warning("No latest run_id found")
            return JSONResponse(content=[])
        
        # List reports
        reports = list_reports(storage, run_id)
        
        response = JSONResponse(content=reports)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list reports: {str(e)}")


@router.get("/api/reports/download")
async def download_report(path: str = Query(..., description="Report file path")):
    """
    Download a specific report file.
    
    Args:
        path: File path relative to reports/ directory
        
    Returns:
        File download
    """
    try:
        # Security: validate path is under reports/ and doesn't traverse
        if ".." in path or path.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Get latest run_id for validation
        run_id = load_latest_run_id(storage)
        if not run_id:
            raise HTTPException(status_code=404, detail="No reports available")
        
        # Validate path starts with run_id
        if not path.startswith(run_id):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # For local mode, serve directly
        if storage.mode == "local":
            file_path = Path("reports") / path
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File not found")
            
            return FileResponse(
                path=file_path,
                filename=file_path.name,
                media_type="application/octet-stream"
            )
        else:
            # For GCS mode, stream from bucket
            try:
                content = storage.read_bytes(f"reports/{path}")
                filename = Path(path).name
                
                return StreamingResponse(
                    iter([content]),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            except Exception as e:
                logger.error(f"Error downloading from GCS: {e}")
                raise HTTPException(status_code=500, detail="Download failed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading report {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

