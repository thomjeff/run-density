"""
Temporal Flow Analysis Module

Handles temporal flow analysis for segments where overtaking or merging is possible.
Only processes segments with overtake_flag = 'y' from flow.csv.
Supports overtake, merge, and diverge flow types.
"""

from __future__ import annotations
import time
from typing import Dict, Optional, Any, List, Tuple
import pandas as pd
import numpy as np
from .constants import (
    SECONDS_PER_MINUTE, SECONDS_PER_HOUR,
    DEFAULT_CONVERGENCE_STEP_KM, DEFAULT_MIN_OVERLAP_DURATION, 
    DEFAULT_CONFLICT_LENGTH_METERS, TEMPORAL_OVERLAP_TOLERANCE_SECONDS,
    METERS_PER_KM, PACE_SIMILAR_THRESHOLD, PACE_MODERATE_DIFFERENCE_THRESHOLD
)
from .utils import load_pace_csv, arrival_time_sec, load_segments_csv


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
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return None

    # Get absolute start times in seconds
    start_a = start_times.get(eventA, 0) * SECONDS_PER_MINUTE
    start_b = start_times.get(eventB, 0) * SECONDS_PER_MINUTE

    # Find the first location where actual temporal overlaps occur
    # We'll check multiple points along the segment to find where overlaps begin
    
    # Create distance check points along the segment
    check_points = []
    current_km = from_km_a
    while current_km <= to_km_a:
        check_points.append(current_km)
        current_km += step_km
    
    # For each check point, see if there are actual temporal overlaps
    for km_point in check_points:
        # Map this km point to both events' coordinate systems
        # For event A: direct mapping
        km_a = km_point
        
        # For event B: map using segment-local axis
        s_local = (km_point - from_km_a) / len_a if len_a > 0 else 0.0
        s_local = max(0.0, min(1.0, s_local))  # Clamp to [0,1]
        km_b = from_km_b + s_local * len_b
        
        # Check if this point is within both segments
        if not (from_km_a <= km_a <= to_km_a and from_km_b <= km_b <= to_km_b):
            continue
        
        # Calculate arrival times for all runners at this point
        # Event A runners
        pace_a = dfA["pace"].values * 60.0  # sec per km
        offset_a = dfA.get("start_offset", pd.Series([0]*len(dfA))).fillna(0).values.astype(float)
        arrival_times_a = start_a + offset_a + pace_a * km_a
        
        # Event B runners  
        pace_b = dfB["pace"].values * 60.0  # sec per km
        offset_b = dfB.get("start_offset", pd.Series([0]*len(dfB))).fillna(0).values.astype(float)
        arrival_times_b = start_b + offset_b + pace_b * km_b
        
        # Check for temporal overlaps at this point
        # A temporal overlap occurs when a runner from one event arrives
        # at the same time (within a small tolerance) as a runner from another event
        tolerance_seconds = TEMPORAL_OVERLAP_TOLERANCE_SECONDS  # tolerance for "same time"
        
        for time_a in arrival_times_a:
            for time_b in arrival_times_b:
                if abs(time_a - time_b) <= tolerance_seconds:
                    # Found actual temporal overlap! Return this as convergence point
                    return round(km_point, 2)
    
    # No temporal overlaps found anywhere in the segment
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


