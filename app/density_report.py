"""
Density Report Module

Generates comprehensive density analysis reports including per-event views.
This module provides reusable functions for generating both combined and per-event
density reports that can be called by the API or other modules.
"""

from __future__ import annotations
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os

try:
    from .density import analyze_density_segments, DensityConfig
    from .constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS
    from .report_utils import get_report_paths
    from .density_template_engine import DensityTemplateEngine, create_template_context
except ImportError:
    from density import analyze_density_segments, DensityConfig
    from constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS
    from report_utils import get_report_paths
    from density_template_engine import DensityTemplateEngine, create_template_context
import pandas as pd
from datetime import datetime


# LOS Thresholds for density classification (aligned with density_rulebook.yml v2)
# Note: Rulebook defines thresholds in runners per meter, but we use areal density (runners/m²)
# for more accurate spatial analysis. Crowd density (runners/m) aligns with rulebook.

LOS_AREAL_THRESHOLDS = {
    'A': (0.0, 0.31),    # Comfortable
    'B': (0.31, 0.43),   # Good
    'C': (0.43, 0.72),   # Moderate
    'D': (0.72, 1.08),   # Busy
    'E': (1.08, 1.63),   # Very Busy
    'F': (1.63, float('inf'))  # Critical
}

# Crowd density thresholds aligned with rulebook (runners per meter)
LOS_CROWD_THRESHOLDS = {
    'A': (0.0, 0.1),     # Comfortable (rulebook: low_density)
    'B': (0.1, 0.2),     # Good (rulebook: medium_density start)
    'C': (0.2, 0.4),     # Moderate (rulebook: medium_density range)
    'D': (0.4, 0.5),     # Busy (rulebook: high_density start)
    'E': (0.5, 0.8),     # Very Busy (rulebook: high_density range)
    'F': (0.8, float('inf'))  # Critical (rulebook: above high_density)
}


def get_los_score(density: float, thresholds: Dict[str, Tuple[float, float]]) -> str:
    """Get LOS score (A-F) for a given density value."""
    for score, (min_val, max_val) in thresholds.items():
        if min_val <= density < max_val:
            return score
    return 'F'  # Default to F if not found


