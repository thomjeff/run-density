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
        # Load Flow CSV data from Cloud Storage
        import pandas as pd
        import tempfile
        import os
        
        # Download Flow CSV from Cloud Storage
        try:
            # Find the latest Flow CSV file in Cloud Storage
            flow_csv_files = []
            # List files in the reports directory
            import subprocess
            result = subprocess.run(['gsutil', 'ls', 'gs://run-density-reports/reports/*/'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line.endswith('/'):
                        date_dir = line.split('/')[-2]
                        # Check if Flow CSV exists in this date directory
                        flow_csv_path = f"gs://run-density-reports/reports/{date_dir}/*-Flow.csv"
                        flow_result = subprocess.run(['gsutil', 'ls', flow_csv_path], 
                                                    capture_output=True, text=True)
                        if flow_result.returncode == 0 and flow_result.stdout.strip():
                            flow_csv_files.extend(flow_result.stdout.strip().split('\n'))
            
            if not flow_csv_files:
                logger.warning("No Flow CSV files found in Cloud Storage")
                return JSONResponse(content=[])
            
            # Use the latest Flow CSV
            latest_flow_csv = max(flow_csv_files, key=lambda f: f.split('/')[-1])
            logger.info(f"Using Flow CSV: {latest_flow_csv}")
            
            # Download to temporary file
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.csv', delete=False) as tmp_file:
                subprocess.run(['gsutil', 'cp', latest_flow_csv, tmp_file.name], check=True)
                df = pd.read_csv(tmp_file.name)
                os.unlink(tmp_file.name)
        
        except Exception as e:
            logger.error(f"Failed to load Flow CSV from Cloud Storage: {e}")
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

