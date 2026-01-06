"""
Temporal Flow Analysis Module

Handles temporal flow analysis for segments where overtaking or merging is possible.
Processes all segments and calculates convergence for segments with flow_type != 'none'.
Supports overtake, merge, and diverge flow types.

KEY CONCEPTS:
1. START TIMES: Must be offsets from midnight in minutes (e.g., 420 = 7:00 AM)
2. NORMALIZED DISTANCES: For segments with different absolute ranges (like F1), 
   we work in normalized space (0.0-1.0) to compare relative positions
3. CONVERGENCE vs FLOW_TYPE: Segments with flow_type != 'none' don't necessarily 
   need to show convergence if there are no temporal overlaps due to timing differences
4. TRUE PASS DETECTION: Only counts actual directional overtaking, not just co-presence
5. INTERSECTION BOUNDARIES: For directional change detection, use intersection 
   boundaries (same segment) rather than individual event boundaries (different segments)
"""

from __future__ import annotations
import time
import logging
import json
from typing import Dict, Optional, Any, List, Tuple, TYPE_CHECKING
from dataclasses import dataclass
import pandas as pd
import numpy as np

if TYPE_CHECKING:
    # Avoid circular import - bin_analysis imports flow, so we only import types for type hints
    from app.bin_analysis import SegmentBinData
from app.utils.constants import (
    SECONDS_PER_MINUTE, SECONDS_PER_HOUR,
    DEFAULT_CONVERGENCE_STEP_KM, DEFAULT_MIN_OVERLAP_DURATION, 
    DEFAULT_CONFLICT_LENGTH_METERS, TEMPORAL_OVERLAP_TOLERANCE_SECONDS,
    METERS_PER_KM, PACE_SIMILAR_THRESHOLD, PACE_MODERATE_DIFFERENCE_THRESHOLD,
    TEMPORAL_BINNING_THRESHOLD_MINUTES, SPATIAL_BINNING_THRESHOLD_METERS,
    SUSPICIOUS_OVERTAKING_RATE_THRESHOLD,
    MIN_NORMALIZED_FRACTION, MAX_NORMALIZED_FRACTION,
    FRACTION_CLAMP_REASON_OUTSIDE_RANGE, FRACTION_CLAMP_REASON_NEGATIVE,
    FRACTION_CLAMP_REASON_EXCEEDS_ONE, CONVERGENCE_POINT_TOLERANCE_KM,
    DISTANCE_BIN_SIZE_KM, DEFAULT_STEP_KM, DEFAULT_TOT_THRESHOLDS,
    DEFAULT_TIME_BIN_SECONDS, CONFLICT_LENGTH_LONG_SEGMENT_M
)
from app.utils.shared import load_pace_csv, arrival_time_sec, load_segments_csv


# Issue #612: Multi-CP data structures
@dataclass
class ConvergencePoint:
    """
    Represents a convergence point detected in a segment.
    
    Attributes:
        km: Kilometer mark of the convergence point (in event A coordinate system)
        type: Type of detection - "true_pass" or "bin_peak"
        overlap_count: Optional count of overlaps at this point (for bin_peak type)
    """
    km: float
    type: str  # "true_pass" or "bin_peak"
    overlap_count: Optional[int] = None


@dataclass
class ConflictZone:
    """
    Represents a conflict zone built from a convergence point.
    
    Attributes:
        cp: The convergence point that defines this zone
        zone_start_km_a: Start of zone in event A coordinates
        zone_end_km_a: End of zone in event A coordinates
        zone_start_km_b: Start of zone in event B coordinates
        zone_end_km_b: End of zone in event B coordinates
        zone_index: Index of this zone within the segment (0-based)
        source: Source identifier (e.g., "true_pass" or "bin_peak")
        metrics: Dictionary with zone-level metrics (overtakes_a, overtakes_b, etc.)
                 Initially empty, populated after zone analysis
    """
    cp: ConvergencePoint
    zone_start_km_a: float
    zone_end_km_a: float
    zone_start_km_b: float
    zone_end_km_b: float
    zone_index: int
    source: str
    metrics: Dict[str, Any]


def _get_event_distance_range(segment: pd.Series, event: str) -> Tuple[float, float]:
    """
    Extract distance range for a specific event from segment data.
    
    Issue #548 Bug 1: Use lowercase event names consistently to match CSV columns.
    
    Args:
        segment: Segment data row
        event: Event name (lowercase: 'full', 'half', '10k', 'elite', 'open')
        
    Returns:
        Tuple of (from_km, to_km) for the event
    """
    # Normalize to lowercase for consistent matching
    event_lower = event.lower()
    
    # Issue #553 Phase 4.2: Support hardcoded events for backward compatibility,
    # but add dynamic fallback for any event name
    if event_lower == "full":
        return segment.get("full_from_km", 0), segment.get("full_to_km", 0)
    elif event_lower == "half":
        return segment.get("half_from_km", 0), segment.get("half_to_km", 0)
    elif event_lower == "10k":
        # Issue #548 Bug 1: Use lowercase '10k' to match CSV column names
        return segment.get("10k_from_km", 0) or segment.get("10K_from_km", 0), segment.get("10k_to_km", 0) or segment.get("10K_to_km", 0)
    elif event_lower == "elite":
        return segment.get("elite_from_km", 0), segment.get("elite_to_km", 0)
    elif event_lower == "open":
        return segment.get("open_from_km", 0), segment.get("open_to_km", 0)
    else:
        # Issue #553 Phase 4.2: Dynamic lookup for any event name
        # Try dynamic lookup: {event}_from_km and {event}_to_km
        from_key = f"{event_lower}_from_km"
        to_key = f"{event_lower}_to_km"
        
        # Case-insensitive lookup
        from_val = segment.get(from_key) or segment.get(from_key.capitalize())
        to_val = segment.get(to_key) or segment.get(to_key.capitalize())
        
        if from_val is not None and to_val is not None:
            return from_val, to_val
        
        # If not found, return 0, 0 (segment not used by this event)
        return 0, 0


def _get_segment_events(segment: pd.Series) -> List[str]:
    """
    Extract list of events present in a segment.
    
    Issue #548 Bug 1: Use lowercase event names consistently to match CSV columns.
    
    Args:
        segment: Segment data row
        
    Returns:
        List of lowercase event names present in the segment ('full', 'half', '10k', 'elite', 'open')
    """
    events = []
    # Issue #548 Bug 1: Check lowercase column names to match CSV format
    if segment.get('full') == 'y':
        events.append('full')
    if segment.get('half') == 'y':
        events.append('half')
    if segment.get('10k') == 'y' or segment.get('10K') == 'y':  # Handle both cases for backward compatibility
        events.append('10k')
    if segment.get('elite') == 'y':
        events.append('elite')
    if segment.get('open') == 'y':
        events.append('open')
    return events


def _create_converted_segment(segment: pd.Series, event_a: str, event_b: str) -> Dict[str, Any]:
    """
    Create a converted segment with event-specific distance ranges.
    
    Args:
        segment: Original segment data row
        event_a: First event name
        event_b: Second event name
        
    Returns:
        Dictionary with converted segment data
    """
    from_km_a, to_km_a = _get_event_distance_range(segment, event_a)
    from_km_b, to_km_b = _get_event_distance_range(segment, event_b)
    
    return {
        "seg_id": segment['seg_id'],
        "segment_label": segment.get("seg_label", ""),
        "eventa": event_a,
        "eventb": event_b,
        "from_km_a": from_km_a,
        "to_km_a": to_km_a,
        "from_km_b": from_km_b,
        "to_km_b": to_km_b,
        "direction": segment.get("direction", ""),  # Issue #549: Physical property from segments.csv
        "width_m": segment.get("width_m", 0),  # Issue #549: Physical property from segments.csv
        "flow_type": segment.get("flow_type", ""),  # Issue #549: Flow-specific metadata
        "length_km": segment.get("length_km", 0)
    }
    """
    Log structured flow segment statistics for debugging.
    
    Args:
        seg_id: Segment identifier
        event_a: Event A name
        event_b: Event B name  
        path: Algorithm path used ("ORIGINAL", "BINNED_TIME", "BINNED_DISTANCE")
        counters: Dictionary with performance counters
    """
    logging.info(json.dumps({
        "component": "flow",
        "seg_id": seg_id,
        "event_a": event_a,
        "event_b": event_b,
        "path": path,
        **counters
    }))


def get_flow_terminology(flow_type: str) -> Dict[str, str]:
    """
    Get appropriate terminology based on flow type.
    
    Args:
        flow_type: The flow type (overtake, counterflow, merge, diverge, none)
        
    Returns:
        Dictionary with terminology for different contexts
    """
    if flow_type == "counterflow":
        return {
            "action": "interactions",
            "action_singular": "interaction", 
            "description": "runners from opposite directions interacting",
            "verb": "interact",
            "past_verb": "interacted",
            "sample_label": "Sample Runners (Interactions)",
            "count_label": "Interactions"
        }
    elif flow_type == "merge":
        return {
            "action": "merges",
            "action_singular": "merge",
            "description": "runners merging from different directions", 
            "verb": "merge",
            "past_verb": "merged",
            "sample_label": "Sample Runners (Merges)",
            "count_label": "Merges"
        }
    elif flow_type == "diverge":
        return {
            "action": "diverges", 
            "action_singular": "diverge",
            "description": "runners diverging to different directions",
            "verb": "diverge", 
            "past_verb": "diverged",
            "sample_label": "Sample Runners (Diverges)",
            "count_label": "Diverges"
        }
    else:  # overtake, none, or other
        return {
            "action": "overtaking",
            "action_singular": "overtake",
            "description": "runners overtaking in same direction",
            "verb": "overtake", 
            "past_verb": "overtook",
            "sample_label": "Sample Runners (Overtaking)",
            "count_label": "Overtaking"
        }


def clamp_normalized_fraction(fraction: float, reason_prefix: str = "") -> Tuple[float, Optional[str]]:
    """
    Clamp a normalized fraction to [0, 1] range and return reason code if clamped.
    
    Args:
        fraction: The fraction to clamp
        reason_prefix: Optional prefix for reason code
        
    Returns:
        Tuple of (clamped_fraction, reason_code)
        - reason_code is None if no clamping was needed
        - reason_code indicates why clamping occurred
    """
    if fraction < MIN_NORMALIZED_FRACTION:
        clamped = MIN_NORMALIZED_FRACTION
        reason = f"{reason_prefix}{FRACTION_CLAMP_REASON_NEGATIVE}" if reason_prefix else FRACTION_CLAMP_REASON_NEGATIVE
        return clamped, reason
    elif fraction > MAX_NORMALIZED_FRACTION:
        clamped = MAX_NORMALIZED_FRACTION
        reason = f"{reason_prefix}{FRACTION_CLAMP_REASON_EXCEEDS_ONE}" if reason_prefix else FRACTION_CLAMP_REASON_EXCEEDS_ONE
        return clamped, reason
    else:
        return fraction, None


# Use shared utility function from utils module


# Use shared utility function from utils module


# Use shared utility function from utils module


def _collect_all_true_pass_points(
    dfA: pd.DataFrame,
    dfB: pd.DataFrame,
    eventA: str,
    eventB: str,
    start_times: Dict[str, float],
    from_km: float,
    to_km: float,
    step_km: float,
) -> List[float]:
    """
    Collect all true-pass convergence points in a segment range.
    
    Issue #612: Scans the entire segment to collect ALL true-pass locations,
    not just the first one. This enables multi-CP detection.
    
    Args:
        dfA: DataFrame with runners from event A
        dfB: DataFrame with runners from event B
        eventA: Event A name
        eventB: Event B name
        start_times: Dictionary mapping event names to start times (minutes from midnight)
        from_km: Start of segment range to scan
        to_km: End of segment range to scan
        step_km: Step size for scanning (km)
        
    Returns:
        List of km points where true passes occur (may be empty)
    """
    if dfA.empty or dfB.empty:
        return []
    
    from app.utils.constants import TRUE_PASS_DETECTION_TOLERANCE_SECONDS
    
    # Get absolute start times in seconds
    start_a = start_times.get(eventA, 0) * 60.0
    start_b = start_times.get(eventB, 0) * 60.0
    
    # Create distance check points along the segment
    check_points = []
    current_km = from_km
    while current_km <= to_km:
        check_points.append(current_km)
        current_km += step_km
    
    true_pass_points = []
    tolerance_seconds = TRUE_PASS_DETECTION_TOLERANCE_SECONDS
    
    # For each check point, detect true passes
    for km_point in check_points:
        # Calculate arrival times for all runners at this point
        pace_a = dfA["pace"].values * 60.0  # sec per km
        offset_a = dfA.get("start_offset", pd.Series([0]*len(dfA))).fillna(0).values.astype(float)
        arrival_times_a = start_a + offset_a + pace_a * km_point
        
        pace_b = dfB["pace"].values * 60.0  # sec per km
        offset_b = dfB.get("start_offset", pd.Series([0]*len(dfB))).fillna(0).values.astype(float)
        arrival_times_b = start_b + offset_b + pace_b * km_point
        
        # Calculate arrival times at segment start (from_km)
        arrival_start_a = start_a + offset_a + pace_a * from_km
        arrival_start_b = start_b + offset_b + pace_b * from_km
        
        # Calculate arrival times at segment end (to_km)
        arrival_end_a = start_a + offset_a + pace_a * to_km
        arrival_end_b = start_b + offset_b + pace_b * to_km
        
        # Vectorized true pass detection using NumPy broadcasting
        # Check for temporal overlap
        time_diff = np.abs(arrival_times_a[:, np.newaxis] - arrival_times_b[np.newaxis, :])
        temporal_overlaps = time_diff <= tolerance_seconds
        
        if not np.any(temporal_overlaps):
            continue  # No temporal overlap at this km_point, skip to next
        
        # For pairs with temporal overlap, check directional passes
        start_a_2d = arrival_start_a[:, np.newaxis]  # (n, 1)
        start_b_2d = arrival_start_b[np.newaxis, :]  # (1, m)
        end_a_2d = arrival_end_a[:, np.newaxis]      # (n, 1)
        end_b_2d = arrival_end_b[np.newaxis, :]      # (1, m)
        
        # Check for pass A -> B (A overtakes B): A starts behind B but finishes ahead of B
        pass_a_b = (start_a_2d > start_b_2d) & (end_a_2d < end_b_2d)
        
        # Check for pass B -> A (B overtakes A): B starts behind A but finishes ahead of A
        pass_b_a = (start_b_2d > start_a_2d) & (end_b_2d < end_a_2d)
        
        # Check for convergence: runners meet at same time at both boundaries
        start_convergence = np.abs(start_a_2d - start_b_2d) <= tolerance_seconds
        end_convergence = np.abs(end_a_2d - end_b_2d) <= tolerance_seconds
        convergence = start_convergence & end_convergence
        
        # Check for runners running together (close in time and space)
        start_close = np.abs(start_a_2d - start_b_2d) <= tolerance_seconds * 2
        end_close = np.abs(end_a_2d - end_b_2d) <= tolerance_seconds * 2
        running_together = start_close & end_close
        
        # Combine all conditions: temporal overlap AND (pass OR convergence OR running together)
        true_pass_mask = temporal_overlaps & (pass_a_b | pass_b_a | convergence | running_together)
        
        if np.any(true_pass_mask):
            true_pass_points.append(float(km_point))
    
    return true_pass_points


def _extract_bin_peak_convergence_points(
    bin_data: "SegmentBinData",
    from_km_a: float,
    to_km_a: float,
) -> List[ConvergencePoint]:
    """
    Extract convergence points from bin data based on RSI peaks.
    
    Issue #612 Task 2: Uses bins where convergence_point == True (RSI > 0.1 threshold)
    to identify potential convergence points.
    
    Args:
        bin_data: SegmentBinData with bin-level analysis results
        from_km_a: Start of segment for event A (for filtering bins within segment)
        to_km_a: End of segment for event A (for filtering bins within segment)
        
    Returns:
        List of ConvergencePoint objects with type="bin_peak"
    """
    bin_peak_cps = []
    
    if not bin_data or not bin_data.bins:
        return bin_peak_cps
    
    for bin_obj in bin_data.bins:
        # Only consider bins marked as convergence points (RSI > 0.1)
        if not bin_obj.convergence_point:
            continue
        
        # Use bin center as the convergence point location
        bin_center_km = (bin_obj.start_km + bin_obj.end_km) / 2.0
        
        # Filter to bins within the segment range (event A coordinates)
        if from_km_a <= bin_center_km <= to_km_a:
            # Use overlap_count (total overtakes + co-presence) if available
            total_overlaps = sum(bin_obj.overtakes.values()) + sum(bin_obj.co_presence.values())
            bin_peak_cps.append(
                ConvergencePoint(
                    km=bin_center_km,
                    type="bin_peak",
                    overlap_count=total_overlaps if total_overlaps > 0 else None
                )
            )
    
    return bin_peak_cps


def calculate_convergence_points(
    dfA: pd.DataFrame,
    dfB: pd.DataFrame,
    eventA: str,
    eventB: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    step_km: float = DEFAULT_CONVERGENCE_STEP_KM,
    bin_data: Optional["SegmentBinData"] = None,
) -> List[ConvergencePoint]:
    """
    Calculate convergence points using TRUE PASS DETECTION and BIN PEAKS.
    
    Issue #612: Replaces single CP detection with multi-CP detection.
    Scans the entire segment to collect ALL true-pass locations.
    Optionally merges with bin-peak CPs from bin analysis.
    
    This function detects when runners from one event actually pass runners
    from another event (directional overtaking), not just co-presence.
    
    A true pass occurs when:
    1. Runner A arrives at km_point at time T_A
    2. Runner B arrives at km_point at time T_B  
    3. |T_A - T_B| <= tolerance
    4. AND one runner was behind the other at from_km but ahead at to_km
    
    Bin-peak CPs are extracted from bin analysis results (bins with RSI > 0.1).
    
    ALGORITHM APPROACH:
    - If events have absolute intersection (like L1): Use intersection-based approach
    - If events have no intersection (like F1): Use normalized approach with fine grid
    - Normalized approach maps relative positions (0.0-1.0) to absolute coordinates
      for pace calculations, then checks for temporal overlap
    - Merge true-pass CPs with bin-peak CPs (if bin_data provided)
    
    Args:
        bin_data: Optional SegmentBinData from bin analysis. If provided, extracts
                  bin-peak CPs (bins with convergence_point == True) and merges with true-pass CPs.
    
    Returns:
        List of ConvergencePoint objects (may be empty), merged from true-pass and bin-peak sources
    """
    # Step 1: Collect true-pass convergence points
    true_pass_cps = []
    
    # Check if there's an intersection in absolute space first
    intersection_start = max(from_km_a, from_km_b)
    intersection_end = min(to_km_a, to_km_b)
    
    if intersection_start < intersection_end:
        # There is an intersection - use normal approach with true pass detection
        true_pass_points = _collect_all_true_pass_points(
            dfA, dfB, eventA, eventB, start_times,
            intersection_start, intersection_end, step_km
        )
        
        # Convert to ConvergencePoint objects
        true_pass_cps = [
            ConvergencePoint(km=km_point, type="true_pass")
            for km_point in true_pass_points
        ]
    else:
        # No intersection in absolute space - need normalized approach for segments like F1
        # NORMALIZED DISTANCE APPROACH: For segments with different absolute ranges but same
        # relative positions (e.g., F1: Full 16.35-18.65km, Half 2.7-5.0km, 10K 5.8-8.1km),
        # we work in normalized space (0.0-1.0) to compare relative positions within each segment.
        # Calculate segment lengths
        len_a = to_km_a - from_km_a
        len_b = to_km_b - from_km_b
        
        if len_a > 0 and len_b > 0:
            # Use a finer grid of normalized positions
            normalized_points = np.linspace(0.0, 1.0, 21)  # 0.0, 0.05, 0.1, ..., 1.0
            
            for norm_point in normalized_points:
                # Map normalized point to absolute coordinates for each event
                abs_km_a = from_km_a + (norm_point * len_a)
                abs_km_b = from_km_b + (norm_point * len_b)
                
                # Use a temporary "intersection" range around this point
                tolerance_km = CONVERGENCE_POINT_TOLERANCE_KM  # 100m tolerance around the point
                range_start = max(from_km_a, abs_km_a - tolerance_km)  # Ensure within segment bounds
                range_end = min(to_km_a, abs_km_a + tolerance_km)      # Ensure within segment bounds
                
                # Collect true pass points in this range
                true_pass_points = _collect_all_true_pass_points(
                    dfA, dfB, eventA, eventB, start_times,
                    range_start, range_end, step_km
                )
                
                # Add to convergence points list (using event A coordinate)
                for km_point in true_pass_points:
                    true_pass_cps.append(ConvergencePoint(km=km_point, type="true_pass"))
    
    # Step 2: Extract bin-peak convergence points (if bin_data provided)
    bin_peak_cps = []
    if bin_data is not None:
        bin_peak_cps = _extract_bin_peak_convergence_points(bin_data, from_km_a, to_km_a)
    
    # Step 3: Merge true-pass and bin-peak CPs
    all_cps = true_pass_cps + bin_peak_cps
    
    # Step 4: Remove duplicates and sort by km (deduplicate within tolerance)
    convergence_points = []
    if all_cps:
        unique_points = []
        seen_km = set()
        tolerance_km = CONVERGENCE_POINT_TOLERANCE_KM
        
        for cp in sorted(all_cps, key=lambda x: x.km):
            # Check if this km is close to any we've already seen
            is_duplicate = False
            for seen in seen_km:
                if abs(cp.km - seen) < tolerance_km:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_points.append(cp)
                seen_km.add(cp.km)
        
        convergence_points = unique_points
    
    return convergence_points


