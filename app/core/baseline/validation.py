"""
Baseline Validation Module

Validates runner CSV files and control variables.

Issue: #676 - Utility to create new runner files
"""

from pathlib import Path
from typing import Dict, Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def validate_runner_file(file_path: Path) -> None:
    """
    Validate runner CSV file structure and data.
    
    Args:
        file_path: Path to runner CSV file
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file structure or data is invalid
    
    Issue: #676 - CSV structure validation
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Runner file not found: {file_path}")
    
    # Read CSV with string dtype for runner_id
    try:
        df = pd.read_csv(file_path, dtype={"runner_id": "string"})
    except Exception as e:
        raise ValueError(f"Failed to read CSV file {file_path}: {e}")
    
    # Check required columns
    required = {"event", "runner_id", "pace", "distance"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Validate data types and ranges
    if df["pace"].min() <= 0:
        raise ValueError("Pace values must be positive")
    
    if df["pace"].max() > 30:  # Reasonable upper bound
        raise ValueError("Pace values exceed reasonable maximum (30 min/km)")
    
    # Check for duplicates
    if df["runner_id"].duplicated().any():
        raise ValueError("Duplicate runner_id values found")
    
    # Validate distance is consistent
    if df["distance"].nunique() > 1:
        raise ValueError("Distance must be the same for all runners")
    
    logger.info(f"Validated runner file: {file_path} ({len(df)} runners)")


def validate_control_variables(control_vars: Dict[str, Dict[str, float]]) -> None:
    """
    Validate control variables for scenario generation.
    
    Args:
        control_vars: Dictionary mapping event names to control variable dicts
    
    Raises:
        ValueError: If validation fails
    
    Issue: #676 - Control variable validation
    """
    required_fields = [
        "chg_participants",
        "chg_p00", "chg_p05", "chg_p25", "chg_p50",
        "chg_p75", "chg_p95", "chg_p100"
    ]
    
    for event_name, vars_dict in control_vars.items():
        # Check all required fields present
        missing = [f for f in required_fields if f not in vars_dict]
        if missing:
            raise ValueError(
                f"Event '{event_name}' missing required fields: {missing}"
            )
        
        # Validate ranges
        if vars_dict["chg_participants"] < -0.5 or vars_dict["chg_participants"] > 2.0:
            raise ValueError(
                f"chg_participants for '{event_name}' out of range (-50% to +200%)"
            )
        
        # Validate pace changes are reasonable (-50% to +200%)
        for field in ["chg_p00", "chg_p05", "chg_p25", "chg_p50", "chg_p75", "chg_p95", "chg_p100"]:
            chg_value = vars_dict[field]
            if chg_value < -0.5 or chg_value > 2.0:
                raise ValueError(
                    f"{field} for '{event_name}' out of range (-50% to +200%)"
                )
    
    logger.info(f"Validated control variables for {len(control_vars)} events")


def validate_cutoff_time_format(cutoff_str: str) -> float:
    """
    Validate and convert cut-off time from hh:mm format to minutes.
    
    Args:
        cutoff_str: Cut-off time in "hh:mm" format (e.g., "06:00")
    
    Returns:
        Cut-off time in minutes (e.g., 360.0 for "06:00")
    
    Raises:
        ValueError: If format is invalid
    
    Issue: #676 - Cut-off time validation
    """
    try:
        parts = cutoff_str.split(":")
        if len(parts) != 2:
            raise ValueError("Cut-off time must be in hh:mm format")
        
        hours = int(parts[0])
        minutes = int(parts[1])
        
        if hours < 0 or hours > 23:
            raise ValueError("Hours must be between 0 and 23")
        if minutes < 0 or minutes > 59:
            raise ValueError("Minutes must be between 0 and 59")
        
        total_minutes = hours * 60 + minutes
        return float(total_minutes)
    
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid cut-off time format '{cutoff_str}': {e}")
