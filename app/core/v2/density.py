"""
Runflow v2 Density Pipeline Module

Refactors density pipeline to support multi-day, multi-event analysis.
Filters segments and runners by day, then calls existing v1 density math.
Upholds existing density calculations while ensuring no cross-day contamination.

Phase 4: Density Pipeline Refactor (Issue #498)

Core Principles:
- Use filter_segments_by_events() to find all segments used by requested events
- Use event-specific distance ranges from segments.csv ({event}_from_km, {event}_to_km)
- Load runners from per-event CSV files, but map them using v1 logic
- Do not alter core bin logic, span resolution, or density calculations
- Reuse v1 analyze_density_segments() function without modification
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import logging

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.core.v2.bins import filter_segments_by_events
from app.core.density.compute import analyze_density_segments, DensityConfig
from app.io.loader import load_runners_by_event, load_runners

logger = logging.getLogger(__name__)


def get_event_distance_range_v2(
    segment: pd.Series,
    event: Event
) -> Tuple[float, float]:
    """
    Extract distance range for a specific event from segment data (v2).
    
    Uses segments.csv columns like {event}_from_km and {event}_to_km.
    Supports all event types: full, half, 10k, elite, open (lowercase).
    
    Args:
        segment: Segment data row as pandas Series
        event: Event object with normalized name (lowercase)
        
    Returns:
        Tuple of (from_km, to_km) for the event
        
    Example:
        >>> segment = pd.Series({
        ...     "seg_id": "A1",
        ...     "full_from_km": 0.0,
        ...     "full_to_km": 0.9,
        ... })
        >>> event = Event(name="full", day=Day.SUN, start_time=420, ...)
        >>> get_event_distance_range_v2(segment, event)
        (0.0, 0.9)
    """
    event_name = event.name.lower()
    from_key = f"{event_name}_from_km"
    to_key = f"{event_name}_to_km"
    
    # Case-insensitive column matching (handles "10K" vs "10k")
    from_col = None
    to_col = None
    for col in segment.index:
        if col.lower() == from_key.lower():
            from_col = col
        elif col.lower() == to_key.lower():
            to_col = col
    
    if from_col and to_col and from_col in segment.index and to_col in segment.index:
        from_km = segment.get(from_col)
        to_km = segment.get(to_col)
        
        if from_km is not None and to_km is not None:
            try:
                return (float(from_km), float(to_km))
            except (ValueError, TypeError):
                logger.debug(f"Invalid span values for event '{event_name}' in segment '{segment.get('seg_id', 'unknown')}'")
                return (0.0, 0.0)
    
    logger.debug(f"No distance range found for event '{event_name}' in segment '{segment.get('seg_id', 'unknown')}'")
    return (0.0, 0.0)


def combine_runners_for_events(
    events: List[str],
    day: str,
    source_dir: str = "data"
) -> pd.DataFrame:
    """
    Combine runners from per-event CSV files for the specified events and day.
    
    This function dynamically loads runner files matching the requested events,
    filters by day if needed, and combines them into a single DataFrame.
    All event names remain lowercase for consistency.
    
    Args:
        events: List of lowercase event names (e.g., ["full", "half", "10k"])
        day: Day identifier (e.g., "sat", "sun")
        source_dir: Directory containing runner CSV files (default: "data")
        
    Returns:
        Combined DataFrame with all runners for the specified events and day.
        Columns match what build_runner_window_mapping() expects.
        Event names remain lowercase.
        
    Example:
        >>> events = ["full", "half", "10k"]
        >>> day = "sun"
        >>> runners = combine_runners_for_events(events, day)
        >>> len(runners) > 0
        True
        >>> set(runners['event'].str.lower().unique()).issubset(set(events))
        True
    """
    if not events:
        logger.warning("No events provided, returning empty DataFrame")
        return pd.DataFrame()
    
    logger.info(f"Loading runners for events {events} from day '{day}'")
    
    combined_runners = []
    source_path = Path(source_dir)
    
    for event_name in events:
        # Construct filename: <event>_runners.csv
        runner_file = source_path / f"{event_name}_runners.csv"
        
        if not runner_file.exists():
            logger.warning(f"Missing file: {runner_file} — skipping event '{event_name}'")
            continue
        
        try:
            # Load runners for this event
            event_runners = pd.read_csv(runner_file)
            
            # Filter by day if day column exists
            if 'day' in event_runners.columns:
                event_runners = event_runners[event_runners['day'].str.lower() == day.lower()].copy()
                logger.debug(f"Filtered {event_name} runners to day {day}: {len(event_runners)} rows")
            
            # Ensure event column is lowercase
            if 'event' in event_runners.columns:
                event_runners['event'] = event_name.lower()
            else:
                event_runners['event'] = event_name.lower()
            
            # Add day column if not present
            if 'day' not in event_runners.columns:
                event_runners['day'] = day.lower()
            
            combined_runners.append(event_runners)
            logger.info(f"✅ Loaded {len(event_runners)} runners from {runner_file.name}")
            
        except Exception as e:
            logger.error(f"Failed to load runners from {runner_file}: {e}")
            continue
    
    if not combined_runners:
        logger.warning(f"No runner files found for events {events} on day {day}")
        return pd.DataFrame()
    
    # Combine all runners
    result = pd.concat(combined_runners, ignore_index=True)
    
    # Drop duplicates if any (based on bib + event + day)
    if 'bib' in result.columns:
        initial_count = len(result)
        result = result.drop_duplicates(subset=['bib', 'event', 'day'], keep='first')
        if len(result) < initial_count:
            logger.debug(f"Dropped {initial_count - len(result)} duplicate runners")
    
    logger.info(f"✅ Combined runner dataset: {len(result)} rows")
    
    return result


def load_all_runners_for_events(
    events: List[Event],
    data_dir: str
) -> pd.DataFrame:
    """
    Load all runners from event-specific CSV files and combine into a single DataFrame.
    
    Loads runners from individual event-specific CSV files ({event}_runners.csv).
    Issue #548: Removed fallback to v1 runners.csv format - file no longer exists.
    
    Args:
        events: List of Event objects
        data_dir: Base directory for data files
        
    Returns:
        Combined DataFrame with all runners from all events
        Columns: runner_id, event, pace, distance, start_offset
        Event names are mapped to v1 format (Full, Half, 10K)
    """
    all_runners = []
    event_names = {event.name.lower() for event in events}
    
    # Issue #548 Bug 1: Use lowercase events consistently (no v1 uppercase compatibility)
    # Try event-specific files first (v2 format: {event}_runners.csv)
    for event in events:
        try:
            runners_df = load_runners_by_event(event.name, data_dir)
            # Ensure event column is lowercase for consistency
            runners_df = runners_df.copy()
            runners_df["event"] = event.name.lower()
            all_runners.append(runners_df)
            logger.debug(f"Loaded {len(runners_df)} runners from {event.runners_file} for event '{event.name}'")
        except FileNotFoundError:
            # Event-specific file doesn't exist, will try v1 format below
            logger.debug(f"Event-specific file '{event.runners_file}' not found for event '{event.name}', will try v1 format")
            continue
    
    # Issue #548: Removed fallback to v1 runners.csv format - file no longer exists
    # All events must have individual {event}_runners.csv files
    if not all_runners:
        logger.warning(f"No runner files found for events: {[e.name for e in events]}")
        logger.warning("Expected individual event files: {event}_runners.csv (e.g., full_runners.csv, 10k_runners.csv)")
        return pd.DataFrame(columns=["runner_id", "event", "pace", "distance", "start_offset"])
    
    # Combine all runners
    combined_df = pd.concat(all_runners, ignore_index=True)
    
    logger.info(f"Loaded {len(combined_df)} total runners from {len(events)} events")
    return combined_df


def filter_runners_by_day(
    runners_df: pd.DataFrame,
    day: Day,
    events: List[Event]
) -> pd.DataFrame:
    """
    Filter runners DataFrame to only include runners from events on the specified day.
    
    Args:
        runners_df: Full runners DataFrame (all events)
        day: Day enum to filter by
        events: List of Event objects (to determine which events are on this day)
        
    Returns:
        Filtered DataFrame with only runners from events on the specified day
    """
    if runners_df.empty:
        return runners_df
    
    # Get event names for this day (in v1 format)
    day_event_names = {event.name.lower() for event in events if event.day == day}
    
    # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
    # day_event_names is already lowercase, and runners_df["event"] should be lowercase too
    if "event" in runners_df.columns:
        filtered = runners_df[runners_df["event"].isin(day_event_names)].copy()
        logger.debug(f"Filtered runners: {len(runners_df)} -> {len(filtered)} for day {day.value}")
        return filtered
    
    return pd.DataFrame(columns=runners_df.columns)


def analyze_density_segments_v2(
    events: List[Event],
    timelines: List[DayTimeline],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame,
    density_csv_path: str,
    config: Optional[DensityConfig] = None
) -> Dict[Day, Dict[str, Any]]:
    """
    Analyze density for all segments using v2 Event objects and day-scoped data.
    
    This is the main v2 entry point that:
    1. Groups events by day
    2. Filters segments to those used by requested events (using filter_segments_by_events)
    3. Filters runners by day
    4. Maps event names to v1 format
    5. Calls existing v1 analyze_density_segments() function
    6. Returns results partitioned by day
    
    Args:
        events: List of Event objects from API payload
        timelines: List of DayTimeline objects from Phase 3
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame (all events)
        density_csv_path: Path to segments.csv file (for v1 compatibility)
        config: Optional DensityConfig (uses default if not provided)
        
    Returns:
        Dictionary mapping Day to density analysis results:
        {
            Day.SUN: {
                "summary": {...},
                "segments": {...},
                ...
            },
            Day.SAT: {...},
            ...
        }
    """
    results_by_day: Dict[Day, Dict[str, Any]] = {}
    
    # Group events by day
    from app.core.v2.loader import group_events_by_day
    events_by_day = group_events_by_day(events)
    
    # Create timeline lookup
    timeline_by_day = {timeline.day: timeline for timeline in timelines}
    
    # Filter segments to those used by requested events
    # This uses filter_segments_by_events() which finds ALL segments where ANY requested event is present
    filtered_segments_df = filter_segments_by_events(segments_df, events)
    
    if filtered_segments_df.empty:
        logger.warning("No segments found for requested events")
        return results_by_day
    
    logger.info(f"Filtered segments: {len(segments_df)} -> {len(filtered_segments_df)} for {len(events)} events")
    
    # Analyze density per day
    for day, day_events in events_by_day.items():
        logger.info(f"Analyzing density for day {day.value} with {len(day_events)} events: {[e.name for e in day_events]}")
        
        # Get timeline for this day
        timeline = timeline_by_day.get(day)
        if not timeline:
            logger.warning(f"No timeline found for day {day.value}, skipping")
            continue
        
        # Filter runners to only those from events on this day
        day_runners_df = filter_runners_by_day(all_runners_df, day, day_events)
        
        if day_runners_df.empty:
            logger.warning(f"No runners found for day {day.value}, skipping density analysis")
            results_by_day[day] = {
                "summary": {
                    "total_segments": len(filtered_segments_df),
                    "processed_segments": 0,
                    "skipped_segments": len(filtered_segments_df),
                    "error": "No runners found for this day"
                },
                "segments": {}
            }
            continue
        
        # Prepare start_times dict (convert minutes to datetime)
        # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
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
            # Use lowercase event names consistently
            start_times[event.name.lower()] = start_datetime
        
        logger.info(f"Day {day.value}: Analyzing {len(day_runners_df)} runners with start_times: {[(k, v.strftime('%H:%M')) for k, v in start_times.items()]}")
        
        # Call v1 analyze_density_segments() function
        # This function expects:
        # - pace_data: DataFrame with columns: runner_id, event, pace, distance, start_offset
        # - start_times: Dict[str, datetime] mapping event names to start times
        # - density_csv_path: Path to segments.csv
        try:
            density_results = analyze_density_segments(
                pace_data=day_runners_df,
                start_times=start_times,
                config=config,
                density_csv_path=density_csv_path
            )
            
            # Add day and events metadata to results
            density_results["day"] = day.value
            density_results["events"] = [e.name for e in day_events]
            
            results_by_day[day] = density_results
            
            logger.info(
                f"Day {day.value}: Density analysis complete. "
                f"Processed {density_results.get('summary', {}).get('processed_segments', 0)} segments, "
                f"Skipped {density_results.get('summary', {}).get('skipped_segments', 0)} segments"
            )
            
        except Exception as e:
            logger.error(f"Day {day.value}: Density analysis failed: {str(e)}", exc_info=True)
            results_by_day[day] = {
                "summary": {
                    "total_segments": len(filtered_segments_df),
                    "processed_segments": 0,
                    "skipped_segments": len(filtered_segments_df),
                    "error": str(e)
                },
                "segments": {},
                "day": day.value,
                "events": [e.name for e in day_events]
            }
    
    return results_by_day
