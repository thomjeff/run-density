"""
Report Module

Combines density and overtake analysis results into unified reports.
Provides both JSON and CSV export capabilities for UI consumption.
"""

from __future__ import annotations
import time
from typing import Dict, Optional, Any, List
import pandas as pd
from datetime import datetime

try:
    from .density import analyze_density_segments
    from .temporal_flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
    from .constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS
except ImportError:
    from density import analyze_density_segments
    from temporal_flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
    from constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS


def generate_combined_report(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    step_km: float = DEFAULT_STEP_KM,
    time_window_s: float = DEFAULT_TIME_WINDOW_SECONDS,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    include_density: bool = True,
    include_overtake: bool = True,
) -> Dict[str, Any]:
    """
    Generate a combined report with both density and overtake analysis.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments CSV
        start_times: Dict mapping event names to start times in minutes
        step_km: Step size for density calculations
        time_window_s: Time window for density calculations
        min_overlap_duration: Minimum overlap duration for overtake analysis
        include_density: Whether to include density analysis
        include_overtake: Whether to include overtake analysis
    
    Returns:
        Dict with combined analysis results
    """
    results = {
        "ok": True,
        "engine": "combined_report",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_times": start_times,
        "parameters": {
            "step_km": step_km,
            "time_window_s": time_window_s,
            "min_overlap_duration": min_overlap_duration
        },
        "density_analysis": None,
        "overtake_analysis": None,
        "summary": {
            "total_segments": 0,
            "density_segments": 0,
            "overtake_segments": 0,
            "segments_with_convergence": 0
        }
    }
    
    # Run density analysis if requested
    if include_density:
        try:
            density_results = analyze_density_segments(
                pace_csv, segments_csv, start_times, step_km, time_window_s
            )
            results["density_analysis"] = density_results
            results["summary"]["density_segments"] = density_results["total_segments"]
            results["summary"]["total_segments"] = density_results["total_segments"]
        except Exception as e:
            results["density_analysis"] = {"ok": False, "error": str(e)}
    
    # Run overtake analysis if requested
    if include_overtake:
        try:
            overtake_results = analyze_temporal_flow_segments(
                pace_csv, segments_csv, start_times, min_overlap_duration, DEFAULT_CONFLICT_LENGTH_METERS
            )
            results["overtake_analysis"] = overtake_results
            results["summary"]["overtake_segments"] = overtake_results["total_segments"]
            results["summary"]["segments_with_convergence"] = overtake_results["segments_with_convergence"]
        except Exception as e:
            results["overtake_analysis"] = {"ok": False, "error": str(e)}
    
    return results


def generate_combined_narrative(results: Dict[str, Any]) -> str:
    """Generate human-readable narrative for combined analysis."""
    if not results["ok"]:
        return "❌ Combined analysis failed"
    
    narrative = []
    narrative.append("📊 COMBINED ANALYSIS REPORT")
    narrative.append("=" * 60)
    narrative.append(f"🕐 Executed: {results['timestamp']}")
    narrative.append("")
    narrative.append("🚀 EVENT START TIMES:")
    for event, start_min in results["start_times"].items():
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        narrative.append(f"   {event}: {start_time}")
    narrative.append("")
    narrative.append("📈 SUMMARY:")
    narrative.append(f"   Total segments: {results['summary']['total_segments']}")
    narrative.append(f"   Density segments: {results['summary']['density_segments']}")
    narrative.append(f"   Overtake segments: {results['summary']['overtake_segments']}")
    narrative.append(f"   Segments with convergence: {results['summary']['segments_with_convergence']}")
    narrative.append("")
    narrative.append("⚙️ PARAMETERS:")
    params = results["parameters"]
    narrative.append(f"   Step size: {params['step_km']}km")
    narrative.append(f"   Time window: {params['time_window_s']}s")
    narrative.append(f"   Min overlap duration: {params['min_overlap_duration']}s")
    narrative.append("")
    narrative.append("=" * 60)
    narrative.append("")
    
    # Add density analysis if available
    if results.get("density_analysis") and results["density_analysis"].get("ok"):
        narrative.append("📊 DENSITY ANALYSIS")
        narrative.append("-" * 30)
        density_narrative = generate_density_narrative(results["density_analysis"])
        # Skip the header since we already have one
        density_lines = density_narrative.split('\n')[1:]
        narrative.extend(density_lines)
        narrative.append("")
    
    # Add overtake analysis if available
    if results.get("overtake_analysis") and results["overtake_analysis"].get("ok"):
        narrative.append("🎯 OVERTAKE ANALYSIS")
        narrative.append("-" * 30)
        overtake_narrative = generate_temporal_flow_narrative(results["overtake_analysis"])
        # Skip the header since we already have one
        overtake_lines = overtake_narrative.split('\n')[1:]
        narrative.extend(overtake_lines)
        narrative.append("")
    
    return "\n".join(narrative)


