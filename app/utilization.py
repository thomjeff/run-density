# app/utilization.py
"""
Utilization Percentile Computation

This module computes percentile ranks for rate_per_m_per_min within cohorts,
enabling utilization-based flagging (e.g., top 5% = P95).

Issue #254: Unified Flagging Architecture
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def ensure_rpm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures rate_per_m_per_min exists:
      rpm = (rate_p_s / width_m) * 60
    
    Leaves existing rpm untouched if present.
    
    Args:
        df: DataFrame with 'rate' and 'width_m' columns
        
    Returns:
        DataFrame with 'rate_per_m_per_min' column added (if missing)
    """
    if "rate_per_m_per_min" not in df.columns:
        if not {"rate", "width_m"}.issubset(df.columns):
            raise ValueError("Columns 'rate' and 'width_m' required to derive rate_per_m_per_min.")
        
        rpm = np.where(
            (df["width_m"] > 0) & np.isfinite(df["rate"]),
            (df["rate"] / df["width_m"]) * 60.0,
            np.nan
        )
        df = df.copy()
        df["rate_per_m_per_min"] = rpm
        logger.info(f"Computed rate_per_m_per_min for {len(df)} bins")
    
    return df


def _percentile_rank(values: pd.Series) -> pd.Series:
    """
    Percentile rank in [0,100] using average rank for ties.
    NaNs are returned as NaN.
    
    Args:
        values: Series of numeric values
        
    Returns:
        Series of percentile ranks (0-100)
    """
    s = values.astype(float)
    mask = s.notna()
    
    if mask.sum() <= 1:
        # 0 or 1 valid values → all NaN or 100.0 (define as 100 for the single value)
        out = pd.Series(np.nan, index=s.index, dtype=float)
        if mask.sum() == 1:
            out.loc[mask] = 100.0
        return out

    ranks = s[mask].rank(method="average", pct=True) * 100.0
    out = pd.Series(np.nan, index=s.index, dtype=float)
    out.loc[mask] = ranks
    return out


def add_utilization_percentile(
    df: pd.DataFrame,
    cohort: str = "window",  # "global" | "window" | "window_schema" | "window_segment"
    rpm_col: str = "rate_per_m_per_min",
    out_col: str = "util_percentile",
) -> pd.DataFrame:
    """
    Adds util_percentile (0..100) per bin based on rpm percentile within the selected cohort.
    
    Cohort options:
    - "global": Across all bins (legacy behavior - tends to flag more)
    - "window": Per window_idx, course-wide (recommended - captures relative surges)
    - "window_schema": Per (window_idx, schema_key) - compares within schema type
    - "window_segment": Per (window_idx, segment_id) - compares within same segment
    
    Args:
        df: DataFrame with bins data
        cohort: Cohort definition for percentile calculation
        rpm_col: Column name for rate per meter per minute
        out_col: Output column name for percentile rank
        
    Returns:
        DataFrame with util_percentile column added
        
    Example:
        bins = add_utilization_percentile(bins, cohort="window")
        # Now bins has util_percentile where top 5% have values >= 95
    """
    needed = {rpm_col}
    if cohort in ("window", "window_schema", "window_segment"):
        needed.add("window_idx")
    if cohort == "window_schema":
        needed.add("schema_key")
    elif cohort == "window_segment":
        needed.add("segment_id")
    
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for cohort='{cohort}': {missing}")

    df = ensure_rpm(df).copy()

    # Determine grouping keys
    if cohort == "global":
        grp_keys = []  # No grouping - compute across all bins
    elif cohort == "window":
        grp_keys = ["window_idx"]
    elif cohort == "window_schema":
        grp_keys = ["window_idx", "schema_key"]
    elif cohort == "window_segment":
        grp_keys = ["window_idx", "segment_id"]
    else:
        raise ValueError(f"Unsupported cohort: {cohort}. Must be 'global', 'window', 'window_schema', or 'window_segment'")

    logger.info(f"Computing utilization percentiles using cohort='{cohort}'")
    
    # Compute percentile rank within each cohort
    if cohort == "global":
        # Global: compute percentile across all bins (no grouping)
        df[out_col] = _percentile_rank(df[rpm_col]).astype(float)
    else:
        # Grouped: compute percentile within each group
        df[out_col] = (
            df.groupby(grp_keys, group_keys=False)[rpm_col]
              .apply(_percentile_rank)
              .astype(float)
        )
    
    # Log statistics
    valid_pctile = df[out_col].notna()
    if valid_pctile.sum() > 0:
        p95_count = len(df[df[out_col] >= 95.0])
        logger.info(f"Utilization percentiles computed: {valid_pctile.sum()} bins, {p95_count} in top 5%")
    
    return df

