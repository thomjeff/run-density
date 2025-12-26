from __future__ import annotations
import time
from typing import Dict, Optional, Any, List, Tuple
import pandas as pd
import numpy as np
from app.utils.shared import load_pace_csv, arrival_time_sec

# Use shared utility functions from utils module

# Phase 3 cleanup: Removed unused v1-only functions (not imported anywhere):
# - analyze_overlaps() - REMOVED
# - detect_overlaps_at_km() - REMOVED (only used by other unused functions)
# - generate_overlap_narrative() - REMOVED
# - generate_overlap_trace() - REMOVED
# - generate_overlap_narrative_convergence() - REMOVED
# - _segment_totals() - REMOVED (only used by unused functions)
# - calculate_convergence_zone_overlaps() - REMOVED (v2 has its own implementation)
# - format_bib_range() - REMOVED (v2 has its own implementation)
# 
# Preserved v2-used functions:
# - calculate_convergence_point() - Used by app/core/flow/flow.py
# - calculate_true_pass_detection() - Used by app/core/flow/flow.py

def calculate_convergence_point(
    dfA: pd.DataFrame,
    dfB: pd.DataFrame,
    eventA: str,
    eventB: str,
    start_times: Dict[str, float],
    from_km: float,
    to_km: float,
    step_km: float,
) -> Optional[float]:
    """
    Calculate convergence point ONLY when actual temporal overlaps occur.
    
    This function finds the first location where runners from different events
    actually overlap in time within the segment. Returns None if no actual
    temporal overlaps exist.
    
    Returns the kilometer mark (in event A's km ruler) where the first
    actual temporal overlap occurs, or None if no overlaps exist.
    """
    if dfA.empty or dfB.empty:
        return None
    
    # Segment lengths in each event's own ruler
    len_a = to_km - from_km
    if len_a <= 0:
        return None

    # Get absolute start times in seconds
    start_a = start_times.get(eventA, 0) * 60.0
    start_b = start_times.get(eventB, 0) * 60.0

    # Find the first location where actual temporal overlaps occur
    # We'll check multiple points along the segment to find where overlaps begin
    
    # Create distance check points along the segment
    # Also check for temporal overlap at segment boundaries and slightly beyond
    check_points = []
    current_km = from_km
    while current_km <= to_km:
        check_points.append(current_km)
        current_km += step_km
    
    # For each check point, see if there are actual temporal overlaps
    for km_point in check_points:
        # Calculate arrival times for all runners at this point
        # Event A runners
        pace_a = dfA["pace"].values * 60.0  # sec per km
        offset_a = dfA.get("start_offset", pd.Series([0]*len(dfA))).fillna(0).values.astype(float)
        arrival_times_a = start_a + offset_a + pace_a * km_point
        
        # Event B runners  
        pace_b = dfB["pace"].values * 60.0  # sec per km
        offset_b = dfB.get("start_offset", pd.Series([0]*len(dfB))).fillna(0).values.astype(float)
        arrival_times_b = start_b + offset_b + pace_b * km_point
        
        # Check for temporal overlaps (runners present at same time)
        # Use configurable tolerance for temporal overlap
        from app.utils.constants import TEMPORAL_OVERLAP_TOLERANCE_SECONDS
        tolerance_seconds = TEMPORAL_OVERLAP_TOLERANCE_SECONDS
        
        # Issue #503: Vectorized overlap detection using NumPy broadcasting
        # Instead of nested loops O(n*m), use broadcasting for O(n*m) but vectorized
        # Shape: arrival_times_a is (n,), arrival_times_b is (m,)
        # Broadcast to (n, 1) - (1, m) = (n, m) difference matrix
        time_diff = np.abs(arrival_times_a[:, np.newaxis] - arrival_times_b[np.newaxis, :])
        overlaps = time_diff <= tolerance_seconds
        
        # Check if any overlap exists
        if np.any(overlaps):
            # Found temporal overlap - return this km point
            # BUT ONLY if it's within the segment boundaries
            if from_km <= km_point <= to_km:
                return float(km_point)
            # If convergence is outside segment, continue searching for one inside
    
    # If no convergence found at specific points, check for general temporal overlap
    # This handles cases where events overlap in time but at different positions
    # Calculate entry/exit times for the entire segment
    entry_times_a = start_a + dfA.get("start_offset", pd.Series([0]*len(dfA))).fillna(0).values.astype(float) + dfA["pace"].values * 60.0 * from_km
    exit_times_a = start_a + dfA.get("start_offset", pd.Series([0]*len(dfA))).fillna(0).values.astype(float) + dfA["pace"].values * 60.0 * to_km
    
    entry_times_b = start_b + dfB.get("start_offset", pd.Series([0]*len(dfB))).fillna(0).values.astype(float) + dfB["pace"].values * 60.0 * from_km
    exit_times_b = start_b + dfB.get("start_offset", pd.Series([0]*len(dfB))).fillna(0).values.astype(float) + dfB["pace"].values * 60.0 * to_km
    
    # Issue #503: Vectorized temporal overlap detection using NumPy broadcasting
    # Check for any temporal overlap between events in the segment
    # Entry/exit times are already numpy arrays from .values
    # Shape: entry_times_a is (n,), exit_times_a is (n,)
    #        entry_times_b is (m,), exit_times_b is (m,)
    # Broadcast to check all pairs: (n, 1) vs (1, m) = (n, m) boolean matrix
    entry_a_2d = entry_times_a[:, np.newaxis]  # (n, 1)
    exit_a_2d = exit_times_a[:, np.newaxis]    # (n, 1)
    entry_b_2d = entry_times_b[np.newaxis, :]  # (1, m)
    exit_b_2d = exit_times_b[np.newaxis, :]    # (1, m)
    
    # Check temporal overlap: (entry_a <= exit_b + tolerance) AND (entry_b <= exit_a + tolerance)
    overlap_condition = (
        (entry_a_2d <= exit_b_2d + tolerance_seconds) &
        (entry_b_2d <= exit_a_2d + tolerance_seconds)
    )
    
    if np.any(overlap_condition):
        # Found temporal overlap - return the segment start
        return float(from_km)
    
    # No temporal overlaps found
    return None


