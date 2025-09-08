from __future__ import annotations
import time
from typing import Dict, Optional, Any, List, Tuple
import pandas as pd
import numpy as np
from .utils import load_pace_csv, arrival_time_sec

# Use shared utility functions from utils module

def analyze_overlaps(
    pace_csv: str,
    overlaps_csv: Optional[str],
    start_times: Dict[str, float],
    step_km: float,
    time_window_s: float,
    eventA: str,
    eventB: Optional[str],
    from_km: float,
    to_km: float,
) -> Dict[str, Any]:
    """Per-step split counts using constant-pace model & staggered starts.

    Returns:
      {
        ok: True,
        engine: "overlap",
        steps: [ {km, <A>_runners, <B>_runners, combined_runners}, ... ],
        peak: {km, A, B, combined}
      }
    """
    t0 = time.perf_counter()
    df = load_pace_csv(pace_csv).copy()
    
    # Convert start times to seconds and add to dataframe
    df["start_sec"] = df["event"].map({k: float(v)*60.0 for k,v in start_times.items()}).astype(float)
    df["pace_sec_per_km"] = df["pace"] * 60.0

    dfA = df[df["event"] == eventA].copy()
    if dfA.empty:
        raise ValueError(f"No runners for eventA={eventA}")
    dfA.name = eventA
    
    dfB = None
    if eventB:
        dfB = df[df["event"] == eventB].copy()
        if dfB.empty:
            raise ValueError(f"No runners for eventB={eventB}")
        dfB.name = eventB

    def count_at_km(df_event: pd.DataFrame, km: float, t_center: float) -> int:
        """Count runners at km within time window."""
        t_arr = df_event["start_sec"] + df_event["start_offset"] + df_event["pace_sec_per_km"] * km
        return int(((t_arr >= (t_center - time_window_s/2)) & (t_arr <= (t_center + time_window_s/2))).sum())

    steps: List[Dict[str, Any]] = []
    kms = np.round(np.arange(from_km, to_km + 1e-9, step_km), 2)
    
    for km in kms:
        # Reference timestamps per event (median) to reduce bias
        tA = (dfA["start_sec"] + dfA["start_offset"] + dfA["pace_sec_per_km"] * km).median()
        cA = count_at_km(dfA, km, tA)
        
        cB = 0
        if dfB is not None:
            tB = (dfB["start_sec"] + dfB["start_offset"] + dfB["pace_sec_per_km"] * km).median()
            cB = count_at_km(dfB, km, tB)
        
        steps.append({
            "km": float(km),
            f"{eventA}_runners": int(cA),
            f"{eventB}_runners": int(cB) if dfB is not None else None,
            "combined_runners": int(cA + cB),
        })

    peak = max(steps, key=lambda s: s["combined_runners"]) if steps else {"km": None, "combined_runners": 0}
    peak_out = {
        "km": peak["km"],
        "A": peak.get(f"{eventA}_runners", 0),
        "B": peak.get(f"{eventB}_runners", 0) if eventB else None,
        "combined": peak["combined_runners"],
    }
    
    return {
        "ok": True,
        "engine": "overlap",
        "steps": steps,
        "peak": peak_out,
    }

def detect_overlaps_at_km(
    df: pd.DataFrame,
    eventA: str,
    eventB: str,
    km_val: float,
    start_times: Dict[str, float],
    tolerance_sec: float = 0.0,
) -> Tuple[int, int, List[str], List[str]]:
    """Detect overlaps between two events at a specific km mark.
    
    Args:
        df: DataFrame with pace data
        eventA: First event name
        eventB: Second event name  
        km_val: Kilometer mark to check
        start_times: Dictionary of start times in minutes
        tolerance_sec: Time tolerance for overlap detection
        
    Returns:
        Tuple of (count_A, count_B, runner_ids_A, runner_ids_B)
    """
    # Filter runners for each event
    dfA = df[df["event"] == eventA]
    dfB = df[df["event"] == eventB]
    
    if dfA.empty or dfB.empty:
        return 0, 0, [], []
    
    # Get eligible runners (those who can reach this km)
    eligA = dfA[dfA["distance"] >= (km_val - 1e-9)]
    eligB = dfB[dfB["distance"] >= (km_val - 1e-9)]
    
    if eligA.empty or eligB.empty:
        return 0, 0, [], []
    
    # Calculate arrival times (vectorized)
    t0_A = start_times.get(eventA, 0) * 60.0
    t0_B = start_times.get(eventB, 0) * 60.0
    
    arrivals_A = t0_A + eligA["start_offset"].values + km_val * eligA["pace"].values * 60.0
    arrivals_B = t0_B + eligB["start_offset"].values + km_val * eligB["pace"].values * 60.0
    
    # Use broadcasting to find all overlaps simultaneously
    # This creates a 2D array of time differences
    time_diff_matrix = np.abs(arrivals_A[:, np.newaxis] - arrivals_B)
    
    # Find overlaps within tolerance (vectorized)
    overlap_matrix = time_diff_matrix <= tolerance_sec
    
    # Get runner IDs for overlaps
    A_indices, B_indices = np.where(overlap_matrix)
    
    # Extract unique runner IDs
    A_runner_ids = eligA.iloc[A_indices]["runner_id"].astype(str).unique().tolist()
    B_runner_ids = eligB.iloc[B_indices]["runner_id"].astype(str).unique().tolist()
    
    return len(A_runner_ids), len(B_runner_ids), A_runner_ids, B_runner_ids

