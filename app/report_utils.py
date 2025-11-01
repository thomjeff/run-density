"""
Report Utilities Module

Provides common utilities for report generation including date-based folder organization
and consistent file naming conventions.
"""

from __future__ import annotations
import os
from datetime import datetime
from typing import Tuple

from app.paths import get_analysis_dir


def get_date_folder_path(base_path: str = "reports") -> Tuple[str, str]:
    """
    Get the date-based folder path for organizing reports.
    
    Args:
        base_path: Base directory for reports (default: "reports")
    
    Returns:
        Tuple of (full_path, date_folder_name)
        - full_path: Complete path including date folder
        - date_folder_name: Just the date folder name (YYYY-MM-DD)
    """
    # Create date folder name (YYYY-MM-DD format)
    date_folder = datetime.now().strftime("%Y-%m-%d")
    full_path = os.path.join(base_path, date_folder)
    
    # Ensure the date folder exists
    os.makedirs(full_path, exist_ok=True)
    
    return full_path, date_folder


def get_standard_filename(report_type: str, extension: str = "csv") -> str:
    """
    Generate standardized filename with consistent naming convention.
    
    Args:
        report_type: Type of report (Flow, Density, Combined, etc.)
        extension: File extension (csv, md, json, etc.)
    
    Returns:
        Standardized filename in format: YYYY-MM-DD-hhmm-[ReportType].[extension]
        Note: Uses hhmm instead of hh:mm to avoid filesystem path separator issues
    """
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    return f"{timestamp}-{report_type}.{extension}"


def get_report_paths(report_type: str, extension: str = "csv", base_path: str = None) -> Tuple[str, str]:
    """
    Get both the full file path and relative path for a report.
    
    Args:
        report_type: Type of report (Flow, Density, Combined, etc.)
        extension: File extension (csv, md, json, etc.)
        base_path: Base directory for reports (default: uses get_analysis_dir())
    
    Returns:
        Tuple of (full_path, relative_path)
        - full_path: Complete file path including date folder
        - relative_path: Relative path from base_path
    """
    # Use Cloud Run-friendly path if not specified
    if base_path is None:
        base_path = get_analysis_dir()
    
    # Get date-based folder
    date_folder_path, date_folder_name = get_date_folder_path(base_path)
    
    # Generate standardized filename
    filename = get_standard_filename(report_type, extension)
    
    # Create full path
    full_path = os.path.join(date_folder_path, filename)
    
    # Create relative path
    relative_path = os.path.join(date_folder_name, filename)
    
    return full_path, relative_path


def format_decimal_places(value: float, places: int = 2) -> float:
    """
    Format a decimal number to specified number of places.
    
    Args:
        value: The value to format
        places: Number of decimal places (default: 2)
    
    Returns:
        Formatted decimal number
    """
    if value is None or value == '':
        return value
    
    try:
        return round(float(value), places)
    except (ValueError, TypeError):
        return value
