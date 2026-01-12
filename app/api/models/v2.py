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
    
    Issue #553: Extended to include event_duration_minutes and updated start_time range.
    
    Attributes:
        name: Event name (lowercase, e.g., "full", "half", "10k")
        day: Day code (fri, sat, sun, mon)
        start_time: Start time in minutes after midnight (300-1200, inclusive)
        event_duration_minutes: Event duration in minutes (1-500, inclusive)
        runners_file: Name of runners CSV file (relative to /data)
        gpx_file: Name of GPX file (relative to /data)
    """
    name: str = Field(..., description="Event name (lowercase)")
    day: str = Field(..., description="Day code (fri, sat, sun, mon)")
    start_time: int = Field(..., ge=300, le=1200, description="Start time in minutes after midnight (300-1200)")
    event_duration_minutes: int = Field(..., ge=1, le=500, description="Event duration in minutes (1-500)")
    runners_file: str = Field(..., description="Name of runners CSV file")
    gpx_file: str = Field(..., description="Name of GPX file")
    
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
    
    Issue #553: Extended to include description field and removed defaults (fail-fast).
    Issue #573: Extended to include event_group field for Runner Experience Score (RES) calculation.
    Issue #680: Extended to include data_dir field for flexible data directory configuration.
    
    Attributes:
        description: Optional description for the analysis (max 254 characters)
        data_dir: Optional data directory path (defaults to DATA_ROOT env var or 'data')
        segments_file: Name of segments CSV file (required, no default)
        locations_file: Name of locations CSV file (required, no default)
        flow_file: Name of flow CSV file (required, no default)
        events: List of event definitions
        event_group: Optional event grouping configuration for RES calculation
            Format: {"group_id": "event1, event2, ..."} where group_id is descriptive (e.g., "sat/elite")
            and value is comma-separated list of event names (e.g., "elite" or "full, 10k, half")
        enableAudit: Enable detailed flow audit generation ('y' or 'n', default 'n')
            When 'y', generates detailed CSV shard files with runner pair overtake information
    """
    description: Optional[str] = Field(None, max_length=254, description="Optional description for the analysis (max 254 characters)")
    data_dir: Optional[str] = Field(None, description="Data directory path (defaults to DATA_ROOT env var or 'data')")
    segments_file: str = Field(..., description="Name of segments CSV file")
    locations_file: str = Field(..., description="Name of locations CSV file")
    flow_file: str = Field(..., description="Name of flow CSV file")
    events: List[V2EventRequest] = Field(..., min_length=1, description="List of events to analyze")
    event_group: Optional[Dict[str, str]] = Field(None, description="Optional event grouping for RES calculation (format: {\"group_id\": \"event1, event2, ...\"})")
    enableAudit: str = Field(default='n', pattern='^[yn]$', description="Enable detailed flow audit generation ('y' or 'n')")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "Scenario to test 10k on Saturday",
                "data_dir": "/app/data",
                "segments_file": "segments.csv",
                "locations_file": "locations.csv",
                "flow_file": "flow.csv",
                "events": [
                    {
                        "name": "10k",
                        "day": "sat",
                        "start_time": 510,
                        "event_duration_minutes": 120,
                        "runners_file": "10k_runners.csv",
                        "gpx_file": "10k.gpx"
                    },
                    {
                        "name": "half",
                        "day": "sun",
                        "start_time": 540,
                        "event_duration_minutes": 180,
                        "runners_file": "half_runners.csv",
                        "gpx_file": "half.gpx"
                    }
                ],
                "event_group": {
                    "sat/10k": "10k",
                    "sun/half": "half"
                },
                "enableAudit": "n"
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
    Error response model matching Issue #553 error format.
    
    Issue #553: Updated to match error response format with status, code, and error fields.
    
    Attributes:
        status: Status string ("ERROR")
        code: HTTP error code (400, 404, 406, 422, 500)
        error: Error message with details
    """
    status: str = Field(default="ERROR", description="Status string")
    code: int = Field(..., description="HTTP error code (400, 404, 406, 422, 500)")
    error: str = Field(..., description="Error message with details")

