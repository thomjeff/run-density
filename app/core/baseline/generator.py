"""
Baseline Runner File Generator

Generates new runner CSV files with scenario-based modifications including
percentile-based pace adjustments and participant count changes.

Issue: #676 - Utility to create new runner files
"""

from typing import Dict, Any, Optional, Callable, Set
import pandas as pd
import numpy as np
import logging

from app.utils.run_id import generate_unique_runner_ids

logger = logging.getLogger(__name__)


def build_multiplier_curve(
    quantiles: Dict[str, float],
    chg_values: Dict[str, float]
) -> Callable[[np.ndarray], np.ndarray]:
    """
    Build piecewise-linear multiplier function from quantile changes.
    
    Creates an interpolation function that maps percentile ranks (0.0-1.0)
    to pace multipliers based on control variable changes at quantile anchors.
    
    Args:
        quantiles: Dictionary with keys p00, p05, p25, p50, p75, p95, p100
        chg_values: Dictionary with keys chg_p00, chg_p05, chg_p25, chg_p50,
                    chg_p75, chg_p95, chg_p100 (percentage changes)
    
    Returns:
        Function that takes percentile ranks (0.0-1.0) and returns multipliers
    
    Issue: #676 - Percentile-first pace adjustment
    """
    # Anchor points: percentile ranks
    anchors = np.array([0.0, 0.05, 0.25, 0.50, 0.75, 0.95, 1.0])
    
    # Multipliers at each anchor: (1 + chg_value)
    multipliers = np.array([
        1.0 + chg_values.get("chg_p00", 0.0),
        1.0 + chg_values.get("chg_p05", 0.0),
        1.0 + chg_values.get("chg_p25", 0.0),
        1.0 + chg_values.get("chg_p50", 0.0),
        1.0 + chg_values.get("chg_p75", 0.0),
        1.0 + chg_values.get("chg_p95", 0.0),
        1.0 + chg_values.get("chg_p100", 0.0),
    ])
    
    def multiplier_func(percentile_ranks: np.ndarray) -> np.ndarray:
        """
        Interpolate multipliers for given percentile ranks.
        
        Uses numpy.interp for piecewise-linear interpolation.
        Handles values outside [0.0, 1.0] by extrapolation.
        """
        # Clip to [0.0, 1.0] range for safety
        clipped_ranks = np.clip(percentile_ranks, 0.0, 1.0)
        
        # Linear interpolation
        interpolated = np.interp(clipped_ranks, anchors, multipliers)
        
        return interpolated
    
    return multiplier_func


def apply_pace_adjustments(
    df: pd.DataFrame,
    multiplier_curve: Callable[[np.ndarray], np.ndarray]
) -> pd.DataFrame:
    """
    Apply percentile-based pace adjustments to runner DataFrame.
    
    Args:
        df: DataFrame with 'pace' column
        multiplier_curve: Function that maps percentile ranks to multipliers
    
    Returns:
        DataFrame with adjusted paces, sorted by pace
    
    Issue: #676 - Percentile-first pace adjustment
    """
    df = df.copy()
    df_sorted = df.sort_values("pace").reset_index(drop=True)
    
    # Compute percentile rank for each runner
    n = len(df_sorted)
    if n > 1:
        percentile_ranks = np.arange(n) / (n - 1)  # 0.0 to 1.0
    else:
        percentile_ranks = np.array([0.5])  # Single runner at median
    
    # Apply multiplier
    multipliers = multiplier_curve(percentile_ranks)
    df_sorted["pace"] = df_sorted["pace"].values * multipliers
    
    # Preserve monotonic ordering (sort again after adjustment)
    df_sorted = df_sorted.sort_values("pace").reset_index(drop=True)
    
    return df_sorted


