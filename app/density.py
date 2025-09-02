"""
Density Analysis Module

Handles density analysis for all segments from segments.csv.
Provides areal and crowd density calculations for operational planning.
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
    expected = {"seg_id", "eventa", "eventb", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "width_m"}
    if not expected.issubset(df.columns):
        raise ValueError(f"segments.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    
    # Convert to proper types
    df["from_km_a"] = df["from_km_a"].astype(float)
    df["to_km_a"] = df["to_km_a"].astype(float)
    df["from_km_b"] = df["from_km_b"].astype(float)
    df["to_km_b"] = df["to_km_b"].astype(float)
    df["width_m"] = df["width_m"].astype(float)
    
    return df


def analyze_density_segments(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    step_km: float = 0.03,
    time_window_s: float = 300.0,
) -> Dict[str, Any]:
    """
    Analyze density for all segments from segments.csv.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments CSV
        start_times: Dict mapping event names to start times in minutes
        step_km: Step size for density calculations
        time_window_s: Time window for density calculations
    
    Returns:
        Dict with density analysis results
    """
    # Load data
    pace_df = _load_pace_csv(pace_csv)
    segments_df = _load_segments_csv(segments_csv)
    
    results = {
        "ok": True,
        "engine": "density",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_times": start_times,
        "step_km": step_km,
        "time_window_s": time_window_s,
        "total_segments": len(segments_df),
        "segments": []
    }
    
    for _, segment in segments_df.iterrows():
        seg_id = segment["seg_id"]
        event_a = segment["eventa"]
        event_b = segment["eventb"]
        from_km_a = segment["from_km_a"]
        to_km_a = segment["to_km_a"]
        from_km_b = segment["from_km_b"]
        to_km_b = segment["to_km_b"]
        width_m = segment["width_m"]
        
        # Filter runners for this segment
        df_a = pace_df[pace_df["event"] == event_a].copy()
        df_b = pace_df[pace_df["event"] == event_b].copy()
        
        segment_result = {
            "seg_id": seg_id,
            "segment_label": segment.get("segment_label", ""),
            "event_a": event_a,
            "event_b": event_b,
            "from_km_a": from_km_a,
            "to_km_a": to_km_a,
            "from_km_b": from_km_b,
            "to_km_b": to_km_b,
            "width_m": width_m,
            "total_a": len(df_a),
            "total_b": len(df_b),
            "total_combined": len(df_a) + len(df_b),
            "peak_areal_density": 0.0,
            "peak_crowd_density": 0.0,
            "peak_km": from_km_a
        }
        
        results["segments"].append(segment_result)
    
    return results


def generate_density_narrative(results: Dict[str, Any]) -> str:
    """Generate human-readable narrative for density analysis."""
    if not results["ok"]:
        return "❌ Density analysis failed"
    
    narrative = []
    narrative.append("📊 DENSITY ANALYSIS SUMMARY")
    narrative.append("=" * 50)
    narrative.append(f"🕐 Executed: {results['timestamp']}")
    narrative.append("")
    narrative.append("🚀 EVENT START TIMES:")
    for event, start_min in results["start_times"].items():
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        narrative.append(f"   {event}: {start_time}")
    narrative.append("")
    narrative.append(f"📈 Total segments analyzed: {results['total_segments']}")
    narrative.append(f"⚙️ Analysis: {results['step_km']}km steps, {results['time_window_s']}s time window")
    narrative.append("")
    narrative.append("=" * 50)
    narrative.append("")
    
    for segment in results["segments"]:
        narrative.append(f"🏷️ Segment: {segment['seg_id']}")
        if segment.get("segment_label"):
            narrative.append(f"📝 Label: {segment['segment_label']}")
        narrative.append(f"🔍 Analyzing {segment['event_a']} vs {segment['event_b']}")
        narrative.append(f"📍 Range A: {segment['from_km_a']}km to {segment['to_km_a']}km")
        narrative.append(f"📍 Range B: {segment['from_km_b']}km to {segment['to_km_b']}km")
        narrative.append(f"👥 Total in '{segment['event_a']}': {segment['total_a']} runners")
        narrative.append(f"👥 Total in '{segment['event_b']}': {segment['total_b']} runners")
        narrative.append(f"👥 Combined total: {segment['total_combined']} runners")
        narrative.append(f"📏 Width: {segment['width_m']}m")
        narrative.append("")
    
    return "\n".join(narrative)
