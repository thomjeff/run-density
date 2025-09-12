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


# LOS Thresholds for density classification (updated to match v2 rulebook)
LOS_AREAL_THRESHOLDS = {
    'A': (0.0, 0.36),    # Free Flow
    'B': (0.36, 0.54),   # Comfortable
    'C': (0.54, 0.72),   # Moderate
    'D': (0.72, 1.08),   # Dense
    'E': (1.08, 1.63),   # Very Dense
    'F': (1.63, float('inf'))  # Extremely Dense
}

LOS_CROWD_THRESHOLDS = {
    'A': (0.0, 0.2),     # Free Flow
    'B': (0.2, 0.4),     # Comfortable
    'C': (0.4, 0.6),     # Moderate
    'D': (0.6, 0.8),     # Dense
    'E': (0.8, 1.0),     # Very Dense
    'F': (1.0, float('inf'))  # Extremely Dense
}


def render_segment(md, ctx, rulebook):
    """Render a segment using v2.0 rulebook structure."""
    # Handle v2.0 rulebook structure
    if "schemas" in rulebook:
        # v2.0 rulebook - use schema-based rendering
        segment_id = ctx.get("segment_id", "")
        segment_label = ctx.get("segment_label", "")
        density_value = ctx.get("density_value", 0.0)
        
        # Determine schema based on segment_id or segment_type
        schema_name = _determine_schema_for_segment(segment_id, ctx, rulebook)
        schema = rulebook.get("schemas", {}).get(schema_name, {})
        
        # Generate narrative based on schema
        if schema:
            # Check for flow_type zone content first
            flow_type = ctx.get("flow_type", "")
            if flow_type:
                flow_key = f"{flow_type}_zone"
                flow_drivers = schema.get(flow_key, {})
                if flow_drivers and "narrative_template" in flow_drivers:
                    md.write(flow_drivers["narrative_template"].format(**ctx) + "\n\n")
            
            # Then add general schema content
            drivers = schema.get("drivers", [])
            mitigations = schema.get("mitigations", [])
            
            if drivers:
                md.write("### Density Analysis\n")
                for driver in drivers:
                    md.write(f"- {driver}\n")
                md.write("\n")
            
            if mitigations:
                md.write("### Operational Implications\n")
                for mitigation in mitigations:
                    md.write(f"- {mitigation}\n")
                md.write("\n")
            
            # Check for operational guidance
            ops_box = schema.get("ops_box", {})
            if ops_box:
                md.write("### Ops Box\n")
                for category, items in ops_box.items():
                    if items:
                        md.write(f"- **{category.title()}:** {', '.join(items)}\n")
                md.write("\n")
        
        # Check triggers for this segment and show triggered actions
        triggers = rulebook.get("triggers", [])
        triggered_actions = []
        
        for trigger in triggers:
            if _trigger_matches(trigger, ctx, schema_name):
                actions = trigger.get("actions", [])
                if actions:
                    # Add trigger context to actions
                    when = trigger.get("when", {})
                    trigger_type = "Density" if "density_gte" in when else "Flow" if "flow_gte" in when else "General"
                    threshold = when.get("density_gte", when.get("flow_gte", "threshold"))
                    
                    for action in actions:
                        triggered_actions.append(f"[{trigger_type} {threshold}] {action}")
        
        # Check for high density warnings (adapted from v1.x patches)
        if ctx.get("is_high_density"):
            # Look for high density triggers
            for trigger in triggers:
                if (trigger.get("when", {}).get("density_gte") in ["E", "F"] and 
                    _trigger_matches(trigger, ctx, schema_name)):
                    actions = trigger.get("actions", [])
                    if actions:
                        for action in actions:
                            triggered_actions.append(f"[High Density] {action}")
        
        # Display triggered actions if any
        if triggered_actions:
            md.write("### Triggered Actions\n")
            for action in triggered_actions:
                md.write(f"- {action}\n")
            md.write("\n")
        
        # Check for event-specific factors (adapted from v1.x patches)
        event_type = ctx.get("event_type", "").lower()
        if event_type:
            # Look for event-specific overrides
            overrides = rulebook.get("overrides", [])
            for override in overrides:
                if override.get("match", {}).get("segment_id") == segment_id:
                    notes = override.get("notes", [])
                    if notes:
                        md.write("_Event factors_: " + "; ".join(notes) + "\n\n")
        
        # Fallback if no schema found
        if not schema:
            md.write(f"**Segment {segment_id} ({segment_label})** — density {density_value:.3f} runners/m²\n\n")
    
    else:
        # Legacy v1.x rulebook structure
        drivers = rulebook["templates"]["drivers"]
        safety  = rulebook["templates"]["safety"]
        events  = rulebook["templates"]["events"]

        flow_key = f"{ctx.get('flow_type','')}_zone"
        if flow_key in drivers:
            md.write(drivers[flow_key]["narrative_template"].format(**ctx) + "\n\n")

        dclass = ctx.get("density_class")
        if dclass and dclass in drivers:
            md.write(drivers[dclass]["narrative_template"].format(**ctx) + "\n\n")
        else:
            # Linear vs Areal density label clarity
            # Uncomment depending on computation:
            # md.write(f"**Segment {ctx['segment_id']} ({ctx['segment_label']})** — linear density {ctx['density_value']} runners/m\n\n")
            # md.write(f"**Segment {ctx['segment_id']} ({ctx['segment_label']})** — density {ctx['density_value']} runners/m²\n\n")
            md.write(f"**Segment {ctx['segment_id']} ({ctx['segment_label']})** — density {ctx['density_value']}\n\n")

        if ctx.get("is_high_density"):
            if "high_density_warning" in safety:
                md.write(safety["high_density_warning"].format(**ctx) + "\n")
            if "flow_control_suggestion" in safety:
                md.write(safety["flow_control_suggestion"].format(**ctx) + "\n")
            md.write("\n")

        et = (ctx.get("event_type") or "").lower()
        if et in events:
            factors = events[et].get("additional_factors", [])
            if factors:
                md.write("_Event factors_: " + "; ".join(factors) + "\n\n")


