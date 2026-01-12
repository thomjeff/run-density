"""
API Routes for Baseline Runner File Generation

Provides endpoints for calculating baseline metrics and generating scenario-based runner files.

Issue: #676 - Utility to create new runner files
"""

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import logging
import zipfile
import io

from app.core.baseline import (
    calculate_baseline_metrics,
    generate_runner_file,
    create_baseline_directory,
    save_baseline_metrics,
    save_generated_files,
    validate_runner_file,
    validate_control_variables,
)
from app.core.baseline.validation import validate_cutoff_time_format
from app.core.v2.analysis_config import get_data_directory
from app.utils.run_id import get_runflow_root
from app.utils.shared import load_pace_csv

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/baseline/calculate")
async def calculate_baseline(
    request: Dict[str, Any]
) -> JSONResponse:
    """
    Calculate baseline metrics from selected runner CSV files.
    
    Phase 1 of two-phase API: Calculate baseline metrics (idempotent, no directory creation).
    
    Request Body:
        {
            "selected_files": ["elite_runners.csv", "open_runners.csv"],
            "data_dir": "/app/data"  # Optional, defaults to get_data_directory()
        }
    
    Response:
        {
            "data_dir": "/app/data",
            "reports_path": "/app/runflow",
            "selected_files": [...],
            "baseline_metrics": {
                "elite": {
                    "runners_file": "elite_runners.csv",
                    "base_participants": 39,
                    "base_p00": 2.90,
                    "base_p05": 2.918,
                    ...
                }
            }
        }
    
    Note: Directory and run_id are created in Phase 2 (/api/baseline/generate).
    
    Issue: #676 - Baseline calculation endpoint
    """
    try:
        # Get parameters
        selected_files = request.get("selected_files", [])
        if not selected_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_files is required and must not be empty"
            )
        
        data_dir = request.get("data_dir")
        if data_dir is None:
            data_dir = get_data_directory()
        
        data_path = Path(data_dir)
        if not data_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data directory does not exist: {data_dir}"
            )
        
        # Get reports path (runflow root) - for response only, not creating directory yet
        reports_path = get_runflow_root()
        
        # Calculate baseline metrics for each selected file
        baseline_metrics = {}
        
        for file_name in selected_files:
            # Extract event name from file name (e.g., "elite_runners.csv" -> "elite")
            if not file_name.endswith("_runners.csv"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid runner file name: {file_name}. Must end with '_runners.csv'"
                )
            
            event_name = file_name.replace("_runners.csv", "")
            
            # Load and validate runner file
            file_path = data_path / file_name
            validate_runner_file(file_path)
            
            # Load runners DataFrame
            runners_df = load_pace_csv(str(file_path))
            
            # Calculate baseline metrics
            metrics = calculate_baseline_metrics(runners_df)
            metrics["runners_file"] = file_name
            baseline_metrics[event_name] = metrics
        
        # Build response (no directory creation, no run_id)
        response = {
            "data_dir": str(data_dir),
            "reports_path": str(reports_path),
            "selected_files": selected_files,
            "baseline_metrics": baseline_metrics
        }
        
        logger.info(f"Calculated baseline metrics for {len(selected_files)} files (no directory created yet)")
        return JSONResponse(content=response, status_code=status.HTTP_200_OK)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating baseline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate baseline: {str(e)}"
        )


