"""
Path utilities for Cloud Run compatibility.

This module provides utilities for managing output paths in a Cloud Run-friendly way,
ensuring all file writes go to writable directories.
"""

import os


def get_output_dir() -> str:
    """
    Get the output directory for reports and analysis files.
    
    In Cloud Run, only /tmp is writable, so we use OUTPUT_DIR environment variable
    with /tmp/analysis as the default. For local development, this can be set to
    reports/analysis to maintain existing behavior.
    
    Returns:
        str: The output directory path (will be created if it doesn't exist)
    """
    output_dir = os.getenv("OUTPUT_DIR", "/tmp/analysis")
    
    # Ensure the directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    return output_dir


def get_reports_dir() -> str:
    """
    Get the reports directory within the output directory.
    
    Returns:
        str: The reports directory path (will be created if it doesn't exist)
    """
    reports_dir = os.path.join(get_output_dir(), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def get_analysis_dir() -> str:
    """
    Get the analysis directory within the reports directory.
    
    Returns:
        str: The analysis directory path (will be created if it doesn't exist)
    """
    analysis_dir = os.path.join(get_reports_dir(), "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    return analysis_dir
