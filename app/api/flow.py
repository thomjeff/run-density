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
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        import pandas as pd
        from app.utils.metadata import get_latest_run_id
        from app.storage import create_runflow_storage
        
        run_id = get_latest_run_id()
        storage = create_runflow_storage(run_id)
        
        # Load Flow CSV from runflow structure
        try:
            # Flow.csv is at: runflow/<run_id>/reports/Flow.csv
            csv_content = storage.read_file("reports/Flow.csv")
            
            if not csv_content:
                logger.error("Failed to read Flow CSV: file is empty")
                return JSONResponse(content=[])
            
            # Parse CSV content
            from io import StringIO
            df = pd.read_csv(StringIO(csv_content))
        
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