@router.post("/api/baseline/generate")
async def generate_scenario(
    request: Dict[str, Any]
) -> JSONResponse:
    """
    Generate new runner files with scenario-based modifications.
    
    Phase 2 of two-phase API: Create directory, save baseline.json, apply control variables and generate files.
    
    Request Body:
        {
            "baseline_metrics": {
                "elite": {
                    "runners_file": "elite_runners.csv",
                    "base_participants": 39,
                    ...
                }
            },
            "selected_files": ["elite_runners.csv", ...],
            "data_dir": "/app/data",
            "control_variables": {
                "elite": {
                    "chg_participants": 0.1026,
                    "chg_p00": 0.0,
                    "chg_p05": 0.0,
                    "chg_p25": 0.0,
                    "chg_p50": 0.0,
                    "chg_p75": 0.0,
                    "chg_p95": 0.0,
                    "chg_p100": 0.0,
                    "cutoff_mins": null  # Optional, or "06:00" format
                }
            }
        }
    
    Response:
        {
            "run_id": "4sawTqXz9CExYcQgJTNQCr",
            "generated_files": [
                {
                    "event": "elite",
                    "path": "/app/runflow/baseline/.../elite_runners.csv"
                }
            ],
            "updated_baseline_json": {...}
        }
    
    Issue: #676 - Scenario generation endpoint
    """
    try:
        import json
        
        # Get parameters
        baseline_metrics = request.get("baseline_metrics", {})
        selected_files = request.get("selected_files", [])
        data_dir = request.get("data_dir")
        control_variables = request.get("control_variables", {})
        
        # Validate required parameters
        if not baseline_metrics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="baseline_metrics is required"
            )
        
        if not selected_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="selected_files is required"
            )
        
        if not data_dir:
            data_dir = get_data_directory()
        
        if not control_variables:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="control_variables is required and must not be empty"
            )
        
        # Validate control variables (before creating directory)
        validate_control_variables(control_variables)
        
        # Validate that all events in control_variables exist in baseline_metrics
        for event_name in control_variables.keys():
            if event_name not in baseline_metrics:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Event '{event_name}' not found in baseline metrics"
                )
        
        # Validate cutoff time formats (before creating directory)
        data_dir_path = Path(data_dir)
        for event_name, control_vars in control_variables.items():
            cutoff_str = control_vars.get("cutoff_mins")
            if cutoff_str:
                if isinstance(cutoff_str, str):
                    # Validate format (will raise ValueError if invalid)
                    validate_cutoff_time_format(cutoff_str)
        
        # Generate all files in memory first and validate all cutoffs BEFORE creating directory
        data_dir_path = Path(data_dir)
        generated_dataframes = {}  # Store generated DataFrames in memory
        new_baseline_metrics = {}
        used_runner_ids = set()  # Track across all events for uniqueness
        
        for event_name, control_vars in control_variables.items():
            # Get baseline metrics for this event (already validated above)
            event_metrics = baseline_metrics[event_name]
            base_participants = event_metrics["base_participants"]
            distance = event_metrics["distance"]
            
            # Calculate new participant count
            chg_participants = control_vars["chg_participants"]
            new_participants = int(base_participants * (1 + chg_participants))
            
            # Parse cut-off time if provided
            cutoff_mins = None
            cutoff_str = control_vars.get("cutoff_mins")
            if cutoff_str:
                if isinstance(cutoff_str, str):
                    cutoff_mins = validate_cutoff_time_format(cutoff_str)
                elif isinstance(cutoff_str, (int, float)):
                    cutoff_mins = float(cutoff_str)
            
            # Load baseline runner file
            runners_file = event_metrics["runners_file"]
            runners_path = data_dir_path / runners_file
            if not runners_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Baseline runner file not found: {runners_path}"
                )
            
            baseline_df = load_pace_csv(str(runners_path))
            
            # Generate new runner file in memory (this validates cutoff time)
            new_df = generate_runner_file(
                baseline_df=baseline_df,
                control_vars=control_vars,
                new_participants=new_participants,
                event_name=event_name,
                distance=distance,
                cutoff_mins=cutoff_mins,
                used_runner_ids=used_runner_ids
            )
            
            # Store generated DataFrame (not saved yet)
            generated_dataframes[event_name] = {
                "df": new_df,
                "runners_file": runners_file
            }
            
            # Calculate new baseline metrics from generated file
            new_metrics = calculate_baseline_metrics(new_df)
            new_metrics["runners_file"] = runners_file
            new_baseline_metrics[event_name] = {
                "new_participants": new_participants,
                "new_p00": new_metrics["base_p00"],
                "new_p05": new_metrics["base_p05"],
                "new_p25": new_metrics["base_p25"],
                "new_p50": new_metrics["base_p50"],
                "new_p75": new_metrics["base_p75"],
                "new_p95": new_metrics["base_p95"],
                "new_p100": new_metrics["base_p100"]
            }
        
        # All validations passed (including cutoff time validation)
        # Return new baseline metrics only (no directory creation, no file saving)
        # Directory and files will be created when user clicks "Create New Files"
        
        # Store generated dataframes in response for later use (will be passed to create-files endpoint)
        # Note: We can't actually store DataFrames in JSON, so we'll regenerate them in create-files
        
        response = {
            "new_baseline_metrics": new_baseline_metrics,
            "generated_dataframes_info": {
                event_name: {"runners_file": file_data["runners_file"]}
                for event_name, file_data in generated_dataframes.items()
            }
        }
        
        logger.info(
            f"Calculated new baseline metrics for {len(control_variables)} events (no directory created)"
        )
        return JSONResponse(content=response, status_code=status.HTTP_200_OK)
    
    except HTTPException:
        raise
    except ValueError as e:
        # Cut-off validation or other ValueError
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating scenario: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate scenario: {str(e)}"
        )


