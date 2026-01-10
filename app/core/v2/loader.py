"""
Runflow v2 Data Loader Module

Provides functions to load and parse API v2 payloads into Event, Segment, and Runner objects.
Handles event name normalization and day grouping for timeline generation.

Phase 1: Models & Validation Layer (Issue #495)
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import pandas as pd

from app.core.v2.models import Day, Event, Segment, Runner
from app.core.v2.validation import validate_api_payload


def load_events_from_payload(
    payload: Dict[str, Any],
    data_dir: str
) -> List[Event]:
    """
    Parse API v2 payload and create Event objects.
    
    Args:
        payload: API v2 request payload dictionary
        data_dir: Base directory for data files
        
    Returns:
        List of Event objects with normalized names and day assignments
        
    Raises:
        ValidationError: If payload validation fails
    """
    # Validate payload first
    events_data, segments_file, _, _ = validate_api_payload(payload, data_dir)
    
    # Load segments to determine which seg_ids each event uses
    segments_df = load_segments_with_spans(segments_file, events_data, data_dir)
    
    # Create Event objects
    events = []
    for event_data in events_data:
        event_name = event_data["name"].lower()  # Normalize to lowercase
        day_str = event_data["day"].lower()
        
        # Convert day string to Day enum
        try:
            day = Day(day_str)
        except ValueError:
            # Should not happen if validation passed, but handle gracefully
            raise ValueError(f"Invalid day code '{day_str}' for event '{event_name}'")
        
        # Determine which segments this event uses based on segments.csv event flags
        seg_ids = []
        if "seg_id" in segments_df.columns:
            # Check event flag column (full, half, 10k, elite, open)
            # Match column name case-insensitively (segments.csv may have "10K" vs "10k")
            event_flag_col = None
            for col in segments_df.columns:
                if col.lower() == event_name.lower():
                    event_flag_col = col
                    break
            
            if event_flag_col and event_flag_col in segments_df.columns:
                # Filter segments where this event flag is 'y'
                event_segments = segments_df[
                    segments_df[event_flag_col].astype(str).str.lower().isin(['y', 'yes', 'true', '1'])
                ]
                seg_ids = event_segments["seg_id"].tolist()
        
        event = Event(
            name=event_name,
            day=day,
            start_time=event_data["start_time"],
            gpx_file=event_data["gpx_file"],
            runners_file=event_data["runners_file"],
            seg_ids=seg_ids
        )
        
        events.append(event)
    
    return events


def load_runners_for_event(
    event: Event,
    data_dir: str
) -> List[Runner]:
    """
    Load runners from CSV file and create Runner objects for an event.
    
    Args:
        event: Event object with runners_file path
        data_dir: Base directory for data files
        
    Returns:
        List of Runner objects with normalized event names
        
    Raises:
        FileNotFoundError: If runners file doesn't exist
        ValueError: If CSV format is invalid
    """
    runners_path = Path(data_dir) / event.runners_file
    
    if not runners_path.exists():
        raise FileNotFoundError(
            f"runners_file '{event.runners_file}' not found for event '{event.name}'"
        )
    
    try:
        runners_df = pd.read_csv(runners_path)
    except Exception as e:
        raise ValueError(
            f"Failed to read runners_file '{event.runners_file}' for event '{event.name}': {str(e)}"
        )
    
    # Validate required columns
    required_columns = ["runner_id", "event", "pace", "distance", "start_offset"]
    missing_cols = [col for col in required_columns if col not in runners_df.columns]
    if missing_cols:
        raise ValueError(
            f"runners_file '{event.runners_file}' missing required columns: {missing_cols}"
        )
    
    # Create Runner objects
    runners = []
    for _, row in runners_df.iterrows():
        runner = Runner(
            runner_id=str(row["runner_id"]),
            event=str(row["event"]).lower(),  # Normalize to lowercase
            pace=float(row["pace"]),
            distance=float(row["distance"]),
            start_offset=int(row["start_offset"])
        )
        runners.append(runner)
    
    return runners


def load_segments_with_spans(
    segments_file: str,
    events_data: List[Dict[str, Any]],
    data_dir: str
) -> pd.DataFrame:
    """
    Load segments.csv and validate per-event span columns exist.
    
    This function loads the segments DataFrame for use in determining
    which segments each event uses and for span validation.
    
    Args:
        segments_file: Path to segments.csv file
        events_data: List of event dictionaries (for span validation context)
        data_dir: Base directory for data files
        
    Returns:
        DataFrame with segments data
        
    Raises:
        FileNotFoundError: If segments file doesn't exist
        ValueError: If CSV format is invalid
    """
    segments_path = Path(data_dir) / segments_file
    
    if not segments_path.exists():
        raise FileNotFoundError(
            f"segments_file '{segments_file}' not found in {data_dir}/ directory"
        )
    
    try:
        segments_df = pd.read_csv(segments_path)
    except Exception as e:
        raise ValueError(
            f"Failed to read segments_file '{segments_file}': {str(e)}"
        )
    
    # Validate required base columns
    if "seg_id" not in segments_df.columns:
        raise ValueError(
            f"segments_file '{segments_file}' missing required column 'seg_id'"
        )
    
    return segments_df


def group_events_by_day(events: List[Event]) -> Dict[Day, List[Event]]:
    """
    Group events by day for timeline generation.
    
    Args:
        events: List of Event objects
        
    Returns:
        Dictionary mapping Day enum to list of Events on that day
    """
    grouped = {}
    for event in events:
        if event.day not in grouped:
            grouped[event.day] = []
        grouped[event.day].append(event)
    
    return grouped