def render_methodology(md, rulebook):
    """Render methodology section using v2.0 rulebook structure."""
    # Handle v2.0 rulebook structure
    if "schemas" in rulebook:
        # v2.0 rulebook - use meta information
        meta = rulebook.get("meta", {})
        units = meta.get("units", {})
        density_unit = units.get("density", "runners/m²")
        flow_unit = units.get("flow", "runners/min/m")
        
        md.write("## Methodology\n\n")
        md.write(f"**Units**: Density thresholds use *{density_unit}* (areal density). ")
        md.write(f"Flow thresholds use *{flow_unit}* (throughput per meter of width).\n\n")
        
        notes = meta.get("notes", [])
        if notes:
            md.write("**Notes:**\n")
            for note in notes:
                md.write(f"- {note}\n")
            md.write("\n")
    else:
        # Legacy v1.x rulebook structure
        meth = rulebook["templates"]["report_sections"]["methodology"]
        md.write(meth + "\n\n> **Units**: thresholds in rulebook currently use *runners per meter (linear)*. "
                 "If you compute areal density, label as **runners/m²** and adjust thresholds accordingly.\n\n")


def _determine_schema_for_segment(segment_id, ctx, rulebook):
    """Determine which schema to use for a segment based on v2.0 rulebook binding rules."""
    binding_rules = rulebook.get("binding", [])
    
    for rule in binding_rules:
        when = rule.get("when", {})
        
        # Check segment_id match
        if "segment_id" in when and when["segment_id"] == segment_id:
            return rule.get("use_schema", "on_course_open")
        
        # Check segment_type match
        if "segment_type" in when:
            segment_types = when["segment_type"]
            if isinstance(segment_types, str):
                segment_types = [segment_types]
            
            # Use flow_type from context if available, otherwise map segment_id
            segment_type = ctx.get("flow_type", _map_segment_id_to_type(segment_id))
            if segment_type in segment_types:
                return rule.get("use_schema", "on_course_open")
    
    # Default fallback
    return "on_course_open"


def _map_segment_id_to_type(segment_id):
    """Map segment_id to segment_type for v2.0 rulebook."""
    segment_id_lower = segment_id.lower()
    
    if segment_id.startswith("A"):
        return "start"
    elif "merge" in segment_id_lower:
        return "merge"
    elif "bridge" in segment_id_lower:
        return "bridge"
    elif "finish" in segment_id_lower:
        return "finish"
    elif "funnel" in segment_id_lower:
        return "funnel"
    elif any(x in segment_id_lower for x in ["road", "trail", "turn"]):
        return "road"  # or "trail", "turn" as appropriate
    else:
        return "road"  # default


