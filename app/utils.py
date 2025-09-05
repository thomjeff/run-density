"""
Shared Utilities Module

Common functions used across multiple modules to avoid code duplication.
"""

from __future__ import annotations
from typing import Dict, Optional
import pandas as pd
from .constants import SECONDS_PER_MINUTE


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
    """Load and validate segments CSV."""
    df = pd.read_csv(url_or_path)
    df.columns = [c.lower() for c in df.columns]
    
    # Ensure required columns exist for segments_new.csv schema
    expected = {"seg_id", "seg_label", "width_m", "direction", "full", "half", "10k", "overtake_flag"}
    if not expected.issubset(df.columns):
        raise ValueError(f"segments_new.csv must have columns {sorted(expected)}; got {df.columns.tolist()}")
    
    # Convert to proper types
    df["seg_id"] = df["seg_id"].astype(str)
    df["seg_label"] = df["seg_label"].astype(str)
    df["width_m"] = df["width_m"].astype(float)
    df["direction"] = df["direction"].astype(str)
    df["full"] = df["full"].astype(str)
    df["half"] = df["half"].astype(str)
    df["10k"] = df["10k"].astype(str)
    
    # Convert event distance columns to float, handling empty values
    for col in ["full_from_km", "full_to_km", "half_from_km", "half_to_km", "10k_from_km", "10k_to_km"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df
