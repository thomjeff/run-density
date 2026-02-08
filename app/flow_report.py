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

from app.core.flow.flow import analyze_temporal_flow_segments, generate_temporal_flow_narrative
from app.utils.constants import DEFAULT_MIN_OVERLAP_DURATION, DEFAULT_CONFLICT_LENGTH_METERS
from app.report_utils import get_report_paths, format_decimal_places
# Issue #466 Step 2: Storage consolidated to app.storage
# Lazy import - flow_density_correlation.py removed in Phase 2B
# from app.flow_density_correlation import analyze_flow_density_correlation

# Get app version from main.py to ensure consistency
def get_app_version():
    """Get the current app version from main.py"""
    try:
        import re
        with open('app/main.py', 'r') as f:
            content = f.read()
            # Look for version="v1.x.x" pattern
            match = re.search(r'version="(v\d+\.\d+\.\d+)"', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "unknown"

APP_VERSION = get_app_version()


def _get_environment_info() -> str:
    """
    Get environment information for report generation.
    
    Returns:
        String describing the current environment
    """
    import os
    if os.environ.get('TEST_CLOUD_RUN', 'false').lower() == 'true':
        return "**Environment:** https://run-density-ln4r3sfkha-uc.a.run.app (Cloud Run Production)"
    else:
        return "**Environment:** http://localhost:8080 (Local Development)"


def generate_temporal_flow_report(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    output_dir: str = "reports",
    density_results: Optional[Dict[str, Any]] = None,
    segments_config: Optional[Dict[str, Any]] = None,
    environment: str = "local",
    run_id: str = None  # Issue #455: UUID for runflow structure
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
    import logging
    logger = logging.getLogger(__name__)
    
    # Issue #455: Surgical path update for runflow structure
    if run_id:
        from app.report_utils import get_runflow_category_path
        # Override output_dir to use runflow/reports/ 
        output_dir = get_runflow_category_path(run_id, "reports")
        logger.info(f"Issue #455: Using runflow structure for run_id={run_id}, reports_dir={output_dir}")
    
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
    
    # Issue #455: Skip storage_service for runflow mode (already written to correct location)
    # Also save to storage service for persistence (legacy mode only)
    if not run_id:
        try:
            storage_service = get_storage_service()
            # Extract filename from local path to ensure timestamp consistency
            # (avoid timezone drift between local write and GCS upload)
            storage_filename = os.path.basename(full_path)
            storage_path = storage_service.save_file(storage_filename, report_content)
            print(f"📊 Flow report saved to storage: {storage_path}")
        except Exception as e:
            print(f"⚠️ Failed to save flow report to storage: {e}")

    # Also generate CSV
    export_temporal_flow_csv(results, output_dir, start_times, min_overlap_duration, conflict_length_m, environment, run_id=run_id)
    
    # Issue #455: Write metadata.json at end of successful generation (flow report only)
    # Note: For combined runs (density+flow), density writes the metadata
    # This is only for standalone flow report calls
    if run_id:
        try:
            from app.utils.metadata import create_run_metadata, write_metadata_json
            from app.report_utils import get_run_folder_path
            from pathlib import Path
            
            run_path = Path(get_run_folder_path(run_id))
            metadata = create_run_metadata(run_id, run_path, status="complete")
            metadata_path = write_metadata_json(run_path, metadata)
            print(f"Issue #455: Written metadata.json to {metadata_path}")
            
            # Issue #456 Phase 4: Update latest.json (index.json updated after UI export)
            from app.utils.metadata import update_latest_pointer
            update_latest_pointer(run_id)
            
            # Issue #466 Step 3: GCS upload removed (Phase 1 declouding)
            # upload_runflow_to_gcs() archived - local-only architecture
        except Exception as e:
            print(f"⚠️ Failed to write metadata.json: {e}")
    
    # Return results in the format expected by other functions
    results.update({
        "ok": True,
        "report_path": full_path,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id  # Issue #455: Include run_id in response
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
    
    # Header with standardized format (Issue #182)
    content.append("# Temporal Flow Analysis Report")
    content.append("")
    content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    content.append(f"**Analysis Engine:** {results.get('engine', 'temporal_flow')}")
    content.append("")
    
    # Add version information using version module
    try:
        from app.version import get_current_version
        version = get_current_version()
    except ImportError:
        try:
            from version import get_current_version
            version = get_current_version()
        except ImportError:
            version = APP_VERSION
    content.append(f"**Version:** {version}")
    content.append("")
    
    # Add environment information using utility function
    content.append(_get_environment_info())
    content.append("")
    
    content.append(f"**Analysis Period:** {results.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
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
    seg_id = segment.get("seg_id")
    if not seg_id:
        raise ValueError("Flow segment missing seg_id for report generation.")
    seg_label = segment.get("segment_label")
    if not seg_label:
        raise ValueError(f"Segment {seg_id} missing segment_label for flow report generation.")
    flow_type = segment.get("flow_type")
    if not flow_type:
        raise ValueError(f"Segment {seg_id} missing flow_type for flow report generation.")
    event_a = segment.get("event_a")
    event_b = segment.get("event_b")
    if not event_a or not event_b:
        raise ValueError(f"Segment {seg_id} missing event pair for flow report generation.")
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
    logger = logging.getLogger(__name__)
    
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
    
    seg_id = segment.get("seg_id")
    width_m = segment.get("width_m")
    if not seg_id:
        raise ValueError("Segment missing seg_id for basic info table.")
    if width_m is None or (isinstance(width_m, float) and pd.isna(width_m)):
        raise ValueError(f"Segment {seg_id} missing width_m for basic info table.")
    
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
            from app.utils.constants import MIN_NORMALIZED_FRACTION, MAX_NORMALIZED_FRACTION
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


def _format_convergence_points_json(convergence_points: Optional[List[Any]]) -> str:
    """
    Format convergence points list as JSON string for CSV export.
    
    Issue #612: Converts list of ConvergencePoint objects to JSON array.
    
    Args:
        convergence_points: List of ConvergencePoint objects (or None)
        
    Returns:
        JSON string representation of convergence points, or empty string if None/empty
    """
    import json
    if not convergence_points:
        return ""
    
    # Convert ConvergencePoint objects to dicts for JSON serialization
    # Handle both dict (from JSON deserialization) and dataclass objects (from direct analysis)
    cp_dicts = []
    for cp in convergence_points:
        # Handle dict (from JSON deserialization in v2 pipeline - Issue #612: now properly serialized)
        if isinstance(cp, dict):
            cp_dict = {
                "km": round(float(cp.get("km", 0)), 2),
                "type": str(cp.get("type", "unknown"))
            }
            if "overlap_count" in cp and cp["overlap_count"] is not None:
                cp_dict["overlap_count"] = cp["overlap_count"]
            cp_dicts.append(cp_dict)
        # Handle ConvergencePoint dataclass object (direct from analysis)
        else:
            cp_dict = {
                "km": round(cp.km, 2),
                "type": cp.type
            }
            if cp.overlap_count is not None:
                cp_dict["overlap_count"] = cp.overlap_count
            cp_dicts.append(cp_dict)
    
    return json.dumps(cp_dicts)


def _format_start_times_for_csv(start_times: Dict[str, float]) -> str:
    """
    Format start times for CSV metadata display.
    
    Issue #553 Phase 5.2: Dynamic formatting of start times (no hardcoded fallbacks).
    
    Args:
        start_times: Dictionary mapping event names to start times in minutes
        
    Returns:
        Formatted string like "full:420, 10k:440, half:460"
    """
    if not start_times:
        return "N/A"
    
    # Format as "event:time, event:time, ..." (sorted for consistency)
    formatted_parts = []
    for event_name, start_time in sorted(start_times.items()):
        formatted_parts.append(f"{event_name}:{int(start_time)}")
    
    return ", ".join(formatted_parts)


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


def export_temporal_flow_csv(results: Dict[str, Any], output_path: str, start_times: Dict[str, float] = None, min_overlap_duration: float = 5.0, conflict_length_m: float = 100.0, environment: str = "local", run_id: str = None, day: str = None, segments_csv_path: Optional[str] = None) -> None:
    """
    Export temporal flow analysis results to CSV with zone-level granularity.
    
    Issue #629: Updated to output one row per zone (seg_id + zone_index) instead of one row per segment.
    This aligns flow.csv with the zone-level structure used in fz.parquet.
    
    Args:
        results: Flow analysis results containing segments with zones
        output_path: Base output directory
        start_times: Event start times (deprecated, kept for backward compatibility)
        min_overlap_duration: Minimum overlap duration (deprecated, kept for backward compatibility)
        conflict_length_m: Conflict length in meters (deprecated, kept for backward compatibility)
        environment: Environment name (deprecated, kept for backward compatibility)
        run_id: Run ID for path organization
        day: Day prefix for filename (e.g., "sat", "sun")
    """
    import csv
    import pandas as pd
    import logging
    logger = logging.getLogger(__name__)
    
    # Use date-based organization and standardized naming
    full_path, relative_path = get_report_paths("Flow", "csv", output_path)
    
    # Load segments for width values (Issue #616: Use segments_csv_path from analysis.json)
    if segments_csv_path is None:
        error_msg = (
            "segments_csv_path is required for export_temporal_flow_csv in v2 pipeline. "
            "This should come from analysis.json segments_file. "
            "Cannot fall back to default CSV as it may not match the analysis configuration."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        from app.io.loader import load_segments
        segments_df = load_segments(segments_csv_path)
        logger.info(f"Loaded {len(segments_df)} segments from {segments_csv_path} for flow report")
    except Exception as e:
        error_msg = f"Failed to load segments from {segments_csv_path} for flow report: {e}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg) from e
    
    # Get segments from results
    segments = results.get("segments", [])
    
    # Sort segments: first by seg_id, then by event pair (normalized)
    # This ensures sub-segments (A1a, A1b, A1c) are grouped together regardless of event pair
    def sort_key(segment):
        """Create sort key: (seg_id, event_pair_normalized)"""
        seg_id = str(segment.get("seg_id", ""))
        event_a = str(segment.get("event_a", "")).lower()
        event_b = str(segment.get("event_b", "")).lower()
        # Create consistent pair (always alphabetical)
        pair = tuple(sorted([event_a, event_b]))
        return (seg_id, pair)
    
    segments = sorted(segments, key=sort_key)
    
    # Issue #629: Collect zone-level rows instead of segment-level
    zone_rows = []
    
    for segment in segments:
        seg_id = segment.get("seg_id")
        if not seg_id:
            raise ValueError("Flow segment missing seg_id for flow report export.")
        zones = segment.get("zones", [])
        
        if not zones:
            # Skip segments without zones
            continue
        
        # Get segment-level metadata (repeated for each zone)
        segment_label = segment.get("segment_label")
        if not segment_label:
            raise ValueError(f"Segment {seg_id} missing segment_label for flow report export.")
        event_a = segment.get("event_a")
        event_b = segment.get("event_b")
        if not event_a or not event_b:
            raise ValueError(f"Segment {seg_id} missing event pair for flow report export.")
        total_a = segment.get("total_a", 0)
        total_b = segment.get("total_b", 0)
        flow_type = segment.get("flow_type")
        if not flow_type:
            raise ValueError(f"Segment {seg_id} missing flow_type for flow report export.")
        has_convergence = segment.get("has_convergence", False)
        
        # Get width from segments.csv
        # Issue #616: Handle sub-segments (e.g., N5a, A2a) by normalizing to base segment (N5, A2)
        # Sub-segments are created dynamically during flow analysis but don't exist in segments.csv
        base_seg_id = seg_id.rstrip('abcdefghijklmnopqrstuvwxyz')  # Strip trailing letters
        seg_row = segments_df[segments_df['seg_id'] == seg_id]
        if seg_row.empty and base_seg_id != seg_id:
            # Try base segment if sub-segment not found
            seg_row = segments_df[segments_df['seg_id'] == base_seg_id]
        if seg_row.empty:
            raise ValueError(f"Segment {seg_id} (and base segment {base_seg_id}) missing from segments.csv for flow report export.")
        width_val = seg_row['width_m'].iloc[0]
        if pd.isna(width_val) or width_val == '':
            raise ValueError(f"Segment {seg_id} missing width_m in segments.csv for flow report export.")
        width_m = float(width_val)
        
        # Process each zone in this segment
        # Sort zones by zone_index to ensure consistent ordering
        sorted_zones = sorted(zones, key=lambda z: (
            z.get("zone_index", 0) if isinstance(z, dict) else z.zone_index
        ))
        
        for zone in sorted_zones:
            # Handle both dict (from JSON deserialization) and ConflictZone dataclass objects
            if isinstance(zone, dict):
                metrics = zone.get("metrics", {})
                zone_index = zone.get("zone_index", 0)
                cp_km = zone.get("cp", {}).get("km", 0) if isinstance(zone.get("cp"), dict) else None
                cp_type = zone.get("cp", {}).get("type", "") if isinstance(zone.get("cp"), dict) else ""
                zone_source = zone.get("source", "")
                zone_start_km_a = zone.get("zone_start_km_a", 0)
                zone_end_km_a = zone.get("zone_end_km_a", 0)
                zone_start_km_b = zone.get("zone_start_km_b", 0)
                zone_end_km_b = zone.get("zone_end_km_b", 0)
            else:
                # ConflictZone dataclass object
                metrics = zone.metrics
                zone_index = zone.zone_index
                cp_km = zone.cp.km if zone.cp else None
                cp_type = zone.cp.type if zone.cp else ""
                zone_source = zone.source
                zone_start_km_a = zone.zone_start_km_a
                zone_end_km_a = zone.zone_end_km_a
                zone_start_km_b = zone.zone_start_km_b
                zone_end_km_b = zone.zone_end_km_b
            
            if not isinstance(metrics, dict):
                continue
            
            # Extract zone-level metrics
            zone_overtaking_a = metrics.get("overtaking_a", 0)
            zone_overtaking_b = metrics.get("overtaking_b", 0)
            zone_copresence_a = metrics.get("copresence_a", 0)
            zone_copresence_b = metrics.get("copresence_b", 0)
            zone_unique_encounters = metrics.get("unique_encounters", 0)
            zone_participants_involved = metrics.get("participants_involved", 0)
            
            # Calculate zone-level percentages (using segment totals)
            pct_a = round((zone_overtaking_a / total_a * 100), 1) if total_a > 0 else 0.0
            pct_b = round((zone_overtaking_b / total_b * 100), 1) if total_b > 0 else 0.0
            
            # Issue #629: Field order matches issue table (updated: zone fields after flow_type)
            zone_row = [
                # Keep fields
                seg_id,
                segment_label,
                event_a,
                event_b,
                total_a,
                total_b,
                flow_type,
                # Zone identification fields (moved after flow_type)
                zone_index,
                round(float(cp_km), 2) if cp_km is not None else None,
                cp_type,
                zone_source,
                # Replace fields (zone boundaries)
                round(float(zone_start_km_a), 2),
                round(float(zone_end_km_a), 2),
                round(float(zone_start_km_b), 2),
                round(float(zone_end_km_b), 2),
                width_m,
                # Update fields (zone-level metrics)
                zone_overtaking_a,
                zone_overtaking_b,
                # pct_a, pct_b (keep, calculated at zone level)
                pct_a,
                pct_b,
                zone_copresence_a,
                zone_copresence_b,
                zone_unique_encounters,
                zone_participants_involved,
                # has_convergence (segment-level, repeated per zone)
                has_convergence,
            ]
            
            zone_rows.append(zone_row)
    
    # Write CSV with zone-level rows
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Issue #629: Header matches field order from issue table (updated: zone fields after flow_type)
        writer.writerow([
            "seg_id",
            "segment_label",
            "event_a",
            "event_b",
            "total_a",
            "total_b",
            "flow_type",
            "zone_index",
            "cp_km",
            "cp_type",
            "zone_source",
            "zone_start_km_a",
            "zone_end_km_a",
            "zone_start_km_b",
            "zone_end_km_b",
            "width_m",
            "overtaking_a",
            "overtaking_b",
            "pct_a",
            "pct_b",
            "copresence_a",
            "copresence_b",
            "unique_encounters",
            "participants_involved",
            "has_convergence",
        ])
        
        # Write all zone rows
        writer.writerows(zone_rows)
    
    logger.info(f"Issue #629: Exported zone-level flow.csv with {len(zone_rows)} zones (was segment-level)")
    print(f"📊 Temporal flow analysis exported to: {full_path} ({len(zone_rows)} zones)")
    
    # Issue #455: Skip storage_service for runflow mode (already written to correct location)
    # Also save to storage service for persistence (legacy mode only)
    if not run_id:
        try:
            storage_service = get_storage_service()
            # Extract filename from local path to ensure timestamp consistency
            # (avoid timezone drift between local write and GCS upload)
            storage_filename = os.path.basename(full_path)
            
            # Read the CSV content to save to storage
            with open(full_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
            
            storage_path = storage_service.save_file(storage_filename, csv_content)
            print(f"📊 Flow CSV saved to storage: {storage_path}")
        except Exception as e:
            print(f"⚠️ Failed to save flow CSV to storage: {e}")
    
    # Issue #627: Generate fz.parquet (renamed from flow_zones.parquet) if any segments have zone data
    zones_segments = [seg for seg in segments if "zones" in seg and seg.get("zones")]
    if zones_segments:
        output_dir = os.path.dirname(full_path)
        zones_path = export_flow_zones_parquet(segments, output_dir, run_id, day=day)
        print(f"📊 Flow zones Parquet exported to: {zones_path}")
        
        # Issue #627: Generate fz_runners.parquet alongside fz.parquet
        # This file is NOT gated by audit - it's always exported when zones exist
        runners_path = export_fz_runners_parquet(segments, output_dir, run_id, day=day)
        if runners_path:
            print(f"📊 Flow zone runners Parquet exported to: {runners_path}")
        else:
            print("ℹ️  No runner-zone-role data to export to fz_runners.parquet")
    else:
        print("ℹ️  No zone data to export to fz.parquet")
    
    # Generate Flow Audit CSV if any segments have audit data
    audit_segments = [seg for seg in segments if "flow_audit_data" in seg]
    if audit_segments:
        # Extract output directory from the CSV path
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


def export_flow_zones_parquet(segments: List[Dict[str, Any]], output_dir: str, run_id: str = None, day: str = None) -> str:
    """
    Export flow zones data to Parquet format.
    
    Issue #627: Creates {day}_fz.parquet with one row per zone, containing:
    - seg_id, event_a, event_b, zone_index, cp_km, zone boundaries, metrics
    
    Args:
        segments: List of segment result dictionaries with zone data
        output_dir: Directory to save the Parquet file
        run_id: Optional run ID for path organization
        day: Day prefix for filename (e.g., "sat", "sun") - if None, no prefix
        
    Returns:
        Path to the created Parquet file
    """
    from dataclasses import asdict
    from pathlib import Path
    
    # Collect all zones from all segments
    zones_rows = []
    
    for segment in segments:
        seg_id = segment.get("seg_id", "")
        event_a = segment.get("event_a", "")
        event_b = segment.get("event_b", "")
        zones = segment.get("zones", [])
        
        if not zones:
            continue
        
        # Convert each zone to a row
        # Handle both dict (from JSON deserialization) and ConflictZone dataclass objects (from direct analysis)
        for zone in zones:
            # Handle dict (from JSON deserialization in v2 pipeline - Issue #612: now properly serialized)
            if isinstance(zone, dict):
                cp = zone.get("cp", {})
                metrics = zone.get("metrics", {})
                zone_row = {
                    "seg_id": seg_id,
                    "event_a": event_a,
                    "event_b": event_b,
                    "zone_index": zone.get("zone_index", 0),
                    "cp_km": round(float(cp.get("km", 0)), 2) if isinstance(cp, dict) else 0.0,
                    "cp_type": str(cp.get("type", "unknown")) if isinstance(cp, dict) else "unknown",
                    "zone_source": str(zone.get("source", "unknown")),
                    "zone_start_km_a": round(float(zone.get("zone_start_km_a", 0)), 2),
                    "zone_end_km_a": round(float(zone.get("zone_end_km_a", 0)), 2),
                    "zone_start_km_b": round(float(zone.get("zone_start_km_b", 0)), 2),
                    "zone_end_km_b": round(float(zone.get("zone_end_km_b", 0)), 2),
                    "overtaking_a": metrics.get("overtaking_a", 0) if isinstance(metrics, dict) else 0,
                    "overtaking_b": metrics.get("overtaking_b", 0) if isinstance(metrics, dict) else 0,
                    "overtaken_a": metrics.get("overtaken_a", 0) if isinstance(metrics, dict) else 0,  # Issue #620: A runners overtaken by B
                    "overtaken_b": metrics.get("overtaken_b", 0) if isinstance(metrics, dict) else 0,  # Issue #620: B runners overtaken by A
                    "copresence_a": metrics.get("copresence_a", 0) if isinstance(metrics, dict) else 0,
                    "copresence_b": metrics.get("copresence_b", 0) if isinstance(metrics, dict) else 0,
                    "unique_encounters": metrics.get("unique_encounters", 0) if isinstance(metrics, dict) else 0,
                    "participants_involved": metrics.get("participants_involved", 0) if isinstance(metrics, dict) else 0,
                    "multi_category_runners": metrics.get("multi_category_runners", 0) if isinstance(metrics, dict) else 0,  # Issue #622: Overlap count for validation
                }
                zones_rows.append(zone_row)
            # Handle ConflictZone dataclass object (direct from analysis)
            else:
                metrics = zone.metrics
                zone_row = {
                    "seg_id": seg_id,
                    "event_a": event_a,
                    "event_b": event_b,
                    "zone_index": zone.zone_index,
                    "cp_km": round(zone.cp.km, 2),
                    "cp_type": zone.cp.type,
                    "zone_source": zone.source,
                    "zone_start_km_a": round(zone.zone_start_km_a, 2),
                    "zone_end_km_a": round(zone.zone_end_km_a, 2),
                    "zone_start_km_b": round(zone.zone_start_km_b, 2),
                    "zone_end_km_b": round(zone.zone_end_km_b, 2),
                    "overtaking_a": metrics.get("overtaking_a", 0),
                    "overtaking_b": metrics.get("overtaking_b", 0),
                    "overtaken_a": metrics.get("overtaken_a", 0),  # Issue #620: A runners overtaken by B
                    "overtaken_b": metrics.get("overtaken_b", 0),  # Issue #620: B runners overtaken by A
                    "copresence_a": metrics.get("copresence_a", 0),
                    "copresence_b": metrics.get("copresence_b", 0),
                    "unique_encounters": metrics.get("unique_encounters", 0),
                    "participants_involved": metrics.get("participants_involved", 0),
                    "multi_category_runners": metrics.get("multi_category_runners", 0),  # Issue #622: Overlap count for validation
                }
                zones_rows.append(zone_row)
    
    if not zones_rows:
        # No zones to export
        return ""
    
    # Create DataFrame and write to Parquet
    zones_df = pd.DataFrame(zones_rows)
    
    # Determine output path with day prefix
    output_path = Path(output_dir)
    if day:
        filename = f"{day}_fz.parquet"
    else:
        filename = "fz.parquet"
    zones_path = output_path / filename
    
    # Write Parquet file
    zones_df.to_parquet(zones_path, index=False, engine='pyarrow')
    
    return str(zones_path)


def export_fz_runners_parquet(segments: List[Dict[str, Any]], output_dir: str, run_id: str = None, day: str = None) -> str:
    """
    Export flow zone participants to Parquet format.
    
    Issue #627: Creates {day}_fz_runners.parquet with one row per (runner, zone, role).
    This file contains runner-level participation in flow zones, enabling:
    - Traceability: which runners were involved in each zone
    - Runner-centric analytics: experience scores, density exposure
    - Drill-downs: who was overtaken, where, how many times
    
    Schema:
    - seg_id: Segment ID (e.g., A2a)
    - zone_index: Index of the zone within the segment
    - runner_id: Unique runner ID (bib number)
    - event: Event name (e.g., "10k", "half")
    - role: One of "overtaking", "overtaken", "copresent"
    - side: "a" or "b" (event A or event B)
    
    Args:
        segments: List of segment result dictionaries with zone data
        output_dir: Directory to save the Parquet file
        run_id: Optional run ID for path organization
        day: Day prefix for filename (e.g., "sat", "sun") - if None, no prefix
        
    Returns:
        Path to the created Parquet file, or empty string if no zones/runners
    """
    from pathlib import Path
    import logging
    logger = logging.getLogger(__name__)
    
    # Collect all runner-zone-role rows
    runners_rows = []
    
    # Debug: Track segments and zones with/without internal sets
    segments_processed = 0
    segments_with_runner_data = 0
    zones_with_internal_sets = 0
    zones_without_internal_sets = 0
    segments_skipped_no_zones = 0
    
    for segment in segments:
        seg_id = segment.get("seg_id", "")
        event_a = segment.get("event_a", "")
        event_b = segment.get("event_b", "")
        zones = segment.get("zones", [])
        
        if not zones:
            segments_skipped_no_zones += 1
            continue
        
        segments_processed += 1
        segment_has_runner_data = False
        segment_zones_with_sets = 0
        segment_zones_without_sets = 0
        rows_before_segment = len(runners_rows)
        
        # Process each zone
        for zone in zones:
            # Handle both dict (from JSON deserialization) and ConflictZone dataclass objects
            if isinstance(zone, dict):
                metrics = zone.get("metrics", {})
                zone_index = zone.get("zone_index", 0)
            else:
                metrics = zone.metrics
                zone_index = zone.zone_index
            
            if not isinstance(metrics, dict):
                continue
            
            # Extract runner sets from metrics (internal sets used for zone aggregation)
            # Issue #627: These sets are available in zone metrics from calculate_zone_metrics_vectorized_direct
            # and calculate_zone_metrics_vectorized_binned
            a_bibs_overtakes = metrics.get("_a_bibs_overtakes", set())
            a_bibs_overtaken = metrics.get("_a_bibs_overtaken", set())
            a_bibs_copresence = metrics.get("_a_bibs_copresence", set())
            b_bibs_overtakes = metrics.get("_b_bibs_overtakes", set())
            b_bibs_overtaken = metrics.get("_b_bibs_overtaken", set())
            b_bibs_copresence = metrics.get("_b_bibs_copresence", set())
            
            # Debug: Check if internal sets are present and non-empty
            internal_set_keys = [
                "_a_bibs_overtakes",
                "_a_bibs_overtaken",
                "_a_bibs_copresence",
                "_b_bibs_overtakes",
                "_b_bibs_overtaken",
                "_b_bibs_copresence",
            ]
            has_internal_sets = any(
                k in metrics and metrics[k] and len(metrics[k]) > 0
                for k in internal_set_keys
            )
            
            # Check if zone has zero counts (all interaction metrics are 0)
            # This indicates the zone exists but has no runner interactions
            has_zero_counts = (
                metrics.get("overtaking_a", 0) == 0 and
                metrics.get("overtaking_b", 0) == 0 and
                metrics.get("overtaken_a", 0) == 0 and
                metrics.get("overtaken_b", 0) == 0 and
                metrics.get("copresence_a", 0) == 0 and
                metrics.get("copresence_b", 0) == 0
            )
            
            if has_internal_sets:
                zones_with_internal_sets += 1
                segment_zones_with_sets += 1
                segment_has_runner_data = True
            else:
                zones_without_internal_sets += 1
                segment_zones_without_sets += 1
                
                # Log zones skipped due to zero counts (zone exists but has no interactions)
                if has_zero_counts:
                    # Log at INFO level since this is expected behavior for empty zones
                    logger.info(
                        f"[fz_runners] Zone {seg_id} index={zone_index} skipped - zero counts "
                        f"(no runner interactions: overtaking_a=0, overtaking_b=0, overtaken_a=0, "
                        f"overtaken_b=0, copresence_a=0, copresence_b=0)"
                    )
                else:
                    # Log missing internal sets for debugging (limit to avoid log spam)
                    # This case indicates internal sets are missing (not just empty)
                    if zones_without_internal_sets <= 10:
                        logger.debug(
                            f"[fz_runners] Zone {seg_id} index={zone_index} - no internal runner sets. "
                            f"Metrics keys: {list(metrics.keys())[:10]}..."
                        )
            
            # Convert sets to lists if needed (handle JSON deserialization)
            def normalize_set(s):
                if isinstance(s, list):
                    return set(s)
                elif isinstance(s, set):
                    return s
                else:
                    return set()
            
            a_bibs_overtakes = normalize_set(a_bibs_overtakes)
            a_bibs_overtaken = normalize_set(a_bibs_overtaken)
            a_bibs_copresence = normalize_set(a_bibs_copresence)
            b_bibs_overtakes = normalize_set(b_bibs_overtakes)
            b_bibs_overtaken = normalize_set(b_bibs_overtaken)
            b_bibs_copresence = normalize_set(b_bibs_copresence)
            
            # Emit rows for event A runners
            # Role: overtaking (A runners who overtook B runners)
            for runner_id in a_bibs_overtakes:
                runners_rows.append({
                    "seg_id": seg_id,
                    "zone_index": zone_index,
                    "runner_id": int(runner_id) if isinstance(runner_id, (int, str)) and str(runner_id).isdigit() else runner_id,
                    "event": event_a,
                    "role": "overtaking",
                    "side": "a",
                })
            
            # Role: overtaken (A runners who were overtaken by B runners)
            for runner_id in a_bibs_overtaken:
                runners_rows.append({
                    "seg_id": seg_id,
                    "zone_index": zone_index,
                    "runner_id": int(runner_id) if isinstance(runner_id, (int, str)) and str(runner_id).isdigit() else runner_id,
                    "event": event_a,
                    "role": "overtaken",
                    "side": "a",
                })
            
            # Role: copresent (A runners who were copresent with B runners)
            for runner_id in a_bibs_copresence:
                runners_rows.append({
                    "seg_id": seg_id,
                    "zone_index": zone_index,
                    "runner_id": int(runner_id) if isinstance(runner_id, (int, str)) and str(runner_id).isdigit() else runner_id,
                    "event": event_a,
                    "role": "copresent",
                    "side": "a",
                })
            
            # Emit rows for event B runners
            # Role: overtaking (B runners who overtook A runners)
            for runner_id in b_bibs_overtakes:
                runners_rows.append({
                    "seg_id": seg_id,
                    "zone_index": zone_index,
                    "runner_id": int(runner_id) if isinstance(runner_id, (int, str)) and str(runner_id).isdigit() else runner_id,
                    "event": event_b,
                    "role": "overtaking",
                    "side": "b",
                })
            
            # Role: overtaken (B runners who were overtaken by A runners)
            for runner_id in b_bibs_overtaken:
                runners_rows.append({
                    "seg_id": seg_id,
                    "zone_index": zone_index,
                    "runner_id": int(runner_id) if isinstance(runner_id, (int, str)) and str(runner_id).isdigit() else runner_id,
                    "event": event_b,
                    "role": "overtaken",
                    "side": "b",
                })
            
            # Role: copresent (B runners who were copresent with A runners)
            for runner_id in b_bibs_copresence:
                runners_rows.append({
                    "seg_id": seg_id,
                    "zone_index": zone_index,
                    "runner_id": int(runner_id) if isinstance(runner_id, (int, str)) and str(runner_id).isdigit() else runner_id,
                    "event": event_b,
                    "role": "copresent",
                    "side": "b",
                })
        
        # Track segments that contributed runner data
        rows_after_segment = len(runners_rows)
        rows_added_this_segment = rows_after_segment - rows_before_segment
        
        if segment_has_runner_data:
            segments_with_runner_data += 1
            logger.debug(
                f"[fz_runners] Segment {seg_id}: {segment_zones_with_sets} zones with sets, "
                f"{segment_zones_without_sets} zones without sets, {rows_added_this_segment} runner rows added"
            )
        elif segment_zones_without_sets > 0:
            # Log segments that have zones but no internal sets (helpful for debugging)
            logger.debug(
                f"[fz_runners] Segment {seg_id}: {len(zones)} zones, but none have internal sets "
                f"({segment_zones_without_sets} zones checked)"
            )
    
    # Debug: Log summary statistics
    logger.info(
        f"[fz_runners] Export summary: {segments_processed} segments processed, "
        f"{segments_with_runner_data} segments with runner data, "
        f"{segments_skipped_no_zones} segments skipped (no zones), "
        f"{zones_with_internal_sets} zones with internal sets, "
        f"{zones_without_internal_sets} zones without internal sets, "
        f"{len(runners_rows)} total runner rows"
    )
    
    if not runners_rows:
        # No runner-zone-role data to export
        logger.warning(
            f"[fz_runners] No runner rows generated. "
            f"Processed {segments_processed} segments with zones, "
            f"but {zones_without_internal_sets} zones had no internal sets."
        )
        return ""
    
    # Create DataFrame and write to Parquet
    runners_df = pd.DataFrame(runners_rows)
    
    # Determine output path with day prefix
    output_path = Path(output_dir)
    if day:
        filename = f"{day}_fz_runners.parquet"
    else:
        filename = "fz_runners.parquet"
    runners_path = output_path / filename
    
    # Write Parquet file
    runners_df.to_parquet(runners_path, index=False, engine='pyarrow')
    
    return str(runners_path)


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
        "reason_codes", "audit_trigger",
        # Issue #612: Multi-zone fields
        "zone_index", "cp_km", "zone_source"
    ]
    
    import csv
    with open(full_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(audit_header)
        
        # Write audit data for segments that have flow_audit_data
        for segment in segments:
            if "flow_audit_data" in segment:
                audit_data = segment["flow_audit_data"]
                seg_id = segment.get("seg_id")
                seg_label = segment.get("segment_label")
                if not seg_id:
                    raise ValueError("Flow audit segment missing seg_id.")
                if not seg_label:
                    raise ValueError(f"Segment {seg_id} missing segment_label for flow audit.")
                audit_data["seg_id"] = seg_id
                audit_data["segment_label"] = seg_label
                
                # Write row with all 33 columns
                writer.writerow([
                    audit_data["seg_id"],
                    audit_data["segment_label"],
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
                    audit_data.get("audit_trigger", ""),
                    # Issue #612: Multi-zone fields
                    audit_data.get("zone_index"),
                    audit_data.get("cp_km"),
                    audit_data.get("zone_source", "")
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
        # Lazy import - will fail if flow_density_correlation.py dependencies are missing
        from app.flow_density_correlation import analyze_flow_density_correlation
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
