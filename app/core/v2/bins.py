"""
Runflow v2 Bin Generation Module

Provides event-aware, day-scoped bin generation for v2 analysis.
Replaces hardcoded event lists with dynamic event filtering.

Phase 3: Timeline & Bin Rewrite (Issue #497)
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.utils.constants import DEFAULT_BIN_SIZE_KM, DEFAULT_TIME_BIN_SECONDS, SECONDS_PER_MINUTE


def calculate_runner_arrival_time(
    event_start_time_minutes: int,
    runner_start_offset_seconds: int,
    pace_minutes_per_km: float,
    segment_distance_km: float
) -> int:
    """
    Calculate runner arrival time at a segment distance.
    
    Formula matches existing codebase pattern:
    absolute_time = event.start_time (seconds) + runner.start_offset + (pace * segment_distance)
    
    This matches the pattern in location_report.py line 414 and overlap.py line 52.
    The day_start (t0) is used for day-scoped timeline normalization, not for arrival calculation.
    
    Args:
        event_start_time_minutes: Event start time in minutes after midnight
        runner_start_offset_seconds: Runner start offset in seconds (already in seconds)
        pace_minutes_per_km: Runner pace in minutes per kilometer
        segment_distance_km: Distance to segment in kilometers
        
    Returns:
        Absolute arrival time in seconds from midnight
        
    Example:
        >>> # Event starts at 7:20 AM (440 min = 26400 sec)
        >>> # Runner offset: 10 seconds
        >>> # Pace: 4 min/km, Distance: 5 km
        >>> # Travel time: 4 * 5 * 60 = 1200 seconds
        >>> calculate_runner_arrival_time(
        ...     event_start_time_minutes=440,
        ...     runner_start_offset_seconds=10,
        ...     pace_minutes_per_km=4.0,
        ...     segment_distance_km=5.0
        ... )
        27610  # 26400 + 10 + 1200 = 27610 seconds from midnight (7:40:10 AM)
    """
    # Convert event start time from minutes to seconds
    event_start_seconds = event_start_time_minutes * SECONDS_PER_MINUTE
    
    # Calculate travel time: pace (min/km) * distance (km) * 60 (sec/min)
    travel_time_seconds = pace_minutes_per_km * segment_distance_km * SECONDS_PER_MINUTE
    
    # Calculate absolute arrival time
    # Pattern matches location_report.py: event_start_sec + start_offset + pace_sec_per_km * seg_distance_km
    absolute_time = event_start_seconds + runner_start_offset_seconds + travel_time_seconds
    
    return int(absolute_time)


def enforce_cross_day_guard(events: List[Event]) -> None:
    """
    Enforce cross-day guard: ensure events share the same day.
    
    Raises error if events from different days are detected.
    This prevents cross-day contamination in bin generation.
    
    Args:
        events: List of events to validate
        
    Raises:
        ValueError: If events are from different days
        
    Example:
        >>> elite = Event(name="elite", day=Day.SAT, start_time=480, ...)
        >>> full = Event(name="full", day=Day.SUN, start_time=420, ...)
        >>> enforce_cross_day_guard([elite, full])  # Should raise ValueError
        Traceback (most recent call last):
        ...
        ValueError: Events must be on the same day
    """
    if not events:
        return
    
    first_day = events[0].day
    for event in events[1:]:
        if event.day != first_day:
            raise ValueError(
                f"Cross-day guard violation: Events must be on the same day. "
                f"Found {first_day.value} and {event.day.value}"
            )


def filter_segments_by_events(
    segments_df: pd.DataFrame,
    events: List[Event]
) -> pd.DataFrame:
    """
    Filter segments DataFrame to only include segments used by requested events.
    
    Uses segments.csv event flags (full, half, 10k, elite, open columns)
    to determine which segments each event uses.
    
    Args:
        segments_df: Full segments DataFrame from segments.csv
        events: List of Event objects from API payload
        
    Returns:
        Filtered DataFrame with only segments used by requested events
        
    Example:
        >>> segments_df = pd.DataFrame({
        ...     "seg_id": ["A1", "A2", "B1"],
        ...     "full": ["y", "y", "n"],
        ...     "half": ["y", "n", "n"],
        ... })
        >>> events = [Event(name="full", day=Day.SUN, ...)]
        >>> filtered = filter_segments_by_events(segments_df, events)
        >>> len(filtered) == 2  # A1 and A2 (where full='y')
        True
    """
    if segments_df.empty:
        return segments_df
    
    # Collect all segment IDs used by any requested event
    used_seg_ids = set()
    
    for event in events:
        event_name = event.name.lower()
        
        # Find event flag column (case-insensitive)
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
            used_seg_ids.update(event_segments["seg_id"].tolist())
    
    # Return filtered DataFrame
    if used_seg_ids:
        return segments_df[segments_df["seg_id"].isin(used_seg_ids)]
    else:
        # No segments found for any event - return empty DataFrame
        return pd.DataFrame(columns=segments_df.columns)


def resolve_segment_spans(
    segment_data: Dict[str, Any],
    events: List[Event]
) -> Tuple[float, float]:
    """
    Resolve segment boundaries from per-event spans.
    
    For each segment, extracts spans for each requested event and calculates
    min/max boundaries across all event spans.
    
    Args:
        segment_data: Segment row as dictionary (from segments DataFrame)
        events: List of Event objects (requested events)
        
    Returns:
        Tuple of (min_km, max_km) representing segment boundaries
        
    Example:
        >>> segment_data = {
        ...     "seg_id": "F1",
        ...     "full_from_km": 16.35,
        ...     "full_to_km": 18.65,
        ...     "half_from_km": 2.7,
        ...     "half_to_km": 5.0,
        ... }
        >>> events = [
        ...     Event(name="full", day=Day.SUN, ...),
        ...     Event(name="half", day=Day.SUN, ...),
        ... ]
        >>> min_km, max_km = resolve_segment_spans(segment_data, events)
        >>> min_km == 2.7  # Minimum across all event spans
        True
        >>> max_km == 18.65  # Maximum across all event spans
        True
    """
    min_km = float('inf')
    max_km = 0.0
    
    for event in events:
        event_name = event.name.lower()
        from_key = f"{event_name}_from_km"
        to_key = f"{event_name}_to_km"
        
        # Find columns case-insensitively
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
                    from_km = float(from_km)
                    to_km = float(to_km)
                    min_km = min(min_km, from_km)
                    max_km = max(max_km, to_km)
                except (ValueError, TypeError):
                    # Skip invalid values
                    continue
    
    if min_km == float('inf'):
        min_km = 0.0
    
    return min_km, max_km


def create_bins_for_segment_v2(
    segment_data: Dict[str, Any],
    events: List[Event],
    bin_size_km: float = DEFAULT_BIN_SIZE_KM
) -> List[Dict[str, Any]]:
    """
    Create bins for a segment using event-aware span resolution.
    
    Replaces hardcoded event list with dynamic event filtering.
    Uses per-event spans from segments.csv to determine bin boundaries.
    
    Args:
        segment_data: Segment row as dictionary
        events: List of Event objects (requested events)
        bin_size_km: Bin size in kilometers (default: 0.1km)
        
    Returns:
        List of bin dictionaries with start_km, end_km, bin_index
        
    Example:
        >>> segment_data = {
        ...     "seg_id": "A1",
        ...     "full_from_km": 0.0,
        ...     "full_to_km": 0.9,
        ...     "half_from_km": 0.0,
        ...     "half_to_km": 0.9,
        ... }
        >>> events = [Event(name="full", day=Day.SUN, ...)]
        >>> bins = create_bins_for_segment_v2(segment_data, events)
        >>> len(bins) == 9  # 0.9 km / 0.1 km = 9 bins
        True
    """
    # Enforce cross-day guard
    enforce_cross_day_guard(events)
    
    # Resolve segment spans from per-event columns
    min_km, max_km = resolve_segment_spans(segment_data, events)
    
    segment_length = max_km - min_km
    
    if segment_length <= 0:
        return []
    
    # Create bins
    bins = []
    num_bins = int(segment_length / bin_size_km) + 1
    
    for i in range(num_bins):
        start_km = min_km + (i * bin_size_km)
        end_km = min(min_km + ((i + 1) * bin_size_km), max_km)
        
        if start_km >= max_km:
            break
        
        bins.append({
            "bin_index": i,
            "start_km": start_km,
            "end_km": end_km,
            "segment_id": segment_data.get("seg_id", "unknown")
        })
    
    return bins


def generate_bins_per_day(
    segments_df: pd.DataFrame,
    events_by_day: Dict[Day, List[Event]],
    bin_size_km: float = DEFAULT_BIN_SIZE_KM
) -> Dict[Day, Dict[str, List[Dict[str, Any]]]]:
    """
    Generate bins partitioned by day.
    
    Creates bins for each day independently, ensuring no cross-day contamination.
    Filters segments to only those used by events on each day.
    
    Args:
        segments_df: Full segments DataFrame
        events_by_day: Dictionary mapping Day to list of Events
        bin_size_km: Bin size in kilometers
        
    Returns:
        Dictionary mapping Day to segment bins: {Day: {seg_id: [bins]}}
        
    Example:
        >>> segments_df = pd.DataFrame({
        ...     "seg_id": ["A1", "A2"],
        ...     "full": ["y", "y"],
        ...     "elite": ["n", "y"],
        ... })
        >>> events_by_day = {
        ...     Day.SUN: [Event(name="full", day=Day.SUN, ...)],
        ...     Day.SAT: [Event(name="elite", day=Day.SAT, ...)],
        ... }
        >>> bins_by_day = generate_bins_per_day(segments_df, events_by_day)
        >>> Day.SUN in bins_by_day
        True
        >>> Day.SAT in bins_by_day
        True
    """
    bins_by_day = {}
    
    for day, day_events in events_by_day.items():
        # Filter segments to only those used by events on this day
        day_segments_df = filter_segments_by_events(segments_df, day_events)
        
        # Create bins for each segment
        day_bins = {}
        for _, segment_row in day_segments_df.iterrows():
            segment_data = segment_row.to_dict()
            seg_id = segment_data.get("seg_id")
            
            if seg_id:
                bins = create_bins_for_segment_v2(segment_data, day_events, bin_size_km)
                day_bins[seg_id] = bins
        
        bins_by_day[day] = day_bins
    
    return bins_by_day

