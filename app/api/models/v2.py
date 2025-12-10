"""
Pydantic Models for Runflow v2 API

Defines request and response models for the v2 API endpoints.
Matches the API specification in runflow_v2/docs/api_v2.md.

Phase 2: API Route (Issue #496)
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class V2EventRequest(BaseModel):
    """
    Event request model matching api_v2.md event structure.
    
    Attributes:
        name: Event name (lowercase, e.g., "full", "half", "10k")
        day: Day code (fri, sat, sun, mon)
        start_time: Start time in minutes after midnight (0-1439)
        runners_file: Path to runners CSV file (relative to /data)
        gpx_file: Path to GPX file (relative to /data)
    """
    name: str = Field(..., description="Event name (lowercase)")
    day: str = Field(..., description="Day code (fri, sat, sun, mon)")
    start_time: int = Field(..., ge=0, le=1439, description="Start time in minutes after midnight")
    runners_file: str = Field(..., description="Path to runners CSV file")
    gpx_file: str = Field(..., description="Path to GPX file")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Normalize event name to lowercase."""
        return v.lower()
    
    @field_validator('day')
    @classmethod
    def validate_day(cls, v: str) -> str:
        """Normalize day code to lowercase."""
        return v.lower()


class V2AnalyzeRequest(BaseModel):
    """
    Main request model for POST /runflow/v2/analyze.
    
    Matches the API specification in api_v2.md.
    
    Attributes:
        segments_file: Path to segments.csv file (default: "segments.csv")
        locations_file: Path to locations.csv file (default: "locations.csv")
        flow_file: Path to flow.csv file (default: "flow.csv")
        events: List of event definitions
    """
    segments_file: str = Field(default="segments.csv", description="Path to segments CSV file")
    locations_file: str = Field(default="locations.csv", description="Path to locations CSV file")
    flow_file: str = Field(default="flow.csv", description="Path to flow CSV file")
    events: List[V2EventRequest] = Field(..., min_length=1, description="List of events to analyze")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "segments_file": "segments.csv",
                "locations_file": "locations.csv",
                "flow_file": "flow.csv",
                "events": [
                    {
                        "name": "full",
                        "day": "sun",
                        "start_time": 420,
                        "runners_file": "full_runners.csv",
                        "gpx_file": "full.gpx"
                    }
                ]
            }
        }
    }


class V2OutputPaths(BaseModel):
    """Output paths for a specific day."""
    day: str = Field(..., description="Day code (fri, sat, sun, mon)")
    reports: str = Field(..., description="Path to reports directory")
    bins: str = Field(..., description="Path to bins directory")
    maps: str = Field(..., description="Path to maps directory")
    ui: str = Field(..., description="Path to UI directory")
    metadata: str = Field(..., description="Path to metadata.json file")


class V2AnalyzeResponse(BaseModel):
    """
    Response model for POST /runflow/v2/analyze.
    
    Attributes:
        run_id: Unique run identifier (UUID)
        status: Status of the analysis ("success" or error details)
        days: List of processed day codes
        output_paths: Dictionary mapping day codes to output paths
    """
    run_id: str = Field(..., description="Unique run identifier (UUID)")
    status: str = Field(default="success", description="Status of the analysis")
    days: List[str] = Field(..., description="List of processed day codes")
    output_paths: Dict[str, V2OutputPaths] = Field(..., description="Output paths per day")


class V2ErrorResponse(BaseModel):
    """
    Error response model matching api_v2.md error format.
    
    Attributes:
        message: Error message
        code: HTTP error code (400, 404, 422, 500)
    """
    message: str = Field(..., description="Error message")
    code: int = Field(..., description="HTTP error code")

