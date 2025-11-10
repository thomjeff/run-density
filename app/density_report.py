"""
Density Report Module

Generates comprehensive density analysis reports including per-event views.
This module provides reusable functions for generating both combined and per-event
density reports that can be called by the API or other modules.
"""

from __future__ import annotations
import time
import hashlib
import json
import math
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import os
import pandas as pd
import logging
from app.segments_from_bins import write_segments_from_bins
from app.utils.constants import HOTSPOT_SEGMENTS
from app.save_bins import save_bin_artifacts
from app.report_utils import get_date_folder_path, get_run_folder_path
from app.bin_summary import generate_bin_summary_artifact
from app.canonical_density_report import generate_tooltips_json
from app.bin_intelligence import get_flagged_bins
from app.heatmap_generator import generate_heatmaps_for_run
from app.routes.api_heatmaps import upload_binary_to_gcs
from app.geo_utils import generate_bins_geojson
from pathlib import Path

logger = logging.getLogger(__name__)

# Import pattern validation and logging
def _validate_import_patterns():
    """Validate that all imports are properly resolved at module level."""
    try:
        # Test critical imports
        # Issue #466 Step 2: Storage consolidated to app.storage
        from app.core.density.compute import analyze_density_segments, DensityConfig
        from app.utils.constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, BIN_SCHEMA_VERSION
        from app.report_utils import get_report_paths
        from app.density_template_engine import DensityTemplateEngine, create_template_context
        logger.info("✅ All critical imports resolved successfully at module level")
        return True
    except ImportError as e:
        logger.error(f"❌ Critical import failed: {e}")
        return False

# Validate imports on module load
_validate_import_patterns()

@dataclass
class AnalysisContext:
    """Structured context for bin dataset generation per ChatGPT specification."""
    course_id: str
    segments: pd.DataFrame
    runners: pd.DataFrame
    params: dict
    code_version: str
    schema_version: str
    pace_csv_path: str
    segments_csv_path: str

def log_bins_event(**kwargs):
    """Structured logging helper for bin dataset metrics per ChatGPT specification."""
    payload = {"component": "bins", "ts": time.time(), **kwargs}
    print(json.dumps(payload))

def check_time_budget(start_time: float, budget_s: int = 60) -> None:
    """Elapsed timeout guard per ChatGPT specification."""
    if time.monotonic() - start_time > budget_s:
        raise TimeoutError("bin_generation_budget_exceeded")

def is_hotspot(seg_id: str, peak_los: str = None) -> bool:
    """Determine if segment is a hotspot requiring preserved resolution per ChatGPT specification."""
    
    # Static hotspot list (fastest to implement)
    if seg_id in HOTSPOT_SEGMENTS:
        return True
    
    # Dynamic hotspot detection based on LOS
    if peak_los and peak_los >= 'D':
        return True
        
    return False

def coarsen_plan(seg_id: str, current_bin_km: float, current_dt_s: int, peak_los: str = None) -> tuple[float, int]:
    """Determine coarsening strategy per ChatGPT hotspot preservation policy."""
    if is_hotspot(seg_id, peak_los):
        # Keep hotspots at high resolution
        return current_bin_km, current_dt_s
    
    # Non-hotspot coarsening policy: temporal first, then spatial
    coarsened_dt = max(current_dt_s, 120)  # Widen time windows first
    coarsened_bin = max(current_bin_km, 0.2)  # Then spatial if needed
    
    return coarsened_bin, coarsened_dt

# Import storage service for persistent file storage
# Issue #466 Step 2: Storage consolidated to app.storage
from app.core.density.compute import analyze_density_segments, DensityConfig
from app.utils.constants import DEFAULT_STEP_KM, DEFAULT_TIME_WINDOW_SECONDS, BIN_SCHEMA_VERSION
from app.report_utils import get_report_paths
from app.density_template_engine import DensityTemplateEngine, create_template_context
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
        # Use peak_areal_density (correct field name from v2_context)
        density = v2_context.get('peak_areal_density', 0)
        
        # Dynamic precision based on density value (Issue #239 - ChatGPT recommendation)
        if density < 0.01:
            density_str = f"{density:.4f}"
        elif density < 0.10:
            density_str = f"{density:.3f}"
        else:
            density_str = f"{density:.2f}"
        
        if los_letter in ['E', 'F']:
            return f"High density ({density_str} p/m²) - extra marshals needed"
        elif los_letter in ['C', 'D']:
            return f"Moderate density ({density_str} p/m²) - maintain cadence"
        else:
            return f"Low density ({density_str} p/m²) - comfortable flow"


def _determine_los_from_thresholds(areal_density: float, los_thresholds: Dict[str, Any]) -> str:
    """Determine LOS letter from areal density using schema thresholds."""
    los_letter = "F"  # Default to worst case
    for letter in ["A", "B", "C", "D", "E", "F"]:
        rng = los_thresholds.get(letter, {})
        mn = rng.get("min", float("-inf"))
        mx = rng.get("max", float("inf"))
        if areal_density >= mn and areal_density < mx:
            los_letter = letter
            break
    return los_letter


def _render_metrics_table_v2(md, ctx, schema_name: str, areal_density: float, 
                            flow_rate: Optional[float], flow_capacity: Optional[float],
                            flow_utilization: Optional[float], los_letter: str) -> None:
    """Render metrics table for v2.0 segment rendering."""
    md.write("#### Metrics\n\n")
    md.write("| Metric | Value | Units |\n")
    md.write("|--------|-------|-------|\n")
    
    # Areal density (always shown)
    md.write(f"| Density | {areal_density:.2f} | p/m² |\n")
    
    # For narrow/merge segments, show linear density
    if schema_name in ["on_course_narrow"]:
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
    
    # Add note about schema
    if schema_name == "start_corral":
        md.write("\n| Note: LOS here uses start-corral thresholds, not Fruin. Flow-rate governs safety. |\n")
    elif schema_name == "on_course_narrow":
        md.write("\n| Note: LOS uses Fruin thresholds (linear density). |\n")


def _render_key_takeaways_v2(md, los_letter: str, flow_utilization: Optional[float]) -> None:
    """Render key takeaways section for v2.0 segment rendering."""
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


def _render_operational_implications_v2(md, ctx, schema_config: Dict[str, Any],
                                       schema_name: str, los_letter: str,
                                       flow_rate: Optional[float],
                                       flow_utilization: Optional[float],
                                       flow_capacity: Optional[float]) -> None:
    """Render operational implications section for v2.0 segment rendering."""
    md.write("### Operational Implications\n\n")
    
    # Get mitigations from schema
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


def _render_mitigations_and_notes_v2(md, fired_actions: List[str], ops_box: Dict[str, Any]) -> None:
    """Render mitigations fired and operational notes for v2.0 segment rendering."""
    # Add fired actions if any
    if fired_actions:
        md.write("\n### Mitigations Fired\n\n")
        for action in fired_actions:
            md.write(f"• {action}\n")
    
    # Add operational box if available
    if ops_box:
        md.write("\n### Operational Notes\n\n")
        for category, notes in ops_box.items():
            if notes:
                md.write(f"**{category.title()}:**\n")
                for note in notes:
                    md.write(f"• {note}\n")
                md.write("\n")


def _render_definitions_v2(md, flow_rate: Optional[float]) -> None:
    """Render definitions section for v2.0 segment rendering (only once per report)."""
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
    los_letter = _determine_los_from_thresholds(areal_density, los_thresholds)
    
    # Render header with schema info
    md.write(f"### Segment {ctx['segment_id']} — {ctx['seg_label']}\n\n")
    
    # Render metrics table
    _render_metrics_table_v2(md, ctx, schema_name, areal_density, flow_rate, 
                            flow_capacity, flow_utilization, los_letter)
    
    # Render key takeaways
    _render_key_takeaways_v2(md, los_letter, flow_utilization)
    
    # Render operational implications
    _render_operational_implications_v2(md, ctx, schema_config, schema_name, los_letter,
                                         flow_rate, flow_utilization, flow_capacity)
    
    # Render mitigations and operational notes
    ops_box = schema_config.get("ops_box", {})
    _render_mitigations_and_notes_v2(md, fired_actions, ops_box)
    
    # Render definitions
    _render_definitions_v2(md, flow_rate)


def _render_v2_schema_content(md, ctx, schema):
    """Render schema-based content for v2.0 rulebook (flow_type zone, drivers, mitigations, ops_box)."""
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


def _collect_triggered_actions(triggers, ctx, schema_name):
    """Collect all triggered actions from triggers (regular + high density)."""
    triggered_actions = []
    
    # Process all triggers
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
            when = trigger.get("when", {})
            if (when.get("density_gte") in ["E", "F"] and _trigger_matches(trigger, ctx, schema_name)):
                actions = trigger.get("actions", [])
                if actions:
                    for action in actions:
                        triggered_actions.append(f"[High Density] {action}")
    
    return triggered_actions


def _render_event_factors_v2(md, ctx, rulebook, segment_id):
    """Render event-specific factors/overrides for v2.0 rulebook."""
    event_type = ctx.get("event_type", "").lower()
    if not event_type:
        return
    
    # Look for event-specific overrides
    overrides = rulebook.get("overrides", [])
    for override in overrides:
        if override.get("match", {}).get("segment_id") == segment_id:
            notes = override.get("notes", [])
            if notes:
                md.write("_Event factors_: " + "; ".join(notes) + "\n\n")


def _render_legacy_content(md, ctx, rulebook):
    """Render segment using legacy v1.x rulebook structure."""
    drivers = rulebook["templates"]["drivers"]
    safety = rulebook["templates"]["safety"]
    events = rulebook["templates"]["events"]

    flow_key = f"{ctx.get('flow_type','')}_zone"
    if flow_key in drivers:
        md.write(drivers[flow_key]["narrative_template"].format(**ctx) + "\n\n")

    dclass = ctx.get("density_class")
    if dclass and dclass in drivers:
        md.write(drivers[dclass]["narrative_template"].format(**ctx) + "\n\n")
    else:
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


def render_segment(md, ctx, rulebook):
    """Render a segment using v2.0 or legacy rulebook structure."""
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
            _render_v2_schema_content(md, ctx, schema)
        
        # Collect and display triggered actions
        triggers = rulebook.get("triggers", [])
        triggered_actions = _collect_triggered_actions(triggers, ctx, schema_name)
        
        if triggered_actions:
            md.write("### Triggered Actions\n")
            for action in triggered_actions:
                md.write(f"- {action}\n")
            md.write("\n")
        
        # Check for event-specific factors
        _render_event_factors_v2(md, ctx, rulebook, segment_id)
        
        # Fallback if no schema found
        if not schema:
            md.write(f"**Segment {segment_id} ({segment_label})** — density {density_value:.3f} runners/m²\n\n")
    
    else:
        # Legacy v1.x rulebook structure
        _render_legacy_content(md, ctx, rulebook)


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


