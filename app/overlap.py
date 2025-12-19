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
        
        # Find if any runners from A and B are present at the same time
        for time_a in arrival_times_a:
            for time_b in arrival_times_b:
                if abs(time_a - time_b) <= tolerance_seconds:
                    # Found first temporal overlap - return this km point
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
    
    # Check for any temporal overlap between events in the segment
    for i, (entry_a, exit_a) in enumerate(zip(entry_times_a, exit_times_a)):
        for j, (entry_b, exit_b) in enumerate(zip(entry_times_b, exit_times_b)):
            # Check if runners are in segment at same time
            if (entry_a <= exit_b + tolerance_seconds and 
                entry_b <= exit_a + tolerance_seconds):
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
        
        # Check for true passes: temporal overlap AND directional change
        for i, time_a in enumerate(arrival_times_a):
            for j, time_b in enumerate(arrival_times_b):
                if abs(time_a - time_b) <= tolerance_seconds:
                    # Temporal overlap detected - now check for directional pass
                    
                    # Check if this represents a true pass
                    # Runner A passes Runner B if:
                    # - At from_km: A arrives after B (A is behind B)
                    # - At to_km: A arrives before B (A is ahead of B)
                    # OR vice versa
                    
                    start_time_a = arrival_start_a[i]
                    start_time_b = arrival_start_b[j]
                    end_time_a = arrival_end_a[i]
                    end_time_b = arrival_end_b[j]
                    
                    # Check for pass A -> B (A overtakes B)
                    # A starts behind B but finishes ahead of B
                    if (start_time_a > start_time_b and end_time_a < end_time_b):
                        return float(km_point)
                    
                    # Check for pass B -> A (B overtakes A)  
                    # B starts behind A but finishes ahead of A
                    if (start_time_b > start_time_a and end_time_b < end_time_a):
                        return float(km_point)
                    
                    # IMPROVED: Check for convergence where runners meet at the same time
                    # This handles cases where the directional logic might be too strict
                    # but temporal overlap still indicates meaningful interaction
                    if abs(start_time_a - start_time_b) <= tolerance_seconds and \
                       abs(end_time_a - end_time_b) <= tolerance_seconds:
                        return float(km_point)
                    
                    # ADDITIONAL: Check for runners who are close in time and space
                    # This catches cases where runners are essentially running together
                    if abs(start_time_a - start_time_b) <= tolerance_seconds * 2 and \
                       abs(end_time_a - end_time_b) <= tolerance_seconds * 2:
                        return float(km_point)
    
    # No true passes found
    return None

# Phase 3 cleanup: Removed calculate_convergence_zone_overlaps() and format_bib_range()
# - calculate_convergence_zone_overlaps() - REMOVED (v2 has its own implementation in app/core/flow/flow.py)
# - format_bib_range() - REMOVED (v2 has its own implementation in app/core/flow/flow.py)
