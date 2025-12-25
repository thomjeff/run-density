"""
Runflow v2 Validation Module

Provides comprehensive validation for API v2 payloads, files, and data structures.
All validation functions return structured errors with HTTP error codes per api_v2.md.

Phase 1: Models & Validation Layer (Issue #495)
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from app.core.v2.models import Day, Event


class ValidationError(Exception):
    """
    Validation error with HTTP error code and message.
    
    Error codes per api_v2.md:
    - 400: Bad request (missing required field, invalid format, duplicate event names, invalid day)
    - 404: File not found
    - 422: Unprocessable entity (malformed CSV, invalid data)
    """
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(self.message)


def validate_day_codes(events: List[Dict[str, Any]]) -> None:
    """
    Validate day codes match vocabulary ["fri", "sat", "sun", "mon"].
    
    Args:
        events: List of event dictionaries from API payload
        
    Raises:
        ValidationError (400): If any event has invalid day code
    """
    valid_days = {"fri", "sat", "sun", "mon"}
    
    for event in events:
        day = event.get("day", "").lower()
        if day not in valid_days:
            raise ValidationError(
                f"Invalid day code '{day}' for event '{event.get('name', 'unknown')}'. "
                f"Must be one of: {sorted(valid_days)}",
                code=400
            )


def validate_start_times(events: List[Dict[str, Any]]) -> None:
    """
    Validate start_time is integer between 300 and 1200 (inclusive).
    
    Issue #553: Updated range to 300-1200 (5:00 AM to 8:00 PM).
    
    Args:
        events: List of event dictionaries from API payload
        
    Raises:
        ValidationError (400): If any start_time is out of range or not an integer
    """
    for event in events:
        start_time = event.get("start_time")
        event_name = event.get("name", "unknown")
        
        if start_time is None:
            raise ValidationError(
                f"Missing required field 'start_time' for event '{event_name}'",
                code=400
            )
        
        if not isinstance(start_time, int):
            raise ValidationError(
                f"start_time must be an integer for event '{event_name}', got {type(start_time).__name__}",
                code=400
            )
        
        if start_time < 300 or start_time > 1200:
            raise ValidationError(
                f"start_time {start_time} for event '{event_name}' must be between 300 and 1200 (5:00 AM to 8:00 PM)",
                code=400
            )


def validate_event_names(events: List[Dict[str, Any]]) -> None:
    """
    Validate event names are unique (no duplicates).
    
    Args:
        events: List of event dictionaries from API payload
        
    Raises:
        ValidationError (400): If duplicate event names found
    """
    seen_names = set()
    for event in events:
        name = event.get("name", "").lower()
        if not name:
            raise ValidationError(
                "Missing required field 'name' in event",
                code=400
            )
        if name in seen_names:
            raise ValidationError(
                f"Duplicate event name '{name}'. Event names must be unique.",
                code=400
            )
        seen_names.add(name)


def validate_file_existence(
    segments_file: str,
    locations_file: str,
    flow_file: str,
    events: List[Dict[str, Any]],
    data_dir: str = "data"
) -> None:
    """
    Validate all files referenced in payload exist in /data directory.
    
    Args:
        segments_file: Path to segments.csv file
        locations_file: Path to locations.csv file
        flow_file: Path to flow.csv file
        events: List of event dictionaries with runners_file and gpx_file
        data_dir: Base directory for data files (default: "data")
        
    Raises:
        ValidationError (404): If any file is missing
    """
    data_path = Path(data_dir)
    
    # Check segments, locations, flow files
    required_files = [
        ("segments_file", segments_file),
        ("locations_file", locations_file),
        ("flow_file", flow_file),
    ]
    
    for file_type, filename in required_files:
        file_path = data_path / filename
        if not file_path.exists():
            raise ValidationError(
                f"{file_type} '{filename}' not found in {data_dir}/ directory",
                code=404
            )
    
    # Check event-specific files
    for event in events:
        event_name = event.get("name", "unknown")
        
        # Check runners_file
        runners_file = event.get("runners_file")
        if not runners_file:
            raise ValidationError(
                f"Missing required field 'runners_file' for event '{event_name}'",
                code=400
            )
        runners_path = data_path / runners_file
        if not runners_path.exists():
            raise ValidationError(
                f"runners_file '{runners_file}' for event '{event_name}' not found in {data_dir}/ directory",
                code=404
            )
        
        # Check gpx_file
        gpx_file = event.get("gpx_file")
        if not gpx_file:
            raise ValidationError(
                f"Missing required field 'gpx_file' for event '{event_name}'",
                code=400
            )
        gpx_path = data_path / gpx_file
        if not gpx_path.exists():
            raise ValidationError(
                f"gpx_file '{gpx_file}' for event '{event_name}' not found in {data_dir}/ directory",
                code=404
            )
        
        # Validate file extensions
        if not runners_file.endswith('.csv'):
            raise ValidationError(
                f"runners_file '{runners_file}' must have .csv extension",
                code=400
            )
        if not gpx_file.endswith('.gpx'):
            raise ValidationError(
                f"gpx_file '{gpx_file}' must have .gpx extension",
                code=400
            )


def validate_segment_spans(
    segments_file: str,
    events: List[Dict[str, Any]],
    data_dir: str = "data"
) -> None:
    """
    Validate segments.csv includes {event}_from_km and {event}_to_km columns for each requested event.
    
    Args:
        segments_file: Path to segments.csv file
        events: List of event dictionaries (need event names)
        data_dir: Base directory for data files (default: "data")
        
    Raises:
        ValidationError (422): If required span columns are missing
    """
    segments_path = Path(data_dir) / segments_file
    
    try:
        segments_df = pd.read_csv(segments_path)
    except Exception as e:
        raise ValidationError(
            f"Failed to read segments.csv: {str(e)}",
            code=422
        )
    
    # Check for required columns
    required_base_columns = ["seg_id"]
    missing_base = [col for col in required_base_columns if col not in segments_df.columns]
    if missing_base:
        raise ValidationError(
            f"segments.csv missing required columns: {missing_base}",
            code=422
        )
    
    # Check per-event span columns
    for event in events:
        event_name = event.get("name", "").lower()
        if not event_name:
            continue
        
        from_col = f"{event_name}_from_km"
        to_col = f"{event_name}_to_km"
        
        missing_cols = []
        if from_col not in segments_df.columns:
            missing_cols.append(from_col)
        if to_col not in segments_df.columns:
            missing_cols.append(to_col)
        
        if missing_cols:
            raise ValidationError(
                f"segments.csv missing required span columns for event '{event_name}': {missing_cols}",
                code=422
            )


def validate_runner_uniqueness(
    events: List[Dict[str, Any]],
    data_dir: str = "data"
) -> None:
    """
    Validate no duplicate runner_id across all runner files.
    
    Args:
        events: List of event dictionaries with runners_file
        data_dir: Base directory for data files (default: "data")
        
    Raises:
        ValidationError (422): If duplicate runner IDs found
    """
    data_path = Path(data_dir)
    all_runner_ids = {}
    
    for event in events:
        event_name = event.get("name", "unknown")
        runners_file = event.get("runners_file")
        
        if not runners_file:
            continue
        
        runners_path = data_path / runners_file
        
        try:
            runners_df = pd.read_csv(runners_path)
        except Exception as e:
            raise ValidationError(
                f"Failed to read runners_file '{runners_file}' for event '{event_name}': {str(e)}",
                code=422
            )
        
        # Check required columns
        required_columns = ["runner_id", "event", "pace", "distance", "start_offset"]
        missing_cols = [col for col in required_columns if col not in runners_df.columns]
        if missing_cols:
            raise ValidationError(
                f"runners_file '{runners_file}' for event '{event_name}' missing required columns: {missing_cols}",
                code=422
            )
        
        # Check for duplicate runner_ids within this file
        duplicates_in_file = runners_df[runners_df.duplicated(subset=["runner_id"], keep=False)]
        if not duplicates_in_file.empty:
            dup_ids = duplicates_in_file["runner_id"].unique().tolist()
            raise ValidationError(
                f"Duplicate runner_id values in '{runners_file}' for event '{event_name}': {dup_ids}",
                code=422
            )
        
        # Check for cross-event duplicates
        for runner_id in runners_df["runner_id"]:
            if runner_id in all_runner_ids:
                conflicting_event = all_runner_ids[runner_id]
                raise ValidationError(
                    f"Duplicate runner_id '{runner_id}' found in both event '{conflicting_event}' and event '{event_name}'. "
                    f"Runner IDs must be unique across all events.",
                    code=422
                )
            all_runner_ids[runner_id] = event_name


def validate_description(description: Optional[str]) -> None:
    """
    Validate description field length (max 254 characters).
    
    Issue #553: Added description validation.
    
    Args:
        description: Optional description string
        
    Raises:
        ValidationError (400): If description exceeds 254 characters
    """
    if description is not None and len(description) > 254:
        raise ValidationError(
            f"description exceeds 254 characters (got {len(description)} characters)",
            code=400
        )


def validate_event_duration_range(events: List[Dict[str, Any]]) -> None:
    """
    Validate event_duration_minutes is integer between 1 and 500 (inclusive).
    
    Issue #553: Added event_duration_minutes validation.
    
    Args:
        events: List of event dictionaries from API payload
        
    Raises:
        ValidationError (400): If any event_duration_minutes is out of range or not an integer
    """
    for event in events:
        duration = event.get("event_duration_minutes")
        event_name = event.get("name", "unknown")
        
        if duration is None:
            raise ValidationError(
                f"Missing required field 'event_duration_minutes' for event '{event_name}'",
                code=400
            )
        
        if not isinstance(duration, int):
            raise ValidationError(
                f"event_duration_minutes must be an integer for event '{event_name}', got {type(duration).__name__}",
                code=400
            )
        
        if duration < 1 or duration > 500:
            raise ValidationError(
                f"event_duration_minutes {duration} for event '{event_name}' must be between 1 and 500 (inclusive)",
                code=400
            )


def validate_gpx_files(
    events: List[Dict[str, Any]],
    data_dir: str = "data"
) -> None:
    """
    Validate GPX files are parseable (basic XML structure check).
    
    Args:
        events: List of event dictionaries with gpx_file
        data_dir: Base directory for data files (default: "data")
        
    Raises:
        ValidationError (422): If GPX file is invalid or unparseable
    """
    data_path = Path(data_dir)
    
    for event in events:
        event_name = event.get("name", "unknown")
        gpx_file = event.get("gpx_file")
        
        if not gpx_file:
            continue
        
        gpx_path = data_path / gpx_file
        
        try:
            # Basic XML structure check - try to parse as XML
            import xml.etree.ElementTree as ET
            tree = ET.parse(gpx_path)
            root = tree.getroot()
            
            # Check if it looks like GPX (namespace check)
            if not (root.tag.endswith('gpx') or 'gpx' in root.tag.lower()):
                raise ValidationError(
                    f"gpx_file '{gpx_file}' for event '{event_name}' does not appear to be a valid GPX file",
                    code=422
                )
        except ET.ParseError as e:
            raise ValidationError(
                f"gpx_file '{gpx_file}' for event '{event_name}' is not valid XML: {str(e)}",
                code=422
            )
        except Exception as e:
            raise ValidationError(
                f"Failed to parse gpx_file '{gpx_file}' for event '{event_name}': {str(e)}",
                code=422
            )


def validate_api_payload(
    payload: Dict[str, Any],
    data_dir: str = "data"
) -> Tuple[List[Dict[str, Any]], str, str, str]:
    """
    Main validation entry point for API v2 payload.
    
    Performs all validation checks in order:
    1. Required fields check
    2. Day code validation
    3. Start time validation
    4. Event name uniqueness
    5. File existence
    6. Segment span validation
    7. Runner uniqueness
    8. GPX file validation
    
    Args:
        payload: API v2 request payload dictionary
        data_dir: Base directory for data files (default: "data")
        
    Returns:
        Tuple of (events list, segments_file, locations_file, flow_file)
        
    Raises:
        ValidationError: If any validation check fails
    """
    # Check required top-level fields
    if "events" not in payload:
        raise ValidationError(
            "Missing required field 'events' in payload",
            code=400
        )
    
    events = payload.get("events", [])
    if not isinstance(events, list) or len(events) == 0:
        raise ValidationError(
            "Payload must contain at least one event in 'events' array",
            code=400
        )
    
    # Get file references
    segments_file = payload.get("segments_file", "segments.csv")
    locations_file = payload.get("locations_file", "locations.csv")
    flow_file = payload.get("flow_file", "flow.csv")
    
    # Validate file extensions
    if not segments_file.endswith('.csv'):
        raise ValidationError(
            f"segments_file must have .csv extension, got '{segments_file}'",
            code=400
        )
    if not locations_file.endswith('.csv'):
        raise ValidationError(
            f"locations_file must have .csv extension, got '{locations_file}'",
            code=400
        )
    if not flow_file.endswith('.csv'):
        raise ValidationError(
            f"flow_file must have .csv extension, got '{flow_file}'",
            code=400
        )
    
    # Run all validation checks (fail-fast order: basic → file existence → file format → event consistency)
    # Basic structure validation
    description = payload.get("description")
    validate_description(description)
    validate_day_codes(events)
    validate_start_times(events)
    validate_event_duration_range(events)
    validate_event_names(events)
    
    # File existence validation
    validate_file_existence(segments_file, locations_file, flow_file, events, data_dir)
    
    # File format validation
    validate_segment_spans(segments_file, events, data_dir)
    validate_runner_uniqueness(events, data_dir)
    validate_gpx_files(events, data_dir)
    
    return events, segments_file, locations_file, flow_file

