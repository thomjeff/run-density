"""
Temporal Flow Analysis Module

Handles temporal flow analysis for segments where overtaking or merging is possible.
Only processes segments with overtake_flag = 'y' from flow.csv.
Supports overtake, merge, and diverge flow types.

KEY CONCEPTS:
1. START TIMES: Must be offsets from midnight in minutes (e.g., 420 = 7:00 AM)
2. NORMALIZED DISTANCES: For segments with different absolute ranges (like F1), 
   we work in normalized space (0.0-1.0) to compare relative positions
3. CONVERGENCE vs OVERTAKE_FLAG: Segments with overtake_flag='y' don't necessarily 
   need to show convergence if there are no temporal overlaps due to timing differences
4. TRUE PASS DETECTION: Only counts actual directional overtaking, not just co-presence
5. INTERSECTION BOUNDARIES: For directional change detection, use intersection 
   boundaries (same segment) rather than individual event boundaries (different segments)
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Optional, Any, List, Tuple
import pandas as pd
import numpy as np
from .constants import (
    SECONDS_PER_MINUTE, SECONDS_PER_HOUR,
    DEFAULT_CONVERGENCE_STEP_KM, DEFAULT_MIN_OVERLAP_DURATION, 
    DEFAULT_CONFLICT_LENGTH_METERS, TEMPORAL_OVERLAP_TOLERANCE_SECONDS,
    METERS_PER_KM, PACE_SIMILAR_THRESHOLD, PACE_MODERATE_DIFFERENCE_THRESHOLD,
    TEMPORAL_BINNING_THRESHOLD_MINUTES, SPATIAL_BINNING_THRESHOLD_METERS,
    SUSPICIOUS_OVERTAKING_RATE_THRESHOLD,
    MIN_NORMALIZED_FRACTION, MAX_NORMALIZED_FRACTION,
    FRACTION_CLAMP_REASON_OUTSIDE_RANGE, FRACTION_CLAMP_REASON_NEGATIVE,
    FRACTION_CLAMP_REASON_EXCEEDS_ONE
)
from .utils import load_pace_csv, arrival_time_sec, load_segments_csv


def clamp_normalized_fraction(fraction: float, reason_prefix: str = "") -> Tuple[float, Optional[str]]:
    """
    Clamp a normalized fraction to [0, 1] range and return reason code if clamped.
    
    Args:
        fraction: The fraction to clamp
        reason_prefix: Optional prefix for reason code
        
    Returns:
        Tuple of (clamped_fraction, reason_code)
        - reason_code is None if no clamping was needed
        - reason_code indicates why clamping occurred
    """
    if fraction < MIN_NORMALIZED_FRACTION:
        clamped = MIN_NORMALIZED_FRACTION
        reason = f"{reason_prefix}{FRACTION_CLAMP_REASON_NEGATIVE}" if reason_prefix else FRACTION_CLAMP_REASON_NEGATIVE
        return clamped, reason
    elif fraction > MAX_NORMALIZED_FRACTION:
        clamped = MAX_NORMALIZED_FRACTION
        reason = f"{reason_prefix}{FRACTION_CLAMP_REASON_EXCEEDS_ONE}" if reason_prefix else FRACTION_CLAMP_REASON_EXCEEDS_ONE
        return clamped, reason
    else:
        return fraction, None


# Use shared utility function from utils module


# Use shared utility function from utils module


# Use shared utility function from utils module


def calculate_convergence_point(
    dfA: pd.DataFrame,
    dfB: pd.DataFrame,
    eventA: str,
    eventB: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    step_km: float = DEFAULT_CONVERGENCE_STEP_KM,
) -> Optional[float]:
    """
    Calculate convergence point using TRUE PASS DETECTION.
    
    This function detects when runners from one event actually pass runners
    from another event (directional overtaking), not just co-presence.
    
    A true pass occurs when:
    1. Runner A arrives at km_point at time T_A
    2. Runner B arrives at km_point at time T_B  
    3. |T_A - T_B| <= tolerance
    4. AND one runner was behind the other at from_km but ahead at to_km
    
    ALGORITHM APPROACH:
    - If events have absolute intersection (like L1): Use intersection-based approach
    - If events have no intersection (like F1): Use normalized approach with fine grid
    - Normalized approach maps relative positions (0.0-1.0) to absolute coordinates
      for pace calculations, then checks for temporal overlap
    
    Returns the kilometer mark where the first true pass occurs, or None.
    """
    # Import the true pass detection function from overlap module
    from .overlap import calculate_true_pass_detection, calculate_convergence_point as calculate_co_presence
    
    # Check if there's an intersection in absolute space first
    intersection_start = max(from_km_a, from_km_b)
    intersection_end = min(to_km_a, to_km_b)
    
    if intersection_start < intersection_end:
        # There is an intersection - use normal approach with true pass detection
        true_pass_result = calculate_true_pass_detection(
            dfA, dfB, eventA, eventB, start_times,
            intersection_start, intersection_end, step_km
        )
        
        # Also check for co-presence (temporal overlap without directional change)
        # This handles cases where events overlap in time but don't have directional overtaking
        co_presence_result = calculate_co_presence(
            dfA, dfB, eventA, eventB, start_times,
            intersection_start, intersection_end, step_km
        )
        
        # Return true pass result if available, otherwise co-presence result
        return true_pass_result if true_pass_result is not None else co_presence_result
    
    # No intersection in absolute space - need normalized approach for segments like F1
    # NORMALIZED DISTANCE APPROACH: For segments with different absolute ranges but same
    # relative positions (e.g., F1: Full 16.35-18.65km, Half 2.7-5.0km, 10K 5.8-8.1km),
    # we work in normalized space (0.0-1.0) to compare relative positions within each segment.
    # Calculate segment lengths
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    
    if len_a <= 0 or len_b <= 0:
        return None
    
    # For segments with different ranges, we need to find where runners from different events
    # are at the same relative position within their respective segments.
    # We'll check multiple normalized positions and find where temporal overlap occurs.
    
    # Use a finer grid of normalized positions
    import numpy as np
    normalized_points = np.linspace(0.0, 1.0, 21)  # 0.0, 0.05, 0.1, ..., 1.0
    
    for norm_point in normalized_points:
        # Map normalized point to absolute coordinates for each event
        abs_km_a = from_km_a + (norm_point * len_a)
        abs_km_b = from_km_b + (norm_point * len_b)
        
        # Use the existing overlap detection functions with the mapped coordinates
        # We'll create a temporary "intersection" range around this point
        tolerance_km = 0.1  # 100m tolerance around the point
        range_start = abs_km_a - tolerance_km
        range_end = abs_km_a + tolerance_km
        
        # Try true pass detection at this normalized position
        true_pass_result = calculate_true_pass_detection(
            dfA, dfB, eventA, eventB, start_times,
            range_start, range_end, step_km
        )
        
        # Try co-presence detection at this normalized position
        co_presence_result = calculate_co_presence(
            dfA, dfB, eventA, eventB, start_times,
            range_start, range_end, step_km
        )
        
        # Return true pass result if available, otherwise co-presence result
        if true_pass_result is not None:
            return true_pass_result
        elif co_presence_result is not None:
            return co_presence_result
    
    # No convergence found in normalized space
    return None


def calculate_entry_exit_times(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
) -> Tuple[str, str, str, str, str]:
    """Calculate first entry and last exit times for both events in the segment, plus overlap window duration."""
    if df_a.empty or df_b.empty:
        return "N/A", "N/A", "N/A", "N/A", "N/A"
    
    # Get start times in seconds
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate entry/exit times for event A
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    entry_times_a = start_a + offset_a + pace_a * from_km_a
    exit_times_a = start_a + offset_a + pace_a * to_km_a
    
    # Calculate entry/exit times for event B
    pace_b = df_b["pace"].values * 60.0  # sec per km
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    entry_times_b = start_b + offset_b + pace_b * from_km_b
    exit_times_b = start_b + offset_b + pace_b * to_km_b
    
    # Find first entry and last exit for each event
    first_entry_a = min(entry_times_a)
    last_exit_a = max(exit_times_a)
    first_entry_b = min(entry_times_b)
    last_exit_b = max(exit_times_b)
    
    # Calculate overlap window duration (time when both events have runners in segment)
    overlap_start = max(first_entry_a, first_entry_b)
    overlap_end = min(last_exit_a, last_exit_b)
    overlap_duration_seconds = max(0, overlap_end - overlap_start)
    
    # Format as HH:MM:SS
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    # Format duration as MM:SS or HH:MM:SS
    def format_duration(seconds):
        if seconds < 3600:  # Less than 1 hour
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1 hour or more
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    return (
        format_time(first_entry_a),
        format_time(last_exit_a),
        format_time(first_entry_b),
        format_time(last_exit_b),
        format_duration(overlap_duration_seconds)
    )


def calculate_convergence_zone_overlaps_with_binning(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
    overlap_duration_minutes: float = 0.0,
) -> Tuple[int, int, List[str], List[str], int, int]:
    """
    Calculate overtaking with binning for long segments.
    Uses time bins if overlap > 10 minutes, distance bins if conflict zone > 100m.
    """
    
    # Check if binning is needed
    use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
    use_distance_bins = conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
    
    if use_time_bins or use_distance_bins:
        # Log binning decision for transparency
        logging.info(f"BINNING APPLIED: time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                    f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
        
        return calculate_convergence_zone_overlaps_binned(
            df_a, df_b, event_a, event_b, start_times,
            cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
            min_overlap_duration, conflict_length_m,
            use_time_bins, use_distance_bins, overlap_duration_minutes
        )
    else:
        # Use original method for short segments
        logging.debug(f"BINNING NOT APPLIED: time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                     f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
        
        return calculate_convergence_zone_overlaps_original(
            df_a, df_b, event_a, event_b, start_times,
            cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
            min_overlap_duration, conflict_length_m
        )


def validate_per_runner_entry_exit_f1(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = 200.0,
) -> Dict[str, Any]:
    """
    PER-RUNNER ENTRY/EXIT VALIDATION for F1 Half vs 10K segment.
    
    This function calculates entry and exit times for ALL runners in each event
    to validate overtaking counts and percentages for the F1 segment.
    
    Returns detailed validation results including:
    - Entry/exit times for all runners
    - Actual temporal overlaps
    - Validated overtaking counts
    - Reason codes for any discrepancies
    """
    import logging
    
    if df_a.empty or df_b.empty:
        return {"error": "Empty dataframes provided"}
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0  # Convert to seconds
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate conflict zone boundaries (using segment centers for F1)
    center_a = (from_km_a + to_km_a) / 2.0
    center_b = (from_km_b + to_km_b) / 2.0
    conflict_half_km = (conflict_length_m / 1000.0) / 2.0
    
    cp_km_a_start = max(from_km_a, center_a - conflict_half_km)
    cp_km_a_end = min(to_km_a, center_a + conflict_half_km)
    cp_km_b_start = max(from_km_b, center_b - conflict_half_km)
    cp_km_b_end = min(to_km_b, center_b + conflict_half_km)
    
    # Calculate entry/exit times for ALL runners in Event A
    a_entry_times = []
    a_exit_times = []
    a_runner_ids = []
    
    for idx, row in df_a.iterrows():
        pace_a = row["pace"] * 60.0  # sec per km
        offset_a = row.get("start_offset", 0)
        runner_id = row["runner_id"]
        
        entry_time = start_a + offset_a + pace_a * cp_km_a_start
        exit_time = start_a + offset_a + pace_a * cp_km_a_end
        
        a_entry_times.append(entry_time)
        a_exit_times.append(exit_time)
        a_runner_ids.append(runner_id)
    
    # Calculate entry/exit times for ALL runners in Event B
    b_entry_times = []
    b_exit_times = []
    b_runner_ids = []
    
    for idx, row in df_b.iterrows():
        pace_b = row["pace"] * 60.0  # sec per km
        offset_b = row.get("start_offset", 0)
        runner_id = row["runner_id"]
        
        entry_time = start_b + offset_b + pace_b * cp_km_b_start
        exit_time = start_b + offset_b + pace_b * cp_km_b_end
        
        b_entry_times.append(entry_time)
        b_exit_times.append(exit_time)
        b_runner_ids.append(runner_id)
    
    # Find temporal overlaps and validate overtaking
    a_overtakes = set()
    b_overtakes = set()
    a_copresence = set()
    b_copresence = set()
    
    overlap_pairs = []
    
    for i, (a_entry, a_exit, a_id) in enumerate(zip(a_entry_times, a_exit_times, a_runner_ids)):
        for j, (b_entry, b_exit, b_id) in enumerate(zip(b_entry_times, b_exit_times, b_runner_ids)):
            # Check for temporal overlap
            overlap_start = max(a_entry, b_entry)
            overlap_end = min(a_exit, b_exit)
            overlap_duration = overlap_end - overlap_start
            
            if overlap_duration > 0:  # Any temporal overlap
                a_copresence.add(a_id)
                b_copresence.add(b_id)
                
                # For F1, we need to check if there's actual directional change
                # Since segments don't intersect, we need to validate if overtaking makes sense
                
                # Check if runner A passes runner B (A starts behind B, finishes ahead of B)
                a_passes_b = (a_entry > b_entry and a_exit < b_exit)
                # Check if runner B passes runner A (B starts behind A, finishes ahead of A)
                b_passes_a = (b_entry > a_entry and b_exit < a_exit)
                
                if a_passes_b or b_passes_a:
                    a_overtakes.add(a_id)
                    b_overtakes.add(b_id)
                
                overlap_pairs.append({
                    "a_id": a_id,
                    "b_id": b_id,
                    "a_entry": a_entry,
                    "a_exit": a_exit,
                    "b_entry": b_entry,
                    "b_exit": b_exit,
                    "overlap_duration": overlap_duration,
                    "a_passes_b": a_passes_b,
                    "b_passes_a": b_passes_a
                })
    
    # Calculate validation results
    total_a = len(df_a)
    total_b = len(df_b)
    overtakes_a = len(a_overtakes)
    overtakes_b = len(b_overtakes)
    copresence_a = len(a_copresence)
    copresence_b = len(b_copresence)
    
    pct_a = (overtakes_a / total_a * 100) if total_a > 0 else 0.0
    pct_b = (overtakes_b / total_b * 100) if total_b > 0 else 0.0
    
    # Log validation results
    logging.info(f"F1 {event_a} vs {event_b} PER-RUNNER VALIDATION:")
    logging.info(f"  Total {event_a}: {total_a}, Overtaking: {overtakes_a} ({pct_a:.1f}%)")
    logging.info(f"  Total {event_b}: {total_b}, Overtaking: {overtakes_b} ({pct_b:.1f}%)")
    logging.info(f"  Co-presence {event_a}: {copresence_a}, {event_b}: {copresence_b}")
    logging.info(f"  Overlap pairs: {len(overlap_pairs)}")
    
    return {
        "total_a": total_a,
        "total_b": total_b,
        "overtakes_a": overtakes_a,
        "overtakes_b": overtakes_b,
        "copresence_a": copresence_a,
        "copresence_b": copresence_b,
        "pct_a": pct_a,
        "pct_b": pct_b,
        "overlap_pairs": overlap_pairs[:10],  # First 10 for debugging
        "conflict_zone_a": (cp_km_a_start, cp_km_a_end),
        "conflict_zone_b": (cp_km_b_start, cp_km_b_end),
        "validation_timestamp": time.time()
    }


def calculate_convergence_zone_overlaps_original(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """
    Calculate the number of overlapping runners within the convergence zone,
    projecting both events onto a common segment-local axis.
    
    CRITICAL: Returns SEPARATE counts for true passes vs co-presence.
    - True passes: runners who actually overtake each other directionally
    - Co-presence: runners who overlap temporally without directional change
    - Checks BOTH temporal overlap AND directional change
    - Uses intersection boundaries for fair directional comparison
    
    PROPORTIONAL TOLERANCE: Uses 5% of shorter segment length, minimum 50m
    to ensure consistent behavior across different segment sizes.
    
    Returns:
        Tuple of (overtakes_a, overtakes_b, copresence_a, copresence_b, 
                 sample_a, sample_b, unique_encounters, participants_involved)
    """
    if df_a.empty or df_b.empty:
        return 0, 0, 0, 0, [], [], 0, 0
    
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return 0, 0, 0, 0, [], [], 0, 0

    # Check if convergence point is within Event A's range (absolute approach)
    # or if we need to use normalized approach (for segments like F1)
    if from_km_a <= cp_km <= to_km_a:
        # Convergence point is within Event A's range - use absolute approach
        s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
        s_cp, clamp_reason = clamp_normalized_fraction(s_cp, "convergence_point_")
        
        # Calculate conflict zone in normalized space
        conflict_length_km = conflict_length_m / 1000.0  # Convert meters to km
        conflict_half_km = conflict_length_km / 2.0
        
        # Convert conflict zone to normalized fractions
        # Use proportional tolerance: 5% of shorter segment, minimum 50m
        min_segment_len = min(len_a, len_b)
        proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)  # 5% of shorter segment, min 50m
        s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
        
        # Define normalized conflict zone boundaries
        s_start = max(0.0, s_cp - s_conflict_half)
        s_end = min(1.0, s_cp + s_conflict_half)
        
        # Ensure conflict zone has some width
        if s_end <= s_start:
            s_start = max(0.0, s_cp - 0.05)  # 5% of segment
            s_end = min(1.0, s_cp + 0.05)    # 5% of segment
        
        # Convert normalized conflict zone to each event's absolute coordinates
        cp_km_a_start = from_km_a + s_start * len_a
        cp_km_a_end = from_km_a + s_end * len_a
        
        cp_km_b_start = from_km_b + s_start * len_b
        cp_km_b_end = from_km_b + s_end * len_b
    else:
        # Convergence point is outside Event A's range - use normalized approach
        # This handles cases where convergence was detected in normalized space
        # but the point doesn't map to Event A's absolute coordinates
        
        # Use the intersection boundaries if they exist, otherwise use proportional zones
        intersection_start = max(from_km_a, from_km_b)
        intersection_end = min(to_km_a, to_km_b)
        
        if intersection_start < intersection_end:
            # There is an intersection - use it for conflict zone
            conflict_length_km = conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0
            
            cp_km_a_start = max(from_km_a, intersection_start - conflict_half_km)
            cp_km_a_end = min(to_km_a, intersection_end + conflict_half_km)
            
            cp_km_b_start = max(from_km_b, intersection_start - conflict_half_km)
            cp_km_b_end = min(to_km_b, intersection_end + conflict_half_km)
        else:
            # No intersection - use proportional zones around segment centers
            center_a = (from_km_a + to_km_a) / 2.0
            center_b = (from_km_b + to_km_b) / 2.0
            
            conflict_length_km = conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0
            
            cp_km_a_start = max(from_km_a, center_a - conflict_half_km)
            cp_km_a_end = min(to_km_a, center_a + conflict_half_km)
            
            cp_km_b_start = max(from_km_b, center_b - conflict_half_km)
            cp_km_b_end = min(to_km_b, center_b + conflict_half_km)

    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0

    # Reset index to prevent iloc[i] mismatch after DataFrame filtering
    df_a = df_a.reset_index(drop=True)
    df_b = df_b.reset_index(drop=True)
    
    # Vectorized times for conflict zone
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    time_enter_a = start_a + offset_a + pace_a * cp_km_a_start
    time_exit_a  = start_a + offset_a + pace_a * cp_km_a_end

    pace_b = df_b["pace"].values * 60.0
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    time_enter_b = start_b + offset_b + pace_b * cp_km_b_start
    time_exit_b  = start_b + offset_b + pace_b * cp_km_b_end

    # Track runners who overtake each other (true passes)
    a_bibs_overtakes = set()
    b_bibs_overtakes = set()
    # Track runners who have temporal overlap (co-presence)
    a_bibs_copresence = set()
    b_bibs_copresence = set()
    unique_pairs = set()

    # TRUE PASS DETECTION: Check for temporal overlap AND directional change
    # This ensures we only count actual overtaking, not just co-presence
    for i, (enter_a, exit_a) in enumerate(zip(time_enter_a, time_exit_a)):
        for j, (enter_b, exit_b) in enumerate(zip(time_enter_b, time_exit_b)):
            overlap_start = max(enter_a, enter_b)
            overlap_end = min(exit_a, exit_b)
            overlap_duration = overlap_end - overlap_start
            
            if overlap_duration >= min_overlap_duration:
                # Temporal overlap detected - now check for directional change
                # Calculate arrival times at boundaries to detect passing
                # Use intersection boundaries if available, otherwise use conflict zone boundaries
                intersection_start = max(from_km_a, from_km_b)
                intersection_end = min(to_km_a, to_km_b)
                
                if intersection_start < intersection_end:
                    # Use intersection boundaries for fair comparison
                    boundary_start = intersection_start
                    boundary_end = intersection_end
                else:
                    # No intersection - use NORMALIZED CONFLICT ZONE for finish line convergence
                    # This handles cases like M1 where runners converge at the same physical location
                    # but have different absolute kilometer ranges
                    
                    # CORRECT APPROACH: 
                    # 1. Normalize each event's segment to 0.0-segment_length first
                    # 2. Calculate conflict zone in normalized space (e.g., 0.0-0.05 km for M1)
                    # 3. Compare runners at the same normalized position within their segments
                    
                    # Calculate conflict zone in NORMALIZED space (0.0 to segment_length)
                    # Use a fixed normalized conflict zone that works for both events
                    # For M1: segment_length = 0.25 km, so conflict zone should be 0.0-0.05 km
                    segment_length_a = to_km_a - from_km_a
                    segment_length_b = to_km_b - from_km_b
                    
                    # Use a small conflict zone (e.g., 20% of the shorter segment length)
                    conflict_zone_length = min(segment_length_a, segment_length_b) * 0.2
                    conflict_zone_norm_start = 0.0  # Start of conflict zone
                    conflict_zone_norm_end = conflict_zone_length  # End of conflict zone
                    
                    # Map normalized conflict zone to absolute coordinates for each event
                    abs_start_a = from_km_a + conflict_zone_norm_start
                    abs_end_a = from_km_a + conflict_zone_norm_end
                    abs_start_b = from_km_b + conflict_zone_norm_start
                    abs_end_b = from_km_b + conflict_zone_norm_end
                    
                    # Use the normalized conflict zone boundaries for directional change detection
                    # This ensures we're comparing runners at the same relative position within their segments
                    boundary_start = conflict_zone_norm_start  # Normalized start position (0.0)
                    boundary_end = conflict_zone_norm_end      # Normalized end position (0.05 for M1)
                
                pace_a = df_a.iloc[i]["pace"] * 60.0
                offset_a = df_a.iloc[i].get("start_offset", 0)
                pace_b = df_b.iloc[j]["pace"] * 60.0
                offset_b = df_b.iloc[j].get("start_offset", 0)
                
                if intersection_start < intersection_end:
                    # Use absolute coordinates for intersection-based segments
                    start_time_a = start_a + offset_a + pace_a * boundary_start
                    end_time_a = start_a + offset_a + pace_a * boundary_end
                    start_time_b = start_b + offset_b + pace_b * boundary_start
                    end_time_b = start_b + offset_b + pace_b * boundary_end
                else:
                    # Use NORMALIZED CONFLICT ZONE for finish line convergence
                    # Map normalized conflict zone boundaries to absolute coordinates for each event
                    # boundary_start = 0.0 (start of conflict zone)
                    # boundary_end = conflict_zone_length (end of conflict zone)
                    
                    # Map normalized conflict zone boundaries to absolute coordinates
                    abs_start_a = from_km_a + boundary_start  # from_km_a + 0.0
                    abs_end_a = from_km_a + boundary_end      # from_km_a + conflict_zone_length
                    abs_start_b = from_km_b + boundary_start  # from_km_b + 0.0
                    abs_end_b = from_km_b + boundary_end      # from_km_b + conflict_zone_length
                    
                    # Calculate arrival times at the conflict zone boundaries
                    start_time_a = start_a + offset_a + pace_a * abs_start_a
                    end_time_a = start_a + offset_a + pace_a * abs_end_a
                    start_time_b = start_b + offset_b + pace_b * abs_start_b
                    end_time_b = start_b + offset_b + pace_b * abs_end_b
                
                # Check for directional pass (true overtaking)
                # Runner A passes Runner B if A starts behind B but finishes ahead of B
                a_passes_b = (start_time_a > start_time_b and end_time_a < end_time_b)
                # Runner B passes Runner A if B starts behind A but finishes ahead of A
                b_passes_a = (start_time_b > start_time_a and end_time_b < end_time_a)
                
                # Check for temporal overlap (co-presence)
                temporal_overlap = (start_time_a < end_time_b and start_time_b < end_time_a)
                
                if temporal_overlap:
                    a_bib = df_a.iloc[i]["runner_id"]
                    b_bib = df_b.iloc[j]["runner_id"]
                    
                    # Always count co-presence
                    a_bibs_copresence.add(a_bib)
                    b_bibs_copresence.add(b_bib)
                    
                    # Count as true pass only if directional change occurs
                    if a_passes_b or b_passes_a:
                        a_bibs_overtakes.add(a_bib)
                        b_bibs_overtakes.add(b_bib)
                        # Track unique pairs (ordered to avoid duplicates)
                        unique_pairs.add((a_bib, b_bib))

    # Calculate participants involved (union of all runners who had encounters)
    all_a_bibs = a_bibs_overtakes.union(a_bibs_copresence)
    all_b_bibs = b_bibs_overtakes.union(b_bibs_copresence)
    participants_involved = len(all_a_bibs.union(all_b_bibs))
    unique_encounters = len(unique_pairs)

    # Return separate counts for true passes vs co-presence
    return (len(a_bibs_overtakes), len(b_bibs_overtakes), 
            len(a_bibs_copresence), len(b_bibs_copresence),
            list(a_bibs_overtakes), list(b_bibs_overtakes), 
            unique_encounters, participants_involved)


def calculate_convergence_zone_overlaps_binned(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
    use_time_bins: bool = False,
    use_distance_bins: bool = False,
    overlap_duration_minutes: float = 0.0,
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """
    Calculate overtaking using binning for long segments.
    """
    if df_a.empty or df_b.empty:
        return 0, 0, 0, 0, [], [], 0, 0
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Track runners who overtake each other (true passes)
    a_bibs_overtakes = set()
    b_bibs_overtakes = set()
    # Track runners who have temporal overlap (co-presence)
    a_bibs_copresence = set()
    b_bibs_copresence = set()
    unique_pairs = set()
    
    if use_time_bins:
        # Create time bins (10-minute intervals)
        bin_duration_minutes = 10.0
        num_bins = max(1, int(overlap_duration_minutes / bin_duration_minutes))
        
        # Calculate overlap window
        df_a['entry_time'] = start_a + df_a['start_offset'] + df_a['pace'] * 60.0 * from_km_a
        df_a['exit_time'] = start_a + df_a['start_offset'] + df_a['pace'] * 60.0 * to_km_a
        df_b['entry_time'] = start_b + df_b['start_offset'] + df_b['pace'] * 60.0 * from_km_b
        df_b['exit_time'] = start_b + df_b['start_offset'] + df_b['pace'] * 60.0 * to_km_b
        
        overlap_start = max(df_a['entry_time'].min(), df_b['entry_time'].min())
        overlap_end = min(df_a['exit_time'].max(), df_b['exit_time'].max())
        
        for bin_idx in range(num_bins):
            bin_start = overlap_start + (bin_idx * bin_duration_minutes * 60)
            bin_end = min(overlap_start + ((bin_idx + 1) * bin_duration_minutes * 60), overlap_end)
            
            # Get runners active in this time bin
            a_in_bin = df_a[(df_a['entry_time'] <= bin_end) & (df_a['exit_time'] >= bin_start)]
            b_in_bin = df_b[(df_b['entry_time'] <= bin_end) & (df_b['exit_time'] >= bin_start)]
            
            # Calculate overtaking for this time bin using original method
            bin_overtakes_a, bin_overtakes_b, bin_copresence_a, bin_copresence_b, bin_bibs_a, bin_bibs_b, bin_encounters, bin_participants = calculate_convergence_zone_overlaps_original(
                a_in_bin, b_in_bin, event_a, event_b, start_times,
                cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
                min_overlap_duration, conflict_length_m
            )
            
            # Accumulate results
            a_bibs_overtakes.update(bin_bibs_a)
            b_bibs_overtakes.update(bin_bibs_b)
            a_bibs_copresence.update(bin_bibs_a)  # Co-presence includes all temporal overlaps
            b_bibs_copresence.update(bin_bibs_b)
            unique_pairs.update([(a, b) for a in bin_bibs_a for b in bin_bibs_b])
    
    elif use_distance_bins:
        # Create distance bins (100m intervals)
        bin_size_km = 0.1  # 100m
        len_a = to_km_a - from_km_a
        len_b = to_km_b - from_km_b
        num_bins = max(1, int(min(len_a, len_b) / bin_size_km))
        
        for bin_idx in range(num_bins):
            bin_start_a = from_km_a + (bin_idx * bin_size_km)
            bin_end_a = min(from_km_a + ((bin_idx + 1) * bin_size_km), to_km_a)
            bin_start_b = from_km_b + (bin_idx * bin_size_km)
            bin_end_b = min(from_km_b + ((bin_idx + 1) * bin_size_km), to_km_b)
            
            # Calculate overtaking for this distance bin
            bin_overtakes_a, bin_overtakes_b, bin_copresence_a, bin_copresence_b, bin_bibs_a, bin_bibs_b, bin_encounters, bin_participants = calculate_convergence_zone_overlaps_original(
                df_a, df_b, event_a, event_b, start_times,
                cp_km, bin_start_a, bin_end_a, bin_start_b, bin_end_b,
                min_overlap_duration, conflict_length_m
            )
            
            # Accumulate results
            a_bibs_overtakes.update(bin_bibs_a)
            b_bibs_overtakes.update(bin_bibs_b)
            a_bibs_copresence.update(bin_bibs_a)  # Co-presence includes all temporal overlaps
            b_bibs_copresence.update(bin_bibs_b)
            unique_pairs.update([(a, b) for a in bin_bibs_a for b in bin_bibs_b])
    
    # Calculate final results
    all_a_bibs = a_bibs_overtakes.union(a_bibs_copresence)
    all_b_bibs = b_bibs_overtakes.union(b_bibs_copresence)
    participants_involved = len(all_a_bibs.union(all_b_bibs))
    unique_encounters = len(unique_pairs)
    
    # Return separate counts for true passes vs co-presence
    return (len(a_bibs_overtakes), len(b_bibs_overtakes), 
            len(a_bibs_copresence), len(b_bibs_copresence),
            list(a_bibs_overtakes), list(b_bibs_overtakes), 
            unique_encounters, participants_involved)


def format_bib_range(bib_list: List[str], max_individual: int = 3) -> str:
    """Format a list of runner IDs for display."""
    if not bib_list:
        return "None"
    
    if len(bib_list) <= max_individual:
        return ", ".join(map(str, bib_list))
    
    # For large lists, show first few and count
    sorted_bibs = sorted(bib_list, key=lambda x: int(x) if str(x).isdigit() else x)
    first_few = sorted_bibs[:max_individual]
    return f"{', '.join(map(str, first_few))}, ... ({len(bib_list)} total)"


def generate_deep_dive_analysis(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    segment_label: str,
    flow_type: str = "overtake",
    prior_segment_id: str = None,
    prior_segment_data: Dict[str, Any] = None,
    current_segment_data: Dict[str, Any] = None,
) -> List[str]:
    """Generate comprehensive deep dive analysis for a segment."""
    if df_a.empty or df_b.empty:
        return ["❌ Deep Dive: No data available for analysis"]
    
    analysis = []
    analysis.append("🔍 DEEP DIVE ANALYSIS")
    analysis.append("=" * 40)
    
    # Basic segment information
    analysis.append(f"📍 Segment: {segment_label}")
    analysis.append(f"🔄 Flow Type: {flow_type}")
    analysis.append(f"🔍 Events: {event_a} vs {event_b}")
    analysis.append("")
    
    # Entry/exit times (already calculated)
    first_entry_a, last_exit_a, first_entry_b, last_exit_b, overlap_duration = calculate_entry_exit_times(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b
    )
    
    analysis.append("⏰ TIMING ANALYSIS:")
    analysis.append(f"   • {event_a} Entry/Exit: {first_entry_a} {last_exit_a}")
    analysis.append(f"   • {event_b} Entry/Exit: {first_entry_b} {last_exit_b}")
    analysis.append(f"   • Overlap Window Duration: {overlap_duration}")
    analysis.append("")
    
    # Runner characteristics
    analysis.append("👥 RUNNER CHARACTERISTICS:")
    
    # Event A characteristics
    pace_a = df_a["pace"].values
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    analysis.append(f"   • {event_a} Runners: {len(df_a)} total")
    analysis.append(f"     - Pace Range: {pace_a.min():.2f} - {pace_a.max():.2f} min/km")
    analysis.append(f"     - Pace Median: {np.median(pace_a):.2f} min/km")
    analysis.append(f"     - Start Offset Range: {offset_a.min():.0f} - {offset_a.max():.0f} seconds")
    analysis.append(f"     - Start Offset Median: {np.median(offset_a):.0f} seconds")
    
    # Event B characteristics
    pace_b = df_b["pace"].values
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    analysis.append(f"   • {event_b} Runners: {len(df_b)} total")
    analysis.append(f"     - Pace Range: {pace_b.min():.2f} - {pace_b.max():.2f} min/km")
    analysis.append(f"     - Pace Median: {np.median(pace_b):.2f} min/km")
    analysis.append(f"     - Start Offset Range: {offset_b.min():.0f} - {offset_b.max():.0f} seconds")
    analysis.append(f"     - Start Offset Median: {np.median(offset_b):.0f} seconds")
    analysis.append("")
    
    # Start offset analysis
    analysis.append("🚀 START OFFSET ANALYSIS:")
    analysis.append(f"   • {event_a} Start Time: {start_times.get(event_a, 0):.0f} minutes")
    analysis.append(f"   • {event_b} Start Time: {start_times.get(event_b, 0):.0f} minutes")
    analysis.append(f"   • Start Time Difference: {abs(start_times.get(event_a, 0) - start_times.get(event_b, 0)):.0f} minutes")
    
    # Calculate effective start times (including offsets)
    start_a_sec = start_times.get(event_a, 0) * 60.0
    start_b_sec = start_times.get(event_b, 0) * 60.0
    effective_start_a = start_a_sec + np.median(offset_a)
    effective_start_b = start_b_sec + np.median(offset_b)
    analysis.append(f"   • Effective Start Difference: {abs(effective_start_a - effective_start_b)/60:.1f} minutes")
    analysis.append("")
    
    # Contextual narrative summary
    analysis.append("📝 CONTEXTUAL SUMMARY:")
    
    # Determine interaction potential based on timing and pace
    time_diff = abs(effective_start_a - effective_start_b) / 60.0  # minutes
    pace_diff = abs(np.median(pace_a) - np.median(pace_b))
    
    if time_diff < 5:
        analysis.append("   • High interaction potential: Events start within 5 minutes")
    elif time_diff < 15:
        analysis.append("   • Moderate interaction potential: Events start within 15 minutes")
    else:
        analysis.append("   • Low interaction potential: Events start >15 minutes apart")
    
    from .constants import (
        PACE_SIMILAR_THRESHOLD,
        PACE_MODERATE_DIFFERENCE_THRESHOLD
    )
    
    if pace_diff < PACE_SIMILAR_THRESHOLD:
        analysis.append("   • Similar pace groups: Runners likely to stay together")
    elif pace_diff < PACE_MODERATE_DIFFERENCE_THRESHOLD:
        analysis.append("   • Moderate pace difference: Some overtaking expected")
    else:
        analysis.append("   • Large pace difference: Significant overtaking expected")
    
    # Overlap window analysis
    if overlap_duration != "N/A" and overlap_duration != "00:00":
        analysis.append(f"   • Active overlap period: {overlap_duration} when both events are present")
    else:
        analysis.append("   • No temporal overlap: Events do not share time in segment")
    
    analysis.append("")
    
    # Prior segment overlap analysis
    if prior_segment_id and prior_segment_data:
        analysis.append("🔗 PRIOR SEGMENT OVERLAP ANALYSIS:")
        analysis.append(f"   • Prior Segment: {prior_segment_id}")
        
        # Compare current segment with prior segment
        current_overtaking_a = current_segment_data.get('overtaking_a', 0) if current_segment_data else 0
        current_overtaking_b = current_segment_data.get('overtaking_b', 0) if current_segment_data else 0
        prior_overtaking_a = prior_segment_data.get('overtaking_a', 0)
        prior_overtaking_b = prior_segment_data.get('overtaking_b', 0)
        
        analysis.append(f"   • Current Segment Overtaking: {event_a}={current_overtaking_a}, {event_b}={current_overtaking_b}")
        analysis.append(f"   • Prior Segment Overtaking: {event_a}={prior_overtaking_a}, {event_b}={prior_overtaking_b}")
        
        # Calculate overlap counts and unique runners
        current_unique_encounters = current_segment_data.get('unique_encounters', 0) if current_segment_data else 0
        current_participants = current_segment_data.get('participants_involved', 0) if current_segment_data else 0
        prior_unique_encounters = prior_segment_data.get('unique_encounters', 0)
        prior_participants = prior_segment_data.get('participants_involved', 0)
        
        analysis.append(f"   • Current Unique Encounters: {current_unique_encounters}")
        analysis.append(f"   • Prior Unique Encounters: {prior_unique_encounters}")
        analysis.append(f"   • Current Participants: {current_participants}")
        analysis.append(f"   • Prior Participants: {prior_participants}")
        
        # Interaction pattern analysis
        if current_unique_encounters > prior_unique_encounters:
            analysis.append("   • Interaction Pattern: Increasing encounters from prior segment")
        elif current_unique_encounters < prior_unique_encounters:
            analysis.append("   • Interaction Pattern: Decreasing encounters from prior segment")
        else:
            analysis.append("   • Interaction Pattern: Similar encounter levels to prior segment")
        
        analysis.append("")
    
    return analysis


def convert_segments_new_to_flow_format(segments_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert segments_new.csv wide format to flow.csv long format.
    This is a minimal conversion to support the new schema.
    """
    converted_segments = []
    
    for _, segment in segments_df.iterrows():
        seg_id = segment['seg_id']
        
        # Get events that are present (y)
        events = []
        if segment.get('full') == 'y':
            events.append('Full')
        if segment.get('half') == 'y':
            events.append('Half')
        if segment.get('10K') == 'y':
            events.append('10K')
        
        # Generate all possible event pairs
        for i, event_a in enumerate(events):
            for event_b in events[i+1:]:
                # Get distance ranges for each event
                if event_a == "Full":
                    from_km_a = segment.get("full_from_km", 0)
                    to_km_a = segment.get("full_to_km", 0)
                elif event_a == "Half":
                    from_km_a = segment.get("half_from_km", 0)
                    to_km_a = segment.get("half_to_km", 0)
                elif event_a == "10K":
                    from_km_a = segment.get("10K_from_km", 0)
                    to_km_a = segment.get("10K_to_km", 0)
                
                if event_b == "Full":
                    from_km_b = segment.get("full_from_km", 0)
                    to_km_b = segment.get("full_to_km", 0)
                elif event_b == "Half":
                    from_km_b = segment.get("half_from_km", 0)
                    to_km_b = segment.get("half_to_km", 0)
                elif event_b == "10K":
                    from_km_b = segment.get("10K_from_km", 0)
                    to_km_b = segment.get("10K_to_km", 0)
                
                # Create converted segment
                converted_segment = {
                    "seg_id": seg_id,
                    "segment_label": segment.get("seg_label", ""),
                    "eventa": event_a,
                    "eventb": event_b,
                    "from_km_a": from_km_a,
                    "to_km_a": to_km_a,
                    "from_km_b": from_km_b,
                    "to_km_b": to_km_b,
                    "direction": segment.get("direction", ""),
                    "width_m": segment.get("width_m", 0),
                    "overtake_flag": segment.get("overtake_flag", ""),
                    "flow_type": segment.get("flow_type", ""),
                    "prior_segment_id": segment.get("prior_segment_id", ""),
                    "notes": segment.get("notes", "")
                }
                converted_segments.append(converted_segment)
    
    return pd.DataFrame(converted_segments)


