"""
API Routes for Health Data Status (RF-FE-002)

Provides system health information from health.json artifact.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #288 | Health Check page fix
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import logging
from pathlib import Path

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health/data")
async def get_health_data():
    """
    Get system health information from health.json artifact.
    
    Issue #288: Health page should render from system health data,
    not operational metrics.
    Issue #460 Phase 5: Read from runflow/<run_id>/ui/health.json
    
    Returns:
        JSON with system health information (environment, files, hashes, endpoints)
    """
    try:
        # Issue #460 Phase 5: Get latest run_id and read from runflow structure
        from app.utils.metadata import get_latest_run_id
        from app.storage import create_runflow_storage
        
        run_id = get_latest_run_id()
        storage = create_runflow_storage(run_id)
        # Issue #580: Updated path to metadata/ subdirectory
        # Note: health.json is run-level, not day-scoped, so we need to determine which day to use
        # For now, use latest day or first available day
        from app.utils.run_id import get_available_days
        available_days = get_available_days(run_id)
        if not available_days:
            raise HTTPException(status_code=404, detail="No days available for run")
        selected_day = available_days[0]  # Use first available day
        health_data = storage.read_json(f"{selected_day}/ui/metadata/health.json")
        
        if health_data is None:
            raise HTTPException(status_code=404, detail="health.json not found in runflow storage")
        
        logger.info(f"Loaded health data from runflow/analysis/{run_id}/{selected_day}/ui/metadata/health.json")
        return JSONResponse(content=health_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading health data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load health data: {str(e)}")


@router.get("/api/health")
async def health_check():
    """
    Simple health check endpoint for load balancers.
    
    Returns:
        Simple OK status
    """
    return JSONResponse(content={"status": "ok"})