def calculate_true_pass_detection(
    dfA: pd.DataFrame,
    dfB: pd.DataFrame,
    eventA: str,
    eventB: str,
    start_times: Dict[str, float],
    from_km: float,
    to_km: float,
    step_km: float,
) -> Optional[float]:
    """
    Calculate convergence point based on TRUE PASS DETECTION.
    
    This function detects when runners from one event actually pass runners
    from another event (directional overtaking), not just co-presence.
    
    A true pass occurs when:
    1. Runner A arrives at km_point at time T_A
    2. Runner B arrives at km_point at time T_B  
    3. |T_A - T_B| <= tolerance
    4. AND one runner was behind the other at from_km but ahead at to_km
    
    Returns the kilometer mark where the first true pass occurs, or None.
    """
    if dfA.empty or dfB.empty:
        return None
    
    # Segment lengths in each event's own ruler
    len_a = to_km - from_km
    if len_a <= 0:
        return None

    # Get absolute start times in seconds
    start_a = start_times.get(eventA, 0) * 60.0
    start_b = start_times.get(eventB, 0) * 60.0

    # Create distance check points along the segment
    check_points = []
    current_km = from_km
    while current_km <= to_km:
        check_points.append(current_km)
        current_km += step_km
    
    # For each check point, detect true passes
    for km_point in check_points:
        # Calculate arrival times for all runners at this point
        pace_a = dfA["pace"].values * 60.0  # sec per km
        offset_a = dfA.get("start_offset", pd.Series([0]*len(dfA))).fillna(0).values.astype(float)
        arrival_times_a = start_a + offset_a + pace_a * km_point
        
        pace_b = dfB["pace"].values * 60.0  # sec per km
        offset_b = dfB.get("start_offset", pd.Series([0]*len(dfB))).fillna(0).values.astype(float)
        arrival_times_b = start_b + offset_b + pace_b * km_point
        
        # Calculate arrival times at segment start (from_km)
        arrival_start_a = start_a + offset_a + pace_a * from_km
        arrival_start_b = start_b + offset_b + pace_b * from_km
        
        # Calculate arrival times at segment end (to_km)  
        arrival_end_a = start_a + offset_a + pace_a * to_km
        arrival_end_b = start_b + offset_b + pace_b * to_km
        
        # Use configurable tolerance for true pass detection
        from app.utils.constants import TRUE_PASS_DETECTION_TOLERANCE_SECONDS
        tolerance_seconds = TRUE_PASS_DETECTION_TOLERANCE_SECONDS
        
        # Issue #503: Vectorized true pass detection using NumPy broadcasting
        # Check for true passes: temporal overlap AND directional change
        # Shape: arrival_times_a is (n,), arrival_times_b is (m,)
        # Broadcast to (n, 1) - (1, m) = (n, m) difference matrix
        time_diff = np.abs(arrival_times_a[:, np.newaxis] - arrival_times_b[np.newaxis, :])
        temporal_overlaps = time_diff <= tolerance_seconds
        
        if not np.any(temporal_overlaps):
            continue  # No temporal overlap at this km_point, skip to next
        
        # For pairs with temporal overlap, check directional passes
        # Broadcast start/end times to (n, m) matrices
        start_a_2d = arrival_start_a[:, np.newaxis]  # (n, 1)
        start_b_2d = arrival_start_b[np.newaxis, :]  # (1, m)
        end_a_2d = arrival_end_a[:, np.newaxis]      # (n, 1)
        end_b_2d = arrival_end_b[np.newaxis, :]      # (1, m)
        
        # Check for pass A -> B (A overtakes B): A starts behind B but finishes ahead of B
        pass_a_b = (start_a_2d > start_b_2d) & (end_a_2d < end_b_2d)
        
        # Check for pass B -> A (B overtakes A): B starts behind A but finishes ahead of A
        pass_b_a = (start_b_2d > start_a_2d) & (end_b_2d < end_a_2d)
        
        # Check for convergence: runners meet at same time at both boundaries
        start_convergence = np.abs(start_a_2d - start_b_2d) <= tolerance_seconds
        end_convergence = np.abs(end_a_2d - end_b_2d) <= tolerance_seconds
        convergence = start_convergence & end_convergence
        
        # Check for runners running together (close in time and space)
        start_close = np.abs(start_a_2d - start_b_2d) <= tolerance_seconds * 2
        end_close = np.abs(end_a_2d - end_b_2d) <= tolerance_seconds * 2
        running_together = start_close & end_close
        
        # Combine all conditions: temporal overlap AND (pass OR convergence OR running together)
        true_pass_mask = temporal_overlaps & (pass_a_b | pass_b_a | convergence | running_together)
        
        if np.any(true_pass_mask):
            return float(km_point)
    
    # No true passes found
    return None

# Phase 3 cleanup: Removed calculate_convergence_zone_overlaps() and format_bib_range()
# - calculate_convergence_zone_overlaps() - REMOVED (v2 has its own implementation in app/core/flow/flow.py)
# - format_bib_range() - REMOVED (v2 has its own implementation in app/core/flow/flow.py)