def analyze_temporal_flow_segments(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
) -> Dict[str, Any]:
    """
    Analyze all segments for temporal flow patterns.
    Supports overtake, merge, and diverge flow types.
    Processes ALL segments but only calculates convergence for overtake_flag = 'y' segments.
    
    START TIMES REQUIREMENT: start_times must be offsets from midnight in minutes.
    Example: {'10K': 420, 'Half': 440, 'Full': 460} means 10K starts at 7:00 AM,
    Half at 7:20 AM, Full at 7:40 AM.
    """
    # Load data
    pace_df = load_pace_csv(pace_csv)
    segments_df = load_segments_csv(segments_csv)
    
    # Check if this is segments_new.csv format and convert if needed
    if '10K' in segments_df.columns and 'full' in segments_df.columns:
        # This is the new format, convert to old format
        all_segments = convert_segments_new_to_flow_format(segments_df)
    else:
        # This is the old format, use as-is
        all_segments = segments_df.copy()
    
    results = {
        "ok": True,
        "engine": "temporal_flow",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_times": start_times,
        "min_overlap_duration": min_overlap_duration,
        "conflict_length_m": conflict_length_m,
        "temporal_binning_threshold_minutes": TEMPORAL_BINNING_THRESHOLD_MINUTES,
        "spatial_binning_threshold_meters": SPATIAL_BINNING_THRESHOLD_METERS,
        "total_segments": len(all_segments),
        "segments_with_convergence": 0,
        "segments": []
    }
    
    for _, segment in all_segments.iterrows():
        seg_id = segment["seg_id"]
        event_a = segment["eventa"]
        event_b = segment["eventb"]
        from_km_a = segment["from_km_a"]
        to_km_a = segment["to_km_a"]
        from_km_b = segment["from_km_b"]
        to_km_b = segment["to_km_b"]
        
        # Filter runners for this segment
        df_a = pace_df[pace_df["event"] == event_a].copy()
        df_b = pace_df[pace_df["event"] == event_b].copy()
        
        # Calculate convergence point (in event A km ruler) - only for overtake segments
        # NOTE: Segments with overtake_flag='y' don't necessarily need to show convergence
        # if there are no temporal overlaps due to timing differences (e.g., A1, B1)
        cp_km = None
        if segment.get("overtake_flag") == "y":
            cp_km = calculate_convergence_point(
                df_a, df_b, event_a, event_b, start_times,
                from_km_a, to_km_a, from_km_b, to_km_b
            )
        
        # Calculate entry/exit times for this segment
        first_entry_a, last_exit_a, first_entry_b, last_exit_b, overlap_window_duration = calculate_entry_exit_times(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b
        )
        
        segment_result = {
            "seg_id": seg_id,
            "segment_label": segment.get("segment_label", ""),
            "flow_type": segment.get("flow_type", ""),
            "event_a": event_a,
            "event_b": event_b,
            "from_km_a": from_km_a,
            "to_km_a": to_km_a,
            "from_km_b": from_km_b,
            "to_km_b": to_km_b,
            "convergence_point": cp_km,
            "has_convergence": cp_km is not None,
            "total_a": len(df_a),
            "total_b": len(df_b),
            "overtaking_a": 0,
            "overtaking_b": 0,
            "sample_a": [],
            "sample_b": [],
            "first_entry_a": first_entry_a,
            "last_exit_a": last_exit_a,
            "first_entry_b": first_entry_b,
            "last_exit_b": last_exit_b,
            "overlap_window_duration": overlap_window_duration,
            "prior_segment_id": segment.get("prior_segment_id", "") if pd.notna(segment.get("prior_segment_id", "")) else "",
            "overtake_flag": segment.get("overtake_flag", "")
        }
        
        if cp_km is not None and segment.get("overtake_flag") == "y":
            # Calculate overtaking runners in convergence zone using local-axis mapping
            # Calculate dynamic conflict length first
            from .constants import (
                CONFLICT_LENGTH_LONG_SEGMENT_M,
                CONFLICT_LENGTH_MEDIUM_SEGMENT_M, 
                CONFLICT_LENGTH_SHORT_SEGMENT_M,
                SEGMENT_LENGTH_LONG_THRESHOLD_KM,
                SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM
            )
            
            segment_length_km = to_km_a - from_km_a
            if segment_length_km > SEGMENT_LENGTH_LONG_THRESHOLD_KM:
                dynamic_conflict_length_m = CONFLICT_LENGTH_LONG_SEGMENT_M
            elif segment_length_km > SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM:
                dynamic_conflict_length_m = CONFLICT_LENGTH_MEDIUM_SEGMENT_M
            else:
                dynamic_conflict_length_m = CONFLICT_LENGTH_SHORT_SEGMENT_M
            
            # For segments with no intersection (like F1), use segment center instead of convergence point
            # The convergence point might be in a different coordinate system
            if from_km_a <= cp_km <= to_km_a:
                # Convergence point is within Event A's range - use it directly
                effective_cp_km = cp_km
            else:
                # Convergence point is outside Event A's range - use segment center
                # This handles segments with no intersection where convergence was detected in normalized space
                effective_cp_km = (from_km_a + to_km_a) / 2.0
            
            # Calculate overlap duration in minutes for binning decision
            # overlap_window_duration is a formatted string like "55:32", need to parse it
            if isinstance(overlap_window_duration, str) and ':' in overlap_window_duration:
                # Parse format like "55:32" or "1:23:45"
                parts = overlap_window_duration.split(':')
                if len(parts) == 2:  # MM:SS
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    overlap_duration_minutes = minutes + seconds / 60.0
                elif len(parts) == 3:  # HH:MM:SS
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    overlap_duration_minutes = hours * 60 + minutes + seconds / 60.0
                else:
                    overlap_duration_minutes = 0.0
            else:
                overlap_duration_minutes = overlap_window_duration / 60.0 if isinstance(overlap_window_duration, (int, float)) else 0.0
            
            overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps_with_binning(
                df_a, df_b, event_a, event_b, start_times,
                effective_cp_km, from_km_a, to_km_a, from_km_b, to_km_b, min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
            )
            
            # F1 Half vs 10K PER-RUNNER VALIDATION
            if seg_id == "F1" and event_a == "Half" and event_b == "10K":
                print(f"🔍 F1 Half vs 10K PER-RUNNER VALIDATION:")
                validation_results = validate_per_runner_entry_exit_f1(
                    df_a, df_b, event_a, event_b, start_times,
                    from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
                )
                
                # Compare validation results with current calculation
                val_overtakes_a = validation_results.get("overtakes_a", 0)
                val_overtakes_b = validation_results.get("overtakes_b", 0)
                val_pct_a = validation_results.get("pct_a", 0.0)
                val_pct_b = validation_results.get("pct_b", 0.0)
                
                print(f"  Current calculation: {overtakes_a} ({overtakes_a/len(df_a)*100:.1f}%), {overtakes_b} ({overtakes_b/len(df_b)*100:.1f}%)")
                print(f"  Validation results:  {val_overtakes_a} ({val_pct_a:.1f}%), {val_overtakes_b} ({val_pct_b:.1f}%)")
                
                # Check for discrepancies
                if abs(overtakes_a - val_overtakes_a) > 0 or abs(overtakes_b - val_overtakes_b) > 0:
                    print(f"  ⚠️  DISCREPANCY DETECTED! Using validation results.")
                    overtakes_a = val_overtakes_a
                    overtakes_b = val_overtakes_b
                    copresence_a = validation_results.get("copresence_a", 0)
                    copresence_b = validation_results.get("copresence_b", 0)
                else:
                    print(f"  ✅ Validation matches current calculation.")
            
            # Log binning decisions and warnings
            
            use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
            use_distance_bins = dynamic_conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
            
            if use_time_bins or use_distance_bins:
                print(f"🔧 BINNING APPLIED to {seg_id}: time_bins={use_time_bins}, distance_bins={use_distance_bins}")
                print(f"   Overlap: {overlap_duration_minutes:.1f}min, Conflict: {dynamic_conflict_length_m:.0f}m")
            
            # Flag suspicious overtaking rates (using true passes, not co-presence)
            pct_a = overtakes_a / len(df_a) if len(df_a) > 0 else 0
            pct_b = overtakes_b / len(df_b) if len(df_b) > 0 else 0
            
            if pct_a > SUSPICIOUS_OVERTAKING_RATE_THRESHOLD or pct_b > SUSPICIOUS_OVERTAKING_RATE_THRESHOLD:
                if not (use_time_bins or use_distance_bins):
                    print(f"⚠️  SUSPICIOUS OVERTAKING RATES in {seg_id}: {pct_a:.1%}, {pct_b:.1%} - NO BINNING APPLIED!")
                else:
                    print(f"✅ High overtaking rates in {seg_id}: {pct_a:.1%}, {pct_b:.1%} - BINNING APPLIED")
            
            # Calculate dynamic conflict zone boundaries using the same logic as calculate_convergence_zone_overlaps
            # This ensures consistency between overtaking count calculation and reporting
            len_a = to_km_a - from_km_a
            len_b = to_km_b - from_km_b
            
            if from_km_a <= cp_km <= to_km_a:
                # Convergence point is within Event A's range - use absolute approach
                s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
                s_cp, clamp_reason = clamp_normalized_fraction(s_cp, "convergence_point_")
                
                # Use proportional tolerance: 5% of shorter segment, minimum 50m
                min_segment_len = min(len_a, len_b)
                proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)
                s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
                
                # Define normalized conflict zone boundaries
                s_start = max(0.0, s_cp - s_conflict_half)
                s_end = min(1.0, s_cp + s_conflict_half)
                
                # Ensure conflict zone has some width
                if s_end <= s_start:
                    s_start = max(0.0, s_cp - 0.05)
                    s_end = min(1.0, s_cp + 0.05)
                
                # Store normalized values for convergence zone (0.0 to 1.0)
                conflict_start = s_start
                conflict_end = s_end
            else:
                # Convergence point is outside Event A's range - use normalized approach
                intersection_start = max(from_km_a, from_km_b)
                intersection_end = min(to_km_a, to_km_b)
                
                if intersection_start < intersection_end:
                    # Use intersection boundaries - normalize to segment
                    len_a = to_km_a - from_km_a
                    intersection_start_norm = (intersection_start - from_km_a) / len_a
                    intersection_end_norm = (intersection_end - from_km_a) / len_a
                    conflict_length_km = dynamic_conflict_length_m / 1000.0
                    conflict_half_km = conflict_length_km / 2.0 / len_a  # Normalize to segment length
                    conflict_start = max(0.0, intersection_start_norm - conflict_half_km)
                    conflict_end = min(1.0, intersection_end_norm + conflict_half_km)
                else:
                    # Use segment center - normalize to segment
                    len_a = to_km_a - from_km_a
                    center_a_norm = 0.5  # Center of normalized segment
                    conflict_length_km = dynamic_conflict_length_m / 1000.0
                    conflict_half_km = conflict_length_km / 2.0 / len_a  # Normalize to segment length
                    conflict_start = max(0.0, center_a_norm - conflict_half_km)
                    conflict_end = min(1.0, center_a_norm + conflict_half_km)
            
            # CRITICAL: Only set has_convergence=True if there are actual overtakes
            # If convergence is detected but no overtaking occurs, set has_convergence=False
            if overtakes_a == 0 and overtakes_b == 0:
                # No overtaking detected despite convergence - set has_convergence=False
                segment_result["has_convergence"] = False
                segment_result["convergence_point"] = None
                segment_result["convergence_point_fraction"] = None
            
            segment_result.update({
                "overtaking_a": overtakes_a,
                "overtaking_b": overtakes_b,
                "copresence_a": copresence_a,
                "copresence_b": copresence_b,
                "sample_a": bibs_a[:10],  # First 10 for samples
                "sample_b": bibs_b[:10],
                "convergence_zone_start": conflict_start,
                "convergence_zone_end": conflict_end,
                "conflict_length_m": dynamic_conflict_length_m,
                "unique_encounters": unique_encounters,
                "participants_involved": participants_involved
            })
            
            results["segments_with_convergence"] += 1
        
        results["segments"].append(segment_result)
    
    # Generate Deep Dive analysis for segments with overtake_flag = 'y' after all segments are processed
    for segment_result in results["segments"]:
        if segment_result.get("overtake_flag") == "y":
            # Find prior segment data if it exists
            prior_segment_id = segment_result.get("prior_segment_id")
            prior_segment_data = None
            if prior_segment_id:
                # Find the prior segment in the results
                for prev_segment in results["segments"]:
                    if prev_segment["seg_id"] == prior_segment_id:
                        prior_segment_data = prev_segment
                        break
            
            # Get the segment data from all_segments (converted format)
            seg_id = segment_result["seg_id"]
            segment_row = all_segments[all_segments["seg_id"] == seg_id].iloc[0]
            event_a = segment_row["eventa"]
            event_b = segment_row["eventb"]
            from_km_a = segment_row["from_km_a"]
            to_km_a = segment_row["to_km_a"]
            from_km_b = segment_row["from_km_b"]
            to_km_b = segment_row["to_km_b"]
            
            # Get the dataframes for this segment
            df_a = pace_df[pace_df["event"] == event_a].copy()
            df_b = pace_df[pace_df["event"] == event_b].copy()
            
            deep_dive = generate_deep_dive_analysis(
                df_a, df_b, event_a, event_b, start_times,
                from_km_a, to_km_a, from_km_b, to_km_b,
                segment_result.get("segment_label", seg_id),
                segment_result.get("flow_type", "overtake"),
                prior_segment_id,
                prior_segment_data,
                segment_result
            )
            segment_result["deep_dive_analysis"] = deep_dive
    
    return results


