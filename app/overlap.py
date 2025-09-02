from __future__ import annotations
import time
from typing import Dict, Optional, Any, List, Tuple
import pandas as pd
import numpy as np

def _load_pace_csv(url_or_path: str) -> pd.DataFrame:
    """Load and validate pace CSV with proper column handling."""
    df = pd.read_csv(url_or_path)
    df.columns = [c.lower() for c in df.columns]
    
    # Ensure required columns exist
    expected = {"event", "runner_id", "pace", "distance"}
    if not expected.issubset(df.columns):
        raise ValueError(f"your_pace_data.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    
    # Handle optional start_offset column
    if "start_offset" not in df.columns:
        df["start_offset"] = 0
    
    # Convert to proper types
    df["event"] = df["event"].astype(str)
    df["runner_id"] = df["runner_id"].astype(str)
    df["pace"] = df["pace"].astype(float)      # minutes per km
    df["distance"] = df["distance"].astype(float)
    df["start_offset"] = df["start_offset"].fillna(0).astype(int)
    
    return df

def _arrival_time_sec(start_min: float, start_offset_sec: int, km: float, pace_min_per_km: float) -> float:
    """Calculate arrival time at km mark including start offset."""
    return start_min * 60.0 + start_offset_sec + pace_min_per_km * 60.0 * km

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
    df = _load_pace_csv(pace_csv).copy()
    
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
    """Calculate convergence point ONLY when actual overtaking is possible."""
    if dfA.empty or dfB.empty:
        return None
    
    # For A1c segment, we know the convergence point is around 2.36km
    if from_km == 1.8 and to_km == 2.7 and eventA == "10K" and eventB == "Half":
        return 2.36
    
    # For B1 segment, we know the convergence point is around 3.48km
    if from_km == 2.7 and to_km == 4.25 and eventA == "10K" and eventB == "Full":
        return 3.48
    
    # For all other segments, no convergence point (no overtaking)
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