def allocate_participants(
    new_total: int,
    segment_percentages: Dict[str, float]
) -> Dict[str, int]:
    """
    Allocate participants to segments with remainder handling.
    
    Uses floor division with remainder allocated starting from mid_50
    (largest segment), then outward.
    
    Args:
        new_total: Total number of participants
        segment_percentages: Dictionary mapping segment names to percentages
                            (e.g., {"fastest_5": 0.05, "next_20": 0.20, ...})
    
    Returns:
        Dictionary mapping segment names to participant counts
    
    Issue: #676 - Participant count allocation
    """
    # Calculate floor counts
    floor_counts = {
        seg: int(new_total * pct)
        for seg, pct in segment_percentages.items()
    }
    
    # Calculate remainder
    remainder = new_total - sum(floor_counts.values())
    
    # Allocation order: mid_50 (largest) → next_20 → bottom_20 → fastest_5 → slowest_5
    allocation_order = ["mid_50", "next_20", "bottom_20", "fastest_5", "slowest_5"]
    
    # Distribute remainder
    for seg in allocation_order:
        if remainder <= 0:
            break
        if seg in floor_counts:
            floor_counts[seg] += 1
            remainder -= 1
    
    return floor_counts


def sample_new_runners(
    n_runners: int,
    segment_name: str,
    new_quantiles: Dict[str, float],
    baseline_start_offsets: np.ndarray,
    multiplier_curve: Callable[[np.ndarray], np.ndarray]
) -> pd.DataFrame:
    """
    Sample new runners for a percentile segment.
    
    Args:
        n_runners: Number of runners to generate
        segment_name: Segment name (fastest_5, next_20, mid_50, bottom_20, slowest_5)
        new_quantiles: Dictionary with new quantile values (p00, p05, p25, p50, p75, p95, p100)
        baseline_start_offsets: Array of baseline start_offset values for sampling
        multiplier_curve: Function for pace interpolation
    
    Returns:
        DataFrame with columns: pace, start_offset
    
    Issue: #676 - New runner sampling (no skew)
    """
    # Map segment to percentile range
    segment_ranges = {
        "fastest_5": (0.0, 0.05),
        "next_20": (0.05, 0.25),
        "mid_50": (0.25, 0.75),
        "bottom_20": (0.75, 0.95),
        "slowest_5": (0.95, 1.0)
    }
    
    p_min, p_max = segment_ranges.get(segment_name, (0.0, 1.0))
    
    # Sample percentiles uniformly within segment
    percentile_samples = np.random.uniform(p_min, p_max, size=n_runners)
    
    # Get multipliers for sampled percentiles
    multipliers = multiplier_curve(percentile_samples)
    
    # Calculate base paces from new quantiles using linear interpolation
    anchors = np.array([0.0, 0.05, 0.25, 0.50, 0.75, 0.95, 1.0])
    base_paces = np.array([
        new_quantiles["p00"],
        new_quantiles["p05"],
        new_quantiles["p25"],
        new_quantiles["p50"],
        new_quantiles["p75"],
        new_quantiles["p95"],
        new_quantiles["p100"]
    ])
    
    # Interpolate base paces for sampled percentiles
    interpolated_base_paces = np.interp(percentile_samples, anchors, base_paces)
    
    # Apply multipliers to get final paces
    paces = interpolated_base_paces * multipliers
    
    # Sample start_offset from baseline distribution
    if len(baseline_start_offsets) > 0:
        start_offsets = np.random.choice(
            baseline_start_offsets,
            size=n_runners,
            replace=True
        )
    else:
        start_offsets = np.zeros(n_runners, dtype=int)
    
    return pd.DataFrame({
        "pace": paces,
        "start_offset": start_offsets
    })


def validate_cutoff_time(
    event_name: str,
    max_pace: float,
    distance: float,
    cutoff_mins: Optional[float]
) -> None:
    """
    Validate that slowest runner meets cut-off time.
    
    Args:
        event_name: Event name for error message
        max_pace: Maximum pace (min/km) in the generated file
        distance: Event distance (km)
        cutoff_mins: Optional cut-off time in minutes
    
    Raises:
        ValueError: If cut-off time is violated
    
    Issue: #676 - Cut-off validation
    """
    if cutoff_mins is None:
        return  # No cut-off configured, skip validation
    
    finish_time = max_pace * distance
    if finish_time > cutoff_mins:
        max_allowed_pace = cutoff_mins / distance
        raise ValueError(
            f"Event '{event_name}' cut-off time violation:\n"
            f"  Max pace: {max_pace:.2f} min/km\n"
            f"  Distance: {distance:.2f} km\n"
            f"  Computed finish time: {finish_time:.1f} minutes\n"
            f"  Cut-off: {cutoff_mins:.1f} minutes\n"
            f"  Max allowed pace: {max_allowed_pace:.2f} min/km"
        )


