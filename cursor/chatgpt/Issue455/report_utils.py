"""
Report Utilities Module

Provides common utilities for report generation including date-based folder organization
and consistent file naming conventions.

Issue #455 Phase 3: Added runflow UUID-based path utilities.
"""

from __future__ import annotations
import os
from datetime import datetime
from typing import Tuple
from pathlib import Path

from app.paths import get_analysis_dir
from app.utils.constants import RUNFLOW_ROOT_CONTAINER, RUNFLOW_ROOT_LOCAL


def get_date_folder_path(base_path: str = "reports") -> Tuple[str, str]:
    """
    Get the date-based folder path for organizing reports.
    
    Args:
        base_path: Base directory for reports (default: "reports")
    
    Returns:
        Tuple of (full_path, date_folder_name)
        - full_path: Complete path including date folder
        - date_folder_name: Just the date folder name (YYYY-MM-DD)
    
    Issue #455: If base_path is already a runflow path (contains /runflow/),
    returns it as-is without adding date subfolder.
    """
    # Issue #455: Surgical update - detect runflow mode
    # If base_path looks like a runflow path, don't add date subfolder
    if "/runflow/" in base_path or base_path.startswith("runflow/"):
        # Already in runflow structure, return as-is
        # Use base_path basename as the "folder name" for compatibility
        return base_path, os.path.basename(base_path)
    
    # Legacy behavior: Create date folder name (YYYY-MM-DD format)
    date_folder = datetime.now().strftime("%Y-%m-%d")
    full_path = os.path.join(base_path, date_folder)
    
    # Ensure the date folder exists
    os.makedirs(full_path, exist_ok=True)
    
    return full_path, date_folder


def get_standard_filename(report_type: str, extension: str = "csv", use_runflow: bool = False) -> str:
    """
    Generate standardized filename with consistent naming convention.
    
    Args:
        report_type: Type of report (Flow, Density, Combined, etc.)
        extension: File extension (csv, md, json, etc.)
        use_runflow: If True, use generic name without timestamp (Issue #455)
    
    Returns:
        Standardized filename in format: YYYY-MM-DD-hhmm-[ReportType].[extension]
        Or if use_runflow=True: [ReportType].[extension]
        Note: Uses hhmm instead of hh:mm to avoid filesystem path separator issues
    
    Issue #455: When use_runflow=True, returns generic filename (e.g., "Density.md")
    """
    if use_runflow:
        # Issue #455: Generic filename without timestamp for runflow structure
        return f"{report_type}.{extension}"
    else:
        # Legacy: Timestamp-prefixed filename
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
    
    Issue #455: Detects runflow mode and uses generic filenames without timestamps
    """
    # Use Cloud Run-friendly path if not specified
    if base_path is None:
        base_path = get_analysis_dir()
    
    # Issue #455: Detect runflow mode
    is_runflow = "/runflow/" in base_path or base_path.startswith("runflow/")
    
    # Get date-based folder (or runflow folder if in runflow mode)
    date_folder_path, date_folder_name = get_date_folder_path(base_path)
    
    # Generate standardized filename (without timestamp if runflow)
    filename = get_standard_filename(report_type, extension, use_runflow=is_runflow)
    
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


# ============================================================================
# Runflow UUID-Based Path Utilities (Issue #455 Phase 3)
# ============================================================================

def get_runflow_root() -> str:
    """
    Get the runflow root directory based on environment.
    
    Returns:
        Path to runflow root directory
    
    Examples:
        In Docker container: /runflow
        Local development: /users/jthompson/documents/runflow
    
    Issue #455: Adapted from commit c8cfb3e (Epic #444 Phase 3)
    """
    # Check if running in container (has /app directory)
    if Path("/app").exists():
        return RUNFLOW_ROOT_CONTAINER
    else:
        return RUNFLOW_ROOT_LOCAL


def get_run_folder_path(run_id: str) -> str:
    """
    Get the runflow folder path for a specific run ID.
    
    Args:
        run_id: Short UUID run identifier
    
    Returns:
        Complete path to run folder
    
    Example:
        >>> get_run_folder_path("p0ZoB1FwH6")
        '/runflow/p0ZoB1FwH6'
    
    Issue #455: Creates parent directory for all run outputs
    """
    runflow_root = get_runflow_root()
    full_path = os.path.join(runflow_root, run_id)
    
    # Ensure the run folder exists
    os.makedirs(full_path, exist_ok=True)
    
    return full_path


def get_runflow_category_path(run_id: str, category: str) -> str:
    """
    Get path to a category subdirectory within a run folder.
    
    Args:
        run_id: Short UUID run identifier
        category: Category name (reports, bins, maps, heatmaps, ui)
    
    Returns:
        Full path to category directory
    
    Example:
        >>> get_runflow_category_path("p0ZoB1FwH6", "reports")
        '/runflow/p0ZoB1FwH6/reports'
    
    Issue #455: Creates category subdirectories as needed
    """
    run_path = get_run_folder_path(run_id)
    category_path = os.path.join(run_path, category)
    
    # Ensure category directory exists
    os.makedirs(category_path, exist_ok=True)
    
    return category_path


def get_runflow_file_path(run_id: str, category: str, filename: str) -> str:
    """
    Get full file path in runflow structure.
    
    Args:
        run_id: Short UUID run identifier
        category: Category name (reports, bins, maps, heatmaps, ui)
        filename: File name (without timestamp prefix - Issue #455)
    
    Returns:
        Complete file path
    
    Examples:
        >>> get_runflow_file_path("p0ZoB1FwH6", "reports", "Density.md")
        '/runflow/p0ZoB1FwH6/reports/Density.md'
    
    Issue #455: Generic filenames without timestamps
    """
    category_path = get_runflow_category_path(run_id, category)
    full_path = os.path.join(category_path, filename)
    
    return full_path


def get_runflow_report_filename(report_type: str, extension: str = "md") -> str:
    """
    Generate runflow report filename (no timestamp prefix - Issue #455).
    
    Args:
        report_type: Type of report (Flow, Density, etc.)
        extension: File extension (md, csv, json)
    
    Returns:
        Generic filename: "<ReportType>.<extension>"
    
    Examples:
        >>> get_runflow_report_filename("Density", "md")
        'Density.md'
        >>> get_runflow_report_filename("Flow", "csv")
        'Flow.csv'
    
    Note:
        Unlike legacy get_standard_filename(), this does NOT include
        timestamps. Temporal tracking is via metadata.json created_at field.
    
    Issue #455: Simplified naming convention for UUID-based runs
    """
    return f"{report_type}.{extension}"
