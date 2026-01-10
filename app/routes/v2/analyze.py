"""
Runflow v2 Analyze Endpoint

Implements POST /runflow/v2/analyze endpoint with full validation and stubbed pipeline.
This enables early E2E testing of the API contract while core refactors proceed.

Phase 2: API Route (Issue #496)
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

from app.api.models.v2 import (
    V2AnalyzeRequest,
    V2AnalyzeResponse,
    V2ErrorResponse,
    V2OutputPaths
)
from app.core.v2.validation import ValidationError, validate_api_payload
from app.core.v2.loader import load_events_from_payload
from app.core.v2.pipeline import create_stubbed_pipeline, create_full_analysis_pipeline
from app.core.v2.analysis_config import generate_analysis_json
from app.utils.run_id import generate_run_id, get_runflow_root

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


def run_analysis_background(
    events,
    segments_file: str,
    locations_file: str,
    flow_file: str,
    data_dir: str,
    run_id: str,
    request_payload: Dict[str, Any]
):
    """
    Background task to run the full analysis pipeline.
    
    Issue #554: Analysis runs asynchronously after API returns success response.
    
    Args:
        events: List of Event objects
        segments_file: Segments CSV file name
        locations_file: Locations CSV file name
        flow_file: Flow CSV file name
        data_dir: Data directory path
        run_id: Run identifier
        request_payload: Original request payload for metadata
    """
    try:
        logger.info(f"Starting background analysis for run_id: {run_id}")
        # Extract enableAudit flag from request payload (default 'n')
        enable_audit = request_payload.get('enableAudit', 'n').lower()
        pipeline_result = create_full_analysis_pipeline(
            events=events,
            segments_file=segments_file,
            locations_file=locations_file,
            flow_file=flow_file,
            data_dir=data_dir,
            run_id=run_id,
            request_payload=request_payload,
            enable_audit=enable_audit
        )
        
        # Update metadata.json files with response payload
        from pathlib import Path
        import json
        
        runflow_root = get_runflow_root()
        run_path = runflow_root / run_id
        
        response_payload = {
            "status": "success",
            "code": 200,
            "run_id": pipeline_result["run_id"],
            "days": pipeline_result["days"],
            "output_paths": {
                day: {
                    "day": paths["day"],
                    "reports": paths["reports"],
                    "bins": paths["bins"],
                    "maps": paths["maps"],
                    "ui": paths["ui"],
                    "metadata": paths["metadata"]
                }
                for day, paths in pipeline_result["output_paths"].items()
            }
        }
        
        # Update run-level metadata.json
        run_metadata_path = run_path / "metadata.json"
        if run_metadata_path.exists():
            with open(run_metadata_path, 'r', encoding='utf-8') as f:
                run_metadata = json.load(f)
            run_metadata["response"] = response_payload
            with open(run_metadata_path, 'w', encoding='utf-8') as f:
                json.dump(run_metadata, f, indent=2, ensure_ascii=False)
        
        # Update day-level metadata.json files
        for day_code in pipeline_result["days"]:
            day_metadata_path = run_path / day_code / "metadata.json"
            if day_metadata_path.exists():
                with open(day_metadata_path, 'r', encoding='utf-8') as f:
                    day_metadata = json.load(f)
                day_metadata["response"] = response_payload
                with open(day_metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(day_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Background analysis completed for run_id: {run_id}")
    except Exception as e:
        logger.error(f"Error in background analysis for run_id {run_id}: {e}", exc_info=True)
        # Note: Error is logged but not returned to client since request already returned


@router.post(
    "/analyze",
    response_model=V2AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run v2 analysis",
    description="Analyze multiple events across multiple days with day-partitioned outputs"
)
async def analyze_v2(request: V2AnalyzeRequest, background_tasks: BackgroundTasks) -> V2AnalyzeResponse:
    """
    Main v2 analysis endpoint.
    
    Accepts v2 payload, validates it using Phase 1 validation layer,
    and creates day-partitioned directory structure with stubbed pipeline.
    
    Args:
        request: V2AnalyzeRequest with events and file references
        
    Returns:
        V2AnalyzeResponse with run_id and output paths
        
    Raises:
        HTTPException: With appropriate error code (400, 404, 422, 500)
    """
    try:
        # Convert Pydantic model to dict for validation
        payload_dict = request.model_dump()
        
        # Validate payload using Phase 1 validation layer
        # This checks all rules from Issue #553
        try:
            validate_api_payload(payload_dict)
        except ValidationError as e:
            # Convert ValidationError to V2ErrorResponse format (Issue #553)
            error_response = V2ErrorResponse(
                status="ERROR",
                code=e.code,
                error=e.message
            )
            return JSONResponse(
                status_code=e.code,
                content=error_response.model_dump()
            )
        
        # Generate run_id and create run directory
        run_id = generate_run_id()
        runflow_root = get_runflow_root()
        run_path = runflow_root / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        
        # Phase 2: Generate analysis.json (single source of truth)
        # This must happen before any analysis execution
        try:
            analysis_config = generate_analysis_json(
                request_payload=payload_dict,
                run_id=run_id,
                run_path=run_path
            )
            logger.info(f"Generated analysis.json for run_id: {run_id}")
        except Exception as e:
            logger.error(f"Failed to generate analysis.json: {e}", exc_info=True)
            error_response = V2ErrorResponse(
                status="ERROR",
                code=500,
                error=f"Failed to generate analysis configuration: {str(e)}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response.model_dump()
            )
        
        # Load events from payload (creates Event objects)
        events = load_events_from_payload(payload_dict)
        
        # Extract data directory and file names from analysis.json (single source of truth)
        data_dir = analysis_config.get("data_dir", "data")
        segments_file = analysis_config.get("segments_file")
        locations_file = analysis_config.get("locations_file")
        flow_file = analysis_config.get("flow_file")
        
        # Issue #554: Extract days from events for immediate response
        # We need to determine which days are in the request to return them in the response
        event_days = list(set([event.get("day") for event in payload_dict.get("events", [])]))
        
        # Issue #554: Create stub output paths structure for immediate response
        # The actual paths will be created during background analysis
        from pathlib import Path
        runflow_root = get_runflow_root()
        run_path = runflow_root / run_id
        
        output_paths_dict = {}
        for day_code in event_days:
            # Create stub paths that will be populated during analysis
            output_paths_dict[day_code] = V2OutputPaths(
                day=day_code,
                reports=f"runflow/{run_id}/{day_code}/reports",
                bins=f"runflow/{run_id}/{day_code}/bins",
                maps=f"runflow/{run_id}/{day_code}/maps",
                ui=f"runflow/{run_id}/{day_code}/ui",
                metadata=f"runflow/{run_id}/{day_code}/metadata.json"
            )
        
        # Issue #554: Add background task to run analysis asynchronously
        # This allows the API to return immediately with success response
        background_tasks.add_task(
            run_analysis_background,
            events=events,
            segments_file=segments_file,
            locations_file=locations_file,
            flow_file=flow_file,
            data_dir=data_dir,
            run_id=run_id,
            request_payload=payload_dict
        )
        
        logger.info(f"Analysis request accepted for run_id: {run_id}. Analysis running in background.")
        
        # Return success response immediately (Issue #554)
        return V2AnalyzeResponse(
            run_id=run_id,
            status="success",
            days=event_days,
            output_paths=output_paths_dict
        )
        
    except Exception as e:
        # Catch-all for unexpected errors (Issue #553: use V2ErrorResponse format)
        logger.error(f"Unexpected error in v2 analyze endpoint: {e}", exc_info=True)
        error_response = V2ErrorResponse(
            status="ERROR",
            code=500,
            error=f"Internal processing error: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )
