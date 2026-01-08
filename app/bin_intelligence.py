"""
Bin Intelligence Module

This module implements operational intelligence flagging logic for canonical bins.
It applies LOS (Level of Service) thresholds and utilization percentile analysis
to identify bins requiring operational attention.

Flagging Logic:
- LOS_HIGH: Bin density meets or exceeds minimum LOS threshold (e.g., LOS >= C)
- UTILIZATION_HIGH: Bin density in top N% globally (e.g., top 5%)
- BOTH: Both conditions met
- NONE: Neither condition met

Severity Assignment:
- CRITICAL: Both LOS and utilization thresholds exceeded
- CAUTION: LOS threshold exceeded only
- WATCH: Utilization threshold exceeded only
- NONE: No thresholds exceeded

Issue #233: Operational Intelligence - Bin Flagging
"""

from __future__ import annotations
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

import pandas as pd
import numpy as np

from app import rulebook

logger = logging.getLogger(__name__)

LOS_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


@dataclass
class FlaggingConfig:
    """Configuration for bin flagging logic."""
    min_los_flag: str = 'C'              # Minimum LOS level to flag
    utilization_pctile: int = 95         # Percentile for utilization flagging
    require_min_bin_len_m: float = 10.0  # Minimum bin length to consider
    density_field: str = 'density_peak'  # Density field to use for analysis
    
    def __post_init__(self):
        """Validate configuration."""
        valid_los = ['A', 'B', 'C', 'D', 'E', 'F']
        if self.min_los_flag not in valid_los:
            raise ValueError(f"Invalid min_los_flag: {self.min_los_flag}")
        
        if not 0 <= self.utilization_pctile <= 100:
            raise ValueError(f"Invalid utilization_pctile: {self.utilization_pctile}")
        
        if self.require_min_bin_len_m < 0:
            raise ValueError(f"Invalid require_min_bin_len_m: {self.require_min_bin_len_m}")


def compute_utilization_threshold(
    df: pd.DataFrame,
    density_field: str = 'density_peak',
    percentile: int = 95
) -> float:
    """
    Compute global utilization threshold at specified percentile.
    
    Args:
        df: DataFrame with density data
        density_field: Column name containing density values
        percentile: Percentile for threshold (e.g., 95 for top 5%)
        
    Returns:
        Density value at the specified percentile
    """
    if density_field not in df.columns:
        logger.error(f"Density field '{density_field}' not found in DataFrame")
        return float('inf')
    
    # Filter out invalid values
    valid_densities = df[density_field].dropna()
    valid_densities = valid_densities[valid_densities >= 0]
    
    if len(valid_densities) == 0:
        logger.warning("No valid density values found, returning inf")
        return float('inf')
    
    threshold = float(valid_densities.quantile(percentile / 100.0))
    
    logger.info(f"Computed P{percentile} utilization threshold: {threshold:.4f}")
    return threshold


def classify_flag_reason(
    meets_los: bool,
    meets_util: bool
) -> str:
    """
    Classify flag reason based on threshold conditions.
    
    Args:
        meets_los: Whether LOS threshold is met
        meets_util: Whether utilization threshold is met
        
    Returns:
        Flag reason: 'BOTH', 'LOS_HIGH', 'UTILIZATION_HIGH', or 'NONE'
    """
    if meets_los and meets_util:
        return 'BOTH'
    elif meets_los:
        return 'LOS_HIGH'
    elif meets_util:
        return 'UTILIZATION_HIGH'
    else:
        return 'NONE'


def classify_severity(flag_reason: str) -> str:
    """
    Classify severity based on flag reason.
    
    Args:
        flag_reason: Flag reason ('BOTH', 'LOS_HIGH', 'UTILIZATION_HIGH', 'NONE')
        
    Returns:
        Severity level: 'CRITICAL', 'CAUTION', 'WATCH', or 'NONE'
    """
    severity_map = {
        'BOTH': 'CRITICAL',
        'LOS_HIGH': 'CAUTION',
        'UTILIZATION_HIGH': 'WATCH',
        'NONE': 'NONE'
    }
    
    return severity_map.get(flag_reason, 'NONE')


def get_severity_rank(severity: str) -> int:
    """
    Get numeric rank for severity level (for sorting).
    
    Args:
        severity: Severity level
        
    Returns:
        Numeric rank (higher is more severe)
    """
    ranks = {
        'CRITICAL': 3,
        'CAUTION': 2,
        'WATCH': 1,
        'NONE': 0
    }
    
    return ranks.get(severity, 0)


def filter_by_min_bin_length(
    df: pd.DataFrame,
    min_length_m: float,
    bin_len_col: str = 'bin_len_m'
) -> pd.DataFrame:
    """
    Filter bins by minimum length requirement.
    
    Args:
        df: DataFrame with bins data
        min_length_m: Minimum bin length in meters
        bin_len_col: Column name for bin length
        
    Returns:
        Filtered DataFrame
    """
    if bin_len_col not in df.columns:
        logger.warning(f"Bin length column '{bin_len_col}' not found, skipping filter")
        return df
    
    filtered = df[df[bin_len_col] >= min_length_m].copy()
    
    logger.info(f"Filtered to {len(filtered)} bins with length >= {min_length_m}m "
                f"(removed {len(df) - len(filtered)} short bins)")
    
    return filtered


def apply_bin_flagging(
    df: pd.DataFrame,
    config: FlaggingConfig
) -> pd.DataFrame:
    """
    Apply operational intelligence flagging to bins.
    
    This is the main entry point for bin intelligence analysis.
    Adds the following columns to the DataFrame:
    - los_class: LOS classification (A-F)
    - los_rank: Numeric rank for LOS (0-5)
    - flag_reason: Why bin was flagged (BOTH, LOS_HIGH, UTILIZATION_HIGH, NONE)
    - severity: Severity level (CRITICAL, CAUTION, WATCH, NONE)
    - severity_rank: Numeric rank for severity (3=CRITICAL, 0=NONE)
    - is_flagged: Boolean indicating if bin is flagged (severity != NONE)
    
    Args:
        df: DataFrame with canonical bins data
        config: Flagging configuration
    Returns:
        DataFrame with added flagging columns
    """
    logger.info(f"Applying bin flagging to {len(df)} bins")
    
    # Make a copy to avoid modifying original
    result = df.copy()
    
    # Step 1: Filter by minimum bin length if specified
    if config.require_min_bin_len_m > 0:
        result = filter_by_min_bin_length(result, config.require_min_bin_len_m)
    
    if len(result) == 0:
        logger.warning("No bins remaining after length filter")
        return result
    
    # Step 2: Classify bins by LOS using rulebook SSOT
    if config.density_field not in result.columns:
        raise ValueError(f"Density field '{config.density_field}' not found in DataFrame")
    bands = rulebook.get_thresholds("on_course_open").los
    result['los_class'] = result[config.density_field].apply(
        lambda d: rulebook.classify_los(d, bands)
    )
    result['los_rank'] = result['los_class'].map(LOS_ORDER).fillna(-1).astype(int)
    
    # Step 3: Compute global utilization threshold
    util_threshold = compute_utilization_threshold(
        result,
        density_field=config.density_field,
        percentile=config.utilization_pctile
    )
    
    # Step 4: Determine which bins meet each threshold
    result['meets_los_threshold'] = result['los_class'].apply(
        lambda los_class: rulebook.los_ge(los_class, config.min_los_flag)
    )
    
    result['meets_util_threshold'] = result[config.density_field] >= util_threshold
    
    # Step 5: Classify flag reason and severity
    result['flag_reason'] = result.apply(
        lambda row: classify_flag_reason(
            row['meets_los_threshold'],
            row['meets_util_threshold']
        ),
        axis=1
    )
    
    result['severity'] = result['flag_reason'].apply(classify_severity)
    result['severity_rank'] = result['severity'].apply(get_severity_rank)
    
    # Step 6: Add convenience boolean flag
    result['is_flagged'] = result['severity'] != 'NONE'
    
    # Clean up temporary columns
    result = result.drop(columns=['meets_los_threshold', 'meets_util_threshold'])
    
    # Log summary statistics
    flagged_count = result['is_flagged'].sum()
    severity_dist = result['severity'].value_counts().to_dict()
    
    logger.info(f"Flagging complete: {flagged_count}/{len(result)} bins flagged")
    logger.info(f"Severity distribution: {severity_dist}")
    
    return result


