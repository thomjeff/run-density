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

from app.storage_service import get_storage_service
from app.storage_service import StorageService

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize storage service
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
        
        # Get latest run_id via StorageService (GCS-aware)
        storage = get_storage_service()
        run_id = storage.get_latest_run_id()
        
        if not run_id:
            logger.warning("Could not determine latest run_id")
            return JSONResponse(content=[])
        
        # Find Flow CSV file using storage service (GCS-aware)
        try:
            # List Flow CSV files in the reports directory for this run_id
            flow_csv_files = storage.list_files(f"reports/{run_id}", suffix="-Flow.csv")
            
            if not flow_csv_files:
                logger.warning(f"No Flow CSV files found in reports/{run_id}")
                return JSONResponse(content=[])
            
            # Use the latest Flow CSV (last in sorted list = most recent timestamp)
            latest_flow_csv = flow_csv_files[-1]
            logger.info(f"Using Flow CSV: {latest_flow_csv}")
            
            # Read the CSV file (GCS-aware)
            df = storage.read_csv(f"reports/{run_id}/{latest_flow_csv}")
            
            if df is None:
                logger.error(f"Failed to read Flow CSV: {latest_flow_csv}")
                return JSONResponse(content=[])
        
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

