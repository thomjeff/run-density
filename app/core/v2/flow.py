"""
Runflow v2 Flow Pipeline Module

Refactors flow pipeline to support multi-day, multi-event analysis.
Uses flow.csv as authoritative source for event pairs, ordering, and distance ranges.
Upholds existing flow calculations while ensuring no cross-day contamination.

Phase 5: Flow Pipeline Refactor (Issue #499)
Issue #553: Removed all fallback logic - fail-fast behavior enforced.

Core Principles:
- flow.csv is the ONLY source for:
  * Which event pairs to analyze (including same-event pairs like elite-elite, open-open)
  * Event ordering (event_a vs event_b)
  * Distance ranges (from_km_a, to_km_a, from_km_b, to_km_b)
  * Flow metadata (flow_type, notes)
- Handle sub-segment pattern (e.g., A1 → A1a, A1b, A1c)
- Issue #553: NO fallbacks - if flow.csv is missing, unreadable, or missing required pairs, the request fails
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


def load_flow_csv(
    flow_file: str,
    data_dir: str = "data"
) -> pd.DataFrame:
    """
    Load flow.csv as the authoritative source for event pairs, ordering, and distance ranges.
    
    Args:
        flow_file: Name of flow CSV file (default: "flow.csv")
        data_dir: Base directory for data files (default: "data")
        
    Returns:
        DataFrame with flow.csv data, or empty DataFrame if file doesn't exist
    """
    flow_path = Path(data_dir) / flow_file
    
    if not flow_path.exists():
        logger.warning(f"Flow file '{flow_file}' not found in {data_dir}/, proceeding without flow.csv")
        return pd.DataFrame()
    
    try:
        flow_df = pd.read_csv(flow_path)
        logger.info(f"Loaded {len(flow_df)} rows from flow.csv")
        return flow_df
    except Exception as e:
        logger.warning(f"Failed to load flow.csv: {e}, proceeding without flow.csv")
        return pd.DataFrame()


def extract_event_pairs_from_flow_csv(
    flow_df: pd.DataFrame,
    events: List[Event]
) -> List[Tuple[Event, Event]]:
    """
    Extract event pairs from flow.csv, preserving the intentional ordering.
    
    flow.csv defines event_a and event_b with intentional ordering based on race dynamics.
    This function extracts unique pairs from flow.csv and maps them to Event objects.
    
    Args:
        flow_df: DataFrame from flow.csv
        events: List of Event objects from API payload
        
    Returns:
        List of (Event, Event) tuples, ordered as specified in flow.csv
    """
    if flow_df.empty:
        return []
    
    # Create event lookup by name (case-insensitive)
    event_lookup = {}
    for event in events:
        event_lookup[event.name.lower()] = event
    
    # Extract unique event pairs from flow.csv
    pairs_set = set()
    pairs_list = []
    
    for _, row in flow_df.iterrows():
        event_a_name = str(row.get('event_a', '')).lower()
        event_b_name = str(row.get('event_b', '')).lower()
        
        # Skip if either event is missing or not in our events list
        if not event_a_name or not event_b_name:
            continue
        
        event_a_obj = event_lookup.get(event_a_name)
        event_b_obj = event_lookup.get(event_b_name)
        
        if event_a_obj and event_b_obj:
            # Use tuple of (lowercase_name_a, lowercase_name_b) as key to preserve ordering
            pair_key = (event_a_name, event_b_name)
            
            if pair_key not in pairs_set:
                pairs_set.add(pair_key)
                # Preserve flow.csv ordering: (event_a, event_b)
                pairs_list.append((event_a_obj, event_b_obj))
    
    logger.info(f"Extracted {len(pairs_list)} unique event pairs from flow.csv")
    return pairs_list


def generate_event_pairs_fallback(
    events: List[Event]
) -> List[Tuple[Event, Event]]:
    """
    Generate event pairs using start_time ordering as fallback when flow.csv is not available.
    
    **WARNING**: This function should only be used when flow.csv doesn't contain a specific event pair.
    flow.csv is the authoritative source for event pair ordering (Issue #512).
    
    This fallback is only for:
    1. Debugging scenarios
    2. Incomplete metadata scenarios (missing flow.csv entries)
    3. Rare cases where flow.csv doesn't have a pair
    
    **If this fallback is used, a warning is logged** to identify missing flow.csv entries.
    
    Orders pairs by start time: event_a (earlier) < event_b (later).
    
    Args:
        events: List of Event objects from API payload
        
    Returns:
        List of (Event, Event) tuples for same-day pairs, ordered by start time
    """
    if not events:
        raise ValueError("Cannot generate event pairs from empty events list")
    
    # Group events by day
    from app.core.v2.loader import group_events_by_day
    events_by_day = group_events_by_day(events)
    
    pairs: List[Tuple[Event, Event]] = []
    
    for day, day_events in events_by_day.items():
        day_combinations = list(combinations(day_events, 2))
        
        # Order each pair by start time: (earlier event, later event)
        for event1, event2 in day_combinations:
            if event1.start_time <= event2.start_time:
                pairs.append((event1, event2))
            else:
                pairs.append((event2, event1))
    
    logger.info(f"Generated {len(pairs)} event pairs using fallback (start_time ordering)")
    return pairs


def find_flow_csv_segments_for_pair(
    flow_df: pd.DataFrame,
    event_a: Event,
    event_b: Event,
    segments_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Find all segments in flow.csv for a specific event pair, including sub-segments.
    
    Handles sub-segment pattern (e.g., A1 → A1a, A1b, A1c) by matching:
    1. Exact seg_id matches
    2. Sub-segments where seg_id starts with the base segment ID
    
    Args:
        flow_df: DataFrame from flow.csv
        event_a: First event in pair (as specified in flow.csv)
        event_b: Second event in pair (as specified in flow.csv)
        segments_df: Full segments DataFrame (for fallback)
        
    Returns:
        DataFrame with matching rows from flow.csv
    """
    if flow_df.empty:
        return pd.DataFrame()
    
    # Normalize event names for matching
    event_a_name = event_a.name.lower()
    event_b_name = event_b.name.lower()
    
    # Find rows matching this event pair (case-insensitive)
    mask = (
        (flow_df["event_a"].astype(str).str.lower() == event_a_name) &
        (flow_df["event_b"].astype(str).str.lower() == event_b_name)
    )
    
    matching_rows = flow_df[mask].copy()
    
    if not matching_rows.empty:
        logger.debug(
            f"Found {len(matching_rows)} flow.csv rows for pair ({event_a.name}, {event_b.name})"
        )
        return matching_rows
    
    return pd.DataFrame()


def _get_required_flow_type(flow_row: pd.Series, seg_id: str, event_a: Event, event_b: Event) -> str:
    """
    Get flow_type from flow.csv, failing if missing or empty.
    
    Issue #549: flow_type is required in flow.csv for all segment-pairs.
    No fallback - flow.csv must be complete.
    
    Args:
        flow_row: Row from flow.csv DataFrame
        seg_id: Segment ID for error message
        event_a: Event A for error message
        event_b: Event B for error message
        
    Returns:
        flow_type string (never empty or None)
        
    Raises:
        ValueError: If flow_type is missing, empty, or NaN
    """
    flow_type = flow_row.get("flow_type", "")
    
    # Check if missing or empty
    if pd.isna(flow_type) or not str(flow_type).strip():
        error_msg = (
            f"flow_type is required in flow.csv for segment '{seg_id}' "
            f"(event pair: {event_a.name}/{event_b.name}), but it is missing or empty. "
            f"flow.csv must contain flow_type for all segment-pairs. "
            f"Valid values: 'overtake', 'merge', 'counterflow', 'parallel', 'none'"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    return str(flow_type).strip()


def create_flow_segments_from_flow_csv(
    flow_rows: pd.DataFrame,
    event_a: Event,
    event_b: Event,
    segments_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Create flow-format segments DataFrame from flow.csv rows.
    
    Uses flow.csv as authoritative source for:
    - Event ordering (event_a, event_b)
    - Distance ranges (from_km_a, to_km_a, from_km_b, to_km_b)
    - Flow metadata (flow_type, notes, prior_seg_id)
    
    Args:
        flow_rows: DataFrame with matching rows from flow.csv
        event_a: First event in pair (as Event object)
        event_b: Second event in pair (as Event object)
        segments_df: Full segments DataFrame (for additional metadata like width_m, direction)
        
    Returns:
        DataFrame in flow format with columns: seg_id, eventa, eventb, from_km_a, to_km_a, etc.
    """
    flow_format_segments = []
    
    # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
    event_a_lower = event_a.name.lower()
    event_b_lower = event_b.name.lower()
    
    for _, flow_row in flow_rows.iterrows():
        seg_id = flow_row["seg_id"]
        
        # Get base segment ID (e.g., "A1" from "A1a")
        base_seg_id = seg_id.rstrip('abcdefghijklmnopqrstuvwxyz')
        
        # Try to find base segment in segments_df for additional metadata
        seg_metadata = segments_df[segments_df["seg_id"] == base_seg_id]
        
        # Use flow.csv distance ranges (authoritative)
        from_km_a = float(flow_row.get("from_km_a", 0))
        to_km_a = float(flow_row.get("to_km_a", 0))
        from_km_b = float(flow_row.get("from_km_b", 0))
        to_km_b = float(flow_row.get("to_km_b", 0))
        
        # Get additional metadata from segments_df (physical properties)
        # Issue #549: direction and width_m are physical properties, only in segments.csv
        width_m = 0
        direction = ""
        if not seg_metadata.empty:
            width_m = seg_metadata.iloc[0].get("width_m", 0)
            direction = seg_metadata.iloc[0].get("direction", "")
        
        # Create flow-format segment using flow.csv data
        flow_segment = {
            "seg_id": seg_id,
            "segment_label": flow_row.get("seg_label", ""),
            "eventa": event_a_lower,  # Issue #548 Bug 1: Use lowercase consistently
            "eventb": event_b_lower,  # Issue #548 Bug 1: Use lowercase consistently
            "from_km_a": from_km_a,  # From flow.csv
            "to_km_a": to_km_a,  # From flow.csv
            "from_km_b": from_km_b,  # From flow.csv
            "to_km_b": to_km_b,  # From flow.csv
            "direction": direction,  # Issue #549: Always from segments.csv (physical property)
            "width_m": width_m,  # Issue #549: Always from segments.csv (physical property)
            "flow_type": flow_row.get("flow_type", "none"),  # Issue #549: Flow-specific, from flow.csv
            "prior_segment_id": flow_row.get("prior_seg_id", "") if pd.notna(flow_row.get("prior_seg_id", "")) else "",
            "notes": flow_row.get("notes", ""),
            "length_km": to_km_a - from_km_a if to_km_a > from_km_a else 0
        }
        flow_format_segments.append(flow_segment)
    
    flow_format_df = pd.DataFrame(flow_format_segments)
    
    logger.debug(
        f"Created {len(flow_format_df)} flow-format segments from flow.csv for pair ({event_a.name}, {event_b.name})"
    )
    
    return flow_format_df


def create_flow_segments_fallback(
    shared_segments: pd.DataFrame,
    event_a: Event,
    event_b: Event
) -> pd.DataFrame:
    """
    Create flow-format segments DataFrame using fallback logic (segments.csv + start_time ordering).
    
    This is only used when flow.csv doesn't contain the segment-pair.
    Uses get_event_distance_range_v2() to extract from segments.csv.
    
    Args:
        shared_segments: Segments DataFrame (segments where both events are present)
        event_a: First event in pair (ordered by start_time)
        event_b: Second event in pair (ordered by start_time)
        
    Returns:
        DataFrame in flow format with columns: seg_id, eventa, eventb, from_km_a, to_km_a, etc.
    """
    flow_format_segments = []
    
    # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
    event_a_lower = event_a.name.lower()
    event_b_lower = event_b.name.lower()
    
    for _, segment_row in shared_segments.iterrows():
        seg_id = segment_row["seg_id"]
        
        # Get distance ranges from segments.csv using get_event_distance_range_v2()
        from_km_a, to_km_a = get_event_distance_range_v2(segment_row, event_a)
        from_km_b, to_km_b = get_event_distance_range_v2(segment_row, event_b)
        
        # Create flow-format segment
        flow_segment = {
            "seg_id": seg_id,
            "segment_label": segment_row.get("seg_label", ""),
            "eventa": event_a_lower,  # Issue #548 Bug 1: Use lowercase consistently
            "eventb": event_b_lower,  # Issue #548 Bug 1: Use lowercase consistently
            "from_km_a": from_km_a,
            "to_km_a": to_km_a,
            "from_km_b": from_km_b,
            "to_km_b": to_km_b,
            "direction": segment_row.get("direction", ""),  # Issue #549: Physical property from segments.csv
            "width_m": segment_row.get("width_m", 0),  # Issue #549: Physical property from segments.csv
            "flow_type": "none",  # Issue #549: Fallback default (flow.csv should have all segment-pairs, this is rare fallback only)
            "prior_segment_id": "",
            "notes": "",
            "length_km": segment_row.get("length_km", 0)
        }
        flow_format_segments.append(flow_segment)
    
    flow_format_df = pd.DataFrame(flow_format_segments)
    
    logger.debug(
        f"Created {len(flow_format_df)} flow-format segments (fallback) for pair ({event_a.name}, {event_b.name})"
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
    enable_audit: str = 'n',
    run_id: Optional[str] = None,
    run_path: Optional[Path] = None
) -> Dict[Day, Dict[str, Any]]:
    """
    Analyze temporal flow for all segments using v2 Event objects and day-scoped data.
    
    Issue #553: This function enforces fail-fast behavior with no fallbacks.
    flow.csv is the ONLY source of event pairs - no auto-generation, no inference.
    
    This is the main v2 entry point that:
    1. Loads flow.csv as authoritative source (fails if missing or unreadable)
    2. Extracts event pairs from flow.csv (preserving intentional ordering)
    3. Validates that all requested events have pairs in flow.csv (fails if missing)
    4. For each pair, finds matching segments in flow.csv (including sub-segments)
    5. Uses flow.csv distance ranges and event ordering
    6. Calls existing v1 analyze_temporal_flow_segments() function
    7. Returns results partitioned by day
    
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
        Dictionary mapping Day to flow analysis results
        
    Raises:
        FileNotFoundError: If flow.csv file does not exist
        ValueError: If flow.csv is empty, unreadable, or missing required event pairs
    """
    results_by_day: Dict[Day, Dict[str, Any]] = {}
    
    # Load flow.csv as authoritative source (Issue #553: fail-fast, no fallbacks)
    # Handle both relative and absolute paths
    # get_flow_file() returns full paths like "data/flow.csv", so check if it already includes data_dir
    if Path(flow_file).is_absolute():
        # Absolute path, use as-is
        flow_path = Path(flow_file)
    elif flow_file.startswith(f"{data_dir}/") or flow_file.startswith(f"{data_dir}\\"):
        # flow_file already includes data_dir prefix (e.g., "data/flow.csv")
        flow_path = Path(flow_file)
    elif '/' in flow_file or '\\' in flow_file:
        # flow_file is a relative path but not starting with data_dir, use as-is
        flow_path = Path(flow_file)
    else:
        # flow_file is just a filename (e.g., "flow.csv"), prepend data_dir
        flow_path = Path(data_dir) / flow_file
    
    if not flow_path.exists():
        error_msg = (
            f"flow.csv file not found at {flow_path}. "
            "flow.csv is required for flow analysis and must be provided in the request. "
            "No fallback or auto-generation of event pairs is allowed per Issue #553."
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        flow_df = pd.read_csv(flow_path)
        logger.info(f"Loaded {len(flow_df)} rows from flow.csv at {flow_path}")
    except Exception as e:
        error_msg = (
            f"Failed to load flow.csv from {flow_path}: {e}. "
            "flow.csv must be readable and valid. No fallback is allowed per Issue #553."
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from e
    
    if flow_df.empty:
        error_msg = (
            f"flow.csv at {flow_path} is empty. "
            "flow.csv must contain valid event pairs. No fallback is allowed per Issue #553."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Extract event pairs from flow.csv (preserving intentional ordering)
    # Issue #553: This is the ONLY source of event pairs - no fallback, no auto-generation
    flow_csv_pairs = extract_event_pairs_from_flow_csv(flow_df, events)
    
    if not flow_csv_pairs:
        requested_event_names = {e.name.lower() for e in events}
        error_msg = (
            f"No valid event pairs found in flow.csv for requested events: {sorted(requested_event_names)}. "
            "flow.csv must contain pairs for all requested events (including same-event pairs like elite-elite, open-open). "
            "No fallback or auto-generation of event pairs is allowed per Issue #553."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate that all requested events have at least one pair in flow.csv
    requested_event_names = {e.name.lower() for e in events}
    flow_csv_event_names = set()
    for pair in flow_csv_pairs:
        flow_csv_event_names.add(pair[0].name.lower())
        flow_csv_event_names.add(pair[1].name.lower())
    
    missing_events = requested_event_names - flow_csv_event_names
    if missing_events:
        error_msg = (
            f"Requested events {sorted(missing_events)} have no pairs defined in flow.csv. "
            f"flow.csv contains pairs for: {sorted(flow_csv_event_names)}. "
            "All requested events must have at least one pair (including same-event pairs) in flow.csv. "
            "No fallback or auto-generation of event pairs is allowed per Issue #553."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.info(f"Extracted {len(flow_csv_pairs)} event pairs from flow.csv for events: {sorted(requested_event_names)}")
    
    # Use only pairs from flow.csv - no fallback, no auto-generation
    all_pairs = flow_csv_pairs
    
    # Group pairs by day
    pairs_by_day: Dict[Day, List[Tuple[Event, Event]]] = {}
    for event_a, event_b in all_pairs:
        day = event_a.day  # Both events have same day
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
        
        # Prepare start_times dict (in minutes, not datetime)
        # Issue #548 Bug 1: Use lowercase event names consistently (no v1 uppercase compatibility)
        start_times = {}
        
        for event in day_events_unique:
            start_times[event.name.lower()] = float(event.start_time)
        
        logger.info(f"Day {day.value}: Analyzing {len(day_pairs)} pairs with {len(day_runners_df)} runners")
        
        # Collect all flow-format segments for all pairs on this day
        all_flow_segments = []
        
        for event_a, event_b in day_pairs:
            # Try to find segments in flow.csv first (authoritative)
            flow_csv_rows = find_flow_csv_segments_for_pair(flow_df, event_a, event_b, segments_df)
            
            if not flow_csv_rows.empty:
                # Use flow.csv as authoritative source
                flow_format_segments = create_flow_segments_from_flow_csv(
                    flow_csv_rows, event_a, event_b, segments_df
                )
                all_flow_segments.append(flow_format_segments)
                logger.debug(
                    f"Using flow.csv for pair ({event_a.name}, {event_b.name}): {len(flow_format_segments)} segments"
                )
            else:
                # Fallback: use segments.csv + start_time ordering
                shared_segments = get_shared_segments(event_a, event_b, segments_df)
                
                if shared_segments.empty:
                    logger.debug(
                        f"No shared segments found for pair ({event_a.name}, {event_b.name}), skipping"
                    )
                    continue
                
                flow_format_segments = create_flow_segments_fallback(
                    shared_segments, event_a, event_b
                )
                all_flow_segments.append(flow_format_segments)
                logger.debug(
                    f"Using fallback for pair ({event_a.name}, {event_b.name}): {len(flow_format_segments)} segments"
                )
        
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
            
            # Generate audit files if enabled
            logger.info(f"Day {day.value}: Checking audit generation - enable_audit={enable_audit}, run_path={run_path}")
            if enable_audit.lower() == 'y' and run_path is not None:
                segments_list = flow_results.get('segments', [])
                logger.info(f"Day {day.value}: Generating flow audit files for {len(segments_list)} segments")
                day_path = run_path / day.value
                # Audit files go directly under {day}/audit/
                output_dir = str(day_path)
                logger.info(f"Day {day.value}: Output directory for audit: {output_dir}")
                
                # Issue #607: Accumulate audit DataFrames from all segments
                audit_dataframes = []
                segment_count = 0
                
                for segment in segments_list:
                    segment_count += 1
                    try:
                        seg_id = segment.get('seg_id')
                        event_a_name = segment.get('event_a')
                        event_b_name = segment.get('event_b')
                        from_km_a = segment.get('from_km_a', 0.0)
                        to_km_a = segment.get('to_km_a', 0.0)
                        from_km_b = segment.get('from_km_b', 0.0)
                        to_km_b = segment.get('to_km_b', 0.0)
                        conflict_start = segment.get('convergence_zone_start')
                        conflict_end = segment.get('convergence_zone_end')
                        conflict_length_m = segment.get('conflict_length_m', conflict_length_m)
                        
                        # Filter runners for event_a and event_b
                        df_a = day_runners_df[day_runners_df['event'].str.lower() == event_a_name.lower()].copy()
                        df_b = day_runners_df[day_runners_df['event'].str.lower() == event_b_name.lower()].copy()
                        
                        if not df_a.empty and not df_b.empty:
                            from app.core.flow.flow import _generate_runner_audit_for_segment
                            audit_result = _generate_runner_audit_for_segment(
                                seg_id=seg_id,
                                segment=segment,
                                event_a=event_a_name,
                                event_b=event_b_name,
                                df_a=df_a,
                                df_b=df_b,
                                start_times=start_times,
                                from_km_a=from_km_a,
                                to_km_a=to_km_a,
                                from_km_b=from_km_b,
                                to_km_b=to_km_b,
                                conflict_start=conflict_start,
                                conflict_end=conflict_end,
                                conflict_length_m=conflict_length_m,
                                output_dir=output_dir
                            )
                            if audit_result is not None:
                                audit_df, stats = audit_result
                                if not audit_df.empty:
                                    audit_dataframes.append(audit_df)
                                logger.info(f"  ✓ Generated audit for {seg_id} ({event_a_name} vs {event_b_name}): {len(audit_df)} rows")
                            else:
                                logger.warning(f"  ⚠ Audit generation returned None for {seg_id} ({event_a_name} vs {event_b_name})")
                        else:
                            logger.warning(f"  ⚠ Skipping audit for {seg_id}: empty dataframes (A: {len(df_a)}, B: {len(df_b)})")
                    except Exception as e:
                        logger.error(f"  ❌ Failed to generate audit for segment {segment.get('seg_id', 'unknown')}: {e}", exc_info=True)
                
                # Issue #607: Write single Parquet file per day
                if audit_dataframes:
                    audit_dir = day_path / "audit"
                    audit_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Combine all segment DataFrames
                    combined_audit_df = pd.concat(audit_dataframes, ignore_index=True)
                    
                    # Determine day name for filename (sat or sun)
                    day_name = day.value.lower()[:3]  # "saturday" -> "sat", "sunday" -> "sun"
                    parquet_path = audit_dir / f"audit_{day_name}.parquet"
                    
                    # Write Parquet file
                    combined_audit_df.to_parquet(parquet_path, index=False, engine='pyarrow')
                    
                    logger.info(f"Day {day.value}: Wrote audit Parquet file: {parquet_path} ({len(combined_audit_df)} rows, {parquet_path.stat().st_size / 1024 / 1024:.1f} MB)")
                else:
                    logger.warning(f"Day {day.value}: No audit data to write (all segments returned empty DataFrames)")
            
                logger.info(f"Day {day.value}: Completed audit generation loop for {segment_count} segments")
            else:
                logger.info(f"Day {day.value}: Audit generation skipped - enable_audit={enable_audit}, run_path={run_path}")
            
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
