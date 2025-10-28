"""
Complexity Helper Utilities for Issue #390 - Phase 4

This module provides common patterns and utilities to help maintain
complexity standards and prevent fragile execution patterns.
"""

from typing import Any, Dict, List, Optional, Union, Callable
import logging
from functools import wraps

logger = logging.getLogger(__name__)


def safe_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a value from a dictionary with optional nested keys.
    
    Args:
        data: Dictionary to search
        key: Key to look for (supports dot notation for nested keys)
        default: Default value if key not found
        
    Returns:
        Value from dictionary or default
    """
    if not isinstance(data, dict):
        return default
    
    keys = key.split('.')
    current = data
    
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return default
        current = current[k]
    
    return current


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """
    Validate that required fields are present in data.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Raises:
        ValueError: If any required field is missing
    """
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")


def extract_event_intervals(event: str, config: Dict[str, Any]) -> Optional[tuple]:
    """
    Extract event intervals from configuration (utility from Phase 1).
    
    Args:
        event: Event name (Full, Half, 10K)
        config: Configuration dictionary
        
    Returns:
        Tuple of (from_km, to_km) or None if not found
    """
    if event == "Full":
        from_key, to_key = "full_from_km", "full_to_km"
    elif event == "Half":
        from_key, to_key = "half_from_km", "half_to_km"
    elif event == "10K":
        from_key, to_key = "tenk_from_km", "tenk_to_km"
    else:
        logger.warning(f"Unrecognized event: {event}")
        return None
    
    from_km = safe_get(config, from_key)
    to_km = safe_get(config, to_key)
    
    if from_km is None or to_km is None:
        logger.warning(f"Missing interval data for event {event}")
        return None
    
    return (from_km, to_km)


def detect_environment() -> tuple[bool, str]:
    """
    Detect the current environment (utility from Phase 3).
    
    Returns:
        Tuple of (is_cloud, environment_name)
    """
    import os
    
    is_cloud = bool(os.getenv('K_SERVICE') or os.getenv('GOOGLE_CLOUD_PROJECT'))
    environment = "Cloud Run" if is_cloud else "Local"
    return is_cloud, environment


def get_environment_info() -> str:
    """
    Get environment information for reports (utility from Phase 3).
    
    Returns:
        Environment description string
    """
    is_cloud, environment = detect_environment()
    
    if is_cloud:
        return "**Environment:** https://run-density-ln4r3sfkha-uc.a.run.app (Cloud Run Production)"
    else:
        return "**Environment:** http://localhost:8080 (Local Development)"


def create_converted_segment(segment: Dict[str, Any], event_a: str, event_b: str) -> Dict[str, Any]:
    """
    Create a converted segment with event-specific distance ranges (utility from Phase 3).
    
    Args:
        segment: Original segment data
        event_a: First event name
        event_b: Second event name
        
    Returns:
        Converted segment dictionary
    """
    def get_event_distance_range(event: str) -> tuple[float, float]:
        if event == "Full":
            return segment.get("full_from_km", 0), segment.get("full_to_km", 0)
        elif event == "Half":
            return segment.get("half_from_km", 0), segment.get("half_to_km", 0)
        elif event == "10K":
            return segment.get("10K_from_km", 0), segment.get("10K_to_km", 0)
        else:
            return 0, 0
    
    from_km_a, to_km_a = get_event_distance_range(event_a)
    from_km_b, to_km_b = get_event_distance_range(event_b)
    
    return {
        "seg_id": segment['seg_id'],
        "segment_label": segment.get("seg_label", ""),
        "eventa": event_a,
        "eventb": event_b,
        "from_km_a": from_km_a,
        "to_km_a": to_km_a,
        "from_km_b": from_km_b,
        "to_km_b": to_km_b,
        "direction": segment.get("direction", ""),
        "width_m": segment.get("width_m", 0),
        "overtake_flag": segment.get("overtake_flag", ""),
        "flow_type": segment.get("flow_type", ""),
        "length_km": segment.get("length_km", 0)
    }


def generate_flow_type_analysis(segment: Dict[str, Any], flow_type: str) -> List[str]:
    """
    Generate flow type specific analysis text (utility from Phase 3).
    
    Args:
        segment: Segment data
        flow_type: Type of flow (merge, diverge, overtake)
        
    Returns:
        List of analysis lines
    """
    analysis_lines = []
    
    if flow_type == "merge":
        analysis_lines.append(f"🔄 MERGE ANALYSIS:")
        analysis_lines.append(f"   • {segment['event_a']} runners in merge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
        analysis_lines.append(f"   • {segment['event_b']} runners in merge zone: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
    elif flow_type == "diverge":
        analysis_lines.append(f"↗️ DIVERGE ANALYSIS:")
        analysis_lines.append(f"   • {segment['event_a']} runners in diverge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
        analysis_lines.append(f"   • {segment['event_b']} runners in diverge zone: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
    else:  # overtake (default)
        analysis_lines.append(f"👥 OVERTAKE ANALYSIS:")
        analysis_lines.append(f"   • {segment['event_a']} runners overtaking: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
        analysis_lines.append(f"   • {segment['event_b']} runners overtaking: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
    
    # Common analysis for all flow types
    analysis_lines.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
    analysis_lines.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
    
    return analysis_lines


def complexity_monitor(func: Callable) -> Callable:
    """
    Decorator to monitor function complexity and log warnings.
    
    Args:
        func: Function to monitor
        
    Returns:
        Wrapped function with complexity monitoring
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Simple complexity monitoring - could be enhanced with actual metrics
        logger.debug(f"Executing {func.__name__} with complexity monitoring")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Successfully completed {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise
    
    return wrapper
