"""
Temporal Flow Report Module

Generates comprehensive temporal flow analysis reports including convergence points,
overtaking patterns, and flow analysis. This module provides reusable functions for 
generating temporal flow reports that can be called by the API or other modules.
"""

from __future__ import annotations
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os

from .temporal_flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
from .constants import DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS


def generate_temporal_flow_report(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    output_dir: str = "reports/analysis"
) -> Dict[str, Any]:
    """
    Generate a comprehensive temporal flow analysis report.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments CSV
        start_times: Dict mapping event names to start times in minutes
        min_overlap_duration: Minimum overlap duration for analysis
        conflict_length_m: Conflict length in meters
        output_dir: Directory to save the report
    
    Returns:
        Dict with analysis results and report path
    """
    print("🔍 Starting temporal flow analysis...")
    
    # Run temporal flow analysis
    results = analyze_temporal_flow_segments(
        pace_csv, segments_csv, start_times, min_overlap_duration, conflict_length_m
    )
    
    if not results.get("ok", False):
        return {
            "ok": False,
            "error": "Temporal flow analysis failed",
            "details": results.get("error", "Unknown error")
        }
    
    # Generate markdown report
    report_content = generate_markdown_report(results, start_times)
    
    # Save report
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_Temporal_Flow_Report.md"
    report_path = os.path.join(output_dir, filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📊 Temporal flow report saved to: {report_path}")

    # Also generate CSV
    export_temporal_flow_csv(results, output_dir)
    
    return {
        "ok": True,
        "report_path": report_path,
        "analysis_results": results,
        "timestamp": timestamp
    }


def generate_markdown_report(
    results: Dict[str, Any], 
    start_times: Dict[str, float]
) -> str:
    """Generate markdown content for the temporal flow report."""
    
    # Event start times for ordering
    event_order = sorted(start_times.items(), key=lambda x: x[1])
    
    # Build report content
    content = []
    
    # Header
    content.append("# Temporal Flow Analysis Report")
    content.append("")
    content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append(f"**Analysis Engine:** {results.get('engine', 'temporal_flow')}")
    content.append(f"**Analysis Period:** {results.get('timestamp', 'N/A')}")
    content.append(f"**Min Overlap Duration:** {results.get('min_overlap_duration', 5.0)} seconds")
    content.append(f"**Conflict Length:** {results.get('conflict_length_m', 100.0)} meters")
    content.append(f"**Total Segments:** {results.get('total_segments', 0)}")
    content.append(f"**Segments with Convergence:** {results.get('segments_with_convergence', 0)}")
    content.append("")
    
    # Legend
    content.append("## Legend")
    content.append("")
    content.append("- **Convergence Point**: Location where runners from different events first overlap in time")
    content.append("- **Overtaking**: Count of runners from one event overtaking another")
    content.append("- **Flow Type**: Type of flow pattern (overtake, merge, diverge)")
    content.append("- **Convergence Zone**: Time window when convergence occurs")
    content.append("- **Deep Dive Analysis**: Detailed analysis of convergence patterns")
    content.append("")
    
    # Event start times
    content.append("## Event Start Times")
    content.append("")
    content.append("| Event | Start Time |")
    content.append("|-------|------------|")
    for event, start_min in event_order:
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        content.append(f"| {event} | {start_time} |")
    content.append("")
    
    # Summary statistics
    content.extend(generate_summary_section(results))
    content.append("")
    
    # Process each segment
    for segment in results.get("segments", []):
        content.extend(generate_segment_section(segment, event_order))
        content.append("")
        content.append("---")
        content.append("")
    
    return "\n".join(content)


def generate_summary_section(results: Dict[str, Any]) -> List[str]:
    """Generate summary statistics section."""
    content = []
    
    content.append("## Summary Statistics")
    content.append("")
    
    # Overall statistics
    total_segments = results.get("total_segments", 0)
    convergence_segments = results.get("segments_with_convergence", 0)
    convergence_rate = (convergence_segments / total_segments * 100) if total_segments > 0 else 0
    
    content.append("| Metric | Value |")
    content.append("|--------|-------|")
    content.append(f"| Total Segments | {total_segments} |")
    content.append(f"| Segments with Convergence | {convergence_segments} |")
    content.append(f"| Convergence Rate | {convergence_rate:.1f}% |")
    content.append("")
    
    # Flow type breakdown
    flow_types = {}
    for segment in results.get("segments", []):
        flow_type = segment.get("flow_type", "unknown")
        flow_types[flow_type] = flow_types.get(flow_type, 0) + 1
    
    if flow_types:
        content.append("### Flow Type Breakdown")
        content.append("")
        content.append("| Flow Type | Count |")
        content.append("|-----------|-------|")
        for flow_type, count in sorted(flow_types.items(), key=lambda x: str(x[0])):
            content.append(f"| {flow_type} | {count} |")
        content.append("")
    
    return content


def generate_segment_section(
    segment: Dict[str, Any], 
    event_order: List[Tuple[str, float]]
) -> List[str]:
    """Generate markdown content for a single segment."""
    content = []
    
    # Segment header
    seg_id = segment.get("seg_id", "Unknown")
    segment_label = segment.get("segment_label", "Unknown")
    flow_type = segment.get("flow_type", "Unknown")
    event_a = segment.get("event_a", "Unknown")
    event_b = segment.get("event_b", "Unknown")
    has_convergence = segment.get("has_convergence", False)
    
    content.append(f"## {seg_id}: {segment_label}")
    content.append("")
    content.append(f"**Flow Type:** {flow_type}")
    content.append(f"**Events:** {event_a} vs {event_b}")
    content.append(f"**Has Convergence:** {'Yes' if has_convergence else 'No'}")
    content.append("")
    
    # Basic segment info
    content.extend(generate_basic_info_table(segment))
    content.append("")
    
    # Convergence analysis if present
    if has_convergence:
        content.extend(generate_convergence_analysis(segment))
        content.append("")
    
    # Deep dive analysis if present
    deep_dive = segment.get("deep_dive_analysis")
    if deep_dive and isinstance(deep_dive, dict):
        content.extend(generate_deep_dive_analysis(segment))
        content.append("")
    
    return content


def generate_basic_info_table(segment: Dict[str, Any]) -> List[str]:
    """Generate basic segment information table."""
    content = []
    
    content.append("### Basic Information")
    content.append("")
    content.append("| Metric | Value |")
    content.append("|--------|-------|")
    
    # Basic metrics
    from_km_a = segment.get("from_km_a", "N/A")
    to_km_a = segment.get("to_km_a", "N/A")
    from_km_b = segment.get("from_km_b", "N/A")
    to_km_b = segment.get("to_km_b", "N/A")
    width_m = segment.get("width_m", "N/A")
    total_a = segment.get("total_a", 0)
    total_b = segment.get("total_b", 0)
    
    content.append(f"| Event A Range | {from_km_a} - {to_km_a} km |")
    content.append(f"| Event B Range | {from_km_b} - {to_km_b} km |")
    content.append(f"| Width | {width_m} m |")
    content.append(f"| Event A Runners | {total_a:,} |")
    content.append(f"| Event B Runners | {total_b:,} |")
    
    return content


def generate_convergence_analysis(segment: Dict[str, Any]) -> List[str]:
    """Generate convergence analysis section."""
    content = []
    
    content.append("### Convergence Analysis")
    content.append("")
    
    # Convergence point
    convergence_point = segment.get("convergence_point")
    if convergence_point is not None:
        content.append(f"**Convergence Point:** {convergence_point:.3f} km")
    else:
        content.append("**Convergence Point:** Not found")
    content.append("")
    
    # Overtaking statistics
    overtaking_a = segment.get("overtaking_a", 0)
    overtaking_b = segment.get("overtaking_b", 0)
    
    content.append("**Overtaking Statistics**")
    content.append("| Event | Overtaking Count |")
    content.append("|-------|------------------|")
    content.append(f"| {segment.get('event_a', 'A')} | {overtaking_a:,} |")
    content.append(f"| {segment.get('event_b', 'B')} | {overtaking_b:,} |")
    content.append("")
    
    # Convergence zone
    convergence_zone_start = segment.get("convergence_zone_start")
    convergence_zone_end = segment.get("convergence_zone_end")
    
    if convergence_zone_start and convergence_zone_end:
        content.append(f"**Convergence Zone:** {convergence_zone_start} - {convergence_zone_end}")
        content.append("")
    
    return content


def generate_deep_dive_analysis(segment: Dict[str, Any]) -> List[str]:
    """Generate deep dive analysis section."""
    content = []
    
    deep_dive = segment.get("deep_dive_analysis", {})
    if not deep_dive:
        return content
    
    content.append("### Deep Dive Analysis")
    content.append("")
    
    # Time-based analysis
    time_analysis = deep_dive.get("time_analysis", {})
    if time_analysis:
        content.append("**Time-Based Analysis**")
        content.append("| Metric | Value |")
        content.append("|--------|-------|")
        
        peak_convergence_time = time_analysis.get("peak_convergence_time")
        convergence_duration = time_analysis.get("convergence_duration_minutes")
        overlap_intensity = time_analysis.get("overlap_intensity")
        
        if peak_convergence_time:
            content.append(f"| Peak Convergence Time | {peak_convergence_time} |")
        if convergence_duration is not None:
            content.append(f"| Convergence Duration | {convergence_duration:.1f} minutes |")
        if overlap_intensity is not None:
            content.append(f"| Overlap Intensity | {overlap_intensity:.3f} |")
        content.append("")
    
    # Pace analysis
    pace_analysis = deep_dive.get("pace_analysis", {})
    if pace_analysis:
        content.append("**Pace Analysis**")
        content.append("| Metric | Event A | Event B |")
        content.append("|--------|---------|---------|")
        
        avg_pace_a = pace_analysis.get("avg_pace_a")
        avg_pace_b = pace_analysis.get("avg_pace_b")
        pace_difference = pace_analysis.get("pace_difference")
        
        if avg_pace_a is not None:
            content.append(f"| Average Pace | {avg_pace_a:.2f} min/km | {avg_pace_b:.2f} min/km |")
        if pace_difference is not None:
            content.append(f"| Pace Difference | {pace_difference:.2f} min/km | |")
        content.append("")
    
    # Density analysis
    density_analysis = deep_dive.get("density_analysis", {})
    if density_analysis:
        content.append("**Density Analysis**")
        content.append("| Metric | Value |")
        content.append("|--------|-------|")
        
        peak_density = density_analysis.get("peak_density")
        avg_density = density_analysis.get("avg_density")
        
        if peak_density is not None:
            content.append(f"| Peak Density | {peak_density:.3f} runners/m² |")
        if avg_density is not None:
            content.append(f"| Average Density | {avg_density:.3f} runners/m² |")
        content.append("")
    
    return content


def generate_simple_temporal_flow_report(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS
) -> Dict[str, Any]:
    """
    Generate a simple temporal flow report without deep dive analysis.
    
    Args:
        pace_csv: Path to pace data CSV
        segments_csv: Path to segments CSV
        start_times: Dict mapping event names to start times in minutes
        min_overlap_duration: Minimum overlap duration for analysis
        conflict_length_m: Conflict length in meters
    
    Returns:
        Dict with analysis results
    """
    return generate_temporal_flow_report(
        pace_csv, segments_csv, start_times, min_overlap_duration, 
        conflict_length_m, output_dir="reports/analysis"
    )


def export_temporal_flow_csv(results: Dict[str, Any], output_path: str) -> None:
    """Export temporal flow analysis results to CSV."""
    import csv
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"temporal_flow_analysis_{timestamp}.csv"
    full_path = f"{output_path}/{filename}"
    
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Header
        writer.writerow([
            "seg_id", "segment_label", "flow_type", "event_a", "event_b",
            "from_km_a", "to_km_a", "from_km_b", "to_km_b",
            "convergence_point", "has_convergence",
            "total_a", "total_b", "overtaking_a", "overtaking_b",
            "convergence_zone_start", "convergence_zone_end", "conflict_length_m",
            "sample_a", "sample_b", "analysis_timestamp"
        ])
        
        # Data rows
        for segment in results["segments"]:
            writer.writerow([
                segment["seg_id"],
                segment.get("segment_label", ""),
                segment.get("flow_type", ""),
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
                segment.get("conflict_length_m", ""),
                format_bib_range(segment["sample_a"]),
                format_bib_range(segment["sample_b"]),
                results["timestamp"]
            ])
    
    print(f"📊 Temporal flow analysis exported to: {full_path}")


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
