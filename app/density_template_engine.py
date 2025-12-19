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
    density_value: float  # runners per meter
    density_level: str    # high, medium, low


@dataclass
class Schema:
    """Schema definition for density analysis."""
    los_thresholds: dict
    flow_ref: dict | None
    debounce_bins: int = 2
    cooldown_bins: int = 3


@dataclass
class DebounceState:
    """State tracking for trigger debounce/cooldown."""
    hot_bins: int = 0
    cool_bins: int = 0
    active: bool = False

    def update(self, fired: bool, debounce_bins: int, cooldown_bins: int) -> bool:
        """Update debounce state and return whether trigger should fire."""
        if not self.active:
            self.hot_bins = self.hot_bins + 1 if fired else 0
            if self.hot_bins >= debounce_bins and fired:
                self.active = True
                self.cool_bins = 0
        else:
            self.cool_bins = self.cool_bins + 1 if not fired else 0
            if self.cool_bins >= cooldown_bins and not fired:
                self.active = False
                self.hot_bins = 0
        return self.active


def evaluate_triggers(segment_id: str, metrics: dict, schema_name: str, schema: Schema, rulebook: dict) -> List[str]:
    """Evaluate triggers for a segment and return fired actions."""
    fired_actions = []
    
    # Get triggers for this schema
    triggers = rulebook.get("triggers", [])
    schema_triggers = [t for t in triggers if t.get("when", {}).get("schema") == schema_name]
    
    for trigger in schema_triggers:
        when = trigger.get("when", {})
        actions = trigger.get("actions", [])
        
        # Check density trigger
        if "density_gte" in when:
            density_threshold = when["density_gte"]
            if isinstance(density_threshold, str):
                # Letter-based threshold (A-F)
                density_value = schema.los_thresholds.get(density_threshold, {}).get("min", 0.0)
            else:
                # Numeric threshold
                density_value = density_threshold
            
            # Ensure density_value is not None
            if density_value is None:
                density_value = 0.0
            
            density_metric = metrics.get("density", 0.0)
            if density_metric is not None and density_metric >= density_value:
                fired_actions.extend(actions)
        
        # Check flow trigger
        if "flow_gte" in when and schema.flow_ref:
            flow_threshold = when["flow_gte"]
            if isinstance(flow_threshold, str):
                # Named threshold (warn, critical)
                flow_value = schema.flow_ref.get(flow_threshold, 0.0)
            else:
                # Numeric threshold
                flow_value = flow_threshold
            
            # Ensure flow_value is not None
            if flow_value is None:
                flow_value = 0.0
            
            flow_metric = metrics.get("flow", 0.0)
            if flow_metric is not None and flow_metric >= flow_value:
                fired_actions.extend(actions)
    
    return fired_actions


def compute_flow_rate(runners_crossing: int, width_m: float, bin_seconds: int) -> float:
    """Compute flow rate in runners/min/m."""
    minutes = max(bin_seconds / 60.0, 1e-9)
    return runners_crossing / (width_m * minutes)  # runners/min/m


# Phase 3 cleanup: Removed map_los() - not imported or used anywhere


def resolve_schema(segment_id: str, segment_type: str, rulebook: dict) -> str:
    """Resolve which schema to use for a segment based on rulebook binding rules."""
    # Check explicit segment_id matches first
    for binding in rulebook.get("binding", []):
        when = binding.get("when", {})
        if when.get("segment_id") == segment_id:
            return binding.get("use_schema", "on_course_open")
    
    # Check segment_type matches
    for binding in rulebook.get("binding", []):
        when = binding.get("when", {})
        if segment_type in when.get("segment_type", []):
            return binding.get("use_schema", "on_course_open")
    
    # Default to on_course_open
    return "on_course_open"


def resolve_schema_with_flow_type(segment_id: str, flow_type: str, rulebook: dict) -> str:
    """Resolve schema using flow_type for segments that don't have segment_type."""
    # Check explicit segment_id matches first
    for binding in rulebook.get("binding", []):
        when = binding.get("when", {})
        if when.get("segment_id") == segment_id:
            return binding.get("use_schema", "on_course_open")
    
    # Map flow_type to appropriate schema
    if flow_type in ["merge", "parallel", "counterflow"]:
        return "on_course_narrow"
    elif flow_type in ["overtake"]:
        return "on_course_open"
    else:
        return "on_course_open"


def get_schema_config(schema_name: str, rulebook: dict) -> Schema:
    """Get schema configuration from rulebook."""
    schemas = rulebook.get("schemas", {})
    schema_config = schemas.get(schema_name, {})
    
    # Get LOS thresholds - use schema-specific or fall back to global
    los_thresholds = schema_config.get("los_thresholds", 
                                     rulebook.get("globals", {}).get("los_thresholds", {}))
    
    # Get flow reference values
    flow_ref = schema_config.get("flow_ref")
    
    return Schema(
        los_thresholds=los_thresholds,
        flow_ref=flow_ref,
        debounce_bins=schema_config.get("debounce_bins", 2),
        cooldown_bins=schema_config.get("cooldown_bins", 3)
    )