def format_duration(seconds: int) -> str:
    """Format duration in seconds to hh:mm:ss format."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def generate_density_report(
    pace_csv: str,
    density_csv: str,
    start_times: Dict[str, float],
    step_km: float = DEFAULT_STEP_KM,
    time_window_s: float = DEFAULT_TIME_WINDOW_SECONDS,
    include_per_event: bool = True,
    output_dir: str = "reports"
) -> Dict[str, Any]:
    """
    Generate a comprehensive density analysis report.
    
    Args:
        pace_csv: Path to pace data CSV
        density_csv: Path to density configuration CSV
        start_times: Dict mapping event names to start times in minutes
        step_km: Step size for density calculations
        time_window_s: Time window for density calculations
        include_per_event: Whether to include per-event analysis
        output_dir: Directory to save the report
    
    Returns:
        Dict with analysis results and report path
    """
    print("🔍 Starting density analysis...")
    
    # Load pace data
    pace_data = pd.read_csv(pace_csv)
    
    # Convert start times from minutes to datetime
    start_datetimes = {}
    for event, start_min in start_times.items():
        start_hour = int(start_min // 60)
        start_minute = int(start_min % 60)
        start_datetimes[event] = datetime(2025, 9, 4, start_hour, start_minute, 0)
    
    # Create density configuration
    config = DensityConfig(step_km=step_km, bin_seconds=time_window_s)
    
    # Run density analysis
    try:
        results = analyze_density_segments(
            pace_data, start_datetimes, config, density_csv
        )
        
        print(f"🔍 Analysis results keys: {list(results.keys())}")
        print(f"🔍 Analysis ok status: {results.get('ok', 'NOT_FOUND')}")
        print(f"🔍 Segments type: {type(results.get('segments', 'NOT_FOUND'))}")
        if results.get('segments'):
            if isinstance(results['segments'], dict):
                segment_keys = list(results['segments'].keys())
                print(f"🔍 Segment keys: {segment_keys[:3]}...")  # Show first 3
                if segment_keys:
                    first_key = segment_keys[0]
                    print(f"🔍 First segment type: {type(results['segments'][first_key])}")
                    print(f"🔍 First segment keys: {list(results['segments'][first_key].keys()) if hasattr(results['segments'][first_key], 'keys') else 'No keys method'}")
            else:
                print(f"🔍 First segment type: {type(results['segments'][0])}")
                print(f"🔍 First segment keys: {list(results['segments'][0].keys()) if hasattr(results['segments'][0], 'keys') else 'No keys method'}")
        
        # Check if analysis was successful - the function returns a dict with segments
        if "segments" not in results:
            error_details = results.get("error", "No segments found in results")
            print(f"❌ Density analysis failed: {error_details}")
            print(f"🔍 Full results: {results}")
            return {
                "ok": False,
                "error": "Density analysis failed",
                "details": error_details
            }
    except Exception as e:
        print(f"❌ Exception during density analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "ok": False,
            "error": "Density analysis failed",
            "details": str(e)
        }
    
    # Generate markdown report
    report_content = generate_markdown_report(results, start_times, include_per_event)
    
    # Save report using standardized naming convention
    full_path, relative_path = get_report_paths("Density", "md", output_dir)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"📊 Density report saved to: {full_path}")
    
    return {
        "ok": True,
        "report_path": full_path,
        "analysis_results": results,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def generate_markdown_report(
    results: Dict[str, Any], 
    start_times: Dict[str, float], 
    include_per_event: bool = True
) -> str:
    """Generate markdown content for the density report."""
    
    # Event start times for ordering
    event_order = sorted(start_times.items(), key=lambda x: x[1])
    
    # Calculate total runners per event
    event_totals = {}
    for event, _ in event_order:
        event_totals[event] = sum(
            getattr(seg.get("per_event", {}).get(event), "n_event_runners", 0)
            for seg in results.get("segments", {}).values()
        )
    
    # Build report content
    content = []
    
    # Header
    content.append("# Improved Per-Event Density Analysis Report")
    content.append("")
    content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    content.append(f"**Analysis Period:** {datetime.now().strftime('%Y-%m-%d')}")
    content.append("")
    content.append(f"**Time Bin Size:** {results.get('time_window_s', 30)} seconds")
    content.append("")
    summary = results.get("summary", {})
    content.append(f"**Total Segments:** {summary.get('total_segments', 0)}")
    content.append("")
    content.append(f"**Processed Segments:** {summary.get('processed_segments', 0)}")
    content.append("")
    content.append(f"**Skipped Segments:** {summary.get('skipped_segments', 0)}")
    content.append("")
    
    # Legend
    content.append("## Legend")
    content.append("")
    content.append("- **TOT**: Time Over Threshold (seconds above E/F LOS thresholds)")
    content.append("- **LOS**: Level of Service (A=Comfortable, B=Good, C=Moderate, D=Busy, E=Very Busy, F=Critical)")
    content.append("- **Experienced Density**: What runners actually experience (includes co-present runners from other events)")
    content.append("- **Self Density**: Only that event's runners (not shown in this report)")
    content.append("- **Active Window**: Time period when the event has runners present in the segment")
    content.append("")
    content.append("### Terminology Note")
    content.append("**Thresholds**: All density thresholds are applied inclusively (≥). For example, '≥0.5 runners/m' means 0.5 or higher density values trigger the threshold.")
    content.append("")
    
    # LOS Thresholds Table
    content.append("## Level of Service Thresholds")
    content.append("")
    content.append("| LOS | Areal Density (runners/m²) | Crowd Density (runners/m) | Description |")
    content.append("|-----|---------------------------|--------------------------|-------------|")
    content.append("| A | 0.00 - 0.31 | 0.00 - 0.20 | Comfortable |")
    content.append("| B | 0.31 - 0.43 | 0.20 - 0.40 | Good |")
    content.append("| C | 0.43 - 0.72 | 0.40 - 0.60 | Moderate |")
    content.append("| D | 0.72 - 1.08 | 0.60 - 0.80 | Busy |")
    content.append("| E | 1.08 - 1.63 | 0.80 - 1.00 | Very Busy |")
    content.append("| F | 1.63+ | 1.00+ | Critical |")
    content.append("")
    
    # Event start times (showing actual participants in first segment as reference)
    content.append("## Event Start Times")
    content.append("")
    content.append("| Event | Start Time | Total Participants |")
    content.append("|-------|------------|-------------------|")
    
    # Get actual participant counts from the first segment as reference
    first_segment = next(iter(results.get("segments", {}).values()), {})
    per_event = first_segment.get("per_event", {})
    
    total_runners = 0
    for event, start_min in event_order:
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        # Use actual participant count from per_event data
        event_data = per_event.get(event, {})
        actual_runners = getattr(event_data, "n_event_runners", 0)
        total_runners += actual_runners
        content.append(f"| {event} | {start_time} | {actual_runners:,} |")
    
    # Add total row
    content.append(f"| **Total** | - | **{total_runners:,}** |")
    content.append("")
    
    # Process each segment
    for segment_id, segment in results.get("segments", {}).items():
        content.extend(generate_segment_section(segment_id, segment, event_order, include_per_event))
        content.append("")
        content.append("---")
        content.append("")
    
    return "\n".join(content)


def generate_segment_section(
    segment_id: str,
    segment_data: Dict[str, Any], 
    event_order: List[Tuple[str, float]], 
    include_per_event: bool
) -> List[str]:
    """Generate markdown content for a single segment."""
    content = []
    
    # Segment header
    seg_label = segment_data.get("seg_label", "Unknown")
    events_included = segment_data.get("events_included", [])
    
    content.append(f"## {segment_id}: {seg_label}")
    content.append("")
    content.append(f"**Events Included:** {', '.join(events_included)}")
    content.append(f"**Segment Label:** {seg_label}")
    content.append("")
    
    # Combined view
    content.extend(generate_combined_view(segment_data))
    content.append("")
    
    # Template-driven narratives
    content.extend(generate_template_narratives(segment_id, segment_data))
    content.append("")
    
    # Per-event analysis if requested
    if include_per_event and "per_event" in segment_data:
        content.extend(generate_per_event_analysis(segment_data, event_order))
        content.append("")
    
    # Combined sustained periods
    content.extend(generate_combined_sustained_periods(segment_data))
    
    return content


def generate_template_narratives(segment_id: str, segment_data: Dict[str, Any]) -> List[str]:
    """Generate template-driven narratives for a segment."""
    content = []
    
    try:
        # Initialize template engine
        template_engine = DensityTemplateEngine()
        
        # Determine segment type (simplified mapping for now)
        segment_type = _determine_segment_type(segment_id, segment_data)
        flow_type = "default"  # Could be enhanced based on flow analysis
        
        # Create template context
        context = create_template_context(segment_id, segment_data, segment_type, flow_type)
        
        # Generate narratives
        drivers = template_engine.generate_drivers(context)
        mitigations = template_engine.generate_mitigations(context)
        ops_insights = template_engine.generate_ops_insights(context)
        safety_warnings = template_engine.generate_safety_warnings(context)
        
        # Add to content with clear separation
        content.append("### Metrics Summary")
        content.append("")
        content.append("**Density Analysis:**")
        content.append(f"- {drivers}")
        content.append("")
        content.append("**Operational Implications:**")
        content.append(f"- {mitigations}")
        content.append("")
        
        # Operational guidance box
        if ops_insights:
            content.append("### Operational Guidance")
            content.append("")
            for key, value in ops_insights.items():
                content.append(f"- **{key.title()}:** {value}")
            content.append("")
        
        # Safety warnings box
        if safety_warnings:
            content.append("### Safety Alerts")
            content.append("")
            for warning in safety_warnings:
                content.append(f"- {warning}")
            content.append("")
        
    except Exception as e:
        # Fallback if template engine fails
        content.append("### Metrics Summary")
        content.append("")
        content.append("**Density Analysis:**")
        content.append(f"- High runner density in {segment_data.get('seg_label', 'Unknown')} segment")
        content.append("")
        content.append("**Operational Implications:**")
        content.append("- Consider additional crowd management measures")
        content.append("")
    
    return content


def _determine_segment_type(segment_id: str, segment_data: Dict[str, Any]) -> str:
    """Determine segment type for template matching."""
    seg_label = segment_data.get("seg_label", "").lower()
    
    # Enhanced mapping based on segment labels and IDs
    if "start" in seg_label or segment_id.startswith("A"):
        return "start"
    elif "bridge" in seg_label or "mill" in seg_label or "i1" in segment_id.lower():
        return "bridge"
    elif "turn" in seg_label or segment_id.startswith("B") or segment_id.startswith("D"):
        return "turn"
    elif "finish" in seg_label or segment_id.startswith("M"):
        return "finish"
    elif "trail" in seg_label or "aberdeen" in seg_label or segment_id.startswith("L"):
        return "trail"
    elif "station" in seg_label or segment_id.startswith("F") or segment_id.startswith("H"):
        return "trail"  # Station Rd segments are trail-like
    else:
        return "default"


def generate_combined_view(segment: Dict[str, Any]) -> List[str]:
    """Generate combined view section for a segment."""
    content = []
    
    content.append("### Combined View (All Events)")
    content.append("")
    
    # Active window summary
    summary = segment.get("summary", {})
    content.append("**Active Window Summary**")
    content.append("| Metric | Value |")
    content.append("|--------|-------|")
    
    active_start = getattr(summary, "active_start", "N/A")
    active_end = getattr(summary, "active_end", "N/A")
    active_duration = getattr(summary, "active_duration_s", 0)
    occupancy_rate = getattr(summary, "occupancy_rate", 0.0)
    peak_concurrency = getattr(summary, "active_peak_concurrency", 0)
    peak_areal = getattr(summary, "active_peak_areal", 0.0)
    peak_crowd = getattr(summary, "active_peak_crowd", 0.0)
    p95_areal = getattr(summary, "active_p95_areal", 0.0)
    p95_crowd = getattr(summary, "active_p95_crowd", 0.0)
    mean_areal = getattr(summary, "active_mean_areal", 0.0)
    mean_crowd = getattr(summary, "active_mean_crowd", 0.0)
    tot_areal = getattr(summary, "active_tot_areal_sec", 0)
    tot_crowd = getattr(summary, "active_tot_crowd_sec", 0)
    
    content.append(f"| Active Start/End | {active_start} - {active_end} |")
    content.append(f"| Active Duration | {format_duration(active_duration)} |")
    content.append(f"| Occupancy Rate | {occupancy_rate:.1%} |")
    content.append(f"| Peak Concurrency | {peak_concurrency:,} |")
    content.append(f"| Peak Areal Density | {peak_areal:.3f} runners/m² |")
    content.append(f"| Peak Crowd Density | {peak_crowd:.3f} runners/m |")
    content.append(f"| P95 Areal Density | {p95_areal:.3f} runners/m² |")
    content.append(f"| P95 Crowd Density | {p95_crowd:.3f} runners/m |")
    content.append(f"| Active Mean Areal | {mean_areal:.3f} runners/m² |")
    content.append(f"| Active Mean Crowd | {mean_crowd:.3f} runners/m |")
    content.append(f"| TOT Areal (E/F) | {tot_areal}s |")
    content.append(f"| TOT Crowd (E/F) | {tot_crowd}s |")
    
    return content


def generate_per_event_analysis(
    segment: Dict[str, Any], 
    event_order: List[Tuple[str, float]]
) -> List[str]:
    """Generate per-event analysis section for a segment."""
    content = []
    
    content.append("### Per-Event Analysis (Experienced Density)")
    content.append("")
    
    per_event = segment.get("per_event", {})
    
    # Process events in start time order
    for event, start_min in event_order:
        if event not in per_event:
            continue
            
        event_data = per_event[event]
        start_time = f"{int(start_min//60):02d}:{int(start_min%60):02d}:00"
        n_runners = getattr(event_data, "n_event_runners", 0)
        
        content.append(f"#### {event} Event — Start {start_time} — N={n_runners:,}")
        content.append("")
        
        # Active window table
        content.extend(generate_event_active_window_table(event_data))
        content.append("")
        
        # LOS scores table
        content.extend(generate_event_los_scores_table(event_data))
        content.append("")
        
        # Sustained periods table
        content.extend(generate_event_sustained_periods_table(event_data))
        content.append("")
    
    return content


def generate_event_active_window_table(event_data: Dict[str, Any]) -> List[str]:
    """Generate active window table for an event."""
    content = []
    
    content.append("**Active Window (Experienced)**")
    content.append("| Metric | Value |")
    content.append("|--------|-------|")
    
    active_start = getattr(event_data, "active_start", "N/A")
    active_end = getattr(event_data, "active_end", "N/A")
    active_duration = getattr(event_data, "active_duration_s", 0)
    occupancy_rate = getattr(event_data, "occupancy_rate", 0.0)
    peak_concurrency = getattr(event_data, "peak_concurrency_exp", 0)
    peak_areal = getattr(event_data, "peak_areal_exp", 0.0)
    peak_crowd = getattr(event_data, "peak_crowd_exp", 0.0)
    p95_areal = getattr(event_data, "p95_areal_exp", 0.0)
    p95_crowd = getattr(event_data, "p95_crowd_exp", 0.0)
    mean_areal = getattr(event_data, "active_mean_areal_exp", 0.0)
    mean_crowd = getattr(event_data, "active_mean_crowd_exp", 0.0)
    tot_areal = getattr(event_data, "active_tot_areal_exp_sec", 0)
    tot_crowd = getattr(event_data, "active_tot_crowd_exp_sec", 0)
    
    content.append(f"| Active Start/End | {active_start} – {active_end} |")
    content.append(f"| Active Duration | {format_duration(active_duration)} |")
    content.append(f"| Occupancy Rate | {occupancy_rate:.1%} |")
    content.append(f"| Peak Concurrency (Experienced) | {peak_concurrency:,} |")
    content.append(f"| Peak Areal Density (Experienced) | {peak_areal:.3f} runners/m² |")
    content.append(f"| Peak Crowd Density (Experienced) | {peak_crowd:.3f} runners/m |")
    content.append(f"| P95 Areal Density (Experienced) | {p95_areal:.3f} runners/m² |")
    content.append(f"| P95 Crowd Density (Experienced) | {p95_crowd:.3f} runners/m |")
    content.append(f"| Active Mean Areal (Experienced) | {mean_areal:.3f} runners/m² |")
    content.append(f"| Active Mean Crowd (Experienced) | {mean_crowd:.3f} runners/m |")
    content.append(f"| TOT Areal (E/F) | {tot_areal}s |")
    content.append(f"| TOT Crowd (E/F) | {tot_crowd}s |")
    
    return content


def generate_event_los_scores_table(event_data: Dict[str, Any]) -> List[str]:
    """Generate LOS scores table for an event."""
    content = []
    
    content.append("**Level of Service Scores**")
    content.append("| Metric | Value | LOS Score |")
    content.append("|--------|-------|----------|")
    
    peak_areal = getattr(event_data, "peak_areal_exp", 0.0)
    peak_crowd = getattr(event_data, "peak_crowd_exp", 0.0)
    p95_areal = getattr(event_data, "p95_areal_exp", 0.0)
    p95_crowd = getattr(event_data, "p95_crowd_exp", 0.0)
    mean_areal = getattr(event_data, "active_mean_areal_exp", 0.0)
    mean_crowd = getattr(event_data, "active_mean_crowd_exp", 0.0)
    
    content.append(f"| Peak Areal Density | {peak_areal:.3f} runners/m² | {get_los_score(peak_areal, LOS_AREAL_THRESHOLDS)} |")
    content.append(f"| Peak Crowd Density | {peak_crowd:.3f} runners/m | {get_los_score(peak_crowd, LOS_CROWD_THRESHOLDS)} |")
    content.append(f"| P95 Areal Density | {p95_areal:.3f} runners/m² | {get_los_score(p95_areal, LOS_AREAL_THRESHOLDS)} |")
    content.append(f"| P95 Crowd Density | {p95_crowd:.3f} runners/m | {get_los_score(p95_crowd, LOS_CROWD_THRESHOLDS)} |")
    content.append(f"| Mean Areal Density | {mean_areal:.3f} runners/m² | {get_los_score(mean_areal, LOS_AREAL_THRESHOLDS)} |")
    content.append(f"| Mean Crowd Density | {mean_crowd:.3f} runners/m | {get_los_score(mean_crowd, LOS_CROWD_THRESHOLDS)} |")
    
    return content


def generate_event_sustained_periods_table(event_data: Dict[str, Any]) -> List[str]:
    """Generate sustained periods table for an event."""
    content = []
    
    sustained_periods = getattr(event_data, "sustained_periods", [])
    if not sustained_periods:
        return content
    
    content.append("**Sustained Periods (Experienced)**")
    content.append("| Start | End | Duration | LOS Areal | LOS Crowd | Avg Areal | Avg Crowd | Peak Conc |")
    content.append("|-------|-----|----------|-----------|-----------|-----------|-----------|----------|")
    
    for period in sustained_periods:
        start = period.get("start_time", "N/A")
        end = period.get("end_time", "N/A")
        duration = period.get("duration_minutes", 0)
        los_areal = period.get("los_areal", "N/A")
        los_crowd = period.get("los_crowd", "N/A")
        avg_areal = period.get("avg_areal_density", 0.0)
        avg_crowd = period.get("avg_crowd_density", 0.0)
        peak_conc = period.get("peak_concurrent_runners", 0)
        
        content.append(f"| {start} | {end} | {duration:.1f} min | {los_areal} | {los_crowd} | {avg_areal:.3f} | {avg_crowd:.3f} | {peak_conc:,} |")
    
    return content


def generate_combined_sustained_periods(segment: Dict[str, Any]) -> List[str]:
    """Generate combined sustained periods section for a segment."""
    content = []
    
    sustained_periods = segment.get("sustained_periods", [])
    if not sustained_periods:
        return content
    
    content.append("### Combined Sustained Periods")
    content.append("")
    content.append("| Start | End | Duration | LOS Areal | LOS Crowd | Avg Areal | Avg Crowd | Peak Conc |")
    content.append("|-------|-----|----------|-----------|-----------|-----------|-----------|----------|")
    
    for period in sustained_periods:
        start = period.get("start_time", "N/A")
        end = period.get("end_time", "N/A")
        duration = period.get("duration_minutes", 0)
        los_areal = period.get("los_areal", "N/A")
        los_crowd = period.get("los_crowd", "N/A")
        avg_areal = period.get("avg_areal_density", 0.0)
        avg_crowd = period.get("avg_crowd_density", 0.0)
        peak_conc = period.get("peak_concurrent_runners", 0)
        
        content.append(f"| {start} | {end} | {duration:.1f} min | {los_areal} | {los_crowd} | {avg_areal:.3f} | {avg_crowd:.3f} | {peak_conc:,} |")
    
    return content


def generate_simple_density_report(
    pace_csv: str,
    density_csv: str,
    start_times: Dict[str, float],
    step_km: float = DEFAULT_STEP_KM,
    time_window_s: float = DEFAULT_TIME_WINDOW_SECONDS
) -> Dict[str, Any]:
    """
    Generate a simple density report without per-event analysis.
    
    Args:
        pace_csv: Path to pace data CSV
        density_csv: Path to density configuration CSV
        start_times: Dict mapping event names to start times in minutes
        step_km: Step size for density calculations
        time_window_s: Time window for density calculations
    
    Returns:
        Dict with analysis results
    """
    return generate_density_report(
        pace_csv, density_csv, start_times, step_km, time_window_s, 
        include_per_event=False, output_dir="reports"
    )
