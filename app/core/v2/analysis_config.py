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
            }
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
    
    # Build analysis.json structure
    analysis_json = {
        "description": description,
        "data_dir": data_dir,
        "segments_file": segments_file,
        "flow_file": flow_file,
        "locations_file": locations_file,
        "runners": total_runners,
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