class DensityTemplateEngine:
    """Basic template engine for density report narratives."""
    
    def __init__(self, rulebook_path: str = "config/density_rulebook.yml"):
        """Initialize the template engine with rulebook."""
        self.rulebook_path = rulebook_path
        self.templates = self._load_templates()
        self.rulebook = self._load_rulebook()
        self.debounce_states = {}  # Track debounce state per segment
    
    def _load_rulebook(self) -> Dict[str, Any]:
        """Load rulebook from YAML file."""
        try:
            with open(self.rulebook_path, 'r') as f:
                rulebook = yaml.safe_load(f)
                # Version guard for v2 rulebook
                version = rulebook.get("meta", {}).get("version", "1.0")
                if not version.startswith("2"):
                    raise ValueError(f"Expected rulebook version 2.x, got {version}")
                
                # Check required keys
                required_keys = ["schemas", "binding", "triggers"]
                for key in required_keys:
                    if key not in rulebook:
                        raise ValueError(f"Missing required rulebook key: {key}")
                
                return rulebook
        except Exception as e:
            logger.error(f"Failed to load rulebook: {e}")
            raise

    def _load_templates(self) -> Dict[str, Any]:
        """Load templates from YAML rulebook."""
        try:
            with open(self.rulebook_path, 'r') as f:
                rulebook = yaml.safe_load(f)
                # Check if rulebook has the expected template structure
                if "templates" in rulebook and "drivers" in rulebook.get("templates", {}):
                    # Merge new rulebook structure with existing structure for compatibility
                    enhanced_rulebook = self._merge_rulebook_structures(rulebook)
                    return enhanced_rulebook
                else:
                    logger.warning(f"Rulebook found but missing expected template structure, using enhanced default templates")
                    return self._get_default_templates()
        except FileNotFoundError:
            logger.warning(f"Rulebook not found at {self.rulebook_path}, using enhanced default templates")
            return self._get_default_templates()
    
    def _merge_rulebook_structures(self, rulebook: Dict[str, Any]) -> Dict[str, Any]:
        """Merge new rulebook structure with existing structure for compatibility."""
        # Start with default templates as base
        merged = self._get_default_templates()
        
        # Add new rulebook data
        if "templates" in rulebook:
            templates = rulebook["templates"]
            
            # Add new driver templates
            if "drivers" in templates:
                new_drivers = templates["drivers"]
                # Convert new structure to old structure for compatibility
                for key, driver_data in new_drivers.items():
                    if isinstance(driver_data, dict) and "narrative_template" in driver_data:
                        merged["templates"]["drivers"][key] = driver_data["narrative_template"]
            
            # Add thresholds
            if "thresholds" in templates:
                merged["thresholds"] = templates["thresholds"]
            
            # Add safety templates
            if "safety" in templates:
                merged["safety"] = templates["safety"]
            
            # Add report sections
            if "report_sections" in templates:
                merged["report_sections"] = templates["report_sections"]
            
            # Add event-specific considerations
            if "events" in templates:
                merged["events"] = templates["events"]
        
        return merged
    
    def _classify_density_level(self, density_value: float) -> str:
        """Classify density level based on thresholds."""
        thresholds = self.templates.get("thresholds", {})
        high_threshold = thresholds.get("high_density", 0.5)
        medium_threshold = thresholds.get("medium_density", 0.2)
        
        if density_value >= high_threshold:
            return "high"
        elif density_value >= medium_threshold:
            return "medium"
        else:
            return "low"
    
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
        
        # Try density level specific templates first
        density_key = f"{context.density_level}_density"
        if density_key in templates:
            template = templates[density_key]
        # Try flow type specific templates
        elif f"{context.flow_type}_zone" in templates:
            template = templates[f"{context.flow_type}_zone"]
        # Try segment_type and flow_type combination
        elif f"{context.segment_type}_{context.flow_type}" in templates:
            template = templates[f"{context.segment_type}_{context.flow_type}"]
        # Fall back to segment_type only
        elif context.segment_type in templates:
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
    
    def generate_safety_warnings(self, context: TemplateContext) -> List[str]:
        """Generate safety warnings for a segment."""
        warnings = []
        safety_templates = self.templates.get("safety", {})
        
        # High density warning
        if context.density_level == "high" and "high_density_warning" in safety_templates:
            warning = self._interpolate_template(safety_templates["high_density_warning"], context)
            warnings.append(warning)
        
        # Flow control suggestion for high density
        if context.density_level == "high" and "flow_control_suggestion" in safety_templates:
            suggestion = self._interpolate_template(safety_templates["flow_control_suggestion"], context)
            warnings.append(suggestion)
        
        # Monitoring recommendation
        if context.density_level in ["high", "medium"] and "monitoring_recommendation" in safety_templates:
            recommendation = self._interpolate_template(safety_templates["monitoring_recommendation"], context)
            warnings.append(recommendation)
        
        return warnings
    
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
                'events_included': context.events_included,
                'density_value': context.density_value,
                'density_level': context.density_level
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
    
    # Calculate density value (runners per meter) - use peak crowd density as proxy
    peak_crowd = getattr(summary, "active_peak_crowd", 0.0)
    density_value = peak_crowd  # This is already runners per meter
    
    # Initialize template engine to get density level classification
    template_engine = DensityTemplateEngine()
    density_level = template_engine._classify_density_level(density_value)
    
    return TemplateContext(
        segment_id=segment_id,
        segment_label=seg_label,
        segment_type=segment_type,
        flow_type=flow_type,
        los_score=los_score,
        peak_concurrency=getattr(summary, "active_peak_concurrency", 0),
        peak_areal_density=peak_areal,
        peak_crowd_density=peak_crowd,
        active_duration=getattr(summary, "active_duration_s", 0),
        peak_window_clock=peak_window_clock,
        events_included=events_included,
        density_value=density_value,
        density_level=density_level
    )
