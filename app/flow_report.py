"""
Temporal Flow Report Module

Generates comprehensive temporal flow analysis reports including convergence points,
overtaking patterns, and flow analysis. This module provides reusable functions for 
generating temporal flow reports that can be called by the API or other modules.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import pandas as pd

try:
    from .flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
    from .constants import DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS
    from .report_utils import get_report_paths, format_decimal_places
    from .flow_density_correlation import analyze_flow_density_correlation
except ImportError:
    from flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
    from constants import DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS
    from report_utils import get_report_paths, format_decimal_places
    from flow_density_correlation import analyze_flow_density_correlation

# Get app version from constants to avoid circular import
APP_VERSION = "v1.6.15"  # This should match the version in main.py


def generate_temporal_flow_report(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    output_dir: str = "reports",
    density_results: Optional[Dict[str, Any]] = None,
    segments_config: Optional[Dict[str, Any]] = None
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
    report_content = generate_markdown_report(results, start_times, density_results, segments_config)
    
    # Save report using standardized naming convention
    full_path, relative_path = get_report_paths("Flow", "md", output_dir)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📊 Temporal flow report saved to: {full_path}")

    # Also generate CSV
    export_temporal_flow_csv(results, output_dir, start_times, min_overlap_duration, conflict_length_m)
    
    # Return results in the format expected by other functions
    results.update({
        "ok": True,
        "report_path": full_path,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return results


def generate_markdown_report(
    results: Dict[str, Any], 
    start_times: Dict[str, float],
    density_results: Optional[Dict[str, Any]] = None,
    segments_config: Optional[Dict[str, Any]] = None
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
    content.append("")
    content.append(f"**Analysis Engine:** {results.get('engine', 'temporal_flow')}")
    content.append("")
    content.append(f"**Analysis Period:** {results.get('timestamp', 'N/A')}")
    content.append("")
    content.append(f"**Min Overlap Duration:** {results.get('min_overlap_duration', 5.0)} seconds")
    content.append("")
    content.append(f"**Conflict Length:** {results.get('conflict_length_m', 100.0)} meters")
    content.append("")
    content.append(f"**Binning Thresholds:** Time > {results.get('temporal_binning_threshold_minutes', 10.0)} min, Distance > {results.get('spatial_binning_threshold_meters', 100.0)} m")
    content.append("")
    content.append(f"**Total Segments:** {results.get('total_segments', 0)}")
    content.append("")
    content.append(f"**Segments with Convergence:** {results.get('segments_with_convergence', 0)}")
    content.append("")
    
    # Legend
    content.append("## Legend")
    content.append("")
    content.append("- **Convergence Point**: Location where runners from different events first overlap in time")
    content.append("- **Flow Interactions**: Count of runners from one event interacting with another (overtaking, merging, or counterflow)")
    content.append("- **Flow Type**: Type of flow pattern (overtake, merge, diverge, counterflow)")
    content.append("- **Convergence Zone**: Time window when convergence occurs")
    content.append("- **Deep Dive Analysis**: Detailed analysis of convergence patterns")
    content.append("")
    
    # Event start times with runner counts
    content.append("## Event Start Times")
    content.append("")
    content.append("| Event | Runners | Start Time |")
    content.append("|-------|---------|------------|")
    
    # Get runner counts from segments data
    runner_counts = {}
    for segment in results.get("segments", []):
        event_a = segment.get("event_a")
        event_b = segment.get("event_b")
        total_a = segment.get("total_a", 0)
        total_b = segment.get("total_b", 0)
        
        if event_a:
            runner_counts[event_a] = total_a
        if event_b:
            runner_counts[event_b] = total_b
    
    for event, start_min in event_order:
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        runner_count = runner_counts.get(event, 0)
        content.append(f"| {event} | {runner_count:,} | {start_time} |")
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
    
    # Add Flow↔Density correlation insights if available
    if density_results and segments_config:
        correlation_insights = generate_flow_density_correlation_insights(
            results, density_results, segments_config
        )
        if correlation_insights:
            content.append(correlation_insights)
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
        flow_type = segment.get("flow_type", "")
        # Handle NaN, empty, and nan values
        if pd.isna(flow_type) or flow_type == "nan" or flow_type == "":
            flow_type = "Not specified"
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
    seg_label = segment.get("segment_label", "Unknown")
    flow_type = segment.get("flow_type", "Unknown")
    event_a = segment.get("event_a", "Unknown")
    event_b = segment.get("event_b", "Unknown")
    has_convergence = segment.get("has_convergence", False)
    
    content.append(f"## {seg_id}: {seg_label}")
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
    
    # Runner Experience Analysis (Overtaking Loads)
    content.extend(generate_runner_experience_analysis(segment))
    content.append("")
    
    # Deep dive analysis if present
    deep_dive = segment.get("deep_dive_analysis")
    if deep_dive and isinstance(deep_dive, dict):
        content.extend(generate_deep_dive_analysis(segment))
        content.append("")
    
    return content


def generate_runner_experience_analysis(segment: Dict[str, Any]) -> List[str]:
    """Generate runner experience analysis section with overtaking loads."""
    content = []
    
    content.append("### Runner Experience Analysis")
    content.append("")
    content.append("This section quantifies the 'passing burden' - how many runners each faster runner needs to navigate around.")
    content.append("")
    
    # Get overtaking load data
    overtaking_load_a = segment.get("overtaking_load_a", 0.0)
    overtaking_load_b = segment.get("overtaking_load_b", 0.0)
    max_load_a = segment.get("max_overtaking_load_a", 0)
    max_load_b = segment.get("max_overtaking_load_b", 0)
    distribution_a = segment.get("overtaking_load_distribution_a", [])
    distribution_b = segment.get("overtaking_load_distribution_b", [])
    
    event_a = segment.get("event_a", "Event A")
    event_b = segment.get("event_b", "Event B")
    
    # Overtaking load summary table
    content.append("| Metric | Value |")
    content.append("|--------|-------|")
    content.append(f"| {event_a} Average Overtaking Load | {overtaking_load_a:.1f} runners |")
    content.append(f"| {event_a} Maximum Overtaking Load | {max_load_a} runners |")
    content.append(f"| {event_b} Average Overtaking Load | {overtaking_load_b:.1f} runners |")
    content.append(f"| {event_b} Maximum Overtaking Load | {max_load_b} runners |")
    content.append("")
    
    # High-load runners analysis
    if distribution_a or distribution_b:
        content.append("#### High-Load Runners")
        content.append("")
        
        # Find runners with high overtaking loads (>5 runners)
        high_load_threshold = 5
        high_load_a = [load for load in distribution_a if load > high_load_threshold]
        high_load_b = [load for load in distribution_b if load > high_load_threshold]
        
        if high_load_a:
            content.append(f"**{event_a} High-Load Runners:** {len(high_load_a)} runners face >{high_load_threshold} passing situations")
            content.append(f"- Load range: {min(high_load_a)} - {max(high_load_a)} runners")
            content.append("")
        
        if high_load_b:
            content.append(f"**{event_b} High-Load Runners:** {len(high_load_b)} runners face >{high_load_threshold} passing situations")
            content.append(f"- Load range: {min(high_load_b)} - {max(high_load_b)} runners")
            content.append("")
        
        if not high_load_a and not high_load_b:
            content.append("No high-load runners detected (all runners face ≤5 passing situations)")
            content.append("")
    
    # Crowd management insights
    content.append("#### Crowd Management Insights")
    content.append("")
    
    if overtaking_load_a > 10 or overtaking_load_b > 10:
        content.append("⚠️ **High Passing Burden Detected**")
        content.append("- Consider wider trails or better event separation")
        content.append("- Monitor for safety concerns during race")
        content.append("")
    elif overtaking_load_a > 5 or overtaking_load_b > 5:
        content.append("⚠️ **Moderate Passing Burden**")
        content.append("- Monitor runner experience and safety")
        content.append("- Consider course adjustments if complaints arise")
        content.append("")
    else:
        content.append("✅ **Low Passing Burden**")
        content.append("- Good runner experience expected")
        content.append("- Current course design appears adequate")
        content.append("")
    
    return content


def generate_basic_info_table(segment: Dict[str, Any]) -> List[str]:
    """Generate basic segment information table."""
    import pandas as pd
    
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
    total_a = segment.get("total_a", 0)
    total_b = segment.get("total_b", 0)
    
    # Get width from segments_new.csv - fix NA values
    seg_id = segment.get("seg_id", "")
    try:
        segments_df = pd.read_csv('data/segments.csv')
        seg_row = segments_df[segments_df['seg_id'] == seg_id]
        if not seg_row.empty:
            width_val = seg_row['width_m'].iloc[0]
            # Handle NaN/NA values
            if pd.isna(width_val) or width_val == '':
                from .constants import DEFAULT_CONFLICT_LENGTH_METERS
                width_m = DEFAULT_CONFLICT_LENGTH_METERS  # Default width
            else:
                width_m = float(width_val)
        else:
            from .constants import DEFAULT_CONFLICT_LENGTH_METERS
            width_m = DEFAULT_CONFLICT_LENGTH_METERS  # Default width
    except Exception:
        from .constants import DEFAULT_CONFLICT_LENGTH_METERS
        width_m = DEFAULT_CONFLICT_LENGTH_METERS  # Default width
    
    # Get event names
    event_a = segment.get("event_a", "A")
    event_b = segment.get("event_b", "B")
    
    content.append(f"| {event_a} Range | {from_km_a} - {to_km_a} km |")
    content.append(f"| {event_b} Range | {from_km_b} - {to_km_b} km |")
    content.append(f"| Width | {width_m} m |")
    
    return content


def generate_convergence_analysis(segment: Dict[str, Any]) -> List[str]:
    """Generate enhanced convergence analysis section."""
    content = []
    
    content.append("### Convergence Analysis")
    content.append("")
    
    # Enhanced flow interaction statistics with percentages and individual convergence zones
    event_a = segment.get('event_a', 'A')
    event_b = segment.get('event_b', 'B')
    flow_type = segment.get('flow_type', 'overtake')
    terminology = segment.get('terminology', {})
    
    # Use appropriate terminology based on flow type
    action_label = terminology.get('count_label', 'Overtaking')
    action_plural = terminology.get('action', 'overtaking')
    
    overtaking_a = segment.get("overtaking_a", 0)
    overtaking_b = segment.get("overtaking_b", 0)
    total_a = segment.get('total_a', 0)
    total_b = segment.get('total_b', 0)
    from_km_a = segment.get('from_km_a', 0)
    to_km_a = segment.get('to_km_a', 0)
    from_km_b = segment.get('from_km_b', 0)
    to_km_b = segment.get('to_km_b', 0)
    
    # Calculate percentages
    pct_a = round((overtaking_a / total_a * 100), 1) if total_a > 0 else 0.0
    pct_b = round((overtaking_b / total_b * 100), 1) if total_b > 0 else 0.0
    
    content.append(f"**{action_label} Statistics**")
    content.append("| Event | True Passes | Co-presence | Convergence Zone |")
    content.append("|-------|-------------|-------------|------------------|")
    
    # Get co-presence counts
    copresence_a = segment.get("copresence_a", 0)
    copresence_b = segment.get("copresence_b", 0)
    
    content.append(f"| {event_a} | {overtaking_a} ({pct_a}%) | {copresence_a} | {from_km_a:.2f} - {to_km_a:.2f} km |")
    content.append(f"| {event_b} | {overtaking_b} ({pct_b}%) | {copresence_b} | {from_km_b:.2f} - {to_km_b:.2f} km |")
    content.append("")
    
    # Enhanced convergence point (normalized) - moved outside table
    convergence_point = segment.get("convergence_point")
    if convergence_point is not None and segment.get('has_convergence', False):
        # Store both absolute and normalized convergence points
        from_km_a = segment.get('from_km_a', 0)
        to_km_a = segment.get('to_km_a', 0)
        
        # Calculate normalized convergence point (0.0 to 1.0)
        segment_len = to_km_a - from_km_a
        if segment_len > 0:
            # Calculate raw fraction
            raw_fraction = (convergence_point - from_km_a) / segment_len
            # Apply fraction clamping to ensure [0.0, 1.0] range
            from app.constants import MIN_NORMALIZED_FRACTION, MAX_NORMALIZED_FRACTION
            if raw_fraction < MIN_NORMALIZED_FRACTION:
                normalized_cp = MIN_NORMALIZED_FRACTION
                logging.warning(f"Clamped negative convergence fraction {raw_fraction:.3f} to {MIN_NORMALIZED_FRACTION} for {segment.get('seg_id', 'unknown')} {event_a} vs {event_b}")
            elif raw_fraction > MAX_NORMALIZED_FRACTION:
                normalized_cp = MAX_NORMALIZED_FRACTION
                logging.warning(f"Clamped convergence fraction {raw_fraction:.3f} > 1.0 to {MAX_NORMALIZED_FRACTION} for {segment.get('seg_id', 'unknown')} {event_a} vs {event_b}")
            else:
                normalized_cp = raw_fraction
            normalized_cp = round(normalized_cp, 2)
            
            # Display both absolute and normalized values clearly
            content.append(f"**Convergence Point (pct):** {normalized_cp}%")
            content.append(f"**Convergence Point (km):** {convergence_point:.2f}")
        else:
            content.append(f"**Convergence Point (km):** {convergence_point:.2f}")
    else:
        content.append("**Convergence Point:** Not found")
    content.append("")
    
    # Convergence zone with proper decimal formatting
    convergence_zone_start = segment.get("convergence_zone_start")
    convergence_zone_end = segment.get("convergence_zone_end")
    
    if convergence_zone_start is not None and convergence_zone_end is not None:
        # Fix decimal precision issues (max 3 decimals)
        start_formatted = f"{convergence_zone_start:.3f}".rstrip('0').rstrip('.')
        end_formatted = f"{convergence_zone_end:.3f}".rstrip('0').rstrip('.')
        content.append(f"**Convergence Zone:** {start_formatted} - {end_formatted} km")
    else:
        content.append("**Convergence Zone:** Not found")
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
        conflict_length_m, output_dir="reports"
    )


def export_temporal_flow_csv(results: Dict[str, Any], output_path: str, start_times: Dict[str, float] = None, min_overlap_duration: float = 5.0, conflict_length_m: float = 100.0) -> None:
    """Export temporal flow analysis results to CSV with enhanced formatting."""
    import csv
    import pandas as pd
    from datetime import datetime
    
    # Use date-based organization and standardized naming
    full_path, relative_path = get_report_paths("Flow", "csv", output_path)
    
    # Load segments for width values
    segments_df = pd.read_csv('data/segments.csv')
    
    # Get segments from results
    segments = results.get("segments", [])
    
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Reorganized header with logical column grouping for better readability
        writer.writerow([
            # Group 1: Segment Identification & Context
            "seg_id", "segment_label", "event_a", "event_b", "total_a", "total_b", 
            "flow_type", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "width_m",
            
            # Group 2: Encounter Results & Analysis  
            "overtaking_a", "overtaking_b", "sample_a", "sample_b", "pct_a", "pct_b",
            "copresence_a", "copresence_b", "unique_encounters", "participants_involved",
            
            # Group 3: Runner Experience Analysis (Overtaking Loads)
            "overtaking_load_a", "overtaking_load_b", "max_overtaking_load_a", "max_overtaking_load_b",
            
            # Group 4: Technical & Debugging
            "spatial_zone_exists", "temporal_overlap_exists", "true_pass_exists",
            "has_convergence_policy", "has_convergence", "convergence_zone_start",
            "convergence_zone_end", "no_pass_reason_code", "conflict_length_m",
            
            # Group 5: Metadata (moved to end as requested)
            "analysis_timestamp", "app_version", "environment", "data_source",
            "start_times", "min_overlap_duration", "conflict_length_m"
        ])
        
        # Enhanced data rows with proper formatting
        for segment in segments:
            seg_id = segment.get("seg_id", "")
            
            # Get width from segments_new.csv - fix NA values
            seg_row = segments_df[segments_df['seg_id'] == seg_id]
            if not seg_row.empty:
                width_val = seg_row['width_m'].iloc[0]
                # Handle NaN/NA values
                if pd.isna(width_val) or width_val == '':
                    from .constants import DEFAULT_CONFLICT_LENGTH_METERS
                    width_m = DEFAULT_CONFLICT_LENGTH_METERS  # Default width
                else:
                    width_m = float(width_val)
            else:
                from .constants import DEFAULT_CONFLICT_LENGTH_METERS
                width_m = DEFAULT_CONFLICT_LENGTH_METERS  # Default width
            
            # Fix convergence point normalization and decimal formatting (max 3 decimals)
            if segment.get('has_convergence', False):
                cp_km = segment.get('convergence_point')
                from_km_a = segment.get('from_km_a', 0)
                to_km_a = segment.get('to_km_a', 0)
                
                # Round convergence point to max 2 decimal places for consistency
                cp_km = format_decimal_places(cp_km, 2)
                
                # Normalize convergence point to segment (0.0 to 1.0)
                segment_len = to_km_a - from_km_a
                if segment_len > 0 and cp_km is not None:
                    # Calculate raw fraction
                    raw_fraction = (cp_km - from_km_a) / segment_len
                    # Apply fraction clamping to ensure [0.0, 1.0] range
                    from app.constants import MIN_NORMALIZED_FRACTION, MAX_NORMALIZED_FRACTION
                    if raw_fraction < MIN_NORMALIZED_FRACTION:
                        normalized_cp = MIN_NORMALIZED_FRACTION
                        logging.warning(f"Clamped negative convergence fraction {raw_fraction:.3f} to {MIN_NORMALIZED_FRACTION} for {seg_id} {segment.get('event_a', 'A')} vs {segment.get('event_b', 'B')}")
                    elif raw_fraction > MAX_NORMALIZED_FRACTION:
                        normalized_cp = MAX_NORMALIZED_FRACTION
                        logging.warning(f"Clamped convergence fraction {raw_fraction:.3f} > 1.0 to {MAX_NORMALIZED_FRACTION} for {seg_id} {segment.get('event_a', 'A')} vs {segment.get('event_b', 'B')}")
                    else:
                        normalized_cp = raw_fraction
                    normalized_cp = format_decimal_places(normalized_cp, 2)  # Max 2 decimal places
                else:
                    normalized_cp = 0.0
            else:
                cp_km = None
                normalized_cp = None
            
            # Fix decimal formatting (max 2 decimals for consistency)
            conv_start = format_decimal_places(segment.get('convergence_zone_start'), 2)
            conv_end = format_decimal_places(segment.get('convergence_zone_end'), 2)
            
            # Calculate percentages
            total_a = segment.get('total_a', 0)
            total_b = segment.get('total_b', 0)
            overtaking_a = segment.get('overtaking_a', 0)
            overtaking_b = segment.get('overtaking_b', 0)
            
            pct_a = round((overtaking_a / total_a * 100), 1) if total_a > 0 else 0.0
            pct_b = round((overtaking_b / total_b * 100), 1) if total_b > 0 else 0.0
            
            writer.writerow([
                # Group 1: Segment Identification & Context
                seg_id,
                segment.get("segment_label", ""),
                segment.get("event_a", ""),
                segment.get("event_b", ""),
                segment.get("total_a", ""),
                segment.get("total_b", ""),
                segment.get("flow_type", ""),
                round(segment.get('from_km_a', 0), 2),
                round(segment.get('to_km_a', 0), 2),
                round(segment.get('from_km_b', 0), 2),
                round(segment.get('to_km_b', 0), 2),
                width_m,
                
                # Group 2: Encounter Results & Analysis
                segment.get("overtaking_a", ""),
                segment.get("overtaking_b", ""),
                format_sample_data(segment.get("sample_a", [])),
                format_sample_data(segment.get("sample_b", [])),
                pct_a,
                pct_b,
                segment.get("copresence_a", ""),
                segment.get("copresence_b", ""),
                segment.get("unique_encounters", 0),
                segment.get("participants_involved", 0),
                
                # Group 3: Runner Experience Analysis (Overtaking Loads)
                segment.get("overtaking_load_a", 0.0),
                segment.get("overtaking_load_b", 0.0),
                segment.get("max_overtaking_load_a", 0),
                segment.get("max_overtaking_load_b", 0),
                
                # Group 4: Technical & Debugging
                segment.get("spatial_zone_exists", False),
                segment.get("temporal_overlap_exists", False),
                segment.get("true_pass_exists", False),
                segment.get("has_convergence_policy", False),
                segment.get("has_convergence", False),
                conv_start,
                conv_end,
                segment.get("no_pass_reason_code", ""),
                segment.get('conflict_length_m', 100.0),  # conflict_length_m from analysis
                
                # Group 5: Metadata (moved to end as requested)
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                APP_VERSION,
                "local",  # Environment detection moved to function parameter
                "runners.csv, segments.csv",
                f"Full:{start_times.get('Full', 420) if start_times else 420}, 10K:{start_times.get('10K', 440) if start_times else 440}, Half:{start_times.get('Half', 460) if start_times else 460}",
                min_overlap_duration,
                conflict_length_m
            ])
    
    print(f"📊 Temporal flow analysis exported to: {full_path}")
    
    # Generate Flow Audit CSV if any segments have audit data
    audit_segments = [seg for seg in segments if "flow_audit_data" in seg]
    if audit_segments:
        # Extract output directory from the CSV path
        import os
        output_dir = os.path.dirname(full_path)
        audit_path = generate_flow_audit_csv(segments, output_dir)
        print(f"🔍 Flow Audit data exported to: {audit_path}")
    else:
        print("ℹ️  No Flow Audit data to export")

    return full_path




def format_sample_data(sample_list: List[str], max_individual: int = 3) -> str:
    """Format sample data for human-readable CSV display."""
    if not sample_list:
        return ""
    
    if len(sample_list) <= max_individual:
        return ", ".join(map(str, sample_list))
    
    # For large lists, show first few and count
    sorted_samples = sorted(sample_list, key=lambda x: int(x) if str(x).isdigit() else x)
    first_few = sorted_samples[:max_individual]
    return f"{', '.join(map(str, first_few))}, ... ({len(sample_list)} total)"


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


def generate_flow_audit_csv(
    segments: List[Dict[str, Any]],
    output_dir: str = "reports"
) -> str:
    """
    Generate Flow_Audit.csv with comprehensive diagnostic data.
    
    This function creates a sidecar diagnostic file to complement Flow.csv,
    providing fine-grained instrumentation for segments with suspicious
    overtaking percentages.
    """
    import os
    from datetime import datetime
    
    # Create audit subdirectory within the output directory
    audit_dir = os.path.join(output_dir, "audit")
    os.makedirs(audit_dir, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{timestamp}-Flow_Audit.csv"
    full_path = os.path.join(audit_dir, filename)
    
    # Flow Audit CSV header (33 columns as per specification)
    audit_header = [
        "seg_id", "segment_label", "event_a", "event_b",
        "spatial_zone_exists", "temporal_overlap_exists", "true_pass_exists", 
        "has_convergence_policy", "no_pass_reason_code",
        "convergence_zone_start", "convergence_zone_end", "conflict_length_m",
        "copresence_a", "copresence_b", "density_ratio",
        "median_entry_diff_sec", "median_exit_diff_sec",
        "avg_overlap_dwell_sec", "max_overlap_dwell_sec", "overlap_window_sec",
        "passes_a", "passes_b", "multipass_bibs_a", "multipass_bibs_b",
        "pct_overtake_raw_a", "pct_overtake_raw_b", 
        "pct_overtake_strict_a", "pct_overtake_strict_b",
        "time_bins_used", "distance_bins_used", "dedup_passes_applied",
        "reason_codes", "audit_trigger"
    ]
    
    import csv
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(audit_header)
        
        # Write audit data for segments that have flow_audit_data
        for segment in segments:
            if "flow_audit_data" in segment:
                audit_data = segment["flow_audit_data"]
                audit_data["seg_id"] = segment.get("seg_id", "")
                audit_data["segment_label"] = segment.get("segment_label", "")
                
                # Write row with all 33 columns
                writer.writerow([
                    audit_data.get("seg_id", ""),
                    audit_data.get("segment_label", ""),
                    audit_data.get("event_a", ""),
                    audit_data.get("event_b", ""),
                    audit_data.get("spatial_zone_exists", False),
                    audit_data.get("temporal_overlap_exists", False),
                    audit_data.get("true_pass_exists", False),
                    audit_data.get("has_convergence_policy", False),
                    audit_data.get("no_pass_reason_code", ""),
                    audit_data.get("convergence_zone_start", ""),
                    audit_data.get("convergence_zone_end", ""),
                    audit_data.get("conflict_length_m", 0.0),
                    audit_data.get("copresence_a", 0),
                    audit_data.get("copresence_b", 0),
                    audit_data.get("density_ratio", 0.0),
                    audit_data.get("median_entry_diff_sec", 0.0),
                    audit_data.get("median_exit_diff_sec", 0.0),
                    audit_data.get("avg_overlap_dwell_sec", 0.0),
                    audit_data.get("max_overlap_dwell_sec", 0.0),
                    audit_data.get("overlap_window_sec", 0.0),
                    audit_data.get("passes_a", 0),
                    audit_data.get("passes_b", 0),
                    audit_data.get("multipass_bibs_a", ""),
                    audit_data.get("multipass_bibs_b", ""),
                    audit_data.get("pct_overtake_raw_a", 0.0),
                    audit_data.get("pct_overtake_raw_b", 0.0),
                    audit_data.get("pct_overtake_strict_a", 0.0),
                    audit_data.get("pct_overtake_strict_b", 0.0),
                    audit_data.get("time_bins_used", False),
                    audit_data.get("distance_bins_used", False),
                    audit_data.get("dedup_passes_applied", False),
                    audit_data.get("reason_codes", ""),
                    audit_data.get("audit_trigger", "")
                ])
    
    return full_path


def generate_flow_density_correlation_insights(
    flow_results: Dict[str, Any],
    density_results: Optional[Dict[str, Any]] = None,
    segments_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate Flow↔Density correlation insights for inclusion in Flow reports.
    
    Args:
        flow_results: Results from analyze_temporal_flow_segments
        density_results: Optional results from analyze_density_segments
        segments_config: Optional configuration from load_density_cfg
        
    Returns:
        Markdown string with correlation insights
    """
    if not density_results or not segments_config:
        return ""
    
    try:
        # Run correlation analysis
        correlation_results = analyze_flow_density_correlation(
            flow_results, density_results, segments_config
        )
        
        if not correlation_results.get("ok", False):
            return ""
        
        summary_insights = correlation_results.get("summary_insights", [])
        correlations = correlation_results.get("correlations", [])
        
        # Count critical correlations
        critical_count = sum(1 for c in correlations if c.get("correlation_type") == "critical_correlation")
        significant_count = sum(1 for c in correlations if c.get("correlation_type") == "significant_correlation")
        
        # Generate insights section
        insights_md = f"""
## Flow↔Density Correlation Insights

This section provides insights into the relationship between temporal flow patterns and density concentrations.

### Key Correlations

"""
        
        if critical_count > 0:
            insights_md += f"⚠️ **{critical_count} Critical Correlations**: High density + High flow intensity\n"
        
        if significant_count > 0:
            insights_md += f"📊 **{significant_count} Significant Correlations**: High density + Medium/High flow intensity\n"
        
        # Add summary insights
        for insight in summary_insights[:5]:  # Limit to top 5 insights
            insights_md += f"- {insight}\n"
        
        insights_md += f"""
### Correlation Analysis Summary

| Correlation Type | Count | Description |
|------------------|-------|-------------|
"""
        
        # Count correlation types
        correlation_counts = {}
        for corr in correlations:
            corr_type = corr.get("correlation_type", "unknown")
            correlation_counts[corr_type] = correlation_counts.get(corr_type, 0) + 1
        
        # Add correlation type descriptions
        type_descriptions = {
            "critical_correlation": "High density + High flow intensity",
            "significant_correlation": "High density + Medium/High flow intensity", 
            "moderate_correlation": "Medium density + High flow intensity",
            "flow_dominant": "Low density + High flow intensity",
            "density_dominant": "High density + Low flow intensity",
            "minimal_correlation": "Other combinations",
            "no_correlation": "No convergence zones"
        }
        
        for corr_type, count in correlation_counts.items():
            description = type_descriptions.get(corr_type, "Unknown")
            insights_md += f"| {corr_type.replace('_', ' ').title()} | {count} | {description} |\n"
        
        insights_md += """
### Recommendations

Based on the correlation analysis:

1. **Monitor Critical Correlations**: Segments with critical correlations require immediate attention
2. **Plan for Significant Correlations**: Segments with significant correlations need careful planning  
3. **Optimize Flow Dominant Areas**: Consider flow management strategies for flow-dominant segments
4. **Address Density Dominant Areas**: Implement density reduction strategies for density-dominant segments

*Note: This analysis requires both Flow and Density data. If Density analysis is not available, this section will be omitted.*
"""
        
        return insights_md
        
    except Exception as e:
        logging.warning(f"Failed to generate Flow↔Density correlation insights: {e}")
        return ""