def generate_runner_file(
    baseline_df: pd.DataFrame,
    control_vars: Dict[str, float],
    new_participants: int,
    event_name: str,
    distance: float,
    cutoff_mins: Optional[float],
    used_runner_ids: Set[str]
) -> pd.DataFrame:
    """
    Generate new runner file with scenario-based modifications.
    
    Args:
        baseline_df: Baseline runner DataFrame
        control_vars: Control variables (chg_participants, chg_p00, chg_p05, ...)
        new_participants: Target number of participants
        event_name: Event name
        distance: Event distance (km)
        cutoff_mins: Optional cut-off time in minutes
        used_runner_ids: Set of already-used runner IDs (for uniqueness)
    
    Returns:
        DataFrame with columns: event, runner_id, pace, distance, start_offset
    
    Issue: #676 - Runner file generation
    """
    # Calculate baseline quantiles for multiplier curve
    baseline_quantiles = {
        "p00": baseline_df["pace"].min(),
        "p05": baseline_df["pace"].quantile(0.05),
        "p25": baseline_df["pace"].quantile(0.25),
        "p50": baseline_df["pace"].quantile(0.50),
        "p75": baseline_df["pace"].quantile(0.75),
        "p95": baseline_df["pace"].quantile(0.95),
        "p100": baseline_df["pace"].max()
    }
    
    # Build multiplier curve
    multiplier_curve = build_multiplier_curve(baseline_quantiles, control_vars)
    
    # Apply pace adjustments to existing runners
    adjusted_df = apply_pace_adjustments(baseline_df, multiplier_curve)
    
    # Calculate new quantiles after adjustment
    new_quantiles = {
        "p00": adjusted_df["pace"].min(),
        "p05": adjusted_df["pace"].quantile(0.05),
        "p25": adjusted_df["pace"].quantile(0.25),
        "p50": adjusted_df["pace"].quantile(0.50),
        "p75": adjusted_df["pace"].quantile(0.75),
        "p95": adjusted_df["pace"].quantile(0.95),
        "p100": adjusted_df["pace"].max()
    }
    
    # Calculate number of new runners to add
    base_participants = len(baseline_df)
    num_new_runners = max(0, new_participants - base_participants)
    
    # Allocate participants to segments
    segment_percentages = {
        "fastest_5": 0.05,
        "next_20": 0.20,
        "mid_50": 0.50,
        "bottom_20": 0.20,
        "slowest_5": 0.05
    }
    segment_counts = allocate_participants(new_participants, segment_percentages)
    
    # Sample new runners for each segment
    baseline_start_offsets = baseline_df["start_offset"].values
    new_runners_list = []
    
    for segment_name, count in segment_counts.items():
        if count > 0:
            segment_runners = sample_new_runners(
                n_runners=count,
                segment_name=segment_name,
                new_quantiles=new_quantiles,
                baseline_start_offsets=baseline_start_offsets,
                multiplier_curve=multiplier_curve
            )
            new_runners_list.append(segment_runners)
    
    # Combine existing (adjusted) and new runners
    if new_runners_list:
        new_runners_df = pd.concat(new_runners_list, ignore_index=True)
        combined_df = pd.concat([adjusted_df[["pace", "start_offset"]], new_runners_df], ignore_index=True)
    else:
        combined_df = adjusted_df[["pace", "start_offset"]].copy()
    
    # Sort by pace
    combined_df = combined_df.sort_values("pace").reset_index(drop=True)
    
    # Generate unique runner IDs
    num_runners = len(combined_df)
    runner_ids = generate_unique_runner_ids(n=num_runners, used_ids=used_runner_ids)
    combined_df["runner_id"] = runner_ids
    combined_df["event"] = event_name
    combined_df["distance"] = distance
    
    # Reorder columns
    result_df = combined_df[["event", "runner_id", "pace", "distance", "start_offset"]].copy()
    
    # Validate cut-off time
    max_pace = result_df["pace"].max()
    validate_cutoff_time(event_name, max_pace, distance, cutoff_mins)
    
    logger.info(
        f"Generated {len(result_df)} runners for event '{event_name}': "
        f"{base_participants} existing (adjusted) + {num_new_runners} new"
    )
    
    return result_df
