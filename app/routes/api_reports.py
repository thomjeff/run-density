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

from app.storage_service import get_storage_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


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
        
        # List report files from GCS using StorageService
        from pathlib import Path as PathLib
        import os
        reports = []
        file_list = storage_service.list_files(f"reports/{run_id}")
        
        for filename in file_list:
            # Get file extension for description
            ext = PathLib(filename).suffix
            description = ""
            if ext == ".md":
                description = "Markdown report"
            elif ext == ".csv":
                description = "CSV data export"
            elif ext == ".parquet":
                description = "Parquet data export"
            elif ext == ".gz":
                description = "Compressed GeoJSON"
            
            # Get file metadata (size and modification time)
            file_path = f"reports/{run_id}/{filename}"
            mtime = None
            size = None
            
            try:
                if storage_service.config.use_cloud_storage:
                    # GCS: Get metadata from blob
                    try:
                        # Normalize path for GCS (remove reports/ prefix if present)
                        gcs_path = file_path
                        if file_path.startswith("reports/"):
                            gcs_path = file_path[len("reports/"):]
                        
                        bucket = storage_service._client.bucket(storage_service.config.bucket_name)
                        blob = bucket.blob(gcs_path)
                        
                        if blob.exists():
                            # Get blob metadata
                            blob.reload()  # Ensure we have latest metadata
                            mtime = blob.time_created.timestamp() if blob.time_created else None
                            size = blob.size if blob.size else None
                        else:
                            logger.warning(f"GCS blob not found: {gcs_path}")
                            mtime = None
                            size = None
                    except Exception as gcs_error:
                        logger.warning(f"Could not get GCS metadata for {file_path}: {gcs_error}")
                        mtime = None
                        size = None
                else:
                    # Local filesystem - get actual file stats
                    if os.path.exists(file_path):
                        stat = os.stat(file_path)
                        mtime = stat.st_mtime
                        size = stat.st_size
                    else:
                        logger.warning(f"Local file not found: {file_path}")
                        mtime = None
                        size = None
            except Exception as e:
                logger.warning(f"Could not get metadata for {file_path}: {e}")
                mtime = None
                size = None
            
            reports.append({
                "name": filename,
                "path": file_path,
                "mtime": mtime,
                "size": size,
                "description": description,
                "type": "report"
            })
        
        # Add core data files from local data/ directory (baked into Docker image)
        from pathlib import Path
        core_data_files = [
            {"name": "runners.csv", "path": "data/runners.csv", "description": "Runner data with start times and event assignments"},
            {"name": "segments.csv", "path": "data/segments.csv", "description": "Course segment definitions and characteristics"},
            {"name": "flow_expected_results.csv", "path": "data/flow_expected_results.csv", "description": "Expected results for validation"}
        ]
        
        # Check if core data files exist locally and add them
        for data_file in core_data_files:
            file_path = Path(data_file["path"])
            if file_path.exists():
                stat = file_path.stat()
                reports.append({
                    "name": data_file["name"],
                    "path": data_file["path"],
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
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
def download_report(path: str = Query(..., description="Report file path")):
    """
    Download a specific report file.
    
    Args:
        path: File path relative to reports/ directory
        
    Returns:
        File download
    """
    logger.info(f"[Download] Requested path: {path}")

    storage_service = get_storage_service()
    run_id = storage_service.get_latest_run_id()

    # Allow only: reports/<run_id>/* or data/*
    if not (path.startswith(f"reports/{run_id}") or path.startswith("data/")):
        logger.warning(f"[Download] Access denied for path: {path}")
        raise HTTPException(status_code=403, detail="Access denied")

    # Case A: Read from local data folder
    if path.startswith("data/"):
        try:
            content = open(path, "r", encoding="utf-8").read()
            logger.info(f"[Download] Loaded local data file: {path}")
        except Exception as e:
            logger.error(f"[Download] Failed to read local file {path}: {e}")
            raise HTTPException(status_code=404, detail="File not found")

    # Case B: Read report files (local or GCS)
    else:
        # Check if we're in local mode or Cloud Run mode
        if storage_service.config.use_cloud_storage:
            # Cloud Run: Read from GCS
            content = storage_service._load_from_gcs(path)
            if content is None:
                logger.warning(f"[Download] GCS file not found or unreadable: {path}")
                raise HTTPException(status_code=404, detail="File not found")
        else:
            # Local: Read from local filesystem
            try:
                if path.startswith("reports/"):
                    file_path = path  # reports/2025-10-21/file.md
                else:
                    file_path = f"reports/{path}"  # 2025-10-21/file.md -> reports/2025-10-21/file.md
                
                content = open(file_path, "r", encoding="utf-8").read()
                logger.info(f"[Download] Loaded local report file: {file_path}")
            except Exception as e:
                logger.error(f"[Download] Failed to read local report file {file_path}: {e}")
                raise HTTPException(status_code=404, detail="File not found")

    # Safe encoding
    try:
        content_bytes = content.encode("utf-8")
    except Exception as e:
        logger.error(f"[Download] Failed to encode content: {e}")
        raise HTTPException(status_code=500, detail="Encoding error")

    filename = path.split("/")[-1]
    logger.info(f"[Download] Sending file: {filename}")
    
    from io import BytesIO
    return StreamingResponse(
        BytesIO(content_bytes),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

