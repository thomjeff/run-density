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
        thresholds: Custom LOS thresholds (not supported; rulebook SSOT only)
        
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
    if thresholds is not None:
        raise ValueError("Custom LOS thresholds are not allowed; rulebook SSOT must be used.")
    from app import rulebook
    bands = rulebook.get_thresholds("on_course_open").los
    
    # Handle edge cases
    if pd.isna(density) or density < 0:
        logger.warning(f"Invalid density value: {density}, defaulting to LOS A")
        return 'A'
    
    return rulebook.classify_los(density, bands)


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
        thresholds: Custom LOS thresholds (not supported; rulebook SSOT only)
        
    Returns:
        DataFrame with added 'los' and 'los_rank' columns
    """
    if density_field not in df.columns:
        logger.error(f"Density field '{density_field}' not found in DataFrame")
        return df
    
    if thresholds is not None:
        raise ValueError("Custom LOS thresholds are not allowed; rulebook SSOT must be used.")
    
    # Classify each bin
    df['los'] = df[density_field].apply(los_from_density)
    
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


# Phase 3 cleanup: Removed unused functions (not imported anywhere):
# - get_los_color() - Not used (main.py has its own _get_los_color)
# - summarize_los_distribution() - Not imported
# - get_worst_los() - Not imported
# - filter_by_los_threshold() - Not imported