def generate_overlap_narrative(
    df: pd.DataFrame,
    seg_id: str,
    eventA: str,
    eventB: str,
    from_km_A: float,
    to_km_A: float,
    from_km_B: float,
    to_km_B: float,
    start_times: Dict[str, float],
    step_km: float = 0.03,
    tolerance_sec: float = 0.0,
    sample_bibs: int = 5,
) -> Dict[str, Any]:
    """Generate a narrative description of overlaps for a segment.
    
    Args:
        df: DataFrame with pace data
        seg_id: Segment identifier
        eventA: First event name
        eventB: Second event name
        from_km_A: Start km for event A
        to_km_A: End km for event A
        from_km_B: Start km for event B
        to_km_B: End km for event B
        start_times: Dictionary of start times in minutes
        step_km: Kilometer step size for analysis
        tolerance_sec: Time tolerance for overlap detection
        sample_bibs: Number of sample runner IDs to include
        
    Returns:
        Dictionary with overlap narrative
    """
    # Get eligible runners for each event
    dfA = df[df["event"] == eventA]
    dfB = df[df["event"] == eventB]
    
    # Calculate segment totals
    total_A = len(dfA)
    total_B = len(dfB)
    
    # Find km positions to analyze
    kms = np.round(np.arange(from_km_A, to_km_A + 1e-9, step_km), 2)
    
    # Track peak overlap
    peak_overlap = {"km": None, "A": 0, "B": 0, "combined": 0}
    first_overlap = None
    
    for km in kms:
        count_A, count_B, runner_ids_A, runner_ids_B = detect_overlaps_at_km(
            df, eventA, eventB, km, start_times, tolerance_sec
        )
        
        combined = count_A + count_B
        
        # Track peak
        if combined > peak_overlap["combined"]:
            peak_overlap = {"km": km, "A": count_A, "B": count_B, "combined": combined}
        
        # Track first overlap
        if first_overlap is None and combined > 0:
            # Sample some runner IDs
            sample_A = runner_ids_A[:sample_bibs] if runner_ids_A else []
            sample_B = runner_ids_B[:sample_bibs] if runner_ids_B else []
            
            first_overlap = {
                "km": km,
                "count_A": count_A,
                "count_B": count_B,
                "sample_runner_ids_A": sample_A,
                "sample_runner_ids_B": sample_B,
            }
    
    return {
        "seg_id": seg_id,
        "eventA": eventA,
        "eventB": eventB,
        "segment_totals": {
            "A": total_A,
            "B": total_B
        },
        "first_overlap": first_overlap,
        "peak_overlap": peak_overlap,
        "analysis_params": {
            "step_km": step_km,
            "tolerance_sec": tolerance_sec,
            "from_km_A": from_km_A,
            "to_km_A": to_km_A,
            "from_km_B": from_km_B,
            "to_km_B": to_km_B
        }
    }

