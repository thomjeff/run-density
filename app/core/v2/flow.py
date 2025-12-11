"""
Runflow v2 Flow Pipeline Module

Refactors flow pipeline to support multi-day, multi-event analysis.
Finds all segments where both events are present, then calls existing v1 flow math.
Upholds existing flow calculations while ensuring no cross-day contamination.

Phase 5: Flow Pipeline Refactor (Issue #499)

Core Principles:
- Use get_shared_segments() to find ALL segments where BOTH events are present (from segments.csv event flags)
- Use get_event_distance_range_v2() to extract {event}_from_km, {event}_to_km from segments.csv
- Use flow.csv ONLY for metadata (flow_type, notes, overtake_flag) - NOT to filter segments
- Load runners from per-event CSV files, map to v1 format
- Do not alter core flow logic (overtake detection, co-presence, convergence)
- Reuse v1 analyze_temporal_flow_segments() function without modification
"""

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import logging
import tempfile
import os
from itertools import combinations

from app.core.v2.models import Day, Event
from app.core.v2.timeline import DayTimeline
from app.core.v2.bins import filter_segments_by_events
from app.core.v2.density import get_event_distance_range_v2, load_all_runners_for_events, filter_runners_by_day
from app.core.flow.flow import analyze_temporal_flow_segments
from app.utils.shared import load_pace_csv
from app.utils.constants import DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS

logger = logging.getLogger(__name__)


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
    if event_a.day != event_b.day:
        raise ValueError(
            f"Cross-day event pair detected: '{event_a.name}' (day: {event_a.day.value}) "
            f"and '{event_b.name}' (day: {event_b.day.value}) cannot be paired. "
            f"Flow analysis only supports same-day event pairs."
        )
    
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


def generate_event_pairs_v2(events: List[Event]) -> List[Tuple[Event, Event]]:
    """
    Generate event pairs only for events sharing the same day.
    
    Uses itertools.combinations to generate unique pairs, then orders them semantically:
    - event_a: The event with earlier start time (being overtaken)
    - event_b: The event with later start time (doing the overtaking)
    
    This ordering is critical for correct interpretation of overtaking counts:
    - overtaking_b = number of event_b runners overtaking event_a runners
    - overtaking_a = number of event_a runners overtaking event_b runners
    
    Args:
        events: List of Event objects from API payload
        
    Returns:
        List of (Event, Event) tuples for same-day pairs, ordered by start time
        
    Examples:
        Sunday events (full=420, half=460, 10k=440):
        Returns (full, 10k), (full, half), (10k, half) - ordered by start time
        
    Raises:
        ValueError: If events list is empty
    """
    if not events:
        raise ValueError("Cannot generate event pairs from empty events list")
    
    # Group events by day
    from app.core.v2.loader import group_events_by_day
    events_by_day = group_events_by_day(events)
    
    # Generate pairs within each day
    # Order pairs by start time: event_a (earlier) < event_b (later)
    pairs: List[Tuple[Event, Event]] = []
    
    for day, day_events in events_by_day.items():
        # Generate all unique combinations of 2 events for the current day
        # combinations() ensures no duplicates and no self-pairs
        day_combinations = list(combinations(day_events, 2))
        
        # Order each pair by start time: (earlier event, later event)
        for event1, event2 in day_combinations:
            # Ensure event_a has earlier or equal start time
            if event1.start_time <= event2.start_time:
                pairs.append((event1, event2))
            else:
                pairs.append((event2, event1))
    
    logger.info(f"Generated {len(pairs)} unique event pairs from {len(events)} events across {len(events_by_day)} days")
    return pairs


