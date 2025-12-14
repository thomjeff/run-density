"""
API Routes for Flow Data (RF-FE-002)

Provides temporal flow analysis endpoints for the flow page.

Author: Cursor AI Assistant (per ChatGPT specification)
Epic: RF-FE-002 | Issue: #279 | Step: 8
Architecture: Option 3 - Hybrid Approach
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
import json

# Issue #466 Step 2: Storage consolidated to app.storage


# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Issue #466 Step 2: Removed legacy storage singleton (not needed)


@router.get("/api/flow/segments")
async def get_flow_segments(
    run_id: Optional[str] = Query(None, description="Run ID (defaults to latest)"),
    day: Optional[str] = Query(None, description="Day code (fri|sat|sun|mon)")
):
    """
    Get flow analysis data for all segments from Flow CSV.
    
    Args:
        run_id: Optional run ID (defaults to latest)
        day: Optional day code (fri|sat|sun|mon) for day-scoped data
    
    Returns:
        Array of flow records with event pairs.
        Each row represents a segment-event_a-event_b combination.
    """
    try:
        # Issue #460 Phase 5: Get latest run_id from runflow/latest.json
        import pandas as pd
        from app.utils.run_id import get_latest_run_id, resolve_selected_day
        from app.storage import create_runflow_storage
        
        # Resolve run_id and day
        if not run_id:
            run_id = get_latest_run_id()
        selected_day, available_days = resolve_selected_day(run_id, day)
        storage = create_runflow_storage(run_id)
        
        # Load Flow CSV from day-scoped path
        try:
            # Flow.csv is at: runflow/<run_id>/<day>/reports/Flow.csv
            csv_content = storage.read_text(f"{selected_day}/reports/Flow.csv")
            
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
        
        logger.info(f"Loaded {len(flow_records)} flow records for day {selected_day}")
        
        response = JSONResponse(content={
            "selected_day": selected_day,
            "available_days": available_days,
            "flow": flow_records
        })
        response.headers["Cache-Control"] = "public, max-age=60"
        return response
        
    except ValueError as e:
        # Convert ValueError from resolve_selected_day to HTTPException
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating flow segments: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load flow data: {str(e)}")