def generate_overlap_trace(
    df: pd.DataFrame,
    seg_id: str,
    eventA: str,
    eventB: str,
    from_km_A: float,
    to_km_A: float,
    from_km_B: float,
    to_km_B: float,
    start_times: Dict[str, float],
    step_km: float = 0.03,
    tolerance_sec: float = 0.0,
    sample_bibs: int = 5,
) -> Dict[str, Any]:
    """Generate a comprehensive overlap trace showing overlaps at every km step.
    
    Args:
        df: DataFrame with pace data
        seg_id: Segment identifier
        eventA: First event name
        eventB: Second event name
        from_km_A: Start km for event A
        to_km_A: End km for event A
        from_km_B: Start km for event B
        to_km_B: End km for event B
        start_times: Dictionary of start times in minutes
        step_km: Kilometer step size for analysis
        tolerance_sec: Time tolerance for overlap detection
        sample_bibs: Number of sample runner IDs to include
        
    Returns:
        Dictionary with complete overlap trace
    """
    # Get eligible runners for each event
    dfA = df[df["event"] == eventA]
    dfB = df[df["event"] == eventB]
    
    # Calculate segment totals
    total_A = len(dfA)
    total_B = len(dfB)
    
    # Find km positions to analyze
    kms = np.round(np.arange(from_km_A, to_km_A + 1e-9, step_km), 2)
    
    # Track all overlaps
    trace = []
    peak_overlap = {"km": None, "A": 0, "B": 0, "combined": 0}
    first_overlap = None
    
    for km in kms:
        count_A, count_B, runner_ids_A, runner_ids_B = detect_overlaps_at_km(
            df, eventA, eventB, km, start_times, tolerance_sec
        )
        
        combined = count_A + count_B
        
        # Track peak
        if combined > peak_overlap["combined"]:
            peak_overlap = {"km": km, "A": count_A, "B": count_B, "combined": combined}
        
        # Track first overlap
        if first_overlap is None and combined > 0:
            sample_A = runner_ids_A[:sample_bibs] if runner_ids_A else []
            sample_B = runner_ids_B[:sample_bibs] if runner_ids_B else []
            
            first_overlap = {
                "km": km,
                "count_A": count_A,
                "count_B": count_B,
                "sample_runner_ids_A": sample_A,
                "sample_runner_ids_B": sample_B,
            }
        
        # Add to trace
        trace.append({
            "km": km,
            "A": count_A,
            "B": count_B,
            "combined": combined,
            "A_runner_ids": runner_ids_A,
            "B_runner_ids": runner_ids_B
        })
    
    return {
        "seg_id": seg_id,
        "eventA": eventA,
        "eventB": eventB,
        "segment_totals": {
            "A": total_A,
            "B": total_B
        },
        "first_overlap": first_overlap,
        "peak_overlap": peak_overlap,
        "trace": trace,
        "analysis_params": {
            "step_km": step_km,
            "tolerance_sec": tolerance_sec,
            "from_km_A": from_km_A,
            "to_km_A": to_km_A,
            "from_km_B": from_km_B,
            "to_km_B": to_km_B
        }
    }

def generate_overlap_narrative_convergence(
    df: pd.DataFrame,
    seg_id: str,
    eventA: str,
    eventB: str,
    from_km_A: float,
    to_km_A: float,
    from_km_B: float,
    to_km_B: float,
    start_times: Dict[str, float],
    step_km: float = 0.03,
    min_overlap_duration: float = 5.0,
    sample_bibs: int = 5,
    max_bib_list_size: int = 10,
) -> Dict[str, Any]:
    """Generate a narrative description of overlaps for a segment using convergence zone logic."""
    # Get eligible runners for each event
    dfA = df[df["event"] == eventA]
    dfB = df[df["event"] == eventB]
    
    # Calculate segment totals
    total_A = _segment_totals(dfA, to_km_A)
    total_B = _segment_totals(dfB, to_km_B)
    
    # Calculate convergence point
    convergence_point = calculate_convergence_point(
        dfA, dfB, eventA, eventB, start_times, from_km_A, to_km_A, step_km
    )
    
    # Initialize overlap data
    convergence_overlaps = None
    first_overlap = None
    
    if convergence_point is not None:
        # Calculate overlaps in convergence zone
        cp_A, cp_B, a_bibs, b_bibs = calculate_convergence_zone_overlaps(
            dfA, dfB, eventA, eventB, start_times, convergence_point, to_km_A, min_overlap_duration
        )
        
        convergence_overlaps = {
            "convergence_point": convergence_point,
            "convergence_zone_start": convergence_point,
            "convergence_zone_end": to_km_A,
            "zone_length": round(to_km_A - convergence_point, 2),
            "count_A": cp_A,
            "count_B": cp_B,
            "a_bibs": a_bibs,
            "b_bibs": b_bibs
        }
        
        # Format bib ranges for display
        a_bib_display = format_bib_range(a_bibs, sample_bibs)
        b_bib_display = format_bib_range(b_bibs, sample_bibs)
        
        # Create first overlap info from convergence zone
        if cp_A > 0 and cp_B > 0:
            first_overlap = {
                "km": convergence_point,
                "count_A": cp_A,
                "count_B": cp_B,
                "sample_runner_ids_A": a_bibs[:sample_bibs] if a_bibs else [],
                "sample_runner_ids_B": b_bibs[:sample_bibs] if b_bibs else [],
                "a_bib_display": a_bib_display,
                "b_bib_display": b_bib_display
            }
    
    return {
        "seg_id": seg_id,
        "eventA": eventA,
        "eventB": eventB,
        "segment_totals": {
            "A": total_A,
            "B": total_B
        },
        "convergence_overlaps": convergence_overlaps,
        "first_overlap": first_overlap,
        "analysis_params": {
            "step_km": step_km,
            "min_overlap_duration": min_overlap_duration,
            "from_km_A": from_km_A,
            "to_km_A": to_km_A,
            "from_km_B": from_km_B,
            "to_km_B": to_km_B
        }
    }

