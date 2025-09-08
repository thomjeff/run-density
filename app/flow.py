"""
Temporal Flow Analysis Module

Handles temporal flow analysis for segments where overtaking or merging is possible.
Only processes segments with overtake_flag = 'y' from flow.csv.
Supports overtake, merge, and diverge flow types.

KEY CONCEPTS:
1. START TIMES: Must be offsets from midnight in minutes (e.g., 420 = 7:00 AM)
2. NORMALIZED DISTANCES: For segments with different absolute ranges (like F1), 
   we work in normalized space (0.0-1.0) to compare relative positions
3. CONVERGENCE vs OVERTAKE_FLAG: Segments with overtake_flag='y' don't necessarily 
   need to show convergence if there are no temporal overlaps due to timing differences
4. TRUE PASS DETECTION: Only counts actual directional overtaking, not just co-presence
5. INTERSECTION BOUNDARIES: For directional change detection, use intersection 
   boundaries (same segment) rather than individual event boundaries (different segments)
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Optional, Any, List, Tuple
import pandas as pd
import numpy as np
from .constants import (
    SECONDS_PER_MINUTE, SECONDS_PER_HOUR,
    DEFAULT_CONVERGENCE_STEP_KM, DEFAULT_MIN_OVERLAP_DURATION, 
    DEFAULT_CONFLICT_LENGTH_METERS, TEMPORAL_OVERLAP_TOLERANCE_SECONDS,
    METERS_PER_KM, PACE_SIMILAR_THRESHOLD, PACE_MODERATE_DIFFERENCE_THRESHOLD,
    TEMPORAL_BINNING_THRESHOLD_MINUTES, SPATIAL_BINNING_THRESHOLD_METERS,
    SUSPICIOUS_OVERTAKING_RATE_THRESHOLD,
    MIN_NORMALIZED_FRACTION, MAX_NORMALIZED_FRACTION,
    FRACTION_CLAMP_REASON_OUTSIDE_RANGE, FRACTION_CLAMP_REASON_NEGATIVE,
    FRACTION_CLAMP_REASON_EXCEEDS_ONE
)
from .utils import load_pace_csv, arrival_time_sec, load_segments_csv


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


def calculate_convergence_point(
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
) -> Optional[float]:
    """
    Calculate convergence point using TRUE PASS DETECTION.
    
    This function detects when runners from one event actually pass runners
    from another event (directional overtaking), not just co-presence.
    
    A true pass occurs when:
    1. Runner A arrives at km_point at time T_A
    2. Runner B arrives at km_point at time T_B  
    3. |T_A - T_B| <= tolerance
    4. AND one runner was behind the other at from_km but ahead at to_km
    
    ALGORITHM APPROACH:
    - If events have absolute intersection (like L1): Use intersection-based approach
    - If events have no intersection (like F1): Use normalized approach with fine grid
    - Normalized approach maps relative positions (0.0-1.0) to absolute coordinates
      for pace calculations, then checks for temporal overlap
    
    Returns the kilometer mark where the first true pass occurs, or None.
    """
    # Import the true pass detection function from overlap module
    from .overlap import calculate_true_pass_detection, calculate_convergence_point as calculate_co_presence
    
    # Check if there's an intersection in absolute space first
    intersection_start = max(from_km_a, from_km_b)
    intersection_end = min(to_km_a, to_km_b)
    
    if intersection_start < intersection_end:
        # There is an intersection - use normal approach with true pass detection
        true_pass_result = calculate_true_pass_detection(
            dfA, dfB, eventA, eventB, start_times,
            intersection_start, intersection_end, step_km
        )
        
        # Also check for co-presence (temporal overlap without directional change)
        # This handles cases where events overlap in time but don't have directional overtaking
        co_presence_result = calculate_co_presence(
            dfA, dfB, eventA, eventB, start_times,
            intersection_start, intersection_end, step_km
        )
        
        # Return true pass result if available, otherwise co-presence result
        return true_pass_result if true_pass_result is not None else co_presence_result
    
    # No intersection in absolute space - need normalized approach for segments like F1
    # NORMALIZED DISTANCE APPROACH: For segments with different absolute ranges but same
    # relative positions (e.g., F1: Full 16.35-18.65km, Half 2.7-5.0km, 10K 5.8-8.1km),
    # we work in normalized space (0.0-1.0) to compare relative positions within each segment.
    # Calculate segment lengths
    len_a = to_km_a - from_km_a
    len_b = to_km_b - from_km_b
    
    if len_a <= 0 or len_b <= 0:
        return None

    # For segments with different ranges, we need to find where runners from different events
    # are at the same relative position within their respective segments.
    # We'll check multiple normalized positions and find where temporal overlap occurs.
    
    # Use a finer grid of normalized positions
    import numpy as np
    normalized_points = np.linspace(0.0, 1.0, 21)  # 0.0, 0.05, 0.1, ..., 1.0
    
    for norm_point in normalized_points:
        # Map normalized point to absolute coordinates for each event
        abs_km_a = from_km_a + (norm_point * len_a)
        abs_km_b = from_km_b + (norm_point * len_b)
        
        # Use the existing overlap detection functions with the mapped coordinates
        # We'll create a temporary "intersection" range around this point
        tolerance_km = 0.1  # 100m tolerance around the point
        range_start = abs_km_a - tolerance_km
        range_end = abs_km_a + tolerance_km
        
        # Try true pass detection at this normalized position
        true_pass_result = calculate_true_pass_detection(
            dfA, dfB, eventA, eventB, start_times,
            range_start, range_end, step_km
        )
        
        # Try co-presence detection at this normalized position
        co_presence_result = calculate_co_presence(
            dfA, dfB, eventA, eventB, start_times,
            range_start, range_end, step_km
        )
        
        # Return true pass result if available, otherwise co-presence result
        if true_pass_result is not None:
            return true_pass_result
        elif co_presence_result is not None:
            return co_presence_result
    
    # No convergence found in normalized space
    return None


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
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
    overlap_duration_minutes: float = 0.0,
) -> Tuple[int, int, List[str], List[str], int, int]:
    """
    Calculate overtaking with binning for long segments.
    Uses time bins if overlap > 10 minutes, distance bins if conflict zone > 100m.
    """
    
    # Check if binning is needed
    use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
    use_distance_bins = conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
    
    # Debug logging for M1
    if event_a == "Half" and event_b == "10K":
        print(f"🔍 BINNING DECISION DEBUG:")
        print(f"  Overlap duration: {overlap_duration_minutes} min (threshold: {TEMPORAL_BINNING_THRESHOLD_MINUTES})")
        print(f"  Conflict length: {conflict_length_m} m (threshold: {SPATIAL_BINNING_THRESHOLD_METERS})")
        print(f"  Use time bins: {use_time_bins}")
        print(f"  Use distance bins: {use_distance_bins}")
        print(f"  Will use: {'BINNED' if (use_time_bins or use_distance_bins) else 'ORIGINAL'} calculation")
    
    if use_time_bins or use_distance_bins:
        # Log binning decision for transparency
        logging.info(f"BINNING APPLIED: time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                    f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
        
        return calculate_convergence_zone_overlaps_binned(
            df_a, df_b, event_a, event_b, start_times,
            cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
            min_overlap_duration, conflict_length_m,
            use_time_bins, use_distance_bins, overlap_duration_minutes
        )
    else:
        # Use original method for short segments
        logging.debug(f"BINNING NOT APPLIED: time_bins={use_time_bins}, distance_bins={use_distance_bins} "
                     f"(window={overlap_duration_minutes:.1f}min, zone={conflict_length_m:.0f}m)")
        
        return calculate_convergence_zone_overlaps_original(
            df_a, df_b, event_a, event_b, start_times,
            cp_km, from_km_a, to_km_a, from_km_b, to_km_b,
            min_overlap_duration, conflict_length_m
        )


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
    conflict_length_m: float = 200.0,
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
        "audit_trigger": ""
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


def emit_runner_audit(
    event_a_csv: str,
    event_b_csv: str,
    out_dir: str,
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
    row_cap_per_shard: int = 50000,
    strict_min_dwell: int = 5,
    strict_margin: int = 2
) -> Dict[str, Any]:
    """
    Pure-CSV runner-level audit emitter (no third-party deps).
    
    Inputs: two CSVs with runner timing windows in a segment (Event A and Event B)
    Outputs: small index CSV + one or more shard CSVs with pairwise overlaps
    Strategy: interval join using two-pointer sweep; shard by minute window and row cap
    """
    import csv, os, math, pathlib, datetime
    
    TOPK_CSV_ROWS = 2000
    WINDOW_GRANULARITY_SEC = 60
    
    # Create audit subdirectory within the output directory
    audit_dir = os.path.join(out_dir, "audit")
    os.makedirs(audit_dir, exist_ok=True)
    
    def read_runners_csv(path):
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

    def shard_key_from_overlap_start(ts):
        m = int(ts // WINDOW_GRANULARITY_SEC)
        return f"min_{m:06d}"

    def ensure_dir(path):
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    def overlap_interval(a_entry, a_exit, b_entry, b_exit):
        start = max(a_entry, b_entry)
        end   = min(a_exit,  b_exit)
        dwell = end - start
        return start, end, dwell

    def sign(x):
        if x > 0: return 1
        if x < 0: return -1
        return 0

    ensure_dir(out_dir)
    A = read_runners_csv(event_a_csv)
    B = read_runners_csv(event_b_csv)

    j = 0
    total_pairs = 0
    overlapped_pairs = 0
    strict_pass = 0
    raw_pass = 0

    shard_writers = {}
    shard_counts = {}
    topk = []

    executed_at_utc = datetime.datetime.utcnow().isoformat()+"Z"
    pair_base_cols = [
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

    def open_shard(shard_key, part_idx):
        shard_name = f"{seg_id}_{event_a_name}-{event_b_name}_{shard_key}_p{part_idx}.csv"
        shard_path = os.path.join(audit_dir, shard_name)
        f = open(shard_path, "w", newline="")
        w = csv.DictWriter(f, fieldnames=pair_base_cols)
        w.writeheader()
        return shard_path, f, w

    current_shard_part = {}
    def write_pair(shard_key, row):
        if shard_key not in shard_writers:
            path, fh, wr = open_shard(shard_key, 1)
            shard_writers[shard_key] = (path, fh, wr)
            shard_counts[shard_key] = 0
            current_shard_part[shard_key] = 1

        path, fh, wr = shard_writers[shard_key]
        if shard_counts[shard_key] >= row_cap_per_shard:
            fh.close()
            current_shard_part[shard_key] += 1
            path, fh, wr = open_shard(shard_key, current_shard_part[shard_key])
            shard_writers[shard_key] = (path, fh, wr)
            shard_counts[shard_key] = 0
        wr.writerow(row)
        shard_counts[shard_key] += 1
        return path

    # Two-pointer sweep algorithm for temporal interval join
    for a in A:
        while j < len(B) and B[j]["exit_time"] < a["entry_time"]:
            j += 1
        k = j
        while k < len(B) and B[k]["entry_time"] <= a["exit_time"]:
            b = B[k]
            total_pairs += 1
            os_, oe_, dwell = overlap_interval(a["entry_time"], a["exit_time"], b["entry_time"], b["exit_time"])
            if dwell > 0:
                overlapped_pairs += 1
                entry_delta = a["entry_time"] - b["entry_time"]
                exit_delta  = a["exit_time"]  - b["exit_time"]
                rel_entry   = sign(entry_delta)
                rel_exit    = sign(exit_delta)
                order_flip  = (rel_entry != rel_exit)
                directional_gain = exit_delta - entry_delta

                pass_raw = order_flip
                pass_strict = (order_flip and dwell >= strict_min_dwell and directional_gain >= strict_margin)
                reason = ""
                if not pass_strict:
                    if not order_flip: reason = "NO_DIRECTIONAL_CHANGE"
                    elif dwell < strict_min_dwell: reason = "DWELL_TOO_SHORT"
                    elif directional_gain < strict_margin: reason = "MARGIN_TOO_SMALL"

                if pass_raw: raw_pass += 1
                if pass_strict: strict_pass += 1

                shard_key = shard_key_from_overlap_start(os_)
                row = {
                    "run_id": run_id,
                    "executed_at_utc": executed_at_utc,
                    "seg_id": seg_id,
                    "segment_label": segment_label,
                    "flow_type": flow_type,
                    "event_a": event_a_name,
                    "event_b": event_b_name,
                    "pair_key": f"{a['runner_id']}-{b['runner_id']}",
                    "convergence_zone_start": convergence_zone_start,
                    "convergence_zone_end":   convergence_zone_end,
                    "zone_width_m": zone_width_m,
                    "binning_applied": binning_applied,
                    "binning_mode": binning_mode,
                    "runner_id_a": a["runner_id"],
                    "entry_km_a": a["entry_km"],
                    "exit_km_a":  a["exit_km"],
                    "entry_time_sec_a": a["entry_time"],
                    "exit_time_sec_a":  a["exit_time"],
                    "runner_id_b": b["runner_id"],
                    "entry_km_b": b["entry_km"],
                    "exit_km_b":  b["exit_km"],
                    "entry_time_sec_b": b["entry_time"],
                    "exit_time_sec_b":  b["exit_time"],
                    "overlap_start_time_sec": os_,
                    "overlap_end_time_sec":   oe_,
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
                shard_path = write_pair(shard_key, row)

                topk.append((dwell, row))
                if len(topk) > TOPK_CSV_ROWS:
                    topk.sort(key=lambda x: x[0], reverse=True)
                    topk = topk[:TOPK_CSV_ROWS]
            k += 1

    # Close all shard files
    shard_paths = []
    for key, (path, fh, wr) in shard_writers.items():
        fh.close()
        shard_paths.append(path)

    # Write index CSV
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

    # Write TopK CSV
    topk_path = os.path.join(audit_dir, f"{seg_id}_{event_a_name}-{event_b_name}_TopK.csv")
    with open(topk_path, "w", newline="") as f:
        cols = list(topk[0][1].keys()) if topk else pair_base_cols
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for _, row in sorted(topk, key=lambda x: x[0], reverse=True):
            w.writerow(row)

    return {
        "index_csv": index_path,
        "shard_csvs": shard_paths,
        "topk_csv": topk_path,
        "stats": {
            "total_pairs": total_pairs,
            "overlapped_pairs": overlapped_pairs,
            "raw_pass": raw_pass,
            "strict_pass": strict_pass
        }
    }


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
    output_dir: str = "reports/analysis"
) -> Dict[str, str]:
    """
    Extract runner timing data from F1 analysis for runner audit emitter.
    
    Creates CSV files with runner entry/exit timing data that can be consumed
    by the emit_runner_audit function.
    """
    import os
    import csv
    from datetime import datetime
    
    # Create audit subdirectory within the output directory
    audit_dir = os.path.join(output_dir, "audit")
    os.makedirs(audit_dir, exist_ok=True)
    
    # Generate filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_a_path = os.path.join(audit_dir, f"F1_{event_a}_runners_{timestamp}.csv")
    csv_b_path = os.path.join(audit_dir, f"F1_{event_b}_runners_{timestamp}.csv")
    
    # Extract runner data for event A
    runners_a = []
    for _, runner in df_a.iterrows():
        # Calculate entry/exit times in seconds from start
        # The DataFrame has 'entry_time' and 'exit_time' columns as numeric values (minutes)
        entry_time_min = runner.get('entry_time', 0.0)
        exit_time_min = runner.get('exit_time', 0.0)
        
        # Convert minutes to seconds
        entry_time_sec = entry_time_min * 60.0
        exit_time_sec = exit_time_min * 60.0
        
        # Calculate entry/exit distances
        entry_km = from_km_a
        exit_km = to_km_a
        
        runners_a.append({
            'runner_id': runner['runner_id'],
            'entry_time_sec': entry_time_sec,
            'exit_time_sec': exit_time_sec,
            'entry_km': entry_km,
            'exit_km': exit_km,
            'pace_min_per_km': runner.get('pace_min_per_km', 0.0),
            'start_offset_sec': runner.get('start_offset_sec', 0.0)
        })
    
    # Extract runner data for event B
    runners_b = []
    for _, runner in df_b.iterrows():
        # Calculate entry/exit times in seconds from start
        # The DataFrame has 'entry_time' and 'exit_time' columns as numeric values (minutes)
        entry_time_min = runner.get('entry_time', 0.0)
        exit_time_min = runner.get('exit_time', 0.0)
        
        # Convert minutes to seconds
        entry_time_sec = entry_time_min * 60.0
        exit_time_sec = exit_time_min * 60.0
        
        # Calculate entry/exit distances
        entry_km = from_km_b
        exit_km = to_km_b
        
        runners_b.append({
            'runner_id': runner['runner_id'],
            'entry_time_sec': entry_time_sec,
            'exit_time_sec': exit_time_sec,
            'entry_km': entry_km,
            'exit_km': exit_km,
            'pace_min_per_km': runner.get('pace_min_per_km', 0.0),
            'start_offset_sec': runner.get('start_offset_sec', 0.0)
        })
    
    # Write CSV files
    csv_headers = ['runner_id', 'entry_time_sec', 'exit_time_sec', 'entry_km', 'exit_km', 'pace_min_per_km', 'start_offset_sec']
    
    with open(csv_a_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(runners_a)
    
    with open(csv_b_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(runners_b)
    
    return {
        'event_a_csv': csv_a_path,
        'event_b_csv': csv_b_path,
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
    conflict_length_m: float = 200.0,
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
    
    # Find temporal overlaps and validate overtaking
    a_overtakes = set()
    b_overtakes = set()
    a_copresence = set()
    b_copresence = set()
    
    overlap_pairs = []
    
    for i, (a_entry, a_exit, a_id) in enumerate(zip(a_entry_times, a_exit_times, a_runner_ids)):
        for j, (b_entry, b_exit, b_id) in enumerate(zip(b_entry_times, b_exit_times, b_runner_ids)):
            # Check for temporal overlap
            overlap_start = max(a_entry, b_entry)
            overlap_end = min(a_exit, b_exit)
            overlap_duration = overlap_end - overlap_start
            
            if overlap_duration > 0:  # Any temporal overlap
                a_copresence.add(a_id)
                b_copresence.add(b_id)
                
                # For F1, we need to check if there's actual directional change
                # Since segments don't intersect, we need to validate if overtaking makes sense
                
                # Check if runner A passes runner B (A starts behind B, finishes ahead of B)
                a_passes_b = (a_entry > b_entry and a_exit < b_exit)
                # Check if runner B passes runner A (B starts behind A, finishes ahead of A)
                b_passes_a = (b_entry > a_entry and b_exit < a_exit)
                
                if a_passes_b or b_passes_a:
                    a_overtakes.add(a_id)
                    b_overtakes.add(b_id)
                
                overlap_pairs.append({
                    "a_id": a_id,
                    "b_id": b_id,
                    "a_entry": a_entry,
                    "a_exit": a_exit,
                    "b_entry": b_entry,
                    "b_exit": b_exit,
                    "overlap_duration": overlap_duration,
                    "a_passes_b": a_passes_b,
                    "b_passes_a": b_passes_a
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
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
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

    # TRUE PASS DETECTION: Check for temporal overlap AND directional change
    # This ensures we only count actual overtaking, not just co-presence
    for i, (enter_a, exit_a) in enumerate(zip(time_enter_a, time_exit_a)):
        for j, (enter_b, exit_b) in enumerate(zip(time_enter_b, time_exit_b)):
            overlap_start = max(enter_a, enter_b)
            overlap_end = min(exit_a, exit_b)
            overlap_duration = overlap_end - overlap_start
            
            if overlap_duration >= min_overlap_duration:
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
                
                # Check for temporal overlap (co-presence)
                temporal_overlap = (start_time_a < end_time_b and start_time_b < end_time_a)
                
                if temporal_overlap:
                    a_bib = df_a.iloc[i]["runner_id"]
                    b_bib = df_b.iloc[j]["runner_id"]
                    
                    # Always count co-presence
                    a_bibs_copresence.add(a_bib)
                    b_bibs_copresence.add(b_bib)
                    
                    # Count as true pass only if directional change occurs
                    if a_passes_b or b_passes_a:
                        a_bibs_overtakes.add(a_bib)
                        b_bibs_overtakes.add(b_bib)
                    
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
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
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
    unique_pairs = set()
    
    if use_time_bins:
        # Create time bins (10-minute intervals)
        bin_duration_minutes = 10.0
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
            unique_pairs.update([(a, b) for a in bin_bibs_a for b in bin_bibs_b])
    
    elif use_distance_bins:
        # Create distance bins (100m intervals)
        bin_size_km = 0.1  # 100m
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
            unique_pairs.update([(a, b) for a in bin_bibs_a for b in bin_bibs_b])
    
    # Calculate final results
    all_a_bibs = a_bibs_overtakes.union(a_bibs_copresence)
    all_b_bibs = b_bibs_overtakes.union(b_bibs_copresence)
    participants_involved = len(all_a_bibs.union(all_b_bibs))
    unique_encounters = len(unique_pairs)
    
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
    
    from .constants import (
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
        
        # Get events that are present (y)
        events = []
        if segment.get('full') == 'y':
            events.append('Full')
        if segment.get('half') == 'y':
            events.append('Half')
        if segment.get('10K') == 'y':
            events.append('10K')
        
        # Generate all possible event pairs
        for i, event_a in enumerate(events):
            for event_b in events[i+1:]:
                # Get distance ranges for each event
                if event_a == "Full":
                    from_km_a = segment.get("full_from_km", 0)
                    to_km_a = segment.get("full_to_km", 0)
                elif event_a == "Half":
                    from_km_a = segment.get("half_from_km", 0)
                    to_km_a = segment.get("half_to_km", 0)
                elif event_a == "10K":
                    from_km_a = segment.get("10K_from_km", 0)
                    to_km_a = segment.get("10K_to_km", 0)
                
                if event_b == "Full":
                    from_km_b = segment.get("full_from_km", 0)
                    to_km_b = segment.get("full_to_km", 0)
                elif event_b == "Half":
                    from_km_b = segment.get("half_from_km", 0)
                    to_km_b = segment.get("half_to_km", 0)
                elif event_b == "10K":
                    from_km_b = segment.get("10K_from_km", 0)
                    to_km_b = segment.get("10K_to_km", 0)
                
                # Create converted segment
                converted_segment = {
                    "seg_id": seg_id,
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
                    "prior_segment_id": segment.get("prior_segment_id", ""),
                    "notes": segment.get("notes", "")
                }
                converted_segments.append(converted_segment)
    
    return pd.DataFrame(converted_segments)


def analyze_temporal_flow_segments(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = 100.0,
) -> Dict[str, Any]:
    """
    Analyze all segments for temporal flow patterns.
    Supports overtake, merge, and diverge flow types.
    Processes ALL segments but only calculates convergence for overtake_flag = 'y' segments.
    
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
        
        # Filter runners for this segment
        df_a = pace_df[pace_df["event"] == event_a].copy()
        df_b = pace_df[pace_df["event"] == event_b].copy()
        
        # Calculate convergence point (in event A km ruler) - only for overtake segments
        # NOTE: Segments with overtake_flag='y' don't necessarily need to show convergence
        # if there are no temporal overlaps due to timing differences (e.g., A1, B1)
        cp_km = None
        if segment.get("overtake_flag") == "y":
            cp_km = calculate_convergence_point(
                df_a, df_b, event_a, event_b, start_times,
                from_km_a, to_km_a, from_km_b, to_km_b
            )
        
        # Calculate entry/exit times for this segment
        first_entry_a, last_exit_a, first_entry_b, last_exit_b, overlap_window_duration = calculate_entry_exit_times(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b
        )
        
        segment_result = {
            "seg_id": seg_id,
            "segment_label": segment.get("segment_label", ""),
            "flow_type": segment.get("flow_type", ""),
            "event_a": event_a,
            "event_b": event_b,
            "from_km_a": from_km_a,
            "to_km_a": to_km_a,
            "from_km_b": from_km_b,
            "to_km_b": to_km_b,
            "convergence_point": cp_km,
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
            "overtake_flag": segment.get("overtake_flag", "")
        }
        
        if cp_km is not None and segment.get("overtake_flag") == "y":
            # Calculate overtaking runners in convergence zone using local-axis mapping
            # Calculate dynamic conflict length first
            from .constants import (
                CONFLICT_LENGTH_LONG_SEGMENT_M,
                CONFLICT_LENGTH_MEDIUM_SEGMENT_M, 
                CONFLICT_LENGTH_SHORT_SEGMENT_M,
                SEGMENT_LENGTH_LONG_THRESHOLD_KM,
                SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM
            )
            
            segment_length_km = to_km_a - from_km_a
            if segment_length_km > SEGMENT_LENGTH_LONG_THRESHOLD_KM:
                dynamic_conflict_length_m = CONFLICT_LENGTH_LONG_SEGMENT_M
            elif segment_length_km > SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM:
                dynamic_conflict_length_m = CONFLICT_LENGTH_MEDIUM_SEGMENT_M
            else:
                dynamic_conflict_length_m = CONFLICT_LENGTH_SHORT_SEGMENT_M
            
            # For segments with no intersection (like F1), use segment center instead of convergence point
            # The convergence point might be in a different coordinate system
            if from_km_a <= cp_km <= to_km_a:
                # Convergence point is within Event A's range - use it directly
                effective_cp_km = cp_km
            else:
                # Convergence point is outside Event A's range - use segment center
                # This handles segments with no intersection where convergence was detected in normalized space
                effective_cp_km = (from_km_a + to_km_a) / 2.0
            
            # Calculate overlap duration in minutes for binning decision
            # overlap_window_duration is a formatted string like "55:32", need to parse it
            if isinstance(overlap_window_duration, str) and ':' in overlap_window_duration:
                # Parse format like "55:32" or "1:23:45"
                parts = overlap_window_duration.split(':')
                if len(parts) == 2:  # MM:SS
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    overlap_duration_minutes = minutes + seconds / 60.0
                elif len(parts) == 3:  # HH:MM:SS
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    overlap_duration_minutes = hours * 60 + minutes + seconds / 60.0
                else:
                    overlap_duration_minutes = 0.0
            else:
                overlap_duration_minutes = overlap_window_duration / 60.0 if isinstance(overlap_window_duration, (int, float)) else 0.0
            
            overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps_with_binning(
                df_a, df_b, event_a, event_b, start_times,
                effective_cp_km, from_km_a, to_km_a, from_km_b, to_km_b, min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
            )
            
            # M1 DETERMINISTIC TRACE LOGGING (for debugging discrepancy)
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
            
            # F1 Half vs 10K PER-RUNNER VALIDATION
            if seg_id == "F1" and event_a == "Half" and event_b == "10K":
                validation_results = validate_per_runner_entry_exit_f1(
                    df_a, df_b, event_a, event_b, start_times,
                    from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
                )
                
                if "error" not in validation_results:
                    # Check for discrepancy between main calculation and validation
                    main_a = overtakes_a
                    main_b = overtakes_b
                    val_a = validation_results["overtakes_a"]
                    val_b = validation_results["overtakes_b"]
                    
                    if main_a != val_a or main_b != val_b:
                        logging.warning(f"F1 {event_a} vs {event_b} DISCREPANCY DETECTED!")
                        logging.warning(f"  Current calculation: {main_a} ({main_a/len(df_a)*100:.1f}%), {main_b} ({main_b/len(df_b)*100:.1f}%)")
                        logging.warning(f"  Validation results:  {val_a} ({val_a/len(df_a)*100:.1f}%), {val_b} ({val_b/len(df_b)*100:.1f}%)")
                        logging.warning(f"  Using validation results.")
                        
                        # Use validation results instead of main calculation
                        overtakes_a = val_a
                        overtakes_b = val_b
                        copresence_a = validation_results["copresence_a"]
                        copresence_b = validation_results["copresence_b"]
            
            # FLOW AUDIT GENERATION (parameterized for any segment)
            # Note: Flow Audit is now available via /api/flow-audit endpoint
            # The hardcoded F1 logic has been removed and replaced with a parameterized function
            
            # B2, K1, L1 CONVERGENCE ZONE DEBUGGING
            if seg_id in ["B2", "K1", "L1"] and cp_km is None and segment.get("overtake_flag") == "y":
                print(f"🔍 {seg_id} {event_a} vs {event_b} CONVERGENCE DEBUG:")
                print(f"  Segment ranges: {event_a} {from_km_a}-{to_km_a}km, {event_b} {from_km_b}-{to_km_b}km")
                print(f"  Convergence point: {cp_km}")
                print(f"  Has convergence: {segment_result.get('has_convergence', False)}")
                print(f"  Convergence zone: {segment_result.get('convergence_zone_start', 'N/A')}-{segment_result.get('convergence_zone_end', 'N/A')}")
                print(f"  Overtaking: {overtakes_a}, {overtakes_b}")
                
                # Check if segments have intersection
                intersection_start = max(from_km_a, from_km_b)
                intersection_end = min(to_km_a, to_km_b)
                has_intersection = intersection_start < intersection_end
                print(f"  Intersection: {intersection_start}-{intersection_end}km (has_intersection={has_intersection})")
                
                # Check overlap window
                print(f"  Overlap window: {overlap_window_duration}")
                print(f"  Total runners: {len(df_a)} {event_a}, {len(df_b)} {event_b}")
            
            # Log binning decisions and warnings
            
            use_time_bins = overlap_duration_minutes > TEMPORAL_BINNING_THRESHOLD_MINUTES
            use_distance_bins = dynamic_conflict_length_m > SPATIAL_BINNING_THRESHOLD_METERS
            
            if use_time_bins or use_distance_bins:
                print(f"🔧 BINNING APPLIED to {seg_id}: time_bins={use_time_bins}, distance_bins={use_distance_bins}")
                print(f"   Overlap: {overlap_duration_minutes:.1f}min, Conflict: {dynamic_conflict_length_m:.0f}m")
            
            # Flag suspicious overtaking rates (using true passes, not co-presence)
            pct_a = overtakes_a / len(df_a) if len(df_a) > 0 else 0
            pct_b = overtakes_b / len(df_b) if len(df_b) > 0 else 0
            
            if pct_a > SUSPICIOUS_OVERTAKING_RATE_THRESHOLD or pct_b > SUSPICIOUS_OVERTAKING_RATE_THRESHOLD:
                if not (use_time_bins or use_distance_bins):
                    print(f"⚠️  SUSPICIOUS OVERTAKING RATES in {seg_id}: {pct_a:.1%}, {pct_b:.1%} - NO BINNING APPLIED!")
                else:
                    print(f"✅ High overtaking rates in {seg_id}: {pct_a:.1%}, {pct_b:.1%} - BINNING APPLIED")
            
            # Calculate dynamic conflict zone boundaries using the same logic as calculate_convergence_zone_overlaps
            # This ensures consistency between overtaking count calculation and reporting
            len_a = to_km_a - from_km_a
            len_b = to_km_b - from_km_b
            
            if from_km_a <= cp_km <= to_km_a:
                # Convergence point is within Event A's range - use absolute approach
                s_cp = (cp_km - from_km_a) / max(len_a, 1e-9)
                s_cp, clamp_reason = clamp_normalized_fraction(s_cp, "convergence_point_")
                
                # Use proportional tolerance: 5% of shorter segment, minimum 50m
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
                
                # Store normalized values for convergence zone (0.0 to 1.0)
                conflict_start = s_start
                conflict_end = s_end
            else:
                # Convergence point is outside Event A's range - use normalized approach
                intersection_start = max(from_km_a, from_km_b)
                intersection_end = min(to_km_a, to_km_b)
                
                if intersection_start < intersection_end:
                    # Use intersection boundaries - normalize to segment
                    len_a = to_km_a - from_km_a
                    intersection_start_norm = (intersection_start - from_km_a) / len_a
                    intersection_end_norm = (intersection_end - from_km_a) / len_a
                    conflict_length_km = dynamic_conflict_length_m / 1000.0
                    conflict_half_km = conflict_length_km / 2.0 / len_a  # Normalize to segment length
                    conflict_start = max(0.0, intersection_start_norm - conflict_half_km)
                    conflict_end = min(1.0, intersection_end_norm + conflict_half_km)
                else:
                    # Use segment center - normalize to segment
                    len_a = to_km_a - from_km_a
                    center_a_norm = 0.5  # Center of normalized segment
                    conflict_length_km = dynamic_conflict_length_m / 1000.0
                    conflict_half_km = conflict_length_km / 2.0 / len_a  # Normalize to segment length
                    conflict_start = max(0.0, center_a_norm - conflict_half_km)
                    conflict_end = min(1.0, center_a_norm + conflict_half_km)
            
            # IMPLEMENT THREE-BOOLEAN SCHEMA FOR CONVERGENCE POLICY
            # Based on convergence policy framework: has_convergence := spatial_zone_exists AND temporal_overlap_exists
            
            # 1. spatial_zone_exists: convergence zones are calculated and non-empty
            spatial_zone_exists = conflict_start is not None and conflict_end is not None
            
            # 2. temporal_overlap_exists: any copresence detected (runners with temporal overlap)
            temporal_overlap_exists = copresence_a > 0 or copresence_b > 0
            
            # 3. true_pass_exists: any overtaking counts (directional changes)
            true_pass_exists = overtakes_a > 0 or overtakes_b > 0
            
            # POLICY: has_convergence := spatial_zone_exists AND temporal_overlap_exists
            has_convergence_policy = spatial_zone_exists and temporal_overlap_exists
            
            # Determine reason code when has_convergence=True but no true passes
            no_pass_reason_code = None
            if has_convergence_policy and not true_pass_exists:
                no_pass_reason_code = "NO_DIRECTIONAL_CHANGE_OR_WINDOW_TOO_SHORT"
            elif spatial_zone_exists and not temporal_overlap_exists:
                no_pass_reason_code = "SPATIAL_ONLY_NO_TEMPORAL"
            
            # Set has_convergence based on policy
            segment_result["has_convergence"] = has_convergence_policy
            
            # Store the three boolean flags for transparency and debugging
            segment_result["spatial_zone_exists"] = spatial_zone_exists
            segment_result["temporal_overlap_exists"] = temporal_overlap_exists
            segment_result["true_pass_exists"] = true_pass_exists
            segment_result["has_convergence_policy"] = has_convergence_policy
            segment_result["no_pass_reason_code"] = no_pass_reason_code
            
            # Clear convergence_point and fraction if no convergence
            if not has_convergence_policy:
                segment_result["convergence_point"] = None
                segment_result["convergence_point_fraction"] = None
            
            segment_result.update({
                "overtaking_a": overtakes_a,
                "overtaking_b": overtakes_b,
                "copresence_a": copresence_a,
                "copresence_b": copresence_b,
                "sample_a": bibs_a[:10],  # First 10 for samples
                "sample_b": bibs_b[:10],
                "convergence_zone_start": conflict_start,
                "convergence_zone_end": conflict_end,
                "conflict_length_m": dynamic_conflict_length_m,
                "unique_encounters": unique_encounters,
                "participants_involved": participants_involved
            })
            
            results["segments_with_convergence"] += 1
        
        results["segments"].append(segment_result)
    
    # Generate Deep Dive analysis for segments with overtake_flag = 'y' after all segments are processed
    for segment_result in results["segments"]:
        if segment_result.get("overtake_flag") == "y":
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
            
            # Flow type specific reporting
            if flow_type == "merge":
                narrative.append(f"🔄 MERGE ANALYSIS:")
                narrative.append(f"   • {segment['event_a']} runners in merge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
                narrative.append(f"   • {segment['event_b']} runners in merge zone: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
                narrative.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
                narrative.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
            elif flow_type == "diverge":
                narrative.append(f"↗️ DIVERGE ANALYSIS:")
                narrative.append(f"   • {segment['event_a']} runners in diverge zone: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
                narrative.append(f"   • {segment['event_b']} runners in diverge zone: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
                narrative.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
                narrative.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
            else:  # overtake (default)
                narrative.append(f"👥 OVERTAKE ANALYSIS:")
                narrative.append(f"   • {segment['event_a']} runners overtaking: {segment['overtaking_a']}/{segment['total_a']} ({segment['overtaking_a']/segment['total_a']*100:.1f}%)")
                narrative.append(f"   • {segment['event_b']} runners overtaking: {segment['overtaking_b']}/{segment['total_b']} ({segment['overtaking_b']/segment['total_b']*100:.1f}%)")
                narrative.append(f"   • Unique Encounters (pairs): {segment.get('unique_encounters', 0)}")
                narrative.append(f"   • Participants Involved (union): {segment.get('participants_involved', 0)}")
            
            narrative.append(f"🏃‍♂️ Sample {segment['event_a']}: {format_bib_range(segment['sample_a'])}")
            narrative.append(f"🏃‍♂️ Sample {segment['event_b']}: {format_bib_range(segment['sample_b'])}")
        else:
            narrative.append("❌ No convergence zone detected")
        
        # Add Deep Dive analysis for all segments with overtake_flag = 'y'
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
    step_km: float = 0.05,
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
    conflict_length_m: float = 100.0,
    thresholds: List[int] = [10, 20, 50, 100],
    time_bin_seconds: int = 30,
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


def generate_flow_audit_for_segment(
    pace_csv: str,
    segments_csv: str,
    start_times: Dict[str, float],
    seg_id: str,
    event_a: str,
    event_b: str,
    min_overlap_duration: float = 5.0,
    conflict_length_m: float = DEFAULT_CONFLICT_LENGTH_METERS,
    output_dir: str = "reports/analysis"
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
    
    # Extract segment parameters based on event types
    if event_a == "Full":
        from_km_a = segment['full_from_km']
        to_km_a = segment['full_to_km']
    elif event_a == "Half":
        from_km_a = segment['half_from_km']
        to_km_a = segment['half_to_km']
    elif event_a == "10K":
        from_km_a = segment['10K_from_km']
        to_km_a = segment['10K_to_km']
    else:
        raise ValueError(f"Unsupported event type: {event_a}")
    
    if event_b == "Full":
        from_km_b = segment['full_from_km']
        to_km_b = segment['full_to_km']
    elif event_b == "Half":
        from_km_b = segment['half_from_km']
        to_km_b = segment['half_to_km']
    elif event_b == "10K":
        from_km_b = segment['10K_from_km']
        to_km_b = segment['10K_to_km']
    else:
        raise ValueError(f"Unsupported event type: {event_b}")
    
    # Filter data for the specific events
    df_a = df[df['event'] == event_a].copy()
    df_b = df[df['event'] == event_b].copy()
    
    if df_a.empty or df_b.empty:
        raise ValueError(f"No data found for {event_a} or {event_b} events")
    
    print(f"  📊 Data loaded: {len(df_a)} {event_a} runners, {len(df_b)} {event_b} runners")
    
    # Calculate convergence point
    cp_km = calculate_convergence_point(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b
    )
    
    if cp_km is None:
        return {
            "error": f"No convergence point found for {seg_id} {event_a} vs {event_b}",
            "segment_id": seg_id,
            "event_a": event_a,
            "event_b": event_b
        }
    
    # Calculate conflict zone (convergence zone) - following the same logic as main analysis
    conflict_start = None
    conflict_end = None
    
    if cp_km is not None:
        # Check if convergence point is within Event A's range
        if from_km_a <= cp_km <= to_km_a:
            # Calculate normalized convergence zone around the convergence point
            len_a = to_km_a - from_km_a
            len_b = to_km_b - from_km_b
            s_cp = (cp_km - from_km_a) / len_a  # Normalized position of convergence point
            
            # Use proportional tolerance approach (same as Main Analysis)
            # Use proportional tolerance: 5% of shorter segment, minimum 50m
            min_segment_len = min(len_a, len_b)
            proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)  # 5% of shorter segment, min 50m
            s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
            
            s_start = max(0.0, s_cp - s_conflict_half)
            s_end = min(1.0, s_cp + s_conflict_half)
            
            # Ensure conflict zone has some width
            if s_end <= s_start:
                s_start = max(0.0, s_cp - 0.05)  # 5% of segment
                s_end = min(1.0, s_cp + 0.05)    # 5% of segment
            
            conflict_start = s_start
            conflict_end = s_end
        else:
            # Convergence point is outside Event A's range - use segment center
            len_a = to_km_a - from_km_a
            len_b = to_km_b - from_km_b
            center_a_norm = 0.5  # Center of normalized segment
            
            # Use proportional tolerance approach (same as Main Analysis)
            min_segment_len = min(len_a, len_b)
            proportional_tolerance_km = max(0.05, 0.05 * min_segment_len)  # 5% of shorter segment, min 50m
            s_conflict_half = proportional_tolerance_km / max(min_segment_len, 1e-9)
            
            conflict_start = max(0.0, center_a_norm - s_conflict_half)
            conflict_end = min(1.0, center_a_norm + s_conflict_half)
    
    # Calculate overlaps and overtakes
    effective_cp_km = cp_km
    overlap_duration_minutes = 60.0  # Default overlap duration
    
    # Use dynamic conflict length (same as Main Analysis)
    try:
        from .constants import (
            CONFLICT_LENGTH_LONG_SEGMENT_M,
            CONFLICT_LENGTH_MEDIUM_SEGMENT_M, 
            CONFLICT_LENGTH_SHORT_SEGMENT_M,
            SEGMENT_LENGTH_LONG_THRESHOLD_KM,
            SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM
        )
        
        segment_length_km = to_km_a - from_km_a
        if segment_length_km > SEGMENT_LENGTH_LONG_THRESHOLD_KM:
            dynamic_conflict_length_m = CONFLICT_LENGTH_LONG_SEGMENT_M
        elif segment_length_km > SEGMENT_LENGTH_MEDIUM_THRESHOLD_KM:
            dynamic_conflict_length_m = CONFLICT_LENGTH_MEDIUM_SEGMENT_M
        else:
            dynamic_conflict_length_m = CONFLICT_LENGTH_SHORT_SEGMENT_M
    except ImportError:
        dynamic_conflict_length_m = conflict_length_m
    
    overtakes_a, overtakes_b, copresence_a, copresence_b, bibs_a, bibs_b, unique_encounters, participants_involved = calculate_convergence_zone_overlaps_with_binning(
        df_a, df_b, event_a, event_b, start_times,
        effective_cp_km, from_km_a, to_km_a, from_km_b, to_km_b, min_overlap_duration, dynamic_conflict_length_m, overlap_duration_minutes
    )
    
    # F1 Half vs 10K PER-RUNNER VALIDATION (same as Main Analysis)
    if seg_id == "F1" and event_a == "Half" and event_b == "10K":
        validation_results = validate_per_runner_entry_exit_f1(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b, dynamic_conflict_length_m
        )
        
        if "error" not in validation_results:
            # Check for discrepancy between main calculation and validation
            main_a = overtakes_a
            main_b = overtakes_b
            val_a = validation_results["overtakes_a"]
            val_b = validation_results["overtakes_b"]
            
            if main_a != val_a or main_b != val_b:
                print(f"🔍 F1 Half vs 10K FLOW RUNNER VALIDATION:")
                print(f"  Main calculation: {main_a}/{main_b}")
                print(f"  Validation results: {val_a}/{val_b}")
                print(f"  Using validation results.")
                
                # Use validation results instead of main calculation
                overtakes_a = val_a
                overtakes_b = val_b
                copresence_a = validation_results["copresence_a"]
                copresence_b = validation_results["copresence_b"]
    
    # M1 DETERMINISTIC TRACE LOGGING (for debugging discrepancy)
    if seg_id == "M1" and event_a == "Half" and event_b == "10K":
        print(f"🔍 M1 Half vs 10K FLOW RUNNER TRACE:")
        print(f"  Input data: A={len(df_a)} runners, B={len(df_b)} runners")
        print(f"  Segment boundaries: A=[{from_km_a}, {to_km_a}], B=[{from_km_b}, {to_km_b}]")
        print(f"  Convergence point: {effective_cp_km} km")
        print(f"  Dynamic conflict length: {dynamic_conflict_length_m} m")
        print(f"  Overlap duration: {overlap_duration_minutes} min")
        print(f"  Raw calculation results: {overtakes_a}/{overtakes_b}")
        print(f"  Co-presence: {copresence_a}/{copresence_b}")
        print(f"  Unique encounters: {unique_encounters}")
        print(f"  Participants involved: {participants_involved}")
    
    # Generate Flow Audit data
    print(f"🔍 {seg_id} {event_a} vs {event_b} FLOW AUDIT DATA GENERATION:")
    
    # Calculate correct boolean values from actual analysis results
    actual_spatial_zone_exists = conflict_start is not None and conflict_end is not None
    actual_temporal_overlap_exists = copresence_a > 0 or copresence_b > 0
    actual_true_pass_exists = overtakes_a > 0 or overtakes_b > 0
    actual_has_convergence_policy = actual_spatial_zone_exists and actual_temporal_overlap_exists
    
    # Determine reason code when has_convergence=True but no true passes
    actual_no_pass_reason_code = None
    if actual_has_convergence_policy and not actual_true_pass_exists:
        actual_no_pass_reason_code = "NO_DIRECTIONAL_CHANGE_OR_WINDOW_TOO_SHORT"
    elif actual_spatial_zone_exists and not actual_temporal_overlap_exists:
        actual_no_pass_reason_code = "SPATIAL_ONLY_NO_TEMPORAL"
    
    flow_audit_data = generate_flow_audit_data(
        df_a, df_b, event_a, event_b, start_times,
        from_km_a, to_km_a, from_km_b, to_km_b, conflict_length_m,
        convergence_zone_start=conflict_start,
        convergence_zone_end=conflict_end,
        spatial_zone_exists=actual_spatial_zone_exists,
        temporal_overlap_exists=actual_temporal_overlap_exists,
        true_pass_exists=actual_true_pass_exists,
        has_convergence_policy=actual_has_convergence_policy,
        no_pass_reason_code=actual_no_pass_reason_code,
        copresence_a=copresence_a,
        copresence_b=copresence_b,
        overtakes_a=overtakes_a,
        overtakes_b=overtakes_b,
        total_a=len(df_a),
        total_b=len(df_b)
    )
    
    print(f"  📊 Flow Audit data generated with {len(flow_audit_data)} fields")
    
    # Generate Runner-Level Audit
    print(f"🔍 {seg_id} {event_a} vs {event_b} RUNNER-LEVEL AUDIT GENERATION:")
    runner_audit_data = None
    
    try:
        # Get date-based output directory for audit files
        try:
            from .report_utils import get_date_folder_path
        except ImportError:
            from report_utils import get_date_folder_path
        
        date_folder_path, _ = get_date_folder_path(output_dir)
        
        # Extract runner timing data
        runner_data = extract_runner_timing_data_for_audit(
            df_a, df_b, event_a, event_b, start_times,
            from_km_a, to_km_a, from_km_b, to_km_b, date_folder_path
        )
        print(f"  📊 Runner timing data extracted: {runner_data['runners_a_count']} {event_a}, {runner_data['runners_b_count']} {event_b}")
        
        # Generate runner audit
        audit_results = emit_runner_audit(
            event_a_csv=runner_data['event_a_csv'],
            event_b_csv=runner_data['event_b_csv'],
            out_dir=date_folder_path,
            run_id=f"{datetime.now().strftime('%Y-%m-%dT%H:%M')}Z",
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
            row_cap_per_shard=50000,
            strict_min_dwell=5,
            strict_margin=2
        )
        
        print(f"  📊 Runner audit generated:")
        print(f"    - Index: {audit_results['index_csv']}")
        print(f"    - Shards: {len(audit_results['shard_csvs'])} files")
        print(f"    - TopK: {audit_results['topk_csv']}")
        print(f"    - Stats: {audit_results['stats']['overlapped_pairs']} overlaps, {audit_results['stats']['raw_pass']} raw passes, {audit_results['stats']['strict_pass']} strict passes")
        
        runner_audit_data = audit_results
        
    except Exception as e:
        print(f"  ⚠️ Runner audit generation failed: {e}")
        runner_audit_data = None
    
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

