"""
Density Template Engine Module

This module provides template-driven narrative generation for density reports,
implementing the basic template engine for Phase 1 of Density v1.6.11.

Author: AI Assistant
Version: 1.6.11
"""

import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TemplateContext:
    """Context data for template interpolation."""
    segment_id: str
    segment_label: str
    segment_type: str
    flow_type: str
    los_score: str
    peak_concurrency: int
    peak_areal_density: float
    peak_crowd_density: float
    active_duration: str
    peak_window_clock: List[str]
    events_included: List[str]


class DensityTemplateEngine:
    """Basic template engine for density report narratives."""
    
    def __init__(self, rulebook_path: str = "requirements/density_v1.6.11/Density_Rulebook_v2.yml"):
        """Initialize the template engine with rulebook."""
        self.rulebook_path = rulebook_path
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Any]:
        """Load templates from YAML rulebook."""
        try:
            with open(self.rulebook_path, 'r') as f:
                rulebook = yaml.safe_load(f)
                # Check if rulebook has the expected template structure
                if "templates" in rulebook and "drivers" in rulebook.get("templates", {}):
                    return rulebook
                else:
                    logger.warning(f"Rulebook found but missing expected template structure, using enhanced default templates")
                    return self._get_default_templates()
        except FileNotFoundError:
            logger.warning(f"Rulebook not found at {self.rulebook_path}, using enhanced default templates")
            return self._get_default_templates()
    
    def _get_default_templates(self) -> Dict[str, Any]:
        """Get default templates when rulebook is not available."""
        return {
            "templates": {
                "drivers": {
                    "start": "High initial runner density in {segment_label} with {peak_concurrency} concurrent runners at peak",
                    "bridge": "Bridge segment {segment_label} experiences {peak_concurrency} concurrent runners with LOS {los_score}",
                    "turn": "Turn segment {segment_label} shows {peak_concurrency} concurrent runners during peak window",
                    "finish": "Finish approach {segment_label} with {peak_concurrency} concurrent runners and LOS {los_score}",
                    "trail": "Trail segment {segment_label} maintains {peak_concurrency} concurrent runners",
                    "default": "Segment {segment_label} shows {peak_concurrency} concurrent runners with peak areal density {peak_areal_density:.3f} runners/m²"
                },
                "mitigations": {
                    "start": "Deploy additional marshals at start area, implement wave starts if needed",
                    "bridge": "Ensure bridge capacity monitoring, maintain emergency access lanes",
                    "turn": "Place directional signage, deploy marshals at turn points",
                    "finish": "Prepare finish line resources, ensure medical support availability",
                    "trail": "Monitor trail conditions, ensure adequate marshaling",
                    "default": "Consider additional crowd management measures based on LOS {los_score} rating"
                }
            },
            "ops_insights": {
                "start": {
                    "access": "Maintain clear start area access for emergency vehicles",
                    "medical": "Position medical tent near start, ensure AED availability",
                    "traffic": "Coordinate with traffic management for start area road closures",
                    "peak": "Peak concurrency: {peak_concurrency} runners at {peak_window_clock[0]}–{peak_window_clock[1]}"
                },
                "bridge": {
                    "access": "Maintain emergency vehicle access across bridge",
                    "medical": "Ensure medical support at bridge entry/exit points",
                    "traffic": "Monitor bridge capacity, implement flow control if needed",
                    "peak": "Peak concurrency: {peak_concurrency} runners with LOS {los_score}"
                },
                "turn": {
                    "access": "Keep turn areas clear for emergency access",
                    "medical": "Position medical support near turn points",
                    "traffic": "Deploy marshals for directional guidance",
                    "peak": "Peak concurrency: {peak_concurrency} runners during turn execution"
                },
                "finish": {
                    "access": "Maintain finish line emergency access routes",
                    "medical": "Ensure medical tent and AED at finish line",
                    "traffic": "Coordinate finish area traffic flow",
                    "peak": "Peak concurrency: {peak_concurrency} runners approaching finish"
                },
                "trail": {
                    "access": "Maintain trail emergency access points",
                    "medical": "Ensure roving medical support on trail",
                    "traffic": "Monitor trail conditions and runner flow",
                    "peak": "Peak concurrency: {peak_concurrency} runners on trail"
                },
                "default": {
                    "access": "Maintain emergency access routes",
                    "medical": "Ensure medical support availability",
                    "traffic": "Monitor traffic flow and runner density",
                    "peak": "Peak concurrency: {peak_concurrency} runners"
                }
            }
        }
    
    def generate_drivers(self, context: TemplateContext) -> str:
        """Generate drivers narrative for a segment."""
        templates = self.templates.get("templates", {}).get("drivers", {})
        
        # Try to match by segment_type and flow_type
        key = f"{context.segment_type}_{context.flow_type}"
        if key in templates:
            template = templates[key]
        else:
            # Fall back to segment_type only
            if context.segment_type in templates:
                template = templates[context.segment_type]
            else:
                # Use default
                template = templates.get("default", "High runner density in {segment_label}")
        
        return self._interpolate_template(template, context)
    
    def generate_mitigations(self, context: TemplateContext) -> str:
        """Generate mitigations narrative for a segment."""
        templates = self.templates.get("templates", {}).get("mitigations", {})
        
        # Try to match by segment_type and flow_type
        key = f"{context.segment_type}_{context.flow_type}"
        if key in templates:
            template = templates[key]
        else:
            # Fall back to segment_type only
            if context.segment_type in templates:
                template = templates[context.segment_type]
            else:
                # Use default
                template = templates.get("default", "Consider additional crowd management measures")
        
        return self._interpolate_template(template, context)
    
    def generate_ops_insights(self, context: TemplateContext) -> Dict[str, str]:
        """Generate operational insights for a segment."""
        ops_templates = self.templates.get("ops_insights", {})
        
        # Try to match by segment_type
        if context.segment_type in ops_templates:
            template_dict = ops_templates[context.segment_type]
        else:
            # Use default
            template_dict = ops_templates.get("default", {})
        
        # Interpolate each template
        insights = {}
        for key, template in template_dict.items():
            insights[key] = self._interpolate_template(template, context)
        
        return insights
    
    def _interpolate_template(self, template: str, context: TemplateContext) -> str:
        """Interpolate template variables with context data."""
        try:
            # Convert context to dict for easier access
            context_dict = {
                'segment_id': context.segment_id,
                'segment_label': context.segment_label,
                'segment_type': context.segment_type,
                'flow_type': context.flow_type,
                'los_score': context.los_score,
                'peak_concurrency': context.peak_concurrency,
                'peak_areal_density': context.peak_areal_density,
                'peak_crowd_density': context.peak_crowd_density,
                'active_duration': context.active_duration,
                'peak_window_clock': context.peak_window_clock,
                'events_included': context.events_included
            }
            
            # Simple string formatting
            return template.format(**context_dict)
        except (KeyError, ValueError) as e:
            logger.warning(f"Template interpolation failed: {e}")
            return template  # Return original template if interpolation fails