def export_combined_csv(results: Dict[str, Any], output_path: str) -> None:
    """Export combined analysis results to CSV."""
    import csv
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"combined_analysis_{timestamp}.csv"
    full_path = f"{output_path}/{filename}"
    
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow([
            "seg_id", "segment_label", "event_a", "event_b",
            "from_km_a", "to_km_a", "from_km_b", "to_km_b", "width_m",
            "total_a", "total_b", "total_combined",
            "peak_areal_density", "peak_areal_km",
            "peak_crowd_density", "peak_crowd_km",
            "convergence_point", "has_convergence",
            "overtaking_a", "overtaking_b",
            "convergence_zone_start", "convergence_zone_end",
            "analysis_timestamp"
        ])
        
        # Get all segments from density analysis (comprehensive list)
        density_segments = {}
        if results.get("density_analysis") and results["density_analysis"].get("ok"):
            for segment in results["density_analysis"]["segments"]:
                density_segments[segment["seg_id"]] = segment
        
        # Get overtake data
        overtake_segments = {}
        if results.get("overtake_analysis") and results["overtake_analysis"].get("ok"):
            for segment in results["overtake_analysis"]["segments"]:
                overtake_segments[segment["seg_id"]] = segment
        
        # Write data rows
        for seg_id, density_data in density_segments.items():
            overtake_data = overtake_segments.get(seg_id, {})
            
            writer.writerow([
                density_data["seg_id"],
                density_data.get("segment_label", ""),
                density_data["event_a"],
                density_data["event_b"],
                density_data["from_km_a"],
                density_data["to_km_a"],
                density_data["from_km_b"],
                density_data["to_km_b"],
                density_data["width_m"],
                density_data["total_a"],
                density_data["total_b"],
                density_data["total_combined"],
                density_data.get("peak_areal_density", ""),
                density_data.get("peak_areal_km", ""),
                density_data.get("peak_crowd_density", ""),
                density_data.get("peak_crowd_km", ""),
                overtake_data.get("convergence_point", ""),
                overtake_data.get("has_convergence", False),
                overtake_data.get("overtaking_a", 0),
                overtake_data.get("overtaking_b", 0),
                overtake_data.get("convergence_zone_start", ""),
                overtake_data.get("convergence_zone_end", ""),
                results["timestamp"]
            ])
    
    print(f"📊 Combined analysis exported to: {full_path}")


def get_segment_summary(results: Dict[str, Any]) -> Dict[str, Any]:
    """Get a summary of key segments for quick reference."""
    summary = {
        "total_segments": results["summary"]["total_segments"],
        "density_segments": results["summary"]["density_segments"],
        "overtake_segments": results["summary"]["overtake_segments"],
        "segments_with_convergence": results["summary"]["segments_with_convergence"],
        "key_segments": []
    }
    
    # Find segments with convergence (high priority)
    if results.get("overtake_analysis") and results["overtake_analysis"].get("ok"):
        for segment in results["overtake_analysis"]["segments"]:
            if segment.get("has_convergence"):
                summary["key_segments"].append({
                    "seg_id": segment["seg_id"],
                    "segment_label": segment.get("segment_label", ""),
                    "event_a": segment["event_a"],
                    "event_b": segment["event_b"],
                    "convergence_point": segment.get("convergence_point"),
                    "overtaking_a": segment.get("overtaking_a", 0),
                    "overtaking_b": segment.get("overtaking_b", 0),
                    "priority": "high"
                })
    
    # Find segments with high density (medium priority)
    if results.get("density_analysis") and results["density_analysis"].get("ok"):
        for segment in results["density_analysis"]["segments"]:
            if segment.get("total_combined", 0) > 100:  # High runner count
                summary["key_segments"].append({
                    "seg_id": segment["seg_id"],
                    "segment_label": segment.get("segment_label", ""),
                    "event_a": segment["event_a"],
                    "event_b": segment["event_b"],
                    "total_combined": segment.get("total_combined", 0),
                    "priority": "medium"
                })
    
    return summary
