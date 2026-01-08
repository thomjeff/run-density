"""
Runflow v2 Analysis Configuration Module

Provides functions for generating and loading analysis.json, the single source of truth
for all analysis parameters.

Issue #553: Make Analysis Inputs Configurable via API Request/Response
Phase 2: analysis.json Creation (Single Source of Truth)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def get_data_directory() -> str:
    """
    Get the data directory path from environment variable or constant.
    
    Issue #553: Data directory is NOT a request parameter. It remains as a 
    constant/environment variable (default: "data").
    
    Returns:
        str: Data directory path (default: "data")
        
    Environment Variables:
        DATA_ROOT: Root directory for data files (e.g., "./data" or "gs://bucket/path")
    """
    # Check environment variable first
    data_dir = os.getenv("DATA_ROOT", "data")
    return data_dir


def count_runners_in_file(runners_file_path: Path) -> int:
    """
    Count the number of runners in a runners CSV file.
    
    Issue #553: Calculate runner counts during analysis.json generation.
    
    Args:
        runners_file_path: Path to runners CSV file
        
    Returns:
        int: Number of runners (rows in CSV, excluding header)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is not a valid CSV
    """
    if not runners_file_path.exists():
        raise FileNotFoundError(f"Runners file not found: {runners_file_path}")
    
    try:
        # Read CSV and count rows (excluding header)
        df = pd.read_csv(runners_file_path)
        return len(df)
    except Exception as e:
        raise ValueError(f"Failed to read runners file {runners_file_path}: {str(e)}")


def generate_analysis_json(
    request_payload: Dict[str, Any],
    run_id: str,
    run_path: Path,
    data_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate analysis.json from validated request payload.
    
    Issue #553: Creates single source of truth for all analysis parameters.
    Issue #566: Includes event_summary with days, events count, and events_by_day.
    
    Args:
        request_payload: Validated request payload dictionary
        run_id: Run identifier (UUID)
        run_path: Path to run directory (where analysis.json will be written)
        data_dir: Optional data directory (defaults to get_data_directory())
        
    Returns:
        dict: Complete analysis.json structure
        
    Structure:
        {
            "description": str,
            "data_dir": str,
            "segments_file": str,
            "flow_file": str,
            "locations_file": str,
            "runners": int,  # Total count across all events
            "event_summary": {
                "days": int,  # Count of unique days
                "events": int,  # Total count of events
                "events_by_day": {
                    "day": {
                        "count": int,
                        "events": [str]  # List of event names for this day
                    }
                }
            },
            "events": [
                {
                    "name": str,
                    "day": str,
                    "start_time": int,
                    "event_duration_minutes": int,
                    "runners_file": str,
                    "gpx_file": str,
                    "runners": int  # Count from this event's runners file
                }
            ],
            "event_days": [str],  # Derived
            "event_names": [str],  # Derived
            "start_times": {str: int},  # Derived
            "data_files": {
                "segments": str,
                "flow": str,
                "locations": str,
                "runners": {str: str},
                "gpx": {str: str}
            },
            "event_group": {str: str}  # Optional (Issue #573): Event grouping for RES calculation
        }
    """
    # Get data directory (from constant/environment, not request)
    if data_dir is None:
        data_dir = get_data_directory()
    
    # Extract fields from request payload
    description = request_payload.get("description")
    segments_file = request_payload.get("segments_file")
    flow_file = request_payload.get("flow_file")
    locations_file = request_payload.get("locations_file")
    events = request_payload.get("events", [])
    event_group = request_payload.get("event_group")  # Issue #573: Optional event grouping for RES
    enableAudit = request_payload.get("enableAudit", "n")  # Issue #635: Enable audit flag (default "n")
    
    # Generate default description if not provided
    if not description:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        description = f"Analysis run on {timestamp}"
    
    # Build data_path for file operations
    data_path = Path(data_dir)
    
    # Process events and count runners
    events_list = []
    total_runners = 0
    event_days_set = set()
    event_names_list = []
    start_times_dict = {}
    runners_files_dict = {}
    gpx_files_dict = {}
    
    for event in events:
        event_name = event.get("name")
        event_day = event.get("day")
        start_time = event.get("start_time")
        event_duration_minutes = event.get("event_duration_minutes")
        runners_file = event.get("runners_file")
        gpx_file = event.get("gpx_file")
        
        # Count runners for this event
        runners_file_path = data_path / runners_file
        try:
            event_runners_count = count_runners_in_file(runners_file_path)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Failed to count runners for event '{event_name}': {e}")
            event_runners_count = 0
        
        total_runners += event_runners_count
        
        # Build event entry
        event_entry = {
            "name": event_name,
            "day": event_day,
            "start_time": start_time,
            "event_duration_minutes": event_duration_minutes,
            "runners_file": runners_file,
            "gpx_file": gpx_file,
            "runners": event_runners_count
        }
        events_list.append(event_entry)
        
        # Build derived structures
        event_days_set.add(event_day)
        event_names_list.append(event_name)
        start_times_dict[event_name] = start_time
        
        # Build data_files structure
        runners_files_dict[event_name] = f"{data_dir}/{runners_file}"
        gpx_files_dict[event_name] = f"{data_dir}/{gpx_file}"
    
    # Issue #566: Compute event_summary
    # Group events by day with count and event names
    events_by_day = {}
    for event in events_list:
        day = event.get("day")
        event_name = event.get("name")
        if day not in events_by_day:
            events_by_day[day] = {"count": 0, "events": []}
        events_by_day[day]["count"] += 1
        events_by_day[day]["events"].append(event_name)
    
    event_summary = {
        "days": len(event_days_set),
        "events": len(events_list),
        "events_by_day": events_by_day
    }
    
    # Build analysis.json structure
    analysis_json = {
        "description": description,
        "data_dir": data_dir,
        "segments_file": segments_file,
        "flow_file": flow_file,
        "locations_file": locations_file,
        "runners": total_runners,
        "event_summary": event_summary,
        "events": events_list,
        "event_days": sorted(list(event_days_set)),
        "event_names": event_names_list,
        "start_times": start_times_dict,
        "data_files": {
            "segments": f"{data_dir}/{segments_file}",
            "flow": f"{data_dir}/{flow_file}",
            "locations": f"{data_dir}/{locations_file}",
            "runners": runners_files_dict,
            "gpx": gpx_files_dict
        }
    }
    
    # Issue #573: Add event_group to analysis.json if provided
    if event_group is not None:
        analysis_json["event_group"] = event_group
    
    # Issue #635: Add enableAudit to analysis.json (always include, default "n")
    analysis_json["enableAudit"] = enableAudit
    
    # Write to run directory
    analysis_json_path = run_path / "analysis.json"
    with open(analysis_json_path, 'w', encoding='utf-8') as f:
        json.dump(analysis_json, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Generated analysis.json at {analysis_json_path}")
    
    return analysis_json


def load_analysis_json(run_path: Path) -> Dict[str, Any]:
    """
    Load and return analysis.json from run directory.
    
    Issue #553: Read single source of truth for analysis parameters.
    
    Args:
        run_path: Path to run directory containing analysis.json
        
    Returns:
        dict: Parsed analysis.json content
        
    Raises:
        FileNotFoundError: If analysis.json doesn't exist
        json.JSONDecodeError: If analysis.json is invalid JSON
    """
    analysis_json_path = run_path / "analysis.json"
    
    if not analysis_json_path.exists():
        raise FileNotFoundError(
            f"analysis.json not found at {analysis_json_path}. "
            f"Run directory may not have been initialized properly."
        )
    
    try:
        with open(analysis_json_path, 'r', encoding='utf-8') as f:
            analysis_json = json.load(f)
        
        logger.info(f"Loaded analysis.json from {analysis_json_path}")
        return analysis_json
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"analysis.json is not valid JSON: {e}",
            e.doc,
            e.pos
        )


