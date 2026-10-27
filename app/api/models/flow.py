"""
Pydantic Models for Flow API

Request and response models for flow analysis endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FlowSegmentsResponse(BaseModel):
    """Response model for flow segments endpoint."""

    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class FlowAnalysisRequest(BaseModel):
    """Request model for flow analysis."""

    segment_ids: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    format: str = "json"


class FlowAnalysisResponse(BaseModel):
    """Response model for flow analysis."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
