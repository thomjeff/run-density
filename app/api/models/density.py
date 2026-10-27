"""
Pydantic Models for Density API

Request and response models for density analysis endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DensityAnalysisRequest(BaseModel):
    """Request model for density analysis."""

    segments: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    width_provider: str = "static"
    paceCsv: Optional[str] = None
    segmentsCsv: Optional[str] = None
    startTimes: Optional[Dict[str, int]] = None


class DensityAnalysisResponse(BaseModel):
    """Response model for density analysis."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DensityReportRequest(BaseModel):
    """Request model for density report generation."""

    segment_ids: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    format: str = "json"  # "json" or "csv"


class DensityReportResponse(BaseModel):
    """Response model for density report generation."""

    success: bool
    report_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
