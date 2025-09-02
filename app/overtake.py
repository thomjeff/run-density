"""
Overtake Analysis Module

Handles convergence zone analysis for segments where overtaking is possible.
Only processes segments with overtake_flag = 'y' from segments.csv.
"""

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


def _load_segments_csv(url_or_path: str) -> pd.DataFrame:
    """Load and validate segments CSV."""
    df = pd.read_csv(url_or_path)
    df.columns = [c.lower() for c in df.columns]
    
    # Ensure required columns exist
    expected = {"seg_id", "eventa", "eventb", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "overtake_flag"}
    if not expected.issubset(df.columns):
        raise ValueError(f"segments.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    
    # Convert to proper types
    df["from_km_a"] = df["from_km_a"].astype(float)
    df["to_km_a"] = df["to_km_a"].astype(float)
    df["from_km_b"] = df["from_km_b"].astype(float)
    df["to_km_b"] = df["to_km_b"].astype(float)
    
    return df


def _arrival_time_sec(start_min: float, start_offset_sec: int, km: float, pace_min_per_km: float) -> float:
    """Calculate arrival time at km mark including start offset."""
    return start_min * 60.0 + start_offset_sec + pace_min_per_km * 60.0 * km


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
    step_km: float = 0.01,
) -> Optional[float]:
    """
    Calculate convergence point dynamically based on runner timing and pace data.
    
    A convergence point is where overtaking becomes most likely to occur within a segment.
    This is determined by:
    1. Checking if overtaking is physically possible (faster event can catch slower event)
    2. Finding the optimal point within the segment where overtaking is most likely
    
    Returns the kilometer mark where overtaking becomes possible, or None if no convergence.
    """
    if dfA.empty or dfB.empty:
        return None
    
    # Get start times in seconds
    start_a = start_times.get(eventA, 0) * 60.0  # Convert minutes to seconds
    start_b = start_times.get(eventB, 0) * 60.0
    
    # Calculate median paces to determine which event is generally faster
    median_pace_a = dfA["pace"].median()
    median_pace_b = dfB["pace"].median()
    
    # Find the overlap segment where both events run
    segment_start = max(from_km_a, from_km_b)
    segment_end = min(to_km_a, to_km_b)
    
    if segment_start >= segment_end:
        # No overlapping segment
        return None
    
    # Check if overtaking is possible by looking at the pace relationship
    # and start time differences
    time_diff = abs(start_a - start_b)
    
    # If events start at the same time, no overtaking possible
    if time_diff < 60:  # Less than 1 minute difference
        return None
    
    # Determine which event can overtake based on start times
    # Generally: later starting events overtake earlier starting events
    # (later start + any pace can catch up to earlier start + slower pace)
    
    if start_a > start_b:
        # Event A starts later - Event A can overtake Event B
        # Use median paces as representative values for convergence calculation
        faster_pace = median_pace_a  # Later starting event
        slower_pace = median_pace_b  # Earlier starting event
        start_faster = start_a
        start_slower = start_b
    elif start_b > start_a:
        # Event B starts later - Event B can overtake Event A
        # Use median paces as representative values for convergence calculation
        faster_pace = median_pace_b  # Later starting event
        slower_pace = median_pace_a  # Earlier starting event
        start_faster = start_b
        start_slower = start_a
    else:
        # Same start time, no overtaking possible
        return None
    
    # Calculate theoretical convergence point
    # Later starting event (start_faster) catches up to earlier starting event (start_slower)
    # Time for later runner: start_faster + faster_pace * km
    # Time for earlier runner: start_slower + slower_pace * km
    # Convergence: start_faster + faster_pace * km = start_slower + slower_pace * km
    # Solving: km = (start_slower - start_faster) / (faster_pace - slower_pace)
    
    # Note: faster_pace is the pace of the later starting event (which can overtake)
    # slower_pace is the pace of the earlier starting event (which gets overtaken)
    pace_diff_sec = (slower_pace - faster_pace) * 60.0  # Convert to seconds per km
    
    # If the later starting event is actually faster (lower pace), overtaking is definitely possible
    # If the later starting event is slower (higher pace), overtaking may still be possible
    # due to the time advantage from starting later
    if pace_diff_sec <= 0:
        # Later starting event is faster or same pace - overtaking definitely possible
        # Use a small positive pace difference for calculation
        pace_diff_sec = 1.0  # 1 second per km difference
    
    theoretical_convergence = (start_slower - start_faster) / pace_diff_sec
    
    # If theoretical convergence is within the segment, use it
    if segment_start <= theoretical_convergence <= segment_end:
        return round(theoretical_convergence, 2)
    
    # If theoretical convergence is before the segment, use segment start
    elif theoretical_convergence < segment_start:
        return round(segment_start, 2)
    
    # If theoretical convergence is after the segment, use segment midpoint
    # (as overtaking is most likely to occur in the middle of the segment)
    else:
        return round((segment_start + segment_end) / 2, 2)


