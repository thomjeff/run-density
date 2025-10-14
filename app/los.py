"""
Level of Service (LOS) Classification Module

This module provides utilities for classifying pedestrian density levels
based on Fruin's Level of Service standards and custom thresholds.

LOS levels (A-F) represent pedestrian comfort and flow quality:
- A: Free flow, no restrictions
- B: Stable flow, minor speed restrictions
- C: Stable flow, significant speed restrictions
- D: Unstable flow, severe restrictions
- E: Very unstable flow, stop-and-go
- F: Breakdown flow, gridlock

Issue #233: Operational Intelligence - LOS Classification
"""

from __future__ import annotations
import logging
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Default LOS thresholds (areal density in people per square meter)
DEFAULT_LOS_THRESHOLDS = {
    'A': 0.0,   # Free flow
    'B': 0.5,   # Stable flow, minor restrictions
    'C': 1.0,   # Stable flow, significant restrictions
    'D': 1.5,   # Unstable flow, severe restrictions
    'E': 2.0,   # Very unstable flow, stop-and-go
    'F': 3.0    # Breakdown flow, gridlock
}

# LOS rank ordering (for comparisons and severity assignment)
LOS_RANKS = {
    'A': 0,
    'B': 1,
    'C': 2,
    'D': 3,
    'E': 4,
    'F': 5
}


