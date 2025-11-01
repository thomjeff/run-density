"""
Shared Utilities Module

Common functions used across multiple modules to avoid code duplication.
"""

from __future__ import annotations
from typing import Dict, Optional
import pandas as pd
from app.utils.constants import SECONDS_PER_MINUTE


def load_pace_csv(url_or_path: str) -> pd.DataFrame:
    """Load and validate pace CSV with proper column handling."""
    df = pd.read_csv(url_or_path)
    df.columns = [c.lower() for c in df.columns]
    
    # Ensure required columns exist
    expected = {"event", "runner_id", "pace", "distance"}
    if not expected.issubset(df.columns):
        raise ValueError(f"runners.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    
    # Handle optional start_offset column
    if "start_offset" not in df.columns:
        df["start_offset"] = 0
    
    # Convert to proper types
    df["event"] = df["event"].astype(str)
    df["runner_id"] = df["runner_id"].astype(str)
    df["pace"] = df["pace"].astype(float)      # minutes per km
    df["distance"] = df["distance"].astype(float)
    df["start_offset"] = df["start_offset"].fillna(0).astype(int)
    
    return df


def arrival_time_sec(start_min: float, start_offset_sec: int, km: float, pace_min_per_km: float) -> float:
    """Calculate arrival time at km mark including start offset."""
    return start_min * SECONDS_PER_MINUTE + start_offset_sec + pace_min_per_km * SECONDS_PER_MINUTE * km


def load_segments_csv(url_or_path: str) -> pd.DataFrame:
    """Load and validate segments CSV - supports both old and new formats."""
    df = pd.read_csv(url_or_path)
    
    # Check if this is the new format (segments_new.csv)
    if '10K' in df.columns and 'full' in df.columns:
        # New format - keep original column names
        expected = {"seg_id", "seg_label", "width_m", "direction", "full", "half", "10K",
                   "full_from_km", "full_to_km", "half_from_km", "half_to_km", 
                   "10K_from_km", "10K_to_km", "flow_type", 
                   "prior_segment_id", "notes"}
        if not expected.issubset(df.columns):
            raise ValueError(f"segments_new.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    else:
        # Old format - convert to lowercase
        df.columns = [c.lower() for c in df.columns]
        expected = {"seg_id", "eventa", "eventb", "from_km_a", "to_km_a", "from_km_b", "to_km_b", "flow_type"}
        if not expected.issubset(df.columns):
            raise ValueError(f"flow.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    
    # Convert to proper types (only for old format)
    df["seg_id"] = df["seg_id"].astype(str)
    
    # Only convert old format columns
    if 'eventa' in df.columns:
        df["eventa"] = df["eventa"].astype(str)
        df["eventb"] = df["eventb"].astype(str)
        df["from_km_a"] = df["from_km_a"].astype(float)
        df["to_km_a"] = df["to_km_a"].astype(float)
        df["from_km_b"] = df["from_km_b"].astype(float)
        df["to_km_b"] = df["to_km_b"].astype(float)
    
    return df
