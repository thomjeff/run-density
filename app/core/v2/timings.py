"""
Runflow v2 Timings Module

Computes predicted timings (first/last finishers, durations) from runner data.
Uses vectorized pandas operations for efficient computation across thousands of runners.

Issue #638: Correct implementation of predicted_timings using runner finish times
instead of bin window timestamps.

Core Principles:
- Compute finish times directly from runner data (pace, distance, start_offset)
- Use vectorized operations (NO loops over runners)
- Return dict only (no file writes)
- Use Event.start_time as primary source, analysis_config for fallback durations
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging

from app.core.v2.models import Event

logger = logging.getLogger(__name__)


def _format_seconds_to_hhmm(seconds_from_midnight: float) -> str:
    """
    Format seconds from midnight to HH:MM string.
    
    Args:
        seconds_from_midnight: Seconds elapsed since midnight (0-86400)
        
    Returns:
        Time string in HH:MM format (e.g., "07:30")
    """
    try:
        total_seconds = int(float(seconds_from_midnight))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours:02d}:{minutes:02d}"
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to format seconds {seconds_from_midnight} to HH:MM: {e}")
        return "00:00"


def compute_predicted_timings(
    *,
    events: List[Event],
    analysis_config: Dict[str, Any],
    runners_df: pd.DataFrame
) -> Optional[Dict[str, Any]]:
    """
    Compute predicted_timings dict from runner data using vectorized operations.
    
    Issue #638: Correct implementation using runner finish times instead of bin windows.
    
    Args:
        events: List of Event objects for the day
        analysis_config: Analysis configuration dict (for event_duration_minutes fallback)
        runners_df: DataFrame with columns: runner_id, event, pace, distance, start_offset
        
    Returns:
        Dictionary with predicted_timings structure, or None if computation fails
        Structure:
        {
            "day_start": "HH:MM",
            "event_first_finisher": {"event_name": "HH:MM", ...},
            "day_first_finisher": "HH:MM",
            "event_last_finisher": {"event_name": "HH:MM", ...},
            "day_last_finisher": "HH:MM",
            "day_end": "HH:MM",
            "actual_event_duration": {"event_name": "HH:MM", ...},
            "day_duration": "HH:MM"
        }
    """
    try:
        # Validate required columns
        required_columns = ['runner_id', 'event', 'pace', 'distance', 'start_offset']
        missing_columns = [col for col in required_columns if col not in runners_df.columns]
        if missing_columns:
            logger.warning(
                f"Issue #638: Missing required columns in runners_df: {missing_columns}. "
                f"Available columns: {list(runners_df.columns)}"
            )
            # If runners_df is completely empty or missing critical columns, return None
            if runners_df.empty or 'pace' not in runners_df.columns or 'distance' not in runners_df.columns:
                return None
        
        # Normalize event names to lowercase (v2 convention)
        if 'event' in runners_df.columns:
            runners_df = runners_df.copy()
            runners_df['event'] = runners_df['event'].str.lower()
        
        # Build lookup from Event objects (primary source for start times)
        event_start_times = {event.name.lower(): event.start_time for event in events}
        
        # Build lookup from analysis_config for fallback durations
        event_durations = {}
        if analysis_config and "events" in analysis_config:
            for event_name, event_data in analysis_config["events"].items():
                event_name_lower = event_name.lower()
                if "event_duration_minutes" in event_data:
                    event_durations[event_name_lower] = event_data["event_duration_minutes"]
        
        # Initialize result dictionaries
        event_first_finisher = {}
        event_last_finisher = {}
        actual_event_duration = {}
        
        # Process each event
        for event in events:
            event_name = event.name.lower()
            event_start_min = event.start_time  # minutes after midnight
            
            # Filter runners for this event (vectorized)
            event_runners = runners_df[runners_df['event'].str.lower() == event_name].copy()
            
            if event_runners.empty:
                # Fallback: use event_duration_minutes if available
                if event_name in event_durations:
                    duration_minutes = event_durations[event_name]
                    event_last_min = event_start_min + duration_minutes
                    event_last_finisher[event_name] = _format_seconds_to_hhmm(event_last_min * 60)
                    # Leave event_first_finisher empty (no runners to compute from)
                    logger.debug(f"Issue #638: No runners for event {event_name}, using fallback duration")
                else:
                    logger.debug(f"Issue #638: No runners and no duration fallback for event {event_name}")
                continue
            
            # Validate required columns for computation
            if 'pace' not in event_runners.columns or 'distance' not in event_runners.columns:
                logger.warning(f"Issue #638: Missing pace or distance columns for event {event_name}")
                continue
            
            # Vectorized computation of finish times
            # pace_sec_per_km = pace * 60
            event_runners['pace_sec_per_km'] = event_runners['pace'] * 60.0
            
            # start_offset_sec = start_offset (already in seconds, or 0 if missing)
            event_runners['start_offset_sec'] = event_runners.get('start_offset', pd.Series([0] * len(event_runners))).fillna(0).astype(float)
            
            # runner_start_sec = event_start_min * 60 + start_offset_sec
            event_runners['runner_start_sec'] = (event_start_min * 60.0) + event_runners['start_offset_sec']
            
            # finish_time_sec = runner_start_sec + (pace_sec_per_km * distance_km)
            event_runners['finish_time_sec'] = (
                event_runners['runner_start_sec'] + 
                (event_runners['pace_sec_per_km'] * event_runners['distance'])
            )
            
            # Aggregate per event using vectorized operations
            event_first_sec = event_runners['finish_time_sec'].min()
            event_last_sec = event_runners['finish_time_sec'].max()
            
            event_first_finisher[event_name] = _format_seconds_to_hhmm(event_first_sec)
            event_last_finisher[event_name] = _format_seconds_to_hhmm(event_last_sec)
            
            # Calculate actual_event_duration: event_last - event_first
            duration_sec = event_last_sec - event_first_sec
            actual_event_duration[event_name] = _format_seconds_to_hhmm(duration_sec)
            
            logger.debug(
                f"Issue #638: Computed timings for event {event_name}: "
                f"first={event_first_finisher[event_name]}, last={event_last_finisher[event_name]}, "
                f"duration={actual_event_duration[event_name]}"
            )
        
        # Day-level aggregation
        # day_start = min(event start times)
        day_start_min = min(event_start_times.values()) if event_start_times else None
        if day_start_min is None:
            logger.warning("Issue #638: No event start times available, cannot compute day_start")
            return None
        
        day_start_str = _format_seconds_to_hhmm(day_start_min * 60)
        
        # day_first_finisher = min(all event_first values that exist)
        # day_last_finisher = max(all event_last values that exist)
        if event_first_finisher:
            # Convert HH:MM strings back to seconds for comparison
            def hhmm_to_seconds(hhmm_str: str) -> float:
                try:
                    parts = hhmm_str.split(':')
                    return int(parts[0]) * 3600 + int(parts[1]) * 60
                except (ValueError, IndexError):
                    return 0.0
            
            day_first_sec = min(hhmm_to_seconds(v) for v in event_first_finisher.values())
            day_last_sec = max(hhmm_to_seconds(v) for v in event_last_finisher.values())
            
            day_first_finisher_str = _format_seconds_to_hhmm(day_first_sec)
            day_last_finisher_str = _format_seconds_to_hhmm(day_last_sec)
        else:
            # Fallback: use event durations if no runners
            if event_durations and event_start_times:
                # Compute day_last from start_time + duration for each event
                day_last_min = max(
                    event_start_times.get(event_name, 0) + event_durations.get(event_name, 0)
                    for event_name in event_start_times.keys()
                    if event_name in event_durations
                )
                day_last_finisher_str = _format_seconds_to_hhmm(day_last_min * 60)
                # Set day_first to day_start as fallback
                day_first_finisher_str = day_start_str
            else:
                logger.warning("Issue #638: No event finishers and no duration fallback available")
                return None
        
        day_end_str = day_last_finisher_str  # day_end = day_last_finisher
        
        # day_duration = day_end - day_start
        def hhmm_to_seconds(hhmm_str: str) -> float:
            try:
                parts = hhmm_str.split(':')
                return int(parts[0]) * 3600 + int(parts[1]) * 60
            except (ValueError, IndexError):
                return 0.0
        
        day_duration_sec = hhmm_to_seconds(day_end_str) - hhmm_to_seconds(day_start_str)
        day_duration_str = _format_seconds_to_hhmm(day_duration_sec)
        
        # Build predicted_timings structure
        predicted_timings = {
            "day_start": day_start_str,
            "event_first_finisher": event_first_finisher,
            "day_first_finisher": day_first_finisher_str,
            "event_last_finisher": event_last_finisher,
            "day_last_finisher": day_last_finisher_str,
            "day_end": day_end_str,
            "actual_event_duration": actual_event_duration,
            "day_duration": day_duration_str
        }
        
        logger.info(
            f"Issue #638: Computed predicted_timings: "
            f"day_start={day_start_str}, day_first={day_first_finisher_str}, "
            f"day_last={day_last_finisher_str}, day_duration={day_duration_str}"
        )
        
        return predicted_timings
        
    except Exception as e:
        logger.error(f"Issue #638: Failed to compute predicted_timings: {e}", exc_info=True)
        return None
