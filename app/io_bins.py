"""
Canonical Bins I/O Module

This module provides utilities for loading and normalizing canonical bins data
from parquet or geojson.gz files. It ensures consistent data types and computes
derived fields like bin_len_m.

Issue #233: Operational Intelligence - Canonical Bins Loader
"""

from __future__ import annotations
import gzip
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def find_canonical_bins_file(
    parquet_path: Optional[str] = None,
    geojson_path: Optional[str] = None,
    reports_dir: str = "reports"
) -> Tuple[Optional[str], str]:
    """
    Find the latest canonical bins file (parquet or geojson.gz).
    
    Args:
        parquet_path: Explicit path to parquet file (optional)
        geojson_path: Explicit path to geojson.gz file (optional)
        reports_dir: Base reports directory to search
        
    Returns:
        Tuple of (file_path, file_type) where file_type is 'parquet' or 'geojson'
        Returns (None, '') if no file found
    """
    # Check explicit paths first
    if parquet_path and Path(parquet_path).exists():
        logger.info(f"Found canonical bins parquet at explicit path: {parquet_path}")
        return (parquet_path, 'parquet')
    
    if geojson_path and Path(geojson_path).exists():
        logger.info(f"Found canonical bins geojson at explicit path: {geojson_path}")
        return (geojson_path, 'geojson')
    
    # Search in reports directory
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        logger.warning(f"Reports directory not found: {reports_dir}")
        return (None, '')
    
    # Find all date directories (YYYY-MM-DD format)
    date_dirs = [
        d for d in reports_path.iterdir()
        if d.is_dir() and len(d.name) == 10 and d.name.count('-') == 2
    ]
    
    if not date_dirs:
        logger.warning(f"No date directories found in {reports_dir}")
        return (None, '')
    
    # Sort by date (newest first)
    date_dirs.sort(key=lambda x: x.name, reverse=True)
    
    # Look for canonical bins files in the latest directories
    for date_dir in date_dirs:
        # Try parquet first (primary format)
        parquet_candidates = [
            date_dir / "segment_windows_from_bins.parquet",
            date_dir / "bins.parquet"
        ]
        
        for parquet_file in parquet_candidates:
            if parquet_file.exists():
                logger.info(f"Found canonical bins parquet: {parquet_file}")
                return (str(parquet_file), 'parquet')
        
        # Try geojson.gz as fallback
        geojson_file = date_dir / "bins.geojson.gz"
        if geojson_file.exists():
            logger.info(f"Found canonical bins geojson.gz: {geojson_file}")
            return (str(geojson_file), 'geojson')
    
    # Check root reports directory for bins files
    root_parquet = reports_path / "bins.parquet"
    if root_parquet.exists():
        logger.info(f"Found canonical bins parquet in root: {root_parquet}")
        return (str(root_parquet), 'parquet')
    
    root_geojson = reports_path / "bins.geojson.gz"
    if root_geojson.exists():
        logger.info(f"Found canonical bins geojson.gz in root: {root_geojson}")
        return (str(root_geojson), 'geojson')
    
    logger.warning("No canonical bins file found")
    return (None, '')


def load_bins_from_parquet(file_path: str) -> Optional[pd.DataFrame]:
    """
    Load canonical bins from parquet file.
    
    Args:
        file_path: Path to parquet file
        
    Returns:
        DataFrame with canonical bins or None on error
    """
    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded {len(df)} bins from parquet: {file_path}")
        return df
    except Exception as e:
        logger.error(f"Error loading parquet {file_path}: {e}")
        return None


def load_bins_from_geojson(file_path: str) -> Optional[pd.DataFrame]:
    """
    Load canonical bins from geojson.gz file.
    
    Args:
        file_path: Path to geojson.gz file
        
    Returns:
        DataFrame with canonical bins or None on error
    """
    try:
        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            geojson_data = json.load(f)
        
        # Extract features and convert to DataFrame
        features = geojson_data.get('features', [])
        if not features:
            logger.warning(f"No features found in geojson: {file_path}")
            return None
        
        # Extract properties from each feature
        records = []
        for feature in features:
            props = feature.get('properties', {})
            if props:
                records.append(props)
        
        if not records:
            logger.warning(f"No properties found in geojson features: {file_path}")
            return None
        
        df = pd.DataFrame(records)
        logger.info(f"Loaded {len(df)} bins from geojson: {file_path}")
        return df
        
    except Exception as e:
        logger.error(f"Error loading geojson {file_path}: {e}")
        return None


