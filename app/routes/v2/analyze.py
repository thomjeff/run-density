"""
Runflow v2 Analyze Endpoint

Implements POST /runflow/v2/analyze endpoint with full validation and stubbed pipeline.
This enables early E2E testing of the API contract while core refactors proceed.

Phase 2: API Route (Issue #496)
"""

from fastapi import APIRouter, BackgroundTasks, status
from fastapi.responses import JSONResponse
import logging

from app.api.models.v2 import V2AnalyzeRequest, V2AnalyzeResponse, V2ErrorResponse
from app.core.v2.analysis_submit import submit_v2_analysis

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/analyze",
    response_model=V2AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Run v2 analysis",
    description="Analyze multiple events across multiple days with day-partitioned outputs",
)
async def analyze_v2(request: V2AnalyzeRequest, background_tasks: BackgroundTasks) -> V2AnalyzeResponse:
    """Main v2 analysis endpoint."""
    try:
        return submit_v2_analysis(request.model_dump(), background_tasks)
    except Exception as e:
        logger.error("Unexpected error in v2 analyze endpoint: %s", e, exc_info=True)
        error_response = V2ErrorResponse(
            status="ERROR",
            code=500,
            error=f"Internal processing error: {str(e)}",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
        )