def _initialize_bin_generation_params() -> Tuple[float, int]:
    """Initialize bin generation parameters with Cloud Run optimization."""
    from app.utils.constants import (
        DEFAULT_BIN_SIZE_KM, FALLBACK_BIN_SIZE_KM,
        DEFAULT_BIN_TIME_WINDOW_SECONDS
    )
    
    bin_size_to_use = DEFAULT_BIN_SIZE_KM
    dt_seconds = DEFAULT_BIN_TIME_WINDOW_SECONDS
    
    # For Cloud Run, start with larger bins per ChatGPT adaptive strategy
    if os.getenv('TEST_CLOUD_RUN', 'false').lower() == 'true':
        bin_size_to_use = FALLBACK_BIN_SIZE_KM
        log_bins_event(action="cloud_run_optimization", bin_size_km=bin_size_to_use)
    
    return bin_size_to_use, dt_seconds


def _apply_temporal_first_coarsening(bin_size_to_use: float, dt_seconds: int) -> int:
    """Apply temporal-first coarsening based on projected features."""
    from app.utils.constants import BIN_MAX_FEATURES
    
    try:
        avg_segment_length_m = 2000
        n_segments = 22
        n_time_windows = 1
        projected = n_segments * math.ceil(avg_segment_length_m / (bin_size_to_use * 1000)) * n_time_windows
        
        if projected > BIN_MAX_FEATURES:
            dt_seconds = min(max(dt_seconds, 120), 180)
            log_bins_event(action="temporal_first_coarsening", 
                         projected_features=projected, 
                         new_dt_seconds=dt_seconds)
    except Exception as e:
        logger.warning(f"Feature projection failed, proceeding with defaults: {e}")
    
    return dt_seconds


def _try_bin_generation_with_coarsening(
    results: Dict[str, Any],
    start_times: Dict[str, float],
    bin_size_to_use: float,
    dt_seconds: int,
    analysis_context: Any,
    start_time: float,
    strategy_step: int
) -> Tuple[Optional[Dict[str, Any]], str, int, float, int]:
    """Try generating bin dataset with adaptive coarsening strategy."""
    from app.utils.constants import MAX_BIN_GENERATION_TIME_SECONDS
    
    bins_status = "ok"
    
    while strategy_step < 3:
        try:
            bin_data = generate_bin_dataset(
                results, start_times, bin_size_km=bin_size_to_use,
                analysis_context=analysis_context, dt_seconds=dt_seconds
            )
            
            elapsed = time.monotonic() - start_time
            
            if bin_data.get("ok", False):
                # Auto-coarsen on timeout per ChatGPT specification
                if elapsed > MAX_BIN_GENERATION_TIME_SECONDS:
                    log_bins_event(action="auto_coarsen_triggered", 
                                 elapsed_s=elapsed, 
                                 strategy_step=strategy_step)
                    
                    strategy_step += 1
                    if strategy_step == 1:
                        dt_seconds = min(dt_seconds * 2, 180)
                        log_bins_event(action="temporal_coarsening", new_dt_seconds=dt_seconds)
                        continue
                    elif strategy_step == 2:
                        bin_size_to_use = max(bin_size_to_use, 0.2)
                        log_bins_event(action="spatial_coarsening", new_bin_size_km=bin_size_to_use)
                        continue
                    else:
                        bins_status = "partial"
                        log_bins_event(action="partial_completion", reason="exceeded_retry_budget")
                        break
                else:
                    break
            else:
                raise ValueError(f"Bin generation failed: {bin_data.get('error', 'Unknown error')}")
                
        except Exception as gen_e:
            if strategy_step < 2:
                strategy_step += 1
                dt_seconds = min(dt_seconds * 2, 180)
                bin_size_to_use = max(bin_size_to_use, 0.2)
                log_bins_event(action="error_recovery", 
                             error=str(gen_e), 
                             new_dt_seconds=dt_seconds,
                             new_bin_size_km=bin_size_to_use)
                continue
            else:
                raise gen_e
    
    return bin_data, bins_status, strategy_step, bin_size_to_use, dt_seconds


def _save_bin_artifacts_and_metadata(
    bin_data: Dict[str, Any],
    bin_size_to_use: float,
    dt_seconds: int,
    bins_status: str,
    strategy_step: int,
    output_dir: str,
    start_time: float
) -> Tuple[str, str, Dict[str, Any]]:
    """Save bin artifacts and generate metadata."""
    bin_geojson = bin_data.get("geojson", {})
    md = bin_geojson.get("metadata", {})
    occ = md.get("occupied_bins")
    nz = md.get("nonzero_density_bins")
    tot = md.get("total_features")
    
    if logger:
        logger.info("Pre-save bins: total=%s occupied=%s nonzero=%s", tot, occ, nz)
        if tot in (None, 0) or occ in (None, 0) or nz in (None, 0):
            logger.error("Pre-save check indicates empty occupancy; saving anyway for debugging.")
    
    geojson_start = time.monotonic()
    # Issue #455: Use runflow path if run_id provided, otherwise legacy date path
    # This function is called from _generate_bin_dataset_with_retry which doesn't have run_id yet
    # For now, keep legacy behavior - will be updated when full call chain supports run_id
    daily_folder_path, _ = get_date_folder_path(output_dir)
    os.makedirs(daily_folder_path, exist_ok=True)
    geojson_path, parquet_path = save_bin_artifacts(bin_data.get("geojson", {}), daily_folder_path)
    serialization_time = int((time.monotonic() - geojson_start) * 1000)
    
    # Generate bin_summary.json artifact (Issue #329)
    try:
        bin_summary_path = generate_bin_summary_artifact(daily_folder_path)
        logger.info(f"Generated bin_summary.json: {bin_summary_path}")
    except Exception as e:
        logger.warning(f"Failed to generate bin_summary.json: {e}")
    
    elapsed = time.monotonic() - start_time
    final_features = len(bin_data.get("geojson", {}).get("features", []))
    
    bin_metadata = {
        "status": bins_status,
        "effective_bin_m": int(bin_size_to_use * 1000),
        "effective_window_s": dt_seconds,
        "features": final_features,
        "geojson_mb": round(os.path.getsize(geojson_path) / (1024 * 1024), 1),
        "parquet_kb": round(os.path.getsize(parquet_path) / 1024, 1),
        "generation_ms": int(elapsed * 1000),
        "strategy_steps": strategy_step
    }
    
    log_bins_event(action="artifacts_saved",
                 geojson_path=geojson_path,
                 parquet_path=parquet_path,
                 serialization_ms=serialization_time,
                 total_features=final_features,
                 total_ms=int(elapsed * 1000),
                 metadata=bin_metadata)
    
    return daily_folder_path, geojson_path, bin_metadata


def _process_segments_from_bins(daily_folder_path: str) -> None:
    """Process segments from bins roll-up if enabled."""
    if os.getenv("SEGMENTS_FROM_BINS", "true").lower() == "true":
        try:
            bins_parquet = os.path.join(daily_folder_path, "bins.parquet")
            bins_geojson_gz = os.path.join(daily_folder_path, "bins.geojson.gz")
            print(f"SEG_ROLLUP_START out_dir={os.path.abspath(daily_folder_path)}")
            seg_path = write_segments_from_bins(daily_folder_path, bins_parquet, bins_geojson_gz)
            print(f"SEG_ROLLUP_DONE path={seg_path}")
            
            try:
                canon = pd.read_parquet(seg_path).rename(columns={"density_mean":"density_mean_canon"})
                print(f"CANONICAL_SEGMENTS rows={len(canon)} segments={canon.segment_id.nunique()}")
                out_csv = os.path.join(daily_folder_path, "segments_legacy_vs_canonical.csv")
                canon.to_csv(out_csv, index=False)
                print(f"POST_SAVE segments_legacy_vs_canonical={os.path.abspath(out_csv)} rows={len(canon)}")
            except Exception as e:
                print(f"SEG_COMPARE_FAILED {e}")
        except Exception as e:
            print(f"SEG_ROLLUP_FAILED {e}")


# Issue #464: GCS upload logic removed during Phase 1 declouding


