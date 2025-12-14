"""
Runflow v2 Analyze Endpoint

Implements POST /runflow/v2/analyze endpoint with full validation and stubbed pipeline.
This enables early E2E testing of the API contract while core refactors proceed.

Phase 2: API Route (Issue #496)
"""

from fastapi import APIRouter, HTTPException, status
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

# Create router
router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=V2AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run v2 analysis",
    description="Analyze multiple events across multiple days with day-partitioned outputs"
)
async def analyze_v2(request: V2AnalyzeRequest) -> V2AnalyzeResponse:
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
        # This checks all rules from api_v2.md
        try:
            validate_api_payload(payload_dict)
        except ValidationError as e:
            # Convert ValidationError to HTTPException with proper status code
            raise HTTPException(
                status_code=e.code,
                detail={
                    "message": e.message,
                    "code": e.code
                }
            )
        
        # Load events from payload (creates Event objects)
        events = load_events_from_payload(payload_dict)
        
        # Extract data directory and file names from payload
        data_dir = payload_dict.get("data_dir", "data")
        segments_file = payload_dict.get("segments_file", "segments.csv")
        locations_file = payload_dict.get("locations_file", "locations.csv")
        flow_file = payload_dict.get("flow_file", "flow.csv")
        
        # Run full analysis pipeline (Phase 4 + 5)
        # This creates directory structure AND runs density + flow analysis
        pipeline_result = create_full_analysis_pipeline(
            events=events,
            segments_file=segments_file,
            locations_file=locations_file,
            flow_file=flow_file,
            data_dir=data_dir
        )
        
        # Format output paths for response
        output_paths_dict = {}
        for day_code, paths in pipeline_result["output_paths"].items():
            output_paths_dict[day_code] = V2OutputPaths(**paths)
        
        # Return success response
        return V2AnalyzeResponse(
            run_id=pipeline_result["run_id"],
            status="success",
            days=pipeline_result["days"],
            output_paths=output_paths_dict
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"Unexpected error in v2 analyze endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": f"Internal processing error: {str(e)}",
                "code": 500
            }
        )

