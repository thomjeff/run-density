# app/schema_resolver.py
"""
Schema resolver for segment-to-schema mapping.

Maps segment IDs to rulebook schema keys (start_corral, on_course_narrow, on_course_open).
This enables schema-specific thresholds for LOS and rate-based flagging.

Issue #254: Centralize Rulebook Logic
"""
from typing import Dict, Optional

# Explicit mapping for known segments
# Expand this as needed for operational hot spots
EXPLICIT: Dict[str, str] = {
    # Start corral (wide, managed release)
    "A1": "start_corral",
    
    # Narrow corridors (1.5m width, high congestion risk)
    "B1": "on_course_narrow",  # Friel to 10K Turn
    "B2": "on_course_narrow",  # 10K Turn to Friel
    "B3": "on_course_narrow",  # 10K Turn to Friel
    "D1": "on_course_narrow",  # 10K Turn to Full Turn Blake (Out)
    "D2": "on_course_narrow",  # Full Turn Blake to 10K Turn (Return)
    "H1": "on_course_narrow",  # Trail/Aberdeen to/from Station Rd
    "J1": "on_course_narrow",  # Bridge/Mill to Half Turn (Outbound)
    "J2": "on_course_narrow",  # Half Turn to Full Turn (Out)
    "J3": "on_course_narrow",  # Full Turn to Half Turn (Return)
    "J4": "on_course_narrow",  # Half Turn to Bridge/Mill
    "J5": "on_course_narrow",  # Half Turn to Bridge/Mill (Slow Half)
    "L1": "on_course_narrow",  # Trail/Aberdeen to/from Station Rd
    "L2": "on_course_narrow",  # Station Rd to Trail/Aberdeen
    
    # Open course (3.0-5.0m width, lower congestion risk)
    "A2": "on_course_open",  # Queen/Regent to WSB mid-point
    "A3": "on_course_open",  # WSB mid-point to Friel
    "F1": "on_course_open",  # Friel to Station Rd.
    "G1": "on_course_open",  # Full Loop around QS to Trail/Aberdeen
    "I1": "on_course_open",  # Station Rd to Bridge/Mill
    "K1": "on_course_open",  # Bridge/Mill to Station Rd
    "M1": "on_course_open",  # Trail/Aberdeen to Finish (Full to Loop)
    "M2": "on_course_open",  # Trail/Aberdeen to Finish
}

def resolve_schema(segment_id: str, segment_type: Optional[str] = None) -> str:
    """
    Resolve segment ID to rulebook schema key.
    
    Resolution order:
    1. Explicit ID mapping (EXPLICIT dict)
    2. Type-based mapping (if segment_type provided)
    3. Default to on_course_open
    
    Args:
        segment_id: Segment identifier (e.g., "A1", "B1")
        segment_type: Optional segment type from segments.csv
        
    Returns:
        Schema key: "start_corral", "on_course_narrow", or "on_course_open"
    """
    # 1) Explicit ID mapping (highest priority)
    if segment_id in EXPLICIT:
        return EXPLICIT[segment_id]
    
    # 2) Type-based mapping (when segment_type is present)
    if segment_type:
        t = segment_type.lower()
        
        # Narrow/constrained segments
        if t in {"funnel", "merge", "bridge", "chute", "finish", "narrow"}:
            return "on_course_narrow"
        
        # Start corrals
        if t in {"start", "corral"}:
            return "start_corral"
    
    # 3) Default to open course
    return "on_course_open"

def get_schema_stats() -> Dict[str, int]:
    """
    Get statistics on explicit schema mappings.
    
    Returns:
        Dict with counts per schema type
    """
    stats = {}
    for schema in EXPLICIT.values():
        stats[schema] = stats.get(schema, 0) + 1
    return stats