def _segment_totals(df_event: pd.DataFrame, to_km: float) -> int:
    """Calculate the total number of runners who reach a given to_km for a specific event."""
    if df_event.empty:
        return 0
    return len(df_event[df_event["distance"] >= to_km])

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
        from .constants import TEMPORAL_OVERLAP_TOLERANCE_SECONDS
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
        from .constants import TRUE_PASS_DETECTION_TOLERANCE_SECONDS
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

def calculate_convergence_zone_overlaps(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    to_km: float,
    min_overlap_duration: float = 5.0,
) -> Tuple[int, int, List[str], List[str]]:
    """Calculate the actual number of overlapping runners within the convergence zone using vectorized operations."""
    if df_a.empty or df_b.empty:
        return 0, 0, [], []
    
    # Get start times in seconds
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Vectorized calculations for all runners at once
    # Event A runners
    pace_a = df_a["pace"].values  # minutes per km
    offset_a = df_a["start_offset"].values
    time_enter_a = start_a + offset_a + (pace_a * 60.0 * cp_km)
    time_exit_a = start_a + offset_a + (pace_a * 60.0 * to_km)
    
    # Event B runners
    pace_b = df_b["pace"].values  # minutes per km
    offset_b = df_b["start_offset"].values
    time_enter_b = start_b + offset_b + (pace_b * 60.0 * cp_km)
    time_exit_b = start_b + offset_b + (pace_b * 60.0 * to_km)
    
    # Track overlapping runners
    a_bibs = set()
    b_bibs = set()
    
    # Use broadcasting to check all pairs efficiently
    # This avoids the O(n²) nested loops
    for i, (enter_a, exit_a) in enumerate(zip(time_enter_a, time_exit_a)):
        # Check overlap with all event B runners
        overlap_start = np.maximum(enter_a, time_enter_b)
        overlap_end = np.minimum(exit_a, time_exit_b)
        
        # Find valid overlaps (duration >= min_overlap_duration)
        valid_overlaps = (overlap_end > overlap_start) & ((overlap_end - overlap_start) >= min_overlap_duration)
        
        if np.any(valid_overlaps):
            # Add runner A
            a_bibs.add(df_a.iloc[i]["runner_id"])
            
            # Add all overlapping runners B
            overlapping_b_indices = np.where(valid_overlaps)[0]
            for b_idx in overlapping_b_indices:
                b_bibs.add(df_b.iloc[b_idx]["runner_id"])
    
    return len(a_bibs), len(b_bibs), list(a_bibs), list(b_bibs)

def format_bib_range(bib_list: List[str], max_individual: int = 10) -> str:
    """Format a list of runner IDs for display."""
    if not bib_list:
        return "None"
    
    if len(bib_list) <= max_individual:
        return ", ".join(map(str, bib_list))
    
    # For large lists, show range
    sorted_bibs = sorted(bib_list, key=lambda x: int(x) if str(x).isdigit() else x)
    first_bib = sorted_bibs[0]
    last_bib = sorted_bibs[-1]
    
    if str(first_bib).isdigit() and str(last_bib).isdigit():
        return f"{first_bib}-{last_bib} ({len(bib_list)} runners)"
    else:
        return f"{first_bib}-{last_bib} ({len(bib_list)} runners)"
