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

# Import storage service for persistent file storage
try:
    from .storage_service import get_storage_service
except ImportError:
    from storage_service import get_storage_service

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
import json
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


def classify_los_areal(density: float) -> str:
    """Classify LOS based on areal density using standard thresholds."""
    for letter, (min_density, max_density) in LOS_AREAL_THRESHOLDS.items():
        if min_density <= density < max_density:
            return letter
    return 'F'  # Default to F for very high densities


def format_los_with_color(los_letter: str) -> str:
    """Format LOS letter with color-coded emoji indicators for better scanability."""
    color_map = {
        'A': '🟢 A',  # Green - Free Flow
        'B': '🟢 B',  # Green - Comfortable  
        'C': '🟡 C',  # Yellow - Moderate
        'D': '🟡 D',  # Yellow - Dense
        'E': '🔴 E',  # Red - Very Dense
        'F': '🔴 F'   # Red - Extremely Dense
    }
    return color_map.get(los_letter, f'❓ {los_letter}')


def generate_summary_table(segments_data: Dict[str, Any]) -> List[str]:
    """Generate TL;DR summary table for quick scanning by race directors."""
    content = []
    
    content.append("## Executive Summary")
    content.append("")
    content.append("| Segment | Label | Key Takeaway | LOS |")
    content.append("|---------|-------|--------------|-----|")
    
    for segment_id, segment_data in segments_data.items():
        # Extract key information
        seg_label = segment_data.get('seg_label', 'Unknown')
        v2_context = segment_data.get('v2_context', {})
        
        # Get LOS and format with color - fallback to summary if v2_context not available
        los_letter = v2_context.get('los')
        if not los_letter:
            # Fallback to summary-based LOS calculation
            summary = segment_data.get('summary', {})
            areal_density = summary.get('peak_areal_density', 0)
            los_letter = classify_los_areal(areal_density)
        
        los_display = format_los_with_color(los_letter)
        
        # Generate key takeaway based on segment type and metrics
        key_takeaway = generate_key_takeaway(segment_id, segment_data, v2_context)
        
        content.append(f"| {segment_id} | {seg_label} | {key_takeaway} | {los_display} |")
    
    content.append("")
    content.append("*Full details in per-segment sections below.*")
    content.append("")
    
    return content


def generate_key_takeaway(segment_id: str, segment_data: Dict[str, Any], v2_context: Dict[str, Any]) -> str:
    """Generate a concise key takeaway for each segment."""
    # Start corral logic
    if segment_id == 'A1':
        flow_rate = v2_context.get('flow_rate', 0)
        if flow_rate > 150:
            return "High release flow - monitor for surges"
        elif flow_rate > 100:
            return "Moderate release flow - stable"
        else:
            return "Low release flow - consider wave adjustments"
    
    # Merge segment logic
    elif segment_id == 'F1':
        flow_utilization = v2_context.get('flow_utilization', 0)
        if flow_utilization > 200:
            return "⚠️ Supply > Capacity - risk of congestion"
        elif flow_utilization > 150:
            return "High flow utilization - monitor closely"
        else:
            return "Flow within capacity - stable"
    
    # General segment logic
    else:
        los_letter = v2_context.get('los', 'Unknown')
        density = v2_context.get('areal_density', 0)
        
        if los_letter in ['E', 'F']:
            return f"High density ({density:.2f} p/m²) - extra marshals needed"
        elif los_letter in ['C', 'D']:
            return f"Moderate density ({density:.2f} p/m²) - maintain cadence"
        else:
            return f"Low density ({density:.2f} p/m²) - comfortable flow"