def build_conflict_zones(
    convergence_points: List[ConvergencePoint],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
) -> List[ConflictZone]:
    """
    Build non-overlapping conflict zones from convergence points.
    
    Issue #612: Creates zones from CPs with non-overlapping enforcement.
    Zones are built in order from start to end of segment, and scanning
    resumes after each zone's end boundary.
    
    Args:
        convergence_points: List of ConvergencePoint objects (should be sorted by km)
        from_km_a: Start of segment for event A (km)
        to_km_a: End of segment for event A (km)
        from_km_b: Start of segment for event B (km)
        to_km_b: End of segment for event B (km)
        conflict_length_m: Conflict zone length in meters
        
    Returns:
        List of ConflictZone objects (non-overlapping, ordered by zone_start_km_a)
    """
    if not convergence_points:
        return []
    
    # Sort CPs by km to process from start to end
    sorted_cps = sorted(convergence_points, key=lambda cp: cp.km)
    
    zones = []
    cursor_km = from_km_a  # Track position in segment, resume scanning after zone ends
    
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    
    if len_a <= 0 or len_b <= 0:
        return []
    
    for cp in sorted_cps:
        cp_km = cp.km
        
        # Skip CPs before cursor (already processed or covered)
        if cp_km < cursor_km:
            continue
        
        # Check if CP falls within an existing zone (if so, ignore it - already covered)
        cp_in_existing_zone = False
        for existing_zone in zones:
            if (existing_zone.zone_start_km_a <= cp_km <= existing_zone.zone_end_km_a):
                cp_in_existing_zone = True
                break
        
        if cp_in_existing_zone:
            continue  # Skip this CP - it's already covered by an existing zone
        
        # Build zone from this CP
        # Use the same logic as _calculate_conflict_zone_boundaries but convert to absolute coordinates
        if from_km_a <= cp_km <= to_km_a:
            # Convergence point within Event A's range - use absolute approach
            s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
            s_cp, _ = clamp_normalized_fraction(s_cp, "convergence_point_")
            
            # Proportional tolerance: 5% of shorter segment, minimum 50m
            min_segment_len = min(len_a, len_b)
            proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)
            s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
            
            # Define normalized conflict zone boundaries
            s_start = max(0.0, s_cp - s_conflict_half)
            s_end = min(1.0, s_cp + s_conflict_half)
            
            # Ensure conflict zone has some width
            if s_end <= s_start:
                s_start = max(0.0, s_cp - 0.05)
                s_end = min(1.0, s_cp + 0.05)
        else:
            # Convergence point outside Event A's range - use normalized approach
            intersection_start = max(from_km_a, from_km_b)
            intersection_end = min(to_km_a, to_km_b)
            
            if intersection_start < intersection_end:
                # Use intersection boundaries
                intersection_start_norm = (intersection_start - from_km_a) / len_a
                intersection_end_norm = (intersection_end - from_km_a) / len_a
                conflict_length_km = conflict_length_m / 1000.0
                conflict_half_km = conflict_length_km / 2.0 / len_a
                s_start = max(0.0, intersection_start_norm - conflict_half_km)
                s_end = min(1.0, intersection_end_norm + conflict_half_km)
            else:
                # Use segment center
                center_a_norm = 0.5
                conflict_length_km = conflict_length_m / 1000.0
                conflict_half_km = conflict_length_km / 2.0 / len_a
                s_start = max(0.0, center_a_norm - conflict_half_km)
                s_end = min(1.0, center_a_norm + conflict_half_km)
        
        # Convert normalized boundaries to absolute coordinates
        zone_start_km_a = from_km_a + s_start * len_a
        zone_end_km_a = from_km_a + s_end * len_a
        zone_start_km_b = from_km_b + s_start * len_b
        zone_end_km_b = from_km_b + s_end * len_b
        
        # Clamp to segment boundaries
        zone_start_km_a = max(from_km_a, zone_start_km_a)
        zone_end_km_a = min(to_km_a, zone_end_km_a)
        zone_start_km_b = max(from_km_b, zone_start_km_b)
        zone_end_km_b = min(to_km_b, zone_end_km_b)
        
        # Create ConflictZone object
        zone = ConflictZone(
            cp=cp,
            zone_start_km_a=zone_start_km_a,
            zone_end_km_a=zone_end_km_a,
            zone_start_km_b=zone_start_km_b,
            zone_end_km_b=zone_end_km_b,
            zone_index=len(zones),  # 0-based index
            source=cp.type,  # "true_pass" or "bin_peak"
            metrics={}  # Will be populated later when zone metrics are calculated
        )
        
        zones.append(zone)
        
        # Resume scanning after this zone's end (enforce non-overlapping)
        cursor_km = zone_end_km_a
    
    return zones


def calculate_zone_metrics(
    zone: ConflictZone,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float,
    conflict_length_m: float,
    overlap_duration_minutes: float,
) -> Dict[str, Any]:
    """
    Calculate metrics for a single conflict zone.
    
    Issue #612: Uses calculate_convergence_zone_overlaps_with_binning to compute
    zone-level metrics (overtakes, copresence, etc.).
    
    Note: The function recalculates zone boundaries from cp_km internally,
    which should match the zone boundaries computed by build_conflict_zones.
    
    Args:
        zone: ConflictZone object with zone boundaries
        df_a: DataFrame of runners for event A
        df_b: DataFrame of runners for event B
        event_a: Event A name
        event_b: Event B name
        start_times: Event start times dictionary
        from_km_a: Start of segment for event A
        to_km_a: End of segment for event A
        from_km_b: Start of segment for event B
        to_km_b: End of segment for event B
        min_overlap_duration: Minimum overlap duration threshold
        conflict_length_m: Conflict length in meters
        overlap_duration_minutes: Overlap duration in minutes
        
    Returns:
        Dictionary with zone metrics (overtaking_a, overtaking_b, copresence_a, etc.)
    """
    # Use the zone's CP km location
    cp_km = zone.cp.km
    
    # Calculate metrics for this zone
    # Function recalculates zone boundaries from cp_km internally
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps_with_binning(
        df_a, df_b, event_a, event_b, start_times,
        cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
        min_overlap_duration, conflict_length_m, overlap_duration_minutes
    )
    
    return {
        "overtaking_a": overtakes_a,
        "overtaking_b": overtakes_b,
        "copresence_a": copresence_a,
        "copresence_b": copresence_b,
        "sample_a": bibs_a[:10],
        "sample_b": bibs_b[:10],
        "unique_encounters": unique_encounters,
        "participants_involved": participants_involved,
    }


def select_worst_zone(zones: List[ConflictZone]) -> Optional[ConflictZone]:
    """
    Select the "worst" zone based on metrics.
    
    Issue #612: Worst zone selection criteria (in order):
    1. Maximum total overtakes (overtaking_a + overtaking_b)
    2. Tie-breaker: Maximum total copresence (copresence_a + copresence_b)
    3. Tie-breaker: Earliest by distance (zone.cp.km)
    
    Args:
        zones: List of ConflictZone objects with populated metrics
        
    Returns:
        The worst ConflictZone, or None if zones list is empty
    """
    if not zones:
        return None
    
    def worst_zone_key(zone: ConflictZone) -> Tuple[int, int, float]:
        """Key function for sorting: (negative overtakes, negative copresence, km)"""
        metrics = zone.metrics
        total_overtakes = metrics.get("overtaking_a", 0) + metrics.get("overtaking_b", 0)
        total_copresence = metrics.get("copresence_a", 0) + metrics.get("copresence_b", 0)
        # Use negative values for descending sort (worst first)
        return (-total_overtakes, -total_copresence, zone.cp.km)
    
    # Sort by worst key and return first (worst) zone
    worst_zone = min(zones, key=worst_zone_key)
    return worst_zone


def calculate_entry_exit_times(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
) -> Tuple[str, str, str, str, str]:
    """Calculate first entry and last exit times for both events in the segment, plus overlap window duration."""
    if df_a.empty or df_b.empty:
        return "N/A", "N/A", "N/A", "N/A", "N/A"
    
    # Get start times in seconds
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate entry/exit times for event A
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    entry_times_a = start_a + offset_a + pace_a * from_km_a
    exit_times_a = start_a + offset_a + pace_a * to_km_a
    
    # Calculate entry/exit times for event B
    pace_b = df_b["pace"].values * 60.0  # sec per km
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    entry_times_b = start_b + offset_b + pace_b * from_km_b
    exit_times_b = start_b + offset_b + pace_b * to_km_b
    
    # Find first entry and last exit for each event
    first_entry_a = min(entry_times_a)
    last_exit_a = max(exit_times_a)
    first_entry_b = min(entry_times_b)
    last_exit_b = max(exit_times_b)
    
    # Calculate overlap window duration (time when both events have runners in segment)
    overlap_start = max(first_entry_a, first_entry_b)
    overlap_end = min(last_exit_a, last_exit_b)
    overlap_duration_seconds = max(0, overlap_end - overlap_start)
    
    # Format as HH:MM:SS
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    # Format duration as MM:SS or HH:MM:SS
    def format_duration(seconds):
        if seconds < 3600:  # Less than 1 hour
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        else:  # 1 hour or more
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    return (
        format_time(first_entry_a),
        format_time(last_exit_a),
        format_time(first_entry_b),
        format_time(last_exit_b),
        format_duration(overlap_duration_seconds)
    )


