"""
Pydantic Models for Report API

Request and response models for report generation endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


class ReportRequest(BaseModel):
    """Request model for report generation."""
    report_type: str = Field(..., alias="reportType")  # "density" or "flow"
    segment_ids: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    format: str = "json"  # "json" or "csv"


class ReportResponse(BaseModel):
    """Response model for report generation."""
    success: bool
    report_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CombinedReportRequest(BaseModel):
    """Request model for combined report generation."""
    pace_csv: str
    segments_csv: str
    start_times: Dict[str, float]
    step_km: float = 0.3
    time_window_s: float = 30.0
    min_overlap_duration: float = 60.0
    include_density: bool = True
    include_overtake: bool = True


class CombinedReportResponse(BaseModel):
    """Response model for combined report generation."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
