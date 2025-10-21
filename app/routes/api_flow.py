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
import json

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
        # Load Flow CSV data using storage service (environment-aware)
        import pandas as pd
        from app.storage_service import get_storage_service
        
        # Get latest run_id from artifacts/latest.json via StorageService
        storage = get_storage_service()
        try:
            if storage.config.use_cloud_storage:
                content = storage._load_from_gcs("artifacts/latest.json")
            else:
                latest_path = Path("artifacts/latest.json")
                content = latest_path.read_text() if latest_path.exists() else None
            
            if not content:
                logger.warning("artifacts/latest.json not found")
                return JSONResponse(content=[])
            
            latest_data = json.loads(content)
            run_id = latest_data.get("run_id")
            if not run_id:
                logger.warning("No run_id found in latest.json")
                return JSONResponse(content=[])
        except Exception as e:
            logger.error(f"Failed to read latest.json: {e}")
            return JSONResponse(content=[])
        
        # Find Flow CSV file using storage service
        try:
            # Look for Flow CSV files in the reports directory for this run_id
            reports_dir = Path("reports") / run_id
            flow_csv_files = list(reports_dir.glob("*-Flow.csv"))
            
            if not flow_csv_files:
                logger.warning(f"No Flow CSV files found in {reports_dir}")
                return JSONResponse(content=[])
            
            # Use the latest Flow CSV (by modification time)
            latest_flow_csv = max(flow_csv_files, key=lambda f: f.stat().st_mtime)
            logger.info(f"Using Flow CSV: {latest_flow_csv}")
            
            # Read the CSV file
            df = pd.read_csv(latest_flow_csv)
        
        except Exception as e:
            logger.error(f"Failed to load Flow CSV: {e}")
            return JSONResponse(content=[])
        
        # Convert to the format expected by the frontend
        flow_records = []
        for _, row in df.iterrows():
            # Skip empty rows
            if pd.isna(row['seg_id']):
                continue
                
            flow_record = {
                "id": str(row['seg_id']),
                "name": str(row['segment_label']),
                "event_a": str(row['event_a']),
                "event_b": str(row['event_b']),
                "flow_type": str(row['flow_type']),
                "overtaking_a": float(row['overtaking_a']) if pd.notna(row['overtaking_a']) else 0.0,
                "pct_a": float(row['pct_a']) if pd.notna(row['pct_a']) else 0.0,
                "overtaking_b": float(row['overtaking_b']) if pd.notna(row['overtaking_b']) else 0.0,
                "pct_b": float(row['pct_b']) if pd.notna(row['pct_b']) else 0.0,
                "copresence_a": float(row['copresence_a']) if pd.notna(row['copresence_a']) else 0.0,
                "copresence_b": float(row['copresence_b']) if pd.notna(row['copresence_b']) else 0.0
            }
            flow_records.append(flow_record)
        
        logger.info(f"Loaded {len(flow_records)} flow records from Cloud Storage")
        
        response = JSONResponse(content=flow_records)
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except Exception as e:
        logger.error(f"Error generating flow segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load flow data: {str(e)}")

