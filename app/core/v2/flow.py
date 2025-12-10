"""
Runflow v2 Flow Pipeline Module

Refactors flow pipeline to generate event pairs only for same-day events,
filter segments to those common to both events, and use per-event distance ranges.
Upholds existing overtake semantics while ensuring no cross-day interactions.

Phase 5: Flow Pipeline Refactor (Issue #499)
"""

from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import logging

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.core.flow.flow import (
    analyze_temporal_flow_segments,
    _get_event_distance_range,  # v1 function (deprecated for v2)
)
from app.utils.shared import load_pace_csv, load_segments_csv

logger = logging.getLogger(__name__)


def generate_event_pairs_v2(events: List[Event]) -> List[Tuple[Event, Event]]:
    """
    Generate event pairs only for events sharing the same day.
    
    Phase 5 (Issue #499): Replaces hardcoded Sunday event pairs with dynamic
    same-day pair generation. Prevents cross-day interactions.
    
    Args:
        events: List of Event objects from API payload
        
    Returns:
        List of (Event, Event) tuples for same-day pairs
        
    Examples:
        Saturday pairs: (elite, elite), (open, open), (elite, open)
        Sunday pairs: (full, half), (full, 10k), (half, 10k), (full, full), (half, half), (10k, 10k)
        No cross-day pairs: (elite, full) is rejected
        
    Raises:
        ValueError: If events list is empty
    """
    if not events:
        raise ValueError("Cannot generate event pairs from empty events list")
    
    # Group events by day
    events_by_day: Dict[Day, List[Event]] = {}
    for event in events:
        events_by_day.setdefault(event.day, []).append(event)
    
    # Generate pairs within each day
    pairs: List[Tuple[Event, Event]] = []
    
    for day, day_events in events_by_day.items():
        # Generate all valid pairs within this day
        for i, event_a in enumerate(day_events):
            for j, event_b in enumerate(day_events):
                # Include all pairs (including same-event pairs like full-full)
                # This matches v1 behavior where same-event pairs are analyzed
                pairs.append((event_a, event_b))
    
    logger.info(f"Generated {len(pairs)} event pairs from {len(events)} events across {len(events_by_day)} days")
    return pairs


def enforce_same_day_pairs(event_a: Event, event_b: Event) -> None:
    """
    Enforce that event pairs must be from the same day.
    
    Args:
        event_a: First event in pair
        event_b: Second event in pair
        
    Raises:
        ValueError: If events are from different days
    """
    if event_a.day != event_b.day:
        raise ValueError(
            f"Cross-day event pair detected: '{event_a.name}' (day: {event_a.day.value}) "
            f"and '{event_b.name}' (day: {event_b.day.value}) cannot be paired. "
            f"Flow analysis only supports same-day event pairs."
        )


