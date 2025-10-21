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

from app.storage import create_storage_from_env, list_reports
from app.storage_service import get_storage_service

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
        # Get latest run_id via StorageService (GCS-aware)
        storage_service = get_storage_service()
        run_id = storage_service.get_latest_run_id()
        
        if not run_id:
            logger.warning("No latest run_id found")
            return JSONResponse(content=[])
        
        # List reports
        reports = list_reports(storage, run_id)
        
        # Add core data files from data/ directory
        core_data_files = [
            {"name": "runners.csv", "path": "data/runners.csv", "description": "Runner data with start times and event assignments"},
            {"name": "segments.csv", "path": "data/segments.csv", "description": "Course segment definitions and characteristics"},
            {"name": "flow_expected_results.csv", "path": "data/flow_expected_results.csv", "description": "Expected results for validation"}
        ]
        
        # Check if core data files exist and add them
        for data_file in core_data_files:
            if storage.exists(data_file["path"]):
                reports.append({
                    "name": data_file["name"],
                    "path": data_file["path"],
                    "mtime": storage.mtime(data_file["path"]),
                    "size": storage.size(data_file["path"]),
                    "description": data_file["description"],
                    "type": "data_file"
                })
        
        response = JSONResponse(content=reports)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error listing reports: {e}")
        raise HTTPException(status_code=500, detail=f"database to list reports: {str(e)}")


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
        # Security: validate path is under reports/ or data/ and doesn't traverse
        if ".." in path or path.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Get latest run_id for validation
        run_id = load_latest_run_id(storage)
        if not run_id:
            raise HTTPException(status_code=404, detail="No reports available")
        
        # Validate path starts with run_id (for reports) or is a data file
        if not (path.startswith(run_id) or path.startswith("data/")):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # For local mode, serve directly
        if storage.mode == "local":
            # Handle both reports/ and data/ files
            if path.startswith("data/"):
                file_path = Path(path)  # data/runners.csv -> data/runners.csv
            else:
                file_path = Path("reports") / path  # 2025-10-19/file.md -> reports/2025-10-19/file.md
            
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
                # Handle both reports/ and data/ files
                if path.startswith("data/"):
                    content = storage.read_bytes(path)  # data/runners.csv
                else:
                    content = storage.read_bytes(f"reports/{path}")  # reports/2025-10-19/file.md
                
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