def los_from_density(
    density: float,
    thresholds: Optional[Dict[str, float]] = None
) -> str:
    """
    Classify density into Level of Service (A-F).
    
    Uses lower-bound thresholds: density >= threshold_X assigns LOS X.
    The highest threshold met determines the LOS level.
    
    Args:
        density: Areal density (people per square meter)
        thresholds: Custom LOS thresholds (optional, uses defaults if not provided)
        
    Returns:
        LOS classification ('A', 'B', 'C', 'D', 'E', or 'F')
        
    Examples:
        >>> los_from_density(0.3)  # Below B threshold
        'A'
        >>> los_from_density(1.2)  # Above C threshold, below D
        'C'
        >>> los_from_density(3.5)  # Above F threshold
        'F'
    """
    if thresholds is None:
        thresholds = DEFAULT_LOS_THRESHOLDS
    
    # Handle edge cases
    if pd.isna(density) or density < 0:
        logger.warning(f"Invalid density value: {density}, defaulting to LOS A")
        return 'A'
    
    # Sort thresholds by value (descending) to find highest threshold met
    sorted_thresholds = sorted(
        thresholds.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Find the highest threshold that density meets or exceeds
    for los_level, threshold in sorted_thresholds:
        if density >= threshold:
            return los_level
    
    # If no threshold is met, return the lowest LOS (A)
    return 'A'


def los_rank(los_level: str) -> int:
    """
    Get numeric rank for a LOS level (A=0, B=1, ..., F=5).
    
    This is useful for:
    - Comparing LOS levels (e.g., is LOS D worse than LOS C?)
    - Sorting by severity
    - Determining if a level meets a minimum threshold
    
    Args:
        los_level: LOS classification ('A' through 'F')
        
    Returns:
        Numeric rank (0-5) or -1 for invalid input
        
    Examples:
        >>> los_rank('A')
        0
        >>> los_rank('C')
        2
        >>> los_rank('F')
        5
        >>> los_rank('C') >= los_rank('C')  # Check if meets minimum threshold
        True
    """
    if los_level not in LOS_RANKS:
        logger.warning(f"Invalid LOS level: {los_level}, returning -1")
        return -1
    
    return LOS_RANKS[los_level]


def meets_los_threshold(los_level: str, min_threshold: str) -> bool:
    """
    Check if a LOS level meets or exceeds a minimum threshold.
    
    Args:
        los_level: LOS classification to check
        min_threshold: Minimum acceptable LOS level
        
    Returns:
        True if los_level >= min_threshold (worse or equal), False otherwise
        
    Examples:
        >>> meets_los_threshold('D', 'C')  # D is worse than C
        True
        >>> meets_los_threshold('B', 'C')  # B is better than C
        False
        >>> meets_los_threshold('C', 'C')  # Equal
        True
    """
    return los_rank(los_level) >= los_rank(min_threshold)


def classify_bins_los(
    df: pd.DataFrame,
    density_field: str = 'density_peak',
    thresholds: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Classify all bins in a DataFrame by LOS level.
    
    Adds 'los' and 'los_rank' columns to the DataFrame.
    
    Args:
        df: DataFrame with density data
        density_field: Column name containing density values (default: 'density_peak')
        thresholds: Custom LOS thresholds (optional)
        
    Returns:
        DataFrame with added 'los' and 'los_rank' columns
    """
    if density_field not in df.columns:
        logger.error(f"Density field '{density_field}' not found in DataFrame")
        return df
    
    if thresholds is None:
        thresholds = DEFAULT_LOS_THRESHOLDS
    
    # Classify each bin
    df['los'] = df[density_field].apply(
        lambda d: los_from_density(d, thresholds)
    )
    
    # Add numeric rank for sorting/filtering
    df['los_rank'] = df['los'].apply(los_rank)
    
    logger.info(f"Classified {len(df)} bins by LOS")
    logger.debug(f"LOS distribution: {df['los'].value_counts().to_dict()}")
    
    return df


def get_los_description(los_level: str) -> str:
    """
    Get human-readable description for a LOS level.
    
    Args:
        los_level: LOS classification ('A' through 'F')
        
    Returns:
        Description string
    """
    descriptions = {
        'A': 'Free flow, no restrictions',
        'B': 'Stable flow, minor speed restrictions',
        'C': 'Stable flow, significant speed restrictions',
        'D': 'Unstable flow, severe restrictions',
        'E': 'Very unstable flow, stop-and-go',
        'F': 'Breakdown flow, gridlock'
    }
    
    return descriptions.get(los_level, 'Unknown LOS level')


def get_los_color(los_level: str, color_scheme: Optional[Dict[str, str]] = None) -> str:
    """
    Get color code for a LOS level (for visualization).
    
    Args:
        los_level: LOS classification ('A' through 'F')
        color_scheme: Custom color scheme (optional)
        
    Returns:
        Hex color code
    """
    if color_scheme is None:
        color_scheme = {
            'A': '#4CAF50',   # Green - excellent
            'B': '#8BC34A',   # Light green - good
            'C': '#FFC107',   # Amber - acceptable
            'D': '#FF9800',   # Orange - concerning
            'E': '#FF5722',   # Red-orange - poor
            'F': '#F44336'    # Red - unacceptable
        }
    
    return color_scheme.get(los_level, '#808080')  # Gray for unknown


def summarize_los_distribution(df: pd.DataFrame, los_column: str = 'los') -> Dict[str, int]:
    """
    Summarize LOS distribution across bins.
    
    Args:
        df: DataFrame with LOS classifications
        los_column: Column name containing LOS values
        
    Returns:
        Dictionary mapping LOS level to count
    """
    if los_column not in df.columns:
        logger.warning(f"LOS column '{los_column}' not found in DataFrame")
        return {}
    
    distribution = df[los_column].value_counts().to_dict()
    
    # Ensure all LOS levels are represented (even with 0 count)
    for level in ['A', 'B', 'C', 'D', 'E', 'F']:
        if level not in distribution:
            distribution[level] = 0
    
    return distribution


def get_worst_los(df: pd.DataFrame, los_column: str = 'los') -> str:
    """
    Get the worst (highest) LOS level in a DataFrame.
    
    Args:
        df: DataFrame with LOS classifications
        los_column: Column name containing LOS values
        
    Returns:
        Worst LOS level ('F' is worst, 'A' is best)
    """
    if los_column not in df.columns or len(df) == 0:
        return 'A'
    
    los_rank_col = 'los_rank' if 'los_rank' in df.columns else None
    
    if los_rank_col:
        # Use pre-computed ranks if available
        worst_rank = df[los_rank_col].max()
        # Find the LOS level corresponding to this rank
        for level, rank in LOS_RANKS.items():
            if rank == worst_rank:
                return level
    
    # Fallback: compute ranks on the fly
    worst_level = 'A'
    worst_rank = -1
    
    for level in df[los_column].unique():
        rank = los_rank(level)
        if rank > worst_rank:
            worst_rank = rank
            worst_level = level
    
    return worst_level


def filter_by_los_threshold(
    df: pd.DataFrame,
    min_threshold: str,
    los_column: str = 'los'
) -> pd.DataFrame:
    """
    Filter DataFrame to bins meeting or exceeding a LOS threshold.
    
    Args:
        df: DataFrame with LOS classifications
        min_threshold: Minimum LOS level to include (e.g., 'C')
        los_column: Column name containing LOS values
        
    Returns:
        Filtered DataFrame with bins >= min_threshold
    """
    if los_column not in df.columns:
        logger.warning(f"LOS column '{los_column}' not found in DataFrame")
        return pd.DataFrame()
    
    min_rank = los_rank(min_threshold)
    
    # Use pre-computed ranks if available
    if 'los_rank' in df.columns:
        return df[df['los_rank'] >= min_rank].copy()
    
    # Compute ranks on the fly
    df_copy = df.copy()
    df_copy['_temp_rank'] = df_copy[los_column].apply(los_rank)
    result = df_copy[df_copy['_temp_rank'] >= min_rank].drop(columns=['_temp_rank'])
    
    logger.info(f"Filtered to {len(result)} bins with LOS >= {min_threshold}")
    return result