def calculate_convergence_zone_overlaps(
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
) -> Tuple[int, int, List[str], List[str], int, int]:
    """
    Calculate the number of overlapping runners within the convergence zone,
    projecting both events onto a common segment-local axis.
    """
    if df_a.empty or df_b.empty:
        return 0, 0, [], [], 0, 0
    
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return 0, 0, [], [], 0, 0

    # Map cp (in event A's ruler) to local fraction
    s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
    s_cp = max(0.0, min(1.0, s_cp))
    
    # Calculate conflict zone around convergence point
    conflict_length_km = conflict_length_m / 1000.0  # Convert meters to km
    conflict_half_km = conflict_length_km / 2.0
    
    # Define conflict zone boundaries
    cp_km_a_start = max(from_km_a, cp_km - conflict_half_km)
    cp_km_a_end = min(to_km_a, cp_km + conflict_half_km)
    
    # Map back to local fractions
    s_start = (cp_km_a_start - from_km_a) / max(len_a, 1e-9)
    s_end = (cp_km_a_end - from_km_a) / max(len_a, 1e-9)
    s_start = max(0.0, min(1.0, s_start))
    s_end = max(0.0, min(1.0, s_end))

    # Convert to each event's km for conflict zone
    cp_km_a_start = from_km_a + s_start * len_a
    cp_km_a_end = from_km_a + s_end * len_a

    cp_km_b_start = from_km_b + s_start * len_b
    cp_km_b_end = from_km_b + s_end * len_b

    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0

    # Vectorized times for conflict zone
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    time_enter_a = start_a + offset_a + pace_a * cp_km_a_start
    time_exit_a  = start_a + offset_a + pace_a * cp_km_a_end

    pace_b = df_b["pace"].values * 60.0
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    time_enter_b = start_b + offset_b + pace_b * cp_km_b_start
    time_exit_b  = start_b + offset_b + pace_b * cp_km_b_end

    a_bibs = set()
    b_bibs = set()
    unique_pairs = set()

    # Pairwise overlap detection
    for i, (enter_a, exit_a) in enumerate(zip(time_enter_a, time_exit_a)):
        for j, (enter_b, exit_b) in enumerate(zip(time_enter_b, time_exit_b)):
            overlap_start = max(enter_a, enter_b)
            overlap_end = min(exit_a, exit_b)
            overlap_duration = overlap_end - overlap_start
            if overlap_duration >= min_overlap_duration:
                a_bib = df_a.iloc[i]["runner_id"]
                b_bib = df_b.iloc[j]["runner_id"]
                a_bibs.add(a_bib)
                b_bibs.add(b_bib)
                # Track unique pairs (ordered to avoid duplicates)
                unique_pairs.add((a_bib, b_bib))

    # Calculate participants involved (union of all runners who had encounters)
    participants_involved = len(a_bibs.union(b_bibs))
    unique_encounters = len(unique_pairs)

    return len(a_bibs), len(b_bibs), list(a_bibs), list(b_bibs), unique_encounters, participants_involved


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
    
    if pace_diff < 1.0:
        analysis.append("   • Similar pace groups: Runners likely to stay together")
    elif pace_diff < 2.0:
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
    """
    # Load data
    pace_df = load_pace_csv(pace_csv)
    segments_df = load_segments_csv(segments_csv)
    
    # Process ALL segments (not just overtake_flag = 'y')
    all_segments = segments_df.copy()
    
    results = {
        "ok": True,
        "engine": "temporal_flow",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_times": start_times,
        "min_overlap_duration": min_overlap_duration,
        "conflict_length_m": conflict_length_m,
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
            "flow_type": segment.get("flow-type", ""),
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
            count_a, count_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps(
                df_a, df_b, event_a, event_b, start_times,
                cp_km, from_km_a, to_km_a, from_km_b, to_km_b, min_overlap_duration, conflict_length_m
            )
            
            # Calculate actual conflict zone boundaries for reporting
            conflict_length_km = conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0
            conflict_start = max(from_km_a, cp_km - conflict_half_km)
            conflict_end = min(to_km_a, cp_km + conflict_half_km)
            
            segment_result.update({
                "overtaking_a": count_a,
                "overtaking_b": count_b,
                "sample_a": bibs_a[:10],  # First 10 for samples
                "sample_b": bibs_b[:10],
                "convergence_zone_start": conflict_start,
                "convergence_zone_end": conflict_end,
                "conflict_length_m": conflict_length_m,
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
            
            # Get the segment data from segments_df
            seg_id = segment_result["seg_id"]
            segment_row = segments_df[segments_df["seg_id"] == seg_id].iloc[0]
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
            s_cp = max(0.0, min(1.0, s_cp))
            
            # Calculate event B distance at convergence point
            cp_km_b = from_km_b + s_cp * len_b
            
            # Format: Segment Converge Point: [position within segment] ([total distance Event A], [total distance Event B])
            event_a = segment.get('event_a', 'A')
            event_b = segment.get('event_b', 'B')
            narrative.append(f"🎯 Segment Converge Point: {s_cp:.2f}km ({cp_km:.1f}km {event_a}, {cp_km_b:.1f}km {event_b})")
            
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
    s_start = max(0.0, min(1.0, s_start))
    s_end = max(0.0, min(1.0, s_end))
    
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

