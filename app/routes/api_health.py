"""
API Routes for Health Data Status (RF-FE-002)

Provides data file status and health checks.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 6 Fix
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any
from datetime import datetime

from app.storage import create_storage_from_env, DATASET

# Create router
router = APIRouter()

# Initialize storage
storage = create_storage_from_env()


@router.get("/api/health/data")
async def get_health_data():
    """
    Get data file status and health information.
    
    Returns:
        JSON with file existence and modification times
    """
    try:
        health_data = {}
        
        # Check each dataset file
        for name, path in DATASET.items():
            exists = storage.exists(path)
            mtime = None
            
            if exists:
                try:
                    mtime_epoch = storage.mtime(path)
                    if mtime_epoch > 0:
                        mtime = datetime.fromtimestamp(mtime_epoch).isoformat() + "Z"
                except Exception as e:
                    mtime = "error"
            
            health_data[path] = {
                "exists": exists,
                "mtime": mtime
            }
        
        # Add additional files
        additional_files = ["runners.csv", "flow.json"]
        for filename in additional_files:
            exists = storage.exists(filename)
            mtime = None
            
            if exists:
                try:
                    mtime_epoch = storage.mtime(filename)
                    if mtime_epoch > 0:
                        mtime = datetime.fromtimestamp(mtime_epoch).isoformat() + "Z"
                except Exception as e:
                    mtime = "error"
            
            health_data[filename] = {
                "exists": exists,
                "mtime": mtime
            }
        
        # Add storage info
        health_data["_storage"] = {
            "mode": storage.mode,
            "root": str(storage.root) if storage.root else None,
            "bucket": storage.bucket if hasattr(storage, 'bucket') else None
        }
        
        return JSONResponse(content=health_data)
        
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to check data health: {str(e)}"},
            status_code=500
        )