@router.get("/api/baseline/files")
async def list_generated_files(
    run_id: str
) -> JSONResponse:
    """
    List generated runner CSV files for a baseline run.
    
    Args:
        run_id: Baseline run ID
    
    Returns:
        List of generated file information with reports_path
    
    Issue: #676 - File listing endpoint
    """
    try:
        reports_path = get_runflow_root()
        baseline_dir = reports_path / "baseline" / run_id
        
        if not baseline_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Baseline run_id not found: {run_id}"
            )
        
        # Load baseline.json
        baseline_json_path = baseline_dir / "baseline.json"
        if not baseline_json_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"baseline.json not found for run_id: {run_id}"
            )
        
        import json
        with open(baseline_json_path, "r") as f:
            baseline_json = json.load(f)
        
        generated_files = baseline_json.get("generated_files", [])
        
        return JSONResponse(
            content={
                "files": generated_files,
                "reports_path": str(reports_path)
            },
            status_code=status.HTTP_200_OK
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.post("/api/baseline/apply-suffix")
async def apply_file_suffix(
    request: Dict[str, Any]
) -> JSONResponse:
    """
    Apply file name suffix to generated baseline files.
    
    Renames existing generated files to include the suffix before .csv extension.
    
    Request Body:
        {
            "baseline_run_id": "4sawTqXz9CExYcQgJTNQCr",
            "file_suffix": "_issue676"  # Optional, text to append before .csv
        }
    
    Response:
        {
            "renamed_files": [
                {
                    "event": "elite",
                    "old_filename": "elite_runners.csv",
                    "new_filename": "elite_runners_issue676.csv",
                    "path": "/app/runflow/baseline/.../elite_runners_issue676.csv"
                }
            ]
        }
    
    Issue: #676 - File name suffix application
    """
    try:
        baseline_run_id = request.get("baseline_run_id")
        if not baseline_run_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="baseline_run_id is required"
            )
        
        file_suffix = request.get("file_suffix")
        if not file_suffix:
            # No suffix provided, return existing files
            file_suffix = None
        
        # Validate suffix format if provided
        if file_suffix and not all(c.isalnum() or c in ['_', '-'] for c in file_suffix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_suffix can only contain letters, numbers, underscores, and hyphens"
            )
        
        # Get baseline directory
        reports_path = get_runflow_root()
        baseline_dir = reports_path / "baseline" / baseline_run_id
        
        if not baseline_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Baseline run_id not found: {baseline_run_id}"
            )
        
        # Load baseline.json
        baseline_json_path = baseline_dir / "baseline.json"
        if not baseline_json_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"baseline.json not found for run_id: {baseline_run_id}"
            )
        
        import json
        import shutil
        
        with open(baseline_json_path, "r") as f:
            baseline_json = json.load(f)
        
        generated_files = baseline_json.get("generated_files", [])
        
        if not generated_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No generated files found. Please generate files first."
            )
        
        renamed_files = []
        
        if file_suffix:
            # Rename files with suffix
            for file_info in generated_files:
                old_filename = file_info.get("filename") or Path(file_info["path"]).name
                old_path = baseline_dir / old_filename
                
                if not old_path.exists():
                    logger.warning(f"File not found for renaming: {old_path}")
                    continue
                
                # Insert suffix before .csv extension
                if old_filename.endswith(".csv"):
                    base_name = old_filename[:-4]  # Remove .csv
                    new_filename = f"{base_name}{file_suffix}.csv"
                else:
                    new_filename = f"{old_filename}{file_suffix}"
                
                new_path = baseline_dir / new_filename
                
                # Rename file
                shutil.move(str(old_path), str(new_path))
                
                renamed_files.append({
                    "event": file_info.get("event", ""),
                    "old_filename": old_filename,
                    "new_filename": new_filename,
                    "path": str(new_path)
                })
                
                # Update file_info in generated_files list
                file_info["filename"] = new_filename
                file_info["path"] = str(new_path)
            
            # Update baseline.json with renamed files
            baseline_json["generated_files"] = generated_files
            baseline_json["file_suffix"] = file_suffix
            
            with open(baseline_json_path, "w") as f:
                json.dump(baseline_json, f, indent=2)
            
            logger.info(f"Applied suffix '{file_suffix}' to {len(renamed_files)} files")
        else:
            # No suffix, return existing files as-is
            renamed_files = [
                {
                    "event": f.get("event", ""),
                    "old_filename": f.get("filename") or Path(f["path"]).name,
                    "new_filename": f.get("filename") or Path(f["path"]).name,
                    "path": f["path"]
                }
                for f in generated_files
            ]
        
        return JSONResponse(
            content={"renamed_files": renamed_files},
            status_code=status.HTTP_200_OK
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying file suffix: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply file suffix: {str(e)}"
        )


@router.get("/api/baseline/download")
def download_baseline_files(
    run_id: str = Query(..., description="Baseline run ID")
) -> StreamingResponse:
    """
    Download all files from a baseline run directory as a ZIP archive.
    
    Args:
        run_id: Baseline run ID
    
    Returns:
        ZIP file containing all files from the baseline run directory
    
    Issue: #676 - File download endpoint
    """
    try:
        reports_path = get_runflow_root()
        baseline_dir = reports_path / "baseline" / run_id
        
        logger.info(f"[Download] Requested baseline run_id: {run_id}, path: {baseline_dir}")
        
        if not baseline_dir.exists():
            logger.warning(f"[Download] Baseline directory not found: {baseline_dir}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Baseline run_id not found: {run_id}"
            )
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all files in the baseline directory
            files_added = 0
            for file_path in baseline_dir.rglob('*'):
                if file_path.is_file():
                    # Get relative path from baseline_dir for archive structure
                    arcname = file_path.relative_to(baseline_dir)
                    zip_file.write(file_path, arcname)
                    files_added += 1
        
        logger.info(f"[Download] Added {files_added} files to ZIP for run_id: {run_id}")
        
        zip_buffer.seek(0)
        
        # Return ZIP file as StreamingResponse (same pattern as Reports download)
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=baseline_{run_id}.zip"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading baseline files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download files: {str(e)}"
        )