def load_flow_metadata(
    flow_file: str,
    data_dir: str = "data"
) -> pd.DataFrame:
    """
    Load flow.csv for metadata only (flow_type, notes, overtake_flag).
    
    This function loads flow.csv but it should NOT be used to filter segments.
    It's only used to provide metadata for segments that are explicitly listed.
    
    Args:
        flow_file: Name of flow CSV file (default: "flow.csv")
        data_dir: Base directory for data files (default: "data")
        
    Returns:
        DataFrame with flow metadata, or empty DataFrame if file doesn't exist
    """
    flow_path = Path(data_dir) / flow_file
    
    if not flow_path.exists():
        logger.warning(f"Flow file '{flow_file}' not found in {data_dir}/, proceeding without flow metadata")
        return pd.DataFrame()
    
    try:
        flow_df = pd.read_csv(flow_path)
        logger.debug(f"Loaded {len(flow_df)} rows from flow.csv for metadata")
        return flow_df
    except Exception as e:
        logger.warning(f"Failed to load flow.csv: {e}, proceeding without flow metadata")
        return pd.DataFrame()


def get_flow_metadata_for_segment(
    seg_id: str,
    event_a: Event,
    event_b: Event,
    flow_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Get flow metadata for a specific segment and event pair from flow.csv.
    
    If the segment/pair is not in flow.csv, returns default values.
    This function is used ONLY for metadata, not to determine which segments to analyze.
    
    Args:
        seg_id: Segment ID
        event_a: First event in pair
        event_b: Second event in pair
        flow_df: Flow DataFrame from flow.csv
        
    Returns:
        Dictionary with flow metadata (flow_type, notes, overtake_flag, etc.)
        or default values if not found in flow.csv
    """
    if flow_df.empty:
        return {
            "flow_type": "none",
            "notes": "",
            "overtake_flag": ""
        }
    
    # Find matching row in flow.csv (case-insensitive event name matching)
    mask = (
        (flow_df["seg_id"].astype(str) == seg_id) &
        (flow_df["event_a"].astype(str).str.lower() == event_a.name.lower()) &
        (flow_df["event_b"].astype(str).str.lower() == event_b.name.lower())
    )
    
    matching_rows = flow_df[mask]
    
    if not matching_rows.empty:
        row = matching_rows.iloc[0]
        return {
            "flow_type": row.get("flow_type", "none"),
            "notes": row.get("notes", ""),
            "overtake_flag": row.get("overtake_flag", ""),
            "prior_seg_id": row.get("prior_seg_id", "") if pd.notna(row.get("prior_seg_id", "")) else ""
        }
    
    # Not found in flow.csv - return defaults
    return {
        "flow_type": "none",
        "notes": "",
        "overtake_flag": "",
        "prior_seg_id": ""
    }


def create_flow_segments_csv(
    shared_segments: pd.DataFrame,
    event_a: Event,
    event_b: Event,
    flow_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create flow-format segments DataFrame for v1 analyze_temporal_flow_segments().
    
    This function:
    1. Uses get_event_distance_range_v2() to get distance ranges from segments.csv
    2. Uses flow.csv for metadata (flow_type, notes) if available
    3. Creates DataFrame in the format v1 expects (eventa, eventb, from_km_a, to_km_a, etc.)
    
    Args:
        shared_segments: Segments DataFrame (segments where both events are present)
        event_a: First event in pair
        event_b: Second event in pair
        flow_df: Flow DataFrame from flow.csv (for metadata only)
        
    Returns:
        DataFrame in flow format with columns: seg_id, eventa, eventb, from_km_a, to_km_a, from_km_b, to_km_b, etc.
    """
    flow_format_segments = []
    
    # Event name mapping from v2 (lowercase) to v1 format
    event_name_mapping = {
        "full": "Full",
        "half": "Half",
        "10k": "10K",
        "elite": "Elite",
        "open": "Open"
    }
    
    v1_event_a = event_name_mapping.get(event_a.name.lower(), event_a.name.capitalize())
    v1_event_b = event_name_mapping.get(event_b.name.lower(), event_b.name.capitalize())
    
    for _, segment_row in shared_segments.iterrows():
        seg_id = segment_row["seg_id"]
        
        # Get distance ranges from segments.csv using get_event_distance_range_v2()
        from_km_a, to_km_a = get_event_distance_range_v2(segment_row, event_a)
        from_km_b, to_km_b = get_event_distance_range_v2(segment_row, event_b)
        
        # Get metadata from flow.csv (if available)
        flow_metadata = get_flow_metadata_for_segment(seg_id, event_a, event_b, flow_df)
        
        # Create flow-format segment
        flow_segment = {
            "seg_id": seg_id,
            "segment_label": segment_row.get("seg_label", ""),
            "eventa": v1_event_a,
            "eventb": v1_event_b,
            "from_km_a": from_km_a,
            "to_km_a": to_km_a,
            "from_km_b": from_km_b,
            "to_km_b": to_km_b,
            "direction": segment_row.get("direction", ""),
            "width_m": segment_row.get("width_m", 0),
            "flow_type": flow_metadata["flow_type"],
            "overtake_flag": flow_metadata["overtake_flag"],
            "prior_segment_id": flow_metadata.get("prior_seg_id", ""),
            "notes": flow_metadata["notes"],
            "length_km": segment_row.get("length_km", 0)
        }
        flow_format_segments.append(flow_segment)
    
    flow_format_df = pd.DataFrame(flow_format_segments)
    
    logger.debug(
        f"Created {len(flow_format_df)} flow-format segments for pair ({event_a.name}, {event_b.name})"
    )
    
    return flow_format_df


def analyze_temporal_flow_segments_v2(
    events: List[Event],
    timelines: List[DayTimeline],
    segments_df: pd.DataFrame,
    all_runners_df: pd.DataFrame,
    flow_file: str = "flow.csv",
    data_dir: str = "data",
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
) -> Dict[Day, Dict[str, Any]]:
    """
    Analyze temporal flow for all segments using v2 Event objects and day-scoped data.
    
    This is the main v2 entry point that:
    1. Generates same-day event pairs
    2. Finds ALL segments where both events are present (using get_shared_segments)
    3. Uses get_event_distance_range_v2() to get distance ranges from segments.csv
    4. Uses flow.csv for metadata only (not to filter segments)
    5. Calls existing v1 analyze_temporal_flow_segments() function
    6. Returns results partitioned by day
    
    Args:
        events: List of Event objects from API payload
        timelines: List of DayTimeline objects from Phase 3
        segments_df: Full segments DataFrame
        all_runners_df: Full runners DataFrame (all events)
        flow_file: Name of flow CSV file (default: "flow.csv")
        data_dir: Base directory for data files (default: "data")
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
    results_by_day: Dict[Day, Dict[str, Any]] = {}
    
    # Load flow.csv for metadata only
    flow_df = load_flow_metadata(flow_file, data_dir)
    
    # Generate same-day event pairs
    pairs = generate_event_pairs_v2(events)
    
    if not pairs:
        logger.warning("No event pairs generated, returning empty results")
        return results_by_day
    
    # Group pairs by day
    pairs_by_day: Dict[Day, List[Tuple[Event, Event]]] = {}
    for event_a, event_b in pairs:
        day = event_a.day  # Both events have same day (enforced in generate_event_pairs_v2)
        pairs_by_day.setdefault(day, []).append((event_a, event_b))
    
    # Create timeline lookup
    timeline_by_day = {timeline.day: timeline for timeline in timelines}
    
    # Analyze flow per day
    for day, day_pairs in pairs_by_day.items():
        logger.info(f"Analyzing flow for day {day.value} with {len(day_pairs)} event pairs")
        
        # Get timeline for this day
        timeline = timeline_by_day.get(day)
        if not timeline:
            logger.warning(f"No timeline found for day {day.value}, skipping")
            continue
        
        # Filter runners to only those from events on this day
        day_events = [event for pair in day_pairs for event in pair]
        day_events_unique = list({event.name: event for event in day_events}.values())
        day_runners_df = filter_runners_by_day(all_runners_df, day, day_events_unique)
        
        if day_runners_df.empty:
            logger.warning(f"No runners found for day {day.value}, skipping flow analysis")
            results_by_day[day] = {
                "ok": False,
                "error": "No runners found for this day",
                "segments": [],
                "day": day.value,
                "events": [e.name for e in day_events_unique]
            }
            continue
        
        # Prepare start_times dict (in minutes, not datetime, for v1 compatibility)
        start_times = {}
        event_name_mapping = {
            "full": "Full",
            "half": "Half",
            "10k": "10K",
            "elite": "Elite",
            "open": "Open"
        }
        
        for event in day_events_unique:
            v1_event_name = event_name_mapping.get(event.name.lower(), event.name.capitalize())
            # v1 expects start_times in minutes (not datetime)
            start_times[v1_event_name] = float(event.start_time)
        
        logger.info(f"Day {day.value}: Analyzing {len(day_pairs)} pairs with {len(day_runners_df)} runners")
        
        # Collect all flow-format segments for all pairs on this day
        all_flow_segments = []
        
        for event_a, event_b in day_pairs:
            # Find ALL segments where both events are present (using get_shared_segments)
            shared_segments = get_shared_segments(event_a, event_b, segments_df)
            
            if shared_segments.empty:
                logger.debug(
                    f"No shared segments found for pair ({event_a.name}, {event_b.name}), skipping"
                )
                continue
            
            # Create flow-format segments DataFrame
            flow_format_segments = create_flow_segments_csv(shared_segments, event_a, event_b, flow_df)
            all_flow_segments.append(flow_format_segments)
        
        if not all_flow_segments:
            logger.warning(f"No flow segments found for day {day.value}")
            results_by_day[day] = {
                "ok": False,
                "error": "No flow segments found",
                "segments": [],
                "day": day.value,
                "events": [e.name for e in day_events_unique]
            }
            continue
        
        # Combine all flow segments
        combined_flow_segments = pd.concat(all_flow_segments, ignore_index=True)
        
        logger.info(
            f"Day {day.value}: Created {len(combined_flow_segments)} flow-format segments "
            f"for {len(day_pairs)} event pairs"
        )
        
        # Create temporary CSV files for v1 function
        temp_pace_csv = None
        temp_segments_csv = None
        
        try:
            # Create temporary pace CSV
            temp_fd, temp_pace_csv = tempfile.mkstemp(suffix='.csv', prefix='pace_')
            os.close(temp_fd)
            day_runners_df.to_csv(temp_pace_csv, index=False)
            
            # Create temporary segments CSV
            temp_fd, temp_segments_csv = tempfile.mkstemp(suffix='.csv', prefix='segments_')
            os.close(temp_fd)
            combined_flow_segments.to_csv(temp_segments_csv, index=False)
            
            # Call v1 analyze_temporal_flow_segments() function
            # This function expects:
            # - pace_csv: Path to CSV file with runner data
            # - segments_csv: Path to CSV file with segment data in flow format
            # - start_times: Dict[str, float] mapping event names to start times in minutes
            flow_results = analyze_temporal_flow_segments(
                pace_csv=temp_pace_csv,
                segments_csv=temp_segments_csv,
                start_times=start_times,
                min_overlap_duration=min_overlap_duration,
                conflict_length_m=conflict_length_m
            )
            
            # Add day and events metadata to results
            flow_results["day"] = day.value
            flow_results["events"] = [e.name for e in day_events_unique]
            
            results_by_day[day] = flow_results
            
            logger.info(
                f"Day {day.value}: Flow analysis complete. "
                f"Processed {len(flow_results.get('segments', []))} segments"
            )
            
        except Exception as e:
            logger.error(f"Day {day.value}: Flow analysis failed: {str(e)}", exc_info=True)
            results_by_day[day] = {
                "ok": False,
                "error": str(e),
                "segments": [],
                "day": day.value,
                "events": [e.name for e in day_events_unique]
            }
        finally:
            # Clean up temporary files
            if temp_pace_csv and os.path.exists(temp_pace_csv):
                os.unlink(temp_pace_csv)
            if temp_segments_csv and os.path.exists(temp_segments_csv):
                os.unlink(temp_segments_csv)
    
    return results_by_day