def get_shared_segments(
    event_a: Event,
    event_b: Event,
    segments_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Find segments common to both events in a pair.
    
    Uses segments.csv event flags (full, half, 10k, elite, open columns)
    to determine which segments are used by both events.
    
    Args:
        event_a: First event in pair
        event_b: Second event in pair
        segments_df: Full segments DataFrame
        
    Returns:
        Filtered DataFrame containing only segments used by both events
        
    Example:
        >>> segments_df = pd.DataFrame({
        ...     "seg_id": ["A1", "A2", "A3"],
        ...     "full": ["y", "y", "n"],
        ...     "half": ["y", "n", "y"],
        ... })
        >>> event_a = Event(name="full", day=Day.SUN, ...)
        >>> event_b = Event(name="half", day=Day.SUN, ...)
        >>> shared = get_shared_segments(event_a, event_b, segments_df)
        >>> len(shared) == 1  # Only A1 is used by both
        True
    """
    enforce_same_day_pairs(event_a, event_b)
    
    # Normalize event names to lowercase for column matching
    event_a_name = event_a.name.lower()
    event_b_name = event_b.name.lower()
    
    # Find segments used by event_a (case-insensitive)
    event_a_mask = pd.Series([False] * len(segments_df), index=segments_df.index)
    for col in segments_df.columns:
        if col.lower() == event_a_name:
            event_a_mask |= segments_df[col].astype(str).str.lower().isin(['y', 'yes', 'true', '1'])
    
    # Find segments used by event_b (case-insensitive)
    event_b_mask = pd.Series([False] * len(segments_df), index=segments_df.index)
    for col in segments_df.columns:
        if col.lower() == event_b_name:
            event_b_mask |= segments_df[col].astype(str).str.lower().isin(['y', 'yes', 'true', '1'])
    
    # Find segments used by both events
    shared_mask = event_a_mask & event_b_mask
    
    shared_segments = segments_df[shared_mask].copy()
    
    logger.debug(
        f"Found {len(shared_segments)} shared segments for pair ({event_a.name}, {event_b.name}) "
        f"out of {len(segments_df)} total segments"
    )
    
    return shared_segments


def _create_converted_segment_v2(
    segment: pd.Series,
    event_a: Event,
    event_b: Event
) -> Dict[str, Any]:
    """
    Create a converted segment with event-specific distance ranges (v2).
    
    Uses get_event_distance_range_v2() instead of hardcoded _get_event_distance_range().
    
    Args:
        segment: Original segment data row
        event_a: First Event object
        event_b: Second Event object
        
    Returns:
        Dictionary with converted segment data in flow format
    """
    from_km_a, to_km_a = get_event_distance_range_v2(segment, event_a)
    from_km_b, to_km_b = get_event_distance_range_v2(segment, event_b)
    
    # Map v2 event names to v1 format for flow analysis compatibility
    event_name_mapping = {
        "full": "Full",
        "half": "Half",
        "10k": "10K",
        "elite": "Elite",
        "open": "Open"
    }
    
    return {
        "seg_id": segment.get('seg_id', ''),
        "segment_label": segment.get("seg_label", ""),
        "eventa": event_name_mapping.get(event_a.name.lower(), event_a.name.capitalize()),
        "eventb": event_name_mapping.get(event_b.name.lower(), event_b.name.capitalize()),
        "from_km_a": from_km_a,
        "to_km_a": to_km_a,
        "from_km_b": from_km_b,
        "to_km_b": to_km_b,
        "direction": segment.get("direction", ""),
        "width_m": segment.get("width_m", 0),
        "overtake_flag": segment.get("overtake_flag", ""),
        "flow_type": segment.get("flow_type", ""),
        "length_km": segment.get("length_km", 0)
    }


def get_event_distance_range_v2(
    segment: pd.Series,
    event: Event
) -> Tuple[float, float]:
    """
    Extract distance range for a specific event from segment data (v2).
    
    Replaces hardcoded event name logic in _get_event_distance_range() with dynamic lookup.
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


def filter_flow_csv_by_events(
    flow_df: pd.DataFrame,
    events: List[Event]
) -> pd.DataFrame:
    """
    Filter flow.csv to only include pairs for requested events.
    
    Matches event_a and event_b columns to requested event names (case-insensitive).
    Only processes flow relationships for same-day pairs.
    
    Args:
        flow_df: Flow DataFrame from flow.csv
        events: List of Event objects from API payload
        
    Returns:
        Filtered DataFrame containing only flow relationships for requested events
        
    Example:
        >>> flow_df = pd.DataFrame({
        ...     "event_a": ["Full", "Half", "Elite"],
        ...     "event_b": ["Half", "10K", "Open"],
        ... })
        >>> events = [
        ...     Event(name="full", day=Day.SUN, ...),
        ...     Event(name="half", day=Day.SUN, ...),
        ... ]
        >>> filtered = filter_flow_csv_by_events(flow_df, events)
        >>> len(filtered) == 1  # Only Full-Half pair
        True
    """
    if flow_df.empty:
        return flow_df
    
    # Get normalized event names (lowercase)
    event_names = {event.name.lower() for event in events}
    
    # Filter rows where both event_a and event_b are in requested events
    # Case-insensitive matching
    if "event_a" in flow_df.columns and "event_b" in flow_df.columns:
        mask = (
            flow_df["event_a"].astype(str).str.lower().isin(event_names) &
            flow_df["event_b"].astype(str).str.lower().isin(event_names)
        )
        filtered = flow_df[mask].copy()
        
        logger.debug(
            f"Filtered flow.csv from {len(flow_df)} rows to {len(filtered)} rows "
            f"for {len(events)} requested events"
        )
        
        return filtered
    else:
        logger.warning("flow.csv missing 'event_a' or 'event_b' columns, returning original DataFrame")
        return flow_df


def analyze_temporal_flow_segments_v2(
    events: List[Event],
    timelines: List[DayTimeline],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame,
    flow_df: pd.DataFrame,
    pace_csv: Optional[str] = None,
    segments_csv: Optional[str] = None,
    min_overlap_duration: float = 0.0,
    conflict_length_m: float = 50.0,
) -> Dict[Day, Dict[str, Any]]:
    """
    Analyze temporal flow for all segments using v2 Event objects and day-scoped data.
    
    This is the main v2 entry point that:
    1. Generates same-day event pairs
    2. Filters segments to those shared by both events
    3. Filters flow.csv to requested events
    4. Calls existing flow math functions with filtered data
    5. Returns results partitioned by day
    
    Args:
        events: List of Event objects from API payload
        timelines: List of DayTimeline objects from Phase 3
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame (all events)
        flow_df: Flow DataFrame from flow.csv
        pace_csv: Optional path to pace CSV (if None, will create temporary file from all_runners_df)
        segments_csv: Optional path to segments CSV (if None, will create temporary file from segments_df)
        min_overlap_duration: Minimum overlap duration for flow analysis
        conflict_length_m: Conflict length in meters for flow analysis
        
    Returns:
        Dictionary mapping Day to flow analysis results:
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
    # Generate same-day event pairs
    pairs = generate_event_pairs_v2(events)
    
    if not pairs:
        logger.warning("No event pairs generated, returning empty results")
        return {}
    
    # Filter flow.csv to requested events
    filtered_flow_df = filter_flow_csv_by_events(flow_df, events)
    
    # Group pairs by day for day-scoped analysis
    pairs_by_day: Dict[Day, List[Tuple[Event, Event]]] = {}
    for event_a, event_b in pairs:
        day = event_a.day  # Both events have same day (enforced in generate_event_pairs_v2)
        pairs_by_day.setdefault(day, []).append((event_a, event_b))
    
    # Analyze flow per day
    results_by_day: Dict[Day, Dict[str, Any]] = {}
    
    for day, day_pairs in pairs_by_day.items():
        # Get timeline for this day
        day_timeline = next((t for t in timelines if t.day == day), None)
        if not day_timeline:
            logger.warning(f"No timeline found for day {day.value}, skipping flow analysis")
            continue
        
        # Filter runners to this day
        day_event_names = {event.name.lower() for pair in day_pairs for event in pair}
        day_runners_df = all_runners_df[
            all_runners_df["event"].astype(str).str.lower().isin(day_event_names)
        ].copy()
        
        if day_runners_df.empty:
            logger.warning(f"No runners found for day {day.value}, skipping flow analysis")
            results_by_day[day] = {
                "ok": False,
                "error": f"No runners found for day {day.value}"
            }
            continue
        
        # Prepare start_times dict (convert minutes to datetime for v1 compatibility)
        # Map v2 event names to v1 format
        event_name_mapping = {
            "full": "Full",
            "half": "Half",
            "10k": "10K",
            "elite": "Elite",
            "open": "Open"
        }
        
        start_times: Dict[str, float] = {}
        for event in [e for pair in day_pairs for e in pair]:
            v1_event_name = event_name_mapping.get(event.name.lower(), event.name.capitalize())
            # start_times expects minutes after midnight (already in Event.start_time)
            start_times[v1_event_name] = float(event.start_time)
        
        # Map event names in runners DataFrame to v1 format
        if "event" in day_runners_df.columns:
            day_runners_df = day_runners_df.copy()
            day_runners_df["event"] = day_runners_df["event"].str.lower().map(
                lambda x: event_name_mapping.get(x, x.capitalize())
            )
        
        # For each pair, filter segments and analyze flow
        day_results = {
            "ok": True,
            "day": day.value,
            "pairs": [],
            "segments": {},
            "summary": {
                "total_pairs": len(day_pairs),
                "processed_pairs": 0,
            }
        }
        
        for event_a, event_b in day_pairs:
            # Get shared segments for this pair
            shared_segments = get_shared_segments(event_a, event_b, segments_df)
            
            if shared_segments.empty:
                logger.debug(
                    f"No shared segments found for pair ({event_a.name}, {event_b.name}), skipping"
                )
                continue
            
            # Create temporary CSV files if needed
            import tempfile
            import os
            
            temp_pace_csv = pace_csv
            temp_segments_csv = segments_csv
            
            if not temp_pace_csv:
                # Create temporary pace CSV from day_runners_df
                temp_fd, temp_pace_csv = tempfile.mkstemp(suffix='.csv', prefix='pace_')
                os.close(temp_fd)
                day_runners_df.to_csv(temp_pace_csv, index=False)
            
            if not temp_segments_csv:
                # Convert shared_segments to flow format (long format with event pairs)
                # This matches what analyze_temporal_flow_segments expects
                flow_format_segments = []
                for _, segment in shared_segments.iterrows():
                    # Create converted segment in flow format using v2 function
                    converted = _create_converted_segment_v2(segment, event_a, event_b)
                    flow_format_segments.append(converted)
                
                flow_format_df = pd.DataFrame(flow_format_segments)
                
                # Create temporary segments CSV from flow format segments
                temp_fd, temp_segments_csv = tempfile.mkstemp(suffix='.csv', prefix='segments_')
                os.close(temp_fd)
                flow_format_df.to_csv(temp_segments_csv, index=False)
            
            try:
                # Call existing flow analysis function with filtered data
                # This reuses all existing flow math (overtake detection, co-presence, etc.)
                pair_results = analyze_temporal_flow_segments(
                    pace_csv=temp_pace_csv,
                    segments_csv=temp_segments_csv,
                    start_times=start_times,
                    min_overlap_duration=min_overlap_duration,
                    conflict_length_m=conflict_length_m,
                )
                
                # Store results for this pair
                pair_key = f"{event_a.name}_{event_b.name}"
                day_results["pairs"].append(pair_key)
                day_results["segments"][pair_key] = pair_results.get("segments", {})
                day_results["summary"]["processed_pairs"] += 1
                
            except Exception as e:
                logger.error(
                    f"Error analyzing flow for pair ({event_a.name}, {event_b.name}): {e}",
                    exc_info=True
                )
                continue
            finally:
                # Clean up temporary files if we created them
                if not pace_csv and os.path.exists(temp_pace_csv):
                    os.remove(temp_pace_csv)
                if not segments_csv and os.path.exists(temp_segments_csv):
                    os.remove(temp_segments_csv)
        
        results_by_day[day] = day_results
    
    return results_by_day