def generate_temporal_flow_narrative(results: Dict[str, Any]) -> str:
    """Generate human-readable narrative for temporal flow analysis."""
    if not results["ok"]:
        return "❌ Temporal flow analysis failed"
    
    narrative = []
    narrative.append("🎯 TEMPORAL FLOW ANALYSIS SUMMARY")
    narrative.append("=" * 50)
    narrative.append(f"🕐 Executed: {results['timestamp']}")
    narrative.append("")
    narrative.append("🚀 EVENT START TIMES:")
    for event, start_min in results["start_times"].items():
        hh = int(start_min // 60)
        mm = int(start_min % 60)
        narrative.append(f"   {event}: {hh:02d}:{mm:02d}:00")
    narrative.append("")
    narrative.append(f"📈 Total flow segments: {results['total_segments']}")
    narrative.append(f"🎯 Segments with convergence: {results['segments_with_convergence']}")
    narrative.append(f"⚙️ Analysis: {results['min_overlap_duration']}s min overlap duration")
    narrative.append(f"📏 Conflict length: {results['conflict_length_m']}m")
    narrative.append("")
    narrative.append("=" * 50)
    narrative.append("")
    
    for segment in results["segments"]:
        narrative.append(f"🏷️ Segment: {segment['seg_id']}")
        if segment.get("segment_label"):
            narrative.append(f"📝 Label: {segment['segment_label']}")
        if segment.get("flow_type"):
            narrative.append(f"🔄 Flow Type: {segment['flow_type']}")
        narrative.append(f"🔍 Checking {segment['event_a']} vs {segment['event_b']}")
        event_a = segment.get('event_a', 'A')
        event_b = segment.get('event_b', 'B')
        narrative.append(f"📍 {event_a}: {segment['total_a']} runners ({segment['from_km_a']}km to {segment['to_km_a']}km)")
        narrative.append(f"📍 {event_b}: {segment['total_b']} runners ({segment['from_km_b']}km to {segment['to_km_b']}km)")
        
        # Add entry/exit times in combined format
        narrative.append(f"⏰ {event_a} Entry/Exit: {segment.get('first_entry_a', 'N/A')} {segment.get('last_exit_a', 'N/A')}")
        narrative.append(f"⏰ {event_b} Entry/Exit: {segment.get('first_entry_b', 'N/A')} {segment.get('last_exit_b', 'N/A')}")
        narrative.append(f"🔄 Overlap Window Duration: {segment.get('overlap_window_duration', 'N/A')}")
        
        if segment["has_convergence"]:
            flow_type = segment.get("flow_type", "overtake")
            # Calculate event-specific distances for the convergence point
            cp_km = segment['convergence_point']
            from_km_a = segment.get('from_km_a', 0)
            to_km_a = segment.get('to_km_a', 0)
            from_km_b = segment.get('from_km_b', 0)
            to_km_b = segment.get('to_km_b', 0)
            
            # Calculate position within segment (0.0 to 1.0)
            len_a = to_km_a - from_km_a
            len_b = to_km_b - from_km_b
            s_cp = (cp_km - from_km_a) / max(len_a, 1e-9) if len_a > 0 else 0.0
            s_cp, clamp_reason = clamp_normalized_fraction(s_cp, "convergence_point_")
            
            # Calculate event B distance at convergence point
            cp_km_b = from_km_b + s_cp * len_b
            
            # Format: Convergence Point: fraction=[position within segment] (km=[total distance Event A], [total distance Event B])
            event_a = segment.get('event_a', 'A')
            event_b = segment.get('event_b', 'B')
            narrative.append(f"🎯 Convergence Point: fraction={s_cp:.2f} (A), km={cp_km:.1f} ({event_a}), {cp_km_b:.1f} ({event_b})")
            
            # Flow type specific reporting
            if flow_type == "merge":
                narrative.append(f"🔄 MERGE ANALYSIS:")
                narrative.append(f"   • {segment['event_a']} runners in merge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
                narrative.append(f"   • {segment['event_b']} runners in merge zone: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
                narrative.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
                narrative.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
            elif flow_type == "diverge":
                narrative.append(f"↗️ DIVERGE ANALYSIS:")
                narrative.append(f"   • {segment['event_a']} runners in diverge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
                narrative.append(f"   • {segment['event_b']} runners in diverge zone: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
                narrative.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
                narrative.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
            else:  # overtake (default)
                narrative.append(f"👥 OVERTAKE ANALYSIS:")
                narrative.append(f"   • {segment['event_a']} runners overtaking: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
                narrative.append(f"   • {segment['event_b']} runners overtaking: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
                narrative.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
                narrative.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
            
            narrative.append(f"🏃‍♂️ Sample {segment['event_a']}: {format_bib_range(segment['sample_a'])}")
            narrative.append(f"🏃‍♂️ Sample {segment['event_b']}: {format_bib_range(segment['sample_b'])}")
        else:
            narrative.append("❌ No convergence zone detected")
        
        # Add Deep Dive analysis for all segments with overtake_flag = 'y'
        if segment.get("deep_dive_analysis"):
            narrative.extend(segment["deep_dive_analysis"])
        
        narrative.append("")
    
    return "\n".join(narrative)


def analyze_distance_progression(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    step_km: float = 0.05,
) -> Dict[str, Any]:
    """
    Analyze runner distribution over distance within a segment.
    Returns distance bins with runner counts for each event.
    """
    if df_a.empty or df_b.empty:
        return {"ok": False, "error": "Empty dataframes"}
    
    # Calculate segment lengths
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return {"ok": False, "error": "Invalid segment lengths"}
    
    # Create distance bins
    min_km = min(from_km_a, from_km_b)
    max_km = max(to_km_a, to_km_b)
    distance_bins = []
    current_km = min_km
    while current_km <= max_km:
        distance_bins.append(round(current_km, 3))
        current_km += step_km
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate runner positions at each distance bin
    progression_data = []
    
    for bin_km in distance_bins:
        # Check if this distance is within each event's segment
        in_segment_a = from_km_a <= bin_km <= to_km_a
        in_segment_b = from_km_b <= bin_km <= to_km_b
        
        # Count runners from each event at this distance
        count_a = 0
        count_b = 0
        
        if in_segment_a and not df_a.empty:
            # Calculate arrival times for event A runners at this distance
            pace_a = df_a["pace"].values * 60.0  # sec per km
            offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
            arrival_times_a = start_a + offset_a + pace_a * bin_km
            count_a = len(arrival_times_a)
        
        if in_segment_b and not df_b.empty:
            # Calculate arrival times for event B runners at this distance
            pace_b = df_b["pace"].values * 60.0  # sec per km
            offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
            arrival_times_b = start_b + offset_b + pace_b * bin_km
            count_b = len(arrival_times_b)
        
        progression_data.append({
            "distance_km": bin_km,
            "count_a": count_a,
            "count_b": count_b,
            "total_count": count_a + count_b,
            "in_segment_a": in_segment_a,
            "in_segment_b": in_segment_b
        })
    
    return {
        "ok": True,
        "event_a": event_a,
        "event_b": event_b,
        "from_km_a": from_km_a,
        "to_km_a": to_km_a,
        "from_km_b": from_km_b,
        "to_km_b": to_km_b,
        "step_km": step_km,
        "progression_data": progression_data
    }


def generate_distance_progression_chart(progression_data: Dict[str, Any]) -> str:
    """
    Generate a text-based distance progression chart.
    """
    if not progression_data["ok"]:
        return f"❌ Distance progression analysis failed: {progression_data.get('error', 'Unknown error')}"
    
    chart = []
    chart.append("📊 DISTANCE PROGRESSION CHART")
    chart.append("=" * 60)
    chart.append(f"🔍 {progression_data['event_a']} vs {progression_data['event_b']}")
    event_a = progression_data.get('event_a', 'A')
    event_b = progression_data.get('event_b', 'B')
    chart.append(f"📍 {event_a}: {progression_data['total_a']} runners ({progression_data['from_km_a']}km to {progression_data['to_km_a']}km)")
    chart.append(f"📍 {event_b}: {progression_data['total_b']} runners ({progression_data['from_km_b']}km to {progression_data['to_km_b']}km)")
    chart.append(f"📏 Step size: {progression_data['step_km']}km")
    chart.append("")
    
    # Find max count for scaling
    max_count = max([d["total_count"] for d in progression_data["progression_data"]])
    if max_count == 0:
        chart.append("No runners found in segment")
        return "\n".join(chart)
    
    # Create chart
    chart.append("Distance(km) | A Count | B Count | Total | Chart")
    chart.append("-" * 60)
    
    for data in progression_data["progression_data"]:
        distance = data["distance_km"]
        count_a = data["count_a"]
        count_b = data["count_b"]
        total = data["total_count"]
        
        # Create simple bar chart
        bar_length = int((total / max_count) * 20) if max_count > 0 else 0
        bar = "█" * bar_length
        
        # Add segment indicators
        segment_indicator = ""
        if data["in_segment_a"] and data["in_segment_b"]:
            segment_indicator = " [A+B]"
        elif data["in_segment_a"]:
            segment_indicator = " [A]"
        elif data["in_segment_b"]:
            segment_indicator = " [B]"
        
        chart.append(f"{distance:8.2f}km | {count_a:7d} | {count_b:7d} | {total:5d} | {bar}{segment_indicator}")
    
    chart.append("")
    chart.append("Legend: [A] = Event A only, [B] = Event B only, [A+B] = Both events")
    
    return "\n".join(chart)


def calculate_tot_metrics(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = 100.0,
    thresholds: List[int] = [10, 20, 50, 100],
    time_bin_seconds: int = 30,
) -> Dict[str, Any]:
    """
    Calculate Time-Over-Threshold (TOT) metrics for operational planning.
    Returns periods when runner counts exceed specified thresholds.
    """
    if df_a.empty or df_b.empty:
        return {"ok": False, "error": "Empty dataframes"}
    
    # Calculate segment lengths
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return {"ok": False, "error": "Invalid segment lengths"}
    
    # Calculate conflict zone boundaries
    conflict_length_km = conflict_length_m / 1000.0
    conflict_half_km = conflict_length_km / 2.0
    
    cp_km_a_start = max(from_km_a, cp_km - conflict_half_km)
    cp_km_a_end = min(to_km_a, cp_km + conflict_half_km)
    
    # Map to local fractions
    s_start = (cp_km_a_start - from_km_a) / max(len_a, 1e-9)
    s_end = (cp_km_a_end - from_km_a) / max(len_a, 1e-9)
    s_start, _ = clamp_normalized_fraction(s_start, "conflict_zone_start_")
    s_end, _ = clamp_normalized_fraction(s_end, "conflict_zone_end_")
    
    # Convert to each event's km
    cp_km_a_start = from_km_a + s_start * len_a
    cp_km_a_end = from_km_a + s_end * len_a
    
    cp_km_b_start = from_km_b + s_start * len_b
    cp_km_b_end = from_km_b + s_end * len_b
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate arrival times for all runners in conflict zone
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    time_enter_a = start_a + offset_a + pace_a * cp_km_a_start
    time_exit_a = start_a + offset_a + pace_a * cp_km_a_end
    
    pace_b = df_b["pace"].values * 60.0
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    time_enter_b = start_b + offset_b + pace_b * cp_km_b_start
    time_exit_b = start_b + offset_b + pace_b * cp_km_b_end
    
    # Find time range
    all_times = list(time_enter_a) + list(time_exit_a) + list(time_enter_b) + list(time_exit_b)
    min_time = min(all_times)
    max_time = max(all_times)
    
    # Create time bins
    time_bins = []
    current_time = min_time
    while current_time <= max_time:
        time_bins.append(current_time)
        current_time += time_bin_seconds
    
    # Calculate runner counts in each time bin
    bin_data = []
    for bin_time in time_bins:
        # Count runners from each event in conflict zone at this time
        count_a = sum((time_enter_a <= bin_time) & (time_exit_a >= bin_time))
        count_b = sum((time_enter_b <= bin_time) & (time_exit_b >= bin_time))
        total_count = count_a + count_b
        
        bin_data.append({
            "time_seconds": bin_time,
            "time_minutes": bin_time / 60.0,
            "count_a": count_a,
            "count_b": count_b,
            "total_count": total_count
        })
    
    # Calculate TOT metrics for each threshold
    tot_metrics = {}
    for threshold in thresholds:
        tot_periods = []
        in_threshold = False
        period_start = None
        
        for bin_data_point in bin_data:
            if bin_data_point["total_count"] >= threshold:
                if not in_threshold:
                    in_threshold = True
                    period_start = bin_data_point["time_seconds"]
            else:
                if in_threshold:
                    in_threshold = False
                    period_end = bin_data_point["time_seconds"]
                    tot_periods.append({
                        "start_seconds": period_start,
                        "end_seconds": period_end,
                        "start_minutes": period_start / 60.0,
                        "end_minutes": period_end / 60.0,
                        "duration_seconds": period_end - period_start,
                        "duration_minutes": (period_end - period_start) / 60.0
                    })
        
        # Handle case where period extends to end
        if in_threshold:
            period_end = max_time
            tot_periods.append({
                "start_seconds": period_start,
                "end_seconds": period_end,
                "start_minutes": period_start / 60.0,
                "end_minutes": period_end / 60.0,
                "duration_seconds": period_end - period_start,
                "duration_minutes": (period_end - period_start) / 60.0
            })
        
        # Calculate total TOT time
        total_tot_seconds = sum([p["duration_seconds"] for p in tot_periods])
        total_tot_minutes = total_tot_seconds / 60.0
        
        tot_metrics[f"threshold_{threshold}"] = {
            "threshold": threshold,
            "periods": tot_periods,
            "total_periods": len(tot_periods),
            "total_tot_seconds": total_tot_seconds,
            "total_tot_minutes": total_tot_minutes,
            "total_tot_percentage": (total_tot_seconds / (max_time - min_time)) * 100 if max_time > min_time else 0
        }
    
    return {
        "ok": True,
        "event_a": event_a,
        "event_b": event_b,
        "conflict_zone_start": cp_km_a_start,
        "conflict_zone_end": cp_km_a_end,
        "conflict_length_m": conflict_length_m,
        "time_range_seconds": max_time - min_time,
        "time_range_minutes": (max_time - min_time) / 60.0,
        "time_bin_seconds": time_bin_seconds,
        "thresholds": thresholds,
        "bin_data": bin_data,
        "tot_metrics": tot_metrics
    }


def generate_tot_report(tot_data: Dict[str, Any]) -> str:
    """
    Generate a text-based TOT metrics report.
    """
    if not tot_data["ok"]:
        return f"❌ TOT analysis failed: {tot_data.get('error', 'Unknown error')}"
    
    report = []
    report.append("⏱️ TIME-OVER-THRESHOLD (TOT) METRICS")
    report.append("=" * 60)
    report.append(f"🔍 {tot_data['event_a']} vs {tot_data['event_b']}")
    report.append(f"📏 Conflict Length: {tot_data['conflict_length_m']}m")
    report.append(f"⏰ Time Range: {tot_data['time_range_minutes']:.1f} minutes")
    report.append(f"📊 Time Bin Size: {tot_data['time_bin_seconds']} seconds")
    report.append("")
    
    # Summary table
    report.append("📈 TOT SUMMARY")
    report.append("-" * 60)
    report.append("Threshold | Periods | Total TOT | TOT %")
    report.append("-" * 60)
    
    for threshold in tot_data["thresholds"]:
        metric = tot_data["tot_metrics"][f"threshold_{threshold}"]
        report.append(f"{threshold:9d} | {metric['total_periods']:7d} | {metric['total_tot_minutes']:8.1f}m | {metric['total_tot_percentage']:5.1f}%")
    
    report.append("")
    
    # Detailed periods for each threshold
    for threshold in tot_data["thresholds"]:
        metric = tot_data["tot_metrics"][f"threshold_{threshold}"]
        if metric["total_periods"] > 0:
            report.append(f"🚨 THRESHOLD {threshold} RUNNERS - {metric['total_periods']} PERIODS")
            report.append("-" * 40)
            for i, period in enumerate(metric["periods"], 1):
                start_time = f"{int(period['start_minutes']//60):02d}:{int(period['start_minutes']%60):02d}"
                end_time = f"{int(period['end_minutes']//60):02d}:{int(period['end_minutes']%60):02d}"
                report.append(f"  {i:2d}. {start_time} - {end_time} ({period['duration_minutes']:.1f}m)")
            report.append("")
    
    return "\n".join(report)

