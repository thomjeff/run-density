"""
Canonical Segments Module

This module provides utilities for loading and working with canonical segments
derived from bins data (segment_windows_from_bins.parquet).

This implements ChatGPT's roadmap for Issue #231 - promoting canonical segments
to be the source of truth for all segment time-series data.
"""

from __future__ import annotations
import os
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def find_latest_canonical_segments_file() -> Optional[str]:
    """
    Find the latest canonical segments file (segment_windows_from_bins.parquet).
    
    Returns:
        Path to latest canonical segments file or None if not found
    """
    reports_dir = Path("reports")
    if not reports_dir.exists():
        logger.info("No reports directory found")
        return None
    
    # Find all YYYY-MM-DD subdirectories
    date_dirs = [d for d in reports_dir.iterdir() if d.is_dir() and len(d.name) == 10 and d.name.count('-') == 2]
    
    if not date_dirs:
        logger.info("No date directories found in reports")
        return None
    
    # Sort by date (newest first)
    date_dirs.sort(key=lambda x: x.name, reverse=True)
    
    # Look for canonical segments files in the latest directories
    for date_dir in date_dirs:
        canonical_file = date_dir / "segment_windows_from_bins.parquet"
        if canonical_file.exists():
            logger.info(f"Found canonical segments file: {canonical_file}")
            return str(canonical_file)
    
    logger.info("No canonical segments file found in any report directory")
    return None

def load_canonical_segments() -> Optional[pd.DataFrame]:
    """
    Load the latest canonical segments data.
    
    Returns:
        DataFrame with canonical segments or None if not found
    """
    canonical_file = find_latest_canonical_segments_file()
    if not canonical_file:
        logger.warning("No canonical segments file found")
        return None
    
    try:
        df = pd.read_parquet(canonical_file)
        logger.info(f"Loaded canonical segments: {len(df)} rows, {df.segment_id.nunique()} segments")
        return df
    except Exception as e:
        logger.error(f"Error loading canonical segments from {canonical_file}: {e}")
        return None

def get_segment_peak_densities() -> Dict[str, Dict[str, float]]:
    """
    Get peak densities for each segment from canonical data.
    
    Returns:
        Dict mapping segment_id to peak density metrics
    """
    df = load_canonical_segments()
    if df is None:
        logger.warning("No canonical segments data available, returning empty dict")
        return {}
    
    # Calculate peak densities per segment
    segment_peaks = {}
    for segment_id in df.segment_id.unique():
        seg_data = df[df.segment_id == segment_id]
        segment_peaks[segment_id] = {
            "peak_areal_density": float(seg_data.density_peak.max()),
            "peak_mean_density": float(seg_data.density_mean.max()),
            "total_windows": len(seg_data),
            "source": "canonical_segments"
        }
    
    logger.info(f"Extracted peak densities for {len(segment_peaks)} segments from canonical data")
    return segment_peaks

def get_segment_time_series() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get time series data for each segment from canonical data.
    
    Returns:
        Dict mapping segment_id to list of time windows with density data
    """
    df = load_canonical_segments()
    if df is None:
        logger.warning("No canonical segments data available, returning empty dict")
        return {}
    
    segment_series = {}
    for segment_id in df.segment_id.unique():
        seg_data = df[df.segment_id == segment_id].copy()
        
        # Convert timestamps to strings for JSON compatibility
        seg_data['t_start_str'] = seg_data['t_start'].dt.strftime('%Y-%m-%d %H:%M:%S')
        seg_data['t_end_str'] = seg_data['t_end'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Create time series list
        time_windows = []
        for _, row in seg_data.iterrows():
            time_windows.append({
                "t_start": row['t_start_str'],
                "t_end": row['t_end_str'],
                "density_mean": float(row['density_mean']),
                "density_peak": float(row['density_peak']),
                "n_bins": int(row['n_bins']) if pd.notna(row['n_bins']) else 0
            })
        
        segment_series[segment_id] = time_windows
    
    logger.info(f"Extracted time series for {len(segment_series)} segments from canonical data")
    return segment_series

def is_canonical_segments_available() -> bool:
    """
    Check if canonical segments data is available.
    
    Returns:
        True if canonical segments file exists and is readable
    """
    canonical_file = find_latest_canonical_segments_file()
    if not canonical_file:
        return False
    
    try:
        # Quick check - try to read the file
        df = pd.read_parquet(canonical_file)
        return len(df) > 0
    except Exception as e:
        logger.error(f"Canonical segments file exists but not readable: {e}")
        return False

def get_canonical_segments_metadata() -> Dict[str, Any]:
    """
    Get metadata about the canonical segments data.
    
    Returns:
        Dict with metadata about canonical segments
    """
    canonical_file = find_latest_canonical_segments_file()
    if not canonical_file:
        return {"available": False}
    
    try:
        df = pd.read_parquet(canonical_file)
        
        # Calculate metadata
        metadata = {
            "available": True,
            "file_path": canonical_file,
            "total_windows": len(df),
            "unique_segments": df.segment_id.nunique(),
            "segment_ids": sorted(df.segment_id.unique().tolist()),
            "time_range": {
                "start": df.t_start.min().isoformat(),
                "end": df.t_end.max().isoformat()
            },
            "density_range": {
                "min_mean": float(df.density_mean.min()),
                "max_mean": float(df.density_mean.max()),
                "min_peak": float(df.density_peak.min()),
                "max_peak": float(df.density_peak.max())
            },
            "source": "canonical_segments_from_bins",
            "methodology": "bottom_up_aggregation"
        }
        
        logger.info(f"Canonical segments metadata: {metadata['total_windows']} windows, {metadata['unique_segments']} segments")
        return metadata
        
    except Exception as e:
        logger.error(f"Error getting canonical segments metadata: {e}")
        return {"available": False, "error": str(e)}