def calculate_convergence_zone_overlaps(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    to_km_a: float,
    to_km_b: float,
    min_overlap_duration: float = 5.0,
) -> Tuple[int, int, List[str], List[str]]:
    """
    Calculate the actual number of overlapping runners within the convergence zone.
    
    Uses vectorized operations for efficient calculation.
    """
    if df_a.empty or df_b.empty:
        return 0, 0, [], []
    
    # Get start times in seconds
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Use the end of the overlapping segment
    zone_end = min(to_km_a, to_km_b)
    
    # Vectorized calculations for all runners at once
    # Event A runners
    pace_a = df_a["pace"].values  # minutes per km
    offset_a = df_a["start_offset"].values
    time_enter_a = start_a + offset_a + (pace_a * 60.0 * cp_km)
    time_exit_a = start_a + offset_a + (pace_a * 60.0 * zone_end)
    
    # Event B runners
    pace_b = df_b["pace"].values  # minutes per km
    offset_b = df_b["start_offset"].values
    time_enter_b = start_b + offset_b + (pace_b * 60.0 * cp_km)
    time_exit_b = start_b + offset_b + (pace_b * 60.0 * zone_end)
    
    # Track overlapping runners
    a_bibs = set()
    b_bibs = set()
    
    # Use broadcasting to check all pairs efficiently
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


def analyze_overtake_segments(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = 5.0,
) -> Dict[str, Any]:
    """
    Analyze all segments with overtake_flag = 'y' for convergence zones and overtaking.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments CSV
        start_times: Dict mapping event names to start times in minutes
        min_overlap_duration: Minimum overlap duration in seconds
    
    Returns:
        Dict with overtake analysis results
    """
    # Load data
    pace_df = _load_pace_csv(pace_csv)
    segments_df = _load_segments_csv(segments_csv)
    
    # Filter to overtake segments only
    overtake_segments = segments_df[segments_df["overtake_flag"] == "y"].copy()
    
    results = {
        "ok": True,
        "engine": "overtake",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_times": start_times,
        "min_overlap_duration": min_overlap_duration,
        "total_segments": len(overtake_segments),
        "segments_with_convergence": 0,
        "segments": []
    }
    
    for _, segment in overtake_segments.iterrows():
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
        
        # Calculate convergence point
        cp_km = calculate_convergence_point(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b
        )
        
        segment_result = {
            "seg_id": seg_id,
            "segment_label": segment.get("segment_label", ""),
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
            "sample_b": []
        }
        
        if cp_km is not None:
            # Calculate overtaking runners in convergence zone
            count_a, count_b, bibs_a, bibs_b = calculate_convergence_zone_overlaps(
                df_a, df_b, event_a, event_b, start_times,
                cp_km, to_km_a, to_km_b, min_overlap_duration
            )
            
            segment_result.update({
                "overtaking_a": count_a,
                "overtaking_b": count_b,
                "sample_a": bibs_a[:10],  # First 10 for samples
                "sample_b": bibs_b[:10],
                "convergence_zone_start": cp_km,
                "convergence_zone_end": min(to_km_a, to_km_b)
            })
            
            results["segments_with_convergence"] += 1
        
        results["segments"].append(segment_result)
    
    return results


