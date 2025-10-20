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

from app.storage_service import StorageService

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)
storage_service = StorageService()


@router.get("/api/health/data")
async def get_health_data():
    """
    Get system health information from health.json artifact.
    
    Issue #288: Health page should render from system health data,
    not operational metrics.
    
    Returns:
        JSON with system health information (environment, files, hashes, endpoints)
    """
    try:
        # Use storage service to find the latest health.json artifact
        health_data = storage_service.load_ui_artifact("health.json")
        
        if health_data is None:
            raise HTTPException(status_code=404, detail="health.json not found in storage")
        
        logger.info("Loaded health data from storage")
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
