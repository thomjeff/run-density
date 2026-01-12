"""
Baseline Metrics Calculator

Calculates baseline metrics from existing runner CSV files including
percentile quantiles (P00, P05, P25, P50, P75, P95, P100) and pace ranges.

Issue: #676 - Utility to create new runner files
"""

from typing import Dict, Any
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


def calculate_baseline_metrics(runners_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate baseline metrics from runner DataFrame.
    
    Computes participant count, percentile quantiles (P00-P100), and
    pace ranges for each percentile segment.
    
    Args:
        runners_df: DataFrame with columns: event, runner_id, pace, distance, start_offset
    
    Returns:
        Dictionary with baseline metrics:
        {
            "base_participants": int,
            "base_p00": float,  # min/lead pace
            "base_p05": float,
            "base_p25": float,
            "base_p50": float,  # median
            "base_p75": float,
            "base_p95": float,
            "base_p100": float,  # max/last pace
            "base_pace_ranges": {
                "fastest_5": {"min": float, "max": float},
                "next_20": {"min": float, "max": float},
                "mid_50": {"min": float, "max": float},
                "bottom_20": {"min": float, "max": float},
                "slowest_5": {"min": float, "max": float}
            }
        }
    
    Raises:
        ValueError: If required columns are missing or data is invalid
    
    Issue: #676 - Baseline metrics calculation
    """
    # Validate required columns
    required = {"event", "runner_id", "pace", "distance"}
    missing = required - set(runners_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Validate data
    if len(runners_df) == 0:
        raise ValueError("Runner DataFrame is empty")
    
    if runners_df["pace"].min() <= 0:
        raise ValueError("Pace values must be positive")
    
    # Calculate participant count
    base_participants = len(runners_df)
    
    # Sort by pace for percentile calculation
    pace_sorted = runners_df["pace"].sort_values()
    
    # Calculate percentile quantiles
    quantiles = [0.0, 0.05, 0.25, 0.50, 0.75, 0.95, 1.0]
    percentile_values = pace_sorted.quantile(quantiles).tolist()
    
    base_p00 = float(percentile_values[0])  # min/lead
    base_p05 = float(percentile_values[1])
    base_p25 = float(percentile_values[2])
    base_p50 = float(percentile_values[3])  # median
    base_p75 = float(percentile_values[4])
    base_p95 = float(percentile_values[5])
    base_p100 = float(percentile_values[6])  # max/last
    
    # Calculate pace ranges for each percentile segment
    base_pace_ranges = {
        "fastest_5": {"min": base_p00, "max": base_p05},
        "next_20": {"min": base_p05, "max": base_p25},
        "mid_50": {"min": base_p25, "max": base_p75},
        "bottom_20": {"min": base_p75, "max": base_p95},
        "slowest_5": {"min": base_p95, "max": base_p100}
    }
    
    # Get distance (should be same for all runners)
    distance = float(runners_df["distance"].iloc[0])
    
    logger.info(
        f"Calculated baseline metrics: {base_participants} participants, "
        f"pace range [{base_p00:.2f}, {base_p100:.2f}] min/km"
    )
    
    return {
        "runners_file": None,  # Will be set by caller
        "base_participants": base_participants,
        "base_p00": base_p00,
        "base_p05": base_p05,
        "base_p25": base_p25,
        "base_p50": base_p50,
        "base_p75": base_p75,
        "base_p95": base_p95,
        "base_p100": base_p100,
        "base_pace_ranges": base_pace_ranges,
        "distance": distance
    }