def create_template_context(
    segment_id: str,
    segment_data: Dict[str, Any],
    segment_type: str = "default",
    flow_type: str = "default"
) -> TemplateContext:
    """Create template context from segment data."""
    
    # Extract data from segment
    summary = segment_data.get("summary", {})
    seg_label = segment_data.get("seg_label", "Unknown")
    events_included = segment_data.get("events_included", [])
    
    # Get LOS score (use peak areal density)
    peak_areal = getattr(summary, "active_peak_areal", 0.0)
    los_score = "A"  # Default
    if peak_areal >= 1.63:
        los_score = "F"
    elif peak_areal >= 1.08:
        los_score = "E"
    elif peak_areal >= 0.72:
        los_score = "D"
    elif peak_areal >= 0.43:
        los_score = "C"
    elif peak_areal >= 0.31:
        los_score = "B"
    
    # Get peak window (simplified for now)
    active_start = getattr(summary, "active_start", "N/A")
    active_end = getattr(summary, "active_end", "N/A")
    peak_window_clock = [active_start, active_end]
    
    return TemplateContext(
        segment_id=segment_id,
        segment_label=seg_label,
        segment_type=segment_type,
        flow_type=flow_type,
        los_score=los_score,
        peak_concurrency=getattr(summary, "active_peak_concurrency", 0),
        peak_areal_density=peak_areal,
        peak_crowd_density=getattr(summary, "active_peak_crowd", 0.0),
        active_duration=getattr(summary, "active_duration_s", 0),
        peak_window_clock=peak_window_clock,
        events_included=events_included
    )
