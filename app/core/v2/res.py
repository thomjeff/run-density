"""
Runflow v2 Runner Experience Score (RES) Module

Calculates Runner Experience Score (RES) per event group using distance-weighted
aggregation of existing density and flow metrics.

Issue #573: Runner Experience Score (RES)

Core Principles:
- Uses existing segment-level metrics from segment_metrics.json (no new calculations)
- Distance-weighted aggregation across segments (segments weighted by course distance contribution)
- Participant-weighted aggregation for multi-event groups
- Deterministic and reproducible
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import logging

from app.core.v2.density import get_event_distance_range_v2
from app.core.v2.models import Event
from app.utils.constants import (
    RES_HIGH_DENSITY_THRESHOLD,
    RES_HIGH_FLOW_THRESHOLD,
    RES_FLOW_PENALTY_WEIGHT,
    RES_DENSITY_PENALTY_WEIGHT,
    SECONDS_PER_MINUTE
)

logger = logging.getLogger(__name__)


def calculate_event_total_distance(
    segments_df: pd.DataFrame,
    event_name: str
) -> float:
    """
    Calculate total course distance for an event from segments.csv.
    
    Uses {event}_from_km and {event}_to_km columns from segments.csv.
    Returns max(to_km) - min(from_km) across all segments used by the event.
    
    Args:
        segments_df: Segments DataFrame from segments.csv
        event_name: Event name (lowercase, e.g., "full", "half", "10k")
        
    Returns:
        float: Total course distance in kilometers
        
    Example:
        >>> segments_df = pd.DataFrame({
        ...     "seg_id": ["A1", "A2"],
        ...     "full": ["y", "y"],
        ...     "full_from_km": [0.0, 0.9],
        ...     "full_to_km": [0.9, 1.8]
        ... })
        >>> calculate_event_total_distance(segments_df, "full")
        1.8
    """
    event_name_lower = event_name.lower()
    
    # Filter segments used by this event (check event flag column)
    event_flag_col = event_name_lower
    if event_flag_col not in segments_df.columns:
        logger.warning(f"Event flag column '{event_flag_col}' not found in segments.csv")
        return 0.0
    
    # Filter segments where event flag is 'y'
    event_segments = segments_df[
        segments_df[event_flag_col].str.lower().isin(['y', 'yes', 'true', '1'])
    ]
    
    if len(event_segments) == 0:
        logger.warning(f"No segments found for event '{event_name}'")
        return 0.0
    
    # Get distance range columns
    from_col = f"{event_name_lower}_from_km"
    to_col = f"{event_name_lower}_to_km"
    
    # Find matching columns (case-insensitive)
    from_col_actual = None
    to_col_actual = None
    for col in event_segments.columns:
        if col.lower() == from_col.lower():
            from_col_actual = col
        elif col.lower() == to_col.lower():
            to_col_actual = col
    
    if from_col_actual is None or to_col_actual is None:
        logger.warning(f"Distance range columns not found for event '{event_name}' (expected {from_col}, {to_col})")
        return 0.0
    
    # Extract distance ranges
    from_values = event_segments[from_col_actual].dropna()
    to_values = event_segments[to_col_actual].dropna()
    
    if len(from_values) == 0 or len(to_values) == 0:
        logger.warning(f"No valid distance ranges found for event '{event_name}'")
        return 0.0
    
    # Calculate total distance: max(to_km) - min(from_km)
    try:
        min_from = float(from_values.min())
        max_to = float(to_values.max())
        total_distance = max_to - min_from
        
        if total_distance <= 0:
            logger.warning(f"Invalid total distance calculated for event '{event_name}': {total_distance}")
            return 0.0
        
        return total_distance
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to calculate total distance for event '{event_name}': {e}")
        return 0.0


def filter_segments_by_event_group(
    segments_df: pd.DataFrame,
    event_names: List[str]
) -> pd.DataFrame:
    """
    Filter segments where event flag matches any event in the group.
    
    Uses event flags (e.g., `elite=y`, `full=y`) from segments.csv.
    A segment is included if any event in the group uses it.
    
    Args:
        segments_df: Segments DataFrame from segments.csv
        event_names: List of event names in the group (e.g., ["elite"] or ["full", "10k", "half"])
        
    Returns:
        pd.DataFrame: Filtered segments DataFrame
        
    Example:
        >>> segments_df = pd.DataFrame({
        ...     "seg_id": ["A1", "N1", "B1"],
        ...     "elite": ["n", "y", "n"],
        ...     "full": ["y", "n", "y"]
        ... })
        >>> filter_segments_by_event_group(segments_df, ["elite"])
           seg_id elite full
        1     N1     y    n
        >>> filter_segments_by_event_group(segments_df, ["full", "10k"])
           seg_id elite full
        0     A1     n    y
        2     B1     n    y
    """
    if len(event_names) == 0:
        return pd.DataFrame(columns=segments_df.columns)
    
    # Build mask: segment is included if ANY event in group uses it
    mask = pd.Series([False] * len(segments_df), index=segments_df.index)
    
    for event_name in event_names:
        event_name_lower = event_name.lower()
        
        # Check if event flag column exists
        if event_name_lower not in segments_df.columns:
            logger.debug(f"Event flag column '{event_name_lower}' not found, skipping")
            continue
        
        # Add segments where this event flag is 'y'
        event_mask = segments_df[event_name_lower].str.lower().isin(['y', 'yes', 'true', '1'])
        mask = mask | event_mask
    
    return segments_df[mask].copy()


def calculate_res_from_metrics(
    avg_density: float,  # p/m²
    avg_rate: float,     # p/s
    avg_width_m: float,  # Distance-weighted average segment width
    density_threshold: float = RES_HIGH_DENSITY_THRESHOLD,
    flow_threshold: float = RES_HIGH_FLOW_THRESHOLD,  # runners/min/m
    flow_weight: float = RES_FLOW_PENALTY_WEIGHT,
    density_weight: float = RES_DENSITY_PENALTY_WEIGHT
) -> float:
    """
    Calculate RES score from aggregated density and flow metrics.
    
    Args:
        avg_density: Weighted average peak density (p/m²)
        avg_rate: Weighted average peak rate (p/s)
        avg_width_m: Distance-weighted average segment width (from segments.csv width_m column) for rate conversion
        density_threshold: High-density threshold (p/m²), defaults to RES_HIGH_DENSITY_THRESHOLD
        flow_threshold: High-flow threshold (runners/min/m), defaults to RES_HIGH_FLOW_THRESHOLD
        flow_weight: Flow penalty weight, defaults to RES_FLOW_PENALTY_WEIGHT
        density_weight: Density penalty weight, defaults to RES_DENSITY_PENALTY_WEIGHT
    
    Returns:
        float: RES score (0.0-5.0)
    """
    if avg_width_m <= 0:
        logger.warning(f"Invalid avg_width_m ({avg_width_m}), using default width for rate conversion")
        avg_width_m = 1.0  # Fallback to avoid division by zero
    
    # Convert rate from p/s to runners/min/m
    rate_per_m_per_min = (avg_rate / avg_width_m) * SECONDS_PER_MINUTE
    
    # Calculate penalty ratios (0.0-1.0)
    # Penalty increases linearly above threshold
    density_penalty = (
        max(0.0, (avg_density - density_threshold) / density_threshold)
        if avg_density > density_threshold else 0.0
    )
    
    flow_penalty = (
        max(0.0, (rate_per_m_per_min - flow_threshold) / flow_threshold)
        if rate_per_m_per_min > flow_threshold else 0.0
    )
    
    # Calculate RES: start at 5.0, subtract weighted penalties
    res = 5.0 - (flow_weight * flow_penalty) - (density_weight * density_penalty)
    
    # Clamp to [0.0, 5.0]
    return max(0.0, min(5.0, res))


def _get_participant_count(
    event_name: str,
    analysis_config: Dict[str, Any]
) -> int:
    """
    Get participant count for an event from analysis.json.
    
    Args:
        event_name: Event name (lowercase)
        analysis_config: Analysis configuration dictionary from analysis.json
        
    Returns:
        int: Participant count for the event (0 if not found)
    """
    event_name_lower = event_name.lower()
    events = analysis_config.get("events", [])
    
    for event in events:
        if event.get("name", "").lower() == event_name_lower:
            return event.get("runners", 0)
    
    logger.warning(f"Event '{event_name}' not found in analysis_config, using 0 participants")
    return 0


def _get_event_distance_range_from_segment(
    segment: pd.Series,
    event_name: str
) -> tuple[float, float]:
    """
    Extract distance range for an event from a segment Series.
    
    Helper function that directly accesses segment columns (similar to get_event_distance_range_v2
    but works with event name string instead of Event object).
    
    Args:
        segment: Segment data row as pandas Series
        event_name: Event name (lowercase)
        
    Returns:
        Tuple of (from_km, to_km) for the event, or (0.0, 0.0) if not found
    """
    event_name_lower = event_name.lower()
    from_key = f"{event_name_lower}_from_km"
    to_key = f"{event_name_lower}_to_km"
    
    # Case-insensitive column matching
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
                return (0.0, 0.0)
    
    return (0.0, 0.0)


def calculate_res_per_event_group(
    event_group_id: str,
    event_names: List[str],
    segment_metrics: Dict[str, Dict[str, Any]],
    segments_df: pd.DataFrame,
    analysis_config: Dict[str, Any]
) -> float:
    """
    Calculate RES score per event group.
    
    Main function for calculating RES per event group. Implements:
    - Distance-weighted aggregation per event
    - Participant-weighted aggregation for multi-event groups
    
    Args:
        event_group_id: Event group identifier (e.g., "sat/elite", "sun/all")
        event_names: List of event names in the group (e.g., ["elite"] or ["full", "10k", "half"])
        segment_metrics: Dictionary mapping seg_id to metrics dict with "peak_density" and "peak_rate"
        segments_df: Segments DataFrame from segments.csv
        analysis_config: Analysis configuration dictionary from analysis.json
        
    Returns:
        float: RES score for the event group (0.0-5.0)
    """
    if len(event_names) == 0:
        logger.warning(f"Empty event list for group '{event_group_id}', returning 0.0")
        return 0.0
    
    # Calculate RES per event (distance-weighted aggregation)
    event_res_scores = {}
    
    for event_name in event_names:
        event_name_lower = event_name.lower()
        
        # Filter segments used by this event
        event_flag_col = event_name_lower
        if event_flag_col not in segments_df.columns:
            logger.warning(f"Event flag column '{event_flag_col}' not found for event '{event_name}' in group '{event_group_id}'")
            event_res_scores[event_name] = 0.0
            continue
        
        event_segments = segments_df[
            segments_df[event_flag_col].str.lower().isin(['y', 'yes', 'true', '1'])
        ]
        
        if len(event_segments) == 0:
            logger.warning(f"No segments found for event '{event_name}' in group '{event_group_id}'")
            event_res_scores[event_name] = 0.0
            continue
        
        # Calculate total event distance
        total_event_distance = calculate_event_total_distance(segments_df, event_name)
        if total_event_distance <= 0:
            logger.warning(f"Invalid total distance for event '{event_name}' in group '{event_group_id}'")
            event_res_scores[event_name] = 0.0
            continue
        
        # Distance-weighted aggregation
        weighted_density_sum = 0.0
        weighted_rate_sum = 0.0
        weighted_width_sum = 0.0
        total_weight = 0.0
        
        for _, segment_row in event_segments.iterrows():
            seg_id = segment_row.get("seg_id")
            if not seg_id or seg_id not in segment_metrics:
                continue  # Skip segments without metrics
            
            # Get segment distance for this event
            from_km, to_km = _get_event_distance_range_from_segment(segment_row, event_name)
            segment_length = to_km - from_km
            
            if segment_length <= 0:
                continue  # Skip segments with invalid distance ranges
            
            # Weight = segment_length / total_event_distance
            weight = segment_length / total_event_distance
            
            # Get segment metrics
            metrics = segment_metrics[seg_id]
            peak_density = metrics.get("peak_density", 0.0)
            peak_rate = metrics.get("peak_rate", 0.0)
            
            # Get width from segments.csv
            width_m = segment_row.get("width_m", 0.0)
            try:
                width_m = float(width_m)
            except (ValueError, TypeError):
                logger.debug(f"Invalid width_m for segment '{seg_id}', using 0.0")
                width_m = 0.0
            
            # Accumulate weighted metrics
            weighted_density_sum += peak_density * weight
            weighted_rate_sum += peak_rate * weight
            weighted_width_sum += width_m * weight
            total_weight += weight
        
        if total_weight <= 0:
            logger.warning(f"No valid weighted segments for event '{event_name}' in group '{event_group_id}'")
            event_res_scores[event_name] = 0.0
            continue
        
        # Calculate weighted averages
        avg_density = weighted_density_sum / total_weight
        avg_rate = weighted_rate_sum / total_weight
        avg_width_m = weighted_width_sum / total_weight
        
        # Calculate RES for this event
        event_res = calculate_res_from_metrics(
            avg_density=avg_density,
            avg_rate=avg_rate,
            avg_width_m=avg_width_m
        )
        event_res_scores[event_name] = event_res
        
        logger.debug(
            f"Event '{event_name}' in group '{event_group_id}': "
            f"RES={event_res:.2f}, avg_density={avg_density:.3f}, avg_rate={avg_rate:.3f}"
        )
    
    # Multi-event group aggregation: weight by participant count
    if len(event_res_scores) == 0:
        logger.warning(f"No valid RES scores calculated for group '{event_group_id}'")
        return 0.0
    
    if len(event_names) == 1:
        # Single event group: return the RES score directly
        return event_res_scores[event_names[0]]
    
    # Multi-event group: participant-weighted average
    participant_counts = {
        event_name: _get_participant_count(event_name, analysis_config)
        for event_name in event_names
    }
    
    total_participants = sum(participant_counts.values())
    if total_participants <= 0:
        logger.warning(f"Total participants is 0 for group '{event_group_id}', using unweighted average")
        # Fallback to unweighted average if no participants
        return sum(event_res_scores.values()) / len(event_res_scores)
    
    # Calculate participant weights
    group_res = sum(
        event_res_scores[event_name] * (participant_counts[event_name] / total_participants)
        for event_name in event_names
        if event_name in event_res_scores
    )
    
    logger.info(
        f"Group '{event_group_id}' RES: {group_res:.2f} "
        f"(events: {event_names}, participant-weighted)"
    )
    
    return group_res
