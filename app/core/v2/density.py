"""
Runflow v2 Density Pipeline Module

Refactors density pipeline to accept per-day event lists and segment metadata from v2 Event objects.
Reuses existing density/LOS math but feeds it day-scoped data.

Phase 4: Density Pipeline Refactor (Issue #498)
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import logging

from pathlib import Path
from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.core.v2.bins import resolve_segment_spans, filter_segments_by_events
from app.core.density.compute import (
    analyze_density_segments,
    DensityConfig,
    load_density_cfg,
    get_event_intervals,  # v1 function (deprecated)
)
from app.io.loader import load_runners_by_event

logger = logging.getLogger(__name__)


def get_event_interval_v2(
    event: Event,
    segment_data: Dict[str, Any]
) -> Optional[Tuple[float, float]]:
    """
    Get event interval (from_km, to_km) for a given event from segment data.
    
    Replaces hardcoded event name logic in get_event_intervals() with dynamic lookup.
    Supports all event types: full, half, 10k, elite, open (lowercase).
    
    Args:
        event: Event object with normalized name (lowercase)
        segment_data: Segment row as dictionary from segments.csv
        
    Returns:
        Tuple of (from_km, to_km) if event span columns exist, None otherwise
        
    Example:
        >>> event = Event(name="full", day=Day.SUN, start_time=420, ...)
        >>> segment_data = {"seg_id": "A1", "full_from_km": 0.0, "full_to_km": 0.9}
        >>> get_event_interval_v2(event, segment_data)
        (0.0, 0.9)
    """
    event_name = event.name.lower()
    from_key = f"{event_name}_from_km"
    to_key = f"{event_name}_to_km"
    
    # Case-insensitive column matching (handles "10K" vs "10k")
    from_col = None
    to_col = None
    for col in segment_data.keys():
        if col.lower() == from_key.lower():
            from_col = col
        elif col.lower() == to_key.lower():
            to_col = col
    
    if from_col and to_col and from_col in segment_data and to_col in segment_data:
        from_km = segment_data.get(from_col)
        to_km = segment_data.get(to_col)
        
        if from_km is not None and to_km is not None:
            try:
                return (float(from_km), float(to_km))
            except (ValueError, TypeError):
                logger.debug(f"Invalid span values for event '{event_name}' in segment '{segment_data.get('seg_id', 'unknown')}'")
                return None
    
    logger.debug(f"No interval configuration found for event '{event_name}' in segment '{segment_data.get('seg_id', 'unknown')}'")
    return None


def filter_runners_by_day(
    runners_df: pd.DataFrame,
    day: Day,
    events: List[Event]
) -> pd.DataFrame:
    """
    Filter runners DataFrame to only include runners from events on the specified day.
    
    Args:
        runners_df: DataFrame with runner data (must have 'event' column)
        day: Day to filter by
        events: List of Event objects (used to get event names for this day)
        
    Returns:
        Filtered DataFrame with only runners from events on the specified day
        
    Example:
        >>> runners_df = pd.DataFrame({
        ...     "runner_id": ["1", "2", "3"],
        ...     "event": ["full", "half", "elite"],
        ... })
        >>> events = [
        ...     Event(name="full", day=Day.SUN, ...),
        ...     Event(name="half", day=Day.SUN, ...),
        ... ]
        >>> filtered = filter_runners_by_day(runners_df, Day.SUN, events)
        >>> len(filtered) == 2  # Only full and half runners
        True
    """
    # Get event names for this day (normalized to lowercase)
    day_event_names = {event.name.lower() for event in events if event.day == day}
    
    if not day_event_names:
        # No events for this day - return empty DataFrame
        return pd.DataFrame(columns=runners_df.columns)
    
    # Filter runners by event name (case-insensitive)
    # Normalize event column to lowercase for comparison
    runners_df_normalized = runners_df.copy()
    if "event" in runners_df_normalized.columns:
        runners_df_normalized["event_normalized"] = runners_df_normalized["event"].astype(str).str.lower()
        filtered = runners_df_normalized[
            runners_df_normalized["event_normalized"].isin(day_event_names)
        ]
        # Drop temporary column
        filtered = filtered.drop(columns=["event_normalized"])
        return filtered
    else:
        logger.warning("runners_df missing 'event' column, cannot filter by day")
        return pd.DataFrame(columns=runners_df.columns)


def aggregate_same_day_events(
    events: List[Event],
    day: Day
) -> List[Event]:
    """
    Get list of events that share the same day.
    
    This is used to aggregate runners from all same-day events in shared segments.
    
    Args:
        events: List of all events
        day: Day to filter by
        
    Returns:
        List of events on the specified day
        
    Example:
        >>> events = [
        ...     Event(name="full", day=Day.SUN, ...),
        ...     Event(name="half", day=Day.SUN, ...),
        ...     Event(name="elite", day=Day.SAT, ...),
        ... ]
        >>> same_day = aggregate_same_day_events(events, Day.SUN)
        >>> len(same_day) == 2  # full and half
        True
    """
    return [event for event in events if event.day == day]


def prepare_density_inputs_v2(
    events: List[Event],
    timelines: List[DayTimeline],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame
) -> Dict[Day, Dict[str, Any]]:
    """
    Prepare density inputs per day for v2 analysis.
    
    Filters segments and runners by day, and prepares data structures
    for day-scoped density calculation.
    
    Args:
        events: List of all Event objects
        timelines: List of DayTimeline objects from Phase 3
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame (all events combined)
        
    Returns:
        Dictionary mapping Day to prepared inputs:
        {
            Day.SUN: {
                "events": [Event, ...],
                "timeline": DayTimeline,
                "segments_df": filtered DataFrame,
                "runners_df": filtered DataFrame,
                "start_times": {event_name: datetime, ...}
            },
            ...
        }
    """
    inputs_by_day = {}
    
    for timeline in timelines:
        day = timeline.day
        day_events = timeline.events
        
        # Filter segments to only those used by events on this day
        day_segments_df = filter_segments_by_events(segments_df, day_events)
        
        # Filter runners to only those from events on this day
        day_runners_df = filter_runners_by_day(all_runners_df, day, day_events)
        
        # Map event names in runners DataFrame to v1 format for analyze_density_segments compatibility
        # analyze_density_segments expects event names like "Full", "Half", "10K"
        event_name_mapping = {
            "full": "Full",
            "half": "Half",
            "10k": "10K",
            "elite": "Elite",  # v2 only
            "open": "Open"     # v2 only
        }
        
        if not day_runners_df.empty and "event" in day_runners_df.columns:
            # Create a copy to avoid modifying the original
            day_runners_df = day_runners_df.copy()
            # Map lowercase event names to v1 format
            day_runners_df["event"] = day_runners_df["event"].str.lower().map(
                lambda x: event_name_mapping.get(x, x.capitalize())
            )
        
        # Prepare start_times dict (convert minutes to datetime for v1 compatibility)
        # Use a reference date (e.g., 2025-01-01) for datetime conversion
        start_times = {}
        for event in day_events:
            # Convert minutes after midnight to datetime
            reference_date = datetime(2025, 1, 1)
            start_datetime = reference_date.replace(
                hour=event.start_time // 60,
                minute=event.start_time % 60,
                second=0,
                microsecond=0
            )
            # Map v2 event name to v1 format for analyze_density_segments compatibility
            v1_event_name = event_name_mapping.get(event.name.lower(), event.name.capitalize())
            start_times[v1_event_name] = start_datetime
        
        inputs_by_day[day] = {
            "events": day_events,
            "timeline": timeline,
            "segments_df": day_segments_df,
            "runners_df": day_runners_df,
            "start_times": start_times
        }
    
    return inputs_by_day


def load_all_runners_for_events(
    events: List[Event],
    data_dir: str = "data"
) -> pd.DataFrame:
    """
    Load all runners from event-specific CSV files and combine into a single DataFrame.
    
    Args:
        events: List of Event objects
        data_dir: Base directory for data files (default: "data")
        
    Returns:
        Combined DataFrame with all runners from all events
        Columns: runner_id, event, pace, distance, start_offset (and any other columns from CSV)
    """
    all_runners = []
    
    for event in events:
        try:
            runners_df = load_runners_by_event(event.name, data_dir)
            # Ensure event column matches the event name (normalized to lowercase)
            runners_df["event"] = event.name.lower()
            all_runners.append(runners_df)
        except FileNotFoundError as e:
            logger.warning(f"Skipping runners for event '{event.name}': {e}")
            continue
    
    if not all_runners:
        return pd.DataFrame()
    
    # Combine all runner DataFrames
    combined_df = pd.concat(all_runners, ignore_index=True)
    return combined_df


def analyze_density_segments_v2(
    events: List[Event],
    timelines: List[DayTimeline],
    segments_df: pd.DataFrame,
    all_runners_df: Optional[pd.DataFrame] = None,
    data_dir: str = "data",
    config: Optional[DensityConfig] = None,
    density_csv_path: str = "data/segments.csv"
) -> Dict[Day, Dict[str, Any]]:
    """
    Analyze density for all segments using v2 Event objects and day-scoped data.
    
    This is the main v2 entry point that:
    1. Prepares day-scoped inputs (segments, runners, start times)
    2. Calls existing density math functions with filtered data
    3. Returns results partitioned by day
    
    Args:
        events: List of Event objects from API payload
        timelines: List of DayTimeline objects from Phase 3
        segments_df: Full segments DataFrame
        all_runners_df: Optional pre-loaded runners DataFrame (if None, will load from files)
        data_dir: Base directory for data files (default: "data")
        config: Density analysis configuration (optional)
        density_csv_path: Path to segments.csv file
        
    Returns:
        Dictionary mapping Day to density analysis results:
        {
            Day.SUN: {
                "ok": True,
                "segments": {...},
                "summary": {...},
                ...
            },
            Day.SAT: {...},
            ...
        }
    """
    config = config or DensityConfig()
    
    # Load all runners if not provided
    if all_runners_df is None:
        all_runners_df = load_all_runners_for_events(events, data_dir)
    
    # Prepare inputs per day
    inputs_by_day = prepare_density_inputs_v2(events, timelines, segments_df, all_runners_df)
    
    # Load density configuration (for segment metadata)
    density_cfg = load_density_cfg(density_csv_path)
    
    # Analyze density per day
    results_by_day = {}
    
    for day, day_inputs in inputs_by_day.items():
        day_events = day_inputs["events"]
        day_runners_df = day_inputs["runners_df"]
        day_start_times = day_inputs["start_times"]
        
        if day_runners_df.empty:
            logger.warning(f"No runners found for day {day.value}, skipping density analysis")
            results_by_day[day] = {
                "ok": False,
                "error": f"No runners found for day {day.value}"
            }
            continue
        
        # Call existing density analysis function with day-scoped data
        # This reuses all existing density math (areal density, LOS, etc.)
        try:
            day_results = analyze_density_segments(
                pace_data=day_runners_df,
                start_times=day_start_times,
                config=config,
                density_csv_path=density_csv_path
            )
            
            # Add day metadata to results
            day_results["day"] = day.value
            day_results["events"] = [event.name for event in day_events]
            
            results_by_day[day] = day_results
            
        except Exception as e:
            logger.error(f"Error analyzing density for day {day.value}: {e}", exc_info=True)
            results_by_day[day] = {
                "ok": False,
                "error": str(e),
                "day": day.value
            }
    
    return results_by_day

