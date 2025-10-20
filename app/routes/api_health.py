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
    
    Returns:
        JSON with system health information (environment, files, hashes, endpoints)
    """
    try:
        # Find the latest health.json artifact
        artifacts_dir = Path("artifacts").resolve()
        if not artifacts_dir.exists():
            raise HTTPException(status_code=404, detail="No artifacts directory found")
        
        # Find the most recent run directory
        run_dirs = [d for d in artifacts_dir.iterdir() if d.is_dir() and d.name not in ["latest.json", "ui"]]
        if not run_dirs:
            raise HTTPException(status_code=404, detail="No artifact runs found")
        
        latest_run = max(run_dirs, key=lambda d: d.name)
        health_path = latest_run / "ui" / "health.json"
        
        if not health_path.exists():
            raise HTTPException(status_code=404, detail=f"health.json not found in {latest_run.name}")
        
        # Load and return health data
        with open(health_path, 'r') as f:
            health_data = json.load(f)
        
        logger.info(f"Loaded health data from {health_path}")
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