def normalize_bins_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize data types for canonical bins DataFrame.
    
    Args:
        df: Raw bins DataFrame
        
    Returns:
        DataFrame with normalized dtypes
    """
    # Define expected dtypes for canonical bins
    dtype_conversions = {
        'segment_id': 'string',
        'start_km': 'float64',
        'end_km': 'float64',
        'density': 'float64',
        'density_mean': 'float64',
        'density_peak': 'float64',
        'n_bins': 'Int64',  # Nullable integer
    }
    
    # Apply conversions for columns that exist
    for col, dtype in dtype_conversions.items():
        if col in df.columns:
            try:
                df[col] = df[col].astype(dtype)
            except Exception as e:
                logger.warning(f"Could not convert {col} to {dtype}: {e}")
    
    # Handle bins.parquet schema: 'density' column -> 'density_peak' for consistency
    if 'density' in df.columns and 'density_peak' not in df.columns:
        df['density_peak'] = df['density']
        df['density_mean'] = df['density']  # Assume peak = mean for bins
        logger.debug("Normalized 'density' column to 'density_peak' and 'density_mean'")
    
    # Handle timestamp columns
    timestamp_cols = ['t_start', 't_end']
    for col in timestamp_cols:
        if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
            try:
                df[col] = pd.to_datetime(df[col])
            except Exception as e:
                logger.warning(f"Could not convert {col} to datetime: {e}")
    
    logger.debug("Normalized bins dtypes")
    return df


def compute_bin_length(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute bin_len_m from start_km and end_km.
    
    Args:
        df: Bins DataFrame with start_km and end_km columns
        
    Returns:
        DataFrame with added bin_len_m column
    """
    if 'start_km' not in df.columns or 'end_km' not in df.columns:
        logger.warning("Cannot compute bin_len_m: missing start_km or end_km")
        return df
    
    try:
        # Compute length in meters
        df['bin_len_m'] = (df['end_km'] - df['start_km']) * 1000.0
        
        # Ensure non-negative lengths
        df['bin_len_m'] = df['bin_len_m'].clip(lower=0.0)
        
        logger.debug(f"Computed bin_len_m: range [{df['bin_len_m'].min():.1f}, {df['bin_len_m'].max():.1f}] meters")
        
    except Exception as e:
        logger.error(f"Error computing bin_len_m: {e}")
    
    return df


def validate_bins_schema(df: pd.DataFrame) -> bool:
    """
    Validate that bins DataFrame has required columns.
    
    Args:
        df: Bins DataFrame to validate
        
    Returns:
        True if schema is valid, False otherwise
    """
    required_columns = [
        'segment_id',
        'start_km',
        'end_km'
    ]
    
    # Need at least one density column
    density_columns = ['density', 'density_mean', 'density_peak']
    has_density = any(col in df.columns for col in density_columns)
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        logger.error(f"Missing required columns in bins data: {missing_columns}")
        return False
    
    if not has_density:
        logger.error(f"Missing density column - need one of: {density_columns}")
        return False
    
    logger.debug("Bins schema validation passed")
    return True


def load_bins(
    parquet_path: Optional[str] = None,
    geojson_path: Optional[str] = None,
    reports_dir: str = "reports",
    validate: bool = True
) -> Optional[pd.DataFrame]:
    """
    Load canonical bins from parquet or geojson.gz with full normalization.
    
    This is the primary entry point for loading canonical bins data.
    
    Args:
        parquet_path: Explicit path to parquet file (optional)
        geojson_path: Explicit path to geojson.gz file (optional)
        reports_dir: Base reports directory to search
        validate: Whether to validate schema (default: True)
        
    Returns:
        Normalized DataFrame with canonical bins or None on error
    """
    # Find the canonical bins file
    file_path, file_type = find_canonical_bins_file(
        parquet_path=parquet_path,
        geojson_path=geojson_path,
        reports_dir=reports_dir
    )
    
    if not file_path:
        logger.error("No canonical bins file found")
        return None
    
    # Load based on file type
    if file_type == 'parquet':
        df = load_bins_from_parquet(file_path)
    elif file_type == 'geojson':
        df = load_bins_from_geojson(file_path)
    else:
        logger.error(f"Unknown file type: {file_type}")
        return None
    
    if df is None:
        logger.error("Failed to load bins data")
        return None
    
    # Validate schema if requested
    if validate and not validate_bins_schema(df):
        logger.error("Bins schema validation failed")
        return None
    
    # Normalize data types
    df = normalize_bins_dtypes(df)
    
    # Compute derived fields
    df = compute_bin_length(df)
    
    logger.info(f"Successfully loaded and normalized {len(df)} canonical bins")
    return df


def get_bins_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract metadata from canonical bins DataFrame.
    
    Args:
        df: Canonical bins DataFrame
        
    Returns:
        Dictionary with bins metadata
    """
    metadata = {
        'total_bins': len(df),
        'unique_segments': df['segment_id'].nunique() if 'segment_id' in df.columns else 0,
        'density_range': {
            'min_mean': float(df['density_mean'].min()) if 'density_mean' in df.columns else None,
            'max_mean': float(df['density_mean'].max()) if 'density_mean' in df.columns else None,
            'min_peak': float(df['density_peak'].min()) if 'density_peak' in df.columns else None,
            'max_peak': float(df['density_peak'].max()) if 'density_peak' in df.columns else None,
        },
        'distance_range': {
            'min_km': float(df['start_km'].min()) if 'start_km' in df.columns else None,
            'max_km': float(df['end_km'].max()) if 'end_km' in df.columns else None,
        },
        'bin_length_stats': {
            'mean_m': float(df['bin_len_m'].mean()) if 'bin_len_m' in df.columns else None,
            'min_m': float(df['bin_len_m'].min()) if 'bin_len_m' in df.columns else None,
            'max_m': float(df['bin_len_m'].max()) if 'bin_len_m' in df.columns else None,
        }
    }
    
    # Add time range if available
    if 't_start' in df.columns and 't_end' in df.columns:
        metadata['time_range'] = {
            'start': df['t_start'].min().isoformat() if pd.notna(df['t_start'].min()) else None,
            'end': df['t_end'].max().isoformat() if pd.notna(df['t_end'].max()) else None,
        }
    
    return metadata