def generate_overtake_narrative(results: Dict[str, Any]) -> str:
    """Generate human-readable narrative for overtake analysis."""
    if not results["ok"]:
        return "❌ Overtake analysis failed"
    
    narrative = []
    narrative.append("🎯 OVERTAKE ANALYSIS SUMMARY")
    narrative.append("=" * 50)
    narrative.append(f"🕐 Executed: {results['timestamp']}")
    narrative.append("")
    narrative.append("🚀 EVENT START TIMES:")
    for event, start_min in results["start_times"].items():
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        narrative.append(f"   {event}: {start_time}")
    narrative.append("")
    narrative.append(f"📈 Total overtake segments: {results['total_segments']}")
    narrative.append(f"🎯 Segments with convergence: {results['segments_with_convergence']}")
    narrative.append(f"⚙️ Analysis: {results['min_overlap_duration']}s min overlap duration")
    narrative.append("")
    narrative.append("=" * 50)
    narrative.append("")
    
    for segment in results["segments"]:
        narrative.append(f"🏷️ Segment: {segment['seg_id']}")
        if segment.get("segment_label"):
            narrative.append(f"📝 Label: {segment['segment_label']}")
        narrative.append(f"🔍 Checking {segment['event_a']} vs {segment['event_b']}")
        narrative.append(f"📍 Range A: {segment['from_km_a']}km to {segment['to_km_a']}km")
        narrative.append(f"📍 Range B: {segment['from_km_b']}km to {segment['to_km_b']}km")
        narrative.append(f"👥 Total in '{segment['event_a']}': {segment['total_a']} runners")
        narrative.append(f"👥 Total in '{segment['event_b']}': {segment['total_b']} runners")
        
        if segment["has_convergence"]:
            narrative.append(f"🎯 Convergence Point: {segment['convergence_point']}km")
            narrative.append(f"📊 Convergence Zone: {segment['convergence_zone_start']}km to {segment['convergence_zone_end']}km")
            narrative.append(f"👥 Overtaking A ({segment['event_a']}): {segment['overtaking_a']}")
            narrative.append(f"👥 Overtaking B ({segment['event_b']}): {segment['overtaking_b']}")
            narrative.append(f"🏃‍♂️ Sample A: {format_bib_range(segment['sample_a'])}")
            narrative.append(f"🏃‍♂️ Sample B: {format_bib_range(segment['sample_b'])}")
        else:
            narrative.append("❌ No convergence zone detected")
        
        narrative.append("")
    
    return "\n".join(narrative)


def export_overtake_csv(results: Dict[str, Any], output_path: str) -> None:
    """Export overtake analysis results to CSV."""
    import csv
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"overtake_analysis_{timestamp}.csv"
    full_path = f"{output_path}/{filename}"
    
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow([
            "seg_id", "segment_label", "event_a", "event_b",
            "from_km_a", "to_km_a", "from_km_b", "to_km_b",
            "convergence_point", "has_convergence",
            "total_a", "total_b", "overtaking_a", "overtaking_b",
            "convergence_zone_start", "convergence_zone_end",
            "sample_a", "sample_b", "analysis_timestamp"
        ])
        
        # Data rows
        for segment in results["segments"]:
            writer.writerow([
                segment["seg_id"],
                segment.get("segment_label", ""),
                segment["event_a"],
                segment["event_b"],
                segment["from_km_a"],
                segment["to_km_a"],
                segment["from_km_b"],
                segment["to_km_b"],
                segment.get("convergence_point", ""),
                segment["has_convergence"],
                segment["total_a"],
                segment["total_b"],
                segment["overtaking_a"],
                segment["overtaking_b"],
                segment.get("convergence_zone_start", ""),
                segment.get("convergence_zone_end", ""),
                format_bib_range(segment["sample_a"]),
                format_bib_range(segment["sample_b"]),
                results["timestamp"]
            ])
    
    print(f"📊 Overtake analysis exported to: {full_path}")
