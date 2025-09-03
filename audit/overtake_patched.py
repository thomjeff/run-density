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
    Calculate convergence point using a segment-local axis so events with
    different course km still align on the same physical geometry.

    Returns the kilometer mark (in event A's km ruler) where overtaking becomes
    possible, or None if no convergence within this segment.
    """
    if dfA.empty or dfB.empty:
        return None
    
    # Segment lengths in each event's own ruler
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return None

    # Get absolute start times in seconds
    start_a = start_times.get(eventA, 0) * 60.0
    start_b = start_times.get(eventB, 0) * 60.0

    # Helper to solve for s (local fraction 0..1) for a given pace pair and optional offsets
    def solve_s(a_pace_min_per_km: float, b_pace_min_per_km: float, off_a: float = 0.0, off_b: float = 0.0) -> Optional[float]:
        a_sec = a_pace_min_per_km * 60.0
        b_sec = b_pace_min_per_km * 60.0
        # start_a + off_a + a_sec*(from_km_a + s*len_a) = start_b + off_b + b_sec*(from_km_b + s*len_b)
        denom = (a_sec * len_a) - (b_sec * len_b)
        if abs(denom) < 1e-9:
            return None
        numer = (start_b + off_b) - (start_a + off_a) + (b_sec * from_km_b) - (a_sec * from_km_a)
        s = numer / denom
        if 0.0 <= s <= 1.0:
            return float(s)
        return None

    convergence_s: List[float] = []

    # Representative pace sampling (quantiles) for both events
    q = [0.05, 0.25, 0.5, 0.75, 0.95]
    paces_a = dfA["pace"].quantile(q).values if len(dfA) else np.array([])
    paces_b = dfB["pace"].quantile(q).values if len(dfB) else np.array([])

    for pa in paces_a:
        for pb in paces_b:
            s = solve_s(pa, pb, 0.0, 0.0)
            if s is not None:
                convergence_s.append(s)

    # Precise sampling using actual runners incl. offsets
    if len(dfA) and len(dfB):
        sample_a = dfA.sample(min(20, len(dfA)), random_state=42)
        sample_b = dfB.sample(min(20, len(dfB)), random_state=42)
        for _, ra in sample_a.iterrows():
            for _, rb in sample_b.iterrows():
                s = solve_s(float(ra["pace"]), float(rb["pace"]), float(ra.get("start_offset", 0.0)), float(rb.get("start_offset", 0.0)))
                if s is not None:
                    convergence_s.append(s)

    if not convergence_s:
        return None

    # Choose the s* closest to midpoint for stability
    s_star = min(convergence_s, key=lambda s: abs(s - 0.5))

    # Return convergence point in event A's km ruler for compatibility
    cp_km_a = from_km_a + s_star * len_a
    return round(cp_km_a, 2)


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
) -> Tuple[int, int, List[str], List[str]]:
    """
    Calculate the number of overlapping runners within the convergence zone,
    projecting both events onto a common segment-local axis.
    """
    if df_a.empty or df_b.empty:
        return 0, 0, [], []
    
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return 0, 0, [], []

    # Map cp (in event A's ruler) to local fraction and set zone end at s=1.0
    s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
    s_cp = max(0.0, min(1.0, s_cp))
    s_end = 1.0

    # Convert to each event's km
    cp_km_a = from_km_a + s_cp * len_a
    end_km_a = from_km_a + s_end * len_a

    cp_km_b = from_km_b + s_cp * len_b
    end_km_b = from_km_b + s_end * len_b

    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0

    # Vectorized times
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    time_enter_a = start_a + offset_a + pace_a * cp_km_a
    time_exit_a  = start_a + offset_a + pace_a * end_km_a

    pace_b = df_b["pace"].values * 60.0
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    time_enter_b = start_b + offset_b + pace_b * cp_km_b
    time_exit_b  = start_b + offset_b + pace_b * end_km_b

    a_bibs = set()
    b_bibs = set()

    # Broadcasted overlap
    for i, (enter_a, exit_a) in enumerate(zip(time_enter_a, time_exit_a)):
        overlap_start = np.maximum(enter_a, time_enter_b)
        overlap_end   = np.minimum(exit_a,  time_exit_b)
        valid = (overlap_end > overlap_start) & ((overlap_end - overlap_start) >= min_overlap_duration)
        if np.any(valid):
            a_bibs.add(df_a.iloc[i]["runner_id"])
            idxs = np.where(valid)[0]
            for j in idxs:
                b_bibs.add(df_b.iloc[j]["runner_id"])

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
        
        # Calculate convergence point (in event A km ruler)
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
            # Calculate overtaking runners in convergence zone using local-axis mapping
            count_a, count_b, bibs_a, bibs_b = calculate_convergence_zone_overlaps(
                df_a, df_b, event_a, event_b, start_times,
                cp_km, from_km_a, to_km_a, from_km_b, to_km_b, min_overlap_duration
            )
            
            segment_result.update({
                "overtaking_a": count_a,
                "overtaking_b": count_b,
                "sample_a": bibs_a[:10],  # First 10 for samples
                "sample_b": bibs_b[:10],
                "convergence_zone_start": cp_km,
                "convergence_zone_end": to_km_a  # in event A ruler; narrative will clarify
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
        hh = int(start_min // 60)
        mm = int(start_min % 60)
        narrative.append(f"   {event}: {hh:02d}:{mm:02d}:00")
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
            narrative.append(f"🎯 Convergence Point (event A km): {segment['convergence_point']}km")
            narrative.append(f"📊 Convergence Zone: {segment.get('convergence_zone_start','')}km to {segment.get('convergence_zone_end','')}km (event A ruler)")
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