def get_event_duration_minutes(
    event_name: str,
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> int:
    """
    Get event duration in minutes from analysis.json.
    
    Issue #553 Phase 4.3: Replace EVENT_DURATION_MINUTES constant with dynamic lookup.
    
    Args:
        event_name: Event name (case-insensitive, e.g., "full", "10k", "half")
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        int: Event duration in minutes
        
    Raises:
        ValueError: If event not found in analysis.json and no fallback available
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        
    Note:
        This function enforces fail-fast behavior per Issue #553 requirements.
        No fallback to EVENT_DURATION_MINUTES constant.
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_event_duration_minutes"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Normalize event name to lowercase for lookup
    event_name_lower = event_name.lower()
    
    # Search through events list for matching event
    events = analysis_config.get("events", [])
    for event in events:
        event_name_in_config = event.get("name", "").lower()
        if event_name_in_config == event_name_lower:
            duration = event.get("event_duration_minutes")
            if duration is None:
                raise ValueError(
                    f"Event '{event_name}' found in analysis.json but missing 'event_duration_minutes' field"
                )
            if not isinstance(duration, int) or duration < 1:
                raise ValueError(
                    f"Event '{event_name}' has invalid event_duration_minutes: {duration} (must be >= 1)"
                )
            return duration
    
    # Event not found - fail fast per Issue #553 requirements
    available_events = [e.get("name", "unknown") for e in events]
    raise ValueError(
        f"Event '{event_name}' not found in analysis.json. "
        f"Available events: {available_events}"
    )


def get_event_names(analysis_config: Optional[Dict[str, Any]] = None, run_path: Optional[Path] = None) -> List[str]:
    """
    Get list of event names from analysis.json.
    
    Issue #553 Phase 4.2: Replace hardcoded event name lists with dynamic lookup.
    
    Args:
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        List[str]: Sorted list of event names
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_event_names"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Return event_names from analysis.json (already sorted)
    event_names = analysis_config.get("event_names", [])
    if not event_names:
        # Fallback: extract from events list
        events = analysis_config.get("events", [])
        event_names = sorted([e.get("name", "") for e in events if e.get("name")])
    
    return event_names


def get_events_by_day(
    day: str,
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> List[str]:
    """
    Get list of event names for a specific day from analysis.json.
    
    Issue #553 Phase 4.2: Replace SATURDAY_EVENTS/SUNDAY_EVENTS constants with dynamic lookup.
    
    Args:
        day: Day code (e.g., "sat", "sun", "fri", "mon")
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        List[str]: List of event names for the specified day
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_events_by_day"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Normalize day code
    day_lower = day.lower()
    
    # Filter events by day
    events = analysis_config.get("events", [])
    day_events = [
        e.get("name") for e in events
        if e.get("day", "").lower() == day_lower and e.get("name")
    ]
    
    return day_events


def get_start_time(
    event_name: str,
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> int:
    """
    Get event start time in minutes from analysis.json.
    
    Issue #553 Phase 5.2: Replace hardcoded start times with dynamic lookup.
    
    Args:
        event_name: Event name (case-insensitive, e.g., "full", "10k", "half")
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        int: Start time in minutes after midnight
        
    Raises:
        ValueError: If event not found in analysis.json and no fallback available
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        
    Note:
        This function enforces fail-fast behavior per Issue #553 requirements.
        No fallback to hardcoded start times.
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_start_time"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Normalize event name to lowercase for lookup
    event_name_lower = event_name.lower()
    
    # Try start_times dictionary first (faster lookup)
    start_times = analysis_config.get("start_times", {})
    if event_name in start_times:
        start_time = start_times[event_name]
    elif event_name_lower in start_times:
        start_time = start_times[event_name_lower]
    else:
        # Fallback: search through events list
        events = analysis_config.get("events", [])
        for event in events:
            event_name_in_config = event.get("name", "").lower()
            if event_name_in_config == event_name_lower:
                start_time = event.get("start_time")
                if start_time is None:
                    raise ValueError(
                        f"Event '{event_name}' found in analysis.json but missing 'start_time' field"
                    )
                if not isinstance(start_time, int) or not (300 <= start_time <= 1200):
                    raise ValueError(
                        f"Event '{event_name}' has invalid start_time: {start_time} (must be integer 300-1200)"
                    )
                return start_time
        
        # Event not found - fail fast per Issue #553 requirements
        available_events = [e.get("name", "unknown") for e in events]
        raise ValueError(
            f"Event '{event_name}' not found in analysis.json. "
            f"Available events: {available_events}"
        )
    
    # Validate start_time
    if not isinstance(start_time, int) or not (300 <= start_time <= 1200):
        raise ValueError(
            f"Event '{event_name}' has invalid start_time: {start_time} (must be integer 300-1200)"
        )
    
    return start_time


def get_all_start_times(
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> Dict[str, int]:
    """
    Get all event start times from analysis.json.
    
    Issue #553 Phase 5.2: Get all start times as a dictionary.
    
    Args:
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        Dict[str, int]: Dictionary mapping event names to start times in minutes
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_all_start_times"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Return start_times dictionary from analysis.json
    start_times = analysis_config.get("start_times", {})
    if not start_times:
        # Fallback: build from events list
        events = analysis_config.get("events", [])
        start_times = {}
        for event in events:
            event_name = event.get("name")
            start_time = event.get("start_time")
            if event_name and start_time is not None:
                start_times[event_name] = start_time
                start_times[event_name.lower()] = start_time
    
    return start_times


def get_segments_file(
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> str:
    """
    Get segments file path from analysis.json.
    
    Issue #553 Phase 6.2: Replace hardcoded file paths with dynamic lookups.
    
    Args:
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        str: Full path to segments file (e.g., "data/segments.csv" or from data_files.segments)
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        ValueError: If segments_file not found in analysis.json
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_segments_file"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Try data_files.segments first (full path)
    data_files = analysis_config.get("data_files", {})
    if "segments" in data_files:
        return data_files["segments"]
    
    # Fallback to segments_file + data_dir
    segments_file = analysis_config.get("segments_file")
    if segments_file:
        data_dir = analysis_config.get("data_dir", "data")
        return f"{data_dir}/{segments_file}"
    
    raise ValueError(
        "segments_file not found in analysis.json. "
        "This is required per Issue #553."
    )


def get_flow_file(
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> str:
    """
    Get flow file path from analysis.json.
    
    Issue #553 Phase 6.2: Replace hardcoded file paths with dynamic lookups.
    
    Args:
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        str: Full path to flow file (e.g., "data/flow.csv" or from data_files.flow)
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        ValueError: If flow_file not found in analysis.json
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_flow_file"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Try data_files.flow first (full path)
    data_files = analysis_config.get("data_files", {})
    if "flow" in data_files:
        return data_files["flow"]
    
    # Fallback to flow_file + data_dir
    flow_file = analysis_config.get("flow_file")
    if flow_file:
        data_dir = analysis_config.get("data_dir", "data")
        return f"{data_dir}/{flow_file}"
    
    raise ValueError(
        "flow_file not found in analysis.json. "
        "This is required per Issue #553."
    )


def get_locations_file(
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> str:
    """
    Get locations file path from analysis.json.
    
    Issue #553 Phase 6.2: Replace hardcoded file paths with dynamic lookups.
    
    Args:
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        str: Full path to locations file (e.g., "data/locations.csv" or from data_files.locations)
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        ValueError: If locations_file not found in analysis.json
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_locations_file"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Try data_files.locations first (full path)
    data_files = analysis_config.get("data_files", {})
    if "locations" in data_files:
        return data_files["locations"]
    
    # Fallback to locations_file + data_dir
    locations_file = analysis_config.get("locations_file")
    if locations_file:
        data_dir = analysis_config.get("data_dir", "data")
        return f"{data_dir}/{locations_file}"
    
    raise ValueError(
        "locations_file not found in analysis.json. "
        "This is required per Issue #553."
    )


def get_runners_file(
    event_name: str,
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> str:
    """
    Get runners file path for a specific event from analysis.json.
    
    Issue #553 Phase 6.2: Replace hardcoded file paths with dynamic lookups.
    
    Args:
        event_name: Event name (case-insensitive, e.g., "full", "10k", "half")
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        str: Full path to runners file (e.g., "data/full_runners.csv" or from data_files.runners)
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        ValueError: If event not found in analysis.json
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_runners_file"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Normalize event name to lowercase for lookup
    event_name_lower = event_name.lower()
    
    # Try data_files.runners dictionary first
    data_files = analysis_config.get("data_files", {})
    runners_dict = data_files.get("runners", {})
    if event_name in runners_dict:
        return runners_dict[event_name]
    elif event_name_lower in runners_dict:
        return runners_dict[event_name_lower]
    
    # Fallback: search through events list
    events = analysis_config.get("events", [])
    for event in events:
        event_name_in_config = event.get("name", "").lower()
        if event_name_in_config == event_name_lower:
            runners_file = event.get("runners_file")
            if runners_file:
                data_dir = analysis_config.get("data_dir", "data")
                return f"{data_dir}/{runners_file}"
    
    # Event not found - fail fast per Issue #553 requirements
    available_events = [e.get("name", "unknown") for e in events]
    raise ValueError(
        f"Event '{event_name}' not found in analysis.json. "
        f"Available events: {available_events}"
    )


def get_gpx_file(
    event_name: str,
    analysis_config: Optional[Dict[str, Any]] = None,
    run_path: Optional[Path] = None
) -> str:
    """
    Get GPX file path for a specific event from analysis.json.
    
    Issue #553 Phase 6.2: Replace hardcoded file paths with dynamic lookups.
    
    Args:
        event_name: Event name (case-insensitive, e.g., "full", "10k", "half")
        analysis_config: Optional pre-loaded analysis.json dict
        run_path: Optional path to run directory (will load analysis.json if config not provided)
        
    Returns:
        str: Full path to GPX file (e.g., "data/full.gpx" or from data_files.gpx)
        
    Raises:
        FileNotFoundError: If run_path provided but analysis.json doesn't exist
        ValueError: If event not found in analysis.json
    """
    # Load analysis_config if not provided
    if analysis_config is None:
        if run_path is None:
            raise ValueError(
                "Either analysis_config or run_path must be provided to get_gpx_file"
            )
        analysis_config = load_analysis_json(run_path)
    
    # Normalize event name to lowercase for lookup
    event_name_lower = event_name.lower()
    
    # Try data_files.gpx dictionary first
    data_files = analysis_config.get("data_files", {})
    gpx_dict = data_files.get("gpx", {})
    if event_name in gpx_dict:
        return gpx_dict[event_name]
    elif event_name_lower in gpx_dict:
        return gpx_dict[event_name_lower]
    
    # Fallback: search through events list
    events = analysis_config.get("events", [])
    for event in events:
        event_name_in_config = event.get("name", "").lower()
        if event_name_in_config == event_name_lower:
            gpx_file = event.get("gpx_file")
            if gpx_file:
                data_dir = analysis_config.get("data_dir", "data")
                return f"{data_dir}/{gpx_file}"
    
    # Event not found - fail fast per Issue #553 requirements
    available_events = [e.get("name", "unknown") for e in events]
    raise ValueError(
        f"Event '{event_name}' not found in analysis.json. "
        f"Available events: {available_events}"
    )