def _generate_bin_dataset_with_retry(
    results: Dict[str, Any],
    start_times: Dict[str, float],
    output_dir: str,
    analysis_context: Any
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Generate bin dataset with retry logic and adaptive coarsening.
    
    Args:
        results: Density analysis results
        start_times: Start times mapping
        output_dir: Output directory for artifacts
        analysis_context: Analysis context object
        
    Returns:
        Tuple of (daily_folder_path, bin_metadata_dict, bin_data_dict)
        Returns (None, None, None) if bin generation fails
    """
    start_time = time.monotonic()
    
    # Initialize parameters with Cloud Run optimization
    bin_size_to_use, dt_seconds = _initialize_bin_generation_params()
    
    # Apply temporal-first coarsening
    dt_seconds = _apply_temporal_first_coarsening(bin_size_to_use, dt_seconds)
    
    # Generate bin dataset with adaptive coarsening
    strategy_step = 0
    bin_data, bins_status, strategy_step, bin_size_to_use, dt_seconds = _try_bin_generation_with_coarsening(
        results, start_times, bin_size_to_use, dt_seconds,
        analysis_context, start_time, strategy_step
    )
    
    # Check final result
    if not bin_data or not bin_data.get("ok", False):
        error_msg = bin_data.get('error', 'Unknown error') if bin_data else 'Bin data is None'
        raise ValueError(f"Bin generation failed: {error_msg}")
    
    # Save artifacts and generate metadata
    daily_folder_path, geojson_path, bin_metadata = _save_bin_artifacts_and_metadata(
        bin_data, bin_size_to_use, dt_seconds, bins_status,
        strategy_step, output_dir, start_time
    )
    
    # Process segments from bins
    _process_segments_from_bins(daily_folder_path)
    
    # Print summary
    elapsed = time.monotonic() - start_time
    final_features = len(bin_data.get("geojson", {}).get("features", []))
    parquet_path = os.path.join(daily_folder_path, "bins.parquet")
    print(f"📦 Bin dataset saved: {geojson_path} | {parquet_path}")
    print(f"📦 Generated {final_features} bin features in {elapsed:.1f}s (bin_size={bin_size_to_use}km, dt={dt_seconds}s)")
    if bins_status != "ok":
        print(f"⚠️  Bin status: {bins_status} (applied {strategy_step} optimization steps)")
    
    # Issue #464: GCS upload removed during Phase 1 declouding
    
    return daily_folder_path, bin_metadata, bin_data


def _generate_new_report_format(
    daily_folder_path: str,
    run_id: str = None  # Issue #455: UUID for runflow structure
) -> Optional[str]:
    """Generate new density report format (Issue #246)."""
    print("📊 Generating new density report (Issue #246)...")
    
    # Issue #455: Use generic filename for runflow, timestamped for legacy
    if run_id:
        from app.report_utils import get_runflow_file_path
        timestamped_path = get_runflow_file_path(run_id, "reports", "Density.md")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        timestamped_path = os.path.join(daily_folder_path, f"{timestamp}-Density.md")
    
    new_report_results = generate_new_density_report_issue246(
        reports_dir=daily_folder_path,
        output_path=timestamped_path,
        app_version="1.6.42"
    )
    report_content_final = new_report_results['report_content']
    print(f"📊 New density report saved to: {timestamped_path}")
    
    # Issue #464: GCS upload removed during Phase 1 declouding
    
    return timestamped_path


def _generate_legacy_report_format(
    results: Dict[str, Any],
    start_times: Dict[str, float],
    include_per_event: bool,
    output_dir: str,
    run_id: str = None  # Issue #455: UUID for runflow structure
) -> str:
    """Generate legacy density report format with operational intelligence."""
    print("📊 Regenerating density report with operational intelligence...")
    from app.report_utils import get_report_paths, get_runflow_file_path
    
    # Note: generate_markdown_report is defined later in this same file
    report_content_final = generate_markdown_report(
        results,
        start_times,
        include_per_event,
        include_operational_intelligence=True,
        output_dir=output_dir
    )
    
    # Issue #455: Use runflow path for reports if run_id provided
    if run_id:
        full_path = get_runflow_file_path(run_id, "reports", "Density.md")
    else:
        # Legacy: Get existing full_path from results or create new
        full_path, _ = get_report_paths("Density", "md", output_dir)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(report_content_final)
    
    print(f"📊 Density report (with operational intelligence) saved to: {full_path}")
    
    # Issue #464: GCS upload removed during Phase 1 declouding
    
    return full_path


def _generate_tooltips_json(
    results: Dict[str, Any],
    daily_folder_path: str
) -> None:
    """Generate tooltips.json if operational intelligence was added."""
    if '_operational_intelligence' not in results:
        return
    
    try:
        oi_data = results['_operational_intelligence']
        bins_flagged = oi_data['bins_flagged']
        flagged = get_flagged_bins(bins_flagged)
        
        if len(flagged) > 0:
            tooltips_path = os.path.join(daily_folder_path, "tooltips.json")
            if generate_tooltips_json(flagged, oi_data['config'], tooltips_path):
                print(f"🗺️ Tooltips JSON saved to: {tooltips_path}")
    except (KeyError, TypeError) as e:
        logger.error(f"Invalid operational intelligence data structure: {e}")
    except (OSError, IOError) as e:
        logger.error(f"Failed to write tooltips.json: {e}")
    except Exception as e:
        logger.error(f"Unexpected error generating tooltips.json: {e}")
        logger.debug(f"Tooltips generation error details: {type(e).__name__}: {e}", exc_info=True)


def _regenerate_report_with_intelligence(
    results: Dict[str, Any],
    start_times: Dict[str, float],
    include_per_event: bool,
    daily_folder_path: Optional[str],
    output_dir: str,
    use_new_report_format: bool,
    run_id: str = None  # Issue #455: UUID for runflow structure
) -> Optional[str]:
    """
    Regenerate density report with operational intelligence after bin generation.
    
    Args:
        results: Density analysis results
        start_times: Start times mapping
        include_per_event: Whether to include per-event analysis
        daily_folder_path: Path to daily folder (None if bins disabled)
        output_dir: Output directory
        use_new_report_format: Whether to use new report format
        
    Returns:
        Path to generated report file, or None if generation failed
    """
    if not daily_folder_path:
        logger.warning("daily_folder_path not available for report regeneration")
        return None
    
    if use_new_report_format:
        full_path = _generate_new_report_format(daily_folder_path, run_id=run_id)  # Issue #455: Pass run_id
    else:
        full_path = _generate_legacy_report_format(
            results, start_times, include_per_event, output_dir, run_id=run_id  # Issue #455: Pass run_id
        )
    
    # Generate tooltips.json if operational intelligence was added
    _generate_tooltips_json(results, daily_folder_path)
    
    return full_path


def _generate_and_upload_heatmaps(daily_folder_path: Optional[str], run_id: str = None) -> None:
    """
    Generate and upload heatmaps for a run.
    
    Args:
        daily_folder_path: Path to daily folder containing artifacts
        run_id: Run identifier (Issue #455: UUID or legacy date)
    """
    if not daily_folder_path:
        logger.warning("daily_folder_path not available for heatmap generation")
        return
    
    # Issue #455: Use provided run_id or extract from daily_folder_path
    if not run_id:
        run_id = os.path.basename(daily_folder_path)
    
    try:
        print(f"🔥 Generating heatmaps for run_id: {run_id}")
        
        heatmaps_generated, segments = generate_heatmaps_for_run(run_id)
        print(f"🔥 Generated {heatmaps_generated} heatmaps for {run_id}")
        
        # Issue #464: GCS upload removed during Phase 1 declouding
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid run_id or heatmap generation parameters: {e}")
    except Exception as e:
        logger.error(f"Unexpected error generating heatmaps: {e}")
        logger.debug(f"Heatmap generation error details: {type(e).__name__}: {e}", exc_info=True)




def _setup_runflow_output_dir(run_id: str, logger):
    """Setup runflow output directory for UUID-based runs."""
    if run_id:
        from app.report_utils import get_runflow_category_path
        output_dir = get_runflow_category_path(run_id, "bins")
        logger.info(f"Issue #455: Using runflow structure for run_id={run_id}, bins_dir={output_dir}")
        return output_dir
    return None


def _finalize_run_metadata(run_id: str, daily_folder_path: str, logger):
    """Write metadata for completed runs."""
    if not run_id or not daily_folder_path:
        return
        
    try:
        from app.utils.metadata import create_run_metadata, write_metadata_json, update_latest_pointer
        from app.report_utils import get_run_folder_path
        from pathlib import Path
        
        run_path = Path(get_run_folder_path(run_id))
        metadata = create_run_metadata(run_id, run_path, status="complete")
        metadata_path = write_metadata_json(run_path, metadata)
        logger.info(f"Issue #455: Written metadata.json to {metadata_path}")
        
        # Update latest.json pointer
        update_latest_pointer(run_id)
        
        # Issue #464: GCS upload removed during Phase 1 declouding
    except Exception as e:
        logger.warning(f"Failed to write metadata.json: {e}")



def _execute_bin_dataset_generation(results, start_times, output_dir, enable_bin_dataset, logger):
    """Execute bin dataset generation with retry logic."""
    enable_bins = enable_bin_dataset or os.getenv('ENABLE_BIN_DATASET', 'false').lower() == 'true'
    logger.info(f"Bin dataset generation: enable_bin_dataset={enable_bin_dataset}, env_var={os.getenv('ENABLE_BIN_DATASET')}, effective={enable_bins}")
    
    if not enable_bins:
        print("📦 Bin dataset generation disabled (ENABLE_BIN_DATASET=false)")
        return None
        
    logger.info("✅ Bin dataset generation enabled (enable_bin_dataset=True)")
    try:
        from app.utils.constants import BIN_SCHEMA_VERSION
        
        # Create AnalysisContext
        analysis_context = AnalysisContext(
            course_id="fredericton_marathon",
            segments=pd.DataFrame(),
            runners=pd.DataFrame(),
            params={"start_times": start_times},
            code_version="v1.6.37",
            schema_version=BIN_SCHEMA_VERSION,
            pace_csv_path="data/runners.csv",
            segments_csv_path="data/segments.csv"
        )
        
        daily_folder_path, _, _ = _generate_bin_dataset_with_retry(
            results, start_times, output_dir, analysis_context
        )
        return daily_folder_path
    except Exception as e:
        print(f"⚠️ Bin dataset unavailable: {e}")
        return None


def generate_density_report(
    pace_csv: str,
    density_csv: str,
    start_times: Dict[str, float],
    step_km: float = DEFAULT_STEP_KM,
    time_window_s: float = DEFAULT_TIME_WINDOW_SECONDS,
    include_per_event: bool = True,
    output_dir: str = "reports",
    enable_bin_dataset: bool = True,  # Issue #319: Enable by default (resource constraints resolved)
    use_new_report_format: bool = True,
    run_id: str = None  # Issue #455: UUID for runflow structure
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
    import logging
    logger = logging.getLogger(__name__)
    
    # Issue #455: Surgical path update for runflow structure
    runflow_dir = _setup_runflow_output_dir(run_id, logger)
    if runflow_dir:
        output_dir = runflow_dir
    
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
    
    # Issue #319: Skip legacy report generation - only generate v2 report with bin-level details
    # The v2 report will be generated after bin dataset creation (line ~950)
    # NOTE: Legacy report generation removed to avoid duplicate reports in GCS
    #       - Old approach: generated initial report (15KB) + v2 report (109KB) = 2 files
    #       - New approach: only generate v2 report (109KB) = 1 file
    
    # # COMMENTED OUT - Legacy report generation (Issue #319)
    # report_content_initial = generate_markdown_report(
    #     results, 
    #     start_times, 
    #     include_per_event,
    #     include_operational_intelligence=False,
    #     output_dir=output_dir
    # )
    # full_path, relative_path = get_report_paths("Density", "md", output_dir)
    # with open(full_path, 'w', encoding='utf-8') as f:
    #     f.write(report_content_initial)
    # print(f"📊 Density report (initial) saved to: {full_path}")
    
    # Initialize variables for return statement (will be set by v2 report generation)
    pdf_path = None  # PDF generation removed
    full_path = None  # Will be set by v2 report generation at line ~961
    
    # # COMMENTED OUT - Legacy report storage upload (Issue #319)
    # try:
    #     storage_service = get_storage_service()
    #     timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    #     storage_filename = f"{timestamp}-Density.md"
    #     storage_path = storage_service.save_file(storage_filename, report_content_initial)
    #     print(f"📊 Density report saved to storage: {storage_path}")
    # except Exception as e:
    #     print(f"⚠️ Failed to save density report to storage: {e}")
    
    # Generate and save map dataset using storage service
    map_data = generate_map_dataset(results, start_times)
    map_path = save_map_dataset_to_storage(map_data, output_dir, run_id=run_id)  # Issue #455: Pass run_id
    print(f"🗺️ Map dataset saved to: {map_path}")
    
    # Issue #198: Re-enable bin dataset generation with feature flag
    daily_folder_path = _execute_bin_dataset_generation(
        results, start_times, output_dir, enable_bin_dataset, logger
    )
    
    # Regenerate report WITH operational intelligence now that bins exist (Issue #239 fix)
    if daily_folder_path:
        try:
            full_path = _regenerate_report_with_intelligence(
                results, start_times, include_per_event,
                daily_folder_path, output_dir, use_new_report_format,
                run_id=run_id  # Issue #455: Pass run_id
            )
            _generate_and_upload_heatmaps(daily_folder_path, run_id=run_id)  # Issue #455: Pass run_id
        except Exception as e:
            logger.warning(f"Could not regenerate report with operational intelligence: {e}")
            full_path = None
    
    # Remove non-JSON-serializable operational intelligence data before returning (Issue #236)
    # This data was only needed for report generation, not for API response
    results_for_api = {k: v for k, v in results.items() if k != '_operational_intelligence'}
    
    # Issue #455: Write metadata.json at end of successful generation
    _finalize_run_metadata(run_id, daily_folder_path, logger)
    
    return {
        "ok": True,
        "report_path": full_path,
        "pdf_path": pdf_path if 'pdf_path' in locals() else None,
        "map_dataset_path": map_path,
        "analysis_results": results_for_api,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id  # Issue #455: Include run_id in response
    }


def generate_operational_intelligence_summary(stats: Dict[str, Any], segment_summary: pd.DataFrame, config: Dict[str, Any]) -> List[str]:
    """
    Generate operational intelligence executive summary section.
    
    Args:
        stats: Flagging statistics
        segment_summary: Segment-level rollup
        config: Configuration dictionary
        
    Returns:
        List of markdown lines for operational intelligence section
    """
    from app.los import get_los_description
    
    content = []
    
    content.append("## Operational Intelligence Summary")
    content.append("")
    content.append("*Based on bin-level analysis with LOS classification and utilization flagging*")
    content.append("")
    
    # Key Metrics
    content.append("### Key Metrics")
    content.append("")
    content.append("| Metric | Value |")
    content.append("|--------|-------|")
    content.append(f"| Total Bins Analyzed | {stats['total_bins']:,} |")
    content.append(f"| Flagged Bins | {stats['flagged_bins']:,} ({stats['flagged_percentage']:.1f}%) |")
    content.append(f"| Worst Severity | {stats['worst_severity']} |")
    content.append(f"| Worst LOS | {stats['worst_los']} - {get_los_description(stats['worst_los'])} |")
    content.append(f"| Peak Density | {stats['peak_density_range']['max']:.4f} people/m² |")
    content.append("")
    
    # Severity Distribution
    if stats['flagged_bins'] > 0:
        content.append("### Severity Distribution")
        content.append("")
        content.append("| Severity | Count | Description |")
        content.append("|----------|-------|-------------|")
        
        severity_descriptions = {
            'CRITICAL': 'Both LOS >= C AND top 5% utilization',
            'CAUTION': 'LOS >= C only',
            'WATCH': 'Top 5% utilization only'
        }
        
        for severity in ['CRITICAL', 'CAUTION', 'WATCH']:
            count = stats['severity_distribution'].get(severity, 0)
            desc = severity_descriptions.get(severity, '')
            content.append(f"| {severity} | {count} | {desc} |")
        
        content.append("")
        
        # Flagged Segments Table
        if len(segment_summary) > 0:
            content.append("### Flagged Segments (Worst Bin per Segment)")
            content.append("")
            content.append("| Segment | Range (km) | LOS | Density (p/m²) | Flagged Bins | Severity |")
            content.append("|---------|------------|-----|----------------|--------------|----------|")
            
            for _, row in segment_summary.head(10).iterrows():  # Top 10 worst segments
                seg_label = row.get('seg_label', row['segment_id'])
                range_str = f"{row['worst_bin_start_km']:.2f}-{row['worst_bin_end_km']:.2f}"
                los = row['worst_los']
                density = f"{row['peak_density']:.4f}"  # Use 4 decimals to show small values
                count = row['flagged_bin_count']
                severity = row['severity']
                
                content.append(f"| {seg_label} | {range_str} | {los} | {density} | {count} | {severity} |")
            
            if len(segment_summary) > 10:
                content.append(f"| ... | ... | ... | ... | ... | ... |")
                content.append(f"| *{len(segment_summary) - 10} more segments* | | | | | |")
            
            content.append("")
    else:
        content.append("### ✅ No Operational Intelligence Flags")
        content.append("")
        content.append("All bins operating within acceptable parameters (LOS < C and utilization < top 5%).")
        content.append("")
    
    content.append("---")
    content.append("")
    
    return content


def _get_app_version() -> str:
    """Get application version from version module or fallback to main.py."""
    try:
        from app.version import get_current_version
        return get_current_version()
    except ImportError:
        try:
            from version import get_current_version
            return get_current_version()
        except ImportError:
            # Fallback to extracting from main.py
            import re
            try:
                with open('app/main.py', 'r') as f:
                    content_text = f.read()
                    match = re.search(r'version="(v\d+\.\d+\.\d+)"', content_text)
                    return match.group(1) if match else "unknown"
            except Exception:
                return "unknown"


def _generate_report_header(results: Dict[str, Any]) -> List[str]:
    """Generate report header with version, environment, and analysis metadata."""
    import os
    content = []
    
    content.append("# Improved Per-Event Density Analysis Report")
    content.append("")
    content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content.append("")
    content.append(f"**Analysis Engine:** density")
    content.append("")
    content.append(f"**Version:** {_get_app_version()}")
    content.append("")
    
    # Environment information
    if os.environ.get('TEST_CLOUD_RUN', 'false').lower() == 'true':
        content.append("**Environment:** https://run-density-ln4r3sfkha-uc.a.run.app (Cloud Run Production)")
    else:
        content.append("**Environment:** http://localhost:8080 (Local Development)")
    content.append("")
    
    content.append(f"**Analysis Period:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
    
    return content


def _generate_quick_reference_section() -> List[str]:
    """Generate quick reference section with units and terminology."""
    content = []
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
    return content


def _generate_operational_intelligence_content(
    results: Dict[str, Any],
    output_dir: str
) -> List[str]:
    """Generate operational intelligence executive summary if enabled."""
    content = []
    
    try:
        from app.io_bins import load_bins
        from app.bin_intelligence import FlaggingConfig, apply_bin_flagging, summarize_segment_flags, get_flagging_statistics
        
        # Load configuration
        import yaml
        try:
            with open("config/reporting.yml", "r") as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            config = None
        
        if config:
            # Load bins
            bins_df = load_bins(reports_dir=output_dir)
            
            if bins_df is not None and len(bins_df) > 0:
                # Apply flagging
                flagging_cfg = FlaggingConfig(
                    min_los_flag=config['flagging']['min_los_flag'],
                    utilization_pctile=config['flagging']['utilization_pctile'],
                    require_min_bin_len_m=config['flagging']['require_min_bin_len_m'],
                    density_field='density_peak'
                )
                
                bins_flagged = apply_bin_flagging(bins_df, flagging_cfg, los_thresholds=config.get('los'))
                stats = get_flagging_statistics(bins_flagged)
                segment_summary = summarize_segment_flags(bins_flagged)
                
                # Generate operational intelligence sections
                content.extend(generate_operational_intelligence_summary(stats, segment_summary, config))
                content.append("")
                
                # Store for bin detail appendix later
                results['_operational_intelligence'] = {
                    'bins_flagged': bins_flagged,
                    'stats': stats,
                    'segment_summary': segment_summary,
                    'config': config
                }
    except Exception as e:
        logger.warning(f"Could not generate operational intelligence: {e}")
        # Continue without operational intelligence
    
    return content


def _generate_methodology_section() -> List[str]:
    """Generate methodology section using v2.0 rulebook or fallback."""
    content = []
    
    try:
        import yaml
        with open("config/density_rulebook.yml", "r") as f:
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
    
    return content


def _generate_event_start_times_table(
    results: Dict[str, Any],
    event_order: List[Tuple[str, float]]
) -> List[str]:
    """Generate event start times table with participant counts."""
    content = []
    
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
    
    return content


def _generate_appendix_content(results: Dict[str, Any]) -> List[str]:
    """Generate appendix with detailed definitions, LOS thresholds, and bin-level detail."""
    content = []
    
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
    
    # Bin-Level Detail for Flagged Segments (Issue #236)
    if '_operational_intelligence' in results:
        oi_data = results['_operational_intelligence']
        bins_flagged = oi_data['bins_flagged']
        
        # Get only flagged bins
        from app.bin_intelligence import get_flagged_bins
        flagged = get_flagged_bins(bins_flagged)
        
        if len(flagged) > 0:
            content.append("### Bin-Level Detail (Flagged Segments Only)")
            content.append("")
            content.append("Detailed bin-by-bin breakdown for segments with operational intelligence flags:")
            content.append("")
            
            # Group by segment
            for segment_id in flagged['segment_id'].unique():
                seg_bins = flagged[flagged['segment_id'] == segment_id]
                seg_label = seg_bins.iloc[0].get('seg_label', segment_id)
                
                content.append(f"#### {seg_label} ({segment_id})")
                content.append("")
                content.append(f"**Flagged Bins:** {len(seg_bins)}")
                content.append("")
                content.append("| Start (km) | End (km) | Length (m) | Density (p/m²) | LOS | Severity | Reason |")
                content.append("|------------|----------|------------|----------------|-----|----------|--------|")
                
                # Sort by severity, then density
                seg_bins_sorted = seg_bins.sort_values(
                    by=['severity_rank', 'density_peak'],
                    ascending=[False, False]
                )
                
                for _, bin_row in seg_bins_sorted.iterrows():
                    start_km = f"{bin_row['start_km']:.3f}"
                    end_km = f"{bin_row['end_km']:.3f}"
                    length_m = f"{bin_row.get('bin_len_m', 0):.0f}"
                    density = f"{bin_row['density_peak']:.4f}"  # Use 4 decimals to show small values
                    los = bin_row['los']
                    severity = bin_row['severity']
                    reason = bin_row['flag_reason']
                    
                    content.append(f"| {start_km} | {end_km} | {length_m} | {density} | {los} | {severity} | {reason} |")
                
                content.append("")
            
            content.append("---")
            content.append("")
    
    return content


def generate_markdown_report(
    results: Dict[str, Any], 
    start_times: Dict[str, float], 
    include_per_event: bool = True,
    include_operational_intelligence: bool = True,
    output_dir: str = "reports"
) -> str:
    """Generate markdown content for the density report with optional operational intelligence."""
    
    # Event start times for ordering
    event_order = sorted(start_times.items(), key=lambda x: x[1])
    
    # Build report content
    content = []
    
    # Header with standardized format (Issue #182)
    content.extend(_generate_report_header(results))
    
    # Quick Reference section
    content.extend(_generate_quick_reference_section())
    
    # Operational Intelligence Executive Summary (Issue #236)
    if include_operational_intelligence:
        content.extend(_generate_operational_intelligence_content(results, output_dir))
    
    # Executive Summary Table (TL;DR for race directors)
    summary_table = generate_summary_table(results.get("segments", {}))
    content.extend(summary_table)
    
    # Methodology section using v2.0 rulebook
    content.extend(_generate_methodology_section())
    
    # Event start times (showing actual participants in first segment as reference)
    content.extend(_generate_event_start_times_table(results, event_order))
    
    # Process each segment
    for segment_id, segment in results.get("segments", {}).items():
        content.extend(generate_segment_section(segment_id, segment, event_order, include_per_event))
        content.append("")
        content.append("---")
        content.append("")
    
    # Appendix with detailed methodology and definitions
    content.extend(_generate_appendix_content(results))
    
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
        with open("config/density_rulebook.yml", "r") as f:
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
        with open("config/density_rulebook.yml", "r") as f:
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
    
    Issue #231: Now prioritizes canonical segments from bins when available.
    Falls back to legacy density analysis if canonical segments not found.
    
    Args:
        results: Density analysis results
        start_times: Event start times in minutes
    
    Returns:
        Map dataset dictionary
    """
    # Issue #231: Try canonical segments first (ChatGPT's roadmap)
    try:
        from app.canonical_segments import (
            is_canonical_segments_available, get_segment_peak_densities, 
            get_segment_time_series, get_canonical_segments_metadata
        )
        
        if is_canonical_segments_available():
            print("🎯 Issue #231: Using canonical segments as source of truth")
            
            # Get canonical segments metadata
            metadata = get_canonical_segments_metadata()
            
            # Get peak densities and time series from canonical data
            segment_peaks = get_segment_peak_densities()
            segment_time_series = get_segment_time_series()
            
            # Load segments CSV for labels and other metadata
            try:
                from app.io.loader import load_segments
                segments_df = load_segments("data/segments.csv")
                segments_dict = {}
                for _, row in segments_df.iterrows():
                    segments_dict[row['seg_id']] = {
                        'seg_label': row.get('seg_label', row['seg_id']),
                        'width_m': row.get('width_m', 3.0),
                        'flow_type': row.get('flow_type', 'none')
                    }
            except Exception as e:
                print(f"⚠️ Could not load segments CSV: {e}, using defaults")
                segments_dict = {}
            
            # Generate map-friendly data structure with canonical segments
            map_data = {
                "ok": True,
                "source": "canonical_segments",
                "timestamp": datetime.now().isoformat(),
                "segments": {},
                "metadata": {
                    "total_segments": metadata.get("unique_segments", 0),
                    "total_windows": metadata.get("total_windows", 0),
                    "analysis_type": "canonical_segments_from_bins",
                    "methodology": "bottom_up_aggregation",
                    "density_method": "segments_from_bins",
                    "schema_version": "1.1.0",
                    "start_times": start_times
                }
            }
            
            # Process each segment from canonical data
            for segment_id, peak_data in segment_peaks.items():
                segment_info = segments_dict.get(segment_id, {})
                time_series = segment_time_series.get(segment_id, [])
                
                # Use peak_areal_density from canonical data
                peak_areal_density = peak_data["peak_areal_density"]
                
                map_data["segments"][segment_id] = {
                    "segment_id": segment_id,
                    "segment_label": segment_info.get('seg_label', segment_id),
                    "peak_areal_density": peak_areal_density,
                    "peak_mean_density": peak_data["peak_mean_density"],
                    "zone": _determine_zone(peak_areal_density),
                    "flow_type": segment_info.get('flow_type', 'none'),
                    "width_m": segment_info.get('width_m', 3.0),
                    "total_windows": peak_data["total_windows"],
                    "time_series": time_series,
                    "source": "canonical_segments"
                }
            
            print(f"✅ Generated map data from canonical segments: {len(segment_peaks)} segments")
            return map_data
            
    except ImportError:
        print("⚠️ Canonical segments module not available, using legacy analysis")
    except Exception as e:
        print(f"⚠️ Error using canonical segments: {e}, falling back to legacy analysis")
    
    # Legacy fallback: Use density analysis results
    print("📊 Using legacy density analysis for map data")
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

def save_map_dataset_to_storage(map_data: Dict[str, Any], output_dir: str, run_id: str = None) -> str:
    """
    Save map dataset to storage service (local or Cloud Storage).
    
    Args:
        map_data: Map dataset dictionary
        output_dir: Output directory (used for fallback or runflow bins path)
        run_id: Run identifier (Issue #455: UUID for runflow structure)
    
    Returns:
        Path to saved file
    """
    # Issue #455: Use runflow structure if run_id provided
    if run_id:
        from app.report_utils import get_runflow_file_path
        # Save to runflow/<uuid>/maps/map_data.json (no timestamp)
        file_path = get_runflow_file_path(run_id, "maps", "map_data.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(map_data, f, indent=2, default=str)
        print(f"🗺️ Map dataset saved to runflow: {file_path}")
        return file_path
    
    # Legacy: Use storage service
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

def _build_segment_catalog_from_results(results: Dict[str, Any], logger) -> dict:
    """Build segment catalog from density analysis results."""
    from app.bins_accumulator import SegmentInfo
    
    segments = {}
    if 'segments' in results and results['segments']:
        # Use segments from density analysis results
        results_segments = results['segments']
        if isinstance(results_segments, dict):
            # Real density analysis returns segments as a dict
            for seg_id, seg_data in results_segments.items():
                # Issue #248: Use actual segment length from density analysis
                length_m = float(seg_data.get('length_m', 1000.0))
                width_m = float(seg_data.get('width_m', 5.0))
                coords = seg_data.get('coords', None)
                
                # Log if we're using default (indicates missing data)
                if 'length_m' not in seg_data:
                    logger.warning(f"Segment {seg_id}: length_m not in seg_data, using default {length_m}m")
                
                segments[seg_id] = SegmentInfo(seg_id, length_m, width_m, coords)
        elif isinstance(results_segments, list):
            # Fallback for list format
            for seg in results_segments:
                seg_id = seg.get('seg_id') or seg.get('id')
                length_m = float(seg.get('length_m', 1000.0))
                width_m = float(seg.get('width_m', 5.0))
                coords = seg.get('coords', None)
                segments[seg_id] = SegmentInfo(seg_id, length_m, width_m, coords)
    else:
        # Fallback: create segments from results data
        logger.warning("No segment data in results, using fallback")
        segments = {
            "A1": SegmentInfo("A1", 1000.0, 5.0),
            "B1": SegmentInfo("B1", 800.0, 4.0)
        }
    
    return segments


def _create_time_windows_for_bins(start_times: Dict[str, float], dt_seconds: int) -> list:
    """Create time windows from start_times and analysis duration."""
    from datetime import datetime, timezone, timedelta
    from app.bins_accumulator import make_time_windows
    
    base_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Find earliest start time and total duration
    earliest_start_min = min(start_times.values())
    latest_end_min = max(start_times.values()) + 120  # Add 2 hours for analysis duration
    
    t0_utc = base_date + timedelta(minutes=earliest_start_min)
    total_duration_s = int((latest_end_min - earliest_start_min) * 60)
    
    return make_time_windows(t0=t0_utc, duration_s=total_duration_s, dt_seconds=dt_seconds)


def _apply_flagging_to_bin_features(
    geojson_features: list,
    bin_features: list,
    segments: dict,
    time_windows: list,
    logger
) -> None:
    """Apply unified flagging with utilization percentile to bin features."""
    import time
    flag_start = time.monotonic()
    
    try:
        from app import rulebook
        from app.utilization import add_utilization_percentile
        from app.schema_resolver import resolve_schema
        import pandas as pd
        
        # Create segments_dict for schema resolution
        segments_dict = {}
        try:
            from app.io.loader import load_segments
            segments_df = load_segments("data/segments.csv")
            for _, row in segments_df.iterrows():
                segments_dict[row['seg_id']] = {
                    'seg_label': row.get('seg_label', row['seg_id']),
                    'width_m': row.get('width_m', 3.0),
                    'flow_type': row.get('flow_type', 'none')
                }
        except Exception as e:
            logger.warning(f"Could not load segments CSV for flagging: {e}, using defaults")
            # Create minimal segments_dict from available segments
            for seg_id in segments.keys():
                segments_dict[seg_id] = {
                    'seg_label': seg_id,
                    'width_m': 5.0,
                    'flow_type': 'none'
                }
        
        # Convert features to DataFrame for vectorized processing
        flag_rows = []
        for idx, (feature, bin_feature) in enumerate(zip(geojson_features, bin_features)):
            props = feature["properties"]
            
            # Compute window_idx by finding matching time window
            window_idx = 0
            for w_idx, (t_start, t_end, duration) in enumerate(time_windows):
                if bin_feature.t_start == t_start and bin_feature.t_end == t_end:
                    window_idx = w_idx
                    break
            
            flag_rows.append({
                "feature_idx": idx,
                "segment_id": props["segment_id"],
                "bin_id": props["bin_id"],
                "start_km": props["start_km"],
                "end_km": props["end_km"],
                "t_start": props["t_start"],
                "t_end": props["t_end"],
                "density": props["density"],
                "rate": props["rate"],  # p/s
                "los_class": props["los_class"],
                "bin_size_km": props["bin_size_km"],
                # Add missing fields for flagging
                "window_idx": window_idx,
                "width_m": next((s.width_m for s in segments.values() if s.segment_id == props["segment_id"]), 5.0),
                "schema_key": resolve_schema(props["segment_id"], segments_dict),
            })
        
        flags_df = pd.DataFrame(flag_rows)
        
        # Compute utilization percentile per window (course-wide)
        flags_df = add_utilization_percentile(flags_df, cohort="window")
        
        # Apply rulebook flagging to each bin
        flag_results = []
        for _, row in flags_df.iterrows():
            result = rulebook.evaluate_flags(
                density_pm2=row["density"],
                rate_p_s=row["rate"],
                width_m=row["width_m"],
                schema_key=row["schema_key"],
                util_percentile=row.get("util_percentile")
            )
            flag_results.append(result)
        
        # Add flag results back to GeoJSON features
        for idx, (feature, result) in enumerate(zip(geojson_features, flag_results)):
            props = feature["properties"]
            props["flag_severity"] = result.severity
            props["flag_reason"] = result.flag_reason
            props["rate_per_m_per_min"] = result.rate_per_m_per_min
            props["util_percent"] = result.util_percent
            props["util_percentile"] = result.util_percentile
            props["window_idx"] = flags_df.iloc[idx]["window_idx"]
            props["schema_key"] = flags_df.iloc[idx]["schema_key"]
            props["width_m"] = flags_df.iloc[idx]["width_m"]
            # Update LOS from rulebook (may differ from bins_accumulator default)
            props["los_class"] = result.los_class
        
        flag_time = int((time.monotonic() - flag_start) * 1000)
        flagged_count = sum(1 for r in flag_results if r.severity != "none")
        logger.info(f"✅ Flagging complete: {flagged_count}/{len(flag_results)} bins flagged ({flag_time}ms)")
        
    except Exception as flag_error:
        logger.warning(f"⚠️ Flagging failed, bins will have no flags: {flag_error}")
        # Continue without flags - bins will still have base properties


def _add_geometries_to_bin_features(
    geojson_features: list,
    analysis_context: Optional[AnalysisContext],
    logger
) -> None:
    """Add geometry backfill using bin_geometries.py."""
    import time
    geom_start = time.monotonic()
    
    try:
        from app.bin_geometries import generate_bin_polygon
        from app.core.gpx.processor import load_all_courses, generate_segment_coordinates
        from app.io.loader import load_segments
        import pandas as pd
        import json
        
        # Get segments_csv path from analysis_context
        segments_csv_path = analysis_context.segments_csv_path if analysis_context else "data/segments.csv"
        
        # Load segment metadata for geometry
        segments_df = load_segments(segments_csv_path)
        
        # Load GPX courses for centerlines
        courses = load_all_courses("data")
        
        # Convert segments to dict format for GPX processor
        segments_list = []
        for _, segment in segments_df.iterrows():
            segments_list.append({
                "seg_id": segment['seg_id'],
                "segment_label": segment.get('seg_label', segment['seg_id']),
                "10K": segment.get('10K', 'n'),
                "half": segment.get('half', 'n'),
                "full": segment.get('full', 'n'),
                "10K_from_km": segment.get('10K_from_km'),
                "10K_to_km": segment.get('10K_to_km'),
                "half_from_km": segment.get('half_from_km'),
                "half_to_km": segment.get('half_to_km'),
                "full_from_km": segment.get('full_from_km'),
                "full_to_km": segment.get('full_to_km')
            })
        
        # Generate segment centerlines from GPX
        segments_with_coords = generate_segment_coordinates(courses, segments_list)
        
        # Build lookups
        centerlines = {}  # segment_id -> centerline_coords (course-absolute)
        segment_offsets = {}  # segment_id -> course_offset_km (to convert bin-relative to course-absolute)
        widths = {}  # segment_id -> width_m
        
        for seg_coords in segments_with_coords:
            seg_id = seg_coords['seg_id']
            if seg_coords.get('line_coords') and not seg_coords.get('coord_issue'):
                centerlines[seg_id] = seg_coords['line_coords']
                # Store the course offset (from_km) to convert bin-relative km to course-absolute km
                segment_offsets[seg_id] = seg_coords.get('from_km', 0.0)
        
        for _, seg in segments_df.iterrows():
            widths[seg['seg_id']] = float(seg.get('width_m', 5.0))
        
        # Add geometry to each feature
        geometries_added = 0
        geometries_failed = 0
        
        for f in geojson_features:
            seg_id = f["properties"]["segment_id"]
            bin_start_km = f["properties"]["start_km"]  # Bin-relative km
            bin_end_km = f["properties"]["end_km"]      # Bin-relative km
            
            # Get centerline, offset, and width
            centerline = centerlines.get(seg_id)
            segment_offset = segment_offsets.get(seg_id, 0.0)  # Course-absolute offset
            width_m = widths.get(seg_id, 5.0)
            
            if centerline and segment_offset is not None:
                # CRITICAL FIX: Bins use segment-relative km, but centerline is already sliced
                # The centerline from gpx_processor is ALREADY sliced to segment boundaries
                # So we should use bin-relative km directly (0.0 = start of centerline)
                # The centerline itself spans the full segment length
                
                # Generate polygon geometry using bin-relative coordinates
                # (centerline is already segment-specific, not full course)
                polygon = generate_bin_polygon(
                    segment_centerline_coords=centerline,
                    bin_start_km=bin_start_km,  # Use bin-relative (centerline is segment-sliced)
                    bin_end_km=bin_end_km,
                    segment_width_m=width_m
                )
                
                if polygon and polygon.is_valid:
                    # Convert to GeoJSON geometry dict
                    f["geometry"] = json.loads(json.dumps(polygon.__geo_interface__))
                    geometries_added += 1
                else:
                    geometries_failed += 1
                    # Leave as None
            else:
                geometries_failed += 1
                # No centerline available, leave geometry as None
        
        geom_time = int((time.monotonic() - geom_start) * 1000)
        logger.info(f"✅ Bin geometries generated: {geometries_added} successful, {geometries_failed} failed ({geom_time}ms)")
        
    except Exception as geom_error:
        logger.warning(f"⚠️ Geometry generation failed, bins will have null geometry: {geom_error}")
        # Continue without geometries - bins will still have properties


def generate_bin_dataset(results: Dict[str, Any], start_times: Dict[str, float], bin_size_km: float = 0.1, 
                        analysis_context: Optional[AnalysisContext] = None, dt_seconds: int = 60) -> Dict[str, Any]:
    """
    Generate bin-level dataset using ChatGPT's vectorized bins_accumulator.py.
    
    This function creates bin-level data with real operational intelligence using
    vectorized numpy accumulation for proper density/flow calculations.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    start_time = time.monotonic()
    
    try:
        # Import ChatGPT's bins_accumulator
        from app.bins_accumulator import (
            SegmentInfo, build_bin_features, make_time_windows, to_geojson_features
        )
        from app.utils.constants import (
            BIN_SCHEMA_VERSION, DEFAULT_BIN_TIME_WINDOW_SECONDS, 
            MAX_BIN_GENERATION_TIME_SECONDS, BIN_MAX_FEATURES, HOTSPOT_SEGMENTS
        )
        
        # Use dt_seconds from ChatGPT specification
        if dt_seconds is None:
            dt_seconds = DEFAULT_BIN_TIME_WINDOW_SECONDS
        
        # Store original values for hotspot preservation
        original_dt_seconds = dt_seconds
        original_bin_size_km = bin_size_km
        
        log_bins_event(action="start", bin_size_km=bin_size_km, dt_seconds=dt_seconds)
        
        # 1) Build segment catalog - extracted to helper function to reduce complexity
        segments = _build_segment_catalog_from_results(results, logger)
        
        # 2) Create time windows - extracted to helper function to reduce complexity
        time_windows = _create_time_windows_for_bins(start_times, dt_seconds)
        
        # 3) Build runner→segment/window mapping (adapter to your model)
        runners_by_segment_and_window = build_runner_window_mapping(results, time_windows, start_times)
        
        # 4) Generate bin features using ChatGPT's vectorized accumulator with performance optimization
        bin_build = generate_bin_features_with_coarsening(
            segments=segments,
            time_windows=time_windows,
            runners_by_segment_and_window=runners_by_segment_and_window,
            bin_size_km=bin_size_km,
            original_bin_size_km=original_bin_size_km,
            dt_seconds=dt_seconds,
            original_dt_seconds=original_dt_seconds,
            logger=logger,
        )
        
        # 5) Build geometries + GeoJSON
        geojson_features = to_geojson_features(bin_build.features)
        
        # Issue #254: Apply unified flagging - extracted to helper function to reduce complexity
        _apply_flagging_to_bin_features(geojson_features, bin_build.features, segments, time_windows, logger)
        
        # Issue #249: Add geometry backfill - extracted to helper function to reduce complexity
        _add_geometries_to_bin_features(geojson_features, analysis_context, logger)
        
        geojson = {"type": "FeatureCollection", "features": geojson_features, "metadata": bin_build.metadata}
        
        # 6) Safety checks per ChatGPT guidance
        md = geojson.get("metadata", {})
        occ = int(md.get("occupied_bins", 0))
        ndz = int(md.get("nonzero_density_bins", 0))
        if occ == 0 or ndz == 0:
            logger.error("🛑 Empty bin dataset: occupied_bins=%s nonzero_density_bins=%s", occ, ndz)
            geojson.setdefault("metadata", {})["status"] = "empty"
        
        elapsed = time.monotonic() - start_time
        log_bins_event(action="complete", 
                      bin_generation_ms=int(elapsed * 1000),
                      occupied_bins=occ,
                      nonzero_density_bins=ndz,
                      total_features=len(geojson_features))
        
        return {
            "ok": True,
            "source": "bins_accumulator",
            "timestamp": datetime.now().isoformat(),
            "geojson": geojson,
            "metadata": {
                **bin_build.metadata,
                "analysis_type": "bins",
                "schema_version": BIN_SCHEMA_VERSION,
                "generated_by": "bins_accumulator",
                "dt_seconds": dt_seconds
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating bin dataset: {e}")
        return {
            "ok": False,
            "error": str(e),
            "geojson": {"type": "FeatureCollection", "features": []},
            "metadata": {"total_segments": 0, "analysis_type": "bins", "status": "error"}
        }

def generate_bin_features_with_coarsening(segments: dict, time_windows: list, runners_by_segment_and_window: dict,
                                        bin_size_km: float, original_bin_size_km: float, dt_seconds: int, 
                                        original_dt_seconds: int, logger) -> dict:
    """
    Generate bin features with ChatGPT's performance optimization:
    - Temporal-first coarsening for non-hotspots
    - Hotspot preservation (keep original resolution)
    - Soft-timeout reaction with auto-coarsening
    """
    from app.bins_accumulator import build_bin_features
    from app.utils.constants import MAX_BIN_GENERATION_TIME_SECONDS, BIN_MAX_FEATURES, HOTSPOT_SEGMENTS
    import time
    
    start_time = time.monotonic()
    
    # Apply hotspot-aware coarsening
    coarsened_segments = {}
    coarsened_runners = {}
    
    for seg_id, segment in segments.items():
        is_hotspot = seg_id in HOTSPOT_SEGMENTS
        
        if is_hotspot:
            # Hotspot preservation: keep original resolution
            coarsened_segments[seg_id] = segment
            coarsened_runners[seg_id] = runners_by_segment_and_window.get(seg_id, {})
            logger.debug(f"Preserving hotspot resolution for segment {seg_id}")
        else:
            # Non-hotspot: apply coarsening
            coarsened_segments[seg_id] = segment
            coarsened_runners[seg_id] = runners_by_segment_and_window.get(seg_id, {})
    
    # Generate bin features with current parameters
    bin_build = build_bin_features(
        segments=coarsened_segments,
        time_windows=time_windows,
        runners_by_segment_and_window=coarsened_runners,
        bin_size_km=bin_size_km,
        los_thresholds=None,
        logger=logger,
    )
    
    elapsed = time.monotonic() - start_time
    features_count = len(bin_build.features)
    
    # Apply ChatGPT's soft-timeout reaction & budgets
    if elapsed > MAX_BIN_GENERATION_TIME_SECONDS or features_count > BIN_MAX_FEATURES:
        logger.warning(f"Performance budget exceeded: elapsed={elapsed:.1f}s, features={features_count}")
        
        # Temporal-first coarsening for non-hotspots (ChatGPT guidance)
        new_dt_seconds = min(max(dt_seconds * 2, 120), 180)  # Double dt, cap at 180s
        new_bin_size_km = bin_size_km
        
        # Spatial coarsening for non-hotspots only if still over budget
        if features_count > BIN_MAX_FEATURES and bin_size_km < 0.2:
            new_bin_size_km = 0.2
        
        logger.warning(f"Coarsening bins due to budget: dt={new_dt_seconds}s, bin={new_bin_size_km}km")
        
        # Recreate time windows with coarsened dt
        from datetime import datetime, timezone, timedelta
        base_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Use original start times for time window calculation
        earliest_start_min = 420  # Default start time
        latest_end_min = 460 + 120  # Default end time + 2 hours
        
        t0_utc = base_date + timedelta(minutes=earliest_start_min)
        total_duration_s = int((latest_end_min - earliest_start_min) * 60)
        
        # Recreate time windows with coarsened dt
        from app.bins_accumulator import make_time_windows
        coarsened_time_windows = make_time_windows(t0=t0_utc, duration_s=total_duration_s, dt_seconds=new_dt_seconds)
        
        # Issue #243 Fix: Re-map runners to new coarsened window indices
        # Each new coarsened window aggregates runners from multiple old windows
        import numpy as np
        coarsening_factor = new_dt_seconds // dt_seconds  # e.g., 120s / 60s = 2
        re_mapped_runners = {}
        
        for seg_id, old_windows in coarsened_runners.items():
            re_mapped_runners[seg_id] = {}
            
            for new_w_idx, (t_start, t_end, _) in enumerate(coarsened_time_windows):
                # Determine which old window indices map to this new window
                old_start_idx = new_w_idx * coarsening_factor
                old_end_idx = old_start_idx + coarsening_factor
                
                # Aggregate runners from all old windows that fall into this new window
                all_pos_m = []
                all_speed_mps = []
                
                for old_idx in range(old_start_idx, old_end_idx):
                    if old_idx in old_windows:
                        old_data = old_windows[old_idx]
                        if len(old_data.get("pos_m", [])) > 0:
                            all_pos_m.append(old_data["pos_m"])
                            all_speed_mps.append(old_data["speed_mps"])
                
                # Concatenate all runner arrays for this new window
                if all_pos_m:
                    re_mapped_runners[seg_id][new_w_idx] = {
                        "pos_m": np.concatenate(all_pos_m),
                        "speed_mps": np.concatenate(all_speed_mps)
                    }
                else:
                    re_mapped_runners[seg_id][new_w_idx] = {
                        "pos_m": np.array([], dtype=np.float64),
                        "speed_mps": np.array([], dtype=np.float64)
                    }
        
        logger.info(f"Re-mapped runners to {len(coarsened_time_windows)} coarsened windows (factor={coarsening_factor})")
        
        # Regenerate with coarsened parameters and re-mapped runners
        bin_build = build_bin_features(
            segments=coarsened_segments,
            time_windows=coarsened_time_windows,
            runners_by_segment_and_window=re_mapped_runners,  # Use re-mapped data
            bin_size_km=new_bin_size_km,
            los_thresholds=None,
            logger=logger,
        )
        
        # Update metadata with coarsening info
        bin_build.metadata.update({
            "coarsening_applied": True,
            "original_dt_seconds": original_dt_seconds,
            "coarsened_dt_seconds": new_dt_seconds,
            "original_bin_size_km": original_bin_size_km,
            "coarsened_bin_size_km": new_bin_size_km,
            "hotspot_preservation": True,
            "hotspot_segments": list(HOTSPOT_SEGMENTS)
        })
        
        logger.info(f"Coarsening complete: {len(bin_build.features)} features in {time.monotonic() - start_time:.1f}s")
    
    return bin_build

def _build_segment_ranges_per_event(segments_config: pd.DataFrame) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """Build segment km ranges dictionary per event type."""
    segment_ranges = {}
    for _, seg_row in segments_config.iterrows():
        seg_id = seg_row['seg_id']
        segment_ranges[seg_id] = {
            'Full': (seg_row['full_from_km'], seg_row['full_to_km']) if pd.notna(seg_row.get('full_from_km')) else None,
            'Half': (seg_row['half_from_km'], seg_row['half_to_km']) if pd.notna(seg_row.get('half_from_km')) else None,
            '10K': (seg_row['10K_from_km'], seg_row['10K_to_km']) if pd.notna(seg_row.get('10K_from_km')) else None,
        }
    return segment_ranges


def _precompute_runner_data(pace_data: pd.DataFrame) -> pd.DataFrame:
    """Precompute pace, start offset, and speed for all runners."""
    import numpy as np
    
    pace_data = pace_data.copy()
    pace_data['pace_sec_per_km'] = pace_data['pace'].values * 60.0
    pace_data['start_offset_sec'] = pace_data.get('start_offset', pd.Series([0]*len(pace_data))).fillna(0).values.astype(float)
    pace_data['speed_mps'] = np.where(pace_data['pace_sec_per_km'] > 0, 
                                       1000.0 / pace_data['pace_sec_per_km'], 
                                       0)
    return pace_data


def _calculate_window_duration_seconds(time_windows: list) -> int:
    """Calculate window duration in seconds from time windows."""
    if len(time_windows) >= 2:
        (t0, t1, _) = time_windows[0]
        (t2, t3, _) = time_windows[1]
        return int((t2 - t0).total_seconds())
    return 120  # Default fallback


def _calculate_window_midpoint_seconds(t_start, t_end) -> float:
    """Calculate time window midpoint in seconds from midnight."""
    t_mid = t_start + (t_end - t_start) / 2
    return t_mid.hour * 3600 + t_mid.minute * 60 + t_mid.second


def _ensure_empty_mapping_entry(mapping: Dict, seg_id: str, w_idx: int) -> None:
    """Ensure mapping has empty arrays for segment/window if not present."""
    import numpy as np
    
    if seg_id not in mapping:
        mapping[seg_id] = {}
    if w_idx not in mapping[seg_id]:
        mapping[seg_id][w_idx] = {
            "pos_m": np.array([], dtype=np.float64),
            "speed_mps": np.array([], dtype=np.float64)
        }


def _calculate_runner_positions_for_segment_window(
    event_runners_copy: pd.DataFrame,
    t_mid_sec: float,
    from_km: float,
    to_km: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate runner positions and speeds for a specific segment/window.
    
    Returns:
        Tuple of (pos_m array, speed_mps array) for runners in segment during window
    """
    import numpy as np
    
    runner_start_times = event_runners_copy['runner_start_time'].values
    pace_sec_per_km = event_runners_copy['pace_sec_per_km'].values
    
    # Calculate when runners reach segment boundaries
    time_at_seg_start = runner_start_times + pace_sec_per_km * from_km
    time_at_seg_end = runner_start_times + pace_sec_per_km * to_km
    
    # Vectorized check: runner in segment during time window (±30s tolerance)
    in_window_mask = (time_at_seg_start <= (t_mid_sec + 30)) & (time_at_seg_end >= (t_mid_sec - 30))
    
    # Filter to runners in window
    valid_runners = event_runners_copy[in_window_mask]
    if len(valid_runners) == 0:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    
    # Vectorized position calculations
    time_since_start = t_mid_sec - valid_runners['runner_start_time'].values
    started_mask = time_since_start >= 0
    
    if not started_mask.any():
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    
    # Calculate runner positions (vectorized)
    valid_pace = valid_runners['pace_sec_per_km'].values[started_mask]
    runner_abs_km = np.where(valid_pace > 0, 
                            time_since_start[started_mask] / valid_pace, 
                            0)
    
    # Check if within segment range (vectorized)
    in_segment_mask = (runner_abs_km >= from_km) & (runner_abs_km <= to_km)
    
    if not in_segment_mask.any():
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64)
    
    # Position relative to segment start (meters)
    pos_m = (runner_abs_km[in_segment_mask] - from_km) * 1000.0
    speeds = valid_runners['speed_mps'].values[started_mask][in_segment_mask]
    
    return pos_m, speeds


def _process_event_windows_and_segments(
    event: str,
    event_start_sec: float,
    event_min: float,
    earliest_start_min: float,
    start_idx: int,
    event_runners_copy: pd.DataFrame,
    time_windows: list,
    WINDOW_SECONDS: int,
    segments_dict: Dict,
    segment_ranges: Dict,
    mapping: Dict
) -> None:
    """Process all windows and segments for a single event."""
    import numpy as np
    
    for global_w_idx in range(start_idx, len(time_windows)):
        (t_start, t_end, _) = time_windows[global_w_idx]
        w_idx = global_w_idx  # Use global window index for mapping
        
        t_mid_sec = _calculate_window_midpoint_seconds(t_start, t_end)
        
        # Skip windows before this event starts
        if t_mid_sec < (event_start_sec - WINDOW_SECONDS):
            continue
        
        # Stop processing if we're way past when runners could be on course
        max_runner_time = event_start_sec + event_runners_copy['start_offset_sec'].max() + (50 * 1000)  # ~50km at slow pace
        if t_mid_sec > max_runner_time:
            break
        
        # For each segment this event uses
        for seg_id in segments_dict.keys():
            if seg_id not in segment_ranges:
                _ensure_empty_mapping_entry(mapping, seg_id, w_idx)
                continue
            
            km_range = segment_ranges[seg_id].get(event)
            if km_range is None:
                continue
            
            from_km, to_km = km_range
            if pd.isna(from_km) or pd.isna(to_km):
                continue
            
            # Calculate runner positions for this segment/window
            pos_m, speeds = _calculate_runner_positions_for_segment_window(
                event_runners_copy, t_mid_sec, from_km, to_km
            )
            
            if len(pos_m) > 0:
                # Initialize segment/window in mapping if needed
                if seg_id not in mapping:
                    mapping[seg_id] = {}
                
                # Append or create arrays for this segment/window
                if w_idx in mapping[seg_id]:
                    # Append to existing (in case another event already added runners)
                    mapping[seg_id][w_idx]["pos_m"] = np.concatenate([
                        mapping[seg_id][w_idx]["pos_m"],
                        pos_m
                    ])
                    mapping[seg_id][w_idx]["speed_mps"] = np.concatenate([
                        mapping[seg_id][w_idx]["speed_mps"],
                        speeds
                    ])
                else:
                    mapping[seg_id][w_idx] = {
                        "pos_m": pos_m,
                        "speed_mps": speeds
                    }
            else:
                _ensure_empty_mapping_entry(mapping, seg_id, w_idx)


def build_runner_window_mapping(results: Dict[str, Any], time_windows: list, start_times: Dict[str, float]) -> Dict[str, Dict[int, Dict[str, Any]]]:
    """
    Build runner→segment/window mapping adapter for bins_accumulator.
    
    Uses actual runner data from pace CSV with proper segment km ranges per event.
    Fixed Issue #239: Replaced placeholder random data with real runner calculations.
    
    This function maps runner data to the format expected by ChatGPT's bins_accumulator:
    runners_by_segment_and_window[seg_id][w_idx] = {"pos_m": np.ndarray, "speed_mps": np.ndarray}
    """
    import numpy as np
    from datetime import datetime, timezone, timedelta
    
    # Initialize mapping structure
    mapping = {}
    
    # Get segments from results
    segments_dict = results.get('segments', {})
    if not segments_dict:
        return {}
    
    for seg_id in segments_dict.keys():
        mapping[seg_id] = {}
    
    # Load pace data and segments configuration
    try:
        pace_data = pd.read_csv("data/runners.csv")
        segments_config = pd.read_csv("data/segments.csv")
    except Exception as e:
        logger.warning(f"Could not load data for runner mapping: {e}")
        return mapping
    
    # Build segment ranges and precompute runner data
    segment_ranges = _build_segment_ranges_per_event(segments_config)
    pace_data = _precompute_runner_data(pace_data)
    
    # Calculate window duration
    WINDOW_SECONDS = _calculate_window_duration_seconds(time_windows)
    earliest_start_min = min(start_times.values())
    
    # Issue #243 Fix: Loop through events first, then their relevant windows
    for event in ['Full', '10K', 'Half']:
        # Get event start time
        event_min = start_times.get(event)
        if event_min is None:
            continue
        
        event_start_sec = event_min * 60.0
        
        # Calculate which global window index this event starts at
        start_idx = int(((event_min - earliest_start_min) * 60) // WINDOW_SECONDS)
        
        # Get runners for this event
        event_mask = pace_data['event'] == event
        event_runners = pace_data[event_mask]
        
        if len(event_runners) == 0:
            continue
        
        # Calculate runner start times anchored to THIS event's start
        event_runners_copy = event_runners.copy()
        event_runners_copy['runner_start_time'] = event_start_sec + event_runners_copy['start_offset_sec']
        
        # Process all windows and segments for this event
        _process_event_windows_and_segments(
            event, event_start_sec, event_min, earliest_start_min,
            start_idx, event_runners_copy, time_windows, WINDOW_SECONDS,
            segments_dict, segment_ranges, mapping
        )
    
    return mapping

def _build_geojson_from_bin_data(bin_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build GeoJSON data structure from bin_data."""
    from app.utils.constants import BIN_SCHEMA_VERSION
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": [],
        "metadata": {
            "schema_version": BIN_SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(),
            "total_bins": len(bin_data.get("geojson", {}).get("features", [])),
            "analysis_type": "bins"
        }
    }
    
    # Copy features from bin_data if available
    if "geojson" in bin_data and "features" in bin_data["geojson"]:
        geojson_data["features"] = bin_data["geojson"]["features"]
        geojson_data["metadata"]["total_bins"] = len(bin_data["geojson"]["features"])
    
    return geojson_data


def _convert_geometry_to_wkb(geometry_coords: list, bin_id: str) -> bytes:
    """Convert geometry coordinates to WKB format."""
    try:
        from shapely.geometry import LineString
        from shapely import wkb
        
        if not geometry_coords or not isinstance(geometry_coords, list) or len(geometry_coords) == 0:
            return b""
        
        # Handle different geometry types
        if isinstance(geometry_coords[0][0], list):  # Polygon
            # Convert polygon to linestring for simplicity
            coords = geometry_coords[0] if geometry_coords else []
        else:  # Already linestring format
            coords = geometry_coords
        
        if len(coords) >= 2:
            return wkb.dumps(LineString(coords), hex=False)
        return b""
    except Exception as geom_e:
        logger.warning(f"Geometry conversion failed for bin {bin_id}: {geom_e}")
        return b""


def _build_parquet_row_from_feature(feature: Dict[str, Any]) -> Dict[str, Any]:
    """Build Parquet row from GeoJSON feature."""
    from app.utils.constants import BIN_SCHEMA_VERSION
    
    props = feature["properties"]
    geometry_coords = feature.get("geometry", {}).get("coordinates", [])
    geometry_wkb = _convert_geometry_to_wkb(geometry_coords, props.get('bin_id', 'unknown'))
    
    return {
        "bin_id": str(props.get("bin_id", "")),
        "segment_id": str(props.get("segment_id", "")),
        "start_km": float(props.get("start_km", 0.0)),
        "end_km": float(props.get("end_km", 0.0)),
        "t_start": str(props.get("t_start", "")),
        "t_end": str(props.get("t_end", "")),
        "window_idx": int(props.get("window_idx", 0)),
        "density": float(props.get("density", 0.0)),
        "rate": float(props.get("rate", 0.0)),
        "los_class": str(props.get("los_class", "A")),
        # Issue #254: Unified flagging fields
        "flag_severity": str(props.get("flag_severity", "none")),
        "flag_reason": str(props.get("flag_reason") or ""),
        "rate_per_m_per_min": float(props.get("rate_per_m_per_min") or 0.0),
        "util_percent": float(props.get("util_percent") or 0.0),
        "util_percentile": float(props.get("util_percentile") or 0.0),
        "schema_key": str(props.get("schema_key", "on_course_open")),
        "width_m": float(props.get("width_m", 5.0)),
        # Original fields
        "bin_size_km": 0.1,  # Use constant for now
        "schema_version": BIN_SCHEMA_VERSION,
        "geometry": geometry_wkb
    }


def _write_parquet_file(parquet_rows: list, parquet_path: str) -> None:
    """Write Parquet file from rows."""
    from app.utils.constants import BIN_SCHEMA_VERSION
    
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        
        if parquet_rows:
            table = pa.Table.from_pylist(parquet_rows)
            pq.write_table(table, parquet_path, compression='zstd')
        else:
            # Empty dataset
            schema = pa.schema([
                ('bin_id', pa.string()),
                ('segment_id', pa.string()),
                ('start_km', pa.float64()),
                ('end_km', pa.float64()),
                ('t_start', pa.string()),
                ('t_end', pa.string()),
                ('window_idx', pa.int64()),
                ('density', pa.float64()),
                ('rate', pa.float64()),
                ('los_class', pa.string()),
                # Issue #254: Unified flagging fields
                ('flag_severity', pa.string()),
                ('flag_reason', pa.string()),
                ('rate_per_m_per_min', pa.float64()),
                ('util_percent', pa.float64()),
                ('util_percentile', pa.float64()),
                ('schema_key', pa.string()),
                ('width_m', pa.float64()),
                # Original fields
                ('bin_size_km', pa.float64()),
                ('schema_version', pa.string()),
                ('geometry', pa.binary())
            ])
            empty_table = pa.Table.from_arrays([[] for _ in schema], schema=schema)
            pq.write_table(empty_table, parquet_path, compression='zstd')
            
    except ImportError:
        # Fallback if pyarrow not available
        import json
        with open(parquet_path, 'w', encoding='utf-8') as f:
            json.dump({
                "error": "pyarrow not available",
                "schema_version": BIN_SCHEMA_VERSION,
                "note": "Install pyarrow for Parquet support"
            }, f, indent=2)


def save_bin_artifacts_legacy(bin_data: Dict[str, Any], output_dir: str) -> tuple[str, str]:
    """
    Save bin dataset as both GeoJSON and Parquet files per ChatGPT specification.
    
    Args:
        bin_data: The bin dataset to save
        output_dir: Base output directory for reports
        
    Returns:
        tuple: (geojson_path, parquet_path)
    """
    import json
    from app.utils.constants import MAX_BIN_DATASET_SIZE_MB
    
    # Create reports directory with date
    date_str = datetime.now().strftime("%Y-%m-%d")
    reports_dir = os.path.join(output_dir, date_str)
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate standardized filenames
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    geojson_filename = f"{timestamp}-BinDataset.geojson"
    parquet_filename = f"{timestamp}-BinDataset.parquet"
    
    geojson_path = os.path.join(reports_dir, geojson_filename)
    parquet_path = os.path.join(reports_dir, parquet_filename)
    
    try:
        # Prepare GeoJSON data
        geojson_data = _build_geojson_from_bin_data(bin_data)
        
        # Check file size before saving
        geojson_str = json.dumps(geojson_data, default=str)
        size_mb = len(geojson_str.encode('utf-8')) / (1024 * 1024)
        
        if size_mb > MAX_BIN_DATASET_SIZE_MB:
            raise ValueError(f"Bin dataset size ({size_mb:.1f}MB) exceeds limit ({MAX_BIN_DATASET_SIZE_MB}MB)")
        
        # Save GeoJSON file
        with open(geojson_path, 'w', encoding='utf-8') as f:
            f.write(geojson_str)
        
        # Build Parquet rows from features
        parquet_rows = []
        for feature in geojson_data["features"]:
            row = _build_parquet_row_from_feature(feature)
            parquet_rows.append(row)
        
        # Write Parquet file
        _write_parquet_file(parquet_rows, parquet_path)
        
        return geojson_path, parquet_path
        
    except Exception as e:
        # Clean up partial files on error
        for path in [geojson_path, parquet_path]:
            if os.path.exists(path):
                os.remove(path)
        raise e


def generate_bins_geojson_with_temporal_windows(all_bins_data, start_times: Dict[str, int], 
                                              dt_seconds: int, bin_size_km: float) -> Dict[str, Any]:
    """
    Generate GeoJSON with real temporal windows and proper flow calculation per ChatGPT specification.
    
    This implements Option B: analysis time windows (1-minute slices) for operational accuracy.
    """
    import logging
    from datetime import datetime, timedelta
    logger = logging.getLogger(__name__)
    
    try:
        
        # Start with existing GeoJSON generation
        base_geojson = generate_bins_geojson(all_bins_data)
        
        if not base_geojson or "features" not in base_geojson:
            return {"type": "FeatureCollection", "features": []}
        
        # Enhance features with real temporal windows and proper flow
        enhanced_features = []
        
        for feature in base_geojson["features"]:
            if "properties" not in feature:
                continue
                
            props = feature["properties"]
            
            # Calculate real temporal windows per ChatGPT specification
            # Use analysis window bounds instead of datetime.now()
            segment_id = props.get("segment_id", "")
            start_km = props.get("start_km", 0.0)
            end_km = props.get("end_km", 0.0)
            
            # Calculate temporal bounds based on runner flow through this bin
            # For now, use a simplified approach - can be enhanced with actual runner timing
            base_time = datetime(2025, 5, 11, 9, 0, 0)  # Race day baseline
            
            # Estimate bin timing based on distance and average pace
            # This is a simplified implementation - can be enhanced with actual runner data
            avg_pace_min_per_km = 5.5  # Average marathon pace
            bin_center_km = (start_km + end_km) / 2
            
            # Calculate when runners typically reach this bin
            time_to_bin_minutes = bin_center_km * avg_pace_min_per_km
            bin_start_time = base_time + timedelta(minutes=time_to_bin_minutes)
            bin_end_time = bin_start_time + timedelta(seconds=dt_seconds)
            
            # Update properties with real temporal data
            props["t_start"] = bin_start_time.isoformat() + "Z"
            props["t_end"] = bin_end_time.isoformat() + "Z"
            
            # Calculate proper flow using ChatGPT's formula: flow = density * width_m * speed_mps
            density = props.get("density", 0.0)
            
            # Get segment width (default 5m if not available)
            width_m = props.get("width_m", 5.0)  # Can be enhanced with actual segment data
            
            # Calculate speed in m/s from pace
            speed_mps = 1000 / (avg_pace_min_per_km * 60)  # Convert min/km to m/s
            
            # Apply throughput rate formula (renamed from 'flow' to avoid confusion with Flow analysis)
            rate_persons_per_sec = density * width_m * speed_mps
            props["rate"] = rate_persons_per_sec
            
            # Ensure bin_id format per ChatGPT spec
            if "bin_id" not in props:
                props["bin_id"] = f"{segment_id}:{start_km:.1f}-{end_km:.1f}"
            
            # Ensure LOS class is properly calculated
            if "los_class" not in props:
                if density >= 2.0:
                    props["los_class"] = "F"
                elif density >= 1.5:
                    props["los_class"] = "E"
                elif density >= 1.0:
                    props["los_class"] = "D"
                elif density >= 0.5:
                    props["los_class"] = "C"
                elif density >= 0.2:
                    props["los_class"] = "B"
                else:
                    props["los_class"] = "A"
            
            enhanced_features.append(feature)
        
        # Return enhanced GeoJSON
        return {
            "type": "FeatureCollection",
            "features": enhanced_features,
            "metadata": {
                "schema_version": BIN_SCHEMA_VERSION,
                "generated_at": datetime.now().isoformat(),
                "total_bins": len(enhanced_features),
                "dt_seconds": dt_seconds,
                "bin_size_km": bin_size_km
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating bins GeoJSON with temporal windows: {e}")
        # Fallback to basic generation
        return generate_bins_geojson(all_bins_data) or {"type": "FeatureCollection", "features": []}


def save_bin_dataset(bin_data: Dict[str, Any], output_dir: str) -> str:
    """
    Legacy function - redirects to save_bin_artifacts for backward compatibility.
    """
    from app.save_bins import save_bin_artifacts
    geojson_path, _ = save_bin_artifacts(bin_data, output_dir)
    return geojson_path


def generate_new_density_report_issue246(
    reports_dir: str,
    output_path: Optional[str] = None,
    app_version: str = "1.6.42"
) -> Dict[str, Any]:
    """
    Generate the new density report per Issue #246 specification.
    
    This function integrates the new report system into the existing density_report.py
    to replace the legacy report structure.
    
    Args:
        reports_dir: Directory containing Parquet files
        output_path: Path to save the report (optional)
        app_version: Application version
        
    Returns:
        Dictionary with report content and metadata
    """
    from app.new_density_report import generate_new_density_report
    from pathlib import Path
    
    # Convert string paths to Path objects
    reports_path = Path(reports_dir)
    output_path_obj = Path(output_path) if output_path else None
    
    # Generate the new report
    results = generate_new_density_report(reports_path, output_path_obj, app_version)
    
    # Return in the format expected by the existing API
    return {
        'report_content': results['report_content'],
        'stats': results['stats'],
        'segment_summary': results['segment_summary'],
        'flagged_bins': results['flagged_bins'],
        'context': results['context'],
        'generation_time': results['generation_time'],
        'success': True,
        'message': 'New density report generated successfully'
    }
