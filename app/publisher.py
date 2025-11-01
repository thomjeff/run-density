# Strict-First Publisher for Algorithm Consistency
# Ensures consistent publication rules across Main Analysis and Flow Runner

from dataclasses import dataclass
from typing import Optional, Tuple
from app.config_algo_consistency import FLAGS

@dataclass
class OvertakeCounts:
    strict_a: int
    strict_b: int
    raw_a: int
    raw_b: int

def apply_override_if_any(segment_key: str, counts: OvertakeCounts) -> Optional[Tuple[int, int]]:
    """
    Apply any segment-specific overrides (e.g., F1 validation).
    
    Args:
        segment_key: Segment identifier
        counts: Raw overtake counts
    
    Returns:
        (a, b) if override applies; else None
    """
    # F1 Half vs 10K special override comes from Main Analysis
    # This would be implemented based on the existing F1 validation logic
    return None

def publish_overtakes(segment_key: str, counts: OvertakeCounts) -> Tuple[int, int]:
    """
    Publish overtake counts using strict-first rule.
    
    Args:
        segment_key: Segment identifier
        counts: Overtake counts (strict and raw)
    
    Returns:
        (a, b) - the final published counts
    """
    if FLAGS.ENABLE_STRICT_FIRST_PUBLISH:
        # Strict-first rule: prefer strict passes, never fall back to raw when strict=0
        if counts.strict_a > 0 or counts.strict_b > 0:
            return (counts.strict_a, counts.strict_b)
        
        # Check for explicit overrides (e.g., F1 validation)
        override = apply_override_if_any(segment_key, counts)
        if override is not None:
            return override
        
        # Never fall back to raw when strict passes = 0
        return (0, 0)
    
    # Legacy behavior (avoid using; present for safety/backward compat)
    return (counts.raw_a, counts.raw_b)