def get_flagged_bins(
    df: pd.DataFrame,
    severity_filter: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Get flagged bins, optionally filtered by severity.
    
    Args:
        df: DataFrame with flagging applied
        severity_filter: List of severity levels to include (None = all flagged)
        
    Returns:
        DataFrame with only flagged bins
    """
    if 'is_flagged' not in df.columns:
        logger.warning("No flagging columns found in DataFrame")
        return pd.DataFrame()
    
    # Start with all flagged bins
    result = df[df['is_flagged']].copy()
    
    # Apply severity filter if specified
    if severity_filter:
        result = result[result['severity'].isin(severity_filter)]
    
    logger.info(f"Retrieved {len(result)} flagged bins "
                f"(filter: {severity_filter or 'all'})")
    
    return result


def summarize_segment_flags(
    df: pd.DataFrame,
    segment_id_col: str = 'segment_id'
) -> pd.DataFrame:
    """
    Roll up bin flags to segment level, selecting worst bin per segment.
    
    For each segment, identifies:
    - Worst severity level
    - Bin with worst severity (tie-break by highest density)
    - Count of flagged bins
    - Summary statistics
    
    Args:
        df: DataFrame with flagging applied
        segment_id_col: Column name for segment IDs
        
    Returns:
        DataFrame with one row per segment, showing worst-case metrics
    """
    if segment_id_col not in df.columns:
        logger.error(f"Segment ID column '{segment_id_col}' not found")
        return pd.DataFrame()
    
    if 'severity_rank' not in df.columns:
        logger.error("Flagging columns not found, run apply_bin_flagging first")
        return pd.DataFrame()
    
    # Get flagged bins only
    flagged = get_flagged_bins(df)
    
    if len(flagged) == 0:
        logger.info("No flagged bins to summarize")
        return pd.DataFrame()
    
    # Group by segment and find worst bin
    segment_summaries = []
    
    for segment_id in flagged[segment_id_col].unique():
        seg_bins = flagged[flagged[segment_id_col] == segment_id].copy()
        
        # Find worst bin (highest severity_rank, then highest density)
        seg_bins = seg_bins.sort_values(
            by=['severity_rank', 'density_peak'],
            ascending=[False, False]
        )
        
        worst_bin = seg_bins.iloc[0]
        
        summary = {
            'segment_id': segment_id,
            'seg_label': worst_bin.get('seg_label', segment_id),
            'worst_bin_start_km': worst_bin['start_km'],
            'worst_bin_end_km': worst_bin['end_km'],
            'worst_los': worst_bin['los_class'],
            'peak_density': worst_bin['density_peak'],
            'flagged_bin_count': len(seg_bins),
            'severity': worst_bin['severity'],
            'flag_reason': worst_bin['flag_reason'],
            'severity_rank': worst_bin['severity_rank']
        }
        
        segment_summaries.append(summary)
    
    result = pd.DataFrame(segment_summaries)
    
    # Sort by severity (worst first), then by density
    result = result.sort_values(
        by=['severity_rank', 'peak_density'],
        ascending=[False, False]
    )
    
    logger.info(f"Summarized flags for {len(result)} segments")
    
    return result


def get_flagging_statistics(df: pd.DataFrame) -> Dict[str, any]:
    """
    Compute comprehensive statistics on flagging results.
    
    Args:
        df: DataFrame with flagging applied
        
    Returns:
        Dictionary with flagging statistics
    """
    if 'is_flagged' not in df.columns:
        return {'error': 'Flagging columns not found'}
    
    flagged = df[df['is_flagged']]
    
    stats = {
        'total_bins': len(df),
        'flagged_bins': len(flagged),
        'flagged_percentage': (len(flagged) / len(df) * 100) if len(df) > 0 else 0,
        'severity_distribution': df['severity'].value_counts().to_dict(),
        'flag_reason_distribution': df['flag_reason'].value_counts().to_dict(),
        'los_distribution': df['los_class'].value_counts().to_dict(),
        'worst_severity': df['severity'].iloc[df['severity_rank'].idxmax()] if len(df) > 0 else 'NONE',
        'worst_los': df['los_class'].iloc[df['los_rank'].idxmax()] if len(df) > 0 else 'A',
        'peak_density_range': {
            'min': float(df['density_peak'].min()) if 'density_peak' in df.columns else None,
            'max': float(df['density_peak'].max()) if 'density_peak' in df.columns else None,
            'mean': float(df['density_peak'].mean()) if 'density_peak' in df.columns else None,
        }
    }
    
    return stats