def calculate_convergence_zone_overlaps_with_binning(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    overlap_duration_minutes: float = 0.0,
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """
    Calculate overtaking with binning for long segments.
    Uses unified selector for consistent path selection across Main Analysis and Flow Runner.
    """
    
    # Import unified selector modules
    from app.normalization import normalize
    from app.selector import choose_path
    from app.telemetry import pub_decision_log
    from app.config_algo_consistency import FLAGS
    
    # Create segment key for unified selector
    segment_key = f"{event_a}_vs_{event_b}"  # Will be enhanced with segment ID later
    
    if FLAGS.ENABLE_BIN_SELECTOR_UNIFICATION:
        # Use unified selector logic (normalization hoisted out of inner loops)
        # Normalize inputs once per segment to prevent threshold drift
        norm_inputs = normalize(conflict_length_m, "m", overlap_duration_minutes * 60, "s")
        
        # Use unified selector to choose calculation path
        chosen_path = choose_path(segment_key, norm_inputs)
        
        # Map unified path to legacy binning flags
        use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
        use_distance_bins = chosen_path == "BINNED"
    else:
        # Use legacy binning logic
        use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
        use_distance_bins = conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
        chosen_path = "BINNED" if (use_time_bins or use_distance_bins) else "ORIGINAL"
        norm_inputs = None
    
    # Debug logging for M1 (sampled to avoid hot-loop overhead)
    if event_a == "Half" and event_b == "10K" and hash(segment_key) % 100 == 0:  # 1% sampling
        print(f"🔍 BINNING DECISION DEBUG:")
        print(f"  Segment key: {segment_key}")
        if norm_inputs is not None:
            print(f"  Normalized conflict length: {norm_inputs.conflict_len_m:.3f} m")
            print(f"  Normalized overlap duration: {norm_inputs.overlap_dur_s:.3f} s")
        else:
            print(f"  Raw conflict length: {conflict_length_m:.3f} m")
            print(f"  Raw overlap duration: {overlap_duration_minutes:.3f} min")
        print(f"  Chosen path: {chosen_path}")
        print(f"  Legacy time bins: {use_time_bins}")
        print(f"  Legacy distance bins: {use_distance_bins}")
        print(f"  Will use: {chosen_path} calculation")
    
    # Calculate results using chosen path
    if use_time_bins or use_distance_bins:
        # Log binning decision for transparency
        logging.info(f"BINNING APPLIED: time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                    f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
        
        results = calculate_convergence_zone_overlaps_binned(
            df_a, df_b, event_a, event_b, start_times,
            cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
            min_overlap_duration, conflict_length_m,
            use_time_bins, use_distance_bins, overlap_duration_minutes
        )
    else:
        # Use original method for short segments
        logging.debug(f"BINNING NOT APPLIED: time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                     f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
        
        results = calculate_convergence_zone_overlaps_original(
            df_a, df_b, event_a, event_b, start_times,
            cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
            min_overlap_duration, conflict_length_m
        )
    
    # Extract results for telemetry
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = results
    
    # Add telemetry logging for algorithm consistency verification (sampled)
    if event_a == "Half" and event_b == "10K" and hash(segment_key) % 100 == 0:  # 1% sampling
        if norm_inputs is not None:
            telemetry_log = pub_decision_log(
                segment_key, chosen_path, norm_inputs.conflict_len_m, norm_inputs.overlap_dur_s,
                (overtakes_a, overtakes_b), (overtakes_a, overtakes_b)  # Using same for strict/raw for now
            )
            print(f"🔍 {telemetry_log}")
        else:
            print(f"🔍 LEGACY BINNING: {chosen_path} -> {overtakes_a}/{overtakes_b}")
    
    return results


def generate_flow_audit_data(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = CONFLICT_LENGTH_LONG_SEGMENT_M,
    convergence_zone_start: float = None,
    convergence_zone_end: float = None,
    spatial_zone_exists: bool = False,
    temporal_overlap_exists: bool = False,
    true_pass_exists: bool = False,
    has_convergence_policy: bool = False,
    no_pass_reason_code: str = None,
    copresence_a: int = 0,
    copresence_b: int = 0,
    overtakes_a: int = 0,
    overtakes_b: int = 0,
    total_a: int = 0,
    total_b: int = 0,
    zone_index: Optional[int] = None,
    cp_km: Optional[float] = None,
    zone_source: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate comprehensive Flow Audit data for diagnostic analysis.
    
    This function provides fine-grained instrumentation for segments where
    overtaking percentages may appear inflated, ambiguous, or suspicious.
    
    Returns all 33 columns as specified in Flow_Audit_Spec.md
    """
    import numpy as np
    from datetime import datetime, timedelta
    
    # Initialize audit data with basic identifiers
    audit_data = {
        "seg_id": "",
        "segment_label": "",
        "event_a": event_a,
        "event_b": event_b,
        "spatial_zone_exists": spatial_zone_exists,
        "temporal_overlap_exists": temporal_overlap_exists,
        "true_pass_exists": true_pass_exists,
        "has_convergence_policy": has_convergence_policy,
        "no_pass_reason_code": no_pass_reason_code or "",
        "convergence_zone_start": convergence_zone_start,
        "convergence_zone_end": convergence_zone_end,
        "conflict_length_m": conflict_length_m,
        "copresence_a": copresence_a,
        "copresence_b": copresence_b,
        "density_ratio": 0.0,
        "median_entry_diff_sec": 0.0,
        "median_exit_diff_sec": 0.0,
        "avg_overlap_dwell_sec": 0.0,
        "max_overlap_dwell_sec": 0.0,
        "overlap_window_sec": 0.0,
        "passes_a": overtakes_a,
        "passes_b": overtakes_b,
        "multipass_bibs_a": "",
        "multipass_bibs_b": "",
        "pct_overtake_raw_a": 0.0,
        "pct_overtake_raw_b": 0.0,
        "pct_overtake_strict_a": 0.0,
        "pct_overtake_strict_b": 0.0,
        "time_bins_used": False,
        "distance_bins_used": False,
        "dedup_passes_applied": False,
        "reason_codes": "",
        "audit_trigger": "",
        # Issue #612: Multi-zone fields
        "zone_index": zone_index,
        "cp_km": cp_km,
        "zone_source": zone_source or ""
    }
    
    # Calculate density ratio
    if total_a > 0 and total_b > 0:
        audit_data["density_ratio"] = (copresence_a + copresence_b) / (total_a + total_b)
    
    # Calculate raw percentages
    if total_a > 0:
        audit_data["pct_overtake_raw_a"] = round((overtakes_a / total_a * 100), 1)
    if total_b > 0:
        audit_data["pct_overtake_raw_b"] = round((overtakes_b / total_b * 100), 1)
    
    # Set audit trigger based on conditions
    if event_a == "Half" and event_b == "10K":
        audit_data["audit_trigger"] = "F1_ALWAYS"
    elif audit_data["pct_overtake_raw_a"] > 40 or audit_data["pct_overtake_raw_b"] > 40:
        audit_data["audit_trigger"] = "PCT_OVER_40"
    else:
        audit_data["audit_trigger"] = "SUSPICIOUS_RATE"
    
    # TODO: Implement detailed timing analysis, multipass detection, and strict validation
    # This is a placeholder implementation - the full implementation would require
    # detailed pairwise analysis of runner timing data
    
    return audit_data


def _read_runners_csv(path: str) -> List[Dict[str, Any]]:
    """Read runners CSV and return sorted list of runner records."""
    import csv
    
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append({
                    "runner_id": r["runner_id"],
                    "entry_time": float(r["entry_time_sec"]),
                    "exit_time":  float(r["exit_time_sec"]),
                    "entry_km":   float(r.get("entry_km", "nan") or "nan"),
                    "exit_km":    float(r.get("exit_km",  "nan") or "nan"),
                    "pace_min_per_km": float(r.get("pace_min_per_km", "nan") or "nan"),
                    "start_offset_sec": float(r.get("start_offset_sec", "nan") or "nan"),
                })
            except KeyError as e:
                raise SystemExit(f"Missing required column {e} in {path}")
    rows.sort(key=lambda x: x["entry_time"])
    return rows


def _shard_key_from_overlap_start(ts: float, window_granularity_sec: int = 60) -> str:
    """Generate shard key from overlap start timestamp."""
    m = int(ts // window_granularity_sec)
    return f"min_{m:06d}"


def _overlap_interval(a_entry: float, a_exit: float, b_entry: float, b_exit: float) -> Tuple[float, float, float]:
    """Calculate overlap interval between two runner time windows."""
    start = max(a_entry, b_entry)
    end   = min(a_exit,  b_exit)
    dwell = end - start
    return start, end, dwell


def _sign(x: float) -> int:
    """Return sign of number: 1 if positive, -1 if negative, 0 if zero."""
    if x > 0: return 1
    if x < 0: return -1
    return 0


def _determine_pass_flags_and_reason(
    order_flip: bool,
    dwell: float,
    directional_gain: float,
    strict_min_dwell: int,
    strict_margin: int
) -> Tuple[bool, bool, str]:
    """Determine pass flags and reason code for overlap pair."""
    pass_raw = order_flip
    pass_strict = (order_flip and dwell >= strict_min_dwell and directional_gain >= strict_margin)
    
    reason = ""
    if not pass_strict:
        if not order_flip:
            reason = "NO_DIRECTIONAL_CHANGE"
        elif dwell < strict_min_dwell:
            reason = "DWELL_TOO_SHORT"
        elif directional_gain < strict_margin:
            reason = "MARGIN_TOO_SMALL"
    
    return pass_raw, pass_strict, reason


def _build_overlap_row(
    run_id: str,
    executed_at_utc: str,
    seg_id: str,
    segment_label: str,
    flow_type: str,
    event_a_name: str,
    event_b_name: str,
    convergence_zone_start: float,
    convergence_zone_end: float,
    zone_width_m: float,
    binning_applied: bool,
    binning_mode: str,
    runner_a: Dict[str, Any],
    runner_b: Dict[str, Any],
    overlap_start: float,
    overlap_end: float,
    dwell: float,
    entry_delta: float,
    exit_delta: float,
    rel_entry: int,
    rel_exit: int,
    order_flip: bool,
    directional_gain: float,
    pass_raw: bool,
    pass_strict: bool,
    reason: str,
    conflict_zone_a_start: Optional[float] = None,
    conflict_zone_a_end: Optional[float] = None,
    conflict_zone_b_start: Optional[float] = None,
    conflict_zone_b_end: Optional[float] = None,
    in_conflict_zone: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Build overlap row dictionary for audit output.
    
    Issue #607 Enhancement: Added conflict zone boundaries and in_conflict_zone flag
    to support querying audit data to match Flow.csv results.
    """
    row = {
        "run_id": run_id,
        "executed_at_utc": executed_at_utc,
        "seg_id": seg_id,
        "segment_label": segment_label,
        "flow_type": flow_type,
        "event_a": event_a_name,
        "event_b": event_b_name,
        "pair_key": f"{runner_a['runner_id']}-{runner_b['runner_id']}",
        "convergence_zone_start": convergence_zone_start,
        "convergence_zone_end":   convergence_zone_end,
        "zone_width_m": zone_width_m,
        "binning_applied": binning_applied,
        "binning_mode": binning_mode,
        "runner_id_a": runner_a["runner_id"],
        "entry_km_a": runner_a["entry_km"],
        "exit_km_a":  runner_a["exit_km"],
        "entry_time_sec_a": runner_a["entry_time"],
        "exit_time_sec_a":  runner_a["exit_time"],
        "runner_id_b": runner_b["runner_id"],
        "entry_km_b": runner_b["entry_km"],
        "exit_km_b":  runner_b["exit_km"],
        "entry_time_sec_b": runner_b["entry_time"],
        "exit_time_sec_b":  runner_b["exit_time"],
        "overlap_start_time_sec": overlap_start,
        "overlap_end_time_sec":   overlap_end,
        "overlap_dwell_sec": dwell,
        "entry_delta_sec": entry_delta,
        "exit_delta_sec":  exit_delta,
        "rel_order_entry": rel_entry,
        "rel_order_exit":  rel_exit,
        "order_flip_bool": order_flip,
        "directional_gain_sec": directional_gain,
        "pass_flag_raw": pass_raw,
        "pass_flag_strict": pass_strict,
        "reason_code": reason
    }
    
    # Issue #607: Add conflict zone boundaries and flag
    if conflict_zone_a_start is not None:
        row["conflict_zone_a_start_km"] = conflict_zone_a_start
        row["conflict_zone_a_end_km"] = conflict_zone_a_end
        row["conflict_zone_b_start_km"] = conflict_zone_b_start
        row["conflict_zone_b_end_km"] = conflict_zone_b_end
        row["in_conflict_zone"] = in_conflict_zone
    
    return row


class _ShardWriter:
    """
    Helper class to manage shard file writing with row capping.
    
    DEPRECATED (Issue #607): This class is no longer used after refactoring audit
    output to Parquet format. Kept for reference but should not be used in new code.
    """
    def __init__(self, audit_dir: str, seg_id: str, event_a_name: str, event_b_name: str, 
                 pair_base_cols: List[str], row_cap_per_shard: int):
        self.audit_dir = audit_dir
        self.seg_id = seg_id
        self.event_a_name = event_a_name
        self.event_b_name = event_b_name
        self.pair_base_cols = pair_base_cols
        self.row_cap_per_shard = row_cap_per_shard
        self.shard_writers = {}
        self.shard_counts = {}
        self.current_shard_part = {}
    
    def _open_shard(self, shard_key: str, part_idx: int) -> Tuple[str, Any, Any]:
        """Open a new shard file and return path, file handle, and writer."""
        import csv, os
        
        shard_name = f"{self.seg_id}_{self.event_a_name}-{self.event_b_name}_{shard_key}_p{part_idx}.csv"
        shard_path = os.path.join(self.audit_dir, shard_name)
        f = open(shard_path, "w", newline="")
        w = csv.DictWriter(f, fieldnames=self.pair_base_cols)
        w.writeheader()
        return shard_path, f, w
    
    def write_pair(self, shard_key: str, row: Dict[str, Any]) -> str:
        """Write pair to appropriate shard, creating new shard if needed."""
        if shard_key not in self.shard_writers:
            path, fh, wr = self._open_shard(shard_key, 1)
            self.shard_writers[shard_key] = (path, fh, wr)
            self.shard_counts[shard_key] = 0
            self.current_shard_part[shard_key] = 1
        
        path, fh, wr = self.shard_writers[shard_key]
        if self.shard_counts[shard_key] >= self.row_cap_per_shard:
            fh.close()
            self.current_shard_part[shard_key] += 1
            path, fh, wr = self._open_shard(shard_key, self.current_shard_part[shard_key])
            self.shard_writers[shard_key] = (path, fh, wr)
            self.shard_counts[shard_key] = 0
        
        wr.writerow(row)
        self.shard_counts[shard_key] += 1
        return path
    
    def close_all(self) -> List[str]:
        """Close all shard files and return list of paths."""
        shard_paths = []
        for key, (path, fh, wr) in self.shard_writers.items():
            fh.close()
            shard_paths.append(path)
        return shard_paths


def _process_two_pointer_sweep(
    A: List[Dict[str, Any]],
    B: List[Dict[str, Any]],
    rows_collector: List[Dict[str, Any]],
    run_id: str,
    executed_at_utc: str,
    seg_id: str,
    segment_label: str,
    flow_type: str,
    event_a_name: str,
    event_b_name: str,
    convergence_zone_start: float,
    convergence_zone_end: float,
    zone_width_m: float,
    binning_applied: bool,
    binning_mode: str,
    strict_min_dwell: int,
    strict_margin: int,
    topk: List[Tuple[float, Dict[str, Any]]],
    topk_size: int = 2000,
    conflict_zone_a_start: Optional[float] = None,
    conflict_zone_a_end: Optional[float] = None,
    conflict_zone_b_start: Optional[float] = None,
    conflict_zone_b_end: Optional[float] = None,
    min_overlap_duration: float = 0.0
) -> Tuple[int, int, int, int]:
    """
    Process two-pointer sweep algorithm for temporal interval join.
    
    Issue #607: Refactored to collect rows in a list instead of writing via _ShardWriter.
    Issue #607 Enhancement: Added conflict zone boundaries and in_conflict_zone flag calculation.
    """
    j = 0
    total_pairs = 0
    overlapped_pairs = 0
    strict_pass = 0
    raw_pass = 0
    
    for a in A:
        while j < len(B) and B[j]["exit_time"] < a["entry_time"]:
            j += 1
        k = j
        while k < len(B) and B[k]["entry_time"] <= a["exit_time"]:
            b = B[k]
            total_pairs += 1
            os_, oe_, dwell = _overlap_interval(a["entry_time"], a["exit_time"], b["entry_time"], b["exit_time"])
            
            if dwell > 0:
                overlapped_pairs += 1
                entry_delta = a["entry_time"] - b["entry_time"]
                exit_delta  = a["exit_time"]  - b["exit_time"]
                rel_entry   = _sign(entry_delta)
                rel_exit    = _sign(exit_delta)
                order_flip  = (rel_entry != rel_exit)
                directional_gain = exit_delta - entry_delta
                
                pass_raw, pass_strict, reason = _determine_pass_flags_and_reason(
                    order_flip, dwell, directional_gain, strict_min_dwell, strict_margin
                )
                
                if pass_raw: raw_pass += 1
                if pass_strict: strict_pass += 1
                
                # Issue #607: Calculate if overlap is within conflict zone
                # The main analysis calculates entry/exit times based on conflict zone boundaries.
                # To match Flow.csv, we need to recalculate entry/exit times for conflict zone
                # and check if the temporal overlap would still occur.
                in_conflict_zone = None
                if (conflict_zone_a_start is not None and conflict_zone_a_end is not None and
                    conflict_zone_b_start is not None and conflict_zone_b_end is not None):
                    # Calculate pace from full segment entry/exit times and distances
                    # pace = (exit_time - entry_time) / (exit_km - entry_km) in sec/km
                    segment_length_a = a["exit_km"] - a["entry_km"]
                    segment_length_b = b["exit_km"] - b["entry_km"]
                    
                    if segment_length_a > 0 and segment_length_b > 0:
                        pace_a_sec_per_km = (a["exit_time"] - a["entry_time"]) / segment_length_a
                        pace_b_sec_per_km = (b["exit_time"] - b["entry_time"]) / segment_length_b
                        
                        # Calculate entry time at conflict zone start (relative to segment entry)
                        # entry_time_at_conflict_start = entry_time + pace * (conflict_start - entry_km)
                        conflict_zone_entry_time_a = a["entry_time"] + pace_a_sec_per_km * (conflict_zone_a_start - a["entry_km"])
                        conflict_zone_exit_time_a = a["entry_time"] + pace_a_sec_per_km * (conflict_zone_a_end - a["entry_km"])
                        conflict_zone_entry_time_b = b["entry_time"] + pace_b_sec_per_km * (conflict_zone_b_start - b["entry_km"])
                        conflict_zone_exit_time_b = b["entry_time"] + pace_b_sec_per_km * (conflict_zone_b_end - b["entry_km"])
                        
                        # Check if temporal overlap occurs within conflict zone boundaries
                        # Overlap occurs if: max(entry_a, entry_b) < min(exit_a, exit_b)
                        overlap_start = max(conflict_zone_entry_time_a, conflict_zone_entry_time_b)
                        overlap_end = min(conflict_zone_exit_time_a, conflict_zone_exit_time_b)
                        conflict_zone_overlap_duration = overlap_end - overlap_start
                        
                        # Also check if both runners actually pass through their conflict zones
                        # (entry_km <= conflict_end AND exit_km >= conflict_start)
                        a_passes_through_zone = (a["entry_km"] <= conflict_zone_a_end and a["exit_km"] >= conflict_zone_a_start)
                        b_passes_through_zone = (b["entry_km"] <= conflict_zone_b_end and b["exit_km"] >= conflict_zone_b_start)
                        
                        # Overlap is in conflict zone if:
                        # 1. Both runners pass through their conflict zones
                        # 2. There is a temporal overlap when using conflict zone entry/exit times
                        # 3. Overlap duration meets minimum threshold (binned method uses >= min_overlap_duration)
                        in_conflict_zone = (a_passes_through_zone and b_passes_through_zone and 
                                          conflict_zone_overlap_duration >= min_overlap_duration)
                    else:
                        # Invalid segment lengths, default to False
                        in_conflict_zone = False
                
                row = _build_overlap_row(
                    run_id, executed_at_utc, seg_id, segment_label, flow_type,
                    event_a_name, event_b_name, convergence_zone_start, convergence_zone_end,
                    zone_width_m, binning_applied, binning_mode, a, b,
                    os_, oe_, dwell, entry_delta, exit_delta, rel_entry, rel_exit,
                    order_flip, directional_gain, pass_raw, pass_strict, reason,
                    conflict_zone_a_start, conflict_zone_a_end,
                    conflict_zone_b_start, conflict_zone_b_end,
                    in_conflict_zone
                )
                rows_collector.append(row)
                
                topk.append((dwell, row))
                if len(topk) > topk_size:
                    topk.sort(key=lambda x: x[0], reverse=True)
                    topk[:] = topk[:topk_size]
            k += 1
    
    return total_pairs, overlapped_pairs, raw_pass, strict_pass


def _write_index_csv(
    audit_dir: str,
    seg_id: str,
    event_a_name: str,
    event_b_name: str,
    run_id: str,
    total_pairs: int,
    overlapped_pairs: int,
    raw_pass: int,
    strict_pass: int,
    shard_paths: List[str]
) -> str:
    """
    Write index CSV with audit summary statistics.
    
    DEPRECATED (Issue #607): This function is no longer used after refactoring audit
    output to Parquet format. Index/TopK summaries can be generated on-demand from
    Parquet files using DuckDB or Pandas. Kept for reference but should not be used.
    """
    import csv, os
    
    index_path = os.path.join(audit_dir, f"{seg_id}_{event_a_name}-{event_b_name}_index.csv")
    with open(index_path, "w", newline="") as f:
        idx_cols = ["run_id","seg_id","event_a","event_b","n_pairs_total","n_pairs_overlapped","n_pass_raw","n_pass_strict","shards"]
        w = csv.DictWriter(f, fieldnames=idx_cols)
        w.writeheader()
        w.writerow({
            "run_id": run_id,
            "seg_id": seg_id,
            "event_a": event_a_name,
            "event_b": event_b_name,
            "n_pairs_total": total_pairs,
            "n_pairs_overlapped": overlapped_pairs,
            "n_pass_raw": raw_pass,
            "n_pass_strict": strict_pass,
            "shards": ";".join(os.path.basename(p) for p in sorted(shard_paths))
        })
    
    return index_path


def _write_topk_csv(
    audit_dir: str,
    seg_id: str,
    event_a_name: str,
    event_b_name: str,
    topk: List[Tuple[float, Dict[str, Any]]],
    pair_base_cols: List[str]
) -> str:
    """
    Write TopK CSV with highest dwell time overlaps.
    
    DEPRECATED (Issue #607): This function is no longer used after refactoring audit
    output to Parquet format. TopK summaries can be generated on-demand from Parquet
    files using DuckDB or Pandas. Kept for reference but should not be used.
    """
    import csv, os
    
    topk_path = os.path.join(audit_dir, f"{seg_id}_{event_a_name}-{event_b_name}_TopK.csv")
    with open(topk_path, "w", newline="") as f:
        cols = list(topk[0][1].keys()) if topk else pair_base_cols
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for _, row in sorted(topk, key=lambda x: x[0], reverse=True):
            w.writerow(row)
    
    return topk_path


def emit_runner_audit(
    event_a_data: pd.DataFrame,
    event_b_data: pd.DataFrame,
    run_id: str,
    seg_id: str,
    segment_label: str,
    flow_type: str,
    event_a_name: str,
    event_b_name: str,
    convergence_zone_start: float,
    convergence_zone_end: float,
    zone_width_m: float,
    binning_applied: bool = False,
    binning_mode: str = "none",
    strict_min_dwell: int = 5,
    strict_margin: int = 2,
    from_km_a: Optional[float] = None,
    to_km_a: Optional[float] = None,
    from_km_b: Optional[float] = None,
    to_km_b: Optional[float] = None
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Generate runner-level audit data and return as DataFrame.
    
    Issue #607: Refactored to return DataFrame instead of writing CSV files.
    Issue #607 Enhancement: Added conflict zone boundaries and in_conflict_zone flag.
    
    Inputs: 
        - event_a_data: DataFrame with columns: runner_id, entry_time, exit_time, entry_km, exit_km
        - event_b_data: DataFrame with columns: runner_id, entry_time, exit_time, entry_km, exit_km
        - from_km_a, to_km_a, from_km_b, to_km_b: Full segment ranges (for conflict zone calculation)
    
    Outputs:
        - DataFrame with all audit rows (including conflict zone columns)
        - Dictionary with summary statistics
    
    Strategy: interval join using two-pointer sweep algorithm.
    """
    import datetime
    
    executed_at_utc = datetime.datetime.utcnow().isoformat()+"Z"
    
    # Convert DataFrames to list of dicts (matching _read_runners_csv format)
    A = event_a_data.to_dict('records') if not event_a_data.empty else []
    B = event_b_data.to_dict('records') if not event_b_data.empty else []
    
    # Sort by entry_time (should already be sorted, but ensure it)
    A.sort(key=lambda x: x["entry_time"])
    B.sort(key=lambda x: x["entry_time"])
    
    # Issue #607: Calculate conflict zone boundaries if segment ranges are provided
    conflict_zone_a_start = None
    conflict_zone_a_end = None
    conflict_zone_b_start = None
    conflict_zone_b_end = None
    
    if from_km_a is not None and to_km_a is not None and from_km_b is not None and to_km_b is not None:
        # Calculate conflict zone boundaries (same logic as main analysis)
        center_a = (from_km_a + to_km_a) / 2.0
        center_b = (from_km_b + to_km_b) / 2.0
        conflict_half_km = (zone_width_m / 1000.0) / 2.0
        
        conflict_zone_a_start = max(from_km_a, center_a - conflict_half_km)
        conflict_zone_a_end = min(to_km_a, center_a + conflict_half_km)
        conflict_zone_b_start = max(from_km_b, center_b - conflict_half_km)
        conflict_zone_b_end = min(to_km_b, center_b + conflict_half_km)
    
    # Collect rows instead of writing to files
    rows_collector = []
    topk = []  # Keep topk for potential future use, but don't write CSV
    
    # Process two-pointer sweep algorithm
    # Issue #607: Pass min_overlap_duration to match main analysis logic
    from app.utils.constants import DEFAULT_MIN_OVERLAP_DURATION
    total_pairs, overlapped_pairs, raw_pass, strict_pass = _process_two_pointer_sweep(
        A, B, rows_collector, run_id, executed_at_utc, seg_id, segment_label, flow_type,
        event_a_name, event_b_name, convergence_zone_start, convergence_zone_end,
        zone_width_m, binning_applied, binning_mode, strict_min_dwell, strict_margin,
        topk, 2000,  # topk_size, not used for CSV anymore
        conflict_zone_a_start, conflict_zone_a_end, conflict_zone_b_start, conflict_zone_b_end,
        DEFAULT_MIN_OVERLAP_DURATION  # Issue #607: Use same min_overlap_duration as main analysis
    )
    
    # Convert collected rows to DataFrame
    if rows_collector:
        audit_df = pd.DataFrame(rows_collector)
    else:
        # Create empty DataFrame with correct schema (including conflict zone columns)
        base_columns = [
            "run_id","executed_at_utc","seg_id","segment_label","flow_type",
            "event_a","event_b","pair_key",
            "convergence_zone_start","convergence_zone_end","zone_width_m",
            "binning_applied","binning_mode",
            "runner_id_a","entry_km_a","exit_km_a","entry_time_sec_a","exit_time_sec_a",
            "runner_id_b","entry_km_b","exit_km_b","entry_time_sec_b","exit_time_sec_b",
            "overlap_start_time_sec","overlap_end_time_sec","overlap_dwell_sec",
            "entry_delta_sec","exit_delta_sec","rel_order_entry","rel_order_exit",
            "order_flip_bool","directional_gain_sec",
            "pass_flag_raw","pass_flag_strict","reason_code"
        ]
        # Issue #607: Add conflict zone columns if calculated
        if conflict_zone_a_start is not None:
            base_columns.extend([
                "conflict_zone_a_start_km", "conflict_zone_a_end_km",
                "conflict_zone_b_start_km", "conflict_zone_b_end_km",
                "in_conflict_zone"
            ])
        audit_df = pd.DataFrame(columns=base_columns)
    
    stats = {
        "total_pairs": total_pairs,
        "overlapped_pairs": overlapped_pairs,
        "raw_pass": raw_pass,
        "strict_pass": strict_pass
    }
    
    return audit_df, stats


def extract_runner_timing_data_for_audit(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    output_dir: str = "reports"
) -> Dict[str, Any]:
    """
    Extract runner timing data from flow analysis for runner audit emitter.
    
    Returns DataFrames with runner entry/exit timing data that can be consumed
    by the emit_runner_audit function.
    
    Updated to work with v2 pipeline DataFrames that have:
    - 'pace' (min per km)
    - 'start_offset' (seconds)
    - 'runner_id'
    
    Entry/exit times are calculated from pace, start_offset, and distance ranges.
    
    Issue #607: Refactored to return DataFrames instead of CSV file paths.
    """
    import os
    
    # Create audit subdirectory within the output directory
    # For v2 pipeline, output_dir is already {run_id}/{day}, so this creates {run_id}/{day}/audit
    audit_dir = os.path.join(output_dir, "audit")
    os.makedirs(audit_dir, exist_ok=True)
    
    # Get start times in seconds (start_times dict is in minutes)
    start_a_sec = start_times.get(event_a, 0.0) * 60.0
    start_b_sec = start_times.get(event_b, 0.0) * 60.0
    
    # Extract runner data for event A
    runners_a = []
    for _, runner in df_a.iterrows():
        # Get pace in min/km, convert to sec/km
        pace_min_per_km = runner.get('pace', 0.0)
        pace_sec_per_km = pace_min_per_km * 60.0
        
        # Get start_offset in seconds
        start_offset_sec = runner.get('start_offset', 0.0)
        if pd.isna(start_offset_sec):
            start_offset_sec = 0.0
        
        # Calculate entry/exit times in seconds from start
        # Formula: start_time_sec + start_offset + pace_sec_per_km * distance_km
        entry_time_sec = start_a_sec + start_offset_sec + pace_sec_per_km * from_km_a
        exit_time_sec = start_a_sec + start_offset_sec + pace_sec_per_km * to_km_a
        
        # Entry/exit distances
        entry_km = from_km_a
        exit_km = to_km_a
        
        runners_a.append({
            'runner_id': runner['runner_id'],
            'entry_time': entry_time_sec,  # Note: using 'entry_time' to match _read_runners_csv format
            'exit_time': exit_time_sec,    # Note: using 'exit_time' to match _read_runners_csv format
            'entry_km': entry_km,
            'exit_km': exit_km,
            'pace_min_per_km': pace_min_per_km,
            'start_offset_sec': float(start_offset_sec)
        })
    
    # Extract runner data for event B
    runners_b = []
    for _, runner in df_b.iterrows():
        # Get pace in min/km, convert to sec/km
        pace_min_per_km = runner.get('pace', 0.0)
        pace_sec_per_km = pace_min_per_km * 60.0
        
        # Get start_offset in seconds
        start_offset_sec = runner.get('start_offset', 0.0)
        if pd.isna(start_offset_sec):
            start_offset_sec = 0.0
        
        # Calculate entry/exit times in seconds from start
        # Formula: start_time_sec + start_offset + pace_sec_per_km * distance_km
        entry_time_sec = start_b_sec + start_offset_sec + pace_sec_per_km * from_km_b
        exit_time_sec = start_b_sec + start_offset_sec + pace_sec_per_km * to_km_b
        
        # Entry/exit distances
        entry_km = from_km_b
        exit_km = to_km_b
        
        runners_b.append({
            'runner_id': runner['runner_id'],
            'entry_time': entry_time_sec,  # Note: using 'entry_time' to match _read_runners_csv format
            'exit_time': exit_time_sec,    # Note: using 'exit_time' to match _read_runners_csv format
            'entry_km': entry_km,
            'exit_km': exit_km,
            'pace_min_per_km': pace_min_per_km,
            'start_offset_sec': float(start_offset_sec)
        })
    
    # Convert to DataFrames and sort by entry_time (matching _read_runners_csv behavior)
    df_a_audit = pd.DataFrame(runners_a)
    df_b_audit = pd.DataFrame(runners_b)
    
    if not df_a_audit.empty:
        df_a_audit = df_a_audit.sort_values('entry_time').reset_index(drop=True)
    if not df_b_audit.empty:
        df_b_audit = df_b_audit.sort_values('entry_time').reset_index(drop=True)
    
    return {
        'event_a_data': df_a_audit,
        'event_b_data': df_b_audit,
        'runners_a_count': len(runners_a),
        'runners_b_count': len(runners_b)
    }


def validate_per_runner_entry_exit_f1(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = CONFLICT_LENGTH_LONG_SEGMENT_M,
) -> Dict[str, Any]:
    """
    PER-RUNNER ENTRY/EXIT VALIDATION for F1 Half vs 10K segment.
    
    This function calculates entry and exit times for ALL runners in each event
    to validate overtaking counts and percentages for the F1 segment.
    
    Returns detailed validation results including:
    - Entry/exit times for all runners
    - Actual temporal overlaps
    - Validated overtaking counts
    - Reason codes for any discrepancies
    """
    import logging
    
    if df_a.empty or df_b.empty:
        return {"error": "Empty dataframes provided"}
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0  # Convert to seconds
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate conflict zone boundaries (using segment centers for F1)
    center_a = (from_km_a + to_km_a) / 2.0
    center_b = (from_km_b + to_km_b) / 2.0
    conflict_half_km = (conflict_length_m / 1000.0) / 2.0
    
    cp_km_a_start = max(from_km_a, center_a - conflict_half_km)
    cp_km_a_end = min(to_km_a, center_a + conflict_half_km)
    cp_km_b_start = max(from_km_b, center_b - conflict_half_km)
    cp_km_b_end = min(to_km_b, center_b + conflict_half_km)
    
    # Calculate entry/exit times for ALL runners in Event A
    a_entry_times = []
    a_exit_times = []
    a_runner_ids = []
    
    for idx, row in df_a.iterrows():
        pace_a = row["pace"] * 60.0  # sec per km
        offset_a = row.get("start_offset", 0)
        runner_id = row["runner_id"]
        
        entry_time = start_a + offset_a + pace_a * cp_km_a_start
        exit_time = start_a + offset_a + pace_a * cp_km_a_end
        
        a_entry_times.append(entry_time)
        a_exit_times.append(exit_time)
        a_runner_ids.append(runner_id)
    
    # Calculate entry/exit times for ALL runners in Event B
    b_entry_times = []
    b_exit_times = []
    b_runner_ids = []
    
    for idx, row in df_b.iterrows():
        pace_b = row["pace"] * 60.0  # sec per km
        offset_b = row.get("start_offset", 0)
        runner_id = row["runner_id"]
        
        entry_time = start_b + offset_b + pace_b * cp_km_b_start
        exit_time = start_b + offset_b + pace_b * cp_km_b_end
        
        b_entry_times.append(entry_time)
        b_exit_times.append(exit_time)
        b_runner_ids.append(runner_id)
    
    # Issue #503: Vectorized temporal overlap detection using NumPy broadcasting
    # Convert lists to numpy arrays for vectorized operations
    a_entry_arr = np.array(a_entry_times)  # (n,)
    a_exit_arr = np.array(a_exit_times)     # (n,)
    b_entry_arr = np.array(b_entry_times)  # (m,)
    b_exit_arr = np.array(b_exit_times)    # (m,)
    
    # Broadcast to compute all pairwise overlaps: (n, 1) vs (1, m) = (n, m)
    a_entry_2d = a_entry_arr[:, np.newaxis]  # (n, 1)
    a_exit_2d = a_exit_arr[:, np.newaxis]    # (n, 1)
    b_entry_2d = b_entry_arr[np.newaxis, :]  # (1, m)
    b_exit_2d = b_exit_arr[np.newaxis, :]     # (1, m)
    
    # Compute overlap start/end/duration for all pairs
    overlap_start = np.maximum(a_entry_2d, b_entry_2d)  # (n, m)
    overlap_end = np.minimum(a_exit_2d, b_exit_2d)     # (n, m)
    overlap_duration = overlap_end - overlap_start      # (n, m)
    
    # Find pairs with temporal overlap (duration > 0)
    has_overlap = overlap_duration > 0  # (n, m) boolean
    
    # Check for directional passes
    a_passes_b = (a_entry_2d > b_entry_2d) & (a_exit_2d < b_exit_2d)  # (n, m)
    b_passes_a = (b_entry_2d > a_entry_2d) & (b_exit_2d < a_exit_2d)  # (n, m)
    has_overtake = a_passes_b | b_passes_a  # (n, m)
    
    # Find temporal overlaps and validate overtaking
    a_overtakes = set()
    b_overtakes = set()
    a_copresence = set()
    b_copresence = set()
    
    overlap_pairs = []
    
    # Iterate only over pairs with overlap (much fewer iterations)
    overlap_indices = np.argwhere(has_overlap)  # (k, 2) array of [i, j] pairs
    
    for i, j in overlap_indices:
        a_id = a_runner_ids[i]
        b_id = b_runner_ids[j]
        
        a_copresence.add(a_id)
        b_copresence.add(b_id)
        
        # Issue #552: Fix overtaking count logic - only count the runner who is actually overtaking
        if a_passes_b[i, j]:  # Runner A overtakes runner B
            a_overtakes.add(a_id)  # Only count A as overtaking
        if b_passes_a[i, j]:  # Runner B overtakes runner A
            b_overtakes.add(b_id)  # Only count B as overtaking
        
        overlap_pairs.append({
            "a_id": a_id,
            "b_id": b_id,
            "a_entry": a_entry_arr[i],
            "a_exit": a_exit_arr[i],
            "b_entry": b_entry_arr[j],
            "b_exit": b_exit_arr[j],
            "overlap_duration": overlap_duration[i, j],
            "a_passes_b": bool(a_passes_b[i, j]),
            "b_passes_a": bool(b_passes_a[i, j])
        })
    
    # Calculate validation results
    total_a = len(df_a)
    total_b = len(df_b)
    overtakes_a = len(a_overtakes)
    overtakes_b = len(b_overtakes)
    copresence_a = len(a_copresence)
    copresence_b = len(b_copresence)
    
    pct_a = (overtakes_a / total_a * 100) if total_a > 0 else 0.0
    pct_b = (overtakes_b / total_b * 100) if total_b > 0 else 0.0
    
    # Log validation results
    logging.info(f"F1 {event_a} vs {event_b} PER-RUNNER VALIDATION:")
    logging.info(f"  Total {event_a}: {total_a}, Overtaking: {overtakes_a} ({pct_a:.1f}%)")
    logging.info(f"  Total {event_b}: {total_b}, Overtaking: {overtakes_b} ({pct_b:.1f}%)")
    logging.info(f"  Co-presence {event_a}: {copresence_a}, {event_b}: {copresence_b}")
    logging.info(f"  Overlap pairs: {len(overlap_pairs)}")
    
    return {
        "total_a": total_a,
        "total_b": total_b,
        "overtakes_a": overtakes_a,
        "overtakes_b": overtakes_b,
        "copresence_a": copresence_a,
        "copresence_b": copresence_b,
        "pct_a": pct_a,
        "pct_b": pct_b,
        "overlap_pairs": overlap_pairs[:10],  # First 10 for debugging
        "conflict_zone_a": (cp_km_a_start, cp_km_a_end),
        "conflict_zone_b": (cp_km_b_start, cp_km_b_end),
        "validation_timestamp": time.time()
    }


def calculate_overtaking_loads(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,                 # convergence point (km) used by your working detector
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
) -> Tuple[Dict[str, int], Dict[str, int], float, float, int, int]:
    """
    Count individual overtaking encounters (per-runner 'overtaking loads') by
    reusing the same conflict-zone + boundary-time logic as the proven detector.

    Returns:
        (loads_a, loads_b, avg_load_a, avg_load_b, max_load_a, max_load_b)
    """
    # Basic guards
    if df_a.empty or df_b.empty:
        return {}, {}, 0.0, 0.0, 0, 0
    if cp_km is None:
        return {}, {}, 0.0, 0.0, 0, 0
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return {}, {}, 0.0, 0.0, 0, 0

    # Convert event start times from minutes to seconds (for BOTH events)
    start_a = float(start_times.get(event_a, 0.0)) * 60.0
    start_b = float(start_times.get(event_b, 0.0)) * 60.0

    # --- Conflict-zone boundaries (mirror working function) ---
    # Try absolute intersection first
    intersection_start = max(from_km_a, from_km_b)
    intersection_end   = min(to_km_a, to_km_b)

    def _compute_normalized_zone():
        # If cp_km lies within A, use proportional window around cp mapped to both events
        if from_km_a <= cp_km <= to_km_a:
            s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
            conflict_length_km = conflict_length_m / 1000.0
            min_seg = max(min(len_a, len_b), 1e-9)
            s_half = max(conflict_length_km / min_seg / 2.0, 0.05)
            s_start = max(0.0, s_cp - s_half)
            s_end   = min(1.0, s_cp + s_half)
            if s_end <= s_start:
                s_start = max(0.0, s_cp - 0.05)
                s_end   = min(1.0, s_cp + 0.05)
            return (
                from_km_a + s_start * len_a,
                from_km_a + s_end   * len_a,
                from_km_b + s_start * len_b,
                from_km_b + s_end   * len_b,
            )
        # Otherwise, a center-based fallback
        center_a = (from_km_a + to_km_a) / 2.0
        center_b = (from_km_b + to_km_b) / 2.0
        half_km  = (conflict_length_m / 1000.0) / 2.0
        return (
            max(from_km_a, center_a - half_km),
            min(to_km_a,   center_a + half_km),
            max(from_km_b, center_b - half_km),
            min(to_km_b,   center_b + half_km),
        )

    if intersection_start < intersection_end:
        boundary_start_a = boundary_start_b = intersection_start
        boundary_end_a   = boundary_end_b   = intersection_end
    else:
        boundary_start_a, boundary_end_a, boundary_start_b, boundary_end_b = _compute_normalized_zone()

    # --- Only keep runners who actually reach the zone end for their event ---
    def within_event_bounds(df, zone_start_km, zone_end_km):
        return df[(df["distance"] >= zone_end_km)]

    df_a_pass = within_event_bounds(df_a, boundary_start_a, boundary_end_a).copy()
    df_b_pass = within_event_bounds(df_b, boundary_start_b, boundary_end_b).copy()
    if df_a_pass.empty or df_b_pass.empty:
        return {}, {}, 0.0, 0.0, 0, 0

    # --- Arrival times at the zone boundaries for each runner ---
    def times_at_bounds(row, start_base_sec, km_start, km_end):
        sec_per_km = float(row["pace"]) * 60.0
        t_start = start_base_sec + float(row["start_offset"]) + sec_per_km * km_start
        t_end   = start_base_sec + float(row["start_offset"]) + sec_per_km * km_end
        return t_start, t_end

    a_times = [(row["runner_id"], *times_at_bounds(row, start_a, boundary_start_a, boundary_end_a))
               for _, row in df_a_pass.iterrows()]
    b_times = [(row["runner_id"], *times_at_bounds(row, start_b, boundary_start_b, boundary_end_b))
               for _, row in df_b_pass.iterrows()]

    # Detect temporal overlap and passes
    loads_a, loads_b = _detect_temporal_overlap_and_passes(a_times, b_times, min_overlap_duration)
    
    # Calculate statistics
    avg_load_a = sum(loads_a.values()) / len(loads_a) if loads_a else 0.0
    avg_load_b = sum(loads_b.values()) / len(loads_b) if loads_b else 0.0
    max_load_a = max(loads_a.values()) if loads_a else 0
    max_load_b = max(loads_b.values()) if loads_b else 0
    
    return loads_a, loads_b, avg_load_a, avg_load_b, max_load_a, max_load_b

def _log_flow_segment_stats(seg_id, event_a, event_b, path, counters):
    """
    Log structured flow segment statistics for debugging.
    
    Args:
        seg_id: Segment identifier
        event_a: First event name
        event_b: Second event name
        path: Analysis path identifier
        counters: Dictionary of counter values
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Flow stats [{path}] {seg_id} {event_a}vs{event_b}: {counters}")


def _generate_flow_type_analysis(segment: Dict[str, Any], flow_type: str) -> List[str]:
    """
    Generate flow type specific analysis text.
    
    Args:
        segment: Segment data dictionary
        flow_type: Type of flow ('merge', 'diverge', 'overtake', etc.)
        
    Returns:
        List of analysis text lines
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


def _detect_temporal_overlap_and_passes(a_times: List[Tuple[str, float, float]], 
                                       b_times: List[Tuple[str, float, float]], 
                                       min_overlap_duration: float) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Detect temporal overlap and directional passes between two sets of runners.
    
    Args:
        a_times: List of (runner_id, start_time, end_time) tuples for event A
        b_times: List of (runner_id, start_time, end_time) tuples for event B
        min_overlap_duration: Minimum overlap duration to consider
        
    Returns:
        Tuple of (loads_a, loads_b) dictionaries mapping runner_id to pass count
    """
    loads_a, loads_b = {}, {}
    
    for a_id, as_, ae_ in a_times:
        loads_a.setdefault(a_id, 0)
        for b_id, bs_, be_ in b_times:
            loads_b.setdefault(b_id, 0)
            
            # Calculate temporal overlap
            overlap_start = max(as_, bs_)
            overlap_end = min(ae_, be_)
            if (overlap_end - overlap_start) < min_overlap_duration:
                continue
                
            # Detect directional passes
            a_passes_b = (as_ > bs_) and (ae_ < be_)
            b_passes_a = (bs_ > as_) and (be_ < ae_)
            
            if a_passes_b:
                loads_a[a_id] += 1
            elif b_passes_a:
                loads_b[b_id] += 1
    
    return loads_a, loads_b


def calculate_convergence_zone_overlaps_with_binning(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    overlap_duration_minutes: float = 0.0,
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """
    Calculate overtaking with binning for all segments.
    
    Issue #612 Task 2: Binning is now always-on for all segments (short and long).
    Binning must never gate analysis - it's always used as the calculation method.
    
    The function still decides between time bins and distance bins based on segment
    characteristics, but the binned calculation path is always used.
    """
    
    # Import unified selector modules
    from app.normalization import normalize
    from app.selector import choose_path
    from app.telemetry import pub_decision_log
    from app.config_algo_consistency import FLAGS
    
    # Create segment key for unified selector
    segment_key = f"{event_a}_vs_{event_b}"  # Will be enhanced with segment ID later
    
    if FLAGS.ENABLE_BIN_SELECTOR_UNIFICATION:
        # Use unified selector logic (normalization hoisted out of inner loops)
        # Normalize inputs once per segment to prevent threshold drift
        norm_inputs = normalize(conflict_length_m, "m", overlap_duration_minutes * 60, "s")
        
        # Use unified selector to choose calculation path
        chosen_path = choose_path(segment_key, norm_inputs)
        
        # Map unified path to legacy binning flags
        use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
        use_distance_bins = chosen_path == "BINNED"
    else:
        # Use legacy binning logic (always use binning - decide between time/distance bins)
        use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
        use_distance_bins = conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
        chosen_path = "BINNED"  # Always use binned path (Issue #612 Task 2)
        norm_inputs = None
    
    # Issue #612 Task 2: Always use binned calculation (binning is always-on)
    # The function still decides between time bins and distance bins, but always uses binning
    # Log binning decision for transparency
    logging.info(f"BINNING APPLIED (always-on): time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
    
    results = calculate_convergence_zone_overlaps_binned(
        df_a, df_b, event_a, event_b, start_times,
        cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
        min_overlap_duration, conflict_length_m,
        use_time_bins, use_distance_bins, overlap_duration_minutes
    )
    
    # Extract results for telemetry
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = results
    
    # Add telemetry logging for algorithm consistency verification (sampled)
    if event_a == "Half" and event_b == "10K" and hash(segment_key) % 100 == 0:  # 1% sampling
        if norm_inputs is not None:
            telemetry_log = pub_decision_log(
                segment_key, chosen_path, norm_inputs.conflict_len_m, norm_inputs.overlap_dur_s,
                (overtakes_a, overtakes_b), (overtakes_a, overtakes_b)  # Using same for strict/raw for now
            )
            print(f"🔍 {telemetry_log}")
        else:
            print(f"🔍 LEGACY BINNING: {chosen_path} -> {overtakes_a}/{overtakes_b}")
    
    return results


def calculate_convergence_zone_overlaps_original(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """
    Calculate the number of overlapping runners within the convergence zone,
    projecting both events onto a common segment-local axis.
    
    CRITICAL: Returns SEPARATE counts for true passes vs co-presence.
    - True passes: runners who actually overtake each other directionally
    - Co-presence: runners who overlap temporally without directional change
    - Checks BOTH temporal overlap AND directional change
    - Uses intersection boundaries for fair directional comparison
    
    PROPORTIONAL TOLERANCE: Uses 5% of shorter segment length, minimum 50m
    to ensure consistent behavior across different segment sizes.
    
    Returns:
        Tuple of (overtakes_a, overtakes_b, copresence_a, copresence_b, 
                 sample_a, sample_b, unique_encounters, participants_involved)
    """
    if df_a.empty or df_b.empty:
        return 0, 0, 0, 0, [], [], 0, 0
    
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return 0, 0, 0, 0, [], [], 0, 0

    # Check if convergence point is within Event A's range (absolute approach)
    # or if we need to use normalized approach (for segments like F1)
    if from_km_a <= cp_km <= to_km_a:
        # Convergence point is within Event A's range - use absolute approach
        s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
        s_cp, clamp_reason = clamp_normalized_fraction(s_cp, "convergence_point_")
    
        # Calculate conflict zone in normalized space
        conflict_length_km = conflict_length_m / 1000.0  # Convert meters to km
        conflict_half_km = conflict_length_km / 2.0
    
        # Convert conflict zone to normalized fractions
        # Use proportional tolerance: 5% of shorter segment, minimum 50m
        min_segment_len = min(len_a, len_b)
        proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)  # 5% of shorter segment, min 50m
        s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
        
        # Define normalized conflict zone boundaries
        s_start = max(0.0, s_cp - s_conflict_half)
        s_end = min(1.0, s_cp + s_conflict_half)
        
        # Ensure conflict zone has some width
        if s_end <= s_start:
            s_start = max(0.0, s_cp - 0.05)  # 5% of segment
            s_end = min(1.0, s_cp + 0.05)    # 5% of segment
        
        # Convert normalized conflict zone to each event's absolute coordinates
        cp_km_a_start = from_km_a + s_start * len_a
        cp_km_a_end = from_km_a + s_end * len_a

        cp_km_b_start = from_km_b + s_start * len_b
        cp_km_b_end = from_km_b + s_end * len_b
    else:
        # Convergence point is outside Event A's range - use normalized approach
        # This handles cases where convergence was detected in normalized space
        # but the point doesn't map to Event A's absolute coordinates
        
        # Use the intersection boundaries if they exist, otherwise use proportional zones
        intersection_start = max(from_km_a, from_km_b)
        intersection_end = min(to_km_a, to_km_b)
        
        if intersection_start < intersection_end:
            # There is an intersection - use it for conflict zone
            conflict_length_km = conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0
            
            cp_km_a_start = max(from_km_a, intersection_start - conflict_half_km)
            cp_km_a_end = min(to_km_a, intersection_end + conflict_half_km)
            
            cp_km_b_start = max(from_km_b, intersection_start - conflict_half_km)
            cp_km_b_end = min(to_km_b, intersection_end + conflict_half_km)
        else:
            # No intersection - use proportional zones around segment centers
            center_a = (from_km_a + to_km_a) / 2.0
            center_b = (from_km_b + to_km_b) / 2.0
            
            conflict_length_km = conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0
            
            cp_km_a_start = max(from_km_a, center_a - conflict_half_km)
            cp_km_a_end = min(to_km_a, center_a + conflict_half_km)
            
            cp_km_b_start = max(from_km_b, center_b - conflict_half_km)
            cp_km_b_end = min(to_km_b, center_b + conflict_half_km)

    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0

    # Reset index to prevent iloc[i] mismatch after DataFrame filtering
    df_a = df_a.reset_index(drop=True)
    df_b = df_b.reset_index(drop=True)

    # Vectorized times for conflict zone
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    time_enter_a = start_a + offset_a + pace_a * cp_km_a_start
    time_exit_a  = start_a + offset_a + pace_a * cp_km_a_end

    pace_b = df_b["pace"].values * 60.0
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    time_enter_b = start_b + offset_b + pace_b * cp_km_b_start
    time_exit_b  = start_b + offset_b + pace_b * cp_km_b_end

    # Track runners who overtake each other (true passes)
    a_bibs_overtakes = set()
    b_bibs_overtakes = set()
    # Track runners who have temporal overlap (co-presence)
    a_bibs_copresence = set()
    b_bibs_copresence = set()
    unique_pairs = set()

    # Issue #503: Vectorized temporal overlap detection using NumPy broadcasting
    # Convert to numpy arrays for vectorized operations
    time_enter_a_arr = np.array(time_enter_a)  # (n,)
    time_exit_a_arr = np.array(time_exit_a)     # (n,)
    time_enter_b_arr = np.array(time_enter_b)  # (m,)
    time_exit_b_arr = np.array(time_exit_b)    # (m,)
    
    # Broadcast to compute all pairwise overlaps: (n, 1) vs (1, m) = (n, m)
    enter_a_2d = time_enter_a_arr[:, np.newaxis]  # (n, 1)
    exit_a_2d = time_exit_a_arr[:, np.newaxis]    # (n, 1)
    enter_b_2d = time_enter_b_arr[np.newaxis, :]  # (1, m)
    exit_b_2d = time_exit_b_arr[np.newaxis, :]    # (1, m)
    
    # Compute overlap start/end/duration for all pairs
    overlap_start = np.maximum(enter_a_2d, enter_b_2d)  # (n, m)
    overlap_end = np.minimum(exit_a_2d, exit_b_2d)     # (n, m)
    overlap_duration = overlap_end - overlap_start     # (n, m)
    
    # Find pairs with sufficient temporal overlap
    has_sufficient_overlap = overlap_duration >= min_overlap_duration  # (n, m) boolean
    
    # TRUE PASS DETECTION: Check for temporal overlap AND directional change
    # This ensures we only count actual overtaking, not just co-presence
    # Iterate only over pairs with sufficient overlap (much fewer iterations)
    overlap_indices = np.argwhere(has_sufficient_overlap)  # (k, 2) array of [i, j] pairs
    
    for i, j in overlap_indices:
        enter_a = time_enter_a_arr[i]
        exit_a = time_exit_a_arr[i]
        enter_b = time_enter_b_arr[j]
        exit_b = time_exit_b_arr[j]
        
        # Calculate overlap duration (already computed, but recalc for clarity)
        overlap_dur = min(exit_a, exit_b) - max(enter_a, enter_b)
        
        if overlap_dur >= min_overlap_duration:
                # Temporal overlap detected - now check for directional change
                # Calculate arrival times at boundaries to detect passing
                # Use intersection boundaries if available, otherwise use conflict zone boundaries
                intersection_start = max(from_km_a, from_km_b)
                intersection_end = min(to_km_a, to_km_b)
                
                if intersection_start < intersection_end:
                    # Use intersection boundaries for fair comparison
                    boundary_start = intersection_start
                    boundary_end = intersection_end
                else:
                    # No intersection - use NORMALIZED CONFLICT ZONE for finish line convergence
                    # This handles cases like M1 where runners converge at the same physical location
                    # but have different absolute kilometer ranges
                    
                    # CORRECT APPROACH: 
                    # 1. Normalize each event's segment to 0.0-segment_length first
                    # 2. Calculate conflict zone in normalized space (e.g., 0.0-0.05 km for M1)
                    # 3. Compare runners at the same normalized position within their segments
                    
                    # Calculate conflict zone in NORMALIZED space (0.0 to segment_length)
                    # Use a fixed normalized conflict zone that works for both events
                    # For M1: segment_length = 0.25 km, so conflict zone should be 0.0-0.05 km
                    segment_length_a = to_km_a - from_km_a
                    segment_length_b = to_km_b - from_km_b
                    
                    # Use a small conflict zone (e.g., 20% of the shorter segment length)
                    conflict_zone_length = min(segment_length_a, segment_length_b) * 0.2
                    conflict_zone_norm_start = 0.0  # Start of conflict zone
                    conflict_zone_norm_end = conflict_zone_length  # End of conflict zone
                    
                    # Map normalized conflict zone to absolute coordinates for each event
                    abs_start_a = from_km_a + conflict_zone_norm_start
                    abs_end_a = from_km_a + conflict_zone_norm_end
                    abs_start_b = from_km_b + conflict_zone_norm_start
                    abs_end_b = from_km_b + conflict_zone_norm_end
                    
                    # Use the normalized conflict zone boundaries for directional change detection
                    # This ensures we're comparing runners at the same relative position within their segments
                    boundary_start = conflict_zone_norm_start  # Normalized start position (0.0)
                    boundary_end = conflict_zone_norm_end      # Normalized end position (0.05 for M1)
                
                pace_a = df_a.iloc[i]["pace"] * 60.0
                offset_a = df_a.iloc[i].get("start_offset", 0)
                pace_b = df_b.iloc[j]["pace"] * 60.0
                offset_b = df_b.iloc[j].get("start_offset", 0)
                
                if intersection_start < intersection_end:
                    # Use absolute coordinates for intersection-based segments
                    start_time_a = start_a + offset_a + pace_a * boundary_start
                    end_time_a = start_a + offset_a + pace_a * boundary_end
                    start_time_b = start_b + offset_b + pace_b * boundary_start
                    end_time_b = start_b + offset_b + pace_b * boundary_end
                else:
                    # Use NORMALIZED CONFLICT ZONE for finish line convergence
                    # Map normalized conflict zone boundaries to absolute coordinates for each event
                    # boundary_start = 0.0 (start of conflict zone)
                    # boundary_end = conflict_zone_length (end of conflict zone)
                    
                    # Map normalized conflict zone boundaries to absolute coordinates
                    abs_start_a = from_km_a + boundary_start  # from_km_a + 0.0
                    abs_end_a = from_km_a + boundary_end      # from_km_a + conflict_zone_length
                    abs_start_b = from_km_b + boundary_start  # from_km_b + 0.0
                    abs_end_b = from_km_b + boundary_end      # from_km_b + conflict_zone_length
                    
                    # Calculate arrival times at the conflict zone boundaries
                    start_time_a = start_a + offset_a + pace_a * abs_start_a
                    end_time_a = start_a + offset_a + pace_a * abs_end_a
                    start_time_b = start_b + offset_b + pace_b * abs_start_b
                    end_time_b = start_b + offset_b + pace_b * abs_end_b
                
                # Check for directional pass (true overtaking)
                # Runner A passes Runner B if A starts behind B but finishes ahead of B
                a_passes_b = (start_time_a > start_time_b and end_time_a < end_time_b)
                # Runner B passes Runner A if B starts behind A but finishes ahead of A
                b_passes_a = (start_time_b > start_time_a and end_time_b < end_time_a)
                
                # Get runner IDs for tracking
                a_bib = df_a.iloc[i]["runner_id"]
                b_bib = df_b.iloc[j]["runner_id"]
                
                # Check for temporal overlap (co-presence)
                temporal_overlap = (start_time_a < end_time_b and start_time_b < end_time_a)
                
                if temporal_overlap:
                    # Always count co-presence
                    a_bibs_copresence.add(a_bib)
                    b_bibs_copresence.add(b_bib)
                    
                    # Issue #552: Fix overtaking count logic - only count the runner who is actually overtaking
                    if a_passes_b:  # Runner A overtakes runner B
                        a_bibs_overtakes.add(a_bib)  # Only count A as overtaking
                    if b_passes_a:  # Runner B overtakes runner A
                        b_bibs_overtakes.add(b_bib)  # Only count B as overtaking
                    
                # Track unique pairs (ordered to avoid duplicates)
                unique_pairs.add((a_bib, b_bib))

    # Calculate participants involved (union of all runners who had encounters)
    all_a_bibs = a_bibs_overtakes.union(a_bibs_copresence)
    all_b_bibs = b_bibs_overtakes.union(b_bibs_copresence)
    participants_involved = len(all_a_bibs.union(all_b_bibs))
    unique_encounters = len(unique_pairs)

    # Return separate counts for true passes vs co-presence
    return (len(a_bibs_overtakes), len(b_bibs_overtakes), 
            len(a_bibs_copresence), len(b_bibs_copresence),
            list(a_bibs_overtakes), list(b_bibs_overtakes), 
            unique_encounters, participants_involved)


def calculate_convergence_zone_overlaps_binned(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    use_time_bins: bool = False,
    use_distance_bins: bool = False,
    overlap_duration_minutes: float = 0.0,
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """
    Calculate overtaking using binning for long segments.
    """
    if df_a.empty or df_b.empty:
        return 0, 0, 0, 0, [], [], 0, 0
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Track runners who overtake each other (true passes)
    a_bibs_overtakes = set()
    b_bibs_overtakes = set()
    # Track runners who have temporal overlap (co-presence)
    a_bibs_copresence = set()
    b_bibs_copresence = set()
    # Track unique encounters across all bins
    unique_encounters = 0
    
    if use_time_bins:
        # Create time bins (10-minute intervals)
        bin_duration_minutes = TEMPORAL_BINNING_THRESHOLD_MINUTES
        num_bins = max(1, int(overlap_duration_minutes / bin_duration_minutes))
        
        # Calculate overlap window
        df_a['entry_time'] = start_a + df_a['start_offset'] + df_a['pace'] * 60.0 * from_km_a
        df_a['exit_time'] = start_a + df_a['start_offset'] + df_a['pace'] * 60.0 * to_km_a
        df_b['entry_time'] = start_b + df_b['start_offset'] + df_b['pace'] * 60.0 * from_km_b
        df_b['exit_time'] = start_b + df_b['start_offset'] + df_b['pace'] * 60.0 * to_km_b
        
        overlap_start = max(df_a['entry_time'].min(), df_b['entry_time'].min())
        overlap_end = min(df_a['exit_time'].max(), df_b['exit_time'].max())
        
        for bin_idx in range(num_bins):
            bin_start = overlap_start + (bin_idx * bin_duration_minutes * 60)
            bin_end = min(overlap_start + ((bin_idx + 1) * bin_duration_minutes * 60), overlap_end)
            
            # Get runners active in this time bin
            a_in_bin = df_a[(df_a['entry_time'] <= bin_end) & (df_a['exit_time'] >= bin_start)]
            b_in_bin = df_b[(df_b['entry_time'] <= bin_end) & (df_b['exit_time'] >= bin_start)]
            
            # Calculate overtaking for this time bin using original method
            bin_overtakes_a, bin_overtakes_b, bin_copresence_a, bin_copresence_b, bin_bibs_a, bin_bibs_b, bin_encounters, bin_participants = calculate_convergence_zone_overlaps_original(
                a_in_bin, b_in_bin, event_a, event_b, start_times,
                cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
                min_overlap_duration, conflict_length_m
            )
            
            # Accumulate results
            a_bibs_overtakes.update(bin_bibs_a)
            b_bibs_overtakes.update(bin_bibs_b)
            a_bibs_copresence.update(bin_bibs_a)  # Co-presence includes all temporal overlaps
            b_bibs_copresence.update(bin_bibs_b)
            
            # FIX: Don't create Cartesian product - use the original algorithm's results
            # The original algorithm already calculated unique pairs correctly for this bin
            # We need to accumulate these unique pairs across all bins
            # Note: We can't just add bin_encounters because that would double-count pairs
            # that appear in multiple bins. Instead, we need to track the actual unique pairs.
            # For now, we'll use a simplified approach: use the original algorithm's unique_encounters
            # and add them to our running total (this is still not perfect but better than Cartesian product)
            unique_encounters += bin_encounters
    
    elif use_distance_bins:
        # Create distance bins (100m intervals)
        bin_size_km = DISTANCE_BIN_SIZE_KM  # 100m
        len_a = to_km_a - from_km_a
        len_b = to_km_b - from_km_b
        num_bins = max(1, int(min(len_a, len_b) / bin_size_km))
        
        for bin_idx in range(num_bins):
            bin_start_a = from_km_a + (bin_idx * bin_size_km)
            bin_end_a = min(from_km_a + ((bin_idx + 1) * bin_size_km), to_km_a)
            bin_start_b = from_km_b + (bin_idx * bin_size_km)
            bin_end_b = min(from_km_b + ((bin_idx + 1) * bin_size_km), to_km_b)
            
            # Calculate overtaking for this distance bin
            bin_overtakes_a, bin_overtakes_b, bin_copresence_a, bin_copresence_b, bin_bibs_a, bin_bibs_b, bin_encounters, bin_participants = calculate_convergence_zone_overlaps_original(
                df_a, df_b, event_a, event_b, start_times,
                cp_km, bin_start_a, bin_end_a, bin_start_b, bin_end_b,
                min_overlap_duration, conflict_length_m
            )
            
            # Accumulate results
            a_bibs_overtakes.update(bin_bibs_a)
            b_bibs_overtakes.update(bin_bibs_b)
            a_bibs_copresence.update(bin_bibs_a)  # Co-presence includes all temporal overlaps
            b_bibs_copresence.update(bin_bibs_b)
            
            # FIX: Don't create Cartesian product - use the original algorithm's results
            # The original algorithm already calculated unique pairs correctly for this bin
            # We need to accumulate these unique pairs across all bins
            # Note: We can't just add bin_encounters because that would double-count pairs
            # that appear in multiple bins. Instead, we need to track the actual unique pairs.
            # For now, we'll use a simplified approach: use the original algorithm's unique_encounters
            # and add them to our running total (this is still not perfect but better than Cartesian product)
            unique_encounters += bin_encounters
    
    # Calculate final results
    all_a_bibs = a_bibs_overtakes.union(a_bibs_copresence)
    all_b_bibs = b_bibs_overtakes.union(b_bibs_copresence)
    participants_involved = len(all_a_bibs.union(all_b_bibs))
    # unique_encounters is already calculated from bin accumulation
    
    # Return separate counts for true passes vs co-presence
    return (len(a_bibs_overtakes), len(b_bibs_overtakes), 
            len(a_bibs_copresence), len(b_bibs_copresence),
            list(a_bibs_overtakes), list(b_bibs_overtakes), 
            unique_encounters, participants_involved)


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


def generate_deep_dive_analysis(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    segment_label: str,
    flow_type: str = "overtake",
    prior_segment_id: str = None,
    prior_segment_data: Dict[str, Any] = None,
    current_segment_data: Dict[str, Any] = None,
) -> List[str]:
    """Generate comprehensive deep dive analysis for a segment."""
    if df_a.empty or df_b.empty:
        return ["❌ Deep Dive: No data available for analysis"]
    
    analysis = []
    analysis.append("🔍 DEEP DIVE ANALYSIS")
    analysis.append("=" * 40)
    
    # Basic segment information
    analysis.append(f"📍 Segment: {segment_label}")
    analysis.append(f"🔄 Flow Type: {flow_type}")
    analysis.append(f"🔍 Events: {event_a} vs {event_b}")
    analysis.append("")
    
    # Entry/exit times (already calculated)
    first_entry_a, last_exit_a, first_entry_b, last_exit_b, overlap_duration = calculate_entry_exit_times(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b
    )
    
    analysis.append("⏰ TIMING ANALYSIS:")
    analysis.append(f"   • {event_a} Entry/Exit: {first_entry_a} {last_exit_a}")
    analysis.append(f"   • {event_b} Entry/Exit: {first_entry_b} {last_exit_b}")
    analysis.append(f"   • Overlap Window Duration: {overlap_duration}")
    analysis.append("")
    
    # Runner characteristics
    analysis.append("👥 RUNNER CHARACTERISTICS:")
    
    # Event A characteristics
    pace_a = df_a["pace"].values
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    analysis.append(f"   • {event_a} Runners: {len(df_a)} total")
    analysis.append(f"     - Pace Range: {pace_a.min():.2f} - {pace_a.max():.2f} min/km")
    analysis.append(f"     - Pace Median: {np.median(pace_a):.2f} min/km")
    analysis.append(f"     - Start Offset Range: {offset_a.min():.0f} - {offset_a.max():.0f} seconds")
    analysis.append(f"     - Start Offset Median: {np.median(offset_a):.0f} seconds")
    
    # Event B characteristics
    pace_b = df_b["pace"].values
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    analysis.append(f"   • {event_b} Runners: {len(df_b)} total")
    analysis.append(f"     - Pace Range: {pace_b.min():.2f} - {pace_b.max():.2f} min/km")
    analysis.append(f"     - Pace Median: {np.median(pace_b):.2f} min/km")
    analysis.append(f"     - Start Offset Range: {offset_b.min():.0f} - {offset_b.max():.0f} seconds")
    analysis.append(f"     - Start Offset Median: {np.median(offset_b):.0f} seconds")
    analysis.append("")
    
    # Start offset analysis
    analysis.append("🚀 START OFFSET ANALYSIS:")
    analysis.append(f"   • {event_a} Start Time: {start_times.get(event_a, 0):.0f} minutes")
    analysis.append(f"   • {event_b} Start Time: {start_times.get(event_b, 0):.0f} minutes")
    analysis.append(f"   • Start Time Difference: {abs(start_times.get(event_a, 0) - start_times.get(event_b, 0)):.0f} minutes")
    
    # Calculate effective start times (including offsets)
    start_a_sec = start_times.get(event_a, 0) * 60.0
    start_b_sec = start_times.get(event_b, 0) * 60.0
    effective_start_a = start_a_sec + np.median(offset_a)
    effective_start_b = start_b_sec + np.median(offset_b)
    analysis.append(f"   • Effective Start Difference: {abs(effective_start_a - effective_start_b)/60:.1f} minutes")
    analysis.append("")
    
    # Contextual narrative summary
    analysis.append("📝 CONTEXTUAL SUMMARY:")
    
    # Determine interaction potential based on timing and pace
    time_diff = abs(effective_start_a - effective_start_b) / 60.0  # minutes
    pace_diff = abs(np.median(pace_a) - np.median(pace_b))
    
    if time_diff < 5:
        analysis.append("   • High interaction potential: Events start within 5 minutes")
    elif time_diff < 15:
        analysis.append("   • Moderate interaction potential: Events start within 15 minutes")
    else:
        analysis.append("   • Low interaction potential: Events start >15 minutes apart")
    
    from app.utils.constants import (
        PACE_SIMILAR_THRESHOLD,
        PACE_MODERATE_DIFFERENCE_THRESHOLD
    )
    
    if pace_diff < PACE_SIMILAR_THRESHOLD:
        analysis.append("   • Similar pace groups: Runners likely to stay together")
    elif pace_diff < PACE_MODERATE_DIFFERENCE_THRESHOLD:
        analysis.append("   • Moderate pace difference: Some overtaking expected")
    else:
        analysis.append("   • Large pace difference: Significant overtaking expected")
    
    # Overlap window analysis
    if overlap_duration != "N/A" and overlap_duration != "00:00":
        analysis.append(f"   • Active overlap period: {overlap_duration} when both events are present")
    else:
        analysis.append("   • No temporal overlap: Events do not share time in segment")
    
    analysis.append("")
    
    # Prior segment overlap analysis
    if prior_segment_id and prior_segment_data:
        analysis.append("🔗 PRIOR SEGMENT OVERLAP ANALYSIS:")
        analysis.append(f"   • Prior Segment: {prior_segment_id}")
        
        # Compare current segment with prior segment
        current_overtaking_a = current_segment_data.get('overtaking_a', 0) if current_segment_data else 0
        current_overtaking_b = current_segment_data.get('overtaking_b', 0) if current_segment_data else 0
        prior_overtaking_a = prior_segment_data.get('overtaking_a', 0)
        prior_overtaking_b = prior_segment_data.get('overtaking_b', 0)
        
        analysis.append(f"   • Current Segment Overtaking: {event_a}={current_overtaking_a}, {event_b}={current_overtaking_b}")
        analysis.append(f"   • Prior Segment Overtaking: {event_a}={prior_overtaking_a}, {event_b}={prior_overtaking_b}")
        
        # Calculate overlap counts and unique runners
        current_unique_encounters = current_segment_data.get('unique_encounters', 0) if current_segment_data else 0
        current_participants = current_segment_data.get('participants_involved', 0) if current_segment_data else 0
        prior_unique_encounters = prior_segment_data.get('unique_encounters', 0)
        prior_participants = prior_segment_data.get('participants_involved', 0)
        
        analysis.append(f"   • Current Unique Encounters: {current_unique_encounters}")
        analysis.append(f"   • Prior Unique Encounters: {prior_unique_encounters}")
        analysis.append(f"   • Current Participants: {current_participants}")
        analysis.append(f"   • Prior Participants: {prior_participants}")
        
        # Interaction pattern analysis
        if current_unique_encounters > prior_unique_encounters:
            analysis.append("   • Interaction Pattern: Increasing encounters from prior segment")
        elif current_unique_encounters < prior_unique_encounters:
            analysis.append("   • Interaction Pattern: Decreasing encounters from prior segment")
        else:
            analysis.append("   • Interaction Pattern: Similar encounter levels to prior segment")
        
        analysis.append("")
    
    return analysis


def convert_segments_new_to_flow_format(segments_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert segments_new.csv wide format to flow.csv long format.
    This is a minimal conversion to support the new schema.
    """
    converted_segments = []
    
    for _, segment in segments_df.iterrows():
        seg_id = segment['seg_id']
        
        # Get events that are present using utility function
        events = _get_segment_events(segment)
        
        # Generate all possible event pairs
        for i, event_a in enumerate(events):
            for event_b in events[i+1:]:
                # Create converted segment using utility function
                converted_segment = _create_converted_segment(segment, event_a, event_b)
                # Add additional fields not handled by utility function
                converted_segment.update({
                    "prior_segment_id": segment.get("prior_segment_id", ""),
                    "notes": segment.get("notes", "")
                })
                converted_segments.append(converted_segment)
    
    return pd.DataFrame(converted_segments)


def _calculate_dynamic_conflict_length(
    segment_length_km: float,
    from_km_a: float,
    to_km_a: float
) -> float:
    """Calculate dynamic conflict length based on segment length."""
    from app.utils.constants import (
        CONFLICT_LENGTH_LONG_SEGMENT_M,
        CONFLICT_LENGTH_MEDIUM_SEGMENT_M,
        CONFLICT_LENGTH_SHORT_SEGMENT_M,
        SEGMENT_LENGTH_LONG_THRESHOLD_KM,
        SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM
    )
    
    if segment_length_km > SEGMENT_LENGTH_LONG_THRESHOLD_KM:
        return CONFLICT_LENGTH_LONG_SEGMENT_M
    elif segment_length_km > SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM:
        return CONFLICT_LENGTH_MEDIUM_SEGMENT_M
    else:
        return CONFLICT_LENGTH_SHORT_SEGMENT_M


def _calculate_effective_convergence_point(
    cp_km: float,
    from_km_a: float,
    to_km_a: float
) -> float:
    """Calculate effective convergence point, using segment center if outside range."""
    if from_km_a <= cp_km <= to_km_a:
        return cp_km
    else:
        # Use segment center for segments with no intersection
        return (from_km_a + to_km_a) / 2.0


def _parse_overlap_duration_minutes(overlap_window_duration: Any) -> float:
    """Parse overlap window duration string or numeric value to minutes."""
    if isinstance(overlap_window_duration, str) and ':' in overlap_window_duration:
        parts = overlap_window_duration.split(':')
        if len(parts) == 2:  # MM:SS
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes + seconds / 60.0
        elif len(parts) == 3:  # HH:MM:SS
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 60 + minutes + seconds / 60.0
        else:
            return 0.0
    else:
        return overlap_window_duration / 60.0 if isinstance(overlap_window_duration, (int, float)) else 0.0


def _calculate_conflict_zone_boundaries(
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    dynamic_conflict_length_m: float
) -> Tuple[float, float]:
    """Calculate normalized conflict zone boundaries (0.0 to 1.0)."""
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    
    if from_km_a <= cp_km <= to_km_a:
        # Convergence point within Event A's range - use absolute approach
        s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
        s_cp, _ = clamp_normalized_fraction(s_cp, "convergence_point_")
        
        # Proportional tolerance: 5% of shorter segment, minimum 50m
        min_segment_len = min(len_a, len_b)
        proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)
        s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
        
        # Define normalized conflict zone boundaries
        s_start = max(0.0, s_cp - s_conflict_half)
        s_end = min(1.0, s_cp + s_conflict_half)
        
        # Ensure conflict zone has some width
        if s_end <= s_start:
            s_start = max(0.0, s_cp - 0.05)
            s_end = min(1.0, s_cp + 0.05)
        
        return s_start, s_end
    else:
        # Convergence point outside Event A's range - use normalized approach
        intersection_start = max(from_km_a, from_km_b)
        intersection_end = min(to_km_a, to_km_b)
        
        if intersection_start < intersection_end:
            # Use intersection boundaries
            intersection_start_norm = (intersection_start - from_km_a) / len_a
            intersection_end_norm = (intersection_end - from_km_a) / len_a
            conflict_length_km = dynamic_conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0 / len_a
            conflict_start = max(0.0, intersection_start_norm - conflict_half_km)
            conflict_end = min(1.0, intersection_end_norm + conflict_half_km)
            return conflict_start, conflict_end
        else:
            # Use segment center
            center_a_norm = 0.5
            conflict_length_km = dynamic_conflict_length_m / 1000.0
            conflict_half_km = conflict_length_km / 2.0 / len_a
            conflict_start = max(0.0, center_a_norm - conflict_half_km)
            conflict_end = min(1.0, center_a_norm + conflict_half_km)
            return conflict_start, conflict_end


def _apply_convergence_policy(
    conflict_start: Optional[float],
    conflict_end: Optional[float],
    copresence_a: int,
    copresence_b: int,
    overtakes_a: int,
    overtakes_b: int
) -> Dict[str, Any]:
    """Apply three-boolean convergence policy and return policy results."""
    # 1. spatial_zone_exists: convergence zones are calculated and non-empty
    spatial_zone_exists = conflict_start is not None and conflict_end is not None
    
    # 2. temporal_overlap_exists: any copresence detected
    temporal_overlap_exists = copresence_a > 0 or copresence_b > 0
    
    # 3. true_pass_exists: any overtaking counts
    true_pass_exists = overtakes_a > 0 or overtakes_b > 0
    
    # POLICY: has_convergence := spatial_zone_exists AND temporal_overlap_exists
    has_convergence_policy = spatial_zone_exists and temporal_overlap_exists
    
    # Determine reason code when has_convergence=True but no true passes
    no_pass_reason_code = None
    if has_convergence_policy and not true_pass_exists:
        no_pass_reason_code = "NO_DIRECTIONAL_CHANGE_OR_WINDOW_TOO_SHORT"
    elif spatial_zone_exists and not temporal_overlap_exists:
        no_pass_reason_code = "SPATIAL_ONLY_NO_TEMPORAL"
    
    return {
        "spatial_zone_exists": spatial_zone_exists,
        "temporal_overlap_exists": temporal_overlap_exists,
        "true_pass_exists": true_pass_exists,
        "has_convergence_policy": has_convergence_policy,
        "no_pass_reason_code": no_pass_reason_code
    }


def _process_segment_with_convergence(
    seg_id: str,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float,
    overlap_window_duration: Any,
    segment_start_time: float,
    segment_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a segment that has convergence, calculating overlaps, conflict zones, and policy.
    Returns updated segment_result dict with convergence data.
    """
    # Calculate dynamic conflict length
    segment_length_km = to_km_a - from_km_a
    dynamic_conflict_length_m = _calculate_dynamic_conflict_length(
        segment_length_km, from_km_a, to_km_a
    )
    
    # Calculate effective convergence point
    effective_cp_km = _calculate_effective_convergence_point(cp_km, from_km_a, to_km_a)
    
    # Parse overlap duration
    overlap_duration_minutes = _parse_overlap_duration_minutes(overlap_window_duration)
    
    # Calculate overlaps with binning
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps_with_binning(
        df_a, df_b, event_a, event_b, start_times,
        effective_cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
        min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
    )
    
    # Calculate execution time
    segment_elapsed_ms = int(1000 * (time.time() - segment_start_time))
    
    # Log structured statistics
    _log_flow_segment_stats(
        seg_id, event_a, event_b, "ORIGINAL",
        {
            "pairs_considered": len(df_a) * len(df_b),
            "pairs_overlapped_ge_threshold": unique_encounters,
            "passes_raw_a": overtakes_a,
            "passes_raw_b": overtakes_b,
            "copresence_a": copresence_a,
            "copresence_b": copresence_b,
            "unique_encounters": unique_encounters,
            "participants_involved": participants_involved,
            "min_overlap_sec": float(min_overlap_duration),
            "elapsed_ms": segment_elapsed_ms,
            "dataset_size_a": len(df_a),
            "dataset_size_b": len(df_b),
            "convergence_point": effective_cp_km,
            "conflict_length_m": dynamic_conflict_length_m
        }
    )
    
    # Special case debugging/logging
    _handle_special_case_debugging(
        seg_id, event_a, event_b, df_a, df_b, from_km_a, to_km_a, from_km_b, to_km_b,
        effective_cp_km, dynamic_conflict_length_m, overlap_duration_minutes,
        overtakes_a, overtakes_b, copresence_a, copresence_b, unique_encounters,
        participants_involved, cp_km, segment_result, overlap_window_duration,
        start_times, min_overlap_duration
    )
    
    # Apply validation and corrections (F1 specific)
    overtakes_a, overtakes_b, copresence_a, copresence_b = _apply_f1_validation_if_needed(
        seg_id, event_a, event_b, df_a, df_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m,
        overtakes_a, overtakes_b, copresence_a, copresence_b
    )
    
    # Log binning decisions
    use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
    use_distance_bins = dynamic_conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
    
    if use_time_bins or use_distance_bins:
        print(f"🔧 BINNING APPLIED to {seg_id}: time_bins={use_time_bins}, distance_bins={use_distance_bins}")
        print(f"   Overlap: {overlap_duration_minutes:.1f}min, Conflict: {dynamic_conflict_length_m:.0f}m")
    
    # Flag suspicious overtaking rates
    pct_a = overtakes_a / len(df_a) if len(df_a) > 0 else 0
    pct_b = overtakes_b / len(df_b) if len(df_b) > 0 else 0
    
    if pct_a > SUSPICIOUS_OVERTAKING_RATE_THRESHOLD or pct_b > SUSPICIOUS_OVERTAKING_RATE_THRESHOLD:
        if not (use_time_bins or use_distance_bins):
            print(f"⚠️  SUSPICIOUS OVERTAKING RATES in {seg_id}: {pct_a:.1%}, {pct_b:.1%} - NO BINNING APPLIED!")
        else:
            print(f"✅ High overtaking rates in {seg_id}: {pct_a:.1%}, {pct_b:.1%} - BINNING APPLIED")
    
    # Calculate conflict zone boundaries
    conflict_start, conflict_end = _calculate_conflict_zone_boundaries(
        cp_km, from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
    )
    
    # Apply convergence policy
    policy_results = _apply_convergence_policy(
        conflict_start, conflict_end, copresence_a, copresence_b, overtakes_a, overtakes_b
    )
    
    # Update segment result with policy
    segment_result["has_convergence"] = policy_results["has_convergence_policy"]
    segment_result.update({
        "spatial_zone_exists": policy_results["spatial_zone_exists"],
        "temporal_overlap_exists": policy_results["temporal_overlap_exists"],
        "true_pass_exists": policy_results["true_pass_exists"],
        "has_convergence_policy": policy_results["has_convergence_policy"],
        "no_pass_reason_code": policy_results["no_pass_reason_code"]
    })
    
    # Clear convergence_point if no convergence
    if not policy_results["has_convergence_policy"]:
        segment_result["convergence_point"] = None
        segment_result["convergence_point_fraction"] = None
    
    # Calculate overtaking loads
    try:
        result = calculate_overtaking_loads(
            df_a, df_b, event_a, event_b, start_times, cp_km,
            from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
        )
        if result is None:
            print(f"Warning: calculate_overtaking_loads returned None for segment {seg_id}")
            overtaking_loads_a, overtaking_loads_b, avg_load_a, avg_load_b, max_load_a, max_load_b = {}, {}, 0.0, 0.0, 0, 0
        else:
            overtaking_loads_a, overtaking_loads_b, avg_load_a, avg_load_b, max_load_a, max_load_b = result
    except Exception as e:
        print(f"Error in calculate_overtaking_loads for segment {seg_id}: {e}")
        overtaking_loads_a, overtaking_loads_b, avg_load_a, avg_load_b, max_load_a, max_load_b = {}, {}, 0.0, 0.0, 0, 0
    
    # Update segment result with all convergence data
    segment_result.update({
        "overtaking_a": overtakes_a,
        "overtaking_b": overtakes_b,
        "copresence_a": copresence_a,
        "copresence_b": copresence_b,
        "sample_a": bibs_a[:10],
        "sample_b": bibs_b[:10],
        "convergence_zone_start": conflict_start,
        "convergence_zone_end": conflict_end,
        "conflict_length_m": dynamic_conflict_length_m,
        "unique_encounters": unique_encounters,
        "participants_involved": participants_involved,
        "overtaking_load_a": round(avg_load_a, 1),
        "overtaking_load_b": round(avg_load_b, 1),
        "max_overtaking_load_a": max_load_a,
        "max_overtaking_load_b": max_load_b,
        "overtaking_load_distribution_a": list(overtaking_loads_a.values()),
        "overtaking_load_distribution_b": list(overtaking_loads_b.values())
    })
    
    return segment_result


def _handle_special_case_debugging(
    seg_id: str,
    event_a: str,
    event_b: str,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    effective_cp_km: float,
    dynamic_conflict_length_m: float,
    overlap_duration_minutes: float,
    overtakes_a: int,
    overtakes_b: int,
    copresence_a: int,
    copresence_b: int,
    unique_encounters: int,
    participants_involved: int,
    cp_km: Optional[float],
    segment_result: Dict[str, Any],
    overlap_window_duration: Any,
    start_times: Dict[str, float],
    min_overlap_duration: float
) -> None:
    """Handle special case debugging for M1, F1, B2/K1/L1 segments."""
    # M1 DETERMINISTIC TRACE LOGGING
    if seg_id == "M1" and event_a == "Half" and event_b == "10K":
        print(f"🔍 M1 Half vs 10K MAIN ANALYSIS TRACE:")
        print(f"  Input data: A={len(df_a)} runners, B={len(df_b)} runners")
        print(f"  Segment boundaries: A=[{from_km_a}, {to_km_a}], B=[{from_km_b}, {to_km_b}]")
        print(f"  Convergence point: {effective_cp_km} km")
        print(f"  Dynamic conflict length: {dynamic_conflict_length_m} m")
        print(f"  Overlap duration: {overlap_duration_minutes} min")
        print(f"  Raw calculation results: {overtakes_a}/{overtakes_b}")
        print(f"  Co-presence: {copresence_a}/{copresence_b}")
        print(f"  Unique encounters: {unique_encounters}")
        print(f"  Participants involved: {participants_involved}")
    
    # B2, K1, L1 CONVERGENCE ZONE DEBUGGING
    if seg_id in ["B2", "K1", "L1"] and cp_km is None:
        print(f"🔍 {seg_id} {event_a} vs {event_b} CONVERGENCE DEBUG:")
        print(f"  Segment ranges: {event_a} {from_km_a}-{to_km_a}km, {event_b} {from_km_b}-{to_km_b}km")
        print(f"  Convergence point: {cp_km}")
        print(f"  Has convergence: {segment_result.get('has_convergence', False)}")
        print(f"  Convergence zone: {segment_result.get('convergence_zone_start', 'N/A')}-{segment_result.get('convergence_zone_end', 'N/A')}")
        print(f"  Overtaking: {overtakes_a}, {overtakes_b}")
        
        intersection_start = max(from_km_a, from_km_b)
        intersection_end = min(to_km_a, to_km_b)
        has_intersection = intersection_start < intersection_end
        print(f"  Intersection: {intersection_start}-{intersection_end}km (has_intersection={has_intersection})")
        print(f"  Overlap window: {overlap_window_duration}")
        print(f"  Total runners: {len(df_a)} {event_a}, {len(df_b)} {event_b}")


def _apply_f1_validation_if_needed(
    seg_id: str,
    event_a: str,
    event_b: str,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    dynamic_conflict_length_m: float,
    overtakes_a: int,
    overtakes_b: int,
    copresence_a: int,
    copresence_b: int
) -> Tuple[int, int, int, int]:
    """Apply F1 per-runner validation if applicable, returning corrected values."""
    if seg_id == "F1" and event_a == "Half" and event_b == "10K":
        validation_results = validate_per_runner_entry_exit_f1(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
        )
        
        if "error" not in validation_results:
            main_a = overtakes_a
            main_b = overtakes_b
            val_a = validation_results["overtakes_a"]
            val_b = validation_results["overtakes_b"]
            
            if main_a != val_a or main_b != val_b:
                logging.warning(f"F1 {event_a} vs {event_b} DISCREPANCY DETECTED!")
                logging.warning(f"  Current calculation: {main_a} ({main_a/len(df_a)*100:.1f}%), {main_b} ({main_b/len(df_b)*100:.1f}%)")
                logging.warning(f"  Validation results:  {val_a} ({val_a/len(df_a)*100:.1f}%), {val_b} ({val_b/len(df_b)*100:.1f}%)")
                logging.warning(f"  Using validation results.")
                return val_a, val_b, validation_results["copresence_a"], validation_results["copresence_b"]
    
    return overtakes_a, overtakes_b, copresence_a, copresence_b


def analyze_temporal_flow_segments(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
) -> Dict[str, Any]:
    """
    Analyze all segments for temporal flow patterns.
    Supports overtake, merge, and diverge flow types.
    Processes ALL segments and calculates convergence for all segments with flow_type != 'none'.
    
    START TIMES REQUIREMENT: start_times must be offsets from midnight in minutes.
    Example: {'10K': 420, 'Half': 440, 'Full': 460} means 10K starts at 7:00 AM,
    Half at 7:20 AM, Full at 7:40 AM.
    """
    # Load data
    pace_df = load_pace_csv(pace_csv)
    segments_df = load_segments_csv(segments_csv)
    
    # Check if this is segments_new.csv format and convert if needed
    if '10K' in segments_df.columns and 'full' in segments_df.columns:
        # This is the new format, convert to old format
        all_segments = convert_segments_new_to_flow_format(segments_df)
    else:
        # This is the old format, use as-is
        all_segments = segments_df.copy()
    
    # Single-segment short-circuit for debugging (Step 5 of triage plan)
    from app.config_algo_consistency import FLAGS
    if FLAGS.SINGLE_SEGMENT_MODE:
        print(f"🔧 SINGLE-SEGMENT MODE: Processing only {FLAGS.SINGLE_SEGMENT_MODE}")
        all_segments = all_segments[all_segments['seg_id'] == FLAGS.SINGLE_SEGMENT_MODE]
        if all_segments.empty:
            print(f"⚠️ Segment {FLAGS.SINGLE_SEGMENT_MODE} not found, processing all segments")
    
    results = {
        "ok": True,
        "engine": "temporal_flow",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "start_times": start_times,
        "min_overlap_duration": min_overlap_duration,
        "conflict_length_m": conflict_length_m,
        "temporal_binning_threshold_minutes": TEMPORAL_BINNING_THRESHOLD_MINUTES,
        "spatial_binning_threshold_meters": SPATIAL_BINNING_THRESHOLD_METERS,
        "total_segments": len(all_segments),
        "segments_with_convergence": 0,
        "segments": []
    }
    
    for _, segment in all_segments.iterrows():
        seg_id = segment["seg_id"]
        event_a = segment["eventa"]
        event_b = segment["eventb"]
        from_km_a = segment["from_km_a"]
        to_km_a = segment["to_km_a"]
        from_km_b = segment["from_km_b"]
        to_km_b = segment["to_km_b"]
        
        # Start timing for this segment
        segment_start_time = time.time()
        
        # Skip segments where either event doesn't exist (NaN values)
        if pd.isna(from_km_a) or pd.isna(to_km_a) or pd.isna(from_km_b) or pd.isna(to_km_b):
            print(f"⚠️  Skipping {seg_id} {event_a} vs {event_b} - missing event data")
            continue
        
        # Filter runners for this segment
        df_a = pace_df[pace_df["event"] == event_a].copy()
        df_b = pace_df[pace_df["event"] == event_b].copy()
        
        # Issue #612: Calculate convergence points (multi-CP) - for all segments
        # NOTE: Segments may not show convergence if there are no temporal overlaps 
        # due to timing differences (e.g., A1, B1)
        convergence_points = calculate_convergence_points(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b
        )
        
        # Calculate entry/exit times for this segment
        first_entry_a, last_exit_a, first_entry_b, last_exit_b, overlap_window_duration = calculate_entry_exit_times(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b
        )
        
        # Get appropriate terminology for this flow type
        flow_type = segment.get("flow_type", "")
        terminology = get_flow_terminology(flow_type)
        
        # Issue #612: Multi-zone processing
        # Calculate dynamic conflict length
        segment_length_km = to_km_a - from_km_a
        dynamic_conflict_length_m = _calculate_dynamic_conflict_length(
            segment_length_km, from_km_a, to_km_a
        )
        
        # Parse overlap duration
        overlap_duration_minutes = _parse_overlap_duration_minutes(overlap_window_duration)
        
        # Build zones from convergence points
        zones = build_conflict_zones(
            convergence_points, from_km_a, to_km_a, from_km_b, to_km_b,
            dynamic_conflict_length_m
        )
        
        # Calculate metrics for all zones
        for zone in zones:
            zone_metrics = calculate_zone_metrics(
                zone, df_a, df_b, event_a, event_b, start_times,
                from_km_a, to_km_a, from_km_b, to_km_b,
                min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
            )
            zone.metrics = zone_metrics
        
        # Select worst zone
        worst_zone = select_worst_zone(zones) if zones else None
        
        # For backward compatibility, use worst zone's CP (or first CP, or None)
        cp_km = worst_zone.cp.km if worst_zone else (convergence_points[0].km if convergence_points else None)
        
        segment_result = {
            "seg_id": seg_id,
            "segment_label": segment.get("segment_label", ""),
            "flow_type": flow_type,
            "terminology": terminology,  # Add terminology dictionary
            "event_a": event_a,
            "event_b": event_b,
            "from_km_a": from_km_a,
            "to_km_a": to_km_a,
            "from_km_b": from_km_b,
            "to_km_b": to_km_b,
            "convergence_point": cp_km,  # Worst zone CP for backward compatibility
            "has_convergence": cp_km is not None,
            "total_a": len(df_a),
            "total_b": len(df_b),
            "overtaking_a": 0,
            "overtaking_b": 0,
            "sample_a": [],
            "sample_b": [],
            "first_entry_a": first_entry_a,
            "last_exit_a": last_exit_a,
            "first_entry_b": first_entry_b,
            "last_exit_b": last_exit_b,
            "overlap_window_duration": overlap_window_duration,
            "prior_segment_id": segment.get("prior_segment_id", "") if pd.notna(segment.get("prior_segment_id", "")) else "",
            # Issue #612: Multi-zone fields
            "convergence_points": convergence_points,  # List of ConvergencePoint objects
            "zones": zones,  # List of ConflictZone objects
            "worst_zone_index": worst_zone.zone_index if worst_zone else None,
            "worst_zone": worst_zone,  # Worst ConflictZone object
            # Issue #549: overtake_flag removed - not used in any logic or calculations
        }
        
        if cp_km is not None and worst_zone is not None:
            # Process segment with worst zone CP - handles policy, validation, loads
            segment_result = _process_segment_with_convergence(
                seg_id, df_a, df_b, event_a, event_b, start_times,
                cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
                min_overlap_duration, overlap_window_duration,
                segment_start_time, segment_result
            )
            # Override metrics with worst zone metrics (preserve policy, validation, loads from above)
            worst_metrics = worst_zone.metrics
            segment_result.update({
                "overtaking_a": worst_metrics.get("overtaking_a", 0),
                "overtaking_b": worst_metrics.get("overtaking_b", 0),
                "copresence_a": worst_metrics.get("copresence_a", 0),
                "copresence_b": worst_metrics.get("copresence_b", 0),
                "sample_a": worst_metrics.get("sample_a", [])[:10],
                "sample_b": worst_metrics.get("sample_b", [])[:10],
                "unique_encounters": worst_metrics.get("unique_encounters", 0),
                "participants_involved": worst_metrics.get("participants_involved", 0),
                "convergence_zone_start": worst_zone.zone_start_km_a,
                "convergence_zone_end": worst_zone.zone_end_km_a,
            })
            results["segments_with_convergence"] += 1
        
        results["segments"].append(segment_result)
    
    # Generate Deep Dive analysis for segments with flow_type != 'none' after all segments are processed
    for segment_result in results["segments"]:
        if segment_result.get("flow_type") != "none":
            # Find prior segment data if it exists
            prior_segment_id = segment_result.get("prior_segment_id")
            prior_segment_data = None
            if prior_segment_id:
                # Find the prior segment in the results
                for prev_segment in results["segments"]:
                    if prev_segment["seg_id"] == prior_segment_id:
                        prior_segment_data = prev_segment
                        break
            
            # Get the segment data from all_segments (converted format)
            seg_id = segment_result["seg_id"]
            segment_row = all_segments[all_segments["seg_id"] == seg_id].iloc[0]
            event_a = segment_row["eventa"]
            event_b = segment_row["eventb"]
            from_km_a = segment_row["from_km_a"]
            to_km_a = segment_row["to_km_a"]
            from_km_b = segment_row["from_km_b"]
            to_km_b = segment_row["to_km_b"]
            
            # Get the dataframes for this segment
            df_a = pace_df[pace_df["event"] == event_a].copy()
            df_b = pace_df[pace_df["event"] == event_b].copy()
            
            deep_dive = generate_deep_dive_analysis(
                df_a, df_b, event_a, event_b, start_times,
                from_km_a, to_km_a, from_km_b, to_km_b,
                segment_result.get("segment_label", seg_id),
                segment_result.get("flow_type", "overtake"),
                prior_segment_id,
                prior_segment_data,
                segment_result
            )
            segment_result["deep_dive_analysis"] = deep_dive
    
    return results


def generate_temporal_flow_narrative(results: Dict[str, Any]) -> str:
    """Generate human-readable narrative for temporal flow analysis."""
    if not results["ok"]:
        return "❌ Temporal flow analysis failed"
    
    narrative = []
    narrative.append("🎯 TEMPORAL FLOW ANALYSIS SUMMARY")
    narrative.append("=" * 50)
    narrative.append(f"🕐 Executed: {results['timestamp']}")
    narrative.append("")
    narrative.append("🚀 EVENT START TIMES:")
    for event, start_min in results["start_times"].items():
        hh = int(start_min // 60)
        mm = int(start_min % 60)
        narrative.append(f"   {event}: {hh:02d}:{mm:02d}:00")
    narrative.append("")
    narrative.append(f"📈 Total flow segments: {results['total_segments']}")
    narrative.append(f"🎯 Segments with convergence: {results['segments_with_convergence']}")
    narrative.append(f"⚙️ Analysis: {results['min_overlap_duration']}s min overlap duration")
    narrative.append(f"📏 Conflict length: {results['conflict_length_m']}m")
    narrative.append("")
    narrative.append("=" * 50)
    narrative.append("")
    
    for segment in results["segments"]:
        narrative.append(f"🏷️ Segment: {segment['seg_id']}")
        if segment.get("segment_label"):
            narrative.append(f"📝 Label: {segment['segment_label']}")
        if segment.get("flow_type"):
            narrative.append(f"🔄 Flow Type: {segment['flow_type']}")
        narrative.append(f"🔍 Checking {segment['event_a']} vs {segment['event_b']}")
        event_a = segment.get('event_a', 'A')
        event_b = segment.get('event_b', 'B')
        narrative.append(f"📍 {event_a}: {segment['total_a']} runners ({segment['from_km_a']}km to {segment['to_km_a']}km)")
        narrative.append(f"📍 {event_b}: {segment['total_b']} runners ({segment['from_km_b']}km to {segment['to_km_b']}km)")
        
        # Add entry/exit times in combined format
        narrative.append(f"⏰ {event_a} Entry/Exit: {segment.get('first_entry_a', 'N/A')} {segment.get('last_exit_a', 'N/A')}")
        narrative.append(f"⏰ {event_b} Entry/Exit: {segment.get('first_entry_b', 'N/A')} {segment.get('last_exit_b', 'N/A')}")
        narrative.append(f"🔄 Overlap Window Duration: {segment.get('overlap_window_duration', 'N/A')}")
        
        if segment["has_convergence"]:
            flow_type = segment.get("flow_type", "overtake")
            # Calculate event-specific distances for the convergence point
            cp_km = segment['convergence_point']
            from_km_a = segment.get('from_km_a', 0)
            to_km_a = segment.get('to_km_a', 0)
            from_km_b = segment.get('from_km_b', 0)
            to_km_b = segment.get('to_km_b', 0)
            
            # Calculate position within segment (0.0 to 1.0)
            len_a = to_km_a - from_km_a
            len_b = to_km_b - from_km_b
            s_cp = (cp_km - from_km_a) / max(len_a, 1e-9) if len_a > 0 else 0.0
            s_cp, clamp_reason = clamp_normalized_fraction(s_cp, "convergence_point_")
            
            # Calculate event B distance at convergence point
            cp_km_b = from_km_b + s_cp * len_b
            
            # Format: Convergence Point: fraction=[position within segment] (km=[total distance Event A], [total distance Event B])
            event_a = segment.get('event_a', 'A')
            event_b = segment.get('event_b', 'B')
            narrative.append(f"🎯 Convergence Point: fraction={s_cp:.2f} (A), km={cp_km:.1f} ({event_a}), {cp_km_b:.1f} ({event_b})")
            
            # Flow type specific reporting using utility function
            flow_analysis = _generate_flow_type_analysis(segment, flow_type)
            narrative.extend(flow_analysis)
            
            narrative.append(f"🏃‍♂️ Sample {segment['event_a']}: {format_bib_range(segment['sample_a'])}")
            narrative.append(f"🏃‍♂️ Sample {segment['event_b']}: {format_bib_range(segment['sample_b'])}")
        else:
            narrative.append("❌ No convergence zone detected")
        
        # Add Deep Dive analysis for all segments with flow_type != 'none'
        if segment.get("deep_dive_analysis"):
            narrative.extend(segment["deep_dive_analysis"])
        
        narrative.append("")
    
    return "\n".join(narrative)


def analyze_distance_progression(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    step_km: float = DEFAULT_STEP_KM,
) -> Dict[str, Any]:
    """
    Analyze runner distribution over distance within a segment.
    Returns distance bins with runner counts for each event.
    """
    if df_a.empty or df_b.empty:
        return {"ok": False, "error": "Empty dataframes"}
    
    # Calculate segment lengths
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return {"ok": False, "error": "Invalid segment lengths"}
    
    # Create distance bins
    min_km = min(from_km_a, from_km_b)
    max_km = max(to_km_a, to_km_b)
    distance_bins = []
    current_km = min_km
    while current_km <= max_km:
        distance_bins.append(round(current_km, 3))
        current_km += step_km
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate runner positions at each distance bin
    progression_data = []
    
    for bin_km in distance_bins:
        # Check if this distance is within each event's segment
        in_segment_a = from_km_a <= bin_km <= to_km_a
        in_segment_b = from_km_b <= bin_km <= to_km_b
        
        # Count runners from each event at this distance
        count_a = 0
        count_b = 0
        
        if in_segment_a and not df_a.empty:
            # Calculate arrival times for event A runners at this distance
            pace_a = df_a["pace"].values * 60.0  # sec per km
            offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
            arrival_times_a = start_a + offset_a + pace_a * bin_km
            count_a = len(arrival_times_a)
        
        if in_segment_b and not df_b.empty:
            # Calculate arrival times for event B runners at this distance
            pace_b = df_b["pace"].values * 60.0  # sec per km
            offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
            arrival_times_b = start_b + offset_b + pace_b * bin_km
            count_b = len(arrival_times_b)
        
        progression_data.append({
            "distance_km": bin_km,
            "count_a": count_a,
            "count_b": count_b,
            "total_count": count_a + count_b,
            "in_segment_a": in_segment_a,
            "in_segment_b": in_segment_b
        })
    
    return {
        "ok": True,
        "event_a": event_a,
        "event_b": event_b,
        "from_km_a": from_km_a,
        "to_km_a": to_km_a,
        "from_km_b": from_km_b,
        "to_km_b": to_km_b,
        "step_km": step_km,
        "progression_data": progression_data
    }


def generate_distance_progression_chart(progression_data: Dict[str, Any]) -> str:
    """
    Generate a text-based distance progression chart.
    """
    if not progression_data["ok"]:
        return f"❌ Distance progression analysis failed: {progression_data.get('error', 'Unknown error')}"
    
    chart = []
    chart.append("📊 DISTANCE PROGRESSION CHART")
    chart.append("=" * 60)
    chart.append(f"🔍 {progression_data['event_a']} vs {progression_data['event_b']}")
    event_a = progression_data.get('event_a', 'A')
    event_b = progression_data.get('event_b', 'B')
    chart.append(f"📍 {event_a}: {progression_data['total_a']} runners ({progression_data['from_km_a']}km to {progression_data['to_km_a']}km)")
    chart.append(f"📍 {event_b}: {progression_data['total_b']} runners ({progression_data['from_km_b']}km to {progression_data['to_km_b']}km)")
    chart.append(f"📏 Step size: {progression_data['step_km']}km")
    chart.append("")
    
    # Find max count for scaling
    max_count = max([d["total_count"] for d in progression_data["progression_data"]])
    if max_count == 0:
        chart.append("No runners found in segment")
        return "\n".join(chart)
    
    # Create chart
    chart.append("Distance(km) | A Count | B Count | Total | Chart")
    chart.append("-" * 60)
    
    for data in progression_data["progression_data"]:
        distance = data["distance_km"]
        count_a = data["count_a"]
        count_b = data["count_b"]
        total = data["total_count"]
        
        # Create simple bar chart
        bar_length = int((total / max_count) * 20) if max_count > 0 else 0
        bar = "█" * bar_length
        
        # Add segment indicators
        segment_indicator = ""
        if data["in_segment_a"] and data["in_segment_b"]:
            segment_indicator = " [A+B]"
        elif data["in_segment_a"]:
            segment_indicator = " [A]"
        elif data["in_segment_b"]:
            segment_indicator = " [B]"
        
        chart.append(f"{distance:8.2f}km | {count_a:7d} | {count_b:7d} | {total:5d} | {bar}{segment_indicator}")
    
    chart.append("")
    chart.append("Legend: [A] = Event A only, [B] = Event B only, [A+B] = Both events")
    
    return "\n".join(chart)


def calculate_tot_metrics(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    thresholds: List[int] = DEFAULT_TOT_THRESHOLDS,
    time_bin_seconds: int = DEFAULT_TIME_BIN_SECONDS,
) -> Dict[str, Any]:
    """
    Calculate Time-Over-Threshold (TOT) metrics for operational planning.
    Returns periods when runner counts exceed specified thresholds.
    """
    if df_a.empty or df_b.empty:
        return {"ok": False, "error": "Empty dataframes"}
    
    # Calculate segment lengths
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    if len_a <= 0 or len_b <= 0:
        return {"ok": False, "error": "Invalid segment lengths"}
    
    # Calculate conflict zone boundaries
    conflict_length_km = conflict_length_m / 1000.0
    conflict_half_km = conflict_length_km / 2.0
    
    cp_km_a_start = max(from_km_a, cp_km - conflict_half_km)
    cp_km_a_end = min(to_km_a, cp_km + conflict_half_km)
    
    # Map to local fractions
    s_start = (cp_km_a_start - from_km_a) / max(len_a, 1e-9)
    s_end = (cp_km_a_end - from_km_a) / max(len_a, 1e-9)
    s_start, _ = clamp_normalized_fraction(s_start, "conflict_zone_start_")
    s_end, _ = clamp_normalized_fraction(s_end, "conflict_zone_end_")
    
    # Convert to each event's km
    cp_km_a_start = from_km_a + s_start * len_a
    cp_km_a_end = from_km_a + s_end * len_a
    
    cp_km_b_start = from_km_b + s_start * len_b
    cp_km_b_end = from_km_b + s_end * len_b
    
    # Get start times
    start_a = start_times.get(event_a, 0) * 60.0
    start_b = start_times.get(event_b, 0) * 60.0
    
    # Calculate arrival times for all runners in conflict zone
    pace_a = df_a["pace"].values * 60.0  # sec per km
    offset_a = df_a.get("start_offset", pd.Series([0]*len(df_a))).fillna(0).values.astype(float)
    time_enter_a = start_a + offset_a + pace_a * cp_km_a_start
    time_exit_a = start_a + offset_a + pace_a * cp_km_a_end
    
    pace_b = df_b["pace"].values * 60.0
    offset_b = df_b.get("start_offset", pd.Series([0]*len(df_b))).fillna(0).values.astype(float)
    time_enter_b = start_b + offset_b + pace_b * cp_km_b_start
    time_exit_b = start_b + offset_b + pace_b * cp_km_b_end
    
    # Find time range
    all_times = list(time_enter_a) + list(time_exit_a) + list(time_enter_b) + list(time_exit_b)
    min_time = min(all_times)
    max_time = max(all_times)
    
    # Create time bins
    time_bins = []
    current_time = min_time
    while current_time <= max_time:
        time_bins.append(current_time)
        current_time += time_bin_seconds
    
    # Calculate runner counts in each time bin
    bin_data = []
    for bin_time in time_bins:
        # Count runners from each event in conflict zone at this time
        count_a = sum((time_enter_a <= bin_time) & (time_exit_a >= bin_time))
        count_b = sum((time_enter_b <= bin_time) & (time_exit_b >= bin_time))
        total_count = count_a + count_b
        
        bin_data.append({
            "time_seconds": bin_time,
            "time_minutes": bin_time / 60.0,
            "count_a": count_a,
            "count_b": count_b,
            "total_count": total_count
        })
    
    # Calculate TOT metrics for each threshold
    tot_metrics = {}
    for threshold in thresholds:
        tot_periods = []
        in_threshold = False
        period_start = None
        
        for bin_data_point in bin_data:
            if bin_data_point["total_count"] >= threshold:
                if not in_threshold:
                    in_threshold = True
                    period_start = bin_data_point["time_seconds"]
            else:
                if in_threshold:
                    in_threshold = False
                    period_end = bin_data_point["time_seconds"]
                    tot_periods.append({
                        "start_seconds": period_start,
                        "end_seconds": period_end,
                        "start_minutes": period_start / 60.0,
                        "end_minutes": period_end / 60.0,
                        "duration_seconds": period_end - period_start,
                        "duration_minutes": (period_end - period_start) / 60.0
                    })
        
        # Handle case where period extends to end
        if in_threshold:
            period_end = max_time
            tot_periods.append({
                "start_seconds": period_start,
                "end_seconds": period_end,
                "start_minutes": period_start / 60.0,
                "end_minutes": period_end / 60.0,
                "duration_seconds": period_end - period_start,
                "duration_minutes": (period_end - period_start) / 60.0
            })
        
        # Calculate total TOT time
        total_tot_seconds = sum([p["duration_seconds"] for p in tot_periods])
        total_tot_minutes = total_tot_seconds / 60.0
        
        tot_metrics[f"threshold_{threshold}"] = {
            "threshold": threshold,
            "periods": tot_periods,
            "total_periods": len(tot_periods),
            "total_tot_seconds": total_tot_seconds,
            "total_tot_minutes": total_tot_minutes,
            "total_tot_percentage": (total_tot_seconds / (max_time - min_time)) * 100 if max_time > min_time else 0
        }
    
    return {
        "ok": True,
        "event_a": event_a,
        "event_b": event_b,
        "conflict_zone_start": cp_km_a_start,
        "conflict_zone_end": cp_km_a_end,
        "conflict_length_m": conflict_length_m,
        "time_range_seconds": max_time - min_time,
        "time_range_minutes": (max_time - min_time) / 60.0,
        "time_bin_seconds": time_bin_seconds,
        "thresholds": thresholds,
        "bin_data": bin_data,
        "tot_metrics": tot_metrics
    }


def generate_tot_report(tot_data: Dict[str, Any]) -> str:
    """
    Generate a text-based TOT metrics report.
    """
    if not tot_data["ok"]:
        return f"❌ TOT analysis failed: {tot_data.get('error', 'Unknown error')}"
    
    report = []
    report.append("⏱️ TIME-OVER-THRESHOLD (TOT) METRICS")
    report.append("=" * 60)
    report.append(f"🔍 {tot_data['event_a']} vs {tot_data['event_b']}")
    report.append(f"📏 Conflict Length: {tot_data['conflict_length_m']}m")
    report.append(f"⏰ Time Range: {tot_data['time_range_minutes']:.1f} minutes")
    report.append(f"📊 Time Bin Size: {tot_data['time_bin_seconds']} seconds")
    report.append("")
    
    # Summary table
    report.append("📈 TOT SUMMARY")
    report.append("-" * 60)
    report.append("Threshold | Periods | Total TOT | TOT %")
    report.append("-" * 60)
    
    for threshold in tot_data["thresholds"]:
        metric = tot_data["tot_metrics"][f"threshold_{threshold}"]
        report.append(f"{threshold:9d} | {metric['total_periods']:7d} | {metric['total_tot_minutes']:8.1f}m | {metric['total_tot_percentage']:5.1f}%")
    
    report.append("")
    
    # Detailed periods for each threshold
    for threshold in tot_data["thresholds"]:
        metric = tot_data["tot_metrics"][f"threshold_{threshold}"]
        if metric["total_periods"] > 0:
            report.append(f"🚨 THRESHOLD {threshold} RUNNERS - {metric['total_periods']} PERIODS")
            report.append("-" * 40)
            for i, period in enumerate(metric["periods"], 1):
                start_time = f"{int(period['start_minutes']//60):02d}:{int(period['start_minutes']%60):02d}"
                end_time = f"{int(period['end_minutes']//60):02d}:{int(period['end_minutes']%60):02d}"
                report.append(f"  {i:2d}. {start_time} - {end_time} ({period['duration_minutes']:.1f}m)")
            report.append("")
    
    return "\n".join(report)


def _extract_segment_parameters_from_new_format(segment: Dict[str, Any], event_a: str, event_b: str) -> Tuple[float, float, float, float]:
    """
    Extract segment parameters (from_km_a, to_km_a, from_km_b, to_km_b) from new format segments CSV.
    
    Issue #548 Bug 1: Handle both lowercase and capitalized event names for backward compatibility.
    """
    # Normalize event names to lowercase for consistent matching
    event_a_lower = event_a.lower()
    event_b_lower = event_b.lower()
    
    # Extract parameters for event_a
    if event_a_lower == "full":
        from_km_a = segment.get('full_from_km', 0)
        to_km_a = segment.get('full_to_km', 0)
    elif event_a_lower == "half":
        from_km_a = segment.get('half_from_km', 0)
        to_km_a = segment.get('half_to_km', 0)
    elif event_a_lower == "10k":
        # Issue #548 Bug 1: Use lowercase '10k' to match CSV column names
        from_km_a = segment.get('10k_from_km', 0) or segment.get('10K_from_km', 0)
        to_km_a = segment.get('10k_to_km', 0) or segment.get('10K_to_km', 0)
    elif event_a_lower == "elite":
        from_km_a = segment.get('elite_from_km', 0)
        to_km_a = segment.get('elite_to_km', 0)
    elif event_a_lower == "open":
        from_km_a = segment.get('open_from_km', 0)
        to_km_a = segment.get('open_to_km', 0)
    else:
        raise ValueError(f"Unsupported event type: {event_a}")
    
    # Extract parameters for event_b
    if event_b_lower == "full":
        from_km_b = segment.get('full_from_km', 0)
        to_km_b = segment.get('full_to_km', 0)
    elif event_b_lower == "half":
        from_km_b = segment.get('half_from_km', 0)
        to_km_b = segment.get('half_to_km', 0)
    elif event_b_lower == "10k":
        # Issue #548 Bug 1: Use lowercase '10k' to match CSV column names
        from_km_b = segment.get('10k_from_km', 0) or segment.get('10K_from_km', 0)
        to_km_b = segment.get('10k_to_km', 0) or segment.get('10K_to_km', 0)
    elif event_b_lower == "elite":
        from_km_b = segment.get('elite_from_km', 0)
        to_km_b = segment.get('elite_to_km', 0)
    elif event_b_lower == "open":
        from_km_b = segment.get('open_from_km', 0)
        to_km_b = segment.get('open_to_km', 0)
    else:
        raise ValueError(f"Unsupported event type: {event_b}")
    
    return from_km_a, to_km_a, from_km_b, to_km_b


def _calculate_conflict_zone_for_audit(
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float
) -> Tuple[Optional[float], Optional[float]]:
    """Calculate conflict zone boundaries (normalized 0.0-1.0) for audit, following main analysis logic."""
    if cp_km is None:
        return None, None
    
    # Check if convergence point is within Event A's range
    if from_km_a <= cp_km <= to_km_a:
        # Calculate normalized convergence zone around the convergence point
        len_a = to_km_a - from_km_a
        len_b = to_km_b - from_km_b
        s_cp = (cp_km - from_km_a) / len_a  # Normalized position of convergence point
        
        # Use proportional tolerance approach (same as Main Analysis)
        min_segment_len = min(len_a, len_b)
        proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)
        s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
        
        s_start = max(0.0, s_cp - s_conflict_half)
        s_end = min(1.0, s_cp + s_conflict_half)
        
        # Ensure conflict zone has some width
        if s_end <= s_start:
            s_start = max(0.0, s_cp - 0.05)
            s_end = min(1.0, s_cp + 0.05)
        
        return s_start, s_end
    else:
        # Convergence point is outside Event A's range - use segment center
        len_a = to_km_a - from_km_a
        len_b = to_km_b - from_km_b
        center_a_norm = 0.5
        
        min_segment_len = min(len_a, len_b)
        proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)
        s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
        
        conflict_start = max(0.0, center_a_norm - s_conflict_half)
        conflict_end = min(1.0, center_a_norm + s_conflict_half)
        
        return conflict_start, conflict_end


def _calculate_audit_overlaps(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_a: str,
    event_b: str,
    start_times: Dict[str, float],
    cp_km: float,
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    min_overlap_duration: float,
    dynamic_conflict_length_m: float,
    overlap_duration_minutes: float
) -> Tuple[int, int, int, int, List[str], List[str], int, int]:
    """Calculate overlaps and overtakes for audit, handling special case debugging."""
    effective_cp_km = cp_km
    
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps_with_binning(
        df_a, df_b, event_a, event_b, start_times,
        effective_cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
        min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
    )
    
    return overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved


def _apply_audit_validation(
    seg_id: str,
    event_a: str,
    event_b: str,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    dynamic_conflict_length_m: float,
    overtakes_a: int,
    overtakes_b: int,
    copresence_a: int,
    copresence_b: int
) -> Tuple[int, int, int, int]:
    """Apply F1 validation if applicable and return corrected values."""
    if seg_id == "F1" and event_a == "Half" and event_b == "10K":
        validation_results = validate_per_runner_entry_exit_f1(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
        )
        
        if "error" not in validation_results:
            main_a = overtakes_a
            main_b = overtakes_b
            val_a = validation_results["overtakes_a"]
            val_b = validation_results["overtakes_b"]
            
            if main_a != val_a or main_b != val_b:
                print(f"🔍 F1 Half vs 10K FLOW RUNNER VALIDATION:")
                print(f"  Main calculation: {main_a}/{main_b}")
                print(f"  Validation results: {val_a}/{val_b}")
                print(f"  Using validation results.")
                
                return val_a, val_b, validation_results["copresence_a"], validation_results["copresence_b"]
    
    return overtakes_a, overtakes_b, copresence_a, copresence_b


def _generate_runner_audit_for_segment(
    seg_id: str,
    segment: Dict[str, Any],
    event_a: str,
    event_b: str,
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    start_times: Dict[str, float],
    from_km_a: float,
    to_km_a: float,
    from_km_b: float,
    to_km_b: float,
    conflict_start: Optional[float],
    conflict_end: Optional[float],
    conflict_length_m: float,
    output_dir: str
) -> Optional[Tuple[pd.DataFrame, Dict[str, int]]]:
    """
    Generate runner-level audit for a segment, returning DataFrame and stats or None on failure.
    
    Issue #607: Refactored to return DataFrame instead of file paths.
    """
    from datetime import datetime
    
    try:
        # Extract runner timing data (returns DataFrames)
        runner_data = extract_runner_timing_data_for_audit(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b, output_dir
        )
        print(f"  📊 Runner timing data extracted: {runner_data['runners_a_count']} {event_a}, {runner_data['runners_b_count']} {event_b}")
        
        # Generate runner audit (returns DataFrame and stats)
        run_id = f"{datetime.now().strftime('%Y-%m-%dT%H:%M')}Z"
        audit_df, stats = emit_runner_audit(
            event_a_data=runner_data['event_a_data'],
            event_b_data=runner_data['event_b_data'],
            run_id=run_id,
            seg_id=seg_id,
            segment_label=segment.get('segment_label', ''),
            flow_type=segment.get('flow_type', 'overtake'),
            event_a_name=event_a,
            event_b_name=event_b,
            convergence_zone_start=conflict_start,
            convergence_zone_end=conflict_end,
            zone_width_m=conflict_length_m,
            binning_applied=True,
            binning_mode="time",
            strict_min_dwell=5,
            strict_margin=2,
            from_km_a=from_km_a,  # Issue #607: Pass segment ranges for conflict zone calculation
            to_km_a=to_km_a,
            from_km_b=from_km_b,
            to_km_b=to_km_b
        )
        
        print(f"  📊 Runner audit generated:")
        print(f"    - Rows: {len(audit_df)}")
        print(f"    - Stats: {stats['overlapped_pairs']} overlaps, {stats['raw_pass']} raw passes, {stats['strict_pass']} strict passes")
        
        # STRICT-FIRST PUBLICATION RULE (Phase 2 Fix)
        audit_strict_passes = stats.get('strict_pass', 0)
        audit_raw_passes = stats.get('raw_pass', 0)
        
        print(f"🔍 STRICT-FIRST RULE APPLIED for {seg_id} {event_a} vs {event_b}:")
        print(f"  Audit generation: {audit_strict_passes} strict, {audit_raw_passes} raw")
        print(f"  Using main calculation results (authoritative)")
        
        return audit_df, stats
        
    except Exception as e:
        print(f"  ⚠️ Runner audit generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_flow_audit_for_segment(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    seg_id: str,
    event_a: str,
    event_b: str,
    min_overlap_duration: float = DEFAULT_MIN_OVERLAP_DURATION,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    output_dir: str = "reports"
) -> Dict[str, Any]:
    """
    Generate Flow Audit for a specific segment and event pair.
    
    This function extracts the Flow Audit logic from the main analysis
    and makes it available as a standalone API endpoint.
    """
    import pandas as pd
    from datetime import datetime
    
    print(f"🔍 GENERATING FLOW AUDIT FOR {seg_id} {event_a} vs {event_b}")
    
    # Load data
    df = pd.read_csv(pace_csv)
    segments_df = pd.read_csv(segments_csv)
    
    # Find the specific segment
    segment_row = segments_df[segments_df['seg_id'] == seg_id]
    
    if segment_row.empty:
        raise ValueError(f"Segment {seg_id} not found in segments CSV")
    
    segment = segment_row.iloc[0].to_dict()
    
    # Extract segment parameters - extracted to helper function to reduce complexity
    from_km_a, to_km_a, from_km_b, to_km_b = _extract_segment_parameters_from_new_format(segment, event_a, event_b)
    
    # Filter data for the specific events
    df_a = df[df['event'] == event_a].copy()
    df_b = df[df['event'] == event_b].copy()
    
    if df_a.empty or df_b.empty:
        raise ValueError(f"No data found for {event_a} or {event_b} events")
    
    print(f"  📊 Data loaded: {len(df_a)} {event_a} runners, {len(df_b)} {event_b} runners")
    
    # Issue #612: Calculate convergence points (multi-CP)
    convergence_points = calculate_convergence_points(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b
    )
    
    # For backward compatibility, use first CP (or None if no CPs)
    cp_km = convergence_points[0].km if convergence_points else None
    
    if cp_km is None:
        return {
            "error": f"No convergence point found for {seg_id} {event_a} vs {event_b}",
            "segment_id": seg_id,
            "event_a": event_a,
            "event_b": event_b
        }
    
    # Calculate conflict zone - extracted to helper function to reduce complexity
    conflict_start, conflict_end = _calculate_conflict_zone_for_audit(
        cp_km, from_km_a, to_km_a, from_km_b, to_km_b
    )
    
    # Calculate overlap duration dynamically
    first_entry_a, last_exit_a, first_entry_b, last_exit_b, overlap_window_duration = calculate_entry_exit_times(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b
    )
    
    # Parse overlap duration - reuse helper from analyze_temporal_flow_segments refactoring
    overlap_duration_minutes = _parse_overlap_duration_minutes(overlap_window_duration)
    
    # Calculate dynamic conflict length - reuse helper from analyze_temporal_flow_segments refactoring
    try:
        from app.utils.constants import (
            CONFLICT_LENGTH_LONG_SEGMENT_M,
            CONFLICT_LENGTH_MEDIUM_SEGMENT_M, 
            CONFLICT_LENGTH_SHORT_SEGMENT_M,
            SEGMENT_LENGTH_LONG_THRESHOLD_KM,
            SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM
        )
        
        segment_length_km = to_km_a - from_km_a
        dynamic_conflict_length_m = _calculate_dynamic_conflict_length(segment_length_km, from_km_a, to_km_a)
    except ImportError:
        dynamic_conflict_length_m = conflict_length_m
    
    # Calculate overlaps - extracted to helper function to reduce complexity
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = _calculate_audit_overlaps(
        df_a, df_b, event_a, event_b, start_times,
        cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
        min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
    )
    
    # Special case debugging for M1
    if seg_id == "M1" and event_a == "Half" and event_b == "10K":
        print(f"🔍 M1 Half vs 10K FLOW RUNNER TRACE:")
        print(f"  Input data: A={len(df_a)} runners, B={len(df_b)} runners")
        print(f"  Segment boundaries: A=[{from_km_a}, {to_km_a}], B=[{from_km_b}, {to_km_b}]")
        print(f"  Convergence point: {cp_km} km")
        print(f"  Dynamic conflict length: {dynamic_conflict_length_m} m")
        print(f"  Overlap duration: {overlap_duration_minutes} min")
        print(f"  Raw calculation results: {overtakes_a}/{overtakes_b}")
        print(f"  Co-presence: {copresence_a}/{copresence_b}")
        print(f"  Unique encounters: {unique_encounters}")
        print(f"  Participants involved: {participants_involved}")
    
    # Apply validation and corrections - extracted to helper function to reduce complexity
    overtakes_a, overtakes_b, copresence_a, copresence_b = _apply_audit_validation(
        seg_id, event_a, event_b, df_a, df_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m,
        overtakes_a, overtakes_b, copresence_a, copresence_b
    )
    
    # Generate Flow Audit data
    print(f"🔍 {seg_id} {event_a} vs {event_b} FLOW AUDIT DATA GENERATION:")
    
    # Calculate convergence policy - reuse helper from analyze_temporal_flow_segments refactoring
    policy_results = _apply_convergence_policy(
        conflict_start, conflict_end, copresence_a, copresence_b, overtakes_a, overtakes_b
    )
    
    flow_audit_data = generate_flow_audit_data(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b, conflict_length_m,
        convergence_zone_start=conflict_start,
        convergence_zone_end=conflict_end,
        spatial_zone_exists=policy_results["spatial_zone_exists"],
        temporal_overlap_exists=policy_results["temporal_overlap_exists"],
        true_pass_exists=policy_results["true_pass_exists"],
        has_convergence_policy=policy_results["has_convergence_policy"],
        no_pass_reason_code=policy_results["no_pass_reason_code"],
        copresence_a=copresence_a,
        copresence_b=copresence_b,
        overtakes_a=overtakes_a,
        overtakes_b=overtakes_b,
        total_a=len(df_a),
        total_b=len(df_b),
        zone_index=None,  # TODO: Issue #612 - Add multi-zone support to generate_flow_audit_for_segment
        cp_km=cp_km,
        zone_source=None  # TODO: Issue #612 - Add multi-zone support to generate_flow_audit_for_segment
    )
    
    print(f"  📊 Flow Audit data generated with {len(flow_audit_data)} fields")
    
    # Generate Runner-Level Audit - extracted to helper function to reduce complexity
    print(f"🔍 {seg_id} {event_a} vs {event_b} RUNNER-LEVEL AUDIT GENERATION:")
    runner_audit_data = _generate_runner_audit_for_segment(
        seg_id, segment, event_a, event_b, df_a, df_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b,
        conflict_start, conflict_end, conflict_length_m, output_dir
    )
    
    # Log strict-first rule (already handled in helper, just log for audit)
    if runner_audit_data and 'stats' in runner_audit_data:
        stats = runner_audit_data['stats']
        audit_strict_passes = stats.get('strict_pass', 0)
        audit_raw_passes = stats.get('raw_pass', 0)
        print(f"🔍 STRICT-FIRST RULE APPLIED for {seg_id} {event_a} vs {event_b}:")
        print(f"  Main calculation: {overtakes_a}/{overtakes_b} strict passes")
        print(f"  Audit generation: {audit_strict_passes} strict, {audit_raw_passes} raw")
        print(f"  Using main calculation results: {overtakes_a}/{overtakes_b}")
    
    # Return comprehensive results
    return {
        "segment_id": seg_id,
        "event_a": event_a,
        "event_b": event_b,
        "convergence_point_km": cp_km,
        "convergence_zone_start": conflict_start,
        "convergence_zone_end": conflict_end,
        "overtakes_a": overtakes_a,
        "overtakes_b": overtakes_b,
        "copresence_a": copresence_a,
        "copresence_b": copresence_b,
        "total_a": len(df_a),
        "total_b": len(df_b),
        "flow_audit_data": flow_audit_data,
        "runner_audit_data": runner_audit_data,
        "audit_files_location": f"{output_dir}/audit/"
    }