def _trigger_matches(trigger, ctx, schema_name):
    """Check if a trigger matches the current context."""
    when = trigger.get("when", {})
    
    # Check schema match
    if "schema" in when and when["schema"] != schema_name:
        return False
    
    # Check density threshold
    if "density_gte" in when:
        density_value = ctx.get("density_value", 0.0)
        threshold = when["density_gte"]
        if threshold == "E" and density_value < 1.08:
            return False
        elif threshold == "F" and density_value < 1.63:
            return False
    
    # Check flow threshold (placeholder - would need actual flow data)
    if "flow_gte" in when:
        # This would need actual flow data integration
        pass
    
    return True


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
    
    # Methodology section using v2.0 rulebook
    try:
        import yaml
        with open("data/density_rulebook.yml", "r") as f:
            rulebook = yaml.safe_load(f)
        
        from io import StringIO
        md_buffer = StringIO()
        render_methodology(md_buffer, rulebook)
        methodology_content = md_buffer.getvalue()
        
        if methodology_content.strip():
            content.extend(methodology_content.strip().split('\n'))
            content.append("")
    except Exception as e:
        # Fallback methodology
        content.append("## Methodology")
        content.append("")
        content.append("**Units**: Density thresholds use *runners/m²* (areal density).")
        content.append("")
    
    # Definitions section
    content.append("## Definitions")
    content.append("")
    content.append("- **gte**: Greater than or equal to (used in trigger conditions like density_gte, flow_gte)")
    content.append("- **TOT**: Time Over Threshold (seconds above E/F LOS thresholds)")
    content.append("- **LOS**: Level of Service (A=Free Flow, B=Comfortable, C=Moderate, D=Dense, E=Very Dense, F=Extremely Dense)")
    content.append("- **Experienced Density**: What runners actually experience (includes co-present runners from other events)")
    content.append("- **Self Density**: Only that event's runners (not shown in this report)")
    content.append("- **Active Window**: Time period when the event has runners present in the segment")
    content.append("- **Ops Box**: Operational guidance for race marshals and organizers")
    content.append("- **Triggered Actions**: Safety alerts and operational responses when density/flow thresholds are exceeded")
    content.append("")
    
    # LOS Thresholds Table
    content.append("## Level of Service Thresholds")
    content.append("")
    content.append("| LOS | Areal Density (runners/m²) | Crowd Density (runners/m) | Description |")
    content.append("|-----|---------------------------|--------------------------|-------------|")
    content.append("| A | 0.00 - 0.36 | 0.00 - 0.20 | Free Flow |")
    content.append("| B | 0.36 - 0.54 | 0.20 - 0.40 | Comfortable |")
    content.append("| C | 0.54 - 0.72 | 0.40 - 0.60 | Moderate |")
    content.append("| D | 0.72 - 1.08 | 0.60 - 0.80 | Dense |")
    content.append("| E | 1.08 - 1.63 | 0.80 - 1.00 | Very Dense |")
    content.append("| F | 1.63+ | 1.00+ | Extremely Dense |")
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
        # Load the rulebook
        import yaml
        with open("data/density_rulebook.yml", "r") as f:
            rulebook = yaml.safe_load(f)
        
        # Get density value from summary object
        summary = segment_data.get("summary")
        if hasattr(summary, 'active_peak_areal'):
            density_value = summary.active_peak_areal
        else:
            density_value = 0.0
        
        # Create context for v2.0 rulebook
        ctx = {
            "segment_id": segment_id,
            "segment_label": segment_data.get("seg_label", "Unknown"),
            "density_value": density_value,
            "flow_type": segment_data.get("flow_type", "default"),  # Extract from segment data
            "event_type": "default"
        }
        
        # Use v2.0 rulebook rendering
        from io import StringIO
        md_buffer = StringIO()
        render_segment(md_buffer, ctx, rulebook)
        narrative_content = md_buffer.getvalue()
        
        if narrative_content.strip():
            content.append("### Template-Driven Analysis")
            content.append("")
            content.extend(narrative_content.strip().split('\n'))
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