def render_segment_v2(md, ctx, rulebook):
    """Render a segment using v2.0 rulebook structure with schema-specific formatting."""
    # Get schema information
    schema_name = ctx.get("schema_name", "on_course_open")
    flow_rate = ctx.get("flow_rate")
    flow_capacity = ctx.get("flow_capacity")
    flow_utilization = ctx.get("flow_utilization")
    fired_actions = ctx.get("fired_actions", [])
    
    # Get schema configuration
    schemas = rulebook.get("schemas", {})
    schema_config = schemas.get(schema_name, {})
    
    # Get LOS thresholds for this schema
    los_thresholds = schema_config.get("los_thresholds", 
                                     rulebook.get("globals", {}).get("los_thresholds", {}))
    
    # Determine LOS from areal density
    areal_density = ctx.get("peak_areal_density", 0.0)
    los_letter = "F"  # Default to worst case
    for letter in ["A", "B", "C", "D", "E", "F"]:
        rng = los_thresholds.get(letter, {})
        mn = rng.get("min", float("-inf"))
        mx = rng.get("max", float("inf"))
        if areal_density >= mn and areal_density < mx:
            los_letter = letter
            break
    
    # Render header with schema info (reduced heading size)
    md.write(f"### Segment {ctx['segment_id']} — {ctx['seg_label']}\n\n")
    
    # Render metrics table (reduced heading size)
    md.write("#### Metrics\n\n")
    md.write("| Metric | Value | Units |\n")
    md.write("|--------|-------|-------|\n")
    
    # Areal density (always shown)
    md.write(f"| Density | {areal_density:.2f} | p/m² |\n")
    
    # For narrow/merge segments, show linear density
    if schema_name in ["on_course_narrow"]:
        # Calculate linear density from areal density and width
        width_m = ctx.get("width_m", 3.0)  # Default width
        linear_density = areal_density * width_m
        md.write(f"| Linear Density | {linear_density:.2f} | p/m |\n")
    
    # Flow rate (if enabled)
    if flow_rate is not None:
        md.write(f"| Flow Rate | {flow_rate:.0f} | p/min/m |\n")
    
    # For merge segments, show supply vs capacity
    if schema_name in ["on_course_narrow"] and flow_capacity is not None and flow_utilization is not None:
        flow_supply = flow_rate * ctx.get("width_m", 3.0) if flow_rate else 0
        md.write(f"| Flow (Supply) | {flow_supply:.0f} | p/min |\n")
        md.write(f"| Flow (Capacity) | {flow_capacity:.0f} | p/min |\n")
        md.write(f"| Flow Utilization | {flow_utilization:.1f}% | — |\n")
    
    # LOS with color coding
    los_display = format_los_with_color(los_letter)
    md.write(f"| LOS | {los_display} ({schema_name.replace('_', ' ').title()}) | — |\n")
    
    # Add note about schema if start_corral
    if schema_name == "start_corral":
        md.write("\n| Note: LOS here uses start-corral thresholds, not Fruin. Flow-rate governs safety. |\n")
    elif schema_name == "on_course_narrow":
        md.write("\n| Note: LOS uses Fruin thresholds (linear density). |\n")
    
    # Add Key Takeaways line
    md.write("\n### Key Takeaways\n\n")
    
    # Determine status based on LOS and flow
    if los_letter in ["A", "B"]:
        if flow_utilization and flow_utilization > 200:
            md.write("⚠️ **Overload**: Flow utilization exceeds 200% - consider flow management.\n\n")
        else:
            md.write("✅ **Stable**: Density and flow within acceptable ranges.\n\n")
    elif los_letter in ["C", "D"]:
        md.write("⚠️ **Moderate**: Density approaching comfort limits - monitor closely.\n\n")
    else:  # E, F
        md.write("🔴 **Critical**: High density detected - immediate action required.\n\n")
    
    # Render operational implications
    md.write("### Operational Implications\n\n")
    
    # Get mitigations from schema
    mitigations = schema_config.get("mitigations", [])
    drivers = schema_config.get("drivers", [])
    
    # Add driver context
    if drivers:
        md.write("• " + drivers[0] + "\n")
    
    # Add LOS-specific guidance with consistent descriptions
    los_descriptions = {
        "A": "Free Flow - Excellent conditions, no restrictions needed",
        "B": "Comfortable - Good conditions, minor monitoring may be helpful", 
        "C": "Moderate - Acceptable conditions, regular monitoring recommended",
        "D": "Dense - Crowded conditions, active management may be needed",
        "E": "Very Dense - Crowded conditions, active management required",
        "F": "Extremely Dense - Critical conditions, immediate intervention needed"
    }
    los_label = los_descriptions.get(los_letter, "Unknown conditions")
    md.write(f"• At LOS {los_letter} ({los_label}).\n")
    
    # Add flow-specific guidance if available
    if flow_rate is not None:
        flow_ref = schema_config.get("flow_ref", {})
        critical_flow = flow_ref.get("critical", 600)
        if flow_rate >= critical_flow:
            md.write(f"• Flow of {flow_rate:.0f} p/min/m exceeds critical threshold ({critical_flow} p/min/m).\n")
        else:
            md.write(f"• Flow of {flow_rate:.0f} p/min/m is within acceptable range.\n")
    
    # Add merge-specific guidance
    if schema_name in ["on_course_narrow"] and flow_utilization and flow_utilization > 200:
        md.write(f"• **Flow Overload**: Supply ({flow_rate * ctx.get('width_m', 3.0):.0f} p/min) exceeds capacity ({flow_capacity:.0f} p/min) by {flow_utilization:.0f}%.\n")
        md.write("• Consider implementing flow metering or temporary holds upstream.\n")
    
    # Add fired actions if any
    if fired_actions:
        md.write("\n### Mitigations Fired\n\n")
        for action in fired_actions:
            md.write(f"• {action}\n")
    
    # Add operational box if available
    ops_box = schema_config.get("ops_box", {})
    if ops_box:
        md.write("\n### Operational Notes\n\n")
        for category, notes in ops_box.items():
            if notes:
                md.write(f"**{category.title()}:**\n")
                for note in notes:
                    md.write(f"• {note}\n")
                md.write("\n")
    
    # Add definitions (only once per report)
    if not hasattr(render_segment_v2, '_definitions_added'):
        md.write("\n📖 Definitions:\n\n")
        md.write("• Density = persons per square meter (p/m²).\n")
        md.write("• Linear Density = persons per meter (p/m).\n")
        if flow_rate is not None:
            md.write("• Flow Rate = persons per minute per meter (p/min/m).\n")
            md.write("• Flow Supply = total persons per minute through segment.\n")
            md.write("• Flow Capacity = maximum theoretical flow rate.\n")
            md.write("• Flow Utilization = percentage of capacity being used.\n")
        md.write("• `gte` = greater-than-or-equal-to (thresholds are inclusive).\n\n")
        render_segment_v2._definitions_added = True


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
    
    # PDF generation removed - focus on core functionality
    pdf_path = None
    print("📄 PDF generation removed - using markdown reports only")
    
    # Also save to storage service for persistence
    try:
        storage_service = get_storage_service()
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        storage_filename = f"{timestamp}-Density.md"
        storage_path = storage_service.save_file(storage_filename, report_content)
        print(f"📊 Density report saved to storage: {storage_path}")
    except Exception as e:
        print(f"⚠️ Failed to save density report to storage: {e}")
    
    # Generate and save map dataset using storage service
    map_data = generate_map_dataset(results, start_times)
    map_path = save_map_dataset_to_storage(map_data, output_dir)
    print(f"🗺️ Map dataset saved to: {map_path}")
    
    # DISABLED: Bin dataset generation causes Cloud Run timeouts
    # bin_data = generate_bin_dataset(results, start_times)
    # bin_path = save_bin_dataset(bin_data, output_dir)
    # print(f"📦 Bin dataset saved to: {bin_path}")
    print("📦 Bin dataset generation disabled to prevent Cloud Run timeouts")
    
    return {
        "ok": True,
        "report_path": full_path,
        "pdf_path": pdf_path if 'pdf_path' in locals() else None,
        "map_dataset_path": map_path,
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
    
    # Legends & Definitions (for quick reference)
    content.append("## Quick Reference")
    content.append("")
    content.append("**Units:**")
    content.append("- Areal density = persons per square meter (p/m²)")
    content.append("- Linear density = persons per meter of course width (p/m)")
    content.append("- Flow = persons per minute per meter (p/min/m)")
    content.append("")
    content.append("**Terminology:**")
    content.append("- **gte** = greater-than-or-equal-to; thresholds are applied inclusively")
    content.append("- **LOS** = Level of Service (A=Free Flow, B=Comfortable, C=Moderate, D=Dense, E=Very Dense, F=Extremely Dense)")
    content.append("")
    content.append("**Color Coding:** 🟢 Green (A-B), 🟡 Yellow (C-D), 🔴 Red (E-F)")
    content.append("")
    
    # Executive Summary Table (TL;DR for race directors)
    summary_table = generate_summary_table(results.get("segments", {}))
    content.extend(summary_table)
    
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
    
    # Note: Detailed definitions and LOS tables moved to Appendix
    
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
    
    # Appendix with detailed methodology and definitions
    content.append("## Appendix")
    content.append("")
    content.append("### Detailed Definitions")
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
    
    content.append("### Level of Service Thresholds")
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
    
    return "\n".join(content)


def generate_segment_section(
    segment_id: str,
    segment_data: Dict[str, Any], 
    event_order: List[Tuple[str, float]], 
    include_per_event: bool
) -> List[str]:
    """Generate markdown content for a single segment using v2 rulebook."""
    content = []
    
    # Try to load v2 rulebook and use new rendering
    try:
        import yaml
        with open("data/density_rulebook.yml", "r") as f:
            rulebook = yaml.safe_load(f)
        
        # Check if this is v2 rulebook
        version = rulebook.get("meta", {}).get("version", "1.0")
        version_str = str(version)
        if version_str.startswith("2"):
            # Use v2 rendering
            from io import StringIO
            md_buffer = StringIO()
            
            # Try to use complete v2_context first
            v2_context = segment_data.get("v2_context")
            if v2_context:
                try:
                    render_segment_v2(md_buffer, v2_context, rulebook)
                    v2_content = md_buffer.getvalue()
                    
                    if v2_content.strip():
                        content.extend(v2_content.strip().split('\n'))
                        return content
                except Exception as e:
                    print(f"Warning: v2_context rendering failed for segment {segment_id}: {e}")
                    # Fall back to summary-based context
                    pass
            
            # Fallback to summary-based context
            summary = segment_data.get("summary", {})
            ctx = {
                "segment_id": segment_id,
                "seg_label": segment_data.get("seg_label", "Unknown"),
                "peak_areal_density": summary.get("peak_areal_density", 0.0),
                "peak_crowd_density": summary.get("peak_crowd_density", 0.0),
                "schema_name": summary.get("schema_name", "on_course_open"),
                "flow_rate": summary.get("flow_rate"),
                "fired_actions": summary.get("fired_actions", [])
            }
            
            try:
                render_segment_v2(md_buffer, ctx, rulebook)
                v2_content = md_buffer.getvalue()
                
                if v2_content.strip():
                    content.extend(v2_content.strip().split('\n'))
                    return content
            except Exception as e:
                # Fall back to v1 rendering if v2 fails
                print(f"Warning: v2 rendering failed for segment {segment_id}: {e}")
                pass
    except Exception as e:
        # Fall back to v1 rendering if v2 fails
        pass
    
    # Fallback to v1 rendering
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


def generate_map_dataset(results: Dict[str, Any], start_times: Dict[str, float]) -> Dict[str, Any]:
    """
    Generate map dataset from density analysis results.
    
    Args:
        results: Density analysis results
        start_times: Event start times in minutes
    
    Returns:
        Map dataset dictionary
    """
    segments = results.get("segments", {})
    
    # Generate map-friendly data structure
    map_data = {
        "ok": True,
        "source": "density_analysis",
        "timestamp": datetime.now().isoformat(),
        "segments": {},
        "metadata": {
            "total_segments": len(segments),
            "analysis_type": "density",
            "start_times": start_times
        }
    }
    
    # Process density data for segments
    for segment_id, segment_data in segments.items():
        if isinstance(segment_data, dict):
            # Extract data from the segment summary
            summary = segment_data.get('summary', {})
            peak_areal_density = summary.get('peak_areal_density', 0.0)
            peak_crowd_density = summary.get('peak_crowd_density', 0.0)
            
            map_data["segments"][segment_id] = {
                "segment_id": segment_id,
                "segment_label": segment_data.get('seg_label', segment_id),
                "peak_areal_density": peak_areal_density,
                "peak_crowd_density": peak_crowd_density,
                "zone": _determine_zone(peak_areal_density),
                "flow_type": segment_data.get('flow_type', 'none'),
                "width_m": summary.get('width_m', 3.0)
            }
    
    return map_data


def _determine_zone(density: float) -> str:
    """Determine zone color based on density value."""
    if density < 0.36:
        return "green"
    elif density < 0.54:
        return "yellow"
    elif density < 0.72:
        return "orange"
    elif density < 1.08:
        return "red"
    else:
        return "dark-red"


def save_map_dataset(map_data: Dict[str, Any], output_dir: str) -> str:
    """
    Save map dataset to JSON file (legacy local-only function).
    
    Args:
        map_data: Map dataset dictionary
        output_dir: Output directory
    
    Returns:
        Path to saved file
    """
    # Create reports directory with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    reports_dir = os.path.join(output_dir, date_str)
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"map_data_{timestamp}.json"
    file_path = os.path.join(reports_dir, filename)
    
    # Save JSON file
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(map_data, f, indent=2, default=str)
    
    return file_path

def save_map_dataset_to_storage(map_data: Dict[str, Any], output_dir: str) -> str:
    """
    Save map dataset to storage service (local or Cloud Storage).
    
    Args:
        map_data: Map dataset dictionary
        output_dir: Output directory (used for fallback)
    
    Returns:
        Path to saved file
    """
    try:
        # Use storage service for persistent storage
        storage_service = get_storage_service()
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        filename = f"map_data_{timestamp}.json"
        
        # Save to storage service (local or Cloud Storage)
        path = storage_service.save_json(filename, map_data)
        
        return path
        
    except Exception as e:
        # Fallback to local file system if storage service fails
        print(f"⚠️ Storage service failed, falling back to local: {e}")
        return save_map_dataset(map_data, output_dir)

def generate_bin_dataset(results: Dict[str, Any], start_times: Dict[str, float]) -> Dict[str, Any]:
    """
    Generate bin-level dataset for map visualization.
    
    This function creates bin-level data that can be consumed by the map frontend
    for bin-level visualization, similar to how generate_map_dataset works for segments.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from .bin_analysis import get_all_segment_bins
        from .geo_utils import generate_bins_geojson
        
        # Use the same data paths as the density analysis
        pace_csv = "data/runners.csv"
        segments_csv = "data/segments.csv"
        
        # Generate bin data using the same parameters
        logger.info("Generating bin data from density analysis results")
        all_bins = get_all_segment_bins(
            pace_csv=pace_csv,
            segments_csv=segments_csv,
            start_times=start_times
        )
        
        # Generate GeoJSON for bins
        geojson = generate_bins_geojson(all_bins)
        
        return {
            "ok": True,
            "source": "density_analysis",
            "timestamp": datetime.now().isoformat(),
            "geojson": geojson,
            "metadata": {
                "total_segments": len(all_bins),
                "analysis_type": "bins",
                "bin_size_km": 0.1,
                "generated_by": "density_report"
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating bin dataset: {e}")
        return {
            "ok": False,
            "error": str(e),
            "geojson": {"type": "FeatureCollection", "features": []},
            "metadata": {"total_segments": 0, "analysis_type": "bins"}
        }

def save_bin_dataset(bin_data: Dict[str, Any], output_dir: str) -> str:
    """
    Save bin dataset to JSON file in the reports directory.
    
    Args:
        bin_data: The bin dataset to save
        output_dir: Base output directory for reports
        
    Returns:
        str: Path to the saved file
    """
    # Create reports directory with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    reports_dir = os.path.join(output_dir, date_str)
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"bin_data_{timestamp}.json"
    file_path = os.path.join(reports_dir, filename)
    
    # Save JSON file
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(bin_data, f, indent=2, default=str)
    
    return file_path
